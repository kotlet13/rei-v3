from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.backend.rei.evaluation.ego_eval import evaluate_ego_sequence
from app.backend.rei.evaluation.models import (
    EgoEvaluationCase,
    EgoEvaluationSample,
    EgoMotifCandidate,
)


def _case_and_candidate():
    case = EgoEvaluationCase(
        case_id="ego_case",
        sequence_id="sequence_1",
        measure_ids=("measure_1", "measure_2", "measure_3"),
        expected_motif_ids=("motif_boundary",),
        expected_translation_gap_ids=("gap_1",),
        expected_unresolved_tension_ids=("tension_1",),
        expected_projection_facets=(
            "R:chronology",
            "E:recurring_scenes",
            "I:boundary_patterns",
        ),
    )
    candidate = EgoEvaluationSample(
        sample_id="ego_candidate",
        sequence_id="sequence_1",
        measure_ids=case.measure_ids,
        motifs=(
            EgoMotifCandidate(
                motif_id="motif_boundary",
                motif_kind="conflict",
                supporting_measure_ids=("measure_1", "measure_3"),
            ),
        ),
        recurring_translation_gap_ids=("gap_1",),
        unresolved_tension_ids=("tension_1",),
        projection_evidence=(
            ("R", ("measure_1",)),
            ("E", ("measure_2",)),
            ("I", ("measure_3",)),
        ),
        projection_facets=case.expected_projection_facets,
        self_narrative_artifact_ids=("narrative_1",),
        composition_artifact_ids=("composition_1",),
    )
    return case, candidate


def test_ego_evaluator_preserves_motif_and_projection_provenance():
    case, candidate = _case_and_candidate()
    result = evaluate_ego_sequence(case=case, candidate=candidate)
    assert result.passed
    assert result.context.measure_ids == case.measure_ids


def test_ego_evaluator_detects_false_motif_and_narrative_conflation():
    case, candidate = _case_and_candidate()
    corrupted = candidate.model_copy(
        update={
            "motifs": (
                *candidate.motifs,
                EgoMotifCandidate(
                    motif_id="false_motif",
                    motif_kind="identity",
                    supporting_measure_ids=("measure_1", "measure_2"),
                ),
            ),
            "self_narrative_artifact_ids": ("composition_1",),
        }
    )
    result = evaluate_ego_sequence(case=case, candidate=corrupted)
    assert not result.passed
    codes = {item.issue_code for item in result.issues}
    assert "false_motif" in codes
    assert "self_narrative_composition_conflation" in codes


def test_ego_evaluator_rejects_candidate_projection_facet_mutation():
    case, candidate = _case_and_candidate()
    corrupted = candidate.model_copy(
        update={
            "projection_facets": (
                "R:chronology",
                "E:chronology",
                "I:boundary_patterns",
            )
        }
    )

    result = evaluate_ego_sequence(case=case, candidate=corrupted)

    assert not result.passed
    assert "modality_projection_mismatch" in {
        item.issue_code for item in result.issues
    }
    metrics = {metric.metric_id: metric for metric in result.metrics}
    assert metrics["ego_modality_projection_evidence"].passed
    assert not metrics["ego_modality_projection_facets"].passed


def test_ego_evaluator_rejects_missing_projection_mind_even_with_valid_measures():
    case, candidate = _case_and_candidate()
    corrupted = candidate.model_copy(
        update={
            "projection_evidence": (
                ("R", ("measure_1",)),
                ("E", ("measure_2",)),
            ),
            "projection_facets": (
                "R:chronology",
                "E:recurring_scenes",
            ),
        }
    )

    result = evaluate_ego_sequence(case=case, candidate=corrupted)

    assert not result.passed
    assert "modality_projection_mismatch" in {
        item.issue_code for item in result.issues
    }


@pytest.mark.parametrize(
    ("model_type", "payload_field"),
    (
        (EgoEvaluationCase, "expected_projection_facets"),
        (EgoEvaluationSample, "projection_facets"),
        (EgoEvaluationSample, "self_narrative_artifact_ids"),
        (EgoEvaluationSample, "composition_artifact_ids"),
    ),
)
def test_ego_contract_requires_explicit_trusted_and_candidate_boundary_fields(
    model_type, payload_field
):
    case, candidate = _case_and_candidate()
    source = case if model_type is EgoEvaluationCase else candidate
    payload = source.model_dump(mode="python", round_trip=True)
    payload.pop(payload_field)

    with pytest.raises(ValidationError):
        model_type.model_validate(payload)
