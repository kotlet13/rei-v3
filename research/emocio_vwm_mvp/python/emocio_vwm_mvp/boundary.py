"""Fail-closed validation for the LPWM-facing clean-media staging surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
from typing import Any


class BoundaryViolation(ValueError):
    """Raised when semantic or non-media data reaches the LPWM call surface."""


_TOP_LEVEL_KEYS = frozenset(
    {"schema_version", "conditioning", "inputs", "sampling"}
)
_INPUT_KEYS = frozenset({"slot", "media_type", "path", "sha256"})
_SAMPLING_KEYS = frozenset({"samples", "stochastic"})
_SLOTS = frozenset({"observation", "self_reference", "goal"})
_MEDIA = frozenset({"image/png", "video/mp4"})
_CONDITIONING = frozenset({"latent_action", "latent_action_image_goal"})
_FORBIDDEN_KEYS = frozenset(
    {
        "text",
        "prompt",
        "caption",
        "scenario",
        "scenario_id",
        "role",
        "role_name",
        "entity",
        "entity_id",
        "option",
        "option_id",
        "description",
        "scene_graph",
        "character",
        "personality",
        "semantic_label",
        "target_path",
        "attribution_target",
    }
)


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).casefold())
            keys.update(_walk_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_walk_keys(nested))
    return keys


def _validate_png_chunks(path: Path) -> None:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BoundaryViolation(f"not a PNG: {path.name}")
    offset = 8
    forbidden = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        if kind in forbidden:
            raise BoundaryViolation(
                f"PNG metadata chunk {kind.decode('ascii')} is forbidden"
            )
        offset += 12 + length
        if kind == b"IEND":
            return
    raise BoundaryViolation(f"malformed PNG: {path.name}")


def _validate_mp4_container(path: Path) -> None:
    prefix = path.read_bytes()[:64]
    if len(prefix) < 12 or prefix[4:8] != b"ftyp":
        raise BoundaryViolation(f"not an MP4 container: {path.name}")


def validate_clean_media_call(call_path: Path) -> dict[str, Any]:
    """Validate exact keys, opaque paths, bytes, hashes, and media-only inputs."""

    call_path = call_path.resolve()
    payload = json.loads(call_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BoundaryViolation("call must be a JSON object")
    if set(payload) != _TOP_LEVEL_KEYS:
        raise BoundaryViolation("call top-level keys differ from the allowlist")
    leaked = _walk_keys(payload) & _FORBIDDEN_KEYS
    if leaked:
        raise BoundaryViolation(f"forbidden semantic keys: {sorted(leaked)}")
    if payload["schema_version"] != "rei-emocio-vwm-clean-media-call-v1":
        raise BoundaryViolation("unknown call schema")
    if payload["conditioning"] not in _CONDITIONING:
        raise BoundaryViolation("language or unsupported conditioning requested")
    sampling = payload["sampling"]
    if not isinstance(sampling, dict) or set(sampling) != _SAMPLING_KEYS:
        raise BoundaryViolation("sampling keys differ from the allowlist")
    if type(sampling["samples"]) is not int or sampling["samples"] < 1:
        raise BoundaryViolation("samples must be a positive integer")
    if type(sampling["stochastic"]) is not bool:
        raise BoundaryViolation("stochastic must be boolean")
    inputs = payload["inputs"]
    if not isinstance(inputs, list) or not inputs:
        raise BoundaryViolation("at least one clean media input is required")
    slots: list[str] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, dict) or set(item) != _INPUT_KEYS:
            raise BoundaryViolation("input keys differ from the allowlist")
        if item["slot"] not in _SLOTS:
            raise BoundaryViolation("unsupported input slot")
        if item["media_type"] not in _MEDIA:
            raise BoundaryViolation("only PNG images and MP4 videos are allowed")
        relative = PurePosixPath(item["path"])
        expected_name = f"i{index}{'.png' if item['media_type'] == 'image/png' else '.mp4'}"
        if relative.is_absolute() or len(relative.parts) != 1 or relative.name != expected_name:
            raise BoundaryViolation("model-visible filenames must be canonical and opaque")
        asset = call_path.parent / relative.name
        if not asset.is_file():
            raise BoundaryViolation(f"missing media input {relative.name}")
        if _digest(asset) != item["sha256"]:
            raise BoundaryViolation(f"hash mismatch for {relative.name}")
        if item["media_type"] == "image/png":
            _validate_png_chunks(asset)
        else:
            _validate_mp4_container(asset)
        slots.append(item["slot"])
    if len(slots) != len(set(slots)) or slots[0] != "observation":
        raise BoundaryViolation("input slots must be unique and observation-first")
    if payload["conditioning"] == "latent_action_image_goal" and "goal" not in slots:
        raise BoundaryViolation("image-goal conditioning requires a goal image")
    return payload


__all__ = ["BoundaryViolation", "validate_clean_media_call"]
