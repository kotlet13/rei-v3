from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path

import pytest

from app.backend.rei.emocio import build_emocio_packet
from app.backend.rei.models.instinkt import InstinktSimulationConfig
from app.backend.rei.models.provider import ensure_call_record_contract
from app.backend.rei.providers import (
    DeterministicEmocioNativeProvider,
    DeterministicInstinktNativeProvider,
    DeterministicRacioNativeProvider,
    build_deterministic_native_providers,
    build_native_call_spec,
    emocio_world_input_id,
)
from app.backend.rei.providers import deterministic as deterministic_module
from tests.rei.test_emocio import _scene as emocio_scene
from tests.rei.test_emocio import _world as emocio_world
from tests.rei.test_instinkt import _body as instinkt_body
from tests.rei.test_instinkt import _effect as instinkt_effect
from tests.rei.test_instinkt import _packet as instinkt_packet
from tests.rei.test_instinkt import _scene as instinkt_scene
from tests.rei.test_racio import _packet as racio_packet


STARTED_AT = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
FINISHED_AT = STARTED_AT + timedelta(milliseconds=1)


def test_provider_set_is_stable_model_free_and_profile_blind() -> None:
    first = build_deterministic_native_providers()
    second = build_deterministic_native_providers()

    assert first.identities == second.identities
    assert tuple(identity.kind for identity in first.identities) == (
        "text_reasoner",
        "visual_world_model",
        "body_dynamics",
    )
    assert all(identity.uses_model is False for identity in first.identities)
    assert all(identity.model is None for identity in first.identities)
    assert all(identity.model_revision is None for identity in first.identities)

    for provider_type in (
        DeterministicRacioNativeProvider,
        DeterministicEmocioNativeProvider,
        DeterministicInstinktNativeProvider,
    ):
        parameters = inspect.signature(provider_type.execute).parameters
        assert not any("profile" in name.casefold() for name in parameters)
        assert not any("character" in name.casefold() for name in parameters)

    source = Path(deterministic_module.__file__).read_text(encoding="utf-8")
    imported_modules = {
        node.module or ""
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    assert not any("character" in module for module in imported_modules)


def test_racio_execution_closes_one_exact_producer_call() -> None:
    provider = DeterministicRacioNativeProvider()
    packet = racio_packet()
    inputs = provider.required_input_artifact_ids(packet)
    call = build_native_call_spec(
        identity=provider.identity,
        request_id=packet.packet_id,
        input_artifact_ids=inputs,
    )

    execution = provider.execute(
        packet,
        call=call,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    ensure_call_record_contract(execution.call_spec, execution.call_record)
    assert execution.conclusion.mind == "R"
    assert execution.call_record.status == "succeeded"
    assert execution.call_record.output_artifact_ids == (
        execution.conclusion.conclusion_id,
    )
    assert execution.call_record.provider == provider.identity
    assert execution.call_record.seed is None
    assert execution.call_record.parameters == ()

    extra_profile_input = build_native_call_spec(
        identity=provider.identity,
        request_id=packet.packet_id,
        input_artifact_ids=(*inputs, "character_profile_must_not_enter_native_call"),
    )
    with pytest.raises(ValueError, match="exactly its profile-blind inputs"):
        provider.execute(
            packet,
            call=extra_profile_input,
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
        )

    forged_call_id = call.model_copy(update={"call_id": "forged_native_call_id"})
    with pytest.raises(ValueError, match="canonical call spec"):
        provider.execute(
            packet,
            call=forged_call_id,
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
        )


def test_emocio_execution_exposes_packet_and_visual_intermediates_without_rendering() -> None:
    provider = DeterministicEmocioNativeProvider()
    scene = emocio_scene()
    world = emocio_world()
    packet = build_emocio_packet(scene)
    call = build_native_call_spec(
        identity=provider.identity,
        request_id=packet.packet_id,
        input_artifact_ids=provider.required_input_artifact_ids(scene, world),
    )

    execution = provider.execute(
        scene,
        world,
        call=call,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    ensure_call_record_contract(execution.call_spec, execution.call_record)
    assert execution.packet == packet
    assert execution.visual_state == execution.processing.visual_state
    assert execution.conclusion == execution.processing.native_conclusion
    assert execution.processing.rendered_images == ()
    assert execution.processing.render_batch is None
    assert "render" not in execution.processing.stage_order
    assert execution.call_record.output_artifact_ids == (
        execution.conclusion.conclusion_id,
    )


def test_emocio_call_identity_closes_over_world_content_not_caller_chosen_id() -> None:
    provider = DeterministicEmocioNativeProvider()
    scene = emocio_scene()
    first_world = emocio_world()
    second_world = first_world.model_copy(
        update={"desired_scenes": (*first_world.desired_scenes, "different world")}
    )

    first_inputs = provider.required_input_artifact_ids(scene, first_world)
    second_inputs = provider.required_input_artifact_ids(scene, second_world)
    first_call = build_native_call_spec(
        identity=provider.identity,
        request_id=build_emocio_packet(scene).packet_id,
        input_artifact_ids=first_inputs,
    )
    second_call = build_native_call_spec(
        identity=provider.identity,
        request_id=build_emocio_packet(scene).packet_id,
        input_artifact_ids=second_inputs,
    )

    assert first_world.world_id == second_world.world_id
    assert emocio_world_input_id(first_world) in first_inputs
    assert emocio_world_input_id(second_world) in second_inputs
    assert emocio_world_input_id(first_world) != emocio_world_input_id(second_world)
    assert first_call.call_id != second_call.call_id


def test_instinkt_execution_records_config_effects_and_replays_independent_of_order() -> None:
    provider = DeterministicInstinktNativeProvider()
    scene = instinkt_scene()
    body = instinkt_body()
    packet = instinkt_packet(scene, body)
    effects = (
        instinkt_effect(packet, scene.options[0].option_id, base_loss=0.1),
        instinkt_effect(packet, scene.options[1].option_id, base_loss=0.8),
    )
    config = InstinktSimulationConfig.create()
    inputs = provider.required_input_artifact_ids(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=effects,
        config=config,
    )
    call = build_native_call_spec(
        identity=provider.identity,
        request_id=packet.packet_id,
        input_artifact_ids=inputs,
    )

    execution = provider.execute(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=tuple(reversed(effects)),
        config=config,
        call=call,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )
    replay = provider.execute(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=effects,
        config=config,
        call=call,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    ensure_call_record_contract(execution.call_spec, execution.call_record)
    assert execution == replay
    assert execution.processing.config == config
    assert execution.packet == packet
    assert execution.source_body_state == body
    assert tuple(effect.option_id for effect in execution.option_effects) == tuple(
        sorted(option.option_id for option in scene.options)
    )
    assert len(execution.rollouts) == len(scene.options)
    assert execution.conclusion == execution.processing.conclusion
    assert execution.call_record.output_artifact_ids == (
        execution.conclusion.conclusion_id,
    )
