"""Deterministic modality-specific projections of one Ego trace."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import NamedTuple

from ..models.ego import (
    EgoClaimKind,
    EgoTrace,
    EmocioProjection,
    InstinktProjection,
    RacioProjection,
    SourcedEgoClaim,
)
from ..models.run import NativeMindBundle


class EgoModalityProjections(NamedTuple):
    racio: RacioProjection
    emocio: EmocioProjection
    instinkt: InstinktProjection


def _claims_from_observations(
    kind: EgoClaimKind,
    observations: list[tuple[str, str]],
) -> tuple[tuple[str, ...], tuple[SourcedEgoClaim, ...]]:
    by_text: OrderedDict[str, list[str]] = OrderedDict()
    for text, measure_id in observations:
        normalized = text.strip()
        if not normalized:
            continue
        by_text.setdefault(normalized, []).append(measure_id)
    values = tuple(by_text)
    claims = tuple(
        SourcedEgoClaim.create(
            kind=kind,
            text=text,
            evidence_measure_ids=tuple(measure_ids),
        )
        for text, measure_ids in by_text.items()
    )
    return values, claims


def _bundles_for_trace(
    trace: EgoTrace,
    bundles: Mapping[str, NativeMindBundle],
) -> tuple[NativeMindBundle, ...]:
    resolved: list[NativeMindBundle] = []
    for measure in trace.measures:
        bundle = bundles.get(measure.native_bundle_id)
        if bundle is None:
            raise ValueError(
                f"Missing native bundle for EgoMeasure {measure.measure_id!r}"
            )
        if bundle.bundle_id != measure.native_bundle_id:
            raise ValueError("Native bundle lookup key does not match bundle identity")
        if bundle.scene_id != measure.event_id:
            raise ValueError("Native bundle scene differs from its EgoMeasure event")
        resolved.append(bundle)
    return tuple(resolved)


def derive_modality_projections(
    trace: EgoTrace,
    bundles: Mapping[str, NativeMindBundle],
) -> EgoModalityProjections:
    """Project the same immutable history without adding a fourth opinion."""

    if not trace.measures:
        raise ValueError("Modality projections require at least one EgoMeasure")
    ordered_bundles = _bundles_for_trace(trace, bundles)
    evidence_measure_ids = tuple(measure.measure_id for measure in trace.measures)
    through_measure_id = evidence_measure_ids[-1]

    chronology_obs: list[tuple[str, str]] = []
    fact_obs: list[tuple[str, str]] = []
    statement_obs: list[tuple[str, str]] = []
    commitment_obs: list[tuple[str, str]] = []
    causal_obs: list[tuple[str, str]] = []
    scene_obs: list[tuple[str, str]] = []
    status_obs: list[tuple[str, str]] = []
    desire_obs: list[tuple[str, str]] = []
    body_obs: list[tuple[str, str]] = []
    danger_obs: list[tuple[str, str]] = []

    for measure, bundle in zip(trace.measures, ordered_bundles, strict=True):
        measure_id = measure.measure_id
        chronology_obs.append((f"event:{measure.event_id}", measure_id))
        statement_obs.append(
            (f"declared_reason:{measure.conscious_decision.declared_reason}", measure_id)
        )
        if measure.conscious_decision.decision_status == "committed":
            commitment_obs.append(
                (f"option:{measure.conscious_decision.option_id}", measure_id)
            )
        if measure.outcome is not None:
            fact_obs.extend(
                (f"observed_effect:{effect}", measure_id)
                for effect in measure.outcome.observed_effects
            )
            causal_obs.append(
                (
                    f"event:{measure.event_id}->outcome:{measure.outcome.outcome_id}",
                    measure_id,
                )
            )

        scene_obs.extend(
            (
                (f"current_scene:{bundle.emocio.current_scene_id}", measure_id),
                (f"desired_scene:{bundle.emocio.desired_scene_id}", measure_id),
            )
        )
        if bundle.emocio.decisive_rollout_scene_id is not None:
            scene_obs.append(
                (
                    f"decisive_rollout:{bundle.emocio.decisive_rollout_scene_id}",
                    measure_id,
                )
            )
        status_obs.append((f"behavior_status:{measure.behavior_resultant.status}", measure_id))
        desire_obs.append(
            (f"desired_transformation:{bundle.emocio.desired_transformation}", measure_id)
        )

        body_obs.append((f"body_state:{bundle.instinkt.source_body_state_id}", measure_id))
        if bundle.instinkt.decisive_rollout_id is not None:
            body_obs.append(
                (f"decisive_rollout:{bundle.instinkt.decisive_rollout_id}", measure_id)
            )
        danger_obs.append((f"dominant_alarm:{bundle.instinkt.dominant_alarm}", measure_id))
        danger_obs.extend(
            (f"danger_claim:{claim}", measure_id)
            for claim in bundle.instinkt.danger_claims
        )

    chronology, chronology_claims = _claims_from_observations(
        "racio_chronology", chronology_obs
    )
    facts, fact_claims = _claims_from_observations("racio_fact", fact_obs)
    statements, statement_claims = _claims_from_observations(
        "racio_statement", statement_obs
    )
    commitments, commitment_claims = _claims_from_observations(
        "racio_commitment", commitment_obs
    )
    causal_links, causal_claims = _claims_from_observations(
        "racio_causal_link", causal_obs
    )
    racio = RacioProjection.create(
        ego_id=trace.ego_id,
        through_measure_id=through_measure_id,
        chronology=chronology,
        facts=facts,
        statements=statements,
        commitments=commitments,
        causal_links=causal_links,
        evidence_measure_ids=evidence_measure_ids,
        source_trace_hash=trace.trace_hash,
        sourced_claims=(
            *chronology_claims,
            *fact_claims,
            *statement_claims,
            *commitment_claims,
            *causal_claims,
        ),
    )

    recurring_scenes, scene_claims = _claims_from_observations(
        "emocio_recurring_scene", scene_obs
    )
    status_patterns, status_claims = _claims_from_observations(
        "emocio_status_pattern", status_obs
    )
    desire_motifs, desire_claims = _claims_from_observations(
        "emocio_desire_motif", desire_obs
    )
    emocio = EmocioProjection.create(
        ego_id=trace.ego_id,
        through_measure_id=through_measure_id,
        recurring_scenes=recurring_scenes,
        image_artifact_ids=(),
        status_patterns=status_patterns,
        belonging_motifs=(),
        success_motifs=(),
        rupture_motifs=(),
        desire_motifs=desire_motifs,
        evidence_measure_ids=evidence_measure_ids,
        source_trace_hash=trace.trace_hash,
        sourced_claims=(*scene_claims, *status_claims, *desire_claims),
    )

    body_consequences, body_claims = _claims_from_observations(
        "instinkt_body_consequence", body_obs
    )
    dangers, danger_claims = _claims_from_observations("instinkt_danger", danger_obs)
    instinkt = InstinktProjection.create(
        ego_id=trace.ego_id,
        through_measure_id=through_measure_id,
        body_consequences=body_consequences,
        dangers=dangers,
        losses=(),
        trust_patterns=(),
        attachment_patterns=(),
        boundary_patterns=(),
        scarcity_patterns=(),
        recovery_patterns=(),
        evidence_measure_ids=evidence_measure_ids,
        source_trace_hash=trace.trace_hash,
        sourced_claims=(*body_claims, *danger_claims),
    )
    return EgoModalityProjections(racio=racio, emocio=emocio, instinkt=instinkt)


__all__ = ["EgoModalityProjections", "derive_modality_projections"]
