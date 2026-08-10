from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RESULT = REPO / "research" / "emocio_vwm_mvp_e2" / "result"
POST = REPO / "research" / "emocio_vwm_mvp_e2" / "post_execution"
PROTOCOL_SHA = "e409ecbdebd220db9da934827f2b1e0a7d73b65c"
LPWM_SHA = "4cf53c403433e64c01652ac2adbec66231a46dea"
DATASET_SHA = "f84bcb3f93734b99d5ebb62a3c02718b14f713b4265d006635770daf3d1e7991"


def load(relative: str) -> dict:
    return json.loads((RESULT / relative).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree(records: list[dict]) -> str:
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_result_is_execution_block_not_model_fit_failure() -> None:
    verdict = load("verdict.json")
    failure = load("failure.json")
    assert verdict["verdict"] == "not_executed_resource_block"
    assert verdict["failed_stage"] == "lpwm_smoke"
    assert verdict["model_fit_failure_claimed"] is False
    assert verdict["medium_failure_claimed"] is False
    assert failure["classification"] == "environment_or_execution_failure"
    assert failure["exception_type"] == "RuntimeError"
    assert "grid_sampler_2d_backward_cuda" in failure["message"]
    assert "deterministic implementation" in failure["message"]


def test_preflight_lineage_passed_before_lpwm_construction() -> None:
    preflight = load("partial_lineage/preflight.json")
    assert preflight["status"] == "passed"
    assert preflight["protocol_commit_sha"] == PROTOCOL_SHA
    assert preflight["lpwm"] == {
        "repository_commit_sha": LPWM_SHA,
        "tracked_source_clean": True,
    }
    assert preflight["dataset"]["dataset_tree_sha256"] == DATASET_SHA


def test_exact_environment_and_cuda_blackwell_smoke_passed() -> None:
    environment = load("partial_lineage/environment.json")
    smoke = load("partial_lineage/cuda_smoke.json")
    assert environment["python"].startswith("3.11.15")
    assert environment["torch_version"] == "2.11.0+cu130"
    assert environment["torchvision_version"] == "0.26.0+cu130"
    assert environment["cuda_runtime"] == "13.0"
    assert smoke["status"] == "passed"
    assert smoke["device_name"] == "NVIDIA GeForce RTX 5090"
    assert smoke["device_capability"] == [12, 0]
    assert "sm_120" in smoke["torch_arch_list"]
    assert smoke["tensor"] == smoke["convolution"] == smoke["backward"] == "passed"
    assert smoke["optimizer_step"] == "passed"


def test_failure_bundle_two_run_tree_is_byte_identical() -> None:
    comparison = load("artifact_tree_determinism.json")
    assert comparison["status"] == "passed"
    assert comparison["runs"] == 2
    assert comparison["byte_identical"] is True
    assert comparison["tree_sha256_a"] == comparison["tree_sha256_b"]
    assert comparison["tree_sha256_a"] == tree(comparison["files"])
    for record in comparison["files"]:
        path = RESULT / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert digest(path) == record["sha256"]


def test_result_bundle_manifest_matches_pre_manifest_tree() -> None:
    manifest = load("result_bundle_manifest.json")
    files = [
        path for path in sorted(RESULT.rglob("*"))
        if path.is_file() and path.name != "result_bundle_manifest.json"
    ]
    records = [
        {"path": path.relative_to(RESULT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in files
    ]
    assert manifest["file_count_before_manifest"] == len(records)
    assert manifest["bytes_before_manifest"] == sum(record["bytes"] for record in records)
    assert manifest["tree_sha256_before_manifest"] == tree(records)


def test_no_measured_outputs_or_unearned_claims_exist() -> None:
    assert not (RESULT / "samples").exists()
    assert not (RESULT / "metrics").exists()
    assert not (RESULT / "model_outputs").exists()
    assert not (RESULT / "lineage" / "training_run.json").exists()
    assert "model_fit_promising" not in (RESULT / "verdict.json").read_text(encoding="utf-8")


def test_post_execution_summary_preserves_resource_block_scope() -> None:
    summary = json.loads((POST / "e2_execution_summary.json").read_text(encoding="utf-8"))
    assert summary["verdict"] == "not_executed_resource_block"
    assert summary["lpwm"]["model_fit_test_executed"] is False
    assert summary["lpwm"]["substitution"] is False
    assert summary["execution"]["first_measured_optimizer_step_completed"] is False
    assert summary["execution"]["protocol_rerun_performed"] is False
    assert summary["metric_weights"]["used"] is False
    assert summary["active_rei_runtime_changed"] is False


def test_final_full_suite_evidence_matches_exact_e1r_failure_set() -> None:
    summary = json.loads((POST / "pytest_summary.json").read_text(encoding="utf-8"))
    final = summary["full_suite"]
    junit = POST / "full_pytest_final.xml"
    assert final["passed"] == 2146
    assert final["failed"] == 30
    assert final["errors"] == 0
    assert final["junit_bytes"] == junit.stat().st_size
    assert final["junit_sha256"] == digest(junit)
    assert summary["regression_comparison"] == {
        "exact_e1r_failure_set_match": True,
        "new_failures": [],
        "resolved_failures": [],
    }
