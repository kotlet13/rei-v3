from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import pytest

from app.backend.rei.providers import ollama_gemma4_epistemic as gemma_provider
from app.backend.rei.communication.conscious_access import (
    ConsciousAccessObservation,
    ConsciousAccessOption,
)
from app.backend.rei.communication.epistemic_interpreter import (
    MOTIVE_AMBIGUITY_SL,
    MOTIVE_HYPOTHESIS_EXPLANATION_SL,
    MOTIVE_SUBTYPES_BY_FAMILY,
    MOTIVE_UNKNOWN_REASON_SL,
    OPTION_AMBIGUITY_SL,
    OPTION_AND_MOTIVE_AMBIGUITY_SL,
    MotiveHypothesis,
    RacioEpistemicInterpretationV2,
    RacioEpistemicPacketV2,
)
from app.backend.rei.ids import canonical_json_bytes, sha256_hex
from app.backend.rei.models.provider import ProviderCallSpec
from app.backend.rei.providers.native import DeterministicExecutionClock
from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaRuntimeModel,
    OllamaTransportError,
)
from app.backend.rei.providers.ollama_gemma4_epistemic import (
    GEMMA4_EPISTEMIC_INSTRUCTION,
    GEMMA4_EPISTEMIC_MODEL,
    GEMMA4_EPISTEMIC_NUM_CTX,
    GEMMA4_EPISTEMIC_NUM_GPU,
    GEMMA4_EPISTEMIC_NUM_PREDICT,
    GEMMA4_EPISTEMIC_PARAMETER_COUNT,
    GEMMA4_EPISTEMIC_SEED,
    GEMMA4_EPISTEMIC_TEMPERATURE,
    GEMMA4_EPISTEMIC_TOP_K,
    GEMMA4_EPISTEMIC_TOP_P,
    Gemma4EpistemicExecutionError,
    Gemma4EpistemicSettings,
    OllamaGemma4EpistemicProvider,
)


DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64
ENVIRONMENT = {
    "REI_OLLAMA_MODEL": GEMMA4_EPISTEMIC_MODEL,
    "REI_OLLAMA_NUM_CTX": str(GEMMA4_EPISTEMIC_NUM_CTX),
    "REI_OLLAMA_NUM_GPU": str(GEMMA4_EPISTEMIC_NUM_GPU),
}


def _packet(
    *,
    visible_description: str = (
        "Prisoten je jasen impulz izvesti pripravljeni korak."
    ),
) -> RacioEpistemicPacketV2:
    return RacioEpistemicPacketV2.create(
        source_mind="E",
        language="sl",
        visible_observations=(
            ConsciousAccessObservation(
                observation_id="observation_001",
                signal_name="motor_urge",
                perception_status="clear",
                perceived_value_json=canonical_json_bytes(
                    {"visible_description": visible_description}
                ).decode("utf-8"),
                provenance="manifested",
            ),
        ),
        omitted_observation_ids=(),
        public_option_scope=(
            ConsciousAccessOption(
                option_id="option_001",
                description="Izvedi pripravljeni korak.",
            ),
        ),
        channel_quality=1.0,
        uncertainty=(
            "Akcijska smer je vidna, globlji motiv pa ni določen."
        ),
    )


def _output(
    *,
    cited: tuple[str, ...] = ("observation_001",),
) -> RacioEpistemicInterpretationV2:
    return RacioEpistemicInterpretationV2(
        source_mind="E",
        cited_observation_ids=cited,
        inferred_action_tendency="perform",
        action_confidence=0.9,
        inferred_option_id="option_001",
        option_confidence=0.9,
        motive_hypotheses=(),
        motive_unknown_reason=MOTIVE_UNKNOWN_REASON_SL,
        unresolved_ambiguity=None,
    )


def _response(
    *,
    output: RacioEpistemicInterpretationV2 | None = None,
    thinking: object = "Zasebna sled s šumniki č, š in ž.",
) -> dict[str, Any]:
    selected = _output() if output is None else output
    return {
        "model": GEMMA4_EPISTEMIC_MODEL,
        "created_at": "2026-07-17T10:00:00Z",
        "message": {
            "role": "assistant",
            "content": selected.model_dump_json(),
            "thinking": thinking,
        },
        "done": True,
        "done_reason": "stop",
        "total_duration": 10,
        "load_duration": 2,
        "prompt_eval_count": 100,
        "prompt_eval_duration": 3,
        "eval_count": 20,
        "eval_duration": 5,
    }


class FakeOllamaTransport:
    def __init__(self, response: Mapping[str, Any] | None = None) -> None:
        self.chat_response = dict(_response() if response is None else response)
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []
        self.chat_count = 0
        self.tags_count = 0
        self.post_call_digest: str | None = None
        self.active_context = GEMMA4_EPISTEMIC_NUM_CTX
        self.active_size = 1000
        self.active_size_vram = 1000
        self.active_remote = False
        self.fail_chat = False
        self.mutate_request = False

    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        del timeout_seconds, max_response_bytes
        path = urlsplit(url).path
        stored_payload = None if payload is None else copy.deepcopy(payload)
        self.calls.append((method, path, stored_payload))
        if path == "/api/version":
            return {"version": "0.31.2"}
        if path == "/api/tags":
            self.tags_count += 1
            digest = DIGEST
            if self.post_call_digest is not None and self.tags_count >= 3:
                digest = self.post_call_digest
            return {
                "models": [
                    {
                        "name": GEMMA4_EPISTEMIC_MODEL,
                        "model": GEMMA4_EPISTEMIC_MODEL,
                        "digest": digest,
                        "size": 19_868_969_920,
                        "details": {
                            "quantization_level": "Q4_K_M",
                            "context_length": 262144,
                        },
                        "capabilities": [
                            "completion",
                            "thinking",
                            "tools",
                        ],
                    }
                ]
            }
        if path == "/api/show":
            return {
                "details": {"quantization_level": "Q4_K_M"},
                "model_info": {
                    "general.architecture": "gemma4",
                    "general.parameter_count": GEMMA4_EPISTEMIC_PARAMETER_COUNT,
                    "gemma4.context_length": 262144,
                },
                "template": "{{ .Prompt }}",
                "capabilities": [
                    "completion",
                    "thinking",
                    "tools",
                    "vision",
                ],
            }
        if path == "/api/chat":
            self.chat_count += 1
            if self.fail_chat:
                raise OllamaTransportError("synthetic transport failure")
            if self.mutate_request:
                assert isinstance(payload, dict)
                payload["model"] = "mutated:latest"
            return copy.deepcopy(self.chat_response)
        if path == "/api/ps":
            active: dict[str, Any] = {
                "name": GEMMA4_EPISTEMIC_MODEL,
                "model": GEMMA4_EPISTEMIC_MODEL,
                "digest": DIGEST,
                "size": self.active_size,
                "size_vram": self.active_size_vram,
                "context_length": self.active_context,
            }
            if self.active_remote:
                active["remote_model"] = "remote/gemma4"
            return {"models": [active]}
        raise AssertionError(f"Unexpected Ollama path: {method} {path}")


def _provider(
    transport: FakeOllamaTransport,
) -> OllamaGemma4EpistemicProvider:
    return OllamaGemma4EpistemicProvider.discover(
        client=OllamaApiClient(transport=transport),
        expected_digest=DIGEST,
        environ=ENVIRONMENT,
    )


def _clock() -> DeterministicExecutionClock:
    return DeterministicExecutionClock(
        datetime(2026, 7, 17, tzinfo=timezone.utc)
    )


def _execute(
    provider: OllamaGemma4EpistemicProvider,
    packet: RacioEpistemicPacketV2 | None = None,
):
    selected = _packet() if packet is None else packet
    return provider.execute(
        selected,
        call=provider.build_call_spec(selected),
        clock=_clock(),
    )


def _parameter_values(call: ProviderCallSpec) -> dict[str, object]:
    return {
        item.name: json.loads(item.canonical_json_value)
        for item in call.parameters
    }


def test_happy_path_pins_request_and_discards_thinking_text() -> None:
    trace = "Zasebna sled s šumniki č, š in ž."
    transport = FakeOllamaTransport(_response(thinking=trace))
    provider = _provider(transport)
    packet = _packet()
    execution = _execute(provider, packet)

    assert transport.chat_count == 1
    chat_calls = [item for item in transport.calls if item[1] == "/api/chat"]
    assert len(chat_calls) == 1
    assert not [item for item in transport.calls if item[1] == "/api/generate"]
    request_payload = chat_calls[0][2]
    assert request_payload is not None
    assert request_payload["model"] == GEMMA4_EPISTEMIC_MODEL
    assert request_payload["messages"] == [
        {
            "role": "system",
            "content": GEMMA4_EPISTEMIC_INSTRUCTION,
        },
        {
            "role": "user",
            "content": packet.provider_payload_bytes().decode("utf-8"),
        },
    ]
    assert request_payload["messages"][0]["content"].startswith("<|think|>\n")
    output_schema = request_payload["format"]
    assert output_schema != RacioEpistemicInterpretationV2.model_json_schema()
    subtype_schema = output_schema["$defs"]["MotiveHypothesis"]["properties"][
        "subtype"
    ]
    assert subtype_schema["enum"] == sorted(
        subtype
        for subtypes in MOTIVE_SUBTYPES_BY_FAMILY.values()
        for subtype in subtypes
    )
    for family, subtypes in MOTIVE_SUBTYPES_BY_FAMILY.items():
        taxonomy_line = f"- {family}: {', '.join(sorted(subtypes))}"
        assert taxonomy_line in GEMMA4_EPISTEMIC_INSTRUCTION
        for subtype in subtypes:
            assert f"- {family}/{subtype}:" in GEMMA4_EPISTEMIC_INSTRUCTION
    ambiguity_description = output_schema["properties"][
        "unresolved_ambiguity"
    ]["description"]
    expected_ambiguity_description = f"""\
Set unresolved_ambiguity mechanically from the other final JSON fields:
- inferred_option_id is null and motive_hypotheses has 0 or 1 item: use
  {OPTION_AMBIGUITY_SL!r}
- inferred_option_id is null and motive_hypotheses has 2 or 3 items: use
  {OPTION_AND_MOTIVE_AMBIGUITY_SL!r}
- inferred_option_id is not null and motive_hypotheses has 0 or 1 item: use null
- inferred_option_id is not null and motive_hypotheses has 2 or 3 items: use
  {MOTIVE_AMBIGUITY_SL!r}"""
    assert ambiguity_description == expected_ambiguity_description
    assert ambiguity_description in GEMMA4_EPISTEMIC_INSTRUCTION
    assert "inferred_option_id is null" in ambiguity_description
    assert "inferred_option_id is not null" in ambiguity_description
    assert "motive_hypotheses has 0 or 1 item" in ambiguity_description
    assert "motive_hypotheses has 2 or 3 items" in ambiguity_description
    for ambiguity_value in (
        OPTION_AMBIGUITY_SL,
        OPTION_AND_MOTIVE_AMBIGUITY_SL,
        MOTIVE_AMBIGUITY_SL,
    ):
        assert repr(ambiguity_value) in ambiguity_description
    assert "raw" not in request_payload
    assert "system" not in request_payload
    assert "prompt" not in request_payload
    assert request_payload["stream"] is False
    assert request_payload["think"] is True
    assert request_payload["keep_alive"] == "10m"
    assert request_payload["options"] == {
        "seed": GEMMA4_EPISTEMIC_SEED,
        "temperature": GEMMA4_EPISTEMIC_TEMPERATURE,
        "top_p": GEMMA4_EPISTEMIC_TOP_P,
        "top_k": GEMMA4_EPISTEMIC_TOP_K,
        "num_ctx": GEMMA4_EPISTEMIC_NUM_CTX,
        "num_gpu": GEMMA4_EPISTEMIC_NUM_GPU,
        "num_predict": GEMMA4_EPISTEMIC_NUM_PREDICT,
    }
    encoded_prompt = str(request_payload["messages"][1]["content"])
    for hidden in ("profile_id", "native_truth", "character_profile", "gold"):
        assert hidden not in encoded_prompt

    parameters = _parameter_values(execution.call_spec)
    assert parameters["endpoint"] == "http://127.0.0.1:11434/api/chat"
    assert parameters["chat_message_roles"] == ["system", "user"]
    assert parameters["chat_messages_sha256"] == sha256_hex(
        request_payload["messages"]
    )
    assert parameters["raw_request_field_sent"] is False
    assert "raw" not in parameters
    assert parameters["model"] == GEMMA4_EPISTEMIC_MODEL
    assert parameters["model_digest"] == DIGEST
    assert parameters["model_quantization"] == "Q4_K_M"
    assert parameters["model_parameter_count"] == GEMMA4_EPISTEMIC_PARAMETER_COUNT
    assert parameters["model_serialized_size_bytes"] == 19_868_969_920
    assert parameters["model_context_capability"] == 262144
    assert parameters["model_capabilities"] == [
        "completion",
        "thinking",
        "tools",
        "vision",
    ]
    assert parameters["model_supported_modalities"] == ["text", "vision"]
    assert parameters["model_template"] == "{{ .Prompt }}"
    assert parameters["system_role_transport"] == "ollama_chat_system_message"
    assert parameters["num_ctx"] == GEMMA4_EPISTEMIC_NUM_CTX
    assert parameters["num_gpu"] == GEMMA4_EPISTEMIC_NUM_GPU
    assert parameters["top_p"] == GEMMA4_EPISTEMIC_TOP_P
    assert parameters["top_k"] == GEMMA4_EPISTEMIC_TOP_K
    assert parameters["retry_count"] == 0
    assert parameters["thinking_separate_required"] is True
    assert execution.call_spec.fallback_policy.mode == "none"

    evidence = execution.response_evidence
    assert execution.output.motive_unknown_reason == MOTIVE_UNKNOWN_REASON_SL
    assert evidence.thinking_present is True
    assert evidence.thinking_byte_count == len(trace.encode("utf-8"))
    assert evidence.thinking_sha256 == hashlib.sha256(trace.encode("utf-8")).hexdigest()
    assert evidence.thinking_token_count is None
    assert evidence.active_context_length == GEMMA4_EPISTEMIC_NUM_CTX
    assert evidence.active_size_bytes == evidence.active_size_vram_bytes
    assert evidence.active_gpu_percent_rounded == 100
    serialized = evidence.model_dump_json()
    assert trace not in serialized
    assert trace not in repr(execution)
    assert _response(thinking=trace)["message"]["content"] not in serialized


@pytest.mark.parametrize(
    "hidden_payload",
    (
        {"native_truth_id": "DO_NOT_EXPOSE"},
        {"gold": "boundary_alarm"},
        {"expected_output": "boundary_alarm"},
    ),
)
def test_provider_rejects_embedded_hidden_lineage_before_chat(
    hidden_payload: Mapping[str, str],
) -> None:
    transport = FakeOllamaTransport()
    provider = _provider(transport)
    packet = RacioEpistemicPacketV2.create(
        source_mind="E",
        language="sl",
        visible_observations=(
            ConsciousAccessObservation(
                observation_id="observation_001",
                signal_name="motor_urge",
                perception_status="clear",
                perceived_value_json=canonical_json_bytes(hidden_payload).decode("utf-8"),
                provenance="manifested",
            ),
        ),
        omitted_observation_ids=(),
        public_option_scope=(
            ConsciousAccessOption(
                option_id="option_001",
                description="Izvedi pripravljeni korak.",
            ),
        ),
        channel_quality=1.0,
        uncertainty="Vidna smer je omejena.",
    )

    with pytest.raises(ValueError, match="forbidden evaluator or identity"):
        provider.build_call_spec(packet)
    with pytest.raises(ValueError, match="forbidden evaluator or identity"):
        provider.request_payload(packet)
    assert transport.chat_count == 0


def test_populated_motive_uses_exposed_closed_vocabulary() -> None:
    output = RacioEpistemicInterpretationV2(
        source_mind="E",
        cited_observation_ids=("observation_001",),
        inferred_action_tendency="perform",
        action_confidence=0.9,
        inferred_option_id="option_001",
        option_confidence=0.9,
        motive_hypotheses=(
            MotiveHypothesis(
                family="motor_social",
                subtype="motor_execution",
                cited_observation_ids=("observation_001",),
                confidence=0.8,
                explanation_short_sl=MOTIVE_HYPOTHESIS_EXPLANATION_SL,
            ),
        ),
        motive_unknown_reason=None,
        unresolved_ambiguity=None,
    )
    transport = FakeOllamaTransport(_response(output=output))

    execution = _execute(_provider(transport))

    assert transport.chat_count == 1
    assert execution.output.motive_hypotheses == output.motive_hypotheses


def test_untrusted_response_metadata_is_not_persisted_or_echoed() -> None:
    response = _response()
    response["created_at"] = "TOP_SECRET_CREATED_AT_TEXT"
    transport = FakeOllamaTransport(response)
    execution = _execute(_provider(transport))
    serialized = execution.response_evidence.model_dump_json()
    assert "TOP_SECRET_CREATED_AT_TEXT" not in serialized
    assert "response_created_at" not in serialized

    invalid = _response()
    invalid["total_duration"] = "TOP_SECRET_BAD_COUNT"
    invalid_transport = FakeOllamaTransport(invalid)
    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        _execute(_provider(invalid_transport))
    assert "TOP_SECRET_BAD_COUNT" not in str(caught.value)
    assert "TOP_SECRET_BAD_COUNT" not in repr(caught.value.__dict__)


def test_non_json_response_value_is_rejected_without_echo() -> None:
    class SecretValue:
        def __repr__(self) -> str:
            return "TOP_SECRET_NON_JSON_VALUE"

    response = _response()
    response["unexpected"] = SecretValue()
    transport = FakeOllamaTransport(response)
    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        _execute(_provider(transport))
    assert caught.value.failure_code == "generation_contract_failure"
    assert "TOP_SECRET_NON_JSON_VALUE" not in str(caught.value)
    assert "TOP_SECRET_NON_JSON_VALUE" not in repr(caught.value.__dict__)
    assert transport.chat_count == 1


@pytest.mark.parametrize(
    "mutate",
    (
        lambda response: response.__setitem__("done", False),
        lambda response: response.__setitem__("done_reason", "length"),
        lambda response: response.__setitem__("model", "gemma4:latest"),
        lambda response: response.__setitem__(
            "remote_host", "TOP_SECRET_REMOTE_HOST"
        ),
        lambda response: response.pop("message"),
        lambda response: response.__setitem__("message", ["TOP_SECRET_MESSAGE"]),
        lambda response: response["message"].__setitem__("role", "user"),
        lambda response: response["message"].__setitem__("content", ""),
        lambda response: response.__setitem__("response", "TOP_SECRET_RESPONSE"),
        lambda response: response.__setitem__("thinking", "TOP_SECRET_THINKING"),
        lambda response: response["message"].__setitem__(
            "tool_calls", [{"secret": "TOP_SECRET_TOOL"}]
        ),
        lambda response: response["message"].__setitem__(
            "images", ["TOP_SECRET_IMAGE"]
        ),
    ),
)
def test_chat_envelope_drift_fails_closed_without_leakage(mutate) -> None:
    response = _response()
    mutate(response)
    transport = FakeOllamaTransport(response)

    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        _execute(_provider(transport))

    assert caught.value.failure_code == "generation_contract_failure"
    assert "TOP_SECRET" not in str(caught.value)
    assert "TOP_SECRET" not in repr(caught.value.__dict__)
    assert transport.chat_count == 1
    assert not [item for item in transport.calls if item[1] == "/api/generate"]


@pytest.mark.parametrize(
    ("environment", "message"),
    (
        ({"REI_OLLAMA_NUM_GPU": "999"}, "REI_OLLAMA_NUM_CTX"),
        (
            {
                "REI_OLLAMA_NUM_CTX": "32768",
                "REI_OLLAMA_NUM_GPU": "999",
            },
            "must equal 65536",
        ),
        (
            {
                "REI_OLLAMA_NUM_CTX": "65536",
                "REI_OLLAMA_NUM_GPU": "998",
            },
            "must equal 999",
        ),
        (
            {
                "REI_OLLAMA_MODEL": "gemma4:latest",
                "REI_OLLAMA_NUM_CTX": "65536",
                "REI_OLLAMA_NUM_GPU": "999",
            },
            "REI_OLLAMA_MODEL",
        ),
    ),
)
def test_environment_profile_is_exact(
    environment: Mapping[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        Gemma4EpistemicSettings.from_environment(environment)


@pytest.mark.parametrize(
    "change",
    (
        {"model": "gemma4:latest"},
        {"seed": 1},
        {"temperature": 0.1},
        {"top_p": 1.0},
        {"top_k": 32},
        {"num_ctx": 32768},
        {"num_gpu": 0},
        {"num_predict": 1024},
        {"keep_alive": "5m"},
        {"require_full_gpu": False},
        {"think": False},
        {"retry_count": 1},
    ),
)
def test_settings_reject_profile_drift(change: Mapping[str, object]) -> None:
    with pytest.raises(ValueError, match="must equal"):
        Gemma4EpistemicSettings(**change)


def test_provider_rejects_remote_alias_and_digest_drift() -> None:
    transport = FakeOllamaTransport()
    provider = _provider(transport)
    with pytest.raises(ValueError, match="local-only"):
        OllamaGemma4EpistemicProvider(
            client=OllamaApiClient(allow_remote=True, transport=transport),
            runtime=provider.runtime,
            settings=provider.settings,
            expected_digest=DIGEST,
        )
    with pytest.raises(ValueError, match="aliases"):
        OllamaGemma4EpistemicProvider(
            client=provider.client,
            runtime=OllamaRuntimeModel(
                server_version="0.31.2",
                model="gemma4:latest",
                digest=DIGEST,
                size_bytes=1,
                quantization_level="Q4_K_M",
                context_length=262144,
                capabilities=("completion", "thinking"),
            ),
            settings=provider.settings,
            expected_digest=DIGEST,
        )
    with pytest.raises(ValueError, match="differs"):
        OllamaGemma4EpistemicProvider(
            client=provider.client,
            runtime=provider.runtime,
            settings=provider.settings,
            expected_digest=OTHER_DIGEST,
        )
    with pytest.raises(ValueError, match="lowercase full model digest"):
        OllamaGemma4EpistemicProvider.discover(
            client=provider.client,
            expected_digest=DIGEST.upper(),
            environ=ENVIRONMENT,
        )


def test_tampered_call_is_rejected_before_chat() -> None:
    transport = FakeOllamaTransport()
    provider = _provider(transport)
    packet = _packet()
    payload = provider.build_call_spec(packet).model_dump(
        mode="python",
        round_trip=True,
    )
    payload["timeout_seconds"] += 1
    tampered = ProviderCallSpec.model_validate(payload)

    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        provider.execute(packet, call=tampered, clock=_clock())
    assert caught.value.failure_code == "request_contract_failure"
    assert transport.chat_count == 0


@pytest.mark.parametrize(
    ("mutate", "failure_code"),
    (
        (
            lambda response: response["message"].pop("thinking"),
            "thinking_separation_failure",
        ),
        (
            lambda response: response["message"].__setitem__("thinking", ""),
            "thinking_separation_failure",
        ),
        (
            lambda response: response["message"].__setitem__(
                "content",
                "<think>private</think>" + str(response["message"]["content"]),
            ),
            "thinking_separation_failure",
        ),
    ),
)
def test_thinking_must_be_separate_and_never_leaks_into_errors(
    mutate,
    failure_code: str,
) -> None:
    response = _response(thinking="TOP_SECRET_PRIVATE_TRACE")
    mutate(response)
    transport = FakeOllamaTransport(response)
    provider = _provider(transport)

    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        _execute(provider)
    assert caught.value.failure_code == failure_code
    assert transport.chat_count == 1
    assert "TOP_SECRET_PRIVATE_TRACE" not in str(caught.value)
    assert "TOP_SECRET_PRIVATE_TRACE" not in repr(caught.value.__dict__)


def test_extra_json_and_out_of_scope_citation_fail_closed() -> None:
    extra = json.loads(_output().model_dump_json())
    extra["unexpected"] = "field"
    extra_response = _response()
    extra_response["message"]["content"] = json.dumps(extra)
    extra_transport = FakeOllamaTransport(extra_response)
    extra_provider = _provider(extra_transport)
    with pytest.raises(Gemma4EpistemicExecutionError) as extra_error:
        _execute(extra_provider)
    assert extra_error.value.failure_code == "structured_output_invalid"
    assert extra_transport.chat_count == 1

    outside_response = _response(output=_output(cited=("observation_999",)))
    outside_transport = FakeOllamaTransport(outside_response)
    outside_provider = _provider(outside_transport)
    with pytest.raises(Gemma4EpistemicExecutionError) as outside_error:
        _execute(outside_provider)
    assert outside_error.value.failure_code == "conscious_access_rejected"
    assert outside_transport.chat_count == 1


def test_structured_output_failure_exposes_only_safe_diagnostics() -> None:
    valid = json.loads(_output().model_dump_json())
    extra = copy.deepcopy(valid)
    extra["TOP_SECRET_FIELD"] = "TOP_SECRET_VALUE"
    wrong_enum = copy.deepcopy(valid)
    wrong_enum["inferred_action_tendency"] = "TOP_SECRET_ENUM"
    cross_field = copy.deepcopy(valid)
    cross_field["action_confidence"] = 0.0
    missing = copy.deepcopy(valid)
    missing.pop("motive_unknown_reason")
    cases = (
        ("TOP_SECRET_INVALID_JSON {", "json_invalid", "$", None),
        (json.dumps(extra), "extra_forbidden", "$.*", None),
        (
            json.dumps(wrong_enum),
            "literal_error",
            "$.inferred_action_tendency",
            None,
        ),
        (
            json.dumps(cross_field),
            "value_error",
            "$",
            "claimed_action_zero_confidence",
        ),
        (
            json.dumps(missing),
            "missing",
            "$.motive_unknown_reason",
            None,
        ),
    )

    for final_content, expected_type, expected_path, expected_invariant in cases:
        response = _response(thinking="TOP_SECRET_PRIVATE_TRACE")
        response["message"]["content"] = final_content
        transport = FakeOllamaTransport(response)
        packet = _packet(visible_description="TOP_SECRET_PACKET_INPUT")

        with pytest.raises(Gemma4EpistemicExecutionError) as caught:
            _execute(_provider(transport), packet)

        error = caught.value
        diagnostics = error.sanitized_diagnostics()
        encoded_diagnostics = json.dumps(diagnostics, sort_keys=True)
        encoded_attributes = json.dumps(error.__dict__, sort_keys=True)
        assert error.failure_code == "structured_output_invalid"
        assert error.rejected_final_response_sha256 == hashlib.sha256(
            final_content.encode("utf-8")
        ).hexdigest()
        assert error.rejected_final_response_byte_count == len(
            final_content.encode("utf-8")
        )
        assert error.validation_issue_count == 1
        assert error.validation_error_type == expected_type
        assert error.validation_field_path == expected_path
        assert error.validation_invariant_code == expected_invariant
        assert len(error.validation_diagnostic_sha256 or "") == 64
        assert error.__cause__ is None
        assert error.__context__ is None
        assert "TOP_SECRET" not in str(error)
        assert "TOP_SECRET" not in repr(error)
        assert "TOP_SECRET" not in repr(error.__dict__)
        assert "TOP_SECRET" not in encoded_attributes
        assert "TOP_SECRET" not in encoded_diagnostics
        assert final_content not in encoded_diagnostics
        assert transport.chat_count == 1


def test_validation_diagnostics_are_stable_bounded_and_value_free() -> None:
    valid = json.loads(_output().model_dump_json())

    def capture(payload: Mapping[str, Any]) -> Gemma4EpistemicExecutionError:
        response = _response(thinking="TOP_SECRET_THINKING")
        response["message"]["content"] = json.dumps(payload)
        with pytest.raises(Gemma4EpistemicExecutionError) as caught:
            _execute(_provider(FakeOllamaTransport(response)))
        return caught.value

    first = copy.deepcopy(valid)
    first["inferred_action_tendency"] = "TOP_SECRET_FIRST"
    second = copy.deepcopy(valid)
    second["inferred_action_tendency"] = "TOP_SECRET_SECOND"
    first_error = capture(first)
    second_error = capture(second)
    assert (
        first_error.validation_diagnostic_sha256
        == second_error.validation_diagnostic_sha256
    )
    assert (
        first_error.rejected_final_response_sha256
        != second_error.rejected_final_response_sha256
    )

    claimed_action = copy.deepcopy(valid)
    claimed_action["action_confidence"] = 0.0
    claimed_action_error = capture(claimed_action)
    missing_reason = copy.deepcopy(valid)
    missing_reason["motive_unknown_reason"] = None
    missing_reason_error = capture(missing_reason)
    assert (
        claimed_action_error.validation_invariant_code
        == "claimed_action_zero_confidence"
    )
    claimed_action_alternative = copy.deepcopy(claimed_action)
    claimed_action_alternative["inferred_action_tendency"] = "connect"
    claimed_action_alternative_error = capture(claimed_action_alternative)
    assert (
        claimed_action_alternative_error.validation_diagnostic_sha256
        == claimed_action_error.validation_diagnostic_sha256
    )
    assert (
        claimed_action_alternative_error.rejected_final_response_sha256
        != claimed_action_error.rejected_final_response_sha256
    )
    assert (
        missing_reason_error.validation_invariant_code
        == "empty_motives_missing_unknown_reason"
    )
    assert (
        claimed_action_error.validation_diagnostic_sha256
        != missing_reason_error.validation_diagnostic_sha256
    )

    nested = json.loads(
        RacioEpistemicInterpretationV2(
            source_mind="E",
            cited_observation_ids=("observation_001",),
            inferred_action_tendency="perform",
            action_confidence=0.9,
            inferred_option_id="option_001",
            option_confidence=0.9,
            motive_hypotheses=(
                MotiveHypothesis(
                    family="motor_social",
                    subtype="motor_execution",
                    cited_observation_ids=("observation_001",),
                    confidence=0.8,
                    explanation_short_sl=MOTIVE_HYPOTHESIS_EXPLANATION_SL,
                ),
            ),
            motive_unknown_reason=None,
            unresolved_ambiguity=None,
        ).model_dump_json()
    )
    nested["motive_hypotheses"][0]["confidence"] = "TOP_SECRET_CONFIDENCE"
    nested_error = capture(nested)
    assert nested_error.validation_error_type == "float_type"
    assert (
        nested_error.validation_field_path
        == "$.motive_hypotheses[].confidence"
    )
    assert (
        nested_error.validation_diagnostic_sha256
        != first_error.validation_diagnostic_sha256
    )
    nested_family_mismatch = copy.deepcopy(nested)
    nested_family_mismatch["motive_hypotheses"][0]["confidence"] = 0.8
    nested_family_mismatch["motive_hypotheses"][0]["family"] = "scene"
    nested_family_mismatch_error = capture(nested_family_mismatch)
    assert nested_family_mismatch_error.validation_error_type == "value_error"
    assert (
        nested_family_mismatch_error.validation_field_path
        == "$.motive_hypotheses[]"
    )
    assert (
        nested_family_mismatch_error.validation_invariant_code
        == "motive_subtype_family_mismatch"
    )

    multiple = copy.deepcopy(valid)
    multiple["action_confidence"] = "TOP_SECRET_ACTION_CONFIDENCE"
    multiple["option_confidence"] = "TOP_SECRET_OPTION_CONFIDENCE"
    multiple_error = capture(multiple)
    assert multiple_error.validation_issue_count == 2
    assert multiple_error.validation_error_type == "float_type"
    assert multiple_error.validation_field_path == "$.action_confidence"
    assert "TOP_SECRET" not in json.dumps(
        multiple_error.sanitized_diagnostics(),
        sort_keys=True,
    )


@pytest.mark.parametrize(
    "attributes",
    (
        {"rejected_final_response_sha256": "a" * 64},
        {"rejected_final_response_byte_count": 1},
        {"validation_issue_count": 1},
        {"validation_error_type": "missing"},
        {"validation_field_path": "$.source_mind"},
        {"validation_invariant_code": "ambiguity_state_mismatch"},
        {"validation_diagnostic_sha256": "b" * 64},
    ),
)
def test_execution_error_rejects_partial_diagnostic_groups(
    attributes: Mapping[str, object],
) -> None:
    with pytest.raises(ValueError):
        Gemma4EpistemicExecutionError(
            "structured_output_invalid",
            "sanitized",
            **attributes,
        )


def test_execution_error_rejects_unrecognized_invariant_code() -> None:
    with pytest.raises(ValueError, match="invariant code is not sanitized"):
        Gemma4EpistemicExecutionError(
            "structured_output_invalid",
            "sanitized",
            rejected_final_response_sha256="a" * 64,
            rejected_final_response_byte_count=1,
            validation_issue_count=1,
            validation_error_type="value_error",
            validation_field_path="$",
            validation_invariant_code="TOP_SECRET_INVARIANT",
            validation_diagnostic_sha256="b" * 64,
        )


def test_execution_error_requires_value_error_for_invariant_code() -> None:
    with pytest.raises(ValueError, match="requires a value error"):
        Gemma4EpistemicExecutionError(
            "structured_output_invalid",
            "sanitized",
            rejected_final_response_sha256="a" * 64,
            rejected_final_response_byte_count=1,
            validation_issue_count=1,
            validation_error_type="missing",
            validation_field_path="$.motive_unknown_reason",
            validation_invariant_code="ambiguity_state_mismatch",
            validation_diagnostic_sha256="b" * 64,
        )


def test_invariant_classifier_requires_exact_context_shapes() -> None:
    known_message = "Unresolved ambiguity differs from the structured claim state"

    class ValueErrorSubclass(ValueError):
        pass

    class StringSubclass(str):
        pass

    class CustomMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            if key != "error":
                raise KeyError(key)
            return ValueError(known_message)

        def __iter__(self):
            return iter(("error",))

        def __len__(self) -> int:
            return 1

    class SyntheticValidationError:
        def __init__(self, context: object) -> None:
            self.context = context

        def errors(self, **options):
            assert options == {
                "include_url": False,
                "include_context": True,
                "include_input": False,
            }
            return [
                {
                    "type": "value_error",
                    "loc": (),
                    "msg": "TOP_SECRET_MESSAGE",
                    "ctx": self.context,
                }
            ]

    exact = gemma_provider._safe_validation_diagnostics(
        SyntheticValidationError({"error": ValueError(known_message)})
    )
    assert exact[3] == "ambiguity_state_mismatch"

    unsafe_contexts = (
        {"error": ValueErrorSubclass(known_message)},
        {"error": ValueError(known_message, "TOP_SECRET_SECOND_ARG")},
        {"error": ValueError(StringSubclass(known_message))},
        CustomMapping(),
        {"error": ValueError(known_message), "TOP_SECRET_EXTRA": True},
        {},
        {"error": ValueError("TOP_SECRET_UNKNOWN_MESSAGE")},
    )
    unclassified_fingerprints = set()
    for context in unsafe_contexts:
        diagnostics = gemma_provider._safe_validation_diagnostics(
            SyntheticValidationError(context)
        )
        assert diagnostics[3] is None
        assert "TOP_SECRET" not in repr(diagnostics)
        unclassified_fingerprints.add(diagnostics[4])
    assert len(unclassified_fingerprints) == 1


@pytest.mark.parametrize(
    ("configure", "failure_code"),
    (
        (
            lambda transport: setattr(
                transport,
                "post_call_digest",
                OTHER_DIGEST,
            ),
            "runtime_identity_mismatch",
        ),
        (
            lambda transport: setattr(transport, "active_context", 32768),
            "gpu_placement_failure",
        ),
        (
            lambda transport: setattr(transport, "active_size_vram", 999),
            "gpu_placement_failure",
        ),
        (
            lambda transport: setattr(transport, "active_remote", True),
            "gpu_placement_failure",
        ),
    ),
)
def test_runtime_digest_context_and_gpu_drift_fail_closed(
    configure,
    failure_code: str,
) -> None:
    transport = FakeOllamaTransport()
    configure(transport)
    provider = _provider(transport)
    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        _execute(provider)
    assert caught.value.failure_code == failure_code
    assert transport.chat_count == 1


def test_transport_failure_has_one_attempt_and_no_fallback() -> None:
    transport = FakeOllamaTransport()
    transport.fail_chat = True
    provider = _provider(transport)
    packet = _packet()
    call = provider.build_call_spec(packet)
    assert call.fallback_policy.mode == "none"

    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        provider.execute(packet, call=call, clock=_clock())
    assert caught.value.failure_code == "generation_contract_failure"
    assert transport.chat_count == 1


def test_transport_request_mutation_is_detected_without_retry() -> None:
    transport = FakeOllamaTransport()
    transport.mutate_request = True
    provider = _provider(transport)
    with pytest.raises(Gemma4EpistemicExecutionError) as caught:
        _execute(provider)
    assert caught.value.failure_code == "request_contract_failure"
    assert transport.chat_count == 1
