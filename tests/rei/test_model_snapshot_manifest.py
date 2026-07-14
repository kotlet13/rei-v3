from __future__ import annotations

import hashlib

import pytest

from app.backend.rei.emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersSnapshotManifest,
    canonical_snapshot_manifest_bytes,
)
from scripts.build_rei_model_snapshot_manifest import build_manifest


def _directory_symlink_or_skip(link, target) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Directory symlinks are unavailable in this environment: {exc}")


def test_snapshot_manifest_is_canonical_stable_and_excludes_transient_cache(
    tmp_path,
) -> None:
    snapshot = tmp_path / "snapshot"
    (snapshot / "transformer").mkdir(parents=True)
    (snapshot / ".cache" / "huggingface").mkdir(parents=True)
    (snapshot / "model_index.json").write_bytes(b'{"_class_name":"Test"}')
    (snapshot / "transformer" / "weights.safetensors").write_bytes(b"weights")
    (snapshot / ".cache" / "huggingface" / "transient.incomplete").write_bytes(
        b"partial"
    )

    manifest, target = build_manifest(
        snapshot_directory=snapshot,
        repo_id="example/model",
        revision="a" * 40,
    )
    first_bytes = target.read_bytes()
    assert target.name == DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    assert tuple(item.relative_path for item in manifest.files) == (
        "model_index.json",
        "transformer/weights.safetensors",
    )
    assert first_bytes == canonical_snapshot_manifest_bytes(manifest)
    parsed = DiffusersSnapshotManifest.model_validate_json(first_bytes)
    assert parsed.model_dump(mode="python") == manifest.model_dump(mode="python")

    repeated, repeated_target = build_manifest(
        snapshot_directory=snapshot,
        repo_id="example/model",
        revision="a" * 40,
    )
    assert repeated_target == target
    assert repeated == manifest
    assert repeated_target.read_bytes() == first_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(
        repeated_target.read_bytes()
    ).hexdigest()


def test_snapshot_manifest_refuses_output_outside_snapshot_root(tmp_path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot root"):
        build_manifest(
            snapshot_directory=snapshot,
            repo_id="example/model",
            revision="b" * 40,
            output=tmp_path / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
        )


def test_snapshot_manifest_rejects_symlinked_component_directory(tmp_path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "model_index.json").write_text("{}", encoding="utf-8")
    external_component = tmp_path / "external-transformer"
    external_component.mkdir()
    (external_component / "weights.safetensors").write_bytes(b"unclosed-weights")
    _directory_symlink_or_skip(snapshot / "transformer", external_component)

    with pytest.raises(ValueError, match="symbolic links and reparse points"):
        build_manifest(
            snapshot_directory=snapshot,
            repo_id="example/model",
            revision="c" * 40,
        )
