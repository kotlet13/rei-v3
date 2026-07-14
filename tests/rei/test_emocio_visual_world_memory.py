from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.backend.rei.ids import canonical_json_bytes, content_id
from app.backend.rei.emocio.renderer import derive_scene_seed
from app.backend.rei.emocio.valuation import value_option_rollout
from app.backend.rei.emocio.vector_encoding import (
    canonical_l2_float32_le_vector,
)
from app.backend.rei.emocio.visual_valuation import (
    BoundVisualEmbedding,
    VisualValuationPolicy,
    VisualValuationResult,
    evaluate_visual_valuation,
)
from app.backend.rei.emocio.visual_world_memory import (
    VisualWorldMemoryOutcomeLink,
    VisualWorldMemoryOutcomeStatus,
    VisualWorldMemoryRecord,
    build_visual_world_memory_record,
)
from app.backend.rei.models.ego import OutcomeRecord
from app.backend.rei.models.emocio import (
    AttentionWeight,
    EmocioVisualState,
    ImageArtifact,
    ImaginedVisualArtifact,
    VisualEmbeddingArtifact,
    VisualSceneSpec,
)
from app.backend.rei.models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderParameter,
)
from app.backend.rei.models.rendering import (
    ImagePipelineSpec,
    ImageRenderBatchOutcome,
    ImageRenderItemOutcome,
    ImageRenderRequest,
    ImageSourceReference,
)
from app.backend.rei.providers.protocols import (
    ImageEncodingRequest,
    ImageEncodingSpec,
    VerifiedImageEncoding,
)


def _renderer_identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="visual_memory_renderer",
        kind="image_renderer",
        implementation="tests.VisualMemoryRenderer",
        implementation_revision="1",
        uses_model=True,
        model="test/visual-renderer",
        model_revision="renderer-revision-1",
    )


def _encoder_identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="visual_memory_encoder",
        kind="image_encoder",
        implementation="tests.VisualMemoryEncoder",
        implementation_revision="1",
        uses_model=True,
        model="facebook/dinov2-base",
        model_revision="f9e44c814b77203eaa57a6bdbbd535f21ede1415",
    )


def _scene(role: str, *, option_id: str | None = None) -> VisualSceneSpec:
    suffix = option_id or role
    special_rollout = option_id == "option_a"
    return VisualSceneSpec(
        scene_id=f"visual_scene_{suffix}",
        scene_kind=role,
        option_id=option_id,
        entities=("other", "self", "other") if special_rollout else ("self",),
        self_position="foreground" if special_rollout else "self",
        attention_structure=(
            (
                AttentionWeight(target="other", score=0.4),
                AttentionWeight(target="self", score=0.6),
            )
            if special_rollout
            else ()
        ),
        group_belonging="approaching",
        status_relations=("peer", "aspirational", "peer"),
        movement=("turn", f"movement_{suffix}", "turn"),
        composition=(f"composition_{suffix}",),
        attraction_markers=("warmth", "recognition", "warmth"),
        obstacle_markers=("distance", "barrier", "distance"),
        grounded_evidence_ids=(),
        inferred_elements=(f"imagined_{suffix}",),
    )


SCENES = {
    "current": _scene("current"),
    "desired": _scene("desired"),
    "broken": _scene("broken"),
    "option_a": _scene("option_rollout", option_id="option_a"),
    "option_b": _scene("option_rollout", option_id="option_b"),
}


def _pipeline_spec(mode: str) -> ImagePipelineSpec:
    conditioning_method = (
        "none" if mode == "text_to_image" else "reference_image"
    )
    values = {
        "conditioning_method": conditioning_method,
        "runtime_profile": "runtime-profile-1",
    }
    return ImagePipelineSpec(
        implementation="tests.VisualMemoryPipeline",
        implementation_revision="pipeline-revision-1",
        parameters=tuple(
            ProviderParameter(
                name=name,
                canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
            )
            for name, value in sorted(values.items())
        ),
    )


def _render_batch(evaluation_seed: int) -> ImageRenderBatchOutcome:
    ordered_keys = ("current", "desired", "broken", "option_a", "option_b")
    renderer = _renderer_identity()
    items: list[ImageRenderItemOutcome] = []
    artifacts: dict[str, ImageArtifact] = {}
    for index, key in enumerate(ordered_keys):
        scene = SCENES[key]
        mode = (
            "image_to_image"
            if scene.scene_kind == "option_rollout"
            else "text_to_image"
        )
        source_image = (
            ImageSourceReference.from_artifact_with_scene_lineage(
                artifacts["current"]
            )
            if mode == "image_to_image"
            else None
        )
        request = ImageRenderRequest.create(
            mode=mode,
            source_spec=scene,
            provider=renderer,
            pipeline=_pipeline_spec(mode),
            seed=derive_scene_seed(evaluation_seed, scene.scene_id),
            prompt=f"prompt for {scene.scene_id}",
            negative_prompt="",
            width=32,
            height=32,
            num_inference_steps=4,
            guidance_scale=0.0,
            source_image=source_image,
            strength=None,
            conditioning_method=(
                "reference_image" if mode == "image_to_image" else "none"
            ),
            prompt_language="sl",
            style_id="visual-memory-style-1",
            profile_hash="a" * 64,
        )
        call_spec = ProviderCallSpec(
            call_id=content_id("render_call", {"request_id": request.request_id}),
            request_id=request.request_id,
            input_artifact_ids=request.input_artifact_ids,
            provider=renderer,
            seed=request.seed,
            parameters=request.provider_parameters,
            timeout_seconds=5.0,
            fallback_policy=ProviderFallbackPolicy(
                mode="none",
                no_fallback_reason="Pinned renderer fails closed",
            ),
        )
        content_sha256 = hashlib.sha256(
            f"{request.request_id}:png".encode("utf-8")
        ).hexdigest()
        image_id = content_id(
            "image",
            {
                "request_id": request.request_id,
                "content_sha256": content_sha256,
            },
        )
        image = ImageArtifact(
            image_id=image_id,
            request_id=request.request_id,
            render_call_id=call_spec.call_id,
            source_spec_id=scene.scene_id,
            provider_id=renderer.provider_id,
            model=renderer.model,
            model_revision=renderer.model_revision,
            seed=request.seed,
            input_spec_hash=scene.content_hash(),
            content_sha256=content_sha256,
            media_type="image/png",
            grounded=False,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            path=f"emocio/images/{image_id}.png",
            width=request.width,
            height=request.height,
            generated_only_elements=("renderer-only crown",),
        )
        started_at = datetime(2026, 7, 14, 10, tzinfo=UTC) + timedelta(
            seconds=evaluation_seed * 10 + index
        )
        finished_at = started_at + timedelta(milliseconds=1)
        call_record = ProviderCallRecord(
            call_id=call_spec.call_id,
            spec_hash=call_spec.content_hash(),
            request_id=call_spec.request_id,
            input_artifact_ids=call_spec.input_artifact_ids,
            provider=call_spec.provider,
            seed=call_spec.seed,
            parameters=call_spec.parameters,
            timeout_seconds=call_spec.timeout_seconds,
            started_at=started_at,
            primary_finished_at=finished_at,
            finished_at=finished_at,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(image.image_id,),
        )
        items.append(
            ImageRenderItemOutcome.create(
                request=request,
                call_spec=call_spec,
                call_record=call_record,
                artifact=image,
            )
        )
        artifacts[key] = image
    return ImageRenderBatchOutcome.create(
        source_spec_ids=tuple(SCENES[key].scene_id for key in ordered_keys),
        root_seed=evaluation_seed,
        status="succeeded",
        items=tuple(items),
    )


def _observation(
    *,
    scene: VisualSceneSpec,
    evaluation_seed: int,
    render_batch: ImageRenderBatchOutcome,
    vector: tuple[float, ...],
) -> BoundVisualEmbedding:
    render_item = next(
        item
        for item in render_batch.items
        if item.request.source_spec_id == scene.scene_id
    )
    assert render_item.artifact is not None
    image = render_item.artifact
    renderer = render_item.request.provider
    imagined = ImaginedVisualArtifact(
        artifact_id=image.image_id,
        originating_scene_spec_id=scene.scene_id,
        option_id=scene.option_id,
        seed=image.seed,
        model_identity=renderer,
        ungrounded_elements=image.generated_only_elements,
    )
    encoder = _encoder_identity()
    _, exact_vector, vector_hash = canonical_l2_float32_le_vector(vector)
    encoding_spec = ImageEncodingSpec(
        implementation="tests.VisualMemoryFeatureBackend",
        implementation_revision="1",
        dimensions=len(exact_vector),
    )
    request = ImageEncodingRequest.create(
        image=image,
        provider=encoder,
        spec=encoding_spec,
    )
    call_spec = ProviderCallSpec(
        call_id=f"encoding_call_{scene.scene_id}_{evaluation_seed}",
        request_id=request.request_id,
        input_artifact_ids=(image.image_id,),
        provider=encoder,
        seed=evaluation_seed,
        parameters=request.provider_parameters,
        timeout_seconds=5.0,
        fallback_policy=ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason="Pinned visual feature space fails closed",
        ),
    )
    vector_ref = f"emocio/vectors/{vector_hash}.f32"
    encoding_id = VerifiedImageEncoding.derive_id(
        request=request,
        vector_ref=vector_ref,
        vector_hash=vector_hash,
        dimensions=len(exact_vector),
    )
    started_at = datetime(2026, 7, 14, 12, tzinfo=UTC) + timedelta(
        seconds=evaluation_seed
    )
    finished_at = started_at + timedelta(milliseconds=1)
    call = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        input_artifact_ids=call_spec.input_artifact_ids,
        provider=call_spec.provider,
        seed=call_spec.seed,
        parameters=call_spec.parameters,
        timeout_seconds=call_spec.timeout_seconds,
        started_at=started_at,
        primary_finished_at=finished_at,
        finished_at=finished_at,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=(encoding_id,),
    )
    encoding = VerifiedImageEncoding.create(
        request=request,
        vector_ref=vector_ref,
        vector_hash=vector_hash,
        dimensions=len(exact_vector),
        call_spec=call_spec,
        call=call,
    )
    return BoundVisualEmbedding.create(
        role=scene.scene_kind,
        evaluation_seed=evaluation_seed,
        render_batch=render_batch,
        scene_spec=scene,
        image=image,
        imagined=imagined,
        encoding=encoding,
        vector=vector,
    )


def _visual_state() -> EmocioVisualState:
    option_rollouts = (SCENES["option_a"], SCENES["option_b"])
    option_valuations = tuple(
        value_option_rollout(
            rollout,
            current_scene=SCENES["current"],
            desired_scene=SCENES["desired"],
            broken_scene=SCENES["broken"],
        )
        for rollout in option_rollouts
    )
    payload = {
        "schema_version": "rei-native-emocio-visual-state-v1",
        "source_scene_id": "scene_visual_memory",
        "source_packet_id": "packet_visual_memory",
        "current_scene": SCENES["current"],
        "desired_scene": SCENES["desired"],
        "broken_scene": SCENES["broken"],
        "option_rollouts": option_rollouts,
        "option_valuations": option_valuations,
    }
    return EmocioVisualState(
        visual_state_id=content_id("emocio_state", payload),
        **payload,
    )


def _policy() -> VisualValuationPolicy:
    return VisualValuationPolicy.create(
        structured_weight=0.4,
        desired_similarity_weight=0.4,
        broken_avoidance_weight=0.2,
        seed_consistency_penalty=0.15,
        uncertainty_penalty=0.1,
    )


def _observations(
    seed: int,
    *,
    option_a: tuple[float, ...],
    option_b: tuple[float, ...],
) -> tuple[BoundVisualEmbedding, ...]:
    render_batch = _render_batch(seed)
    vectors = {
        "current": (0.8, 0.2),
        "desired": (1.0, 0.0),
        "broken": (0.0, 1.0),
        "option_a": option_a,
        "option_b": option_b,
    }
    return tuple(
        _observation(
            scene=SCENES[key],
            evaluation_seed=seed,
            render_batch=render_batch,
            vector=vectors[key],
        )
        for key in ("current", "desired", "broken", "option_a", "option_b")
    )


def _multi_seed_result() -> tuple[
    BoundVisualEmbedding,
    BoundVisualEmbedding,
    EmocioVisualState,
    tuple[BoundVisualEmbedding, ...],
    VisualValuationResult,
]:
    seed_11 = _observations(
        11,
        option_a=(0.95, 0.05),
        option_b=(0.2, 0.8),
    )
    seed_13 = _observations(
        13,
        option_a=(0.35, 0.65),
        option_b=(0.1, 0.9),
    )
    visual_state = _visual_state()
    observation_set = (*reversed(seed_13), *reversed(seed_11))
    result = evaluate_visual_valuation(
        policy=_policy(),
        visual_state=visual_state,
        observations=observation_set,
        include_cross_seed_consistency=True,
    )
    option_a_11 = next(
        item
        for item in seed_11
        if item.role == "option_rollout"
        and item.scene_spec.option_id == "option_a"
    )
    option_a_13 = next(
        item
        for item in seed_13
        if item.role == "option_rollout"
        and item.scene_spec.option_id == "option_a"
    )
    return (
        option_a_11,
        option_a_13,
        visual_state,
        observation_set,
        result,
    )


def _outcome(
    *,
    outcome_id: str = "outcome_option_a",
    event_id: str = "event_after_option_a",
) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id=outcome_id,
        event_id=event_id,
        recorded_at=datetime(2026, 7, 14, 15, tzinfo=UTC),
        source="external_observation",
        observed_effects=("contact increased",),
        evidence_ids=("outcome_evidence_1",),
    )


def _build(
    observation: BoundVisualEmbedding,
    valuation: VisualValuationResult,
    *,
    visual_state: EmocioVisualState,
    observations: tuple[BoundVisualEmbedding, ...],
    outcome: OutcomeRecord | None = None,
    outcome_status: VisualWorldMemoryOutcomeStatus | None = None,
) -> VisualWorldMemoryRecord:
    return build_visual_world_memory_record(
        observation=observation,
        valuation=valuation,
        visual_state=visual_state,
        observations=observations,
        outcome=outcome,
        outcome_status=outcome_status,
    )


def test_builder_uses_only_verified_observation_and_complete_valuation() -> None:
    option_a_11, _, visual_state, observations, valuation = _multi_seed_result()
    first = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )
    replay = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )

    assert replay == first
    assert first.memory_id.startswith("visual_world_memory_")
    assert first.visual_valuation_result_id == valuation.result_id
    assert first.visual_valuation_result_hash == valuation.content_hash()
    assert first.observation_id == option_a_11.observation_id
    assert first.observation_hash == option_a_11.content_hash()
    assert first.encoding_id == option_a_11.encoding.encoding_id
    assert first.encoding_hash == option_a_11.encoding.content_hash()
    assert first.embedding_artifact_hash == option_a_11.embedding.content_hash()
    assert first.vector_hash == option_a_11.embedding.vector_hash
    assert set(inspect.signature(build_visual_world_memory_record).parameters) == {
        "observation",
        "valuation",
        "visual_state",
        "observations",
        "outcome",
        "outcome_status",
    }


def test_multi_seed_selects_exact_comparisons_for_the_observation() -> None:
    option_a_11, option_a_13, visual_state, observations, valuation = (
        _multi_seed_result()
    )
    memory_11 = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )
    memory_13 = _build(
        option_a_13,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )

    expected_11 = {
        item.kind: item
        for item in valuation.comparisons
        if item.left_observation_id == option_a_11.observation_id
        and item.kind in {"rollout_to_desired", "rollout_to_broken"}
    }
    expected_13 = {
        item.kind: item
        for item in valuation.comparisons
        if item.left_observation_id == option_a_13.observation_id
        and item.kind in {"rollout_to_desired", "rollout_to_broken"}
    }
    assert memory_11.desired_comparison.comparison_id == expected_11[
        "rollout_to_desired"
    ].comparison_id
    assert memory_11.broken_comparison.comparison_id == expected_11[
        "rollout_to_broken"
    ].comparison_id
    assert memory_13.desired_comparison.comparison_id == expected_13[
        "rollout_to_desired"
    ].comparison_id
    assert memory_13.broken_comparison.comparison_id == expected_13[
        "rollout_to_broken"
    ].comparison_id
    assert memory_11.desired_comparison != memory_13.desired_comparison
    assert memory_11.broken_comparison != memory_13.broken_comparison
    assert memory_11.desired_similarity == expected_11[
        "rollout_to_desired"
    ].normalized_similarity
    assert memory_13.broken_similarity == expected_13[
        "rollout_to_broken"
    ].normalized_similarity


def test_arbitrary_float_and_comparison_tampering_fail_closed() -> None:
    option_a_11, _, visual_state, observations, valuation = _multi_seed_result()
    memory = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )

    with pytest.raises(TypeError, match="unexpected keyword"):
        build_visual_world_memory_record(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
            desired_similarity=0.123,
            broken_similarity=0.987,
        )

    forged_link = memory.desired_comparison.model_copy(
        update={"normalized_similarity": 0.123}
    )
    with pytest.raises(ValueError, match="comparison lineage"):
        memory.model_copy(
            update={"desired_comparison": forged_link}
        ).validate_against(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )

    source_comparisons = list(valuation.comparisons)
    source_index = next(
        index
        for index, item in enumerate(source_comparisons)
        if item.comparison_id == memory.desired_comparison.comparison_id
    )
    source_comparisons[source_index] = source_comparisons[
        source_index
    ].model_copy(update={"normalized_similarity": 0.456})
    forged_result = valuation.model_copy(
        update={"comparisons": tuple(source_comparisons)}
    )
    with pytest.raises(ValidationError, match="Normalized visual similarity"):
        memory.validate_against(
            observation=option_a_11,
            valuation=forged_result,
            visual_state=visual_state,
            observations=observations,
        )


def test_rehashed_structured_valuation_forgery_fails_source_replay() -> None:
    option_a_11, _, visual_state, observations, valuation = _multi_seed_result()
    memory = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )
    forged = valuation.model_dump(mode="python", round_trip=True)
    forged_score = forged["option_scores"][0]
    forged_score["structured_valuation_hash"] = "f" * 64
    forged_score["score_id"] = content_id(
        "visual_option_score",
        {
            key: value
            for key, value in forged_score.items()
            if key != "score_id"
        },
    )
    forged["result_id"] = content_id(
        "visual_valuation_result",
        {
            key: value
            for key, value in forged.items()
            if key != "result_id"
        },
    )
    algebraically_valid = VisualValuationResult.model_validate(forged)

    assert (
        algebraically_valid.option_scores[0].structured_valuation_hash
        == "f" * 64
    )
    with pytest.raises(ValueError, match="deterministic source replay"):
        memory.validate_against(
            observation=option_a_11,
            valuation=algebraically_valid,
            visual_state=visual_state,
            observations=observations,
        )


def test_stale_vector_model_copy_fails_before_memory_membership() -> None:
    option_a_11, _, visual_state, observations, valuation = _multi_seed_result()
    stale = option_a_11.model_copy(update={"vector": (0.0, 1.0)})
    stale_observations = tuple(
        stale if item.observation_id == option_a_11.observation_id else item
        for item in observations
    )

    with pytest.raises(ValueError, match="vector hash"):
        build_visual_world_memory_record(
            observation=stale,
            valuation=valuation,
            visual_state=visual_state,
            observations=stale_observations,
        )


def test_result_observation_and_hash_tampering_fail_closed() -> None:
    option_a_11, option_a_13, visual_state, observations, valuation = (
        _multi_seed_result()
    )
    memory = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )

    with pytest.raises(ValueError, match="valuation lineage"):
        memory.model_copy(
            update={"visual_valuation_result_hash": "9" * 64}
        ).validate_against(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )
    with pytest.raises(ValueError, match="observation lineage"):
        memory.model_copy(update={"observation_hash": "8" * 64}).validate_against(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )
    forged_comparison = memory.broken_comparison.model_copy(
        update={"comparison_hash": "7" * 64}
    )
    with pytest.raises(ValueError, match="comparison lineage"):
        memory.model_copy(
            update={"broken_comparison": forged_comparison}
        ).validate_against(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )
    with pytest.raises(ValidationError, match="result ID"):
        memory.validate_against(
            observation=option_a_11,
            valuation=valuation.model_copy(update={"result_id": "tampered"}),
            visual_state=visual_state,
            observations=observations,
        )
    with pytest.raises(ValidationError, match="observation ID"):
        memory.validate_against(
            observation=option_a_11.model_copy(
                update={"observation_id": "tampered"}
            ),
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )

    foreign_visual_state = _visual_state()
    foreign_observations = _observations(
        19,
        option_a=(0.7, 0.3),
        option_b=(0.3, 0.7),
    )
    foreign_result = evaluate_visual_valuation(
        policy=_policy(),
        visual_state=foreign_visual_state,
        observations=foreign_observations,
    )
    with pytest.raises(ValueError, match="replay-set member"):
        _build(
            option_a_13,
            foreign_result,
            visual_state=foreign_visual_state,
            observations=foreign_observations,
        )


def test_historical_unverified_embedding_is_rejected_through_observation() -> None:
    option_a_11, _, visual_state, observations, valuation = _multi_seed_result()
    historical = VisualEmbeddingArtifact(
        source_artifact_id=option_a_11.image.image_id,
        encoder_identity=option_a_11.embedding.encoder_identity,
        vector_hash=option_a_11.embedding.vector_hash,
        dimensions=option_a_11.embedding.dimensions,
    )
    forged = option_a_11.model_copy(update={"embedding": historical})

    with pytest.raises(ValidationError):
        _build(
            forged,
            valuation,
            visual_state=visual_state,
            observations=observations,
        )


def test_meaning_is_structured_only_and_outcome_linkage_is_fail_closed() -> None:
    option_a_11, option_a_13, visual_state, observations, valuation = (
        _multi_seed_result()
    )
    first = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )
    second = _build(
        option_a_13,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )

    assert first.social_meaning == second.social_meaning
    assert first.motor_pattern == second.motor_pattern
    meaning_bytes = (
        first.social_meaning.canonical_json_bytes()
        + first.motor_pattern.canonical_json_bytes()
    )
    assert b"renderer-only crown" not in meaning_bytes
    assert first.social_meaning.entities == ("other", "self")
    assert first.social_meaning.status_relations == ("aspirational", "peer")
    assert first.motor_pattern.obstacle_markers == ("barrier", "distance")
    assert first.outcome is None
    assert first.external_fact_boundary == (
        "generated_images_never_extend_external_facts"
    )
    first.validate_against(
        observation=option_a_11,
        valuation=valuation,
        visual_state=visual_state,
        observations=observations,
    )

    outcome = _outcome()
    with pytest.raises(ValueError, match="forbids outcome linkage"):
        _build(
            option_a_11,
            valuation,
            visual_state=visual_state,
            observations=observations,
            outcome=outcome,
            outcome_status="observed_positive",
        )
    with pytest.raises(ValueError, match="forbids outcome linkage"):
        _build(
            option_a_11,
            valuation,
            visual_state=visual_state,
            observations=observations,
            outcome=outcome,
        )
    with pytest.raises(ValueError, match="forbids outcome linkage"):
        _build(
            option_a_11,
            valuation,
            visual_state=visual_state,
            observations=observations,
            outcome_status="mixed",
        )
    foreign_outcome = _outcome(
        outcome_id="outcome_foreign",
        event_id="event_foreign",
    )
    with pytest.raises(ValueError, match="forbids outcome linkage"):
        _build(
            option_a_11,
            valuation,
            visual_state=visual_state,
            observations=observations,
            outcome=foreign_outcome,
            outcome_status="observed_positive",
        )
    with pytest.raises(ValueError, match="forbids outcome linkage"):
        first.validate_against(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
            outcome=outcome,
            outcome_status="observed_positive",
        )

    forged_record = first.model_dump(mode="python", round_trip=True)
    forged_record["outcome"] = VisualWorldMemoryOutcomeLink.from_outcome(
        outcome,
        status="observed_positive",
    ).model_dump(mode="python", round_trip=True)
    forged_record["memory_id"] = content_id(
        "visual_world_memory",
        {
            key: value
            for key, value in forged_record.items()
            if key != "memory_id"
        },
    )
    with pytest.raises(ValidationError, match="forbids observed outcomes"):
        VisualWorldMemoryRecord.model_validate(forged_record)


def test_record_content_id_canonical_order_and_boundary_fail_closed() -> None:
    option_a_11, _, visual_state, observations, valuation = _multi_seed_result()
    memory = _build(
        option_a_11,
        valuation,
        visual_state=visual_state,
        observations=observations,
    )

    with pytest.raises(ValueError, match="canonical content"):
        memory.model_copy(update={"memory_id": "tampered"}).validate_against(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )
    with pytest.raises(ValueError, match="external-fact boundary"):
        memory.model_copy(update={"internal_only": False}).validate_against(
            observation=option_a_11,
            valuation=valuation,
            visual_state=visual_state,
            observations=observations,
        )

    reversed_social = memory.social_meaning.model_dump(mode="python")
    reversed_social["entities"] = tuple(reversed(memory.social_meaning.entities))
    with pytest.raises(ValidationError, match="sorted and unique"):
        type(memory.social_meaning)(**reversed_social)

    payload = memory.model_dump(
        mode="python",
        round_trip=True,
        exclude={"memory_id"},
    )
    with pytest.raises(ValidationError):
        VisualWorldMemoryRecord(
            memory_id=memory.memory_id,
            **{
                **payload,
                "external_fact_boundary": "generated_images_are_evidence",
            },
        )
