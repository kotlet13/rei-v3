from __future__ import annotations

import json

from app.backend.rei.contract_loader import (
    build_ego_prompt,
    build_processor_prompt,
    ego_required_keys,
    get_processor_contract,
    required_keys_for,
    runtime_required_keys_for,
)
from app.backend.rei import prompts


def _prompt_shape(prompt: str) -> dict[str, object]:
    blob = prompt.split("Required JSON shape, fill every key:", maxsplit=1)[1].strip()
    shape, _end = json.JSONDecoder().raw_decode(blob)
    return shape


CANONICAL_BOILERPLATE_KEYS = {
    "native_language",
    "world_filter",
    "primary_motive",
    "truth_model",
    "defense_mode",
    "justice_model",
    "accepting_expression",
    "accepted_expression",
    "non_accepting_distortion",
    "non_accepted_expression",
    "resistance_to_other_minds",
    "what_this_mind_needs",
    "risk_if_ignored",
    "risk_if_dominant",
    "blind_spot",
    "source_refs",
    "safety_flags",
}


def test_processor_flags_are_canonical() -> None:
    assert get_processor_contract("racio")["conscious_access"] is True
    assert get_processor_contract("racio")["translated_by_racio"] is False

    for mind in ("emocio", "instinkt"):
        contract = get_processor_contract(mind)  # type: ignore[arg-type]
        assert contract["conscious_access"] is False
        assert contract["translated_by_racio"] is True


def test_required_keys_include_canonical_fields() -> None:
    racio_keys = set(required_keys_for("racio"))
    emocio_keys = set(required_keys_for("emocio"))
    instinkt_keys = set(required_keys_for("instinkt"))

    assert {"known_facts", "unknowns", "rationalization_risk", "translation_of_other_minds_risk"} <= racio_keys
    assert {"current_image", "desired_image", "broken_image", "recognition_need", "body_expression"} <= emocio_keys
    assert {"threat_map", "loss_map", "fear_feeling", "trust_boundary", "minimum_safety_condition"} <= instinkt_keys

    for keys in (racio_keys, emocio_keys, instinkt_keys):
        assert {"native_language", "world_filter", "truth_model", "defense_mode", "justice_model", "source_refs"} <= keys


def test_prompts_preserve_processor_boundaries() -> None:
    racio_prompt = build_processor_prompt("racio")
    emocio_prompt = build_processor_prompt("emocio")
    instinkt_prompt = build_processor_prompt("instinkt")

    assert "translated_by_racio=false" in racio_prompt
    assert "translated_by_racio=true" in emocio_prompt
    assert "translated_by_racio=true" in instinkt_prompt

    assert "image/social/desire signal" in emocio_prompt
    assert "protective/body/fear/loss signal" in instinkt_prompt
    assert "must not claim objective truth" in racio_prompt


def test_processor_prompt_skeleton_uses_correct_constants() -> None:
    expected = {
        "racio": (True, False, "conscious verbal-analytical interpretation"),
        "emocio": (False, True, "Racio-translated approximation of unconscious image/social/desire signal"),
        "instinkt": (False, True, "Racio-translated approximation of unconscious protective/fear/attachment signal"),
    }
    for mind, (is_conscious, translated_by_racio, processing_mode) in expected.items():
        shape = _prompt_shape(build_processor_prompt(mind))  # type: ignore[arg-type]
        assert shape["mind"] == mind
        assert shape["is_conscious"] is is_conscious
        assert shape["translated_by_racio"] is translated_by_racio
        assert shape["processing_mode"] == processing_mode


def test_runtime_prompt_does_not_require_canonical_boilerplate() -> None:
    for mind in ("racio", "emocio", "instinkt"):
        runtime_keys = set(runtime_required_keys_for(mind))  # type: ignore[arg-type]
        full_keys = set(required_keys_for(mind))  # type: ignore[arg-type]
        prompt = build_processor_prompt(mind, mode="compact")  # type: ignore[arg-type]
        shape = _prompt_shape(prompt)

        assert runtime_keys == set(prompts.PROCESSOR_REQUIRED_KEYS[mind])
        assert full_keys == set(prompts.PROCESSOR_FULL_REQUIRED_KEYS[mind])
        assert not runtime_keys & CANONICAL_BOILERPLATE_KEYS
        assert CANONICAL_BOILERPLATE_KEYS & full_keys
        assert not set(shape) & CANONICAL_BOILERPLATE_KEYS
        assert "Required JSON keys, all must be present:" in prompt


def test_runtime_prompts_are_compact_not_full() -> None:
    for prompt in (
        prompts.RACIO_SYSTEM_PROMPT,
        prompts.EMOCIO_SYSTEM_PROMPT,
        prompts.INSTINKT_SYSTEM_PROMPT,
    ):
        assert "Canonical acceptance/non-acceptance:" not in prompt
        assert "Source reference IDs to include in source_refs:" not in prompt

    assert "Canonical acceptance/non-acceptance:" in prompts.RACIO_AUDIT_PROMPT


def test_ego_is_not_fourth_mind() -> None:
    prompt = build_ego_prompt()
    keys = set(ego_required_keys())

    assert "not a fourth mind" in prompt.lower()
    assert "never default to Racio" in prompt
    assert {"perceived_world", "conscious_story", "hidden_signal_sources", "racio_after_story"} <= keys
