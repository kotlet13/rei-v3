from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp"
sys.path.insert(0, str(RESEARCH_ROOT / "python"))

from emocio_vwm_mvp.boundary import (  # noqa: E402
    BoundaryViolation,
    validate_clean_media_call,
)


def _load(name: str) -> dict[str, object]:
    return json.loads((RESEARCH_ROOT / "specs" / name).read_text(encoding="utf-8"))


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _clean_png() -> bytes:
    raw = b"\x00\xff\x00\x00"
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def _write_call(directory: Path, *, extra: dict[str, object] | None = None) -> Path:
    media = _clean_png()
    (directory / "i0.png").write_bytes(media)
    payload: dict[str, object] = {
        "schema_version": "rei-emocio-vwm-clean-media-call-v1",
        "conditioning": "latent_action",
        "inputs": [
            {
                "slot": "observation",
                "media_type": "image/png",
                "path": "i0.png",
                "sha256": hashlib.sha256(media).hexdigest(),
            }
        ],
        "sampling": {"samples": 8, "stochastic": True},
    }
    if extra:
        payload.update(extra)
    target = directory / "call.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_world_has_exact_required_social_cast_and_rooms() -> None:
    world = _load("world_manifest.json")
    scenario = world["scenario"]
    people = scenario["people"]
    roles = [person["role"] for person in people]
    assert len(people) == 9
    assert roles.count("self") == 1
    assert roles.count("coworker") == 1
    assert roles.count("leader") == 1
    assert roles.count("audience") == 6
    assert {room["kind"] for room in scenario["rooms"]} == {
        "meeting_room",
        "private_office",
    }
    assert len({person["entity_id"] for person in people}) == 9


def test_world_has_all_required_visual_props_without_text_glyphs() -> None:
    world = _load("world_manifest.json")
    kinds = {item["kind"] for item in world["scenario"]["props"]}
    assert kinds == {
        "projection",
        "evidence_card",
        "official_attribution_marker",
        "pending_marker",
    }
    assert world["invariants"]["text_glyphs_allowed"] is False


def test_lpwm_pin_is_visual_only_and_has_no_download_authority() -> None:
    pin = _load("lpwm_pin.json")
    assert pin["commit"] == "4cf53c403433e64c01652ac2adbec66231a46dea"
    assert pin["conditioning"] == {
        "latent_action_sampling": True,
        "image_goal_condition": True,
        "action_condition": False,
        "language_condition": False,
        "language_embed_dim": 0,
        "language_max_len": 0,
    }
    assert pin["weights"]["vendored"] is False
    assert pin["weights"]["automatic_download"] is False


def test_clean_media_call_accepts_only_opaque_visual_input(tmp_path: Path) -> None:
    call = _write_call(tmp_path)
    validated = validate_clean_media_call(call)
    assert validated["inputs"][0]["slot"] == "observation"


@pytest.mark.parametrize(
    "leak",
    [
        {"prompt": "claim credit"},
        {"scenario_id": "public_credit"},
        {"entity_id": "person_self"},
        {"scene_graph": {"hidden": True}},
        {"character": "status-seeking"},
    ],
)
def test_visual_only_leakage_gate_rejects_semantic_fields(
    tmp_path: Path,
    leak: dict[str, object],
) -> None:
    call = _write_call(tmp_path, extra=leak)
    with pytest.raises(BoundaryViolation):
        validate_clean_media_call(call)


def test_png_text_metadata_is_rejected(tmp_path: Path) -> None:
    clean = _clean_png()
    insertion = clean.index(_png_chunk(b"IEND", b""))
    contaminated = clean[:insertion] + _png_chunk(b"tEXt", b"role\x00self") + clean[insertion:]
    (tmp_path / "i0.png").write_bytes(contaminated)
    call = {
        "schema_version": "rei-emocio-vwm-clean-media-call-v1",
        "conditioning": "latent_action",
        "inputs": [{
            "slot": "observation",
            "media_type": "image/png",
            "path": "i0.png",
            "sha256": hashlib.sha256(contaminated).hexdigest(),
        }],
        "sampling": {"samples": 2, "stochastic": True},
    }
    call_path = tmp_path / "call.json"
    call_path.write_text(json.dumps(call), encoding="utf-8")
    with pytest.raises(BoundaryViolation, match="metadata"):
        validate_clean_media_call(call_path)


def test_dataset_plan_contains_required_ablations_and_disjoint_holdout() -> None:
    plan = _load("dataset_plan.json")
    assert 0 < plan["conditioning_frames"] < plan["episode_frames"]
    assert set(plan["arms"]) == {
        "self_anchor_on_goal_off",
        "self_anchor_off_goal_off",
        "self_anchor_on_goal_match",
        "self_anchor_on_goal_mismatch",
    }
    assert plan["sampling"]["distinct_seed_repeats"] >= 8
    assert plan["split_rules"]["episode_seed_disjoint"] is True
    assert plan["split_rules"]["layout_family_disjoint_for_held_out"] is True
    splits = {split["name"]: split for split in plan["splits"]}
    assert splits["held_out"]["may_train"] is False
    assert splits["blind_human_review"]["may_train"] is False


def test_acceptance_is_frozen_and_stop_conditions_are_negative() -> None:
    acceptance = _load("acceptance.json")
    assert acceptance["frozen"] is True
    assert set(acceptance["verdicts"]) == {
        "medium_failed",
        "model_fit_failed",
        "model_fit_promising",
        "not_executed_resource_block",
    }
    stop = acceptance["stop_condition"]
    assert stop["technical_overfit_failure"] == "model_fit_failed"
    assert stop["social_model_fit_failure"] == "model_fit_failed"
    assert stop["model_substitution_within_result"] is False
    assert stop["acceptance_relaxation_within_result"] is False


def test_grounded_and_imagined_authority_are_non_interchangeable() -> None:
    world = _load("world_manifest.json")
    contract = world["reality_contract"]
    assert contract["grounded_namespace"] != contract["imagined_namespace"]
    assert contract["imagined_reality_authority"] is False
    assert contract["imagined_may_mutate_grounded"] is False


def test_model_output_contract_is_visual_and_non_authoritative() -> None:
    contract = _load("model_output_contract.json")
    assert contract["native_model_output"] == "visual_media_only"
    assert contract["required_future_samples"] == 8
    assert contract["reality_authority"] is False
    assert "explanation" in contract["forbidden_native_outputs"]
    assert "entity_id" in contract["forbidden_native_outputs"]
    assert set(contract["bundle_outputs"]) == {
        "future_clips",
        "key_mosaic",
        "selected_visual_path",
    }


def test_research_phase_starts_directly_from_requested_commit() -> None:
    phase = _load("research_phase.json")
    assert phase["direct_base_commit"] == "1300e1d6e1a94a4baae20152e895141543fbcd37"
    assert phase["phase"] == "exploration"
    assert phase["validation_started"] is False
    assert phase["human_review_required_before_validation"] is True
    assert phase["active_rei_runtime_modified"] is False


def test_exploration_package_does_not_modify_active_rei_runtime() -> None:
    research_files = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in RESEARCH_ROOT.rglob("*")
        if path.is_file() and "node_modules" not in path.parts
    ]
    assert research_files
    assert all(not name.startswith("app/backend/rei/") for name in research_files)
