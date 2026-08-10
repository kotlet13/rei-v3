"""Deterministic artifact helpers for the E2 result bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_tree(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(root.rglob("*")) if path.is_file()
    ]


def artifact_tree_hash(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def copy_tree_exact(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, copy_function=shutil.copyfile)


def save_sequence_png(sequence: object, output: Path) -> None:
    import numpy as np
    from PIL import Image

    output.mkdir(parents=True, exist_ok=True)
    array = sequence.detach().float().clamp(0, 1).cpu().permute(0, 2, 3, 1).numpy()
    array = np.rint(array * 255.0).astype(np.uint8)
    for index, frame in enumerate(array):
        Image.fromarray(frame, mode="RGB").save(output / f"{index:06d}.png", optimize=False)


def encode_mp4(frame_root: Path, output: Path, *, fps: int = 6) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-framerate", str(fps),
            "-i", str(frame_root / "%06d.png"), "-frames:v", "24",
            "-an", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-movflags", "+faststart", str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed")


def make_contact_sheet(images: list[Path], output: Path, *, columns: int, label_height: int = 0) -> None:
    from PIL import Image, ImageDraw

    loaded = [Image.open(path).convert("RGB") for path in images]
    if not loaded:
        raise ValueError("contact sheet needs at least one image")
    width, height = loaded[0].size
    rows = (len(loaded) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * (height + label_height)), (11, 16, 32))
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(loaded):
        x = (index % columns) * width
        y = (index // columns) * (height + label_height)
        sheet.paste(frame, (x, y))
        if label_height:
            draw.text((x + 3, y + height + 2), f"{index:02d}", fill=(235, 240, 250))
        frame.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=False)


__all__ = [
    "artifact_tree", "artifact_tree_hash", "copy_tree_exact", "encode_mp4",
    "make_contact_sheet", "save_sequence_png", "sha256", "write_json",
]
