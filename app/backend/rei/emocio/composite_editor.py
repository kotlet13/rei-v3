"""C4 screen-only composite image-editor adapter.

This module deliberately reuses the existing provider-neutral image-render
contracts.  It adds only the local, split-model mechanics required to compare
two image editors against the exact same current-scene PNG.  A screen result
is never production authority and never changes the native Emocio conclusion.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import threading
import time
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    CommitDigest,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from ..models.emocio import ImageArtifact, VisualSceneSpec
from ..models.provider import ProviderIdentity, ProviderParameter
from ..models.rendering import (
    ImagePipelineSpec,
    ImageRenderBatchOutcome,
    ImageRenderMode,
    ImageRenderRequest,
    ImageSourceReference,
)
from ..providers.protocols import ImageRenderer
from .artifacts import LocalPngArtifactStore, inspect_png
from .diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersImageRenderer,
    DiffusersSnapshotManifest,
    build_diffusers_snapshot_manifest,
    canonical_snapshot_manifest_bytes,
)
from .prompting import BilingualStructuredScenePromptCompiler, VisualPromptProfile
from .renderer import LocalEmocioRenderer, RenderSettings


EDITOR_ADAPTER_REVISION = "rei-c4-composite-editor-screen-v1"
PINNED_DIFFUSERS_VERSION = "0.39.0"
PINNED_TORCH_DTYPE = "bfloat16"


class CompositeEditorRuntimeConfig(FrozenModel):
    """Exact local model/runtime pin for one non-authoritative C4 editor."""

    editor_id: NonEmptyId
    repo_id: NonEmptyId
    revision: CommitDigest
    adapter_implementation: NonEmptyText
    adapter_implementation_revision: NonEmptyText
    pipeline_class: NonEmptyId
    guidance_argument: Literal["guidance_scale", "true_cfg_scale"]
    pass_output_dimensions: bool
    local_snapshot_path: NonEmptyText
    expected_snapshot_manifest_sha256: HashDigest
    diffusers_version: Literal["0.39.0"] = PINNED_DIFFUSERS_VERSION
    torch_version: Literal["2.13.0"] = "2.13.0"
    transformers_version: Literal["5.13.0"] = "5.13.0"
    accelerate_version: Literal["1.14.0"] = "1.14.0"
    safetensors_version: Literal["0.8.0"] = "0.8.0"
    pillow_version: Literal["12.3.0"] = "12.3.0"
    torch_dtype: Literal["bfloat16"] = PINNED_TORCH_DTYPE
    execution_device: Literal["cuda"] = "cuda"
    generator_device: Literal["cpu"] = "cpu"
    local_files_only: Literal[True] = True
    use_safetensors: Literal[True] = True
    enable_model_cpu_offload: Literal[True] = True
    output_size_policy: Literal["source_dimensions_lanczos"] = (
        "source_dimensions_lanczos"
    )

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        snapshot = Path(self.local_snapshot_path)
        if not snapshot.is_absolute():
            raise ValueError("Editor snapshot path must be absolute")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", self.pipeline_class) is None:
            raise ValueError("Editor pipeline class must be one import-safe class name")
        return self

    def provider_identity(self) -> ProviderIdentity:
        payload = {
            "schema_version": "rei-native-provider-identity-v1",
            "kind": "image_renderer",
            "implementation": self.adapter_implementation,
            "implementation_revision": self.adapter_implementation_revision,
            "uses_model": True,
            "model": self.repo_id,
            "model_revision": self.revision,
        }
        return ProviderIdentity(
            provider_id=content_id("provider", payload),
            **payload,
        )

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        values = {
            "accelerate_version": self.accelerate_version,
            "conditioning_method": (
                "reference_image" if mode == "image_to_image" else "unsupported"
            ),
            "diffusers_version": self.diffusers_version,
            "enable_model_cpu_offload": self.enable_model_cpu_offload,
            "execution_device": self.execution_device,
            "generator_device": self.generator_device,
            "guidance_argument": self.guidance_argument,
            "local_files_only": self.local_files_only,
            "load_source": "verified_local_snapshot",
            "mode_supported": mode == "image_to_image",
            "network_access": False,
            "output_size_policy": self.output_size_policy,
            "pass_output_dimensions": self.pass_output_dimensions,
            "pillow_version": self.pillow_version,
            "safetensors_version": self.safetensors_version,
            "snapshot_manifest_sha256": self.expected_snapshot_manifest_sha256,
            "snapshot_path_provenance": (
                "absolute_machine_path_excluded_from_portable_request_identity"
            ),
            "torch_dtype": self.torch_dtype,
            "torch_version": self.torch_version,
            "timeout_enforcement_mode": (
                "cooperative_before_and_after_load_and_inference"
            ),
            "timeout_hard_cancellation": False,
            "use_safetensors": self.use_safetensors,
            "transformers_version": self.transformers_version,
        }
        return ImagePipelineSpec(
            implementation=f"diffusers.{self.pipeline_class}",
            implementation_revision=self.diffusers_version,
            parameters=tuple(
                ProviderParameter(
                    name=name,
                    canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
                )
                for name, value in sorted(values.items())
            ),
        )


class VerifiedEditorSnapshot(FrozenArtifactModel):
    """Portable evidence for a completely inventoried local model snapshot."""

    schema_version: Literal["rei-c4-editor-snapshot-evidence-v1"] = (
        "rei-c4-editor-snapshot-evidence-v1"
    )
    snapshot_id: NonEmptyId
    editor_id: NonEmptyId
    repo_id: NonEmptyId
    revision: CommitDigest
    manifest_sha256: HashDigest
    file_count: Annotated[int, Field(gt=0)]
    total_size_bytes: Annotated[int, Field(gt=0)]

    @classmethod
    def create(
        cls,
        *,
        config: CompositeEditorRuntimeConfig,
        manifest: DiffusersSnapshotManifest,
    ) -> "VerifiedEditorSnapshot":
        payload = {
            "schema_version": "rei-c4-editor-snapshot-evidence-v1",
            "editor_id": config.editor_id,
            "repo_id": manifest.repo_id,
            "revision": manifest.revision,
            "manifest_sha256": config.expected_snapshot_manifest_sha256,
            "file_count": len(manifest.files),
            "total_size_bytes": sum(item.size_bytes for item in manifest.files),
        }
        return cls(
            snapshot_id=content_id("c4_editor_snapshot", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_snapshot_id(self) -> Self:
        expected = content_id(
            "c4_editor_snapshot",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"snapshot_id"},
            ),
        )
        if self.snapshot_id != expected:
            raise ValueError("Editor snapshot evidence ID differs from canonical content")
        return self


def verify_editor_snapshot(
    config: CompositeEditorRuntimeConfig,
) -> VerifiedEditorSnapshot:
    """Hash and compare every non-cache snapshot file before runtime import."""

    try:
        root = Path(config.local_snapshot_path).resolve(strict=True)
    except OSError as exc:
        raise ValueError("Configured editor snapshot does not exist") from exc
    if not root.is_dir():
        raise ValueError("Configured editor snapshot is not a directory")
    manifest_path = root / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise ValueError("Configured editor snapshot manifest is unreadable") from exc
    actual_digest = hashlib.sha256(manifest_bytes).hexdigest()
    if actual_digest != config.expected_snapshot_manifest_sha256:
        raise ValueError("Editor snapshot manifest SHA-256 differs from runtime pin")
    try:
        manifest = DiffusersSnapshotManifest.model_validate_json(manifest_bytes)
    except Exception as exc:
        raise ValueError("Configured editor snapshot manifest is invalid") from exc
    if manifest_bytes != canonical_snapshot_manifest_bytes(manifest):
        raise ValueError("Configured editor snapshot manifest is not canonical JSON")
    if manifest.repo_id != config.repo_id or manifest.revision != config.revision:
        raise ValueError("Editor snapshot repository or revision differs from runtime pin")

    actual_manifest = build_diffusers_snapshot_manifest(
        root,
        repo_id=config.repo_id,
        revision=config.revision,
    )
    if actual_manifest != manifest:
        raise ValueError("Editor snapshot inventory or file digest differs from manifest")
    return VerifiedEditorSnapshot.create(config=config, manifest=manifest)


class LazyLocalCompositeEditorBackend:
    """Lazy BF16/CPU-offload Diffusers editor using one verified local snapshot."""

    def __init__(self, config: CompositeEditorRuntimeConfig) -> None:
        self.config = config
        self._snapshot: VerifiedEditorSnapshot | None = None
        self._pipeline: object | None = None
        self._torch: object | None = None
        self._image_module: object | None = None
        self._lock = threading.RLock()

    def pipeline_spec(self, mode: ImageRenderMode) -> ImagePipelineSpec:
        return self.config.pipeline_spec(mode)

    def verify_snapshot(self) -> VerifiedEditorSnapshot:
        with self._lock:
            if self._snapshot is None:
                self._snapshot = verify_editor_snapshot(self.config)
            return self._snapshot

    def release_pipeline(self) -> None:
        """Drop the optional runtime after a bounded screen slice completes."""

        with self._lock:
            self._pipeline = None
            self._torch = None
            self._image_module = None

    def _load_pipeline(self) -> tuple[object, object, object]:
        with self._lock:
            if (
                self._pipeline is not None
                and self._torch is not None
                and self._image_module is not None
            ):
                return self._pipeline, self._torch, self._image_module

            cached_snapshot = self._snapshot
            fresh_snapshot = verify_editor_snapshot(self.config)
            if cached_snapshot is not None and fresh_snapshot != cached_snapshot:
                raise ValueError(
                    "Editor snapshot changed after its portable evidence was issued"
                )
            self._snapshot = fresh_snapshot
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_DATASETS_OFFLINE"] = "1"
            try:
                import diffusers
                import torch
                from PIL import Image
            except ImportError as exc:
                raise RuntimeError(
                    "Install app/backend/requirements-renderer.txt before C4 editing"
                ) from exc
            pinned_distributions = {
                "accelerate": self.config.accelerate_version,
                "diffusers": self.config.diffusers_version,
                "Pillow": self.config.pillow_version,
                "safetensors": self.config.safetensors_version,
                "torch": self.config.torch_version,
                "transformers": self.config.transformers_version,
            }
            try:
                dependency_matches = all(
                    version(distribution).split("+", 1)[0] == expected
                    for distribution, expected in pinned_distributions.items()
                )
            except PackageNotFoundError as exc:
                raise RuntimeError("Pinned editor dependency is not installed") from exc
            if not dependency_matches:
                raise RuntimeError("Installed editor dependency differs from runtime pin")
            if not torch.cuda.is_available():
                raise RuntimeError("C4 editor screen requires a CUDA device")
            pipeline_type = getattr(diffusers, self.config.pipeline_class, None)
            if pipeline_type is None:
                raise RuntimeError("Pinned Diffusers editor pipeline is unavailable")
            pipeline = pipeline_type.from_pretrained(
                str(Path(self.config.local_snapshot_path).resolve(strict=True)),
                torch_dtype=torch.bfloat16,
                local_files_only=True,
                use_safetensors=True,
            )
            if verify_editor_snapshot(self.config) != fresh_snapshot:
                raise ValueError("Editor snapshot changed while its pipeline was loading")
            enable_offload = getattr(pipeline, "enable_model_cpu_offload", None)
            if not callable(enable_offload):
                raise RuntimeError("Pinned editor pipeline cannot enable model CPU offload")
            enable_offload()
            self._pipeline = pipeline
            self._torch = torch
            self._image_module = Image
            return pipeline, torch, Image

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        return self.render_with_timeout(
            request,
            source_png=source_png,
            timeout_seconds=24 * 60 * 60.0,
        )

    def render_with_timeout(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
        timeout_seconds: float,
    ) -> bytes:
        if request.mode != "image_to_image" or source_png is None:
            raise ValueError("Composite editor accepts image-to-image requests only")
        if request.provider != self.config.provider_identity():
            raise ValueError("Editor request provider differs from runtime pin")
        if request.pipeline != self.config.pipeline_spec("image_to_image"):
            raise ValueError("Editor request pipeline differs from runtime pin")
        if request.conditioning_method != "reference_image" or request.strength is not None:
            raise ValueError("Composite editor requires reference-image conditioning")
        if inspect_png(source_png) != (request.width, request.height):
            raise ValueError("Editor source PNG dimensions differ from request")
        deadline = time.monotonic() + timeout_seconds

        def check_deadline(stage: str) -> None:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Composite editor deadline exceeded during {stage}")

        check_deadline("pipeline_load_start")
        pipeline, torch, image_module = self._load_pipeline()
        check_deadline("pipeline_load_complete")
        with image_module.open(io.BytesIO(source_png)) as opened:
            source_image = opened.convert("RGB").copy()
        generator = torch.Generator(device=self.config.generator_device).manual_seed(
            request.seed
        )
        options: dict[str, object] = {
            "image": source_image,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "num_inference_steps": request.num_inference_steps,
            "num_images_per_prompt": 1,
            "generator": generator,
        }
        options[self.config.guidance_argument] = request.guidance_scale
        if self.config.pass_output_dimensions:
            options.update(height=request.height, width=request.width)
        check_deadline("inference_start")
        result = pipeline(**options)
        check_deadline("inference_complete")
        images = getattr(result, "images", None)
        if not images:
            raise RuntimeError("Diffusers editor returned no image")
        output_image = images[0].convert("RGB")
        if output_image.size != (request.width, request.height):
            output_image = output_image.resize(
                (request.width, request.height),
                image_module.Resampling.LANCZOS,
            )
        output = io.BytesIO()
        output_image.save(output, format="PNG", optimize=False)
        check_deadline("png_serialization_complete")
        return output.getvalue()


@dataclass(frozen=True, slots=True)
class CompositeEditorMember:
    """One renderer/store pair whose portable pins were already verified."""

    config: CompositeEditorRuntimeConfig
    snapshot: VerifiedEditorSnapshot
    renderer: ImageRenderer
    artifact_store: LocalPngArtifactStore

    def __post_init__(self) -> None:
        if self.snapshot.editor_id != self.config.editor_id:
            raise ValueError("Editor member snapshot belongs to another editor")
        if (
            self.snapshot.repo_id != self.config.repo_id
            or self.snapshot.revision != self.config.revision
            or self.snapshot.manifest_sha256
            != self.config.expected_snapshot_manifest_sha256
        ):
            raise ValueError("Editor member snapshot differs from runtime pin")
        if self.renderer.identity != self.config.provider_identity():
            raise ValueError("Editor member provider differs from runtime pin")
        if self.renderer.pipeline_spec("image_to_image") != self.config.pipeline_spec(
            "image_to_image"
        ):
            raise ValueError("Editor member pipeline differs from runtime pin")


class CompositeEditorMemberResult(FrozenModel):
    editor_id: NonEmptyId
    snapshot: VerifiedEditorSnapshot
    provider: ProviderIdentity
    pipeline: ImagePipelineSpec
    batch: ImageRenderBatchOutcome


class CompositeEditorScreenResult(FrozenArtifactModel):
    """Typed result that can never claim semantic or production approval."""

    schema_version: Literal["rei-c4-composite-editor-screen-v1"] = (
        "rei-c4-composite-editor-screen-v1"
    )
    screen_id: NonEmptyId
    source: ImageSourceReference
    source_artifact: ImageArtifact
    source_scene_spec_id: NonEmptyId
    source_scene_spec_hash: HashDigest
    root_seed: int
    prompt_profile: VisualPromptProfile
    option_order: tuple[NonEmptyId, ...]
    members: tuple[CompositeEditorMemberResult, ...]
    technical_execution_passed: bool
    semantic_review_status: Literal["requires_human_review"] = "requires_human_review"
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        source: ImageSourceReference,
        source_artifact: ImageArtifact,
        source_scene: VisualSceneSpec,
        root_seed: int,
        prompt_profile: VisualPromptProfile,
        option_order: tuple[str, ...],
        members: tuple[CompositeEditorMemberResult, ...],
    ) -> "CompositeEditorScreenResult":
        technical_passed = bool(members) and all(
            member.batch.status == "succeeded" for member in members
        )
        payload = {
            "schema_version": "rei-c4-composite-editor-screen-v1",
            "source": source,
            "source_artifact": source_artifact,
            "source_scene_spec_id": source_scene.scene_id,
            "source_scene_spec_hash": source_scene.content_hash(),
            "root_seed": root_seed,
            "prompt_profile": prompt_profile,
            "option_order": option_order,
            "members": members,
            "technical_execution_passed": technical_passed,
            "semantic_review_status": "requires_human_review",
            "semantic_quality_gate_passed": False,
            "production_authority_granted": False,
            "generated_images_are_external_evidence": False,
        }
        return cls(screen_id=content_id("c4_editor_screen", payload), **payload)

    @model_validator(mode="after")
    def validate_screen(self) -> Self:
        editor_ids = tuple(member.editor_id for member in self.members)
        if len(editor_ids) < 2 or len(set(editor_ids)) != len(editor_ids):
            raise ValueError("Composite editor screen requires distinct editors")
        if self.source_scene_spec_id != self.source.originating_scene_spec_id or (
            self.source_scene_spec_hash != self.source.originating_scene_spec_hash
        ):
            raise ValueError("Composite editor source scene lineage differs")
        if self.source != ImageSourceReference.from_artifact_with_scene_lineage(
            self.source_artifact
        ):
            raise ValueError("Composite editor source differs from prior artifact")
        expected_technical_pass = bool(self.members) and all(
            member.batch.status == "succeeded" for member in self.members
        )
        if self.technical_execution_passed != expected_technical_pass:
            raise ValueError("Composite technical status differs from member batches")
        reference_by_scene: dict[str, tuple[str, int, str]] = {}
        for member in self.members:
            if member.editor_id != member.snapshot.editor_id:
                raise ValueError("Composite member ID differs from snapshot evidence")
            if member.batch.root_seed != self.root_seed:
                raise ValueError("Composite member root seed differs")
            if member.batch.source_spec_ids != self.option_order:
                raise ValueError("Composite member option order differs")
            if member.provider.model != member.snapshot.repo_id or (
                member.provider.model_revision != member.snapshot.revision
            ):
                raise ValueError("Composite member provider differs from snapshot")
            runtime_parameters = {
                item.name: item.canonical_json_value
                for item in member.pipeline.parameters
            }
            expected_runtime_parameters = {
                "enable_model_cpu_offload": "true",
                "local_files_only": "true",
                "snapshot_manifest_sha256": canonical_json_bytes(
                    member.snapshot.manifest_sha256
                ).decode("utf-8"),
                "torch_dtype": canonical_json_bytes(PINNED_TORCH_DTYPE).decode(
                    "utf-8"
                ),
            }
            if any(
                runtime_parameters.get(name) != value
                for name, value in expected_runtime_parameters.items()
            ):
                raise ValueError("Composite member runtime provenance is incomplete")
            for item in member.batch.items:
                request = item.request
                if request.mode != "image_to_image" or request.source_image is None:
                    raise ValueError("Composite screen permits image editing only")
                if (
                    request.prompt_language != self.prompt_profile.language
                    or request.style_id != self.prompt_profile.style_id
                    or request.profile_hash != self.prompt_profile.content_hash()
                ):
                    raise ValueError(
                        "Composite request prompt metadata differs from its profile"
                    )
                if request.source_image != self.source:
                    raise ValueError(
                        "Composite members did not reuse exact source lineage"
                    )
                if request.provider != member.provider or request.pipeline != member.pipeline:
                    raise ValueError("Composite request differs from member runtime")
                if item.call_spec.fallback_policy.mode != "none":
                    raise ValueError("Composite editor screen forbids provider fallback")
                comparison = (request.prompt, request.seed, request.source_spec_hash)
                previous = reference_by_scene.setdefault(request.source_spec_id, comparison)
                if comparison != previous:
                    raise ValueError("Composite members received different screen inputs")
        expected_id = content_id(
            "c4_editor_screen",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"screen_id"},
            ),
        )
        if self.screen_id != expected_id:
            raise ValueError("Composite editor screen ID differs from canonical content")
        return self


def build_editor_renderer(
    config: CompositeEditorRuntimeConfig,
    *,
    backend: LazyLocalCompositeEditorBackend,
    artifact_store: LocalPngArtifactStore,
) -> DiffusersImageRenderer:
    """Bind a local editor backend to the existing auditable provider adapter."""

    return DiffusersImageRenderer(
        identity=config.provider_identity(),
        backend=backend,
        artifact_store=artifact_store,
        pipeline_specs={
            mode: config.pipeline_spec(mode)
            for mode in ("text_to_image", "image_to_image")
        },
    )


def render_editor_member_screen(
    *,
    member: CompositeEditorMember,
    source_scene: VisualSceneSpec,
    source_artifact: ImageArtifact,
    option_rollouts: tuple[VisualSceneSpec, ...],
    source_png: bytes,
    root_seed: int,
    prompt_compiler: BilingualStructuredScenePromptCompiler,
    num_inference_steps: int,
    guidance_scale: float,
    negative_prompt: str,
    timeout_seconds: float,
) -> CompositeEditorMemberResult:
    """Render one non-authoritative cell through one verified editor member."""

    if source_scene.scene_kind != "current":
        raise ValueError("Composite editor source scene must be current")
    if not option_rollouts or any(
        scene.scene_kind != "option_rollout" for scene in option_rollouts
    ):
        raise ValueError("Composite editor screen requires option rollouts")
    option_order = tuple(scene.scene_id for scene in option_rollouts)
    if len(set(option_order)) != len(option_order):
        raise ValueError("Composite editor option scenes must be unique")
    width, height = inspect_png(source_png)
    source_digest = hashlib.sha256(source_png).hexdigest()
    if (
        source_artifact.content_sha256 != source_digest
        or source_artifact.media_type != "image/png"
        or (source_artifact.width, source_artifact.height) != (width, height)
        or source_artifact.source_spec_id != source_scene.scene_id
        or source_artifact.input_spec_hash != source_scene.content_hash()
        or source_artifact.grounded is not False
    ):
        raise ValueError("Current PNG differs from its immutable source artifact")
    source = ImageSourceReference.from_artifact_with_scene_lineage(source_artifact)
    stored = member.artifact_store.persist_png(
        source.path,
        source_png,
        expected_width=width,
        expected_height=height,
    )
    if stored.content_sha256 != source.content_sha256:
        raise ValueError("Materialized editor source differs from shared source")
    settings = RenderSettings(
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        negative_prompt=negative_prompt,
        timeout_seconds=timeout_seconds,
    )
    renderer = LocalEmocioRenderer(
        provider=member.renderer,
        settings=settings,
        prompt_compiler=prompt_compiler,
        image_to_image_sources={scene.scene_id: source for scene in option_rollouts},
        image_to_image_conditioning={
            scene.scene_id: "reference_image" for scene in option_rollouts
        },
    )
    batch = renderer.render(option_rollouts, seed=root_seed)
    return CompositeEditorMemberResult(
        editor_id=member.config.editor_id,
        snapshot=member.snapshot,
        provider=member.renderer.identity,
        pipeline=member.renderer.pipeline_spec("image_to_image"),
        batch=batch,
    )


def render_composite_editor_screen(
    *,
    members: tuple[CompositeEditorMember, ...],
    source_scene: VisualSceneSpec,
    source_artifact: ImageArtifact,
    option_rollouts: tuple[VisualSceneSpec, ...],
    source_png: bytes,
    root_seed: int,
    prompt_compiler: BilingualStructuredScenePromptCompiler,
    num_inference_steps: int,
    guidance_scale: float,
    negative_prompt: str,
    timeout_seconds: float,
) -> CompositeEditorScreenResult:
    """Render one controlled cell through every editor using identical inputs."""

    results = tuple(
        render_editor_member_screen(
            member=member,
            source_scene=source_scene,
            source_artifact=source_artifact,
            option_rollouts=option_rollouts,
            source_png=source_png,
            root_seed=root_seed,
            prompt_compiler=prompt_compiler,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            negative_prompt=negative_prompt,
            timeout_seconds=timeout_seconds,
        )
        for member in members
    )
    option_order = tuple(scene.scene_id for scene in option_rollouts)
    return CompositeEditorScreenResult.create(
        source=ImageSourceReference.from_artifact_with_scene_lineage(source_artifact),
        source_artifact=source_artifact,
        source_scene=source_scene,
        root_seed=root_seed,
        prompt_profile=prompt_compiler.prompt_profile,
        option_order=option_order,
        members=results,
    )


__all__ = [
    "CompositeEditorMember",
    "CompositeEditorMemberResult",
    "CompositeEditorRuntimeConfig",
    "CompositeEditorScreenResult",
    "EDITOR_ADAPTER_REVISION",
    "LazyLocalCompositeEditorBackend",
    "PINNED_DIFFUSERS_VERSION",
    "PINNED_TORCH_DTYPE",
    "VerifiedEditorSnapshot",
    "build_editor_renderer",
    "render_composite_editor_screen",
    "render_editor_member_screen",
    "verify_editor_snapshot",
]
