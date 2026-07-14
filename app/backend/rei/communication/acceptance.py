"""Record-only audit of declared acceptance fidelity versus measured translation."""

from __future__ import annotations

import math

from ..ids import content_id, sha256_hex
from ..models.communication import (
    B9_ACCEPTANCE_FIDELITY_AUDIT_POLICY,
    AcceptanceFidelityAssessment,
    AcceptanceState,
    TranslationGap,
)


def assess_acceptance_fidelity(
    *,
    acceptance_state: AcceptanceState,
    gap: TranslationGap,
) -> AcceptanceFidelityAssessment:
    """Audit a declared relation; never infer acceptance or alter authority/behavior."""

    if gap.gap_status != "derived_b9" or gap.translation_gap_hash is None:
        raise ValueError("Acceptance fidelity audit requires an evaluated B9 gap")
    relation = acceptance_state.R_to_E if gap.source_mind == "E" else acceptance_state.R_to_I
    direction = "R_to_E" if gap.source_mind == "E" else "R_to_I"
    declared = relation.interpretation_fidelity
    measured = gap.motive_fidelity
    difference = abs(measured - declared)
    delta = measured - declared
    comparison = (
        "equal"
        if math.isclose(delta, 0.0, rel_tol=0.0, abs_tol=1e-12)
        else "measured_higher"
        if delta > 0.0
        else "measured_lower"
    )
    base = {
        "schema_version": "rei-native-acceptance-fidelity-assessment-v1",
        "source_mind": gap.source_mind,
        "acceptance_state_id": acceptance_state.acceptance_state_id,
        "acceptance_state_hash": acceptance_state.content_hash(),
        "relation_direction": direction,
        "declared_interpretation_fidelity": declared,
        "translation_gap_id": gap.translation_gap_id,
        "translation_gap_hash": gap.content_hash(),
        "measured_motive_fidelity": measured,
        "absolute_difference": difference,
        "comparison": comparison,
        "audit_policy": B9_ACCEPTANCE_FIDELITY_AUDIT_POLICY,
    }
    assessment_id = content_id("acceptance_fidelity", base)
    payload = {"assessment_id": assessment_id, **base}
    return AcceptanceFidelityAssessment(
        **payload,
        assessment_hash=sha256_hex(payload),
    )


def validate_acceptance_fidelity_replay(
    *,
    assessment: AcceptanceFidelityAssessment,
    acceptance_state: AcceptanceState,
    gap: TranslationGap,
) -> AcceptanceFidelityAssessment:
    """Reject a self-consistent audit that does not replay from its two inputs."""

    expected = assess_acceptance_fidelity(
        acceptance_state=acceptance_state,
        gap=gap,
    )
    if assessment != expected:
        raise ValueError("Acceptance fidelity assessment differs from replay")
    return assessment


__all__ = [
    "assess_acceptance_fidelity",
    "validate_acceptance_fidelity_replay",
]
