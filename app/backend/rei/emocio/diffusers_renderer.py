"""Lazy local Diffusers adapter behind the provider-neutral B7 contract.

Importing this module never imports Torch, loads model weights, or touches a
device.  The optional stack is imported only when ``LazyDiffusersBackend`` is
actually asked to render.
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import re
import stat
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self, runtime_checkable

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id, utc_now
from ..models.common import (
    ArtifactRelativePath,
    CommitDigest,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from ..models.emocio import ImageArtifact
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_contract,
)
from ..models.rendering import (
    ImageConditioningMethod,
    ImagePipelineSpec,
    ImageRenderItemOutcome,
    ImageRenderMode,
    ImageRenderRequest,
)
from .artifacts import LocalPngArtifactStore, inspect_png


DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME = ".rei_snapshot_manifest.json"
RENDERER_TIMEOUT_FAILURE_CODE = "renderer_timeout"


class _CooperativeDeadline:
    """Monotonic deadline checked only at explicit safe interruption points.

    Diffusers does not expose hard cancellation for an in-flight CUDA kernel or
    model load.  This guard therefore stops work before/after load operations
    and at diffusion-step boundaries without claiming stronger cancellation.
    """

    def __init__(self, timeout_seconds: float) -> None:
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Renderer timeout must be finite and positive")
        self._expires_at = time.monotonic() + timeout_seconds

    def check(self, stage: str) -> None:
        if time.monotonic() >= self._expires_at:
            raise TimeoutError(
                "Cooperative renderer deadline exceeded during " + stage
            )


class DiffusersSnapshotFile(FrozenModel):
    """One immutable file entry in a local Diffusers snapshot manifest."""

    relative_path: ArtifactRelativePath
    sha256: HashDigest
    size_bytes: Annotated[int, Field(ge=0)]


class DiffusersSnapshotManifest(FrozenModel):
    """Canonical inventory that closes a local model snapshot byte-for-byte."""

    schema_version: Literal["rei-diffusers-snapshot-manifest-v1"] = (
        "rei-diffusers-snapshot-manifest-v1"
    )
    repo_id: NonEmptyId
    revision: CommitDigest
    files: tuple[DiffusersSnapshotFile, ...]

    @model_validator(mode="after")
    def validate_files(self) -> Self:
        paths = tuple(item.relative_path for item in self.files)
        if not paths:
            raise ValueError("Diffusers snapshot manifest requires at least one file")
        if len(set(paths)) != len(paths):
            raise ValueError("Diffusers snapshot manifest file paths must be unique")
        if paths != tuple(sorted(paths)):
            raise ValueError("Diffusers snapshot manifest files must be path-sorted")
        if DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME in paths:
            raise ValueError("Diffusers snapshot manifest cannot inventory itself")
        if any(path.split("/", 1)[0] == ".cache" for path in paths):
            raise ValueError(
                "Diffusers snapshot manifest excludes transient .cache files"
            )
        return self


def canonical_snapshot_manifest_bytes(
    manifest: DiffusersSnapshotManifest,
) -> bytes:
    """Serialize the manifest exactly as the verifier hashes it."""

    return canonical_json_bytes(manifest)


def _file_sha256(
    path: Path,
    *,
    deadline: _CooperativeDeadline | None = None,
) -> str:
    digest = hashlib.sha256()
    if deadline is not None:
        deadline.check("snapshot_file_hash_open")
    with path.open("rb") as source:
        while True:
            if deadline is not None:
                deadline.check("snapshot_file_hash_read")
            chunk = source.read(4 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    if deadline is not None:
        deadline.check("snapshot_file_hash_complete")
    return digest.hexdigest()


def _is_forbidden_snapshot_link(path: Path) -> bool:
    """Reject symlinks and Windows reparse points before any file filtering."""

    metadata = os.lstat(path)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        reparse_attribute and file_attributes & reparse_attribute
    )


def build_diffusers_snapshot_manifest(
    snapshot_path: str | Path,
    *,
    repo_id: str,
    revision: str,
) -> DiffusersSnapshotManifest:
    """Inventory a completed local snapshot, excluding manifest/cache metadata."""

    try:
        snapshot_root = Path(snapshot_path).resolve(strict=True)
    except OSError as exc:
        raise ValueError("Local Diffusers snapshot does not exist") from exc
    if not snapshot_root.is_dir():
        raise ValueError("Local Diffusers snapshot is not a directory")
    paths: list[Path] = []
    candidates = sorted(
        snapshot_root.rglob("*"),
        key=lambda path: path.relative_to(snapshot_root).as_posix(),
    )
    for path in candidates:
        relative_path = path.relative_to(snapshot_root)
        if _is_forbidden_snapshot_link(path):
            raise ValueError(
                "Local Diffusers snapshot forbids symbolic links and reparse "
                f"points: {relative_path.as_posix()}"
            )
        try:
            resolved_path = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                "Local Diffusers snapshot entry is unreadable: "
                f"{relative_path.as_posix()}"
            ) from exc
        if not resolved_path.is_relative_to(snapshot_root):
            raise ValueError(
                "Local Diffusers snapshot entry resolves outside its root: "
                f"{relative_path.as_posix()}"
            )
        if relative_path.parts[0] == ".cache":
            continue
        if relative_path.as_posix() == DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME:
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(
                "Local Diffusers snapshot contains an unsupported entry: "
                f"{relative_path.as_posix()}"
            )
        paths.append(path)
    return DiffusersSnapshotManifest(
        repo_id=repo_id,
        revision=revision,
        files=tuple(
            DiffusersSnapshotFile(
                relative_path=path.relative_to(snapshot_root).as_posix(),
                sha256=_file_sha256(path),
                size_bytes=path.stat().st_size,
            )
            for path in paths
        ),
    )


@runtime_checkable
class DiffusionBackend(Protocol):
    """Minimal byte-returning seam used by deterministic tests and Diffusers."""

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes: ...


@runtime_checkable
class TimedDiffusionBackend(Protocol):
    """Optional cooperative-timeout capability for renderer backends."""

    def render_with_timeout(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
        timeout_seconds: float,
    ) -> bytes: ...


class DiffusersRuntimeConfig(FrozenModel):
    """Explicit local execution settings; no model is selected here."""

    device: NonEmptyText
    torch_dtype: Literal["float16", "bfloat16", "float32"]
    local_files_only: Literal[True]
    variant: NonEmptyText | None = None
    enable_attention_slicing: bool
    enable_model_cpu_offload: bool = False
    pipeline_family: Literal["auto", "flux2_klein"] = "auto"
    local_snapshot_path: NonEmptyText | None = None
    expected_snapshot_manifest_sha256: HashDigest | None = None

    @model_validator(mode="after")
    def validate_local_snapshot(self) -> Self:
        has_path = self.local_snapshot_path is not None
        has_digest = self.expected_snapshot_manifest_sha256 is not None
        if has_path != has_digest:
            raise ValueError(
                "local_snapshot_path and expected manifest SHA-256 are required "
                "together"
            )
        if self.local_snapshot_path is not None and not Path(
            self.local_snapshot_path
        ).is_absolute():
            raise ValueError("local_snapshot_path must be an explicit absolute path")
        if self.enable_model_cpu_offload and self.device != "cuda":
            raise ValueError("Model CPU offload requires the CUDA execution device")
        return self

    def conditioning_method(
        self,
        mode: ImageRenderMode,
    ) -> ImageConditioningMethod:
        if mode == "text_to_image":
            return "none"
        if self.pipeline_family == "flux2_klein":
            return "reference_image"
        return "classic_strength"

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        if self.pipeline_family == "flux2_klein":
            pipeline = "diffusers.Flux2KleinPipeline"
        else:
            pipeline = (
                "diffusers.AutoPipelineForText2Image"
                if mode == "text_to_image"
                else "diffusers.AutoPipelineForImage2Image"
            )
        values = {
            "conditioning_method": self.conditioning_method(mode),
            "device": self.device,
            "enable_attention_slicing": self.enable_attention_slicing,
            "enable_model_cpu_offload": self.enable_model_cpu_offload,
            "generator_device": (
                "cpu" if self.enable_model_cpu_offload else self.device
            ),
            "guidance_behavior": (
                "stepwise_distilled_ignored"
                if self.pipeline_family == "flux2_klein"
                else "pipeline_defined"
            ),
            "local_files_only": self.local_files_only,
            "load_source": (
                "verified_local_snapshot"
                if self.local_snapshot_path is not None
                else "huggingface_cache_exact_revision"
            ),
            "negative_prompt_argument": self.pipeline_family != "flux2_klein",
            "pipeline_family": self.pipeline_family,
            "snapshot_manifest_sha256": self.expected_snapshot_manifest_sha256,
            "snapshot_path_provenance": (
                "absolute_machine_path_explicit_in_runtime_config_but_excluded_from_"
                "portable_request_identity"
                if self.local_snapshot_path is not None
                else "not_applicable"
            ),
            "torch_dtype": self.torch_dtype,
            "timeout_enforcement_mode": "cooperative_monotonic_deadline",
            "timeout_hard_cancellation": False,
            "timeout_interruption_points": (
                "snapshot_verification",
                "before_and_after_pipeline_load",
                "each_diffusion_step_end",
                "before_and_after_inference",
            ),
            "use_safetensors": True,
            "variant": self.variant,
        }
        return ImagePipelineSpec(
            implementation=pipeline,
            implementation_revision="0.39.0",
            parameters=tuple(
                ProviderParameter(
                    name=name,
                    canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
                )
                for name, value in sorted(values.items())
            ),
        )


class LazyDiffusersBackend:
    """Load exact-revision Diffusers pipelines only on the first real call."""

    def __init__(self, config: DiffusersRuntimeConfig) -> None:
        self._config = config
        self._pipelines: dict[tuple[str, str, str], object] = {}
        self._verified_snapshots: dict[tuple[str, str, str], Path] = {}
        self._lock = threading.RLock()

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        return self._config.pipeline_spec(mode)

    def _verified_load_target(
        self,
        *,
        model: str,
        revision: str,
        deadline: _CooperativeDeadline | None = None,
    ) -> Path | None:
        if deadline is not None:
            deadline.check("snapshot_verification_start")
        snapshot_value = self._config.local_snapshot_path
        expected_digest = self._config.expected_snapshot_manifest_sha256
        if snapshot_value is None or expected_digest is None:
            if deadline is not None:
                deadline.check("snapshot_verification_not_configured")
            return None
        cache_key = (model, revision, expected_digest)
        cached = self._verified_snapshots.get(cache_key)
        if cached is not None:
            if deadline is not None:
                deadline.check("snapshot_verification_cache_hit")
            return cached

        try:
            snapshot_root = Path(snapshot_value).resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                "Configured local Diffusers snapshot does not exist"
            ) from exc
        if not snapshot_root.is_dir():
            raise ValueError("Configured local Diffusers snapshot is not a directory")
        manifest_path = snapshot_root / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
        if deadline is not None:
            deadline.check("snapshot_manifest_read_start")
        try:
            manifest_bytes = manifest_path.read_bytes()
        except OSError as exc:
            raise ValueError("Local Diffusers snapshot manifest is unreadable") from exc
        if deadline is not None:
            deadline.check("snapshot_manifest_read_complete")
        actual_manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
        if deadline is not None:
            deadline.check("snapshot_manifest_hash_complete")
        if actual_manifest_digest != expected_digest:
            raise ValueError(
                "Local Diffusers snapshot manifest SHA-256 differs from runtime config"
            )
        try:
            manifest = DiffusersSnapshotManifest.model_validate_json(manifest_bytes)
        except Exception as exc:
            raise ValueError("Local Diffusers snapshot manifest is invalid") from exc
        if deadline is not None:
            deadline.check("snapshot_manifest_validation_complete")
        if manifest_bytes != canonical_snapshot_manifest_bytes(manifest):
            raise ValueError("Local Diffusers snapshot manifest is not canonical JSON")
        if manifest.repo_id != model:
            raise ValueError(
                "Local Diffusers snapshot repo_id differs from provider model"
            )
        if manifest.revision != revision:
            raise ValueError(
                "Local Diffusers snapshot revision differs from provider revision"
            )

        expected_paths = {item.relative_path for item in manifest.files}
        actual_paths: set[str] = set()
        for path in snapshot_root.rglob("*"):
            if deadline is not None:
                deadline.check("snapshot_inventory_scan")
            relative_path = path.relative_to(snapshot_root)
            try:
                if _is_forbidden_snapshot_link(path):
                    raise ValueError(
                        "Local Diffusers snapshot forbids symbolic links and "
                        f"reparse points: {relative_path.as_posix()}"
                    )
                resolved_path = path.resolve(strict=True)
            except OSError as exc:
                raise ValueError(
                    "Local Diffusers snapshot entry is unreadable: "
                    f"{relative_path.as_posix()}"
                ) from exc
            if not resolved_path.is_relative_to(snapshot_root):
                raise ValueError(
                    "Local Diffusers snapshot entry resolves outside its root: "
                    f"{relative_path.as_posix()}"
                )
            if relative_path.parts[0] == ".cache":
                continue
            if path == manifest_path:
                continue
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError(
                    "Local Diffusers snapshot contains an unsupported entry: "
                    f"{relative_path.as_posix()}"
                )
            actual_paths.add(relative_path.as_posix())
        if deadline is not None:
            deadline.check("snapshot_inventory_complete")
        if actual_paths != expected_paths:
            missing = sorted(expected_paths - actual_paths)
            unexpected = sorted(actual_paths - expected_paths)
            detail = f"missing={missing[:3]}, unexpected={unexpected[:3]}"
            raise ValueError(f"Local Diffusers snapshot inventory differs: {detail}")
        for entry in manifest.files:
            if deadline is not None:
                deadline.check("snapshot_file_verification_start")
            file_path = snapshot_root.joinpath(*entry.relative_path.split("/"))
            try:
                resolved_file = file_path.resolve(strict=True)
                if not resolved_file.is_relative_to(snapshot_root):
                    raise ValueError(
                        "Local Diffusers snapshot file resolves outside its root: "
                        f"{entry.relative_path}"
                    )
                size_bytes = file_path.stat().st_size
            except OSError as exc:
                raise ValueError(
                    "Local Diffusers snapshot file is unreadable: "
                    f"{entry.relative_path}"
                ) from exc
            if size_bytes != entry.size_bytes:
                raise ValueError(
                    f"Local Diffusers snapshot file size differs: {entry.relative_path}"
                )
            if _file_sha256(file_path, deadline=deadline) != entry.sha256:
                raise ValueError(
                    "Local Diffusers snapshot file SHA-256 differs: "
                    f"{entry.relative_path}"
                )
        if deadline is not None:
            deadline.check("snapshot_verification_complete")
        self._verified_snapshots[cache_key] = snapshot_root
        return snapshot_root

    def _pipeline(
        self,
        request: ImageRenderRequest,
        *,
        deadline: _CooperativeDeadline | None = None,
    ) -> tuple[object, object, object]:
        if deadline is not None:
            deadline.check("pipeline_resolution_start")
        if not request.provider.uses_model:
            raise ValueError("Diffusers requires a model-backed provider identity")
        model = request.provider.model
        revision = request.provider.model_revision
        if model is None or revision is None:
            raise ValueError("Diffusers requires an exact model and revision")

        expected_pipeline = self.pipeline_spec(request.mode)
        if request.pipeline != expected_pipeline:
            raise ValueError("Render request pipeline differs from Diffusers runtime")

        local_load_target = self._verified_load_target(
            model=model,
            revision=revision,
            deadline=deadline,
        )

        if deadline is not None:
            deadline.check("renderer_runtime_import_start")
        try:
            from importlib.metadata import version

            import torch
            import diffusers
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError(
                "Install app/backend/requirements-renderer.txt before rendering"
            ) from exc
        if deadline is not None:
            deadline.check("renderer_runtime_import_complete")

        installed_diffusers = version("diffusers")
        if installed_diffusers != expected_pipeline.implementation_revision:
            raise RuntimeError(
                "Installed Diffusers version differs from approved pipeline revision"
            )

        cache_key = (model, revision, expected_pipeline.implementation)
        pipeline = self._pipelines.get(cache_key)
        if pipeline is None:
            dtype = getattr(torch, self._config.torch_dtype)
            pipeline_name = expected_pipeline.implementation.rsplit(".", 1)[-1]
            pipeline_type = getattr(diffusers, pipeline_name, None)
            if pipeline_type is None:
                raise RuntimeError(
                    f"Installed Diffusers has no approved pipeline {pipeline_name}"
                )
            load_options: dict[str, object] = {
                "torch_dtype": dtype,
                "use_safetensors": True,
                "local_files_only": self._config.local_files_only,
            }
            if local_load_target is None:
                load_target = model
                load_options["revision"] = revision
            else:
                load_target = str(local_load_target)
            if self._config.variant is not None:
                load_options["variant"] = self._config.variant
            if deadline is not None:
                deadline.check("pipeline_load_start")
            pipeline = pipeline_type.from_pretrained(load_target, **load_options)
            if deadline is not None:
                deadline.check("pipeline_load_complete")
            if self._config.enable_model_cpu_offload:
                enable_offload = getattr(pipeline, "enable_model_cpu_offload", None)
                if not callable(enable_offload):
                    raise RuntimeError(
                        "Approved Diffusers pipeline cannot enable model CPU offload"
                    )
                enable_offload()
                if deadline is not None:
                    deadline.check("pipeline_model_cpu_offload_complete")
            else:
                pipeline = pipeline.to(self._config.device)
                if deadline is not None:
                    deadline.check("pipeline_device_transfer_complete")
            if self._config.enable_attention_slicing:
                pipeline.enable_attention_slicing()
                if deadline is not None:
                    deadline.check("pipeline_attention_slicing_complete")
            self._pipelines[cache_key] = pipeline
        if deadline is not None:
            deadline.check("pipeline_resolution_complete")
        return pipeline, torch, Image

    def _validate_invocation(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> None:
        expected_conditioning = self._config.conditioning_method(request.mode)
        if request.conditioning_method != expected_conditioning:
            raise ValueError(
                "Render request conditioning differs from Diffusers runtime"
            )
        if request.mode == "text_to_image" and source_png is not None:
            raise ValueError("text_to_image backend call received source bytes")
        if request.mode == "image_to_image" and source_png is None:
            raise ValueError("image_to_image backend call requires source bytes")
        if self._config.pipeline_family == "flux2_klein":
            if request.negative_prompt:
                raise ValueError(
                    "Flux2KleinPipeline does not accept a negative_prompt argument"
                )
            if request.strength is not None:
                raise ValueError(
                    "Flux2KleinPipeline reference conditioning does not accept strength"
                )

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        return self._render(request, source_png=source_png, deadline=None)

    def render_with_timeout(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
        timeout_seconds: float,
    ) -> bytes:
        """Render with cooperative checks; this is not hard GPU cancellation."""

        deadline = _CooperativeDeadline(timeout_seconds)
        return self._render(request, source_png=source_png, deadline=deadline)

    def _render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
        deadline: _CooperativeDeadline | None,
    ) -> bytes:
        with self._lock:
            if deadline is not None:
                deadline.check("renderer_lock_acquired")
            self._validate_invocation(request, source_png=source_png)
            if deadline is not None:
                deadline.check("renderer_invocation_validated")
            pipeline, torch, image_module = self._pipeline(
                request,
                deadline=deadline,
            )
            if deadline is not None:
                deadline.check("generator_creation_start")
            generator_device = (
                "cpu" if self._config.enable_model_cpu_offload else self._config.device
            )
            generator = torch.Generator(device=generator_device).manual_seed(request.seed)
            if deadline is not None:
                deadline.check("generator_creation_complete")
            options: dict[str, object] = {
                "prompt": request.prompt,
                "num_inference_steps": request.num_inference_steps,
                "guidance_scale": request.guidance_scale,
                "generator": generator,
            }
            if self._config.pipeline_family != "flux2_klein":
                options["negative_prompt"] = request.negative_prompt
            if request.mode == "text_to_image":
                options.update(width=request.width, height=request.height)
            else:
                assert source_png is not None
                if deadline is not None:
                    deadline.check("source_image_decode_start")
                with image_module.open(io.BytesIO(source_png)) as opened:
                    source_image = opened.convert("RGB").copy()
                if deadline is not None:
                    deadline.check("source_image_decode_complete")
                options["image"] = source_image
                if request.conditioning_method == "classic_strength":
                    options["strength"] = request.strength
                else:
                    options.update(width=request.width, height=request.height)

            if deadline is not None:
                def check_step_deadline(
                    _pipeline: object,
                    step_index: int,
                    _timestep: object,
                    callback_kwargs: dict[str, object],
                ) -> dict[str, object]:
                    deadline.check(f"diffusion_step_{step_index}_complete")
                    return callback_kwargs

                options["callback_on_step_end"] = check_step_deadline
                options["callback_on_step_end_tensor_inputs"] = []
                deadline.check("inference_start")
            result = pipeline(**options)
            if deadline is not None:
                deadline.check("inference_complete")
            images = getattr(result, "images", None)
            if not images:
                raise RuntimeError("Diffusers returned no image")
            output = io.BytesIO()
            images[0].save(output, format="PNG")
            if deadline is not None:
                deadline.check("png_serialization_complete")
            return output.getvalue()


def _sanitized_failure(exc: Exception) -> tuple[str, str]:
    exception_names = {kind.__name__ for kind in type(exc).__mro__}
    if isinstance(exc, TimeoutError):
        code = RENDERER_TIMEOUT_FAILURE_CODE
    elif exception_names.intersection({"OutOfMemoryError", "CUDAOutOfMemoryError"}):
        code = "renderer_out_of_memory"
    elif isinstance(exc, (TypeError, AttributeError, NotImplementedError)):
        code = "renderer_api_incompatibility"
    else:
        code = "renderer_provider_failure"
    return code, f"Image renderer failed closed ({code})"


class DiffusersImageRenderer:
    """Provider implementation that returns auditable success/failure outcomes."""

    def __init__(
        self,
        *,
        identity: ProviderIdentity,
        backend: DiffusionBackend,
        artifact_store: LocalPngArtifactStore,
        pipeline_specs: Mapping[ImageRenderMode, ImagePipelineSpec] | None = None,
    ) -> None:
        if identity.kind != "image_renderer" or not identity.uses_model:
            raise ValueError(
                "DiffusersImageRenderer requires a model-backed image_renderer identity"
            )
        if identity.model_revision is None or re.fullmatch(
            r"[0-9a-f]{40}", identity.model_revision
        ) is None:
            raise ValueError(
                "Diffusers model_revision must be an immutable 40-hex Hub commit"
            )
        self._identity = identity
        self._backend = backend
        self._artifact_store = artifact_store
        if pipeline_specs is None:
            resolver = getattr(backend, "pipeline_spec", None)
            if callable(resolver):
                pipeline_specs = {
                    mode: resolver(mode)
                    for mode in ("text_to_image", "image_to_image")
                }
            else:
                pipeline_specs = {
                    mode: ImagePipelineSpec(
                        implementation=identity.implementation,
                        implementation_revision=identity.implementation_revision,
                    )
                    for mode in ("text_to_image", "image_to_image")
                }
        if set(pipeline_specs) != {"text_to_image", "image_to_image"}:
            raise ValueError("Renderer requires exact T2I and img2img pipeline specs")
        self._pipeline_specs = dict(pipeline_specs)

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        return self._pipeline_specs[mode]

    def read_artifact_bytes(self, image: ImageArtifact) -> bytes:
        """Re-read one published PNG through the byte-verifying artifact store."""

        validated = ImageArtifact.model_validate(
            image.model_dump(mode="python", round_trip=True)
        )
        return self._artifact_store.verify_artifact(validated)

    def _validate_call(
        self,
        request: ImageRenderRequest,
        call: ProviderCallSpec,
    ) -> None:
        ensure_call_contract(
            self.identity,
            call,
            request_id=request.request_id,
            seed=request.seed,
            expected_kind="image_renderer",
            required_input_artifact_ids=request.input_artifact_ids,
        )
        if call.input_artifact_ids != request.input_artifact_ids:
            raise ValueError("Renderer call must exactly close request input artifacts")
        if call.parameters != request.provider_parameters:
            raise ValueError("Renderer call parameters differ from approved request")
        if request.pipeline != self.pipeline_spec(request.mode):
            raise ValueError("Renderer request pipeline differs from provider runtime")
        if call.fallback_policy.mode != "none":
            raise ValueError(
                "This local adapter does not execute implicit provider fallbacks"
            )

    def _validate_cached_artifact(
        self,
        artifact: ImageArtifact,
        *,
        request: ImageRenderRequest,
        call: ProviderCallSpec,
    ) -> None:
        """Close a cache hit to the exact immutable request and call lineage."""

        expected_image_id = content_id(
            "image",
            {
                "request_id": request.request_id,
                "content_sha256": artifact.content_sha256,
            },
        )
        expected_path = f"emocio/images/{expected_image_id}.png"
        expected = {
            "request_id": request.request_id,
            "render_call_id": call.call_id,
            "source_spec_id": request.source_spec_id,
            "provider_id": self.identity.provider_id,
            "model": self.identity.model,
            "model_revision": self.identity.model_revision,
            "seed": request.seed,
            "input_spec_hash": request.source_spec_hash,
            "media_type": "image/png",
            "grounded": False,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "generated_only_elements": ("unverified_renderer_details",),
            "grounded_mask_path": None,
            "image_id": expected_image_id,
            "path": expected_path,
        }
        actual = {field: getattr(artifact, field) for field in expected}
        if actual != expected:
            mismatches = tuple(
                field for field in expected if actual[field] != expected[field]
            )
            raise ValueError(
                "Renderer cache artifact differs from request/call lineage: "
                + ", ".join(mismatches)
            )

    def render(
        self,
        request: ImageRenderRequest,
        *,
        call: ProviderCallSpec,
    ) -> ImageRenderItemOutcome:
        self._validate_call(request, call)
        started_at = utc_now()
        try:
            source_png = (
                self._artifact_store.read_verified_source(request.source_image)
                if request.source_image is not None
                else None
            )
            cached_artifact = self._artifact_store.read_cached_artifact(
                request.request_id
            )
            if cached_artifact is not None:
                self._validate_cached_artifact(
                    cached_artifact,
                    request=request,
                    call=call,
                )
                finished_at = utc_now()
                record = ProviderCallRecord(
                    call_id=call.call_id,
                    spec_hash=call.content_hash(),
                    request_id=call.request_id,
                    input_artifact_ids=call.input_artifact_ids,
                    provider=call.provider,
                    seed=call.seed,
                    parameters=call.parameters,
                    timeout_seconds=call.timeout_seconds,
                    started_at=started_at,
                    primary_finished_at=finished_at,
                    finished_at=finished_at,
                    status="succeeded",
                    primary_status="succeeded",
                    fallback=None,
                    output_artifact_ids=(cached_artifact.image_id,),
                    warnings=("cache_hit_verified",),
                    safety_notice=call.safety_notice,
                )
                return ImageRenderItemOutcome.create(
                    request=request,
                    call_spec=call,
                    call_record=record,
                    artifact=cached_artifact,
                )
            timed_render = getattr(self._backend, "render_with_timeout", None)
            if callable(timed_render):
                png_bytes = timed_render(
                    request,
                    source_png=source_png,
                    timeout_seconds=call.timeout_seconds,
                )
            else:
                # Legacy/custom backends keep their existing synchronous contract.
                # No hard or cooperative timeout is claimed for this path.
                png_bytes = self._backend.render(request, source_png=source_png)
            width, height = inspect_png(png_bytes)
            if (width, height) != (request.width, request.height):
                raise ValueError(
                    "Renderer output dimensions differ from approved request"
                )
            content_sha256 = hashlib.sha256(png_bytes).hexdigest()
            image_id = content_id(
                "image",
                {
                    "request_id": request.request_id,
                    "content_sha256": content_sha256,
                },
            )
            relative_path = f"emocio/images/{image_id}.png"
            artifact = ImageArtifact(
                image_id=image_id,
                request_id=request.request_id,
                render_call_id=call.call_id,
                source_spec_id=request.source_spec_id,
                provider_id=self.identity.provider_id,
                model=self.identity.model,
                model_revision=self.identity.model_revision,
                seed=request.seed,
                input_spec_hash=request.source_spec_hash,
                content_sha256=content_sha256,
                media_type="image/png",
                grounded=False,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                path=relative_path,
                width=width,
                height=height,
                generated_only_elements=("unverified_renderer_details",),
                grounded_mask_path=None,
            )
            stored = self._artifact_store.persist_png(
                relative_path,
                png_bytes,
                expected_width=width,
                expected_height=height,
            )
            if stored.content_sha256 != artifact.content_sha256:
                raise ValueError("Stored image hash differs from image artifact")
            self._artifact_store.persist_cached_artifact(artifact)
            finished_at = utc_now()
            record = ProviderCallRecord(
                call_id=call.call_id,
                spec_hash=call.content_hash(),
                request_id=call.request_id,
                input_artifact_ids=call.input_artifact_ids,
                provider=call.provider,
                seed=call.seed,
                parameters=call.parameters,
                timeout_seconds=call.timeout_seconds,
                started_at=started_at,
                primary_finished_at=finished_at,
                finished_at=finished_at,
                status="succeeded",
                primary_status="succeeded",
                fallback=None,
                output_artifact_ids=(artifact.image_id,),
                warnings=(),
                safety_notice=call.safety_notice,
            )
            return ImageRenderItemOutcome.create(
                request=request,
                call_spec=call,
                call_record=record,
                artifact=artifact,
            )
        except Exception as exc:
            finished_at = utc_now()
            if isinstance(exc, TimeoutError):
                status: Literal["failed", "timed_out"] = "timed_out"
                code = RENDERER_TIMEOUT_FAILURE_CODE
                _, message = _sanitized_failure(exc)
            else:
                status = "failed"
                code, message = _sanitized_failure(exc)
            record = ProviderCallRecord(
                call_id=call.call_id,
                spec_hash=call.content_hash(),
                request_id=call.request_id,
                input_artifact_ids=call.input_artifact_ids,
                provider=call.provider,
                seed=call.seed,
                parameters=call.parameters,
                timeout_seconds=call.timeout_seconds,
                started_at=started_at,
                primary_finished_at=finished_at,
                finished_at=finished_at,
                status=status,
                primary_status=status,
                fallback=None,
                output_artifact_ids=(),
                warnings=(message,),
                safety_notice=call.safety_notice,
            )
            return ImageRenderItemOutcome.create(
                request=request,
                call_spec=call,
                call_record=record,
                failure_code=code,
                failure_message=message,
            )


__all__ = [
    "DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME",
    "DiffusersImageRenderer",
    "DiffusersRuntimeConfig",
    "DiffusersSnapshotFile",
    "DiffusersSnapshotManifest",
    "DiffusionBackend",
    "LazyDiffusersBackend",
    "RENDERER_TIMEOUT_FAILURE_CODE",
    "TimedDiffusionBackend",
    "build_diffusers_snapshot_manifest",
    "canonical_snapshot_manifest_bytes",
]
