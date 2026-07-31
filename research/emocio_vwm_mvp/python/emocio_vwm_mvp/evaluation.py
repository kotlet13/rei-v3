"""Model-free exploration metrics and artifact assembly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from PIL import Image, ImageDraw

from .boundary import BoundaryViolation, validate_clean_media_call
from .preflight import inspect_lpwm_environment


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _acceptance_hash(acceptance_path: Path) -> str:
    return hashlib.sha256(acceptance_path.read_bytes()).hexdigest()


def _video_frame_count(path: Path) -> int:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr.strip() or "ffprobe failed")
    return int(completed.stdout.strip())


def _make_contact_sheet(bundle_dir: Path, manifest: dict[str, Any]) -> Path:
    cells: list[tuple[str, Image.Image]] = []
    for episode in manifest["episodes"]:
        frames = episode["grounded_frames"]
        for frame in (frames[0], frames[len(frames) // 2], frames[-1]):
            source = (
                bundle_dir
                / Path(episode["grounded_video"]["path"]).parent
                / "frames"
                / frame["filename"]
            )
            cells.append((f"{episode['episode_id'][-6:]}:{frame['index']:02d}", Image.open(source).convert("RGB")))
    width, height = 128, 152
    columns = 6
    rows = (len(cells) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * height), "#0b1020")
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(cells):
        x = (index % columns) * width
        y = (index // columns) * height
        sheet.paste(image, (x, y))
        draw.text((x + 5, y + 133), label, fill="#dce7ff")
    output = bundle_dir / "contact_sheets"
    output.mkdir(parents=True, exist_ok=True)
    target = output / "grounded_key_mosaic.png"
    sheet.save(target, format="PNG", optimize=False)
    return target


def _human_review_template(bundle_dir: Path, manifest: dict[str, Any]) -> Path:
    rows = "\n".join(
        f"| {index + 1:02d} | sealed |  |  |  |  |"
        for index, _ in enumerate(manifest["episodes"])
    )
    content = f"""# Blind human visual review

Do not open evaluator manifests before completing this sheet. Review only the
sealed visual assets supplied for a future validation run. No natural-language
interpretation is a native Emocio output; comments below are reviewer metadata.

Reviewer: ____________________

UTC start: ____________________

UTC end: ____________________

| Item | Condition | Identity stable (0/1) | Count correct (0/1) | Duplicate (0/1) | Preferred path A-H | Severe artifact (0/1) |
|---|---|---:|---:|---:|---|---:|
{rows}

Certification: I completed the sealed visual pass before viewing evaluator
ground truth or path semantics.

Signature/initials: ____________________
"""
    target = bundle_dir / "human_review.md"
    target.write_text(content, encoding="utf-8")
    return target


def evaluate_exploration_bundle(
    *,
    bundle_dir: Path,
    research_root: Path,
) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    manifest = _json(bundle_dir / "dataset_manifest.json")
    acceptance_path = research_root / "specs" / "acceptance.json"
    acceptance = _json(acceptance_path)
    world = _json(research_root / "specs" / "world_manifest.json")
    dataset_plan = _json(research_root / "specs" / "dataset_plan.json")
    boundary_failures: list[dict[str, str]] = []
    meeting_correct = 0
    meeting_total = 0
    office_correct = 0
    office_total = 0
    duplicate_count = 0
    graph_frames = 0
    for episode in manifest["episodes"]:
        graph_path = bundle_dir / episode["evaluator_path"]
        for line in graph_path.read_text(encoding="utf-8").splitlines():
            state = json.loads(line)
            graph_frames += 1
            duplicate_count += state["duplicate_entity_ids"]
            if state["room_id"] == "meeting_room":
                meeting_total += 1
                meeting_correct += int(
                    state["person_count"]
                    == world["invariants"]["meeting_room_person_count"]
                )
            else:
                office_total += 1
                office_correct += int(
                    state["person_count"]
                    == world["invariants"]["private_office_person_count"]
                )
        call_path = bundle_dir / episode["model_visible_call"]
        try:
            call = validate_clean_media_call(call_path)
            observation = next(
                item for item in call["inputs"] if item["slot"] == "observation"
            )
            if observation["media_type"] == "video/mp4":
                count = _video_frame_count(call_path.parent / observation["path"])
                if count != dataset_plan["conditioning_frames"]:
                    raise BoundaryViolation(
                        "observation video contains frames outside the fixed prefix"
                    )
        except BoundaryViolation as exc:
            boundary_failures.append(
                {"call": episode["model_visible_call"], "error": str(exc)}
            )
    medium = {
        "render_success_rate": len(manifest["episodes"])
        / next(item["episodes"] for item in dataset_plan["splits"] if item["name"] == "exploration_preview"),
        "deterministic_pixel_hash_match_rate": float(
            manifest["deterministic_rerender"]["match"]
        ),
        "meeting_person_count_accuracy": meeting_correct / meeting_total,
        "private_office_person_count_accuracy": (
            office_correct / office_total if office_total else 1.0
        ),
        "duplicate_entity_rate": duplicate_count / graph_frames,
        "visual_only_leakage_failures": len(boundary_failures),
    }
    gate = acceptance["medium_gate"]
    checks = {
        "render_success": medium["render_success_rate"] >= gate["render_success_rate_min"],
        "deterministic_pixels": medium["deterministic_pixel_hash_match_rate"] >= gate["deterministic_pixel_hash_match_rate_min"],
        "meeting_count": medium["meeting_person_count_accuracy"] >= gate["meeting_person_count_accuracy_min"],
        "office_count": medium["private_office_person_count_accuracy"] >= gate["private_office_person_count_accuracy_min"],
        "no_duplicates": medium["duplicate_entity_rate"] <= gate["duplicate_entity_rate_max"],
        "visual_only": medium["visual_only_leakage_failures"] <= gate["visual_only_leakage_failures_max"],
    }
    preflight = inspect_lpwm_environment(research_root / "specs" / "lpwm_pin.json")
    model_tests = {
        name: {"status": "not_executed", "reason": "exploration_phase_and_lpwm_resource_block"}
        for name in (
            "identity_stability",
            "person_count",
            "absence_of_duplication",
            "self_anchor_ablation",
            "stochastic_diversity",
            "image_goal_sensitivity",
            "grounded_imagined_lineage",
            "held_out_generalization",
            "blind_human_review",
        )
    }
    verdict = "medium_failed" if not all(checks.values()) else "not_executed_resource_block"
    contact_sheet = _make_contact_sheet(bundle_dir, manifest)
    human_review = _human_review_template(bundle_dir, manifest)
    lineage = {
        "schema_version": "rei-emocio-vwm-lineage-v1",
        "grounded": {
            "authority": "three_js_evaluator_ground_truth",
            "reality_authority": True,
            "dataset_manifest": "dataset_manifest.json",
        },
        "imagined": {
            "authority": "lpwm_prediction_only",
            "reality_authority": False,
            "may_mutate_grounded": False,
            "artifacts": [],
        },
        "model_call": None,
        "selected_visual_path": None,
        "natural_language_native_output": False,
    }
    metrics = {
        "schema_version": "rei-emocio-vwm-exploration-metrics-v1",
        "acceptance_sha256": _acceptance_hash(acceptance_path),
        "medium": medium,
        "medium_checks": checks,
        "boundary_failures": boundary_failures,
        "model_tests": model_tests,
    }
    verdict_record = {
        "schema_version": "rei-emocio-vwm-verdict-v1",
        "verdict": verdict,
        "phase": "exploration",
        "model": "LPWM",
        "model_commit": preflight["expected_commit"],
        "model_invoked": False,
        "reason": (
            "controlled_medium_failed"
            if verdict == "medium_failed"
            else "LPWM dependencies and explicit local checkpoint are unavailable; validation was not executed"
        ),
        "acceptance_changed_after_call": False,
        "model_substituted": False,
        "review_gate": "stop_for_human_review_before_validation",
    }
    _write_json(bundle_dir / "metrics.json", metrics)
    _write_json(bundle_dir / "lpwm_preflight.json", preflight)
    _write_json(bundle_dir / "lineage.json", lineage)
    _write_json(bundle_dir / "verdict.json", verdict_record)
    _write_json(
        bundle_dir / "bundle_manifest.json",
        {
            "schema_version": "rei-emocio-vwm-research-bundle-v1",
            "phase": "exploration",
            "dataset_manifest": "dataset_manifest.json",
            "world_manifest": "specs/world_manifest.json",
            "model_lineage": "lpwm_preflight.json",
            "call_lineage": "lineage.json",
            "samples": [
                episode["grounded_video"] for episode in manifest["episodes"]
            ],
            "imagined_samples": [],
            "metrics": "metrics.json",
            "contact_sheets": [str(contact_sheet.relative_to(bundle_dir)).replace("\\", "/")],
            "human_review": str(human_review.relative_to(bundle_dir)).replace("\\", "/"),
            "verdict": "verdict.json",
            "checksums": "checksums.json",
        },
    )
    checksum_path = bundle_dir / "checksums.json"
    checksum_entries = [
        {
            "path": str(path.relative_to(bundle_dir)).replace("\\", "/"),
            "sha256": _file_sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(bundle_dir.rglob("*"))
        if path.is_file() and path != checksum_path
    ]
    _write_json(
        checksum_path,
        {
            "schema_version": "rei-emocio-vwm-checksums-v1",
            "algorithm": "sha256",
            "files": checksum_entries,
        },
    )
    return {"verdict": verdict_record, "metrics": metrics, "preflight": preflight}


__all__ = ["evaluate_exploration_bundle"]
