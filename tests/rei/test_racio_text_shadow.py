from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Literal

import pytest

from app.backend.rei.communication.epistemic_interpreter import (
    MOTIVE_UNKNOWN_REASON_SL,
    RacioReportedUncertainty,
)
from app.backend.rei.communication.epistemic_interpreter_en import (
    RacioEpistemicInterpretationEnV3,
    RacioEpistemicPacketEnV3,
    canonicalize_racio_epistemic_draft_en_v3,
)
from app.backend.rei.communication.epistemic_interpreter_v3 import (
    ACTION_UNKNOWN_REASON_SL_V3,
    OPTION_UNKNOWN_REASON_SL_V3,
    ActionHypothesisDraftV3,
    OptionInferenceDraftV3,
    RacioEpistemicDraftV3,
    RacioEpistemicPacketV3,
    canonicalize_racio_epistemic_draft_v3,
)
from app.backend.rei.communication.text_shadow import (
    ShadowFailureCode,
    ShadowFailureStage,
    ShadowNoAuthorityLedger,
    ShadowProviderAttempt,
)
from app.backend.rei.engine import (
    ReiNativeCycleRequest,
    ReiNativeCycleResult,
    ReiNativeEngine,
)
from app.backend.rei.ids import canonical_json_bytes, content_id, sha256_hex
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
S1_E_PACKET = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "s1-gemma4-text-shadow-2026-07-19"
    / "shadow"
    / "runs"
    / "s1-gemma4-text-shadow-cycle"
    / "communication_shadow"
    / "emocio_packet_v3.json"
)


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
    def create(cls, packet: RacioEpistemicPacketEnV3) -> "_FakeShadowEvidence":
        base = {
            "schema_version": "rei-test-shadow-response-evidence-v1",
            "packet_id": packet.packet_id,
            "final_content_sanitized": True,
            "private_thinking_persisted": False,
            "no_authority": True,
        }
        return cls(result_id=content_id("test_shadow_evidence", base), **base)


class _FakeShadowFailureEvidence(FrozenArtifactModel):
    schema_version: Literal[
        "rei-test-shadow-failure-evidence-v1"
    ] = "rei-test-shadow-failure-evidence-v1"
    result_id: NonEmptyId
    packet_id: NonEmptyId
    call_id: NonEmptyId
    final_content: str
    validation_error: str
    thinking_content_persisted: Literal[False] = False
    accepted_interpretation_published: Literal[False] = False
    no_authority: Literal[True] = True

    @classmethod
    def create(
        cls,
        packet: RacioEpistemicPacketEnV3,
        call_id: str,
    ) -> "_FakeShadowFailureEvidence":
        base = {
            "schema_version": "rei-test-shadow-failure-evidence-v1",
            "packet_id": packet.packet_id,
            "call_id": call_id,
            "final_content": '{"source_mind":"E","unexpected":true}',
            "validation_error": '[{"loc":["unexpected"],"type":"extra_forbidden"}]',
            "thinking_content_persisted": False,
            "accepted_interpretation_published": False,
            "no_authority": True,
        }
        return cls(
            result_id=content_id("test_shadow_failure", base),
            **base,
        )


class _FakeShadowInterpreter:
    def __init__(
        self,
        *,
        failure_stage: ShadowFailureStage | None = None,
        failure_code: ShadowFailureCode | None = None,
        preserve_failure_evidence: bool = False,
    ) -> None:
        self.failure_stage = failure_stage
        self.failure_code = failure_code
        self.preserve_failure_evidence = preserve_failure_evidence
        self.packets: list[RacioEpistemicPacketEnV3] = []
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

    def _call_spec(self, packet: RacioEpistemicPacketEnV3):
        return build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=(packet.packet_id,),
            seed=314159,
            timeout_seconds=1.0,
        )

    def interpret_shadow(
        self,
        packet: RacioEpistemicPacketEnV3,
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
            failure_evidence = (
                _FakeShadowFailureEvidence.create(packet, call.call_id)
                if self.preserve_failure_evidence
                else None
            )
            return ShadowProviderAttempt(
                status="failed",
                call_spec=call,
                call_record=record,
                failure_stage=self.failure_stage,
                failure_code=self.failure_code,
                failure_summary="The bounded fake shadow attempt failed.",
                failure_evidence=failure_evidence,
                failure_evidence_id=(
                    None if failure_evidence is None else failure_evidence.result_id
                ),
                failure_evidence_sha256=(
                    None
                    if failure_evidence is None
                    else failure_evidence.content_hash()
                ),
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
        output: RacioEpistemicInterpretationEnV3 = (
            canonicalize_racio_epistemic_draft_en_v3(
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


def _en_request() -> ReiNativeCycleRequest:
    return ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())


def _engine(
    root: Path,
    request: ReiNativeCycleRequest,
    *,
    shadow: object | None = None,
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
        result.request.character,
        result.racio_world_input,
        result.emocio_world_input,
        result.instinkt_world_input,
        result.racio_execution.conclusion,
        result.emocio_execution.conclusion,
        result.instinkt_execution.conclusion,
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


def test_committed_s1_emocio_packet_permits_exact_full_abstention() -> None:
    packet = RacioEpistemicPacketV3.model_validate_json(S1_E_PACKET.read_bytes())
    uncertainty = RacioReportedUncertainty(
        option_mapping="uncertain",
        motive_interpretation="not_reported",
    )

    output = canonicalize_racio_epistemic_draft_v3(
        packet,
        RacioEpistemicDraftV3(
            source_mind="E",
            action_hypotheses=(),
            option_inference=None,
            motive_hypotheses=(),
            racio_reported_uncertainty=uncertainty,
        ),
    )

    assert output.source_mind == "E"
    assert output.cited_observation_ids == ()
    assert output.action_hypotheses == ()
    assert output.action_unknown_reason == ACTION_UNKNOWN_REASON_SL_V3
    assert output.option_inference is None
    assert output.option_unknown_reason == OPTION_UNKNOWN_REASON_SL_V3
    assert output.motive_hypotheses == ()
    assert output.motive_unknown_reason == MOTIVE_UNKNOWN_REASON_SL
    assert output.racio_reported_uncertainty == uncertainty


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (r"C:\Users\Name\file.json", True),
        ("D:/tmp/file.json", True),
        (r"path=C:\private\file", True),
        ("http://127.0.0.1:11434/api/chat", False),
        ("https://example.org/path", False),
        ("ollama://local/model", False),
        ("status: /ordinary/text", False),
    ),
)
def test_shadow_verifier_distinguishes_windows_paths_from_urls(
    value: str,
    expected: bool,
) -> None:
    from scripts import run_gemma4_racio_text_shadow_smoke as shadow_smoke

    assert shadow_smoke._contains_windows_absolute_path(value) is expected


def test_verifier_failure_cannot_create_a_success_receipt_or_summary_claim(
    tmp_path: Path,
) -> None:
    from scripts import run_gemma4_racio_text_shadow_smoke as shadow_smoke

    summary = {
        "schema_version": "rei-test-shadow-summary-v1",
        **shadow_smoke._pending_cold_verification_state(),
    }
    summary_path = tmp_path / "summary.json"
    summary_path.write_bytes(canonical_json_bytes(summary))
    receipt_path = tmp_path / "cold-verification-receipt.json"

    def fail_verification(output_root: Path) -> dict[str, object]:
        assert output_root in {
            shadow_smoke.ORIGINAL_OUTPUT_ROOT,
            shadow_smoke.DEFAULT_OUTPUT_ROOT,
        }
        raise ValueError("synthetic verifier failure")

    with pytest.raises(ValueError, match="synthetic verifier failure"):
        shadow_smoke._verify_and_issue_cold_receipt(
            shadow_smoke.DEFAULT_OUTPUT_ROOT,
            receipt_path=receipt_path,
            verifier=fail_verification,
        )

    persisted_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted_summary["cold_verification_required"] is True
    assert persisted_summary["evidence_root_closed"] is True
    assert "cold_verification" not in persisted_summary
    assert not receipt_path.exists()


def test_s1r_receipt_id_is_stable_and_content_addressed() -> None:
    from scripts import run_gemma4_racio_text_shadow_smoke as shadow_smoke

    original_manifest = json.loads(
        (
            shadow_smoke.ORIGINAL_OUTPUT_ROOT
            / shadow_smoke.SMOKE_MANIFEST_NAME
        ).read_text(encoding="utf-8")
    )
    s1r_manifest = json.loads(
        (
            shadow_smoke.DEFAULT_OUTPUT_ROOT
            / shadow_smoke.SMOKE_MANIFEST_NAME
        ).read_text(encoding="utf-8")
    )
    original_snapshot = shadow_smoke._evidence_root_snapshot(
        shadow_smoke.ORIGINAL_OUTPUT_ROOT
    )
    s1r_snapshot = shadow_smoke._evidence_root_snapshot(
        shadow_smoke.DEFAULT_OUTPUT_ROOT
    )
    head = shadow_smoke._git_text("rev-parse", "HEAD")

    first = shadow_smoke._cold_receipt_value(
        shadow_smoke.DEFAULT_OUTPUT_ROOT,
        manifest=s1r_manifest,
        original_manifest=original_manifest,
        verification_head=head,
        original_snapshot=original_snapshot,
        s1r_snapshot=s1r_snapshot,
    )
    repeated = shadow_smoke._cold_receipt_value(
        shadow_smoke.DEFAULT_OUTPUT_ROOT,
        manifest=s1r_manifest,
        original_manifest=original_manifest,
        verification_head=head,
        original_snapshot=original_snapshot,
        s1r_snapshot=s1r_snapshot,
    )
    changed = shadow_smoke._cold_receipt_value(
        shadow_smoke.DEFAULT_OUTPUT_ROOT,
        manifest=s1r_manifest,
        original_manifest=original_manifest,
        verification_head="f" * 40,
        original_snapshot=original_snapshot,
        s1r_snapshot=s1r_snapshot,
    )

    assert shadow_smoke.S1R_VERIFY_RECEIPT_PREFIX == "s1r_verify_receipt"
    assert first == repeated
    assert first["receipt_id"].startswith("s1r_verify_receipt_")
    assert first["verification_head"] == head
    assert first["original_s1_execution_head"] == (
        "85030ac9c6f6fd62439c000910d0eb6d0271c524"
    )
    assert first["s1r_execution_head"] == (
        "82b219c17eb62a1afbc807159da05244923998dd"
    )
    assert first["execution_head"] == first["s1r_execution_head"]
    assert first["verification_head"] != first["execution_head"]
    assert first["receipt_sha256"] == sha256_hex(
        {key: value for key, value in first.items() if key != "receipt_sha256"}
    )
    assert changed["receipt_id"] != first["receipt_id"]
    assert changed["receipt_sha256"] != first["receipt_sha256"]


@pytest.mark.parametrize(
    "prefix",
    (
        "S1r_verify_receipt",
        "s1r verify receipt",
        "s1r/verify/receipt",
        "s1r:verify:receipt",
        "a" * 33,
    ),
)
def test_global_content_id_prefix_protection_remains_strict(prefix: str) -> None:
    with pytest.raises(ValueError, match="ID prefix"):
        content_id(prefix, {"status": "succeeded"})


def test_existing_s1r_evidence_issues_create_only_receipt_without_mutation_or_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import run_gemma4_racio_text_shadow_smoke as shadow_smoke

    def forbidden_model_path(*args: object, **kwargs: object) -> None:
        raise AssertionError("receipt issuance reached a model/provider path")

    monkeypatch.setattr(
        shadow_smoke,
        "_discover_shadow_interpreter",
        forbidden_model_path,
    )
    monkeypatch.setattr(shadow_smoke, "_run_cycle", forbidden_model_path)
    monkeypatch.setattr(shadow_smoke, "_seal_candidate", forbidden_model_path)
    concrete_provider_suffixes = (
        ".providers.gemma4_text_shadow",
        ".providers.ollama",
        ".providers.ollama_gemma4_epistemic_v3",
    )
    concrete_providers_before = {
        name
        for name in sys.modules
        if name.endswith(concrete_provider_suffixes)
    }
    receipt_path = tmp_path / "post-verification-receipt.json"
    original_before = _all_files(shadow_smoke.ORIGINAL_OUTPUT_ROOT)
    s1r_before = _all_files(shadow_smoke.DEFAULT_OUTPUT_ROOT)

    receipt = shadow_smoke._verify_and_issue_cold_receipt(
        shadow_smoke.DEFAULT_OUTPUT_ROOT,
        receipt_path=receipt_path,
    )

    assert receipt_path.read_bytes() == canonical_json_bytes(receipt)
    assert receipt["receipt_generation_model_calls"] == 0
    assert receipt["execution_head"] == (
        "82b219c17eb62a1afbc807159da05244923998dd"
    )
    assert receipt["e_status"] == receipt["i_status"] == "succeeded"
    assert receipt["e_semantic_shape"] == "full_abstention"
    assert receipt["i_semantic_shape"] == "action_only"
    assert receipt["calls"] == 2
    assert receipt["retries"] == receipt["fallbacks"] == 0
    assert receipt["draft_v3_validity"] == "2/2"
    assert receipt["canonicalizer_validity"] == "2/2"
    assert receipt["evidence_roots_mutated_during_verification"] is False
    assert {
        name
        for name in sys.modules
        if name.endswith(concrete_provider_suffixes)
    } == concrete_providers_before
    assert _all_files(shadow_smoke.ORIGINAL_OUTPUT_ROOT) == original_before
    assert _all_files(shadow_smoke.DEFAULT_OUTPUT_ROOT) == s1r_before

    manifest = shadow_smoke._cold_verification_checks(
        shadow_smoke.DEFAULT_OUTPUT_ROOT
    )
    assert shadow_smoke._verify_cold_receipt(
        shadow_smoke.DEFAULT_OUTPUT_ROOT,
        manifest=manifest,
        receipt_path=receipt_path,
    ) == receipt
    persisted = receipt_path.read_bytes()

    with pytest.raises(FileExistsError):
        shadow_smoke._verify_and_issue_cold_receipt(
            shadow_smoke.DEFAULT_OUTPUT_ROOT,
            receipt_path=receipt_path,
            verifier=forbidden_model_path,
        )

    assert receipt_path.read_bytes() == persisted
    assert _all_files(shadow_smoke.ORIGINAL_OUTPUT_ROOT) == original_before
    assert _all_files(shadow_smoke.DEFAULT_OUTPUT_ROOT) == s1r_before


def test_post_verification_receipt_must_remain_outside_evidence_roots() -> None:
    from scripts import run_gemma4_racio_text_shadow_smoke as shadow_smoke

    inside_root = shadow_smoke.DEFAULT_OUTPUT_ROOT / "forbidden-receipt.json"
    with pytest.raises(ValueError, match="outside evidence roots"):
        shadow_smoke._verify_and_issue_cold_receipt(
            shadow_smoke.DEFAULT_OUTPUT_ROOT,
            receipt_path=inside_root,
        )

    assert not inside_root.exists()


def test_default_and_explicit_none_are_byte_stable_and_create_no_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import http.client
    import socket
    import urllib.request

    def forbidden_external_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("default runtime attempted an external call")

    monkeypatch.setattr(socket, "create_connection", forbidden_external_call)
    monkeypatch.setattr(
        http.client.HTTPConnection,
        "connect",
        forbidden_external_call,
    )
    monkeypatch.setattr(urllib.request, "urlopen", forbidden_external_call)
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


def test_import_rei_does_not_load_gemma_or_ollama_shadow_modules() -> None:
    script = """
import http.client
import json
import socket
import sys
import urllib.request

def forbidden_external_call(*args, **kwargs):
    raise AssertionError("import rei attempted an external call")

socket.create_connection = forbidden_external_call
http.client.HTTPConnection.connect = forbidden_external_call
urllib.request.urlopen = forbidden_external_call
sys.path.insert(0, sys.argv[1])
import rei

forbidden = (
    ".providers.gemma4_text_shadow",
    ".providers.ollama",
    ".providers.ollama_gemma4_chat_transport",
    ".providers.ollama_gemma4_epistemic",
    ".providers.ollama_gemma4_epistemic_v3",
)
print(json.dumps(sorted(
    name for name in sys.modules if name.endswith(forbidden)
)))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            script,
            str(ROOT / "app" / "backend"),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == []


def test_fake_shadow_runs_e_then_i_with_visible_request_scope_only(
    tmp_path: Path,
) -> None:
    request = _en_request()
    fake = _FakeShadowInterpreter()
    result = _engine(tmp_path, request, shadow=fake).run_cycle(request)

    assert tuple(packet.source_mind for packet in fake.packets) == ("E", "I")
    assert len(result.shadow_communications) == 2
    assert all(item.result.status == "succeeded" for item in result.shadow_communications)
    assert all(item.result.no_authority for item in result.shadow_communications)
    assert all(
        item.interpretation is not None
        and item.interpretation.schema_version
        == "rei-native-shadow-racio-interpretation-v2"
        and isinstance(
            item.interpretation.structured_output,
            RacioEpistemicInterpretationEnV3,
        )
        for item in result.shadow_communications
    )
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
    source_option_descriptions = {
        option.description for option in request.scene.options
    }
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
        assert isinstance(packet, RacioEpistemicPacketEnV3)
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
        payload = packet.provider_payload()
        payload_text = packet.provider_payload_bytes().decode("utf-8")
        assert packet.language == payload["language"] == "en"
        assert all(
            observation["text"] is None
            or (
                isinstance(observation["text"], str)
                and bool(observation["text"].strip())
            )
            for observation in payload["visible_observations"]
        )
        assert {
            option["description"] for option in payload["public_option_scope"]
        }.issubset(source_option_descriptions)
        assert payload["public_option_scope"]
        assert all(
            isinstance(option["description"], str)
            and bool(option["description"].strip())
            for option in payload["public_option_scope"]
        )
        assert "canonical_sl" not in payload_text
        assert "operational_en" not in payload_text
        assert "gloss_audit" not in payload_text
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
    request = _en_request()
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
    ledger_path = "communication_shadow/no_authority_ledger.json"
    assert ledger_path in relative_paths
    ledger = ShadowNoAuthorityLedger.model_validate_json(
        (
            tmp_path
            / "shadow"
            / "runs"
            / request.run_id
            / ledger_path
        ).read_bytes()
    )
    shadow_paths = {
        path for path in relative_paths if path.startswith("communication_shadow/")
    }
    assert {item.relative_path for item in ledger.artifacts} == shadow_paths - {
        ledger_path
    }
    assert ledger.no_authority is True
    assert all(item.no_authority is True for item in ledger.artifacts)
    for item in ledger.artifacts:
        stored = tmp_path / "shadow" / "runs" / request.run_id / item.relative_path
        assert hashlib.sha256(stored.read_bytes()).hexdigest() == item.artifact_sha256
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
    request = _en_request()
    control = _engine(tmp_path / "control", request).run_cycle(request)
    failures: tuple[tuple[ShadowFailureStage, ShadowFailureCode], ...] = (
        ("transport", "ollama_unavailable"),
        ("transport", "timeout"),
        ("draft_v3_validation", "invalid_json"),
        ("draft_v3_validation", "draft_v3_validation"),
        ("transport", "wrong_model_digest"),
        ("canonicalizer_v3_validation", "canonicalizer_failure"),
        ("canonicalizer_v3_validation", "citation_scope_violation"),
        ("canonicalizer_v3_validation", "option_scope_violation"),
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


def test_validation_failure_evidence_is_terminal_no_authority_and_manifest_closed(
    tmp_path: Path,
) -> None:
    request = _en_request()
    control = _engine(tmp_path / "control", request).run_cycle(request)
    fake = _FakeShadowInterpreter(
        failure_stage="draft_v3_validation",
        failure_code="draft_v3_validation",
        preserve_failure_evidence=True,
    )

    result = _engine(
        tmp_path / "failed_with_evidence",
        request,
        shadow=fake,
    ).run_cycle(request)

    assert _authoritative_projection(control) == _authoritative_projection(result)
    assert tuple(packet.source_mind for packet in fake.packets) == ("E", "I")
    assert all(
        item.result.status == "failed"
        and item.interpretation is None
        and item.response_evidence is None
        and isinstance(item.failure_evidence, _FakeShadowFailureEvidence)
        and item.failure_evidence.no_authority is True
        and item.failure_evidence.accepted_interpretation_published is False
        and item.call_record is not None
        and item.call_record.output_artifact_ids == ()
        for item in result.shadow_communications
    )
    run_root = (
        tmp_path
        / "failed_with_evidence"
        / "runs"
        / request.run_id
        / "communication_shadow"
    )
    for label in ("emocio", "instinkt"):
        failure_path = run_root / f"{label}_failure_response_evidence.json"
        assert failure_path.is_file()
        failure = _FakeShadowFailureEvidence.model_validate_json(
            failure_path.read_bytes()
        )
        assert failure.thinking_content_persisted is False
        assert not (run_root / f"{label}_interpretation_v3.json").exists()
        assert not (run_root / f"{label}_response_evidence.json").exists()
    ledger = ShadowNoAuthorityLedger.model_validate_json(
        (run_root / "no_authority_ledger.json").read_bytes()
    )
    failure_roles = tuple(
        item
        for item in ledger.artifacts
        if item.role == "failure_response_evidence"
    )
    assert len(failure_roles) == 2
    assert all(item.no_authority is True for item in failure_roles)
    assert FileArtifactStore(
        tmp_path / "failed_with_evidence" / "runs"
    ).verify_run(request.run_id) == result.manifest


def test_english_shadow_input_succeeds_and_slovenian_fails_before_dispatch(
    tmp_path: Path,
) -> None:
    english_request = _en_request()
    english_fake = _FakeShadowInterpreter()
    english_result = _engine(
        tmp_path / "english",
        english_request,
        shadow=english_fake,
    ).run_cycle(english_request)

    assert tuple(packet.source_mind for packet in english_fake.packets) == ("E", "I")
    assert all(
        item.result.status == "succeeded"
        and item.packet is not None
        and item.packet.language == "en"
        for item in english_result.shadow_communications
    )

    slovenian_request = _sl_request()
    slovenian_fake = _FakeShadowInterpreter()
    slovenian_result = _engine(
        tmp_path / "slovenian",
        slovenian_request,
        shadow=slovenian_fake,
    ).run_cycle(slovenian_request)

    assert slovenian_fake.packets == []
    assert tuple(
        item.source_mind for item in slovenian_result.shadow_communications
    ) == ("E", "I")
    assert all(
        item.result.status == "failed"
        and item.result.failure_stage == "packet_construction"
        and item.result.failure_code == "unsupported_language"
        and item.call_spec is None
        and item.call_record is None
        for item in slovenian_result.shadow_communications
    )
    assert FileArtifactStore(tmp_path / "english" / "runs").verify_run(
        english_request.run_id
    ) == english_result.manifest
    assert FileArtifactStore(tmp_path / "slovenian" / "runs").verify_run(
        slovenian_request.run_id
    ) == slovenian_result.manifest


def test_concrete_shadow_adapter_rejects_non_english_provider_injection() -> None:
    from app.backend.rei.providers.gemma4_text_shadow import (
        Gemma4TextShadowInterpreter,
    )

    with pytest.raises(TypeError, match="English provider wrapper"):
        Gemma4TextShadowInterpreter(provider=object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("client_kind", "expected_code"),
    (("unavailable", "ollama_unavailable"), ("wrong_digest", "wrong_model_digest")),
)
def test_concrete_discovery_failure_is_fail_soft_and_manifest_closed(
    tmp_path: Path,
    client_kind: str,
    expected_code: ShadowFailureCode,
) -> None:
    from app.backend.rei.providers.gemma4_text_shadow import (
        Gemma4TextShadowInterpreter,
    )
    from app.backend.rei.providers.ollama import OllamaTransportError

    class DiscoveryClient:
        allow_remote = False
        base_url = "http://127.0.0.1:11434"

        def version(self):
            if client_kind == "unavailable":
                raise OllamaTransportError("sanitized test transport failure")
            return "0.31.2"

        def model_entry(self, model: str):
            del model
            return {"digest": "0" * 64}

        def show(self, model: str):
            del model
            return {}

    interpreter = Gemma4TextShadowInterpreter.discover(
        client=DiscoveryClient(),
        environ={
            "REI_OLLAMA_MODEL": "gemma4:31b",
            "REI_OLLAMA_NUM_CTX": "65536",
            "REI_OLLAMA_NUM_GPU": "999",
        },
    )
    assert interpreter.provider is None
    assert interpreter.preflight_failure is not None
    assert interpreter.preflight_failure.failure_code == expected_code

    request = _en_request()
    control = _engine(tmp_path / "control", request).run_cycle(request)
    result = _engine(
        tmp_path / client_kind,
        request,
        shadow=interpreter,
    ).run_cycle(request)

    assert _authoritative_projection(control) == _authoritative_projection(result)
    assert len(result.shadow_communications) == 2
    assert all(
        item.packet is not None
        and item.call_spec is None
        and item.call_record is None
        and item.result.status == "failed"
        and item.result.failure_stage == "transport"
        and item.result.failure_code == expected_code
        for item in result.shadow_communications
    )
    relative_paths = {item.relative_path for item in result.stored_artifacts}
    assert "communication_shadow/no_authority_ledger.json" in relative_paths
    assert not any("provider_call_record" in path for path in relative_paths)
    assert FileArtifactStore(
        tmp_path / client_kind / "runs"
    ).verify_run(request.run_id) == result.manifest


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
    request = _en_request()
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
