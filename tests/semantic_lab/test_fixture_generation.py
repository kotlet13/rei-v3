from __future__ import annotations

import hashlib
import tempfile
from contextlib import suppress
from pathlib import Path

from scripts.build_semantic_lab_fixtures import build

from .conftest import FIXTURE_ROOT, REPO_ROOT, SOURCE_ROOT


def test_fixture_generation_is_deterministic_and_matches_committed_files():
    temp_base = REPO_ROOT / ".pytest-semantic-lab"
    temp_base.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=temp_base) as temp_dir:
            generated_root = Path(temp_dir) / "semantic_lab_v1"
            summary = build(
                source_root=SOURCE_ROOT,
                output_root=generated_root,
                repo_root=REPO_ROOT,
            )

            assert summary["family_count"] == 24
            assert summary["variant_count"] == 192
            assert summary["file_count"] == 25
            assert summary["model_calls"] == 0
            assert summary["training_exports"] == 0

            committed = sorted(
                path.relative_to(FIXTURE_ROOT) for path in FIXTURE_ROOT.glob("*.json")
            )
            generated = sorted(
                path.relative_to(generated_root) for path in generated_root.glob("*.json")
            )
            assert generated == committed
            for relative_path in committed:
                assert (generated_root / relative_path).read_bytes() == (
                    FIXTURE_ROOT / relative_path
                ).read_bytes()
    finally:
        with suppress(OSError):
            temp_base.rmdir()


def test_committed_fixture_hashes_and_check_mode(fixture_manifest):
    summary = build(
        source_root=SOURCE_ROOT,
        output_root=FIXTURE_ROOT,
        repo_root=REPO_ROOT,
        check=True,
    )
    assert summary["mode"] == "check"

    for entry in fixture_manifest["files"]:
        content = (FIXTURE_ROOT / entry["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
