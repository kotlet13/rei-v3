from __future__ import annotations

import builtins
import hashlib
import math
import struct
import sys
import types
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.emocio.artifacts import LocalPngArtifactStore
from app.backend.rei.emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    build_diffusers_snapshot_manifest,
    canonical_snapshot_manifest_bytes,
)
from app.backend.rei.emocio.dinov2_encoder import (
    DINOV2_BASE_DIMENSIONS,
    DINOV2_BASE_MODEL_ID,
    DINOV2_BASE_MODEL_REVISION,
    DINOV2_BASE_PILLOW_VERSION,
    DINOV2_BASE_TORCH_VERSION,
    DINOV2_BASE_TORCHVISION_VERSION,
    DINOV2_BASE_TRANSFORMERS_VERSION,
    DinoV2BaseImageEncoder,
    DinoV2RuntimeConfig,
    LazyTransformersDinoV2Backend,
    LocalFloat32VectorStore,
)
from app.backend.rei.emocio import dinov2_encoder as dinov2_module
from app.backend.rei.ids import canonical_json_bytes
from app.backend.rei.models.emocio import (
    ImageArtifact,
    VerifiedVisualEmbeddingArtifact,
    VisualEmbeddingArtifact,
    VisualSceneSpec,
)
from app.backend.rei.models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPlan,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderParameter,
)
from app.backend.rei.providers.protocols import (
    ImageEncoding,
    VerifiedImageEncoder,
    VerifiedImageEncoding,
)


def _png(width: int = 4, height: int = 3) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanline = bytes((0,)) + bytes((32, 96, 160, 255)) * width
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(scanline * height, level=9)),
            chunk(b"IEND", b""),
        )
    )


def _scene() -> VisualSceneSpec:
    return VisualSceneSpec(
        scene_id="dinov2_source_scene",
        scene_kind="current",
        option_id=None,
        entities=("self",),
        self_position="center",
        attention_structure=(),
        group_belonging="unspecified",
        status_relations=(),
        movement=(),
        composition=("generated fixture",),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=(),
        inferred_elements=("generated fixture",),
    )


def _renderer_identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="dinov2_fixture_renderer",
        kind="image_renderer",
        implementation="tests.DinoV2FixtureRenderer",
        implementation_revision="1",
        uses_model=True,
        model="test/image-renderer",
        model_revision="0123456789abcdef",
    )


def _image(store: LocalPngArtifactStore) -> ImageArtifact:
    stored = store.persist_png(
        "emocio/images/dinov2-source.png",
        _png(),
        expected_width=4,
        expected_height=3,
    )
    renderer = _renderer_identity()
    return ImageArtifact(
        image_id="dinov2_source_image",
        request_id="image_request_0123456789abcdef0123456789abcdef",
        render_call_id="dinov2_source_render_call",
        source_spec_id="dinov2_source_scene",
        provider_id=renderer.provider_id,
        model=renderer.model,
        model_revision=renderer.model_revision,
        seed=17,
        input_spec_hash=_scene().content_hash(),
        content_sha256=stored.content_sha256,
        media_type="image/png",
        prompt="internal generated fixture",
        negative_prompt="",
        path=stored.relative_path,
        width=stored.width,
        height=stored.height,
        generated_only_elements=("all visual details remain ungrounded",),
    )


def _snapshot(
    tmp_path: Path,
    *,
    repo_id: str = DINOV2_BASE_MODEL_ID,
    revision: str = DINOV2_BASE_MODEL_REVISION,
) -> tuple[Path, str]:
    snapshot = tmp_path / "dinov2-snapshot"
    snapshot.mkdir()
    (snapshot / "config.json").write_bytes(b'{"model_type":"dinov2"}')
    (snapshot / "model.safetensors").write_bytes(b"test-only-dinov2-weights")
    manifest = build_diffusers_snapshot_manifest(
        snapshot,
        repo_id=repo_id,
        revision=revision,
    )
    manifest_bytes = canonical_snapshot_manifest_bytes(manifest)
    (snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME).write_bytes(manifest_bytes)
    return snapshot.resolve(), hashlib.sha256(manifest_bytes).hexdigest()


class RecordingFeatureBackend:
    def __init__(self, values: tuple[float, ...] | None = None) -> None:
        self.values = values or (1.0,) * DINOV2_BASE_DIMENSIONS
        self.calls: list[tuple[bytes, Path]] = []

    def encode_png(
        self,
        png_bytes: bytes,
        *,
        verified_snapshot_path: Path,
    ) -> tuple[float, ...]:
        self.calls.append((png_bytes, verified_snapshot_path))
        return self.values


def _install_fake_optional_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], object]:
    calls: dict[str, object] = {}
    float32 = object()

    torch_module = types.ModuleType("torch")
    torch_module.float32 = float32
    torch_module.backends = types.SimpleNamespace(
        cudnn=types.SimpleNamespace(benchmark=True, deterministic=False)
    )

    def use_deterministic_algorithms(value: bool) -> None:
        calls["deterministic_algorithms"] = value

    def set_float32_matmul_precision(value: str) -> None:
        calls["float32_matmul_precision"] = value

    torch_module.use_deterministic_algorithms = use_deterministic_algorithms
    torch_module.set_float32_matmul_precision = set_float32_matmul_precision

    pillow_module = types.ModuleType("PIL")
    pillow_module.Image = object()

    class RecordingProcessorLoader:
        @classmethod
        def from_pretrained(cls, target: str, **options: object) -> object:
            calls["processor"] = (target, options)
            return object()

    class RecordingModel:
        def eval(self) -> RecordingModel:
            calls["eval"] = True
            return self

        def to(self, *args: object, **options: object) -> RecordingModel:
            calls["model_to"] = (args, options)
            return self

    class RecordingModelLoader:
        @classmethod
        def from_pretrained(cls, target: str, **options: object) -> RecordingModel:
            calls["model"] = (target, options)
            return RecordingModel()

    transformers_module = types.ModuleType("transformers")
    transformers_module.AutoImageProcessor = RecordingProcessorLoader
    transformers_module.AutoModel = RecordingModelLoader

    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "PIL", pillow_module)
    monkeypatch.setitem(sys.modules, "transformers", transformers_module)
    return calls, float32


def _encoder(
    tmp_path: Path,
    backend: RecordingFeatureBackend,
    *,
    snapshot: Path | None = None,
    manifest_digest: str | None = None,
) -> tuple[
    DinoV2BaseImageEncoder,
    LocalPngArtifactStore,
    LocalFloat32VectorStore,
]:
    if snapshot is None or manifest_digest is None:
        snapshot, manifest_digest = _snapshot(tmp_path)
    image_store = LocalPngArtifactStore(tmp_path / "artifacts")
    vector_store = LocalFloat32VectorStore(tmp_path / "artifacts")
    encoder = DinoV2BaseImageEncoder(
        runtime=DinoV2RuntimeConfig(
            local_snapshot_path=str(snapshot),
            expected_snapshot_manifest_sha256=manifest_digest,
            device="cpu",
        ),
        image_store=image_store,
        vector_store=vector_store,
        backend=backend,
    )
    return encoder, image_store, vector_store


def test_pinned_encoder_is_deterministic_and_closes_vector_provenance(
    tmp_path: Path,
) -> None:
    backend = RecordingFeatureBackend()
    encoder, image_store, vector_store = _encoder(tmp_path, backend)
    image = _image(image_store)

    assert isinstance(encoder, VerifiedImageEncoder)
    assert encoder.identity.kind == "image_encoder"
    assert encoder.identity.model == DINOV2_BASE_MODEL_ID
    assert encoder.identity.model_revision == DINOV2_BASE_MODEL_REVISION
    request = encoder.request_for(image)
    replay_request = encoder.request_for(image)
    assert request == replay_request
    assert request.provider == encoder.identity
    assert request.spec.dimensions == DINOV2_BASE_DIMENSIONS
    assert ProviderParameter(
        name="snapshot_trust_boundary",
        canonical_json_value='"trusted_local_filesystem"',
    ) in request.spec.parameters

    call = encoder.build_call_spec(image, timeout_seconds=5.0)
    result = encoder.encode(image, call=call)
    replay = encoder.encode(image, call=call)

    expected_component = struct.pack(
        "<f",
        1.0 / math.sqrt(DINOV2_BASE_DIMENSIONS),
    )
    expected_bytes = expected_component * DINOV2_BASE_DIMENSIONS
    assert vector_store.read_verified(result) == expected_bytes
    assert isinstance(result, VerifiedImageEncoding)
    assert encoder.read_vector(result) == struct.unpack(
        f"<{DINOV2_BASE_DIMENSIONS}f",
        expected_bytes,
    )
    assert result.vector_hash == hashlib.sha256(expected_bytes).hexdigest()
    assert result.dimensions == DINOV2_BASE_DIMENSIONS
    assert result.encoding_id == replay.encoding_id
    assert result.vector_hash == replay.vector_hash
    assert result.call_spec == call
    assert result.call.output_artifact_ids == (result.encoding_id,)
    assert result.call.provider == encoder.identity
    assert result.call.fallback is None
    assert result.internal_only is True
    assert result.external_evidence is False
    assert result.semantic_interpretation == "none"
    assert len(backend.calls) == 2
    assert all(png_bytes == _png() for png_bytes, _ in backend.calls)
    assert all(path.name == "dinov2-snapshot" for _, path in backend.calls)

    visual = result.to_visual_embedding()
    assert isinstance(visual, VerifiedVisualEmbeddingArtifact)
    assert visual.source_artifact_id == image.image_id
    assert visual.encoder_identity == encoder.identity
    assert visual.vector_hash == result.vector_hash
    assert visual.dimensions == DINOV2_BASE_DIMENSIONS
    assert visual.internal_only is True
    assert visual.external_evidence is False
    assert visual.semantic_interpretation == "none"
    assert {
        "social_meaning",
        "grounded_evidence_ids",
        "inferred_claims",
    }.isdisjoint(type(result).model_fields)

    assert visual.vector_hash == hashlib.sha256(expected_bytes).hexdigest()

    legacy = ImageEncoding(
        encoding_id=result.encoding_id,
        request_id=result.request_id,
        image_id=result.image_id,
        vector_ref=result.vector_ref,
        dimensions=result.dimensions,
        call_spec=result.call_spec,
        call=result.call,
    )
    assert legacy.schema_version == "rei-native-image-encoding-v1"
    assert ImageEncoding.model_validate_json(legacy.model_dump_json()) == legacy
    assert set(legacy.model_dump()) == {
        "schema_version",
        "encoding_id",
        "request_id",
        "image_id",
        "vector_ref",
        "dimensions",
        "call_spec",
        "call",
    }
    with pytest.raises(TypeError, match="byte-verifiable"):
        encoder.read_vector(legacy)

    forged = result.model_copy(update={"encoding_id": "forged_encoding"})
    with pytest.raises(ValidationError, match="returned artifact ID"):
        encoder.read_vector(forged)

    vector_path = vector_store.root / result.vector_ref
    vector_path.write_bytes(
        struct.pack("<f", -struct.unpack("<f", expected_component)[0])
        + expected_bytes[4:]
    )
    with pytest.raises(ValueError, match="hash differs"):
        encoder.read_vector(result)


def test_historical_visual_embedding_v1_serialization_and_hash_are_unchanged() -> None:
    identity = ProviderIdentity(
        provider_id="legacy_visual_encoder",
        kind="image_encoder",
        implementation="tests.LegacyVisualEncoder",
        implementation_revision="1",
    )
    legacy = VisualEmbeddingArtifact(
        source_artifact_id="legacy_imagined_visual",
        encoder_identity=identity,
        vector_hash="0" * 64,
        dimensions=4,
    )
    expected_payload = {
        "schema_version": "rei-native-visual-embedding-artifact-v1",
        "source_artifact_id": "legacy_imagined_visual",
        "encoder_identity": identity.model_dump(mode="python", round_trip=True),
        "vector_hash": "0" * 64,
        "dimensions": 4,
    }
    expected_canonical = (
        b'{"dimensions":4,"encoder_identity":{"implementation":'
        b'"tests.LegacyVisualEncoder","implementation_revision":"1",'
        b'"kind":"image_encoder","model":null,"model_revision":null,'
        b'"provider_id":"legacy_visual_encoder","schema_version":'
        b'"rei-native-provider-identity-v1","uses_model":false},'
        b'"schema_version":"rei-native-visual-embedding-artifact-v1",'
        b'"source_artifact_id":"legacy_imagined_visual","vector_hash":"'
        + (b"0" * 64)
        + b'"}'
    )

    assert legacy.model_dump(mode="python", round_trip=True) == expected_payload
    assert canonical_json_bytes(expected_payload) == expected_canonical
    assert legacy.canonical_json_bytes() == expected_canonical
    assert legacy.content_hash() == (
        "a7650522250166af702cf622e0ee4b67d39a47da09932c5fcbf79087ee750a25"
    )
    restored = VisualEmbeddingArtifact.model_validate_json(legacy.model_dump_json())
    assert restored == legacy
    assert set(type(legacy).model_fields) == {
        "schema_version",
        "source_artifact_id",
        "encoder_identity",
        "vector_hash",
        "dimensions",
    }


def test_historical_image_encoding_v1_serialization_and_hash_are_unchanged() -> None:
    identity = ProviderIdentity(
        provider_id="legacy_image_encoder",
        kind="image_encoder",
        implementation="tests.LegacyImageEncoder",
        implementation_revision="1",
    )
    call_spec = ProviderCallSpec(
        call_id="legacy_image_encoding_call",
        request_id="legacy_image_encoding_request",
        input_artifact_ids=("legacy_image",),
        provider=identity,
        seed=0,
        parameters=(),
        timeout_seconds=5.0,
        fallback_policy=ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason="Historical encoder had no fallback",
        ),
    )
    started_at = datetime(2026, 7, 14, 12, tzinfo=UTC)
    finished_at = started_at + timedelta(milliseconds=1)
    call = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        input_artifact_ids=call_spec.input_artifact_ids,
        provider=call_spec.provider,
        seed=call_spec.seed,
        parameters=call_spec.parameters,
        timeout_seconds=call_spec.timeout_seconds,
        started_at=started_at,
        primary_finished_at=finished_at,
        finished_at=finished_at,
        status="succeeded",
        primary_status="succeeded",
        fallback=None,
        output_artifact_ids=("legacy_image_encoding",),
        warnings=(),
        safety_notice=call_spec.safety_notice,
    )
    legacy = ImageEncoding(
        encoding_id="legacy_image_encoding",
        request_id=call_spec.request_id,
        image_id="legacy_image",
        vector_ref="emocio/embeddings/legacy.f32",
        dimensions=4,
        call_spec=call_spec,
        call=call,
    )
    expected_payload = {
        "schema_version": "rei-native-image-encoding-v1",
        "encoding_id": "legacy_image_encoding",
        "request_id": "legacy_image_encoding_request",
        "image_id": "legacy_image",
        "vector_ref": "emocio/embeddings/legacy.f32",
        "dimensions": 4,
        "call_spec": call_spec.model_dump(mode="python", round_trip=True),
        "call": call.model_dump(mode="python", round_trip=True),
    }

    assert legacy.model_dump(mode="python", round_trip=True) == expected_payload
    assert legacy.canonical_json_bytes() == canonical_json_bytes(expected_payload)
    assert len(legacy.canonical_json_bytes()) == 2176
    assert legacy.content_hash() == (
        "a6187afb1e5de05e109412ff5172e098cf37247f614cacb1d9a9cbbf7ff94e19"
    )
    assert ImageEncoding.model_validate_json(legacy.model_dump_json()) == legacy
    assert set(type(legacy).model_fields) == {
        "schema_version",
        "encoding_id",
        "request_id",
        "image_id",
        "vector_ref",
        "dimensions",
        "call_spec",
        "call",
    }


def test_snapshot_tampering_fails_closed_before_backend_or_vector_write(
    tmp_path: Path,
) -> None:
    snapshot, manifest_digest = _snapshot(tmp_path)
    backend = RecordingFeatureBackend()
    encoder, image_store, vector_store = _encoder(
        tmp_path,
        backend,
        snapshot=snapshot,
        manifest_digest=manifest_digest,
    )
    image = _image(image_store)
    (snapshot / "model.safetensors").write_bytes(b"tampered")

    with pytest.raises(ValueError, match="bytes differ"):
        encoder.encode(
            image,
            call=encoder.build_call_spec(image, timeout_seconds=5.0),
        )

    assert backend.calls == []
    assert list(vector_store.root.rglob("*.f32")) == []


def test_snapshot_is_reverified_before_every_encoding(tmp_path: Path) -> None:
    snapshot, manifest_digest = _snapshot(tmp_path)
    backend = RecordingFeatureBackend()
    encoder, image_store, vector_store = _encoder(
        tmp_path,
        backend,
        snapshot=snapshot,
        manifest_digest=manifest_digest,
    )
    image = _image(image_store)
    call = encoder.build_call_spec(image, timeout_seconds=5.0)

    encoder.encode(image, call=call)
    (snapshot / "model.safetensors").write_bytes(b"tampered-after-first-call")

    with pytest.raises(ValueError, match="bytes differ"):
        encoder.encode(image, call=call)

    assert len(backend.calls) == 1
    assert len(list(vector_store.root.rglob("*.f32"))) == 1


def test_snapshot_mutation_during_inference_fails_before_vector_write(
    tmp_path: Path,
) -> None:
    snapshot, manifest_digest = _snapshot(tmp_path)

    class MutatingFeatureBackend(RecordingFeatureBackend):
        def encode_png(
            self,
            png_bytes: bytes,
            *,
            verified_snapshot_path: Path,
        ) -> tuple[float, ...]:
            values = super().encode_png(
                png_bytes,
                verified_snapshot_path=verified_snapshot_path,
            )
            (verified_snapshot_path / "model.safetensors").write_bytes(
                b"tampered-during-inference"
            )
            return values

    backend = MutatingFeatureBackend()
    encoder, image_store, vector_store = _encoder(
        tmp_path,
        backend,
        snapshot=snapshot,
        manifest_digest=manifest_digest,
    )
    image = _image(image_store)

    with pytest.raises(ValueError, match="bytes differ"):
        encoder.encode(
            image,
            call=encoder.build_call_spec(image, timeout_seconds=5.0),
        )

    assert len(backend.calls) == 1
    assert list(vector_store.root.rglob("*.f32")) == []


def test_nested_model_copy_call_forgery_is_revalidated_before_encoding(
    tmp_path: Path,
) -> None:
    backend = RecordingFeatureBackend()
    encoder, image_store, vector_store = _encoder(tmp_path, backend)
    image = _image(image_store)
    call = encoder.build_call_spec(image, timeout_seconds=5.0)
    fallback_provider = ProviderIdentity(
        provider_id="forged_fallback_encoder",
        kind="image_encoder",
        implementation="tests.ForgedFallbackEncoder",
        implementation_revision="1",
        uses_model=True,
        model="tests/forged-encoder",
        model_revision="1",
    )
    plan = ProviderFallbackPlan(
        provider=fallback_provider,
        seed=0,
        parameters=(),
        timeout_seconds=5.0,
    )
    invalid_policy = call.fallback_policy.model_copy(update={"plan": plan})
    forged_call = call.model_copy(update={"fallback_policy": invalid_policy})

    with pytest.raises(ValidationError, match="forbids a provider plan"):
        encoder.encode(image, call=forged_call)

    assert backend.calls == []
    assert list(vector_store.root.rglob("*.f32")) == []


@pytest.mark.parametrize(
    "values, message",
    (
        ((1.0,) * (DINOV2_BASE_DIMENSIONS - 1), "dimensions differ"),
        ((0.0,) * DINOV2_BASE_DIMENSIONS, "cannot be normalized"),
        (
            (float("nan"),) + (1.0,) * (DINOV2_BASE_DIMENSIONS - 1),
            "must be finite",
        ),
    ),
)
def test_invalid_backend_features_fail_closed_without_publishing_vector(
    tmp_path: Path,
    values: tuple[float, ...],
    message: str,
) -> None:
    backend = RecordingFeatureBackend(values)
    encoder, image_store, vector_store = _encoder(tmp_path, backend)
    image = _image(image_store)

    with pytest.raises(ValueError, match=message):
        encoder.encode(
            image,
            call=encoder.build_call_spec(image, timeout_seconds=5.0),
        )

    assert len(backend.calls) == 1
    assert list(vector_store.root.rglob("*.f32")) == []


def test_wrong_snapshot_identity_and_call_parameters_are_rejected(
    tmp_path: Path,
) -> None:
    snapshot, manifest_digest = _snapshot(tmp_path, repo_id="other/model")
    backend = RecordingFeatureBackend()
    encoder, image_store, _ = _encoder(
        tmp_path,
        backend,
        snapshot=snapshot,
        manifest_digest=manifest_digest,
    )
    image = _image(image_store)
    call = encoder.build_call_spec(image, timeout_seconds=5.0)
    with pytest.raises(ValueError, match="repo_id differs"):
        encoder.encode(image, call=call)
    assert backend.calls == []

    valid_root = tmp_path / "valid"
    valid_root.mkdir()
    valid_backend = RecordingFeatureBackend()
    valid_encoder, valid_image_store, _ = _encoder(valid_root, valid_backend)
    valid_image = _image(valid_image_store)
    valid_call = valid_encoder.build_call_spec(valid_image, timeout_seconds=5.0)
    changed = ProviderParameter(
        name="dimensions",
        canonical_json_value="1",
    )
    tampered_parameters = tuple(
        changed if item.name == "dimensions" else item
        for item in valid_call.parameters
    )
    tampered_call = valid_call.model_copy(update={"parameters": tampered_parameters})
    with pytest.raises(ValueError, match="parameters differ"):
        valid_encoder.encode(valid_image, call=tampered_call)
    assert valid_backend.calls == []


def test_snapshot_revision_must_match_the_exact_dinov2_pin(tmp_path: Path) -> None:
    snapshot, manifest_digest = _snapshot(tmp_path, revision="0" * 40)
    backend = RecordingFeatureBackend()
    encoder, image_store, _ = _encoder(
        tmp_path,
        backend,
        snapshot=snapshot,
        manifest_digest=manifest_digest,
    )
    image = _image(image_store)

    with pytest.raises(ValueError, match="revision differs"):
        encoder.encode(
            image,
            call=encoder.build_call_spec(image, timeout_seconds=5.0),
        )
    assert backend.calls == []


def test_source_png_tampering_fails_before_snapshot_or_backend(tmp_path: Path) -> None:
    backend = RecordingFeatureBackend()
    encoder, image_store, vector_store = _encoder(tmp_path, backend)
    image = _image(image_store)
    (image_store.root / image.path).write_bytes(b"tampered image")

    with pytest.raises(ValueError, match="SHA-256"):
        encoder.encode(
            image,
            call=encoder.build_call_spec(image, timeout_seconds=5.0),
        )
    assert backend.calls == []
    assert list(vector_store.root.rglob("*.f32")) == []


def test_cooperative_deadline_fails_before_backend_or_vector_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = RecordingFeatureBackend()
    encoder, image_store, vector_store = _encoder(tmp_path, backend)
    image = _image(image_store)
    clock = iter((100.0, 106.0))
    monkeypatch.setattr(dinov2_module.time, "monotonic", lambda: next(clock))

    with pytest.raises(TimeoutError, match="source_image_verification"):
        encoder.encode(
            image,
            call=encoder.build_call_spec(image, timeout_seconds=5.0),
        )
    assert backend.calls == []
    assert list(vector_store.root.rglob("*.f32")) == []


def test_cooperative_deadline_is_checked_after_vector_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = RecordingFeatureBackend()
    encoder, image_store, vector_store = _encoder(tmp_path, backend)
    image = _image(image_store)
    ticks = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 106.0]

    def monotonic() -> float:
        return ticks.pop(0) if ticks else 106.0

    monkeypatch.setattr(dinov2_module.time, "monotonic", monotonic)

    with pytest.raises(TimeoutError, match="vector_persistence"):
        encoder.encode(
            image,
            call=encoder.build_call_spec(image, timeout_seconds=5.0),
        )
    assert len(backend.calls) == 1
    assert len(list(vector_store.root.rglob("*.f32"))) == 1


def test_runtime_is_offline_absolute_and_lazy_optional_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError, match="must be absolute"):
        DinoV2RuntimeConfig(
            local_snapshot_path="relative/model",
            expected_snapshot_manifest_sha256="0" * 64,
        )

    snapshot, manifest_digest = _snapshot(tmp_path)
    runtime = DinoV2RuntimeConfig(
        local_snapshot_path=str(snapshot),
        expected_snapshot_manifest_sha256=manifest_digest,
    )
    imported: list[str] = []
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "transformers", "PIL"}:
            imported.append(name)
            raise AssertionError("optional runtime imported during construction")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    LazyTransformersDinoV2Backend(runtime)
    assert imported == []
    assert runtime.local_files_only is True
    assert runtime.offline is True


def test_lazy_runtime_enforces_pins_and_deterministic_load_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, manifest_digest = _snapshot(tmp_path)
    runtime = DinoV2RuntimeConfig(
        local_snapshot_path=str(snapshot),
        expected_snapshot_manifest_sha256=manifest_digest,
    )
    calls, float32 = _install_fake_optional_runtime(monkeypatch)
    installed = {
        "torch": DINOV2_BASE_TORCH_VERSION + "+cu130",
        "torchvision": DINOV2_BASE_TORCHVISION_VERSION,
        "Pillow": DINOV2_BASE_PILLOW_VERSION,
        "transformers": DINOV2_BASE_TRANSFORMERS_VERSION,
    }
    monkeypatch.setattr(dinov2_module, "version", installed.__getitem__)

    backend = LazyTransformersDinoV2Backend(runtime)
    backend._load_components(snapshot)

    processor_target, processor_options = calls["processor"]
    assert processor_target == str(snapshot)
    assert processor_options == {
        "backend": "pil",
        "local_files_only": True,
        "trust_remote_code": False,
    }
    model_target, model_options = calls["model"]
    assert model_target == str(snapshot)
    assert model_options == {
        "dtype": float32,
        "local_files_only": True,
        "trust_remote_code": False,
        "use_safetensors": True,
    }
    assert calls["eval"] is True
    assert calls["model_to"] == ((), {"device": "cpu", "dtype": float32})
    assert calls["deterministic_algorithms"] is True
    assert calls["float32_matmul_precision"] == "highest"
    torch_module = sys.modules["torch"]
    assert torch_module.backends.cudnn.benchmark is False
    assert torch_module.backends.cudnn.deterministic is True

    torch_module.backends.cudnn.benchmark = True
    torch_module.backends.cudnn.deterministic = False
    calls["deterministic_algorithms"] = False
    calls["float32_matmul_precision"] = "medium"
    backend._load_components(snapshot)

    assert calls["deterministic_algorithms"] is True
    assert calls["float32_matmul_precision"] == "highest"
    assert torch_module.backends.cudnn.benchmark is False
    assert torch_module.backends.cudnn.deterministic is True


@pytest.mark.parametrize(
    ("distribution", "installed_version", "message"),
    (
        ("torch", "2.13.1+cu130", "Torch base version differs"),
        ("torchvision", "0.28.1", "Torchvision version differs"),
        ("Pillow", "12.3.1", "Pillow version differs"),
        ("transformers", "5.13.1", "Transformers version differs"),
    ),
)
def test_lazy_runtime_rejects_every_distribution_pin_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    distribution: str,
    installed_version: str,
    message: str,
) -> None:
    snapshot, manifest_digest = _snapshot(tmp_path)
    runtime = DinoV2RuntimeConfig(
        local_snapshot_path=str(snapshot),
        expected_snapshot_manifest_sha256=manifest_digest,
    )
    _install_fake_optional_runtime(monkeypatch)
    installed = {
        "torch": DINOV2_BASE_TORCH_VERSION + "+cu130",
        "torchvision": DINOV2_BASE_TORCHVISION_VERSION,
        "Pillow": DINOV2_BASE_PILLOW_VERSION,
        "transformers": DINOV2_BASE_TRANSFORMERS_VERSION,
    }
    installed[distribution] = installed_version
    monkeypatch.setattr(dinov2_module, "version", installed.__getitem__)

    with pytest.raises(RuntimeError, match=message):
        LazyTransformersDinoV2Backend(runtime)._load_components(snapshot)


def test_encoding_contract_rejects_semantic_or_grounded_extensions(
    tmp_path: Path,
) -> None:
    backend = RecordingFeatureBackend()
    encoder, image_store, _ = _encoder(tmp_path, backend)
    image = _image(image_store)
    result = encoder.encode(
        image,
        call=encoder.build_call_spec(image, timeout_seconds=5.0),
    )
    payload = result.model_dump(mode="python", round_trip=True)
    payload["social_meaning"] = "invented status interpretation"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        VerifiedImageEncoding.model_validate(payload)
