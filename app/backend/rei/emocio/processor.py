"""End-to-end deterministic Emocio structured native processor."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ..ids import content_id
from ..models.emocio import (
    EmocioCognitionFallbackReason,
    EmocioCognitionMode,
    EmocioCognitionTrace,
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioVisualState,
    EmocioWorld,
    ImageArtifact,
)
from ..models.scene import SceneEvent
from ..models.rendering import ImageRenderBatchOutcome
from ..providers.protocols import VerifiedImageEncoder
from .packets import build_emocio_packet
from .policy import EmocioPolicyDecision, choose_native_option
from .renderer import (
    EmocioRenderer,
    validate_render_batch,
    validate_renderer_outputs,
)
from .scene_graph import compile_emocio_scenes
from .valuation import build_emocio_visual_state
from .visual_integration import (
    PinnedVisualInfluenceAuthority,
    VisualCognitionFailure,
    VisualNativeInfluenceApproval,
    VisualObservationBuildError,
    build_visual_observations,
    policy_from_visual_valuation,
    require_repository_pinned_visual_authority,
    visual_failure_summary,
)
from .visual_policy_config import VisualValuationPolicyConfig
from .visual_valuation import (
    BoundVisualEmbedding,
    VisualValuationResult,
    evaluate_visual_valuation,
)
from .visual_world_memory import (
    VisualWorldMemoryRecord,
    build_visual_world_memory_record,
)


@dataclass(frozen=True, slots=True)
class EmocioProcessingResult:
    source_scene_hash: str
    source_world_id: str
    source_world_hash: str
    packet: EmocioInputPacket
    visual_state: EmocioVisualState
    structured_native_conclusion: EmocioNativeConclusion
    native_conclusion: EmocioNativeConclusion
    # Historical public field: always the deterministic structured baseline.
    policy: EmocioPolicyDecision
    cognition_trace: EmocioCognitionTrace
    rendered_images: tuple[ImageArtifact, ...]
    render_batch: ImageRenderBatchOutcome | None
    render_seed: int | None
    renderer_warning: str | None
    visual_policy_config: VisualValuationPolicyConfig | None
    visual_observations: tuple[BoundVisualEmbedding, ...]
    visual_valuation: VisualValuationResult | None
    visual_memories: tuple[VisualWorldMemoryRecord, ...]
    visual_influence_approval: VisualNativeInfluenceApproval | None
    visual_influence_authority: PinnedVisualInfluenceAuthority | None
    visual_failure: VisualCognitionFailure | None
    visual_warning: str | None
    stage_order: tuple[str, ...]

    @property
    def effective_policy(self) -> EmocioPolicyDecision:
        """Policy that produced ``native_conclusion``; ``policy`` stays legacy-safe."""

        if self.cognition_trace.conclusion_source == "approved_visual_valuation":
            if self.visual_valuation is None:
                raise ValueError(
                    "Approved visual conclusion is missing its effective valuation"
                )
            return policy_from_visual_valuation(
                visual_state=self.visual_state,
                valuation=self.visual_valuation,
            )
        return self.policy

    def validate_against(self, scene: SceneEvent, world: EmocioWorld) -> None:
        """Replay the structured baseline and any admitted visual influence."""

        if self.source_scene_hash != scene.scene_hash():
            raise ValueError("Emocio result source scene hash differs")
        if (
            self.source_world_id != world.world_id
            or self.source_world_hash != world.content_hash()
        ):
            raise ValueError("Emocio result source world lineage differs")
        validated_trace = EmocioCognitionTrace.model_validate(
            self.cognition_trace.model_dump(mode="python", round_trip=True)
        )
        if validated_trace != self.cognition_trace:
            raise ValueError("Emocio cognition trace differs from strict replay")
        if (
            self.cognition_trace.requested_mode == "structured_only"
            and (
                self.rendered_images
                or self.render_batch is not None
                or self.render_seed is not None
                or "render" in self.stage_order
            )
        ):
            raise ValueError("structured_only cognition cannot execute a renderer")
        if (
            self.cognition_trace.effective_mode == "render_observe"
            and not self.rendered_images
        ):
            raise ValueError("render_observe requires at least one validated image")
        if (
            self.cognition_trace.effective_mode == "visual_cognition"
            and not self.visual_observations
        ):
            raise ValueError("visual_cognition requires verified visual observations")
        if (
            self.cognition_trace.requested_mode != "visual_cognition"
            and (
                self.visual_policy_config is not None
                or self.visual_observations
                or self.visual_valuation is not None
                or self.visual_memories
                or self.visual_influence_approval is not None
                or self.visual_influence_authority is not None
                or self.visual_failure is not None
                or self.visual_warning is not None
            )
        ):
            raise ValueError(
                "Non-visual cognition cannot carry visual valuation artifacts"
            )
        # B11 may admit an exact, content-addressed longitudinal projection in
        # the packet. Revalidate that approved packet against the scene, then
        # replay every downstream stage from it; rebuilding a projection-free
        # default here would erase valid history lineage.
        self.packet.validate_against(scene)
        compiled = compile_emocio_scenes(scene, self.packet, world)
        expected_state = build_emocio_visual_state(
            scene=scene,
            packet=self.packet,
            world=world,
            compiled=compiled,
        )
        if self.visual_state != expected_state:
            raise ValueError("Emocio visual state differs from deterministic replay")
        expected_policy = choose_native_option(self.visual_state.option_valuations)
        if self.policy != expected_policy:
            raise ValueError(
                "Emocio structured policy differs from deterministic replay"
            )
        expected_structured_conclusion = _native_conclusion(
            packet=self.packet,
            visual_state=self.visual_state,
            policy=self.policy,
        )
        if self.structured_native_conclusion != expected_structured_conclusion:
            raise ValueError(
                "Emocio structured conclusion differs from deterministic replay"
            )
        scenes = (
            self.visual_state.current_scene,
            self.visual_state.desired_scene,
            self.visual_state.broken_scene,
            *self.visual_state.option_rollouts,
        )
        if self.render_batch is not None:
            validate_render_batch(
                self.render_batch,
                scenes,
                expected_seed=self.render_seed,
            )
            if self.rendered_images != self.render_batch.artifacts:
                raise ValueError("Rendered images differ from the B7 batch provenance")
        else:
            validate_renderer_outputs(
                self.rendered_images,
                scenes,
                expected_seed=self.render_seed,
            )

        observations = tuple(
            BoundVisualEmbedding.model_validate(
                observation.model_dump(mode="python", round_trip=True)
            )
            for observation in self.visual_observations
        )
        if observations != self.visual_observations:
            raise ValueError("Visual observations differ from strict replay")
        if observations:
            if self.render_batch is None:
                raise ValueError(
                    "Visual observations require their exact render batch"
                )
            if any(
                observation.render_batch != self.render_batch
                for observation in observations
            ):
                raise ValueError(
                    "Visual observation belongs to another render batch"
                )
            expected_scene_ids = tuple(scene.scene_id for scene in scenes)
            observation_scene_ids = tuple(
                observation.scene_spec.scene_id for observation in observations
            )
            if self.cognition_trace.fallback_reason == "visual_encoding_failed":
                if (
                    len(observation_scene_ids) >= len(expected_scene_ids)
                    or observation_scene_ids
                    != expected_scene_ids[: len(observation_scene_ids)]
                ):
                    raise ValueError(
                        "Partial visual observations must be the strict scene prefix"
                    )
            elif observation_scene_ids != expected_scene_ids:
                raise ValueError(
                    "Completed visual observations must cover every scene in order"
                )
        config = None
        if self.visual_policy_config is not None:
            config = VisualValuationPolicyConfig.model_validate(
                self.visual_policy_config.model_dump(
                    mode="python",
                    round_trip=True,
                )
            )
            if config != self.visual_policy_config:
                raise ValueError("Visual policy config differs from strict replay")
        valuation = None
        if self.visual_valuation is not None:
            if config is None or not observations:
                raise ValueError(
                    "Visual valuation requires its config and observations"
                )
            valuation = VisualValuationResult.model_validate(
                self.visual_valuation.model_dump(mode="python", round_trip=True)
            )
            valuation.validate_against(
                visual_state=self.visual_state,
                observations=observations,
                include_cross_seed_consistency=False,
            )
            if valuation.policy != config.policy:
                raise ValueError(
                    "Visual valuation policy differs from its admitted config"
                )
        elif self.visual_memories:
            raise ValueError(
                "Visual memories cannot outlive a missing valuation"
            )
        elif observations and self.cognition_trace.fallback_reason not in {
            "visual_encoding_failed",
            "visual_valuation_failed",
        }:
            raise ValueError(
                "Observations without a valuation require a typed encoding or "
                "valuation failure"
            )

        memories = tuple(
            VisualWorldMemoryRecord.model_validate(
                memory.model_dump(mode="python", round_trip=True)
            )
            for memory in self.visual_memories
        )
        if (
            valuation is not None
            and self.cognition_trace.fallback_reason != "visual_memory_failed"
        ):
            expected_memories = tuple(
                build_visual_world_memory_record(
                    observation=observation,
                    valuation=valuation,
                    visual_state=self.visual_state,
                    observations=observations,
                )
                for observation in observations
                if observation.role == "option_rollout"
            )
            if memories != expected_memories:
                raise ValueError(
                    "Visual-world memories differ from deterministic replay"
                )
        elif self.cognition_trace.fallback_reason == "visual_memory_failed" and memories:
            raise ValueError("Failed visual memory construction cannot publish memories")

        approval = None
        if self.visual_influence_approval is not None:
            approval = VisualNativeInfluenceApproval.model_validate(
                self.visual_influence_approval.model_dump(
                    mode="python",
                    round_trip=True,
                )
            )
        authority = None
        if self.visual_influence_authority is not None:
            authority = PinnedVisualInfluenceAuthority.model_validate(
                self.visual_influence_authority.model_dump(
                    mode="python",
                    round_trip=True,
                )
            )
        failure = None
        if self.visual_failure is not None:
            failure = VisualCognitionFailure.model_validate(
                self.visual_failure.model_dump(mode="python", round_trip=True)
            )
            if self.render_batch is None and failure.stage != "render":
                raise ValueError(
                    "Post-render visual failure requires its exact render batch"
                )
            failure.validate_against(
                render_batch=self.render_batch,
                observations=observations,
                valuation=valuation,
                approval=approval,
                authority=authority,
            )
        expected_failure_stages = {
            "visual_encoding_failed": frozenset({"encoding"}),
            "visual_valuation_failed": frozenset(
                {"policy_config", "valuation"}
            ),
            "visual_memory_failed": frozenset({"memory"}),
            "visual_approval_mismatch": frozenset({"approval"}),
        }
        allowed_failure_stages = expected_failure_stages.get(
            self.cognition_trace.fallback_reason
        )
        if (
            self.cognition_trace.fallback_reason == "renderer_failed"
            and self.cognition_trace.requested_mode == "visual_cognition"
            and self.render_batch is None
        ):
            allowed_failure_stages = frozenset({"render"})
        if allowed_failure_stages is None:
            if failure is not None or self.visual_warning is not None:
                raise ValueError(
                    "Non-exception visual fallback cannot carry a failure artifact"
                )
        elif (
            failure is None
            or failure.stage not in allowed_failure_stages
            or self.visual_warning is None
        ):
            raise ValueError(
                "Visual exception fallback requires its typed failure and warning"
            )
        if (
            self.cognition_trace.conclusion_source != "approved_visual_valuation"
            and (approval is not None or authority is not None)
            and (
                self.cognition_trace.fallback_reason
                != "visual_approval_mismatch"
                or failure is None
                or failure.stage != "approval"
            )
        ):
            raise ValueError(
                "Approval artifacts may survive only an exact typed approval attempt"
            )

        if valuation is not None:
            reason = self.cognition_trace.fallback_reason
            if reason == "visual_action_collapse" and (
                valuation.integration_disposition != "review_action_collapse"
            ):
                raise ValueError("Visual action-collapse fallback differs from result")
            if reason == "visual_valuation_tie" and (
                valuation.integration_disposition != "review_tie"
            ):
                raise ValueError("Visual tie fallback differs from result")
            if reason == "visual_approval_unavailable" and (
                valuation.integration_disposition != "usable" or approval is not None
            ):
                raise ValueError(
                    "Unavailable approval fallback differs from usable visual result"
                )
            if reason == "visual_approval_mismatch" and (
                valuation.integration_disposition != "usable"
            ):
                raise ValueError(
                    "Approval mismatch requires an otherwise usable visual result"
                )
        if self.cognition_trace.conclusion_source == "approved_visual_valuation":
            if (
                config is None
                or valuation is None
                or approval is None
                or authority is None
            ):
                raise ValueError(
                    "Approved visual conclusion is missing config, result, approval, "
                    "or authority"
                )
            authority = require_repository_pinned_visual_authority(authority)
            approval = authority.admit(approval)
            approval.validate_against(
                policy_config=config,
                valuation=valuation,
                visual_state=self.visual_state,
                observations=observations,
                option_order=tuple(option.option_id for option in scene.options),
            )
            visual_policy = policy_from_visual_valuation(
                visual_state=self.visual_state,
                valuation=valuation,
            )
            expected_conclusion = _native_conclusion(
                packet=self.packet,
                visual_state=self.visual_state,
                policy=visual_policy,
                visual_valuation=valuation,
                visual_approval=approval,
                visual_authority=authority,
            )
            if (
                self.cognition_trace.source_visual_valuation_result_id
                != valuation.result_id
                or self.cognition_trace.source_visual_valuation_result_hash
                != valuation.content_hash()
                or self.cognition_trace.source_visual_influence_approval_id
                != approval.approval_id
                or self.cognition_trace.source_visual_influence_approval_hash
                != approval.content_hash()
                or self.cognition_trace.source_visual_influence_authority_id
                != authority.authority_id
                or self.cognition_trace.source_visual_influence_authority_hash
                != authority.content_hash()
            ):
                raise ValueError(
                    "Emocio cognition trace differs from visual influence lineage"
                )
        else:
            expected_conclusion = expected_structured_conclusion
        if self.native_conclusion != expected_conclusion:
            raise ValueError(
                "Emocio native conclusion differs from deterministic replay"
            )
        expected_stages = ["packet", "scene_graph", "valuation"]
        if self.cognition_trace.requested_mode != "visual_cognition":
            expected_stages.append("native_conclusion")
            if self.render_seed is not None:
                expected_stages.append("render")
        else:
            if self.render_seed is not None:
                expected_stages.append("render")
            if config is not None:
                expected_stages.append("visual_encoding")
                if (
                    self.cognition_trace.fallback_reason
                    != "visual_encoding_failed"
                ):
                    expected_stages.append("visual_valuation")
            if valuation is not None:
                expected_stages.append("visual_memory")
            if (
                self.cognition_trace.conclusion_source
                == "approved_visual_valuation"
                or self.cognition_trace.fallback_reason
                == "visual_approval_mismatch"
            ):
                expected_stages.append("visual_approval")
            expected_stages.append("native_conclusion")
        if self.stage_order != tuple(expected_stages):
            raise ValueError(
                "Emocio stage order differs from deterministic execution replay"
            )


def _native_conclusion(
    *,
    packet: EmocioInputPacket,
    visual_state: EmocioVisualState,
    policy: EmocioPolicyDecision,
    visual_valuation: VisualValuationResult | None = None,
    visual_approval: VisualNativeInfluenceApproval | None = None,
    visual_authority: PinnedVisualInfluenceAuthority | None = None,
) -> EmocioNativeConclusion:
    visual_inputs = (visual_valuation, visual_approval, visual_authority)
    if any(item is not None for item in visual_inputs) and not all(
        item is not None for item in visual_inputs
    ):
        raise ValueError(
            "Visual native conclusion requires valuation, approval, and authority"
        )
    selected = policy.selected
    if selected is None:
        tied = ", ".join(policy.tied_option_ids)
        uncertainty = (
            f"Izena\u010dena najvi\u0161ja vrednotenja: {tied}."
            if tied
            else "Ni razpolo\u017eljive strukturirane mo\u017enosti."
        )
        option_id = None
        decisive_rollout_scene_id = None
        dimensions = ()
        action_tendency = "unknown"
    else:
        uncertainty = (
            "Enoli\u010dno najvi\u0161je odobreno vizualno-strukturno vrednotenje."
            if visual_valuation is not None
            else "Enoli\u010dno najvi\u0161je transparentno strukturno vrednotenje."
        )
        option_id = selected.option_id
        decisive_rollout_scene_id = selected.rollout_scene_id
        dimensions = selected.dimensions
        action_tendency = "approach"
    desired_transformation = "; ".join(visual_state.desired_scene.composition)
    if not desired_transformation:
        desired_transformation = "\u017delena transformacija ni strukturirano podana."
    main_obstacle = "; ".join(visual_state.broken_scene.obstacle_markers)
    if not main_obstacle:
        main_obstacle = "Strukturirana ovira ni podana."
    aggregate_by_option = {
        item.option_id: item.score for item in policy.aggregate_scores
    }
    intensity = (
        aggregate_by_option[option_id]
        if option_id is not None
        else max(aggregate_by_option.values(), default=0.0)
    )
    payload = {
        "schema_version": "rei-native-emocio-conclusion-v1",
        "source_packet_id": packet.packet_id,
        "source_scene_id": packet.scene_id,
        "mind": "E",
        "option_id": option_id,
        "desired_transformation": desired_transformation,
        "current_scene_id": visual_state.current_scene.scene_id,
        "desired_scene_id": visual_state.desired_scene.scene_id,
        "decisive_rollout_scene_id": decisive_rollout_scene_id,
        "main_obstacle": main_obstacle,
        "action_tendency": action_tendency,
        "valuation_dimensions": dimensions,
        "intensity": intensity,
        "abstains": option_id is None,
        "uncertainty": uncertainty,
    }
    if (
        visual_valuation is not None
        and visual_approval is not None
        and visual_authority is not None
    ):
        if (
            visual_valuation.integration_disposition != "usable"
            or visual_valuation.leading_option_id != option_id
        ):
            raise ValueError(
                "Visual native conclusion differs from its unique approved leader"
            )
        payload.update(
            conclusion_source="approved_visual_valuation",
            source_visual_valuation_result_id=visual_valuation.result_id,
            source_visual_valuation_result_hash=visual_valuation.content_hash(),
            source_visual_influence_approval_id=visual_approval.approval_id,
            source_visual_influence_approval_hash=visual_approval.content_hash(),
            source_visual_influence_authority_id=visual_authority.authority_id,
            source_visual_influence_authority_hash=visual_authority.content_hash(),
        )
    conclusion = EmocioNativeConclusion(
        conclusion_id=content_id(
            "emocio_conclusion",
            {
                "source_packet_hash": packet.content_hash(),
                "source_visual_state_hash": visual_state.content_hash(),
                **payload,
            },
        ),
        **payload,
    )
    conclusion.validate_against(packet, visual_state)
    return conclusion


def process_emocio(
    scene: SceneEvent,
    world: EmocioWorld,
    *,
    renderer: EmocioRenderer | None = None,
    render_seed: int = 0,
    packet: EmocioInputPacket | None = None,
    cognition_mode: EmocioCognitionMode | None = None,
    image_encoder: VerifiedImageEncoder | None = None,
    visual_policy_config: VisualValuationPolicyConfig | None = None,
    visual_influence_approval: VisualNativeInfluenceApproval | None = None,
    visual_influence_authority: PinnedVisualInfluenceAuthority | None = None,
    encoding_timeout_seconds: float = 30.0,
) -> EmocioProcessingResult:
    """Execute one explicit structured, observation, or visual cognition path.

    ``None`` is the compatibility sentinel: a supplied renderer retains the
    historical render-after-conclusion path and no renderer retains the exact
    structured baseline. Explicit ``structured_only`` never invokes a renderer.
    Internal images may influence the final conclusion only when the complete
    verified valuation and a matching semantic robustness approval both replay.
    """

    if (
        not isinstance(encoding_timeout_seconds, (int, float))
        or isinstance(encoding_timeout_seconds, bool)
        or not math.isfinite(encoding_timeout_seconds)
        or encoding_timeout_seconds <= 0.0
    ):
        raise ValueError("Image encoding timeout must be finite and positive")

    stages: list[str] = []
    requested_mode: EmocioCognitionMode = (
        cognition_mode
        if cognition_mode is not None
        else ("render_observe" if renderer is not None else "structured_only")
    )
    packet = packet or build_emocio_packet(scene)
    packet.validate_against(scene)
    stages.append("packet")
    compiled = compile_emocio_scenes(scene, packet, world)
    stages.append("scene_graph")
    visual_state = build_emocio_visual_state(
        scene=scene,
        packet=packet,
        world=world,
        compiled=compiled,
    )
    stages.append("valuation")
    policy = choose_native_option(visual_state.option_valuations)
    structured_native_conclusion: EmocioNativeConclusion
    native_conclusion: EmocioNativeConclusion
    if requested_mode != "visual_cognition":
        structured_native_conclusion = _native_conclusion(
            packet=packet,
            visual_state=visual_state,
            policy=policy,
        )
        native_conclusion = structured_native_conclusion
        stages.append("native_conclusion")

    images: tuple[ImageArtifact, ...] = ()
    render_batch: ImageRenderBatchOutcome | None = None
    warning: str | None = None
    active_config: VisualValuationPolicyConfig | None = None
    observations: tuple[BoundVisualEmbedding, ...] = ()
    visual_valuation: VisualValuationResult | None = None
    visual_memories: tuple[VisualWorldMemoryRecord, ...] = ()
    active_approval: VisualNativeInfluenceApproval | None = None
    active_authority: PinnedVisualInfluenceAuthority | None = None
    visual_failure: VisualCognitionFailure | None = None
    visual_warning: str | None = None
    visual_native_policy: EmocioPolicyDecision | None = None
    effective_mode: EmocioCognitionMode = "structured_only"
    fallback_reason: EmocioCognitionFallbackReason | None = None
    should_render = requested_mode != "structured_only"
    if should_render and renderer is None:
        fallback_reason = "renderer_not_configured"
    elif should_render and renderer is not None:
        try:
            rendered = renderer.render(compiled.all_scenes, seed=render_seed)
            if isinstance(rendered, ImageRenderBatchOutcome):
                render_batch = rendered
                validate_render_batch(
                    render_batch,
                    compiled.all_scenes,
                    expected_seed=render_seed,
                )
                images = render_batch.artifacts
                if render_batch.warnings:
                    timing = (
                        "after native conclusion"
                        if requested_mode != "visual_cognition"
                        else "before visual valuation"
                    )
                    warning = (
                        f"Renderer completed {timing} with warnings: "
                        + " | ".join(render_batch.warnings)
                    )
            else:
                images = tuple(rendered)
                validate_renderer_outputs(
                    images,
                    compiled.all_scenes,
                    expected_seed=render_seed,
                )
        except Exception as exc:  # fail closed to the structured native state
            images = ()
            render_batch = None
            timing = (
                "ignored after native conclusion"
                if requested_mode != "visual_cognition"
                else "failed before visual valuation"
            )
            if requested_mode == "visual_cognition":
                visual_failure = VisualCognitionFailure.create(
                    stage="render",
                    error=exc,
                )
                _, visual_warning = visual_failure_summary("render", exc)
                warning = visual_warning
            else:
                warning = f"Renderer {timing}: {type(exc).__name__}: {exc}"
        stages.append("render")

        if render_batch is not None:
            if render_batch.status == "succeeded" and images:
                effective_mode = "render_observe"
            elif render_batch.status == "disabled":
                fallback_reason = "renderer_disabled"
            elif render_batch.status == "partial":
                fallback_reason = "renderer_partial"
            else:
                fallback_reason = "renderer_failed"
        elif images:
            effective_mode = "render_observe"
        elif warning is None:
            fallback_reason = "renderer_returned_no_artifacts"
        else:
            fallback_reason = "renderer_failed"

    if requested_mode == "visual_cognition" and effective_mode == "render_observe":
        if render_batch is None:
            fallback_reason = "visual_render_provenance_unavailable"
        elif image_encoder is None or visual_policy_config is None:
            fallback_reason = "visual_valuation_unavailable"
        else:
            try:
                active_config = VisualValuationPolicyConfig.model_validate(
                    visual_policy_config.model_dump(
                        mode="python",
                        round_trip=True,
                    )
                )
            except Exception as exc:
                fallback_reason = "visual_valuation_failed"
                assert render_batch is not None
                visual_failure = VisualCognitionFailure.create(
                    stage="policy_config",
                    error=exc,
                    render_batch=render_batch,
                )
                _, visual_warning = visual_failure_summary("policy_config", exc)

        if fallback_reason is None:
            stages.append("visual_encoding")
            try:
                assert render_batch is not None
                assert image_encoder is not None
                observations = build_visual_observations(
                    visual_state=visual_state,
                    render_batch=render_batch,
                    encoder=image_encoder,
                    encoding_timeout_seconds=float(encoding_timeout_seconds),
                )
            except VisualObservationBuildError as exc:
                observations = exc.partial_observations
                fallback_reason = "visual_encoding_failed"
                assert render_batch is not None
                visual_failure = VisualCognitionFailure.create(
                    stage="encoding",
                    error=exc,
                    render_batch=render_batch,
                    observations=observations,
                    attempted_call_spec=exc.attempted_call_spec,
                )
                _, visual_warning = visual_failure_summary("encoding", exc)
            except Exception as exc:
                observations = ()
                fallback_reason = "visual_encoding_failed"
                assert render_batch is not None
                visual_failure = VisualCognitionFailure.create(
                    stage="encoding",
                    error=exc,
                    render_batch=render_batch,
                )
                _, visual_warning = visual_failure_summary("encoding", exc)

        if fallback_reason is None:
            stages.append("visual_valuation")
            try:
                assert active_config is not None
                visual_valuation = evaluate_visual_valuation(
                    policy=active_config.policy,
                    visual_state=visual_state,
                    observations=observations,
                    include_cross_seed_consistency=False,
                )
            except Exception as exc:
                visual_valuation = None
                fallback_reason = "visual_valuation_failed"
                assert render_batch is not None
                visual_failure = VisualCognitionFailure.create(
                    stage="valuation",
                    error=exc,
                    render_batch=render_batch,
                    observations=observations,
                )
                _, visual_warning = visual_failure_summary("valuation", exc)

        if fallback_reason is None:
            stages.append("visual_memory")
            try:
                assert visual_valuation is not None
                visual_memories = tuple(
                    build_visual_world_memory_record(
                        observation=observation,
                        valuation=visual_valuation,
                        visual_state=visual_state,
                        observations=observations,
                    )
                    for observation in observations
                    if observation.role == "option_rollout"
                )
            except Exception as exc:
                visual_memories = ()
                fallback_reason = "visual_memory_failed"
                assert render_batch is not None
                visual_failure = VisualCognitionFailure.create(
                    stage="memory",
                    error=exc,
                    render_batch=render_batch,
                    observations=observations,
                    valuation=visual_valuation,
                )
                _, visual_warning = visual_failure_summary("memory", exc)

        if fallback_reason is None:
            assert visual_valuation is not None
            if visual_valuation.integration_disposition == "review_action_collapse":
                fallback_reason = "visual_action_collapse"
            elif visual_valuation.integration_disposition == "review_tie":
                fallback_reason = "visual_valuation_tie"
            elif (
                visual_influence_approval is None
                or visual_influence_authority is None
            ):
                fallback_reason = "visual_approval_unavailable"
            else:
                stages.append("visual_approval")
                try:
                    active_approval = VisualNativeInfluenceApproval.model_validate(
                        visual_influence_approval.model_dump(
                            mode="python",
                            round_trip=True,
                        )
                    )
                    active_authority = PinnedVisualInfluenceAuthority.model_validate(
                        visual_influence_authority.model_dump(
                            mode="python",
                            round_trip=True,
                        )
                    )
                    active_authority = require_repository_pinned_visual_authority(
                        active_authority
                    )
                    active_approval = active_authority.admit(active_approval)
                    assert active_config is not None
                    active_approval.validate_against(
                        policy_config=active_config,
                        valuation=visual_valuation,
                        visual_state=visual_state,
                        observations=observations,
                        option_order=tuple(
                            option.option_id for option in scene.options
                        ),
                    )
                except Exception as exc:
                    fallback_reason = "visual_approval_mismatch"
                    assert render_batch is not None
                    visual_failure = VisualCognitionFailure.create(
                        stage="approval",
                        error=exc,
                        render_batch=render_batch,
                        observations=observations,
                        valuation=visual_valuation,
                        approval=active_approval,
                        authority=active_authority,
                    )
                    _, visual_warning = visual_failure_summary("approval", exc)

        if fallback_reason is None:
            assert visual_valuation is not None
            assert active_approval is not None
            assert active_authority is not None
            visual_native_policy = policy_from_visual_valuation(
                visual_state=visual_state,
                valuation=visual_valuation,
            )
            effective_mode = "visual_cognition"

    if requested_mode == "visual_cognition":
        structured_native_conclusion = _native_conclusion(
            packet=packet,
            visual_state=visual_state,
            policy=policy,
        )
        if visual_native_policy is None:
            native_conclusion = structured_native_conclusion
        else:
            assert visual_valuation is not None
            assert active_approval is not None
            assert active_authority is not None
            native_conclusion = _native_conclusion(
                packet=packet,
                visual_state=visual_state,
                policy=visual_native_policy,
                visual_valuation=visual_valuation,
                visual_approval=active_approval,
                visual_authority=active_authority,
            )
        stages.append("native_conclusion")

    cognition_trace = EmocioCognitionTrace.create(
        requested_mode=requested_mode,
        effective_mode=effective_mode,
        fallback_reason=fallback_reason,
        conclusion_source=(
            "approved_visual_valuation"
            if effective_mode == "visual_cognition"
            else "structured_valuation"
        ),
        source_visual_valuation_result_id=(
            visual_valuation.result_id
            if effective_mode == "visual_cognition"
            and visual_valuation is not None
            else None
        ),
        source_visual_valuation_result_hash=(
            visual_valuation.content_hash()
            if effective_mode == "visual_cognition"
            and visual_valuation is not None
            else None
        ),
        source_visual_influence_approval_id=(
            active_approval.approval_id
            if effective_mode == "visual_cognition"
            and active_approval is not None
            else None
        ),
        source_visual_influence_approval_hash=(
            active_approval.content_hash()
            if effective_mode == "visual_cognition"
            and active_approval is not None
            else None
        ),
        source_visual_influence_authority_id=(
            active_authority.authority_id
            if effective_mode == "visual_cognition"
            and active_authority is not None
            else None
        ),
        source_visual_influence_authority_hash=(
            active_authority.content_hash()
            if effective_mode == "visual_cognition"
            and active_authority is not None
            else None
        ),
    )
    result = EmocioProcessingResult(
        source_scene_hash=scene.scene_hash(),
        source_world_id=world.world_id,
        source_world_hash=world.content_hash(),
        packet=packet,
        visual_state=visual_state,
        structured_native_conclusion=structured_native_conclusion,
        native_conclusion=native_conclusion,
        policy=policy,
        cognition_trace=cognition_trace,
        rendered_images=images,
        render_batch=render_batch,
        render_seed=(
            render_seed
            if should_render and renderer is not None
            else None
        ),
        renderer_warning=warning,
        visual_policy_config=active_config,
        visual_observations=observations,
        visual_valuation=visual_valuation,
        visual_memories=visual_memories,
        visual_influence_approval=active_approval,
        visual_influence_authority=active_authority,
        visual_failure=visual_failure,
        visual_warning=visual_warning,
        stage_order=tuple(stages),
    )
    result.validate_against(scene, world)
    return result


@dataclass(frozen=True, slots=True)
class DeterministicEmocioProcessor:
    """Injectable processor configuration used by the REI engine boundary."""

    renderer: EmocioRenderer | None = None
    render_seed: int = 0
    cognition_mode: EmocioCognitionMode | None = None
    image_encoder: VerifiedImageEncoder | None = None
    visual_policy_config: VisualValuationPolicyConfig | None = None
    visual_influence_approval: VisualNativeInfluenceApproval | None = None
    visual_influence_authority: PinnedVisualInfluenceAuthority | None = None
    encoding_timeout_seconds: float = 30.0

    def process(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
        *,
        packet: EmocioInputPacket | None = None,
    ) -> EmocioProcessingResult:
        return process_emocio(
            scene,
            world,
            renderer=self.renderer,
            render_seed=self.render_seed,
            packet=packet,
            cognition_mode=self.cognition_mode,
            image_encoder=self.image_encoder,
            visual_policy_config=self.visual_policy_config,
            visual_influence_approval=self.visual_influence_approval,
            visual_influence_authority=self.visual_influence_authority,
            encoding_timeout_seconds=self.encoding_timeout_seconds,
        )


__all__ = [
    "DeterministicEmocioProcessor",
    "EmocioProcessingResult",
    "process_emocio",
]
