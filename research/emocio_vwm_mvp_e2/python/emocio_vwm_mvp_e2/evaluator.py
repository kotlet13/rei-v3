"""Evaluator-only visual metrics for frozen E2 model generations."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any


MARKERS = {
    "evidence_card": (196, 85, 78),
    "official_attribution": (72, 209, 122),
    "pending": (240, 171, 69),
}


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]


def _mask(image: object, color: tuple[int, int, int], tolerance: int) -> object:
    import numpy as np

    target = np.asarray(color, dtype=np.int16)
    return np.max(np.abs(image.astype(np.int16) - target), axis=-1) <= tolerance


def _components(mask: object, *, dilation_radius: int, minimum_area: int) -> int:
    import numpy as np
    from skimage.measure import label
    from skimage.morphology import binary_dilation, disk

    expanded = binary_dilation(mask, disk(dilation_radius))
    labels = label(expanded, connectivity=2)
    return sum(int(np.count_nonzero(labels == index)) >= minimum_area for index in range(1, labels.max() + 1))


def _read_rgb(path: Path) -> object:
    import numpy as np
    from PIL import Image

    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _foreground_mask(gold: object, state: dict[str, Any]) -> object:
    import numpy as np
    from skimage.morphology import binary_dilation, disk

    combined = np.zeros(gold.shape[:2], dtype=bool)
    colors = [
        _rgb(target[key])
        for target in state["pixel_identity_targets"]
        for key in ("body_color", "gaze_color")
    ] + list(MARKERS.values())
    for color in colors:
        combined |= _mask(gold, color, 18)
    return binary_dilation(combined, disk(3))


def _lpips(predicted: object, gold: object, mask: object, metric: object, device: object) -> float:
    import numpy as np
    import torch

    masked_pred = np.where(mask[..., None], predicted, 0).astype(np.float32) / 255.0
    masked_gold = np.where(mask[..., None], gold, 0).astype(np.float32) / 255.0
    pred_tensor = torch.from_numpy(masked_pred).permute(2, 0, 1).unsqueeze(0).to(device)
    gold_tensor = torch.from_numpy(masked_gold).permute(2, 0, 1).unsqueeze(0).to(device)
    return float(metric(pred_tensor, gold_tensor).detach().cpu().item())


def evaluate_samples(dataset_root: Path, sample_root: Path, device: object) -> dict[str, Any]:
    """Read evaluator semantics only here, after RGB model outputs exist."""
    from piqa import LPIPS

    metric = LPIPS(network="alex", reduction="none").to(device).eval()
    expected_observations = detected_observations = duplicate_observations = 0
    count_matches = total_frames = 0
    marker_matches: list[bool] = []
    lpips_values: list[float] = []
    frame_records: list[dict[str, Any]] = []

    for episode_file in sorted((dataset_root / "evaluator" / "episodes").glob("*.json")):
        episode = json.loads(episode_file.read_text(encoding="utf-8"))
        episode_id = episode["episode_id"]
        by_frame = {item["frame"]: item["state"] for item in episode["states"]}
        generated_dir = sample_root / episode_id
        for frame_index in range(6, 24):
            predicted_path = generated_dir / f"{frame_index:06d}.png"
            gold_path = dataset_root / "model_visible" / episode_id / f"{frame_index:06d}.png"
            predicted = _read_rgb(predicted_path)
            gold = _read_rgb(gold_path)
            state = by_frame[frame_index]
            detections = []
            duplicates = 0
            for target in state["pixel_identity_targets"]:
                count = _components(
                    _mask(predicted, _rgb(target["body_color"]), 34),
                    dilation_radius=4,
                    minimum_area=4,
                )
                detections.append(count > 0)
                duplicates += max(0, count - 1)
            expected = state["person_count"]
            detected = sum(detections)
            expected_observations += expected
            detected_observations += detected
            duplicate_observations += duplicates
            count_matches += int(detected == expected)
            total_frames += 1
            value = _lpips(predicted, gold, _foreground_mask(gold, state), metric, device)
            lpips_values.append(value)
            record = {
                "episode_id": episode_id,
                "frame": frame_index,
                "expected_person_count": expected,
                "detected_person_count": detected,
                "duplicate_count": duplicates,
                "foreground_lpips": value,
            }
            if frame_index == 23:
                expected_markers = {
                    "evidence_card": bool(state["evidence_card_visible"]),
                    "official_attribution": state["visible_official_marker_target"] is not None,
                    "pending": state["visible_pending_marker_target"] is not None,
                }
                predicted_markers = {
                    name: int(_mask(predicted, color, 34).sum()) >= 4 for name, color in MARKERS.items()
                }
                marker_match = predicted_markers == expected_markers
                marker_matches.append(marker_match)
                record["expected_markers"] = expected_markers
                record["predicted_markers"] = predicted_markers
                record["marker_match"] = marker_match
            frame_records.append(record)

    metrics = {
        "identity_stability": detected_observations / expected_observations,
        "person_count_accuracy": count_matches / total_frames,
        "duplicate_person_rate": duplicate_observations / expected_observations,
        "foreground_lpips": mean(lpips_values),
        "goal_marker_accuracy": mean(marker_matches),
    }
    return {
        "schema_version": "rei-emocio-vwm-e2-visual-metrics-v1",
        "evaluator_only": True,
        "metric_source": "generated_model_visuals",
        "metrics": metrics,
        "counts": {
            "future_frames": total_frames,
            "expected_person_observations": expected_observations,
            "detected_person_observations": detected_observations,
            "duplicate_person_observations": duplicate_observations,
            "terminal_frames": len(marker_matches),
        },
        "frames": frame_records,
    }


def hard_gate_results(metrics: dict[str, float], acceptance: dict[str, Any]) -> dict[str, Any]:
    gates = acceptance["hard_gates"]
    checks = {
        "identity_stability": metrics["identity_stability"] >= gates["identity_stability_min"],
        "person_count_accuracy": metrics["person_count_accuracy"] >= gates["person_count_accuracy_min"],
        "duplicate_person_rate": metrics["duplicate_person_rate"] <= gates["duplicate_person_rate_max"],
        "foreground_lpips": metrics["foreground_lpips"] <= gates["foreground_lpips_max"],
        "goal_marker_accuracy": metrics["goal_marker_accuracy"] >= gates["goal_marker_accuracy_min"],
    }
    return {"checks": checks, "all_passed": all(checks.values())}


__all__ = ["evaluate_samples", "hard_gate_results"]
