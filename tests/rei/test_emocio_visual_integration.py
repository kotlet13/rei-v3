from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib

import pytest

from app.backend.rei.emocio import (
    ApprovedVisualPromptProfile,
    BilingualStructuredScenePromptCompiler,
    CurrentFirstEmocioRenderer,
    PinnedVisualInfluenceAuthority,
    RenderSettings,
    ReviewedVisualCohortCell,
    VisualCognitionFailure,
    VisualNativeInfluenceApproval,
    VisualPromptProfile,
    VisualValuationPolicy,
    VisualValuationPolicyConfig,
    process_emocio,
    visual_cognition_prompt_batch_hash,
    visual_cognition_runtime_profile_hash,
)
from app.backend.rei.emocio import visual_integration
from app.backend.rei.emocio.runtime import EmocioProcessingArtifact
from app.backend.rei.emocio.vector_encoding import (
    canonical_l2_float32_le_vector,
)
from app.backend.rei.ids import canonical_json_bytes, content_id
from app.backend.rei.models.emocio import ImageArtifact
from app.backend.rei.models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_contract,
)
from app.backend.rei.models.rendering import (
    ImagePipelineSpec,
    ImageRenderItemOutcome,
    ImageRenderRequest,
)
from app.backend.rei.providers.protocols import (
    ImageEncodingRequest,
    ImageEncodingSpec,
    VerifiedImageEncoding,
    build_image_encoding_call_spec,
)
from tests.rei.test_emocio import _scene, _world


def _renderer_identity(
    suffix: str = "primary",
    revision: str = "0123456789abcdef0123456789abcdef01234567",
) -> ProviderIdentity:
    return ProviderIdentity(
        provider_id=f"visual_integration_renderer_{suffix}",
        kind="image_renderer",
        implementation="tests.VisualIntegrationRenderer",
        implementation_revision="1",
        uses_model=True,
        model=f"test/visual-renderer-{suffix}",
        model_revision=revision,
    )


def _encoder_identity() -> ProviderIdentity:
    return ProviderIdentity(
        provider_id="visual_integration_encoder",
        kind="image_encoder",
        implementation="tests.VisualIntegrationEncoder",
        implementation_revision="1",
        uses_model=True,
        model="test/visual-encoder",
        model_revision="encoder-revision-1",
    )


def _parameters(**values: object) -> tuple[ProviderParameter, ...]:
    return tuple(
        ProviderParameter(
            name=name,
            canonical_json_value=canonical_json_bytes(value).decode("utf-8"),
        )
        for name, value in sorted(values.items())
    )


class DeterministicVisualRenderer:
    def __init__(self, identity: ProviderIdentity | None = None) -> None:
        self._identity = identity or _renderer_identity()
        self.calls = 0

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def pipeline_spec(self, mode: str) -> ImagePipelineSpec:
        return ImagePipelineSpec(
            implementation="tests.VisualIntegrationPipeline",
            implementation_revision="1",
            parameters=_parameters(
                conditioning_method=(
                    "reference_image" if mode == "image_to_image" else "none"
                ),
                runtime_profile="deterministic-visual-integration-v1",
            ),
        )

    def render(
        self,
        request: ImageRenderRequest,
        *,
        call: ProviderCallSpec,
    ) -> ImageRenderItemOutcome:
        ensure_call_contract(
            self.identity,
            call,
            request_id=request.request_id,
            seed=request.seed,
            expected_kind="image_renderer",
            required_input_artifact_ids=request.input_artifact_ids,
        )
        self.calls += 1
        content_sha256 = hashlib.sha256(
            canonical_json_bytes(
                {
                    "request_id": request.request_id,
                    "synthetic_png": True,
                }
            )
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
            render_call_id=call.call_id,
            source_spec_id=request.source_spec_id,
            provider_id=self.identity.provider_id,
            model=self.identity.model,
            model_revision=self.identity.model_revision,
            seed=request.seed,
            input_spec_hash=request.source_spec_hash,
            content_sha256=content_sha256,
            media_type="image/png",
            grounded=False,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            path=f"emocio/images/{image_id}.png",
            width=request.width,
            height=request.height,
            generated_only_elements=("synthetic imagined detail",),
        )
        started = datetime(2026, 7, 14, 9, tzinfo=UTC) + timedelta(
            milliseconds=self.calls
        )
        finished = started + timedelta(milliseconds=1)
        record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=call.provider,
            seed=call.seed,
            parameters=call.parameters,
            timeout_seconds=call.timeout_seconds,
            started_at=started,
            primary_finished_at=finished,
            finished_at=finished,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(image.image_id,),
        )
        return ImageRenderItemOutcome.create(
            request=request,
            call_spec=call,
            call_record=record,
            artifact=image,
        )


class DeterministicVisualEncoder:
    def __init__(self, vectors_by_scene_id: dict[str, tuple[float, ...]]) -> None:
        self._identity = _encoder_identity()
        self._vectors_by_scene_id = vectors_by_scene_id
        self._vectors_by_encoding_id: dict[str, tuple[float, ...]] = {}
        self.calls = 0

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def encoding_spec(self) -> ImageEncodingSpec:
        return ImageEncodingSpec(
            implementation="tests.VisualIntegrationFeatureBackend",
            implementation_revision="1",
            dimensions=2,
        )

    def request_for(self, image: ImageArtifact) -> ImageEncodingRequest:
        return ImageEncodingRequest.create(
            image=image,
            provider=self.identity,
            spec=self.encoding_spec(),
        )

    def build_call_spec(
        self,
        image: ImageArtifact,
        *,
        timeout_seconds: float,
    ) -> ProviderCallSpec:
        request = self.request_for(image)
        return build_image_encoding_call_spec(
            request,
            timeout_seconds=timeout_seconds,
        )

    def encode(
        self,
        image: ImageArtifact,
        *,
        call: ProviderCallSpec,
    ) -> VerifiedImageEncoding:
        request = self.request_for(image)
        ensure_call_contract(
            self.identity,
            call,
            request_id=request.request_id,
            seed=0,
            expected_kind="image_encoder",
            required_input_artifact_ids=(image.image_id,),
        )
        raw_vector = self._vectors_by_scene_id[image.source_spec_id]
        _, vector, vector_hash = canonical_l2_float32_le_vector(raw_vector)
        vector_ref = f"emocio/embeddings/{vector_hash}.f32"
        encoding_id = VerifiedImageEncoding.derive_id(
            request=request,
            vector_ref=vector_ref,
            vector_hash=vector_hash,
            dimensions=len(vector),
        )
        self.calls += 1
        started = datetime(2026, 7, 14, 10, tzinfo=UTC) + timedelta(
            milliseconds=self.calls
        )
        finished = started + timedelta(milliseconds=1)
        record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=call.provider,
            seed=call.seed,
            parameters=call.parameters,
            timeout_seconds=call.timeout_seconds,
            started_at=started,
            primary_finished_at=finished,
            finished_at=finished,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(encoding_id,),
        )
        encoding = VerifiedImageEncoding.create(
            request=request,
            vector_ref=vector_ref,
            vector_hash=vector_hash,
            dimensions=len(vector),
            call_spec=call,
            call=record,
        )
        self._vectors_by_encoding_id[encoding.encoding_id] = vector
        return encoding

    def read_vector(
        self,
        encoding: VerifiedImageEncoding,
    ) -> tuple[float, ...]:
        return self._vectors_by_encoding_id[encoding.encoding_id]


def _digest(*parts: object) -> str:
    return hashlib.sha256(canonical_json_bytes(parts)).hexdigest()


def _pin_visual_authority(
    monkeypatch: pytest.MonkeyPatch,
    authority: PinnedVisualInfluenceAuthority,
) -> None:
    monkeypatch.setattr(
        visual_integration,
        "REPOSITORY_PINNED_VISUAL_INFLUENCE_AUTHORITIES",
        frozenset({(authority.authority_id, authority.content_hash())}),
    )


def _visual_dependencies():
    baseline = process_emocio(_scene(), _world())
    visual_state = baseline.visual_state
    vectors = {
        visual_state.current_scene.scene_id: (1.0, 0.0),
        visual_state.desired_scene.scene_id: (1.0, 0.0),
        visual_state.broken_scene.scene_id: (0.0, 1.0),
        **{
            rollout.scene_id: (
                (1.0, 0.0)
                if rollout.option_id == "option_broken"
                else (0.0, 1.0)
            )
            for rollout in visual_state.option_rollouts
        },
    }
    renderer_identities = (
        _renderer_identity(),
        _renderer_identity(
            "alternate",
            "89abcdef0123456789abcdef0123456789abcdef",
        ),
    )
    renderer_provider = DeterministicVisualRenderer(renderer_identities[0])
    visual_profiles = tuple(
        VisualPromptProfile.create(
            language=language,
            style_id=style_id,
            style_directive=style_directive,
        )
        for language, style_id, style_directive in (
            ("en", "style_a", "flat deterministic geometry"),
            ("en", "style_b", "alternate deterministic geometry"),
            ("sl", "style_a", "flat deterministic geometry"),
            ("sl", "style_b", "alternate deterministic geometry"),
        )
    )
    runtime_profile = next(
        profile
        for profile in visual_profiles
        if profile.language == "en" and profile.style_id == "style_a"
    )
    renderer = CurrentFirstEmocioRenderer(
        provider=renderer_provider,
        settings=RenderSettings(
            width=32,
            height=32,
            num_inference_steps=2,
            guidance_scale=0.0,
            negative_prompt="",
            timeout_seconds=5.0,
        ),
        prompt_compiler=BilingualStructuredScenePromptCompiler(runtime_profile),
    )
    encoder = DeterministicVisualEncoder(vectors)
    policy_config = VisualValuationPolicyConfig.create(
        policy=VisualValuationPolicy.create(
            structured_weight=0.0,
            desired_similarity_weight=1.0,
            broken_avoidance_weight=1.0,
            seed_consistency_penalty=0.0,
            uncertainty_penalty=0.0,
        )
    )

    preflight = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=policy_config,
    )
    assert preflight.cognition_trace.fallback_reason == "visual_approval_unavailable"
    assert preflight.visual_valuation is not None
    assert preflight.visual_valuation.integration_disposition == "usable"
    assert preflight.visual_valuation.leading_option_id == "option_broken"

    actual_runtime_hash = visual_cognition_runtime_profile_hash(
        preflight.visual_observations
    )
    actual_prompt_batch_hash = visual_cognition_prompt_batch_hash(
        preflight.visual_observations
    )
    encoding_spec_hash = preflight.visual_observations[
        0
    ].encoding.request.spec.content_hash()
    ranked_scores = sorted(
        (
            score.fused_score
            for score in preflight.visual_valuation.option_scores
        ),
        reverse=True,
    )
    actual_margin = round(ranked_scores[0] - ranked_scores[1], 12)
    assert actual_margin > 0.0

    approved_profiles = tuple(
        ApprovedVisualPromptProfile(
            language=profile.language,
            style_id=profile.style_id,
            profile_hash=profile.content_hash(),
        )
        for profile in visual_profiles
    )
    state_hash = visual_state.content_hash()
    canonical_order = tuple(option.option_id for option in _scene().options)
    option_orders = (canonical_order, tuple(reversed(canonical_order)))
    runtime_hashes: dict[tuple[str, str], str] = {}
    for renderer_identity in renderer_identities:
        for profile in approved_profiles:
            scope = (renderer_identity.provider_id, profile.profile_hash)
            runtime_hashes[scope] = (
                actual_runtime_hash
                if renderer_identity == renderer_identities[0]
                and profile.language == "en"
                and profile.style_id == "style_a"
                else _digest("synthetic-runtime-profile", *scope)
            )

    cohort_cells = tuple(
        ReviewedVisualCohortCell(
            visual_state_hash=state_hash,
            evaluation_seed=seed,
            renderer_identity=renderer_identity,
            prompt_profile=profile,
            option_order=option_order,
            encoding_spec_hash=encoding_spec_hash,
            runtime_profile_hash=runtime_hashes[
                (renderer_identity.provider_id, profile.profile_hash)
            ],
            prompt_batch_hash=(
                actual_prompt_batch_hash
                if seed == 41
                and renderer_identity == renderer_identities[0]
                and profile.language == "en"
                and profile.style_id == "style_a"
                else _digest(
                    "synthetic-prompt-batch",
                    state_hash,
                    seed,
                    renderer_identity.provider_id,
                    profile.profile_hash,
                )
            ),
            approved_leading_option_id="option_broken",
            minimum_leading_margin=min(actual_margin, 0.5),
            evidence_hash=_digest(
                "synthetic-reviewed-cell",
                state_hash,
                seed,
                renderer_identity.provider_id,
                profile.profile_hash,
                option_order,
            ),
        )
        for seed in (40, 41, 42)
        for renderer_identity in renderer_identities
        for profile in approved_profiles
        for option_order in option_orders
    )
    approval = VisualNativeInfluenceApproval.create(
        policy_config=policy_config,
        encoder_identity=encoder.identity,
        approved_renderer_identities=renderer_identities,
        evaluated_seeds=(40, 41, 42),
        approved_prompt_profiles=approved_profiles,
        reviewed_visual_state_hashes=(state_hash,),
        approved_encoding_spec_hashes=(encoding_spec_hash,),
        approved_runtime_profile_hashes=tuple(
            sorted(set(runtime_hashes.values()))
        ),
        reviewed_cohort_cells=cohort_cells,
        robustness_report_hash="a" * 64,
        semantic_review_record_hash="b" * 64,
        review_authority="synthetic-test-review",
    )
    authority = PinnedVisualInfluenceAuthority.create(
        authority_name="synthetic-test-authority",
        trust_root_hash=_digest("synthetic-trust-root", approval.content_hash()),
        admitted_approvals=(approval,),
    )
    return baseline, renderer, encoder, policy_config, approval, authority


def test_only_approved_visual_mode_can_change_native_conclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline, renderer, encoder, config, approval, authority = (
        _visual_dependencies()
    )
    _pin_visual_authority(monkeypatch, authority)

    visual = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
        visual_influence_approval=approval,
        visual_influence_authority=authority,
    )

    assert baseline.native_conclusion.option_id == "option_desired"
    assert visual.native_conclusion.option_id == "option_broken"
    assert visual.structured_native_conclusion == baseline.native_conclusion
    assert visual.policy == baseline.policy
    assert visual.effective_policy != visual.policy
    assert visual.effective_policy.selected is not None
    assert visual.effective_policy.selected.option_id == "option_broken"
    assert visual.cognition_trace.effective_mode == "visual_cognition"
    assert visual.cognition_trace.conclusion_source == "approved_visual_valuation"
    assert visual.cognition_trace.source_visual_influence_authority_id == (
        authority.authority_id
    )
    assert visual.cognition_trace.source_visual_influence_authority_hash == (
        authority.content_hash()
    )
    assert visual.visual_valuation is not None
    assert visual.visual_valuation.leading_option_id == "option_broken"
    assert len(visual.visual_observations) == 5
    assert len(visual.visual_memories) == 2
    assert visual.native_conclusion.source_visual_valuation_result_id == (
        visual.visual_valuation.result_id
    )
    assert visual.stage_order[-2:] == ("visual_approval", "native_conclusion")
    visual.validate_against(_scene(), _world())


def test_usable_but_unapproved_visual_result_falls_back_exactly() -> None:
    baseline, renderer, encoder, config, _, _ = _visual_dependencies()

    result = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
    )

    assert result.visual_valuation is not None
    assert result.visual_valuation.integration_disposition == "usable"
    assert result.cognition_trace.effective_mode == "render_observe"
    assert result.cognition_trace.fallback_reason == "visual_approval_unavailable"
    assert result.native_conclusion == baseline.native_conclusion
    assert result.native_conclusion.canonical_json_bytes() == (
        baseline.native_conclusion.canonical_json_bytes()
    )
    assert result.effective_policy == baseline.policy


def test_structured_baseline_bytes_and_ids_remain_locked() -> None:
    result = process_emocio(_scene(), _world())

    assert result.packet.content_hash() == (
        "a9e029d224cb08c563d7dc9f3bbca93d80ecccd0b2f3a929274cb0da7185b1bd"
    )
    assert result.visual_state.content_hash() == (
        "8fc6eab85957037e21513f296256b2c670d99530b32fdd9108aee735bfe3dacd"
    )
    assert result.native_conclusion.content_hash() == (
        "d6aacf160601893566609cfb00a16931e392cbfa18a1ce982b55c3d0f4a0479a"
    )
    assert len(result.native_conclusion.canonical_json_bytes()) == 1148


def test_visual_encoding_failure_preserves_partial_provenance_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline, renderer, encoder, config, _, _ = _visual_dependencies()
    original_encode = encoder.encode
    call_count = 0
    secret = "sk-secret-do-not-persist"
    absolute_path = r"C:\Users\Kotlet\private\visual-encoding.bin"

    def fail_second_encoding(
        image: ImageArtifact,
        *,
        call: ProviderCallSpec,
    ) -> VerifiedImageEncoding:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError(f"{secret} at {absolute_path}")
        return original_encode(image, call=call)

    monkeypatch.setattr(encoder, "encode", fail_second_encoding)

    result = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
    )

    assert result.cognition_trace.fallback_reason == "visual_encoding_failed"
    assert result.cognition_trace.effective_mode == "render_observe"
    assert result.native_conclusion == baseline.native_conclusion
    assert len(result.visual_observations) == 1
    assert result.visual_failure is not None
    assert result.visual_failure.stage == "encoding"
    assert result.visual_failure.attempted_call_spec is not None
    assert result.visual_failure.attempted_call_record is not None
    assert result.visual_failure.attempted_call_record.status == "failed"
    assert result.visual_failure.attempted_call_record.output_artifact_ids == ()
    assert result.visual_failure.observation_ids == (
        result.visual_observations[0].observation_id,
    )
    assert result.visual_warning is not None
    persisted_failure = result.visual_failure.canonical_json_bytes().decode("utf-8")
    persisted_text = f"{result.visual_warning}\n{persisted_failure}"
    assert secret not in persisted_text
    assert absolute_path not in persisted_text
    assert "Kotlet" not in persisted_text


def test_successful_encoder_warnings_are_redacted_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, renderer, encoder, config, _, _ = _visual_dependencies()
    original_encode = encoder.encode
    secret = "sk-c4-success-warning-must-not-persist"

    def encode_with_warning(
        image: ImageArtifact,
        *,
        call: ProviderCallSpec,
    ) -> VerifiedImageEncoding:
        encoding = original_encode(image, call=call)
        warned_record = encoding.call.model_copy(
            update={"warnings": (secret,)}
        )
        return VerifiedImageEncoding.create(
            request=encoding.request,
            vector_ref=encoding.vector_ref,
            vector_hash=encoding.vector_hash,
            dimensions=encoding.dimensions,
            call_spec=encoding.call_spec,
            call=warned_record,
        )

    monkeypatch.setattr(encoder, "encode", encode_with_warning)
    result = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
    )

    assert len(result.visual_observations) == 5
    assert all(
        observation.encoding.call.warnings == ()
        for observation in result.visual_observations
    )
    assert secret.encode("utf-8") not in (
        EmocioProcessingArtifact.create(result).canonical_json_bytes()
    )


def test_unapproved_encoder_call_text_is_rejected_without_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, renderer, encoder, config, _, _ = _visual_dependencies()
    original_build = encoder.build_call_spec
    calls_before = encoder.calls
    secret = "C4-UNAPPROVED-ENCODER-FALLBACK-SECRET"

    def build_unapproved_call(
        image: ImageArtifact,
        *,
        timeout_seconds: float,
    ) -> ProviderCallSpec:
        call = original_build(image, timeout_seconds=timeout_seconds)
        payload = call.model_dump(
            mode="python",
            round_trip=True,
            exclude={"call_id"},
        )
        payload["fallback_policy"] = ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason=secret,
        )
        return ProviderCallSpec(
            call_id=content_id("image_encoding_call", payload),
            **payload,
        )

    monkeypatch.setattr(encoder, "build_call_spec", build_unapproved_call)
    result = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
    )

    assert encoder.calls == calls_before
    assert result.visual_failure is not None
    assert result.visual_failure.stage == "encoding"
    assert result.visual_failure.attempted_call_spec is None
    assert secret.encode("utf-8") not in (
        EmocioProcessingArtifact.create(result).canonical_json_bytes()
    )


def test_visual_encoding_failure_rejects_foreign_partial_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, renderer, encoder, config, _, _ = _visual_dependencies()
    original_encode = encoder.encode
    call_count = 0

    def fail_second_encoding(
        image: ImageArtifact,
        *,
        call: ProviderCallSpec,
    ) -> VerifiedImageEncoding:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("synthetic partial encoding failure")
        return original_encode(image, call=call)

    monkeypatch.setattr(encoder, "encode", fail_second_encoding)
    failed = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
    )
    assert failed.render_batch is not None
    assert failed.visual_failure is not None
    assert len(failed.visual_observations) == 1

    monkeypatch.setattr(encoder, "encode", original_encode)
    foreign_run = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=42,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
    )
    assert len(foreign_run.visual_observations) == 5
    foreign_observation = foreign_run.visual_observations[0]
    assert foreign_observation.render_batch != failed.render_batch

    forged_failure = VisualCognitionFailure.create(
        stage="encoding",
        error=RuntimeError("synthetic foreign partial observation"),
        render_batch=failed.render_batch,
        observations=(foreign_observation,),
        attempted_call_spec=failed.visual_failure.attempted_call_spec,
    )
    forged = replace(
        failed,
        visual_observations=(foreign_observation,),
        visual_failure=forged_failure,
    )

    with pytest.raises(ValueError, match="another render batch"):
        forged.validate_against(_scene(), _world())


def test_unpinned_visual_authority_fails_closed() -> None:
    baseline, renderer, encoder, config, approval, authority = (
        _visual_dependencies()
    )
    assert (
        authority.authority_id,
        authority.content_hash(),
    ) not in visual_integration.REPOSITORY_PINNED_VISUAL_INFLUENCE_AUTHORITIES

    result = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
        visual_influence_approval=approval,
        visual_influence_authority=authority,
    )

    assert result.cognition_trace.fallback_reason == "visual_approval_mismatch"
    assert result.cognition_trace.effective_mode == "render_observe"
    assert result.native_conclusion == baseline.native_conclusion
    assert result.effective_policy == baseline.policy
    assert result.visual_failure is not None
    assert result.visual_failure.stage == "approval"
    assert result.visual_failure.failure_code == "visual_approval_failure"
    assert result.visual_warning == (
        "Visual cognition approval failed closed (visual_approval_failure)"
    )
    result.validate_against(_scene(), _world())


def test_visual_approval_rejects_runtime_seed_outside_reviewed_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline, renderer, encoder, config, approval, authority = (
        _visual_dependencies()
    )
    _pin_visual_authority(monkeypatch, authority)
    assert 99 not in approval.evaluated_seeds

    result = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=99,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
        visual_influence_approval=approval,
        visual_influence_authority=authority,
    )

    assert result.cognition_trace.fallback_reason == "visual_approval_mismatch"
    assert result.cognition_trace.effective_mode == "render_observe"
    assert result.native_conclusion == baseline.native_conclusion
    assert result.visual_failure is not None
    assert result.visual_failure.failure_code == "visual_approval_failure"
    assert result.visual_warning == (
        "Visual cognition approval failed closed (visual_approval_failure)"
    )


def test_visual_action_collapse_is_typed_and_cannot_influence_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline, renderer, encoder, config, approval, authority = (
        _visual_dependencies()
    )
    _pin_visual_authority(monkeypatch, authority)
    rollout_ids = tuple(
        rollout.scene_id for rollout in baseline.visual_state.option_rollouts
    )
    for scene_id in rollout_ids:
        encoder._vectors_by_scene_id[scene_id] = (1.0, 0.0)

    result = process_emocio(
        _scene(),
        _world(),
        renderer=renderer,
        render_seed=41,
        cognition_mode="visual_cognition",
        image_encoder=encoder,
        visual_policy_config=config,
        visual_influence_approval=approval,
        visual_influence_authority=authority,
    )

    assert result.visual_valuation is not None
    assert result.visual_valuation.action_collapse.detected is True
    assert result.cognition_trace.fallback_reason == "visual_action_collapse"
    assert result.native_conclusion == baseline.native_conclusion


def test_visual_influence_approval_requires_full_robustness_scope() -> None:
    _, _, encoder, config, approval, _ = _visual_dependencies()

    with pytest.raises(ValueError, match="at least 2 items"):
        VisualNativeInfluenceApproval.create(
            policy_config=config,
            encoder_identity=encoder.identity,
            approved_renderer_identities=(_renderer_identity(),),
            evaluated_seeds=approval.evaluated_seeds,
            approved_prompt_profiles=approval.approved_prompt_profiles,
            reviewed_visual_state_hashes=approval.reviewed_visual_state_hashes,
            approved_encoding_spec_hashes=approval.approved_encoding_spec_hashes,
            approved_runtime_profile_hashes=(
                approval.approved_runtime_profile_hashes
            ),
            reviewed_cohort_cells=approval.reviewed_cohort_cells,
            robustness_report_hash="d" * 64,
            semantic_review_record_hash="e" * 64,
            review_authority="incomplete-review",
        )
