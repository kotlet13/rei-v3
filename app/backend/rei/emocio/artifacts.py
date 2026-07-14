"""Byte-verifying local PNG persistence for optional B7 render artifacts."""

from __future__ import annotations

import hashlib
import os
import re
import struct
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter

from ..ids import canonical_json_bytes
from ..models.common import ArtifactRelativePath
from ..models.emocio import ImageArtifact
from ..models.rendering import ImageSourceReference


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PATH_ADAPTER = TypeAdapter(ArtifactRelativePath)
_IMAGE_REQUEST_ID = re.compile(r"^image_request_[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class StoredPng:
    relative_path: str
    content_sha256: str
    width: int
    height: int
    size_bytes: int


def inspect_png(data: bytes) -> tuple[int, int]:
    """Validate a complete, non-interlaced PNG stream and return dimensions."""

    if len(data) < 45 or not data.startswith(_PNG_SIGNATURE):
        raise ValueError("Renderer output is not a PNG byte stream")
    offset = len(_PNG_SIGNATURE)
    width = height = bit_depth = color_type = 0
    saw_ihdr = False
    saw_iend = False
    idat = bytearray()
    while offset < len(data):
        if len(data) - offset < 12:
            raise ValueError("Renderer PNG contains a truncated chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        chunk_end = payload_end + 4
        if chunk_end > len(data):
            raise ValueError("Renderer PNG chunk exceeds the byte stream")
        payload = data[payload_start:payload_end]
        expected_crc = struct.unpack(">I", data[payload_end:chunk_end])[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError("Renderer PNG chunk failed CRC verification")
        if not saw_ihdr:
            if kind != b"IHDR" or length != 13:
                raise ValueError("Renderer PNG is missing the canonical IHDR header")
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filter_method,
                interlace,
            ) = struct.unpack(">IIBBBBB", payload)
            if width <= 0 or height <= 0 or width >= 2**31 or height >= 2**31:
                raise ValueError("Renderer PNG declares invalid dimensions")
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if bit_depth not in valid_depths.get(color_type, set()):
                raise ValueError("Renderer PNG uses an invalid color/depth pair")
            if compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError(
                    "B7 renderer artifacts require canonical non-interlaced PNG"
                )
            saw_ihdr = True
        elif kind == b"IHDR":
            raise ValueError("Renderer PNG contains multiple IHDR chunks")
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            if length != 0:
                raise ValueError("Renderer PNG IEND chunk must be empty")
            saw_iend = True
            if chunk_end != len(data):
                raise ValueError("Renderer PNG contains bytes after IEND")
        offset = chunk_end
        if saw_iend:
            break
    if not saw_ihdr or not idat or not saw_iend:
        raise ValueError("Renderer PNG requires IHDR, IDAT and terminal IEND chunks")

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    expected_size = height * (row_bytes + 1)
    decompressor = zlib.decompressobj()
    pixels = decompressor.decompress(bytes(idat), expected_size + 1)
    if decompressor.unconsumed_tail or len(pixels) > expected_size:
        raise ValueError("Renderer PNG expands beyond declared dimensions")
    pixels += decompressor.flush(max(1, expected_size - len(pixels) + 1))
    if (
        not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
        or len(pixels) != expected_size
    ):
        raise ValueError("Renderer PNG IDAT stream does not match declared dimensions")
    for row in range(height):
        if pixels[row * (row_bytes + 1)] > 4:
            raise ValueError("Renderer PNG uses an invalid row filter")
    return width, height


class LocalPngArtifactStore:
    """Persist content-addressed PNG bytes below one trusted artifact root."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, relative_path: str) -> Path:
        canonical = _PATH_ADAPTER.validate_python(relative_path, strict=True)
        target = (self._root / canonical).resolve()
        if not target.is_relative_to(self._root):
            raise ValueError("Image artifact path escapes its configured root")
        return target

    def _cache_metadata_path(self, request_id: str) -> Path:
        if _IMAGE_REQUEST_ID.fullmatch(request_id) is None:
            raise ValueError("Renderer cache requires a canonical image request ID")
        return self._resolve(f"emocio/cache/{request_id}.json")

    @staticmethod
    def _persist_immutable_bytes(target: Path, data: bytes) -> None:
        """Create one immutable file atomically, rejecting conflicting content."""

        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=target.parent,
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(temporary_path, target)
                except FileExistsError:
                    pass
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()

        try:
            existing = target.read_bytes()
        except OSError as exc:
            raise ValueError("Immutable artifact metadata is unreadable") from exc
        if existing != data:
            raise ValueError("Immutable artifact path already contains other bytes")

    def persist_png(
        self,
        relative_path: str,
        data: bytes,
        *,
        expected_width: int,
        expected_height: int,
    ) -> StoredPng:
        """Atomically store bytes after media and dimension verification."""

        width, height = inspect_png(data)
        if (width, height) != (expected_width, expected_height):
            raise ValueError("Renderer PNG dimensions differ from its approved request")
        digest = hashlib.sha256(data).hexdigest()
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if not target.exists():
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    dir=target.parent,
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(temporary_path, target)
                except FileExistsError:
                    pass
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()

        existing = target.read_bytes()
        if existing != data:
            raise ValueError("Content-addressed image path already contains other bytes")

        persisted = existing
        if hashlib.sha256(persisted).hexdigest() != digest:
            raise ValueError("Persisted image bytes failed SHA-256 verification")
        persisted_width, persisted_height = inspect_png(persisted)
        return StoredPng(
            relative_path=relative_path,
            content_sha256=digest,
            width=persisted_width,
            height=persisted_height,
            size_bytes=len(persisted),
        )

    def read_verified_source(self, source: ImageSourceReference) -> bytes:
        """Read an img2img source and close path, hash, media and dimensions."""

        if source.media_type != "image/png":
            raise ValueError("The B7 local source store accepts PNG img2img inputs")
        data = self._resolve(source.path).read_bytes()
        if hashlib.sha256(data).hexdigest() != source.content_sha256:
            raise ValueError("Image-to-image source bytes differ from recorded SHA-256")
        if inspect_png(data) != (source.width, source.height):
            raise ValueError("Image-to-image source dimensions differ from provenance")
        return data

    def verify_artifact(self, artifact: ImageArtifact) -> bytes:
        """Re-read a published artifact and verify its byte-level provenance."""

        return self.read_verified_source(ImageSourceReference.from_artifact(artifact))

    def persist_cached_artifact(self, artifact: ImageArtifact) -> None:
        """Publish canonical cache metadata only after re-verifying its PNG bytes."""

        self.verify_artifact(artifact)
        metadata = canonical_json_bytes(artifact)
        self._persist_immutable_bytes(
            self._cache_metadata_path(artifact.request_id),
            metadata,
        )

    def read_cached_artifact(self, request_id: str) -> ImageArtifact | None:
        """Return a byte-verified cached artifact, or ``None`` for a true miss.

        Once cache metadata exists, every parse, canonicalization, and PNG error is
        surfaced to the caller.  A corrupt entry is never treated as a cache miss.
        """

        metadata_path = self._cache_metadata_path(request_id)
        try:
            metadata = metadata_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ValueError("Renderer cache metadata is unreadable") from exc
        try:
            artifact = ImageArtifact.model_validate_json(metadata)
        except Exception as exc:
            raise ValueError("Renderer cache metadata is invalid") from exc
        if metadata != canonical_json_bytes(artifact):
            raise ValueError("Renderer cache metadata is not canonical JSON")
        self.verify_artifact(artifact)
        return artifact


__all__ = ["LocalPngArtifactStore", "StoredPng", "inspect_png"]
