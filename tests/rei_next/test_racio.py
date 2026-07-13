from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei_next.governance.fixtures import load_governance_fixture
from app.backend.rei_next.models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ensure_call_contract,
)
from app.backend.rei_next.models.racio import (
    RacioConsequence,
    RacioInputPacket,
    RacioNativeConclusion,
    RacioWorld,
)
from app.backend.rei_next.models.scene import DecisionOption, EvidenceItem, SceneEvent
from app.backend.rei_next.providers.protocols import (
    TextReasoningRequest,
    TextReasoningResult,
)
from app.backend.rei_next.racio import (
    DeterministicRacioProvider,
    RacioNativeProcessor,
    RacioStructuredOutput,
    TextReasonerRacioAdapter,
    build_racio_packet,
)


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _scene(*, with_options: bool = True) -> SceneEvent:
    options = (
        (
            DecisionOption(
                option_id="option_first",
                label="bad unsafe keyword bait",
            ),
            DecisionOption(
                option_id="option_second",
                label="best safe optimal keyword bait",
            ),
        )
        if with_options
        else ()
    )
    return SceneEvent(
        event_id="racio_event",
        raw_input="Two explicitly ordered options are presented.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="evidence_grounded",
                modality="text",
                content="The first option is listed before the second option.",
                grounded=True,
                source_ref="test:racio_event",
                confidence=1.0,
            ),
            EvidenceItem(
                evidence_id="evidence_inferred",
                modality="text",
                content="The second option might be emotionally preferred.",
                grounded=False,
                source_ref="derived:racio_event",
                confidence=0.2,
                provenance_kind="inferred",
                inferred_by="test_router",
            ),
        ),
        options=options,
        actors=("synthetic actor",),
        constraints=("Preserve explicit ordering.",),
        unknowns=("The outcome is unknown.",),
    )


def _world() -> RacioWorld:
    return RacioWorld(
        world_id="racio_world",
        explicit_beliefs=("Only explicit inputs are authoritative.",),
        facts=("The fixture policy is positional.",),
        rules=("Do not score option labels.",),
        timelines=("facts precede option selection",),
        commitments=("preserve reproducibility",),
    )


def _packet(*, with_options: bool = True) -> RacioInputPacket:
    scene = _scene(with_options=with_options)
    consequences = (
        tuple(
            RacioConsequence(
                option_id=option.option_id,
                consequence=f"Explicit consequence for {option.option_id}.",
                evidence_ids=("evidence_grounded",),
            )
            for option in scene.options
        )
        if scene.options
        else ()
    )
    return build_racio_packet(
        scene,
        _world(),
        numeric_cues=(2,),
        time=("facts precede the choice",),
        rules=("Use only allowed option IDs.",),
        explicit_consequences=consequences,
        previous_racio_projection_ids=("racio_projection_previous",),
        previous_racio_projection_hashes=("1" * 64,),
    )


def test_racio_projection_ids_require_exact_hashes() -> None:
    with pytest.raises(ValueError, match="IDs and hashes"):
        build_racio_packet(
            _scene(),
            _world(),
            previous_racio_projection_ids=("racio_projection_previous",),
        )


def _structured_payload(packet: RacioInputPacket) -> dict[str, object]:
    return {
        "option_id": packet.allowed_option_ids[0],
        "facts_used": [packet.explicit_facts[0], packet.world.facts[0]],
        "evidence_ids_used": [packet.evidence_ids[0]],
        "unknowns": [packet.explicit_unknowns[0]],
        "causal_sequence": ["fact -> compare -> select"],
        "utility_structure": ["compare explicit consequences"],
        "explicit_goal": "Select an allowed option after explicit comparison.",
        "main_objection": "The outcome remains unknown.",
        "confidence": 0.6,
        "abstains": False,
        "uncertainty": "The supplied unknown remains unresolved.",
    }


class FakeTextReasoner:
    """In-process fake; it never opens a model runtime or network connection."""

    def __init__(
        self,
        text: str,
        *,
        supporting_evidence_ids: tuple[str, ...] = ("evidence_grounded",),
    ) -> None:
        self._text = text
        self._supporting_evidence_ids = supporting_evidence_ids
        self.invocations = 0
        self._identity = ProviderIdentity(
            provider_id="fake_text_reasoner",
            kind="text_reasoner",
            implementation="tests.rei_next.test_racio.FakeTextReasoner",
            implementation_revision="1",
        )

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def reason(
        self,
        request: TextReasoningRequest,
        *,
        call: ProviderCallSpec,
    ) -> TextReasoningResult:
        self.invocations += 1
        ensure_call_contract(
            self.identity,
            call,
            request_id=request.request_id,
            expected_kind="text_reasoner",
        )
        result_id = "fake_text_result"
        record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=request.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=self.identity,
            timeout_seconds=call.timeout_seconds,
            started_at=NOW,
            primary_finished_at=NOW,
            finished_at=NOW,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(result_id,),
        )
        return TextReasoningResult(
            result_id=result_id,
            request_id=request.request_id,
            text=self._text,
            supporting_evidence_ids=self._supporting_evidence_ids,
            call_spec=call,
            call=record,
        )


def _adapter_call(
    adapter: TextReasonerRacioAdapter,
    packet: RacioInputPacket,
    *,
    include_all_inputs: bool = True,
) -> ProviderCallSpec:
    request = adapter.build_request(packet)
    return ProviderCallSpec(
        call_id="fake_racio_call",
        request_id=request.request_id,
        input_artifact_ids=(
            adapter.required_input_artifact_ids(packet)
            if include_all_inputs
            else (packet.packet_id,)
        ),
        provider=adapter.reasoner.identity,
        timeout_seconds=1.0,
        fallback_policy=ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason="The B5 adapter test uses one in-process fake.",
        ),
    )


def test_racio_packet_is_profile_blind_content_addressed_and_replayable() -> None:
    scene = _scene()
    first = _packet()
    second = _packet()

    assert first == second
    assert first.packet_id.startswith("racio_packet_")
    assert first.language == scene.language
    assert first.source_scene_hash == scene.scene_hash()
    assert first.explicit_facts == (scene.evidence[0].content,)
    assert first.evidence_ids == (scene.evidence[0].evidence_id,)
    assert scene.evidence[1].content not in first.explicit_facts

    forbidden = {
        "character_profile",
        "character_authority",
        "authority_tiers",
        "emocio_native_conclusion",
        "instinkt_native_conclusion",
        "hidden_motive",
    }
    assert forbidden.isdisjoint(RacioInputPacket.model_fields)
    restored = RacioInputPacket.model_validate_json(first.model_dump_json())
    assert restored == first
    restored.validate_against(scene)


def test_content_addressed_packet_rejects_hallucinated_fact_and_tampering() -> None:
    packet = _packet()
    scene = _scene()

    with pytest.raises(ValueError, match="supplied and grounded"):
        packet.model_copy(
            update={"explicit_facts": ("A fabricated fact.",)}
        ).validate_against(scene)

    with pytest.raises(ValueError, match="canonical content"):
        packet.model_copy(update={"packet_id": "tampered"}).validate_against(scene)

    with pytest.raises(ValueError, match="source hash"):
        packet.model_copy(
            update={"source_scene_hash": "0" * 64}
        ).validate_against(scene)

    with pytest.raises(ValueError, match="evidence must match"):
        packet.model_copy(
            update={"evidence_ids": ("evidence_inferred",)}
        ).validate_against(scene)

    with pytest.raises(ValueError, match="option order"):
        packet.model_copy(
            update={"allowed_option_ids": tuple(reversed(packet.allowed_option_ids))}
        ).validate_against(scene)


def test_deterministic_provider_is_a_native_processor_with_distinct_fields() -> None:
    packet = _packet()
    provider = DeterministicRacioProvider()

    assert isinstance(provider, RacioNativeProcessor)
    first = provider.process(packet)
    second = provider.process(packet)

    assert first == second
    assert first.option_id == packet.allowed_option_ids[0]
    assert first.option_id == "option_first"
    assert first.source_packet_hash == packet.content_hash()
    assert first.evidence_ids_used == packet.evidence_ids
    assert set(first.facts_used).isdisjoint(first.unknowns)
    assert set(first.facts_used).isdisjoint(first.causal_sequence)
    assert set(first.unknowns).isdisjoint(first.causal_sequence)
    assert {
        "interpretation",
        "governance_mandate",
        "committed_option_id",
        "behavior_resultant",
    }.isdisjoint(RacioNativeConclusion.model_fields)
    restored = RacioNativeConclusion.model_validate_json(first.model_dump_json())
    assert restored == first
    restored.validate_against(packet)


def test_deterministic_policy_uses_position_not_semantic_keywords() -> None:
    conclusion = DeterministicRacioProvider().process(_packet())

    assert conclusion.option_id == "option_first"
    assert conclusion.explicit_goal == "Apply the first allowed option in packet order."


def test_deterministic_provider_abstains_when_packet_has_no_options() -> None:
    conclusion = DeterministicRacioProvider().process(_packet(with_options=False))

    assert conclusion.option_id is None
    assert conclusion.abstains is True


@pytest.mark.parametrize(
    ("override", "message"),
    (
        ({"facts_used": ("A hallucinated fact.",)}, "fact absent"),
        ({"unknowns": ("A fabricated unknown.",)}, "unknown absent"),
        ({"evidence_ids_used": ("outside_evidence",)}, "outside its packet"),
        ({"option_id": "outside_option", "abstains": False}, "outside its packet"),
    ),
)
def test_native_conclusion_factory_rejects_claims_outside_packet(
    override: dict[str, object],
    message: str,
) -> None:
    packet = _packet()
    payload: dict[str, object] = {
        "packet": packet,
        "option_id": packet.allowed_option_ids[0],
        "facts_used": packet.explicit_facts,
        "evidence_ids_used": packet.evidence_ids,
        "unknowns": packet.explicit_unknowns,
        "causal_sequence": ("compare supplied fields",),
        "utility_structure": ("preserve explicit ordering",),
        "explicit_goal": "Select one allowed option.",
        "main_objection": "Outcome unknown.",
        "confidence": 0.5,
        "abstains": False,
        "uncertainty": "Explicit unknown remains.",
    }
    payload.update(override)

    with pytest.raises(ValueError, match=message):
        RacioNativeConclusion.create(**payload)


def test_content_addressed_conclusion_rejects_id_and_packet_hash_tampering() -> None:
    packet = _packet()
    conclusion = DeterministicRacioProvider().process(packet)

    with pytest.raises(ValueError, match="canonical content"):
        conclusion.model_copy(
            update={"conclusion_id": "tampered"}
        ).validate_against(packet)

    with pytest.raises(ValueError, match="source packet hash"):
        conclusion.model_copy(
            update={"source_packet_hash": "0" * 64}
        ).validate_against(packet)


def test_structured_output_keeps_fact_unknown_and_sequence_distinct() -> None:
    packet = _packet()
    payload = _structured_payload(packet)
    payload["causal_sequence"] = [packet.explicit_facts[0]]

    with pytest.raises(ValidationError, match="must remain distinct"):
        RacioStructuredOutput.model_validate_json(json.dumps(payload))


def test_structured_output_citations_support_the_exact_explicit_fact() -> None:
    packet = _packet()
    payload = _structured_payload(packet)
    payload["facts_used"] = [packet.world.facts[0]]

    with pytest.raises(ValueError, match="does not support a used fact"):
        RacioStructuredOutput.model_validate_json(
            json.dumps(payload)
        ).validate_against(packet)


def test_text_reasoner_adapter_uses_strict_structured_fake_output() -> None:
    packet = _packet()
    fake = FakeTextReasoner(json.dumps(_structured_payload(packet)))
    adapter = TextReasonerRacioAdapter(fake)
    request = adapter.build_request(packet)
    call = _adapter_call(adapter, packet)

    request_payload = json.loads(request.input_text)
    assert request == adapter.build_request(packet)
    assert not isinstance(adapter, RacioNativeProcessor)
    assert "character_profile" not in request_payload
    assert "character_authority" not in request_payload
    assert "emocio_native_conclusion" not in request_payload
    assert "instinkt_native_conclusion" not in request_payload

    conclusion = adapter.process(packet, call=call)

    assert fake.invocations == 1
    assert conclusion.option_id == packet.allowed_option_ids[0]
    assert conclusion.reasoning_provider_result_id == "fake_text_result"
    assert conclusion.reasoning_provider_result_hash is not None
    assert conclusion.source_packet_hash == packet.content_hash()
    assert conclusion.evidence_ids_used == packet.evidence_ids


@pytest.mark.parametrize(
    "text",
    (
        "not json",
        json.dumps({"option_id": "option_first"}),
        json.dumps(
            {
                **_structured_payload(_packet()),
                "unexpected_interpretation": "forbidden extra field",
            }
        ),
        json.dumps(
            {
                **_structured_payload(_packet()),
                "facts_used": ["A hallucinated provider fact."],
            }
        ),
    ),
)
def test_text_reasoner_adapter_rejects_invalid_structured_output(text: str) -> None:
    packet = _packet()
    fake = FakeTextReasoner(text)
    adapter = TextReasonerRacioAdapter(fake)

    with pytest.raises(ValueError):
        adapter.process(packet, call=_adapter_call(adapter, packet))


def test_text_reasoner_adapter_rejects_uncited_evidence() -> None:
    packet = _packet()
    fake = FakeTextReasoner(
        json.dumps(_structured_payload(packet)),
        supporting_evidence_ids=(),
    )
    adapter = TextReasonerRacioAdapter(fake)

    with pytest.raises(ValueError, match="not reported"):
        adapter.process(packet, call=_adapter_call(adapter, packet))


def test_text_reasoner_adapter_rejects_call_without_full_input_lineage() -> None:
    packet = _packet()
    fake = FakeTextReasoner(json.dumps(_structured_payload(packet)))
    adapter = TextReasonerRacioAdapter(fake)

    with pytest.raises(ValueError, match="omits required"):
        adapter.process(
            packet,
            call=_adapter_call(adapter, packet, include_all_inputs=False),
        )
    assert fake.invocations == 0


def test_all_canonical_native_fixtures_smoke_with_deterministic_racio() -> None:
    fixture_paths = sorted(
        Path("tests/fixtures/native_bundles").glob("*.json")
    )
    provider = DeterministicRacioProvider()

    assert len(fixture_paths) == 12
    for path in fixture_paths:
        fixture = load_governance_fixture(path)
        conclusion = provider.process(fixture.racio_packet)
        conclusion.validate_against(fixture.racio_packet)
        assert conclusion.option_id in fixture.racio_packet.allowed_option_ids
