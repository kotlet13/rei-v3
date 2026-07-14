from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

SCENARIO = r"""
import base64
import json

from app.backend.rei.evaluation.human_review import (
    commit_review_material,
    prepare_blind_review,
    record_final_review,
    record_first_pass,
    reveal_review_context,
    reviewer_agreement,
)
from app.backend.rei.evaluation.models import (
    CandidateClaim,
    CandidateNativeRoute,
    InputExposureRecord,
    NativeRouteEvaluationCase,
    TerminologyUse,
)
from app.backend.rei.evaluation.racio_eval import evaluate_racio_route


case = NativeRouteEvaluationCase(
    case_id="native-case-hash-seed",
    family_id="family-hash-seed",
    variant_id="variant-hash-seed",
    expected_route_id="route-hash-seed",
    mind="R",
    allowed_option_ids=("option-b", "option-a"),
    grounded_evidence_ids=("evidence-b", "evidence-a"),
    canonical_claim_ids=("source-claim-b", "source-claim-a"),
    expected_evidence_ids=("evidence-b", "evidence-a"),
    expected_route_tags=("explicit-rule", "grounded-fact"),
    expected_option_id="option-a",
    expected_decisive_representation="Rule and evidence select option A.",
    required_terminology_ids=("REI_RACIO",),
    source_locator_refs=("source-locator-b", "source-locator-a"),
)
candidate = CandidateNativeRoute(
    candidate_route_id="native-candidate-hash-seed",
    family_id=case.family_id,
    variant_id=case.variant_id,
    mind="R",
    claims=(
        CandidateClaim(
            claim_id="candidate-claim-b",
            facet="grounded-fact",
            value="Evidence B is present.",
            source_claim_ids=("source-claim-b",),
            evidence_ids=("evidence-b",),
            provenance_kind="supplied",
        ),
        CandidateClaim(
            claim_id="candidate-claim-a",
            facet="explicit-rule",
            value="The explicit rule selects option A.",
            source_claim_ids=("source-claim-a",),
            evidence_ids=("evidence-a",),
            provenance_kind="supplied",
        ),
    ),
    route_tags=("grounded-fact", "explicit-rule"),
    option_id="option-a",
    decisive_representation=case.expected_decisive_representation,
    short_decision_bridge_sl="Pravilo in dokazi izberejo možnost A.",
    terminology_uses=(
        TerminologyUse(
            terminology_id="REI_RACIO",
            language="sl",
            surface_form="Racio",
        ),
    ),
    confidence=0.9,
    uncertainty="The fixture has no unresolved material ambiguity.",
)
exposure = InputExposureRecord.create(
    subject_id=candidate.candidate_route_id,
    allowed_artifact_ids=("evidence-b", "evidence-a"),
    actual_input_artifact_ids=("evidence-a", "evidence-b"),
    visible_evidence_ids=("evidence-b", "evidence-a"),
    visible_option_ids=("option-b", "option-a"),
)
result = evaluate_racio_route(
    case=case,
    candidate=candidate,
    trusted_exposure=exposure,
    terminology_policy={"REI_RACIO": "Racio"},
)

review_case_id = "review-case-hash-seed"
review_subject_id = "review-subject-hash-seed"
commitment = commit_review_material(
    authority_id="review-authority-hash-seed",
    source_manifest_hash="a" * 64,
    case_id=review_case_id,
    subject_id=review_subject_id,
    blind_presented_text="Nevtralen opis za slepo presojo.",
    language="sl",
    route_ids=("review-route-b", "review-route-a"),
    visible_artifact_ids=("review-artifact-b", "review-artifact-a"),
    visible_observation_ids=("review-observation-b", "review-observation-a"),
    source_excerpts=(
        ("review-source-b", "Drugi povzetek vira."),
        ("review-source-a", "Prvi povzetek vira."),
    ),
    grounded_scene_text="Utemeljena scena za presojo.",
    grounded_scene_artifact_ids=("scene-b", "scene-a"),
    grounded_evidence_ids=("review-evidence-b", "review-evidence-a"),
)
packet = prepare_blind_review(commitment)


def final_review(reviewer_id):
    session = record_first_pass(
        packet,
        reviewer_id=reviewer_id,
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=4,
        translation_quality=4,
        uncertainty=2,
    )
    revealed = reveal_review_context(
        session,
        material_commitment=commitment,
    )
    return record_final_review(
        revealed,
        selected_mind="R",
        selected_route_id=packet.blind_route_ids[0],
        reasoning_quality=5,
        translation_quality=4,
        uncertainty=1,
    )


agreement = reviewer_agreement(
    (final_review("reviewer-b"), final_review("reviewer-a"))
)
result_bytes = result.canonical_json_bytes()
agreement_bytes = agreement.canonical_json_bytes()
print(
    json.dumps(
        {
            "result_id": result.result_id,
            "agreement_id": agreement.agreement_id,
            "result_canonical_b64": base64.b64encode(result_bytes).decode("ascii"),
            "agreement_canonical_b64": base64.b64encode(agreement_bytes).decode(
                "ascii"
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
)
"""


def _run_scenario(hash_seed: int) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = str(hash_seed)
    environment["PYTHONPATH"] = str(REPO_ROOT)
    environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, "-c", SCENARIO],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return json.loads(completed.stdout)


def test_native_result_and_reviewer_agreement_ignore_python_hash_seed() -> None:
    seed_one = _run_scenario(1)
    seed_four = _run_scenario(4)

    assert seed_one == seed_four
    assert seed_one["result_id"].startswith("semantic_eval_")
    assert seed_one["agreement_id"].startswith("reviewer_agreement_")

    result_payload = json.loads(
        base64.b64decode(seed_one["result_canonical_b64"])
    )
    agreement_payload = json.loads(
        base64.b64decode(seed_one["agreement_canonical_b64"])
    )
    assert result_payload["result_id"] == seed_one["result_id"]
    assert agreement_payload["agreement_id"] == seed_one["agreement_id"]
