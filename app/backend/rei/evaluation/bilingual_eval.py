"""Structured Slovene/English consistency checks with trusted signatures."""

from __future__ import annotations

from collections.abc import Mapping

from .models import (
    BilingualCandidatePair,
    BilingualEvaluationCase,
    EvaluationResultContext,
    SemanticEvaluationResult,
)
from .native_routes import boolean_metric, issue


BILINGUAL_POLICY = "c2-trusted-structured-bilingual-policy-v1"


def evaluate_bilingual_pair(
    *,
    case: BilingualEvaluationCase,
    candidate: BilingualCandidatePair,
    terminology_policy: Mapping[str, tuple[str, str]],
) -> SemanticEvaluationResult:
    family_ok = candidate.family_id == case.family_id
    sl_ok = candidate.sl_signature == case.trusted_signature
    en_ok = candidate.en_signature == case.trusted_signature
    cross_ok = candidate.sl_signature == candidate.en_signature
    uses = {(item.terminology_id, item.language): item.surface_form for item in candidate.terminology_uses}
    terminology_ok = all(
        term_id in terminology_policy
        and uses.get((term_id, "sl")) == terminology_policy[term_id][0]
        and uses.get((term_id, "en")) == terminology_policy[term_id][1]
        for term_id in case.required_terminology_ids
    )
    metrics = (
        boolean_metric(
            "bilingual_family_binding",
            "bilingual_consistency",
            family_ok,
            "Candidate pair family matches the trusted bilingual case.",
            policy_id=BILINGUAL_POLICY,
        ),
        boolean_metric(
            "sl_semantic_signature",
            "bilingual_consistency",
            sl_ok,
            "Slovene structured signature matches trusted evaluator truth.",
            policy_id=BILINGUAL_POLICY,
        ),
        boolean_metric(
            "en_semantic_signature",
            "bilingual_consistency",
            en_ok,
            "English operational-gloss signature matches trusted evaluator truth.",
            policy_id=BILINGUAL_POLICY,
        ),
        boolean_metric(
            "cross_language_signature",
            "bilingual_consistency",
            cross_ok,
            "Slovene and English structured signatures are identical.",
            policy_id=BILINGUAL_POLICY,
        ),
        boolean_metric(
            "bilingual_terminology",
            "slovenian_terminology",
            terminology_ok,
            "Reviewed terminology pairs use canonical Slovene and operational English forms.",
            policy_id=BILINGUAL_POLICY,
        ),
    )
    issues = []
    for passed, code, dimension in (
        (family_ok, "bilingual_family_mismatch", "bilingual_consistency"),
        (sl_ok, "sl_signature_mismatch", "bilingual_consistency"),
        (en_ok, "en_signature_mismatch", "bilingual_consistency"),
        (cross_ok, "cross_language_semantic_mismatch", "bilingual_consistency"),
        (terminology_ok, "bilingual_terminology_mismatch", "slovenian_terminology"),
    ):
        if not passed:
            issues.append(
                issue(
                    code,
                    dimension,
                    f"Bilingual evaluation failed: {code}.",
                )
            )
    passed = all(metric.passed for metric in metrics)
    return SemanticEvaluationResult.create(
        subject_id=candidate.pair_id,
        subject_kind="bilingual_pair",
        family_id=case.family_id,
        expected_label="consistent",
        observed_label="consistent" if passed else "inconsistent",
        metrics=metrics,
        issues=tuple(issues),
        evaluator_policies=(BILINGUAL_POLICY,),
        context=EvaluationResultContext(
            language="sl",
            review_status="canon_approved",
            actual_route_ids=candidate.sl_signature.route_ids,
            candidate_content_hash=candidate.content_hash(),
        ),
    )


__all__ = ["BILINGUAL_POLICY", "evaluate_bilingual_pair"]
