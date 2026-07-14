from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.backend.rei.ego.projections import derive_modality_projections
from app.backend.rei.ego.trace_store import InMemoryEgoTraceStore
from app.backend.rei.engine import (
    ReiNativeEngine,
    _emocio_world_with_projection,
    _historical_context,
    _instinkt_history_inputs,
)
from app.backend.rei.evaluation.longitudinal_eval import (
    _InMemoryEvaluationArtifactStore,
)
from app.backend.rei.instinkt.association_memory import BoundedAssociativeMemory
from app.backend.rei.instinkt.packets import bind_instinkt_effects, build_instinkt_packet
from app.backend.rei.instinkt.processor import process_instinkt
from app.backend.rei.models.ego import InstinktBodyHistoryRef
from app.backend.rei.providers.deterministic import (
    build_deterministic_native_providers,
)
from app.backend.rei.providers.native import DeterministicExecutionClock
from tests.rei.test_ego_world_updates import _cycle_result


def _projection_fixture():
    result, store, visual_signal, body_signal = _cycle_result()
    bundles = {result.native_bundle.bundle_id: result.native_bundle}
    projections = derive_modality_projections(
        result.ego_trace,
        bundles,
        emocio_history=(visual_signal,),
        instinkt_history=(body_signal,),
    )
    return result, store, visual_signal, body_signal, projections


def test_measure_bound_signals_become_compact_epistemically_typed_refs() -> None:
    result, _, visual_signal, body_signal, projections = _projection_fixture()

    assert projections.emocio.image_artifact_ids == (
        visual_signal.bound_observation.image.image_id,
    )
    visual_ref = projections.emocio.visual_history[0]
    assert visual_ref.source_run_id == result.request.run_id
    assert visual_ref.source_measure_id == result.ego_measure.measure_id
    assert visual_ref.vector_hash == visual_signal.bound_observation.embedding.vector_hash
    assert visual_ref.epistemic_status == "internal_visual_hypothesis"
    assert visual_ref.external_evidence is False
    assert projections.emocio.embedding_feature_refs == (
        "visual_embedding_feature:"
        f"{visual_ref.observation_id}:{visual_ref.vector_hash}:"
        f"{visual_ref.dimensions}",
    )

    body_ref = projections.instinkt.body_history[0]
    assert body_ref.source_measure_id == result.ego_measure.measure_id
    assert body_ref.predicted_body_after_id == body_signal.predicted_body_after.body_state_id
    assert body_ref.epistemic_status == "predicted_rollout"
    assert body_ref.measured_body_after_id is None
    assert any(
        value.startswith("predicted_body_after:")
        for value in projections.instinkt.body_consequences
    )
    assert not any(
        value.startswith("measured_body_after:")
        for value in projections.instinkt.body_consequences
    )


def test_projection_history_changes_native_inputs_without_claiming_measurement() -> None:
    result, _, _, _, with_history = _projection_fixture()
    without_history = derive_modality_projections(
        result.ego_trace,
        {result.native_bundle.bundle_id: result.native_bundle},
    )

    assert with_history.emocio.projection_id != without_history.emocio.projection_id
    assert with_history.instinkt.projection_id != without_history.instinkt.projection_id
    projected_world = _emocio_world_with_projection(
        result.request.emocio_world,
        with_history,
    )
    assert with_history.emocio.image_artifact_ids[0] in projected_world.visual_memories
    assert (
        with_history.emocio.embedding_feature_refs[0]
        in projected_world.visual_memories
    )

    _, history_records = _instinkt_history_inputs(
        projection=with_history.instinkt,
        specs=result.request.instinkt_effect_specs,
    )
    assert any(
        getattr(item, "observation_kind", None) == "body_consequence"
        for item in history_records
    )


def test_predicted_recovery_history_has_bounded_native_effect_not_body_mutation() -> None:
    result, _, _, _, projections = _projection_fixture()
    active_specs, history_records = _instinkt_history_inputs(
        projection=projections.instinkt,
        specs=result.request.instinkt_effect_specs,
    )
    request = result.request
    packet = build_instinkt_packet(
        request.scene,
        request.body_state,
        physical_cues=request.instinkt_physical_cues,
        uncertainty_cues=request.instinkt_uncertainty_cues,
        trust_cues=request.instinkt_trust_cues,
        boundary_cues=request.instinkt_boundary_cues,
        attachment_cues=request.instinkt_attachment_cues,
        scarcity_cues=request.instinkt_scarcity_cues,
        escape_cues=request.instinkt_escape_cues,
        explicit_body_cues=request.instinkt_explicit_body_cues,
        evidence_ids=request.instinkt_evidence_ids,
        cue_evidence_bindings=request.instinkt_cue_evidence_bindings,
        previous_instinkt_projection_ids=(projections.instinkt.projection_id,),
        previous_instinkt_projection_hashes=(projections.instinkt.projection_hash,),
    )
    effects = bind_instinkt_effects(packet, active_specs)
    memory = BoundedAssociativeMemory()
    for record in history_records:
        memory.add(record)
    with_history = process_instinkt(
        scene=request.scene,
        packet=packet,
        source_body_state=request.body_state,
        option_effects=effects,
        config=request.instinkt_config,
        memory=memory,
    )
    without_history = process_instinkt(
        scene=request.scene,
        packet=packet,
        source_body_state=request.body_state,
        option_effects=effects,
        config=request.instinkt_config,
    )

    assert tuple(item.trajectory for item in with_history.rollouts) == tuple(
        item.trajectory for item in without_history.rollouts
    )
    assert tuple(item.recoverability for item in with_history.rollouts) != tuple(
        item.recoverability for item in without_history.rollouts
    )
    assert any(
        match.predicted_recoverability is not None
        for rollout in with_history.rollouts
        for match in rollout.association_matches
    )


def test_projection_boundary_rejects_forged_lineage_and_cold_storage_bytes() -> None:
    result, store, visual_signal, body_signal, _ = _projection_fixture()
    bundles = {result.native_bundle.bundle_id: result.native_bundle}
    forged = visual_signal.model_copy(update={"source_measure_id": "future_measure"})
    with pytest.raises((ValidationError, ValueError)):
        derive_modality_projections(
            result.ego_trace,
            bundles,
            emocio_history=(forged,),
            instinkt_history=(body_signal,),
        )

    forged_receipt = visual_signal.image_storage.model_copy(
        update={"run_id": "forged_run"}
    )
    payload = visual_signal.model_dump(mode="python", round_trip=True)
    payload["image_storage"] = forged_receipt
    with pytest.raises(ValidationError, match="StoredArtifact ID|storage_id"):
        type(visual_signal).model_validate(payload)

    store._content[visual_signal.image_storage.storage_id] = b"forged"  # noqa: SLF001
    with pytest.raises(ValueError, match="stored bytes|storage bytes"):
        _historical_context(
            trace=result.ego_trace,
            bundles=(result.native_bundle,),
            emocio_signals=(visual_signal,),
            instinkt_signals=(body_signal,),
            artifact_store=store,
            current_body_state=result.request.body_state,
            current_instinkt_world=result.request.instinkt_world,
            structural_character=result.request.character,
        )


def test_predicted_history_cannot_be_relabelled_as_measured() -> None:
    _, _, _, _, projections = _projection_fixture()
    predicted = projections.instinkt.body_history[0]
    payload = predicted.model_dump(mode="python", round_trip=True)
    payload["epistemic_status"] = "measured_outcome"
    with pytest.raises(ValidationError, match="complete outcome lineage"):
        InstinktBodyHistoryRef.model_validate(payload)


def test_same_current_cycle_with_sidecars_changes_bounded_native_semantics() -> None:
    first, store, visual_signal, body_signal = _cycle_result()
    request = first.request.model_copy(
        update={
            "run_id": "c6-sidecar-semantic-current-cycle",
            "historical_bundles": (first.native_bundle,),
            "historical_emocio_signals": (visual_signal,),
            "historical_instinkt_signals": (body_signal,),
            "started_at": first.request.started_at + timedelta(seconds=1),
        }
    )

    def trace_store() -> InMemoryEgoTraceStore:
        target = InMemoryEgoTraceStore()
        target.append_measure(first.request.ego_id, first.ego_measure)
        return target

    with_sidecars = ReiNativeEngine(
        artifact_store=store,
        ego_trace_store=trace_store(),
        providers=build_deterministic_native_providers(),
        clock=DeterministicExecutionClock(request.started_at),
    ).run_cycle(request)
    without_request = request.model_copy(
        update={
            "historical_emocio_signals": (),
            "historical_instinkt_signals": (),
        }
    )
    without_sidecars = ReiNativeEngine(
        artifact_store=_InMemoryEvaluationArtifactStore(),
        ego_trace_store=trace_store(),
        providers=build_deterministic_native_providers(),
        clock=DeterministicExecutionClock(without_request.started_at),
    ).run_cycle(without_request)

    assert with_sidecars.request.scene == without_sidecars.request.scene
    assert with_sidecars.request.character == without_sidecars.request.character
    assert (
        with_sidecars.request.historical_bundles
        == without_sidecars.request.historical_bundles
    )
    assert with_sidecars.prior_projections.emocio.embedding_feature_refs
    assert without_sidecars.prior_projections.emocio.embedding_feature_refs == ()
    with_novelty = next(
        item.score
        for item in with_sidecars.native_bundle.emocio.valuation_dimensions
        if item.name == "novelty"
    )
    without_novelty = next(
        item.score
        for item in without_sidecars.native_bundle.emocio.valuation_dimensions
        if item.name == "novelty"
    )
    assert with_novelty != without_novelty
    assert tuple(
        item.recoverability for item in with_sidecars.instinkt_execution.rollouts
    ) != tuple(
        item.recoverability for item in without_sidecars.instinkt_execution.rollouts
    )
