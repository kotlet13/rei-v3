from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from rei.evaluation.c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY,
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
    C4_STAGE1_REVIEW_PRESENTER_REVISION,
    C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
    C4Stage1ReviewRuntimeError,
    C4Stage1ReviewRuntimeManifest,
    capture_c4_stage1_review_runtime_manifest,
    verify_c4_stage1_review_runtime_manifest,
)
from rei.ids import canonical_json_bytes, content_id


ROOT = Path(__file__).resolve().parents[2]
UI_RELATIVE = Path("app/backend/rei/evaluation/c4_stage1_review_ui")
EXPECTED_ASSETS = (
    (
        "app/backend/rei/evaluation/c4_stage1_review_ui/index.html",
        8235,
        "56f444301db1901c227b939cca0503f29b1848ee35bb2f3d7397bd87d3076e76",
    ),
    (
        "app/backend/rei/evaluation/c4_stage1_review_ui/review.css",
        3539,
        "0f08b314970c8546655b6a9003e3c9c6a79c5d2517ee0b7cf7ebfa9dceb868a5",
    ),
    (
        "app/backend/rei/evaluation/c4_stage1_review_ui/review.js",
        9908,
        "2d7115e0ea5ebdf1473c60de32c40069f02ad37195f90d6445f4d95baa049f5c",
    ),
)


def _copy_ui(tmp_path: Path) -> Path:
    repository = (tmp_path / "repository").resolve()
    target = repository / UI_RELATIVE
    target.mkdir(parents=True)
    source = ROOT / UI_RELATIVE
    for name in ("index.html", "review.css", "review.js"):
        shutil.copy2(source / name, target / name)
    return repository


def test_runtime_manifest_is_exact_content_addressed_and_path_free() -> None:
    manifest = capture_c4_stage1_review_runtime_manifest(ROOT.resolve())

    assert manifest.schema_version == "rei-c4-stage1-review-runtime-manifest-v1"
    assert manifest.presenter_implementation_id == (
        C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
    )
    assert manifest.presenter_revision == C4_STAGE1_REVIEW_PRESENTER_REVISION
    assert manifest.ipc_protocol == C4_STAGE1_REVIEW_IPC_PROTOCOL
    assert manifest.service_schema_revision == C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION
    assert manifest.ledger_schema_revision == C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION
    assert manifest.content_security_policy == C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY
    assert manifest.ui_bundle_sha256 == (
        "a6c0a268af2fe35ce9981518f9081a4ed852a93f0b3e45d61fae22c3b0e00b8f"
    )
    assert (
        tuple(
            (item.relative_path, item.byte_size, item.sha256)
            for item in manifest.assets
        )
        == EXPECTED_ASSETS
    )
    assert manifest.required_review_boolean_count == 16
    assert manifest.review_boolean_defaults_allowed is False
    assert manifest.offline_only is True
    assert manifest.network_access_allowed is False
    assert manifest.visible_provider_or_model_identity_tokens_present is False
    assert manifest.semantic_quality_gate_passed is False
    assert manifest.production_authority_granted is False
    assert manifest.model_calls == 0

    payload = manifest.model_dump(
        mode="python",
        round_trip=True,
        exclude={"runtime_manifest_id", "runtime_manifest_sha256"},
    )
    assert manifest.runtime_manifest_id == content_id("c4_s1_review_runtime", payload)
    assert (
        manifest.runtime_manifest_sha256
        == hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    )
    serialized = manifest.canonical_json_bytes()
    assert str(ROOT.resolve()).encode() not in serialized
    assert b'model_calls":0' in serialized


def test_runtime_manifest_capture_and_cold_verification_are_deterministic(
    tmp_path: Path,
) -> None:
    repository = _copy_ui(tmp_path)
    first = capture_c4_stage1_review_runtime_manifest(repository)
    second = capture_c4_stage1_review_runtime_manifest(repository)

    assert first == second
    assert first.canonical_json_bytes() == second.canonical_json_bytes()
    assert verify_c4_stage1_review_runtime_manifest(repository, first) == first
    assert (
        C4Stage1ReviewRuntimeManifest.model_validate_json(first.model_dump_json())
        == first
    )


@pytest.mark.parametrize("name", ["index.html", "review.css", "review.js"])
def test_runtime_capture_rejects_missing_and_tampered_assets(
    tmp_path: Path,
    name: str,
) -> None:
    missing_repository = _copy_ui(tmp_path / "missing")
    (missing_repository / UI_RELATIVE / name).unlink()
    with pytest.raises(C4Stage1ReviewRuntimeError, match="missing or additional"):
        capture_c4_stage1_review_runtime_manifest(missing_repository)

    tampered_repository = _copy_ui(tmp_path / "tampered")
    with (tampered_repository / UI_RELATIVE / name).open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(C4Stage1ReviewRuntimeError, match="pinned revision"):
        capture_c4_stage1_review_runtime_manifest(tampered_repository)


def test_runtime_capture_rejects_additional_assets_and_directories(
    tmp_path: Path,
) -> None:
    repository = _copy_ui(tmp_path / "file")
    (repository / UI_RELATIVE / "unexpected.txt").write_bytes(b"unexpected")
    with pytest.raises(C4Stage1ReviewRuntimeError, match="missing or additional"):
        capture_c4_stage1_review_runtime_manifest(repository)

    directory_repository = _copy_ui(tmp_path / "directory")
    (directory_repository / UI_RELATIVE / "nested").mkdir()
    with pytest.raises(C4Stage1ReviewRuntimeError, match="missing or additional"):
        capture_c4_stage1_review_runtime_manifest(directory_repository)


def test_runtime_capture_rejects_hardlinks(tmp_path: Path) -> None:
    repository = _copy_ui(tmp_path)
    asset = repository / UI_RELATIVE / "review.css"
    outside = tmp_path / "outside.css"
    shutil.copy2(asset, outside)
    asset.unlink()
    asset.hardlink_to(outside)

    with pytest.raises(C4Stage1ReviewRuntimeError, match="ordinary non-linked"):
        capture_c4_stage1_review_runtime_manifest(repository)


def test_runtime_capture_rejects_linked_assets_and_ui_ancestry(tmp_path: Path) -> None:
    asset_repository = _copy_ui(tmp_path / "asset")
    asset = asset_repository / UI_RELATIVE / "review.js"
    outside = tmp_path / "outside.js"
    shutil.copy2(asset, outside)
    asset.unlink()
    try:
        asset.symlink_to(outside)
    except OSError:
        pytest.skip("This account cannot create file symlinks")
    with pytest.raises(C4Stage1ReviewRuntimeError, match="ordinary non-linked"):
        capture_c4_stage1_review_runtime_manifest(asset_repository)

    ancestry_repository = _copy_ui(tmp_path / "ancestry")
    directory = ancestry_repository / UI_RELATIVE
    moved = tmp_path / "moved-ui"
    directory.rename(moved)
    try:
        directory.symlink_to(moved, target_is_directory=True)
    except OSError:
        pytest.skip("This account cannot create directory symlinks")
    with pytest.raises(
        C4Stage1ReviewRuntimeError, match="ordinary non-reparse directory"
    ):
        capture_c4_stage1_review_runtime_manifest(ancestry_repository)


def test_runtime_verifier_rejects_forged_or_wrong_expected_manifest(
    tmp_path: Path,
) -> None:
    repository = _copy_ui(tmp_path)
    manifest = capture_c4_stage1_review_runtime_manifest(repository)
    forged = manifest.model_copy(update={"runtime_manifest_sha256": "0" * 64})

    with pytest.raises(C4Stage1ReviewRuntimeError, match="manifest is invalid"):
        verify_c4_stage1_review_runtime_manifest(repository, forged)
    with pytest.raises(TypeError, match="C4Stage1ReviewRuntimeManifest"):
        verify_c4_stage1_review_runtime_manifest(repository, object())  # type: ignore[arg-type]


def test_runtime_capture_requires_an_absolute_repository_root() -> None:
    with pytest.raises(C4Stage1ReviewRuntimeError, match="must be absolute"):
        capture_c4_stage1_review_runtime_manifest(Path("."))
