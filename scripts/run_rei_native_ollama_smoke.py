"""Run one native REI cycle with Ollama-backed Racio only.

Emocio and Instinkt remain deterministic native processors.  This explicit
smoke runner is separate from the model-free deterministic cycle and 12 x 13
governance matrix runners.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.engine import ReiNativeCycleRequest, ReiNativeEngine  # noqa: E402
from rei.ids import canonical_json_bytes, utc_now  # noqa: E402
from rei.persistence import FileArtifactStore  # noqa: E402
from rei.ego.trace_store import FileEgoTraceStore  # noqa: E402
from rei.providers.native import SystemExecutionClock  # noqa: E402
from rei.providers.ollama import (  # noqa: E402
    DEFAULT_OLLAMA_BASE_URL,
    OllamaApiClient,
    OllamaRacioNativeProvider,
    OllamaRacioResponseEvidence,
    OllamaRacioSettings,
    build_ollama_racio_native_providers,
)


DEFAULT_INPUT = (
    ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")
    return f"b14-ollama-racio-smoke-{stamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    environment = OllamaRacioSettings.from_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=ROOT / "output" / "runs",
    )
    parser.add_argument(
        "--ego-traces-root",
        type=Path,
        default=ROOT / "output" / "ego_traces",
    )
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--run-id", default=_default_run_id())
    parser.add_argument("--ego-id")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("REI_OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
    )
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--model", default=environment.model)
    parser.add_argument("--expected-model-digest")
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
        help="Fail unless Ollama reports the complete active model in VRAM.",
    )
    return parser.parse_args(argv)


def _load_request(path: Path) -> ReiNativeCycleRequest:
    source = path.expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Native cycle input must be a regular JSON file")
    return ReiNativeCycleRequest.model_validate_json(source.read_bytes())


def _source_commit() -> str:
    runtime_paths = (
        "app/backend/rei",
        "scripts/run_rei_native_ollama_smoke.py",
    )
    status = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *runtime_paths,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise ValueError(
            "Native runtime sources must be committed before a provenance run"
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
        raise ValueError("Expected a full Git source commit")
    return commit


def _write_exclusive(path: Path, content: bytes) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(content)


def _summary_target(path: Path | None, *, runs_root: Path) -> Path | None:
    if path is None:
        return None
    target = path.expanduser().resolve()
    if target.is_relative_to(runs_root):
        raise ValueError("Summary output must stay outside the manifest-owned runs root")
    if target.exists():
        raise FileExistsError("Summary output already exists")
    return target


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runs_root = args.runs_root.expanduser().resolve()
    ego_traces_root = args.ego_traces_root.expanduser().resolve()
    summary_target = _summary_target(args.summary_output, runs_root=runs_root)
    settings = OllamaRacioSettings(
        model=args.model,
        seed=args.seed,
        temperature=args.temperature,
        num_ctx=args.num_ctx,
        num_gpu=args.num_gpu,
        num_predict=args.num_predict,
        timeout_seconds=args.timeout_seconds,
        keep_alive=args.keep_alive,
        require_full_gpu=args.require_full_gpu,
    )
    client = OllamaApiClient(
        base_url=args.base_url,
        allow_remote=args.allow_remote,
    )
    provider = OllamaRacioNativeProvider.discover(
        client=client,
        settings=settings,
        expected_digest=args.expected_model_digest,
    )
    request_value = _load_request(args.input)
    run_id = args.run_id
    ego_id = args.ego_id or f"{run_id}-ego"
    request_payload = request_value.model_dump(mode="python", round_trip=True)
    request_payload.update(
        {
            "run_id": run_id,
            "ego_id": ego_id,
            "source_commit": _source_commit(),
            "started_at": utc_now(),
        }
    )
    cycle_request = ReiNativeCycleRequest.model_validate(request_payload)
    artifact_store = FileArtifactStore(runs_root)
    engine = ReiNativeEngine(
        artifact_store=artifact_store,
        ego_trace_store=FileEgoTraceStore(ego_traces_root),
        providers=build_ollama_racio_native_providers(provider),
        clock=SystemExecutionClock(),
    )
    result = engine.run_cycle(cycle_request)
    verified_manifest = FileArtifactStore(runs_root).verify_run(run_id)
    if verified_manifest != result.manifest:
        raise ValueError("Cold run verification returned a different manifest")
    evidence = result.racio_execution.reasoning_artifact
    if not isinstance(evidence, OllamaRacioResponseEvidence):
        raise ValueError("Ollama smoke result is missing typed Racio response evidence")
    placement = {
        "model": evidence.model,
        "digest": evidence.model_revision,
        "context_length": evidence.active_context_length,
        "size_bytes": evidence.active_size_bytes,
        "size_vram_bytes": evidence.active_size_vram_bytes,
        "gpu_percent_rounded": evidence.active_gpu_percent_rounded,
        "full_gpu_by_api_sizes": evidence.active_gpu_percent_rounded == 100,
    }
    summary = {
        "schema_version": "rei-native-ollama-smoke-summary-v1",
        "run_id": run_id,
        "ego_id": ego_id,
        "source_commit": cycle_request.source_commit,
        "runtime_sources_committed": True,
        "ollama_server_version": provider.runtime.server_version,
        "model": provider.runtime.model,
        "model_digest": provider.runtime.digest,
        "quantization_level": provider.runtime.quantization_level,
        "model_context_length": provider.runtime.context_length,
        "seed": settings.seed,
        "num_ctx": settings.num_ctx,
        "num_gpu": settings.num_gpu,
        "num_predict": settings.num_predict,
        "temperature": settings.temperature,
        "provider_id": provider.identity.provider_id,
        "provider_call_id": result.racio_execution.call_spec.call_id,
        "reasoning_result_id": evidence.result_id,
        "reasoning_result_hash": evidence.content_hash(),
        "racio_conclusion_id": result.racio_execution.conclusion.conclusion_id,
        "racio_option_id": result.racio_execution.conclusion.option_id,
        "native_bundle_id": result.native_bundle.bundle_id,
        "native_bundle_hash": result.native_bundle.immutable_hash,
        "manifest_hash": result.manifest.content_hash(),
        "invariant_report_hash": result.invariants.report_hash,
        "all_invariants_passed": result.invariants.all_passed,
        "stored_artifact_count": len(result.stored_artifacts),
        "cold_manifest_verification": True,
        "model_backed_minds": [
            mind
            for mind, identity in zip(
                ("R", "E", "I"),
                result.manifest.providers[:3],
                strict=True,
            )
            if identity.uses_model
        ],
        "placement": placement,
    }
    encoded = canonical_json_bytes(summary)
    if summary_target is not None:
        _write_exclusive(summary_target, encoded)
    sys.stdout.buffer.write(encoded + b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
