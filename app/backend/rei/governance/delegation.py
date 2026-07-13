"""Validation and application of explicit operational delegation."""

from __future__ import annotations

from ..ids import content_id
from ..models.character import EffectiveAuthority
from ..models.common import MindId, NonEmptyId
from ..models.governance import GovernanceMandate, TaskDelegation


def apply_task_delegation(
    *,
    base_mandate: GovernanceMandate,
    effective_authority: EffectiveAuthority,
    allowed_option_ids: tuple[NonEmptyId, ...],
    option_by_mind: dict[MindId, NonEmptyId | None],
    delegation: TaskDelegation,
) -> GovernanceMandate:
    """Apply an explicit task handoff without changing any authority tier."""

    if effective_authority.functional_override is not None:
        raise ValueError("Delegation and functional override cannot share one resolution")
    if delegation.delegating_minds != base_mandate.structural_source_minds:
        raise ValueError("Every current mandate source must explicitly delegate")
    available_minds = {
        mind for tier in effective_authority.effective_tiers for mind in tier
    }
    if delegation.delegate_mind not in available_minds:
        raise ValueError("Delegation must target a functionally available mind")
    if delegation.option_id is None:
        raise ValueError("An operational delegation requires an explicit option")
    if delegation.option_id not in allowed_option_ids:
        raise ValueError("Delegation option must remain inside the native bundle scope")
    if option_by_mind[delegation.delegate_mind] != delegation.option_id:
        raise ValueError(
            "Delegation option must equal the delegate mind's frozen native option"
        )
    if (
        base_mandate.option_id is not None
        and delegation.option_id != base_mandate.option_id
    ):
        raise ValueError("Delegation cannot replace an authoritative resolved option")

    option_id = delegation.option_id
    base = {
        "schema_version": "rei-native-governance-mandate-v1",
        "status": "delegated",
        "structural_source_minds": base_mandate.structural_source_minds,
        "option_id": option_id,
        "objections": base_mandate.objections,
        "delegation": delegation,
        "hidden_native_motives": base_mandate.hidden_native_motives,
    }
    return GovernanceMandate(
        mandate_id=content_id("mandate", base),
        **base,
    )


__all__ = ["apply_task_delegation"]
