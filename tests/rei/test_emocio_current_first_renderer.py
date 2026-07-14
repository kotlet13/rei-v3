from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.emocio import (
    CurrentFirstEmocioRenderer,
    CurrentFirstRolloutConfig,
    DiffusersImageRenderer,
    EmocioRenderer,
    LocalPngArtifactStore,
    RenderSettings,
    derive_scene_seed,
)
from app.backend.rei.emocio.current_first_renderer import (
    CurrentFirstRendererRuntimeBinding,
)
from app.backend.rei.emocio.prompting import (
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from app.backend.rei.emocio.renderer import MaterializedEmocioRenderer
from app.backend.rei.models.emocio import VisualSceneSpec
from app.backend.rei.models.provider import ProviderIdentity
from app.backend.rei.models.rendering import (
    ImagePipelineSpec,
    ImageRenderRequest,
    ImageSourceReference,
)


def _png(
    width: int,
    height: int,
    rgba: tuple[int, int, int, int] = (31, 83, 149, 255),
) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanline = bytes((0,)) + bytes(rgba) * width
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(scanline * height, level=9)),
            chunk(b"IEND", b""),
        )
    )


def _scene_spec(
    scene_kind: str,
    *,
    scene_id: str,
    option_id: str | None = None,
) -> VisualSceneSpec:
    return VisualSceneSpec(
        scene_id=scene_id,
        scene_kind=scene_kind,
        option_id=option_id,
        entities=("observer",),
        self_position="center",
        attention_structure=(),
        group_belonging="present",
        status_relations=(),
        movement=(),
        composition=(scene_kind,),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=(),
        inferred_elements=(),
    )


def _scenes() -> tuple[VisualSceneSpec, ...]:
    return (
        _scene_spec("current", scene_id="current_scene"),
        _scene_spec("desired", scene_id="desired_scene"),
        _scene_spec("broken", scene_id="broken_scene"),
        _scene_spec(
            "option_rollout",
            scene_id="rollout_a_scene",
            option_id="option_a",
        ),
        _scene_spec(
            "option_rollout",
            scene_id="rollout_b_scene",
            option_id="option_b",
        ),
    )


def _identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="current_first_test_renderer",
        kind="image_renderer",
        implementation="tests.rei.CurrentFirstRecordingBackend",
        implementation_revision="1",
        uses_model=True,
        model="test/current-first-model",
        model_revision="0123456789abcdef0123456789abcdef01234567",
    )


def _settings() -> RenderSettings:
    return RenderSettings(
        width=4,
        height=3,
        num_inference_steps=2,
        guidance_scale=1.0,
        negative_prompt="",
        timeout_seconds=1.0,
    )


class RecordingBackend:
    def __init__(self, *, fail_scene_id: str | None = None) -> None:
        self.fail_scene_id = fail_scene_id
        self.calls: list[tuple[ImageRenderRequest, bytes | None]] = []

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        self.calls.append((request, source_png))
        if request.source_spec_id == self.fail_scene_id:
            raise RuntimeError("synthetic current render failure")
        return _png(request.width, request.height)


def _renderer(
    tmp_path: Path,
    backend: RecordingBackend,
    *,
    rollout: CurrentFirstRolloutConfig | None = None,
    prompt_compiler: BilingualStructuredScenePromptCompiler | None = None,
) -> tuple[CurrentFirstEmocioRenderer, LocalPngArtifactStore]:
    store = LocalPngArtifactStore(tmp_path / "artifacts")
    provider = DiffusersImageRenderer(
        identity=_identity(),
        backend=backend,
        artifact_store=store,
    )
    return (
        CurrentFirstEmocioRenderer(
            provider=provider,
            settings=_settings(),
            rollout=rollout,
            prompt_compiler=prompt_compiler,
        ),
        store,
    )


def test_current_first_success_reuses_one_verified_current_artifact(
    tmp_path: Path,
) -> None:
    scenes = _scenes()
    backend = RecordingBackend()
    renderer, store = _renderer(tmp_path, backend)

    assert isinstance(renderer, EmocioRenderer)
    batch = renderer.render(scenes, seed=71)

    assert batch.status == "succeeded"
    assert batch.source_spec_ids == tuple(scene.scene_id for scene in scenes)
    assert tuple(item.request.source_spec_id for item in batch.items) == (
        batch.source_spec_ids
    )
    assert tuple(request.source_spec_id for request, _ in backend.calls) == (
        batch.source_spec_ids
    )

    current_item = batch.items[0]
    current_artifact = current_item.artifact
    assert current_artifact is not None
    assert isinstance(renderer, MaterializedEmocioRenderer)
    assert current_item.request.mode == "text_to_image"
    assert current_artifact.source_spec_id == scenes[0].scene_id
    current_bytes = (store.root / current_artifact.path).read_bytes()
    assert renderer.read_artifact_bytes(current_artifact) == current_bytes
    assert hashlib.sha256(current_bytes).hexdigest() == current_artifact.content_sha256
    expected_source = ImageSourceReference.from_artifact_with_scene_lineage(
        current_artifact
    )

    assert all(item.request.mode == "text_to_image" for item in batch.items[:3])
    rollout_items = batch.items[3:]
    assert len(rollout_items) == 2
    for scene, item, (_, source_png) in zip(
        scenes[3:], rollout_items, backend.calls[3:], strict=True
    ):
        request = item.request
        artifact = item.artifact
        assert artifact is not None
        assert request.mode == "image_to_image"
        assert request.conditioning_method == "reference_image"
        assert request.strength is None
        assert request.source_image == expected_source
        assert request.source_image.image_id == current_artifact.image_id
        assert request.source_image.content_sha256 == current_artifact.content_sha256
        assert request.source_image.path == current_artifact.path
        assert request.source_image.originating_scene_spec_id == scenes[0].scene_id
        assert (
            request.source_image.originating_scene_spec_hash
            == scenes[0].content_hash()
            == current_artifact.input_spec_hash
        )
        assert request.input_artifact_ids == (scene.scene_id, current_artifact.image_id)
        assert source_png == current_bytes
        assert request.seed == derive_scene_seed(71, scene.scene_id)
        assert artifact.seed == request.seed
        assert artifact.provider_id == current_artifact.provider_id
        assert artifact.model == current_artifact.model
        assert artifact.model_revision == current_artifact.model_revision

    for scene, item in zip(scenes, batch.items, strict=True):
        assert item.request.seed == derive_scene_seed(71, scene.scene_id)
        assert item.call_spec.fallback_policy.mode == "none"
        assert item.call_record.fallback is None


def test_current_first_runtime_binding_closes_every_runtime_input(
    tmp_path: Path,
) -> None:
    renderer, _ = _renderer(tmp_path, RecordingBackend())
    binding = renderer.runtime_binding()

    assert binding == renderer.runtime_binding()
    assert binding.provider_identity == _identity()
    assert binding.render_settings == _settings()
    assert binding.rollout_config == CurrentFirstRolloutConfig()
    assert binding.prompt_compiler_binding.prompt_profile_id is None
    assert binding.prompt_compiler_binding.prompt_profile is None
    assert binding.text_to_image_pipeline == ImagePipelineSpec(
        implementation=_identity().implementation,
        implementation_revision=_identity().implementation_revision,
    )
    assert binding.image_to_image_pipeline == binding.text_to_image_pipeline

    profile = VisualPromptProfile.create(
        language="en",
        style_id="runtime-binding-profile",
        style_directive="Use the exact runtime binding profile.",
    )
    profiled_renderer, _ = _renderer(
        tmp_path / "profiled",
        RecordingBackend(),
        prompt_compiler=BilingualStructuredScenePromptCompiler(profile),
    )
    profiled_compiler = profiled_renderer.runtime_binding().prompt_compiler_binding
    assert profiled_compiler.prompt_profile == profile

    values = {
        "provider_identity": binding.provider_identity,
        "text_to_image_pipeline": binding.text_to_image_pipeline,
        "image_to_image_pipeline": binding.image_to_image_pipeline,
        "render_settings": binding.render_settings,
        "rollout_config": binding.rollout_config,
        "prompt_compiler_binding": binding.prompt_compiler_binding,
    }

    def changed(**updates: object) -> CurrentFirstRendererRuntimeBinding:
        return CurrentFirstRendererRuntimeBinding.create(
            **{**values, **updates},  # type: ignore[arg-type]
        )

    changed_bindings = (
        changed(
            provider_identity=binding.provider_identity.model_copy(
                update={"provider_id": "alternate-runtime-provider"}
            )
        ),
        changed(
            text_to_image_pipeline=ImagePipelineSpec(
                implementation="tests.AlternateT2IPipeline",
                implementation_revision="2",
            )
        ),
        changed(
            image_to_image_pipeline=ImagePipelineSpec(
                implementation="tests.AlternateImg2ImgPipeline",
                implementation_revision="3",
            )
        ),
        changed(
            render_settings=RenderSettings(
                width=8,
                height=3,
                num_inference_steps=2,
                guidance_scale=1.0,
                negative_prompt="",
                timeout_seconds=1.0,
            )
        ),
        changed(
            rollout_config=CurrentFirstRolloutConfig(
                conditioning_method="classic_strength",
                classic_strength=0.4,
            )
        ),
        changed(prompt_compiler_binding=profiled_compiler),
    )
    assert len(
        {
            binding.content_hash(),
            *(item.content_hash() for item in changed_bindings),
        }
    ) == 1 + len(changed_bindings)


def test_current_first_materialization_rejects_tampered_or_unreadable_bytes(
    tmp_path: Path,
) -> None:
    renderer, store = _renderer(tmp_path, RecordingBackend())
    batch = renderer.render(_scenes(), seed=72)
    artifact = batch.items[0].artifact
    assert artifact is not None
    artifact_path = store.root / artifact.path
    artifact_path.write_bytes(_png(artifact.width, artifact.height, (9, 8, 7, 255)))

    with pytest.raises(ValueError, match="recorded SHA-256"):
        renderer.read_artifact_bytes(artifact)

    class NonMaterializedProvider:
        @property
        def identity(self) -> ProviderIdentity:
            return _identity()

        def pipeline_spec(self, mode: str) -> ImagePipelineSpec:
            del mode
            return ImagePipelineSpec(
                implementation=_identity().implementation,
                implementation_revision=_identity().implementation_revision,
            )

        def render(self, request: object, *, call: object) -> None:
            del request, call

    unmaterialized = CurrentFirstEmocioRenderer(
        provider=NonMaterializedProvider(),  # type: ignore[arg-type]
        settings=_settings(),
    )
    with pytest.raises(TypeError, match="cannot verify artifact bytes"):
        unmaterialized.read_artifact_bytes(artifact)


def test_current_first_propagates_slovenian_prompt_profile_to_every_request(
    tmp_path: Path,
) -> None:
    profile = VisualPromptProfile.create(
        language="sl",
        style_id="documentary_sl_v1",
        style_directive="Ohrani dokumentarno kompozicijo.",
    )
    compiler = BilingualStructuredScenePromptCompiler(profile)
    renderer, _ = _renderer(
        tmp_path,
        RecordingBackend(),
        prompt_compiler=compiler,
    )

    batch = renderer.render(_scenes(), seed=73)

    assert batch.status == "succeeded"
    assert len(batch.items) == len(_scenes())
    assert all(
        item.request.prompt_language == profile.language
        and item.request.style_id == profile.style_id
        and item.request.profile_hash == profile.content_hash()
        and "language_gloss=sl" in item.request.prompt
        for item in batch.items
    )
    rollout_prompts = tuple(
        item.request.prompt
        for item in batch.items
        if item.request.mode == "image_to_image"
    )
    assert rollout_prompts
    assert all(
        "Primarni slikovni popravek vidno uporabi na isti osrednji osebi" in prompt
        and "Želenega prizora ne uresniči" in prompt
        for prompt in rollout_prompts
    )


def test_current_failure_keeps_context_and_structurally_blocks_rollouts(
    tmp_path: Path,
) -> None:
    scenes = _scenes()
    backend = RecordingBackend(fail_scene_id=scenes[0].scene_id)
    renderer, _ = _renderer(tmp_path, backend)

    batch = renderer.render(scenes, seed=73)

    assert batch.status == "partial"
    assert batch.source_spec_ids == tuple(scene.scene_id for scene in scenes)
    assert tuple(request.source_spec_id for request, _ in backend.calls) == tuple(
        scene.scene_id for scene in scenes[:3]
    )
    assert tuple(item.request.source_spec_id for item in batch.items) == tuple(
        scene.scene_id for scene in scenes[:3]
    )
    assert batch.items[0].artifact is None
    assert batch.items[0].call_record.status == "failed"
    assert all(item.artifact is not None for item in batch.items[1:])
    assert tuple(
        failure.source_spec_id for failure in batch.preparation_failures
    ) == tuple(scene.scene_id for scene in scenes[3:])
    assert {
        failure.failure_code for failure in batch.preparation_failures
    } == {"current_scene_render_unavailable"}
    assert all(item.call_spec.fallback_policy.mode == "none" for item in batch.items)
    assert all(item.call_record.fallback is None for item in batch.items)


def test_current_source_preparation_warning_redacts_raw_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-secret-current-source"
    absolute_path = r"C:\Users\Kotlet\private\current.png"

    def fail_source_creation(
        cls: type[ImageSourceReference],
        artifact: object,
    ) -> ImageSourceReference:
        del cls, artifact
        raise RuntimeError(f"{secret} at {absolute_path}")

    monkeypatch.setattr(
        ImageSourceReference,
        "from_artifact_with_scene_lineage",
        classmethod(fail_source_creation),
    )
    renderer, _ = _renderer(tmp_path, RecordingBackend())

    batch = renderer.render(_scenes(), seed=77)

    assert batch.status == "partial"
    assert any(
        "preparation failed closed (current_source_preparation_failure)" in warning
        for warning in batch.warnings
    )
    persisted = batch.canonical_json_bytes().decode("utf-8")
    assert secret not in persisted
    assert absolute_path not in persisted
    assert "Kotlet" not in persisted


def test_current_first_rejects_noncanonical_option_or_role_order_before_calls(
    tmp_path: Path,
) -> None:
    scenes = _scenes()
    backend = RecordingBackend()
    renderer, _ = _renderer(tmp_path, backend)

    with pytest.raises(ValueError, match="canonical option_id order"):
        renderer.render((*scenes[:3], scenes[4], scenes[3]), seed=79)
    with pytest.raises(ValueError, match="second scene must be desired"):
        renderer.render(
            (scenes[0], scenes[2], scenes[1], *scenes[3:]),
            seed=79,
        )

    assert backend.calls == []


def test_classic_strength_rollout_is_explicit_and_reference_mode_forbids_it(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="cannot carry classic_strength"):
        CurrentFirstRolloutConfig(
            conditioning_method="reference_image",
            classic_strength=0.4,
        )
    with pytest.raises(ValidationError, match="requires an explicit strength"):
        CurrentFirstRolloutConfig(conditioning_method="classic_strength")

    backend = RecordingBackend()
    renderer, _ = _renderer(
        tmp_path,
        backend,
        rollout=CurrentFirstRolloutConfig(
            conditioning_method="classic_strength",
            classic_strength=0.35,
        ),
    )
    batch = renderer.render(_scenes(), seed=83)

    assert batch.status == "succeeded"
    for item in batch.items[3:]:
        assert item.request.conditioning_method == "classic_strength"
        assert item.request.strength == 0.35
