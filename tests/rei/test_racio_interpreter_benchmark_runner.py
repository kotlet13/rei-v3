from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.backend.rei.evaluation.racio_interpreter_benchmark import (
    MANIFEST_PATH,
    evaluate_c3_benchmark_run,
    load_c3_racio_interpreter_benchmark,
)
from scripts.run_racio_interpreter_benchmark import (
    SCOPED_RUNTIME_PATHS,
    deterministic_results,
    parse_args,
    write_artifacts,
)


DIGEST = "3f3e5df8a021439fd6f867a0e526bdc303cac79c811201cb6bac193298cb9fcd"


def test_ollama_cli_requires_explicit_identity_and_full_gpu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_OLLAMA_NUM_CTX", "65536")
    monkeypatch.setenv("REI_OLLAMA_NUM_GPU", "999")
    with pytest.raises(SystemExit):
        parse_args(["--mode", "ollama", "--output-dir", str(tmp_path / "a")])
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--mode",
                "ollama",
                "--output-dir",
                str(tmp_path / "b"),
                "--model-id",
                "granite4.1:30b",
                "--model-digest",
                DIGEST,
                "--no-require-full-gpu",
            ]
        )

    args = parse_args(
        [
            "--mode",
            "ollama",
            "--output-dir",
            str(tmp_path / "c"),
            "--model-id",
            "granite4.1:30b",
            "--model-digest",
            DIGEST,
            "--require-full-gpu",
        ]
    )
    assert args.num_ctx == 65536
    assert args.num_gpu == 999
    assert args.require_full_gpu is True


def test_runner_scope_is_c3_specific_and_excludes_native_matrix_runner() -> None:
    script = Path("scripts/run_racio_interpreter_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter" in (
        SCOPED_RUNTIME_PATHS
    )
    assert "scripts/run_racio_interpreter_benchmark.py" in SCOPED_RUNTIME_PATHS
    assert "run_rei_native_profile_matrix" not in script


def test_artifacts_are_create_only_and_record_exact_hashes(tmp_path: Path) -> None:
    suite = load_c3_racio_interpreter_benchmark()
    results = deterministic_results(suite)
    metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="deterministic",
        results=results,
        model_call_count=0,
    )
    output_dir = tmp_path / "artifacts"

    summary = write_artifacts(
        output_dir=output_dir,
        run_id="c3-offline-test",
        source_commit="a" * 40,
        manifest_path=MANIFEST_PATH,
        suite=suite,
        metrics=metrics,
        results=results,
        baseline_results=None,
        registry_path=None,
        candidate=None,
    )

    assert set(path.name for path in output_dir.iterdir()) == {
        "results.jsonl",
        "metrics.json",
        "provenance.json",
    }
    provenance = json.loads((output_dir / "provenance.json").read_text("utf-8"))
    assert provenance["results_sha256"] == summary["results_sha256"]
    assert provenance["metrics_sha256"] == summary["metrics_sha256"]
    assert provenance["model_call_count"] == 0
    assert provenance["source_commit"] == "a" * 40

    with pytest.raises(FileExistsError):
        write_artifacts(
            output_dir=output_dir,
            run_id="c3-offline-test",
            source_commit="a" * 40,
            manifest_path=MANIFEST_PATH,
            suite=suite,
            metrics=metrics,
            results=results,
            baseline_results=None,
            registry_path=None,
            candidate=None,
        )
