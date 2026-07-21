from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from app.backend.rei.communication.epistemic_interpreter_en import (
    MOTIVE_UNKNOWN_REASON_EN,
    EnglishObservationV3,
    EnglishOptionV3,
    RacioEpistemicPacketEnV3,
)
from app.backend.rei.ids import sha256_hex
from app.backend.rei.models.provider import ProviderCallSpec
from app.backend.rei.providers.language_policy import (
    LOCAL_MODEL_LANGUAGE_POLICY_ID,
    LocalModelLanguagePolicyError,
)
from app.backend.rei.providers.native import DeterministicExecutionClock
from app.backend.rei.providers.ollama import OllamaApiClient, OllamaTransportError
from app.backend.rei.providers.ollama_gemma4_epistemic import (
    GEMMA4_EPISTEMIC_MODEL,
    GEMMA4_EPISTEMIC_NUM_CTX,
    GEMMA4_EPISTEMIC_NUM_GPU,
    GEMMA4_EPISTEMIC_PARAMETER_COUNT,
)
from app.backend.rei.providers.ollama_gemma4_epistemic_en import (
    GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION,
    OllamaGemma4EpistemicEnProvider,
)
from app.backend.rei.providers.ollama_gemma4_epistemic_en_explained import (
    GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION,
    GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION_SHA256,
    GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION,
    GEMMA4_EPISTEMIC_EN_EXPLAINED_SCHEMA_SHA256,
    OllamaGemma4EpistemicExplainedEnProvider,
    gemma4_epistemic_en_explained_output_schema,
)
from app.backend.rei.providers.ollama_gemma4_epistemic_v3 import (
    GEMMA4_EPISTEMIC_V3_INSTRUCTION,
    GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256,
    GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
    GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
    GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256,
    Gemma4EpistemicV3ExecutionError,
    P3_TECHNICAL_PACKET_HASH,
    P3_TECHNICAL_PACKET_V3,
    gemma4_epistemic_v3_output_schema,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT = {
    "REI_OLLAMA_MODEL": GEMMA4_EPISTEMIC_MODEL,
    "REI_OLLAMA_NUM_CTX": str(GEMMA4_EPISTEMIC_NUM_CTX),
    "REI_OLLAMA_NUM_GPU": str(GEMMA4_EPISTEMIC_NUM_GPU),
}


def _packet() -> RacioEpistemicPacketEnV3:
    return RacioEpistemicPacketEnV3.create(
        source_mind="E",
        visible_observations=(
            EnglishObservationV3(
                observation_id="observation_001",
                atomic_evidence_unit_id="atomic_001",
                signal_alias="signal_001",
                perception_status="clear",
                text="One clear backward step increases physical distance.",
                provenance="manifested",
            ),
        ),
        omitted_observation_ids=(),
        public_option_scope=(
            EnglishOptionV3(
                option_id="option_001",
                description="Move away from the marked point.",
            ),
            EnglishOptionV3(
                option_id="option_002",
                description="Move toward the marked point.",
            ),
        ),
        channel_quality=1.0,
        uncertainty=(
            "The direction and matching option are clear; the deeper motive is "
            "not visible."
        ),
    )


def _draft_payload() -> dict[str, Any]:
    return {
        "source_mind": "E",
        "action_hypotheses": [
            {
                "family": "protection_regulation",
                "subtype": "retreat",
                "family_fallback": None,
                "cited_observation_ids": ["observation_001"],
                "confidence": 0.95,
                "support_mode": "direct_manifestation",
            }
        ],
        "option_inference": {
            "option_id": "option_001",
            "cited_observation_ids": ["observation_001"],
            "confidence": 0.94,
        },
        "motive_hypotheses": [],
        "racio_reported_uncertainty": {
            "option_mapping": "not_uncertain",
            "motive_interpretation": "not_reported",
        },
    }


def _response(final_json: str | None = None) -> dict[str, Any]:
    return {
        "model": GEMMA4_EPISTEMIC_MODEL,
        "created_at": "2026-07-20T10:00:00Z",
        "message": {
            "role": "assistant",
            "content": final_json or json.dumps(_draft_payload()),
            "thinking": "Private model reasoning that must never be persisted.",
        },
        "done": True,
        "done_reason": "stop",
        "total_duration": 10,
        "load_duration": 2,
        "prompt_eval_count": 100,
        "prompt_eval_duration": 3,
        "eval_count": 20,
        "eval_duration": 5,
        "thinking_count": 7,
    }


class FakeEnglishOllamaTransport:
    def __init__(self, response: Mapping[str, Any] | None = None) -> None:
        self.response = dict(_response() if response is None else response)
        self.chat_count = 0
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []
        self.fail_chat = False

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
        self.calls.append(
            (method, path, None if payload is None else copy.deepcopy(payload))
        )
        if path == "/api/version":
            return {"version": "0.31.2"}
        if path == "/api/tags":
            return {
                "models": [
                    {
                        "name": GEMMA4_EPISTEMIC_MODEL,
                        "model": GEMMA4_EPISTEMIC_MODEL,
                        "digest": GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
                        "size": 19_868_969_920,
                        "details": {
                            "quantization_level": "Q4_K_M",
                            "context_length": 262144,
                        },
                        "capabilities": ["completion", "thinking", "tools"],
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
                "capabilities": ["completion", "thinking", "tools", "vision"],
            }
        if path == "/api/chat":
            self.chat_count += 1
            if self.fail_chat:
                raise OllamaTransportError("synthetic chat failure")
            return copy.deepcopy(self.response)
        if path == "/api/ps":
            return {
                "models": [
                    {
                        "name": GEMMA4_EPISTEMIC_MODEL,
                        "model": GEMMA4_EPISTEMIC_MODEL,
                        "digest": GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
                        "size": 1000,
                        "size_vram": 1000,
                        "context_length": GEMMA4_EPISTEMIC_NUM_CTX,
                    }
                ]
            }
        raise AssertionError(f"Unexpected Ollama path: {method} {path}")


def _provider(
    transport: FakeEnglishOllamaTransport,
) -> OllamaGemma4EpistemicEnProvider:
    provider = OllamaGemma4EpistemicEnProvider.discover(
        client=OllamaApiClient(transport=transport),
        environ=ENVIRONMENT,
    )
    assert isinstance(provider, OllamaGemma4EpistemicEnProvider)
    return provider


def _clock() -> DeterministicExecutionClock:
    return DeterministicExecutionClock(
        datetime(2026, 7, 20, tzinfo=timezone.utc)
    )


def _parameter_values(call: ProviderCallSpec) -> dict[str, object]:
    return {
        item.name: json.loads(item.canonical_json_value)
        for item in call.parameters
    }


def test_provider_has_new_revision_and_reuses_exact_frozen_v3_profile() -> None:
    transport = FakeEnglishOllamaTransport()
    provider = _provider(transport)
    call = provider.build_call_spec(_packet())
    parameters = _parameter_values(call)

    assert GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION == (
        "rei-racio-gemma4-epistemic-v3-en-chat-v1"
    )
    assert GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION != (
        GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION
    )
    assert provider.identity.implementation_revision.startswith(
        f"{GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION};"
    )
    assert provider.identity.model_revision == GEMMA4_EPISTEMIC_V3_MODEL_DIGEST
    assert parameters["instruction_sha256"] == (
        GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256
    )
    assert parameters["draft_schema_sha256"] == GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256
    assert parameters["local_model_language_policy_id"] == (
        LOCAL_MODEL_LANGUAGE_POLICY_ID
    )
    assert parameters["num_ctx"] == 65536
    assert parameters["num_gpu"] == 999
    assert parameters["retry_count"] == 0
    assert call.fallback_policy.mode == "none"


def test_provider_payload_is_english_only_and_reuses_exact_instruction() -> None:
    provider = _provider(FakeEnglishOllamaTransport())
    packet = _packet()
    payload = provider.request_payload(packet)
    user_content = payload["messages"][1]["content"]

    assert payload["messages"][0] == {
        "role": "system",
        "content": GEMMA4_EPISTEMIC_V3_INSTRUCTION,
    }
    assert user_content == packet.provider_payload_bytes().decode("utf-8")
    assert payload["format"] == gemma4_epistemic_v3_output_schema()
    assert "canonical_sl" not in user_content
    assert "operational_en" not in user_content
    assert '"language":"en"' in user_content


def test_language_policy_rejects_before_chat_transport() -> None:
    transport = FakeEnglishOllamaTransport()
    provider = _provider(transport)
    tampered = _packet().model_copy(update={"language": "sl"})

    with pytest.raises(LocalModelLanguagePolicyError) as error:
        provider.request_payload(tampered)  # type: ignore[arg-type]

    assert error.value.failure_code == "non_english_language"
    assert transport.chat_count == 0
    assert not [call for call in transport.calls if call[1] == "/api/chat"]


def test_success_uses_english_canonicalizer_and_private_thinking_hash_only() -> None:
    transport = FakeEnglishOllamaTransport()
    provider = _provider(transport)
    packet = _packet()
    call = provider.build_call_spec(packet)

    execution = provider.execute(packet, call=call, clock=_clock())

    assert transport.chat_count == 1
    assert execution.output.language == "en"
    assert execution.output.action_hypotheses[0].subtype == "retreat"
    assert execution.output.option_inference is not None
    assert execution.output.option_inference.option_id == "option_001"
    assert execution.output.motive_hypotheses == ()
    assert execution.output.motive_unknown_reason == MOTIVE_UNKNOWN_REASON_EN
    evidence = execution.response_evidence
    assert evidence.provider_revision == GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION
    assert evidence.language == "en"
    assert evidence.language_policy_id == LOCAL_MODEL_LANGUAGE_POLICY_ID
    assert evidence.active_context_length == 65536
    assert evidence.active_gpu_percent_rounded == 100
    assert evidence.model_call_count == 1
    assert evidence.retry_count == 0
    assert evidence.fallback_count == 0
    serialized = evidence.canonical_json_bytes().decode("utf-8")
    assert "Private model reasoning" not in serialized
    assert evidence.thinking_sha256 == hashlib.sha256(
        b"Private model reasoning that must never be persisted."
    ).hexdigest()


@pytest.mark.parametrize(
    ("final_json", "expected_stage", "validation_fragment"),
    (
        (
            (
                '{"source_mind":"E","source_mind":"I",'
                '"action_hypotheses":[],"option_inference":null,'
                '"motive_hypotheses":[],"racio_reported_uncertainty":'
                '{"option_mapping":"not_reported",'
                '"motive_interpretation":"not_reported"}}'
            ),
            "draft_v3_validation",
            "duplicate_json_key",
        ),
        (
            json.dumps(
                {
                    **_draft_payload(),
                    "action_hypotheses": [
                        {
                            **_draft_payload()["action_hypotheses"][0],
                            "cited_observation_ids": ["observation_outside"],
                        }
                    ],
                }
            ),
            "canonicalizer_v3_validation",
            "outside visible English packet scope",
        ),
        (
            json.dumps(
                {
                    **_draft_payload(),
                    "option_inference": {
                        **_draft_payload()["option_inference"],
                        "option_id": "option_outside",
                    },
                }
            ),
            "canonicalizer_v3_validation",
            "outside public English option scope",
        ),
    ),
)
def test_english_validation_failures_stop_after_one_chat_without_evidence(
    final_json: str,
    expected_stage: str,
    validation_fragment: str,
) -> None:
    transport = FakeEnglishOllamaTransport(_response(final_json))
    provider = _provider(transport)
    packet = _packet()

    with pytest.raises(Gemma4EpistemicV3ExecutionError) as caught:
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=_clock(),
        )

    error = caught.value
    assert transport.chat_count == 1
    assert error.failure_stage == expected_stage
    assert error.final_json == final_json
    assert error.validation_error is not None
    assert validation_fragment in error.validation_error
    assert "Private model reasoning" not in str(error)
    assert "Private model reasoning" not in json.dumps(error.p3_diagnostics())


def test_english_call_contract_failure_stops_before_chat() -> None:
    transport = FakeEnglishOllamaTransport()
    provider = _provider(transport)
    packet = _packet()
    call = provider.build_call_spec(packet).model_copy(
        update={"timeout_seconds": 1.0}
    )

    with pytest.raises(Gemma4EpistemicV3ExecutionError) as caught:
        provider.execute(packet, call=call, clock=_clock())

    assert caught.value.failure_stage == "transport"
    assert transport.chat_count == 0


def test_english_transport_failure_is_one_attempt_without_evidence() -> None:
    transport = FakeEnglishOllamaTransport()
    transport.fail_chat = True
    provider = _provider(transport)
    packet = _packet()

    with pytest.raises(Gemma4EpistemicV3ExecutionError) as caught:
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=_clock(),
        )

    assert caught.value.failure_stage == "transport"
    assert transport.chat_count == 1


def test_frozen_v3_instruction_schema_packet_and_source_files_are_unchanged() -> None:
    assert GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256 == (
        "470bb45de824a438aafdbb3efeae924c71d2bfce844eddf69597443b06bfc30d"
    )
    assert GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256 == (
        "321cecc980ec82346260b6ef3910a69a5f9b91233f101526254ff3e392704d6a"
    )
    assert P3_TECHNICAL_PACKET_HASH == (
        "e13b268ae91605638943094a643534689b9e833f2240c9b778fac77bfd990de4"
    )
    assert P3_TECHNICAL_PACKET_V3.packet_hash == P3_TECHNICAL_PACKET_HASH
    assert sha256_hex(P3_TECHNICAL_PACKET_V3.provider_payload()) == (
        "45d123f7b1c1e1d1c9d24dc2d7199685cb49a8421e4dde140aed0963867a1d66"
    )
    frozen_hashes = {
        "app/backend/rei/providers/ollama_gemma4_epistemic_v3.py": (
            "b5beb2dc3807b5bb3cc00e0385b8c93cd89365693cd22314eefa78af4fdfc882"
        ),
        "app/backend/rei/communication/epistemic_interpreter_v3.py": (
            "c2e70ddccccb8b2d3fe865d2a97a89fa3b5fe4d25f135b501e53f479347f24af"
        ),
    }
    for relative_path, expected in frozen_hashes.items():
        actual = hashlib.sha256((REPO_ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected


def _explained_provider(
    transport: FakeEnglishOllamaTransport,
) -> OllamaGemma4EpistemicExplainedEnProvider:
    provider = OllamaGemma4EpistemicExplainedEnProvider.discover(
        client=OllamaApiClient(transport=transport),
        environ=ENVIRONMENT,
    )
    assert isinstance(provider, OllamaGemma4EpistemicExplainedEnProvider)
    return provider


def _explained_draft_payload(*, full_abstention: bool = False) -> dict[str, Any]:
    semantic = _draft_payload()
    if full_abstention:
        semantic["action_hypotheses"] = []
        semantic["option_inference"] = None
    semantic.update(
        {
            "action_abstention_explanation": (
                {
                    "explanation": (
                        "The visible observation does not display a supported action."
                    ),
                    "cited_observation_ids": ["observation_001"],
                }
                if full_abstention
                else None
            ),
            "option_abstention_explanation": (
                {
                    "explanation": (
                        "The visible observation does not distinguish a public option."
                    ),
                    "cited_observation_ids": ["observation_001"],
                }
                if full_abstention
                else None
            ),
            "motive_abstention_explanation": {
                "explanation": (
                    "The visible movement supplies no independent evidence of a motive."
                ),
                "cited_observation_ids": ["observation_001"],
            },
        }
    )
    return semantic


def test_explained_provider_is_additive_and_uses_exact_names() -> None:
    provider = _explained_provider(FakeEnglishOllamaTransport())
    parameters = _parameter_values(provider.build_call_spec(_packet()))

    assert GEMMA4_EPISTEMIC_EN_EXPLAINED_PROVIDER_REVISION == (
        "rei-racio-gemma4-epistemic-v3-en-explained-chat-v1"
    )
    assert GEMMA4_EPISTEMIC_EN_PROVIDER_REVISION == (
        "rei-racio-gemma4-epistemic-v3-en-chat-v1"
    )
    assert parameters["instruction_sha256"] == (
        GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION_SHA256
    )
    assert parameters["draft_schema_sha256"] == (
        GEMMA4_EPISTEMIC_EN_EXPLAINED_SCHEMA_SHA256
    )
    assert "Emocio, Instinkt, and Racio exactly" in (
        GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION
    )
    assert "Emotion" not in GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION
    assert "Instinct" not in GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION


def test_explained_request_is_exact_english_and_closed() -> None:
    provider = _explained_provider(FakeEnglishOllamaTransport())
    packet = _packet()
    payload = provider.request_payload(packet)

    assert payload["messages"] == [
        {
            "role": "system",
            "content": GEMMA4_EPISTEMIC_EN_EXPLAINED_INSTRUCTION,
        },
        {
            "role": "user",
            "content": packet.provider_payload_bytes().decode("utf-8"),
        },
    ]
    assert payload["format"] == gemma4_epistemic_en_explained_output_schema()
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert "canonical_sl" not in serialized
    assert "native_truth" not in serialized
    assert "GovernanceMandate" not in serialized


def test_explained_success_persists_exact_request_and_model_explanation() -> None:
    final_json = json.dumps(_explained_draft_payload())
    transport = FakeEnglishOllamaTransport(_response(final_json))
    provider = _explained_provider(transport)
    packet = _packet()

    execution = provider.execute(
        packet,
        call=provider.build_call_spec(packet),
        clock=_clock(),
    )

    assert transport.chat_count == 1
    assert execution.output.action_hypotheses[0].subtype == "retreat"
    assert execution.output.option_inference is not None
    assert execution.output.motive_hypotheses == ()
    explanation = execution.draft.motive_abstention_explanation
    assert explanation is not None
    assert explanation.cited_observation_ids == ("observation_001",)
    evidence = execution.response_evidence
    assert evidence.exact_model_request == provider.request_payload(packet)
    assert evidence.exact_model_request_hash == evidence.request_payload_hash
    assert evidence.abstention_explanations_authority is False
    assert evidence.abstention_explanations_semantic_claim_evidence is False
    serialized = evidence.canonical_json_bytes().decode("utf-8")
    assert "Private model reasoning" not in serialized


def test_explained_full_abstention_requires_concrete_scoped_explanations() -> None:
    final_json = json.dumps(_explained_draft_payload(full_abstention=True))
    transport = FakeEnglishOllamaTransport(_response(final_json))
    provider = _explained_provider(transport)
    packet = _packet()

    execution = provider.execute(
        packet,
        call=provider.build_call_spec(packet),
        clock=_clock(),
    )

    assert execution.output.action_hypotheses == ()
    assert execution.output.option_inference is None
    assert execution.output.motive_hypotheses == ()
    assert execution.draft.action_abstention_explanation is not None
    assert execution.draft.option_abstention_explanation is not None
    assert execution.draft.motive_abstention_explanation is not None


@pytest.mark.parametrize("failure", ("missing", "outside_scope"))
def test_invalid_explanation_fails_closed_after_one_attempt(failure: str) -> None:
    payload = _explained_draft_payload(full_abstention=True)
    if failure == "missing":
        payload["action_abstention_explanation"] = None
    else:
        payload["action_abstention_explanation"]["cited_observation_ids"] = [
            "observation_outside"
        ]
    transport = FakeEnglishOllamaTransport(_response(json.dumps(payload)))
    provider = _explained_provider(transport)
    packet = _packet()

    with pytest.raises(Gemma4EpistemicV3ExecutionError) as caught:
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=_clock(),
        )

    assert transport.chat_count == 1
    if failure == "missing":
        assert caught.value.failure_stage == "draft_v3_validation"
    else:
        assert caught.value.failure_stage == "canonicalizer_v3_validation"
        assert "outside visible English packet scope" in str(
            caught.value.validation_error
        )
