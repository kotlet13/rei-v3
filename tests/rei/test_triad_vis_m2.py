from __future__ import annotations

from pathlib import Path

from app.backend.rei.research.triad_vis_m2 import (
    _context_and_requests,
    _json,
    _mapping,
    _preflight,
)
from app.backend.rei.research.triad_vis_m1r2 import (
    OUTPUT_RELATIVE_PATH as M1R2_RELATIVE_PATH,
)


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = (
    Path.home()
    / ".cache"
    / "rei-v3-models"
    / "FLUX.2-klein-4B-e7b7dc27"
)


def _prepared():
    return _context_and_requests(ROOT, snapshot=SNAPSHOT)


def test_exact_twenty_canvases_and_eighteen_render_keys() -> None:
    manifest, requests = _prepared()
    assert len(manifest.items) == 20
    assert len({item.canvas_id for item in manifest.items}) == 20
    assert len({item.render_key for item in manifest.items}) == 18
    assert len(requests) == 18


def test_private_cross_variant_dedup_and_matched_seeds() -> None:
    manifest, _ = _prepared()
    by_key = {(item.variant, item.semantic_role): item for item in manifest.items}
    assert (
        by_key[("visible", "private_action")].render_key
        == by_key[("absent", "private_action")].render_key
    )
    assert (
        by_key[("visible", "private_result")].render_key
        == by_key[("absent", "private_result")].render_key
    )
    assert all(
        item.seed == (
            314160
            if item.semantic_role in {"private_action", "private_result"}
            else 314159
        )
        for item in manifest.items
    )


def test_lineage_and_conditional_modality_are_complete() -> None:
    manifest, _ = _prepared()
    assert all(
        bool(item.primary_support_record_ids)
        != bool(item.primary_trigger_record_ids)
        for item in manifest.items
    )
    assert all(item.inherited_context_record_ids for item in manifest.items)
    recognition = manifest.conditional_evidence_policy["credit_ev_recognition"]
    assert recognition["conditional_relation"] == "present"
    assert recognition["realization"] == "unresolved"
    assert all(
        item.negative_constraint_record_ids
        for item in manifest.items
        if item.semantic_role
        in {"public_action", "public_result", "public_completion"}
    )


def test_signed_projection_basis_is_route_specific() -> None:
    manifest, _ = _prepared()
    roles = {item.semantic_role: item for item in manifest.items if item.variant == "visible"}
    assert roles["no_response_completion"].render_projection_basis == (
        "self_centered_desired_image_denied",
        "competition_loss",
        "obstacle_persistence",
    )
    assert "obstacle_removal" not in roles["no_response_completion"].render_projection_basis
    assert "gullibility" in roles["private_completion"].render_projection_basis
    assert "attention_gain" in roles["public_completion"].render_projection_basis


def test_prompts_are_natural_identity_stable_and_variant_correct() -> None:
    manifest, _ = _prepared()
    forbidden = (
        "credit_ev_",
        "record_",
        "sha256",
        "schema",
        "option_",
        "winner",
        "best",
        "preferred",
        "safest",
        "{",
        "}",
        "=",
    )
    for item in manifest.items:
        prompt = item.clean_natural_prompt.lower()
        assert not any(token in prompt for token in forbidden)
        assert "cobalt-blue blazer" in prompt
        assert "white shirt" in prompt
        assert "no tie" in prompt
        assert "charcoal suit" in prompt
        assert "burgundy tie" in prompt
        assert "cream blazer" in prompt
        assert "dark blouse" in prompt
        if item.variant == "absent":
            assert "wider audience" not in prompt
            assert "wider group" not in prompt


def test_epistemic_boundary_and_zero_authority() -> None:
    manifest, _ = _prepared()
    imagined = tuple(
        item for item in manifest.items
        if item.epistemic_classification == "imagined"
    )
    assert len(imagined) == 6
    assert all(not any(item.reality_claim_authorities) for item in imagined)
    assert all(item.primary_trigger_record_ids for item in imagined)
    assert all(not item.primary_support_record_ids for item in imagined)


def test_preflight_passes_without_calls() -> None:
    manifest, requests = _prepared()
    report = _preflight(manifest, requests)
    assert report["passed"] is True
    assert all(report["checks"].values())
    assert report["expected_image_model_calls"] == 18
    assert report["text_model_calls"] == 0
    assert report["racio_vision"] == 0
    assert report["visual_valuation"] == 0
    assert report["character_replay"] == 0
    assert report["native_decision_influence"] == 0


def test_panel_canvas_image_mapping_preserves_aliases() -> None:
    manifest, requests = _prepared()
    fake_images = tuple(
        {
            "render_key": item["render_key"],
            "artifact": {
                "image_id": f"image_{item['call_index']:02d}",
                "content_sha256": f"{item['call_index']:064x}",
            },
            "repository_image_path": (
                "Docs/evals/semantic_lab_v1/triad-vis-m2-2026-07-24/"
                f"images/render_{item['call_index']:02d}.png"
            ),
        }
        for item in requests
    )
    mapping = _mapping(
        _json(ROOT / M1R2_RELATIVE_PATH / "mosaic_manifest.json"),
        tuple(item.model_dump(mode="json") for item in manifest.items),
        fake_images,
    )
    assert mapping["display_panel_count"] == 24
    assert mapping["source_addressed_canvas_count"] == 20
    assert mapping["generated_image_artifact_count"] == 18
    assert sum(row["exact_current_image_alias"] for row in mapping["rows"]) == 4
    assert sum(row["cross_variant_shared_render"] for row in mapping["rows"]) == 4
