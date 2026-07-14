"""Instinkt-specific protective-route checks."""

from __future__ import annotations

from collections.abc import Mapping

from .models import (
    CandidateNativeRoute,
    InputExposureRecord,
    NativeRouteEvaluationCase,
    SemanticEvaluationResult,
)
from .native_routes import boolean_metric, evaluate_native_route, extend_result, issue


INSTINKT_POLICY = "c2-instinkt-protective-route-policy-v1"
PROTECTIVE_FACETS = {
    "anticipated_loss",
    "attachment",
    "body_alarm",
    "body_readiness",
    "body_tension",
    "boundary",
    "boundary_protection",
    "boundary_violation",
    "escape_availability",
    "escape_available",
    "protected_target",
    "recoverability",
    "resource_security",
    "scarcity",
    "trust_uncertainty",
}


def evaluate_instinkt_route(
    *,
    case: NativeRouteEvaluationCase,
    candidate: CandidateNativeRoute,
    trusted_exposure: InputExposureRecord,
    terminology_policy: Mapping[str, str],
) -> SemanticEvaluationResult:
    result = evaluate_native_route(
        case=case,
        candidate=candidate,
        trusted_exposure=trusted_exposure,
        terminology_policy=terminology_policy,
    )
    expected_protective = set(case.expected_route_tags) & PROTECTIVE_FACETS
    protective_ok = expected_protective.issubset(candidate.route_tags)
    # Withdrawal/escape is never sufficient by itself; the expected structured
    # protective reason must also be present when the source route provides one.
    withdrawal_only = set(candidate.route_tags).issubset(
        {"withdrawal", "escape", "protective_exit"}
    )
    passed = candidate.mind == "I" and protective_ok and not withdrawal_only
    return extend_result(
        result,
        metrics=(
            boolean_metric(
                "instinkt_protective_route",
                "native_route_semantics",
                passed,
                "Instinkt is evaluated through structured danger/loss/body/boundary/recovery facets, not withdrawal alone.",
            ),
        ),
        issues=(
            ()
            if passed
            else (
                issue(
                    "instinkt_withdrawal_only_or_missing_protection",
                    "native_route_semantics",
                    "Instinkt lacks its canonical protective basis or is reduced to withdrawal.",
                ),
            )
        ),
        policies=(INSTINKT_POLICY,),
    )


__all__ = [
    "INSTINKT_POLICY",
    "PROTECTIVE_FACETS",
    "evaluate_instinkt_route",
]
