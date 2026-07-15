from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from app.backend.rei.communication.structured_interpreter import (
    StructuredRacioInterpreterOutput,
)
from app.backend.rei.evaluation.racio_interpreter_benchmark import (
    DATA_ROOT,
    MANIFEST_PATH,
    OFFICIAL_MANIFEST_SHA256,
    evaluate_c3_benchmark_case,
    evaluate_c3_benchmark_run,
    load_c3_racio_interpreter_benchmark,
)
from scripts.run_racio_interpreter_benchmark import deterministic_results


def _raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_corpus_is_lf_only_hashed_and_exactly_balanced() -> None:
    for source in (
        DATA_ROOT / "public_cases.jsonl",
        DATA_ROOT / "gold.jsonl",
        MANIFEST_PATH,
    ):
        assert b"\r\n" not in source.read_bytes()

    suite = load_c3_racio_interpreter_benchmark()

    assert suite.manifest_file_hash == OFFICIAL_MANIFEST_SHA256
    assert _raw_sha256(MANIFEST_PATH) == OFFICIAL_MANIFEST_SHA256
    assert len(suite.cases) == 32
    assert suite.manifest.counts.model_dump(mode="python") == {
        "cases": 32,
        "roots": 8,
        "emocio": 16,
        "instinkt": 16,
        "slovenian": 16,
        "english": 16,
        "unambiguous": 16,
        "ambiguous": 16,
        "accepting": 16,
        "mixed": 8,
        "conflicted": 8,
        "bilingual_pairs": 16,
    }
    for declared in suite.manifest.files:
        source = DATA_ROOT / declared.path
        assert _raw_sha256(source) == declared.sha256
        assert len(source.read_text(encoding="utf-8").splitlines()) == 32


def test_gold_is_physical_evaluator_only_data_and_never_provider_payload() -> None:
    public_bytes = (DATA_ROOT / "public_cases.jsonl").read_bytes()
    gold_bytes = (DATA_ROOT / "gold.jsonl").read_bytes()
    assert b"expected_option_id" not in public_bytes
    assert b"evaluator_only_canary" not in public_bytes
    assert b"expected_option_id" in gold_bytes
    assert b"evaluator_only_canary" in gold_bytes

    suite = load_c3_racio_interpreter_benchmark()
    hidden_tokens = {
        token
        for case in suite.cases
        for token in (
            case.gold.native_truth_id,
            case.gold.profile_id,
            case.gold.evaluator_only_canary,
            case.gold.family_id,
            case.gold.variant_id,
        )
    }
    for case in suite.cases:
        payload = case.packet.provider_payload()
        encoded = case.packet.provider_payload_bytes().decode("utf-8")
        assert case.public.case_id not in encoded
        assert case.public.root_id not in encoded
        assert not any(token in encoded for token in hidden_tokens)
        assert {
            "case_id",
            "root_id",
            "acceptance_mode",
            "ambiguity_class",
            "expected_option_id",
            "expected_action_tendency",
            "expected_motive_class",
            "native_truth_id",
            "profile_id",
            "evaluator_only_canary",
        }.isdisjoint(payload)


def test_gold_uses_the_frozen_controlled_action_and_motive_vocabularies() -> None:
    suite = load_c3_racio_interpreter_benchmark()

    assert {case.gold.expected_action_tendency for case in suite.cases} == {
        "attack",
        "seek_attachment",
        "perform",
        "seek_safety",
        "connect",
        "protect",
        "set_boundary",
        "unknown",
    }
    assert {case.gold.expected_motive_class for case in suite.cases} == {
        "broken_scene",
        "attachment",
        "motor_pattern",
        "body_alarm",
        "boundary_alarm",
        "unknown",
    }


def test_deterministic_baseline_is_model_free_and_closes_structural_gate() -> None:
    suite = load_c3_racio_interpreter_benchmark()
    results = deterministic_results(suite)
    metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="deterministic",
        results=results,
        model_call_count=0,
    )

    assert metrics.model_call_count == 0
    assert metrics.structured_output_valid_count == 32
    assert metrics.citation_scope_failure_count == 0
    assert metrics.hidden_truth_leakage_count == 0
    assert metrics.profile_leakage_count == 0
    assert metrics.input_packet_mutation_count == 0
    assert metrics.provenance_scope_failure_count == 0
    assert metrics.unambiguous_exact_option_count == 0
    assert metrics.unambiguous_exact_action_count == 16
    assert metrics.unambiguous_exact_motive_count == 0
    assert metrics.ambiguous_gate_pass_count == 16
    assert metrics.bilingual_consistent_pair_count == 16
    assert metrics.passed_case_count == 16
    assert metrics.structural_gate_pass is True
    assert metrics.quality_gate_pass is True
    assert all(result.provenance.provider_uses_model is False for result in results)
    assert all(result.provenance.call_record is not None for result in results)
    assert all(result.provenance.response_evidence_json for result in results)


def test_out_of_scope_observation_citation_is_a_case_failure() -> None:
    suite = load_c3_racio_interpreter_benchmark()
    baseline = deterministic_results(suite)
    case = suite.cases[0]
    original = baseline[0]
    assert original.output is not None
    invalid_output = StructuredRacioInterpreterOutput(
        **{
            **original.output.model_dump(mode="python"),
            "cited_observation_ids": ("observation_999",),
        }
    )

    result = evaluate_c3_benchmark_case(
        case=case,
        provider_mode="deterministic",
        output=invalid_output,
        provenance=original.provenance,
        input_packet_unchanged=True,
    )

    assert result.structured_output_valid is True
    assert result.citation_scope_valid is False
    assert result.passed is False
    assert "citation_scope_failure" in result.issues


def test_ambiguous_gate_requires_every_abstention_condition() -> None:
    suite = load_c3_racio_interpreter_benchmark()
    baseline = deterministic_results(suite)
    index = next(
        index
        for index, case in enumerate(suite.cases)
        if case.gold.ambiguity_class == "ambiguous"
    )
    case = suite.cases[index]
    original = baseline[index]
    assert original.output is not None
    assert original.ambiguity_gate_pass is True

    invalid_updates = (
        {"inferred_option_id": case.packet.public_option_scope[0].option_id},
        {"confidence": case.gold.maximum_ambiguous_confidence + 0.01},
        {"inferred_action_tendency": "protect"},
        {"inferred_motive_class": "body_alarm"},
    )
    for update in invalid_updates:
        invalid_output = StructuredRacioInterpreterOutput.model_validate(
            {**original.output.model_dump(mode="python"), **update}
        )
        result = evaluate_c3_benchmark_case(
            case=case,
            provider_mode="deterministic",
            output=invalid_output,
            provenance=original.provenance,
            input_packet_unchanged=True,
        )

        assert result.ambiguity_gate_pass is False
        assert result.passed is False
        assert "semantic_gate_failure" in result.issues


def test_run_gate_requires_exact_model_call_count_and_strict_improvement() -> None:
    suite = load_c3_racio_interpreter_benchmark()
    baseline = deterministic_results(suite)

    with pytest.raises(ValueError, match="model call count"):
        evaluate_c3_benchmark_run(
            suite=suite,
            provider_mode="deterministic",
            results=baseline,
            model_call_count=1,
        )

    unchanged_model_results = tuple(
        result.model_copy(update={"provider_mode": "ollama"})
        for result in baseline
    )
    with pytest.raises(ValueError, match="result artifact is invalid"):
        evaluate_c3_benchmark_run(
            suite=suite,
            provider_mode="ollama",
            results=unchanged_model_results,
            model_call_count=32,
            baseline_results=baseline,
        )


def test_loader_rejects_raw_corpus_tampering(tmp_path: Path) -> None:
    copied = tmp_path / "c3_racio_interpreter"
    shutil.copytree(DATA_ROOT, copied)
    public_path = copied / "public_cases.jsonl"
    original = public_path.read_bytes()
    public_path.write_bytes(original.replace(b'"channel_quality":1.0', b'"channel_quality":0.9', 1))

    with pytest.raises(ValueError, match="file hash mismatch"):
        load_c3_racio_interpreter_benchmark(copied / "manifest.json")


def test_manifest_declares_manually_authored_non_training_gold() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["gold_origin"] == "manually_authored"
    assert manifest["model_generated_gold"] is False
    assert manifest["training_export"] is False
