from __future__ import annotations

import json

from app.backend.rei.evaluation.models import CandidateNativeRoute

from .conftest import TERMINOLOGY_POLICY


def _with_payload(candidate, mutation):
    payload = candidate.model_dump(mode="json")
    mutation(payload)
    return CandidateNativeRoute.model_validate_json(json.dumps(payload, ensure_ascii=False))


def test_racio_rejects_character_moral_status_and_hidden_motive_shortcuts(
    canonical_route_records,
):
    case, candidate, exposure, evaluator = next(
        record for record in canonical_route_records if record[0].mind == "R"
    )
    corrupted = _with_payload(
        candidate,
        lambda payload: payload["route_tags"].append("character_label"),
    )
    result = evaluator(
        case=case,
        candidate=corrupted,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert "racio_forbidden_reasoning_shortcut" in {
        item.issue_code for item in result.issues
    }


def test_emocio_rejects_renderer_added_material_as_grounded_fact(
    canonical_route_records,
):
    case, candidate, exposure, evaluator = next(
        record for record in canonical_route_records if record[0].mind == "E"
    )

    def add_renderer_claim(payload):
        payload["claims"].append(
            {
                "claim_id": "renderer_claim",
                "facet": "grounded_fact",
                "value": "Element je dodal renderer.",
                "source_claim_ids": list(case.canonical_claim_ids),
                "evidence_ids": [],
                "observation_ids": [],
                "provenance_kind": "renderer_added_ungrounded",
            }
        )

    corrupted = _with_payload(candidate, add_renderer_claim)
    result = evaluator(
        case=case,
        candidate=corrupted,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert "emocio_scene_or_renderer_boundary_failure" in {
        item.issue_code for item in result.issues
    }


def test_instinkt_is_not_scored_by_withdrawal_alone(canonical_route_records):
    case, candidate, exposure, evaluator = next(
        record for record in canonical_route_records if record[0].mind == "I"
    )
    corrupted = _with_payload(
        candidate,
        lambda payload: payload.update({"route_tags": ["withdrawal"]}),
    )
    result = evaluator(
        case=case,
        candidate=corrupted,
        trusted_exposure=exposure,
        terminology_policy=TERMINOLOGY_POLICY,
    )
    assert "instinkt_withdrawal_only_or_missing_protection" in {
        item.issue_code for item in result.issues
    }
