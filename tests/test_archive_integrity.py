from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive" / "rei_v3_text_llm_baseline_2026-07-13"
CHECKSUMS = ARCHIVE / "FILES.sha256"
SHA256_LINE = re.compile(r"^(?P<digest>[0-9a-f]{64})  (?P<path>.+)$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _recorded_checksums() -> dict[str, str]:
    records: dict[str, str] = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        matched = SHA256_LINE.fullmatch(line)
        assert matched is not None, f"Invalid checksum line: {line!r}"
        relative = matched.group("path")
        posix = PurePosixPath(relative)
        assert not posix.is_absolute()
        assert ".." not in posix.parts
        assert "\\" not in relative
        assert relative not in records, f"Duplicate checksum path: {relative}"
        records[relative] = matched.group("digest")
    return records


def test_frozen_textual_baseline_matches_complete_sha256_inventory() -> None:
    recorded = _recorded_checksums()
    actual_payload = {
        path.relative_to(ARCHIVE).as_posix()
        for path in ARCHIVE.rglob("*")
        if path.is_file() and path != CHECKSUMS
    }
    assert set(recorded) == actual_payload

    for relative, expected in recorded.items():
        path = ARCHIVE.joinpath(*PurePosixPath(relative).parts)
        assert path.is_file() and not path.is_symlink()
        assert _sha256(path) == expected, relative


def test_archive_manifest_and_source_commit_are_self_consistent() -> None:
    manifest = json.loads((ARCHIVE / "MANIFEST.json").read_text(encoding="utf-8"))
    source_commit = (ARCHIVE / "SOURCE_COMMIT").read_text(encoding="ascii").strip()

    assert re.fullmatch(r"[0-9a-f]{40}", source_commit)
    assert manifest["source_commit"] == source_commit
    assert manifest["verification"]["archive_hashes"] == "passed"
    assert manifest["verification"]["pytest_result"] == "not run by archive script"
    verification = (ARCHIVE / "BASELINE_VERIFICATION.md").read_text(encoding="utf-8")
    assert "Kickoff gate status: PASSED" in verification
    assert "There are 75 hashed files" in verification
