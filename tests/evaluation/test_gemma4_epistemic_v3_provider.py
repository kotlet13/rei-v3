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

from app.backend.rei.communication.epistemic_interpreter_v3 import (
    RacioEpistemicStructuralSidecarV3,
)
from app.backend.rei.ids import sha256_hex
from app.backend.rei.models.provider import ProviderCallSpec
from app.backend.rei.providers.native import DeterministicExecutionClock
from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaTransportError,
)
from app.backend.rei.providers.ollama_gemma4_epistemic import (
    GEMMA4_EPISTEMIC_MODEL,
    GEMMA4_EPISTEMIC_NUM_CTX,
    GEMMA4_EPISTEMIC_NUM_GPU,
    GEMMA4_EPISTEMIC_NUM_PREDICT,
    GEMMA4_EPISTEMIC_PARAMETER_COUNT,
    GEMMA4_EPISTEMIC_PROVIDER_REVISION,
)
from app.backend.rei.providers.ollama_gemma4_epistemic_v3 import (
    GEMMA4_EPISTEMIC_V3_INSTRUCTION,
    GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256,
    GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
    GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION,
    GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256,
    Gemma4EpistemicV3Execution,
    Gemma4EpistemicV3ExecutionError,
    OllamaGemma4EpistemicV3Provider,
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
        "created_at": "2026-07-17T10:00:00Z",
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


class FakeV3OllamaTransport:
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
    transport: FakeV3OllamaTransport,
) -> OllamaGemma4EpistemicV3Provider:
    return OllamaGemma4EpistemicV3Provider.discover(
        client=OllamaApiClient(transport=transport),
        environ=ENVIRONMENT,
    )


def _clock() -> DeterministicExecutionClock:
    return DeterministicExecutionClock(
        datetime(2026, 7, 17, tzinfo=timezone.utc)
    )


def _parameter_values(call: ProviderCallSpec) -> dict[str, object]:
    return {
        item.name: json.loads(item.canonical_json_value)
        for item in call.parameters
    }


def test_frozen_v2_provider_and_precommitted_p3_packet_are_unchanged() -> None:
    provider_path = (
        REPO_ROOT / "app/backend/rei/providers/ollama_gemma4_epistemic.py"
    )
    assert hashlib.sha256(provider_path.read_bytes()).hexdigest() == (
        "51b10fb2ac67491250d5cdb69d584b16bb33aa9765ffce9d7f29aa346fa854a8"
    )
    assert GEMMA4_EPISTEMIC_PROVIDER_REVISION == (
        "rei-racio-gemma4-epistemic-g2-chat-v6"
    )
    assert GEMMA4_EPISTEMIC_V3_PROVIDER_REVISION != (
        GEMMA4_EPISTEMIC_PROVIDER_REVISION
    )
    assert GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256 == (
        "321cecc980ec82346260b6ef3910a69a5f9b91233f101526254ff3e392704d6a"
    )
    assert P3_TECHNICAL_PACKET_V3.presentation_mode == "canonical_sl_only"
    assert P3_TECHNICAL_PACKET_V3.packet_hash == P3_TECHNICAL_PACKET_HASH
    assert len(P3_TECHNICAL_PACKET_V3.visible_observations) == 1
    assert len(P3_TECHNICAL_PACKET_V3.public_option_scope) == 2
    assert hashlib.sha256(
        P3_TECHNICAL_PACKET_V3.provider_payload_bytes()
    ).hexdigest() == (
        "45d123f7b1c1e1d1c9d24dc2d7199685cb49a8421e4dde140aed0963867a1d66"
    )


def test_recorded_p3_output_hashes_remain_valid() -> None:
    payload = _draft_payload()
    payload["action_hypotheses"][0]["confidence"] = 0.9
    payload["option_inference"]["confidence"] = 0.9
    transport = FakeV3OllamaTransport(_response(json.dumps(payload)))
    provider = _provider(transport)

    execution = provider.execute(
        P3_TECHNICAL_PACKET_V3,
        call=provider.build_call_spec(P3_TECHNICAL_PACKET_V3),
        clock=_clock(),
    )

    assert transport.chat_count == 1
    assert sha256_hex(execution.draft) == (
        "42fd718cefa995a7637e7acf53e8f15655f5abfe5db3b64b5a0fc949456ab2ba"
    )
    assert sha256_hex(execution.output) == (
        "286cb5b4e27874cb083b1a2dbaed811d9763d17956b5ec424f085d77a5cad505"
    )


def test_v3_happy_path_reuses_exact_profile_and_canonicalizes_once() -> None:
    transport = FakeV3OllamaTransport()
    provider = _provider(transport)
    packet = P3_TECHNICAL_PACKET_V3
    request = provider.request_payload(packet)
    call = provider.build_call_spec(packet)
    parameters = _parameter_values(call)

    assert request["messages"][0] == {
        "role": "system",
        "content": GEMMA4_EPISTEMIC_V3_INSTRUCTION,
    }
    assert request["messages"][1]["content"] == (
        packet.provider_payload_bytes().decode("utf-8")
    )
    assert request["format"] == gemma4_epistemic_v3_output_schema()
    for definition_name in (
        "ActionHypothesisDraftV3",
        "OptionInferenceDraftV3",
        "MotiveHypothesisDraftV3",
    ):
        confidence_schema = request["format"]["$defs"][definition_name][
            "properties"
        ]["confidence"]
        assert confidence_schema["exclusiveMinimum"] == 0.0
        assert "minimum" not in confidence_schema
    assert request["options"] == {
        "seed": 314159,
        "temperature": 0.0,
        "top_p": 0.95,
        "top_k": 64,
        "num_ctx": 65536,
        "num_gpu": 999,
        "num_predict": GEMMA4_EPISTEMIC_NUM_PREDICT,
    }
    assert "raw" not in request
    assert request["think"] is True
    assert request["stream"] is False
    assert parameters["instruction_sha256"] == (
        GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256
    )
    assert parameters["draft_schema_sha256"] == (
        GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256
    )
    assert parameters["model_digest"] == GEMMA4_EPISTEMIC_V3_MODEL_DIGEST
    assert parameters["retry_count"] == 0
    assert call.fallback_policy.mode == "none"

    execution = provider.execute(packet, call=call, clock=_clock())

    assert transport.chat_count == 1
    assert len([item for item in transport.calls if item[1] == "/api/chat"]) == 1
    assert not [item for item in transport.calls if item[1] == "/api/generate"]
    assert execution.output.action_hypotheses[0].subtype == "retreat"
    assert execution.output.option_inference is not None
    assert execution.output.option_inference.option_id == "option_001"
    assert execution.output.option_inference.cited_observation_ids == (
        "observation_001",
    )
    assert execution.output.cited_observation_ids == ("observation_001",)
    assert execution.response_evidence.structural_sidecar == (
        RacioEpistemicStructuralSidecarV3(
            option_id_present=True,
            motive_hypothesis_count=0,
        )
    )
    assert execution.response_evidence.active_context_length == 65536
    assert execution.response_evidence.active_gpu_percent_rounded == 100
    assert execution.response_evidence.model_call_count == 1
    assert execution.response_evidence.retry_count == 0
    assert execution.response_evidence.fallback_count == 0
    assert execution.call_record.status == "succeeded"
    assert execution.call_record.primary_status == "succeeded"
    assert execution.call_record.fallback is None
    serialized_evidence = execution.response_evidence.model_dump_json()
    assert "Private model reasoning" not in serialized_evidence
    assert execution.response_evidence.thinking_sha256 == hashlib.sha256(
        b"Private model reasoning that must never be persisted."
    ).hexdigest()
    assert execution.response_evidence.structured_output_hash == sha256_hex(
        execution.output
    )

    tampered_evidence = execution.response_evidence.model_copy(
        update={"packet_hash": "b" * 64}
    )
    with pytest.raises(ValueError, match="lineage is inconsistent"):
        Gemma4EpistemicV3Execution(
            draft=execution.draft,
            output=execution.output,
            call_spec=execution.call_spec,
            call_record=execution.call_record,
            response_evidence=tampered_evidence,
        )


@pytest.mark.parametrize(
    ("final_json", "expected_stage", "validation_fragment"),
    (
        (
            json.dumps(
                {
                    key: value
                    for key, value in _draft_payload().items()
                    if key != "option_inference"
                }
            ),
            "draft_v3_validation",
            "option_inference",
        ),
        (
            json.dumps(
                {
                    **_draft_payload(),
                    "action_hypotheses": [
                        {
                            **_draft_payload()["action_hypotheses"][0],
                            "cited_observation_ids": ["observation_999"],
                        }
                    ],
                }
            ),
            "canonicalizer_v3_validation",
            "outside visible packet scope",
        ),
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
    ),
)
def test_v3_validation_failures_stop_after_one_call_and_keep_only_final_json(
    final_json: str,
    expected_stage: str,
    validation_fragment: str,
) -> None:
    transport = FakeV3OllamaTransport(_response(final_json))
    provider = _provider(transport)
    packet = P3_TECHNICAL_PACKET_V3

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
    assert "Private model reasoning" not in json.dumps(error.p3_diagnostics())
    assert "Private model reasoning" not in str(error)


def test_inline_thinking_is_fingerprinted_but_never_retained_as_final_json() -> None:
    inline_private = "<think>private inline reasoning</think>"
    transport = FakeV3OllamaTransport(_response(inline_private))
    provider = _provider(transport)
    packet = P3_TECHNICAL_PACKET_V3

    with pytest.raises(Gemma4EpistemicV3ExecutionError) as caught:
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=_clock(),
        )

    error = caught.value
    assert transport.chat_count == 1
    assert error.failure_stage == "transport"
    assert error.failure_code == "thinking_separation_failure"
    assert error.final_json is None
    assert error.rejected_final_response_sha256 == hashlib.sha256(
        inline_private.encode("utf-8")
    ).hexdigest()
    assert error.rejected_final_response_byte_count == len(
        inline_private.encode("utf-8")
    )
    assert "private inline reasoning" not in str(error.p3_diagnostics())
    assert "private inline reasoning" not in str(error)
