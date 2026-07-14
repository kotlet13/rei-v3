from __future__ import annotations

from app.backend.rei.evaluation.bilingual_eval import evaluate_bilingual_pair
from app.backend.rei.evaluation.models import (
    BilingualCandidatePair,
    BilingualEvaluationCase,
    TerminologyUse,
    TrustedSemanticSignature,
)


def _case_and_pair():
    signature = TrustedSemanticSignature(
        concept_ids=("concept_native_route",),
        route_ids=("route_R", "route_E", "route_I"),
        option_ids=("option_continue",),
    )
    case = BilingualEvaluationCase(
        case_id="bilingual_case",
        family_id="sf_bilingual",
        trusted_signature=signature,
        required_terminology_ids=("REI_RACIO", "REI_EMOCIO"),
    )
    pair = BilingualCandidatePair(
        pair_id="bilingual_pair",
        family_id="sf_bilingual",
        sl_variant_id="sl_variant",
        en_variant_id="en_variant",
        sl_text="Racio razlaga Emocievo manifestacijo.",
        en_text="Racio interprets Emocio's manifestation.",
        sl_signature=signature,
        en_signature=signature,
        terminology_uses=(
            TerminologyUse(
                terminology_id="REI_RACIO", language="sl", surface_form="Racio"
            ),
            TerminologyUse(
                terminology_id="REI_RACIO", language="en", surface_form="Racio"
            ),
            TerminologyUse(
                terminology_id="REI_EMOCIO", language="sl", surface_form="Emocio"
            ),
            TerminologyUse(
                terminology_id="REI_EMOCIO", language="en", surface_form="Emocio"
            ),
        ),
    )
    policy = {
        "REI_RACIO": ("Racio", "Racio"),
        "REI_EMOCIO": ("Emocio", "Emocio"),
    }
    return case, pair, policy


def test_bilingual_evaluator_uses_trusted_structured_signature():
    case, pair, policy = _case_and_pair()
    result = evaluate_bilingual_pair(
        case=case, candidate=pair, terminology_policy=policy
    )
    assert result.passed
    assert result.observed_label == "consistent"


def test_bilingual_evaluator_detects_semantic_drift_without_keyword_scoring():
    case, pair, policy = _case_and_pair()
    drifted_signature = pair.en_signature.model_copy(
        update={"option_ids": ("option_withdraw",)}
    )
    drifted = pair.model_copy(update={"en_signature": drifted_signature})
    result = evaluate_bilingual_pair(
        case=case, candidate=drifted, terminology_policy=policy
    )
    assert not result.passed
    assert "cross_language_semantic_mismatch" in {
        item.issue_code for item in result.issues
    }


def test_bilingual_evaluator_rejects_candidate_from_another_family():
    case, pair, policy = _case_and_pair()
    wrong_family = pair.model_copy(update={"family_id": "sf_other_family"})

    result = evaluate_bilingual_pair(
        case=case,
        candidate=wrong_family,
        terminology_policy=policy,
    )

    assert not result.passed
    assert any(
        metric.metric_id == "bilingual_family_binding"
        and metric.status == "failed"
        for metric in result.metrics
    )
    assert "bilingual_family_mismatch" in {
        item.issue_code for item in result.issues
    }
