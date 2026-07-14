"""Shared structural and provenance evaluation for canonical native routes."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from ..ids import sha256_hex
from .models import (
    CandidateNativeRoute,
    EvaluationDimension,
    EvaluationIssue,
    EvaluationMetric,
    EvaluationResultContext,
    InputExposureRecord,
    NativeRouteEvaluationCase,
    SemanticEvaluationResult,
)


COMMON_ROUTE_POLICY = "c2-structured-native-route-policy-v1"
DEFAULT_TERMINOLOGY_POLICY = {
    "REI_RACIO": "Racio",
    "REI_EMOCIO": "Emocio",
    "REI_INSTINKT": "Instinkt",
}


def boolean_metric(
    metric_id: str,
    dimension: EvaluationDimension,
    passed: bool,
    detail: str,
    *,
    policy_id: str = COMMON_ROUTE_POLICY,
) -> EvaluationMetric:
    return EvaluationMetric(
        metric_id=metric_id,
        dimension=dimension,
        status="passed" if passed else "failed",
        policy_id=policy_id,
        value=passed,
        threshold=True,
        detail=detail,
    )


def numeric_metric(
    metric_id: str,
    dimension: EvaluationDimension,
    value: float | int,
    threshold: float | int,
    passed: bool,
    detail: str,
    *,
    policy_id: str = COMMON_ROUTE_POLICY,
) -> EvaluationMetric:
    return EvaluationMetric(
        metric_id=metric_id,
        dimension=dimension,
        status="passed" if passed else "failed",
        policy_id=policy_id,
        value=value,
        threshold=threshold,
        detail=detail,
    )


def not_applicable_metric(
    metric_id: str,
    dimension: EvaluationDimension,
    detail: str,
    *,
    policy_id: str = COMMON_ROUTE_POLICY,
) -> EvaluationMetric:
    return EvaluationMetric(
        metric_id=metric_id,
        dimension=dimension,
        status="not_applicable",
        policy_id=policy_id,
        value=None,
        threshold=None,
        detail=detail,
    )


def issue(
    issue_code: str,
    dimension: EvaluationDimension,
    detail: str,
    *,
    refs: Sequence[str] = (),
    severity: str = "error",
) -> EvaluationIssue:
    return EvaluationIssue(
        issue_code=issue_code,
        dimension=dimension,
        severity=severity,
        detail=detail,
        evidence_refs=tuple(refs),
    )


def _context(
    case: NativeRouteEvaluationCase,
    candidate: CandidateNativeRoute | None = None,
    trusted_exposure: InputExposureRecord | None = None,
    candidate_content_hash: str | None = None,
) -> EvaluationResultContext:
    return EvaluationResultContext(
        source_locator_refs=case.source_locator_refs,
        language=case.language,
        review_status="canon_approved",
        expected_route_ids=(case.expected_route_id,),
        actual_route_ids=(candidate.candidate_route_id,) if candidate else (),
        cognition_mode=(
            trusted_exposure.cognition_mode if trusted_exposure is not None else None
        ),
        candidate_content_hash=(
            candidate.content_hash()
            if candidate is not None
            else candidate_content_hash
        ),
        replay_artifact_ids=(
            (trusted_exposure.exposure_id,)
            if trusted_exposure is not None
            else ()
        ),
    )


def evaluate_native_route_payload(
    *,
    case: NativeRouteEvaluationCase,
    payload: Mapping[str, Any],
    trusted_exposure: InputExposureRecord,
    terminology_policy: Mapping[str, str] = DEFAULT_TERMINOLOGY_POLICY,
) -> SemanticEvaluationResult:
    """Evaluate raw output against a separately captured trusted input record."""

    try:
        candidate = CandidateNativeRoute.model_validate_json(
            json.dumps(payload, ensure_ascii=False)
        )
    except ValidationError as exc:
        metric = boolean_metric(
            "schema_validity",
            "schema_validity",
            False,
            "Candidate failed the strict C2 route schema.",
        )
        return SemanticEvaluationResult.create(
            subject_id=f"{case.case_id}__invalid_payload",
            subject_kind="native_route",
            family_id=case.family_id,
            variant_id=case.variant_id,
            mind=case.mind,
            expected_label="accurate",
            observed_label="invalid_schema",
            metrics=(metric,),
            issues=(
                issue(
                    "schema_invalid",
                    "schema_validity",
                    f"Candidate schema validation failed with {exc.error_count()} error(s).",
                ),
            ),
            evaluator_policies=(COMMON_ROUTE_POLICY,),
            evidence_artifact_ids=(trusted_exposure.exposure_id,),
            context=_context(
                case,
                trusted_exposure=trusted_exposure,
                candidate_content_hash=sha256_hex(payload),
            ),
        )
    return evaluate_native_route(
        case=case,
        candidate=candidate,
        trusted_exposure=trusted_exposure,
        terminology_policy=terminology_policy,
    )


def evaluate_native_route(
    *,
    case: NativeRouteEvaluationCase,
    candidate: CandidateNativeRoute,
    trusted_exposure: InputExposureRecord,
    terminology_policy: Mapping[str, str] = DEFAULT_TERMINOLOGY_POLICY,
) -> SemanticEvaluationResult:
    """Evaluate typed fields and lineage without keyword-searching candidate prose."""

    claim_evidence = {
        evidence_id for claim in candidate.claims for evidence_id in claim.evidence_ids
    }
    claim_observations = {
        observation_id
        for claim in candidate.claims
        for observation_id in claim.observation_ids
    }
    grounded = set(case.grounded_evidence_ids)
    allowed_observations = set(case.allowed_observation_ids)
    canonical_claims = set(case.canonical_claim_ids)

    def supported(claim: Any) -> bool:
        sources_ok = bool(claim.source_claim_ids) and set(
            claim.source_claim_ids
        ).issubset(canonical_claims)
        if claim.provenance_kind in {"supplied", "world_projection"}:
            return (
                sources_ok
                and bool(claim.evidence_ids)
                and set(claim.evidence_ids).issubset(grounded)
                and set(claim.evidence_ids).issubset(
                trusted_exposure.visible_evidence_ids
                )
            )
        if claim.provenance_kind == "visible_manifestation":
            return (
                sources_ok
                and bool(claim.observation_ids)
                and set(claim.observation_ids).issubset(allowed_observations)
                and set(claim.observation_ids).issubset(
                trusted_exposure.visible_observation_ids
                )
            )
        if claim.provenance_kind == "candidate_inference":
            refs = bool(claim.evidence_ids or claim.observation_ids)
            return (
                sources_ok
                and refs
                and set(claim.evidence_ids).issubset(grounded)
                and set(claim.evidence_ids).issubset(
                    trusted_exposure.visible_evidence_ids
                )
                and set(claim.observation_ids).issubset(allowed_observations)
                and set(claim.observation_ids).issubset(
                    trusted_exposure.visible_observation_ids
                )
            )
        return False

    unsupported_claim_ids = tuple(
        claim.claim_id
        for claim in candidate.claims
        if not supported(claim)
    )
    provenance_ok = bool(candidate.claims) and all(supported(claim) for claim in candidate.claims)
    exposure_binding_ok = trusted_exposure.subject_id == candidate.candidate_route_id
    actual_inputs = set(trusted_exposure.actual_input_artifact_ids)
    exposure_scope_ok = actual_inputs.issubset(trusted_exposure.allowed_artifact_ids)
    provenance_ok = provenance_ok and exposure_binding_ok and exposure_scope_ok

    evidence_coverage = (
        len(set(case.expected_evidence_ids) & claim_evidence)
        / len(case.expected_evidence_ids)
        if case.expected_evidence_ids
        else 1.0
    )
    evidence_ok = evidence_coverage == 1.0
    profile_refs = actual_inputs & set(trusted_exposure.profile_artifact_ids)
    hidden_refs = actual_inputs & (
        set(trusted_exposure.evaluator_truth_artifact_ids)
        | set(trusted_exposure.forbidden_artifact_ids)
    )
    profile_ok = not profile_refs
    hidden_ok = not hidden_refs

    semantic_ok = all(
        (
            candidate.family_id == case.family_id,
            candidate.variant_id == case.variant_id,
            candidate.mind == case.mind,
            set(case.expected_route_tags).issubset(candidate.route_tags),
            candidate.decisive_representation
            == case.expected_decisive_representation,
        )
    )
    abstention_ok = candidate.abstains == case.expected_abstention
    if case.expected_abstention:
        option_metric = not_applicable_metric(
            "allowed_option_validity",
            "allowed_option_validity",
            "Both canonical case and candidate abstain; option comparison is not applicable.",
        )
        option_semantic_ok = candidate.option_id is None
    else:
        option_semantic_ok = (
            candidate.option_id == case.expected_option_id
            and candidate.option_id in case.allowed_option_ids
            and candidate.option_id in trusted_exposure.visible_option_ids
        )
        option_metric = boolean_metric(
            "allowed_option_validity",
            "allowed_option_validity",
            option_semantic_ok,
            "Selected option matches canonical expectation and scene scope.",
        )
    semantic_ok = semantic_ok and option_semantic_ok

    terminology_by_id = {
        item.terminology_id: item for item in candidate.terminology_uses
    }
    terminology_ok = all(
        term_id in terminology_by_id
        and terminology_by_id[term_id].language == "sl"
        and terminology_by_id[term_id].surface_form == terminology_policy.get(term_id)
        for term_id in case.required_terminology_ids
    )

    core_correct = all(
        (
            provenance_ok,
            not unsupported_claim_ids,
            evidence_ok,
            profile_ok,
            hidden_ok,
            semantic_ok,
            abstention_ok,
            terminology_ok,
        )
    )
    brier = (candidate.confidence - (1.0 if core_correct else 0.0)) ** 2
    calibration_ok = brier <= case.calibration_max_brier

    metrics = (
        boolean_metric(
            "schema_validity",
            "schema_validity",
            True,
            "Candidate passed the strict C2 route schema.",
        ),
        boolean_metric(
            "provenance_completeness",
            "provenance_completeness",
            provenance_ok,
            "Every claim has trusted evidence/observation lineage and actual inputs stay in allowed scope.",
        ),
        option_metric,
        numeric_metric(
            "source_evidence_coverage",
            "source_evidence_coverage",
            evidence_coverage,
            1.0,
            evidence_ok,
            "Fraction of canonical route evidence represented by candidate claims.",
        ),
        numeric_metric(
            "unsupported_claim_count",
            "unsupported_claims",
            len(unsupported_claim_ids),
            0,
            not unsupported_claim_ids,
            "Claims are derived from trusted case claim IDs and supported lineage.",
        ),
        numeric_metric(
            "profile_leakage_count",
            "profile_leakage",
            len(profile_refs),
            0,
            profile_ok,
            "Actual input lineage intersects no profile artifact.",
        ),
        numeric_metric(
            "hidden_ground_truth_leakage_count",
            "hidden_ground_truth_leakage",
            len(hidden_refs),
            0,
            hidden_ok,
            "Actual input lineage intersects no evaluator-only or forbidden artifact.",
        ),
        numeric_metric(
            "confidence_brier",
            "confidence_calibration",
            brier,
            case.calibration_max_brier,
            calibration_ok,
            "Per-case Brier error under the versioned C2 calibration hypothesis.",
            policy_id="c2-per-case-brier-threshold-v1",
        ),
        boolean_metric(
            "abstention_correctness",
            "abstention_correctness",
            abstention_ok,
            "Candidate abstention matches the trusted case expectation.",
        ),
        boolean_metric(
            "slovenian_terminology",
            "slovenian_terminology",
            terminology_ok,
            "Required terminology IDs use exact canonical Slovene forms from the trusted policy.",
        ),
        boolean_metric(
            "native_route_semantics",
            "native_route_semantics",
            semantic_ok,
            "Mind, route facets, option and decisive representation match trusted structure.",
        ),
    )

    issues: list[EvaluationIssue] = []
    findings = (
        (
            provenance_ok,
            "incomplete_or_out_of_scope_provenance",
            "provenance_completeness",
            "Claim or input lineage is missing or outside trusted scope.",
            tuple(sorted(claim_evidence | claim_observations)),
        ),
        (
            option_semantic_ok,
            "invalid_option_id",
            "allowed_option_validity",
            "Candidate option differs from the canonical scoped option.",
            (candidate.option_id,) if candidate.option_id else (),
        ),
        (
            evidence_ok,
            "missing_source_evidence",
            "source_evidence_coverage",
            "Canonical route evidence is absent from candidate claims.",
            tuple(sorted(set(case.expected_evidence_ids) - claim_evidence)),
        ),
        (
            not unsupported_claim_ids,
            "unsupported_claim",
            "unsupported_claims",
            "Candidate contains unsupported claims.",
            unsupported_claim_ids,
        ),
        (
            profile_ok,
            "profile_leakage",
            "profile_leakage",
            "Actual provider/interpreter inputs expose profile artifacts.",
            tuple(sorted(profile_refs)),
        ),
        (
            hidden_ok,
            "hidden_ground_truth_leakage",
            "hidden_ground_truth_leakage",
            "Actual inputs expose evaluator-only native truth.",
            tuple(sorted(hidden_refs)),
        ),
        (
            calibration_ok,
            "miscalibrated_confidence",
            "confidence_calibration",
            "Confidence is incompatible with observed route correctness.",
            (),
        ),
        (
            abstention_ok,
            "incorrect_abstention",
            "abstention_correctness",
            "Candidate abstention differs from the trusted case.",
            (),
        ),
        (
            terminology_ok,
            "slovenian_terminology_mismatch",
            "slovenian_terminology",
            "Required canonical Slovene terminology is missing or altered.",
            case.required_terminology_ids,
        ),
        (
            semantic_ok,
            "native_route_mismatch",
            "native_route_semantics",
            "Structured route semantics differ from the canonical case.",
            (),
        ),
    )
    for passed, code, dimension, detail, refs in findings:
        if not passed:
            issues.append(issue(code, dimension, detail, refs=refs))

    return SemanticEvaluationResult.create(
        subject_id=candidate.candidate_route_id,
        subject_kind="native_route",
        family_id=case.family_id,
        variant_id=case.variant_id,
        mind=case.mind,
        expected_label="accurate",
        observed_label="accurate" if core_correct else "invalid",
        metrics=metrics,
        issues=tuple(issues),
        evaluator_policies=(
            COMMON_ROUTE_POLICY,
            "c2-per-case-brier-threshold-v1",
        ),
        evidence_artifact_ids=(trusted_exposure.exposure_id,),
        context=_context(case, candidate, trusted_exposure),
    )


def extend_result(
    result: SemanticEvaluationResult,
    *,
    metrics: Sequence[EvaluationMetric] = (),
    issues: Sequence[EvaluationIssue] = (),
    policies: Sequence[str] = (),
    observed_label: str | None = None,
) -> SemanticEvaluationResult:
    all_metrics = (*result.metrics, *metrics)
    all_issues = (*result.issues, *issues)
    return SemanticEvaluationResult.create(
        subject_id=result.subject_id,
        subject_kind=result.subject_kind,
        family_id=result.family_id,
        variant_id=result.variant_id,
        mind=result.mind,
        expected_label=result.expected_label,
        observed_label=observed_label or result.observed_label,
        metrics=tuple(all_metrics),
        issues=tuple(all_issues),
        evaluator_policies=(*result.evaluator_policies, *policies),
        evidence_artifact_ids=result.evidence_artifact_ids,
        context=result.context,
    )


__all__ = [
    "COMMON_ROUTE_POLICY",
    "DEFAULT_TERMINOLOGY_POLICY",
    "boolean_metric",
    "evaluate_native_route",
    "evaluate_native_route_payload",
    "extend_result",
    "issue",
    "not_applicable_metric",
    "numeric_metric",
]
