from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.backend.rei.evaluation.models import (
    CandidateClaim,
    CandidateInterpretation,
    CandidateNativeRoute,
    InputExposureRecord,
    InterpretationDistortionEvidence,
    InterpretationEvaluationCase,
    NativeRouteEvaluationCase,
    TerminologyUse,
)
from app.backend.rei.evaluation.racio_eval import evaluate_racio_route
from app.backend.rei.evaluation.emocio_eval import evaluate_emocio_route
from app.backend.rei.evaluation.instinkt_eval import evaluate_instinkt_route


REPO_ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "semantic_lab_v1"
MIND_TERMS = {
    "R": ("REI_RACIO", "Racio"),
    "E": ("REI_EMOCIO", "Emocio"),
    "I": ("REI_INSTINKT", "Instinkt"),
}
TERMINOLOGY_POLICY = {term_id: value for term_id, value in MIND_TERMS.values()}
ROUTE_EVALUATORS = {
    "R": evaluate_racio_route,
    "E": evaluate_emocio_route,
    "I": evaluate_instinkt_route,
}


def load_semantic_fixtures():
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SEMANTIC_FIXTURES.glob("sf_*.json"))
    ]


def make_route_case_candidate(family, variant, route):
    evidence_ids = tuple(
        item["evidence_id"] for item in family["grounded_scene"]["evidence"]
    )
    option_ids = tuple(
        item["option_id"] for item in family["grounded_scene"]["options"]
    )
    source_claim_ids = tuple(
        dict.fromkeys(
            claim_id
            for locator in family["source_locators"]
            for claim_id in locator["claim_ids"]
        )
    )
    source_locator_refs = tuple(
        f"{family['family_id']}__source_{index}"
        for index, _ in enumerate(family["source_locators"], start=1)
    )
    term_id, surface = MIND_TERMS[route["mind"]]
    candidate_id = f"{route['route_id']}__candidate"
    case = NativeRouteEvaluationCase(
        case_id=f"{route['route_id']}__case",
        family_id=family["family_id"],
        variant_id=variant["variant_id"],
        expected_route_id=route["route_id"],
        mind=route["mind"],
        allowed_option_ids=option_ids,
        grounded_evidence_ids=evidence_ids,
        canonical_claim_ids=source_claim_ids,
        expected_evidence_ids=tuple(route["evidence_ids"]),
        expected_route_tags=tuple(route["route_tags"]),
        expected_option_id=route["option_id"],
        expected_decisive_representation=route["decisive_representation"],
        expected_abstention=route["option_id"] is None,
        required_terminology_ids=(term_id,),
        source_locator_refs=source_locator_refs,
        language=variant["language"],
    )
    exposure = InputExposureRecord.create(
        subject_id=candidate_id,
        allowed_artifact_ids=evidence_ids,
        actual_input_artifact_ids=tuple(route["evidence_ids"]),
        visible_evidence_ids=evidence_ids,
        visible_option_ids=option_ids,
    )
    candidate = CandidateNativeRoute(
        candidate_route_id=candidate_id,
        family_id=family["family_id"],
        variant_id=variant["variant_id"],
        mind=route["mind"],
        claims=(
            CandidateClaim(
                claim_id=f"{candidate_id}__claim",
                facet=route["route_tags"][0],
                value=route["decisive_representation"],
                source_claim_ids=source_claim_ids,
                evidence_ids=tuple(route["evidence_ids"]),
                provenance_kind="supplied",
            ),
        ),
        route_tags=tuple(route["route_tags"]),
        option_id=route["option_id"],
        decisive_representation=route["decisive_representation"],
        short_decision_bridge_sl=route["short_decision_bridge_sl"],
        terminology_uses=(
            TerminologyUse(
                terminology_id=term_id,
                language="sl",
                surface_form=surface,
            ),
        ),
        confidence=0.9 if route["option_id"] is not None else 0.1,
        abstains=route["option_id"] is None,
        uncertainty="Negotovost je izrecno omejena na navedene neznanke.",
    )
    return case, candidate, exposure, ROUTE_EVALUATORS[route["mind"]]


def make_interpretation_case_candidate(family, variant, expected):
    source_claim_ids = tuple(
        dict.fromkeys(
            claim_id
            for locator in family["source_locators"]
            for claim_id in locator["claim_ids"]
        )
    )
    option_ids = tuple(
        item["option_id"] for item in family["grounded_scene"]["options"]
    )
    visible = tuple(expected["visible_manifestation_ids"])
    candidate_id = f"{expected['interpretation_id']}__candidate"
    expected_class = expected["expected_interpretation_class"]
    operation = {
        "accurate": "direct_inference",
        "partial": "alternative_hypothesis",
        "unknown": "insufficient_information",
    }[expected_class]
    evidence_kind = {
        "accurate": "supported_visible_match",
        "partial": "supported_facet_with_explicit_omission",
        "unknown": "insufficient_evidence_for_specific_label",
    }[expected_class]
    evidence_claim_ids = (
        () if expected_class == "unknown" else (f"{candidate_id}__claim",)
    )
    case = InterpretationEvaluationCase(
        case_id=f"{expected['interpretation_id']}__case",
        family_id=family["family_id"],
        variant_id=variant["variant_id"],
        source_mind=expected["source_mind"],
        visible_manifestation_ids=visible,
        visible_observation_ids=visible,
        allowed_option_ids=option_ids,
        canonical_claim_ids=source_claim_ids,
        expected_option_id=expected["expected_option_id"],
        expected_motive_class=expected["expected_motive_class"],
        expected_interpretation_class=expected_class,
        distortion_evidence=InterpretationDistortionEvidence(
            evidence_kind=evidence_kind,
            visible_support_ids=visible,
            candidate_claim_ids=evidence_claim_ids,
            contradicted_claim_ids=(),
            expected_label=expected_class,
        ),
        evaluator_truth_artifact_ids=(
            f"{expected['interpretation_id']}__native_truth",
        ),
    )
    exposure = InputExposureRecord.create(
        subject_id=candidate_id,
        allowed_artifact_ids=visible,
        actual_input_artifact_ids=visible,
        visible_observation_ids=visible,
        visible_option_ids=option_ids,
        evaluator_truth_artifact_ids=case.evaluator_truth_artifact_ids,
    )
    if expected_class == "unknown":
        claims = ()
        inferred_option = None
        inferred_motive = None
    else:
        claims = (
            CandidateClaim(
                claim_id=f"{candidate_id}__claim",
                facet="visible_signal",
                value="Strukturirana vidna manifestacija.",
                source_claim_ids=source_claim_ids,
                observation_ids=visible,
                provenance_kind="visible_manifestation",
            ),
        )
        inferred_option = expected["expected_option_id"]
        inferred_motive = expected["expected_motive_class"]
    candidate = CandidateInterpretation(
        candidate_interpretation_id=candidate_id,
        family_id=family["family_id"],
        variant_id=variant["variant_id"],
        source_mind=expected["source_mind"],
        claims=claims,
        cited_observation_ids=visible,
        route_tags=(inferred_motive,) if inferred_motive else ("uncertain",),
        inferred_option_id=inferred_option,
        inferred_motive_class=inferred_motive,
        reasoning_operation=operation,
        justification_kind=(
            "visible_evidence" if expected_class == "accurate" else "alternative_hypothesis"
        ),
        alternative_hypotheses=(
            () if expected_class == "accurate" else ("Druga pot ostaja možna.",)
        ),
        unresolved_ambiguity=(
            "Odločilni signal manjka." if expected_class == "unknown" else None
        ),
        confidence=0.9 if expected_class == "accurate" else 0.2,
        uncertainty="Negotovost je izrecno zapisana.",
    )
    return case, candidate, exposure


@pytest.fixture(scope="session")
def semantic_fixtures():
    return load_semantic_fixtures()


@pytest.fixture(scope="session")
def canonical_route_records(semantic_fixtures):
    return [
        make_route_case_candidate(family, variant, route)
        for family in semantic_fixtures
        for variant in family["variants"]
        for route in variant["expected_routes"]
    ]


@pytest.fixture(scope="session")
def canonical_interpretation_records(semantic_fixtures):
    return [
        make_interpretation_case_candidate(family, variant, expected)
        for family in semantic_fixtures
        for variant in family["variants"]
        for expected in variant["interpretation_variants"]
    ]
