"""Stable, filesystem-safe locators for GUI Ego run partitions."""

from __future__ import annotations

import re

from app.backend.rei.ids import sha256_hex


EGO_PARTITION_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def ego_partition_id(ego_id: str) -> str:
    """Derive the same canonical hash namespace used by the EgoTrace store."""

    if type(ego_id) is not str or not ego_id.strip():
        raise ValueError("ego_id must be a non-empty string")
    return sha256_hex(ego_id)


def validate_ego_partition_id(value: str) -> str:
    """Reject any URL locator that is not one canonical lowercase digest."""

    if type(value) is not str or EGO_PARTITION_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("Ego partition ID must be exactly 64 lowercase hex digits")
    return value


__all__ = ["ego_partition_id", "validate_ego_partition_id"]
