"""Validate and freeze an externally stored E2 visual-only dataset tree."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
E2_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e2"
sys.path.insert(0, str(E2_ROOT / "python"))

from emocio_vwm_mvp_e2.boundary import validate_mp4, validate_png  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def artifact_tree(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def tree_hash(entries: list[dict[str, Any]]) -> str:
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate(root: Path) -> dict[str, Any]:
    if REPO_ROOT.resolve() == root or REPO_ROOT.resolve() in root.parents:
        raise ValueError("dataset root must be outside the rei-v3 repository")
    manifest = json.loads((root / "dataset_manifest.json").read_text(encoding="utf-8"))
    if manifest["source_e1r_sha"] != "01aa8d3e10c04275e528fd45796d0c4c5bb4ac0b":
        raise ValueError("unexpected E1R source SHA")
    if manifest["episode_count"] != 12 or len(manifest["episodes"]) != 12:
        raise ValueError("E2 requires exactly 12 episodes")
    if manifest["routes_evaluator_only"] != {
        "public_pending": 4,
        "private_pending": 4,
        "no_response_hold": 4,
    }:
        raise ValueError("route balance differs from the frozen 4x3 plan")

    visible_files = sorted(path for path in (root / "model_visible").rglob("*") if path.is_file())
    if len(visible_files) != 12 * 25:
        raise ValueError("model-visible tree must contain 24 PNGs and one MP4 per episode")
    opaque = re.compile(r"^model_visible/[0-9a-f]{24}/[0-9]{6}\.(?:png|mp4)$")
    for path in visible_files:
        relative = path.relative_to(root).as_posix()
        if not opaque.fullmatch(relative):
            raise ValueError(f"non-opaque model-visible path: {relative}")

    route_counts: dict[str, int] = {}
    for episode in manifest["episodes"]:
        frames = episode["frame_paths"]
        if len(frames) != 24 or [item["index"] for item in frames] != list(range(24)):
            raise ValueError("episode frame sequence is not exactly 0..23")
        if episode["observation_prefix_indices"] != [0, 5] or episode["future_indices"] != [6, 23]:
            raise ValueError("conditioning/future split differs from the E2 contract")
        terminal = frames[-1]
        goal = episode["image_goal"]
        if goal["frame_index"] != 23 or goal["path"] != terminal["path"] or goal["sha256"] != terminal["sha256"]:
            raise ValueError("image goal must be the exact terminal frame of the same trajectory")
        for record in frames:
            frame = root / record["path"]
            if frame.stat().st_size != record["bytes"] or sha256(frame) != record["sha256"]:
                raise ValueError(f"frame checksum mismatch: {record['path']}")
            validate_png(frame, width=128, height=128)
        video_record = episode["video"]
        video = root / video_record["path"]
        if video.stat().st_size != video_record["bytes"] or sha256(video) != video_record["sha256"]:
            raise ValueError(f"video checksum mismatch: {video_record['path']}")
        validate_mp4(video, width=128, height=128, fps=6, frame_count=24)
        evaluator = json.loads((root / episode["evaluator_only"]["record"]).read_text(encoding="utf-8"))
        if not evaluator["evaluator_only"] or len(evaluator["states"]) != 24:
            raise ValueError("invalid evaluator-only episode record")
        route = evaluator["route"]
        route_counts[route] = route_counts.get(route, 0) + 1
        if any(state["state"].get("source_event_reality_authority") for state in evaluator["states"][6:]):
            raise ValueError("authored counterfactual frame has source-event reality authority")

    if route_counts != {"public_reclaim": 4, "private_evidence": 4, "no_response": 4}:
        raise ValueError(f"unexpected evaluator route counts: {route_counts}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", required=True)
    args = parser.parse_args()
    root = Path(args.dataset_root).resolve()
    manifest = validate(root)
    entries = artifact_tree(root)
    root_hash = tree_hash(entries)
    output = E2_ROOT / "dataset"
    write_json(output / "dataset_checksums.json", {
        "schema_version": "rei-emocio-vwm-e2-dataset-checksums-v1",
        "algorithm": "sha256",
        "files": entries,
    })
    write_json(output / "frozen_dataset_manifest.json", {
        "schema_version": "rei-emocio-vwm-e2-frozen-dataset-v1",
        "freeze_status": "frozen_before_first_lpwm_call",
        "dataset_tree_sha256": root_hash,
        "file_count": len(entries),
        "total_bytes": sum(item["bytes"] for item in entries),
        "environment_relative_root": "datasets/emocio_e2_01aa8d3_v1",
        "source_e1r_sha": manifest["source_e1r_sha"],
        "reproducible_run_id": manifest["reproducible_run_id"],
        "model_visible_root": "model_visible",
        "model_visible_content": "visual_media_only",
        "dataset_manifest_sha256": sha256(root / "dataset_manifest.json"),
        "generator_source_sha256": manifest["generator"]["source_sha256"],
        "browser_executable_sha256": manifest["generator"]["browser_executable_sha256"],
        "three_version": manifest["generator"]["three_version"],
        "playwright_core_version": manifest["generator"]["playwright_core_version"],
        "pre_training_hash_verification_required": True,
        "rerender_after_protocol_freeze_allowed": False,
    })
    write_json(output / "dataset_boundary_audit.json", {
        "schema_version": "rei-emocio-vwm-e2-dataset-boundary-audit-v1",
        "status": "passed",
        "model_visible_file_count": 300,
        "model_visible_media_types": ["image/png", "video/mp4"],
        "model_visible_json_files": 0,
        "opaque_path_pattern": "model_visible/<24-lower-hex>/<6-digits>.(png|mp4)",
        "png_metadata_validation": "passed",
        "mp4_ffprobe_stream_and_metadata_validation": "passed",
        "allowed_model_tensors": ["rgb_observation_prefix", "rgb_image_goal"],
        "forbidden": [
            "scenario_text", "path_name", "role_name", "entity_id", "option_id", "scene_graph",
            "attribution_target_metadata", "evidence_class", "character", "racio_interpretation",
            "human_review", "semantic_filename",
        ],
    })
    print(json.dumps({"dataset_tree_sha256": root_hash, "file_count": len(entries)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
