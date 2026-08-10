from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
E2R = REPO / "research" / "emocio_vwm_mvp_e2r"
RESULT = E2R / "result"
POST = E2R / "post_execution"
PROTOCOL_SHA = "b01e95ded1a4e990cd29ece4753ea04d41c5c091"
INITIAL_SHA = "94838e369457dc266b75a20839ef272fc4c3e9b53c9acbd5bcbda091d702f94b"


def load(relative: str) -> dict:
    return json.loads((RESULT / relative).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def tree(records: list[dict]) -> str:
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_two_smokes_complete_one_step_with_equal_initialization() -> None:
    first = load("lineage/smoke_1.json")
    second = load("lineage/smoke_2.json")
    comparison = load("lineage/smoke_comparison.json")
    assert first["initial_state_sha256"] == second["initial_state_sha256"] == INITIAL_SHA
    assert first["initial_loss"] == second["initial_loss"] == 1255.0283203125
    assert first["backward_status"] == second["backward_status"] == "passed"
    assert first["optimizer_step_count"] == second["optimizer_step_count"] == 1
    assert first["finite_loss"] is second["finite_loss"] is True
    assert math.isfinite(first["gradient_norm"]) and math.isfinite(second["gradient_norm"])
    assert first["post_step_state_sha256"] != second["post_step_state_sha256"]
    assert comparison["initial_state_hashes_equal"] is True
    assert comparison["post_step_byte_identity_required"] is False
    assert comparison["used_for_selection"] is False
    assert comparison["numeric_difference"]["post_step_state_l2"] > 0


def test_expected_warn_only_grid_sample_warning_is_captured() -> None:
    for relative in ("lineage/smoke_1.json", "lineage/smoke_2.json"):
        warnings = load(relative)["captured_warnings"]
        assert len(warnings) == 1
        assert warnings[0]["count"] == 3
        assert "grid_sampler_2d_backward_cuda" in warnings[0]["message"]
        assert "warn_only=True" in warnings[0]["message"]
    policy = load("lineage/determinism_policy.json")
    assert policy["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
    assert policy["torch_deterministic_algorithms"] is True
    assert policy["warn_only"] is True
    assert policy["cudnn_benchmark"] is False
    assert policy["cudnn_deterministic"] is True
    assert policy["bitwise_model_optimization_reproducibility_claimed"] is False


def test_measured_run_completes_exact_frozen_budget() -> None:
    training = load("lineage/measured_training.json")
    assert training["status"] == "completed"
    assert training["optimizer_steps_required"] == training["optimizer_steps_completed"] == 1200
    assert training["seed"] == 73013
    assert training["precision"] == "float32"
    assert training["initial_state_sha256"] == INITIAL_SHA
    assert len(training["measurements"]) == len(training["checkpoints"]) == 12
    assert [record["step"] for record in training["checkpoints"]] == list(range(100, 1201, 100))
    assert training["best_step"] == 1200
    assert training["best_checkpoint"]["sha256"] == training["final_checkpoint"]["sha256"]
    assert training["peak_allocated_vram_bytes"] > 0
    assert training["peak_reserved_vram_bytes"] >= training["peak_allocated_vram_bytes"]


def test_completed_budget_verdict_is_model_fit_failed() -> None:
    verdict = load("verdict.json")
    metrics = load("metrics/selected_visual_metrics.json")["metrics"]
    assert verdict["verdict"] == "model_fit_failed"
    assert verdict["claim_scope"] == "technical_overfit_only"
    assert verdict["full_frozen_budget_completed"] is True
    assert verdict["social_model_fit_started"] is False
    assert verdict["working_emocio_claimed"] is False
    assert verdict["hard_gates"] == {
        "all_passed": False,
        "checks": {
            "duplicate_person_rate": False,
            "foreground_lpips": True,
            "goal_marker_accuracy": False,
            "identity_stability": False,
            "person_count_accuracy": False,
        },
    }
    assert metrics == {
        "duplicate_person_rate": 2.1318407960199006,
        "foreground_lpips": 0.15281087777542848,
        "goal_marker_accuracy": 0.3333333333333333,
        "identity_stability": 0.8899253731343284,
        "person_count_accuracy": 0.30092592592592593,
    }


def test_particle_diagnostics_expose_collapse_without_invented_gate() -> None:
    diagnostics = load("metrics/particle_diagnostics.json")
    assert diagnostics["numeric_acceptance_thresholds"] is None
    assert set(diagnostics["routes"]) == {"public_reclaim", "private_evidence", "no_response"}
    for route in diagnostics["routes"].values():
        assert route["active_particle_count_mean"] == 0.0
        assert route["particle_objectness_mean"] < 0.003
        assert route["particle_objectness_std"] < 0.001
        assert route["particle_position_coverage"] > 0
        assert route["particle_temporal_displacement"] > 0
        assert route["latent_context_variance"] > 0


def test_samples_diagnostics_and_blind_material_are_complete() -> None:
    assert len(list((RESULT / "samples" / "selected").glob("*/*.png"))) == 288
    assert len(list((RESULT / "samples").rglob("*.mp4"))) == 39
    assert len(list((RESULT / "blind_review" / "clips").glob("*.mp4"))) == 12
    for name in (
        "selected_key_mosaic.png", "selected_terminal_mosaic.png", "stochastic_terminal_mosaic.png",
        "goal_sensitivity_mosaic.png", "image_goal_terminal_mosaic.png", "particle_mosaic.png",
        "mask_mosaic.png", "reconstruction_mosaic.png",
    ):
        assert (RESULT / "contact_sheets" / name).is_file()
    for kind in ("particles", "masks", "reconstruction"):
        assert len(list((RESULT / "diagnostics" / kind).glob("*/*.png"))) == 72
    boundary = load("metrics/generated_media_boundary_audit.json")
    assert boundary == {
        "schema_version": "rei-emocio-vwm-e2r-generated-media-boundary-v1",
        "status": "passed",
        "png_files_checked": 288,
        "mp4_files_checked": 39,
        "ffprobe_stream_and_metadata_validation": "passed",
    }


def test_post_budget_packaging_failure_is_preserved_not_hidden() -> None:
    correction = load("lineage/packaging_correction.json")
    archived_failure = json.loads((POST / "bundle_attempt_1_failure" / "failure.json").read_text(encoding="utf-8"))
    archived_verdict = json.loads((POST / "bundle_attempt_1_failure" / "verdict.json").read_text(encoding="utf-8"))
    assert archived_failure["stage"] == "bundle"
    assert archived_failure["exception_type"] == "KeyError"
    assert archived_failure["message"] == "'lpwm_smoke'"
    assert archived_verdict["verdict"] == "not_executed_resource_block"
    assert correction["classification"] == "post_budget_packaging_defect_not_model_execution_failure"
    assert correction["measured_run_reexecuted"] is False
    assert correction["optimizer_steps_added"] == 0
    assert correction["samples_regenerated"] is False
    assert correction["hard_gates_recomputed"] is False
    assert correction["verdict_changed_by_correction"] is False


def test_protocol_environment_and_dataset_lineage_are_exact() -> None:
    preflight = load("lineage/preflight.json")
    assert preflight["protocol_commit_sha"] == PROTOCOL_SHA
    assert preflight["dataset"]["dataset_tree_sha256"] == "f84bcb3f93734b99d5ebb62a3c02718b14f713b4265d006635770daf3d1e7991"
    assert digest(RESULT / "lineage" / "environment_manifest.json") == "2f88a3f694eed8c7af84959e0a53db09a41d10614bcf423b8a100186497dcfc2"
    diagnostic = load("lineage/diagnostic_postprocess.json")
    training = load("lineage/measured_training.json")
    assert diagnostic["optimizer_steps"] == 0
    assert diagnostic["sample_selection"] is False
    assert diagnostic["hard_gate_evaluation"] is False
    assert diagnostic["loaded_state_sha256"] == training["final_state_sha256"]


def test_result_tree_comparison_and_manifest_are_byte_exact() -> None:
    comparison = load("artifact_tree_determinism.json")
    assert comparison["status"] == "passed"
    assert comparison["runs"] == 2
    assert comparison["byte_identical"] is True
    assert comparison["tree_sha256_a"] == comparison["tree_sha256_b"] == tree(comparison["files"])
    for record in comparison["files"]:
        path = RESULT / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert digest(path) == record["sha256"]
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
