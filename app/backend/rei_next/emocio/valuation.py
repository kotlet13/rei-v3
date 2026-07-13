"""Transparent deterministic valuation of structured visual rollouts."""

from __future__ import annotations

from ..ids import content_id
from ..models.emocio import (
    EmocioInputPacket,
    EmocioOptionValuation,
    EmocioVisualState,
    EmocioWorld,
    ValuationDimension,
    VisualSceneSpec,
)
from ..models.scene import SceneEvent
from .scene_graph import CompiledEmocioScenes


def _exact_overlap(candidate: tuple[str, ...], reference: tuple[str, ...]) -> float:
    """Exact structured-atom overlap; absent references produce neutral 0.5."""

    reference_set = set(reference)
    if not reference_set:
        return 0.5
    return round(len(set(candidate) & reference_set) / len(reference_set), 6)


def _distance(candidate: tuple[str, ...], reference: tuple[str, ...]) -> float:
    if not reference:
        return 0.5
    return round(1.0 - _exact_overlap(candidate, reference), 6)


def _jaccard_distance(candidate: tuple[str, ...], reference: tuple[str, ...]) -> float:
    candidate_set = set(candidate)
    reference_set = set(reference)
    union = candidate_set | reference_set
    if not union:
        return 0.5
    return round(1.0 - (len(candidate_set & reference_set) / len(union)), 6)


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        return 0.5
    return round(sum(values) / len(values), 6)


def value_option_rollout(
    rollout: VisualSceneSpec,
    *,
    current_scene: VisualSceneSpec,
    desired_scene: VisualSceneSpec,
    broken_scene: VisualSceneSpec,
) -> EmocioOptionValuation:
    """Value one rollout with equal-weight, inspectable structural formulas."""

    if rollout.scene_kind != "option_rollout" or rollout.option_id is None:
        raise ValueError("Only an option rollout can be valued")
    desired_match = _exact_overlap(rollout.composition, desired_scene.composition)
    broken_distance = _distance(rollout.composition, broken_scene.composition)
    self_visibility = (
        1.0
        if rollout.self_position != "unspecified"
        and rollout.self_position in rollout.entities
        else 0.5
    )
    belonging = (
        0.5
        if desired_scene.group_belonging == "unspecified"
        else 1.0
        if rollout.group_belonging == desired_scene.group_belonging
        else 0.0
    )
    attention = _mean(tuple(item.score for item in rollout.attention_structure))
    attraction = _exact_overlap(
        rollout.composition,
        desired_scene.attraction_markers,
    )
    novelty = _jaccard_distance(rollout.composition, current_scene.composition)
    movement = _exact_overlap(rollout.movement, desired_scene.movement)
    status = _exact_overlap(rollout.status_relations, desired_scene.status_relations)
    competitive_success = _distance(
        rollout.composition,
        broken_scene.obstacle_markers,
    )
    breakthrough = _mean((broken_distance, novelty, movement))
    dimensions = (
        ValuationDimension(name="desired_scene_match", score=desired_match),
        ValuationDimension(
            name="distance_from_broken_scene", score=broken_distance
        ),
        ValuationDimension(name="self_visibility", score=self_visibility),
        ValuationDimension(name="belonging", score=belonging),
        ValuationDimension(name="attention", score=attention),
        ValuationDimension(name="attraction", score=attraction),
        ValuationDimension(name="novelty", score=novelty),
        ValuationDimension(name="movement", score=movement),
        ValuationDimension(name="status", score=status),
        ValuationDimension(
            name="competitive_success", score=competitive_success
        ),
        ValuationDimension(
            name="attack_or_breakthrough_affordance", score=breakthrough
        ),
    )
    return EmocioOptionValuation(
        option_id=rollout.option_id,
        rollout_scene_id=rollout.scene_id,
        dimensions=dimensions,
    )


def aggregate_option_valuation(valuation: EmocioOptionValuation) -> float:
    """Equal-weight aggregate; no hidden coefficients or profile influence."""

    return _mean(tuple(item.score for item in valuation.dimensions))


def build_emocio_visual_state(
    *,
    scene: SceneEvent,
    packet: EmocioInputPacket,
    world: EmocioWorld,
    compiled: CompiledEmocioScenes,
) -> EmocioVisualState:
    valuations = tuple(
        value_option_rollout(
            rollout,
            current_scene=compiled.current_scene,
            desired_scene=compiled.desired_scene,
            broken_scene=compiled.broken_scene,
        )
        for rollout in compiled.option_rollouts
    )
    payload = {
        "schema_version": "rei-native-emocio-visual-state-v1",
        "source_scene_id": scene.event_id,
        "source_packet_id": packet.packet_id,
        "current_scene": compiled.current_scene,
        "desired_scene": compiled.desired_scene,
        "broken_scene": compiled.broken_scene,
        "option_rollouts": compiled.option_rollouts,
        "option_valuations": valuations,
    }
    visual_state = EmocioVisualState(
        visual_state_id=content_id(
            "emocio_state",
            {
                "source_scene_hash": scene.scene_hash(),
                "source_packet_hash": packet.content_hash(),
                "source_world_id": world.world_id,
                "source_world_hash": world.content_hash(),
                **payload,
            },
        ),
        **payload,
    )
    visual_state.validate_against(packet, scene)
    return visual_state


__all__ = [
    "aggregate_option_valuation",
    "build_emocio_visual_state",
    "value_option_rollout",
]
