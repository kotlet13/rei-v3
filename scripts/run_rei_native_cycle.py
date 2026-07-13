"""Run one deterministic native REI cycle from a checked-in JSON request.

This runner uses only the provider-free deterministic R/E/I implementations.
It does not invoke a model, renderer, image generator, LLM, or GPU.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.engine import (  # noqa: E402
    ReiNativeCycleRequest,
    ReiNativeCycleResult,
    ReiNativeEngine,
)
from rei.ids import canonical_json_bytes  # noqa: E402
from rei.providers.native import DeterministicExecutionClock  # noqa: E402


DEFAULT_INPUT = (
    ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="A JSON document matching ReiNativeCycleRequest.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=ROOT / "output" / "runs",
        help="Create-only root for output/runs/{run_id} artifacts.",
    )
    parser.add_argument(
        "--ego-traces-root",
        type=Path,
        default=ROOT / "output" / "ego_traces",
        help="Append-only root for longitudinal Ego traces.",
    )
    return parser.parse_args(argv)


def _load_request(path: Path) -> ReiNativeCycleRequest:
    source = path.expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Native cycle input must be a regular JSON file")
    return ReiNativeCycleRequest.model_validate_json(source.read_bytes())


def _summary(result: ReiNativeCycleResult) -> dict[str, object]:
    # Kept local to the CLI so the engine result remains the single typed API.
    return {
        "schema_version": "rei-native-cycle-summary-v1",
        "run_id": result.request.run_id,
        "ego_id": result.request.ego_id,
        "scene_id": result.request.scene.event_id,
        "profile_id": result.request.character.profile_id,
        "native_bundle_id": result.native_bundle.bundle_id,
        "native_bundle_hash": result.native_bundle.immutable_hash,
        "governance_resolution_id": result.governance.resolution_id,
        "governance_status": result.governance.mandate.status,
        "governance_option_id": result.governance.mandate.option_id,
        "conscious_decision_id": result.conscious_decision.decision_id,
        "conscious_decision_status": result.conscious_decision.decision_status,
        "conscious_option_id": result.conscious_decision.option_id,
        "behavior_resultant_id": result.behavior_resultant.resultant_id,
        "behavior_status": result.behavior_resultant.status,
        "behavior_option_id": result.behavior_resultant.option_id,
        "narrative_id": result.narrative.narrative_id,
        "ego_measure_id": result.ego_measure.measure_id,
        "ego_trace_hash": result.ego_trace.trace_hash,
        "composition_snapshot_id": result.composition_snapshot.snapshot_id,
        "manifest_hash": result.manifest.content_hash(),
        "invariant_report_id": result.invariants.report_id,
        "invariant_report_hash": result.invariants.report_hash,
        "all_invariants_passed": result.invariants.all_passed,
        "stored_artifact_count": len(result.stored_artifacts),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    request = _load_request(args.input)
    engine = ReiNativeEngine.with_file_stores(
        runs_root=args.runs_root,
        ego_traces_root=args.ego_traces_root,
        clock=DeterministicExecutionClock(request.started_at),
    )
    result = engine.run_cycle(request)
    sys.stdout.buffer.write(canonical_json_bytes(_summary(result)))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
