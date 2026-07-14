from __future__ import annotations

import json

from app.backend.rei.evaluation.models import CandidateNativeRoute, InputExposureRecord
from app.backend.rei.evaluation.native_routes import evaluate_native_route_payload

from conftest import TERMINOLOGY_POLICY


def _rebuild(candidate, mutate):
    payload = candidate.model_dump(mode="json")
    mutate(payload)
    return CandidateNativeRoute.model_validate_json(json.dumps(payload, ensure_ascii=False))


def _rebuild_exposure(exposure, mutate):
    payload = exposure.model_dump(
        mode="json", exclude={"schema_version", "exposure_id"}
    )
    mutate(payload)
    return InputExposureRecord.create(**payload)


def test_all_304_canonical_routes_pass_structured_domain_evaluation(
    canonical_route_records,
):
    results = [
        evaluator(
            case=case,
            candidate=candidate,
            trusted_exposure=exposure,
            terminology_policy=TERMINOLOGY_POLICY,
        )
        for case, candidate, exposure, evaluator in canonical_route_records
    ]
    assert len(results) == 304
    assert all(result.passed for result in results)
    assert all(result.evaluator_model_calls == 0 for result in results)


def test_raw_schema_failure_is_reported_instead_of_raising(canonical_route_records):
    case, candidate, exposure, _ = canonical_route_records[0]
    payload = candidate.model_dump(mode="json")
    del payload["route_tags"]
    result = evaluate_native_route_payload(
        case=case,
        payload=payload,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert not result.passed
    assert result.observed_label == "invalid_schema"
    assert {item.issue_code for item in result.issues} == {"schema_invalid"}


def test_raw_candidate_cannot_self_report_its_input_exposure(
    canonical_route_records,
):
    case, candidate, exposure, _ = canonical_route_records[0]
    payload = candidate.model_dump(mode="json")
    payload["exposure"] = exposure.model_dump(mode="json")
    result = evaluate_native_route_payload(
        case=case,
        payload=payload,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert not result.passed
    assert result.observed_label == "invalid_schema"
    assert {item.issue_code for item in result.issues} == {"schema_invalid"}


def test_profile_and_hidden_truth_leakage_use_trusted_exposure_lineage(
    canonical_route_records,
):
    case, candidate, exposure, evaluator = canonical_route_records[0]

    def leak(payload):
        profile_id = "profile_artifact_secret"
        truth_id = "native_truth_secret"
        payload["actual_input_artifact_ids"] += [profile_id, truth_id]
        payload["allowed_artifact_ids"] += [profile_id, truth_id]
        payload["profile_artifact_ids"] = [profile_id]
        payload["evaluator_truth_artifact_ids"] = [truth_id]

    leaked = _rebuild_exposure(exposure, leak)
    result = evaluator(
        case=case,
        candidate=candidate,
        trusted_exposure=leaked,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    codes = {item.issue_code for item in result.issues}
    assert not result.passed
    assert "profile_leakage" in codes
    assert "hidden_ground_truth_leakage" in codes


def test_trusted_exposure_must_be_bound_to_the_evaluated_subject(
    canonical_route_records,
):
    case, candidate, exposure, evaluator = canonical_route_records[0]
    mismatched = _rebuild_exposure(
        exposure,
        lambda payload: payload.update({"subject_id": "different_candidate"}),
    )
    result = evaluator(
        case=case,
        candidate=candidate,
        trusted_exposure=mismatched,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert not result.passed
    assert "incomplete_or_out_of_scope_provenance" in {
        item.issue_code for item in result.issues
    }


def test_result_binds_the_exact_candidate_payload(canonical_route_records):
    case, candidate, exposure, evaluator = canonical_route_records[0]
    changed = _rebuild(
        candidate,
        lambda payload: payload.update(
            {"uncertainty": "Drugačen, a še vedno veljaven zapis negotovosti."}
        ),
    )
    original_result = evaluator(
        case=case,
        candidate=candidate,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    changed_result = evaluator(
        case=case,
        candidate=changed,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert original_result.metrics == changed_result.metrics
    assert (
        original_result.context.candidate_content_hash
        != changed_result.context.candidate_content_hash
    )
    assert original_result.result_id != changed_result.result_id


def test_missing_evidence_and_unsupported_claim_are_detected(canonical_route_records):
    case, candidate, exposure, evaluator = canonical_route_records[0]

    def corrupt(payload):
        payload["claims"][0]["source_claim_ids"] = ["C-UNSUPPORTED-999"]
        payload["claims"][0]["evidence_ids"] = []

    corrupted = _rebuild(candidate, corrupt)
    result = evaluator(
        case=case,
        candidate=corrupted,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    codes = {item.issue_code for item in result.issues}
    assert "unsupported_claim" in codes
    assert "missing_source_evidence" in codes
    assert "incomplete_or_out_of_scope_provenance" in codes


def test_wrong_but_allowed_option_is_a_semantic_failure(canonical_route_records):
    case, candidate, exposure, evaluator = next(
        record
        for record in canonical_route_records
        if len(record[0].allowed_option_ids) > 1 and not record[0].expected_abstention
    )
    wrong_option = next(
        option for option in case.allowed_option_ids if option != case.expected_option_id
    )
    corrupted = _rebuild(
        candidate,
        lambda payload: payload.update({"option_id": wrong_option}),
    )
    result = evaluator(
        case=case,
        candidate=corrupted,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert "invalid_option_id" in {item.issue_code for item in result.issues}
    assert "native_route_mismatch" in {item.issue_code for item in result.issues}
