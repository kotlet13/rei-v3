"""Identity-preserving deterministic Emocio scene compilation."""

from __future__ import annotations

from dataclasses import dataclass

from ..ids import content_id
from ..models.emocio import (
    EmocioInputPacket,
    EmocioSceneKind,
    EmocioWorld,
    VisualSceneSpec,
)
from ..models.scene import DecisionOption, SceneEvent


def _canonical(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(value for value in values if value)))


def _option_atoms(option: DecisionOption) -> tuple[str, ...]:
    return _canonical([option.label, option.description])


def _visual_lineage_hashes(
    scene: SceneEvent,
    packet: EmocioInputPacket,
) -> tuple[str, str]:
    """Canonicalize only option order for visual identity derivation.

    ``SceneEvent.scene_hash()`` remains the exact structured-input hash and the
    packet remains bound to it. Visual scene identity, however, represents
    scene semantics rather than presentation order, so two otherwise identical
    events with permuted options must compile to the same visual scene IDs.
    The already-canonical path returns the historical hashes byte-for-byte.
    """

    canonical_options = tuple(sorted(scene.options, key=lambda item: item.option_id))
    if scene.options == canonical_options:
        return scene.scene_hash(), packet.content_hash()

    canonical_scene = scene.model_copy(update={"options": canonical_options})
    canonical_scene_hash = canonical_scene.scene_hash()
    packet_payload = packet.model_dump(
        mode="python",
        round_trip=True,
        exclude={"packet_id"},
    )
    if packet.source_scene_hash is not None:
        packet_payload["source_scene_hash"] = canonical_scene_hash
    canonical_packet_id = content_id("emocio_packet", packet_payload)
    canonical_packet = packet.model_copy(
        update={
            "packet_id": canonical_packet_id,
            "source_scene_hash": (
                canonical_scene_hash
                if packet.source_scene_hash is not None
                else None
            ),
        }
    )
    return canonical_scene_hash, canonical_packet.content_hash()


def _build_scene(
    *,
    scene: SceneEvent,
    packet: EmocioInputPacket,
    world: EmocioWorld,
    scene_kind: EmocioSceneKind,
    option: DecisionOption | None,
    composition: tuple[str, ...],
    group_belonging: str,
    status_relations: tuple[str, ...],
    movement: tuple[str, ...],
    attraction_markers: tuple[str, ...],
    obstacle_markers: tuple[str, ...],
    inferred_elements: tuple[str, ...],
) -> VisualSceneSpec:
    source_scene_hash, source_packet_hash = _visual_lineage_hashes(scene, packet)
    payload = {
        "schema_version": "rei-native-visual-scene-spec-v1",
        "scene_kind": scene_kind,
        "option_id": option.option_id if option is not None else None,
        "entities": _canonical(list(packet.explicit_identity_cues)),
        "self_position": "unspecified",
        "attention_structure": (),
        "group_belonging": group_belonging,
        "status_relations": _canonical(list(status_relations)),
        "movement": _canonical(list(movement)),
        "composition": _canonical(list(composition)),
        "attraction_markers": _canonical(list(attraction_markers)),
        "obstacle_markers": _canonical(list(obstacle_markers)),
        "grounded_evidence_ids": tuple(sorted(packet.evidence_ids)),
        "inferred_elements": _canonical(list(inferred_elements)),
    }
    visual_scene = VisualSceneSpec(
        scene_id=content_id(
            "visual_scene",
            {
                "source_scene_hash": source_scene_hash,
                "source_packet_hash": source_packet_hash,
                "source_world_hash": world.content_hash(),
                **payload,
            },
        ),
        **payload,
    )
    visual_scene.validate_against(scene)
    return visual_scene


@dataclass(frozen=True, slots=True)
class CompiledEmocioScenes:
    """Structured scenes before valuation; no renderer output is present."""

    current_scene: VisualSceneSpec
    desired_scene: VisualSceneSpec
    broken_scene: VisualSceneSpec
    option_rollouts: tuple[VisualSceneSpec, ...]

    @property
    def all_scenes(self) -> tuple[VisualSceneSpec, ...]:
        return (
            self.current_scene,
            self.desired_scene,
            self.broken_scene,
            *self.option_rollouts,
        )


def compile_emocio_scenes(
    scene: SceneEvent,
    packet: EmocioInputPacket,
    world: EmocioWorld,
) -> CompiledEmocioScenes:
    """Compile current, desired, broken and per-option counterfactual scenes.

    Exact structured atoms are preserved.  There is no tokenization, sentiment
    lookup, synonym table, or keyword-based option inference.  Every scene
    retains the same actor identities and grounded evidence scope.
    """

    packet.validate_against(scene)
    current_inferred = _canonical(list(world.visual_memories))
    current_composition = _canonical(
        [*packet.grounded_visual_cues, *current_inferred]
    )
    desired_elements = _canonical(list(world.desired_scenes))
    broken_elements = _canonical(list(world.broken_scenes))
    current = _build_scene(
        scene=scene,
        packet=packet,
        world=world,
        scene_kind="current",
        option=None,
        composition=current_composition,
        group_belonging="unspecified",
        status_relations=packet.social_layout,
        movement=packet.movement_cues,
        attraction_markers=packet.aesthetic_cues,
        obstacle_markers=(),
        inferred_elements=current_inferred,
    )
    desired = _build_scene(
        scene=scene,
        packet=packet,
        world=world,
        scene_kind="desired",
        option=None,
        composition=desired_elements,
        group_belonging=(
            sorted(world.social_identity_motifs)[0]
            if world.social_identity_motifs
            else "unspecified"
        ),
        status_relations=world.social_identity_motifs,
        movement=world.motor_patterns,
        attraction_markers=world.attraction_patterns,
        obstacle_markers=(),
        inferred_elements=desired_elements,
    )
    broken = _build_scene(
        scene=scene,
        packet=packet,
        world=world,
        scene_kind="broken",
        option=None,
        composition=broken_elements,
        group_belonging="unspecified",
        status_relations=(),
        movement=(),
        attraction_markers=(),
        obstacle_markers=broken_elements,
        inferred_elements=broken_elements,
    )
    option_by_id = {option.option_id: option for option in scene.options}
    rollouts = tuple(
        _build_scene(
            scene=scene,
            packet=packet,
            world=world,
            scene_kind="option_rollout",
            option=option_by_id[option_id],
            composition=_canonical(
                [*current.composition, *_option_atoms(option_by_id[option_id])]
            ),
            group_belonging=desired.group_belonging,
            status_relations=desired.status_relations,
            movement=_canonical([*current.movement, *desired.movement]),
            attraction_markers=desired.attraction_markers,
            obstacle_markers=(),
            inferred_elements=_option_atoms(option_by_id[option_id]),
        )
        for option_id in sorted(packet.allowed_option_ids)
    )
    compiled = CompiledEmocioScenes(
        current_scene=current,
        desired_scene=desired,
        broken_scene=broken,
        option_rollouts=rollouts,
    )
    for visual_scene in compiled.all_scenes:
        visual_scene.validate_against(scene)
        if set(visual_scene.grounded_evidence_ids) - set(packet.evidence_ids):
            raise ValueError("Compiled scene escaped the Emocio packet evidence scope")
    return compiled


__all__ = ["CompiledEmocioScenes", "compile_emocio_scenes"]
