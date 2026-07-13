"""Bounded, provenance-bearing negotiation for an equal top pair."""

from __future__ import annotations

from ..ids import content_id
from ..models.common import MindId, NonEmptyId
from ..models.governance import (
    MindOption,
    PairConflict,
    PairNegotiationRound,
)


def resolve_pair_conflict(
    *,
    native_bundle_id: NonEmptyId,
    top_minds: tuple[MindId, MindId],
    initial_option_by_mind: tuple[MindOption, MindOption],
    negotiation_rounds: tuple[PairNegotiationRound, ...] = (),
) -> PairConflict:
    """Resolve only through the two top minds and at most two proven rounds."""

    if len(negotiation_rounds) > 2:
        raise ValueError("A pair negotiation permits at most two additional rounds")
    if tuple(item.mind for item in initial_option_by_mind) != top_minds:
        raise ValueError("Initial pair options must follow top_minds order")

    current_options = initial_option_by_mind
    seen_provenance_ids: set[str] = set()
    for expected_number, round_record in enumerate(negotiation_rounds, start=1):
        if len({item.option_id for item in current_options}) == 1:
            raise ValueError("Negotiation must stop once the top pair agrees")
        if round_record.round_number != expected_number:
            raise ValueError("Negotiation rounds must be contiguous from one")
        if round_record.top_minds != top_minds:
            raise ValueError("A negotiation round cannot change the top pair")
        provenance_ids = set(
            round_record.new_information_ids + round_record.new_rollout_ids
        )
        if seen_provenance_ids.intersection(provenance_ids):
            raise ValueError("Each negotiation round must add new provenance")
        seen_provenance_ids.update(provenance_ids)
        current_options = round_record.option_by_mind

    status = (
        "resolved"
        if len({item.option_id for item in current_options}) == 1
        else "unresolved"
    )
    base = {
        "schema_version": "rei-native-pair-conflict-v1",
        "native_bundle_id": native_bundle_id,
        "top_minds": top_minds,
        "initial_option_by_mind": initial_option_by_mind,
        "option_by_mind": current_options,
        "status": status,
        "negotiation_rounds": len(negotiation_rounds),
        "negotiation_history": negotiation_rounds,
    }
    return PairConflict(
        pair_conflict_id=content_id("pair_conflict", base),
        top_minds=top_minds,
        initial_option_by_mind=initial_option_by_mind,
        option_by_mind=current_options,
        status=status,
        negotiation_rounds=len(negotiation_rounds),
        negotiation_history=negotiation_rounds,
    )


__all__ = ["resolve_pair_conflict"]
