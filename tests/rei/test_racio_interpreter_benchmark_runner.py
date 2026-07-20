from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.backend.rei.communication.conscious_access import ConsciousAccessPacket
from app.backend.rei.communication.model_registry import (
    RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
    load_racio_interpreter_model_registry,
)
from app.backend.rei.evaluation.racio_interpreter_benchmark import (
    C3FailureEvidence,
    MANIFEST_PATH,
    evaluate_c3_benchmark_run,
    load_c3_racio_interpreter_benchmark,
)
from app.backend.rei.ids import content_id
from app.backend.rei.models.provider import (
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
)
from app.backend.rei.providers.native import (
    DeterministicExecutionClock,
    build_provider_call_spec,
)
from app.backend.rei.providers.ollama_interpreter import (
    OllamaInterpreterExecutionError,
)
import scripts.run_racio_interpreter_benchmark as benchmark_runner
from scripts.run_racio_interpreter_benchmark import (
    FIXED_CLOCK_START,
    SCOPED_RUNTIME_PATHS,
    deterministic_results,
    execute_provider_suite,
    parse_args,
    scoped_source_commit,
    verify_scoped_source_unchanged,
    write_artifacts,
)


DIGEST = "3f3e5df8a021439fd6f867a0e526bdc303cac79c811201cb6bac193298cb9fcd"
QWEN_36_DIGEST = (
    "07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522"
)


class RejectingModelProvider:
    @property
    def identity(self) -> ProviderIdentity:
        payload: dict[str, Any] = {
            "kind": "text_reasoner",
            "implementation": "tests.RejectingModelProvider",
            "implementation_revision": "failure-closure-v1",
            "uses_model": True,
            "model": "qwen3.6:35b",
            "model_revision": QWEN_36_DIGEST,
        }
        return ProviderIdentity(
            provider_id=content_id("provider", payload),
            **payload,
        )

    def build_call_spec(self, packet: ConsciousAccessPacket) -> ProviderCallSpec:
        return build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=(packet.packet_id,),
            seed=314159,
            fallback_policy=ProviderFallbackPolicy(
                mode="none",
                no_fallback_reason="Synthetic failure closure has no fallback.",
            ),
        )

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        raise OllamaInterpreterExecutionError(
            "structured_output_invalid",
            "secret raw response and local path must not persist",
            rejected_response_sha256="d" * 64,
            rejected_response_byte_count=17,
        )


class EmptyResponseRejectingModelProvider(RejectingModelProvider):
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        raise OllamaInterpreterExecutionError(
            "structured_output_invalid",
            "empty response",
            rejected_response_sha256=sha256(b"").hexdigest(),
            rejected_response_byte_count=0,
        )


def test_historical_bilingual_ollama_cli_is_retired_on_current_source(
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

    with pytest.raises(SystemExit):
        parse_args(
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


def test_runner_scope_is_c3_specific_and_excludes_native_matrix_runner() -> None:
    script = Path("scripts/run_racio_interpreter_benchmark.py").read_text(
        encoding="utf-8"
    )
    assert "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter" in (
        SCOPED_RUNTIME_PATHS
    )
    assert "tests/fixtures/semantic_lab_v1" in SCOPED_RUNTIME_PATHS
    assert "scripts/run_racio_interpreter_benchmark.py" in SCOPED_RUNTIME_PATHS
    assert "app/backend/rei" in SCOPED_RUNTIME_PATHS
    assert not any(
        path.startswith("app/backend/rei/") for path in SCOPED_RUNTIME_PATHS
    )
    assert "run_rei_native_profile_matrix" not in script


def test_official_source_gate_requires_clean_main_at_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40

    def fake_run(command, **kwargs):
        del kwargs
        if command[:3] == ["git", "branch", "--show-current"]:
            return SimpleNamespace(stdout="main\n", returncode=0)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=f"{commit}\n", returncode=0)
        if command[:4] == ["git", "rev-parse", "--verify", "origin/main"]:
            return SimpleNamespace(stdout=f"{commit}\n", returncode=0)
        if command[:2] == ["git", "status"]:
            return SimpleNamespace(stdout="", returncode=0)
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(benchmark_runner.subprocess, "run", fake_run)
    assert scoped_source_commit() == commit


def test_official_source_gate_rejects_dirty_package_initializer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40

    def fake_run(command, **kwargs):
        del kwargs
        if command[:3] == ["git", "branch", "--show-current"]:
            return SimpleNamespace(stdout="main\n", returncode=0)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=f"{commit}\n", returncode=0)
        if command[:4] == ["git", "rev-parse", "--verify", "origin/main"]:
            return SimpleNamespace(stdout=f"{commit}\n", returncode=0)
        if command[:2] == ["git", "status"]:
            assert "app/backend/rei" in command
            return SimpleNamespace(
                stdout=" M app/backend/rei/evaluation/__init__.py\n",
                returncode=0,
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(benchmark_runner.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="must be committed"):
        scoped_source_commit()


def test_official_source_gate_rejects_non_main_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        benchmark_runner.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout="codex/feature\n",
            returncode=0,
        ),
    )
    with pytest.raises(ValueError, match="directly on main"):
        scoped_source_commit()


def test_post_run_gate_detects_registry_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    registry_path = tmp_path / "registry.json"
    registry_path.write_text("{}\n", encoding="utf-8")
    snapshot = sha256(registry_path.read_bytes()).hexdigest()
    monkeypatch.setattr(benchmark_runner, "scoped_source_commit", lambda: commit)

    verify_scoped_source_unchanged(
        source_commit=commit,
        registry_path=registry_path,
        registry_sha256=snapshot,
    )
    registry_path.write_text('{"changed":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="registry changed"):
        verify_scoped_source_unchanged(
            source_commit=commit,
            registry_path=registry_path,
            registry_sha256=snapshot,
        )


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
    assert provenance["schema_version"] == (
        "rei-c3-racio-interpreter-run-provenance-v2"
    )
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


def test_writer_rejects_forged_metrics_before_publication(tmp_path: Path) -> None:
    suite = load_c3_racio_interpreter_benchmark()
    results = deterministic_results(suite)
    metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="deterministic",
        results=results,
        model_call_count=0,
    )
    forged = metrics.model_copy(
        update={
            "passed_case_count": 0,
            "quality_gate_pass": not metrics.quality_gate_pass,
        }
    )

    with pytest.raises(ValueError, match="recomputed evidence"):
        write_artifacts(
            output_dir=tmp_path / "forged-metrics",
            run_id="c3-forged-metrics",
            source_commit="a" * 40,
            manifest_path=MANIFEST_PATH,
            suite=suite,
            metrics=forged,
            results=results,
            baseline_results=None,
            registry_path=None,
            candidate=None,
        )
    assert not (tmp_path / "forged-metrics").exists()


def test_empty_rejected_response_is_recorded_without_aborting_suite() -> None:
    suite = load_c3_racio_interpreter_benchmark()
    failures: list[C3FailureEvidence] = []
    results = execute_provider_suite(
        suite=suite,
        provider_mode="ollama",
        provider=EmptyResponseRejectingModelProvider(),
        clock=DeterministicExecutionClock(FIXED_CLOCK_START),
        run_id="c3-empty-response-test",
        failure_records=failures,
    )

    assert len(results) == 32
    assert len(failures) == 32
    assert all(item.rejected_response_byte_count == 0 for item in failures)
    assert all(
        item.rejected_response_sha256 == sha256(b"").hexdigest()
        for item in failures
    )


def test_model_failure_artifacts_are_sanitized_and_exactly_closed(
    tmp_path: Path,
) -> None:
    suite = load_c3_racio_interpreter_benchmark()
    baseline = deterministic_results(suite)
    failures = []
    results = execute_provider_suite(
        suite=suite,
        provider_mode="ollama",
        provider=RejectingModelProvider(),
        clock=DeterministicExecutionClock(FIXED_CLOCK_START),
        run_id="c3-failure-closure-test",
        failure_records=failures,
    )
    metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="ollama",
        results=results,
        model_call_count=32,
        baseline_results=baseline,
    )
    registry = load_racio_interpreter_model_registry()
    candidate = registry.require_candidate(
        model_id="qwen3.6:35b",
        digest=QWEN_36_DIGEST,
    )
    output_dir = tmp_path / "model-failures"

    write_artifacts(
        output_dir=output_dir,
        run_id="c3-failure-closure-test",
        source_commit="a" * 40,
        manifest_path=MANIFEST_PATH,
        suite=suite,
        metrics=metrics,
        results=results,
        baseline_results=baseline,
        registry_path=RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
        candidate=candidate,
        failures=tuple(failures),
    )

    assert len(failures) == 32
    raw_failures = (output_dir / "failures.jsonl").read_text("utf-8")
    records = [json.loads(line) for line in raw_failures.splitlines()]
    assert len(records) == 32
    assert all(item["failure_code"] == "structured_output_invalid" for item in records)
    assert all(item["rejected_response_sha256"] == "d" * 64 for item in records)
    assert "secret raw response" not in raw_failures
    assert "local path" not in raw_failures
    assert all(
        result.provenance.execution_error_type == "structured_output_invalid"
        for result in results
    )
    provenance = json.loads((output_dir / "provenance.json").read_text("utf-8"))
    assert provenance["failure_count"] == 32
    assert provenance["failures_sha256"] is not None

    first_case = next(
        case for case in suite.cases if case.public.case_id == failures[0].case_id
    )
    substituted_code = C3FailureEvidence.create(
        run_id="c3-failure-closure-test",
        benchmark_id=suite.manifest.benchmark_id,
        case_id=first_case.public.case_id,
        packet=first_case.packet,
        call=results[0].provenance.call_spec,
        failure_code="gpu_placement_failure",
    )
    invalid_sets = (
        tuple(failures[:-1]),
        (*failures, failures[-1]),
        (
            failures[0].model_copy(update={"run_id": "another-run"}),
            *failures[1:],
        ),
        (
            failures[0].model_copy(
                update={"rejected_response_sha256": "e" * 64}
            ),
            *failures[1:],
        ),
        (substituted_code, *failures[1:]),
    )
    for index, invalid in enumerate(invalid_sets):
        with pytest.raises(ValueError, match="failure evidence"):
            write_artifacts(
                output_dir=tmp_path / f"invalid-failures-{index}",
                run_id="c3-failure-closure-test",
                source_commit="a" * 40,
                manifest_path=MANIFEST_PATH,
                suite=suite,
                metrics=metrics,
                results=results,
                baseline_results=baseline,
                registry_path=RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
                candidate=candidate,
                failures=tuple(invalid),
            )
