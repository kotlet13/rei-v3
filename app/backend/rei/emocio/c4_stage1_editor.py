"""Shared model-free contracts for the exact C4 Stage 1 image editors.

The portable artifacts in this module never contain a machine-local snapshot
path.  A local path exists only in :class:`C4Stage1LocalSnapshotBinding`, which
is deliberately a runtime dataclass rather than a serializable REI artifact.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    CommitDigest,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from ..models.provider import (
    ProviderCallSpec,
    ProviderIdentity,
    ProviderParameter,
)
from ..models.rendering import ImagePipelineSpec, ImageRenderRequest
from .diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersSnapshotManifest,
    canonical_snapshot_manifest_bytes,
)
from .renderer import build_render_call_spec


C4_STAGE1_SOURCE_WIDTH = 1024
C4_STAGE1_SOURCE_HEIGHT = 768
C4_STAGE1_PER_OPTION_TIMEOUT_SECONDS = 180.0
C4_STAGE1_MEMBER_TIMEOUT_SECONDS = 420.0
C4_STAGE1_MAX_CUDA_MEMORY_MIB = 31_500
C4_STAGE1_MAX_CUDA_MEMORY_BYTES = 31_500 * 1024 * 1024
C4_STAGE1_MAX_SNAPSHOT_FILES = 4096
C4_STAGE1_MAX_MANIFEST_BYTES = 4 * 1024 * 1024
C4_STAGE1_MAX_PNG_BYTES = 64 * 1024 * 1024
C4_STAGE1_MAX_PNG_DIMENSION = 4096
C4_STAGE1_SOURCE_ARTIFACT_ID = "image_d1e97e56432b23038b8a01f6fdc24d42"
C4_STAGE1_SOURCE_PNG_SHA256 = (
    "72c9fec75d838f0db9a9abc71cbd86c4f4e637c8f54f05c0ea629e12e0f6da58"
)
C4_STAGE1_CURRENT_SCENE_ID = "visual_scene_2caca3e7e6424d6bafa3b365d935c4c5"
C4_STAGE1_CURRENT_SCENE_HASH = (
    "c795bdd82b0b01ba54f453b7881a636de5ff118f692e250af5b6d32c4ddb5a65"
)
C4_STAGE1_PROFILE_HASH = (
    "26908b02adc969b1c894b46f69bbd1c81a92464cc62b1e74b4217d9edd06a3c8"
)
C4_STAGE1_OPTION_ORDER = ("enter_circle", "remain_edge")
C4_STAGE1_OPTION_SCENE_IDS = (
    "visual_scene_acbc451d7b30336076e5c1e5bd31e02b",
    "visual_scene_12e01b7dc48013135871ba28868f8180",
)
C4_STAGE1_OPTION_SCENE_HASHES = (
    "7e9b9f91e0ea2f0504548d178b36ccbf0bbc8664b7e38b8ab4ea4e9be960ea57",
    "48af410ba6f01adf5540044dbbe6d1bad4e3e08ddeb60ef772f7924a49e39272",
)
C4_STAGE1_OPTION_SEEDS = (
    1_366_714_956_115_613_163,
    297_232_311_612_386_773,
)
C4_STAGE1_OPTION_PROMPT_SHA256 = (
    "3c046f45c9c66bc35e6c1b4890f24cc021e6c692d5ca6b7288951db6d2c54cba",
    "a92224abe970e7deafef346085bc8751d76aea1d484f4268c66131a05c25c25e",
)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_ALLOWED_CHUNKS = frozenset({b"IHDR", b"IDAT", b"IEND"})
_READ_CHUNK_BYTES = 4 * 1024 * 1024

C4Stage1FailureCode = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$"),
]

_C4_STAGE1_MODEL_LICENSES = {
    "meituan-longcat/LongCat-Image-Edit-Turbo": "Apache-2.0",
    "Shitao/OmniGen-v1-diffusers": "MIT",
}

_C4_STAGE1_OUTPUT_POLICY_BY_ADAPTER = {
    (
        "meituan-longcat/LongCat-Image-Edit-Turbo",
        "6a7262de5549f0bf0ec54c08ef7d283ef41f3214",
        "app.backend.rei.emocio.longcat_turbo_editor.run_longcat_turbo_stage1_lazy",
        "c4-stage1-v1;diffusers=0.39.0",
        "diffusers.LongCatImageEditPipeline",
        "0.39.0;c4-stage1-exact-v1",
    ): (
        frozenset({"primary", "test"}),
        "longcat_rgb_lanczos_1024x768",
        "rgb_then_pillow_lanczos_1024x768",
    ),
    (
        "Shitao/OmniGen-v1-diffusers",
        "016e2f61d12a98303f6bbdf122687694d7984268",
        "app.backend.rei.emocio.omnigen_editor.run_omnigen_stage1_lazy",
        "c4-stage1-v1;diffusers=0.39.0",
        "diffusers.OmniGenPipeline",
        "0.39.0;c4-stage1-exact-v1",
    ): (
        frozenset({"alternate", "test"}),
        "omnigen_strict_identity_rgb_1024x768",
        "strict_identity_rgb_1024x768_no_resize_no_crop",
    ),
}


class C4Stage1DependencyVersions(FrozenModel):
    """Exact external worker environment frozen before Stage 1 inference."""

    python: Literal["3.11"] = "3.11"
    torch: Literal["2.13.0+cu130"] = "2.13.0+cu130"
    diffusers: Literal["0.39.0"] = "0.39.0"
    transformers: Literal["5.13.0"] = "5.13.0"
    accelerate: Literal["1.14.0"] = "1.14.0"
    safetensors: Literal["0.8.0"] = "0.8.0"
    pillow: Literal["12.3.0"] = "12.3.0"


class C4Stage1EditorSpec(FrozenArtifactModel):
    """Portable, content-addressed provider and exact call-surface contract."""

    schema_version: Literal["rei-c4-stage1-editor-spec-v1"] = (
        "rei-c4-stage1-editor-spec-v1"
    )
    spec_id: NonEmptyId
    editor_role: Literal["primary", "alternate", "test"]
    provider: ProviderIdentity
    pipeline: ImagePipelineSpec
    repo_id: NonEmptyId
    revision: CommitDigest
    license_spdx: Literal["Apache-2.0", "MIT", "test-only"]
    snapshot_manifest_sha256: HashDigest
    snapshot_file_count: Annotated[int, Field(gt=0, le=C4_STAGE1_MAX_SNAPSHOT_FILES)]
    snapshot_total_bytes: Annotated[int, Field(gt=0)]
    dependencies: C4Stage1DependencyVersions = C4Stage1DependencyVersions()
    source_width: Literal[1024] = C4_STAGE1_SOURCE_WIDTH
    source_height: Literal[768] = C4_STAGE1_SOURCE_HEIGHT
    per_option_timeout_seconds: Literal[180.0] = C4_STAGE1_PER_OPTION_TIMEOUT_SECONDS
    member_timeout_seconds: Literal[420.0] = C4_STAGE1_MEMBER_TIMEOUT_SECONDS
    max_cuda_memory_mib: Literal[31500] = C4_STAGE1_MAX_CUDA_MEMORY_MIB
    max_cuda_memory_bytes: Literal[33030144000] = C4_STAGE1_MAX_CUDA_MEMORY_BYTES
    fallback: Literal["none"] = "none"
    offline: Literal[True] = True
    local_files_only: Literal[True] = True
    use_safetensors: Literal[True] = True
    torch_dtype: Literal["bfloat16"] = "bfloat16"
    remote_code_allowed: Literal[False] = False
    best_of_n_allowed: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        editor_role: Literal["primary", "alternate", "test"],
        provider: ProviderIdentity,
        pipeline: ImagePipelineSpec,
        repo_id: str,
        revision: str,
        license_spdx: Literal["Apache-2.0", "MIT", "test-only"] | None = None,
        snapshot_manifest_sha256: str,
        snapshot_file_count: int,
        snapshot_total_bytes: int,
    ) -> C4Stage1EditorSpec:
        resolved_license = license_spdx or _C4_STAGE1_MODEL_LICENSES.get(repo_id)
        if resolved_license is None:
            if editor_role != "test":
                raise ValueError("Real C4 Stage 1 specs require a pinned model license")
            resolved_license = "test-only"
        payload = {
            "schema_version": "rei-c4-stage1-editor-spec-v1",
            "editor_role": editor_role,
            "provider": provider,
            "pipeline": pipeline,
            "repo_id": repo_id,
            "revision": revision,
            "license_spdx": resolved_license,
            "snapshot_manifest_sha256": snapshot_manifest_sha256,
            "snapshot_file_count": snapshot_file_count,
            "snapshot_total_bytes": snapshot_total_bytes,
            "dependencies": C4Stage1DependencyVersions(),
            "source_width": C4_STAGE1_SOURCE_WIDTH,
            "source_height": C4_STAGE1_SOURCE_HEIGHT,
            "per_option_timeout_seconds": C4_STAGE1_PER_OPTION_TIMEOUT_SECONDS,
            "member_timeout_seconds": C4_STAGE1_MEMBER_TIMEOUT_SECONDS,
            "max_cuda_memory_mib": C4_STAGE1_MAX_CUDA_MEMORY_MIB,
            "max_cuda_memory_bytes": C4_STAGE1_MAX_CUDA_MEMORY_BYTES,
            "fallback": "none",
            "offline": True,
            "local_files_only": True,
            "use_safetensors": True,
            "torch_dtype": "bfloat16",
            "remote_code_allowed": False,
            "best_of_n_allowed": False,
            "generated_images_are_external_evidence": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(spec_id=content_id("c4_stage1_editor_spec", payload), **payload)

    @model_validator(mode="after")
    def validate_spec(self) -> Self:
        if self.provider.kind != "image_renderer" or not self.provider.uses_model:
            raise ValueError("C4 Stage 1 editors require a model-backed image renderer")
        if self.provider.model != self.repo_id:
            raise ValueError("Editor provider model must equal the pinned repository")
        if self.provider.model_revision != self.revision:
            raise ValueError("Editor provider revision must equal the pinned revision")
        expected_license = _C4_STAGE1_MODEL_LICENSES.get(self.repo_id)
        if expected_license is not None and self.license_spdx != expected_license:
            raise ValueError("Editor license differs from the pinned repository")
        if expected_license is None and (
            self.editor_role != "test" or self.license_spdx != "test-only"
        ):
            raise ValueError("Unpinned editor licenses are allowed only in test specs")
        expected = content_id(
            "c4_stage1_editor_spec",
            self.model_dump(mode="python", round_trip=True, exclude={"spec_id"}),
        )
        if self.spec_id != expected:
            raise ValueError("C4 Stage 1 editor spec ID differs from canonical content")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1LocalSnapshotBinding:
    """Runtime-only binding between one portable spec and an absolute path."""

    spec_id: str
    spec_hash: str
    snapshot_path: Path = field(repr=False)

    @classmethod
    def create(
        cls,
        spec: C4Stage1EditorSpec,
        snapshot_path: str | Path,
    ) -> C4Stage1LocalSnapshotBinding:
        return cls(
            spec_id=spec.spec_id,
            spec_hash=spec.content_hash(),
            snapshot_path=Path(snapshot_path),
        )

    def __post_init__(self) -> None:
        if not self.snapshot_path.is_absolute():
            raise ValueError("C4 Stage 1 snapshot path must be absolute")


class VerifiedC4Stage1Snapshot(FrozenArtifactModel):
    """Portable proof that a local path matched the exact manifest and spec."""

    schema_version: Literal["rei-c4-stage1-verified-snapshot-v1"] = (
        "rei-c4-stage1-verified-snapshot-v1"
    )
    verified_snapshot_id: NonEmptyId
    spec_id: NonEmptyId
    spec_hash: HashDigest
    repo_id: NonEmptyId
    revision: CommitDigest
    manifest_sha256: HashDigest
    file_count: Annotated[int, Field(gt=0)]
    total_bytes: Annotated[int, Field(gt=0)]
    local_path_recorded: Literal[False] = False
    authority_granted: Literal[False] = False

    @classmethod
    def create(cls, spec: C4Stage1EditorSpec) -> VerifiedC4Stage1Snapshot:
        payload = {
            "schema_version": "rei-c4-stage1-verified-snapshot-v1",
            "spec_id": spec.spec_id,
            "spec_hash": spec.content_hash(),
            "repo_id": spec.repo_id,
            "revision": spec.revision,
            "manifest_sha256": spec.snapshot_manifest_sha256,
            "file_count": spec.snapshot_file_count,
            "total_bytes": spec.snapshot_total_bytes,
            "local_path_recorded": False,
            "authority_granted": False,
        }
        return cls(
            verified_snapshot_id=content_id("c4_stage1_verified_snapshot", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        expected = content_id(
            "c4_stage1_verified_snapshot",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"verified_snapshot_id"},
            ),
        )
        if self.verified_snapshot_id != expected:
            raise ValueError("Verified snapshot ID differs from canonical content")
        return self


class C4Stage1ImageEvidence(FrozenArtifactModel):
    """Direct and staged PNG evidence without a publishable filesystem path."""

    schema_version: Literal["rei-c4-stage1-image-evidence-v1"] = (
        "rei-c4-stage1-image-evidence-v1"
    )
    image_evidence_id: NonEmptyId
    direct_png_sha256: HashDigest
    direct_png_size_bytes: Annotated[int, Field(gt=0)]
    direct_width: Annotated[int, Field(gt=0)]
    direct_height: Annotated[int, Field(gt=0)]
    staged_png_sha256: HashDigest
    staged_png_size_bytes: Annotated[int, Field(gt=0)]
    staged_width: Literal[1024] = C4_STAGE1_SOURCE_WIDTH
    staged_height: Literal[768] = C4_STAGE1_SOURCE_HEIGHT
    normalization_policy: Literal[
        "longcat_rgb_lanczos_1024x768",
        "omnigen_strict_identity_rgb_1024x768",
    ]
    staged_only: Literal[True] = True
    publish_authorized: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        direct_png: bytes,
        staged_png: bytes,
        normalization_policy: Literal[
            "longcat_rgb_lanczos_1024x768",
            "omnigen_strict_identity_rgb_1024x768",
        ],
    ) -> C4Stage1ImageEvidence:
        direct_width, direct_height = inspect_c4_stage1_png_bytes(direct_png)
        staged_width, staged_height = inspect_c4_stage1_png_bytes(staged_png)
        payload = {
            "schema_version": "rei-c4-stage1-image-evidence-v1",
            "direct_png_sha256": hashlib.sha256(direct_png).hexdigest(),
            "direct_png_size_bytes": len(direct_png),
            "direct_width": direct_width,
            "direct_height": direct_height,
            "staged_png_sha256": hashlib.sha256(staged_png).hexdigest(),
            "staged_png_size_bytes": len(staged_png),
            "staged_width": staged_width,
            "staged_height": staged_height,
            "normalization_policy": normalization_policy,
            "staged_only": True,
            "publish_authorized": False,
            "generated_images_are_external_evidence": False,
        }
        return cls(
            image_evidence_id=content_id("c4_stage1_image_evidence", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if (self.staged_width, self.staged_height) != (
            C4_STAGE1_SOURCE_WIDTH,
            C4_STAGE1_SOURCE_HEIGHT,
        ):
            raise ValueError("C4 Stage 1 staged image must be exactly 1024x768")
        if self.normalization_policy == "omnigen_strict_identity_rgb_1024x768":
            direct = (
                self.direct_png_sha256,
                self.direct_png_size_bytes,
                self.direct_width,
                self.direct_height,
            )
            staged = (
                self.staged_png_sha256,
                self.staged_png_size_bytes,
                self.staged_width,
                self.staged_height,
            )
            if direct != staged:
                raise ValueError("OmniGen output policy forbids output normalization")
        expected = content_id(
            "c4_stage1_image_evidence",
            self.model_dump(
                mode="python", round_trip=True, exclude={"image_evidence_id"}
            ),
        )
        if self.image_evidence_id != expected:
            raise ValueError("Stage 1 image evidence ID differs from content")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1EditorOutput:
    """Runtime-only bytes returned by a worker before parent-side publication."""

    direct_png: bytes
    staged_png: bytes
    evidence: C4Stage1ImageEvidence

    def __post_init__(self) -> None:
        direct_dimensions = inspect_c4_stage1_png_bytes(self.direct_png)
        staged_dimensions = inspect_c4_stage1_png_bytes(self.staged_png)
        if (
            hashlib.sha256(self.direct_png).hexdigest()
            != self.evidence.direct_png_sha256
        ):
            raise ValueError("Direct PNG bytes differ from their evidence")
        if (
            hashlib.sha256(self.staged_png).hexdigest()
            != self.evidence.staged_png_sha256
        ):
            raise ValueError("Staged PNG bytes differ from their evidence")
        if direct_dimensions != (
            self.evidence.direct_width,
            self.evidence.direct_height,
        ) or staged_dimensions != (
            self.evidence.staged_width,
            self.evidence.staged_height,
        ):
            raise ValueError("Stage 1 PNG dimensions differ from their evidence")


class C4Stage1WorkerRequest(FrozenArtifactModel):
    """Portable child-process request; the local snapshot path is out-of-band."""

    schema_version: Literal["rei-c4-stage1-worker-request-v1"] = (
        "rei-c4-stage1-worker-request-v1"
    )
    worker_request_id: NonEmptyId
    editor_spec: C4Stage1EditorSpec
    verified_snapshot: VerifiedC4Stage1Snapshot
    render_request: ImageRenderRequest
    call_spec: ProviderCallSpec
    output_staged_only: Literal[True] = True
    publish_authorized: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        editor_spec: C4Stage1EditorSpec,
        verified_snapshot: VerifiedC4Stage1Snapshot,
        render_request: ImageRenderRequest,
    ) -> C4Stage1WorkerRequest:
        call_spec = build_render_call_spec(
            render_request,
            timeout_seconds=editor_spec.per_option_timeout_seconds,
        )
        payload = {
            "schema_version": "rei-c4-stage1-worker-request-v1",
            "editor_spec": editor_spec,
            "verified_snapshot": verified_snapshot,
            "render_request": render_request,
            "call_spec": call_spec,
            "output_staged_only": True,
            "publish_authorized": False,
        }
        return cls(
            worker_request_id=content_id("c4_stage1_worker_request", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        spec = self.editor_spec
        snapshot = self.verified_snapshot
        request = self.render_request
        if (
            snapshot.spec_id != spec.spec_id
            or snapshot.spec_hash != spec.content_hash()
            or snapshot.manifest_sha256 != spec.snapshot_manifest_sha256
        ):
            raise ValueError("Worker snapshot proof differs from the editor spec")
        if request.provider != spec.provider or request.pipeline != spec.pipeline:
            raise ValueError("Worker render request differs from the editor spec")
        if request.mode != "image_to_image" or request.source_image is None:
            raise ValueError("C4 Stage 1 requires one source-image edit request")
        if (
            request.conditioning_method != "reference_image"
            or request.strength is not None
        ):
            raise ValueError(
                "C4 Stage 1 uses reference-image conditioning without strength"
            )
        if (request.width, request.height) != (
            C4_STAGE1_SOURCE_WIDTH,
            C4_STAGE1_SOURCE_HEIGHT,
        ):
            raise ValueError("C4 Stage 1 request must preserve source dimensions")
        if spec.editor_role != "test":
            source = request.source_image
            try:
                option_index = C4_STAGE1_OPTION_SCENE_IDS.index(request.source_spec_id)
            except ValueError as exc:
                raise ValueError(
                    "C4 Stage 1 request uses an unfrozen option scene"
                ) from exc
            if (
                request.source_spec_hash != C4_STAGE1_OPTION_SCENE_HASHES[option_index]
                or request.seed != C4_STAGE1_OPTION_SEEDS[option_index]
                or hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
                != C4_STAGE1_OPTION_PROMPT_SHA256[option_index]
                or request.prompt_language != "en"
                or request.style_id != "documentary_cinematic_v1"
                or request.profile_hash != C4_STAGE1_PROFILE_HASH
                or request.negative_prompt != ""
                or source.image_id != C4_STAGE1_SOURCE_ARTIFACT_ID
                or source.content_sha256 != C4_STAGE1_SOURCE_PNG_SHA256
                or source.media_type != "image/png"
                or source.path != f"emocio/images/{C4_STAGE1_SOURCE_ARTIFACT_ID}.png"
                or source.grounded
                or source.originating_scene_spec_id != C4_STAGE1_CURRENT_SCENE_ID
                or source.originating_scene_spec_hash != C4_STAGE1_CURRENT_SCENE_HASH
            ):
                raise ValueError("C4 Stage 1 request differs from the frozen fixture")
        if self.call_spec.request_id != request.request_id:
            raise ValueError("Worker call spec differs from its render request")
        if self.call_spec.provider != request.provider:
            raise ValueError("Worker call provider differs from its render request")
        if self.call_spec.parameters != request.provider_parameters:
            raise ValueError("Worker call parameters differ from its render request")
        if self.call_spec.seed != request.seed:
            raise ValueError("Worker call seed differs from its render request")
        if self.call_spec.timeout_seconds != spec.per_option_timeout_seconds:
            raise ValueError(
                "Worker call timeout differs from the frozen Stage 1 timeout"
            )
        if self.call_spec.fallback_policy.mode != "none":
            raise ValueError("C4 Stage 1 forbids fallback providers")
        expected = content_id(
            "c4_stage1_worker_request",
            self.model_dump(
                mode="python", round_trip=True, exclude={"worker_request_id"}
            ),
        )
        if self.worker_request_id != expected:
            raise ValueError("Stage 1 worker request ID differs from content")
        return self


class C4Stage1ChildRuntimeProvenance(FrozenArtifactModel):
    """Path-free effective child runtime and PyTorch lower-bound measurements."""

    schema_version: Literal["rei-c4-stage1-child-runtime-provenance-v1"] = (
        "rei-c4-stage1-child-runtime-provenance-v1"
    )
    runtime_provenance_id: NonEmptyId
    worker_request_id: NonEmptyId
    worker_request_hash: HashDigest
    editor_spec_id: NonEmptyId
    editor_spec_hash: HashDigest
    verified_snapshot_id: NonEmptyId
    provider: ProviderIdentity
    pipeline: ImagePipelineSpec
    dependencies: C4Stage1DependencyVersions
    pipeline_class: Literal["LongCatImageEditPipeline", "OmniGenPipeline"]
    placement: Literal["model_cpu_offload", "direct_cuda"]
    model_cpu_offload_enabled: bool
    generator_device: Literal["cpu"] = "cpu"
    effective_seed: int
    effective_call_parameters: tuple[ProviderParameter, ...]
    torch_peak_allocated_bytes: Annotated[int, Field(ge=0)]
    torch_peak_reserved_bytes: Annotated[int, Field(ge=0)]
    pytorch_peaks_are_supporting_lower_bound: Literal[True] = True
    offline: Literal[True] = True
    local_files_only: Literal[True] = True
    use_safetensors: Literal[True] = True
    remote_code_allowed: Literal[False] = False
    local_paths_recorded: Literal[False] = False
    authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        request: C4Stage1WorkerRequest,
        *,
        pipeline_class: Literal["LongCatImageEditPipeline", "OmniGenPipeline"],
        placement: Literal["model_cpu_offload", "direct_cuda"],
        model_cpu_offload_enabled: bool,
        torch_peak_allocated_bytes: int,
        torch_peak_reserved_bytes: int,
    ) -> C4Stage1ChildRuntimeProvenance:
        spec = request.editor_spec
        payload = {
            "schema_version": "rei-c4-stage1-child-runtime-provenance-v1",
            "worker_request_id": request.worker_request_id,
            "worker_request_hash": request.content_hash(),
            "editor_spec_id": spec.spec_id,
            "editor_spec_hash": spec.content_hash(),
            "verified_snapshot_id": request.verified_snapshot.verified_snapshot_id,
            "provider": spec.provider,
            "pipeline": spec.pipeline,
            "dependencies": spec.dependencies,
            "pipeline_class": pipeline_class,
            "placement": placement,
            "model_cpu_offload_enabled": model_cpu_offload_enabled,
            "generator_device": "cpu",
            "effective_seed": request.render_request.seed,
            "effective_call_parameters": request.call_spec.parameters,
            "torch_peak_allocated_bytes": torch_peak_allocated_bytes,
            "torch_peak_reserved_bytes": torch_peak_reserved_bytes,
            "pytorch_peaks_are_supporting_lower_bound": True,
            "offline": True,
            "local_files_only": True,
            "use_safetensors": True,
            "remote_code_allowed": False,
            "local_paths_recorded": False,
            "authority_granted": False,
        }
        return cls(
            runtime_provenance_id=content_id("c4_stage1_child_runtime", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_runtime(self) -> Self:
        if self.torch_peak_reserved_bytes < self.torch_peak_allocated_bytes:
            raise ValueError(
                "PyTorch peak reserved bytes cannot be below allocated bytes"
            )
        if self.pipeline_class == "LongCatImageEditPipeline":
            expected = ("model_cpu_offload", True)
            expected_pipeline = "diffusers.LongCatImageEditPipeline"
        else:
            expected = ("direct_cuda", False)
            expected_pipeline = "diffusers.OmniGenPipeline"
        if (self.placement, self.model_cpu_offload_enabled) != expected:
            raise ValueError("Child placement differs from the exact provider policy")
        if self.pipeline.implementation != expected_pipeline:
            raise ValueError(
                "Child pipeline class differs from effective pipeline spec"
            )
        if self.effective_call_parameters != tuple(
            sorted(self.effective_call_parameters, key=lambda item: item.name)
        ):
            raise ValueError("Effective child call parameters must use canonical order")
        expected_id = content_id(
            "c4_stage1_child_runtime",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"runtime_provenance_id"},
            ),
        )
        if self.runtime_provenance_id != expected_id:
            raise ValueError("Child runtime provenance ID differs from content")
        return self

    def validate_against(
        self,
        request: C4Stage1WorkerRequest,
    ) -> C4Stage1ChildRuntimeProvenance:
        spec = request.editor_spec
        if (
            self.worker_request_id != request.worker_request_id
            or self.worker_request_hash != request.content_hash()
            or self.editor_spec_id != spec.spec_id
            or self.editor_spec_hash != spec.content_hash()
            or self.verified_snapshot_id
            != request.verified_snapshot.verified_snapshot_id
            or self.provider != spec.provider
            or self.pipeline != spec.pipeline
            or self.dependencies != spec.dependencies
            or self.effective_seed != request.render_request.seed
            or self.effective_call_parameters != request.call_spec.parameters
        ):
            raise ValueError("Child runtime provenance differs from the worker request")
        return self


def _validate_c4_stage1_result_lineage(
    request: C4Stage1WorkerRequest,
    evidence: C4Stage1ImageEvidence,
) -> None:
    """Re-derive the exact parent request and provider-specific output boundary."""

    spec = request.editor_spec
    provider = spec.provider
    pipeline = spec.pipeline

    # Re-run every nested content-addressed request boundary.  The request is
    # parent-held, but result acceptance must not rely on a child-provided ID
    # alone when a fully re-derived contract is available.
    spec.validate_spec()
    request.verified_snapshot.validate_id()
    request.render_request.validate_request()
    request.validate_request()
    expected_call_spec = build_render_call_spec(
        request.render_request,
        timeout_seconds=spec.per_option_timeout_seconds,
    )
    if request.call_spec != expected_call_spec:
        raise ValueError("Worker request call lineage differs from canonical content")

    adapter_key = (
        provider.model,
        provider.model_revision,
        provider.implementation,
        provider.implementation_revision,
        pipeline.implementation,
        pipeline.implementation_revision,
    )
    exact_adapter = adapter_key in _C4_STAGE1_OUTPUT_POLICY_BY_ADAPTER
    try:
        allowed_roles, expected_policy, expected_normalization = (
            _C4_STAGE1_OUTPUT_POLICY_BY_ADAPTER[adapter_key]
        )
    except KeyError as exc:
        if spec.editor_role != "test":
            raise ValueError(
                "Worker result uses an unsupported Stage 1 provider pipeline"
            ) from exc
        test_policy = {
            "diffusers.LongCatImageEditPipeline": (
                "longcat_rgb_lanczos_1024x768",
                "rgb_then_pillow_lanczos_1024x768",
            ),
            "diffusers.OmniGenPipeline": (
                "omnigen_strict_identity_rgb_1024x768",
                "strict_identity_rgb_1024x768_no_resize_no_crop",
            ),
        }.get(pipeline.implementation)
        if test_policy is None:
            raise ValueError(
                "Worker result uses an unsupported Stage 1 provider pipeline"
            ) from exc
        allowed_roles = frozenset({"test"})
        expected_policy, expected_normalization = test_policy
    if spec.editor_role not in allowed_roles:
        raise ValueError("Stage 1 provider differs from its frozen editor role")

    if exact_adapter:
        expected_provider_id = content_id(
            "provider",
            provider.model_dump(
                mode="python",
                round_trip=True,
                exclude={"provider_id"},
            ),
        )
        if provider.provider_id != expected_provider_id:
            raise ValueError("Stage 1 provider identity differs from canonical content")

    pipeline_parameters = {
        parameter.name: parameter.canonical_json_value
        for parameter in pipeline.parameters
    }
    normalization_parameter = pipeline_parameters.get("output.normalization")
    if (exact_adapter or normalization_parameter is not None) and (
        normalization_parameter
        != canonical_json_bytes(expected_normalization).decode("utf-8")
    ):
        raise ValueError("Stage 1 pipeline normalization differs from its provider")
    snapshot_parameter = pipeline_parameters.get("load.snapshot_manifest_sha256")
    if (exact_adapter or snapshot_parameter is not None) and (
        snapshot_parameter
        != canonical_json_bytes(spec.snapshot_manifest_sha256).decode("utf-8")
    ):
        raise ValueError("Stage 1 pipeline snapshot lineage differs from its spec")
    if evidence.normalization_policy != expected_policy:
        raise ValueError("Stage 1 image evidence policy differs from its provider")

    if expected_policy == "omnigen_strict_identity_rgb_1024x768":
        direct = (
            evidence.direct_png_sha256,
            evidence.direct_png_size_bytes,
            evidence.direct_width,
            evidence.direct_height,
        )
        staged = (
            evidence.staged_png_sha256,
            evidence.staged_png_size_bytes,
            evidence.staged_width,
            evidence.staged_height,
        )
        if direct != staged:
            raise ValueError("OmniGen worker result forbids output normalization")


class C4Stage1WorkerResult(FrozenArtifactModel):
    """Child-process result that can only describe staged, unpublished output."""

    schema_version: Literal["rei-c4-stage1-worker-result-v1"] = (
        "rei-c4-stage1-worker-result-v1"
    )
    worker_result_id: NonEmptyId
    worker_request_id: NonEmptyId
    worker_request_hash: HashDigest
    status: Literal["succeeded", "failed"]
    image_evidence: C4Stage1ImageEvidence | None = None
    runtime_provenance: C4Stage1ChildRuntimeProvenance | None = None
    failure_code: C4Stage1FailureCode | None = None
    failure_message: NonEmptyText | None = None
    output_staged_only: Literal[True] = True
    publish_authorized: Literal[False] = False
    published_artifact_id: Literal[None] = None

    @classmethod
    def succeeded(
        cls,
        request: C4Stage1WorkerRequest,
        evidence: C4Stage1ImageEvidence,
        runtime_provenance: C4Stage1ChildRuntimeProvenance,
    ) -> C4Stage1WorkerResult:
        return cls._create(
            request=request,
            status="succeeded",
            evidence=evidence,
            runtime_provenance=runtime_provenance,
        )

    @classmethod
    def failed(
        cls,
        request: C4Stage1WorkerRequest,
        *,
        failure_code: str,
        failure_message: str | None = None,
        runtime_provenance: C4Stage1ChildRuntimeProvenance | None = None,
    ) -> C4Stage1WorkerResult:
        del failure_message
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", failure_code) is None:
            raise ValueError("C4 Stage 1 failure code is invalid")
        sanitized = f"C4 Stage 1 worker failed closed ({failure_code})"
        return cls._create(
            request=request,
            status="failed",
            runtime_provenance=runtime_provenance,
            failure_code=failure_code,
            failure_message=sanitized,
        )

    @classmethod
    def _create(
        cls,
        *,
        request: C4Stage1WorkerRequest,
        status: Literal["succeeded", "failed"],
        evidence: C4Stage1ImageEvidence | None = None,
        runtime_provenance: C4Stage1ChildRuntimeProvenance | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> C4Stage1WorkerResult:
        payload = {
            "schema_version": "rei-c4-stage1-worker-result-v1",
            "worker_request_id": request.worker_request_id,
            "worker_request_hash": request.content_hash(),
            "status": status,
            "image_evidence": evidence,
            "runtime_provenance": runtime_provenance,
            "failure_code": failure_code,
            "failure_message": failure_message,
            "output_staged_only": True,
            "publish_authorized": False,
            "published_artifact_id": None,
        }
        return cls(
            worker_result_id=content_id("c4_stage1_worker_result", payload),
            **payload,
        )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.runtime_provenance is not None and (
            self.runtime_provenance.worker_request_id != self.worker_request_id
            or self.runtime_provenance.worker_request_hash != self.worker_request_hash
        ):
            raise ValueError("Worker result runtime provenance cites another request")
        if self.status == "succeeded":
            if self.image_evidence is None:
                raise ValueError(
                    "Successful Stage 1 worker result requires image evidence"
                )
            if self.runtime_provenance is None:
                raise ValueError(
                    "Successful Stage 1 worker result requires runtime provenance"
                )
            if self.failure_code is not None or self.failure_message is not None:
                raise ValueError(
                    "Successful Stage 1 worker result forbids failure data"
                )
        else:
            if self.image_evidence is not None:
                raise ValueError("Failed Stage 1 worker result cannot expose output")
            if self.failure_code is None or self.failure_message is None:
                raise ValueError("Failed Stage 1 worker result requires failure data")
            expected_failure = f"C4 Stage 1 worker failed closed ({self.failure_code})"
            if self.failure_message != expected_failure:
                raise ValueError("Stage 1 failure message must be fixed and path-free")
        expected = content_id(
            "c4_stage1_worker_result",
            self.model_dump(
                mode="python", round_trip=True, exclude={"worker_result_id"}
            ),
        )
        if self.worker_result_id != expected:
            raise ValueError("Stage 1 worker result ID differs from content")
        return self

    def validate_against(
        self,
        request: C4Stage1WorkerRequest,
    ) -> C4Stage1WorkerResult:
        if (
            self.worker_request_id != request.worker_request_id
            or self.worker_request_hash != request.content_hash()
        ):
            raise ValueError("Worker result differs from the parent-held request")
        if self.runtime_provenance is not None:
            self.runtime_provenance.validate_against(request)
        if self.image_evidence is not None:
            _validate_c4_stage1_result_lineage(request, self.image_evidence)
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1WorkerExecution:
    """Runtime-only successful worker execution with staged bytes and provenance."""

    request: C4Stage1WorkerRequest
    output: C4Stage1EditorOutput = field(repr=False)
    runtime_provenance: C4Stage1ChildRuntimeProvenance

    def __post_init__(self) -> None:
        self.runtime_provenance.validate_against(self.request)

    @property
    def worker_result(self) -> C4Stage1WorkerResult:
        return C4Stage1WorkerResult.succeeded(
            self.request,
            self.output.evidence,
            self.runtime_provenance,
        )


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    mode_type: int
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True, slots=True)
class _SnapshotInventory:
    files: dict[str, _FileIdentity]
    directories: tuple[str, ...]


def _identity(metadata: os.stat_result) -> _FileIdentity:
    return _FileIdentity(
        mode_type=stat.S_IFMT(metadata.st_mode),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        size=metadata.st_size,
        mtime_ns=getattr(metadata, "st_mtime_ns", int(metadata.st_mtime * 1e9)),
        ctime_ns=getattr(metadata, "st_ctime_ns", int(metadata.st_ctime * 1e9)),
    )


def _is_forbidden_link(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(reparse and attributes & reparse)


def _lstat_regular(path: Path) -> tuple[os.stat_result, _FileIdentity]:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise ValueError("C4 Stage 1 snapshot entry is unreadable") from exc
    if _is_forbidden_link(metadata):
        raise ValueError("C4 Stage 1 snapshot forbids links and reparse points")
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("C4 Stage 1 snapshot entry is not a regular file")
    if metadata.st_nlink != 1:
        raise ValueError("C4 Stage 1 snapshot forbids hard-linked files")
    return metadata, _identity(metadata)


def _open_stable_regular(
    path: Path, *, expected_size: int
) -> tuple[int, _FileIdentity]:
    path_metadata, path_identity = _lstat_regular(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("C4 Stage 1 snapshot file cannot be opened safely") from exc
    try:
        handle_metadata = os.fstat(descriptor)
        handle_identity = _identity(handle_metadata)
        if not stat.S_ISREG(handle_metadata.st_mode):
            raise ValueError("C4 Stage 1 snapshot handle is not a regular file")
        if path_identity != handle_identity:
            raise ValueError("C4 Stage 1 snapshot path changed while opening")
        if handle_metadata.st_size != expected_size:
            raise ValueError("C4 Stage 1 snapshot file size differs from manifest")
        return descriptor, handle_identity
    except Exception:
        os.close(descriptor)
        raise


def _finish_stable_regular(
    descriptor: int,
    path: Path,
    initial_identity: _FileIdentity,
) -> None:
    try:
        final_handle_identity = _identity(os.fstat(descriptor))
        if final_handle_identity != initial_identity:
            raise ValueError("C4 Stage 1 snapshot file changed while reading")
        _, final_path_identity = _lstat_regular(path)
        if final_path_identity != initial_identity:
            raise ValueError("C4 Stage 1 snapshot path changed while reading")
    finally:
        os.close(descriptor)


def _read_stable_regular(path: Path, *, max_bytes: int) -> tuple[bytes, _FileIdentity]:
    _, initial = _lstat_regular(path)
    if initial.size > max_bytes:
        raise ValueError("C4 Stage 1 snapshot manifest exceeds its byte limit")
    descriptor, initial = _open_stable_regular(path, expected_size=initial.size)
    payload = bytearray()
    try:
        while True:
            chunk = os.read(
                descriptor, min(_READ_CHUNK_BYTES, max_bytes + 1 - len(payload))
            )
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > max_bytes:
                raise ValueError("C4 Stage 1 snapshot manifest exceeds its byte limit")
        if len(payload) != initial.size:
            raise ValueError("C4 Stage 1 snapshot manifest was truncated while reading")
    except Exception:
        os.close(descriptor)
        raise
    _finish_stable_regular(descriptor, path, initial)
    return bytes(payload), initial


def _hash_stable_regular(
    path: Path,
    *,
    expected_size: int,
) -> tuple[str, _FileIdentity]:
    descriptor, initial = _open_stable_regular(path, expected_size=expected_size)
    digest = hashlib.sha256()
    bytes_read = 0
    try:
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            bytes_read += len(chunk)
            if bytes_read > expected_size:
                raise ValueError("C4 Stage 1 snapshot file grew while hashing")
        if bytes_read != expected_size:
            raise ValueError("C4 Stage 1 snapshot file was truncated while hashing")
    except Exception:
        os.close(descriptor)
        raise
    _finish_stable_regular(descriptor, path, initial)
    return digest.hexdigest(), initial


def _snapshot_inventory(root: Path) -> _SnapshotInventory:
    files: dict[str, _FileIdentity] = {}
    directories: list[str] = []
    stack: list[tuple[Path, tuple[str, ...]]] = [(root, ())]
    while stack:
        directory, parts = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise ValueError("C4 Stage 1 snapshot directory is unreadable") from exc
        for entry in entries:
            path = Path(entry.path)
            relative_parts = (*parts, entry.name)
            relative = "/".join(relative_parts)
            try:
                metadata = os.lstat(path)
            except OSError as exc:
                raise ValueError("C4 Stage 1 snapshot entry is unreadable") from exc
            if _is_forbidden_link(metadata):
                raise ValueError("C4 Stage 1 snapshot forbids links and reparse points")
            try:
                resolved = path.resolve(strict=True)
            except OSError as exc:
                raise ValueError(
                    "C4 Stage 1 snapshot entry cannot be resolved"
                ) from exc
            if not resolved.is_relative_to(root):
                raise ValueError("C4 Stage 1 snapshot entry escapes its root")
            if not parts and entry.name == ".cache":
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(
                        "C4 Stage 1 snapshot .cache entry must be a directory"
                    )
                continue
            if stat.S_ISDIR(metadata.st_mode):
                directories.append(relative)
                stack.append((path, relative_parts))
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise ValueError("C4 Stage 1 snapshot forbids hard-linked files")
                if not parts and entry.name == DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME:
                    continue
                files[relative] = _identity(metadata)
                if len(files) > C4_STAGE1_MAX_SNAPSHOT_FILES:
                    raise ValueError("C4 Stage 1 snapshot contains too many files")
            else:
                raise ValueError("C4 Stage 1 snapshot contains a special file")
    return _SnapshotInventory(files=files, directories=tuple(sorted(directories)))


def _expected_directories(paths: tuple[str, ...]) -> tuple[str, ...]:
    result: set[str] = set()
    for value in paths:
        parts = value.split("/")
        for index in range(1, len(parts)):
            result.add("/".join(parts[:index]))
    return tuple(sorted(result))


def verify_c4_stage1_snapshot(
    spec: C4Stage1EditorSpec,
    binding: C4Stage1LocalSnapshotBinding,
    *,
    after_verification: Callable[[], object] | None = None,
) -> VerifiedC4Stage1Snapshot:
    """Verify one exact snapshot before invoking any injected/import callback.

    Each file is hashed through one handle with pre/post ``fstat`` and matching
    path ``lstat`` identities.  A final complete inventory scan proves that no
    file or directory was added, removed, replaced, or changed during hashing.
    """

    if binding.spec_id != spec.spec_id or binding.spec_hash != spec.content_hash():
        raise ValueError("C4 Stage 1 runtime binding differs from the portable spec")
    path = binding.snapshot_path
    try:
        root_metadata = os.lstat(path)
    except OSError as exc:
        raise ValueError("C4 Stage 1 snapshot root does not exist") from exc
    if _is_forbidden_link(root_metadata):
        raise ValueError("C4 Stage 1 snapshot root cannot be a link or reparse point")
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("C4 Stage 1 snapshot root is not a directory")
    try:
        root = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("C4 Stage 1 snapshot root cannot be resolved") from exc
    lexical_root = Path(os.path.abspath(path))
    if os.path.normcase(os.fspath(root)) != os.path.normcase(os.fspath(lexical_root)):
        raise ValueError("C4 Stage 1 snapshot path traverses a linked parent")
    root_identity = _identity(root_metadata)

    manifest_path = root / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    manifest_bytes, manifest_identity = _read_stable_regular(
        manifest_path,
        max_bytes=C4_STAGE1_MAX_MANIFEST_BYTES,
    )
    if hashlib.sha256(manifest_bytes).hexdigest() != spec.snapshot_manifest_sha256:
        raise ValueError("C4 Stage 1 snapshot manifest digest differs from its pin")
    try:
        manifest = DiffusersSnapshotManifest.model_validate_json(manifest_bytes)
    except Exception as exc:
        raise ValueError("C4 Stage 1 snapshot manifest is invalid") from exc
    if canonical_snapshot_manifest_bytes(manifest) != manifest_bytes:
        raise ValueError("C4 Stage 1 snapshot manifest is not canonical")
    if manifest.repo_id != spec.repo_id or manifest.revision != spec.revision:
        raise ValueError("C4 Stage 1 snapshot manifest repository pin differs")
    if len(manifest.files) != spec.snapshot_file_count:
        raise ValueError("C4 Stage 1 snapshot manifest file count differs")
    if sum(item.size_bytes for item in manifest.files) != spec.snapshot_total_bytes:
        raise ValueError("C4 Stage 1 snapshot manifest byte total differs")

    initial_inventory = _snapshot_inventory(root)
    manifest_paths = tuple(item.relative_path for item in manifest.files)
    if tuple(sorted(initial_inventory.files)) != manifest_paths:
        raise ValueError("C4 Stage 1 snapshot inventory differs from its manifest")
    if initial_inventory.directories != _expected_directories(manifest_paths):
        raise ValueError("C4 Stage 1 snapshot directory inventory differs")

    hashed_identities: dict[str, _FileIdentity] = {}
    for item in manifest.files:
        inventory_identity = initial_inventory.files[item.relative_path]
        if inventory_identity.size != item.size_bytes:
            raise ValueError("C4 Stage 1 snapshot file size differs from manifest")
        digest, hashed_identity = _hash_stable_regular(
            root.joinpath(*item.relative_path.split("/")),
            expected_size=item.size_bytes,
        )
        if digest != item.sha256:
            raise ValueError("C4 Stage 1 snapshot file digest differs from manifest")
        if hashed_identity != inventory_identity:
            raise ValueError("C4 Stage 1 snapshot file changed after inventory")
        hashed_identities[item.relative_path] = hashed_identity

    final_manifest_bytes, final_manifest_identity = _read_stable_regular(
        manifest_path,
        max_bytes=C4_STAGE1_MAX_MANIFEST_BYTES,
    )
    if (
        final_manifest_bytes != manifest_bytes
        or final_manifest_identity != manifest_identity
    ):
        raise ValueError("C4 Stage 1 snapshot manifest changed during verification")
    final_inventory = _snapshot_inventory(root)
    if final_inventory.directories != initial_inventory.directories:
        raise ValueError("C4 Stage 1 snapshot directories changed during verification")
    if final_inventory.files != hashed_identities:
        raise ValueError("C4 Stage 1 snapshot files changed during verification")
    try:
        final_root_metadata = os.lstat(root)
    except OSError as exc:
        raise ValueError(
            "C4 Stage 1 snapshot root changed during verification"
        ) from exc
    if _is_forbidden_link(final_root_metadata) or (
        _identity(final_root_metadata) != root_identity
    ):
        raise ValueError("C4 Stage 1 snapshot root changed during verification")

    verified = VerifiedC4Stage1Snapshot.create(spec)
    if after_verification is not None:
        after_verification()
    return verified


def inspect_c4_stage1_png_bytes(payload: bytes) -> tuple[int, int]:
    """Validate the strict raw PNG boundary and return ``(width, height)``."""

    if not isinstance(payload, bytes):
        raise TypeError("C4 Stage 1 PNG payload must be bytes")
    if len(payload) > C4_STAGE1_MAX_PNG_BYTES:
        raise ValueError("C4 Stage 1 PNG exceeds its byte limit")
    if not payload.startswith(_PNG_SIGNATURE):
        raise ValueError("C4 Stage 1 output is not a PNG")

    cursor = len(_PNG_SIGNATURE)
    chunk_count = 0
    saw_ihdr = False
    saw_idat = False
    ended_idat = False
    saw_iend = False
    width = height = channels = 0
    compressed_parts: list[bytes] = []
    while cursor < len(payload):
        if cursor + 12 > len(payload):
            raise ValueError("C4 Stage 1 PNG contains a truncated chunk")
        length = struct.unpack(">I", payload[cursor : cursor + 4])[0]
        kind = payload[cursor + 4 : cursor + 8]
        data_start = cursor + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(payload):
            raise ValueError("C4 Stage 1 PNG chunk length exceeds its payload")
        data = payload[data_start:data_end]
        expected_crc = struct.unpack(">I", payload[data_end:crc_end])[0]
        actual_crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ValueError("C4 Stage 1 PNG chunk CRC differs")
        chunk_count += 1
        if chunk_count > 65_536:
            raise ValueError("C4 Stage 1 PNG contains too many chunks")
        if kind not in _PNG_ALLOWED_CHUNKS:
            raise ValueError("C4 Stage 1 PNG forbids ancillary or unknown chunks")
        if kind == b"IHDR":
            if saw_ihdr or chunk_count != 1 or length != 13:
                raise ValueError("C4 Stage 1 PNG has an invalid IHDR")
            width, height, bit_depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            if not (1 <= width <= C4_STAGE1_MAX_PNG_DIMENSION):
                raise ValueError("C4 Stage 1 PNG width is out of bounds")
            if not (1 <= height <= C4_STAGE1_MAX_PNG_DIMENSION):
                raise ValueError("C4 Stage 1 PNG height is out of bounds")
            if bit_depth != 8 or color_type not in {2, 6}:
                raise ValueError("C4 Stage 1 PNG must be 8-bit RGB or RGBA")
            if compression != 0 or filtering != 0 or interlace != 0:
                raise ValueError("C4 Stage 1 PNG uses an unsupported encoding")
            channels = 3 if color_type == 2 else 4
            saw_ihdr = True
        elif kind == b"IDAT":
            if not saw_ihdr or saw_iend or ended_idat:
                raise ValueError("C4 Stage 1 PNG has invalid IDAT ordering")
            saw_idat = True
            compressed_parts.append(data)
        else:
            if not saw_idat or saw_iend or length != 0:
                raise ValueError("C4 Stage 1 PNG has an invalid IEND")
            saw_iend = True
        if saw_idat and kind != b"IDAT" and kind != b"IEND":
            ended_idat = True
        cursor = crc_end
        if saw_iend:
            break

    if not (saw_ihdr and saw_idat and saw_iend) or cursor != len(payload):
        raise ValueError("C4 Stage 1 PNG is incomplete or has trailing bytes")

    expected_decoded = (1 + width * channels) * height
    decoder = zlib.decompressobj()
    decoded = bytearray()
    for compressed in compressed_parts:
        pending = compressed
        while pending:
            remaining = expected_decoded + 1 - len(decoded)
            if remaining <= 0:
                raise ValueError("C4 Stage 1 PNG expands beyond its dimensions")
            decoded.extend(decoder.decompress(pending, remaining))
            pending = decoder.unconsumed_tail
            if pending and len(decoded) >= expected_decoded + 1:
                raise ValueError("C4 Stage 1 PNG expands beyond its dimensions")
    remaining = expected_decoded + 1 - len(decoded)
    if remaining <= 0:
        raise ValueError("C4 Stage 1 PNG expands beyond its dimensions")
    decoded.extend(decoder.flush(remaining))
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("C4 Stage 1 PNG contains an invalid zlib stream")
    if len(decoded) != expected_decoded:
        raise ValueError("C4 Stage 1 PNG decoded size differs from its dimensions")
    row_bytes = 1 + width * channels
    if any(decoded[index] > 4 for index in range(0, len(decoded), row_bytes)):
        raise ValueError("C4 Stage 1 PNG uses an invalid row filter")
    return width, height


def canonical_provider_parameters(
    values: dict[str, object],
) -> tuple[ProviderParameter, ...]:
    """Build path-free, canonically ordered provider pipeline parameters."""

    return tuple(
        ProviderParameter(
            name=name,
            canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
        )
        for name, value in sorted(values.items())
    )


__all__ = [
    "C4_STAGE1_CURRENT_SCENE_HASH",
    "C4_STAGE1_CURRENT_SCENE_ID",
    "C4_STAGE1_MAX_CUDA_MEMORY_BYTES",
    "C4_STAGE1_MAX_CUDA_MEMORY_MIB",
    "C4_STAGE1_MEMBER_TIMEOUT_SECONDS",
    "C4_STAGE1_OPTION_ORDER",
    "C4_STAGE1_OPTION_PROMPT_SHA256",
    "C4_STAGE1_OPTION_SCENE_HASHES",
    "C4_STAGE1_OPTION_SCENE_IDS",
    "C4_STAGE1_OPTION_SEEDS",
    "C4_STAGE1_PER_OPTION_TIMEOUT_SECONDS",
    "C4_STAGE1_PROFILE_HASH",
    "C4_STAGE1_SOURCE_ARTIFACT_ID",
    "C4_STAGE1_SOURCE_HEIGHT",
    "C4_STAGE1_SOURCE_WIDTH",
    "C4_STAGE1_SOURCE_PNG_SHA256",
    "C4Stage1DependencyVersions",
    "C4Stage1ChildRuntimeProvenance",
    "C4Stage1EditorOutput",
    "C4Stage1EditorSpec",
    "C4Stage1ImageEvidence",
    "C4Stage1LocalSnapshotBinding",
    "C4Stage1WorkerRequest",
    "C4Stage1WorkerResult",
    "C4Stage1WorkerExecution",
    "VerifiedC4Stage1Snapshot",
    "canonical_provider_parameters",
    "inspect_c4_stage1_png_bytes",
    "verify_c4_stage1_snapshot",
]
