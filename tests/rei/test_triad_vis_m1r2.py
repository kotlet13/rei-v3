from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.research.triad_vis_m1r2 import (
    CANVAS_ROLES,
    EmocioVisualMosaicR2,
    _build_mosaic,
    _canvas,
    _panel_evidence_ids,
    _validate_inventory,
    deterministic_canvas_bytes,
    evidence_records,
)


ROOT = Path(__file__).resolve().parents[2]


def _mosaic(variant: str) -> EmocioVisualMosaicR2:
    records, sources = evidence_records(ROOT)
    case_id = f"public_credit_audience_{variant}"
    source = sources[case_id]
    record_lookup = {
        (record.original_source_case_id, record.evidence_id): record
        for record in records
    }
    canvases = {}
    for role in CANVAS_ROLES:
        ids = _panel_evidence_ids(semantic_role=role, variant=variant)
        role_records = tuple(record_lookup[(case_id, evidence_id)] for evidence_id in ids)
        data = deterministic_canvas_bytes(variant=variant, semantic_role=role)
        imagined = role.endswith("_completion")
        canvases[role] = _canvas(
            variant=variant,
            role=role,
            source=source,
            record_ids=tuple(record.record_id for record in role_records),
            evidence_role="projection_trigger" if imagined else "support",
            path=f"m1r2/{variant}/{role}.png",
            data=data,
            authority=(role == "present"),
        )
    return _build_mosaic(
        variant=variant,
        source=source,
        records=records,
        canvases=canvases,
    )


def test_original_evidence_record_hash_closure_and_polarity() -> None:
    records, _ = evidence_records(ROOT)
    assert len(records) == 16
    assert len({record.record_id for record in records}) == 16
    assert all(len(record.evidence_sha256) == 64 for record in records)
    by_key = {
        (record.original_source_case_id, record.evidence_id): record
        for record in records
    }
    assert by_key[
        ("public_credit_audience_visible", "credit_ev_audience")
    ].polarity == "present"
    assert by_key[
        ("public_credit_audience_absent", "credit_ev_audience")
    ].polarity == "absent"
    assert by_key[
        ("public_credit_audience_visible", "credit_ev_recognition")
    ].polarity == "unknown"
    assert by_key[
        ("public_credit_audience_absent", "credit_ev_retaliation")
    ].polarity == "absent"


def test_m1r_repository_blobs_remain_exactly_frozen() -> None:
    manifest = json.loads(
        (
            ROOT
            / "Docs/evals/semantic_lab_v1/triad-vis-m1r2-2026-07-24/"
            "mosaic_manifest.json"
        ).read_text(encoding="utf-8")
    )
    _validate_inventory(ROOT, manifest["m1r_frozen_inventory"])


def test_imagined_completion_uses_triggers_not_support() -> None:
    for variant in ("visible", "absent"):
        mosaic = _mosaic(variant)
        for option in mosaic.options:
            completion = option.emocio_imagined_completion_panel
            assert completion.supporting_evidence_ids is None
            assert completion.supporting_evidence_record_ids is None
            assert completion.triggering_evidence_ids
            assert completion.triggering_evidence_record_ids
            dumped = completion.model_dump(mode="json", exclude_none=True)
            assert "supporting_evidence_ids" not in dumped
            assert dumped["triggering_evidence_ids"]


def test_depicted_imagined_world_is_separate_from_grounded_status() -> None:
    completion = _mosaic("visible").options[2].emocio_imagined_completion_panel
    assert completion.depicted_imagined_state.official_attribution == "self_recognized"
    assert completion.depicted_imagined_state.imagined_leader_outcome == "confirming_self"
    assert completion.grounded_reality_status.actual_leader_decision == "unknown"
    assert completion.grounded_reality_status.actual_official_correction == "pending"
    assert completion.grounded_reality_status.actual_audience_support == "unknown"
    assert completion.reality_claim_authority is False


def test_absent_audience_support_must_be_not_applicable() -> None:
    mosaic = _mosaic("absent")
    public = mosaic.options[2]
    relation = next(
        item for item in public.unresolved_relations
        if item.relation_type == "audience_support"
    )
    assert relation.state == "not_applicable"
    assert (
        public.emocio_imagined_completion_panel.grounded_reality_status
        .actual_audience_support
        == "not_applicable"
    )
    value = mosaic.model_dump(mode="python", round_trip=True)
    relation_value = next(
        item
        for item in value["options"][2]["unresolved_relations"]
        if item["relation_type"] == "audience_support"
    )
    relation_value["state"] = "unknown"
    with pytest.raises(ValidationError):
        EmocioVisualMosaicR2.model_validate(value)


def test_absent_text_and_canvases_have_no_wider_audience() -> None:
    mosaic = _mosaic("absent")
    serialized = json.dumps(mosaic.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "wider audience" not in serialized
    assert "wider group" not in serialized
    assert "public admiration" not in serialized
    assert all(
        panel.canvas.additional_person_count == 0
        for _, panel in (
            ("present", mosaic.present_state),
            ("desired", mosaic.desired_counterfactual),
            ("broken", mosaic.broken_counterfactual),
            *(
                (option.option_id, panel)
                for option in mosaic.options
                for panel in (
                    option.action_panel,
                    option.grounded_immediate_result_panel,
                    option.emocio_imagined_completion_panel,
                )
            ),
        )
    )


def test_visible_and_absent_completion_summaries_differ() -> None:
    visible = _mosaic("visible")
    absent = _mosaic("absent")
    for index in (1, 2):
        assert (
            visible.options[index].emocio_imagined_completion_panel.semantic_summary
            != absent.options[index].emocio_imagined_completion_panel.semantic_summary
        )
    assert (
        visible.options[2].emocio_imagined_completion_panel
        .depicted_imagined_state.recognition_scope
        == "wider_group"
    )
    assert (
        absent.options[2].emocio_imagined_completion_panel
        .depicted_imagined_state.recognition_scope
        == "three_person_meeting"
    )


def test_all_semantic_layers_remain_distinct() -> None:
    for variant in ("visible", "absent"):
        mosaic = _mosaic(variant)
        desired_hash = mosaic.desired_counterfactual.canvas.content_sha256
        for option in mosaic.options:
            layers = (
                option.action_panel,
                option.grounded_immediate_result_panel,
                option.emocio_imagined_completion_panel,
            )
            assert len({panel.panel_id for panel in layers}) == 3
            assert (
                option.emocio_imagined_completion_panel.canvas.content_sha256
                != option.grounded_immediate_result_panel.canvas.content_sha256
            )
            assert desired_hash not in {
                option.action_panel.canvas.content_sha256,
                option.grounded_immediate_result_panel.canvas.content_sha256,
                option.emocio_imagined_completion_panel.canvas.content_sha256,
            }


def test_no_calls_or_authority() -> None:
    mosaic = _mosaic("visible")
    assert mosaic.model_calls == 0
    assert mosaic.image_calls == 0
    assert mosaic.character_replay == 0
    assert mosaic.native_decision_influence == 0
    assert mosaic.runtime_authority is False
    serialized = json.dumps(mosaic.model_dump(mode="json"), sort_keys=True)
    assert "character_profile" not in serialized
    assert "governance_tier" not in serialized
    assert "expected_option" not in serialized
