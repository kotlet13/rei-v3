from __future__ import annotations

from pathlib import Path

from app.backend.rei.emocio.prompting import (
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from app.backend.rei.research.triad_vis_o1 import (
    BANNED_PROMPT_TERMS,
    CASE_ORDER,
    SCENE_SEEDS,
    _request_from_manifest,
    build_scene_plan,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_scene_plan_freezes_exact_24_render_inputs() -> None:
    plan = build_scene_plan(REPOSITORY_ROOT)
    assert len(plan) == 24
    assert tuple(dict.fromkeys(item["case_id"] for item in plan)) == CASE_ORDER
    for case_id in CASE_ORDER:
        items = [item for item in plan if item["case_id"] == case_id]
        assert tuple(item["role"] for item in items[:3]) == (
            "current",
            "desired",
            "broken",
        )
        option_items = items[3:]
        option_ids = tuple(item["option_id"] for item in option_items)
        assert option_ids == tuple(sorted(option_ids))
        assert tuple(item["seed"] for item in items) == (
            SCENE_SEEDS["current"],
            SCENE_SEEDS["desired"],
            SCENE_SEEDS["broken"],
            SCENE_SEEDS["option_0"],
            SCENE_SEEDS["option_1"],
            SCENE_SEEDS["option_2"],
        )


def test_prompts_are_model_free_and_do_not_predetermine_options() -> None:
    profile = VisualPromptProfile.create(
        language="en",
        style_id="documentary_cinematic_v1",
        style_directive=(
            "Documentary cinematic still, restrained natural colors, stable identity "
            "and composition. No text, labels, logos, crowns, weapons, or extra people."
        ),
    )
    compiler = BilingualStructuredScenePromptCompiler(profile)
    for item in build_scene_plan(REPOSITORY_ROOT):
        prompt = compiler.compile(item["scene"])
        lowered = prompt.lower()
        assert not any(term in lowered for term in BANNED_PROMPT_TERMS)
        assert "generated details are imagined" in lowered
        assert item["scene"].grounded_evidence_ids


def test_scene_specs_preserve_route_scope_and_profile_blindness() -> None:
    forbidden = {
        "character",
        "character_profile",
        "governance",
        "expected_option",
        "expected_action",
        "gold_route",
        "leading_mind",
    }
    for item in build_scene_plan(REPOSITORY_ROOT):
        payload = item["scene"].model_dump(mode="json", round_trip=True)
        assert forbidden.isdisjoint(payload)
        assert payload["scene_kind"] == (
            "option_rollout" if item["role"].startswith("option_") else item["role"]
        )


def test_strict_json_scene_replay_preserves_frozen_scene(monkeypatch) -> None:
    item = build_scene_plan(REPOSITORY_ROOT)[0]
    profile = VisualPromptProfile.create(
        language="en",
        style_id="documentary_cinematic_v1",
        style_directive=(
            "Documentary cinematic still, restrained natural colors, stable identity "
            "and composition. No text, labels, logos, crowns, weapons, or extra people."
        ),
    )
    compiler = BilingualStructuredScenePromptCompiler(profile)

    class _Provider:
        identity = None

    # The request factory needs the real provider contract, so this regression
    # isolates the strict JSON path by intercepting construction after the scene
    # has been validated and compared.
    def capture(**kwargs):
        assert kwargs["source_spec"] == item["scene"]
        raise RuntimeError("scene_replay_verified")

    monkeypatch.setattr(
        "app.backend.rei.research.triad_vis_o1.ImageRenderRequest.create",
        capture,
    )
    prompt_item = {
        **item,
        "scene_spec": item["scene"].model_dump(mode="json", round_trip=True),
        "positive_prompt": compiler.compile(item["scene"]),
        "negative_prompt": "",
    }
    provider = _Provider()
    provider.identity = object()
    provider.pipeline_spec = lambda _mode: object()
    try:
        _request_from_manifest(
            prompt_item,
            provider=provider,
            profile=profile,
            source_image=None,
        )
    except RuntimeError as error:
        assert str(error) == "scene_replay_verified"
    else:
        raise AssertionError("request construction interception did not run")
