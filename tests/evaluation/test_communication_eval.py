from __future__ import annotations

import json

from app.backend.rei.evaluation.communication_eval import (
    evaluate_interpretation,
    evaluate_interpretation_payload,
)
from app.backend.rei.evaluation.models import (
    CandidateInterpretation,
    InputExposureRecord,
    InterpretationDistortionEvidence,
    InterpretationEvaluationCase,
)


def _rebuild(candidate, mutate):
    payload = candidate.model_dump(mode="json")
    mutate(payload)
    return CandidateInterpretation.model_validate_json(
        json.dumps(payload, ensure_ascii=False)
    )


def _rebuild_exposure(exposure, mutate):
    payload = exposure.model_dump(
        mode="json", exclude={"schema_version", "exposure_id"}
    )
    mutate(payload)
    return InputExposureRecord.create(**payload)


def test_all_192_c1_interpretations_match_reviewed_classes(
    canonical_interpretation_records,
):
    results = [
        evaluate_interpretation(
            case=case,
            candidate=candidate,
            trusted_exposure=exposure,
        )
        for case, candidate, exposure in canonical_interpretation_records
    ]
    assert len(results) == 192
    assert sum(result.passed for result in results) == 144
    assert all(
        result.passed == (result.observed_label == "accurate")
        for result in results
    )
    assert {result.observed_label for result in results} == {
        "accurate",
        "partial",
        "unknown",
    }


def test_rationalization_is_distinguished_from_accurate_interpretation(
    canonical_interpretation_records,
):
    base_case, candidate, exposure = next(
        record
        for record in canonical_interpretation_records
        if record[0].expected_interpretation_class == "accurate"
    )
    case = InterpretationEvaluationCase.model_validate(
        base_case.model_copy(
            update={
                "expected_interpretation_class": "rationalization",
                "distortion_evidence": InterpretationDistortionEvidence(
                    evidence_kind="self_justification_without_visible_support",
                    visible_support_ids=base_case.visible_observation_ids,
                    candidate_claim_ids=(candidate.claims[0].claim_id,),
                    contradicted_claim_ids=(candidate.claims[0].claim_id,),
                    expected_label="rationalization",
                ),
            }
        )
    )

    def rationalize(payload):
        payload["reasoning_operation"] = "self_justify"
        payload["justification_kind"] = "self_justification"
        payload["inferred_motive_class"] = "self_protective_story"
        payload["confidence"] = 0.2
        payload["alternative_hypotheses"] = ["Vidni signal podpira drugo razlago."]

    rationalized = _rebuild(candidate, rationalize)
    result = evaluate_interpretation(
        case=case,
        candidate=rationalized,
        trusted_exposure=exposure,
    )
    assert not result.passed
    assert result.observed_label == "rationalization"
    assert "rationalization_detected" in {item.issue_code for item in result.issues}


def test_hidden_truth_leakage_is_computed_from_actual_input_lineage(
    canonical_interpretation_records,
):
    case, candidate, exposure = canonical_interpretation_records[0]

    def leak(payload):
        truth_id = case.evaluator_truth_artifact_ids[0]
        payload["actual_input_artifact_ids"].append(truth_id)
        payload["allowed_artifact_ids"].append(truth_id)

    leaked = _rebuild_exposure(exposure, leak)
    result = evaluate_interpretation(
        case=case,
        candidate=candidate,
        trusted_exposure=leaked,
    )
    assert not result.passed
    assert "hidden_ground_truth_leakage" in {
        item.issue_code for item in result.issues
    }


def test_invalid_interpretation_payload_becomes_schema_failure(
    canonical_interpretation_records,
):
    case, candidate, exposure = canonical_interpretation_records[0]
    payload = candidate.model_dump(mode="json")
    del payload["reasoning_operation"]
    result = evaluate_interpretation_payload(
        case=case,
        payload=payload,
        trusted_exposure=exposure,
    )
    assert not result.passed
    assert result.observed_label == "invalid_schema"


def test_wrong_identity_empty_claims_and_empty_exposure_cannot_pass(
    canonical_interpretation_records,
):
    case, candidate, exposure = next(
        record
        for record in canonical_interpretation_records
        if record[0].expected_interpretation_class == "accurate"
    )
    corrupted = _rebuild(
        candidate,
        lambda payload: payload.update(
            {
                "family_id": "wrong_family",
                "variant_id": "wrong_variant",
                "source_mind": "I" if case.source_mind == "E" else "E",
                "claims": [],
                "cited_observation_ids": [],
            }
        ),
    )
    empty_exposure = _rebuild_exposure(
        exposure,
        lambda payload: payload.update(
            {
                "allowed_artifact_ids": [],
                "actual_input_artifact_ids": [],
                "visible_observation_ids": [],
            }
        ),
    )
    result = evaluate_interpretation(
        case=case,
        candidate=corrupted,
        trusted_exposure=empty_exposure,
    )
    assert not result.passed
    codes = {item.issue_code for item in result.issues}
    assert "interpretation_identity_mismatch" in codes
    assert "incomplete_or_out_of_scope_provenance" in codes


def test_unknown_operation_cannot_hide_non_null_inferences_behind_na(
    canonical_interpretation_records,
):
    case, candidate, exposure = next(
        record
        for record in canonical_interpretation_records
        if record[0].expected_interpretation_class == "unknown"
    )
    corrupted = _rebuild(
        candidate,
        lambda payload: payload.update(
            {
                "inferred_option_id": "hallucinated_option",
                "inferred_motive_class": "hallucinated_motive",
                "inferred_action_tendency": "hallucinated_action",
            }
        ),
    )
    result = evaluate_interpretation(
        case=case,
        candidate=corrupted,
        trusted_exposure=exposure,
    )
    assert result.observed_label == "unknown"
    assert not result.passed
    codes = {item.issue_code for item in result.issues}
    assert "reasoning_operation_inconsistent" in codes
    assert "option_misclassification" in codes


def test_candidate_operation_cannot_override_trusted_distortion_evidence(
    canonical_interpretation_records,
):
    case, candidate, exposure = next(
        record
        for record in canonical_interpretation_records
        if record[0].expected_interpretation_class == "accurate"
    )
    self_labeled = _rebuild(
        candidate,
        lambda payload: payload.update(
            {
                "reasoning_operation": "self_justify",
                "justification_kind": "self_justification",
            }
        ),
    )
    result = evaluate_interpretation(
        case=case,
        candidate=self_labeled,
        trusted_exposure=exposure,
    )
    assert result.observed_label == "accurate"
    assert not result.passed
    assert "reasoning_operation_inconsistent" in {
        item.issue_code for item in result.issues
    }
