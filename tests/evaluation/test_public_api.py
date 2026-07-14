from __future__ import annotations

import app.backend.rei.evaluation as evaluation


def test_public_api_exposes_models_evaluators_review_and_reporting() -> None:
    expected_symbols = {
        "InputExposureRecord",
        "NativeRouteEvaluationCase",
        "InterpretationEvaluationCase",
        "BilingualEvaluationCase",
        "EgoEvaluationCase",
        "evaluate_native_route",
        "evaluate_interpretation",
        "evaluate_bilingual_pair",
        "evaluate_ego_sequence",
        "commit_review_material",
        "BlindReviewLedger",
        "reviewer_agreement",
        "render_evaluation_report",
        "write_evaluation_report",
    }

    assert expected_symbols <= set(evaluation.__all__)
    assert all(hasattr(evaluation, symbol) for symbol in expected_symbols)
