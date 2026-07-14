from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.backend.rei.evaluation.models import (
    EvaluationMetric,
    InputExposureRecord,
    SemanticEvaluationRun,
)


def test_metric_supports_not_applicable_and_thresholded_values():
    not_applicable = EvaluationMetric(
        metric_id="option_comparison",
        dimension="allowed_option_validity",
        status="not_applicable",
        policy_id="test-policy-v1",
        value=None,
        detail="Two null options do not prove semantic agreement.",
    )
    thresholded = EvaluationMetric(
        metric_id="motif_precision",
        dimension="longitudinal_motif_precision",
        status="passed",
        policy_id="test-policy-v1",
        value=0.9,
        threshold=0.8,
        detail="Precision exceeds the reviewed threshold.",
    )
    assert not_applicable.passed
    assert thresholded.passed


def test_run_contract_has_no_aggregate_rei_score():
    fields = set(SemanticEvaluationRun.model_fields)
    assert "score" not in fields
    assert "rei_score" not in fields
    assert "aggregate_score" not in fields
    assert "evaluator_model_calls" in fields


def test_trusted_input_exposure_is_content_addressed():
    exposure = InputExposureRecord.create(
        subject_id="candidate_1",
        allowed_artifact_ids=("scene_1",),
        actual_input_artifact_ids=("scene_1",),
    )
    payload = exposure.model_dump(mode="python")
    payload["actual_input_artifact_ids"] = ("scene_2",)
    with pytest.raises(ValidationError, match="canonical content"):
        InputExposureRecord.model_validate(payload)
