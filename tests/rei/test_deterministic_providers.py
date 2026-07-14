from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path

import pytest

from app.backend.rei.emocio import (
    DeterministicEmocioProcessor,
    EmocioProcessorRuntimeConfig,
    build_emocio_packet,
)
from app.backend.rei.ids import canonical_json_bytes
from app.backend.rei.models.instinkt import InstinktSimulationConfig
from app.backend.rei.models.provider import ProviderCallSpec, ensure_call_record_contract
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
from tests.rei.test_emocio_visual_integration import _visual_dependencies
from tests.rei.test_instinkt import _body as instinkt_body
from tests.rei.test_instinkt import _effect as instinkt_effect
from tests.rei.test_instinkt import _packet as instinkt_packet
from tests.rei.test_instinkt import _scene as instinkt_scene
from tests.rei.test_racio import _packet as racio_packet


STARTED_AT = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
FINISHED_AT = STARTED_AT + timedelta(milliseconds=1)


def _replace_parameter(
    call: ProviderCallSpec,
    name: str,
    value: object,
) -> ProviderCallSpec:
    encoded = canonical_json_bytes(value).decode("utf-8")
    parameters = tuple(
        parameter.model_copy(update={"canonical_json_value": encoded})
        if parameter.name == name
        else parameter
        for parameter in call.parameters
    )
    assert parameters != call.parameters
    return call.model_copy(update={"parameters": parameters})


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
    assert provider.identity.provider_id == "provider_fd6c527f3612bfa8f3d258aba6d16781"
    assert provider.identity.implementation_revision == "b11-v1"
    assert provider.build_call_spec(scene, world, packet) == call
    assert call.call_id == "provider_call_b929f08347496ad95e97100b716ac9b5"
    assert (
        execution.conclusion.conclusion_id
        == "emocio_conclusion_a4af7e2ff17076a88b812ad9b4ae2c0a"
    )
    assert call.seed is None
    assert call.parameters == ()
    assert execution.runtime_config is None
    assert execution.processing_artifact is None
    assert execution.binary_snapshots == ()


def test_configured_structured_emocio_publishes_replayable_processing_artifact() -> None:
    processor = DeterministicEmocioProcessor()
    providers = build_deterministic_native_providers(
        emocio_processor=processor,
    )
    provider = providers.emocio
    scene = emocio_scene()
    world = emocio_world()
    packet = build_emocio_packet(scene)
    runtime_config = EmocioProcessorRuntimeConfig.from_processor(processor)
    call = provider.build_call_spec(scene, world, packet)

    execution = provider.execute(
        scene,
        world,
        packet=packet,
        call=call,
        started_at=STARTED_AT,
        finished_at=FINISHED_AT,
    )

    assert provider.processor is processor
    assert provider.publish_runtime_config is True
    assert provider.identity.implementation_revision.startswith("c4-runtime-v1:")
    assert provider.identity != DeterministicEmocioNativeProvider().identity
    assert call.seed is None
    assert call.parameters == runtime_config.provider_parameters
    assert set(runtime_config.input_artifact_ids).issubset(call.input_artifact_ids)
    assert execution.runtime_config == runtime_config
    assert execution.processing_artifact is not None
    assert (
        execution.processing_artifact.to_result(scene, world)
        == execution.processing
    )
    assert execution.binary_snapshots == ()
    assert execution.call_record.output_artifact_ids == (
        execution.conclusion.conclusion_id,
        execution.processing_artifact.result_id,
    )


def test_configured_outer_deadline_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = build_deterministic_native_providers(
        emocio_processor=DeterministicEmocioProcessor(),
    ).emocio
    scene = emocio_scene()
    world = emocio_world()
    packet = build_emocio_packet(scene)
    call = provider.build_call_spec(scene, world, packet)
    monotonic_calls = 0

    def expired_monotonic() -> float:
        nonlocal monotonic_calls
        monotonic_calls += 1
        return 100.0 if monotonic_calls == 1 else 131.0

    monkeypatch.setattr(deterministic_module.time, "monotonic", expired_monotonic)

    with pytest.raises(TimeoutError, match="outer call exceeded"):
        provider.execute(
            scene,
            world,
            packet=packet,
            call=call,
            started_at=STARTED_AT,
            finished_at=FINISHED_AT,
        )


def test_adversarial_renderer_equality_cannot_enter_legacy_execution() -> None:
    class EqualToNoneRenderer:
        calls = 0

        def __eq__(self, other: object) -> bool:
            return other is None

        def render(self, scenes, *, seed):
            del scenes, seed
            self.calls += 1
            raise AssertionError("unbound renderer must never execute")

    renderer = EqualToNoneRenderer()
    provider = DeterministicEmocioNativeProvider(
        processor=DeterministicEmocioProcessor(renderer=renderer),
    )

    assert provider._is_legacy_default is False
    with pytest.raises(ValueError, match="current-first renderer"):
        _ = provider.identity
    assert renderer.calls == 0


def test_configured_visual_call_tampering_fails_before_renderer() -> None:
    _, renderer, encoder, policy, approval, authority = _visual_dependencies()
    processor = DeterministicEmocioProcessor(
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=policy,
        visual_influence_approval=approval,
        visual_influence_authority=authority,
        encoding_timeout_seconds=7.0,
    )
    provider = DeterministicEmocioNativeProvider(processor=processor)
    scene = emocio_scene()
    world = emocio_world()
    packet = build_emocio_packet(scene)
    runtime_config = provider.runtime_config
    call = provider.build_call_spec(scene, world, packet)
    renderer_provider = renderer._provider
    calls_before = renderer_provider.calls

    assert call.seed == runtime_config.render_seed == 41
    assert runtime_config.encoding_timeout_seconds == 7.0
    assert call.timeout_seconds == runtime_config.outer_timeout_seconds_for(
        scene_count=3 + len(scene.options)
    )
    assert call.parameters == runtime_config.provider_parameters
    assert set(runtime_config.input_artifact_ids).issubset(call.input_artifact_ids)
    assert runtime_config.visual_policy_config_id is not None
    assert runtime_config.visual_influence_approval_id is not None
    assert runtime_config.visual_influence_authority_id is not None

    without_config_id = call.model_copy(
        update={
            "input_artifact_ids": tuple(
                artifact_id
                for artifact_id in call.input_artifact_ids
                if artifact_id != runtime_config.config_id
            )
        }
    )
    without_policy_id = call.model_copy(
        update={
            "input_artifact_ids": tuple(
                artifact_id
                for artifact_id in call.input_artifact_ids
                if artifact_id != runtime_config.visual_policy_config_id
            )
        }
    )
    without_approval_id = call.model_copy(
        update={
            "input_artifact_ids": tuple(
                artifact_id
                for artifact_id in call.input_artifact_ids
                if artifact_id != runtime_config.visual_influence_approval_id
            )
        }
    )
    without_authority_id = call.model_copy(
        update={
            "input_artifact_ids": tuple(
                artifact_id
                for artifact_id in call.input_artifact_ids
                if artifact_id != runtime_config.visual_influence_authority_id
            )
        }
    )
    tampered_calls = (
        _replace_parameter(call, "emocio.cognition_mode", "render_observe"),
        call.model_copy(update={"seed": 42}),
        call.model_copy(update={"timeout_seconds": 8.0}),
        without_config_id,
        _replace_parameter(
            call,
            "emocio.processor_runtime_config_hash",
            "f" * 64,
        ),
        _replace_parameter(call, "emocio.renderer_binding_hash", "f" * 64),
        _replace_parameter(call, "emocio.encoder_provider_id", "forged_encoder"),
        without_policy_id,
        without_approval_id,
        without_authority_id,
    )

    for tampered in tampered_calls:
        with pytest.raises(ValueError):
            provider.execute(
                scene,
                world,
                packet=packet,
                call=tampered,
                started_at=STARTED_AT,
                finished_at=FINISHED_AT,
            )
        assert renderer_provider.calls == calls_before


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
