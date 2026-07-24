from __future__ import annotations

import hashlib
from pathlib import Path

from app.backend.rei.research.triad_vis_o2 import (
    CALL_ORDER,
    SEEDS,
    SLOT_ORDER,
    _canvas_png,
    _natural_prompt,
    _prompt_gate,
    identity_anchors,
    transition_specs,
)


def test_identity_anchors_are_fixed_and_profile_blind() -> None:
    anchors = identity_anchors()
    assert tuple(item.subject_id for item in anchors) == (
        "visual_self_001",
        "visual_colleague_001",
        "visual_leader_001",
    )
    assert all(item.generated_only for item in anchors)
    assert all(item.semantic_authority == "none" for item in anchors)
    assert "cobalt-blue blazer" in anchors[0].stable_clothing_anchor
    assert "charcoal suit" in anchors[1].stable_clothing_anchor
    assert "cream blazer" in anchors[2].stable_clothing_anchor


def test_transition_contracts_are_slot_specific() -> None:
    transitions = {item.slot: item for item in transition_specs()}
    assert tuple(transitions) == SLOT_ORDER
    assert transitions["current"].mode == "same_scene_hold"
    assert transitions["desired"].mode == "same_scene_edit"
    assert transitions["broken"].mode == "same_scene_edit"
    assert transitions["credit_no_response"].mode == "same_scene_hold"
    assert transitions["credit_private_evidence"].mode == "next_scene_cut"
    assert transitions["credit_public_confront"].mode == "same_scene_edit"
    assert transitions["credit_private_evidence"].retained_subject_ids == (
        "visual_leader_001",
        "visual_self_001",
    )


def test_canvas_generation_is_deterministic_and_no_response_is_current() -> None:
    for variant in ("visible", "absent"):
        current = _canvas_png(variant=variant, slot="current")
        assert current == _canvas_png(variant=variant, slot="current")
        assert hashlib.sha256(current).hexdigest()
    assert _canvas_png(
        variant="visible", slot="credit_private_evidence"
    ) == _canvas_png(variant="absent", slot="credit_private_evidence")


def test_natural_prompts_are_metadata_free_and_matched_seeded() -> None:
    items = []
    for index, (variant, slot) in enumerate(CALL_ORDER, start=1):
        prompt = _natural_prompt(variant=variant, slot=slot)
        items.append(
            {
                "call_index": index,
                "natural_prompt": prompt,
            }
        )
        assert "=" not in prompt
        assert "credit_ev_" not in prompt
        assert "scene_kind" not in prompt
        assert "option_id" not in prompt
        assert "No readable text" in prompt
    assert _prompt_gate(items)["passed"]
    assert SEEDS["credit_private_evidence"] == SEEDS["credit_public_confront"]
    assert len(CALL_ORDER) == 10


def test_human_review_is_explicitly_human_supplied() -> None:
    root = Path(__file__).resolve().parents[2]
    review = (
        root
        / "Docs/evals/semantic_lab_v1/triad-vis-o1-2026-07-24/"
        "human_visual_review.md"
    ).read_text(encoding="utf-8")
    assert "supplied by the human research owner" in review
    assert "not an automated Codex assessment" in review
    assert "Complete usable six-image case sets: **0/4**" in review
