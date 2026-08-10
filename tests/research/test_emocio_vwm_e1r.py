from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e1r"
sys.path.insert(0, str(RESEARCH_ROOT / "python"))

from emocio_vwm_mvp_e1r.boundary import (  # noqa: E402
    BoundaryViolation,
    validate_clean_media_call,
)
from emocio_vwm_mvp_e1r.preflight import inspect_lpwm_execution_gate  # noqa: E402


def _load(name: str) -> dict[str, object]:
    return json.loads((RESEARCH_ROOT / "specs" / name).read_text(encoding="utf-8"))


def _write_call(directory: Path, media: Path) -> Path:
    suffix = media.suffix
    opaque = directory / f"i0{suffix}"
    shutil.copy2(media, opaque)
    payload = {
        "schema_version": "rei-emocio-vwm-clean-media-call-v2",
        "conditioning": "latent_action",
        "inputs": [{
            "slot": "observation",
            "media_type": "video/mp4" if suffix == ".mp4" else "image/png",
            "path": opaque.name,
            "sha256": hashlib.sha256(opaque.read_bytes()).hexdigest(),
        }],
        "sampling": {"samples": 8, "stochastic": True},
    }
    call = directory / "call.json"
    call.write_text(json.dumps(payload), encoding="utf-8")
    return call


def _make_mp4(path: Path, *, title: str | None = None) -> None:
    args = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=128x128:r=6:d=1",
        "-frames:v", "6", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-map_metadata", "-1",
    ]
    if title is not None:
        args.extend(["-metadata", f"title={title}"])
    args.append(str(path))
    subprocess.run(args, check=True, timeout=30)


def test_evidence_classes_have_exact_authority_partition() -> None:
    world = _load("world_manifest.json")
    classes = world["evidence_classes"]
    assert set(classes) == {
        "observed_grounded", "authored_counterfactual", "authored_goal",
        "imagined_completion",
    }
    assert classes["observed_grounded"] == {
        "source_event_reality_authority": True,
        "may_update_grounded_state": True,
    }
    for name in ("authored_counterfactual", "authored_goal", "imagined_completion"):
        assert classes[name] == {
            "source_event_reality_authority": False,
            "may_update_grounded_state": False,
        }


def test_public_credit_immediate_and_goal_semantics_are_corrected() -> None:
    trajectory = _load("world_manifest.json")["trajectory_contract"]
    assert trajectory["no_response"] == {
        "official_attribution_target": "coworker",
        "pending_target": "self",
    }
    for name in ("private_evidence", "public_reclaim"):
        assert trajectory[name]["immediate_result"] == "pending"
        assert trajectory[name]["official_attribution_target"] == "coworker"
        assert trajectory[name]["pending_target"] == "self"
    assert trajectory["authored_goal"] == {
        "official_attribution_target": "self",
        "source_event_reality_authority": False,
    }


def test_orientation_and_camera_metrics_are_pixel_sourced() -> None:
    source = (RESEARCH_ROOT / "python" / "emocio_vwm_mvp_e1r" / "visual_metrics.py").read_text(encoding="utf-8")
    lab = (RESEARCH_ROOT / "lab" / "main.js").read_text(encoding="utf-8")
    assert '"scene_graph_only": False' in source
    assert '"evidence_source": "rendered_rgb_pixels_with_evaluator_color_targets"' in source
    assert "gaze_offset_from_body" in source
    assert "person.lookAt" in lab
    assert "face visor, pupils, and nose" in lab
    assert 'gesture(person, "leader_hold")' in lab


def test_technical_overfit_and_social_identity_plans_are_distinct() -> None:
    plan = _load("appearance_role_plan.json")
    assert plan["frozen"] is True
    assert plan["technical_overfit"]["fixed_identities_allowed"] is True
    social = plan["social_fit"]
    assert social["fixed_role_color_forbidden"] is True
    assert social["held_out_identity_overlap_with_train"] is False
    assert set(social["train_identity_ids"]).isdisjoint(social["held_out_identity_ids"])
    assert len(social["counterbalance_blocks"]) == 9
    assert len(social["held_out_blocks"]) == 9
    assert social["self_reference_source"] == "current_episode_assigned_self_identity"


def test_environment_execution_and_model_fit_statuses_are_not_conflated() -> None:
    acceptance = _load("acceptance.json")
    assert set(acceptance["status_layers"]) == {
        "environment_status", "execution_status", "model_fit_status",
    }
    failure = acceptance["failure_mapping"]
    assert failure["environment_or_execution_failure"] == {
        "model_fit_status": "not_assessed",
        "verdict": "not_executed_resource_block",
    }
    assert failure["completed_technical_gate_failure"]["verdict"] == "model_fit_failed"
    assert failure["completed_social_gate_failure"]["verdict"] == "model_fit_failed"


def test_lpwm_preflight_blocks_before_checkpoint_environment_and_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    pin = _load("lpwm_pin.json")
    for name in (
        pin["required_root_env"], pin["required_checkpoint_env"],
        pin["required_environment_manifest_env"],
    ):
        monkeypatch.delenv(name, raising=False)
    gate = inspect_lpwm_execution_gate(RESEARCH_ROOT / "specs")
    assert gate["environment_status"] == "blocked"
    assert gate["execution_status"] == "not_started"
    assert gate["model_fit_status"] == "not_assessed"
    assert gate["ready_for_first_model_call"] is False
    assert gate["live_cuda_smoke"]["attempted"] is False
    assert gate["automatic_source_download_attempted"] is False
    assert gate["automatic_weight_download_attempted"] is False
    assert gate["environment_install_attempted"] is False


def test_clean_png_boundary_rejects_semantic_call_keys(tmp_path: Path) -> None:
    media = tmp_path / "source.png"
    Image.new("RGB", (128, 128), "black").save(media)
    call = _write_call(tmp_path, media)
    validate_clean_media_call(call)
    payload = json.loads(call.read_text(encoding="utf-8"))
    payload["scene_graph"] = {"role": "self"}
    call.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BoundaryViolation):
        validate_clean_media_call(call)


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg/ffprobe unavailable")
def test_mp4_boundary_checks_stream_shape_and_rejects_semantic_metadata(tmp_path: Path) -> None:
    clean = tmp_path / "clean.mp4"
    _make_mp4(clean)
    validated = validate_clean_media_call(_write_call(tmp_path, clean))
    probe = validated["media_probes"][0]
    assert probe["codec"] == "h264"
    assert probe["frames"] == 6
    assert probe["frame_rate"] == "6/1"
    contaminated_dir = tmp_path / "contaminated"
    contaminated_dir.mkdir()
    contaminated = contaminated_dir / "source.mp4"
    _make_mp4(contaminated, title="public credit self")
    with pytest.raises(BoundaryViolation, match="metadata"):
        validate_clean_media_call(_write_call(contaminated_dir, contaminated))


def test_dataset_plan_freezes_heldout_generalization_and_self_anchor_ablation() -> None:
    plan = _load("dataset_plan.json")
    assert plan["plan_status"] == "frozen_before_first_model_call"
    assert set(plan["arms"]) == {
        "self_anchor_on_goal_off", "self_anchor_off_goal_off",
        "self_anchor_on_goal_match", "self_anchor_on_goal_mismatch",
    }
    assert all(plan["held_out_rules"].values())
    splits = {item["name"]: item for item in plan["splits"]}
    assert splits["technical_overfit"]["identity_plan"] == "overfit_fixed"
    assert splits["held_out"]["identity_plan"] == "held_out_identities"
    assert splits["held_out"]["may_train"] is False


def test_phase_preserves_e1_and_forbids_model_execution() -> None:
    phase = _load("research_phase.json")
    assert phase["immutable_e1_commit"] == "a1a8e0922a9fb1fd21893b46087cc0e9155146d9"
    assert phase["lpwm_call_count"] == 0
    assert phase["lpwm_environment_install_performed"] is False
    assert phase["checkpoint_acquisition_performed"] is False
    assert phase["training_performed"] is False
    assert phase["inference_performed"] is False
    assert phase["active_rei_runtime_modified"] is False
    assert phase["review_gate"] == "owner_approved_independent_visual_review"
    assert phase["review_gate_satisfied_by"] == "research_owner_supplied_external_assistant_review"
    assert phase["human_review_performed"] is False


def test_failed_human_review_is_hash_bound_and_not_promoted_to_active_pass() -> None:
    history = RESEARCH_ROOT / "reviews" / "history" / "human_visual_review_attempt_1.json"
    record = json.loads(history.read_text(encoding="utf-8"))
    assert record["review_source"] == "human_supplied"
    assert record["reviewed_artifact_sha256"] == "a0094963c651ad4cf71d5b4673c66c9930e86a2718fb467c1968eab135367ac8"
    assert record["overall"] == "fail"
    assert record["identity_stability"] is True
    assert record["self_official_only_in_non_authoritative_goal"] is True
    assert record["body_orientation_readable"] is False
    assert record["gaze_attention_readable"] is False
    assert record["camera_expression_acceptable"] is False
    assert not (RESEARCH_ROOT / "reviews" / "human_visual_review.json").exists()


def test_external_ai_review_pass_is_transparent_and_owner_approved() -> None:
    history = RESEARCH_ROOT / "reviews" / "history" / "visual_review_attempt_2.json"
    record = json.loads(history.read_text(encoding="utf-8"))
    assert record["review_source"] == "research_owner_supplied_external_assistant_review"
    assert record["reviewer_type"] == "external_ai_assistant"
    assert record["reviewer_id"] == "GPT-5.6-Pro"
    assert record["reviewed_artifact_sha256"] == "f0e2f5d804653b464683164e02f795a9352dc92cde562a1a236ca596b5284753"
    assert record["failed_items"] == []
    assert record["partial_items"] == []
    assert record["passed_items"] == [1, 2, 3, 4, 5, 6, 7]
    assert record["overall"] == "pass"
    acceptance = _load("acceptance.json")["medium_gate"]
    assert acceptance["accepted_review_source"] == record["review_source"]
    assert acceptance["accepted_reviewer_type"] == record["reviewer_type"]
    assert acceptance["human_review_performed"] is False
    approval = json.loads(
        (RESEARCH_ROOT / "reviews" / "external_ai_gate_approval_2026-08-10.json").read_text(encoding="utf-8")
    )
    assert approval["approved"] is True
    assert approval["human_review_performed"] is False


def test_attempt_3_seals_only_the_new_canonical_mosaic() -> None:
    record = json.loads(
        (RESEARCH_ROOT / "reviews" / "visual_review_attempt_3.json").read_text(encoding="utf-8")
    )
    assert record["review_source"] == "research_owner_supplied_external_assistant_review"
    assert record["reviewer_type"] == "external_ai_assistant"
    assert record["human_review_performed"] is False
    assert record["reviewed_artifact_sha256"] == "6531711a323431fd23ea9cdd9ebca9d25855f9e07f6bc1fdcde0add1a864f9e2"
    assert record["overall"] == "pass"
    assert record["failed_items"] == []
    assert record["partial_items"] == []
    assert record["passed_items"] == [1, 2, 3, 4, 5, 6, 7]
    seal_source = (REPO_ROOT / "scripts" / "seal_emocio_vwm_e1r_review.py").read_text(encoding="utf-8")
    assert '"rerender_performed": False' in seal_source
    assert 'raise RuntimeError("visual media changed during review seal")' in seal_source
