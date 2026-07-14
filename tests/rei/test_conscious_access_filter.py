from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.backend.rei.communication.conscious_access import (
    ConsciousAccessFilter,
    ConsciousAccessPacket,
    TrustedVisibleArtifact,
)
from app.backend.rei.communication.conscious_view import (
    build_racio_interpreter_request,
)
from app.backend.rei.communication.manifestations import build_emocio_manifestation
from app.backend.rei.communication.processor import interpret_manifestations
from app.backend.rei.communication.structured_interpreter import (
    DeterministicStructuredRacioInterpreterProvider,
    StructuredLLMRacioInterpreter,
    StructuredRacioInterpreterOutput,
)
from app.backend.rei.providers.native import DeterministicExecutionClock
from tests.rei.test_communication import (
    _acceptance,
    _emocio_conclusion,
    _emocio_request,
    _image_artifact,
)


def _image_request(*, visibility: float = 1.0):
    conclusion = _emocio_conclusion()
    manifestation = build_emocio_manifestation(
        conclusion=conclusion,
        images=(_image_artifact(),),
    )
    acceptance = _acceptance(r_to_e_visibility=visibility)
    request = build_racio_interpreter_request(
        manifestations=(manifestation,),
        allowed_option_ids=("actual_continue", "actual_pause"),
        acceptance_state=acceptance,
    )
    return conclusion, manifestation, request


def test_zero_visibility_omits_every_signal_and_artifact() -> None:
    _, _, request = _image_request(visibility=0.0)
    before = request.model_dump_json()

    result = ConsciousAccessFilter(seed=7).apply(
        request,
        language="sl",
        ablation_mode="structured_plus_image",
        option_descriptions={
            "actual_continue": "Nadaljuj reverzibilno",
            "actual_pause": "Ustavi se in preveri",
        },
        supplemental_artifacts=(
            TrustedVisibleArtifact(
                source_artifact_id="supplemental_image",
                source_artifact_hash="c" * 64,
                kind="emocio_image",
                media_type="image/png",
            ),
        ),
    )

    assert result.packet.visible_observations == ()
    assert result.packet.visible_artifacts == ()
    assert result.packet.visible_artifact_ids == ()
    assert result.packet.channel_quality == 0.0
    assert set(result.packet.omitted_observation_ids) == {
        item.public_observation_id for item in result.audit.observation_lineage
    }
    assert request.model_dump_json() == before


def test_visible_and_omitted_aliases_form_complete_disjoint_partition() -> None:
    _, _, request = _emocio_request(
        acceptance_state=_acceptance(r_to_e_visibility=0.4)
    )
    result = ConsciousAccessFilter(seed=17).apply(request)
    visible = {item.observation_id for item in result.packet.visible_observations}
    omitted = set(result.packet.omitted_observation_ids)
    source_scope = {
        item.public_observation_id for item in result.audit.observation_lineage
    }

    assert visible
    assert omitted
    assert visible.isdisjoint(omitted)
    assert visible | omitted == source_scope
    assert set(result.packet.degraded_observation_ids).issubset(visible)


def test_provider_payload_excludes_trusted_native_and_acceptance_lineage() -> None:
    canary = "HIDDEN_NATIVE_PROFILE_CANARY_DO_NOT_DISCLOSE"
    conclusion = _emocio_conclusion(
        conclusion_id="native_conclusion_secret",
        option_id="native_option_secret",
        desired_transformation=canary,
        main_obstacle="authority_tier_secret",
    )
    _, _, request = _emocio_request(
        conclusion=conclusion,
        acceptance_state=_acceptance(acceptance_state_id="acceptance_secret"),
        allowed_option_ids=("native_option_secret", "native_other_secret"),
    )
    result = ConsciousAccessFilter(seed=2).apply(
        request,
        option_descriptions={
            "native_option_secret": "Approach the bounded public scene",
            "native_other_secret": "Pause before acting",
        },
    )
    payload = result.packet.provider_payload_bytes().decode("utf-8")

    for forbidden in (
        canary,
        "native_conclusion_secret",
        "native_option_secret",
        "native_other_secret",
        "acceptance_secret",
        request.request_id,
        request.acceptance_state_hash,
        result.audit.audit_id,
        result.packet.packet_id,
        result.packet.packet_hash,
        "sabotage_risk",
        "authority_tier",
        "profile",
    ):
        assert forbidden not in payload
    assert set(json.loads(payload)) == {
        "schema_version",
        "source_mind",
        "language",
        "ablation_mode",
        "visible_observations",
        "omitted_observation_ids",
        "degraded_observation_ids",
        "visible_artifacts",
        "visible_artifact_ids",
        "public_option_scope",
        "channel_quality",
        "uncertainty",
    }


def test_hidden_native_and_actual_id_renaming_is_provider_non_interfering() -> None:
    conclusion_a = _emocio_conclusion(
        conclusion_id="hidden_native_a",
        option_id="actual_a",
        desired_transformation="hidden motive A",
        main_obstacle="hidden obstacle A",
    )
    conclusion_b = _emocio_conclusion(
        conclusion_id="hidden_native_b",
        option_id="actual_b",
        desired_transformation="hidden motive B",
        main_obstacle="hidden obstacle B",
    )
    _, _, request_a = _emocio_request(
        conclusion=conclusion_a,
        allowed_option_ids=("actual_a", "other_a"),
    )
    _, _, request_b = _emocio_request(
        conclusion=conclusion_b,
        allowed_option_ids=("actual_b", "other_b"),
    )
    access_filter = ConsciousAccessFilter(seed=99)
    result_a = access_filter.apply(
        request_a,
        language="en",
        option_descriptions={
            "actual_a": "Move toward the bounded scene",
            "other_a": "Pause before acting",
        },
    )
    result_b = access_filter.apply(
        request_b,
        language="en",
        option_descriptions={
            "actual_b": "Move toward the bounded scene",
            "other_b": "Pause before acting",
        },
    )

    assert result_a.packet == result_b.packet
    assert result_a.packet.provider_payload_bytes() == (
        result_b.packet.provider_payload_bytes()
    )
    assert result_a.audit != result_b.audit
    assert result_a.audit.source_request_hash != result_b.audit.source_request_hash
    assert {
        item.source_option_id for item in result_a.audit.option_lineage
    } != {item.source_option_id for item in result_b.audit.option_lineage}


def test_seed_is_deterministic_and_changes_only_filter_selection() -> None:
    _, _, request = _emocio_request(
        acceptance_state=_acceptance(r_to_e_visibility=0.4)
    )
    first = ConsciousAccessFilter(seed=11).apply(request)
    replay = ConsciousAccessFilter(seed=11).apply(request)
    alternate = ConsciousAccessFilter(seed=12).apply(request)

    assert first == replay
    assert first.audit.filter_seed == 11
    assert alternate.audit.filter_seed == 12
    assert first.audit.source_request_hash == alternate.audit.source_request_hash


def test_ablation_modes_expose_only_declared_signal_classes() -> None:
    _, _, request = _image_request()
    descriptions = {
        "actual_continue": "Continue",
        "actual_pause": "Pause",
    }
    structured = ConsciousAccessFilter().apply(
        request,
        ablation_mode="structured_only",
        option_descriptions=descriptions,
    )
    images = ConsciousAccessFilter().apply(
        request,
        ablation_mode="image_only",
        option_descriptions=descriptions,
    )

    assert all(
        item.signal_name not in {"visible_image_artifact_id", "renderer_interpretation"}
        for item in structured.packet.visible_observations
    )
    assert structured.packet.visible_artifacts == ()
    assert images.packet.visible_observations
    assert all(
        item.signal_name in {"visible_image_artifact_id", "renderer_interpretation"}
        for item in images.packet.visible_observations
    )
    assert images.packet.visible_artifacts


def test_conflicting_supplemental_artifact_lineage_is_rejected() -> None:
    _, _, request = _image_request()
    with pytest.raises(ValueError, match="lineage is ambiguous"):
        ConsciousAccessFilter().apply(
            request,
            ablation_mode="structured_plus_image",
            option_descriptions={
                "actual_continue": "Continue",
                "actual_pause": "Pause",
            },
            supplemental_artifacts=(
                TrustedVisibleArtifact(
                    source_artifact_id="image_b9",
                    source_artifact_hash="d" * 64,
                    kind="emocio_image",
                    media_type="image/png",
                ),
            ),
        )


def test_packet_rejects_tampered_hash_and_provider_payload_has_no_hashes() -> None:
    _, _, request = _emocio_request()
    packet = ConsciousAccessFilter().apply(request).packet
    tampered = packet.model_dump(mode="python", round_trip=True)
    tampered["packet_hash"] = "0" * 64

    with pytest.raises(ValidationError, match="packet_hash differs"):
        ConsciousAccessPacket.model_validate(tampered)
    payload = packet.provider_payload()
    assert "packet_id" not in payload
    assert "packet_hash" not in payload
    assert "filter_policy" not in payload


def test_deterministic_structured_baseline_uses_only_packet_aliases() -> None:
    _, _, request = _emocio_request()
    access = ConsciousAccessFilter(seed=5).apply(
        request,
        language="en",
        option_descriptions={
            "option_native": "Continue toward the bounded scene",
            "option_wrong": "Pause before acting",
        },
    )
    provider = DeterministicStructuredRacioInterpreterProvider()
    call = provider.build_call_spec(access.packet)
    execution = provider.execute(
        access.packet,
        call=call,
        clock=DeterministicExecutionClock(
            base=datetime(2026, 7, 14, tzinfo=timezone.utc)
        ),
    )

    assert provider.required_input_artifact_ids(access.packet) == (
        access.packet.packet_id,
    )
    assert call.input_artifact_ids == (access.packet.packet_id,)
    assert call.fallback_policy.mode == "none"
    assert execution.output.inferred_option_id is None
    assert execution.output.inferred_action_tendency == "approach"
    assert set(execution.output.cited_observation_ids).issubset(
        {item.observation_id for item in access.packet.visible_observations}
    )
    serialized = execution.output.model_dump_json()
    assert "option_native" not in serialized
    assert request.request_id not in serialized
    assert execution.call_record.output_artifact_ids == (
        execution.response_evidence.result_id,
    )


def test_structured_output_rejects_foreign_aliases_and_chain_of_thought() -> None:
    _, _, request = _emocio_request()
    packet = ConsciousAccessFilter().apply(request).packet
    visible_id = packet.visible_observations[0].observation_id
    base = {
        "source_mind": packet.source_mind,
        "cited_observation_ids": (visible_id,),
        "inferred_option_id": None,
        "inferred_action_tendency": None,
        "inferred_motive_class": None,
        "confidence": 0.2,
        "alternative_hypotheses": ("Insufficient evidence",),
        "unresolved_ambiguity": "No grounded option choice",
    }
    valid = StructuredRacioInterpreterOutput(**base)
    valid.validate_against(packet)

    with pytest.raises(ValueError, match="outside packet scope"):
        valid.model_copy(
            update={"cited_observation_ids": ("observation_foreign",)}
        ).validate_against(packet)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StructuredRacioInterpreterOutput.model_validate(
            {**base, "chain_of_thought": "forbidden private reasoning"}
        )


def test_high_level_structured_adapter_closes_aliases_to_trusted_lineage() -> None:
    _, _, request = _emocio_request()
    interpreter = StructuredLLMRacioInterpreter(
        provider=DeterministicStructuredRacioInterpreterProvider(),
        language="sl",
        option_descriptions={
            "option_native": "Nadaljuj proti omejenemu prizoru",
            "option_wrong": "Ustavi se in preveri",
        },
        access_filter=ConsciousAccessFilter(seed=19),
        clock=DeterministicExecutionClock(
            base=datetime(2026, 7, 14, tzinfo=timezone.utc)
        ),
    )

    result = interpreter.interpret_with_evidence(request)
    interpretation = result.interpretation

    assert interpretation.language == "sl"
    assert interpretation.conscious_access_packet_id == result.access.packet.packet_id
    assert interpretation.conscious_access_packet_hash == (
        result.access.packet.content_hash()
    )
    assert interpretation.interpreter_result_id == (
        result.execution.response_evidence.result_id
    )
    assert interpretation.interpreter_result_hash == (
        result.execution.response_evidence.content_hash()
    )
    assert interpretation.inferred_option_id is None
    assert interpretation.inferred_action_tendency == "approach"
    assert interpretation.unresolved_ambiguity is not None
    assert len(interpretation.supporting_observation_ids) == 1
    public_citation = result.execution.output.cited_observation_ids[0]
    assert interpretation.supporting_observation_ids == (
        result.access.audit.source_observation_id(public_citation),
    )
    interpretation.validate_against_request(request)


def test_high_level_adapter_omits_inference_when_filter_exposes_nothing() -> None:
    _, _, request = _emocio_request(
        acceptance_state=_acceptance(r_to_e_visibility=0.0)
    )
    result = StructuredLLMRacioInterpreter(
        provider=DeterministicStructuredRacioInterpreterProvider(),
        clock=DeterministicExecutionClock(
            base=datetime(2026, 7, 14, tzinfo=timezone.utc)
        ),
    ).interpret_with_evidence(request)

    assert result.access.packet.visible_observations == ()
    assert result.execution.output.cited_observation_ids == ()
    assert result.interpretation.interpretation_status == "omitted_b9"
    assert result.interpretation.observed_manifestations == ()
    assert result.interpretation.confidence == 0.0


def test_safe_processor_retains_c3_evidence_and_executes_provider_once() -> None:
    class CountingProvider:
        def __init__(self) -> None:
            self.delegate = DeterministicStructuredRacioInterpreterProvider()
            self.calls = 0

        @property
        def identity(self):
            return self.delegate.identity

        def required_input_artifact_ids(self, packet):
            return self.delegate.required_input_artifact_ids(packet)

        def build_call_spec(self, packet):
            return self.delegate.build_call_spec(packet)

        def execute(self, packet, *, call, clock):
            self.calls += 1
            return self.delegate.execute(packet, call=call, clock=clock)

    conclusion = _emocio_conclusion()
    manifestation = build_emocio_manifestation(conclusion=conclusion)
    provider = CountingProvider()
    interpreter = StructuredLLMRacioInterpreter(
        provider=provider,
        option_descriptions={
            "option_native": "Nadaljuj",
            "option_wrong": "Ustavi se",
        },
        clock=DeterministicExecutionClock(
            base=datetime(2026, 7, 14, tzinfo=timezone.utc)
        ),
    )

    processed = interpret_manifestations(
        manifestations=(manifestation,),
        allowed_option_ids=("option_native", "option_wrong"),
        acceptance_state=_acceptance(),
        interpreter=interpreter,
    )

    assert provider.calls == 1
    assert processed.c3_result is not None
    assert processed.interpretation == processed.c3_result.interpretation
