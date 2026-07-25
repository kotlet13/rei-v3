from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.backend.rei.research.triad_vis_m1r import (
    IMAGINED_HORIZON,
    IMMEDIATE_HORIZON,
    OPTION_IDS,
    RELATION_STATES,
    _build_mosaic,
    _canvas,
    deterministic_canvas_bytes,
    source_case_projections,
)


ROOT = Path(__file__).resolve().parents[2]


def _mosaic(variant: str):
    source = next(
        item
        for item in source_case_projections(ROOT)
        if item["source_case_id"].endswith(variant)
    )
    source_roles = {
        "present": "current",
        "desired": "desired",
        "broken": "broken",
        "private_action": "option_1",
        "private_result": "option_1",
        "public_action": "option_2",
        "public_result": "option_2",
        "no_response_completion": "option_0",
        "private_completion": "option_1",
        "public_completion": "option_2",
    }
    source_items = {item["role"]: item for item in source["source_items"]}
    canvases = {}
    for role, source_role in source_roles.items():
        data = deterministic_canvas_bytes(variant=variant, semantic_role=role)
        evidence = tuple(
            sorted(source_items[source_role]["scene_spec"]["grounded_evidence_ids"])
        )
        canvases[role] = _canvas(
            variant=variant,
            semantic_role=role,
            source=source,
            evidence_ids=evidence,
            derivation_status=(
                "imagined_by_emocio"
                if role.endswith("_completion")
                else "implementation_neutral"
            ),
            reality_claim_authority=(role == "present"),
            repository_path=f"m1r/{variant}/{role}.png",
            data=data,
        )
    return _build_mosaic(variant=variant, source=source, canvases=canvases)


def test_opaque_case_and_option_ids_are_preserved() -> None:
    for variant in ("visible", "absent"):
        mosaic = _mosaic(variant)
        assert mosaic.case_id == f"public_credit_audience_{variant}"
        assert mosaic.case_id == mosaic.source_case_id
        assert tuple(item.option_id for item in mosaic.options) == OPTION_IDS


def test_source_evidence_closure_covers_panels_and_relations() -> None:
    mosaic = _mosaic("visible")
    allowed = set(mosaic.source_evidence_ids)
    panels = (
        mosaic.present_state,
        mosaic.desired_counterfactual,
        mosaic.broken_counterfactual,
        *(
            panel
            for option in mosaic.options
            for panel in (
                option.action_panel,
                option.grounded_immediate_result_panel,
                option.emocio_imagined_completion_panel,
            )
        ),
    )
    assert all(set(panel.supporting_evidence_ids) <= allowed for panel in panels)
    assert all(
        set(relation.supporting_evidence_ids) <= allowed
        for option in mosaic.options
        for relation in option.unresolved_relations
    )
    assert all(
        panel.canvas.supporting_evidence_ids == panel.supporting_evidence_ids
        for panel in panels
    )


def test_counterfactual_states_have_no_option_horizon() -> None:
    mosaic = _mosaic("visible")
    assert mosaic.present_state.temporal_horizon is None
    assert mosaic.desired_counterfactual.temporal_horizon is None
    assert mosaic.broken_counterfactual.temporal_horizon is None
    assert mosaic.desired_counterfactual.leader_decision_state == "not_applicable"
    assert mosaic.broken_counterfactual.leader_decision_state == "not_applicable"
    assert all(
        option.action_panel.temporal_horizon == IMMEDIATE_HORIZON
        and option.grounded_immediate_result_panel.temporal_horizon
        == IMMEDIATE_HORIZON
        and option.emocio_imagined_completion_panel.temporal_horizon
        == IMAGINED_HORIZON
        for option in mosaic.options
    )


def test_grounded_results_never_resolve_leader_decision() -> None:
    mosaic = _mosaic("visible")
    assert tuple(
        option.grounded_immediate_result_panel.leader_decision_state
        for option in mosaic.options
    ) == ("not_triggered", "pending", "pending")
    assert tuple(
        option.grounded_immediate_result_panel.official_attribution_state
        for option in mosaic.options
    ) == ("unchanged", "unchanged", "pending")


def test_imagined_completion_has_no_reality_authority_or_alias() -> None:
    mosaic = _mosaic("visible")
    for option in mosaic.options:
        completion = option.emocio_imagined_completion_panel
        assert completion.derivation_status == "imagined_by_emocio"
        assert completion.reality_claim_authority is False
        assert completion.imagined_route_rationale
        assert completion.panel_id not in {
            option.action_panel.panel_id,
            option.grounded_immediate_result_panel.panel_id,
            mosaic.desired_counterfactual.panel_id,
        }


def test_option_specific_relations_are_not_cross_copied() -> None:
    mosaic = _mosaic("visible")
    observed = tuple(
        tuple((item.relation_type, item.state) for item in option.unresolved_relations)
        for option in mosaic.options
    )
    assert observed == tuple(RELATION_STATES[option_id] for option_id in OPTION_IDS)
    assert len(set(observed)) == 3


def test_official_marker_is_distinct_from_attention_only_marker() -> None:
    mosaic = _mosaic("visible")
    desired = mosaic.desired_counterfactual
    public_result = mosaic.options[2].grounded_immediate_result_panel
    assert desired.official_attribution_state == "desired_self_recognized"
    assert public_result.official_attribution_state == "pending"
    assert desired.canvas.content_sha256 != public_result.canvas.content_sha256
    assert deterministic_canvas_bytes(
        variant="visible", semantic_role="desired"
    ) != deterministic_canvas_bytes(
        variant="visible", semantic_role="public_result"
    )


def test_broken_canvas_uses_no_m1_gray_occlusion_bytes() -> None:
    new = deterministic_canvas_bytes(variant="visible", semantic_role="broken")
    old = (
        ROOT
        / "Docs/evals/semantic_lab_v1/triad-vis-m1-2026-07-24/"
        "canvases/visible/broken_failure_state.png"
    ).read_bytes()
    assert hashlib.sha256(new).hexdigest() != hashlib.sha256(old).hexdigest()


def test_no_character_governance_or_call_authority() -> None:
    mosaic = _mosaic("visible")
    serialized = json.dumps(mosaic.model_dump(mode="json"), sort_keys=True)
    assert "character_profile" not in serialized
    assert "governance_tier" not in serialized
    assert "expected_option" not in serialized
    assert mosaic.model_calls == 0
    assert mosaic.character_replay == 0
    assert mosaic.native_decision_influence == 0
