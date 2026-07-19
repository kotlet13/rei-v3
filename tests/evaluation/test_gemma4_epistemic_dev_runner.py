from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

import scripts.run_gemma4_racio_epistemic_dev as dev_runner
from app.backend.rei.communication.epistemic_interpreter import (
    MOTIVE_UNKNOWN_REASON_SL,
    RacioEpistemicInterpretationV2,
    RacioReportedUncertainty,
)
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


class ModelFreeFailingTransport:
    """Exercise the real provider without contacting Ollama."""

    def __init__(self, ledger_path: Path, *, succeed: bool = False) -> None:
        self.ledger_path = ledger_path
        self.succeed = succeed
        self.chat_count = 0
        self.discovery_observed_ledger = False

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
            self.discovery_observed_ledger = self.ledger_path.is_file()
            return {"version": "0.31.2"}
        if path == "/api/tags":
            return {
                "models": [
                    {
                        "name": GEMMA4_EPISTEMIC_MODEL,
                        "model": GEMMA4_EPISTEMIC_MODEL,
                        "digest": dev_runner.EXPECTED_MODEL_DIGEST,
                        "size": 19_868_969_920,
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
                "details": {
                    "quantization_level": GEMMA4_EPISTEMIC_QUANTIZATION,
                },
                "model_info": {
                    "general.architecture": "gemma4",
                    "general.parameter_count": GEMMA4_EPISTEMIC_PARAMETER_COUNT,
                    "gemma4.context_length": 262144,
                },
                "template": GEMMA4_EPISTEMIC_TEMPLATE,
                "capabilities": list(GEMMA4_EPISTEMIC_CAPABILITIES),
            }
        if path == "/api/chat":
            self.chat_count += 1
            if self.succeed:
                assert payload is not None
                packet = json.loads(payload["messages"][1]["content"])
                output = RacioEpistemicInterpretationV2(
                    source_mind=packet["source_mind"],
                    cited_observation_ids=(
                        packet["visible_observations"][0]["observation_id"],
                    ),
                    inferred_action_tendency="unknown",
                    action_confidence=0.0,
                    inferred_option_id=None,
                    option_confidence=0.0,
                    motive_hypotheses=(),
                    motive_unknown_reason=MOTIVE_UNKNOWN_REASON_SL,
                    racio_reported_uncertainty=RacioReportedUncertainty(
                        option_mapping="not_reported",
                        motive_interpretation="not_reported",
                    ),
                )
                return {
                    "model": GEMMA4_EPISTEMIC_MODEL,
                    "message": {
                        "role": "assistant",
                        "content": output.model_dump_json(),
                        "thinking": "synthetic private trace",
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
            return {
                "model": GEMMA4_EPISTEMIC_MODEL,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "thinking": "synthetic private trace",
                },
                "done": False,
                "done_reason": "length",
            }
        if path == "/api/ps":
            return {
                "models": [
                    {
                        "name": GEMMA4_EPISTEMIC_MODEL,
                        "model": GEMMA4_EPISTEMIC_MODEL,
                        "digest": dev_runner.EXPECTED_MODEL_DIGEST,
                        "size": 1000,
                        "size_vram": 1000,
                        "context_length": GEMMA4_EPISTEMIC_NUM_CTX,
                    }
                ]
            }
        raise AssertionError(f"Unexpected fake Ollama endpoint: {path}")


@pytest.fixture(scope="module")
def sealed_suite() -> dev_runner.Gemma4DevSuite:
    return dev_runner.load_development_suite()


@pytest.fixture(scope="module")
def failed_screen(
    tmp_path_factory: pytest.TempPathFactory,
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> tuple[Path, ModelFreeFailingTransport, dict[str, Any]]:
    output_dir = tmp_path_factory.mktemp("gemma4-dev-run") / "screen"
    transport = ModelFreeFailingTransport(
        output_dir / "attempt_ledger" / "000_planned.json"
    )
    summary = dev_runner.execute_development_screen(
        suite=sealed_suite,
        output_dir=output_dir,
        source_commit="a" * 40,
        environ=ENVIRONMENT,
        inner_transport=transport,
    )
    return output_dir, transport, summary


@pytest.fixture(scope="module")
def successful_screen(
    tmp_path_factory: pytest.TempPathFactory,
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> tuple[Path, ModelFreeFailingTransport, dict[str, Any]]:
    output_dir = tmp_path_factory.mktemp("gemma4-dev-success") / "screen"
    transport = ModelFreeFailingTransport(
        output_dir / "attempt_ledger" / "000_planned.json",
        succeed=True,
    )
    summary = dev_runner.execute_development_screen(
        suite=sealed_suite,
        output_dir=output_dir,
        source_commit="a" * 40,
        environ=ENVIRONMENT,
        inner_transport=transport,
    )
    return output_dir, transport, summary


def _all_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for item in value.values():
            keys.update(_all_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_all_keys(item))
    return keys


def test_committed_corpus_seal_hashes_and_order(
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    assert sealed_suite.manifest_sha256 == dev_runner.EXPECTED_MANIFEST_SHA256
    assert [case.case_id for case in sealed_suite.cases] == sealed_suite.manifest[
        "case_order"
    ]


def test_gold_json_arrays_load_as_strict_tuple_fields(
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    gold = sealed_suite.cases[0].gold
    assert type(gold.acceptable_option_ids) is tuple
    assert type(gold.expected_action_tendencies) is tuple
    assert type(gold.acceptable_motive_hypotheses) is tuple
    assert type(gold.acceptable_motive_hypotheses[0].supporting_observation_ids) is tuple
    assert len(sealed_suite.cases) == 16
    assert len({case.bilingual_pair_id for case in sealed_suite.cases}) == 8
    assert [case.packet.language for case in sealed_suite.cases] == [
        language for _ in range(8) for language in ("sl", "en")
    ]


def test_manifest_and_corpus_tampering_fail_closed(
    tmp_path: Path,
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    copied = tmp_path / "corpus"
    shutil.copytree(sealed_suite.manifest_path.parent, copied)
    manifest_path = copied / "manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="manifest differs"):
        dev_runner.load_development_suite(manifest_path)

    shutil.rmtree(copied)
    shutil.copytree(sealed_suite.manifest_path.parent, copied)
    public_path = copied / "public_cases.jsonl"
    public_path.write_bytes(public_path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="corpus hash differs"):
        dev_runner.load_development_suite(
            copied / "manifest.json",
            expected_manifest_sha256=sealed_suite.manifest_sha256,
        )


def test_provider_packets_exclude_wrapper_and_gold_tokens(
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    for case in sealed_suite.cases:
        payload = case.packet.provider_payload_bytes().decode("utf-8").casefold()
        forbidden_values = (
            case.case_id,
            case.root_label,
            case.source_case_id,
            case.source_root_id,
            case.bilingual_pair_id,
            *case.gold.hidden_provider_tokens,
            case.gold.profile_id,
        )
        assert all(value.casefold() not in payload for value in forbidden_values)
        assert "evaluator_only_canary" not in payload
        assert "native_truth_id" not in payload
        assert "profile_id" not in payload


def test_attempt_ledger_precedes_discovery_and_dispatch_is_one_shot(
    failed_screen: tuple[Path, ModelFreeFailingTransport, dict[str, Any]],
) -> None:
    output_dir, transport, summary = failed_screen
    assert transport.discovery_observed_ledger is True
    assert transport.chat_count == 16
    assert summary["technical_completeness"]["chat_dispatch_count"] == 16
    assert summary["technical_completeness"]["retry_count"] == 0
    assert summary["technical_completeness"]["fallback_count"] == 0
    assert summary["technical_completeness"]["one_dispatch_per_case"] is True
    after_events = sorted((output_dir / "attempt_ledger").glob("*_after.json"))
    assert len(after_events) == 16
    assert all(json.loads(path.read_text())["dispatch_delta"] == 1 for path in after_events)


def test_existing_output_directory_refuses_rerun_before_chat(
    failed_screen: tuple[Path, ModelFreeFailingTransport, dict[str, Any]],
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    output_dir, transport, _ = failed_screen
    before = transport.chat_count
    with pytest.raises(FileExistsError):
        dev_runner.execute_development_screen(
            suite=sealed_suite,
            output_dir=output_dir,
            source_commit="a" * 40,
            environ=ENVIRONMENT,
            inner_transport=transport,
        )
    assert transport.chat_count == before


def test_dispatched_failure_has_standard_record_and_missing_receipts(
    failed_screen: tuple[Path, ModelFreeFailingTransport, dict[str, Any]],
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    output_dir, _, _ = failed_screen
    case_dir = output_dir / "cases" / sealed_suite.cases[0].case_id
    record = ProviderCallRecord.model_validate_json(
        (case_dir / "provider_call_record.json").read_bytes()
    )
    failure = json.loads((case_dir / "sanitized_failure.json").read_text())
    assert record.status == "failed"
    assert record.primary_status == "failed"
    assert record.output_artifact_ids == ()
    assert record.warnings == (
        "sanitized_failure_code:generation_contract_failure",
    )
    assert failure["failure_code"] == "generation_contract_failure"
    assert failure["validation_boundary"] == "before_json_pydantic_validation"
    assert failure["thinking_content_persisted"] is False
    assert failure["raw_response_envelope_persisted"] is False
    assert (case_dir / "structured_output_missing.json").is_file()
    assert (case_dir / "response_evidence_missing.json").is_file()


def test_success_persists_validated_evidence_without_private_text(
    successful_screen: tuple[Path, ModelFreeFailingTransport, dict[str, Any]],
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    output_dir, transport, summary = successful_screen
    assert transport.chat_count == 16
    assert summary["technical_completeness"]["provider_success_count"] == 16
    assert summary["technical_completeness"]["provider_failure_count"] == 0
    case_dir = output_dir / "cases" / sealed_suite.cases[0].case_id
    evidence = json.loads((case_dir / "response_evidence.json").read_text())
    record = ProviderCallRecord.model_validate_json(
        (case_dir / "provider_call_record.json").read_bytes()
    )
    assert record.status == "succeeded"
    assert evidence["thinking_present"] is True
    assert len(evidence["thinking_sha256"]) == 64
    assert "synthetic private trace" not in (
        case_dir / "response_evidence.json"
    ).read_text()
    pair_receipts = sorted((output_dir / "bilingual_pairs").glob("*.json"))
    assert len(pair_receipts) == 8
    assert all(json.loads(path.read_text())["status"] == "evaluated" for path in pair_receipts)
    case_pair_receipts = sorted(
        (output_dir / "cases").glob("*/bilingual_pair_evaluation.json")
    )
    assert len(case_pair_receipts) == 16
    global_pairs = {
        item["bilingual_pair_id"]: item
        for item in (json.loads(path.read_text()) for path in pair_receipts)
    }
    for path in case_pair_receipts:
        receipt = json.loads(path.read_text())
        assert receipt["status"] == "evaluated"
        assert receipt == global_pairs[receipt["bilingual_pair_id"]]
    assert all(
        json.loads(path.read_text())["evaluation"][
            "reported_uncertainty_consistent"
        ]
        is True
        for path in pair_receipts
    )


def test_uncertainty_comparison_is_descriptive_and_non_gating(
    sealed_suite: dev_runner.Gemma4DevSuite,
) -> None:
    case = sealed_suite.cases[0]
    output = RacioEpistemicInterpretationV2(
        source_mind=case.packet.source_mind,
        cited_observation_ids=(case.packet.visible_observation_ids[0],),
        inferred_action_tendency="unknown",
        action_confidence=0.0,
        inferred_option_id=None,
        option_confidence=0.0,
        motive_hypotheses=(),
        motive_unknown_reason=MOTIVE_UNKNOWN_REASON_SL,
        racio_reported_uncertainty=RacioReportedUncertainty(
            option_mapping="uncertain",
            motive_interpretation="not_reported",
        ),
    )
    comparison = dev_runner.build_uncertainty_comparison(case=case, output=output)
    assert comparison["structure_status"] == "valid"
    assert comparison["racio_reported_uncertainty"] == {
        "option_mapping": "uncertain",
        "motive_interpretation": "not_reported",
    }
    assert comparison["used_as_hard_gate"] is False
    assert comparison["mechanically_repaired"] is False
    assert "unique" in comparison["descriptive_comparison"]["option_mapping"]
    assert not _all_keys(comparison).intersection(
        dev_runner._FORBIDDEN_AGGREGATE_KEYS
    )


def test_reports_keep_dimensions_separate_and_have_no_semantic_aggregate(
    failed_screen: tuple[Path, ModelFreeFailingTransport, dict[str, Any]],
) -> None:
    output_dir, _, summary = failed_screen
    report = json.loads((output_dir / "report.json").read_text())
    persisted_summary = json.loads((output_dir / "summary.json").read_text())
    assert set(report["sections"]) == {
        "1. Structural contract",
        "2. Action interpretation",
        "3. Option mapping",
        "4. Required abstention",
        "5. Motive hypotheses",
        "6. Unsupported overclaims",
        "7. Confidence",
        "8. Racio-reported uncertainty",
        "9. Slovenian-English consistency",
        "10. Individual failures",
    }
    assert set(persisted_summary) == {
        "technical_completeness",
        "independent_dimension_counts",
    }
    assert persisted_summary == summary
    forbidden = dev_runner._FORBIDDEN_AGGREGATE_KEYS
    assert not _all_keys(report).intersection(forbidden)
    assert not _all_keys(summary).intersection(forbidden)
    for case_path in (output_dir / "cases").glob("*/case_result.json"):
        assert not _all_keys(json.loads(case_path.read_text())).intersection(forbidden)
    pair_receipts = sorted((output_dir / "bilingual_pairs").glob("*.json"))
    assert len(pair_receipts) == 8
    assert all(json.loads(path.read_text())["status"] == "not_evaluable" for path in pair_receipts)
    case_pair_receipts = sorted(
        (output_dir / "cases").glob("*/bilingual_pair_evaluation.json")
    )
    assert len(case_pair_receipts) == 16
    global_pairs = {
        item["bilingual_pair_id"]: item
        for item in (json.loads(path.read_text()) for path in pair_receipts)
    }
    for path in case_pair_receipts:
        receipt = json.loads(path.read_text())
        assert receipt["status"] == "not_evaluable"
        assert receipt == global_pairs[receipt["bilingual_pair_id"]]
