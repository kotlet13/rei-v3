from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.emocio import (
    BilingualStructuredScenePromptCompiler,
    CurrentFirstEmocioRenderer,
    CurrentFirstRolloutConfig,
    DeterministicEmocioProcessor,
    DiffusersImageRenderer,
    LocalPngArtifactStore,
    RenderSettings,
    VisualPromptProfile,
    VisualValuationPolicy,
    VisualValuationPolicyConfig,
    process_emocio,
)
from app.backend.rei.emocio.runtime import (
    EmocioBinarySnapshot,
    EmocioProcessingArtifact,
    EmocioProcessorRuntimeConfig,
    binary_snapshots_from_processing,
    nested_provider_calls,
    validate_binary_snapshots_against_processing,
    validate_processing_runtime_closure,
)
from app.backend.rei.models.provider import ProviderIdentity
from app.backend.rei.models.rendering import ImagePipelineSpec
from app.backend.rei.providers.protocols import ImageEncodingSpec
from tests.rei.test_emocio import _scene, _world
from tests.rei.test_emocio_current_first_renderer import (
    RecordingBackend,
    _identity as renderer_identity,
    _png,
)
from tests.rei.test_emocio_visual_integration import DeterministicVisualEncoder


def _settings(*, width: int = 4) -> RenderSettings:
    return RenderSettings(
        width=width,
        height=3,
        num_inference_steps=2,
        guidance_scale=1.0,
        negative_prompt="",
        timeout_seconds=1.0,
    )


def _pipelines(
    *,
    text_revision: str = "text-v1",
    image_revision: str = "image-v1",
) -> dict[str, ImagePipelineSpec]:
    return {
        "text_to_image": ImagePipelineSpec(
            implementation="tests.RuntimeTextPipeline",
            implementation_revision=text_revision,
        ),
        "image_to_image": ImagePipelineSpec(
            implementation="tests.RuntimeImagePipeline",
            implementation_revision=image_revision,
        ),
    }


def _renderer(
    root: Path,
    *,
    identity: ProviderIdentity | None = None,
    settings: RenderSettings | None = None,
    rollout: CurrentFirstRolloutConfig | None = None,
    prompt_compiler: object | None = None,
    text_revision: str = "text-v1",
    image_revision: str = "image-v1",
) -> CurrentFirstEmocioRenderer:
    provider = DiffusersImageRenderer(
        identity=identity or renderer_identity(),
        backend=RecordingBackend(),
        artifact_store=LocalPngArtifactStore(root),
        pipeline_specs=_pipelines(
            text_revision=text_revision,
            image_revision=image_revision,
        ),
    )
    return CurrentFirstEmocioRenderer(
        provider=provider,
        settings=settings or _settings(),
        rollout=rollout,
        prompt_compiler=(
            prompt_compiler
            if prompt_compiler is not None
            else BilingualStructuredScenePromptCompiler(
                VisualPromptProfile.create(
                    language="en",
                    style_id="runtime-test-default-style-v1",
                    style_directive="Use the bounded runtime test composition.",
                )
            )
        ),
    )


def _policy(*, desired_weight: float = 1.0) -> VisualValuationPolicyConfig:
    return VisualValuationPolicyConfig.create(
        policy=VisualValuationPolicy.create(
            structured_weight=0.0,
            desired_similarity_weight=desired_weight,
            broken_avoidance_weight=1.0,
            seed_consistency_penalty=0.0,
            uncertainty_penalty=0.0,
        )
    )


def _vectors() -> dict[str, tuple[float, ...]]:
    baseline = process_emocio(_scene(), _world())
    scenes = (
        baseline.visual_state.current_scene,
        baseline.visual_state.desired_scene,
        baseline.visual_state.broken_scene,
        *baseline.visual_state.option_rollouts,
    )
    return {
        scene.scene_id: ((1.0, 0.0) if index % 2 == 0 else (0.0, 1.0))
        for index, scene in enumerate(scenes)
    }


class _AlternativeEncoder(DeterministicVisualEncoder):
    def encoding_spec(self) -> ImageEncodingSpec:
        return ImageEncodingSpec(
            implementation="tests.AlternativeRuntimeEncoder",
            implementation_revision="2",
            dimensions=2,
        )


class _UnknownRenderer:
    def render(self, scenes, *, seed):
        del scenes, seed
        raise AssertionError("must not execute")


class _UnknownCompiler:
    def compile(self, scene):
        return scene.scene_id


def test_default_config_normalizes_and_excludes_inactive_values(tmp_path: Path) -> None:
    default = EmocioProcessorRuntimeConfig.from_processor(
        DeterministicEmocioProcessor()
    )
    unused_values_changed = EmocioProcessorRuntimeConfig.from_processor(
        DeterministicEmocioProcessor(
            render_seed=987,
            encoding_timeout_seconds=0.25,
        )
    )

    assert default == unused_values_changed
    assert default.cognition_mode == "structured_only"
    assert default.render_seed is None
    assert default.encoding_timeout_seconds is None
    assert default.renderer_binding is None
    assert default.encoder_identity is None
    assert default.encoder_spec is None
    assert default.input_artifact_ids == (default.config_id,)

    parameters = default.provider_parameters
    assert tuple(item.name for item in parameters) == tuple(
        sorted(item.name for item in parameters)
    )
    assert len({item.name for item in parameters}) == len(parameters)
    decoded = {
        item.name: json.loads(item.canonical_json_value) for item in parameters
    }
    assert decoded["emocio.cognition_mode"] == "structured_only"
    assert decoded["emocio.render_seed"] is None
    assert decoded["emocio.visual_policy_config_id"] is None
    assert default.outer_call_parameters == parameters
    assert default.outer_call_input_artifact_ids == default.input_artifact_ids
    assert default.outer_timeout_seconds_for(scene_count=5) == 30.0
    with pytest.raises(ValueError, match="positive scene count"):
        default.outer_timeout_seconds_for(scene_count=0)
    with pytest.raises(ValueError, match="positive scene count"):
        default.outer_timeout_seconds_for(scene_count=True)

    renderer = _renderer(tmp_path / "normalized-renderer")
    inferred_render = EmocioProcessorRuntimeConfig.from_processor(
        DeterministicEmocioProcessor(renderer=renderer, render_seed=19)
    )
    assert inferred_render.cognition_mode == "render_observe"
    assert inferred_render.render_seed == 19
    assert inferred_render.renderer_binding == renderer.runtime_binding()
    assert inferred_render.outer_timeout_seconds_for(scene_count=5) == 35.0


def test_runtime_config_rejects_dependency_ambiguity_and_unknown_components(
    tmp_path: Path,
) -> None:
    encoder = DeterministicVisualEncoder(_vectors())
    known_renderer = _renderer(tmp_path / "known")

    with pytest.raises(ValueError, match="structured_only"):
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=known_renderer,
                cognition_mode="structured_only",
            )
        )
    with pytest.raises(ValueError, match="render_observe"):
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=known_renderer,
                cognition_mode="render_observe",
                image_encoder=encoder,
            )
        )
    with pytest.raises(ValueError, match="verified image encoder"):
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=known_renderer,
                cognition_mode="visual_cognition",
                visual_policy_config=_policy(),
            )
        )
    with pytest.raises(ValueError, match="policy config"):
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=known_renderer,
                cognition_mode="visual_cognition",
                image_encoder=encoder,
            )
        )
    with pytest.raises(ValueError, match="supplied together"):
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=known_renderer,
                cognition_mode="visual_cognition",
                image_encoder=encoder,
                visual_policy_config=_policy(),
                visual_influence_approval=object(),  # type: ignore[arg-type]
            )
        )
    with pytest.raises(ValueError, match="current-first renderer"):
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=_UnknownRenderer(),  # type: ignore[arg-type]
                cognition_mode="render_observe",
            )
        )

    unknown_compiler_renderer = _renderer(
        tmp_path / "unknown-compiler",
        prompt_compiler=_UnknownCompiler(),
    )
    with pytest.raises(ValueError, match="binding failed closed"):
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=unknown_compiler_renderer,
                cognition_mode="render_observe",
            )
        )

    class ProcessorSubclass(DeterministicEmocioProcessor):
        def process(self, *args, **kwargs):
            raise AssertionError("hidden subclass execution must never run")

    with pytest.raises(TypeError, match="exact DeterministicEmocioProcessor"):
        EmocioProcessorRuntimeConfig.from_processor(ProcessorSubclass())


def test_config_hash_changes_for_every_renderer_and_visual_binding_mutation(
    tmp_path: Path,
) -> None:
    profile = VisualPromptProfile.create(
        language="en",
        style_id="runtime-test-style",
        style_directive="flat geometric composition",
    )
    alternate_identity = renderer_identity().model_copy(
        update={
            "provider_id": "runtime_alternate_renderer",
            "model": "test/runtime-alternate-model",
        }
    )
    renderers = (
        _renderer(tmp_path / "baseline"),
        _renderer(tmp_path / "provider", identity=alternate_identity),
        _renderer(tmp_path / "text-pipeline", text_revision="text-v2"),
        _renderer(tmp_path / "image-pipeline", image_revision="image-v2"),
        _renderer(tmp_path / "settings", settings=_settings(width=5)),
        _renderer(
            tmp_path / "rollout",
            rollout=CurrentFirstRolloutConfig(
                conditioning_method="classic_strength",
                classic_strength=0.4,
            ),
        ),
        _renderer(
            tmp_path / "compiler",
            prompt_compiler=BilingualStructuredScenePromptCompiler(profile),
        ),
    )
    render_configs = tuple(
        EmocioProcessorRuntimeConfig.from_processor(
            DeterministicEmocioProcessor(
                renderer=renderer,
                cognition_mode="render_observe",
                render_seed=31,
            )
        )
        for renderer in renderers
    )
    assert len({item.config_id for item in render_configs}) == len(render_configs)
    assert len({item.content_hash() for item in render_configs}) == len(
        render_configs
    )

    baseline_renderer = renderers[0]
    encoder = DeterministicVisualEncoder(_vectors())
    visual_processors = (
        DeterministicEmocioProcessor(
            renderer=baseline_renderer,
            cognition_mode="visual_cognition",
            render_seed=31,
            image_encoder=encoder,
            visual_policy_config=_policy(),
            encoding_timeout_seconds=2.0,
        ),
        DeterministicEmocioProcessor(
            renderer=baseline_renderer,
            cognition_mode="visual_cognition",
            render_seed=32,
            image_encoder=encoder,
            visual_policy_config=_policy(),
            encoding_timeout_seconds=2.0,
        ),
        DeterministicEmocioProcessor(
            renderer=baseline_renderer,
            cognition_mode="visual_cognition",
            render_seed=31,
            image_encoder=_AlternativeEncoder(_vectors()),
            visual_policy_config=_policy(),
            encoding_timeout_seconds=2.0,
        ),
        DeterministicEmocioProcessor(
            renderer=baseline_renderer,
            cognition_mode="visual_cognition",
            render_seed=31,
            image_encoder=encoder,
            visual_policy_config=_policy(desired_weight=0.5),
            encoding_timeout_seconds=2.0,
        ),
        DeterministicEmocioProcessor(
            renderer=baseline_renderer,
            cognition_mode="visual_cognition",
            render_seed=31,
            image_encoder=encoder,
            visual_policy_config=_policy(),
            encoding_timeout_seconds=3.0,
        ),
    )
    visual_configs = tuple(
        EmocioProcessorRuntimeConfig.from_processor(item)
        for item in visual_processors
    )
    assert len({item.config_id for item in visual_configs}) == len(visual_configs)
    assert all(
        item.visual_policy_config_id in item.input_artifact_ids
        for item in visual_configs
    )


def test_processing_artifact_round_trip_and_tamper_replay() -> None:
    scene = _scene()
    world = _world()
    result = process_emocio(scene, world)
    conclusion_bytes = result.native_conclusion.canonical_json_bytes()

    artifact = EmocioProcessingArtifact.create(result)
    restored_artifact = EmocioProcessingArtifact.model_validate_json(
        artifact.canonical_json_bytes()
    )
    restored = restored_artifact.to_result(scene, world)

    assert restored == result
    assert restored.native_conclusion.canonical_json_bytes() == conclusion_bytes
    assert EmocioProcessingArtifact.create(restored) == artifact

    forged_id = artifact.model_copy(update={"result_id": "forged_processing_result"})
    with pytest.raises(ValidationError, match="canonical content"):
        forged_id.to_result(scene, world)

    forged_conclusion = artifact.model_copy(
        update={
            "native_conclusion": artifact.native_conclusion.model_copy(
                update={"option_id": "forged_option"}
            )
        }
    )
    with pytest.raises(ValidationError, match="canonical content"):
        forged_conclusion.to_result(scene, world)


def test_binary_snapshots_and_nested_calls_close_visual_processing(
    tmp_path: Path,
) -> None:
    scene = _scene()
    world = _world()
    processor = DeterministicEmocioProcessor(
        renderer=_renderer(tmp_path / "visual"),
        cognition_mode="visual_cognition",
        render_seed=43,
        image_encoder=DeterministicVisualEncoder(_vectors()),
        visual_policy_config=_policy(),
        encoding_timeout_seconds=2.0,
    )
    runtime_config = EmocioProcessorRuntimeConfig.from_processor(processor)
    assert runtime_config.outer_timeout_seconds_for(scene_count=5) == 45.0
    result = processor.process(scene, world)

    snapshots = binary_snapshots_from_processing(result, processor)
    runtime_config = EmocioProcessorRuntimeConfig.from_processor(processor)
    assert validate_processing_runtime_closure(runtime_config, result) == (
        nested_provider_calls(result)
    )
    validate_binary_snapshots_against_processing(result, snapshots)
    with pytest.raises(ValueError, match="cognition mode"):
        validate_processing_runtime_closure(
            EmocioProcessorRuntimeConfig.from_processor(
                DeterministicEmocioProcessor()
            ),
            result,
        )
    with pytest.raises(ValueError, match="Renderer warning"):
        replace(
            result,
            renderer_warning="secret=C4-RUNTIME-WARNING",
        ).validate_against(scene, world)
    image_snapshots = tuple(item for item in snapshots if item.role == "image")
    vector_snapshots = tuple(item for item in snapshots if item.role == "vector")
    assert len(image_snapshots) == len(result.rendered_images)
    assert len(vector_snapshots) == len(result.visual_observations)
    assert {item.artifact_id for item in vector_snapshots} == {
        item.encoding.encoding_id for item in result.visual_observations
    }
    assert len({item.relative_path for item in vector_snapshots}) < len(
        vector_snapshots
    )
    assert tuple(item.relative_path for item in snapshots) == tuple(
        sorted(item.relative_path for item in snapshots)
    )
    assert all(
        hashlib.sha256(item.content).hexdigest() == item.content_sha256
        for item in snapshots
    )
    first_image = image_snapshots[0]
    alternate_png = _png(
        first_image.width,
        first_image.height,
        (220, 15, 45, 255),
    )
    altered_snapshot = EmocioBinarySnapshot(
        artifact_id=first_image.artifact_id,
        role="image",
        relative_path="emocio/images/altered.png",
        content_sha256=hashlib.sha256(alternate_png).hexdigest(),
        content=alternate_png,
        width=first_image.width,
        height=first_image.height,
    )
    altered_snapshots = tuple(
        sorted(
            (
                altered_snapshot if item is first_image else item
                for item in snapshots
            ),
            key=lambda item: (item.relative_path, item.artifact_id),
        )
    )
    with pytest.raises(ValueError, match="processing provenance"):
        validate_binary_snapshots_against_processing(result, altered_snapshots)
    with pytest.raises(ValueError, match="Image snapshot requires"):
        EmocioBinarySnapshot(
            artifact_id=first_image.artifact_id,
            role="image",
            relative_path="emocio/images/nested/forbidden.png",
            content_sha256=first_image.content_sha256,
            content=first_image.content,
            width=first_image.width,
            height=first_image.height,
        )

    specs, records, renderer_ids, encoder_ids = nested_provider_calls(result)
    assert len(specs) == len(records) == len(renderer_ids) + len(encoder_ids)
    assert len(renderer_ids) == len(result.render_batch.items)  # type: ignore[union-attr]
    assert len(encoder_ids) == len(result.visual_observations)
    assert tuple(item.call_id for item in specs) == (
        *renderer_ids,
        *encoder_ids,
    )
    assert tuple(item.call_id for item in records) == tuple(
        item.call_id for item in specs
    )

    assert binary_snapshots_from_processing(
        process_emocio(scene, world),
        DeterministicEmocioProcessor(),
    ) == ()
    assert nested_provider_calls(process_emocio(scene, world)) == ((), (), (), ())

    png = _png(2, 2)
    with pytest.raises((ValueError, ValidationError), match="SHA-256"):
        EmocioBinarySnapshot(
            artifact_id="image_bad_hash",
            role="image",
            relative_path="emocio/images/bad.png",
            content_sha256="0" * 64,
            content=png,
            width=2,
            height=2,
        )
    vector = vector_snapshots[0]
    with pytest.raises(ValueError, match="dimensions"):
        EmocioBinarySnapshot(
            artifact_id=vector.artifact_id,
            role="vector",
            relative_path=vector.relative_path,
            content_sha256=vector.content_sha256,
            content=vector.content,
            dimensions=vector.dimensions + 1,  # type: ignore[operator]
        )


def test_nested_calls_include_failed_encoder_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encoder = DeterministicVisualEncoder(_vectors())
    original_encode = encoder.encode
    attempts = 0

    def fail_second(image, *, call):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise RuntimeError("provider detail must remain inside typed failure")
        return original_encode(image, call=call)

    monkeypatch.setattr(encoder, "encode", fail_second)
    processor = DeterministicEmocioProcessor(
        renderer=_renderer(tmp_path / "failed-encoder"),
        cognition_mode="visual_cognition",
        render_seed=47,
        image_encoder=encoder,
        visual_policy_config=_policy(),
        encoding_timeout_seconds=2.0,
    )
    result = processor.process(_scene(), _world())
    assert result.visual_failure is not None
    assert result.visual_failure.stage == "encoding"
    assert result.visual_failure.attempted_call_record is not None

    specs, records, renderer_ids, encoder_ids = nested_provider_calls(result)
    assert len(renderer_ids) == 5
    assert len(encoder_ids) == 2
    assert len(specs) == len(records) == 7
    assert records[-1] == result.visual_failure.attempted_call_record
    assert records[-1].status == "failed"
    assert records[-1].output_artifact_ids == ()
