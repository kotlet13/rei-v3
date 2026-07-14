"""Racio-specific structured route checks."""

from __future__ import annotations

from collections.abc import Mapping

from .models import (
    CandidateNativeRoute,
    InputExposureRecord,
    NativeRouteEvaluationCase,
    SemanticEvaluationResult,
)
from .native_routes import boolean_metric, evaluate_native_route, extend_result, issue


RACIO_POLICY = "c2-racio-structured-reasoning-policy-v1"
FORBIDDEN_RACIO_FACETS = {
    "character_label",
    "ei_motive_invention",
    "moral_judgment",
    "status_assumption",
}


def evaluate_racio_route(
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
    forbidden = tuple(sorted(set(candidate.route_tags) & FORBIDDEN_RACIO_FACETS))
    passed = candidate.mind == "R" and not forbidden
    return extend_result(
        result,
        metrics=(
            boolean_metric(
                "racio_fact_rule_route",
                "native_route_semantics",
                passed,
                "Racio route uses explicit structured facets without character, moral, status or invented E/I motives.",
            ),
        ),
        issues=(
            ()
            if passed
            else (
                issue(
                    "racio_forbidden_reasoning_shortcut",
                    "native_route_semantics",
                    "Racio route uses a forbidden shortcut or the wrong mind identity.",
                    refs=forbidden,
                ),
            )
        ),
        policies=(RACIO_POLICY,),
    )


__all__ = ["FORBIDDEN_RACIO_FACETS", "RACIO_POLICY", "evaluate_racio_route"]
