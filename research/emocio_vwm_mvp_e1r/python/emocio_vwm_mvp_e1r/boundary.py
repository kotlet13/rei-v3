"""Fail-closed clean-media boundary with ffprobe container inspection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
from typing import Any


class BoundaryViolation(ValueError):
    """Semantic data or an unexpected media/container property crossed the gate."""


_TOP_LEVEL_KEYS = frozenset({"schema_version", "conditioning", "inputs", "sampling"})
_INPUT_KEYS = frozenset({"slot", "media_type", "path", "sha256"})
_SAMPLING_KEYS = frozenset({"samples", "stochastic"})
_SLOTS = frozenset({"observation", "self_reference", "goal"})
_MEDIA = frozenset({"image/png", "video/mp4"})
_CONDITIONING = frozenset({"latent_action", "latent_action_image_goal"})
_FORBIDDEN_KEYS = frozenset(
    {
        "text", "prompt", "caption", "scenario", "scenario_id", "role",
        "role_name", "entity", "entity_id", "option", "option_id",
        "description", "scene_graph", "character", "personality",
        "semantic_label", "target_path", "attribution_target",
    }
)
_STREAM_TAGS = frozenset({"language", "handler_name", "encoder"})
_FORMAT_TAGS = frozenset({"major_brand", "minor_version", "compatible_brands", "encoder"})


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


def _validate_png(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BoundaryViolation(f"not a PNG: {path.name}")
    offset = 8
    width = height = None
    forbidden = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
    chunks: list[str] = []
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunks.append(kind.decode("ascii", errors="replace"))
        if kind in forbidden:
            raise BoundaryViolation(f"PNG metadata chunk {kind.decode('ascii')} is forbidden")
        if kind == b"IHDR":
            width, height = struct.unpack(">II", data[offset + 8 : offset + 16])
        offset += 12 + length
        if kind == b"IEND":
            if (width, height) != (128, 128):
                raise BoundaryViolation("PNG dimensions must be exactly 128x128")
            return {"kind": "png", "width": width, "height": height, "chunks": chunks}
    raise BoundaryViolation(f"malformed PNG: {path.name}")


def _ffprobe(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error", "-count_frames", "-show_streams",
            "-show_format", "-show_chapters", "-show_programs", "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise BoundaryViolation(completed.stderr.strip() or "ffprobe failed")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BoundaryViolation("ffprobe returned invalid JSON") from exc


def _validate_mp4(path: Path) -> dict[str, Any]:
    prefix = path.read_bytes()[:64]
    if len(prefix) < 12 or prefix[4:8] != b"ftyp":
        raise BoundaryViolation(f"not an MP4 container: {path.name}")
    probe = _ffprobe(path)
    streams = probe.get("streams", [])
    if len(streams) != 1:
        raise BoundaryViolation("MP4 must contain exactly one stream")
    stream = streams[0]
    expected = {
        "codec_type": "video",
        "codec_name": "h264",
        "width": 128,
        "height": 128,
        "pix_fmt": "yuv420p",
        "r_frame_rate": "6/1",
        "avg_frame_rate": "6/1",
        "nb_read_frames": "6",
    }
    for key, value in expected.items():
        if stream.get(key) != value:
            raise BoundaryViolation(f"MP4 stream {key} differs from clean-media contract")
    if probe.get("chapters") or probe.get("programs"):
        raise BoundaryViolation("MP4 chapters and programs are forbidden")
    disposition = stream.get("disposition", {})
    if any(value != int(key == "default") for key, value in disposition.items()):
        raise BoundaryViolation("MP4 stream disposition carries non-default semantics")
    stream_tags = stream.get("tags", {})
    if set(stream_tags) - _STREAM_TAGS:
        raise BoundaryViolation("MP4 stream contains non-allowlisted metadata")
    if stream_tags.get("language") not in (None, "und"):
        raise BoundaryViolation("MP4 language metadata must be absent or undetermined")
    if stream_tags.get("handler_name") not in (None, "VideoHandler"):
        raise BoundaryViolation("MP4 handler metadata is not structural")
    encoder = stream_tags.get("encoder")
    if encoder is not None and re.fullmatch(r"Lavc[0-9.]+ libx264", encoder) is None:
        raise BoundaryViolation("MP4 stream encoder metadata is not structural")
    format_info = probe.get("format", {})
    format_tags = format_info.get("tags", {})
    if set(format_tags) - _FORMAT_TAGS:
        raise BoundaryViolation("MP4 format contains non-allowlisted metadata")
    if format_tags.get("major_brand") not in (None, "isom"):
        raise BoundaryViolation("MP4 major brand differs from the pinned encoder")
    format_encoder = format_tags.get("encoder")
    if format_encoder is not None and re.fullmatch(r"Lavf[0-9.]+", format_encoder) is None:
        raise BoundaryViolation("MP4 format encoder metadata is not structural")
    return {
        "kind": "mp4",
        "codec": stream["codec_name"],
        "width": stream["width"],
        "height": stream["height"],
        "pix_fmt": stream["pix_fmt"],
        "frame_rate": stream["avg_frame_rate"],
        "frames": int(stream["nb_read_frames"]),
        "stream_tags": stream_tags,
        "format_tags": format_tags,
    }


def validate_clean_media_call(call_path: Path) -> dict[str, Any]:
    """Validate exact JSON shape, opaque filenames, bytes, and media metadata."""

    call_path = call_path.resolve()
    payload = json.loads(call_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_KEYS:
        raise BoundaryViolation("call top-level keys differ from the allowlist")
    leaked = _walk_keys(payload) & _FORBIDDEN_KEYS
    if leaked:
        raise BoundaryViolation(f"forbidden semantic keys: {sorted(leaked)}")
    if payload["schema_version"] != "rei-emocio-vwm-clean-media-call-v2":
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
    probes: list[dict[str, Any]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, dict) or set(item) != _INPUT_KEYS:
            raise BoundaryViolation("input keys differ from the allowlist")
        if item["slot"] not in _SLOTS or item["media_type"] not in _MEDIA:
            raise BoundaryViolation("unsupported input slot or media type")
        relative = PurePosixPath(item["path"])
        suffix = ".png" if item["media_type"] == "image/png" else ".mp4"
        if relative.is_absolute() or len(relative.parts) != 1 or relative.name != f"i{index}{suffix}":
            raise BoundaryViolation("model-visible filenames must be canonical and opaque")
        asset = call_path.parent / relative.name
        if not asset.is_file() or _digest(asset) != item["sha256"]:
            raise BoundaryViolation(f"missing or hash-mismatched media input {relative.name}")
        media_probe = _validate_png(asset) if suffix == ".png" else _validate_mp4(asset)
        probes.append({"slot": item["slot"], "path": relative.name, **media_probe})
        slots.append(item["slot"])
    if len(slots) != len(set(slots)) or slots[0] != "observation":
        raise BoundaryViolation("input slots must be unique and observation-first")
    if payload["conditioning"] == "latent_action_image_goal" and "goal" not in slots:
        raise BoundaryViolation("image-goal conditioning requires a goal image")
    return {"call": payload, "media_probes": probes}


__all__ = ["BoundaryViolation", "validate_clean_media_call"]
