from __future__ import annotations

import hashlib
import math
import struct
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.backend.rei.ids import canonical_json_bytes, content_id
from app.backend.rei.emocio.renderer import derive_scene_seed
from app.backend.rei.emocio.visual_valuation import (
    BoundVisualEmbedding,
    VisualValuationPolicy,
    VisualValuationResult,
    canonical_visual_vector_hash,
    evaluate_visual_valuation,
)
from app.backend.rei.emocio.vector_encoding import (
    canonical_l2_float32_le_vector,
)
from app.backend.rei.models.emocio import (
    EmocioVisualState,
    ImageArtifact,
    ImaginedVisualArtifact,
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
from app.backend.rei.emocio.valuation import value_option_rollout


def _renderer_identity(
    *,
    revision: str = "0123456789abcdef0123456789abcdef01234567",
) -> ProviderIdentity:
    suffix = "" if revision.startswith("0123456789") else "_alternate"
    return ProviderIdentity(
        provider_id=f"visual_valuation_renderer{suffix}",
        kind="image_renderer",
        implementation="tests.VisualValuationRenderer",
        implementation_revision="1",
        uses_model=True,
        model="test/visual-renderer",
        model_revision=revision,
    )


def _encoder_identity(*, revision: str = "encoder-revision-1") -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="visual_valuation_encoder",
        kind="image_encoder",
        implementation="tests.VisualValuationEncoder",
        implementation_revision="1",
        uses_model=True,
        model="test/visual-encoder",
        model_revision=revision,
    )


def _scene(role: str, *, option_id: str | None = None) -> VisualSceneSpec:
    suffix = option_id or role
    semantic_role = option_id or role
    if semantic_role in {"desired", "option_a"}:
        composition = ("desired_shape",)
        movement = ("approach",)
        belonging = "connected"
    elif semantic_role in {"broken", "option_b"}:
        composition = ("broken_shape",)
        movement = ("withdraw",)
        belonging = "excluded"
    else:
        composition = ("current_shape",)
        movement = ("observe",)
        belonging = "approaching"
    return VisualSceneSpec(
        scene_id=f"visual_scene_{suffix}",
        scene_kind=role,
        option_id=option_id,
        entities=("self", "group"),
        self_position="self",
        attention_structure=(),
        group_belonging=belonging,
        status_relations=("equal",),
        movement=movement,
        composition=composition,
        attraction_markers=("desired_shape",),
        obstacle_markers=("broken_shape",),
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


def _pipeline_spec(
    mode: str,
    *,
    runtime_profile: str = "runtime-profile-1",
) -> ImagePipelineSpec:
    conditioning_method = "none" if mode == "text_to_image" else "reference_image"
    values = {
        "conditioning_method": conditioning_method,
        "runtime_profile": runtime_profile,
    }
    return ImagePipelineSpec(
        implementation="tests.VisualValuationPipeline",
        implementation_revision="pipeline-revision-1",
        parameters=tuple(
            ProviderParameter(
                name=name,
                canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
            )
            for name, value in sorted(values.items())
        ),
    )


def _render_batch(
    evaluation_seed: int,
    *,
    renderer_overrides: dict[str, ProviderIdentity] | None = None,
    runtime_profile_overrides: dict[str, str] | None = None,
    prompt_profile_overrides: dict[
        str,
        tuple[str | None, str | None, str | None],
    ]
    | None = None,
    rollout_source_key: str = "current",
    warnings: tuple[str, ...] = (),
) -> ImageRenderBatchOutcome:
    renderer_overrides = renderer_overrides or {}
    runtime_profile_overrides = runtime_profile_overrides or {}
    prompt_profile_overrides = prompt_profile_overrides or {}
    ordered_keys = ("current", "desired", "broken", "option_a", "option_b")
    items: list[ImageRenderItemOutcome] = []
    artifacts: dict[str, ImageArtifact] = {}
    for index, key in enumerate(ordered_keys):
        scene = SCENES[key]
        mode = (
            "image_to_image"
            if scene.scene_kind == "option_rollout"
            else "text_to_image"
        )
        renderer = renderer_overrides.get(key, _renderer_identity())
        pipeline = _pipeline_spec(
            mode,
            runtime_profile=runtime_profile_overrides.get(
                key,
                "runtime-profile-1",
            ),
        )
        source_image = None
        if mode == "image_to_image":
            source_image = ImageSourceReference.from_artifact_with_scene_lineage(
                artifacts[rollout_source_key]
            )
        prompt_language, style_id, profile_hash = prompt_profile_overrides.get(
            key,
            ("sl", "visual-style-1", "a" * 64),
        )
        request = ImageRenderRequest.create(
            mode=mode,
            source_spec=scene,
            provider=renderer,
            pipeline=pipeline,
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
            prompt_language=prompt_language,
            style_id=style_id,
            profile_hash=profile_hash,
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
            generated_only_elements=("unverified_renderer_details",),
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
        warnings=warnings,
    )


def _observation(
    *,
    scene: VisualSceneSpec,
    evaluation_seed: int,
    vector: tuple[float, ...],
    encoder: ProviderIdentity | None = None,
    render_batch: ImageRenderBatchOutcome | None = None,
    encoding_spec_revision: str | None = None,
) -> BoundVisualEmbedding:
    render_batch = render_batch or _render_batch(evaluation_seed)
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
    encoder = encoder or _encoder_identity()
    _, exact_vector, vector_hash = canonical_l2_float32_le_vector(vector)
    encoding_spec = ImageEncodingSpec(
        implementation="tests.VisualValuationFeatureBackend",
        implementation_revision=(
            encoding_spec_revision or encoder.implementation_revision
        ),
        dimensions=len(vector),
    )
    request = ImageEncodingRequest.create(
        image=image,
        provider=encoder,
        spec=encoding_spec,
    )
    call_spec = ProviderCallSpec(
        call_id=f"encoding_call_{image.image_id}",
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
    valuations = tuple(
        value_option_rollout(
            SCENES[option_id],
            current_scene=SCENES["current"],
            desired_scene=SCENES["desired"],
            broken_scene=SCENES["broken"],
        )
        for option_id in ("option_a", "option_b")
    )
    return EmocioVisualState(
        visual_state_id="visual_state_fixture",
        source_scene_id="source_scene_fixture",
        source_packet_id="source_packet_fixture",
        current_scene=SCENES["current"],
        desired_scene=SCENES["desired"],
        broken_scene=SCENES["broken"],
        option_rollouts=(SCENES["option_a"], SCENES["option_b"]),
        option_valuations=valuations,
    )


def test_visual_vector_hash_is_exact_normalized_float32_little_endian() -> None:
    raw = (3.0, 4.0)
    expected_bytes = struct.pack("<2f", 0.6, 0.8)

    assert canonical_visual_vector_hash(raw) == hashlib.sha256(
        expected_bytes
    ).hexdigest()
    observation = _observation(
        scene=SCENES["current"],
        evaluation_seed=3,
        vector=raw,
    )
    assert observation.vector == struct.unpack("<2f", expected_bytes)
    assert observation.embedding.vector_hash == hashlib.sha256(
        expected_bytes
    ).hexdigest()


def _policy() -> VisualValuationPolicy:
    return VisualValuationPolicy.create(
        structured_weight=0.4,
        desired_similarity_weight=0.4,
        broken_avoidance_weight=0.2,
        seed_consistency_penalty=0.15,
        uncertainty_penalty=0.1,
        action_collapse_epsilon=0.01,
        selection_tie_epsilon=0.000001,
    )


def _observations(
    seed: int,
    *,
    current: tuple[float, ...] = (0.8, 0.2),
    desired: tuple[float, ...] = (1.0, 0.0),
    broken: tuple[float, ...] = (0.0, 1.0),
    option_a: tuple[float, ...] = (0.9, 0.1),
    option_b: tuple[float, ...] = (0.2, 0.8),
    encoder: ProviderIdentity | None = None,
    render_batch: ImageRenderBatchOutcome | None = None,
) -> tuple[BoundVisualEmbedding, ...]:
    vectors = {
        "current": current,
        "desired": desired,
        "broken": broken,
        "option_a": option_a,
        "option_b": option_b,
    }
    render_batch = render_batch or _render_batch(seed)
    return tuple(
        _observation(
            scene=SCENES[key],
            evaluation_seed=seed,
            vector=vectors[key],
            encoder=encoder,
            render_batch=render_batch,
        )
        for key in ("current", "desired", "broken", "option_a", "option_b")
    )


def test_policy_and_result_are_canonical_internal_hypotheses() -> None:
    policy = _policy()
    weights = (
        policy.structured_weight,
        policy.desired_similarity_weight,
        policy.broken_avoidance_weight,
        policy.seed_consistency_penalty,
        policy.uncertainty_penalty,
    )
    assert policy.basis == "implementation_hypothesis"
    assert all(weight.basis == "implementation_hypothesis" for weight in weights)

    visual_state = _visual_state()
    observations = _observations(7)
    result = evaluate_visual_valuation(
        policy=policy,
        visual_state=visual_state,
        observations=tuple(reversed(observations)),
    )
    replay = evaluate_visual_valuation(
        policy=policy,
        visual_state=visual_state,
        observations=observations,
    )

    assert result == replay
    assert (
        result.validate_against(
            visual_state=visual_state,
            observations=tuple(reversed(observations)),
        )
        is result
    )
    assert result.result_id.startswith("visual_valuation_result_")
    assert result.visual_state_id == visual_state.visual_state_id
    assert result.visual_state_hash == visual_state.content_hash()
    assert result.leading_option_id == "option_a"
    assert result.integration_disposition == "usable"
    assert tuple(score.option_id for score in result.option_scores) == (
        "option_a",
        "option_b",
    )
    option_a, option_b = result.option_scores
    assert option_a.fused_score > option_b.fused_score
    assert option_a.seed_consistency is None
    assert option_a.consistency_penalty == 0.0
    assert option_a.pre_penalty_score == pytest.approx(
        option_a.base_weighted_numerator / option_a.base_weight_denominator,
        abs=1e-12,
    )
    assert {comparison.kind for comparison in result.comparisons} == {
        "current_to_desired",
        "rollout_to_desired",
        "rollout_to_broken",
        "rollout_to_rollout_action_separation",
    }
    assert len(result.comparisons) == 6
    action_comparison = next(
        comparison
        for comparison in result.comparisons
        if comparison.kind == "rollout_to_rollout_action_separation"
    )
    assert (action_comparison.option_id, action_comparison.paired_option_id) == (
        "option_a",
        "option_b",
    )
    assert result.internal_only is True
    assert result.external_evidence_claim is False
    assert all(
        comparison.external_evidence_claim is False
        for comparison in result.comparisons
    )
    assert all(score.external_evidence_claim is False for score in result.option_scores)

    alternate_state = visual_state.model_copy(
        update={"visual_state_id": "another_visual_state"}
    )
    with pytest.raises(ValueError, match="deterministic source replay"):
        result.validate_against(
            visual_state=alternate_state,
            observations=observations,
        )

    tampered = policy.model_dump(mode="python", round_trip=True)
    tampered["structured_weight"]["value"] = 0.9
    with pytest.raises(ValidationError, match="canonical content"):
        VisualValuationPolicy.model_validate(tampered)


def test_evaluator_revalidates_copied_policy_state_and_observations() -> None:
    policy = _policy()
    visual_state = _visual_state()
    valuations = visual_state.option_valuations
    observations = _observations(9)
    baseline = evaluate_visual_valuation(
        policy=policy,
        visual_state=visual_state,
        observations=observations,
    )
    assert baseline.leading_option_id == "option_a"

    stale_current = observations[0].model_copy(update={"vector": (0.0, 1.0)})
    with pytest.raises(ValueError, match="vector hash"):
        evaluate_visual_valuation(
            policy=policy,
            visual_state=visual_state,
            observations=(stale_current, *observations[1:]),
        )

    stale_weight = policy.structured_weight.model_copy(update={"value": 0.9})
    stale_policy = policy.model_copy(update={"structured_weight": stale_weight})
    with pytest.raises(ValueError, match="canonical content"):
        evaluate_visual_valuation(
            policy=stale_policy,
            visual_state=visual_state,
            observations=observations,
        )

    stale_dimension = valuations[0].dimensions[0].model_copy(
        update={"name": valuations[0].dimensions[1].name}
    )
    stale_valuation = valuations[0].model_copy(
        update={
            "dimensions": (stale_dimension, *valuations[0].dimensions[1:])
        }
    )
    stale_state = visual_state.model_copy(
        update={"option_valuations": (stale_valuation, valuations[1])}
    )
    with pytest.raises(ValueError, match="all canonical dimensions"):
        evaluate_visual_valuation(
            policy=policy,
            visual_state=stale_state,
            observations=observations,
        )

    forged_dimension = valuations[0].dimensions[0].model_copy(
        update={"score": 0.123456}
    )
    forged_valuation = valuations[0].model_copy(
        update={
            "dimensions": (forged_dimension, *valuations[0].dimensions[1:])
        }
    )
    forged_state = visual_state.model_copy(
        update={"option_valuations": (forged_valuation, valuations[1])}
    )
    with pytest.raises(ValueError, match="deterministic scene replay"):
        evaluate_visual_valuation(
            policy=policy,
            visual_state=forged_state,
            observations=observations,
        )


def test_source_replay_rejects_rehashed_structured_valuation_forgery() -> None:
    policy = _policy()
    visual_state = _visual_state()
    observations = _observations(10)
    result = evaluate_visual_valuation(
        policy=policy,
        visual_state=visual_state,
        observations=observations,
    )
    forged = result.model_dump(mode="python", round_trip=True)
    forged_score = forged["option_scores"][0]
    forged_score["structured_valuation_hash"] = "f" * 64
    forged_score_payload = {
        key: value
        for key, value in forged_score.items()
        if key != "score_id"
    }
    forged_score["score_id"] = content_id(
        "visual_option_score",
        forged_score_payload,
    )
    forged_result_payload = {
        key: value for key, value in forged.items() if key != "result_id"
    }
    forged["result_id"] = content_id(
        "visual_valuation_result",
        forged_result_payload,
    )

    algebraically_valid = VisualValuationResult.model_validate(forged)
    assert (
        algebraically_valid.option_scores[0].structured_valuation_hash
        == "f" * 64
    )
    with pytest.raises(ValueError, match="deterministic source replay"):
        algebraically_valid.validate_against(
            visual_state=visual_state,
            observations=observations,
        )


def test_cross_seed_consistency_is_optional_recorded_and_penalized() -> None:
    visual_state = _visual_state()
    first = _observations(11)
    second = _observations(
        13,
        option_a=(0.88, 0.12),
        option_b=(0.8, 0.2),
    )
    result = evaluate_visual_valuation(
        policy=_policy(),
        visual_state=visual_state,
        observations=(*second, *first),
        include_cross_seed_consistency=True,
    )

    option_a, option_b = result.option_scores
    assert option_a.seed_consistency is not None
    assert option_b.seed_consistency is not None
    assert option_a.seed_consistency > option_b.seed_consistency
    assert option_a.consistency_penalty < option_b.consistency_penalty
    consistency = tuple(
        comparison
        for comparison in result.comparisons
        if comparison.kind == "rollout_cross_seed_consistency"
    )
    assert len(consistency) == 2
    assert {item.option_id for item in consistency} == {"option_a", "option_b"}
    assert all(score.replicate_count == 2 for score in result.option_scores)
    replay_observations = tuple(reversed((*first, *second)))
    assert (
        result.validate_against(
            visual_state=visual_state,
            observations=replay_observations,
        )
        is result
    )
    assert (
        result.validate_against(
            visual_state=visual_state,
            observations=replay_observations,
            include_cross_seed_consistency=True,
        )
        is result
    )
    with pytest.raises(ValueError, match="mode differs from the result"):
        result.validate_against(
            visual_state=visual_state,
            observations=replay_observations,
            include_cross_seed_consistency=False,
        )

    with pytest.raises(ValueError, match="at least two"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=visual_state,
            observations=first,
            include_cross_seed_consistency=True,
        )


def test_near_identical_rollouts_collapse_despite_divergent_target_projections(
) -> None:
    policy = VisualValuationPolicy.create(
        structured_weight=0.4,
        desired_similarity_weight=0.4,
        broken_avoidance_weight=0.2,
        seed_consistency_penalty=0.15,
        uncertainty_penalty=0.1,
        action_collapse_epsilon=0.001,
    )
    result = evaluate_visual_valuation(
        policy=policy,
        visual_state=_visual_state(),
        observations=_observations(
            17,
            option_a=(1.0, 0.0),
            option_b=(1.0, 0.02),
        ),
    )

    assert result.action_collapse.detected is True
    assert result.action_collapse.minimum_direct_separation <= 0.001
    assert result.action_collapse.maximum_projection_profile_spread > 0.001
    assert result.action_collapse.method == "minimum_direct_rollout_separation"
    assert result.integration_disposition == "review_action_collapse"
    assert result.leading_option_id is None
    assert result.tied_option_ids == ()
    assert result.option_scores[0].fused_score > result.option_scores[1].fused_score
    assert result.action_collapse.external_evidence_claim is False


def test_orthogonal_rollouts_do_not_collapse_when_target_projections_match() -> None:
    result = evaluate_visual_valuation(
        policy=_policy(),
        visual_state=_visual_state(),
        observations=_observations(
            18,
            desired=(1.0, 1.0),
            broken=(-1.0, -1.0),
            option_a=(1.0, 0.0),
            option_b=(0.0, 1.0),
        ),
    )

    assert result.action_collapse.maximum_projection_profile_spread == 0.0
    assert result.action_collapse.minimum_direct_separation == 0.5
    assert result.action_collapse.detected is False
    assert result.leading_option_id == "option_a"
    assert result.integration_disposition == "usable"

    forged_replay = result.model_dump(mode="python", round_trip=True)
    forged_replay["action_collapse"]["minimum_direct_separation"] = 0.0
    forged_replay["action_collapse"]["detected"] = True
    with pytest.raises(ValidationError, match="diagnostic differs"):
        VisualValuationResult.model_validate(forged_replay)


def test_lineage_hash_dimensions_and_nonfinite_vectors_fail_closed() -> None:
    valid = _observations(19)[0]

    wrong_source = valid.embedding.model_copy(
        update={"source_artifact_id": "another_image"}
    )
    with pytest.raises(ValueError, match="Supplied visual embedding differs"):
        BoundVisualEmbedding.create(
            role=valid.role,
            evaluation_seed=valid.evaluation_seed,
            render_batch=valid.render_batch,
            scene_spec=valid.scene_spec,
            image=valid.image,
            imagined=valid.imagined,
            encoding=valid.encoding,
            embedding=wrong_source,
            vector=valid.vector,
        )

    with pytest.raises(ValueError, match="vector hash"):
        BoundVisualEmbedding.create(
            role=valid.role,
            evaluation_seed=valid.evaluation_seed,
            render_batch=valid.render_batch,
            scene_spec=valid.scene_spec,
            image=valid.image,
            imagined=valid.imagined,
            encoding=valid.encoding,
            vector=(0.7, 0.3),
        )

    forged_request = valid.encoding.request.model_copy(
        update={"image_content_sha256": "f" * 64}
    )
    forged_encoding_metadata = valid.encoding.model_copy(
        update={"request": forged_request}
    )
    with pytest.raises(
        ValueError,
        match="parameters differ from its request|request ID differs",
    ):
        BoundVisualEmbedding.create(
            role=valid.role,
            evaluation_seed=valid.evaluation_seed,
            render_batch=valid.render_batch,
            scene_spec=valid.scene_spec,
            image=valid.image,
            imagined=valid.imagined,
            encoding=forged_encoding_metadata,
            vector=valid.vector,
        )

    forged_call = valid.encoding.call.model_copy(update={"spec_hash": "0" * 64})
    forged_call_encoding = valid.encoding.model_copy(update={"call": forged_call})
    with pytest.raises(ValueError, match="does not match its spec hash"):
        BoundVisualEmbedding.create(
            role=valid.role,
            evaluation_seed=valid.evaluation_seed,
            render_batch=valid.render_batch,
            scene_spec=valid.scene_spec,
            image=valid.image,
            imagined=valid.imagined,
            encoding=forged_call_encoding,
            vector=valid.vector,
        )

    forged_vector_encoding = valid.encoding.model_copy(
        update={"vector_hash": "0" * 64}
    )
    with pytest.raises(ValueError, match="differs from image encoding"):
        BoundVisualEmbedding.create(
            role=valid.role,
            evaluation_seed=valid.evaluation_seed,
            render_batch=valid.render_batch,
            scene_spec=valid.scene_spec,
            image=valid.image,
            imagined=valid.imagined,
            encoding=forged_vector_encoding,
            vector=valid.vector,
        )

    changed_scene = valid.scene_spec.model_copy(
        update={"composition": ("changed scene",)}
    )
    with pytest.raises(ValueError, match="source spec hash|input hash"):
        BoundVisualEmbedding.create(
            role=valid.role,
            evaluation_seed=valid.evaluation_seed,
            render_batch=valid.render_batch,
            scene_spec=changed_scene,
            image=valid.image,
            imagined=valid.imagined,
            encoding=valid.encoding,
            vector=valid.vector,
        )

    with pytest.raises(ValueError, match="finite"):
        canonical_visual_vector_hash((math.nan, 1.0))
    with pytest.raises(ValueError, match="zero visual vector"):
        _observation(
            scene=SCENES["current"],
            evaluation_seed=23,
            vector=(0.0, 0.0),
        )


def test_incomplete_or_mixed_encoder_observation_matrix_is_rejected() -> None:
    visual_state = _visual_state()
    observations = _observations(29)
    with pytest.raises(ValueError, match="requires current, desired, broken"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=visual_state,
            observations=observations[:-1],
        )

    mixed = (
        *observations[:-1],
        _observation(
            scene=SCENES["option_b"],
            evaluation_seed=29,
            vector=(0.2, 0.8),
            encoder=_encoder_identity(revision="encoder-revision-2"),
            render_batch=observations[0].render_batch,
        ),
    )
    with pytest.raises(ValueError, match="one exact encoder"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=visual_state,
            observations=mixed,
        )


def test_bound_observation_rejects_caller_chosen_evaluation_seed() -> None:
    valid = _observations(31)[0]

    with pytest.raises(ValueError, match="render batch root seed"):
        BoundVisualEmbedding.create(
            role=valid.role,
            evaluation_seed=valid.evaluation_seed + 1,
            render_batch=valid.render_batch,
            scene_spec=valid.scene_spec,
            image=valid.image,
            imagined=valid.imagined,
            encoding=valid.encoding,
            vector=valid.vector,
        )


def test_matrix_rejects_mixed_render_batches_and_renderer_identities() -> None:
    visual_state = _visual_state()
    observations = _observations(37)
    another_batch = _render_batch(37, warnings=("different exact batch",))
    mixed_batches = (
        *observations[:-1],
        _observation(
            scene=SCENES["option_b"],
            evaluation_seed=37,
            vector=(0.2, 0.8),
            render_batch=another_batch,
        ),
    )
    with pytest.raises(ValueError, match="one exact render batch"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=visual_state,
            observations=mixed_batches,
        )

    mixed_renderer_batch = _render_batch(
        41,
        renderer_overrides={
            "option_b": _renderer_identity(revision="f" * 40),
        },
    )
    with pytest.raises(ValueError, match="one exact renderer identity"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=visual_state,
            observations=_observations(
                41,
                render_batch=mixed_renderer_batch,
            ),
        )


def test_matrix_rejects_mixed_pipeline_runtime_and_encoding_specs() -> None:
    visual_state = _visual_state()
    mixed_pipeline_batch = _render_batch(
        43,
        runtime_profile_overrides={"option_b": "runtime-profile-2"},
    )
    with pytest.raises(ValueError, match="one exact pipeline spec per render mode"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=visual_state,
            observations=_observations(
                43,
                render_batch=mixed_pipeline_batch,
            ),
        )

    observations = _observations(47)
    mixed_encoding_specs = (
        *observations[:-1],
        _observation(
            scene=SCENES["option_b"],
            evaluation_seed=47,
            vector=(0.2, 0.8),
            render_batch=observations[0].render_batch,
            encoding_spec_revision="feature-spec-revision-2",
        ),
    )
    with pytest.raises(ValueError, match="one exact image encoding spec"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=visual_state,
            observations=mixed_encoding_specs,
        )


def test_rollouts_require_the_exact_current_image_from_their_batch() -> None:
    wrong_source_batch = _render_batch(53, rollout_source_key="desired")

    with pytest.raises(ValueError, match="exact current-scene image"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=_visual_state(),
            observations=_observations(
                53,
                render_batch=wrong_source_batch,
            ),
        )


def test_prompt_profile_is_explicit_and_exact_across_the_cohort() -> None:
    no_profile = {
        key: (None, None, None)
        for key in ("current", "desired", "broken", "option_a", "option_b")
    }
    legacy_batch = _render_batch(59, prompt_profile_overrides=no_profile)
    with pytest.raises(ValueError, match="explicit prompt language"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=_visual_state(),
            observations=_observations(59, render_batch=legacy_batch),
        )

    mixed_profile_batch = _render_batch(
        61,
        prompt_profile_overrides={
            "option_b": ("en", "visual-style-2", "b" * 64),
        },
    )
    with pytest.raises(ValueError, match="one exact prompt language/style profile"):
        evaluate_visual_valuation(
            policy=_policy(),
            visual_state=_visual_state(),
            observations=_observations(
                61,
                render_batch=mixed_profile_batch,
            ),
        )
