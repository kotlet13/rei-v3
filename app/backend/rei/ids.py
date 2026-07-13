from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence, Set
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel


_CONTENT_ID_PREFIX = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python", round_trip=True))
    if isinstance(value, Enum):
        return _canonicalize(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Canonical timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Canonical JSON object keys must be strings")
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, Set) and not isinstance(value, (str, bytes, bytearray)):
        normalized = [_canonicalize(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Canonical JSON does not permit NaN or infinity")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any, *, exclude_fields: Set[str] = frozenset()) -> bytes:
    """Serialize a value to the B2 canonical JSON representation.

    The contract is UTF-8 JSON, sorted object keys, compact separators, preserved
    Unicode, finite numbers only, and RFC 3339 UTC timestamps with microseconds.
    ``exclude_fields`` applies only to a top-level Pydantic model.
    """

    if isinstance(value, BaseModel) and exclude_fields:
        value = value.model_dump(
            mode="python",
            round_trip=True,
            exclude=set(exclude_fields),
        )
    normalized = _canonicalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(value: Any, *, exclude_fields: Set[str] = frozenset()) -> str:
    return hashlib.sha256(
        canonical_json_bytes(value, exclude_fields=exclude_fields)
    ).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    """Create a reproducible, content-addressed ID for derived artifacts."""

    if not _CONTENT_ID_PREFIX.fullmatch(prefix):
        raise ValueError("ID prefix must start with a-z and contain only a-z, 0-9, _ or -")
    return f"{prefix}_{sha256_hex(value)[:32]}"
