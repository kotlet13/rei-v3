from __future__ import annotations

import inspect
import socket
import subprocess
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.backend.rei_next.communication.conscious_view import (
    build_observable_manifestation_view,
    build_racio_interpreter_request,
)
from app.backend.rei_next.communication.acceptance import (
    assess_acceptance_fidelity,
    validate_acceptance_fidelity_replay,
)
from app.backend.rei_next.communication.interpreter import (
    DeterministicRacioInterpreter,
    RacioInterpreter,
    ScriptedRacioInterpreter,
    validate_interpretation_replay,
)
from app.backend.rei_next.communication.fake_vlm import (
    EmocioVlmEnrichment,
    FakeVisionLanguageInterpreter,
    build_emocio_vlm_request,
)
from app.backend.rei_next.communication.manifestations import (
    build_emocio_manifestation,
)
from app.backend.rei_next.communication.processor import (
    interpret_manifestations,
    process_communication,
)
from app.backend.rei_next.communication.translation_gap import (
    evaluate_translation_gap,
    validate_translation_gap_replay,
)
from app.backend.rei_next.ids import content_id, sha256_hex
from app.backend.rei_next.instinkt import build_instinkt_manifestation
from app.backend.rei_next.models.communication import (
    AcceptanceFidelityAssessment,
    AcceptanceState,
    B9_EXACT_DISTORTION_POLICY,
    CommunicationArtifactRef,
    DirectedMindRelation,
    EmocioManifestation,
    FidelityComponent,
    ManifestationObservation,
    RacioInterpretation,
    RacioInterpreterRequest,
    TranslationGap,
)
from app.backend.rei_next.models.emocio import (
    EMOCIO_VALUATION_DIMENSIONS,
    EmocioNativeConclusion,
    ImageArtifact,
    ValuationDimension,
)
from app.backend.rei_next.models.instinkt import BodyState, InstinktNativeConclusion
from app.backend.rei_next.models.provider import (
    ProviderCallSpec,
    ProviderFallbackPolicy,
)
from tests.rei_next.test_domain_models import _native_bundle


HIDDEN_MOTIVE_CANARY = "HIDDEN_NATIVE_MOTIVE_CANARY_DO_NOT_DISCLOSE"


def _relation(
    *,
    visibility: float = 1.0,
    interpretation_fidelity: float = 1.0,
) -> DirectedMindRelation:
    return DirectedMindRelation(
        visibility=visibility,
        interpretation_fidelity=interpretation_fidelity,
        tolerance=0.5,
        delegation_willingness=0.5,
        sabotage_risk=0.0,
    )


def _acceptance(
    *,
    acceptance_state_id: str = "acceptance_b9",
    r_to_e_visibility: float = 1.0,
    r_to_e_fidelity: float = 1.0,
    r_to_i_visibility: float = 1.0,
    r_to_i_fidelity: float = 1.0,
) -> AcceptanceState:
    neutral = _relation(visibility=0.25, interpretation_fidelity=0.25)
    return AcceptanceState(
        acceptance_state_id=acceptance_state_id,
        R_to_E=_relation(
            visibility=r_to_e_visibility,
            interpretation_fidelity=r_to_e_fidelity,
        ),
        R_to_I=_relation(
            visibility=r_to_i_visibility,
            interpretation_fidelity=r_to_i_fidelity,
        ),
        E_to_R=neutral,
        E_to_I=neutral,
        I_to_R=neutral,
        I_to_E=neutral,
        overall_mode="mixed",
    )


def _emocio_conclusion(
    *,
    conclusion_id: str = "emocio_conclusion_b9",
    option_id: str = "option_native",
    action_tendency: str = "approach",
    desired_transformation: str = "move toward a bounded desired state",
    main_obstacle: str = "explicit obstacle",
) -> EmocioNativeConclusion:
    return EmocioNativeConclusion(
        conclusion_id=conclusion_id,
        source_packet_id="emocio_packet_b9",
        source_scene_id="event_b9",
        option_id=option_id,
        desired_transformation=desired_transformation,
        current_scene_id="visual_current_b9",
        desired_scene_id="visual_desired_b9",
        decisive_rollout_scene_id="visual_rollout_b9",
        main_obstacle=main_obstacle,
        action_tendency=action_tendency,
        valuation_dimensions=tuple(
            ValuationDimension(name=name, score=0.5)
            for name in EMOCIO_VALUATION_DIMENSIONS
        ),
        intensity=0.8,
        uncertainty="bounded fixture uncertainty",
    )


def _body_state() -> BodyState:
    return BodyState(
        body_state_id="body_state_b9",
        energy=0.7,
        fatigue=0.3,
        pain=0.0,
        arousal=0.4,
        tension=0.6,
        physical_integrity=1.0,
        uncertainty=0.4,
        trust=0.5,
        attachment_security=0.5,
        resource_security=0.7,
        boundary_integrity=0.8,
        escape_availability=0.9,
        predictability=0.5,
    )


def _image_artifact(image_id: str = "image_b9") -> ImageArtifact:
    return ImageArtifact(
        image_id=image_id,
        request_id="render_request_b9",
        render_call_id="render_call_b9",
        source_spec_id="visual_current_b9",
        provider_id="fixture_renderer",
        seed=17,
        input_spec_hash="a" * 64,
        content_sha256="b" * 64,
        media_type="image/png",
        prompt="presentation-only fixture prompt",
        negative_prompt="",
        path=f"emocio/images/{image_id}.png",
        width=64,
        height=64,
        generated_only_elements=(),
    )


def _instinkt_conclusion() -> InstinktNativeConclusion:
    return InstinktNativeConclusion(
        conclusion_id="instinkt_conclusion_b9",
        source_packet_id="instinkt_packet_b9",
        source_scene_id="event_b9",
        source_body_state_id="body_state_b9",
        option_id=None,
        dominant_alarm="bounded alarm",
        danger_claims=("explicit danger claim",),
        protected_targets=("boundary",),
        action_tendency="maintain",
        minimum_safety_condition="preserve a reversible exit",
        decisive_rollout_id=None,
        decisive_rollout_option_id=None,
        intensity=0.6,
        abstains=True,
        uncertainty="bounded fixture uncertainty",
    )


def _emocio_request(
    *,
    conclusion: EmocioNativeConclusion | None = None,
    acceptance_state: AcceptanceState | None = None,
    allowed_option_ids: tuple[str, ...] = ("option_native", "option_wrong"),
) -> tuple[EmocioNativeConclusion, EmocioManifestation, RacioInterpreterRequest]:
    native = conclusion or _emocio_conclusion()
    acceptance = acceptance_state or _acceptance()
    manifestation = build_emocio_manifestation(conclusion=native)
    request = build_racio_interpreter_request(
        manifestations=(manifestation,),
        allowed_option_ids=allowed_option_ids,
        acceptance_state=acceptance,
    )
    return native, manifestation, request


def _rehashed_artifact_payload(
    artifact: BaseModel,
    *,
    id_field: str,
    hash_field: str,
    id_prefix: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    base = artifact.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, hash_field},
    )
    base.update(updates)
    artifact_id = content_id(id_prefix, base)
    payload = {id_field: artifact_id, **base}
    return {**payload, hash_field: sha256_hex(payload)}


def test_racio_interpreter_boundary_excludes_native_ground_truth_and_hidden_canary() -> None:
    conclusion = _emocio_conclusion(
        desired_transformation=HIDDEN_MOTIVE_CANARY,
        main_obstacle=f"obstacle::{HIDDEN_MOTIVE_CANARY}",
    )
    _, manifestation, request = _emocio_request(conclusion=conclusion)

    forbidden_fields = {
        "native_bundle",
        "native_conclusion",
        "governance_mandate",
        "hidden_native_motive",
        "hidden_native_motives",
        "translation_gap",
    }
    assert forbidden_fields.isdisjoint(RacioInterpreterRequest.model_fields)
    assert tuple(inspect.signature(RacioInterpreter.interpret).parameters) == (
        "self",
        "request",
    )
    request_json = request.model_dump_json()
    assert HIDDEN_MOTIVE_CANARY not in request_json
    assert conclusion.desired_transformation not in request_json
    assert conclusion.main_obstacle not in request_json

    interpretation = DeterministicRacioInterpreter().interpret(request)
    assert HIDDEN_MOTIVE_CANARY not in interpretation.model_dump_json()
    interpretation.validate_against((manifestation,))

    diagnostic_gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )
    assert diagnostic_gap.native_motive_summary == HIDDEN_MOTIVE_CANARY
    assert HIDDEN_MOTIVE_CANARY in diagnostic_gap.model_dump_json()

    injected = request.model_dump(mode="python", round_trip=True)
    injected["hidden_native_motive"] = HIDDEN_MOTIVE_CANARY
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RacioInterpreterRequest.model_validate(injected)


def test_unverified_free_text_cannot_enter_a_b9_interpretation_as_manifested() -> None:
    _, _, request = _emocio_request()
    injected = ManifestationObservation(
        manifestation_id=request.observable_views[0].manifestation_id,
        content=HIDDEN_MOTIVE_CANARY,
        provenance="manifested",
    )

    assert injected.observation_status == "unverified_contract"
    with pytest.raises(ValidationError, match="only structured observations"):
        RacioInterpretation.create_b9(
            request=request,
            status="interpreted_b9",
            observations=(injected,),
            inferred_option_id=None,
            inferred_action_tendency=None,
            inferred_motive="injected",
            confidence=0.1,
            alternative_hypotheses=(),
            interpreter_id="adversarial_fixture",
            interpreter_revision="1",
            interpreter_policy="attempted_hidden_motive_injection",
        )

    motor_observation = next(
        observation
        for observation in request.observable_views[0].observations
        if observation.signal_name == "motor_urge"
    )
    canary_json = f'"{HIDDEN_MOTIVE_CANARY}"'
    with pytest.raises(ValidationError, match="typed tendency code"):
        ManifestationObservation(
            **_rehashed_artifact_payload(
                motor_observation,
                id_field="observation_id",
                hash_field="observation_hash",
                id_prefix="manifestation_observation",
                updates={
                    "content": f"motor_urge={canary_json}",
                    "canonical_json_value": canary_json,
                },
            )
        )


def test_emocio_manifestation_is_content_addressed_and_replays_native_lineage() -> None:
    conclusion = _emocio_conclusion()
    manifestation = build_emocio_manifestation(conclusion=conclusion)

    assert manifestation.source_conclusion_hash == conclusion.content_hash()
    assert manifestation.manifestation_hash == manifestation.content_hash(
        exclude_fields=frozenset({"manifestation_hash"})
    )
    manifestation.validate_against(conclusion)

    tampered = EmocioManifestation(
        **_rehashed_artifact_payload(
            manifestation,
            id_field="manifestation_id",
            hash_field="manifestation_hash",
            id_prefix="emocio_manifestation",
            updates={"motor_urge": "structured_tendency:attack"},
        )
    )
    with pytest.raises(ValueError, match="motor_urge does not replay"):
        tampered.validate_against(conclusion)

    same_id_foreign_content = _emocio_conclusion(
        desired_transformation="foreign native motive",
    )
    with pytest.raises(ValueError, match="conclusion hash differs"):
        manifestation.validate_against(same_id_foreign_content)


def test_request_and_interpretation_close_exact_manifestation_hash_scope() -> None:
    native, manifestation, request = _emocio_request()
    interpreter = DeterministicRacioInterpreter()
    interpretation = interpreter.interpret(request)

    request.validate_against(
        manifestations=(manifestation,),
        acceptance_state=_acceptance(),
    )
    interpretation.validate_against_request(request)
    interpretation.validate_against((manifestation,))
    validate_interpretation_replay(
        interpreter=interpreter,
        request=request,
        interpretation=interpretation,
    )

    foreign_manifestation = build_emocio_manifestation(
        conclusion=_emocio_conclusion(
            conclusion_id="foreign_emocio_conclusion_b9",
            desired_transformation="foreign motive",
        )
    )
    with pytest.raises(ValueError, match="exactly match request views"):
        request.validate_against(
            manifestations=(foreign_manifestation,),
            acceptance_state=_acceptance(),
        )
    with pytest.raises(ValueError, match="another AcceptanceState"):
        request.validate_against(
            manifestations=(manifestation,),
            acceptance_state=_acceptance(
                acceptance_state_id="foreign_acceptance_b9",
                r_to_e_fidelity=0.2,
            ),
        )
    with pytest.raises(ValueError, match="exactly match the interpretation scope"):
        interpretation.validate_against((foreign_manifestation,))

    tampered_interpretation = RacioInterpretation(
        **_rehashed_artifact_payload(
            interpretation,
            id_field="interpretation_id",
            hash_field="interpretation_hash",
            id_prefix="racio_interpretation",
            updates={"inferred_motive": f"tampered::{native.desired_transformation}"},
        )
    )
    with pytest.raises(ValueError, match="differs from deterministic replay"):
        validate_interpretation_replay(
            interpreter=interpreter,
            request=request,
            interpretation=tampered_interpretation,
        )


def test_request_uses_only_the_directed_racio_to_source_relation() -> None:
    acceptance = _acceptance(
        r_to_e_visibility=0.8,
        r_to_e_fidelity=0.7,
        r_to_i_visibility=0.6,
        r_to_i_fidelity=0.2,
    )
    _, _, emocio_request = _emocio_request(acceptance_state=acceptance)

    body = _body_state()
    instinkt = _instinkt_conclusion()
    instinkt_manifestation = build_instinkt_manifestation(
        conclusion=instinkt,
        body_state=body,
    )
    instinkt_request = build_racio_interpreter_request(
        manifestations=(instinkt_manifestation,),
        allowed_option_ids=("option_native",),
        acceptance_state=acceptance,
    )

    assert emocio_request.relation_direction == "R_to_E"
    assert emocio_request.relation == acceptance.R_to_E
    assert instinkt_request.relation_direction == "R_to_I"
    assert instinkt_request.relation == acceptance.R_to_I
    assert emocio_request.relation != acceptance.E_to_R
    assert instinkt_request.relation != acceptance.I_to_R


def test_acceptance_is_explicit_and_not_inferred_from_native_keywords() -> None:
    acceptance = _acceptance(r_to_e_fidelity=0.4)
    accepting_words = _emocio_conclusion(
        conclusion_id="emocio_accepting_words",
        desired_transformation="accepting high fidelity fully delegated",
        main_obstacle="tolerant and visible",
    )
    rejecting_words = _emocio_conclusion(
        conclusion_id="emocio_rejecting_words",
        desired_transformation="reject sabotage conflicted hidden",
        main_obstacle="intolerant and unavailable",
    )
    _, accepting_manifestation, accepting_request = _emocio_request(
        conclusion=accepting_words,
        acceptance_state=acceptance,
    )
    _, rejecting_manifestation, rejecting_request = _emocio_request(
        conclusion=rejecting_words,
        acceptance_state=acceptance,
    )
    interpreter = DeterministicRacioInterpreter()
    accepting_interpretation = interpreter.interpret(accepting_request)
    rejecting_interpretation = interpreter.interpret(rejecting_request)
    accepting_gap = evaluate_translation_gap(
        conclusion=accepting_words,
        manifestations=(accepting_manifestation,),
        interpretation=accepting_interpretation,
    )
    rejecting_gap = evaluate_translation_gap(
        conclusion=rejecting_words,
        manifestations=(rejecting_manifestation,),
        interpretation=rejecting_interpretation,
    )

    assert accepting_request.relation == rejecting_request.relation == acceptance.R_to_E
    assert accepting_request.relation.interpretation_fidelity == 0.4
    assert accepting_interpretation.inferred_action_tendency == "approach"
    assert rejecting_interpretation.inferred_action_tendency == "approach"
    assert accepting_gap.motive_fidelity == rejecting_gap.motive_fidelity == 1.0
    assert accepting_gap.distortion_type == rejecting_gap.distortion_type


def test_no_provider_path_returns_structured_option_abstention_without_external_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("provider, process, or network call is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden_call)
    monkeypatch.setattr(subprocess, "Popen", forbidden_call)
    monkeypatch.setattr(subprocess, "run", forbidden_call)

    acceptance = _acceptance(r_to_e_visibility=0.0, r_to_e_fidelity=1.0)
    conclusion, manifestation, request = _emocio_request(
        acceptance_state=acceptance
    )
    interpreter = DeterministicRacioInterpreter()

    assert "provider" not in inspect.signature(DeterministicRacioInterpreter).parameters
    assert "model" not in inspect.signature(DeterministicRacioInterpreter).parameters
    interpretation = interpreter.interpret(request)

    assert interpretation.interpretation_status == "interpreted_b9"
    assert interpretation.observed_manifestations
    assert interpretation.supporting_observation_ids
    assert interpretation.inferred_option_id is None
    assert interpretation.inferred_action_tendency == "approach"
    assert interpretation.confidence == 1.0
    interpretation.validate_against_request(request)
    interpretation.validate_against((manifestation,))
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )
    assessment = assess_acceptance_fidelity(
        acceptance_state=acceptance,
        gap=gap,
    )
    assert gap.motive_fidelity == 1.0
    assert assessment.measured_motive_fidelity == 1.0


def test_scripted_interpreter_rejects_option_outside_public_scope() -> None:
    _, _, request = _emocio_request(allowed_option_ids=("option_native",))
    interpreter = ScriptedRacioInterpreter(
        scripted_option_id="hidden_option",
        scripted_action_tendency="approach",
        scripted_motive="attempt to escape public option scope",
        scripted_confidence=1.0,
    )

    with pytest.raises(ValueError, match="outside public scope"):
        interpreter.interpret(request)


def test_renderer_observation_keeps_ungrounded_image_lineage_and_rejects_spoofing() -> None:
    conclusion = _emocio_conclusion()
    image = _image_artifact()
    manifestation = build_emocio_manifestation(
        conclusion=conclusion,
        images=(image,),
    )
    view = build_observable_manifestation_view(manifestation)
    request = build_racio_interpreter_request(
        manifestations=(manifestation,),
        allowed_option_ids=("option_native",),
        acceptance_state=_acceptance(),
    )
    interpreter = DeterministicRacioInterpreter()
    interpretation = interpreter.interpret(request)
    image_observation = view.observations[-1]

    assert image_observation.signal_name == "visible_image_artifact_id"
    assert image_observation.provenance == "renderer_added_ungrounded"
    assert image_observation.source_image_artifact_id == image.image_id
    assert image_observation.source_image_artifact_hash == image.content_hash()
    interpretation.validate_against((manifestation,))

    foreign_observation = ManifestationObservation.create_structured(
        manifestation_id=manifestation.manifestation_id,
        manifestation_hash=manifestation.content_hash(),
        signal_name="visible_image_artifact_id",
        value="image_foreign",
        image_ref=CommunicationArtifactRef(
            artifact_id="image_foreign",
            artifact_hash="f" * 64,
        ),
    )
    spoofed_observations = (
        *interpretation.observed_manifestations[:-1],
        foreign_observation,
    )
    spoofed = RacioInterpretation(
        **_rehashed_artifact_payload(
            interpretation,
            id_field="interpretation_id",
            hash_field="interpretation_hash",
            id_prefix="racio_interpretation",
            updates={
                "observed_manifestations": spoofed_observations,
                "supporting_observation_ids": tuple(
                    observation.observation_id
                    for observation in spoofed_observations
                ),
            },
        )
    )
    with pytest.raises(ValueError, match="non-request observation"):
        spoofed.validate_against_request(request)
    with pytest.raises(ValueError, match="must cite an image visible"):
        spoofed.validate_against((manifestation,))


def test_fake_vlm_has_unique_call_lineage_and_enters_safe_processor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("fake VLM must not use a process or network")

    monkeypatch.setattr(socket, "create_connection", forbidden_call)
    monkeypatch.setattr(subprocess, "Popen", forbidden_call)
    monkeypatch.setattr(subprocess, "run", forbidden_call)

    conclusion = _emocio_conclusion()
    image = _image_artifact()
    manifestation = build_emocio_manifestation(
        conclusion=conclusion,
        images=(image,),
    )
    vlm_request = build_emocio_vlm_request(
        manifestation=manifestation,
        question="Describe only the visible presentation artifact.",
        language="en",
    )
    fake = FakeVisionLanguageInterpreter(
        interpretation="fixture-only visual description",
        inferred_claims=("fixture-only ungrounded claim",),
    )

    def call(call_id: str, timeout_seconds: float) -> ProviderCallSpec:
        return ProviderCallSpec(
            call_id=call_id,
            request_id=vlm_request.request_id,
            input_artifact_ids=vlm_request.artifact_ids,
            provider=fake.identity,
            timeout_seconds=timeout_seconds,
            fallback_policy=ProviderFallbackPolicy(
                mode="none",
                no_fallback_reason="Deterministic no-model fixture.",
            ),
        )

    first_result = fake.interpret(vlm_request, call=call("vlm_call_1", 1.0))
    second_result = fake.interpret(vlm_request, call=call("vlm_call_2", 2.0))

    assert first_result.result_id != second_result.result_id
    assert first_result.content_hash() != second_result.content_hash()
    assert first_result.call.output_artifact_ids == (first_result.result_id,)
    assert fake.identity.uses_model is False

    processed = process_communication(
        conclusion=conclusion,
        manifestations=(manifestation,),
        allowed_option_ids=("option_native", "option_wrong"),
        acceptance_state=_acceptance(),
        interpreter=DeterministicRacioInterpreter(),
        vlm_enrichments=(
            EmocioVlmEnrichment(
                manifestation_id=manifestation.manifestation_id,
                request=vlm_request,
                result=first_result,
            ),
        ),
    )
    renderer_observations = tuple(
        observation
        for observation in processed.request.observable_views[0].observations
        if observation.signal_name == "renderer_interpretation"
    )

    assert len(renderer_observations) == 1
    assert renderer_observations[0].provenance == "renderer_added_ungrounded"
    assert renderer_observations[0].source_image_artifact_id == image.image_id
    assert renderer_observations[0].source_provider_result_id == first_result.result_id
    assert renderer_observations[0].source_provider_result_hash == first_result.content_hash()
    assert renderer_observations[0] in processed.interpretation.observed_manifestations
    assert processed.translation_gap.native_motive_summary == (
        conclusion.desired_transformation
    )
    processed.request.validate_against(
        manifestations=(manifestation,),
        acceptance_state=_acceptance(),
        renderer_observations_by_manifestation={
            manifestation.manifestation_id: renderer_observations,
        },
    )


def test_wrong_translation_is_possible_and_measured_from_exact_typed_fields() -> None:
    conclusion, manifestation, request = _emocio_request()
    wrong_interpreter = ScriptedRacioInterpreter(
        scripted_option_id="option_wrong",
        scripted_action_tendency="attack",
        scripted_motive="explicitly scripted wrong interpretation",
        scripted_confidence=0.9,
    )

    interpretation = wrong_interpreter.interpret(request)
    interpretation.validate_against((manifestation,))
    validate_interpretation_replay(
        interpreter=wrong_interpreter,
        request=request,
        interpretation=interpretation,
    )
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )

    assert interpretation.inferred_option_id == "option_wrong"
    assert interpretation.inferred_action_tendency == "attack"
    assert gap.option_match is False
    assert gap.option_comparison_applicable is True
    assert gap.motive_fidelity == 0.0
    assert gap.distortion_type == "misclassification"
    assert gap.distortion_policy == B9_EXACT_DISTORTION_POLICY
    assert gap.fidelity_components == (
        FidelityComponent(
            facet="action_tendency",
            native_value="approach",
            interpreted_value="attack",
            score=0.0,
            weight=1.0,
        ),
    )
    assert gap.source_conclusion_hash == conclusion.content_hash()
    assert gap.source_interpretation_hash == interpretation.content_hash()
    validate_translation_gap_replay(
        gap=gap,
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )


def test_translation_gap_replay_rejects_self_rehashed_metric_and_lineage_tampering() -> None:
    conclusion, manifestation, request = _emocio_request()
    correct_interpreter = ScriptedRacioInterpreter(
        scripted_option_id="option_native",
        scripted_action_tendency="approach",
        scripted_motive="correct fixture interpretation",
        scripted_confidence=1.0,
    )
    interpretation = correct_interpreter.interpret(request)
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )
    assert gap.motive_fidelity == 1.0
    assert gap.distortion_type == "none"

    internally_consistent_wrong_metric = TranslationGap(
        **_rehashed_artifact_payload(
            gap,
            id_field="translation_gap_id",
            hash_field="translation_gap_hash",
            id_prefix="translation_gap",
            updates={
                "motive_fidelity": 0.0,
                "distortion_type": "misclassification",
                "fidelity_components": (
                    FidelityComponent(
                        facet="action_tendency",
                        native_value="approach",
                        interpreted_value="approach",
                        score=0.0,
                        weight=1.0,
                    ),
                ),
            },
        )
    )
    with pytest.raises(ValueError, match="differs from native/interpretation replay"):
        validate_translation_gap_replay(
            gap=internally_consistent_wrong_metric,
            conclusion=conclusion,
            manifestations=(manifestation,),
            interpretation=interpretation,
        )

    foreign_hash_gap = TranslationGap(
        **_rehashed_artifact_payload(
            gap,
            id_field="translation_gap_id",
            hash_field="translation_gap_hash",
            id_prefix="translation_gap",
            updates={"source_conclusion_hash": "0" * 64},
        )
    )
    with pytest.raises(ValueError, match="differs from native/interpretation replay"):
        validate_translation_gap_replay(
            gap=foreign_hash_gap,
            conclusion=conclusion,
            manifestations=(manifestation,),
            interpretation=interpretation,
        )


def test_translation_gap_rejects_cross_mind_and_foreign_artifacts() -> None:
    conclusion, manifestation, request = _emocio_request()
    interpreter = ScriptedRacioInterpreter(
        scripted_option_id="option_native",
        scripted_action_tendency="approach",
        scripted_motive="first interpretation",
        scripted_confidence=1.0,
    )
    interpretation = interpreter.interpret(request)
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )

    with pytest.raises(ValueError, match="source minds differ"):
        evaluate_translation_gap(
            conclusion=_instinkt_conclusion(),
            manifestations=(manifestation,),
            interpretation=interpretation,
        )

    foreign_conclusion = _emocio_conclusion(
        desired_transformation="foreign diagnostic native content",
    )
    with pytest.raises(ValueError, match="belongs to another native conclusion"):
        validate_translation_gap_replay(
            gap=gap,
            conclusion=foreign_conclusion,
            manifestations=(manifestation,),
            interpretation=interpretation,
        )

    foreign_interpretation = ScriptedRacioInterpreter(
        scripted_option_id="option_native",
        scripted_action_tendency="approach",
        scripted_motive="foreign interpretation",
        scripted_confidence=0.5,
    ).interpret(request)
    with pytest.raises(ValueError, match="differs from native/interpretation replay"):
        validate_translation_gap_replay(
            gap=gap,
            conclusion=conclusion,
            manifestations=(manifestation,),
            interpretation=foreign_interpretation,
        )


def test_scripted_high_fidelity_fixture_has_smaller_exact_gap() -> None:
    conclusion = _emocio_conclusion()
    low_acceptance = _acceptance(
        acceptance_state_id="acceptance_low_fixture",
        r_to_e_fidelity=0.25,
    )
    high_acceptance = _acceptance(
        acceptance_state_id="acceptance_high_fixture",
        r_to_e_fidelity=1.0,
    )
    _, low_manifestation, low_request = _emocio_request(
        conclusion=conclusion,
        acceptance_state=low_acceptance,
    )
    _, high_manifestation, high_request = _emocio_request(
        conclusion=conclusion,
        acceptance_state=high_acceptance,
    )

    low_interpretation = ScriptedRacioInterpreter(
        scripted_option_id="option_wrong",
        scripted_action_tendency="attack",
        scripted_motive="declared low-fidelity fixture script",
        scripted_confidence=0.25,
    ).interpret(low_request)
    high_interpretation = ScriptedRacioInterpreter(
        scripted_option_id="option_native",
        scripted_action_tendency="approach",
        scripted_motive="declared high-fidelity fixture script",
        scripted_confidence=1.0,
    ).interpret(high_request)
    low_gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(low_manifestation,),
        interpretation=low_interpretation,
    )
    high_gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(high_manifestation,),
        interpretation=high_interpretation,
    )
    low_assessment = assess_acceptance_fidelity(
        acceptance_state=low_acceptance,
        gap=low_gap,
    )
    high_assessment = assess_acceptance_fidelity(
        acceptance_state=high_acceptance,
        gap=high_gap,
    )

    assert low_gap.motive_fidelity == 0.0
    assert high_gap.motive_fidelity == 1.0
    assert low_gap.option_match is False
    assert high_gap.option_match is True
    assert low_assessment.declared_interpretation_fidelity == 0.25
    assert low_assessment.comparison == "measured_lower"
    assert high_assessment.declared_interpretation_fidelity == 1.0
    assert high_assessment.comparison == "equal"
    validate_acceptance_fidelity_replay(
        assessment=low_assessment,
        acceptance_state=low_acceptance,
        gap=low_gap,
    )
    validate_acceptance_fidelity_replay(
        assessment=high_assessment,
        acceptance_state=high_acceptance,
        gap=high_gap,
    )


def test_gap_measurement_is_not_a_copy_of_declared_acceptance_fidelity() -> None:
    conclusion, manifestation, request = _emocio_request(
        acceptance_state=_acceptance(r_to_e_fidelity=0.6),
    )
    correct = ScriptedRacioInterpreter(
        scripted_option_id="option_native",
        scripted_action_tendency="approach",
        scripted_motive="correct script",
        scripted_confidence=0.6,
    ).interpret(request)
    wrong = ScriptedRacioInterpreter(
        scripted_option_id="option_wrong",
        scripted_action_tendency="attack",
        scripted_motive="wrong script",
        scripted_confidence=0.6,
    ).interpret(request)

    correct_gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=correct,
    )
    wrong_gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=wrong,
    )

    assert request.relation.interpretation_fidelity == 0.6
    assert correct_gap.motive_fidelity == 1.0
    assert wrong_gap.motive_fidelity == 0.0


def test_abstention_id_equality_is_not_claimed_as_successful_option_comparison() -> None:
    acceptance = _acceptance(r_to_i_fidelity=0.9)
    conclusion = _instinkt_conclusion()
    body = _body_state()
    manifestation = build_instinkt_manifestation(
        conclusion=conclusion,
        body_state=body,
    )
    request = build_racio_interpreter_request(
        manifestations=(manifestation,),
        allowed_option_ids=("option_native",),
        acceptance_state=acceptance,
    )
    interpretation = ScriptedRacioInterpreter(
        scripted_option_id=None,
        scripted_action_tendency="maintain",
        scripted_motive="Racio made no option inference",
        scripted_confidence=0.9,
    ).interpret(request)
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )
    assessment = assess_acceptance_fidelity(
        acceptance_state=acceptance,
        gap=gap,
    )

    assert gap.native_option_id is None
    assert gap.interpreted_option_id is None
    assert gap.option_match is True
    assert gap.option_comparison_applicable is False
    assert gap.motive_fidelity == 1.0
    assert gap.distortion_type == "unknown"
    assert assessment.relation_direction == "R_to_I"
    assert assessment.declared_interpretation_fidelity == 0.9


def test_acceptance_fidelity_replay_rejects_self_rehashed_foreign_lineage() -> None:
    acceptance = _acceptance(r_to_e_fidelity=0.6)
    conclusion, manifestation, request = _emocio_request(
        acceptance_state=acceptance
    )
    interpretation = ScriptedRacioInterpreter(
        scripted_option_id="option_native",
        scripted_action_tendency="approach",
        scripted_motive="correct fixture",
        scripted_confidence=1.0,
    ).interpret(request)
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )
    assessment = assess_acceptance_fidelity(
        acceptance_state=acceptance,
        gap=gap,
    )
    tampered = AcceptanceFidelityAssessment(
        **_rehashed_artifact_payload(
            assessment,
            id_field="assessment_id",
            hash_field="assessment_hash",
            id_prefix="acceptance_fidelity",
            updates={"acceptance_state_hash": "0" * 64},
        )
    )

    with pytest.raises(ValueError, match="differs from replay"):
        validate_acceptance_fidelity_replay(
            assessment=tampered,
            acceptance_state=acceptance,
            gap=gap,
        )


def test_omitted_interpretation_records_omission_without_any_provider() -> None:
    conclusion, manifestation, request = _emocio_request()
    interpreter = ScriptedRacioInterpreter(
        scripted_option_id="option_wrong",
        scripted_action_tendency="attack",
        scripted_motive="discarded because no observation is retained",
        scripted_confidence=1.0,
        observation_limit=0,
    )
    interpretation = interpreter.interpret(request)
    gap = evaluate_translation_gap(
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )

    assert interpretation.interpretation_status == "omitted_b9"
    assert interpretation.inferred_option_id is None
    assert interpretation.inferred_action_tendency is None
    assert gap.distortion_type == "omission"
    assert gap.motive_fidelity == 0.0
    interpretation.validate_against((manifestation,))
    validate_translation_gap_replay(
        gap=gap,
        conclusion=conclusion,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )


def test_request_rejects_mixed_minds_and_duplicate_manifestations() -> None:
    acceptance = _acceptance()
    emocio_manifestation = build_emocio_manifestation(
        conclusion=_emocio_conclusion(),
    )
    instinkt_manifestation = build_instinkt_manifestation(
        conclusion=_instinkt_conclusion(),
        body_state=_body_state(),
    )

    with pytest.raises(ValueError, match="cannot mix E and I"):
        build_racio_interpreter_request(
            manifestations=(emocio_manifestation, instinkt_manifestation),
            allowed_option_ids=("option_native",),
            acceptance_state=acceptance,
        )
    with pytest.raises(ValueError, match="unique"):
        build_racio_interpreter_request(
            manifestations=(emocio_manifestation, emocio_manifestation),
            allowed_option_ids=("option_native",),
            acceptance_state=acceptance,
        )


class _FailingInterpreter:
    interpreter_id = "failing_b9_fixture"
    interpreter_revision = "1"
    interpreter_policy = "raise_without_fallback"

    def __init__(self) -> None:
        self.calls = 0

    def interpret(self, request: RacioInterpreterRequest) -> RacioInterpretation:
        self.calls += 1
        raise RuntimeError("explicit interpreter failure")


def test_interpreter_failure_propagates_without_hidden_fallback() -> None:
    manifestation = build_emocio_manifestation(conclusion=_emocio_conclusion())
    interpreter = _FailingInterpreter()

    assert "views" not in inspect.signature(interpret_manifestations).parameters
    with pytest.raises(RuntimeError, match="explicit interpreter failure"):
        interpret_manifestations(
            manifestations=(manifestation,),
            allowed_option_ids=("option_native",),
            acceptance_state=_acceptance(),
            interpreter=interpreter,
        )
    assert interpreter.calls == 1


class _SingleCallNonReplayInterpreter:
    """Provider-shaped fixture: valid output, but no permission to re-execute."""

    def __init__(self) -> None:
        self.calls = 0
        self.delegate = ScriptedRacioInterpreter(
            scripted_option_id=None,
            scripted_action_tendency="approach",
            scripted_motive="single-call fixture output",
            scripted_confidence=0.8,
        )

    @property
    def interpreter_id(self) -> str:
        return self.delegate.interpreter_id

    @property
    def interpreter_revision(self) -> str:
        return self.delegate.interpreter_revision

    @property
    def interpreter_policy(self) -> str:
        return self.delegate.interpreter_policy

    def interpret(self, request: RacioInterpreterRequest) -> RacioInterpretation:
        self.calls += 1
        return self.delegate.interpret(request)


def test_non_replay_interpreter_is_called_exactly_once() -> None:
    manifestation = build_emocio_manifestation(conclusion=_emocio_conclusion())
    interpreter = _SingleCallNonReplayInterpreter()

    interpreted = interpret_manifestations(
        manifestations=(manifestation,),
        allowed_option_ids=("option_native",),
        acceptance_state=_acceptance(),
        interpreter=interpreter,
    )

    assert interpreted.interpretation.inferred_action_tendency == "approach"
    assert interpreter.calls == 1
    with pytest.raises(ValueError, match="not declared safe"):
        validate_interpretation_replay(
            interpreter=interpreter,
            request=interpreted.request,
            interpretation=interpreted.interpretation,
        )
    assert interpreter.calls == 1


def test_interpretation_pipeline_does_not_mutate_native_bundle() -> None:
    bundle = _native_bundle()
    before_json = bundle.model_dump_json()
    before_bundle_hash = bundle.immutable_hash
    before_native_hashes = (
        bundle.racio.content_hash(),
        bundle.emocio.content_hash(),
        bundle.instinkt.content_hash(),
    )

    manifestation = build_emocio_manifestation(conclusion=bundle.emocio)
    request = build_racio_interpreter_request(
        manifestations=(manifestation,),
        allowed_option_ids=("option_a",),
        acceptance_state=_acceptance(),
    )
    interpretation = DeterministicRacioInterpreter().interpret(request)
    interpretation.validate_against((manifestation,))
    gap = evaluate_translation_gap(
        conclusion=bundle.emocio,
        manifestations=(manifestation,),
        interpretation=interpretation,
    )
    assessment = assess_acceptance_fidelity(
        acceptance_state=_acceptance(),
        gap=gap,
    )

    assert bundle.model_dump_json() == before_json
    assert bundle.immutable_hash == before_bundle_hash
    assert (
        bundle.racio.content_hash(),
        bundle.emocio.content_hash(),
        bundle.instinkt.content_hash(),
    ) == before_native_hashes
    assert gap.source_conclusion_hash == before_native_hashes[1]
    assert assessment.translation_gap_hash == gap.content_hash()
    with pytest.raises(ValidationError, match="Instance is frozen"):
        bundle.emocio.intensity = 0.0
