from __future__ import annotations

from dataclasses import replace
import pytest
from pydantic import ValidationError

from app.backend.rei_next.emocio import (
    DeterministicEmocioProcessor,
    NullRenderer,
    aggregate_option_valuation,
    build_emocio_packet,
    process_emocio,
)
from app.backend.rei_next.emocio import processor as processor_module
from app.backend.rei_next.models.emocio import (
    EMOCIO_VALUATION_DIMENSIONS,
    EmocioWorld,
    ImageArtifact,
)
from app.backend.rei_next.models.scene import (
    DecisionOption,
    EvidenceItem,
    SceneEvent,
)


def _scene(
    *,
    raw_input: str = "Oseba izbira med dvema strukturiranima prizoroma.",
    text_evidence: str = "Besedni opis brez avtomatske semanti\u010dne razvrstitve.",
    reverse_options: bool = False,
) -> SceneEvent:
    options = (
        DecisionOption(
            option_id="option_broken",
            label="collapsed room",
            description="",
        ),
        DecisionOption(
            option_id="option_desired",
            label="future home",
            description="",
        ),
    )
    if reverse_options:
        options = tuple(reversed(options))
    return SceneEvent(
        event_id="event_emocio_b6",
        raw_input=raw_input,
        language="sl",
        evidence=(
            EvidenceItem(
                evidence_id="evidence_text",
                modality="text",
                content=text_evidence,
                grounded=True,
                source_ref="user:event_emocio_b6",
                confidence=1.0,
            ),
            EvidenceItem(
                evidence_id="evidence_image",
                modality="image",
                content="current hallway",
                grounded=True,
                source_ref="user:image_1",
                confidence=1.0,
            ),
            EvidenceItem(
                evidence_id="evidence_generated",
                modality="image",
                content="renderer-only crown",
                grounded=False,
                source_ref="renderer:image_1",
                confidence=0.2,
                provenance_kind="generated",
                inferred_by="renderer_test",
            ),
        ),
        options=options,
        actors=("observer", "other"),
        constraints=("keep identity stable",),
        unknowns=("outcome",),
    )


def _world(
    *,
    desired: tuple[str, ...] = ("future home",),
    broken: tuple[str, ...] = ("collapsed room",),
) -> EmocioWorld:
    return EmocioWorld(
        world_id="emocio_world_b6",
        visual_memories=("remembered doorway",),
        desired_scenes=desired,
        broken_scenes=broken,
        social_identity_motifs=("recognized place",),
        attraction_patterns=("future home",),
        motor_patterns=("step forward",),
    )


def _image_for_first_scene(scenes: tuple, *, detail: str) -> ImageArtifact:
    source = scenes[0]
    return ImageArtifact(
        image_id=f"image_{detail.replace(' ', '_')}",
        request_id="render_request_test",
        render_call_id="render_call_test",
        source_spec_id=source.scene_id,
        provider_id="test_renderer",
        seed=17,
        input_spec_hash=source.content_hash(),
        content_sha256="1" * 64,
        media_type="image/png",
        prompt="test-only render",
        negative_prompt="",
        path="emocio/images/test.png",
        width=32,
        height=32,
        generated_only_elements=(detail,),
    )


class AddedDetailRenderer:
    def render(self, scenes: tuple, *, seed: int) -> tuple[ImageArtifact, ...]:
        assert seed == 17
        return (_image_for_first_scene(scenes, detail="renderer-only crown"),)


class ExplodingRenderer:
    def render(self, scenes: tuple, *, seed: int) -> tuple[ImageArtifact, ...]:
        del scenes, seed
        raise RuntimeError("synthetic renderer outage")


class InvalidLineageRenderer:
    def render(self, scenes: tuple, *, seed: int) -> tuple[ImageArtifact, ...]:
        del seed
        image = _image_for_first_scene(scenes, detail="foreign detail")
        return (image.model_copy(update={"input_spec_hash": "2" * 64}),)


class InvalidSeedRenderer:
    def render(self, scenes: tuple, *, seed: int) -> tuple[ImageArtifact, ...]:
        image = _image_for_first_scene(scenes, detail="seed mismatch")
        return (image.model_copy(update={"seed": seed + 1}),)


def test_packet_router_is_profile_blind_and_uses_explicit_modalities_only() -> None:
    packet = build_emocio_packet(_scene())

    assert packet.allowed_option_ids == ("option_broken", "option_desired")
    assert packet.source_scene_hash == _scene().scene_hash()
    assert packet.evidence_ids == ("evidence_image",)
    assert packet.grounded_visual_cues == ("current hallway",)
    assert packet.aesthetic_cues == ("current hallway",)
    assert "renderer-only crown" not in packet.grounded_visual_cues
    assert packet.explicit_identity_cues == ("observer", "other")
    assert {
        "character_profile",
        "character_authority",
        "authority_tiers",
        "preferred_option",
    }.isdisjoint(type(packet).model_fields)


def test_content_addressed_packet_rejects_scene_and_field_tampering() -> None:
    scene = _scene()
    packet = build_emocio_packet(scene)

    with pytest.raises(ValueError, match="source hash"):
        packet.model_copy(
            update={"source_scene_hash": "0" * 64}
        ).validate_against(scene)
    with pytest.raises(ValueError, match="deterministic router"):
        packet.model_copy(
            update={"grounded_visual_cues": ("fabricated visual fact",)}
        ).validate_against(scene)
    with pytest.raises(ValueError, match="canonical content"):
        packet.model_copy(update={"packet_id": "tampered"}).validate_against(scene)


def test_scene_graph_preserves_identity_and_grounded_scope_across_rollouts() -> None:
    result = process_emocio(_scene(), _world())
    state = result.visual_state
    scenes = (
        state.current_scene,
        state.desired_scene,
        state.broken_scene,
        *state.option_rollouts,
    )

    assert tuple(item.option_id for item in state.option_rollouts) == (
        "option_broken",
        "option_desired",
    )
    assert len({item.scene_id for item in scenes}) == len(scenes)
    assert {item.entities for item in scenes} == {("observer", "other")}
    assert {item.self_position for item in scenes} == {"unspecified"}
    assert {item.grounded_evidence_ids for item in scenes} == {
        ("evidence_image",)
    }
    assert "renderer-only crown" not in {
        element for item in scenes for element in item.inferred_elements
    }


def test_transparent_valuator_records_all_dimensions_and_unique_native_option() -> None:
    result = process_emocio(_scene(), _world())
    valuations = result.visual_state.option_valuations
    scores = {
        item.option_id: aggregate_option_valuation(item) for item in valuations
    }

    assert all(
        tuple(dimension.name for dimension in item.dimensions)
        == EMOCIO_VALUATION_DIMENSIONS
        for item in valuations
    )
    assert scores["option_desired"] > scores["option_broken"]
    assert result.native_conclusion.option_id == "option_desired"
    assert result.native_conclusion.decisive_rollout_scene_id == next(
        item.scene_id
        for item in result.visual_state.option_rollouts
        if item.option_id == "option_desired"
    )
    result.native_conclusion.validate_against(result.packet, result.visual_state)


def test_exact_policy_tie_abstains_instead_of_using_option_order() -> None:
    neutral_world = _world(desired=(), broken=()).model_copy(
        update={
            "social_identity_motifs": (),
            "attraction_patterns": (),
            "motor_patterns": (),
        }
    )
    result = process_emocio(_scene(), neutral_world)

    assert result.native_conclusion.option_id is None
    assert result.native_conclusion.abstains is True
    assert result.native_conclusion.valuation_dimensions == ()
    assert result.policy.tied_option_ids == ("option_broken", "option_desired")


def test_no_options_produces_explicit_abstention() -> None:
    scene = _scene().model_copy(update={"options": ()})
    result = process_emocio(scene, _world())

    assert result.visual_state.option_rollouts == ()
    assert result.visual_state.option_valuations == ()
    assert result.native_conclusion.option_id is None
    assert result.native_conclusion.abstains is True
    assert result.native_conclusion.intensity == 0.0


def test_replay_has_stable_content_ids_and_canonical_json() -> None:
    first = process_emocio(_scene(reverse_options=False), _world())
    replay = process_emocio(_scene(reverse_options=False), _world())

    assert replay.packet == first.packet
    assert replay.visual_state == first.visual_state
    assert replay.native_conclusion == first.native_conclusion
    assert replay.packet.canonical_json_bytes() == first.packet.canonical_json_bytes()
    assert replay.visual_state.content_hash() == first.visual_state.content_hash()
    assert replay.native_conclusion.content_hash() == first.native_conclusion.content_hash()
    replay.validate_against(_scene(), _world())


def test_input_order_does_not_choose_an_option() -> None:
    forward = process_emocio(_scene(reverse_options=False), _world())
    reversed_input = process_emocio(_scene(reverse_options=True), _world())

    assert tuple(
        item.option_id for item in reversed_input.visual_state.option_rollouts
    ) == ("option_broken", "option_desired")
    assert reversed_input.native_conclusion.option_id == forward.native_conclusion.option_id


def test_raw_text_keywords_do_not_drive_the_native_policy() -> None:
    first = process_emocio(
        _scene(
            raw_input="varno mirno dobro",
            text_evidence="nevarno poru\u0161eno slabo",
        ),
        _world(),
    )
    second = process_emocio(
        _scene(
            raw_input="nevarno poru\u0161eno slabo",
            text_evidence="varno mirno dobro",
        ),
        _world(),
    )

    assert first.native_conclusion.option_id == "option_desired"
    assert second.native_conclusion.option_id == "option_desired"
    assert first.policy.aggregate_scores == second.policy.aggregate_scores


def test_native_conclusion_exists_before_optional_render(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[str] = []
    original = processor_module._native_conclusion

    def traced_native_conclusion(**kwargs):
        observed.append("native_conclusion")
        return original(**kwargs)

    class TracedRenderer:
        def render(self, scenes: tuple, *, seed: int) -> tuple[ImageArtifact, ...]:
            del scenes, seed
            observed.append("render")
            return ()

    monkeypatch.setattr(processor_module, "_native_conclusion", traced_native_conclusion)
    result = process_emocio(_scene(), _world(), renderer=TracedRenderer())

    assert observed[:2] == ["native_conclusion", "render"]
    # The final call is deterministic replay validation; it still consumes no
    # renderer output and therefore cannot revise the already-created result.
    assert observed == ["native_conclusion", "render", "native_conclusion"]
    assert result.stage_order == (
        "packet",
        "scene_graph",
        "valuation",
        "native_conclusion",
        "render",
    )
    assert "interpretation" not in result.stage_order


def test_null_renderer_is_optional_and_cannot_change_native_result() -> None:
    without_renderer = process_emocio(_scene(), _world())
    with_null = process_emocio(_scene(), _world(), renderer=NullRenderer())

    assert without_renderer.native_conclusion == with_null.native_conclusion
    assert without_renderer.visual_state == with_null.visual_state
    assert with_null.rendered_images == ()
    assert with_null.renderer_warning is None


def test_renderer_added_detail_is_ungrounded_and_cannot_change_option() -> None:
    native_only = process_emocio(_scene(), _world())
    rendered = process_emocio(
        _scene(),
        _world(),
        renderer=AddedDetailRenderer(),
        render_seed=17,
    )

    assert rendered.native_conclusion == native_only.native_conclusion
    assert rendered.visual_state == native_only.visual_state
    assert rendered.rendered_images[0].grounded is False
    assert rendered.rendered_images[0].generated_only_elements == (
        "renderer-only crown",
    )
    assert "renderer-only crown" not in {
        element
        for scene in (
            rendered.visual_state.current_scene,
            rendered.visual_state.desired_scene,
            rendered.visual_state.broken_scene,
            *rendered.visual_state.option_rollouts,
        )
        for element in (
            *scene.composition,
            *scene.inferred_elements,
        )
    }


def test_generated_image_id_cannot_be_promoted_to_grounded_scene_evidence() -> None:
    scene = _scene()
    rendered = process_emocio(
        scene,
        _world(),
        renderer=AddedDetailRenderer(),
        render_seed=17,
    )
    image_id = rendered.rendered_images[0].image_id
    forged = rendered.visual_state.current_scene.model_copy(
        update={
            "grounded_evidence_ids": (
                *rendered.visual_state.current_scene.grounded_evidence_ids,
                image_id,
            )
        }
    )

    with pytest.raises(ValueError, match="grounded evidence"):
        forged.validate_against(scene)


@pytest.mark.parametrize(
    "renderer",
    [ExplodingRenderer(), InvalidLineageRenderer(), InvalidSeedRenderer()],
)
def test_renderer_failure_or_invalid_lineage_does_not_destroy_native_result(
    renderer,
) -> None:
    expected = process_emocio(_scene(), _world())
    result = process_emocio(_scene(), _world(), renderer=renderer)

    assert result.native_conclusion == expected.native_conclusion
    assert result.visual_state == expected.visual_state
    assert result.rendered_images == ()
    assert result.renderer_warning is not None
    assert "after native conclusion" in result.renderer_warning


def test_result_world_lineage_rejects_a_different_world() -> None:
    result = process_emocio(_scene(), _world())
    changed_world = _world(desired=("another future",))

    with pytest.raises(ValueError, match="world lineage"):
        result.validate_against(_scene(), changed_world)

    tampered = replace(result, source_world_hash="0" * 64)
    with pytest.raises(ValueError, match="world lineage"):
        tampered.validate_against(_scene(), _world())


def test_processor_facade_is_deterministic_and_has_no_racio_interpretation_api() -> None:
    processor = DeterministicEmocioProcessor(renderer=NullRenderer(), render_seed=17)
    first = processor.process(_scene(), _world())
    replay = processor.process(_scene(), _world())

    assert first == replay
    assert "interpret" not in DeterministicEmocioProcessor.__dict__
    assert "RacioInterpretation" not in processor_module.__dict__


def test_image_artifact_cannot_claim_grounded_true() -> None:
    with pytest.raises(ValidationError):
        ImageArtifact(
            image_id="image_invalid_grounded",
            request_id="request",
            render_call_id="call",
            source_spec_id="scene",
            provider_id="renderer",
            seed=1,
            input_spec_hash="1" * 64,
            content_sha256="2" * 64,
            media_type="image/png",
            grounded=True,
            prompt="",
            negative_prompt="",
            path="emocio/images/invalid.png",
            width=32,
            height=32,
            generated_only_elements=(),
        )
