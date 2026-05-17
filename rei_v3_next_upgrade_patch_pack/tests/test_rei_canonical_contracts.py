from __future__ import annotations

from app.backend.rei.contract_loader import (
    build_ego_prompt,
    build_processor_prompt,
    ego_required_keys,
    get_processor_contract,
    required_keys_for,
)


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


def test_ego_is_not_fourth_mind() -> None:
    prompt = build_ego_prompt()
    keys = set(ego_required_keys())

    assert "not a fourth mind" in prompt.lower()
    assert "never default to Racio" in prompt
    assert {"perceived_world", "conscious_story", "hidden_signal_sources", "racio_after_story"} <= keys
