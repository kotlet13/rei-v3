"""Finalize E2R execution and exact d1415007 pytest-regression evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
E2_RESULT_SHA = "d1415007b97e651e59953bbdf093d64516603365"
E2R_PROTOCOL_SHA = "b01e95ded1a4e990cd29ece4753ea04d41c5c091"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def node_id(case: ET.Element) -> str:
    return f"{case.attrib['classname'].replace('.', '/')}.py::{case.attrib['name']}"


def read_junit(path: Path) -> dict[str, object]:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    failures = sorted(
        node_id(case) for case in cases
        if case.find("failure") is not None or case.find("error") is not None
    )
    skipped = sum(case.find("skipped") is not None for case in cases)
    return {
        "tests": len(cases),
        "passed": len(cases) - len(failures) - skipped,
        "failed": len(failures),
        "skipped": skipped,
        "junit_bytes": path.stat().st_size,
        "junit_sha256": sha256(path),
        "failure_node_ids": failures,
        "failure_node_set_sha256": hashlib.sha256(
            json.dumps(failures, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=float, required=True)
    args = parser.parse_args()
    baseline = read_junit(args.baseline.resolve())
    candidate = read_junit(args.candidate.resolve())
    baseline_set = set(baseline["failure_node_ids"])
    candidate_set = set(candidate["failure_node_ids"])
    new_failures = sorted(candidate_set - baseline_set)
    resolved_failures = sorted(baseline_set - candidate_set)
    exact = baseline_set == candidate_set
    if not exact:
        raise RuntimeError(f"E2R full suite differs: new={new_failures}, resolved={resolved_failures}")

    output = args.output_root.resolve()
    comparison = {
        "schema_version": "rei-emocio-vwm-e2r-pytest-regression-v1",
        "baseline_commit": E2_RESULT_SHA,
        "candidate": "uncommitted_e2r_result_candidate",
        "command_contract": "python -m pytest -q --tb=short --basetemp=<external> --junitxml=<path>",
        "baseline": baseline,
        "candidate_result": candidate,
        "new_failures": new_failures,
        "resolved_failures": resolved_failures,
        "shared_failures": sorted(baseline_set & candidate_set),
        "exact_failure_set_match": exact,
        "e2r_introduced_new_failure": bool(new_failures),
    }
    write_json(output / "pytest_regression_comparison.json", comparison)
    write_json(output / "pytest_summary.json", {
        "schema_version": "rei-emocio-vwm-e2r-pytest-summary-v1",
        "targeted_suite": {
            "command": "python -m pytest <E2R targeted + E2/E1R regression> -q --tb=short --basetemp=<external>",
            "passed": 57,
            "failed": 0,
            "errors": 0,
        },
        "discarded_targeted_attempts": [{
            "passed": 55,
            "errors": 2,
            "reason": "default Windows pytest temp root denied access",
            "valid_regression_result": False,
        }],
        "full_suite": {
            "command": "python -m pytest -q --tb=short --basetemp=<external> --junitxml=research/emocio_vwm_mvp_e2r/post_execution/full_pytest_final.xml",
            "duration_seconds": args.duration_seconds,
            "passed": candidate["passed"],
            "failed": candidate["failed"],
            "skipped": candidate["skipped"],
            "errors": 0,
            "junit_bytes": candidate["junit_bytes"],
            "junit_sha256": candidate["junit_sha256"],
            "failure_node_set_sha256": candidate["failure_node_set_sha256"],
        },
        "d1415007_baseline": {
            "passed": baseline["passed"],
            "failed": baseline["failed"],
            "skipped": baseline["skipped"],
            "junit_sha256": baseline["junit_sha256"],
            "failure_node_set_sha256": baseline["failure_node_set_sha256"],
        },
        "regression_comparison": {
            "exact_d1415007_failure_set_match": exact,
            "new_failures": new_failures,
            "resolved_failures": resolved_failures,
        },
    })

    result = REPO_ROOT / "research" / "emocio_vwm_mvp_e2r" / "result"
    smoke_1 = read_json(result / "lineage" / "smoke_1.json")
    smoke_2 = read_json(result / "lineage" / "smoke_2.json")
    smoke_comparison = read_json(result / "lineage" / "smoke_comparison.json")
    training = read_json(result / "lineage" / "measured_training.json")
    verdict = read_json(result / "verdict.json")
    metrics = read_json(result / "metrics" / "selected_visual_metrics.json")["metrics"]
    particles = read_json(result / "metrics" / "particle_diagnostics.json")
    manifest = read_json(result / "result_bundle_manifest.json")
    write_json(output / "e2r_execution_summary.json", {
        "schema_version": "rei-emocio-vwm-e2r-execution-summary-v1",
        "branch": "codex/emocio-visual-world-model-mvp",
        "e2_frozen_result_sha": E2_RESULT_SHA,
        "e2_frozen_verdict": "not_executed_resource_block",
        "e2r_protocol_sha": E2R_PROTOCOL_SHA,
        "e2r_result_commit_sha": "this_result_commit_not_self_addressed",
        "execution_policy_only_remediation": True,
        "smokes": {
            "initial_state_sha256": [smoke_1["initial_state_sha256"], smoke_2["initial_state_sha256"]],
            "initial_loss": [smoke_1["initial_loss"], smoke_2["initial_loss"]],
            "post_step_state_sha256": [smoke_1["post_step_state_sha256"], smoke_2["post_step_state_sha256"]],
            "numeric_difference": smoke_comparison["numeric_difference"],
            "captured_warnings": [smoke_1["captured_warnings"], smoke_2["captured_warnings"]],
        },
        "measured_run": {
            "optimizer_steps": training["optimizer_steps_completed"],
            "training_duration_seconds": training["training_duration_seconds"],
            "peak_allocated_vram_bytes": training["peak_allocated_vram_bytes"],
            "peak_reserved_vram_bytes": training["peak_reserved_vram_bytes"],
            "best_checkpoint_sha256": training["best_checkpoint"]["sha256"],
            "final_checkpoint_sha256": training["final_checkpoint"]["sha256"],
        },
        "hard_gates": verdict["hard_gates"],
        "metrics": metrics,
        "particle_collapse_diagnostic": {
            "classification": "collapsed_objectness",
            "evidence": particles,
        },
        "post_budget_packaging_failure_preserved": True,
        "packaging_correction_added_optimizer_steps": 0,
        "result_bundle": {
            "file_count_before_manifest": manifest["file_count_before_manifest"],
            "bytes_before_manifest": manifest["bytes_before_manifest"],
            "tree_sha256_before_manifest": manifest["tree_sha256_before_manifest"],
        },
        "contact_sheets": "research/emocio_vwm_mvp_e2r/result/contact_sheets",
        "videos": "research/emocio_vwm_mvp_e2r/result/samples",
        "blind_review": "research/emocio_vwm_mvp_e2r/result/blind_review",
        "active_rei_runtime_changed": False,
        "social_model_fit_started": False,
        "verdict": verdict["verdict"],
    })
    print(json.dumps({
        "baseline": f"{baseline['passed']} passed, {baseline['failed']} failed",
        "candidate": f"{candidate['passed']} passed, {candidate['failed']} failed",
        "exact_failure_set_match": exact,
        "new_failures": new_failures,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
