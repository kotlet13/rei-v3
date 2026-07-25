from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from app.backend.rei.research.triad_vis_m1 import (
    OPTIONS,
    TEMPORAL_HORIZON,
    EmocioVisualMosaicV1,
    _canvas,
    _mosaic,
    deterministic_canvas_bytes,
)


def _canvases(variant: str) -> dict[str, object]:
    values = {}
    for role in (
        "current_state",
        "desired_target_state",
        "broken_failure_state",
        "private_action",
        "private_immediate_result",
        "public_action",
        "public_immediate_result",
    ):
        data = deterministic_canvas_bytes(variant=variant, semantic_role=role)
        values[role] = _canvas(
            variant=variant,
            semantic_role=role,
            repository_path=f"m1/{variant}/{role}.png",
            content_sha256=hashlib.sha256(data).hexdigest(),
        )
    return values


def test_mosaic_contract_preserves_temporal_and_option_boundaries() -> None:
    mosaic = _mosaic(variant="visible", canvases=_canvases("visible"))
    assert isinstance(mosaic, EmocioVisualMosaicV1)
    assert mosaic.temporal_horizon == TEMPORAL_HORIZON
    assert tuple(item.option_id for item in mosaic.options) == OPTIONS
    assert mosaic.desired_target_state.option_id is None
    assert mosaic.desired_target_state.panel_kind == "desired_target_state"
    assert mosaic.desired_target_state.leader_decision_state == "unknown"
    assert mosaic.broken_failure_state.leader_decision_state == "unknown"
    option_hashes = {
        panel.canvas.content_sha256
        for option in mosaic.options
        for panel in (option.action_panel, option.immediate_result_panel)
    }
    assert mosaic.desired_target_state.canvas.content_sha256 not in option_hashes
    assert mosaic.root_audience_count == 6
    assert mosaic.model_calls == 0
    assert mosaic.native_decision_influence == 0


def test_only_no_response_panels_alias_current() -> None:
    mosaic = _mosaic(variant="absent", canvases=_canvases("absent"))
    current = mosaic.current_state
    no_response = mosaic.options[0]
    assert no_response.action_panel.alias_of_panel_id == current.panel_id
    assert no_response.immediate_result_panel.alias_of_panel_id == current.panel_id
    assert no_response.action_panel.canvas.content_sha256 == current.canvas.content_sha256
    assert (
        no_response.immediate_result_panel.canvas.content_sha256
        == current.canvas.content_sha256
    )
    assert all(
        panel.alias_of_panel_id is None
        for option in mosaic.options[1:]
        for panel in (option.action_panel, option.immediate_result_panel)
    )


def test_attention_shift_does_not_resolve_recognition() -> None:
    mosaic = _mosaic(variant="visible", canvases=_canvases("visible"))
    result = mosaic.options[2].immediate_result_panel
    assert result.attention_target == "self"
    assert result.official_recognition_state == "unresolved"
    assert result.leader_decision_state == "unknown"
    assert not result.public_attribution_changed


def test_private_evidence_does_not_resolve_public_attribution() -> None:
    mosaic = _mosaic(variant="visible", canvases=_canvases("visible"))
    action = mosaic.options[1].action_panel
    result = mosaic.options[1].immediate_result_panel
    assert action.official_recognition_state == "unresolved"
    assert result.attention_target == "leader_considering_evidence"
    assert result.leader_decision_state == "unknown"
    assert not result.public_attribution_changed


def test_invalid_resolved_option_result_is_rejected() -> None:
    mosaic = _mosaic(variant="visible", canvases=_canvases("visible"))
    value = mosaic.model_dump(mode="python", round_trip=True)
    value["options"][2]["immediate_result_panel"][
        "official_recognition_state"
    ] = "desired_official_recognition_of_self"
    with pytest.raises(ValidationError):
        EmocioVisualMosaicV1.model_validate(value)


def test_canvases_are_deterministic_and_variant_isolation_is_bounded() -> None:
    for variant in ("visible", "absent"):
        for role in (
            "current_state",
            "desired_target_state",
            "broken_failure_state",
            "private_action",
            "private_immediate_result",
            "public_action",
            "public_immediate_result",
        ):
            assert deterministic_canvas_bytes(
                variant=variant, semantic_role=role
            ) == deterministic_canvas_bytes(variant=variant, semantic_role=role)
    assert deterministic_canvas_bytes(
        variant="visible", semantic_role="private_action"
    ) == deterministic_canvas_bytes(
        variant="absent", semantic_role="private_action"
    )
    assert deterministic_canvas_bytes(
        variant="visible", semantic_role="current_state"
    ) != deterministic_canvas_bytes(
        variant="absent", semantic_role="current_state"
    )
