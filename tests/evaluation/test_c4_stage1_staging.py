from __future__ import annotations

import hashlib
import os
from pathlib import Path
import struct
import sys
import zlib

import pytest

from rei.emocio.c4_stage1_editor import (
    C4Stage1ChildRuntimeProvenance,
    C4Stage1EditorSpec,
    C4Stage1ImageEvidence,
    C4Stage1WorkerRequest,
    C4Stage1WorkerResult,
    VerifiedC4Stage1Snapshot,
)
from rei.evaluation import c4_stage1_staging as staging_module
from rei.evaluation.c4_stage1_fixture import build_c4_stage1_fixture
from rei.evaluation.c4_stage1_staging import (
    prepare_c4_stage1_staging_root,
    verify_c4_stage1_staging,
)
from rei.models.provider import ProviderIdentity
from rei.models.rendering import (
    ImagePipelineSpec,
    ImageRenderRequest,
    ImageSourceReference,
)


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png(red: int) -> bytes:
    width, height = 1024, 768
    raw = (b"\x00" + bytes((red, 20, 30)) * width) * height
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _chunk(
                b"IHDR",
                struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0),
            ),
            _chunk(b"IDAT", zlib.compress(raw, 9)),
            _chunk(b"IEND", b""),
        )
    )


def _request() -> C4Stage1WorkerRequest:
    source_png = _png(10)
    fixture = build_c4_stage1_fixture()
    scene = fixture.prompts[0].scene
    repo_id = "test/c4-stage1-staging"
    revision = "f" * 40
    provider = ProviderIdentity(
        provider_id="provider_c4_stage1_staging_fixture",
        kind="image_renderer",
        implementation="test.C4Stage1StagingFixture",
        implementation_revision="model-free-v1",
        uses_model=True,
        model=repo_id,
        model_revision=revision,
    )
    pipeline = ImagePipelineSpec(
        implementation="diffusers.LongCatImageEditPipeline",
        implementation_revision="model-free-v1",
    )
    editor_spec = C4Stage1EditorSpec.create(
        editor_role="test",
        provider=provider,
        pipeline=pipeline,
        repo_id=repo_id,
        revision=revision,
        snapshot_manifest_sha256="e" * 64,
        snapshot_file_count=1,
        snapshot_total_bytes=1,
    )
    source = ImageSourceReference(
        image_id="image_c4_stage1_staging_fixture",
        content_sha256=hashlib.sha256(source_png).hexdigest(),
        media_type="image/png",
        path="emocio/images/source.png",
        width=1024,
        height=768,
        grounded=False,
        originating_scene_spec_id=fixture.current_scene.scene_id,
        originating_scene_spec_hash=fixture.current_scene_hash,
    )
    render = ImageRenderRequest.create(
        mode="image_to_image",
        source_spec=scene,
        provider=provider,
        pipeline=pipeline,
        seed=7,
        prompt="model-free staging fixture prompt",
        negative_prompt="",
        width=1024,
        height=768,
        num_inference_steps=1,
        guidance_scale=1.0,
        source_image=source,
        strength=None,
        conditioning_method="reference_image",
    )
    return C4Stage1WorkerRequest.create(
        editor_spec=editor_spec,
        verified_snapshot=VerifiedC4Stage1Snapshot.create(editor_spec),
        render_request=render,
    )


def _success(
    request: C4Stage1WorkerRequest,
    *,
    direct: bytes | None = None,
    staged: bytes | None = None,
) -> tuple[C4Stage1WorkerResult, bytes, bytes]:
    direct = _png(80) if direct is None else direct
    staged = _png(90) if staged is None else staged
    evidence = C4Stage1ImageEvidence.create(
        direct_png=direct,
        staged_png=staged,
        normalization_policy="longcat_rgb_lanczos_1024x768",
    )
    provenance = C4Stage1ChildRuntimeProvenance.create(
        request,
        pipeline_class="LongCatImageEditPipeline",
        placement="model_cpu_offload",
        model_cpu_offload_enabled=True,
        torch_peak_allocated_bytes=100,
        torch_peak_reserved_bytes=120,
    )
    return C4Stage1WorkerResult.succeeded(request, evidence, provenance), direct, staged


def _write_success(
    root: Path,
    request: C4Stage1WorkerRequest,
    *,
    direct: bytes | None = None,
    staged: bytes | None = None,
) -> tuple[C4Stage1WorkerResult, bytes, bytes]:
    result, direct, staged = _success(request, direct=direct, staged=staged)
    (root / "direct.png").write_bytes(direct)
    (root / "staged.png").write_bytes(staged)
    (root / "worker_result.json").write_bytes(result.canonical_json_bytes())
    return result, direct, staged


def test_success_returns_only_portable_result_and_runtime_bytes(tmp_path: Path) -> None:
    request = _request()
    root = (tmp_path / "staging").resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    expected_result, direct, staged = _write_success(root, request)
    model_modules_before = {
        name for name in sys.modules if name in {"torch", "diffusers"}
    }

    verified = verify_c4_stage1_staging(prepared, request)

    assert verified.worker_result == expected_result
    assert verified.direct_png == direct
    assert verified.staged_png == staged
    assert str(root) not in repr(prepared)
    assert str(root).encode() not in verified.worker_result.canonical_json_bytes()
    assert {name for name in sys.modules if name in {"torch", "diffusers"}} == (
        model_modules_before
    )


def test_failure_requires_only_one_canonical_result(tmp_path: Path) -> None:
    request = _request()
    root = (tmp_path / "staging").resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    failed = C4Stage1WorkerResult.failed(request, failure_code="fixture_failure")
    (root / "worker_result.json").write_bytes(failed.canonical_json_bytes())

    verified = verify_c4_stage1_staging(prepared, request)

    assert verified.worker_result == failed
    assert verified.direct_png is None
    assert verified.staged_png is None


def test_preparation_rejects_relative_or_nonfresh_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute lexical"):
        prepare_c4_stage1_staging_root(Path("relative-staging"))

    root = (tmp_path / "staging").resolve()
    root.mkdir()
    (root / "owned.txt").write_text("owned", encoding="utf-8")
    with pytest.raises(ValueError, match="fresh and empty"):
        prepare_c4_stage1_staging_root(root)


def test_prepared_root_identity_cannot_be_replaced(tmp_path: Path) -> None:
    request = _request()
    root = (tmp_path / "staging").resolve()
    displaced = (tmp_path / "displaced").resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    root.rename(displaced)
    root.mkdir()
    failed = C4Stage1WorkerResult.failed(request, failure_code="fixture_failure")
    (root / "worker_result.json").write_bytes(failed.canonical_json_bytes())

    with pytest.raises(ValueError, match="prepared identity"):
        verify_c4_stage1_staging(prepared, request)


@pytest.mark.parametrize("mutation", ["unknown", "failure_png", "result_trailing"])
def test_exact_inventory_and_canonical_result_are_required(
    tmp_path: Path,
    mutation: str,
) -> None:
    request = _request()
    root = (tmp_path / mutation).resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    failed = C4Stage1WorkerResult.failed(request, failure_code="fixture_failure")
    result_bytes = failed.canonical_json_bytes()
    (root / "worker_result.json").write_bytes(
        result_bytes + (b"\n" if mutation == "result_trailing" else b"")
    )
    if mutation == "unknown":
        (root / "unknown.bin").write_bytes(b"unknown")
    elif mutation == "failure_png":
        (root / "direct.png").write_bytes(_png(80))

    with pytest.raises(ValueError):
        verify_c4_stage1_staging(prepared, request)


def test_png_trailing_bytes_or_evidence_mismatch_fail_closed(tmp_path: Path) -> None:
    request = _request()
    root = (tmp_path / "trailing").resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    _, direct, staged = _success(request)
    result, _, _ = _success(request, direct=direct, staged=staged)
    (root / "direct.png").write_bytes(direct + b"trailing")
    (root / "staged.png").write_bytes(staged)
    (root / "worker_result.json").write_bytes(result.canonical_json_bytes())

    with pytest.raises(ValueError):
        verify_c4_stage1_staging(prepared, request)


def test_hardlinks_and_symlinks_are_rejected(tmp_path: Path) -> None:
    request = _request()
    shared = _png(80)
    result, _, _ = _success(request, direct=shared, staged=shared)
    root = (tmp_path / "hardlink").resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    (root / "direct.png").write_bytes(shared)
    os.link(root / "direct.png", root / "staged.png")
    (root / "worker_result.json").write_bytes(result.canonical_json_bytes())
    with pytest.raises(ValueError, match="hard link"):
        verify_c4_stage1_staging(prepared, request)

    link_root = (tmp_path / "symlink").resolve()
    link_root.mkdir()
    prepared_link = prepare_c4_stage1_staging_root(link_root)
    target = (tmp_path / "target.png").resolve()
    target.write_bytes(shared)
    try:
        (link_root / "direct.png").symlink_to(target)
    except OSError:
        pytest.skip("This Windows account cannot create symlinks")
    (link_root / "staged.png").write_bytes(shared)
    (link_root / "worker_result.json").write_bytes(result.canonical_json_bytes())
    with pytest.raises(ValueError, match="links and reparse"):
        verify_c4_stage1_staging(prepared_link, request)


def test_file_swap_between_inventory_and_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    root = (tmp_path / "swap").resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    _write_success(root, request)
    original = staging_module._read_stable_regular
    swapped = False

    def swap_after_result(path: Path, **kwargs) -> bytes:
        nonlocal swapped
        payload = original(path, **kwargs)
        if path.name == "worker_result.json" and not swapped:
            swapped = True
            (root / "direct.png").unlink()
            (root / "direct.png").write_bytes(_png(81))
        return payload

    monkeypatch.setattr(staging_module, "_read_stable_regular", swap_after_result)
    with pytest.raises(ValueError, match="changed while opening"):
        verify_c4_stage1_staging(prepared, request)


def test_result_must_match_parent_held_request(tmp_path: Path) -> None:
    request = _request()
    other_request = request.model_copy(
        update={"worker_request_id": "c4_stage1_worker_request_" + "0" * 32}
    )
    root = (tmp_path / "request-mismatch").resolve()
    root.mkdir()
    prepared = prepare_c4_stage1_staging_root(root)
    failed = C4Stage1WorkerResult.failed(request, failure_code="fixture_failure")
    (root / "worker_result.json").write_bytes(failed.canonical_json_bytes())

    with pytest.raises(ValueError):
        verify_c4_stage1_staging(prepared, other_request)
