from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.backend.rei.evaluation.manual_cases import (
    DEFAULT_FIXTURE_ROOT,
    ManualEvaluationCase,
    ManualFixtureSetOutcome,
    evaluate_manual_case,
    evaluate_manual_fixture_set,
    load_manual_evaluation_cases,
    load_manual_fixture_manifest,
    load_manual_terminology_policy,
)
from app.backend.rei.evaluation.models import (
    BilingualEvaluationCase,
    EgoEvaluationCase,
    NativeRouteEvaluationCase,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mismatch_diagnostics(
    suite: ManualFixtureSetOutcome,
) -> list[dict[str, object]]:
    return [
        {
            "case_id": outcome.case_id,
            "pass": (outcome.candidate_passed, outcome.expected_passed),
            "observed": (
                outcome.observed_label,
                outcome.expected_observed_label,
            ),
            "issues": (outcome.issue_codes, outcome.expected_issue_codes),
            "dimensions": (
                outcome.dimension_outcomes,
                outcome.expected_dimension_outcomes,
            ),
            "unexpected_failed_dimensions": outcome.unexpected_failed_dimensions,
        }
        for outcome in suite.outcomes
        if not outcome.exact_match
    ]


def _case(case_id: str) -> ManualEvaluationCase:
    return next(
        case for case in load_manual_evaluation_cases() if case.case_id == case_id
    )


def _mutated_case(
    case_id: str,
    mutate: Callable[[dict[str, Any]], None],
) -> ManualEvaluationCase:
    payload = _case(case_id).model_dump(mode="json")
    mutate(payload)
    return ManualEvaluationCase.model_validate_json(
        json.dumps(payload, ensure_ascii=False)
    )


def test_manual_fixture_manifest_hashes_and_counts_are_integral() -> None:
    manifest = load_manual_fixture_manifest()
    cases = load_manual_evaluation_cases()

    assert manifest.case_count == len(cases) == 32
    assert manifest.positive_case_count == 8
    assert manifest.negative_case_count == 24
    assert Counter(case.polarity for case in cases) == {
        "positive": 8,
        "negative": 24,
    }
    assert Counter(case.subject_kind for case in cases) == manifest.subject_counts
    assert manifest.model_judge_calls == 0
    assert manifest.model_generated_gold is False
    assert manifest.training_export is False
    assert manifest.reporting.global_rei_score is False
    assert manifest.reporting.dimensions_remain_separate is True

    assert _sha256(REPOSITORY_ROOT / manifest.policy.path) == manifest.policy.sha256
    assert (
        _sha256(REPOSITORY_ROOT / manifest.case_schema.path)
        == manifest.case_schema.sha256
    )
    for entry in manifest.files:
        assert _sha256(DEFAULT_FIXTURE_ROOT / entry.path) == entry.sha256


def test_all_32_manual_cases_match_exactly_without_model_calls() -> None:
    suite = evaluate_manual_fixture_set()

    assert len(suite.outcomes) == 32
    assert suite.exact_match_count == 32, _mismatch_diagnostics(suite)
    assert suite.exact_match is True
    assert suite.evaluator_model_calls == 0
    assert all(outcome.exact_match for outcome in suite.outcomes)
    assert all(outcome.evaluator_model_calls == 0 for outcome in suite.outcomes)
    assert all(not outcome.unexpected_failed_dimensions for outcome in suite.outcomes)
    assert all(
        outcome.semantic_result.evaluator_model_calls == 0
        for outcome in suite.outcomes
    )


def test_raw_schema_invalid_candidate_reaches_typed_schema_evaluator() -> None:
    case = next(
        case
        for case in load_manual_evaluation_cases()
        if case.case_id == "eval_schema_invalid_candidate"
    )
    assert "schema_version" not in case.candidate_payload

    outcome = evaluate_manual_case(case)

    assert outcome.exact_match is True
    assert outcome.observed_label == "schema_invalid"
    assert outcome.semantic_result.observed_label == "invalid_schema"
    assert outcome.semantic_result.passed is False
    assert {issue.issue_code for issue in outcome.semantic_result.issues} == {
        "schema_invalid"
    }
    assert outcome.semantic_result.evaluator_model_calls == 0


def test_manifest_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    copied_root = tmp_path / "semantic_evaluation_v1"
    shutil.copytree(DEFAULT_FIXTURE_ROOT, copied_root)
    with (copied_root / "native_routes.jsonl").open("ab") as handle:
        handle.write(b"\n")

    with pytest.raises(ValueError, match="digest mismatch"):
        load_manual_evaluation_cases(copied_root)


def test_case_envelope_forbids_undeclared_fields() -> None:
    raw = load_manual_evaluation_cases()[0].model_dump(mode="python")
    raw["candidate_result_copied_from_gold"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ManualEvaluationCase.model_validate(raw)


@pytest.mark.parametrize("field_name", ["family_id", "variant_id"])
def test_case_envelope_requires_outer_identity(field_name: str) -> None:
    raw = _case("eval_racio_route_complete").model_dump(mode="python")
    raw[field_name] = None

    with pytest.raises(ValidationError):
        ManualEvaluationCase.model_validate(raw)


def test_runtime_cases_do_not_receive_outer_gold_pass_or_issue_codes() -> None:
    for model in (
        NativeRouteEvaluationCase,
        BilingualEvaluationCase,
        EgoEvaluationCase,
    ):
        assert "expected_pass" not in model.model_fields
        assert "expected_issue_codes" not in model.model_fields


def test_native_decisive_representation_comes_from_explicit_gold() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["decisive_representation"] = "candidate tamper"

    outcome = evaluate_manual_case(_mutated_case("eval_racio_route_complete", mutate))

    assert outcome.exact_match is False
    assert any(
        metric.metric_id == "native_route_semantics" and metric.status == "failed"
        for metric in outcome.semantic_result.metrics
    )


def test_candidate_claim_sources_are_never_injected_from_gold() -> None:
    official = _case("eval_racio_route_complete")
    assert all(
        claim["source_claim_ids"]
        for claim in official.candidate_payload["claims"]
    )

    def mutate(payload: dict[str, object]) -> None:
        del payload["candidate_payload"]["claims"][0]["source_claim_ids"]

    outcome = evaluate_manual_case(_mutated_case(official.case_id, mutate))

    assert outcome.exact_match is False
    assert "unsupported_claim" in {
        item.issue_code for item in outcome.semantic_result.issues
    }


def test_native_candidate_wrong_terminology_surface_is_not_overwritten() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["terminology_uses"][0][
            "surface_form"
        ] = "Razum"

    outcome = evaluate_manual_case(_mutated_case("eval_racio_route_complete", mutate))

    assert outcome.exact_match is False
    assert "slovenian_terminology_mismatch" in {
        item.issue_code for item in outcome.semantic_result.issues
    }


@pytest.mark.parametrize("surface_field", ["sl_surface", "en_surface"])
def test_bilingual_candidate_wrong_surface_is_not_overwritten(
    surface_field: str,
) -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["terminology_pairs"][0][surface_field] = (
            "wrong surface"
        )

    outcome = evaluate_manual_case(
        _mutated_case("eval_bilingual_signature_consistent", mutate)
    )

    assert outcome.exact_match is False
    assert "bilingual_terminology_mismatch" in {
        item.issue_code for item in outcome.semantic_result.issues
    }


def test_canonical_term_pairs_are_loaded_from_trusted_c2_policy() -> None:
    policy = load_manual_terminology_policy()

    assert policy.canonical_term_pairs["REI_EMOCIO"].sl_surface == "Emocio"
    assert policy.canonical_term_pairs["REI_EMOCIO"].en_surface == "Emocio"
    assert (
        policy.canonical_term_pairs["REI_TRANSLATION_GAP"].en_surface
        == "translation gap"
    )


def test_bilingual_family_binding_is_evaluated_explicitly() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["family_id"] = "sf_wrong_family"

    outcome = evaluate_manual_case(
        _mutated_case("eval_bilingual_signature_consistent", mutate)
    )

    assert outcome.exact_match is False
    assert any(
        metric.metric_id == "bilingual_family_binding"
        and metric.status == "failed"
        for metric in outcome.semantic_result.metrics
    )
    assert "bilingual_family_mismatch" in {
        item.issue_code for item in outcome.semantic_result.issues
    }


def test_undeclared_failed_dimension_alone_blocks_exact_match() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["confidence"] = 0.1

    outcome = evaluate_manual_case(
        _mutated_case("eval_provenance_incomplete", mutate)
    )

    assert outcome.pass_matches is True
    assert outcome.observed_label_matches is True
    assert outcome.issue_codes_match is True
    assert outcome.dimension_outcomes_match is True
    assert outcome.unexpected_failed_dimensions == ("confidence_calibration",)
    assert outcome.exact_match is False


def test_interpretation_source_mind_is_bound_to_trusted_gold() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["source_mind"] = "I"

    outcome = evaluate_manual_case(
        _mutated_case("eval_interpretation_accurate", mutate)
    )

    assert outcome.exact_match is False
    assert "interpretation_identity_mismatch" in {
        item.issue_code for item in outcome.semantic_result.issues
    }


def test_interpretation_visible_scope_ignores_candidate_self_report() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["visible_manifestation_ids"] = [
            "forged_candidate_manifestation"
        ]

    outcome = evaluate_manual_case(
        _mutated_case("eval_interpretation_accurate", mutate)
    )

    assert outcome.exact_match is True
    assert outcome.semantic_result.passed is True


def test_ego_sequence_truth_is_not_copied_from_candidate() -> None:
    def mutate(payload: dict[str, object]) -> None:
        payload["candidate_payload"]["sequence_id"] = "sequence_candidate_tamper"

    outcome = evaluate_manual_case(
        _mutated_case("eval_ego_grounded_recurring_motif", mutate)
    )

    assert outcome.exact_match is False
    assert "ego_measure_scope_mismatch" in {
        item.issue_code for item in outcome.semantic_result.issues
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "projection_evidence",
        "projection_facets",
        "narrative_boundary",
    ],
)
def test_ego_candidate_evidence_facets_and_boundary_are_not_synthesized(
    mutation: str,
) -> None:
    def mutate(payload: dict[str, object]) -> None:
        candidate = payload["candidate_payload"]
        if mutation == "projection_evidence":
            candidate["projection_evidence"][0]["measure_ids"][0] = "measure_untrusted"
        elif mutation == "projection_facets":
            candidate["projection_facets"][1] = "E:wrong_facet"
        else:
            candidate["composition_artifact_ids"] = ["ego_self_narrative"]

    outcome = evaluate_manual_case(
        _mutated_case("eval_ego_grounded_recurring_motif", mutate)
    )

    assert outcome.exact_match is False
    raw_issues = {item.issue_code for item in outcome.semantic_result.issues}
    assert raw_issues & {
        "modality_projection_mismatch",
        "self_narrative_composition_conflation",
    }


def test_ego_empty_narrative_and_composition_sets_are_rejected() -> None:
    def mutate(payload: dict[str, object]) -> None:
        candidate = payload["candidate_payload"]
        candidate["self_narrative_artifact_ids"] = []
        candidate["composition_artifact_ids"] = []

    case = _mutated_case("eval_ego_grounded_recurring_motif", mutate)

    with pytest.raises(
        ValidationError,
        match="must explicitly identify self-narrative and composition",
    ):
        evaluate_manual_case(case)


def test_manifest_cannot_repoint_and_self_sign_policy(tmp_path: Path) -> None:
    copied_root = tmp_path / "repointed_manifest"
    shutil.copytree(DEFAULT_FIXTURE_ROOT, copied_root)
    manifest_path = copied_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["policy"]["path"] = "tests/fixtures/semantic_evaluation_v1/native_routes.jsonl"
    manifest["policy"]["sha256"] = _sha256(DEFAULT_FIXTURE_ROOT / "native_routes.jsonl")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValidationError, match="Input should be"):
        load_manual_fixture_manifest(copied_root)


def test_self_signed_small_manifest_is_not_an_official_fixture_set(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "small_manifest"
    shutil.copytree(DEFAULT_FIXTURE_ROOT, copied_root)
    manifest_path = copied_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["case_count"] = 1
    manifest["positive_case_count"] = 1
    manifest["negative_case_count"] = 0
    manifest["subject_counts"] = {"native_route": 1}
    manifest["files"] = [
        {
            "path": "native_routes.jsonl",
            "case_count": 1,
            "sha256": _sha256(copied_root / "native_routes.jsonl"),
        }
    ]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_manual_fixture_manifest(copied_root)
