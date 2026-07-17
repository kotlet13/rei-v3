from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

import scripts.run_gemma4_racio_epistemic_v3_g3c as g3c
from app.backend.rei.models.provider import ProviderCallRecord
from app.backend.rei.providers.ollama_gemma4_epistemic import (
    GEMMA4_EPISTEMIC_CAPABILITIES,
    GEMMA4_EPISTEMIC_MODEL,
    GEMMA4_EPISTEMIC_NUM_CTX,
    GEMMA4_EPISTEMIC_NUM_GPU,
    GEMMA4_EPISTEMIC_PARAMETER_COUNT,
    GEMMA4_EPISTEMIC_QUANTIZATION,
    GEMMA4_EPISTEMIC_TEMPLATE,
)


ENVIRONMENT = {
    "REI_OLLAMA_MODEL": GEMMA4_EPISTEMIC_MODEL,
    "REI_OLLAMA_NUM_CTX": str(GEMMA4_EPISTEMIC_NUM_CTX),
    "REI_OLLAMA_NUM_GPU": str(GEMMA4_EPISTEMIC_NUM_GPU),
}


class FakeG3CV3Transport:
    """Exercise all real V3 provider boundaries without network or model use."""

    def __init__(
        self,
        output_dir: Path,
        *,
        failing_chat_indices: frozenset[int] = frozenset(),
        failure_modes: Mapping[int, str] | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.failure_modes = {
            **{index: "transport" for index in failing_chat_indices},
            **dict(failure_modes or {}),
        }
        if not set(self.failure_modes.values()).issubset(
            {"transport", "draft", "canonicalizer"}
        ):
            raise ValueError("Unsupported fake G3C failure mode")
        self.chat_count = 0
        self.discovery_observed_planned_ledger = False
        self.first_chat_observed_complete_preflight = False

    def request_json(
        self,
        *,
        method: str,
        url: str,
        payload: Mapping[str, Any] | None,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> Mapping[str, Any]:
        del method, timeout_seconds, max_response_bytes
        path = urlsplit(url).path
        if path == "/api/version":
            self.discovery_observed_planned_ledger = (
                self.output_dir / "attempt_ledger" / "000_planned.json"
            ).is_file()
            return {"version": "0.31.2"}
        if path == "/api/tags":
            return {
                "models": [
                    {
                        "name": GEMMA4_EPISTEMIC_MODEL,
                        "model": GEMMA4_EPISTEMIC_MODEL,
                        "digest": g3c.GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
                        "size": 19_868_981_791,
                        "details": {
                            "quantization_level": GEMMA4_EPISTEMIC_QUANTIZATION,
                            "context_length": 262144,
                        },
                        "capabilities": ["completion", "thinking", "tools"],
                    }
                ]
            }
        if path == "/api/show":
            return {
                "details": {"quantization_level": GEMMA4_EPISTEMIC_QUANTIZATION},
                "model_info": {
                    "general.architecture": "gemma4",
                    "general.parameter_count": GEMMA4_EPISTEMIC_PARAMETER_COUNT,
                    "gemma4.context_length": 262144,
                },
                "template": GEMMA4_EPISTEMIC_TEMPLATE,
                "capabilities": list(GEMMA4_EPISTEMIC_CAPABILITIES),
            }
        if path == "/api/chat":
            if self.chat_count == 0:
                case_specs = sorted(
                    (self.output_dir / "cases").glob("*/call_spec.json")
                )
                case_gold = sorted(
                    (self.output_dir / "cases").glob("*/evaluator_gold.json")
                )
                self.first_chat_observed_complete_preflight = (
                    (self.output_dir / "preflight_seal.json").is_file()
                    and (self.output_dir / "pair_registry.json").is_file()
                    and len(case_specs) == g3c.CASE_COUNT
                    and len(case_gold) == g3c.CASE_COUNT
                )
            chat_index = self.chat_count
            self.chat_count += 1
            failure_mode = self.failure_modes.get(chat_index)
            if failure_mode == "transport":
                return {
                    "model": GEMMA4_EPISTEMIC_MODEL,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "thinking": "synthetic private failure trace",
                    },
                    "done": False,
                    "done_reason": "length",
                }
            assert payload is not None
            packet = json.loads(payload["messages"][1]["content"])
            observation_id = packet["visible_observations"][0]["observation_id"]
            draft = {
                "source_mind": packet["source_mind"],
                "action_hypotheses": [
                    {
                        "family": "execution_expression",
                        "subtype": "perform",
                        "family_fallback": None,
                        "cited_observation_ids": [observation_id],
                        "confidence": 0.51,
                        "support_mode": "speculative",
                    }
                ],
                "option_inference": None,
                "motive_hypotheses": [],
                "racio_reported_uncertainty": {
                    "option_mapping": "not_reported",
                    "motive_interpretation": "not_reported",
                },
            }
            if failure_mode == "draft":
                draft["action_hypotheses"] = "not-a-list"
            elif failure_mode == "canonicalizer":
                draft["action_hypotheses"][0]["cited_observation_ids"] = [
                    "observation_outside_visible_scope"
                ]
            return {
                "model": GEMMA4_EPISTEMIC_MODEL,
                "created_at": "2026-07-17T10:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(draft),
                    "thinking": "synthetic private success trace",
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
        if path == "/api/ps":
            return {
                "models": [
                    {
                        "name": GEMMA4_EPISTEMIC_MODEL,
                        "model": GEMMA4_EPISTEMIC_MODEL,
                        "digest": g3c.GEMMA4_EPISTEMIC_V3_MODEL_DIGEST,
                        "size": 1000,
                        "size_vram": 1000,
                        "context_length": GEMMA4_EPISTEMIC_NUM_CTX,
                    }
                ]
            }
        raise AssertionError(f"Unexpected fake Ollama endpoint: {path}")


@pytest.fixture(scope="module")
def sealed_suite() -> g3c.G3CSuite:
    return g3c.load_g3c_suite()


@pytest.fixture(scope="module")
def successful_screen(
    tmp_path_factory: pytest.TempPathFactory,
    sealed_suite: g3c.G3CSuite,
) -> tuple[Path, FakeG3CV3Transport, dict[str, Any]]:
    output_dir = tmp_path_factory.mktemp("g3c-v3-success") / "screen"
    transport = FakeG3CV3Transport(output_dir)
    summary = g3c.execute_g3c_screen(
        suite=sealed_suite,
        output_dir=output_dir,
        source_commit="a" * 40,
        environ=ENVIRONMENT,
        inner_transport=transport,
        enforce_sealed_output_root=False,
    )
    return output_dir, transport, summary


@pytest.fixture(scope="module")
def mixed_screen(
    tmp_path_factory: pytest.TempPathFactory,
    sealed_suite: g3c.G3CSuite,
) -> tuple[Path, FakeG3CV3Transport, dict[str, Any]]:
    output_dir = tmp_path_factory.mktemp("g3c-v3-mixed") / "screen"
    transport = FakeG3CV3Transport(
        output_dir,
        failure_modes={0: "transport", 1: "draft", 2: "canonicalizer"},
    )
    summary = g3c.execute_g3c_screen(
        suite=sealed_suite,
        output_dir=output_dir,
        source_commit="b" * 40,
        environ=ENVIRONMENT,
        inner_transport=transport,
        enforce_sealed_output_root=False,
    )
    return output_dir, transport, summary


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {
            *value,
            *(nested for item in value.values() for nested in _all_keys(item)),
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _all_keys(item)}
    return set()


def _canonical_write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(g3c.canonical_json_bytes(value) + b"\n")


def _copy_screen(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    receipt = target / "cold_validation.json"
    if receipt.exists():
        receipt.unlink()
    return target


def test_committed_suite_is_strictly_sealed_and_model_free(
    sealed_suite: g3c.G3CSuite,
) -> None:
    if g3c.EXPECTED_MANIFEST_SHA256 is not None:
        assert sealed_suite.manifest_sha256 == g3c.EXPECTED_MANIFEST_SHA256
    assert len(sealed_suite.cases) == 16
    assert len(sealed_suite.pairs) == 8
    assert tuple(
        (
            case.case_id,
            case.root_label,
            case.bilingual_pair_id,
            case.source_case_id,
            case.source_root_id,
            case.packet.presentation_mode,
        )
        for case in sealed_suite.cases
    ) == g3c.EXPECTED_CASE_IDENTITIES
    assert tuple(pair.root_label for pair in sealed_suite.pairs) == (
        g3c.EXPECTED_ROOT_LABELS
    )
    assert len({case.call_spec.call_id for case in sealed_suite.cases}) == 16
    assert [case.case_id for case in sealed_suite.cases] == sealed_suite.manifest[
        "case_order"
    ]
    assert [pair.bilingual_pair_id for pair in sealed_suite.pairs] == (
        sealed_suite.manifest["pair_order"]
    )
    verification = g3c.model_free_verify(sealed_suite)
    assert verification["model_call_count"] == 0
    assert verification["static_call_spec_count"] == 16


def test_manifest_or_corpus_tampering_fails_closed(
    tmp_path: Path,
    sealed_suite: g3c.G3CSuite,
) -> None:
    copied = tmp_path / "corpus"
    shutil.copytree(sealed_suite.manifest_path.parent, copied)
    manifest = copied / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(ValueError, match="canonical JSON|pinned SHA"):
        g3c.load_g3c_suite(
            manifest,
            expected_manifest_sha256=sealed_suite.manifest_sha256,
        )

    shutil.rmtree(copied)
    shutil.copytree(sealed_suite.manifest_path.parent, copied)
    packets = copied / "packets.jsonl"
    packets.write_bytes(packets.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="corpus hash differs"):
        g3c.load_g3c_suite(
            copied / "manifest.json",
            expected_manifest_sha256=sealed_suite.manifest_sha256,
        )


def test_provider_payloads_exclude_gold_and_bilingual_attestations(
    sealed_suite: g3c.G3CSuite,
) -> None:
    forbidden_keys = {
        "atomic_evidence_unit_id",
        "perceptual_unit_count",
        "gloss_audit",
        "audit_hash",
        "evaluator_only_canary",
        "native_truth_id",
        "profile_id",
    }
    for case in sealed_suite.cases:
        payload = case.packet.provider_payload()
        encoded = case.packet.provider_payload_bytes().decode("utf-8")
        assert not forbidden_keys.intersection(_all_keys(payload))
        assert all(token not in encoded for token in case.gold.hidden_provider_tokens)


def test_success_uses_static_preflight_and_exactly_one_dispatch_per_case(
    successful_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    output_dir, transport, summary = successful_screen
    assert transport.discovery_observed_planned_ledger is True
    assert transport.first_chat_observed_complete_preflight is True
    assert transport.chat_count == 16
    assert summary["technical_completeness"]["one_dispatch_per_case"] is True
    assert summary["technical_completeness"]["retry_count"] == 0
    assert summary["technical_completeness"]["fallback_count"] == 0
    preflight = json.loads((output_dir / "preflight_seal.json").read_text())
    assert preflight["chat_dispatch_count"] == 0
    assert preflight["call_spec_hashes"] == {
        case.case_id: case.call_spec.content_hash() for case in sealed_suite.cases
    }
    after = sorted((output_dir / "attempt_ledger").glob("*_after.json"))
    assert len(after) == 16
    assert all(json.loads(path.read_text())["dispatch_delta"] == 1 for path in after)


def test_success_persists_draft_output_sidecar_and_private_free_lineage(
    successful_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    output_dir, _, summary = successful_screen
    assert summary["technical_completeness"]["provider_success_count"] == 16
    case_dir = output_dir / "cases" / sealed_suite.cases[0].case_id
    for name in (
        "model_draft.json",
        "structured_output.json",
        "structural_sidecar.json",
        "response_evidence.json",
        "provider_call_record.json",
        "case_evaluation.json",
    ):
        assert (case_dir / name).is_file()
    sidecar = json.loads((case_dir / "structural_sidecar.json").read_text())
    assert set(sidecar) == {"option_id_present", "motive_hypothesis_count"}
    evidence_text = (case_dir / "response_evidence.json").read_text()
    assert "synthetic private success trace" not in evidence_text
    record = ProviderCallRecord.model_validate_json(
        (case_dir / "provider_call_record.json").read_bytes()
    )
    assert record.status == "succeeded"
    assert record.fallback is None
    case_result = json.loads((case_dir / "case_result.json").read_text())
    assert case_result["draft_v3_status"] == "valid"
    assert case_result["canonicalizer_v3_status"] == "valid"
    assert case_result["failure_stage"] is None
    assert case_result["option_inference_present"] is False
    assert case_result["motive_hypothesis_count"] == 0
    assert case_result["confidence_values"]["action_hypotheses"] == [
        {
            "family": "execution_expression",
            "subtype": "perform",
            "family_fallback": None,
            "support_mode": "speculative",
            "confidence": 0.51,
        }
    ]


def test_mixed_failures_continue_and_use_stage_receipts(
    mixed_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    output_dir, transport, summary = mixed_screen
    assert transport.chat_count == 16
    assert summary["technical_completeness"]["provider_failure_count"] == 3
    assert summary["technical_completeness"]["provider_success_count"] == 13
    first_case = sealed_suite.cases[0]
    failure_dir = output_dir / "cases" / first_case.case_id
    failure = json.loads((failure_dir / "sanitized_failure.json").read_text())
    assert failure["failure_stage"] == "transport"
    assert failure["validation_boundary"] == "before_json_pydantic_validation"
    assert failure["thinking_content_persisted"] is False
    assert failure["rejected_content_persisted"] is False
    assert "synthetic private failure trace" not in json.dumps(failure)
    failure_result = json.loads((failure_dir / "case_result.json").read_text())
    assert failure_result["draft_v3_status"] == "not_reached"
    assert failure_result["canonicalizer_v3_status"] == "not_reached"
    assert failure_result["option_inference_present"] is None
    assert failure_result["motive_hypothesis_count"] is None
    assert failure_result["confidence_values"] is None
    assert (failure_dir / "model_draft_missing.json").is_file()
    assert (failure_dir / "structural_sidecar_missing.json").is_file()
    draft_failure_dir = output_dir / "cases" / sealed_suite.cases[1].case_id
    draft_failure = json.loads(
        (draft_failure_dir / "case_result.json").read_text()
    )
    assert draft_failure["failure_stage"] == "draft_v3_validation"
    assert draft_failure["draft_v3_status"] == "invalid"
    assert draft_failure["canonicalizer_v3_status"] == "not_reached"
    canonical_failure_dir = output_dir / "cases" / sealed_suite.cases[2].case_id
    canonical_failure = json.loads(
        (canonical_failure_dir / "case_result.json").read_text()
    )
    assert canonical_failure["failure_stage"] == "canonicalizer_v3_validation"
    assert canonical_failure["draft_v3_status"] == "valid"
    assert canonical_failure["canonicalizer_v3_status"] == "invalid"
    later_case = sealed_suite.cases[3]
    assert (
        output_dir / "cases" / later_case.case_id / "structured_output.json"
    ).is_file()
    affected_pair = first_case.bilingual_pair_id
    pair = json.loads(
        (output_dir / "bilingual_pairs" / f"{affected_pair}.json").read_text()
    )
    assert pair["status"] == "not_evaluable"


def test_existing_output_root_refuses_rerun_before_discovery(
    tmp_path: Path,
    sealed_suite: g3c.G3CSuite,
) -> None:
    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    transport = FakeG3CV3Transport(output_dir)
    with pytest.raises(FileExistsError):
        g3c.execute_g3c_screen(
            suite=sealed_suite,
            output_dir=output_dir,
            source_commit="c" * 40,
            environ=ENVIRONMENT,
            inner_transport=transport,
            enforce_sealed_output_root=False,
        )
    assert transport.chat_count == 0
    assert transport.discovery_observed_planned_ledger is False


def test_report_keeps_dimensions_independent_and_has_no_aggregate(
    mixed_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
) -> None:
    output_dir, _, summary = mixed_screen
    report = json.loads((output_dir / "report.json").read_text())
    assert set(report["sections"]) == {
        "1. Structural contract",
        "2. Action family and subtype",
        "3. Action unsupported overclaims",
        "4. Option mapping and abstention",
        "5. Motive coverage and precision",
        "6. Motive overclaims and minimality",
        "7. Unknown preservation",
        "8. Racio-reported uncertainty",
        "9. Slovenian-English consistency",
        "10. Individual failures",
        "11. Confidence values",
        "12. Frozen G3 V2 versus G3C V3",
    }
    assert report["study_context"] == {
        "development_rerun": True,
        "untouched_holdout": False,
        "generalization_claim": False,
        "model_promoted": False,
        "governance_authority": False,
        "runtime_authority": False,
    }
    assert summary["study_context"] == report["study_context"]
    assert set(report["metric_contract"]) == {
        "action_family_coverage",
        "action_subtype_coverage",
        "action_unsupported_overclaims",
        "option_mapping",
        "required_abstention",
        "motive_family_coverage",
        "motive_subtype_coverage",
        "motive_precision",
        "high_confidence_unsupported_motives",
        "unknown_preservation",
        "bilingual_family_consistency",
        "bilingual_subtype_consistency",
        "uncertainty_consistency",
    }
    assert not _all_keys(report).intersection(g3c._FORBIDDEN_AGGREGATE_KEYS)
    assert not _all_keys(summary).intersection(g3c._FORBIDDEN_AGGREGATE_KEYS)
    assert report["sections"]["8. Racio-reported uncertainty"][
        "used_as_hard_gate"
    ] is False
    contract = report["sections"]["1. Structural contract"]
    assert contract["attempted_calls"] == 16
    assert contract["successful_calls"] == 13
    assert contract["retries"] == 0
    assert contract["fallbacks"] == 0
    action = report["sections"]["2. Action family and subtype"]
    assert action["target_level_coverage"]["family"]["denominator"] == 13
    assert action["target_level_coverage"]["exact_subtype"]["denominator"] == 13
    assert action["planned_target_level_coverage"]["family"]["denominator"] == 16
    motive = report["sections"]["5. Motive coverage and precision"]
    assert motive["target_level_coverage"]["direct_family"]["denominator"] == 11
    assert motive["planned_target_level_coverage"]["direct_family"][
        "denominator"
    ] == 14
    option = report["sections"]["4. Option mapping and abstention"]
    assert option["option_specific_evidence_support"]["denominator"] == 0
    assert option["option_specific_evidence_support"]["value"] is None
    uncertainty = report["sections"]["8. Racio-reported uncertainty"]
    assert uncertainty["self_report_unavailable_case_count"] == 3
    assert set(uncertainty["option_mapping_self_report_states"]).issubset(
        {"uncertain", "not_uncertain", "not_reported"}
    )
    assert set(uncertainty["motive_interpretation_self_report_states"]).issubset(
        {"uncertain", "not_uncertain", "not_reported"}
    )
    comparison = report["sections"]["12. Frozen G3 V2 versus G3C V3"]
    assert comparison["motive_overclaims"]["frozen_v2_flagged_total"] == 15
    assert comparison["motive_overclaims"]["g3a_adjudicated_true_total"] == 14
    assert comparison["motive_overclaims"][
        "direct_historical_comparison_available"
    ] is False
    assert set(comparison["action_family_interpretation"]["g3c_v3"]) == {
        "combined",
        "sl",
        "en",
    }


def test_cold_validation_replays_success_without_network(
    successful_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
) -> None:
    output_dir, transport, _ = successful_screen
    before = transport.chat_count
    receipt = g3c.cold_validate_g3c_output(
        suite=g3c.load_g3c_suite(),
        output_dir=output_dir,
        persist_receipt=False,
    )
    assert transport.chat_count == before
    assert receipt["model_call_count"] == 0
    assert receipt["case_evaluations_recomputed"] == 16
    assert receipt["bilingual_evaluations_recomputed"] == 8
    assert receipt["provider_execution_lineages_revalidated"] == 16


def test_cold_validation_handles_mixed_failures_and_persists_once(
    mixed_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    output_dir, transport, _ = mixed_screen
    receipt = g3c.cold_validate_g3c_output(
        suite=sealed_suite,
        output_dir=output_dir,
    )
    assert transport.chat_count == 16
    assert receipt["model_call_count"] == 0
    assert receipt["provider_execution_lineages_revalidated"] == 13
    assert receipt["bilingual_not_evaluable_count"] >= 1
    assert (output_dir / "cold_validation.json").is_file()
    with pytest.raises(FileExistsError):
        g3c.cold_validate_g3c_output(suite=sealed_suite, output_dir=output_dir)


def test_cold_validation_rejects_tampered_evaluation(
    tmp_path: Path,
    successful_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    source, _, _ = successful_screen
    copied = tmp_path / "tampered"
    shutil.copytree(source, copied)
    case_id = sealed_suite.cases[0].case_id
    evaluation_path = copied / "cases" / case_id / "case_evaluation.json"
    evaluation = json.loads(evaluation_path.read_text())
    evaluation["action_unsupported_overclaims"] += 1
    evaluation_path.write_bytes(g3c.canonical_json_bytes(evaluation) + b"\n")
    with pytest.raises(ValueError, match="evaluation replay differs"):
        g3c.cold_validate_g3c_output(
            suite=sealed_suite,
            output_dir=copied,
            persist_receipt=False,
        )


def test_observations_are_atomic_and_bilingual_glosses_are_audited(
    sealed_suite: g3c.G3CSuite,
) -> None:
    for case in sealed_suite.cases:
        observations = case.packet.visible_observations
        assert all(item.perceptual_unit_count == 1 for item in observations)
        assert len({item.observation_id for item in observations}) == len(observations)
        assert len({item.atomic_evidence_unit_id for item in observations}) == len(
            observations
        )
        for observation in observations:
            audit = observation.text.gloss_audit
            assert audit.approved is True
            assert audit.signatures_equivalent is True
            assert audit.reserved_collisions_aligned is True
            assert audit.no_added_action_claims is True
            assert audit.no_added_motive_claims is True
            assert audit.no_added_causal_claims is True
            assert audit.strength_aligned is True


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("retry_count", 1),
        ("fallback", "synthetic"),
        ("presentation_mode", "operational_en_only"),
        ("packet_hash", "0" * 64),
        ("call_spec_hash", "1" * 64),
        ("confidence_values", None),
    ),
)
def test_cold_validation_rejects_tampered_case_result_contract(
    tmp_path: Path,
    successful_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
    field: str,
    replacement: Any,
) -> None:
    source, _, _ = successful_screen
    copied = _copy_screen(source, tmp_path / f"tampered-{field}")
    case_id = sealed_suite.cases[0].case_id
    result_path = copied / "cases" / case_id / "case_result.json"
    result = json.loads(result_path.read_text())
    result[field] = replacement
    _canonical_write(result_path, result)
    with pytest.raises(ValueError, match="case result differs"):
        g3c.cold_validate_g3c_output(
            suite=sealed_suite,
            output_dir=copied,
            persist_receipt=False,
        )


def test_cold_validation_rejects_private_failure_diagnostic(
    tmp_path: Path,
    mixed_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    source, _, _ = mixed_screen
    copied = _copy_screen(source, tmp_path / "private-failure")
    case_id = sealed_suite.cases[0].case_id
    failure_path = copied / "cases" / case_id / "sanitized_failure.json"
    failure = json.loads(failure_path.read_text())
    failure["sanitized_diagnostics"]["thinking"] = "must-not-persist"
    _canonical_write(failure_path, failure)
    with pytest.raises(ValueError, match="private response content key persisted"):
        g3c.cold_validate_g3c_output(
            suite=sealed_suite,
            output_dir=copied,
            persist_receipt=False,
        )


def test_cold_validation_rejects_tampered_failure_boundary(
    tmp_path: Path,
    mixed_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    source, _, _ = mixed_screen
    copied = _copy_screen(source, tmp_path / "failure-boundary")
    case_id = sealed_suite.cases[1].case_id
    failure_path = copied / "cases" / case_id / "sanitized_failure.json"
    failure = json.loads(failure_path.read_text())
    failure["validation_boundary"] = "before_json_pydantic_validation"
    _canonical_write(failure_path, failure)
    with pytest.raises(ValueError, match="failure artifact differs"):
        g3c.cold_validate_g3c_output(
            suite=sealed_suite,
            output_dir=copied,
            persist_receipt=False,
        )


def test_cold_validation_rejects_validation_code_relabelled_as_transport(
    tmp_path: Path,
    mixed_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    source, _, _ = mixed_screen
    copied = _copy_screen(source, tmp_path / "failure-stage")
    case_id = sealed_suite.cases[1].case_id
    failure_path = copied / "cases" / case_id / "sanitized_failure.json"
    failure = json.loads(failure_path.read_text())
    failure["failure_stage"] = "transport"
    failure["validation_boundary"] = "before_json_pydantic_validation"
    _canonical_write(failure_path, failure)
    with pytest.raises(ValueError, match="failure code/stage pair differs"):
        g3c.cold_validate_g3c_output(
            suite=sealed_suite,
            output_dir=copied,
            persist_receipt=False,
        )


def test_cold_validation_rejects_coordinated_not_evaluable_pair_tampering(
    tmp_path: Path,
    mixed_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    source, _, _ = mixed_screen
    copied = _copy_screen(source, tmp_path / "pair")
    pair = sealed_suite.pairs[0]
    pair_path = copied / "bilingual_pairs" / f"{pair.bilingual_pair_id}.json"
    tampered = json.loads(pair_path.read_text())
    assert tampered["status"] == "not_evaluable"
    tampered["available_output_case_ids"] = [pair.sl_case_id]
    _canonical_write(pair_path, tampered)
    for case_id in (pair.sl_case_id, pair.en_case_id):
        _canonical_write(
            copied / "cases" / case_id / "bilingual_pair_evaluation.json",
            tampered,
        )
    with pytest.raises(ValueError, match="pair replay differs"):
        g3c.cold_validate_g3c_output(
            suite=sealed_suite,
            output_dir=copied,
            persist_receipt=False,
        )


def test_cold_validation_rejects_tampered_dispatch_ledger(
    tmp_path: Path,
    successful_screen: tuple[Path, FakeG3CV3Transport, dict[str, Any]],
    sealed_suite: g3c.G3CSuite,
) -> None:
    source, _, _ = successful_screen
    copied = _copy_screen(source, tmp_path / "ledger")
    case = sealed_suite.cases[0]
    before_path = copied / "attempt_ledger" / f"002_{case.case_id}_before.json"
    before = json.loads(before_path.read_text())
    before["call_id"] = "provider_call_tampered"
    _canonical_write(before_path, before)
    with pytest.raises(ValueError, match="dispatch ledger differs"):
        g3c.cold_validate_g3c_output(
            suite=sealed_suite,
            output_dir=copied,
            persist_receipt=False,
        )


def test_report_metric_oracle_covers_positive_and_overclaim_paths(
    sealed_suite: g3c.G3CSuite,
) -> None:
    outputs: dict[str, Any] = {}
    case_results: list[dict[str, Any]] = []
    for case in sealed_suite.cases:
        action_target = case.gold.exact_action_targets[0]
        motive_drafts = [
            {
                "family": target.family,
                "subtype": target.subtype,
                "cited_observation_ids": target.supporting_observation_ids,
                "confidence": 0.75,
                "support_mode": "directly_supported",
            }
            for target in case.gold.direct_motive_targets
        ]
        if case.root_label == "H1":
            motive_drafts.append(
                {
                    "family": "motor_social",
                    "subtype": "motor_execution",
                    "cited_observation_ids": (
                        case.gold.action_only_observation_ids[0],
                    ),
                    "confidence": 0.75,
                    "support_mode": "directly_supported",
                }
            )
        option = (
            None
            if case.gold.option_determinacy != "unique"
            else {
                "option_id": case.gold.acceptable_option_ids[0],
                "cited_observation_ids": case.gold.option_support_observation_ids,
                "confidence": 0.8,
            }
        )
        draft = g3c.RacioEpistemicDraftV3.model_validate(
            {
                "source_mind": case.packet.source_mind,
                "action_hypotheses": (
                    {
                        "family": action_target.family,
                        "subtype": action_target.subtype,
                        "family_fallback": action_target.family_fallback,
                        "cited_observation_ids": (
                            action_target.supporting_observation_ids
                        ),
                        "confidence": 0.8,
                        "support_mode": action_target.accepted_support_modes[0],
                    },
                ),
                "option_inference": option,
                "motive_hypotheses": tuple(motive_drafts),
                "racio_reported_uncertainty": {
                    "option_mapping": (
                        "not_uncertain"
                        if case.gold.option_determinacy == "unique"
                        else "uncertain"
                    ),
                    "motive_interpretation": (
                        "not_uncertain"
                        if case.gold.direct_motive_targets
                        else "uncertain"
                    ),
                },
            }
        )
        output = g3c.canonicalize_racio_epistemic_draft_v3(case.packet, draft)
        outputs[case.case_id] = output
        evaluation = g3c.evaluate_racio_epistemic_case_v3(
            packet=case.packet,
            gold=case.gold,
            output=output,
            input_packet_unchanged=True,
        )
        uncertainty = g3c.build_uncertainty_receipt(case=case, output=output)
        case_results.append(
            g3c._build_case_result(
                case=case,
                draft=draft,
                output=output,
                provider_status="succeeded",
                failure_code=None,
                failure_payload=None,
                evaluation=evaluation,
                uncertainty=uncertainty,
            )
        )

    case_by_id = {case.case_id: case for case in sealed_suite.cases}
    pair_results = []
    for pair in sealed_suite.pairs:
        evaluation = g3c.evaluate_racio_epistemic_bilingual_pair_v3(
            bilingual_pair_id=pair.bilingual_pair_id,
            sl_packet=case_by_id[pair.sl_case_id].packet,
            sl_output=outputs[pair.sl_case_id],
            en_packet=case_by_id[pair.en_case_id].packet,
            en_output=outputs[pair.en_case_id],
        )
        pair_results.append(
            {
                "schema_version": "rei-racio-g3c-v3-pair-result-v1",
                "bilingual_pair_id": pair.bilingual_pair_id,
                "status": "evaluated",
                "sl_case_id": pair.sl_case_id,
                "en_case_id": pair.en_case_id,
                "evaluation": evaluation.model_dump(mode="json"),
            }
        )

    report = g3c.build_g3c_report(
        cases=sealed_suite.cases,
        case_results=tuple(case_results),
        pair_results=tuple(pair_results),
    )
    metrics = report["metric_contract"]
    assert metrics["action_family_coverage"] == {
        "numerator": 16,
        "denominator": 16,
        "value": 1.0,
    }
    assert metrics["action_subtype_coverage"]["numerator"] == 16
    assert metrics["option_mapping"]["unique_option_mapping"]["numerator"] == 12
    assert metrics["required_abstention"]["numerator"] == 4
    assert metrics["motive_family_coverage"]["numerator"] == 14
    assert metrics["motive_subtype_coverage"]["numerator"] == 14
    assert metrics["motive_precision"] == {
        "numerator": 14,
        "denominator": 16,
        "value": 0.875,
    }
    assert metrics["high_confidence_unsupported_motives"] == 2
    comparison = report["sections"]["12. Frozen G3 V2 versus G3C V3"]
    assert comparison["motive_overclaims"]["frozen_v2_flagged_total"] == 15
    assert comparison["motive_overclaims"]["g3a_adjudicated_true_total"] == 14
    assert comparison["motive_overclaims"][
        "direct_historical_comparison_available"
    ] is True
    assert comparison["action_family_interpretation"]["g3c_v3"]["sl"][
        "denominator"
    ] == 8
    assert comparison["action_family_interpretation"]["g3c_v3"]["en"][
        "denominator"
    ] == 8
