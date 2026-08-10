"""Strict visual-only PNG and MP4 validation for E2 media."""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct
import subprocess
from typing import Any


class BoundaryViolation(ValueError):
    """A media file differs from the frozen visual-only contract."""


_STREAM_TAGS = frozenset({"language", "handler_name", "encoder"})
_FORMAT_TAGS = frozenset({"major_brand", "minor_version", "compatible_brands", "encoder"})


def validate_png(path: Path, *, width: int, height: int) -> dict[str, Any]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BoundaryViolation(f"not a PNG: {path.name}")
    offset = 8
    dimensions = None
    forbidden = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
    chunks: list[str] = []
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunks.append(kind.decode("ascii", errors="replace"))
        if kind in forbidden:
            raise BoundaryViolation(f"PNG metadata chunk {kind.decode('ascii')} is forbidden")
        if kind == b"IHDR":
            dimensions = struct.unpack(">II", data[offset + 8 : offset + 16])
        offset += 12 + length
        if kind == b"IEND":
            if dimensions != (width, height):
                raise BoundaryViolation(f"PNG dimensions must be exactly {width}x{height}")
            return {"kind": "png", "width": width, "height": height, "chunks": chunks}
    raise BoundaryViolation(f"malformed PNG: {path.name}")


def _ffprobe(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format",
            "-show_chapters", "-show_programs", "-of", "json", str(path),
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


def validate_mp4(path: Path, *, width: int, height: int, fps: int, frame_count: int) -> dict[str, Any]:
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
        "width": width,
        "height": height,
        "pix_fmt": "yuv420p",
        "r_frame_rate": f"{fps}/1",
        "avg_frame_rate": f"{fps}/1",
        "nb_read_frames": str(frame_count),
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
    format_tags = probe.get("format", {}).get("tags", {})
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
