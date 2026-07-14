from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.ego.trace_store import InMemoryEgoTraceStore
from app.backend.rei.ego.world_updates import (
    EmocioLongitudinalVisualSignal,
    EmocioWorldUpdate,
    EmocioWorldUpdater,
    InstinktLongitudinalBodySignal,
    InstinktWorldUpdate,
    InstinktWorldUpdater,
    RacioWorldUpdate,
    RacioWorldUpdater,
)
from app.backend.rei.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei.evaluation.longitudinal_eval import (
    _InMemoryEvaluationArtifactStore,
    _materialize_visual_signal,
)
from app.backend.rei.ids import content_id, sha256_hex
from app.backend.rei.models.emocio import EmocioWorld
from app.backend.rei.models.instinkt import InstinktWorld
from app.backend.rei.models.racio import RacioWorld
from app.backend.rei.providers.deterministic import build_deterministic_native_providers
from app.backend.rei.providers.native import DeterministicExecutionClock
from tests.rei.test_ego import _trace


ROOT = Path(__file__).resolve().parents[2]


def _cycle_result():
    request = ReiNativeCycleRequest.model_validate_json(
        (ROOT / "tests/fixtures/native_cycles/deterministic_e2e.json").read_bytes()
    )
    store = _InMemoryEvaluationArtifactStore()
    result = ReiNativeEngine(
        artifact_store=store,
        ego_trace_store=InMemoryEgoTraceStore(),
        providers=build_deterministic_native_providers(),
        clock=DeterministicExecutionClock(request.started_at),
    ).run_cycle(request)
    visual_signal = _materialize_visual_signal(
        result=result,
        artifact_store=store,
        evaluation_seed=0,
    )
    rollout = next(
        item
        for item in result.instinkt_execution.rollouts
        if item.rollout_id == result.native_bundle.instinkt.decisive_rollout_id
    )
    body_signal = InstinktLongitudinalBodySignal.create(
        measure=result.ego_measure,
        bundle=result.native_bundle,
        rollout=rollout,
    )
    return result, store, visual_signal, body_signal


def _source_worlds() -> tuple[RacioWorld, EmocioWorld, InstinktWorld]:
    return (
        RacioWorld(
            world_id="source_racio_world",
            explicit_beliefs=("existing belief",),
            facts=("existing fact",),
            rules=("existing rule",),
            timelines=("existing event",),
            commitments=("existing commitment",),
        ),
        EmocioWorld(
            world_id="source_emocio_world",
            visual_memories=("existing scene",),
            desired_scenes=("existing desire",),
            broken_scenes=("existing obstacle",),
            social_identity_motifs=("existing social motif",),
            attraction_patterns=("existing attraction",),
            motor_patterns=("existing motor pattern",),
        ),
        InstinktWorld.create(
            associations=("existing association",),
            trusted_patterns=("existing trust",),
            threat_patterns=("existing threat",),
            attachment_objects=("existing attachment",),
            unresolved_losses=("existing loss",),
            boundary_patterns=("existing boundary",),
        ),
    )


def test_world_updates_are_modality_specific_replayable_and_content_addressed() -> None:
    result, store, visual_signal, body_signal = _cycle_result()
    measure = result.ego_measure
    bundle = result.native_bundle
    racio_world, emocio_world, instinkt_world = _source_worlds()

    updates = (
        RacioWorldUpdater().update(
            racio_world, measure, bundle, result.narrative
        ),
        EmocioWorldUpdater().update(
            emocio_world, measure, bundle, visual_signal, store
        ),
        InstinktWorldUpdater().update(
            instinkt_world, measure, bundle, body_signal
        ),
    )
    replay = (
        RacioWorldUpdater().update(
            racio_world, measure, bundle, result.narrative
        ),
        EmocioWorldUpdater().update(
            emocio_world, measure, bundle, visual_signal, store
        ),
        InstinktWorldUpdater().update(
            instinkt_world, measure, bundle, body_signal
        ),
    )

    assert updates == replay
    assert updates[0].updated_world.facts == (
        "existing fact",
        *bundle.racio.facts_used,
    )
    assert updates[0].updated_world.timelines[-1] == f"event:{measure.event_id}"
    assert updates[1].visual_memory_additions == (
        visual_signal.world_memory_reference,
    )
    assert updates[1].visual_signal.bound_observation.image.image_id
    assert updates[1].visual_signal.bound_observation.embedding.vector_hash
    expected_social_positions = visual_signal.social_position_references
    assert updates[1].social_identity_motif_additions == expected_social_positions
    assert set(expected_social_positions).issubset(
        updates[1].updated_world.social_identity_motifs
    )
    assert (
        bundle.instinkt.dominant_alarm
        in updates[2].updated_world.threat_patterns
    )
    assert updates[2].association_additions == ()
    assert updates[2].updated_world.associations == instinkt_world.associations
    assert updates[2].trusted_pattern_additions == ()
    assert updates[2].updated_world.trusted_patterns == instinkt_world.trusted_patterns
    assert updates[2].predicted_body_after == body_signal.predicted_body_after
    assert updates[2].predicted_body_after.trust == body_signal.predicted_body_after.trust
    assert body_signal.selected_rollout.predicted_loss >= 0.0
    assert body_signal.selected_rollout.trust_outcome
    assert body_signal.selected_rollout.association_match_ids == tuple(
        match.match_id for match in body_signal.selected_rollout.association_matches
    )
    assert updates[2].measured_body_after is None
    assert updates[2].recovery_pattern_additions == (
        body_signal.recovery_reference,
    )
    assert body_signal.recovery_reference.startswith("predicted_recoverability:")
    assert updates[0].self_narrative_additions[0].startswith("self_narrative:")
    assert racio_world.facts == ("existing fact",)
    assert emocio_world.visual_memories == ("existing scene",)
    assert instinkt_world.threat_patterns == ("existing threat",)

    for update in updates:
        assert "summary" not in type(update).model_fields
        assert all("summary" not in name for name in type(update).model_fields)
        assert type(update).model_validate_json(update.model_dump_json()) == update


def test_world_update_rejects_semantic_tampering_and_cross_cycle_lineage() -> None:
    result, store, visual_signal, body_signal = _cycle_result()
    first = result.ego_measure
    first_bundle = result.native_bundle
    racio_world, emocio_world, _ = _source_worlds()

    update = RacioWorldUpdater().update(
        racio_world, first, first_bundle, result.narrative
    )
    payload = update.model_dump(mode="python", round_trip=True)
    payload["fact_additions"] = ("fabricated fact",)
    with pytest.raises(ValidationError, match="deterministic modality replay"):
        RacioWorldUpdate.model_validate(payload)

    emocio_update = EmocioWorldUpdater().update(
        emocio_world,
        first,
        first_bundle,
        visual_signal,
        store,
    )
    payload = emocio_update.model_dump(mode="python", round_trip=True)
    payload["updated_world"]["desired_scenes"] = ("fabricated desire",)
    with pytest.raises(ValidationError, match="deterministic modality replay"):
        EmocioWorldUpdate.model_validate(payload)

    wrong_bundle = first_bundle.model_copy(update={"bundle_id": "other_bundle"})
    with pytest.raises(ValidationError, match="bundle_id"):
        RacioWorldUpdater().update(
            racio_world, first, wrong_bundle, result.narrative
        )

    stale_measure = first.model_copy(update={"event_id": "stale_event"})
    with pytest.raises(ValidationError, match="measure_id"):
        InstinktWorldUpdater().update(
            _source_worlds()[2], stale_measure, first_bundle, body_signal
        )


def test_world_update_delta_fields_do_not_cross_modality_ownership() -> None:
    update_fields = {
        "racio": set(RacioWorldUpdate.model_fields),
        "emocio": set(EmocioWorldUpdate.model_fields),
        "instinkt": set(InstinktWorldUpdate.model_fields),
    }
    assert "visual_memory_additions" not in update_fields["racio"]
    assert "threat_pattern_additions" not in update_fields["racio"]
    assert "fact_additions" not in update_fields["emocio"]
    assert "fact_additions" not in update_fields["instinkt"]
    assert "visual_memory_additions" not in update_fields["instinkt"]


def test_visual_signal_rejects_vector_mutation_and_forged_storage_receipt() -> None:
    result, store, visual_signal, _ = _cycle_result()
    payload = visual_signal.model_dump(mode="python", round_trip=True)
    payload["embedding_vector"] = (
        0.0,
        *payload["embedding_vector"][1:],
    )
    with pytest.raises(ValidationError, match="vector|L2"):
        EmocioLongitudinalVisualSignal.model_validate(payload)

    base = visual_signal.model_dump(
        mode="python", round_trip=True, exclude={"signal_id", "signal_hash"}
    )
    base["image_storage"]["storage_id"] = "forged_storage_receipt"
    signal_id = content_id("c6_emocio_visual_signal", base)
    envelope = {"signal_id": signal_id, **base}
    with pytest.raises(ValidationError, match="StoredArtifact ID"):
        EmocioLongitudinalVisualSignal.model_validate(
            {**envelope, "signal_hash": sha256_hex(envelope)}
        )

    forged_run = visual_signal.model_dump(
        mode="python", round_trip=True, exclude={"signal_id", "signal_hash"}
    )
    forged_run["source_run_id"] = "forged_run"
    forged_run["image_storage"]["run_id"] = "forged_run"
    forged_run["embedding_storage"]["run_id"] = "forged_run"
    signal_id = content_id("c6_emocio_visual_signal", forged_run)
    envelope = {"signal_id": signal_id, **forged_run}
    with pytest.raises(ValidationError, match="StoredArtifact ID"):
        EmocioLongitudinalVisualSignal.model_validate(
            {**envelope, "signal_hash": sha256_hex(envelope)}
        )


def test_c6_v1_measured_body_signal_fails_closed_without_c5_replay_context() -> None:
    from tests.rei.test_instinkt_outcome_learning import _update

    result, _, _, _ = _cycle_result()
    rollout = next(
        item
        for item in result.instinkt_execution.rollouts
        if item.rollout_id == result.native_bundle.instinkt.decisive_rollout_id
    )
    measured_update = _update()[-1]
    with pytest.raises(ValueError, match="full C5 replay context"):
        InstinktLongitudinalBodySignal.create(
            measure=result.ego_measure,
            bundle=result.native_bundle,
            rollout=rollout,
            measured_outcome_update=measured_update,
        )
