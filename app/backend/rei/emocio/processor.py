"""End-to-end deterministic Emocio structured native processor."""

from __future__ import annotations

from dataclasses import dataclass

from ..ids import content_id
from ..models.emocio import (
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioVisualState,
    EmocioWorld,
    ImageArtifact,
)
from ..models.scene import SceneEvent
from ..models.rendering import ImageRenderBatchOutcome
from .packets import build_emocio_packet
from .policy import EmocioPolicyDecision, choose_native_option
from .renderer import (
    EmocioRenderer,
    validate_render_batch,
    validate_renderer_outputs,
)
from .scene_graph import compile_emocio_scenes
from .valuation import build_emocio_visual_state


@dataclass(frozen=True, slots=True)
class EmocioProcessingResult:
    source_scene_hash: str
    source_world_id: str
    source_world_hash: str
    packet: EmocioInputPacket
    visual_state: EmocioVisualState
    native_conclusion: EmocioNativeConclusion
    policy: EmocioPolicyDecision
    rendered_images: tuple[ImageArtifact, ...]
    render_batch: ImageRenderBatchOutcome | None
    render_seed: int | None
    renderer_warning: str | None
    stage_order: tuple[str, ...]

    def validate_against(self, scene: SceneEvent, world: EmocioWorld) -> None:
        if self.source_scene_hash != scene.scene_hash():
            raise ValueError("Emocio result source scene hash differs")
        if (
            self.source_world_id != world.world_id
            or self.source_world_hash != world.content_hash()
        ):
            raise ValueError("Emocio result source world lineage differs")
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
            raise ValueError("Emocio policy differs from deterministic replay")
        expected_conclusion = _native_conclusion(
            packet=self.packet,
            visual_state=self.visual_state,
            policy=self.policy,
        )
        if self.native_conclusion != expected_conclusion:
            raise ValueError("Emocio native conclusion differs from deterministic replay")
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


def _native_conclusion(
    *,
    packet: EmocioInputPacket,
    visual_state: EmocioVisualState,
    policy: EmocioPolicyDecision,
) -> EmocioNativeConclusion:
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
        uncertainty = "Enoli\u010dno najvi\u0161je transparentno strukturno vrednotenje."
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
) -> EmocioProcessingResult:
    """Build the native result first, then optionally render frozen scenes."""

    stages: list[str] = []
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
    native_conclusion = _native_conclusion(
        packet=packet,
        visual_state=visual_state,
        policy=policy,
    )
    stages.append("native_conclusion")

    images: tuple[ImageArtifact, ...] = ()
    render_batch: ImageRenderBatchOutcome | None = None
    warning: str | None = None
    if renderer is not None:
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
                    warning = (
                        "Renderer completed after native conclusion with warnings: "
                        + " | ".join(render_batch.warnings)
                    )
            else:
                images = tuple(rendered)
                validate_renderer_outputs(
                    images,
                    compiled.all_scenes,
                    expected_seed=render_seed,
                )
        except Exception as exc:  # optional presentation must not destroy native state
            images = ()
            render_batch = None
            warning = f"Renderer ignored after native conclusion: {type(exc).__name__}: {exc}"
        stages.append("render")
    result = EmocioProcessingResult(
        source_scene_hash=scene.scene_hash(),
        source_world_id=world.world_id,
        source_world_hash=world.content_hash(),
        packet=packet,
        visual_state=visual_state,
        native_conclusion=native_conclusion,
        policy=policy,
        rendered_images=images,
        render_batch=render_batch,
        render_seed=render_seed if renderer is not None else None,
        renderer_warning=warning,
        stage_order=tuple(stages),
    )
    result.validate_against(scene, world)
    return result


@dataclass(frozen=True, slots=True)
class DeterministicEmocioProcessor:
    """Small injectable facade used by the later REI engine."""

    renderer: EmocioRenderer | None = None
    render_seed: int = 0

    def process(
        self,
        scene: SceneEvent,
        world: EmocioWorld,
    ) -> EmocioProcessingResult:
        return process_emocio(
            scene,
            world,
            renderer=self.renderer,
            render_seed=self.render_seed,
        )


__all__ = [
    "DeterministicEmocioProcessor",
    "EmocioProcessingResult",
    "process_emocio",
]
