from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.backend.rei.emocio import build_emocio_packet, process_emocio
from app.backend.rei.ids import content_id
from app.backend.rei.models.emocio import (
    EmocioCognitionTrace,
    EmocioWorld,
    GroundedVisualRepresentation,
    ImageArtifact,
    ImaginedVisualArtifact,
    VisualEmbeddingArtifact,
)
from app.backend.rei.models.provider import ProviderIdentity
from app.backend.rei.models.scene import DecisionOption, EvidenceItem, SceneEvent


def _scene(*, reverse_options: bool = False) -> SceneEvent:
    options = (
        DecisionOption(
            option_id="option_a",
            label="stay",
            description="keep the current composition",
        ),
        DecisionOption(
            option_id="option_b",
            label="move",
            description="approach the desired composition",
        ),
    )
    if reverse_options:
        options = tuple(reversed(options))
    return SceneEvent(
        event_id="event_emocio_c4",
        raw_input="Choose a structured scene transformation.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="evidence_grounded_image",
                modality="image",
                content="a person at a doorway",
                grounded=True,
                source_ref="user:image",
                confidence=1.0,
            ),
            EvidenceItem(
                evidence_id="evidence_generated_image",
                modality="image",
                content="a renderer invented a crown",
                grounded=False,
                source_ref="renderer:image",
                confidence=0.1,
                provenance_kind="generated",
                inferred_by="test_renderer",
            ),
        ),
        options=options,
        actors=("self", "other"),
        constraints=(),
        unknowns=("outcome",),
    )


def _world() -> EmocioWorld:
    return EmocioWorld(
        world_id="emocio_world_c4",
        visual_memories=("known doorway",),
        desired_scenes=("shared bright room",),
        broken_scenes=("isolated dark room",),
        social_identity_motifs=("belonging",),
        attraction_patterns=("warm light",),
        motor_patterns=("step forward",),
    )


def _renderer_identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="c4_test_renderer",
        kind="image_renderer",
        implementation="tests.C4Renderer",
        implementation_revision="1",
        uses_model=True,
        model="test/image-model",
        model_revision="0123456789abcdef",
    )


def _image(scenes: tuple, seed: int) -> ImageArtifact:
    source = scenes[0]
    return ImageArtifact(
        image_id="imagined_image_c4",
        request_id="render_request_c4",
        render_call_id="render_call_c4",
        source_spec_id=source.scene_id,
        provider_id=_renderer_identity().provider_id,
        model=_renderer_identity().model,
        model_revision=_renderer_identity().model_revision,
        seed=seed,
        input_spec_hash=source.content_hash(),
        content_sha256="1" * 64,
        media_type="image/png",
        prompt="structured scene",
        negative_prompt="",
        path="emocio/images/c4.png",
        width=32,
        height=32,
        generated_only_elements=("unverified renderer details",),
    )


class SuccessfulRenderer:
    def render(self, scenes: tuple, *, seed: int) -> tuple[ImageArtifact, ...]:
        return (_image(scenes, seed),)


class ExplodingRenderer:
    def __init__(self) -> None:
        self.called = False

    def render(self, scenes: tuple, *, seed: int) -> tuple[ImageArtifact, ...]:
        del scenes, seed
        self.called = True
        raise RuntimeError("synthetic renderer outage")


def test_explicit_modes_trace_effective_path_and_freeze_structured_conclusion() -> None:
    baseline = process_emocio(_scene(), _world())
    assert baseline.cognition_trace.requested_mode == "structured_only"
    assert baseline.cognition_trace.effective_mode == "structured_only"
    assert baseline.cognition_trace.fallback_reason is None

    renderer = SuccessfulRenderer()
    observed = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        cognition_mode="render_observe",
        render_seed=17,
    )
    assert observed.cognition_trace.requested_mode == "render_observe"
    assert observed.cognition_trace.effective_mode == "render_observe"
    assert observed.cognition_trace.fallback_reason is None
    assert observed.native_conclusion == baseline.native_conclusion
    assert observed.stage_order.index("native_conclusion") < observed.stage_order.index(
        "render"
    )

    visual_request = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        cognition_mode="visual_cognition",
        render_seed=17,
    )
    assert visual_request.cognition_trace.requested_mode == "visual_cognition"
    assert visual_request.cognition_trace.effective_mode == "render_observe"
    assert (
        visual_request.cognition_trace.fallback_reason
        == "visual_render_provenance_unavailable"
    )
    assert visual_request.native_conclusion == baseline.native_conclusion


def test_structured_only_never_calls_renderer_and_renderer_failure_is_explicit() -> None:
    renderer = ExplodingRenderer()
    structured = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        cognition_mode="structured_only",
    )
    assert renderer.called is False
    assert structured.render_batch is None
    assert structured.render_seed is None
    assert "render" not in structured.stage_order
    with pytest.raises(ValueError, match="stage order"):
        replace(structured, stage_order=()).validate_against(
            _scene(),
            _world(),
        )

    failed = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        cognition_mode="render_observe",
    )
    assert renderer.called is True
    assert failed.cognition_trace.requested_mode == "render_observe"
    assert failed.cognition_trace.effective_mode == "structured_only"
    assert failed.cognition_trace.fallback_reason == "renderer_failed"

    visual_failed = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        cognition_mode="visual_cognition",
    )
    assert visual_failed.cognition_trace.effective_mode == "structured_only"
    assert visual_failed.cognition_trace.fallback_reason == "renderer_failed"
    assert visual_failed.visual_failure is not None
    assert visual_failed.visual_failure.stage == "render"
    assert visual_failed.visual_failure.render_batch_id is None
    assert visual_failed.visual_warning == (
        "Visual cognition render failed closed (RuntimeError)"
    )
    assert "synthetic renderer outage" not in (
        visual_failed.visual_failure.canonical_json_bytes().decode("utf-8")
        + (visual_failed.renderer_warning or "")
        + (visual_failed.visual_warning or "")
    )

    unavailable = process_emocio(
        _scene(),
        _world(),
        cognition_mode="visual_cognition",
    )
    assert unavailable.cognition_trace.effective_mode == "structured_only"
    assert unavailable.cognition_trace.fallback_reason == "renderer_not_configured"


def test_option_order_does_not_change_visual_scene_identity_or_old_baseline_ids() -> None:
    canonical_scene = _scene(reverse_options=False)
    reversed_scene = _scene(reverse_options=True)
    canonical = process_emocio(canonical_scene, _world())
    reversed_result = process_emocio(reversed_scene, _world())

    canonical_specs = (
        canonical.visual_state.current_scene,
        canonical.visual_state.desired_scene,
        canonical.visual_state.broken_scene,
        *canonical.visual_state.option_rollouts,
    )
    reversed_specs = (
        reversed_result.visual_state.current_scene,
        reversed_result.visual_state.desired_scene,
        reversed_result.visual_state.broken_scene,
        *reversed_result.visual_state.option_rollouts,
    )
    assert canonical_scene.scene_hash() != reversed_scene.scene_hash()
    assert tuple(item.scene_id for item in canonical_specs) == tuple(
        item.scene_id for item in reversed_specs
    )

    packet = build_emocio_packet(canonical_scene)
    for spec in canonical_specs:
        historical_payload = spec.model_dump(
            mode="python",
            round_trip=True,
            exclude={"scene_id"},
        )
        historical_id = content_id(
            "visual_scene",
            {
                "source_scene_hash": canonical_scene.scene_hash(),
                "source_packet_hash": packet.content_hash(),
                "source_world_hash": _world().content_hash(),
                **historical_payload,
            },
        )
        assert spec.scene_id == historical_id


def test_visual_artifact_contracts_enforce_the_external_fact_boundary() -> None:
    scene = _scene()
    result = process_emocio(scene, _world())
    spec = result.visual_state.current_scene
    grounded = GroundedVisualRepresentation(
        source_evidence_ids=spec.grounded_evidence_ids,
        scene_spec_id=spec.scene_id,
    )
    grounded.validate_against(spec, scene)

    contaminated = grounded.model_copy(
        update={"source_evidence_ids": ("evidence_generated_image",)}
    )
    with pytest.raises(ValueError, match="evidence scope|only grounded"):
        contaminated.validate_against(spec, scene)

    image = _image((spec,), 23)
    imagined = ImaginedVisualArtifact(
        artifact_id=image.image_id,
        originating_scene_spec_id=spec.scene_id,
        option_id=None,
        seed=23,
        model_identity=_renderer_identity(),
        ungrounded_elements=image.generated_only_elements,
    )
    imagined.validate_against(image, spec)
    assert imagined.internal_only is True

    encoder = ProviderIdentity(
        provider_id="c4_test_encoder",
        kind="image_encoder",
        implementation="tests.C4Encoder",
        implementation_revision="1",
        uses_model=True,
        model="test/image-encoder",
        model_revision="fedcba9876543210",
    )
    embedding = VisualEmbeddingArtifact(
        source_artifact_id=imagined.artifact_id,
        encoder_identity=encoder,
        vector_hash="2" * 64,
        dimensions=768,
    )
    embedding.validate_against(imagined)

    with pytest.raises(ValidationError):
        ImaginedVisualArtifact(
            artifact_id=image.image_id,
            originating_scene_spec_id=spec.scene_id,
            option_id=None,
            seed=23,
            model_identity=_renderer_identity(),
            internal_only=False,
            ungrounded_elements=image.generated_only_elements,
        )


def test_cognition_trace_rejects_untyped_or_upward_fallbacks() -> None:
    with pytest.raises(ValidationError, match="typed fallback reason"):
        EmocioCognitionTrace(
            trace_id="not_content_addressed",
            requested_mode="render_observe",
            effective_mode="structured_only",
        )
    with pytest.raises(ValidationError, match="cannot increase capability"):
        EmocioCognitionTrace.create(
            requested_mode="structured_only",
            effective_mode="render_observe",
            fallback_reason="visual_valuation_unavailable",
        )
