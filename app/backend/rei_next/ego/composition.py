"""Transparent deterministic derivation of Ego composition snapshots."""

from __future__ import annotations

from collections import OrderedDict

from ..models.ego import EgoClaimKind, EgoCompositionSnapshot, EgoTrace, SourcedEgoClaim


def _claims_from_observations(
    kind: EgoClaimKind,
    observations: list[tuple[str, str]],
    *,
    minimum_occurrences: int = 1,
) -> tuple[tuple[str, ...], tuple[SourcedEgoClaim, ...]]:
    by_text: OrderedDict[str, list[str]] = OrderedDict()
    for text, measure_id in observations:
        normalized = text.strip()
        if not normalized:
            continue
        by_text.setdefault(normalized, []).append(measure_id)
    values: list[str] = []
    claims: list[SourcedEgoClaim] = []
    for text, evidence_ids in by_text.items():
        if len(set(evidence_ids)) < minimum_occurrences:
            continue
        values.append(text)
        claims.append(
            SourcedEgoClaim.create(
                kind=kind,
                text=text,
                evidence_measure_ids=tuple(evidence_ids),
            )
        )
    return tuple(values), tuple(claims)


def derive_composition_snapshot(trace: EgoTrace) -> EgoCompositionSnapshot:
    """Derive only directly observable, reproducible claims from a trace.

    Recurrence means the exact same explicit token occurs in at least two
    measures.  No semantic similarity model, hidden weighting, or reflector is
    used.  Correction events affect ``source_trace_hash`` but never rewrite the
    measure they target.
    """

    if not trace.measures:
        raise ValueError("A composition snapshot requires at least one EgoMeasure")

    identity_observations: list[tuple[str, str]] = []
    conflict_observations: list[tuple[str, str]] = []
    translation_observations: list[tuple[str, str]] = []
    tension_observations: list[tuple[str, str]] = []
    spoznanje_observations: list[tuple[str, str]] = []
    commitment_observations: list[tuple[str, str]] = []
    relationship_observations: list[tuple[str, str]] = []

    for measure in trace.measures:
        measure_id = measure.measure_id
        identity_observations.append(
            (f"structural_character:{measure.structural_character.profile_id}", measure_id)
        )
        if measure.governance_mandate.status == "unresolved":
            sources = ",".join(measure.governance_mandate.structural_source_minds)
            conflict_observations.append((f"unresolved_governance:{sources}", measure_id))
        for gap in measure.translation_gaps:
            if gap.option_match and gap.distortion_type == "none":
                continue
            translation_observations.append(
                (
                    "translation_gap:"
                    f"{gap.source_mind}:{gap.distortion_type}:"
                    f"{gap.native_option_id}->{gap.interpreted_option_id}",
                    measure_id,
                )
            )
        tension_observations.extend(
            (tension, measure_id) for tension in measure.unresolved_tensions
        )
        if measure.spoznanje_status == "simulated_spoznanje":
            spoznanje_observations.append(
                (f"simulated_spoznanje:{measure.native_bundle_id}", measure_id)
            )
        if (
            measure.conscious_decision.decision_status == "committed"
            and measure.conscious_decision.option_id is not None
        ):
            commitment_observations.append(
                (
                    "conscious_commitment:"
                    f"{measure.conscious_decision.option_id}:"
                    f"{measure.conscious_decision.declared_reason}",
                    measure_id,
                )
            )
        relationship_observations.append(
            (f"acceptance_mode:{measure.acceptance_state.overall_mode}", measure_id)
        )

    identity_motifs, identity_claims = _claims_from_observations(
        "identity_motif", identity_observations
    )
    recurring_conflicts, conflict_claims = _claims_from_observations(
        "recurring_conflict", conflict_observations, minimum_occurrences=2
    )
    recurring_translation_errors, translation_claims = _claims_from_observations(
        "recurring_translation_error",
        translation_observations,
        minimum_occurrences=2,
    )
    unresolved_tensions, tension_claims = _claims_from_observations(
        "unresolved_tension", tension_observations
    )
    spoznanja, spoznanje_claims = _claims_from_observations(
        "spoznanje", spoznanje_observations
    )
    commitments, commitment_claims = _claims_from_observations(
        "commitment", commitment_observations
    )
    relationship_patterns, relationship_claims = _claims_from_observations(
        "relationship_pattern", relationship_observations, minimum_occurrences=2
    )

    evidence_measure_ids = tuple(measure.measure_id for measure in trace.measures)
    current_section = f"measure:{len(trace.measures)}"
    current_section_claim = SourcedEgoClaim.create(
        kind="current_section",
        text=current_section,
        evidence_measure_ids=evidence_measure_ids,
    )
    sourced_claims = (
        *identity_claims,
        *conflict_claims,
        *translation_claims,
        *tension_claims,
        *spoznanje_claims,
        *commitment_claims,
        *relationship_claims,
        current_section_claim,
    )
    last_measure = trace.measures[-1]
    return EgoCompositionSnapshot.create(
        ego_id=trace.ego_id,
        through_measure_id=last_measure.measure_id,
        identity_motifs=identity_motifs,
        recurring_conflicts=recurring_conflicts,
        recurring_translation_errors=recurring_translation_errors,
        unresolved_tensions=unresolved_tensions,
        resolved_tensions=(),
        spoznanja=spoznanja,
        commitments=commitments,
        relationship_patterns=relationship_patterns,
        current_section=current_section,
        evidence_measure_ids=evidence_measure_ids,
        created_at=last_measure.created_at,
        source_trace_hash=trace.trace_hash,
        sourced_claims=sourced_claims,
    )


__all__ = ["derive_composition_snapshot"]
