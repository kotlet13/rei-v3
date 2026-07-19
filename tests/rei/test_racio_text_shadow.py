from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from app.backend.rei.communication.epistemic_interpreter import (
    RacioReportedUncertainty,
)
from app.backend.rei.communication.epistemic_interpreter_v3 import (
    ActionHypothesisDraftV3,
    OptionInferenceDraftV3,
    RacioEpistemicDraftV3,
    RacioEpistemicPacketV3,
    canonicalize_racio_epistemic_draft_v3,
)
from app.backend.rei.communication.text_shadow import (
    ShadowFailureCode,
    ShadowFailureStage,
    ShadowProviderAttempt,
)
from app.backend.rei.engine import (
    ReiNativeCycleRequest,
    ReiNativeCycleResult,
    ReiNativeEngine,
)
from app.backend.rei.ids import canonical_json_bytes, content_id
from app.backend.rei.models.common import FrozenArtifactModel, NonEmptyId
from app.backend.rei.models.provider import ProviderCallRecord, ProviderIdentity
from app.backend.rei.persistence import ArtifactIntegrityError, FileArtifactStore
from app.backend.rei.providers.native import (
    DeterministicExecutionClock,
    ExecutionClock,
    build_provider_call_spec,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"


class _FakeShadowEvidence(FrozenArtifactModel):
    schema_version: Literal[
        "rei-test-shadow-response-evidence-v1"
    ] = "rei-test-shadow-response-evidence-v1"
    result_id: NonEmptyId
    packet_id: NonEmptyId
    final_content_sanitized: Literal[True] = True
    private_thinking_persisted: Literal[False] = False
    no_authority: Literal[True] = True

    @classmethod
    def create(cls, packet: RacioEpistemicPacketV3) -> "_FakeShadowEvidence":
        base = {
            "schema_version": "rei-test-shadow-response-evidence-v1",
            "packet_id": packet.packet_id,
            "final_content_sanitized": True,
            "private_thinking_persisted": False,
            "no_authority": True,
        }
        return cls(result_id=content_id("test_shadow_evidence", base), **base)


class _FakeShadowInterpreter:
    def __init__(
        self,
        *,
        failure_stage: ShadowFailureStage | None = None,
        failure_code: ShadowFailureCode | None = None,
    ) -> None:
        self.failure_stage = failure_stage
        self.failure_code = failure_code
        self.packets: list[RacioEpistemicPacketV3] = []
        identity_payload = {
            "kind": "text_reasoner",
            "implementation": "tests.FakeShadowInterpreter",
            "implementation_revision": "s1-model-free-v1",
            "uses_model": True,
            "model": "fake-shadow-model",
            "model_revision": "fake-shadow-model-v1",
        }
        self.identity = ProviderIdentity(
            provider_id=content_id("provider", identity_payload),
            **identity_payload,
        )

    def _call_spec(self, packet: RacioEpistemicPacketV3):
        return build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=(packet.packet_id,),
            seed=314159,
            timeout_seconds=1.0,
        )

    def interpret_shadow(
        self,
        packet: RacioEpistemicPacketV3,
        *,
        clock: ExecutionClock,
    ) -> ShadowProviderAttempt:
        self.packets.append(packet)
        call = self._call_spec(packet)
        started_at = clock.timestamp("racio_call_started")
        finished_at = clock.timestamp("racio_call_finished")
        if self.failure_code is not None:
            status = "timed_out" if self.failure_code == "timeout" else "failed"
            record = ProviderCallRecord(
                call_id=call.call_id,
                spec_hash=call.content_hash(),
                request_id=call.request_id,
                input_artifact_ids=call.input_artifact_ids,
                provider=call.provider,
                seed=call.seed,
                parameters=call.parameters,
                timeout_seconds=call.timeout_seconds,
                started_at=started_at,
                primary_finished_at=finished_at,
                finished_at=finished_at,
                status=status,
                primary_status=status,
                output_artifact_ids=(),
                warnings=(f"sanitized_shadow_failure_code:{self.failure_code}",),
                safety_notice=call.safety_notice,
            )
            assert self.failure_stage is not None
            return ShadowProviderAttempt(
                status="failed",
                call_spec=call,
                call_record=record,
                failure_stage=self.failure_stage,
                failure_code=self.failure_code,
                failure_summary="The bounded fake shadow attempt failed.",
            )

        assert packet.visible_observation_ids
        citation = packet.visible_observation_ids[0]
        action = (
            ActionHypothesisDraftV3(
                family="confrontation",
                subtype="attack",
                cited_observation_ids=(citation,),
                confidence=0.51,
                support_mode="speculative",
            )
            if packet.source_mind == "E"
            else ActionHypothesisDraftV3(
                family="execution_expression",
                subtype="perform",
                cited_observation_ids=(citation,),
                confidence=0.52,
                support_mode="speculative",
            )
        )
        option = (
            None
            if not packet.public_option_ids
            else OptionInferenceDraftV3(
                option_id=packet.public_option_ids[0],
                cited_observation_ids=(citation,),
                confidence=0.53,
            )
        )
        output = canonicalize_racio_epistemic_draft_v3(
            packet,
            RacioEpistemicDraftV3(
                source_mind=packet.source_mind,
                action_hypotheses=(action,),
                option_inference=option,
                motive_hypotheses=(),
                racio_reported_uncertainty=RacioReportedUncertainty(
                    option_mapping="uncertain",
                    motive_interpretation="not_reported",
                ),
            ),
        )
        evidence = _FakeShadowEvidence.create(packet)
        record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=call.provider,
            seed=call.seed,
            parameters=call.parameters,
            timeout_seconds=call.timeout_seconds,
            started_at=started_at,
            primary_finished_at=finished_at,
            finished_at=finished_at,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(evidence.result_id,),
            safety_notice=call.safety_notice,
        )
        return ShadowProviderAttempt(
            status="succeeded",
            call_spec=call,
            call_record=record,
            output=output,
            response_evidence=evidence,
            response_evidence_id=evidence.result_id,
            response_evidence_sha256=evidence.content_hash(),
        )


def _sl_request() -> ReiNativeCycleRequest:
    request = ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())
    options = tuple(
        option.model_copy(
            update={
                "label": (
                    "obnovi delavnico"
                    if option.option_id == "option_restore"
                    else "pusti zaprto"
                ),
                "description": (
                    "Odpri in obnovi skupno delavnico."
                    if option.option_id == "option_restore"
                    else "Skupna delavnica naj ostane zaprta."
                ),
            }
        )
        for option in request.scene.options
    )
    scene = request.scene.model_copy(
        update={
            "raw_input": "Skupna delavnica po sporu ostaja zaprta.",
            "language": "sl",
            "options": options,
        }
    )
    return ReiNativeCycleRequest.model_validate(
        request.model_copy(update={"scene": scene}).model_dump(
            mode="python",
            round_trip=True,
        )
    )


def _engine(
    root: Path,
    request: ReiNativeCycleRequest,
    *,
    shadow: _FakeShadowInterpreter | None = None,
) -> ReiNativeEngine:
    return ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(request.started_at),
        racio_interpreter_mode=(
            "deterministic" if shadow is None else "gemma4_text_shadow"
        ),
        shadow_racio_interpreter=shadow,
    )


def _authoritative_projection(result: ReiNativeCycleResult) -> tuple[bytes, ...]:
    values = (
        result.racio_world_input,
        result.emocio_world_input,
        result.instinkt_world_input,
        result.native_bundle,
        result.effective_authority,
        result.governance,
        result.emocio_manifestation,
        result.instinkt_manifestation,
        result.emocio_communication.request,
        result.emocio_communication.interpretation,
        result.emocio_communication.translation_gap,
        result.emocio_communication.acceptance_fidelity,
        result.instinkt_communication.request,
        result.instinkt_communication.interpretation,
        result.instinkt_communication.translation_gap,
        result.instinkt_communication.acceptance_fidelity,
        result.mandate_view,
        result.interpretation_inputs,
        result.conscious_decision,
        result.behavior_resultant,
        result.narrative,
        result.ego_measure,
        result.ego_trace,
        result.composition_snapshot,
        result.projections,
    )
    return tuple(canonical_json_bytes(value) for value in values)


def _all_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_default_and_explicit_none_are_byte_stable_and_create_no_shadow(
    tmp_path: Path,
) -> None:
    request = _sl_request()
    default = _engine(tmp_path / "default", request).run_cycle(request)
    explicit = ReiNativeEngine.with_file_stores(
        runs_root=tmp_path / "explicit" / "runs",
        ego_traces_root=tmp_path / "explicit" / "ego_traces",
        clock=DeterministicExecutionClock(request.started_at),
        racio_interpreter_mode="deterministic",
        shadow_racio_interpreter=None,
    ).run_cycle(request)

    assert default.shadow_communications == explicit.shadow_communications == ()
    assert default.manifest == explicit.manifest
    assert _authoritative_projection(default) == _authoritative_projection(explicit)
    assert _all_files(tmp_path / "default") == _all_files(tmp_path / "explicit")
    assert not any(
        "shadow" in artifact.relative_path for artifact in default.stored_artifacts
    )


def test_fake_shadow_runs_e_then_i_with_visible_request_scope_only(
    tmp_path: Path,
) -> None:
    request = _sl_request()
    fake = _FakeShadowInterpreter()
    result = _engine(tmp_path, request, shadow=fake).run_cycle(request)

    assert tuple(packet.source_mind for packet in fake.packets) == ("E", "I")
    assert len(result.shadow_communications) == 2
    assert all(item.result.status == "succeeded" for item in result.shadow_communications)
    assert all(item.result.no_authority for item in result.shadow_communications)
    forbidden_keys = {
        "native_mind_bundle",
        "native_option",
        "native_motive",
        "profile_id",
        "character_authority",
        "governance_mandate",
        "conscious_decision",
        "behavior_resultant",
        "translation_gap",
        "acceptance_state",
        "ego_composition_history",
    }
    source_option_ids = set(result.emocio_communication.request.allowed_option_ids)
    source_observation_ids = {
        observation.observation_id
        for communication in (
            result.emocio_communication,
            result.instinkt_communication,
        )
        for view in communication.request.observable_views
        for observation in view.observations
    }
    for packet in fake.packets:
        serialized = packet.model_dump(mode="json")

        def keys(value):
            if isinstance(value, dict):
                yield from value
                for child in value.values():
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        assert forbidden_keys.isdisjoint(set(keys(serialized)))
        payload_text = packet.provider_payload_bytes().decode("utf-8")
        assert packet.presentation_mode == "canonical_sl_only"
        assert all(option.startswith("option_") for option in packet.public_option_ids)
        assert all(
            observation.startswith("observation_")
            for observation in packet.visible_observation_ids
        )
        assert source_option_ids.isdisjoint(packet.public_option_ids)
        assert not any(value in payload_text for value in source_option_ids)
        assert not any(
            value is not None and value in payload_text
            for value in source_observation_ids
        )
        assert request.character.profile_id not in payload_text
        assert request.acceptance_state.acceptance_state_id not in payload_text


def test_shadow_success_cannot_change_authoritative_cycle_and_cold_verifies(
    tmp_path: Path,
) -> None:
    request = _sl_request()
    control = _engine(tmp_path / "control", request).run_cycle(request)
    fake = _FakeShadowInterpreter()
    shadow = _engine(tmp_path / "shadow", request, shadow=fake).run_cycle(request)

    assert _authoritative_projection(control) == _authoritative_projection(shadow)
    assert shadow.emocio_communication.interpretation == (
        control.emocio_communication.interpretation
    )
    assert shadow.instinkt_communication.interpretation == (
        control.instinkt_communication.interpretation
    )
    assert FileArtifactStore(tmp_path / "shadow" / "runs").verify_run(
        request.run_id
    ) == shadow.manifest
    relative_paths = {item.relative_path for item in shadow.stored_artifacts}
    for label in ("emocio", "instinkt"):
        assert f"communication_shadow/{label}_packet_v3.json" in relative_paths
        assert f"communication_shadow/{label}_interpretation_v3.json" in relative_paths
        assert f"communication_shadow/{label}_provider_call_record.json" in relative_paths
        assert f"communication_shadow/{label}_response_evidence.json" in relative_paths
        assert f"communication_shadow/{label}_comparison.json" in relative_paths
        assert f"communication_shadow/{label}_result.json" in relative_paths
    assert len(shadow.manifest.provider_calls) == len(control.manifest.provider_calls) + 2
    assert all(
        result.call_record is not None
        and result.call_record.fallback is None
        and result.call_record.status == "succeeded"
        for result in shadow.shadow_communications
    )


def test_bounded_shadow_failures_leave_authoritative_cycle_successful(
    tmp_path: Path,
) -> None:
    request = _sl_request()
    control = _engine(tmp_path / "control", request).run_cycle(request)
    failures: tuple[tuple[ShadowFailureStage, ShadowFailureCode], ...] = (
        ("transport", "ollama_unavailable"),
        ("transport", "timeout"),
        ("draft_v3_validation", "invalid_json"),
        ("transport", "wrong_model_digest"),
        ("canonicalizer_v3_validation", "citation_scope_violation"),
    )
    for index, (stage, code) in enumerate(failures, start=1):
        fake = _FakeShadowInterpreter(
            failure_stage=stage,
            failure_code=code,
        )
        result = _engine(
            tmp_path / f"failure_{index}",
            request,
            shadow=fake,
        ).run_cycle(request)
        assert tuple(packet.source_mind for packet in fake.packets) == ("E", "I")
        assert _authoritative_projection(control) == _authoritative_projection(result)
        assert result.conscious_decision == control.conscious_decision
        assert result.behavior_resultant == control.behavior_resultant
        assert all(
            item.result.status == "failed"
            and item.result.failure_stage == stage
            and item.result.failure_code == code
            and item.interpretation is None
            and item.response_evidence is None
            and item.comparison is None
            for item in result.shadow_communications
        )
        relative_paths = {item.relative_path for item in result.stored_artifacts}
        assert not any("interpretation_v3" in path for path in relative_paths)
        assert not any("response_evidence" in path for path in relative_paths)
        assert FileArtifactStore(
            tmp_path / f"failure_{index}" / "runs"
        ).verify_run(request.run_id) == result.manifest


def test_english_shadow_input_fails_before_provider_dispatch(tmp_path: Path) -> None:
    request = ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())
    fake = _FakeShadowInterpreter()
    result = _engine(tmp_path, request, shadow=fake).run_cycle(request)

    assert fake.packets == []
    assert tuple(item.source_mind for item in result.shadow_communications) == ("E", "I")
    assert all(
        item.result.status == "failed"
        and item.result.failure_stage == "packet_construction"
        and item.result.failure_code == "unsupported_language"
        and item.call_spec is None
        and item.call_record is None
        for item in result.shadow_communications
    )
    assert FileArtifactStore(tmp_path / "runs").verify_run(request.run_id) == result.manifest


def test_shadow_mode_requires_explicit_dependency(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit dependency"):
        ReiNativeEngine.with_file_stores(
            runs_root=tmp_path / "runs",
            ego_traces_root=tmp_path / "traces",
            racio_interpreter_mode="gemma4_text_shadow",
        )

    with pytest.raises(ValueError, match="explicit gemma4_text_shadow"):
        ReiNativeEngine.with_file_stores(
            runs_root=tmp_path / "runs_2",
            ego_traces_root=tmp_path / "traces_2",
            shadow_racio_interpreter=_FakeShadowInterpreter(),
        )


def test_shadow_inventory_rejects_tampering_and_contains_no_private_content(
    tmp_path: Path,
) -> None:
    request = _sl_request()
    result = _engine(
        tmp_path,
        request,
        shadow=_FakeShadowInterpreter(),
    ).run_cycle(request)
    store = FileArtifactStore(tmp_path / "runs")
    assert store.verify_run(request.run_id) == result.manifest

    shadow_root = tmp_path / "runs" / request.run_id / "communication_shadow"
    forbidden_exact_keys = {
        "thinking",
        "raw_traceback",
        "raw_response_envelope",
        "native_truth",
        "evaluator_gold",
    }
    for path in shadow_root.glob("*.json"):
        content = path.read_text(encoding="utf-8")
        assert str(tmp_path) not in content
        assert "private chain of thought sentinel" not in content
        payload = json.loads(content)

        def object_keys(value):
            if isinstance(value, dict):
                yield from value
                for child in value.values():
                    yield from object_keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from object_keys(child)

        assert forbidden_exact_keys.isdisjoint(set(object_keys(payload)))

    target = shadow_root / "emocio_result.json"
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ArtifactIntegrityError):
        store.verify_run(request.run_id)
