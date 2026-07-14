"""Emocio-specific scene and renderer-boundary checks."""

from __future__ import annotations

from collections.abc import Mapping

from .models import (
    CandidateNativeRoute,
    InputExposureRecord,
    NativeRouteEvaluationCase,
    SemanticEvaluationResult,
)
from .native_routes import boolean_metric, evaluate_native_route, extend_result, issue


EMOCIO_POLICY = "c2-emocio-scene-route-policy-v1"
SCENE_FACETS = {
    "current_scene",
    "desired_scene",
    "broken_scene",
    "scene_transformation",
    "internal_image",
    "motor_pattern",
}


def evaluate_emocio_route(
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
    expected_tags = set(case.expected_route_tags)
    required_scene_facets = expected_tags & SCENE_FACETS
    scene_ok = required_scene_facets.issubset(candidate.route_tags)
    renderer_refs = tuple(
        claim.claim_id
        for claim in candidate.claims
        if claim.provenance_kind == "renderer_added_ungrounded"
    )
    renderer_ok = not renderer_refs
    passed = candidate.mind == "E" and scene_ok and renderer_ok
    return extend_result(
        result,
        metrics=(
            boolean_metric(
                "emocio_scene_and_renderer_boundary",
                "native_route_semantics",
                passed,
                "Emocio preserves canonical scene/motor facets and never promotes renderer additions to grounded facts.",
            ),
        ),
        issues=(
            ()
            if passed
            else (
                issue(
                    "emocio_scene_or_renderer_boundary_failure",
                    "native_route_semantics",
                    "Emocio scene facets are missing, the mind is wrong, or renderer-only material was treated as fact.",
                    refs=renderer_refs,
                ),
            )
        ),
        policies=(EMOCIO_POLICY,),
    )


__all__ = ["EMOCIO_POLICY", "SCENE_FACETS", "evaluate_emocio_route"]
