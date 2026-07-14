from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from app.backend.rei.communication.structured_interpreter import (
    StructuredLLMRacioInterpreter,
)
from app.backend.rei.ego.trace_store import FileEgoTraceStore
from app.backend.rei.engine import ReiNativeEngine, _validated_c3_results
from app.backend.rei.ids import canonical_json_bytes
from app.backend.rei.models.provider import (
    ProviderFallbackPlan,
    ProviderFallbackPolicy,
    ProviderIdentity,
)
from app.backend.rei.persistence import FileArtifactStore
from app.backend.rei.providers.native import DeterministicExecutionClock
from app.backend.rei.providers.ollama import OllamaApiClient, OllamaRacioSettings
from app.backend.rei.providers.ollama_interpreter import (
    OllamaStructuredRacioInterpreterProvider,
)
from tests.rei.test_engine import _request
from tests.rei.test_ollama_interpreter import DIGEST, FakeOllamaTransport


class _CycleOllamaTransport(FakeOllamaTransport):
    """Return a source-correct abstention for each engine communication call."""

    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        if url.endswith("/api/generate"):
            assert payload is not None
            packet_payload = json.loads(str(payload["prompt"]))
            observations = packet_payload["visible_observations"]
            citations = (
                [observations[0]["observation_id"]] if observations else []
            )
            self.response_text = json.dumps(
                {
                    "source_mind": packet_payload["source_mind"],
                    "cited_observation_ids": citations,
                    "inferred_option_id": None,
                    "inferred_action_tendency": "unknown",
                    "inferred_motive_class": "unknown",
                    "confidence": 0.25 if citations else 0.0,
                    "alternative_hypotheses": (
                        ["The visible signal supports more than one option."]
                        if citations
                        else []
                    ),
                    "unresolved_ambiguity": (
                        "The visible signal is insufficient to select an option."
                    ),
                }
            )
        return super().request_json(
            method=method,
            url=url,
            payload=payload,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
        )


def _files_below(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_engine_persists_both_model_c3_calls_and_scene_public_scope(
    tmp_path: Path,
) -> None:
    request = _request()
    root = tmp_path / "c3-engine"
    clock = DeterministicExecutionClock(request.started_at)
    transport = _CycleOllamaTransport("{}")
    provider = OllamaStructuredRacioInterpreterProvider.discover(
        client=OllamaApiClient(transport=transport),
        settings=OllamaRacioSettings(require_full_gpu=True),
        expected_digest=DIGEST,
    )
    interpreter = StructuredLLMRacioInterpreter(
        provider=provider,
        language="sl",
        option_descriptions={"wrong_static_option": "Wrong static description."},
        clock=clock,
    )
    store = FileArtifactStore(root / "runs")
    engine = ReiNativeEngine(
        artifact_store=store,
        ego_trace_store=FileEgoTraceStore(root / "ego_traces"),
        clock=clock,
        interpreter=interpreter,
    )

    result = engine.run_cycle(request)

    generate_calls = tuple(
        call for call in transport.calls if call["url"].endswith("/api/generate")
    )
    assert len(generate_calls) == 2
    c3_results = (
        result.emocio_communication.c3_result,
        result.instinkt_communication.c3_result,
    )
    assert all(item is not None for item in c3_results)
    validated_results = tuple(item for item in c3_results if item is not None)
    assert tuple(item.access.packet.source_mind for item in validated_results) == (
        "E",
        "I",
    )

    scene_descriptions = {
        option.option_id: option.description for option in request.scene.options
    }
    for item, generate_call in zip(
        validated_results,
        generate_calls,
        strict=True,
    ):
        packet = item.access.packet
        audit = item.access.audit
        assert packet.language == request.scene.language == "en"
        assert {
            audit.source_option_id(option.option_id): option.description
            for option in packet.public_option_scope
        } == scene_descriptions
        prompt = str(generate_call["payload"]["prompt"])
        assert prompt == packet.provider_payload_bytes().decode("utf-8")
        assert all(description in prompt for description in scene_descriptions.values())
        assert all(option_id not in prompt for option_id in scene_descriptions)
        assert request.acceptance_state.acceptance_state_id not in prompt
        assert audit.audit_id not in prompt

    manifest = result.manifest
    assert tuple(spec.provider.provider_id for spec in manifest.provider_call_specs[3:]) == (
        provider.identity.provider_id,
        provider.identity.provider_id,
    )
    assert tuple(call.provider.provider_id for call in manifest.provider_calls[3:]) == (
        provider.identity.provider_id,
        provider.identity.provider_id,
    )
    assert len(manifest.provider_call_specs) == len(manifest.provider_calls) == 5
    assert sum(
        identity == provider.identity for identity in manifest.providers
    ) == 1
    assert {
        (seed.call_id, seed.provider_id, seed.seed) for seed in manifest.seeds
    } == {
        (
            item.execution.call_record.call_id,
            provider.identity.provider_id,
            provider.settings.seed,
        )
        for item in validated_results
    }

    run_directory = root / "runs" / request.run_id
    files = _files_below(run_directory)
    for label, item, communication in zip(
        ("emocio", "instinkt"),
        validated_results,
        (result.emocio_communication, result.instinkt_communication),
        strict=True,
    ):
        prefix = f"communication/c3_{label}"
        expected = {
            "interpreter_request.json": communication.request,
            "access_packet.json": item.access.packet,
            "access_audit.json": item.access.audit,
            "call_spec.json": item.execution.call_spec,
            "call_record.json": item.execution.call_record,
            "structured_output.json": item.execution.output,
            "response_evidence.json": item.execution.response_evidence,
        }
        for filename, artifact in expected.items():
            stem = filename.removesuffix(".json")
            assert files[f"{prefix}_{stem}.json"] == canonical_json_bytes(artifact)

    inventory_paths = {
        artifact.relative_path for artifact in manifest.artifact_inventory
    }
    assert {
        f"communication/c3_{label}_{filename}"
        for label in ("emocio", "instinkt")
        for filename in (
            "interpreter_request.json",
            "access_packet.json",
            "access_audit.json",
            "call_spec.json",
            "call_record.json",
            "structured_output.json",
            "response_evidence.json",
        )
    }.issubset(inventory_paths)
    assert store.verify_run(request.run_id) == manifest

    first = validated_results[0]
    fallback_identity = ProviderIdentity(
        provider_id="provider_c3_forbidden_fallback",
        kind="text_reasoner",
        implementation="tests.c3.ForbiddenFallback",
        implementation_revision="1",
        uses_model=False,
    )
    tampered_spec = first.execution.call_spec.model_copy(
        update={
            "fallback_policy": ProviderFallbackPolicy(
                mode="provider",
                plan=ProviderFallbackPlan(
                    provider=fallback_identity,
                    timeout_seconds=1.0,
                ),
            )
        }
    )
    tampered_execution = SimpleNamespace(
        output=first.execution.output,
        call_spec=tampered_spec,
        call_record=first.execution.call_record,
        response_evidence=first.execution.response_evidence,
    )
    tampered_c3_result = replace(first, execution=tampered_execution)
    tampered_communication = replace(
        result.emocio_communication,
        c3_result=tampered_c3_result,
    )
    with pytest.raises(ValueError, match="no-fallback"):
        _validated_c3_results(
            (tampered_communication, result.instinkt_communication)
        )
