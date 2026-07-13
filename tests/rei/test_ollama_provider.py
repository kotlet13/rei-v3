from __future__ import annotations

import json
import subprocess
import sys
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

import pytest
from pydantic import ValidationError

from app.backend.rei.ego.trace_store import FileEgoTraceStore
from app.backend.rei.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei.persistence import FileArtifactStore, validate_run_id
from app.backend.rei.providers.native import DeterministicExecutionClock
from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaRacioNativeProvider,
    OllamaRacioSettings,
    OllamaResponseError,
    OllamaTransportError,
    UrllibOllamaTransport,
    build_ollama_racio_native_providers,
)
from app.backend.rei.racio.packets import build_racio_packet


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
DIGEST = "3f3e5df8a021439fd6f867a0e526bdc303cac79c811201cb6bac193298cb9fcd"


def _cycle_request() -> ReiNativeCycleRequest:
    return ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())


def _packet():
    source = _cycle_request()
    return build_racio_packet(
        source.scene,
        source.racio_world,
        symbolic_and_language_cues=source.symbolic_and_language_cues,
        numeric_cues=source.numeric_cues,
        time=source.time_cues,
        rules=source.explicit_rules,
        explicit_consequences=source.explicit_consequences,
    )


def _structured_payload(packet) -> dict[str, Any]:
    return {
        "option_id": packet.allowed_option_ids[0],
        "facts_used": [packet.explicit_facts[0], packet.world.facts[0]],
        "evidence_ids_used": [packet.evidence_ids[0]],
        "unknowns": [packet.explicit_unknowns[0]],
        "causal_sequence": ["inspect packet, compare options, select"],
        "utility_structure": ["compare explicit consequences"],
        "explicit_goal": "Select one allowed option from grounded inputs.",
        "main_objection": "The supplied outcome remains unknown.",
        "confidence": 0.7,
        "abstains": False,
        "uncertainty": "The supplied unknown remains unresolved.",
    }


class FakeOllamaTransport:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []
        self.fail_generate = False
        self.remote_tags = False
        self.remote_generate = False
        self.post_generate_digest: str | None = None
        self.digest = DIGEST
        self.done_reason = "stop"
        self.thinking: str | None = None

    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        if url.endswith("/api/version"):
            return {"version": "0.31.2"}
        if url.endswith("/api/tags"):
            return {
                "models": [
                    {
                        "name": "granite4.1:30b",
                        "model": "granite4.1:30b",
                        "digest": self.digest,
                        "size": 17_490_259_354,
                        "details": {
                            "quantization_level": "Q4_K_M",
                        },
                        **(
                            {
                                "remote_model": "cloud/granite",
                                "remote_host": "https://ollama.com",
                            }
                            if self.remote_tags
                            else {}
                        ),
                    }
                ]
            }
        if url.endswith("/api/show"):
            return {
                "capabilities": ["completion", "tools"],
                "details": {"quantization_level": "Q4_K_M"},
                "model_info": {
                    "general.architecture": "granite",
                    "granite.context_length": 131072,
                },
            }
        if url.endswith("/api/generate"):
            if self.fail_generate:
                raise OllamaTransportError("synthetic transport failure")
            response = {
                "model": "granite4.1:30b",
                "created_at": "2026-07-13T14:00:00Z",
                "response": self.response_text,
                "done": True,
                "done_reason": self.done_reason,
                "total_duration": 10,
                "load_duration": 2,
                "prompt_eval_count": 300,
                "prompt_eval_duration": 3,
                "eval_count": 120,
                "eval_duration": 5,
            }
            if self.thinking is not None:
                response["thinking"] = self.thinking
            if self.remote_generate:
                response.update(
                    {
                        "remote_model": "cloud/granite",
                        "remote_host": "https://ollama.com",
                    }
                )
            if self.post_generate_digest is not None:
                self.digest = self.post_generate_digest
            return response
        if url.endswith("/api/ps"):
            return {
                "models": [
                    {
                        "name": "granite4.1:30b",
                        "model": "granite4.1:30b",
                        "digest": self.digest,
                        "size": 17_490_259_354,
                        "size_vram": 17_490_259_354,
                        "context_length": 65536,
                    }
                ]
            }
        raise AssertionError(f"Unexpected fake Ollama URL: {url}")


def _provider(
    packet,
    *,
    response_text: str | None = None,
) -> tuple[OllamaRacioNativeProvider, FakeOllamaTransport]:
    transport = FakeOllamaTransport(
        response_text or json.dumps(_structured_payload(packet))
    )
    client = OllamaApiClient(transport=transport)
    provider = OllamaRacioNativeProvider.discover(
        client=client,
        settings=OllamaRacioSettings(require_full_gpu=True),
        expected_digest=DIGEST,
    )
    return provider, transport


def test_settings_map_explicit_gpu_environment() -> None:
    settings = OllamaRacioSettings.from_environment(
        {
            "REI_OLLAMA_MODEL": "granite4.1:30b",
            "REI_OLLAMA_SEED": "17",
            "REI_OLLAMA_NUM_CTX": "65536",
            "REI_OLLAMA_NUM_GPU": "999",
            "REI_OLLAMA_NUM_PREDICT": "1024",
            "REI_OLLAMA_KEEP_ALIVE": "10m",
            "REI_OLLAMA_REQUIRE_FULL_GPU": "true",
        }
    )

    assert settings.seed == 17
    assert settings.num_ctx == 65536
    assert settings.num_gpu == 999
    assert settings.num_predict == 1024
    assert settings.require_full_gpu is True


def test_client_rejects_remote_endpoint_without_opt_in() -> None:
    with pytest.raises(ValueError, match="allow_remote"):
        OllamaApiClient(base_url="http://example.invalid:11434")

    client = OllamaApiClient(
        base_url="https://example.invalid:11434",
        allow_remote=True,
        transport=FakeOllamaTransport("{}"),
    )
    assert client.base_url == "https://example.invalid:11434"


def test_default_transport_refuses_http_redirects() -> None:
    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            self.send_response(302)
            self.send_header("Location", "https://example.invalid/prompt-leak")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(OllamaTransportError, match="status 302"):
            UrllibOllamaTransport().request_json(
                method="GET",
                url=f"http://127.0.0.1:{server.server_port}/redirect",
                payload=None,
                timeout_seconds=2.0,
                max_response_bytes=1024,
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def test_ollama_native_racio_closes_model_and_response_provenance() -> None:
    packet = _packet()
    provider, transport = _provider(packet)
    call = provider.build_call_spec(packet)

    execution = provider.execute(
        packet,
        call=call,
        clock=DeterministicExecutionClock(_cycle_request().started_at),
    )

    generate = next(item for item in transport.calls if item["url"].endswith("/api/generate"))
    payload = generate["payload"]
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["raw"] is False
    assert payload["logprobs"] is False
    assert payload["truncate"] is False
    assert payload["shift"] is False
    assert payload["options"] == {
        "seed": 314159,
        "temperature": 0.0,
        "num_ctx": 65536,
        "num_gpu": 999,
        "num_predict": 1536,
    }
    assert payload["format"]["additionalProperties"] is False
    prompt = json.loads(payload["prompt"])
    assert {
        "character",
        "character_authority",
        "profile_id",
        "emocio_native_conclusion",
        "instinkt_native_conclusion",
    }.isdisjoint(prompt)
    assert provider.identity.uses_model is True
    assert provider.identity.model_revision == DIGEST
    assert call.request_id == packet.packet_id
    assert call.seed == 314159
    assert call.fallback_policy.mode == "none"
    recorded = {
        item.name: json.loads(item.canonical_json_value)
        for item in call.parameters
    }
    assert recorded["num_ctx"] == 65536
    assert recorded["num_gpu"] == 999
    assert recorded["require_full_gpu"] is True
    assert recorded["raw"] is False
    assert recorded["logprobs"] is False
    assert recorded["truncate"] is False
    assert recorded["shift"] is False
    assert recorded["stream"] is False
    assert execution.call_record.output_artifact_ids == (
        execution.reasoning_artifact.result_id,
        execution.conclusion.conclusion_id,
    )
    assert execution.conclusion.reasoning_provider_result_id == (
        execution.reasoning_artifact.result_id
    )
    assert execution.conclusion.reasoning_provider_result_hash == (
        execution.reasoning_artifact.content_hash()
    )
    assert execution.reasoning_artifact.model_revision == DIGEST
    assert execution.reasoning_artifact.active_context_length == 65536
    assert execution.reasoning_artifact.active_gpu_percent_rounded == 100


@pytest.mark.parametrize(
    ("done_reason", "thinking", "message"),
    (
        ("length", None, "stop cleanly"),
        ("stop", "private chain", "unapproved thinking"),
    ),
)
def test_ollama_native_racio_rejects_incomplete_or_unapproved_output(
    done_reason: str,
    thinking: str | None,
    message: str,
) -> None:
    packet = _packet()
    provider, transport = _provider(packet)
    transport.done_reason = done_reason
    transport.thinking = thinking

    with pytest.raises(OllamaResponseError, match=message):
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=DeterministicExecutionClock(_cycle_request().started_at),
        )


def test_ollama_response_evidence_rejects_noncanonical_id_and_cross_lineage() -> None:
    packet = _packet()
    provider, transport = _provider(packet)
    execution = provider.execute(
        packet,
        call=provider.build_call_spec(packet),
        clock=DeterministicExecutionClock(_cycle_request().started_at),
    )
    payload = execution.reasoning_artifact.model_dump(mode="python", round_trip=True)
    payload["result_id"] = "forged_result_id"

    with pytest.raises(ValidationError, match="content-addressed"):
        type(execution.reasoning_artifact).model_validate(payload)

    tampered_artifact = execution.reasoning_artifact.model_copy(
        update={"packet_hash": "0" * 64}
    )
    tampered_conclusion = execution.conclusion.model_copy(
        update={
            "reasoning_provider_result_hash": tampered_artifact.content_hash(),
        }
    )
    with pytest.raises(ValueError, match="inconsistent lineage"):
        type(execution)(
            conclusion=tampered_conclusion,
            call_spec=execution.call_spec,
            call_record=execution.call_record,
            reasoning_artifact=tampered_artifact,
        )


@pytest.mark.parametrize("mutation", ("malformed", "extra", "fact", "option"))
def test_ollama_native_racio_rejects_untrusted_output(mutation: str) -> None:
    packet = _packet()
    payload = deepcopy(_structured_payload(packet))
    if mutation == "malformed":
        text = "not json"
    else:
        if mutation == "extra":
            payload["character_authority"] = "R>E>I"
        elif mutation == "fact":
            payload["facts_used"] = ["A hallucinated fact."]
        else:
            payload["option_id"] = "option_not_in_packet"
        text = json.dumps(payload)
    provider, _ = _provider(packet, response_text=text)

    with pytest.raises(OllamaResponseError):
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=DeterministicExecutionClock(_cycle_request().started_at),
        )


def test_ollama_native_racio_rejects_tampered_call_before_transport() -> None:
    packet = _packet()
    provider, transport = _provider(packet)
    call = provider.build_call_spec(packet).model_copy(
        update={"timeout_seconds": 1.0}
    )

    with pytest.raises(ValueError, match="canonical contract"):
        provider.execute(
            packet,
            call=call,
            clock=DeterministicExecutionClock(_cycle_request().started_at),
        )

    assert not any(item["url"].endswith("/api/generate") for item in transport.calls)


def test_ollama_native_racio_has_no_hidden_transport_fallback() -> None:
    packet = _packet()
    provider, transport = _provider(packet)
    transport.fail_generate = True
    call = provider.build_call_spec(packet)

    with pytest.raises(OllamaTransportError):
        provider.execute(
            packet,
            call=call,
            clock=DeterministicExecutionClock(_cycle_request().started_at),
        )

    assert call.fallback_policy.mode == "none"
    assert sum(item["url"].endswith("/api/generate") for item in transport.calls) == 1


def test_ollama_provider_rejects_remote_or_changed_model_provenance() -> None:
    packet = _packet()
    remote_transport = FakeOllamaTransport(json.dumps(_structured_payload(packet)))
    remote_transport.remote_tags = True
    with pytest.raises(OllamaResponseError, match="remote"):
        OllamaRacioNativeProvider.discover(
            client=OllamaApiClient(transport=remote_transport),
            settings=OllamaRacioSettings(),
        )

    provider, transport = _provider(packet)
    transport.remote_generate = True
    with pytest.raises(OllamaResponseError, match="remote"):
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=DeterministicExecutionClock(_cycle_request().started_at),
        )

    provider, transport = _provider(packet)
    transport.post_generate_digest = "a" * 64
    with pytest.raises(OllamaResponseError, match="digest"):
        provider.execute(
            packet,
            call=provider.build_call_spec(packet),
            clock=DeterministicExecutionClock(_cycle_request().started_at),
        )


def test_engine_persists_mixed_provider_evidence_and_verifies_cold(
    tmp_path: Path,
) -> None:
    request_value = _cycle_request().model_copy(
        update={"run_id": "b14-fake-ollama-engine", "ego_id": "b14-fake-ollama-ego"}
    )
    packet = _packet()
    provider, transport = _provider(packet)
    runs_root = tmp_path / "runs"
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(runs_root),
        ego_trace_store=FileEgoTraceStore(tmp_path / "ego_traces"),
        providers=build_ollama_racio_native_providers(provider),
        clock=DeterministicExecutionClock(request_value.started_at),
    )

    result = engine.run_cycle(request_value)

    native_providers = result.manifest.providers[:3]
    assert [item.uses_model for item in native_providers] == [True, False, False]
    assert len(result.manifest.seeds) == 1
    assert result.manifest.seeds[0].seed == 314159
    assert result.invariants.all_passed
    assert len(result.stored_artifacts) == 46
    evidence_path = runs_root / request_value.run_id / "native" / "racio_reasoning_evidence.json"
    assert evidence_path.is_file()
    assert FileArtifactStore(runs_root).verify_run(request_value.run_id) == result.manifest
    assert sum(item["url"].endswith("/api/generate") for item in transport.calls) == 1


def test_smoke_runner_help_does_not_contact_ollama() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/run_rei_native_ollama_smoke.py", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Ollama-backed Racio only" in completed.stdout


def test_smoke_runner_default_run_id_is_store_safe() -> None:
    from scripts.run_rei_native_ollama_smoke import _default_run_id, _summary_target

    run_id = _default_run_id()
    assert run_id == run_id.casefold()
    assert validate_run_id(run_id) == run_id
    with pytest.raises(ValueError, match="manifest-owned"):
        _summary_target(
            ROOT / "output" / "runs" / run_id / "summary.json",
            runs_root=(ROOT / "output" / "runs").resolve(),
        )
