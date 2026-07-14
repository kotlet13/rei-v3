from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.backend.rei.evaluation.manual_cases import (
    DEFAULT_FIXTURE_ROOT,
    evaluate_manual_fixture_set,
)
from app.backend.rei.evaluation.report import REPORT_FILENAMES
from scripts.run_semantic_lab_evaluation import (
    OFFICIAL_MANIFEST_SHA256,
    REPO_ROOT,
    RUN_ID,
    build_evaluation_run,
)


SCRIPT = REPO_ROOT / "scripts" / "run_semantic_lab_evaluation.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(value) for value in args)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_quality_gate_builds_exact_model_free_run() -> None:
    suite, run = build_evaluation_run()

    assert run.run_id == RUN_ID
    assert run.source_manifest_hash == OFFICIAL_MANIFEST_SHA256
    assert len(run.results) == 32
    assert suite.exact_match_count == 32
    assert suite.exact_match
    assert run.evaluator_model_calls == 0
    assert all(result.evaluator_model_calls == 0 for result in run.results)


def test_runner_creates_then_reproduces_exact_six_artifacts(tmp_path: Path) -> None:
    output = tmp_path / RUN_ID

    created = _run("--output-root", output)
    assert created.returncode == 0, created.stderr
    assert tuple(sorted(path.name for path in output.iterdir())) == tuple(
        sorted(REPORT_FILENAMES)
    )

    checked = _run("--output-root", output, "--check")
    assert checked.returncode == 0, checked.stderr
    assert '"exact_match_count": 32' in checked.stdout

    (output / "summary.md").write_text("tampered", encoding="utf-8")
    rejected = _run("--output-root", output, "--check")
    assert rejected.returncode != 0
    assert "not reproducible" in rejected.stderr


def test_resigned_alternative_corpus_cannot_claim_official_run_id(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "resigned-alternative"
    shutil.copytree(DEFAULT_FIXTURE_ROOT, copied_root)

    native_path = copied_root / "native_routes.jsonl"
    records = [
        json.loads(line)
        for line in native_path.read_text(encoding="utf-8").splitlines()
    ]
    records[0]["notes_sl"] += " Alternativni ponovno podpisani korpus."
    native_path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = copied_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    native_entry = next(
        entry for entry in manifest["files"] if entry["path"] == native_path.name
    )
    native_entry["sha256"] = _sha256(native_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert evaluate_manual_fixture_set(copied_root).exact_match
    with pytest.raises(ValueError, match="Official C2 manifest hash mismatch"):
        build_evaluation_run(copied_root)
