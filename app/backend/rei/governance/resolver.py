"""Deterministic ordinal governance over one frozen NativeMindBundle."""

from __future__ import annotations

from collections import Counter

from ..ids import content_id
from ..models.character import (
    CharacterAuthority,
    EffectiveAuthority,
    FunctionalOverride,
)
from ..models.common import MindId, NonEmptyId
from ..models.governance import (
    AgreementPattern,
    GovernanceMandate,
    GovernanceResolution,
    MindConclusionPosition,
    MindOption,
    MindStatement,
    PairConflict,
    PairNegotiationRound,
    TaskDelegation,
)
from ..models.run import NativeMindBundle
from .delegation import apply_task_delegation
from .negotiation import resolve_pair_conflict
from .profiles import derive_effective_authority


_MIND_ORDER: tuple[MindId, ...] = ("R", "E", "I")


def _positions(
    bundle: NativeMindBundle,
) -> tuple[
    MindConclusionPosition,
    MindConclusionPosition,
    MindConclusionPosition,
]:
    return (
        MindConclusionPosition(
            mind="R",
            conclusion_id=bundle.racio.conclusion_id,
            option_id=bundle.racio.option_id,
            abstains=bundle.racio.abstains,
        ),
        MindConclusionPosition(
            mind="E",
            conclusion_id=bundle.emocio.conclusion_id,
            option_id=bundle.emocio.option_id,
            abstains=bundle.emocio.abstains,
        ),
        MindConclusionPosition(
            mind="I",
            conclusion_id=bundle.instinkt.conclusion_id,
            option_id=bundle.instinkt.option_id,
            abstains=bundle.instinkt.abstains,
        ),
    )


def assess_agreement_pattern(bundle: NativeMindBundle) -> AgreementPattern:
    """Classify native option equality independently of character authority."""

    positions = _positions(bundle)
    options = tuple(position.option_id for position in positions)
    if any(position.abstains or position.option_id is None for position in positions):
        return AgreementPattern.create(
            native_bundle_id=bundle.bundle_id,
            native_bundle_hash=bundle.immutable_hash,
            positions=positions,
            agreement_kind="incomplete",
            spoznanje_status="unknown",
        )

    non_null_options = tuple(option for option in options if option is not None)
    counts = Counter(non_null_options)
    if len(counts) == 1:
        return AgreementPattern.create(
            native_bundle_id=bundle.bundle_id,
            native_bundle_hash=bundle.immutable_hash,
            positions=positions,
            agreement_kind="unanimous",
            spoznanje_status="simulated_spoznanje",
            winning_option_id=non_null_options[0],
            agreeing_minds=_MIND_ORDER,
        )
    majority_option = next(
        (option_id for option_id in non_null_options if counts[option_id] == 2),
        None,
    )
    if majority_option is not None:
        agreeing_minds = tuple(
            position.mind
            for position in positions
            if position.option_id == majority_option
        )
        return AgreementPattern.create(
            native_bundle_id=bundle.bundle_id,
            native_bundle_hash=bundle.immutable_hash,
            positions=positions,
            agreement_kind="majority",
            spoznanje_status="partial_agreement",
            winning_option_id=majority_option,
            agreeing_minds=agreeing_minds,
        )
    return AgreementPattern.create(
        native_bundle_id=bundle.bundle_id,
        native_bundle_hash=bundle.immutable_hash,
        positions=positions,
        agreement_kind="all_different",
        spoznanje_status="no_spoznanje",
    )


def _native_objections(bundle: NativeMindBundle) -> dict[MindId, str]:
    return {
        "R": bundle.racio.main_objection,
        "E": bundle.emocio.main_obstacle,
        "I": bundle.instinkt.dominant_alarm,
    }


def _native_motives(bundle: NativeMindBundle) -> dict[MindId, str]:
    return {
        "R": bundle.racio.explicit_goal,
        "E": bundle.emocio.desired_transformation,
        "I": bundle.instinkt.minimum_safety_condition,
    }


def _build_mandate(
    *,
    bundle: NativeMindBundle,
    source_minds: tuple[MindId, ...],
    option_id: NonEmptyId | None,
    functionally_overridden: bool,
) -> GovernanceMandate:
    status = (
        "unresolved"
        if option_id is None
        else "functionally_overridden"
        if functionally_overridden
        else "resolved"
    )
    option_by_mind = {
        "R": bundle.racio.option_id,
        "E": bundle.emocio.option_id,
        "I": bundle.instinkt.option_id,
    }
    objections_by_mind = _native_objections(bundle)
    objections = tuple(
        MindStatement(mind=mind, statement=objections_by_mind[mind])
        for mind in _MIND_ORDER
        if option_id is None or option_by_mind[mind] != option_id
    )
    motives_by_mind = _native_motives(bundle)
    hidden_native_motives = tuple(
        MindStatement(mind=mind, statement=motives_by_mind[mind])
        for mind in _MIND_ORDER
    )
    base = {
        "schema_version": "rei-native-governance-mandate-v1",
        "status": status,
        "structural_source_minds": source_minds,
        "option_id": option_id,
        "objections": objections,
        "delegation": None,
        "hidden_native_motives": hidden_native_motives,
    }
    return GovernanceMandate(
        mandate_id=content_id("mandate", base),
        **base,
    )


def _effective_authority(
    authority: CharacterAuthority | EffectiveAuthority,
    functional_override: FunctionalOverride | None,
) -> EffectiveAuthority:
    if isinstance(authority, EffectiveAuthority):
        if functional_override is not None:
            raise ValueError(
                "Pass either an EffectiveAuthority or a FunctionalOverride, not both"
            )
        return authority
    return derive_effective_authority(authority, functional_override)


def resolve_governance(
    bundle: NativeMindBundle,
    authority: CharacterAuthority | EffectiveAuthority,
    *,
    functional_override: FunctionalOverride | None = None,
    delegation: TaskDelegation | None = None,
    negotiation_rounds: tuple[PairNegotiationRound, ...] = (),
) -> GovernanceResolution:
    """Resolve a frozen bundle using only stable ordinal authority.

    Confidence, intensity, mood, acceptance, and subordinate positions are not
    inputs to rank or tie-breaking.  A caller may provide an already derived
    EffectiveAuthority or a structural profile plus an explicit override.
    """

    effective = _effective_authority(authority, functional_override)
    if not effective.effective_tiers:
        raise ValueError("Governance cannot resolve when every mind is unavailable")
    if delegation is not None and effective.functional_override is not None:
        raise ValueError("Delegation and functional override cannot share one resolution")

    agreement_pattern = assess_agreement_pattern(bundle)
    options: dict[MindId, NonEmptyId | None] = {
        "R": bundle.racio.option_id,
        "E": bundle.emocio.option_id,
        "I": bundle.instinkt.option_id,
    }
    top_minds = effective.effective_tiers[0]
    source_minds: tuple[MindId, ...]
    selected_option: NonEmptyId | None
    pair_conflict: PairConflict | None = None

    if len(top_minds) == 1:
        if negotiation_rounds:
            raise ValueError("Pair negotiation is valid only for an equal top pair")
        source_minds = top_minds
        selected_option = options[top_minds[0]]
    elif len(top_minds) == 2:
        source_minds = top_minds
        pair_options = tuple(options[mind] for mind in top_minds)
        if any(option_id is None for option_id in pair_options):
            if negotiation_rounds:
                raise ValueError("An incomplete top pair cannot enter option negotiation")
            selected_option = None
        else:
            initial_options = (
                MindOption(mind=top_minds[0], option_id=pair_options[0]),
                MindOption(mind=top_minds[1], option_id=pair_options[1]),
            )
            allowed_options = set(bundle.allowed_option_ids)
            if any(
                entry.option_id not in allowed_options
                for round_record in negotiation_rounds
                for entry in round_record.option_by_mind
            ):
                raise ValueError("Negotiated options must remain inside bundle scope")
            pair_conflict = resolve_pair_conflict(
                native_bundle_id=bundle.bundle_id,
                top_minds=(top_minds[0], top_minds[1]),
                initial_option_by_mind=initial_options,
                negotiation_rounds=negotiation_rounds,
            )
            selected_option = (
                pair_conflict.option_by_mind[0].option_id
                if pair_conflict.status == "resolved"
                else None
            )
    elif len(top_minds) == 3:
        if negotiation_rounds:
            raise ValueError("Pair negotiation cannot replace the two-of-three rule")
        if agreement_pattern.agreement_kind in {"unanimous", "majority"}:
            selected_option = agreement_pattern.winning_option_id
            source_minds = agreement_pattern.agreeing_minds
        else:
            selected_option = None
            source_minds = top_minds
    else:
        raise ValueError("An effective top tier must contain one, two, or three minds")

    base_mandate = _build_mandate(
        bundle=bundle,
        source_minds=source_minds,
        option_id=selected_option,
        functionally_overridden=effective.functional_override is not None,
    )
    mandate = (
        apply_task_delegation(
            base_mandate=base_mandate,
            effective_authority=effective,
            allowed_option_ids=bundle.allowed_option_ids,
            option_by_mind=options,
            delegation=delegation,
        )
        if delegation is not None
        else base_mandate
    )
    structural = effective.structural_profile
    return GovernanceResolution.create(
        native_bundle_id=bundle.bundle_id,
        native_bundle_hash=bundle.immutable_hash,
        character_id=structural.character_id,
        character_hash=structural.content_hash(),
        profile_id=structural.profile_id,
        effective_authority_id=effective.effective_authority_id,
        effective_authority_hash=effective.content_hash(),
        structural_top_minds=structural.authority_tiers[0],
        effective_source_minds=source_minds,
        agreement_pattern=agreement_pattern,
        mandate=mandate,
        pair_conflict=pair_conflict,
    )


__all__ = ["assess_agreement_pattern", "resolve_governance"]
