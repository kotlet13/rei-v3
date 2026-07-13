"""Canonical character parsing and explicit availability projection."""

from __future__ import annotations

from typing import cast

from ..ids import content_id
from ..models.character import (
    CHARACTER_PROFILE_CONTRACTS,
    CharacterAuthority,
    CharacterProfileId,
    EffectiveAuthority,
    FunctionalOverride,
)
from ..models.common import NonEmptyId


def parse_character_profile(
    profile_id: str,
    *,
    character_id: NonEmptyId | None = None,
) -> CharacterAuthority:
    """Parse one exact canonical profile without permissive syntax rewriting."""

    contract = CHARACTER_PROFILE_CONTRACTS.get(profile_id)  # type: ignore[arg-type]
    if contract is None:
        allowed = ", ".join(CHARACTER_PROFILE_CONTRACTS)
        raise ValueError(
            f"Unknown character profile {profile_id!r}; expected one of: {allowed}"
        )
    canonical_profile_id = cast(CharacterProfileId, profile_id)
    authority_tiers, rule = contract
    base = {
        "schema_version": "rei-native-character-authority-v1",
        "profile_id": canonical_profile_id,
        "authority_tiers": authority_tiers,
        "rule": rule,
    }
    return CharacterAuthority(
        character_id=character_id or content_id("character", base),
        **base,
    )


def derive_effective_authority(
    structural_profile: CharacterAuthority,
    functional_override: FunctionalOverride | None = None,
) -> EffectiveAuthority:
    """Project tiers only from an explicit FunctionalOverride declaration.

    Availability scores are retained as evidence but are never thresholded or
    compared by this policy.  The explicit unavailable-mind declaration is the
    sole source of removals.  A total outage is representable here and rejected
    later by the resolver because it has no mandate source.
    """

    unavailable = (
        set(functional_override.unavailable_minds)
        if functional_override is not None
        else set()
    )
    effective_tiers = tuple(
        retained
        for tier in structural_profile.authority_tiers
        if (retained := tuple(mind for mind in tier if mind not in unavailable))
    )
    base = {
        "schema_version": "rei-native-effective-authority-v1",
        "structural_profile": structural_profile,
        "effective_tiers": effective_tiers,
        "override_reason": (
            functional_override.reason if functional_override is not None else None
        ),
        "functional_override": functional_override,
    }
    return EffectiveAuthority(
        effective_authority_id=content_id("effective_authority", base),
        **base,
    )


__all__ = ["derive_effective_authority", "parse_character_profile"]
