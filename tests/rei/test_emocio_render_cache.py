from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

from app.backend.rei.emocio.artifacts import LocalPngArtifactStore
from app.backend.rei.emocio.diffusers_renderer import DiffusersImageRenderer
from app.backend.rei.models.emocio import VisualSceneSpec
from app.backend.rei.models.provider import (
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
)
from app.backend.rei.models.rendering import ImagePipelineSpec, ImageRenderRequest


def _png(
    width: int = 4,
    height: int = 3,
    rgba: tuple[int, int, int, int] = (20, 70, 130, 255),
) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    rows = (bytes((0,)) + bytes(rgba) * width) * height
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(rows, level=9)),
            chunk(b"IEND", b""),
        )
    )


class CountingBackend:
    def __init__(self) -> None:
        self.calls: list[ImageRenderRequest] = []

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        assert source_png is None
        self.calls.append(request)
        return _png(request.width, request.height)


def _identity(*, revision: str = "0123456789abcdef0123456789abcdef01234567"):
    return ProviderIdentity(
        provider_id="cache_test_renderer",
        kind="image_renderer",
        implementation="tests.rei.CountingBackend",
        implementation_revision="1",
        uses_model=True,
        model="test/cache-image-model",
        model_revision=revision,
    )


def _scene() -> VisualSceneSpec:
    return VisualSceneSpec(
        scene_id="cache_test_scene",
        scene_kind="current",
        option_id=None,
        entities=("observer",),
        self_position="centered",
        attention_structure=(),
        group_belonging="unknown",
        status_relations=(),
        movement=(),
        composition=("stable",),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=(),
        inferred_elements=("test-only scene",),
    )


def _pipeline(identity: ProviderIdentity) -> ImagePipelineSpec:
    return ImagePipelineSpec(
        implementation=identity.implementation,
        implementation_revision=identity.implementation_revision,
    )


def _request(identity: ProviderIdentity, *, seed: int) -> ImageRenderRequest:
    return ImageRenderRequest.create(
        mode="text_to_image",
        source_spec=_scene(),
        provider=identity,
        pipeline=_pipeline(identity),
        seed=seed,
        prompt="cache test structured scene",
        negative_prompt="",
        prompt_language="en",
        width=4,
        height=3,
        num_inference_steps=4,
        guidance_scale=1.0,
    )


def _call(request: ImageRenderRequest) -> ProviderCallSpec:
    return ProviderCallSpec(
        call_id=f"call_{request.request_id}",
        request_id=request.request_id,
        input_artifact_ids=request.input_artifact_ids,
        provider=request.provider,
        seed=request.seed,
        parameters=request.provider_parameters,
        timeout_seconds=5.0,
        fallback_policy=ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason="A corrupt renderer cache must fail closed.",
        ),
    )


def _renderer(
    store: LocalPngArtifactStore,
    backend: CountingBackend,
    identity: ProviderIdentity,
) -> DiffusersImageRenderer:
    return DiffusersImageRenderer(
        identity=identity,
        backend=backend,
        artifact_store=store,
        pipeline_specs={
            "text_to_image": _pipeline(identity),
            "image_to_image": _pipeline(identity),
        },
    )


def test_verified_cache_hit_skips_backend_and_stays_ungrounded(
    tmp_path: Path,
) -> None:
    store = LocalPngArtifactStore(tmp_path / "artifacts")
    backend = CountingBackend()
    identity = _identity()
    renderer = _renderer(store, backend, identity)
    request = _request(identity, seed=11)
    call = _call(request)

    first = renderer.render(request, call=call)
    replay = renderer.render(request, call=call)

    assert first.artifact is not None
    assert replay.artifact == first.artifact
    assert len(backend.calls) == 1
    assert replay.call_record.status == "succeeded"
    assert replay.call_record.warnings == ("cache_hit_verified",)
    assert replay.artifact.grounded is False
    assert replay.artifact.grounded_mask_path is None
    assert (
        store.root / "emocio" / "cache" / f"{request.request_id}.json"
    ).is_file()


def test_seed_and_exact_model_revision_changes_are_cache_misses(
    tmp_path: Path,
) -> None:
    store = LocalPngArtifactStore(tmp_path / "artifacts")
    backend = CountingBackend()
    first_identity = _identity()
    first_renderer = _renderer(store, backend, first_identity)

    for seed in (11, 12):
        request = _request(first_identity, seed=seed)
        assert first_renderer.render(request, call=_call(request)).artifact is not None

    changed_identity = _identity(
        revision="89abcdef0123456789abcdef0123456789abcdef"
    )
    changed_renderer = _renderer(store, backend, changed_identity)
    changed_request = _request(changed_identity, seed=11)
    changed = changed_renderer.render(
        changed_request,
        call=_call(changed_request),
    )

    assert changed.artifact is not None
    assert len(backend.calls) == 3
    assert len({request.request_id for request in backend.calls}) == 3


def test_changed_call_lineage_fails_closed_instead_of_reusing_request_cache(
    tmp_path: Path,
) -> None:
    store = LocalPngArtifactStore(tmp_path / "artifacts")
    backend = CountingBackend()
    identity = _identity()
    renderer = _renderer(store, backend, identity)
    request = _request(identity, seed=17)
    call = _call(request)
    assert renderer.render(request, call=call).artifact is not None

    changed_call = call.model_copy(update={"call_id": "changed_render_call"})
    failed = renderer.render(request, call=changed_call)

    assert failed.artifact is None
    assert failed.failure_code == "renderer_provider_failure"
    assert failed.failure_message == (
        "Image renderer failed closed (renderer_provider_failure)"
    )
    assert len(backend.calls) == 1


def test_grounded_metadata_tamper_fails_closed_without_backend_regeneration(
    tmp_path: Path,
) -> None:
    store = LocalPngArtifactStore(tmp_path / "artifacts")
    backend = CountingBackend()
    identity = _identity()
    renderer = _renderer(store, backend, identity)
    request = _request(identity, seed=21)
    call = _call(request)
    success = renderer.render(request, call=call)
    assert success.artifact is not None
    calls_before_tamper = len(backend.calls)

    metadata_path = (
        store.root / "emocio" / "cache" / f"{request.request_id}.json"
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["grounded"] = True
    metadata_path.write_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    failed = renderer.render(request, call=call)

    assert failed.artifact is None
    assert failed.call_record.status == "failed"
    assert failed.failure_code == "renderer_provider_failure"
    assert failed.failure_message == (
        "Image renderer failed closed (renderer_provider_failure)"
    )
    assert len(backend.calls) == calls_before_tamper


def test_png_tamper_fails_closed_without_backend_regeneration(
    tmp_path: Path,
) -> None:
    store = LocalPngArtifactStore(tmp_path / "artifacts")
    backend = CountingBackend()
    identity = _identity()
    renderer = _renderer(store, backend, identity)
    request = _request(identity, seed=31)
    call = _call(request)
    success = renderer.render(request, call=call)
    assert success.artifact is not None
    calls_before_tamper = len(backend.calls)

    (store.root / success.artifact.path).write_bytes(
        _png(rgba=(220, 30, 40, 255))
    )
    failed = renderer.render(request, call=call)

    assert failed.artifact is None
    assert failed.call_record.status == "failed"
    assert failed.failure_code == "renderer_provider_failure"
    assert failed.failure_message == (
        "Image renderer failed closed (renderer_provider_failure)"
    )
    assert len(backend.calls) == calls_before_tamper


def test_cache_key_rejects_path_traversal(tmp_path: Path) -> None:
    store = LocalPngArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ValueError, match="canonical image request ID"):
        store.read_cached_artifact("../../outside")
