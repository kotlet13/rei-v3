from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.backend.rei.ids import content_id, sha256_hex
from app.backend.rei.instinkt.dynamics import simulate_option_rollout
from app.backend.rei.instinkt.effect_compiler import (
    compile_prediction_to_option_body_effect,
)
from app.backend.rei.instinkt.effect_mapper import RuleBasedEmbodiedCueInterpreter
from app.backend.rei.instinkt.outcome_learning import (
    ExecutedActionReceipt,
    GroundedOutcomeEvidence,
    InstinktOutcomeLearningTrace,
    InstinktOutcomeObservation,
    InstinktOutcomeUpdate,
    NormalizedBodyMeasurement,
)
from app.backend.rei.instinkt.packets import build_instinkt_packet
from app.backend.rei.models.ego import OutcomeRecord
from app.backend.rei.models.instinkt import (
    BodyState,
    InstinktCueEvidenceBinding,
    InstinktCueEvidenceCitation,
    InstinktSimulationConfig,
    InstinktWorld,
)
from app.backend.rei.models.scene import DecisionOption, EvidenceItem, SceneEvent


RUN_FINISHED = datetime(2026, 7, 14, 19, 0, tzinfo=UTC)
ACTION_EXECUTED = RUN_FINISHED + timedelta(minutes=5)
EVIDENCE_OBSERVED = RUN_FINISHED + timedelta(minutes=30)
OUTCOME_RECORDED = RUN_FINISHED + timedelta(hours=1)
ADMITTED = OUTCOME_RECORDED + timedelta(minutes=1)
MANIFEST_HASH = "a" * 64
BEHAVIOR_HASH = "b" * 64


def _body(identifier: str = "body_before", *, tension: float = 0.3) -> BodyState:
    return BodyState(
        body_state_id=identifier,
        energy=0.7,
        fatigue=0.2,
        pain=0.0,
        arousal=0.3,
        tension=tension,
        physical_integrity=1.0,
        uncertainty=0.3,
        trust=0.6,
        attachment_security=0.7,
        resource_security=0.7,
        boundary_integrity=0.8,
        escape_availability=0.8,
        predictability=0.6,
    )


def _prediction(*, body: BodyState | None = None):
    option = DecisionOption(
        option_id="leave_area",
        label="leave",
        description="Leave and avoid the physical threat.",
    )
    evidence = EvidenceItem(
        evidence_id="scene_threat",
        modality="text",
        content="A physical threat and immediate danger are visibly present.",
        grounded=True,
        source_ref="fixture:c5-scene",
        confidence=1.0,
    )
    scene = SceneEvent(
        event_id="event_threat",
        raw_input="A bounded synthetic threat fixture.",
        language="en",
        evidence=(evidence,),
        options=(option,),
        actors=("self",),
    )
    source_body = body or _body()
    world = InstinktWorld.create()
    cue_start = evidence.content.casefold().index("physical threat")
    citation = InstinktCueEvidenceCitation.create(
        evidence=evidence,
        start_char=cue_start,
        end_char=cue_start + len("physical threat"),
    )
    binding = InstinktCueEvidenceBinding.create(
        lane="physical_cues",
        cue_class="physical_threat",
        cue="physical threat danger",
        assertion_status="asserted_positive",
        citations=(citation,),
    )
    packet = build_instinkt_packet(
        scene,
        source_body,
        physical_cues=("physical threat danger",),
        evidence_ids=(evidence.evidence_id,),
        cue_evidence_bindings=(binding,),
    )
    mapper = RuleBasedEmbodiedCueInterpreter()
    prediction = mapper.infer_effects(scene, packet, world, source_body, option)
    assert not prediction.abstains
    compilation = compile_prediction_to_option_body_effect(
        prediction=prediction,
        scene=scene,
        packet=packet,
        world=world,
        body=source_body,
        option=option,
        ruleset=mapper.ruleset,
    )
    config = InstinktSimulationConfig.create()
    rollout = simulate_option_rollout(
        packet=packet,
        source_body_state=source_body,
        effect=compilation.option_body_effect,
        config=config,
    )
    return mapper, prediction, rollout, world, source_body, scene


def _receipt(scene: SceneEvent) -> ExecutedActionReceipt:
    base = {
        "schema_version": "rei-native-executed-action-receipt-v1",
        "source_run_id": "completed_rule_run",
        "source_manifest_id": "completed_manifest",
        "source_manifest_hash": MANIFEST_HASH,
        "source_run_finished_at": RUN_FINISHED,
        "source_scene_id": scene.event_id,
        "source_scene_hash": scene.scene_hash(),
        "source_behavior_resultant_id": "executed_behavior",
        "source_behavior_resultant_hash": BEHAVIOR_HASH,
        "executed_option_id": "leave_area",
        "executor_kind": "external_executor",
        "executed_at": ACTION_EXECUTED,
    }
    receipt_id = content_id("executed_action_receipt", base)
    payload = {"receipt_id": receipt_id, **base}
    return ExecutedActionReceipt(**payload, receipt_hash=sha256_hex(payload))


def _outcome_evidence(
    *,
    evidence_id: str = "postrun_body_sensor",
    observed_at: datetime = EVIDENCE_OBSERVED,
) -> tuple[GroundedOutcomeEvidence, ...]:
    return (
        GroundedOutcomeEvidence(
            evidence=EvidenceItem(
                evidence_id=evidence_id,
                modality="body",
                content="A normalized post-action tension measurement was recorded.",
                grounded=True,
                source_ref="outcome-sensor:c5",
                confidence=0.9,
            ),
            observed_at=observed_at,
        ),
    )


def _observation(
    *,
    scene: SceneEvent,
    body: BodyState,
    after_tension: float = 0.5,
    status: str = "measured_change",
    outcome_id: str = "opaque_outcome_id",
) -> InstinktOutcomeObservation:
    receipt = _receipt(scene)
    evidence = _outcome_evidence()
    measurement = NormalizedBodyMeasurement.create(
        action_receipt=receipt,
        body_before=body,
        dimension="tension",
        status=status,
        after_value=after_tension,
        evidence=evidence,
    )
    record = OutcomeRecord(
        outcome_id=outcome_id,
        event_id=scene.event_id,
        recorded_at=OUTCOME_RECORDED,
        source="external_observation",
        observed_effects=("A normalized measurement was observed.",),
        evidence_ids=("postrun_body_sensor",),
    )
    return InstinktOutcomeObservation.create(
        scene=scene,
        body_before=body,
        action_receipt=receipt,
        outcome_record=record,
        measurements=(measurement,),
        outcome_evidence=evidence,
        uncertainty="Normalized state only; no medical inference.",
        admitted_at=ADMITTED,
    ).validate_against(
        scene=scene,
        body_before=body,
        action_receipt=receipt,
        outcome_record=record,
    )


def _update(*, body: BodyState | None = None, no_change: bool = False):
    mapper, prediction, rollout, world, source_body, scene = _prediction(body=body)
    observation = _observation(
        scene=scene,
        body=source_body,
        after_tension=source_body.tension if no_change else min(1.0, source_body.tension + 0.2),
        status="measured_no_change" if no_change else "measured_change",
    )
    update = InstinktOutcomeUpdate.create(
        ego_id="ego_c5_learning",
        prediction=prediction,
        rollout=rollout,
        outcome=observation,
        ruleset=mapper.ruleset,
        world=world,
        body_before=source_body,
    )
    return mapper, prediction, rollout, world, source_body, observation, update


def test_outcome_update_is_append_only_and_uses_typed_actual_outcome() -> None:
    mapper, prediction, rollout, world, body, observation, update = _update()
    before = InstinktOutcomeLearningTrace.empty(ego_id="ego_c5_learning")
    before_bytes = before.canonical_json_bytes()
    after = before.append(update)
    assert before.updates == ()
    assert before.canonical_json_bytes() == before_bytes
    assert after.updates == (update,)
    assert update.learned_association.association_id in update.world_after.associations
    assert update.body_after.tension == pytest.approx(0.5)
    assert tuple(item.dimension for item in update.residuals) == ("tension",)
    update.validate_against(
        ego_id="ego_c5_learning",
        prediction=prediction,
        rollout=rollout,
        outcome=observation,
        ruleset=mapper.ruleset,
        world=world,
        body_before=body,
    )


def test_evidence_backed_measured_no_change_is_allowed() -> None:
    *_, body, observation, update = _update(no_change=True)
    assert observation.measurements[0].status == "measured_no_change"
    assert observation.measurements[0].delta == 0.0
    assert update.residuals[0].observed_delta == 0.0
    assert update.body_after.tension == body.tension


def test_measurement_rejects_arbitrary_sign_with_unchanged_evidence_hash() -> None:
    _, _, _, _, body, scene = _prediction()
    receipt = _receipt(scene)
    evidence = _outcome_evidence()
    positive = NormalizedBodyMeasurement.create(
        action_receipt=receipt,
        body_before=body,
        dimension="tension",
        status="measured_change",
        after_value=0.5,
        evidence=evidence,
    )
    tampered = positive.model_dump(mode="python", round_trip=True)
    tampered["after_value"] = 0.1
    with pytest.raises(ValidationError, match="measurement_id|measurement_hash"):
        NormalizedBodyMeasurement.model_validate(tampered)


def test_observation_rejects_non_post_action_or_future_evidence() -> None:
    _, _, _, _, body, scene = _prediction()
    receipt = _receipt(scene)
    early = _outcome_evidence(observed_at=RUN_FINISHED)
    measurement = NormalizedBodyMeasurement.create(
        action_receipt=receipt,
        body_before=body,
        dimension="tension",
        status="measured_change",
        after_value=0.5,
        evidence=early,
    )
    record = OutcomeRecord(
        outcome_id="early_outcome",
        event_id=scene.event_id,
        recorded_at=OUTCOME_RECORDED,
        source="external_observation",
        evidence_ids=("postrun_body_sensor",),
    )
    with pytest.raises(ValidationError, match="follow execution"):
        InstinktOutcomeObservation.create(
            scene=scene,
            body_before=body,
            action_receipt=receipt,
            outcome_record=record,
            measurements=(measurement,),
            outcome_evidence=early,
            uncertainty="Must fail.",
            admitted_at=ADMITTED,
        )


def test_self_consistent_update_tamper_requires_external_replay_to_detect() -> None:
    mapper, prediction, rollout, world, body, observation, update = _update()
    base = update.model_dump(
        mode="python", round_trip=True, exclude={"update_id", "update_hash"}
    )
    base["body_after"]["tension"] = 0.99
    base["body_after"]["body_state_id"] = "forged_body"
    update_id = content_id("instinkt_outcome_update", base)
    payload = {"update_id": update_id, **base}
    forged = InstinktOutcomeUpdate.model_validate(
        {**payload, "update_hash": sha256_hex(payload)}
    )
    InstinktOutcomeLearningTrace.create(
        ego_id="ego_c5_learning", updates=(forged,)
    )
    with pytest.raises(ValueError, match="deterministic source replay"):
        forged.validate_against(
            ego_id="ego_c5_learning",
            prediction=prediction,
            rollout=rollout,
            outcome=observation,
            ruleset=mapper.ruleset,
            world=world,
            body_before=body,
        )
