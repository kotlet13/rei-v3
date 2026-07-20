"""Run the frozen C3 benchmark in model-free deterministic replay mode.

The historical bilingual Ollama mode is retired on current source. Exact model
replay remains attached to its accepted historical commit; active local-model
work must use a separately reviewed English-only runner and provider revision.
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
from typing import Any, Literal, Self

from pydantic import Field, model_validator


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
    C3FailureCode,
    C3FailureEvidence,
    build_execution_provenance,
    evaluate_c3_benchmark_case,
    evaluate_c3_benchmark_run,
    load_c3_racio_interpreter_benchmark,
)
from app.backend.rei.ids import canonical_json_bytes, utc_now  # noqa: E402
from app.backend.rei.models.common import (  # noqa: E402
    CommitDigest,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    UtcTimestamp,
)
from app.backend.rei.providers.native import (  # noqa: E402
    DeterministicExecutionClock,
    ExecutionClock,
    SystemExecutionClock,
)
from app.backend.rei.providers.ollama import (  # noqa: E402
    DEFAULT_OLLAMA_BASE_URL,
    OllamaApiClient,
    OllamaRacioSettings,
    OllamaResponseError,
    OllamaTransportError,
)
from app.backend.rei.providers.ollama_interpreter import (  # noqa: E402
    OllamaInterpreterExecutionError,
    OllamaStructuredRacioInterpreterProvider,
)


SCOPED_RUNTIME_PATHS = (
    "app/backend/rei",
    "config/racio_interpreter_models.yaml",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1",
    "scripts/build_c3_racio_holdout.py",
    "scripts/run_racio_interpreter_benchmark.py",
    "tests/fixtures/semantic_lab_v1",
)
FIXED_CLOCK_START = datetime(2026, 7, 14, tzinfo=timezone.utc)


class C3BenchmarkRunProvenance(FrozenModel):
    schema_version: Literal["rei-c3-racio-interpreter-run-provenance-v2"]
    run_id: NonEmptyId
    source_commit: CommitDigest
    created_at: UtcTimestamp
    provider_mode: Literal["deterministic", "ollama"]
    benchmark_id: Literal[
        "rei-c3-racio-interpreter-benchmark-v1",
        "rei-c3-racio-interpreter-holdout-v1",
    ]
    benchmark_manifest_path: NonEmptyText
    benchmark_manifest_hash: HashDigest
    public_cases_hash: HashDigest
    gold_hash: HashDigest
    model_call_count: int = Field(ge=0)
    results_sha256: HashDigest
    metrics_sha256: HashDigest
    baseline_results_sha256: HashDigest | None = None
    failure_count: int = Field(ge=0)
    failures_sha256: HashDigest | None = None
    registry_path: NonEmptyText | None = None
    registry_sha256: HashDigest | None = None
    model_candidate: RacioInterpreterModelCandidate | None = None
    quality_gate_pass: bool

    @model_validator(mode="after")
    def validate_run_closure(self) -> Self:
        if self.provider_mode == "deterministic":
            if (
                self.model_call_count != 0
                or self.baseline_results_sha256 is not None
                or self.failure_count != 0
                or self.failures_sha256 is not None
                or self.registry_path is not None
                or self.registry_sha256 is not None
                or self.model_candidate is not None
            ):
                raise ValueError("Deterministic C3 run provenance claims model artifacts")
        elif (
            self.model_call_count != 32
            or self.baseline_results_sha256 is None
            or self.failures_sha256 is None
            or self.registry_path is None
            or self.registry_sha256 is None
            or self.model_candidate is None
        ):
            raise ValueError("Ollama C3 run provenance is not fully closed")
        return self


def _default_run_id(mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    return f"c3-racio-interpreter-{mode}-{stamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    environment = OllamaRacioSettings.from_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("deterministic",), default="deterministic")
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
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if branch.stdout.strip() != "main":
        raise ValueError("Official C3 runs must execute directly on main")
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
    remote = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if remote.stdout.strip() != commit:
        raise ValueError("Official C3 runs require HEAD to equal origin/main")
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
    return commit


def verify_scoped_source_unchanged(
    *,
    source_commit: str,
    registry_path: Path | None,
    registry_sha256: str | None,
) -> None:
    if scoped_source_commit() != source_commit:
        raise ValueError("C3 scoped source changed during benchmark execution")
    if (registry_path is None) != (registry_sha256 is None):
        raise ValueError("C3 registry snapshot identity is incomplete")
    if registry_path is not None and _file_hash(registry_path.resolve()) != registry_sha256:
        raise ValueError("C3 model registry changed during benchmark execution")


def execute_provider_suite(
    *,
    suite: C3BenchmarkSuite,
    provider_mode: str,
    provider: RacioInterpreterProvider,
    clock: ExecutionClock,
    run_id: str | None = None,
    failure_records: list[C3FailureEvidence] | None = None,
) -> tuple[C3BenchmarkCaseResult, ...]:
    if provider_mode not in {"deterministic", "ollama"}:
        raise ValueError("Unsupported C3 benchmark provider mode")
    if (run_id is None) != (failure_records is None):
        raise ValueError("C3 failure evidence requires both run ID and output sink")
    results: list[C3BenchmarkCaseResult] = []
    for case in suite.cases:
        packet = case.packet
        before_bytes = packet.canonical_json_bytes()
        before_hash = packet.content_hash()
        call = provider.build_call_spec(packet)
        execution = None
        failure_code: C3FailureCode | None = None
        try:
            execution = provider.execute(packet, call=call, clock=clock)
        except Exception as exc:  # one failed attempt remains in the denominator
            failure_code = classify_c3_execution_failure(exc)
            if failure_records is not None and run_id is not None:
                rejected_hash = None
                rejected_size = None
                if isinstance(exc, OllamaInterpreterExecutionError):
                    rejected_hash = exc.rejected_response_sha256
                    rejected_size = exc.rejected_response_byte_count
                failure_records.append(
                    C3FailureEvidence.create(
                        run_id=run_id,
                        benchmark_id=suite.manifest.benchmark_id,
                        case_id=case.public.case_id,
                        packet=packet,
                        call=call,
                        failure_code=failure_code,
                        rejected_response_sha256=rejected_hash,
                        rejected_response_byte_count=rejected_size,
                    )
                )
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
            execution_failure_code=failure_code,
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


def classify_c3_execution_failure(exc: Exception) -> C3FailureCode:
    """Map an exception to a stable code without persisting its message."""

    if isinstance(exc, OllamaInterpreterExecutionError):
        return exc.failure_code
    if isinstance(exc, OllamaTransportError):
        return "transport_failure"
    if isinstance(exc, OllamaResponseError):
        return "generation_contract_failure"
    return "unexpected_provider_failure"


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
    raise RuntimeError(
        "Historical bilingual C3 Ollama execution is retired on current source"
    )

    # Retained below only to preserve the historical implementation for audit.
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


def _failure_jsonl_bytes(values: tuple[C3FailureEvidence, ...]) -> bytes:
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


def _validate_failure_closure(
    *,
    run_id: str,
    metrics: C3BenchmarkRunMetrics,
    results: tuple[C3BenchmarkCaseResult, ...],
    registry_path: Path | None,
    candidate: RacioInterpreterModelCandidate | None,
    failures: tuple[C3FailureEvidence, ...],
) -> None:
    for failure in failures:
        try:
            cold = C3FailureEvidence.model_validate_json(
                failure.canonical_json_bytes()
            )
        except ValueError as exc:
            raise ValueError("C3 failure evidence is not content-address valid") from exc
        if cold != failure:
            raise ValueError("C3 failure evidence differs after cold validation")
    if candidate is None:
        if registry_path is not None or failures:
            raise ValueError(
                "Deterministic C3 artifacts cannot claim registry or failure evidence"
            )
        if any(result.provenance.execution_error_type is not None for result in results):
            raise ValueError(
                "Deterministic C3 artifacts cannot contain provider failures"
            )
        return
    if registry_path is None or metrics.provider_mode != "ollama":
        raise ValueError("Model-backed C3 artifacts require registry provenance")

    expected: dict[str, C3BenchmarkCaseResult] = {}
    for result in results:
        provenance = result.provenance
        if (
            provenance.model_id != candidate.model_id
            or provenance.model_digest != candidate.model_digest
        ):
            raise ValueError("C3 result model identity differs from candidate")
        if provenance.execution_error_type is not None:
            expected[result.case_id] = result

    failure_case_ids = tuple(failure.case_id for failure in failures)
    if failure_case_ids != tuple(sorted(expected)):
        raise ValueError(
            "C3 failure evidence must exactly cover provider-rejected cases"
        )
    for failure in failures:
        result = expected[failure.case_id]
        provenance = result.provenance
        if (
            failure.run_id != run_id
            or failure.benchmark_id != metrics.benchmark_id
            or failure.packet_id != result.packet_id
            or failure.packet_hash != result.packet_hash
            or failure.provider_payload_sha256 != result.provider_payload_hash
            or failure.call_id != provenance.call_id
            or failure.call_spec_hash != provenance.call_spec_hash
            or failure.provider_id != provenance.provider_id
            or failure.provider_revision
            != provenance.provider_identity.implementation_revision
            or failure.model_id != candidate.model_id
            or failure.model_digest != candidate.model_digest
            or failure.failure_code != provenance.execution_error_type
        ):
            raise ValueError("C3 failure evidence differs from its rejected result")


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
    failures: tuple[C3FailureEvidence, ...] = (),
) -> dict[str, Any]:
    try:
        cold_metrics = C3BenchmarkRunMetrics.model_validate_json(
            canonical_json_bytes(metrics)
        )
    except ValueError as exc:
        raise ValueError("C3 run metrics are invalid") from exc
    recomputed_metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode=metrics.provider_mode,
        results=results,
        model_call_count=metrics.model_call_count,
        baseline_results=baseline_results,
    )
    if cold_metrics != metrics or recomputed_metrics != metrics:
        raise ValueError("C3 run metrics differ from recomputed evidence")
    _validate_failure_closure(
        run_id=run_id,
        metrics=metrics,
        results=results,
        registry_path=registry_path,
        candidate=candidate,
        failures=failures,
    )
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
    failures_path = None
    if candidate is not None:
        failures_path = target / "failures.jsonl"
        failures_path.write_bytes(_failure_jsonl_bytes(failures))

    provenance = C3BenchmarkRunProvenance(
        schema_version="rei-c3-racio-interpreter-run-provenance-v2",
        run_id=run_id,
        source_commit=source_commit,
        created_at=utc_now(),
        provider_mode=metrics.provider_mode,
        benchmark_id=metrics.benchmark_id,
        benchmark_manifest_path=_recorded_path(manifest_path),
        benchmark_manifest_hash=suite.manifest_file_hash,
        public_cases_hash=suite.manifest.files[0].sha256,
        gold_hash=suite.manifest.files[1].sha256,
        model_call_count=metrics.model_call_count,
        results_sha256=_file_hash(results_path),
        metrics_sha256=_file_hash(metrics_path),
        baseline_results_sha256=(
            _file_hash(baseline_path) if baseline_path is not None else None
        ),
        failure_count=len(failures),
        failures_sha256=(
            _file_hash(failures_path) if failures_path is not None else None
        ),
        registry_path=(
            _recorded_path(registry_path) if registry_path is not None else None
        ),
        registry_sha256=(
            _file_hash(registry_path.resolve()) if registry_path is not None else None
        ),
        model_candidate=candidate,
        quality_gate_pass=metrics.quality_gate_pass,
    )
    provenance_path = target / "provenance.json"
    provenance_path.write_bytes(canonical_json_bytes(provenance) + b"\n")
    return {
        "output_dir": str(target),
        "results_sha256": provenance.results_sha256,
        "metrics_sha256": provenance.metrics_sha256,
        "provenance_sha256": _file_hash(provenance_path),
        "quality_gate_pass": metrics.quality_gate_pass,
        "failure_count": len(failures),
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
    registry_snapshot_sha256 = None
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
        registry_path = args.registry
        registry_snapshot_sha256 = _file_hash(registry_path.resolve())
        provider, candidate = _ollama_provider(args)
        failures: list[C3FailureEvidence] = []
        results = execute_provider_suite(
            suite=suite,
            provider_mode="ollama",
            provider=provider,
            clock=SystemExecutionClock(),
            run_id=args.run_id,
            failure_records=failures,
        )
        metrics = evaluate_c3_benchmark_run(
            suite=suite,
            provider_mode="ollama",
            results=results,
            model_call_count=32,
            baseline_results=baseline,
        )
        baseline_artifact = baseline
    verify_scoped_source_unchanged(
        source_commit=source_commit,
        registry_path=registry_path,
        registry_sha256=registry_snapshot_sha256,
    )
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
        failures=(tuple(failures) if args.mode == "ollama" else ()),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if metrics.quality_gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
