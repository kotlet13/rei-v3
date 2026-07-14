"""Canonical normalized float32-LE bytes shared by encoding and valuation."""

from __future__ import annotations

import hashlib
import math
import struct


def verified_float32_le_vector(
    data: bytes,
    *,
    expected_dimensions: int | None = None,
) -> tuple[tuple[float, ...], str]:
    """Decode exact normalized bytes and return their values and SHA-256."""

    if not data or len(data) % 4:
        raise ValueError("Float32-LE vector bytes must be non-empty and 4-byte aligned")
    dimensions = len(data) // 4
    if expected_dimensions is not None and dimensions != expected_dimensions:
        raise ValueError("Float32-LE vector byte dimensions differ from provenance")
    values = struct.unpack(f"<{dimensions}f", data)
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Float32-LE vectors must contain only finite values")
    for index, value in enumerate(values):
        if value == 0.0 and data[index * 4 : index * 4 + 4] != b"\x00\x00\x00\x00":
            raise ValueError("Float32-LE vectors require canonical positive zero")
    norm = math.sqrt(math.fsum(value * value for value in values))
    if not math.isclose(norm, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError("Float32-LE visual vectors must be L2-normalized")
    return tuple(values), hashlib.sha256(data).hexdigest()


def normalized_float32_le_bytes(
    values: tuple[float, ...],
    *,
    expected_dimensions: int | None = None,
) -> bytes:
    """Pack already-normalized values and verify the exact byte representation."""

    if not values:
        raise ValueError("Visual vectors must be non-empty")
    if expected_dimensions is not None and len(values) != expected_dimensions:
        raise ValueError("Visual vector dimensions differ from provenance")
    packed: list[bytes] = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError("Visual vector values must be numeric floats")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("Visual vector values must be finite")
        try:
            single = struct.unpack("<f", struct.pack("<f", numeric))[0]
        except (OverflowError, struct.error) as exc:
            raise ValueError("Visual vector value exceeds float32 range") from exc
        if not math.isfinite(single):
            raise ValueError("Visual vector value exceeds float32 range")
        packed.append(struct.pack("<f", 0.0 if single == 0.0 else single))
    data = b"".join(packed)
    verified_float32_le_vector(data, expected_dimensions=expected_dimensions)
    return data


def canonical_l2_float32_le_vector(
    values: tuple[float, ...],
    *,
    expected_dimensions: int | None = None,
) -> tuple[bytes, tuple[float, ...], str]:
    """Preserve exact normalized bytes or canonicalize one raw vector once."""

    if not values:
        raise ValueError("Visual vectors must be non-empty")
    if expected_dimensions is not None and len(values) != expected_dimensions:
        raise ValueError("Visual vector dimensions differ from provenance")
    try:
        exact_data = normalized_float32_le_bytes(
            values,
            expected_dimensions=expected_dimensions,
        )
    except ValueError as exc:
        if "L2-normalized" not in str(exc):
            raise
    else:
        exact_values, exact_digest = verified_float32_le_vector(
            exact_data,
            expected_dimensions=expected_dimensions,
        )
        return exact_data, exact_values, exact_digest

    float32_values: list[float] = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError("Visual vector values must be numeric floats")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError("Visual vector values must be finite")
        try:
            single = struct.unpack("<f", struct.pack("<f", numeric))[0]
        except (OverflowError, struct.error) as exc:
            raise ValueError("Visual vector value exceeds float32 range") from exc
        if not math.isfinite(single):
            raise ValueError("Visual vector value exceeds float32 range")
        float32_values.append(0.0 if single == 0.0 else single)
    norm = math.sqrt(math.fsum(value * value for value in float32_values))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("A zero visual vector cannot be normalized")
    data = b"".join(
        struct.pack("<f", 0.0 if value == 0.0 else value / norm)
        for value in float32_values
    )
    decoded, digest = verified_float32_le_vector(
        data,
        expected_dimensions=expected_dimensions,
    )
    return data, decoded, digest


__all__ = [
    "canonical_l2_float32_le_vector",
    "normalized_float32_le_bytes",
    "verified_float32_le_vector",
]
