"""Camera-expression measurements computed from rendered RGB pixels."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from PIL import Image


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _mask_points(
    pixels: list[tuple[int, int, int]],
    width: int,
    target: tuple[int, int, int],
    *,
    tolerance: int = 10,
) -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for index, pixel in enumerate(pixels):
        if max(abs(pixel[channel] - target[channel]) for channel in range(3)) <= tolerance:
            points.append((index % width, index // width))
    return points


def _centroid(points: list[tuple[int, int]]) -> tuple[float, float] | None:
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def measure_frame(image_path: Path, state: dict[str, Any]) -> dict[str, Any]:
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    pixels = list(image.getdata())
    identities = []
    for target in state["pixel_identity_targets"]:
        body_points = _mask_points(pixels, width, _rgb(target["body_color"]))
        gaze_points = _mask_points(pixels, width, _rgb(target["gaze_color"]))
        body_center = _centroid(body_points)
        gaze_center = _centroid(gaze_points)
        edge_touch = any(
            x <= 1 or y <= 1 or x >= width - 2 or y >= height - 2
            for x, y in body_points
        )
        offset = None
        if body_center is not None and gaze_center is not None:
            offset = [
                gaze_center[0] - body_center[0],
                gaze_center[1] - body_center[1],
            ]
        identities.append(
            {
                "role": target["role"],
                "appearance_id": target["appearance_id"],
                "body_pixel_count": len(body_points),
                "gaze_pixel_count": len(gaze_points),
                "body_centroid": body_center,
                "gaze_centroid": gaze_center,
                "gaze_offset_from_body": offset,
                "edge_touch": edge_touch,
                "body_detected": len(body_points) >= 4,
                "gaze_detected": len(gaze_points) >= 2,
            }
        )
    centers = [item["body_centroid"] for item in identities if item["body_detected"]]
    separations = [
        math.dist(centers[left], centers[right])
        for left in range(len(centers))
        for right in range(left + 1, len(centers))
    ]
    return {
        "image": image_path.name,
        "evidence_class": state["evidence_class"],
        "camera_variant": state["camera_variant"],
        "expected_identities": len(identities),
        "detected_identities": sum(item["body_detected"] for item in identities),
        "detected_gaze_markers": sum(item["gaze_detected"] for item in identities),
        "edge_touch_count": sum(item["edge_touch"] for item in identities),
        "minimum_identity_separation_px": min(separations) if separations else 128.0,
        "identities": identities,
    }


def measure_bundle(bundle_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    for episode in manifest["episodes"]:
        for class_name in ("observed_grounded", "authored_counterfactual"):
            section = episode[class_name]
            states = [
                json.loads(line)
                for line in (bundle_dir / section["scene_graph"]).read_text(encoding="utf-8").splitlines()
            ]
            state_by_frame = {state["frame"]: state for state in states}
            frames_root = (bundle_dir / section["video"]["path"]).parent / "frames"
            for frame in section["frames"]:
                measurement = measure_frame(
                    frames_root / frame["filename"],
                    state_by_frame[frame["index"]],
                )
                measurement["episode_id"] = episode["episode_id"]
                frames.append(measurement)
        goal_state = json.loads(
            (bundle_dir / episode["authored_goal"]["evaluator_state"]).read_text(encoding="utf-8")
        )
        goal_path = bundle_dir / episode["authored_goal"]["image"]["path"]
        measurement = measure_frame(goal_path, goal_state)
        measurement["episode_id"] = episode["episode_id"]
        frames.append(measurement)
    expected = sum(frame["expected_identities"] for frame in frames)
    detected = sum(frame["detected_identities"] for frame in frames)
    gaze_detected = sum(frame["detected_gaze_markers"] for frame in frames)
    edge_touches = sum(frame["edge_touch_count"] for frame in frames)
    offsets = [
        math.dist((0.0, 0.0), item["gaze_offset_from_body"])
        for frame in frames
        for item in frame["identities"]
        if item["gaze_offset_from_body"] is not None
    ]
    return {
        "schema_version": "rei-emocio-vwm-pixel-camera-metrics-v1",
        "evidence_source": "rendered_rgb_pixels_with_evaluator_color_targets",
        "scene_graph_only": False,
        "frame_count": len(frames),
        "expected_identity_observations": expected,
        "pixel_identity_detection_rate": detected / expected,
        "pixel_gaze_marker_detection_rate": gaze_detected / expected,
        "camera_edge_clipping_rate": edge_touches / expected,
        "camera_min_identity_separation_px": min(frame["minimum_identity_separation_px"] for frame in frames),
        "mean_gaze_marker_offset_px": mean(offsets),
        "frames": frames,
    }


__all__ = ["measure_bundle", "measure_frame"]
