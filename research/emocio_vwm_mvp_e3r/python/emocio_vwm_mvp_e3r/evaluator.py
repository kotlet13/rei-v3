"""Shared, model-free decomposition/overlay/packaging path for E3R evaluation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from .shape_contract import normalize_lpwm_output_shapes


def _array(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().numpy()
    return np.asarray(value)


def _rgb(value: Any) -> np.ndarray:
    x = np.clip(_array(value), 0.0, 1.0)
    return np.rint(x.transpose(1, 2, 0) * 255.0).astype(np.uint8)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evaluate_and_package(
    output: dict[str, Any], batch_size: int, timesteps: int, destination: Path
) -> dict:
    """Exercise the exact target/control adapter path without any model import."""
    normalized, shape_manifest = normalize_lpwm_output_shapes(output, batch_size, timesteps)
    alpha = _array(normalized["alpha_masks"])
    if alpha.shape[3] != 1:
        raise ValueError(f"alpha singleton channel is {alpha.shape[3]}, expected 1")
    alpha = alpha[:, :, :, 0, :, :]
    union = alpha.max(axis=2)
    obj = _array(normalized["obj_on"])[..., 0]
    pos = _array(normalized["mu_tot"])
    active = obj > 0.5

    destination.mkdir(parents=True, exist_ok=False)
    _write_json(destination / "tensor_shapes.json", shape_manifest)
    hashes: list[dict] = []
    for b in range(batch_size):
        for t in range(timesteps):
            stem = f"b{b:02d}_t{t:06d}.png"
            images = {
                "full": Image.fromarray(_rgb(normalized["rec_rgb"][b, t])),
                "background": Image.fromarray(_rgb(normalized["bg_rgb"][b, t])),
                "foreground": Image.fromarray(_rgb(normalized["dec_objects"][b, t])),
                "mask_union": Image.fromarray(np.rint(np.clip(union[b, t], 0, 1) * 255).astype(np.uint8)),
            }
            overlay = images["full"].convert("RGB")
            draw = ImageDraw.Draw(overlay)
            height, width = union.shape[-2:]
            for point in pos[b, t][active[b, t]]:
                x = int(round((float(point[0]) + 1.0) * (width - 1) / 2.0))
                y = int(round((float(point[1]) + 1.0) * (height - 1) / 2.0))
                draw.ellipse((x - 2, y - 2, x + 2, y + 2), outline=(255, 0, 200), width=1)
            images["particles"] = overlay
            for kind, image in images.items():
                path = destination / kind / stem
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(path, optimize=False)
                hashes.append({"path": path.relative_to(destination).as_posix(), "sha256": _sha(path)})

    metrics = {
        "active_particle_count_by_frame": active.sum(axis=2).tolist(),
        "active_particle_count_mean": float(active.sum(axis=2).mean()),
        "objectness_min": float(obj.min()),
        "objectness_max": float(obj.max()),
        "objectness_mean": float(obj.mean()),
        "mask_union_mean": float(union.mean()),
        "mask_union_max": float(union.max()),
        "reconstruction_std": float(_array(normalized["rec_rgb"]).std()),
    }
    verdict = {
        "adapter_complete": True,
        "verdict": "fixture_passed" if hashes else "not_executed_resource_block",
        "not_a_model_fit_claim": True,
    }
    _write_json(destination / "metrics.json", metrics)
    _write_json(destination / "verdict.json", verdict)
    hashes.extend(
        {"path": name, "sha256": _sha(destination / name)}
        for name in ("tensor_shapes.json", "metrics.json", "verdict.json")
    )
    manifest = {"files": sorted(hashes, key=lambda x: x["path"]), "metrics": metrics, "verdict": verdict}
    _write_json(destination / "artifact_manifest.json", manifest)
    return manifest
