"""Opaque visual-only adapter for the frozen E2 LPWM dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import re
from typing import Iterator


_EPISODE_ID = re.compile(r"^[0-9a-f]{24}$")
_FRAME_NAME = re.compile(r"^[0-9]{6}\.png$")


@dataclass(frozen=True)
class VisualEpisode:
    opaque_id: str
    sequence: object
    observation_prefix: object
    image_goal: object


def opaque_episode_dirs(dataset_root: Path) -> tuple[Path, ...]:
    root = dataset_root / "model_visible"
    if not root.is_dir():
        raise ValueError("missing model-visible media root")
    episodes = tuple(sorted(path for path in root.iterdir() if path.is_dir()))
    if len(episodes) != 12 or any(_EPISODE_ID.fullmatch(path.name) is None for path in episodes):
        raise ValueError("expected exactly twelve opaque episode directories")
    return episodes


def load_episode(episode_dir: Path, *, conditioning_frames: int = 6) -> VisualEpisode:
    """Decode only opaque RGB PNGs; no manifest or evaluator sidecar is read."""
    from PIL import Image
    import numpy as np
    import torch

    if _EPISODE_ID.fullmatch(episode_dir.name) is None:
        raise ValueError("episode directory is not opaque")
    paths = tuple(sorted(path for path in episode_dir.iterdir() if path.suffix.lower() == ".png"))
    if len(paths) != 24 or any(_FRAME_NAME.fullmatch(path.name) is None for path in paths):
        raise ValueError("episode must contain exactly 24 six-digit PNG frames")
    if tuple(path.name for path in paths) != tuple(f"{index:06d}.png" for index in range(24)):
        raise ValueError("frame names are not the exact sequence 000000..000023")
    arrays = []
    for path in paths:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            if rgb.size != (128, 128):
                raise ValueError("E2 frames must be exactly 128x128 RGB")
            arrays.append(np.asarray(rgb, dtype=np.float32).copy() / 255.0)
    sequence = torch.from_numpy(np.stack(arrays)).permute(0, 3, 1, 2).contiguous()
    if not bool(torch.isfinite(sequence).all()) or sequence.min().item() < 0 or sequence.max().item() > 1:
        raise ValueError("decoded RGB tensor is outside [0,1] or non-finite")
    return VisualEpisode(
        opaque_id=episode_dir.name,
        sequence=sequence,
        observation_prefix=sequence[:conditioning_frames].contiguous(),
        image_goal=sequence[-1].contiguous(),
    )


def frozen_training_order(dataset_root: Path, *, seed: int, optimizer_steps: int) -> Iterator[Path]:
    episodes = list(opaque_episode_dirs(dataset_root))
    generator = random.Random(seed)
    yielded = 0
    while yielded < optimizer_steps:
        generator.shuffle(episodes)
        for episode in episodes:
            if yielded >= optimizer_steps:
                return
            yield episode
            yielded += 1


__all__ = ["VisualEpisode", "frozen_training_order", "load_episode", "opaque_episode_dirs"]
