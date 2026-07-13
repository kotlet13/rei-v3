from __future__ import annotations

import builtins
import hashlib
import importlib
import struct
import zlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei.emocio import (
    DiffusersImageRenderer,
    DiffusersRuntimeConfig,
    LocalEmocioRenderer,
    LocalPngArtifactStore,
    NullRenderer,
    RenderSettings,
    derive_scene_seed,
    inspect_png,
    process_emocio,
)
from app.backend.rei.ids import content_id, utc_now
from app.backend.rei.models.emocio import EmocioWorld, ImageArtifact
from app.backend.rei.models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPlan,
    ProviderFallbackPolicy,
    ProviderFallbackRecord,
    ProviderIdentity,
)
from app.backend.rei.models.rendering import (
    ImagePipelineSpec,
    ImageRenderBatchOutcome,
    ImageRenderItemOutcome,
    ImageRenderRequest,
    ImageSourceReference,
)
from app.backend.rei.models.scene import (
    DecisionOption,
    EvidenceItem,
    SceneEvent,
)
from app.backend.rei.providers.protocols import (
    VisionLanguageRequest,
    VisionLanguageResult,
    validate_image_render_outcome,
)


def _png(
    width: int,
    height: int,
    rgba: tuple[int, int, int, int] = (25, 80, 140, 255),
) -> bytes:
    """Create one deterministic, valid RGBA PNG using only the stdlib."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanline = bytes((0,)) + bytes(rgba) * width
    pixels = scanline * height
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(pixels, level=9)),
            chunk(b"IEND", b""),
        )
    )


def _scene() -> SceneEvent:
    return SceneEvent(
        event_id="renderer_event",
        raw_input="A synthetic visual choice.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="renderer_evidence",
                modality="image",
                content="a grounded doorway",
                grounded=True,
                source_ref="test:renderer_event",
                confidence=1.0,
            ),
        ),
        options=(
            DecisionOption(option_id="option_broken", label="collapsed room"),
            DecisionOption(option_id="option_desired", label="future home"),
        ),
        actors=("observer",),
        constraints=("keep identity stable",),
        unknowns=("outcome",),
    )


def _world() -> EmocioWorld:
    return EmocioWorld(
        world_id="renderer_world",
        visual_memories=("remembered doorway",),
        desired_scenes=("future home",),
        broken_scenes=("collapsed room",),
        social_identity_motifs=("recognized place",),
        attraction_patterns=("future home",),
        motor_patterns=("step forward",),
    )


def _identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="fake_diffusers_renderer",
        kind="image_renderer",
        implementation="tests.rei.DeterministicPngBackend",
        implementation_revision="1",
        uses_model=True,
        model="test/image-model",
        model_revision="0123456789abcdef0123456789abcdef01234567",
    )


def _pipeline() -> ImagePipelineSpec:
    identity = _identity()
    return ImagePipelineSpec(
        implementation=identity.implementation,
        implementation_revision=identity.implementation_revision,
    )


def _settings() -> RenderSettings:
    return RenderSettings(
        width=4,
        height=3,
        num_inference_steps=2,
        guidance_scale=1.0,
        negative_prompt="test-only negative prompt",
        timeout_seconds=1.0,
    )


def _source_spec():
    return process_emocio(_scene(), _world()).visual_state.current_scene


def _no_fallback() -> ProviderFallbackPolicy:
    return ProviderFallbackPolicy(
        mode="none",
        no_fallback_reason="The deterministic test backend has no fallback.",
    )


def _call_for(
    request: ImageRenderRequest,
    *,
    request_id: str | None = None,
) -> ProviderCallSpec:
    return ProviderCallSpec(
        call_id="renderer_call",
        request_id=request_id or request.request_id,
        input_artifact_ids=request.input_artifact_ids,
        provider=request.provider,
        seed=request.seed,
        parameters=request.provider_parameters,
        timeout_seconds=1.0,
        fallback_policy=_no_fallback(),
    )


class DeterministicPngBackend:
    def __init__(
        self,
        rgba: tuple[int, int, int, int] = (25, 80, 140, 255),
    ) -> None:
        self.rgba = rgba
        self.calls: list[tuple[ImageRenderRequest, bytes | None]] = []

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        self.calls.append((request, source_png))
        return _png(request.width, request.height, self.rgba)


class ExplodingBackend:
    def __init__(self) -> None:
        self.calls = 0

    def render(
        self,
        request: ImageRenderRequest,
        *,
        source_png: bytes | None,
    ) -> bytes:
        del request, source_png
        self.calls += 1
        raise RuntimeError("synthetic backend outage")


def _provider(
    tmp_path: Path,
    backend,
) -> tuple[DiffusersImageRenderer, LocalPngArtifactStore]:
    store = LocalPngArtifactStore(tmp_path / "artifacts")
    return (
        DiffusersImageRenderer(
            identity=_identity(),
            backend=backend,
            artifact_store=store,
        ),
        store,
    )


def test_t2i_and_img2img_requests_are_content_addressed_and_strict() -> None:
    spec = _source_spec()
    common = {
        "source_spec": spec,
        "provider": _identity(),
        "pipeline": _pipeline(),
        "seed": 17,
        "prompt": "structured test scene",
        "negative_prompt": "none",
        "width": 4,
        "height": 3,
        "num_inference_steps": 2,
        "guidance_scale": 1.0,
    }
    first = ImageRenderRequest.create(mode="text_to_image", **common)
    replay = ImageRenderRequest.create(mode="text_to_image", **common)
    changed_seed = ImageRenderRequest.create(
        mode="text_to_image",
        **{**common, "seed": 18},
    )

    assert first == replay
    assert first.request_id.startswith("image_request_")
    assert changed_seed.request_id != first.request_id
    assert first.input_artifact_ids == (spec.scene_id,)
    first.validate_source_spec(spec)

    tampered = first.model_dump(mode="python", round_trip=True)
    tampered["seed"] = 99
    with pytest.raises(ValidationError, match="canonical content"):
        ImageRenderRequest.model_validate(tampered)

    source = ImageSourceReference(
        image_id="source_image",
        content_sha256="a" * 64,
        media_type="image/png",
        path="sources/source.png",
        width=4,
        height=3,
        grounded=False,
    )
    img2img = ImageRenderRequest.create(
        mode="image_to_image",
        source_image=source,
        strength=0.4,
        **common,
    )
    img2img_replay = ImageRenderRequest.create(
        mode="image_to_image",
        source_image=source,
        strength=0.4,
        **common,
    )
    assert img2img.input_artifact_ids == (spec.scene_id, source.image_id)
    assert img2img.source_image.content_sha256 == "a" * 64
    assert img2img_replay == img2img

    changed_source = source.model_copy(update={"content_sha256": "b" * 64})
    changed_img2img = ImageRenderRequest.create(
        mode="image_to_image",
        source_image=changed_source,
        strength=0.4,
        **common,
    )
    assert changed_img2img.request_id != img2img.request_id
    tampered_img2img = img2img.model_dump(mode="python", round_trip=True)
    tampered_img2img["source_image"]["content_sha256"] = "c" * 64
    with pytest.raises(ValidationError, match="canonical content"):
        ImageRenderRequest.model_validate(tampered_img2img)

    with pytest.raises(ValidationError, match="cannot carry"):
        ImageRenderRequest.create(
            mode="text_to_image",
            source_image=source,
            strength=0.4,
            **common,
        )
    with pytest.raises(ValidationError, match="require source"):
        ImageRenderRequest.create(
            mode="image_to_image",
            strength=0.4,
            **common,
        )


def test_unapproved_call_is_rejected_before_fake_backend(tmp_path: Path) -> None:
    backend = DeterministicPngBackend()
    provider, store = _provider(tmp_path, backend)
    spec = _source_spec()
    request = ImageRenderRequest.create(
        mode="text_to_image",
        source_spec=spec,
        provider=provider.identity,
        pipeline=provider.pipeline_spec("text_to_image"),
        seed=17,
        prompt="approved prompt",
        negative_prompt="",
        width=4,
        height=3,
        num_inference_steps=2,
        guidance_scale=1.0,
    )

    with pytest.raises(ValueError, match="request_id"):
        provider.render(
            request,
            call=_call_for(request, request_id="unapproved_request"),
        )

    assert backend.calls == []
    assert list(store.root.rglob("*.png")) == []


def test_fake_png_success_closes_bytes_path_dimensions_and_call_provenance(
    tmp_path: Path,
) -> None:
    backend = DeterministicPngBackend()
    provider, store = _provider(tmp_path, backend)
    renderer = LocalEmocioRenderer(provider=provider, settings=_settings())
    spec = _source_spec()

    batch = renderer.render((spec,), seed=17)

    assert batch.status == "succeeded"
    assert len(batch.items) == 1
    item = batch.items[0]
    artifact = item.artifact
    assert artifact is not None
    validate_image_render_outcome(item, source_spec=spec)
    stored_path = store.root / artifact.path
    stored_bytes = stored_path.read_bytes()
    assert stored_path.is_file()
    assert hashlib.sha256(stored_bytes).hexdigest() == artifact.content_sha256
    assert inspect_png(stored_bytes) == (artifact.width, artifact.height) == (4, 3)
    assert artifact.input_spec_hash == spec.content_hash()
    assert artifact.model == provider.identity.model
    assert artifact.model_revision == provider.identity.model_revision
    assert item.call_spec.request_id == item.request.request_id
    assert item.call_spec.input_artifact_ids == (spec.scene_id,)
    assert item.call_spec.parameters == item.request.provider_parameters
    assert item.call_record.status == "succeeded"
    assert item.call_record.output_artifact_ids == (artifact.image_id,)
    assert batch.artifacts == (artifact,)
    assert backend.calls == [(item.request, None)]

    replay = renderer.render((spec,), seed=17)
    assert replay.items[0].request == item.request
    assert replay.artifacts[0] == artifact


def test_img2img_source_bytes_and_hash_are_closed_before_backend(
    tmp_path: Path,
) -> None:
    backend = DeterministicPngBackend((160, 70, 20, 255))
    provider, store = _provider(tmp_path, backend)
    spec = _source_spec()
    source_bytes = _png(4, 3, (5, 10, 15, 255))
    stored = store.persist_png(
        "sources/base.png",
        source_bytes,
        expected_width=4,
        expected_height=3,
    )
    source = ImageSourceReference(
        image_id="source_image",
        content_sha256=stored.content_sha256,
        media_type="image/png",
        path=stored.relative_path,
        width=stored.width,
        height=stored.height,
        grounded=False,
    )
    renderer = LocalEmocioRenderer(
        provider=provider,
        settings=_settings(),
        image_to_image_sources={spec.scene_id: source},
        image_to_image_strengths={spec.scene_id: 0.35},
    )

    success = renderer.render((spec,), seed=19)
    request = success.items[0].request
    assert success.status == "succeeded"
    assert request.mode == "image_to_image"
    assert request.source_image == source
    assert request.strength == 0.35
    assert request.input_artifact_ids == (spec.scene_id, source.image_id)
    assert success.items[0].call_spec.input_artifact_ids == request.input_artifact_ids
    assert backend.calls[0][1] == source_bytes

    (store.root / source.path).write_bytes(_png(4, 3, (9, 9, 9, 255)))
    calls_before_tamper = len(backend.calls)
    failed = renderer.render((spec,), seed=19)
    assert failed.status == "failed"
    assert failed.artifacts == ()
    assert failed.items[0].failure_code == "ValueError"
    assert failed.items[0].call_record.status == "failed"
    assert len(backend.calls) == calls_before_tamper


def test_backend_failure_is_structured_and_cannot_change_native_result(
    tmp_path: Path,
) -> None:
    backend = ExplodingBackend()
    provider, _ = _provider(tmp_path, backend)
    renderer = LocalEmocioRenderer(provider=provider, settings=_settings())
    native_only = process_emocio(_scene(), _world())

    failed = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=23,
    )

    assert failed.native_conclusion == native_only.native_conclusion
    assert (
        failed.native_conclusion.content_hash()
        == native_only.native_conclusion.content_hash()
    )
    assert failed.visual_state == native_only.visual_state
    assert failed.rendered_images == ()
    assert failed.render_batch is not None
    assert failed.render_batch.status == "failed"
    assert failed.render_batch.root_seed == 23
    assert failed.renderer_warning is not None
    assert len(failed.render_batch.items) == backend.calls
    assert all(item.artifact is None for item in failed.render_batch.items)
    assert all(
        item.failure_code == "RuntimeError" for item in failed.render_batch.items
    )
    assert all(
        item.call_record.status == "failed"
        and item.call_record.output_artifact_ids == ()
        for item in failed.render_batch.items
    )
    assert failed.stage_order.index("native_conclusion") < failed.stage_order.index(
        "render"
    )
    failed.validate_against(_scene(), _world())


def test_invalid_provider_outcome_is_quarantined(tmp_path: Path) -> None:
    backend = DeterministicPngBackend()
    valid_provider, _ = _provider(tmp_path, backend)

    class TamperingProvider:
        @property
        def identity(self) -> ProviderIdentity:
            return valid_provider.identity

        def pipeline_spec(self, mode):
            return valid_provider.pipeline_spec(mode)

        def render(self, request: ImageRenderRequest, *, call: ProviderCallSpec):
            outcome = valid_provider.render(request, call=call)
            assert outcome.artifact is not None
            invalid_artifact = outcome.artifact.model_copy(
                update={"input_spec_hash": "0" * 64}
            )
            return outcome.model_copy(update={"artifact": invalid_artifact})

    renderer = LocalEmocioRenderer(
        provider=TamperingProvider(),
        settings=_settings(),
    )
    batch = renderer.render((_source_spec(),), seed=29)

    assert len(backend.calls) == 1
    assert batch.status == "failed"
    assert batch.artifacts == ()
    assert batch.items[0].artifact is None
    assert batch.items[0].failure_code == "invalid_or_failed_provider_outcome"
    assert batch.items[0].call_record.output_artifact_ids == ()


def test_adversarial_caption_cannot_mutate_native_conclusion_or_scene_facts(
    tmp_path: Path,
) -> None:
    backend = DeterministicPngBackend()
    provider, _ = _provider(tmp_path, backend)
    rendered = process_emocio(
        _scene(),
        _world(),
        renderer=LocalEmocioRenderer(provider=provider, settings=_settings()),
        render_seed=31,
    )
    image = rendered.rendered_images[0]
    vlm = ProviderIdentity(
        provider_id="synthetic_vlm",
        kind="vision_language",
        implementation="tests.synthetic.CaptionOnlyVlm",
        implementation_revision="1",
    )
    request = VisionLanguageRequest(
        request_id="caption_request",
        artifact_ids=(image.image_id,),
        question="Describe renderer-added details.",
        language="en",
    )
    call = ProviderCallSpec(
        call_id="caption_call",
        request_id=request.request_id,
        input_artifact_ids=request.artifact_ids,
        provider=vlm,
        timeout_seconds=1.0,
        fallback_policy=_no_fallback(),
    )
    record = ProviderCallRecord(
        call_id=call.call_id,
        spec_hash=call.content_hash(),
        request_id=call.request_id,
        input_artifact_ids=call.input_artifact_ids,
        provider=call.provider,
        timeout_seconds=call.timeout_seconds,
        started_at=rendered.render_batch.items[0].call_record.started_at,
        primary_finished_at=rendered.render_batch.items[0].call_record.finished_at,
        finished_at=rendered.render_batch.items[0].call_record.finished_at,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=("caption_result",),
    )
    native_hash = rendered.native_conclusion.content_hash()
    scene_hash = _scene().scene_hash()
    caption = VisionLanguageResult(
        result_id="caption_result",
        request_id=request.request_id,
        interpretation="Emocio secretly selected option_broken.",
        inferred_claims=("renderer-only crown is a grounded fact",),
        source_artifact_ids=request.artifact_ids,
        call_spec=call,
        call=record,
    )

    assert caption.source_artifact_ids == (image.image_id,)
    with pytest.raises(ValidationError):
        rendered.native_conclusion.option_id = "option_broken"
    assert rendered.native_conclusion.content_hash() == native_hash
    assert _scene().scene_hash() == scene_hash
    scene_claims = {item.content for item in _scene().evidence}
    assert caption.inferred_claims[0] not in scene_claims
    assert caption.result_id not in {
        evidence_id
        for scene in (
            rendered.visual_state.current_scene,
            rendered.visual_state.desired_scene,
            rendered.visual_state.broken_scene,
            *rendered.visual_state.option_rollouts,
        )
        for evidence_id in scene.grounded_evidence_ids
    }
    rendered.validate_against(_scene(), _world())


def test_null_and_disabled_paths_do_not_import_or_call_heavy_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imported_heavy: list[str] = []
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"torch", "diffusers", "PIL"}:
            imported_heavy.append(name)
            raise AssertionError(f"unexpected heavy import: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    import app.backend.rei.emocio.diffusers_renderer as renderer_module

    reloaded = importlib.reload(renderer_module)
    lazy = reloaded.LazyDiffusersBackend(
        reloaded.DiffusersRuntimeConfig(
            device="cuda",
            torch_dtype="bfloat16",
            local_files_only=True,
            enable_attention_slicing=False,
        )
    )
    spec = _source_spec()
    null_batch = NullRenderer().render((spec,), seed=37)
    disabled = process_emocio(
        _scene(),
        _world(),
        renderer=NullRenderer(),
        render_seed=37,
    )
    no_renderer = process_emocio(_scene(), _world())

    assert imported_heavy == []
    assert lazy._pipelines == {}
    assert null_batch.status == "disabled"
    assert null_batch.items == ()
    assert disabled.render_batch is not None
    assert disabled.render_batch.status == "disabled"
    assert disabled.rendered_images == ()
    assert no_renderer.render_batch is None
    assert no_renderer.rendered_images == ()


def test_scene_seeds_are_distinct_deterministic_derivations(tmp_path: Path) -> None:
    backend = DeterministicPngBackend()
    provider, _ = _provider(tmp_path, backend)
    visual_state = process_emocio(_scene(), _world()).visual_state
    scenes = (visual_state.current_scene, visual_state.desired_scene)
    renderer = LocalEmocioRenderer(provider=provider, settings=_settings())

    first = renderer.render(scenes, seed=41)
    replay = renderer.render(scenes, seed=41)
    seeds = tuple(item.request.seed for item in first.items)

    assert seeds == tuple(derive_scene_seed(41, scene.scene_id) for scene in scenes)
    assert len(set(seeds)) == len(scenes)
    assert tuple(item.request for item in replay.items) == tuple(
        item.request for item in first.items
    )


def test_pipeline_runtime_provenance_changes_request_identity() -> None:
    spec = _source_spec()
    provider = _identity()
    first_pipeline = DiffusersRuntimeConfig(
        device="cuda",
        torch_dtype="bfloat16",
        local_files_only=True,
        enable_attention_slicing=False,
    ).pipeline_spec("text_to_image")
    changed_pipeline = DiffusersRuntimeConfig(
        device="cuda",
        torch_dtype="float16",
        local_files_only=True,
        enable_attention_slicing=False,
    ).pipeline_spec("text_to_image")
    common = {
        "mode": "text_to_image",
        "source_spec": spec,
        "provider": provider,
        "seed": 43,
        "prompt": "structured scene",
        "negative_prompt": "",
        "width": 4,
        "height": 3,
        "num_inference_steps": 2,
        "guidance_scale": 1.0,
    }

    first = ImageRenderRequest.create(pipeline=first_pipeline, **common)
    changed = ImageRenderRequest.create(pipeline=changed_pipeline, **common)

    assert first.request_id != changed.request_id
    assert first.pipeline.parameters != changed.pipeline.parameters
    parameter_names = {item.name for item in first.provider_parameters}
    assert "pipeline_spec_hash" in parameter_names
    assert "runtime.torch_dtype" in parameter_names


def test_preparation_failure_is_recorded_without_losing_prior_artifact(
    tmp_path: Path,
) -> None:
    backend = DeterministicPngBackend()
    provider, _ = _provider(tmp_path, backend)
    visual_state = process_emocio(_scene(), _world()).visual_state
    scenes = (visual_state.current_scene, visual_state.desired_scene)

    class FailingSecondPromptCompiler:
        def compile(self, scene):
            if scene.scene_id == scenes[1].scene_id:
                raise RuntimeError("synthetic prompt preparation failure")
            return "valid structured prompt"

    batch = LocalEmocioRenderer(
        provider=provider,
        settings=_settings(),
        prompt_compiler=FailingSecondPromptCompiler(),
    ).render(scenes, seed=47)

    assert batch.status == "partial"
    assert len(batch.artifacts) == 1
    assert len(batch.items) == 1
    assert len(batch.preparation_failures) == 1
    assert batch.preparation_failures[0].source_spec_id == scenes[1].scene_id
    assert batch.preparation_failures[0].failure_code == "RuntimeError"
    assert len(backend.calls) == 1

    with pytest.raises(ValidationError, match="cover every frozen source scene"):
        ImageRenderBatchOutcome.create(
            source_spec_ids=tuple(scene.scene_id for scene in scenes),
            root_seed=47,
            status="succeeded",
            items=batch.items,
        )


def test_complete_png_validation_rejects_crc_and_truncation() -> None:
    valid = _png(4, 3)
    assert inspect_png(valid) == (4, 3)

    bad_crc = bytearray(valid)
    bad_crc[29] ^= 0x01
    with pytest.raises(ValueError, match="CRC"):
        inspect_png(bytes(bad_crc))
    with pytest.raises(ValueError, match="IEND|chunk|byte stream"):
        inspect_png(valid[:-12])


def test_provider_neutral_fallback_uses_actual_provider_and_seed() -> None:
    spec = _source_spec()
    primary = _identity()
    fallback = primary.model_copy(
        update={
            "provider_id": "fallback_renderer",
            "model": "test/fallback-image-model",
            "model_revision": "89abcdef0123456789abcdef0123456789abcdef",
        }
    )
    request = ImageRenderRequest.create(
        mode="text_to_image",
        source_spec=spec,
        provider=primary,
        pipeline=_pipeline(),
        seed=17,
        prompt="fallback scene",
        negative_prompt="",
        width=4,
        height=3,
        num_inference_steps=2,
        guidance_scale=1.0,
    )
    fallback_plan = ProviderFallbackPlan(
        provider=fallback,
        seed=22,
        parameters=request.provider_parameters,
        timeout_seconds=1.0,
    )
    call = ProviderCallSpec(
        call_id="fallback_render_call",
        request_id=request.request_id,
        input_artifact_ids=request.input_artifact_ids,
        provider=primary,
        seed=request.seed,
        parameters=request.provider_parameters,
        timeout_seconds=1.0,
        fallback_policy=ProviderFallbackPolicy(mode="provider", plan=fallback_plan),
    )
    digest = hashlib.sha256(_png(4, 3)).hexdigest()
    image_id = content_id(
        "image",
        {"request_id": request.request_id, "content_sha256": digest},
    )
    artifact = ImageArtifact(
        image_id=image_id,
        request_id=request.request_id,
        render_call_id=call.call_id,
        source_spec_id=spec.scene_id,
        provider_id=fallback.provider_id,
        model=fallback.model,
        model_revision=fallback.model_revision,
        seed=22,
        input_spec_hash=spec.content_hash(),
        content_sha256=digest,
        media_type="image/png",
        grounded=False,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        path=f"emocio/images/{image_id}.png",
        width=4,
        height=3,
        generated_only_elements=("unverified_renderer_details",),
    )
    timestamp = utc_now()
    fallback_record = ProviderFallbackRecord(
        provider=fallback,
        seed=22,
        parameters=request.provider_parameters,
        timeout_seconds=1.0,
        started_at=timestamp,
        finished_at=timestamp,
        status="succeeded",
        output_artifact_ids=(image_id,),
    )
    record = ProviderCallRecord(
        call_id=call.call_id,
        spec_hash=call.content_hash(),
        request_id=call.request_id,
        input_artifact_ids=call.input_artifact_ids,
        provider=call.provider,
        seed=call.seed,
        parameters=call.parameters,
        timeout_seconds=call.timeout_seconds,
        started_at=timestamp,
        primary_finished_at=timestamp,
        finished_at=timestamp,
        status="fell_back",
        primary_status="failed",
        fallback=fallback_record,
        output_artifact_ids=(image_id,),
    )
    outcome = ImageRenderItemOutcome.create(
        request=request,
        call_spec=call,
        call_record=record,
        artifact=artifact,
    )

    validate_image_render_outcome(outcome, source_spec=spec)
