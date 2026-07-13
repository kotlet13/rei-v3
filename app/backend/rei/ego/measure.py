"""Lineage-closing construction of one immutable Ego measure."""

from __future__ import annotations

from ..models.character import CharacterAuthority, EffectiveAuthority
from ..models.common import UtcTimestamp
from ..models.communication import AcceptanceState, RacioInterpretation, TranslationGap
from ..models.conscious import BehaviorResultant, ConsciousDecision
from ..models.ego import EgoMeasure, OutcomeRecord
from ..models.governance import GovernanceResolution
from ..models.run import NativeMindBundle


def build_ego_measure(
    *,
    bundle: NativeMindBundle,
    governance: GovernanceResolution,
    structural_character: CharacterAuthority,
    effective_authority: EffectiveAuthority,
    acceptance_state: AcceptanceState,
    conscious_decision: ConsciousDecision,
    behavior_resultant: BehaviorResultant,
    racio_interpretations: tuple[RacioInterpretation, ...] = (),
    translation_gaps: tuple[TranslationGap, ...] = (),
    unresolved_tensions: tuple[str, ...] = (),
    outcome: OutcomeRecord | None = None,
    created_at: UtcTimestamp | None = None,
) -> EgoMeasure:
    """Build a full-cycle measure only after closing cross-artifact lineage.

    The function is intentionally a deterministic assembler.  It does not infer
    an Ego preference, call a provider, or reinterpret any native conclusion.
    """

    if (
        governance.native_bundle_id != bundle.bundle_id
        or governance.native_bundle_hash != bundle.immutable_hash
    ):
        raise ValueError("Governance resolution belongs to another native bundle")
    if governance.character_id != structural_character.character_id:
        raise ValueError("Governance resolution belongs to another character")
    if governance.character_hash != structural_character.content_hash():
        raise ValueError("Governance character hash does not match the supplied profile")
    if governance.profile_id != structural_character.profile_id:
        raise ValueError("Governance profile differs from the structural character")
    if governance.effective_authority_id != effective_authority.effective_authority_id:
        raise ValueError("Governance resolution belongs to another effective authority")
    if governance.effective_authority_hash != effective_authority.content_hash():
        raise ValueError("Governance effective-authority hash does not match")
    if effective_authority.structural_profile != structural_character:
        raise ValueError("Effective authority must preserve the structural character")

    allowed_options = set(bundle.allowed_option_ids)
    for label, option_id in (
        ("governance mandate", governance.mandate.option_id),
        ("conscious decision", conscious_decision.option_id),
        ("behavior resultant", behavior_resultant.option_id),
    ):
        if option_id is not None and option_id not in allowed_options:
            raise ValueError(f"{label} selected an option outside the native bundle")

    interpretation_by_id = {
        item.interpretation_id: item for item in racio_interpretations
    }
    if len(interpretation_by_id) != len(racio_interpretations):
        raise ValueError("Racio interpretation IDs must be unique")
    for interpretation in racio_interpretations:
        if (
            interpretation.inferred_option_id is not None
            and interpretation.inferred_option_id not in allowed_options
        ):
            raise ValueError("Racio interpretation inferred an out-of-bundle option")

    native_by_mind = {"E": bundle.emocio, "I": bundle.instinkt}
    for gap in translation_gaps:
        interpretation = interpretation_by_id.get(gap.interpretation_id)
        if interpretation is None or interpretation.source_mind != gap.source_mind:
            raise ValueError("Translation gap must cite its matching interpretation")
        native = native_by_mind[gap.source_mind]
        if gap.source_conclusion_id != native.conclusion_id:
            raise ValueError("Translation gap cites a conclusion outside the bundle")
        if gap.native_option_id != native.option_id:
            raise ValueError("Translation gap native option differs from the bundle")
        if gap.interpreted_option_id != interpretation.inferred_option_id:
            raise ValueError("Translation gap interpreted option differs from Racio output")

    return EgoMeasure.create(
        event_id=bundle.scene_id,
        native_bundle_id=bundle.bundle_id,
        native_bundle_hash=bundle.immutable_hash,
        governance_resolution_id=governance.resolution_id,
        governance_resolution_hash=governance.resolution_hash,
        structural_character=structural_character,
        effective_authority=effective_authority,
        acceptance_state=acceptance_state,
        governance_mandate=governance.mandate,
        racio_interpretations=racio_interpretations,
        conscious_decision=conscious_decision,
        behavior_resultant=behavior_resultant,
        outcome=outcome,
        translation_gaps=translation_gaps,
        unresolved_tensions=unresolved_tensions,
        spoznanje_status=governance.spoznanje_status,
        created_at=created_at,
    )


__all__ = ["build_ego_measure"]
