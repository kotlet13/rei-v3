"""Pinned, offline DINOv2 Base adapter for internal visual feature vectors.

Importing this module never imports Torch, Transformers, or Pillow and never
loads model weights.  The optional runtime is reached only after the source PNG
and the complete local model snapshot have passed byte-level verification.
"""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import Field, TypeAdapter, model_validator

from ..ids import canonical_json_bytes, content_id, utc_now
from ..models.common import (
    ArtifactRelativePath,
    FrozenModel,
    HashDigest,
    NonEmptyText,
    SafetyNotice,
)
from ..models.emocio import ImageArtifact
from ..models.provider import (
    PositiveSeconds,
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_contract,
)
from ..providers.protocols import (
    ImageEncodingRequest,
    ImageEncodingSpec,
    VerifiedImageEncoding,
)
from .artifacts import LocalPngArtifactStore
from .diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersSnapshotManifest,
    build_diffusers_snapshot_manifest,
    canonical_snapshot_manifest_bytes,
)
from .vector_encoding import (
    canonical_l2_float32_le_vector,
    verified_float32_le_vector,
)


DINOV2_BASE_MODEL_ID = "facebook/dinov2-base"
DINOV2_BASE_MODEL_REVISION = "f9e44c814b77203eaa57a6bdbbd535f21ede1415"
DINOV2_BASE_DIMENSIONS = 768
DINOV2_BASE_TORCH_VERSION = "2.13.0"
DINOV2_BASE_TORCHVISION_VERSION = "0.28.0"
DINOV2_BASE_PILLOW_VERSION = "12.3.0"
DINOV2_BASE_TRANSFORMERS_VERSION = "5.13.0"
DINOV2_BASE_IMAGE_PROCESSOR_BACKEND = "pil"
DINOV2_ENCODER_SEED = 0
DINOV2_BASE_IMPLEMENTATION_REVISION = (
    "c4-dinov2-base-v3"
    ";torch=2.13.0"
    ";torchvision=0.28.0"
    ";pillow=12.3.0"
    ";transformers=5.13.0"
    ";dtype=float32"
    ";image_processor_backend=pil"
    ";deterministic_algorithms=true"
    ";snapshot_verification=pre_and_post_inference_sha256"
    ";snapshot_trust=trusted_local_filesystem"
    ";runtime_reassertion=per_inference"
)

_PATH_ADAPTER = TypeAdapter(ArtifactRelativePath)


class DinoV2RuntimeConfig(FrozenModel):
    """Closed local runtime settings; network-backed model resolution is forbidden."""

    local_snapshot_path: NonEmptyText
    expected_snapshot_manifest_sha256: HashDigest
    device: Literal["cpu", "cuda"] = "cpu"
    local_files_only: Literal[True] = True
    offline: Literal[True] = True
    torch_dtype: Literal["float32"] = "float32"
    image_processor_backend: Literal["pil"] = DINOV2_BASE_IMAGE_PROCESSOR_BACKEND
    deterministic_algorithms: Literal[True] = True
    cudnn_benchmark: Literal[False] = False
    cudnn_deterministic: Literal[True] = True
    float32_matmul_precision: Literal["highest"] = "highest"
    snapshot_trust_boundary: Literal["trusted_local_filesystem"] = (
        "trusted_local_filesystem"
    )
    torch_version: Literal["2.13.0"] = DINOV2_BASE_TORCH_VERSION
    torchvision_version: Literal["0.28.0"] = DINOV2_BASE_TORCHVISION_VERSION
    pillow_version: Literal["12.3.0"] = DINOV2_BASE_PILLOW_VERSION
    transformers_version: Literal["5.13.0"] = DINOV2_BASE_TRANSFORMERS_VERSION

    @model_validator(mode="after")
    def validate_snapshot_path(self) -> Self:
        if not Path(self.local_snapshot_path).is_absolute():
            raise ValueError("DINOv2 local snapshot path must be absolute")
        return self


@runtime_checkable
class DinoV2FeatureBackend(Protocol):
    """Small inference seam returning the raw CLS feature for canonicalization."""

    def encode_png(
        self,
        png_bytes: bytes,
        *,
        verified_snapshot_path: Path,
    ) -> tuple[float, ...]: ...


class LazyTransformersDinoV2Backend:
    """Lazy Transformers implementation; construction performs no optional imports."""

    def __init__(self, config: DinoV2RuntimeConfig) -> None:
        self._config = config
        self._components: tuple[object, object, object, object] | None = None
        self._loaded_snapshot: Path | None = None
        self._lock = threading.RLock()

    def _apply_deterministic_runtime(self, torch: object) -> None:
        torch.use_deterministic_algorithms(
            self._config.deterministic_algorithms,
        )
        torch.backends.cudnn.benchmark = self._config.cudnn_benchmark
        torch.backends.cudnn.deterministic = self._config.cudnn_deterministic
        torch.set_float32_matmul_precision(
            self._config.float32_matmul_precision,
        )

    def _load_components(
        self,
        snapshot_path: Path,
    ) -> tuple[object, object, object, object]:
        if self._components is not None:
            if self._loaded_snapshot != snapshot_path:
                raise ValueError(
                    "A loaded DINOv2 backend cannot switch model snapshots"
                )
            self._apply_deterministic_runtime(self._components[2])
            return self._components

        try:
            import torch
            from PIL import Image
            from transformers import AutoImageProcessor, AutoModel
        except ImportError as exc:
            raise RuntimeError(
                "Install app/backend/requirements-renderer.txt before DINOv2 encoding"
            ) from exc

        try:
            installed_versions = {
                "torch": version("torch"),
                "torchvision": version("torchvision"),
                "Pillow": version("Pillow"),
                "transformers": version("transformers"),
            }
        except PackageNotFoundError as exc:
            raise RuntimeError(
                "Install app/backend/requirements-renderer.txt before DINOv2 encoding"
            ) from exc
        installed_torch_base = installed_versions["torch"].split("+", 1)[0]
        if installed_torch_base != self._config.torch_version:
            raise RuntimeError(
                "Installed Torch base version differs from the DINOv2 runtime pin"
            )
        if installed_versions["torchvision"] != self._config.torchvision_version:
            raise RuntimeError(
                "Installed Torchvision version differs from the DINOv2 runtime pin"
            )
        if installed_versions["Pillow"] != self._config.pillow_version:
            raise RuntimeError(
                "Installed Pillow version differs from the DINOv2 runtime pin"
            )
        if installed_versions["transformers"] != self._config.transformers_version:
            raise RuntimeError(
                "Installed Transformers version differs from the DINOv2 runtime pin"
            )

        self._apply_deterministic_runtime(torch)

        load_target = str(snapshot_path)
        common_options = {
            "local_files_only": True,
            "trust_remote_code": False,
        }
        processor = AutoImageProcessor.from_pretrained(
            load_target,
            backend=self._config.image_processor_backend,
            **common_options,
        )
        model = AutoModel.from_pretrained(
            load_target,
            dtype=torch.float32,
            use_safetensors=True,
            **common_options,
        )
        model = model.eval().to(device=self._config.device, dtype=torch.float32)
        self._components = (processor, model, torch, Image)
        self._loaded_snapshot = snapshot_path
        return self._components

    def encode_png(
        self,
        png_bytes: bytes,
        *,
        verified_snapshot_path: Path,
    ) -> tuple[float, ...]:
        with self._lock:
            return self._encode_png_locked(
                png_bytes,
                verified_snapshot_path=verified_snapshot_path,
            )

    def _encode_png_locked(
        self,
        png_bytes: bytes,
        *,
        verified_snapshot_path: Path,
    ) -> tuple[float, ...]:
        processor, model, torch, image_module = self._load_components(
            verified_snapshot_path
        )
        with image_module.open(io.BytesIO(png_bytes)) as opened:
            image = opened.convert("RGB").copy()
        inputs = processor(images=image, return_tensors="pt")
        inputs = {
            name: tensor.to(self._config.device) for name, tensor in inputs.items()
        }
        with torch.inference_mode():
            outputs = model(**inputs)
        hidden = getattr(outputs, "last_hidden_state", None)
        if hidden is None:
            raise RuntimeError("DINOv2 output has no last_hidden_state")
        cls_feature = hidden[:, 0, :]
        values = (
            cls_feature.detach()
            .to(device="cpu", dtype=torch.float32)
            .reshape(-1)
            .tolist()
        )
        return tuple(float(value) for value in values)


@dataclass(frozen=True, slots=True)
class StoredFloat32Vector:
    relative_path: str
    content_sha256: str
    dimensions: int
    size_bytes: int


class LocalFloat32VectorStore:
    """Immutable content-addressed persistence for canonical float32 vectors."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, relative_path: str) -> Path:
        canonical = _PATH_ADAPTER.validate_python(relative_path, strict=True)
        target = (self._root / canonical).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("Visual vector path escapes its configured root")
        return target

    def persist(self, data: bytes, *, dimensions: int) -> StoredFloat32Vector:
        _, digest = verified_float32_le_vector(
            data,
            expected_dimensions=dimensions,
        )
        relative_path = f"emocio/embeddings/{digest}.f32"
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=target.parent,
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(temporary_path, target)
                except FileExistsError:
                    pass
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()
        try:
            persisted = target.read_bytes()
        except OSError as exc:
            raise ValueError("Persisted visual vector is unreadable") from exc
        if persisted != data or hashlib.sha256(persisted).hexdigest() != digest:
            raise ValueError("Content-addressed visual vector bytes differ")
        return StoredFloat32Vector(
            relative_path=relative_path,
            content_sha256=digest,
            dimensions=dimensions,
            size_bytes=len(persisted),
        )

    def read_verified(self, encoding: VerifiedImageEncoding) -> bytes:
        data = self._resolve(encoding.vector_ref).read_bytes()
        _, digest = verified_float32_le_vector(
            data,
            expected_dimensions=encoding.dimensions,
        )
        if digest != encoding.vector_hash:
            raise ValueError("Stored visual vector hash differs from provenance")
        return data


def dinov2_base_provider_identity() -> ProviderIdentity:
    payload = {
        "schema_version": "rei-native-provider-identity-v1",
        "kind": "image_encoder",
        "implementation": "rei.emocio.DinoV2BaseImageEncoder",
        "implementation_revision": DINOV2_BASE_IMPLEMENTATION_REVISION,
        "uses_model": True,
        "model": DINOV2_BASE_MODEL_ID,
        "model_revision": DINOV2_BASE_MODEL_REVISION,
    }
    return ProviderIdentity(
        provider_id=content_id("provider", payload),
        **payload,
    )


class DinoV2BaseImageEncoder:
    """Provider adapter producing features only, with no semantic claim surface."""

    def __init__(
        self,
        *,
        runtime: DinoV2RuntimeConfig,
        image_store: LocalPngArtifactStore,
        vector_store: LocalFloat32VectorStore,
        backend: DinoV2FeatureBackend | None = None,
    ) -> None:
        self._runtime = runtime
        self._image_store = image_store
        self._vector_store = vector_store
        self._backend = backend or LazyTransformersDinoV2Backend(runtime)
        self._identity = dinov2_base_provider_identity()

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def encoding_spec(self) -> ImageEncodingSpec:
        runtime_values = {
            "device": self._runtime.device,
            "cudnn_benchmark": self._runtime.cudnn_benchmark,
            "cudnn_deterministic": self._runtime.cudnn_deterministic,
            "deterministic_algorithms": self._runtime.deterministic_algorithms,
            "float32_matmul_precision": self._runtime.float32_matmul_precision,
            "local_files_only": self._runtime.local_files_only,
            "model_repo": DINOV2_BASE_MODEL_ID,
            "model_revision": DINOV2_BASE_MODEL_REVISION,
            "offline": self._runtime.offline,
            "runtime_reassertion": "per_inference",
            "snapshot_manifest_filename": DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
            "snapshot_manifest_sha256": (
                self._runtime.expected_snapshot_manifest_sha256
            ),
            "snapshot_trust_boundary": self._runtime.snapshot_trust_boundary,
            "pillow_version": self._runtime.pillow_version,
            "torch_dtype": self._runtime.torch_dtype,
            "torch_version": self._runtime.torch_version,
            "torchvision_version": self._runtime.torchvision_version,
            "transformers_version": self._runtime.transformers_version,
            "image_processor_backend": self._runtime.image_processor_backend,
            "timeout_enforcement_mode": "cooperative_monotonic_deadline",
            "timeout_hard_cancellation": False,
        }
        return ImageEncodingSpec(
            implementation="transformers.AutoImageProcessor+AutoModel:DINOv2-CLS",
            implementation_revision=DINOV2_BASE_IMPLEMENTATION_REVISION,
            dimensions=DINOV2_BASE_DIMENSIONS,
            pooling="cls_token",
            normalization="l2",
            vector_encoding="float32-little-endian",
            parameters=tuple(
                ProviderParameter(
                    name=name,
                    canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
                )
                for name, value in sorted(runtime_values.items())
            ),
        )

    def request_for(self, image: ImageArtifact) -> ImageEncodingRequest:
        image = ImageArtifact.model_validate(
            image.model_dump(mode="python", round_trip=True)
        )
        return ImageEncodingRequest.create(
            image=image,
            provider=self.identity,
            spec=self.encoding_spec(),
        )

    def build_call_spec(
        self,
        image: ImageArtifact,
        *,
        timeout_seconds: PositiveSeconds,
    ) -> ProviderCallSpec:
        request = self.request_for(image)
        fallback = ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason=(
                "Visual feature extraction fails closed; another encoder cannot "
                "silently replace the pinned DINOv2 feature space"
            ),
        )
        safety_notice = SafetyNotice()
        payload = {
            "schema_version": "rei-native-provider-call-spec-v1",
            "request_id": request.request_id,
            "input_artifact_ids": (request.image_id,),
            "provider": self.identity,
            "seed": DINOV2_ENCODER_SEED,
            "parameters": request.provider_parameters,
            "timeout_seconds": timeout_seconds,
            "fallback_policy": fallback,
            "safety_notice": safety_notice,
        }
        return ProviderCallSpec(
            call_id=content_id("image_encoding_call", payload),
            **payload,
        )

    def _verify_snapshot(self) -> Path:
        try:
            snapshot = Path(self._runtime.local_snapshot_path).resolve(strict=True)
        except OSError as exc:
            raise ValueError("DINOv2 local snapshot does not exist") from exc
        if not snapshot.is_dir():
            raise ValueError("DINOv2 local snapshot must be a directory")
        manifest_path = snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
        try:
            manifest_bytes = manifest_path.read_bytes()
        except OSError as exc:
            raise ValueError("DINOv2 snapshot manifest is unreadable") from exc
        actual_digest = hashlib.sha256(manifest_bytes).hexdigest()
        if actual_digest != self._runtime.expected_snapshot_manifest_sha256:
            raise ValueError("DINOv2 snapshot manifest SHA-256 differs from its pin")
        try:
            manifest = DiffusersSnapshotManifest.model_validate_json(manifest_bytes)
        except Exception as exc:
            raise ValueError("DINOv2 snapshot manifest is invalid") from exc
        if manifest_bytes != canonical_snapshot_manifest_bytes(manifest):
            raise ValueError("DINOv2 snapshot manifest is not canonical JSON")
        if manifest.repo_id != DINOV2_BASE_MODEL_ID:
            raise ValueError("DINOv2 snapshot repo_id differs from the encoder pin")
        if manifest.revision != DINOV2_BASE_MODEL_REVISION:
            raise ValueError("DINOv2 snapshot revision differs from the encoder pin")
        actual_manifest = build_diffusers_snapshot_manifest(
            snapshot,
            repo_id=DINOV2_BASE_MODEL_ID,
            revision=DINOV2_BASE_MODEL_REVISION,
        )
        if actual_manifest != manifest:
            raise ValueError("DINOv2 snapshot bytes differ from its manifest")
        return snapshot

    def encode(
        self,
        image: ImageArtifact,
        *,
        call: ProviderCallSpec,
    ) -> VerifiedImageEncoding:
        image = ImageArtifact.model_validate(
            image.model_dump(mode="python", round_trip=True)
        )
        call = ProviderCallSpec.model_validate(
            call.model_dump(mode="python", round_trip=True)
        )
        request = self.request_for(image)
        request.validate_image(image)
        ensure_call_contract(
            self.identity,
            call,
            request_id=request.request_id,
            seed=DINOV2_ENCODER_SEED,
            expected_kind="image_encoder",
            required_input_artifact_ids=(image.image_id,),
        )
        if call.input_artifact_ids != (image.image_id,):
            raise ValueError("DINOv2 call may encode exactly one image artifact")
        if call.parameters != request.provider_parameters:
            raise ValueError("DINOv2 call parameters differ from its immutable request")
        if call.fallback_policy.mode != "none":
            raise ValueError("DINOv2 encoder forbids provider fallback")

        started_at = utc_now()
        expires_at = time.monotonic() + call.timeout_seconds

        def check_deadline(stage: str) -> None:
            if time.monotonic() >= expires_at:
                raise TimeoutError(
                    "Cooperative DINOv2 deadline exceeded during " + stage
                )

        png_bytes = self._image_store.verify_artifact(image)
        check_deadline("source_image_verification")
        snapshot = self._verify_snapshot()
        check_deadline("snapshot_verification")
        raw_values = self._backend.encode_png(
            png_bytes,
            verified_snapshot_path=snapshot,
        )
        check_deadline("model_inference")
        reverified_snapshot = self._verify_snapshot()
        if reverified_snapshot != snapshot:
            raise ValueError("DINOv2 snapshot path changed during model inference")
        check_deadline("post_inference_snapshot_verification")
        vector_bytes, _, _ = canonical_l2_float32_le_vector(
            raw_values,
            expected_dimensions=DINOV2_BASE_DIMENSIONS,
        )
        check_deadline("vector_canonicalization")
        stored = self._vector_store.persist(
            vector_bytes,
            dimensions=DINOV2_BASE_DIMENSIONS,
        )
        check_deadline("vector_persistence")
        encoding_id = VerifiedImageEncoding.derive_id(
            request=request,
            vector_ref=stored.relative_path,
            vector_hash=stored.content_sha256,
            dimensions=stored.dimensions,
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
            output_artifact_ids=(encoding_id,),
            warnings=(),
            safety_notice=call.safety_notice,
        )
        return VerifiedImageEncoding.create(
            request=request,
            vector_ref=stored.relative_path,
            vector_hash=stored.content_sha256,
            dimensions=stored.dimensions,
            call_spec=call,
            call=record,
        )

    def read_vector(
        self,
        encoding: VerifiedImageEncoding,
    ) -> tuple[float, ...]:
        """Return exact verified float32 values without exposing the store."""

        if not isinstance(encoding, VerifiedImageEncoding):
            raise TypeError("DINOv2 requires a byte-verifiable image encoding v2")
        validated = VerifiedImageEncoding.model_validate(
            encoding.model_dump(mode="python", round_trip=True)
        )
        validated.validate_lineage()
        if validated.call.provider != self.identity:
            raise ValueError("Visual encoding belongs to another image encoder")
        data = self._vector_store.read_verified(validated)
        values, digest = verified_float32_le_vector(
            data,
            expected_dimensions=validated.dimensions,
        )
        if digest != validated.vector_hash:
            raise ValueError("Visual vector hash differs from encoding provenance")
        return values


__all__ = [
    "DINOV2_BASE_DIMENSIONS",
    "DINOV2_BASE_IMAGE_PROCESSOR_BACKEND",
    "DINOV2_BASE_IMPLEMENTATION_REVISION",
    "DINOV2_BASE_MODEL_ID",
    "DINOV2_BASE_MODEL_REVISION",
    "DINOV2_BASE_PILLOW_VERSION",
    "DINOV2_BASE_TORCH_VERSION",
    "DINOV2_BASE_TORCHVISION_VERSION",
    "DINOV2_BASE_TRANSFORMERS_VERSION",
    "DinoV2BaseImageEncoder",
    "DinoV2FeatureBackend",
    "DinoV2RuntimeConfig",
    "LazyTransformersDinoV2Backend",
    "LocalFloat32VectorStore",
    "StoredFloat32Vector",
    "dinov2_base_provider_identity",
]
