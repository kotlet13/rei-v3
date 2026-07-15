from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rei.emocio.diffusers_renderer import (
    DiffusersSnapshotManifest,
    canonical_snapshot_manifest_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_ROOT = (
    ROOT / "Docs" / "evals" / "semantic_lab_v1" / "c4-stage1-preflight-2026-07-15"
)

EXPECTED = {
    "longcat_turbo_snapshot_manifest.json": {
        "repo_id": "meituan-longcat/LongCat-Image-Edit-Turbo",
        "revision": "6a7262de5549f0bf0ec54c08ef7d283ef41f3214",
        "sha256": "4a447342e10a7b214f43818e666af6a25b8c757650f7f8b6ff4317fca0f24783",
        "file_count": 37,
        "total_bytes": 29_322_428_829,
    },
    "omnigen_snapshot_manifest.json": {
        "repo_id": "Shitao/OmniGen-v1-diffusers",
        "revision": "016e2f61d12a98303f6bbdf122687694d7984268",
        "sha256": "3522d2bb368a4a304045432d6641abb69a4b73d876d8f904d36efe9458998bce",
        "file_count": 11,
        "total_bytes": 8_088_956_424,
    },
}


@pytest.mark.parametrize(("filename", "expected"), EXPECTED.items())
def test_committed_stage1_snapshot_manifest_normalizes_to_exact_canonical_bytes(
    filename: str,
    expected: dict[str, object],
) -> None:
    raw = (PREFLIGHT_ROOT / filename).read_bytes()
    manifest = DiffusersSnapshotManifest.model_validate_json(raw)
    canonical = canonical_snapshot_manifest_bytes(manifest)

    assert raw in {canonical, canonical + b"\n"}
    assert manifest.repo_id == expected["repo_id"]
    assert manifest.revision == expected["revision"]
    assert hashlib.sha256(canonical).hexdigest() == expected["sha256"]
    assert len(manifest.files) == expected["file_count"]
    assert sum(item.size_bytes for item in manifest.files) == expected["total_bytes"]

    paths = tuple(item.relative_path for item in manifest.files)
    assert paths == tuple(sorted(paths))
    assert len(paths) == len(set(paths))
    assert all(
        path
        and "\\" not in path
        and not Path(path).is_absolute()
        and all(part not in {"", ".", ".."} for part in path.split("/"))
        for path in paths
    )


def test_stage1_addendum_preserves_model_free_and_sampled_memory_boundary() -> None:
    addendum = (
        ROOT
        / "Docs"
        / "evals"
        / "semantic_lab_v1"
        / "c4_stage1_model_free_integration_addendum_2026-07-15.md"
    ).read_text(encoding="utf-8")

    assert "NO MODEL LOAD, INFERENCE" in addendum
    assert (
        "sampled whole-device CUDA used-memory stop threshold = 31,500 MiB" in addendum
    )
    assert "neither proves an unsampled transient maximum" in addendum
    assert "reviewed, committed and pushed to `main`" in addendum
