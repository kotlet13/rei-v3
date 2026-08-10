"""E1R protocol checks, pixel metrics, review packet, and bundle closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from PIL import Image, ImageDraw

from .boundary import BoundaryViolation, validate_clean_media_call
from .preflight import inspect_lpwm_execution_gate
from .visual_metrics import measure_bundle


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _states(bundle_dir: Path, relative: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (bundle_dir / relative).read_text(encoding="utf-8").splitlines()
    ]


def _make_review_mosaics(bundle_dir: Path, manifest: dict[str, Any]) -> list[str]:
    labeled_cells: list[tuple[str, Image.Image]] = []
    sealed_cells: list[tuple[str, Image.Image]] = []
    for episode in manifest["episodes"]:
        observed = episode["observed_grounded"]
        counterfactual = episode["authored_counterfactual"]
        observed_frame = observed["frames"][-1]
        counterfactual_frame = counterfactual["frames"][-1]
        observed_path = (bundle_dir / observed["video"]["path"]).parent / "frames" / observed_frame["filename"]
        counterfactual_path = (bundle_dir / counterfactual["video"]["path"]).parent / "frames" / counterfactual_frame["filename"]
        goal_path = bundle_dir / episode["authored_goal"]["image"]["path"]
        short_id = episode["episode_id"][-5:]
        semantic = episode["evaluator_only"]["path_name"]
        path_label = {
            "public_reclaim": "PUBLIC",
            "private_evidence": "PRIVATE",
            "no_response": "NO RESPONSE",
        }[semantic]
        for code, label, image_path in (
            ("O", f"{path_label} · OBSERVED", observed_path),
            ("C", f"{path_label} · {'HOLD' if semantic == 'no_response' else 'PENDING'}", counterfactual_path),
            ("G", f"{path_label} · TARGET", goal_path),
        ):
            image = Image.open(image_path).convert("RGB")
            labeled_cells.append((label, image))
            sealed_cells.append((f"{short_id}:{code}", image.copy()))

    def render(cells: list[tuple[str, Image.Image]], filename: str) -> str:
        cell_width, cell_height = 256, 282
        columns = 9
        rows = (len(cells) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "#0b1020")
        draw = ImageDraw.Draw(sheet)
        for index, (label, image) in enumerate(cells):
            x = (index % columns) * cell_width
            y = (index // columns) * cell_height
            enlarged = image.resize((256, 256), Image.Resampling.NEAREST)
            sheet.paste(enlarged, (x, y))
            draw.text((x + 6, y + 262), label, fill="#dce7ff")
        target = bundle_dir / "contact_sheets" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(target, format="PNG", optimize=False)
        return str(target.relative_to(bundle_dir)).replace("\\", "/")

    return [render(labeled_cells, "review_mosaic.png"), render(sealed_cells, "sealed_mosaic.png")]


def _copy_review_history(research_root: Path, bundle_dir: Path) -> list[dict[str, Any]]:
    source = research_root / "reviews" / "history"
    target = bundle_dir / "review_history"
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    return [
        {
            "path": str(path.relative_to(bundle_dir)).replace("\\", "/"),
            "sha256": file_sha256(path),
        }
        for path in sorted(target.rglob("*"))
        if path.is_file()
    ] if target.is_dir() else []


def _review_record(research_root: Path, bundle_dir: Path, history: list[dict[str, Any]]) -> dict[str, Any]:
    supplied = research_root / "reviews" / "visual_review_attempt_3.json"
    if not supplied.is_file():
        packet = """# E1R independent visual review packet

Status: awaiting an explicitly sourced independent review.

Earlier review attempts, including failures, are preserved under
`review_history/` and do not count as a pass for this mosaic.

Inspect `contact_sheets/review_mosaic.png` and representative videos. Confirm:

- bodies and gaze/attention directions are visibly readable;
- identities remain visually stable inside each episode;
- the no-response continuation retains current official attribution;
- public/private immediate continuations remain pending;
- official self-attribution appears only in non-authoritative goal cells;
- camera framing does not clip or merge people;
- evidence class transitions are visually coherent.

Codex pixel checks are separate automated evidence and are not a substitute for
an independent review. Reviewer type and source must be recorded exactly.
"""
        (bundle_dir / "visual_review.md").write_text(packet, encoding="utf-8")
        return {
            "status": "awaiting_independent_visual_review",
            "review_source": None,
            "reviewer_type": None,
            "passed": False,
            "record": None,
            "human_review_performed": False,
            "history": history,
        }
    record = read_json(supplied)
    required = {
        "schema_version", "review_source", "reviewer_type", "reviewer_id", "reviewed_artifact_sha256",
        "body_orientation_readable", "gaze_attention_readable", "identity_stability",
        "no_response_attribution_retained", "immediate_results_pending",
        "self_official_only_in_non_authoritative_goal", "camera_expression_acceptable",
        "failed_items", "partial_items", "passed_items", "overall", "notes",
    }
    if (
        set(record) != required
        or record["review_source"] != "research_owner_supplied_external_assistant_review"
        or record["reviewer_type"] != "external_ai_assistant"
    ):
        raise ValueError("Independent review record does not match the exact E1R schema")
    mosaic = bundle_dir / "contact_sheets" / "review_mosaic.png"
    if record["reviewed_artifact_sha256"] != file_sha256(mosaic):
        raise ValueError("Independent review cites a different review mosaic")
    booleans = [
        "body_orientation_readable", "gaze_attention_readable", "identity_stability",
        "no_response_attribution_retained", "immediate_results_pending",
        "self_official_only_in_non_authoritative_goal", "camera_expression_acceptable",
    ]
    passed = (
        all(record[key] is True for key in booleans)
        and record["overall"] == "pass"
        and record["failed_items"] == []
        and record["partial_items"] == []
        and record["passed_items"] == [1, 2, 3, 4, 5, 6, 7]
    )
    shutil.copy2(supplied, bundle_dir / "visual_review_attempt_3.json")
    shutil.copy2(
        research_root / "reviews" / "external_ai_gate_approval_2026-08-10.json",
        bundle_dir / "external_ai_gate_approval_2026-08-10.json",
    )
    (bundle_dir / "visual_review.md").write_text(
        "# E1R owner-supplied external-assistant visual review\n\n"
        "This is explicitly not a human review.\n\n"
        f"Review source: `{record['review_source']}`\n\n"
        f"Reviewer type: `{record['reviewer_type']}`\n\n"
        f"Reviewer ID: `{record['reviewer_id']}`\n\n"
        f"Overall: `{record['overall']}`\n\n"
        f"Notes: {record['notes']}\n",
        encoding="utf-8",
    )
    return {
        "status": "complete",
        "review_source": record["review_source"],
        "reviewer_type": record["reviewer_type"],
        "passed": passed,
        "record": "visual_review_attempt_3.json",
        "human_review_performed": False,
        "history": history,
    }


def evaluate_run(*, bundle_dir: Path, research_root: Path) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    manifest = read_json(bundle_dir / "dataset_manifest.json")
    acceptance = read_json(research_root / "specs" / "acceptance.json")
    world = read_json(research_root / "specs" / "world_manifest.json")
    trajectory_failures: list[str] = []
    boundary_failures: list[dict[str, str]] = []
    person_checks = 0
    person_correct = 0
    duplicates = 0
    for episode in manifest["episodes"]:
        observed = _states(bundle_dir, episode["observed_grounded"]["scene_graph"])
        counterfactual = _states(bundle_dir, episode["authored_counterfactual"]["scene_graph"])
        goal = read_json(bundle_dir / episode["authored_goal"]["evaluator_state"])
        path_name = episode["evaluator_only"]["path_name"]
        if any(
            state["evidence_class"] != "observed_grounded"
            or state["source_event_reality_authority"] is not True
            or state["may_update_grounded_state"] is not True
            for state in observed
        ):
            trajectory_failures.append(f"{episode['episode_id']}:observed_authority")
        if any(
            state["evidence_class"] != "authored_counterfactual"
            or state["source_event_reality_authority"] is not False
            or state["may_update_grounded_state"] is not False
            for state in counterfactual
        ):
            trajectory_failures.append(f"{episode['episode_id']}:counterfactual_authority")
        if (
            goal["evidence_class"] != "authored_goal"
            or goal["source_event_reality_authority"] is not False
            or goal["may_update_grounded_state"] is not False
        ):
            trajectory_failures.append(f"{episode['episode_id']}:goal_authority")
        if any(state["official_attribution_target"] != "coworker" for state in counterfactual):
            trajectory_failures.append(f"{episode['episode_id']}:official_changed_in_immediate")
        if any(state["visible_pending_marker_target"] != "self" for state in counterfactual):
            trajectory_failures.append(f"{episode['episode_id']}:immediate_not_pending")
        expected_goal = "coworker" if path_name == "no_response" else "self"
        if goal["official_attribution_target"] != expected_goal:
            trajectory_failures.append(f"{episode['episode_id']}:goal_target")
        for state in (*observed, *counterfactual, goal):
            expected_count = 2 if state["room_id"] == "private_office" else 9
            person_checks += 1
            person_correct += int(state["person_count"] == expected_count)
            duplicates += state["duplicate_role_count"]
        call_path = bundle_dir / episode["model_visible_call"]
        try:
            validate_clean_media_call(call_path)
        except BoundaryViolation as exc:
            boundary_failures.append({"call": episode["model_visible_call"], "error": str(exc)})

    pixel_metrics = measure_bundle(bundle_dir, manifest)
    write_json(bundle_dir / "pixel_camera_metrics.json", pixel_metrics)
    contact_sheets = _make_review_mosaics(bundle_dir, manifest)
    review_history = _copy_review_history(research_root, bundle_dir)
    human_review = _review_record(research_root, bundle_dir, review_history)
    preflight = inspect_lpwm_execution_gate(research_root / "specs")
    write_json(bundle_dir / "lpwm_execution_gate.json", preflight)
    medium = {
        "render_success_rate": len(manifest["episodes"]) / 9,
        "person_count_accuracy": person_correct / person_checks,
        "duplicate_entity_rate": duplicates / person_checks,
        "visual_only_leakage_failures": len(boundary_failures),
        "trajectory_protocol_failures": len(trajectory_failures),
        "pixel_identity_detection_rate": pixel_metrics["pixel_identity_detection_rate"],
        "pixel_gaze_marker_detection_rate": pixel_metrics["pixel_gaze_marker_detection_rate"],
        "camera_edge_clipping_rate": pixel_metrics["camera_edge_clipping_rate"],
        "camera_min_identity_separation_px": pixel_metrics["camera_min_identity_separation_px"],
        "independent_visual_review_passed": human_review["passed"],
        "human_visual_review_performed": human_review["human_review_performed"],
        "two_run_artifact_tree_match": None,
    }
    gate = acceptance["medium_gate"]
    checks = {
        "render_success": medium["render_success_rate"] >= gate["render_success_rate_min"],
        "person_count": medium["person_count_accuracy"] >= gate["person_count_accuracy_min"],
        "no_duplicates": medium["duplicate_entity_rate"] <= gate["duplicate_entity_rate_max"],
        "visual_only_boundary": medium["visual_only_leakage_failures"] <= gate["visual_only_leakage_failures_max"],
        "trajectory_protocol": medium["trajectory_protocol_failures"] == 0,
        "pixel_identity": medium["pixel_identity_detection_rate"] >= gate["pixel_identity_detection_rate_min"],
        "pixel_gaze": medium["pixel_gaze_marker_detection_rate"] >= gate["pixel_gaze_marker_detection_rate_min"],
        "camera_edges": medium["camera_edge_clipping_rate"] <= gate["camera_edge_clipping_rate_max"],
        "camera_separation": medium["camera_min_identity_separation_px"] >= gate["camera_min_identity_separation_px_min"],
        "independent_visual_review": human_review["passed"],
    }
    metrics = {
        "schema_version": "rei-emocio-vwm-e1r-metrics-v1",
        "acceptance_sha256": file_sha256(research_root / "specs" / "acceptance.json"),
        "medium": medium,
        "checks": checks,
        "trajectory_failures": trajectory_failures,
        "boundary_failures": boundary_failures,
        "independent_visual_review": human_review,
        "model_fit_metrics": {"status": "not_assessed", "reason": "no_lpwm_call"},
    }
    write_json(bundle_dir / "metrics.json", metrics)
    lineage = {
        "schema_version": "rei-emocio-vwm-lineage-v2",
        "observed_grounded": {"source_event_reality_authority": True, "may_update_grounded_state": True},
        "authored_counterfactual": {"source_event_reality_authority": False, "may_update_grounded_state": False},
        "authored_goal": {"source_event_reality_authority": False, "may_update_grounded_state": False},
        "imagined_completion": {"source_event_reality_authority": False, "may_update_grounded_state": False, "artifacts": []},
        "model_call": None,
    }
    write_json(bundle_dir / "lineage.json", lineage)
    verdict = {
        "schema_version": "rei-emocio-vwm-e1r-verdict-v1",
        "verdict": "not_executed_resource_block",
        "protocol_status": "awaiting_independent_visual_review" if not human_review["passed"] else "protocol_correction_passed",
        "environment_status": preflight["environment_status"],
        "execution_status": preflight["execution_status"],
        "model_fit_status": preflight["model_fit_status"],
        "model_invoked": False,
        "lpwm_commit": world.get("lpwm_commit", "4cf53c403433e64c01652ac2adbec66231a46dea"),
        "immutable_e1_parent": "a1a8e0922a9fb1fd21893b46087cc0e9155146d9",
        "active_rei_runtime_modified": False,
    }
    write_json(bundle_dir / "verdict.json", verdict)
    write_json(
        bundle_dir / "bundle_manifest.json",
        {
            "schema_version": "rei-emocio-vwm-e1r-bundle-v1",
            "dataset_manifest": "dataset_manifest.json",
            "lineage": "lineage.json",
            "pixel_camera_metrics": "pixel_camera_metrics.json",
            "lpwm_execution_gate": "lpwm_execution_gate.json",
            "metrics": "metrics.json",
            "contact_sheets": contact_sheets,
            "independent_visual_review": human_review["record"],
            "visual_review_history": review_history,
            "two_run_determinism": None,
            "test_results": None,
            "verdict": "verdict.json",
            "checksums": None,
        },
    )
    return {"metrics": metrics, "verdict": verdict, "preflight": preflight}


def artifact_tree(root: Path, *, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude or set()
    return [
        {
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and str(path.relative_to(root)).replace("\\", "/") not in excluded
    ]


def finalize_bundle(bundle_dir: Path) -> None:
    bundle = read_json(bundle_dir / "bundle_manifest.json")
    bundle["two_run_determinism"] = "two_run_determinism.json"
    test_results = bundle_dir / "test_results.json"
    bundle["test_results"] = "test_results.json" if test_results.is_file() else None
    bundle["checksums"] = "checksums.json"
    write_json(bundle_dir / "bundle_manifest.json", bundle)
    checksum_path = bundle_dir / "checksums.json"
    write_json(
        checksum_path,
        {
            "schema_version": "rei-emocio-vwm-e1r-checksums-v1",
            "algorithm": "sha256",
            "files": artifact_tree(bundle_dir, exclude={"checksums.json"}),
        },
    )


__all__ = [
    "artifact_tree",
    "evaluate_run",
    "file_sha256",
    "finalize_bundle",
    "read_json",
    "write_json",
]
