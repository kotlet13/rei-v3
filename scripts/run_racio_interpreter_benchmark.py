"""Run the frozen C3 Racio-interpreter benchmark without touching native matrix runs.

Deterministic mode is model-free.  Ollama mode requires an explicit registry
model ID plus full digest and runs the paired deterministic baseline first.
Official artifact creation refuses dirty scoped runtime or benchmark sources.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backend.rei.communication.model_registry import (  # noqa: E402
    RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
    RacioInterpreterModelCandidate,
    load_racio_interpreter_model_registry,
)
from app.backend.rei.communication.structured_interpreter import (  # noqa: E402
    DeterministicStructuredRacioInterpreterProvider,
    RacioInterpreterProvider,
)
from app.backend.rei.evaluation.racio_interpreter_benchmark import (  # noqa: E402
    MANIFEST_PATH,
    OFFICIAL_MANIFEST_SHA256,
    C3BenchmarkCaseResult,
    C3BenchmarkRunMetrics,
    C3BenchmarkSuite,
    build_execution_provenance,
    evaluate_c3_benchmark_case,
    evaluate_c3_benchmark_run,
    load_c3_racio_interpreter_benchmark,
)
from app.backend.rei.ids import canonical_json_bytes, utc_now  # noqa: E402
from app.backend.rei.providers.native import (  # noqa: E402
    DeterministicExecutionClock,
    ExecutionClock,
    SystemExecutionClock,
)
from app.backend.rei.providers.ollama import (  # noqa: E402
    DEFAULT_OLLAMA_BASE_URL,
    OllamaApiClient,
    OllamaRacioSettings,
)
from app.backend.rei.providers.ollama_interpreter import (  # noqa: E402
    OllamaStructuredRacioInterpreterProvider,
)


SCOPED_RUNTIME_PATHS = (
    "app/backend/rei/models/communication.py",
    "app/backend/rei/communication/__init__.py",
    "app/backend/rei/communication/conscious_access.py",
    "app/backend/rei/communication/model_registry.py",
    "app/backend/rei/communication/processor.py",
    "app/backend/rei/communication/structured_interpreter.py",
    "app/backend/rei/providers/__init__.py",
    "app/backend/rei/providers/ollama_interpreter.py",
    "app/backend/rei/evaluation/racio_interpreter_benchmark.py",
    "config/racio_interpreter_models.yaml",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter",
    "scripts/run_racio_interpreter_benchmark.py",
)
FIXED_CLOCK_START = datetime(2026, 7, 14, tzinfo=timezone.utc)


def _default_run_id(mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    return f"c3-racio-interpreter-{mode}-{stamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    environment = OllamaRacioSettings.from_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("deterministic", "ollama"), default="deterministic")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--model-id")
    parser.add_argument("--model-digest")
    parser.add_argument(
        "--registry", type=Path, default=RACIO_INTERPRETER_MODEL_REGISTRY_PATH
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("REI_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
    )
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--seed", type=int, default=environment.seed)
    parser.add_argument("--temperature", type=float, default=environment.temperature)
    parser.add_argument("--num-ctx", type=int, default=environment.num_ctx)
    parser.add_argument("--num-gpu", type=int, default=environment.num_gpu)
    parser.add_argument("--num-predict", type=int, default=environment.num_predict)
    parser.add_argument("--timeout-seconds", type=float, default=environment.timeout_seconds)
    parser.add_argument("--keep-alive", default=environment.keep_alive)
    parser.add_argument(
        "--require-full-gpu",
        action=argparse.BooleanOptionalAction,
        default=environment.require_full_gpu,
    )
    args = parser.parse_args(argv)
    if args.mode == "ollama":
        if args.model_id is None or args.model_digest is None:
            parser.error("Ollama mode requires --model-id and --model-digest")
        if not args.require_full_gpu:
            parser.error("Official Ollama benchmark requires --require-full-gpu")
    elif args.model_id is not None or args.model_digest is not None:
        parser.error("Deterministic mode does not accept model identity arguments")
    args.run_id = args.run_id or _default_run_id(args.mode)
    return args


def scoped_source_commit() -> str:
    status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *SCOPED_RUNTIME_PATHS,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise ValueError(
            "C3 benchmark runtime and corpus sources must be committed before a run"
        )
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = completed.stdout.strip()
    if len(commit) != 40:
        raise ValueError("C3 benchmark requires a full Git source commit")
    return commit


def execute_provider_suite(
    *,
    suite: C3BenchmarkSuite,
    provider_mode: str,
    provider: RacioInterpreterProvider,
    clock: ExecutionClock,
) -> tuple[C3BenchmarkCaseResult, ...]:
    if provider_mode not in {"deterministic", "ollama"}:
        raise ValueError("Unsupported C3 benchmark provider mode")
    results: list[C3BenchmarkCaseResult] = []
    for case in suite.cases:
        packet = case.packet
        before_bytes = packet.canonical_json_bytes()
        before_hash = packet.content_hash()
        call = provider.build_call_spec(packet)
        execution = None
        error_type = None
        try:
            execution = provider.execute(packet, call=call, clock=clock)
        except Exception as exc:  # one failed attempt remains in the denominator
            error_type = type(exc).__name__
        output = execution.output if execution is not None else None
        call_record = execution.call_record if execution is not None else None
        evidence = None
        if execution is not None:
            evidence = getattr(execution, "response_evidence", None)
            if evidence is None:
                evidence = getattr(execution, "reasoning_artifact", None)
        provenance = build_execution_provenance(
            identity=provider.identity,
            call=call,
            call_record=call_record,
            response_evidence=evidence,
            execution_error_type=error_type,
        )
        unchanged = (
            packet.canonical_json_bytes() == before_bytes
            and packet.content_hash() == before_hash
        )
        results.append(
            evaluate_c3_benchmark_case(
                case=case,
                provider_mode=provider_mode,
                output=output,
                provenance=provenance,
                input_packet_unchanged=unchanged,
            )
        )
    return tuple(results)


def deterministic_results(
    suite: C3BenchmarkSuite,
) -> tuple[C3BenchmarkCaseResult, ...]:
    return execute_provider_suite(
        suite=suite,
        provider_mode="deterministic",
        provider=DeterministicStructuredRacioInterpreterProvider(),
        clock=DeterministicExecutionClock(FIXED_CLOCK_START),
    )


def _ollama_provider(
    args: argparse.Namespace,
) -> tuple[OllamaStructuredRacioInterpreterProvider, RacioInterpreterModelCandidate]:
    registry = load_racio_interpreter_model_registry(args.registry)
    candidate = registry.require_candidate(
        model_id=args.model_id,
        digest=args.model_digest,
    )
    if candidate.runtime != "ollama" or "structured_text" not in candidate.modality_support:
        raise ValueError("Selected registry candidate cannot run this structured benchmark")
    if args.num_ctx > candidate.max_context:
        raise ValueError("Requested context exceeds the selected registry candidate")
    settings = OllamaRacioSettings(
        model=candidate.model_id,
        seed=args.seed,
        temperature=args.temperature,
        num_ctx=args.num_ctx,
        num_gpu=args.num_gpu,
        num_predict=args.num_predict,
        timeout_seconds=args.timeout_seconds,
        keep_alive=args.keep_alive,
        require_full_gpu=True,
    )
    client = OllamaApiClient(
        base_url=args.base_url,
        allow_remote=args.allow_remote,
    )
    provider = OllamaStructuredRacioInterpreterProvider.discover(
        client=client,
        settings=settings,
        expected_digest=candidate.model_digest,
    )
    return provider, candidate


def _jsonl_bytes(values: tuple[C3BenchmarkCaseResult, ...]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recorded_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        value = resolved.relative_to(ROOT)
    except ValueError:
        value = resolved
    return str(value).replace("\\", "/")


def write_artifacts(
    *,
    output_dir: Path,
    run_id: str,
    source_commit: str,
    manifest_path: Path,
    suite: C3BenchmarkSuite,
    metrics: C3BenchmarkRunMetrics,
    results: tuple[C3BenchmarkCaseResult, ...],
    baseline_results: tuple[C3BenchmarkCaseResult, ...] | None,
    registry_path: Path | None,
    candidate: RacioInterpreterModelCandidate | None,
) -> dict[str, Any]:
    target = output_dir.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=False)
    results_path = target / "results.jsonl"
    metrics_path = target / "metrics.json"
    results_path.write_bytes(_jsonl_bytes(results))
    metrics_path.write_bytes(canonical_json_bytes(metrics) + b"\n")
    baseline_path = None
    if baseline_results is not None:
        baseline_path = target / "baseline_results.jsonl"
        baseline_path.write_bytes(_jsonl_bytes(baseline_results))

    provenance: dict[str, Any] = {
        "schema_version": "rei-c3-racio-interpreter-run-provenance-v1",
        "run_id": run_id,
        "source_commit": source_commit,
        "created_at": utc_now(),
        "provider_mode": metrics.provider_mode,
        "benchmark_id": metrics.benchmark_id,
        "benchmark_manifest_path": _recorded_path(manifest_path),
        "benchmark_manifest_hash": suite.manifest_file_hash,
        "public_cases_hash": suite.manifest.files[0].sha256,
        "gold_hash": suite.manifest.files[1].sha256,
        "model_call_count": metrics.model_call_count,
        "results_sha256": _file_hash(results_path),
        "metrics_sha256": _file_hash(metrics_path),
        "baseline_results_sha256": (
            _file_hash(baseline_path) if baseline_path is not None else None
        ),
        "registry_path": (
            _recorded_path(registry_path)
            if registry_path is not None
            else None
        ),
        "registry_sha256": (
            _file_hash(registry_path.resolve()) if registry_path is not None else None
        ),
        "model_candidate": candidate,
        "quality_gate_pass": metrics.quality_gate_pass,
    }
    provenance_path = target / "provenance.json"
    provenance_path.write_bytes(canonical_json_bytes(provenance) + b"\n")
    return {
        "output_dir": str(target),
        "results_sha256": provenance["results_sha256"],
        "metrics_sha256": provenance["metrics_sha256"],
        "provenance_sha256": _file_hash(provenance_path),
        "quality_gate_pass": metrics.quality_gate_pass,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_commit = scoped_source_commit()
    suite = load_c3_racio_interpreter_benchmark(args.manifest)
    if suite.manifest_file_hash != OFFICIAL_MANIFEST_SHA256:
        raise ValueError("Official C3 runs require the pinned benchmark manifest")
    baseline = deterministic_results(suite)
    candidate = None
    registry_path = None
    if args.mode == "deterministic":
        results = baseline
        metrics = evaluate_c3_benchmark_run(
            suite=suite,
            provider_mode="deterministic",
            results=results,
            model_call_count=0,
        )
        baseline_artifact = None
    else:
        provider, candidate = _ollama_provider(args)
        registry_path = args.registry
        results = execute_provider_suite(
            suite=suite,
            provider_mode="ollama",
            provider=provider,
            clock=SystemExecutionClock(),
        )
        metrics = evaluate_c3_benchmark_run(
            suite=suite,
            provider_mode="ollama",
            results=results,
            model_call_count=32,
            baseline_results=baseline,
        )
        baseline_artifact = baseline
    summary = write_artifacts(
        output_dir=args.output_dir,
        run_id=args.run_id,
        source_commit=source_commit,
        manifest_path=args.manifest,
        suite=suite,
        metrics=metrics,
        results=results,
        baseline_results=baseline_artifact,
        registry_path=registry_path,
        candidate=candidate,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if metrics.quality_gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
