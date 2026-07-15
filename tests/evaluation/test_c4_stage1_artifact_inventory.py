from __future__ import annotations

from pathlib import Path

import pytest

from rei.persistence.artifacts import (
    ArtifactIntegrityError,
    FileArtifactStore,
)


def test_exact_inventory_public_boundary_is_sorted_and_restart_safe(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    store = FileArtifactStore(root)
    first = store.write_json("c4-stage1-test", "diagnostics/b.json", {"value": 2})
    second = store.write_json("c4-stage1-test", "diagnostics/a.json", {"value": 1})

    inventory = FileArtifactStore(root).inspect_run_inventory_exact("c4-stage1-test")

    assert tuple(item.relative_path for item in inventory) == (
        "diagnostics/a.json",
        "diagnostics/b.json",
    )
    assert set(inventory) == {first, second}


def test_exact_inventory_rejects_undeclared_directory(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "runs")
    run_path = store.ensure_run_tree("c4-stage1-test")
    (run_path / "undeclared").mkdir()

    with pytest.raises(ArtifactIntegrityError, match="undeclared directory"):
        store.inspect_run_inventory_exact("c4-stage1-test")


def test_exact_inventory_rejects_change_between_cold_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileArtifactStore(tmp_path / "runs")
    stored = store.write_bytes(
        "c4-stage1-test",
        "diagnostics/value.bin",
        b"first",
    )
    target = store.artifact_path(stored.run_id, stored.relative_path)
    original = store._inspect_target_streaming
    calls = 0

    def inspect_and_replace(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == 1:
            target.write_bytes(b"other")
        return result

    monkeypatch.setattr(store, "_inspect_target_streaming", inspect_and_replace)

    with pytest.raises(ArtifactIntegrityError, match="changed during"):
        store.inspect_run_inventory_exact("c4-stage1-test")


def test_exact_inventory_rejects_external_hardlink(tmp_path: Path) -> None:
    store = FileArtifactStore(tmp_path / "runs")
    stored = store.write_bytes(
        "c4-stage1-test",
        "diagnostics/value.bin",
        b"immutable",
    )
    target = store.artifact_path(stored.run_id, stored.relative_path)
    (tmp_path / "outside-link.bin").hardlink_to(target)

    with pytest.raises(ArtifactIntegrityError, match="hard-linked"):
        store.inspect_run_inventory_exact("c4-stage1-test")

    with pytest.raises(ArtifactIntegrityError, match="hard-linked"):
        FileArtifactStore(store.root).read_verified(stored)
