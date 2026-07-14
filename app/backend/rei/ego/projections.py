"""Deterministic modality-specific projections of one Ego trace."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from typing import NamedTuple

from .world_updates import (
    EmocioLongitudinalVisualSignal,
    InstinktLongitudinalBodySignal,
)
from ..models.ego import (
    EgoClaimKind,
    EgoTrace,
    EmocioProjection,
    EmocioVisualHistoryRef,
    InstinktBodyHistoryRef,
    InstinktProjection,
    RacioProjection,
    SourcedEgoClaim,
)
from ..models.run import NativeMindBundle


class EgoModalityProjections(NamedTuple):
    racio: RacioProjection
    emocio: EmocioProjection
    instinkt: InstinktProjection


def _cold_revalidate(value: object) -> object:
    model_type = type(value)
    validator = getattr(model_type, "model_validate", None)
    dumper = getattr(value, "model_dump", None)
    if validator is None or dumper is None:
        raise TypeError("Projection inputs must be Pydantic artifacts")
    cold = validator(dumper(mode="python", round_trip=True))
    if cold != value:
        raise ValueError("Projection input changed during cold revalidation")
    return cold


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
        bundle = _cold_revalidate(bundle)  # type: ignore[assignment]
        if bundle.bundle_id != measure.native_bundle_id:
            raise ValueError("Native bundle lookup key does not match bundle identity")
        if (
            bundle.scene_id != measure.event_id
            or bundle.immutable_hash != measure.native_bundle_hash
        ):
            raise ValueError(
                "Native bundle scene/hash differs from its EgoMeasure lineage"
            )
        resolved.append(bundle)
    return tuple(resolved)


def _ordered_emocio_history(
    trace: EgoTrace,
    bundles: Mapping[str, NativeMindBundle],
    signals: tuple[EmocioLongitudinalVisualSignal, ...],
) -> tuple[EmocioLongitudinalVisualSignal, ...]:
    measure_by_id = {measure.measure_id: measure for measure in trace.measures}
    measure_order = {measure.measure_id: index for index, measure in enumerate(trace.measures)}
    cold_signals: list[EmocioLongitudinalVisualSignal] = []
    for signal in signals:
        cold = _cold_revalidate(signal)
        if not isinstance(cold, EmocioLongitudinalVisualSignal):
            raise TypeError("Emocio projection history contains another artifact type")
        measure = measure_by_id.get(cold.source_measure_id)
        if measure is None:
            raise ValueError("Emocio history cites a future or foreign EgoMeasure")
        bundle = bundles[measure.native_bundle_id]
        cold.validate_against(
            measure=measure,
            bundle=bundle,
            visual_state=cold.source_visual_state,
        )
        cold_signals.append(cold)
    ids = tuple(item.source_measure_id for item in cold_signals)
    if len(set(ids)) != len(ids):
        raise ValueError("Emocio history may contain at most one signal per measure")
    if tuple(measure_order[item] for item in ids) != tuple(
        sorted(measure_order[item] for item in ids)
    ):
        raise ValueError("Emocio history must follow EgoTrace measure order")
    return tuple(cold_signals)


def _ordered_instinkt_history(
    trace: EgoTrace,
    bundles: Mapping[str, NativeMindBundle],
    signals: tuple[InstinktLongitudinalBodySignal, ...],
) -> tuple[InstinktLongitudinalBodySignal, ...]:
    measure_by_id = {measure.measure_id: measure for measure in trace.measures}
    measure_order = {measure.measure_id: index for index, measure in enumerate(trace.measures)}
    cold_signals: list[InstinktLongitudinalBodySignal] = []
    for signal in signals:
        cold = _cold_revalidate(signal)
        if not isinstance(cold, InstinktLongitudinalBodySignal):
            raise TypeError("Instinkt projection history contains another artifact type")
        measure = measure_by_id.get(cold.source_measure_id)
        if measure is None:
            raise ValueError("Instinkt history cites a future or foreign EgoMeasure")
        bundle = bundles[measure.native_bundle_id]
        cold.validate_against(measure=measure, bundle=bundle)
        cold_signals.append(cold)
    ids = tuple(item.source_measure_id for item in cold_signals)
    if len(set(ids)) != len(ids):
        raise ValueError("Instinkt history may contain at most one signal per measure")
    if tuple(measure_order[item] for item in ids) != tuple(
        sorted(measure_order[item] for item in ids)
    ):
        raise ValueError("Instinkt history must follow EgoTrace measure order")
    return tuple(cold_signals)


def _emocio_history_ref(
    signal: EmocioLongitudinalVisualSignal,
) -> EmocioVisualHistoryRef:
    observation = signal.bound_observation
    return EmocioVisualHistoryRef.create(
        source_run_id=signal.source_run_id,
        source_measure_id=signal.source_measure_id,
        source_measure_hash=signal.source_measure_hash,
        source_bundle_id=signal.source_bundle_id,
        source_bundle_hash=signal.source_bundle_hash,
        source_signal_id=signal.signal_id,
        source_signal_hash=signal.signal_hash,
        observation_id=observation.observation_id,
        observation_hash=signal.bound_observation_hash,
        image_id=observation.image.image_id,
        image_content_sha256=observation.image.content_sha256,
        embedding_source_artifact_id=observation.embedding.source_artifact_id,
        vector_hash=observation.embedding.vector_hash,
        dimensions=observation.embedding.dimensions,
        role=observation.role,
    )


def _instinkt_history_ref(
    signal: InstinktLongitudinalBodySignal,
) -> InstinktBodyHistoryRef:
    measured = signal.measured_outcome_update
    return InstinktBodyHistoryRef.create(
        source_measure_id=signal.source_measure_id,
        source_measure_hash=signal.source_measure_hash,
        source_bundle_id=signal.source_bundle_id,
        source_bundle_hash=signal.source_bundle_hash,
        source_signal_id=signal.signal_id,
        source_signal_hash=signal.signal_hash,
        rollout_id=signal.selected_rollout.rollout_id,
        rollout_hash=signal.selected_rollout_hash,
        body_before_id=signal.body_before.body_state_id,
        body_before_hash=signal.body_before_hash,
        predicted_body_after_id=signal.predicted_body_after.body_state_id,
        predicted_body_after_hash=signal.predicted_body_after_hash,
        predicted_recoverability=signal.predicted_recoverability,
        measured_outcome_update_id=(None if measured is None else measured.update_id),
        measured_outcome_update_hash=(
            None if measured is None else measured.update_hash
        ),
        measured_body_after_id=(
            None if measured is None else measured.body_after.body_state_id
        ),
        measured_body_after_hash=(
            None if measured is None else measured.body_after.content_hash()
        ),
        learned_association_id=(
            None if measured is None else measured.learned_association.association_id
        ),
    )


def derive_modality_projections(
    trace: EgoTrace,
    bundles: Mapping[str, NativeMindBundle],
    *,
    emocio_history: tuple[EmocioLongitudinalVisualSignal, ...] = (),
    instinkt_history: tuple[InstinktLongitudinalBodySignal, ...] = (),
) -> EgoModalityProjections:
    """Project the same immutable history without adding a fourth opinion."""

    trace = _cold_revalidate(trace)  # type: ignore[assignment]
    if not trace.measures:
        raise ValueError("Modality projections require at least one EgoMeasure")
    ordered_bundles = _bundles_for_trace(trace, bundles)
    bundle_by_id = {item.bundle_id: item for item in ordered_bundles}
    ordered_emocio_history = _ordered_emocio_history(
        trace,
        bundle_by_id,
        emocio_history,
    )
    ordered_instinkt_history = _ordered_instinkt_history(
        trace,
        bundle_by_id,
        instinkt_history,
    )
    emocio_refs = tuple(_emocio_history_ref(item) for item in ordered_emocio_history)
    instinkt_refs = tuple(
        _instinkt_history_ref(item) for item in ordered_instinkt_history
    )
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
    recovery_obs: list[tuple[str, str]] = []
    loss_obs: list[tuple[str, str]] = []
    trust_obs: list[tuple[str, str]] = []
    attachment_obs: list[tuple[str, str]] = []
    boundary_obs: list[tuple[str, str]] = []

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

        danger_obs.append((f"dominant_alarm:{bundle.instinkt.dominant_alarm}", measure_id))
        danger_obs.extend(
            (f"danger_claim:{claim}", measure_id)
            for claim in bundle.instinkt.danger_claims
        )

    image_obs = [
        (reference.image_id, reference.source_measure_id)
        for reference in emocio_refs
    ]
    embedding_feature_obs = [
        (
            "visual_embedding_feature:"
            f"{reference.observation_id}:{reference.vector_hash}:"
            f"{reference.dimensions}",
            reference.source_measure_id,
        )
        for reference in emocio_refs
    ]
    for reference, signal in zip(instinkt_refs, ordered_instinkt_history, strict=True):
        body_obs.append(
            (
                "predicted_body_after:"
                f"{reference.predicted_body_after_id}:"
                f"{reference.predicted_body_after_hash}",
                reference.source_measure_id,
            )
        )
        recovery_obs.append(
            (
                "predicted_recoverability:"
                f"{reference.source_signal_id}:"
                f"{reference.predicted_recoverability:.12g}",
                reference.source_measure_id,
            )
        )
        measured = signal.measured_outcome_update
        if measured is None:
            continue
        body_obs.append(
            (
                f"measured_body_after:{measured.body_after.body_state_id}:"
                f"{measured.body_after.content_hash()}",
                reference.source_measure_id,
            )
        )
        association = measured.learned_association
        if association.experienced_loss is not None:
            loss_obs.append((association.experienced_loss, reference.source_measure_id))
        if association.trust_delta != 0.0:
            trust_obs.append(
                (
                    f"measured_trust_delta:{association.trust_delta:.12g}",
                    reference.source_measure_id,
                )
            )
        if association.attachment_delta != 0.0:
            attachment_obs.append(
                (
                    "measured_attachment_delta:"
                    f"{association.attachment_delta:.12g}",
                    reference.source_measure_id,
                )
            )
        if association.boundary_delta != 0.0:
            boundary_obs.append(
                (
                    f"measured_boundary_delta:{association.boundary_delta:.12g}",
                    reference.source_measure_id,
                )
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
    image_artifact_ids, image_claims = _claims_from_observations(
        "emocio_image_artifact", image_obs
    )
    embedding_feature_refs, embedding_feature_claims = _claims_from_observations(
        "emocio_embedding_feature", embedding_feature_obs
    )
    emocio = EmocioProjection.create(
        ego_id=trace.ego_id,
        through_measure_id=through_measure_id,
        recurring_scenes=recurring_scenes,
        image_artifact_ids=image_artifact_ids,
        embedding_feature_refs=embedding_feature_refs,
        status_patterns=status_patterns,
        belonging_motifs=(),
        success_motifs=(),
        rupture_motifs=(),
        desire_motifs=desire_motifs,
        evidence_measure_ids=evidence_measure_ids,
        source_trace_hash=trace.trace_hash,
        sourced_claims=(
            *scene_claims,
            *image_claims,
            *embedding_feature_claims,
            *status_claims,
            *desire_claims,
        ),
        visual_history=emocio_refs,
    )

    body_consequences, body_claims = _claims_from_observations(
        "instinkt_body_consequence", body_obs
    )
    dangers, danger_claims = _claims_from_observations("instinkt_danger", danger_obs)
    recovery_patterns, recovery_claims = _claims_from_observations(
        "instinkt_recovery_pattern", recovery_obs
    )
    losses, loss_claims = _claims_from_observations("instinkt_loss", loss_obs)
    trust_patterns, trust_claims = _claims_from_observations(
        "instinkt_trust_pattern", trust_obs
    )
    attachment_patterns, attachment_claims = _claims_from_observations(
        "instinkt_attachment_pattern", attachment_obs
    )
    boundary_patterns, boundary_claims = _claims_from_observations(
        "instinkt_boundary_pattern", boundary_obs
    )
    instinkt = InstinktProjection.create(
        ego_id=trace.ego_id,
        through_measure_id=through_measure_id,
        body_consequences=body_consequences,
        dangers=dangers,
        losses=losses,
        trust_patterns=trust_patterns,
        attachment_patterns=attachment_patterns,
        boundary_patterns=boundary_patterns,
        scarcity_patterns=(),
        recovery_patterns=recovery_patterns,
        evidence_measure_ids=evidence_measure_ids,
        source_trace_hash=trace.trace_hash,
        sourced_claims=(
            *body_claims,
            *danger_claims,
            *loss_claims,
            *trust_claims,
            *attachment_claims,
            *boundary_claims,
            *recovery_claims,
        ),
        body_history=instinkt_refs,
    )
    return EgoModalityProjections(racio=racio, emocio=emocio, instinkt=instinkt)


__all__ = ["EgoModalityProjections", "derive_modality_projections"]
