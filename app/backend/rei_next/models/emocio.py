"""Strict contracts for Emocio's structured visual-scenic processing route.

Rendering is represented only by provenance-rich artifacts.  It is optional
presentation infrastructure and generated details never become scene evidence.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from ..ids import content_id
from .common import (
    ArtifactRelativePath,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    Score01,
)
from .scene import SceneEvent


EmocioSceneKind = Literal["current", "desired", "broken", "option_rollout"]
ImageMediaType = Annotated[
    str,
    StringConstraints(pattern=r"^image/[a-z0-9][a-z0-9.+-]*$"),
]
EmocioActionTendency = Literal[
    "approach",
    "perform",
    "compete",
    "connect",
    "attack",
    "improvise",
    "withdraw_contact",
    "unknown",
]
EmocioValuationDimensionName = Literal[
    "desired_scene_match",
    "distance_from_broken_scene",
    "self_visibility",
    "belonging",
    "attention",
    "attraction",
    "novelty",
    "movement",
    "status",
    "competitive_success",
    "attack_or_breakthrough_affordance",
]
EMOCIO_VALUATION_DIMENSIONS: tuple[EmocioValuationDimensionName, ...] = (
    "desired_scene_match",
    "distance_from_broken_scene",
    "self_visibility",
    "belonging",
    "attention",
    "attraction",
    "novelty",
    "movement",
    "status",
    "competitive_success",
    "attack_or_breakthrough_affordance",
)


class AttentionWeight(FrozenModel):
    """One ordered entry in a deterministic attention map."""

    target: NonEmptyId
    score: Score01


class ValuationDimension(FrozenModel):
    """One ordered visual-valuation dimension and normalized score."""

    name: EmocioValuationDimensionName
    score: Score01


class EmocioOptionValuation(FrozenModel):
    """Transparent canonical valuation for one option-rollout scene."""

    option_id: NonEmptyId
    rollout_scene_id: NonEmptyId
    dimensions: tuple[ValuationDimension, ...]

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        names = tuple(item.name for item in self.dimensions)
        if names != EMOCIO_VALUATION_DIMENSIONS:
            raise ValueError(
                "Emocio option valuation must record all canonical dimensions in order"
            )
        return self


class EmocioWorld(FrozenArtifactModel):
    """Immutable snapshot of Emocio's visual and motor world projection."""

    schema_version: Literal["rei-native-emocio-world-v1"] = (
        "rei-native-emocio-world-v1"
    )
    world_id: NonEmptyId
    visual_memories: tuple[str, ...]
    desired_scenes: tuple[str, ...]
    broken_scenes: tuple[str, ...]
    social_identity_motifs: tuple[str, ...]
    attraction_patterns: tuple[str, ...]
    motor_patterns: tuple[str, ...]


class EmocioInputPacket(FrozenArtifactModel):
    """Profile-blind grounded cues routed to Emocio without prewritten intent."""

    schema_version: Literal["rei-native-emocio-input-packet-v1"] = (
        "rei-native-emocio-input-packet-v1"
    )
    packet_id: NonEmptyId
    scene_id: NonEmptyId
    source_scene_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    grounded_visual_cues: tuple[str, ...]
    social_layout: tuple[str, ...]
    actor_positions: tuple[str, ...]
    observed_attention: tuple[str, ...]
    movement_cues: tuple[str, ...]
    aesthetic_cues: tuple[str, ...]
    explicit_identity_cues: tuple[str, ...]
    allowed_option_ids: tuple[NonEmptyId, ...]
    evidence_ids: tuple[NonEmptyId, ...]
    previous_emocio_projection_ids: tuple[NonEmptyId, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    previous_emocio_projection_hashes: tuple[HashDigest, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    caveat: str

    @model_validator(mode="after")
    def validate_packet_references(self) -> "EmocioInputPacket":
        if len(set(self.allowed_option_ids)) != len(self.allowed_option_ids):
            raise ValueError("allowed_option_ids must be unique")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        if len(self.previous_emocio_projection_ids) != len(
            self.previous_emocio_projection_hashes
        ):
            raise ValueError("Emocio projection IDs and hashes must have equal length")
        if len(set(self.previous_emocio_projection_ids)) != len(
            self.previous_emocio_projection_ids
        ):
            raise ValueError("Emocio projection IDs must be unique")
        return self

    def validate_against(self, scene: SceneEvent) -> Self:
        """Bind profile-blind visual cues to the complete trusted event scope."""

        if self.scene_id != scene.event_id:
            raise ValueError("Emocio packet belongs to another SceneEvent")
        if (
            self.source_scene_hash is not None
            and self.source_scene_hash != scene.scene_hash()
        ):
            raise ValueError("Emocio packet source hash differs from the SceneEvent")
        scene_option_ids = {option.option_id for option in scene.options}
        if set(self.allowed_option_ids) != scene_option_ids:
            raise ValueError("Emocio packet must preserve every SceneEvent option")
        scene_evidence_ids = {item.evidence_id for item in scene.evidence}
        if not set(self.evidence_ids).issubset(scene_evidence_ids):
            raise ValueError("Emocio packet evidence must belong to the SceneEvent")
        if self.source_scene_hash is not None:
            grounded = tuple(item for item in scene.evidence if item.grounded)
            routed = tuple(
                item
                for item in grounded
                if item.modality in {"image", "video", "body"}
            )
            expected_visual = tuple(
                sorted(
                    {
                        item.content
                        for item in grounded
                        if item.modality in {"image", "video"}
                    }
                )
            )
            expected_movement = tuple(
                sorted(
                    {
                        item.content
                        for item in grounded
                        if item.modality in {"video", "body"}
                    }
                )
            )
            actors = tuple(sorted(set(scene.actors)))
            expected = {
                "grounded_visual_cues": expected_visual,
                "social_layout": actors,
                "actor_positions": (),
                "observed_attention": (),
                "movement_cues": expected_movement,
                "aesthetic_cues": expected_visual,
                "explicit_identity_cues": actors,
                "allowed_option_ids": tuple(
                    sorted(option.option_id for option in scene.options)
                ),
                "evidence_ids": tuple(
                    sorted(item.evidence_id for item in routed)
                ),
            }
            for field_name, expected_value in expected.items():
                if getattr(self, field_name) != expected_value:
                    raise ValueError(
                        f"Content-addressed Emocio packet {field_name} differs "
                        "from the deterministic router"
                    )
            expected_packet_id = content_id(
                "emocio_packet",
                self.model_dump(
                    mode="python",
                    round_trip=True,
                    exclude={"packet_id"},
                ),
            )
            if self.packet_id != expected_packet_id:
                raise ValueError("Emocio packet ID does not match its canonical content")
        return self


class VisualSceneSpec(FrozenArtifactModel):
    """A grounded/inferred structured scene, independent of image rendering."""

    schema_version: Literal["rei-native-visual-scene-spec-v1"] = (
        "rei-native-visual-scene-spec-v1"
    )
    scene_id: NonEmptyId
    scene_kind: EmocioSceneKind
    option_id: NonEmptyId | None
    entities: tuple[str, ...]
    self_position: str
    attention_structure: tuple[AttentionWeight, ...]
    group_belonging: str
    status_relations: tuple[str, ...]
    movement: tuple[str, ...]
    composition: tuple[str, ...]
    attraction_markers: tuple[str, ...]
    obstacle_markers: tuple[str, ...]
    grounded_evidence_ids: tuple[NonEmptyId, ...]
    inferred_elements: tuple[str, ...]

    @model_validator(mode="after")
    def validate_option_scope(self) -> "VisualSceneSpec":
        """Bind option IDs only to counterfactual option-rollout scenes."""

        if self.scene_kind == "option_rollout" and self.option_id is None:
            raise ValueError("option_rollout scenes require option_id")
        if self.scene_kind != "option_rollout" and self.option_id is not None:
            raise ValueError("only option_rollout scenes may carry option_id")
        attention_targets = tuple(item.target for item in self.attention_structure)
        if len(set(attention_targets)) != len(attention_targets):
            raise ValueError("attention_structure targets must be unique")
        if len(set(self.grounded_evidence_ids)) != len(self.grounded_evidence_ids):
            raise ValueError("grounded_evidence_ids must be unique")
        if tuple(sorted(attention_targets)) != attention_targets:
            raise ValueError("attention_structure must use canonical target order")
        return self

    def validate_against(self, scene: SceneEvent) -> Self:
        """Verify grounded references and optional rollout scope against an event."""

        if self.option_id is not None and self.option_id not in {
            option.option_id for option in scene.options
        }:
            raise ValueError("Visual rollout option must belong to the SceneEvent")
        evidence_by_id = {item.evidence_id: item for item in scene.evidence}
        for evidence_id in self.grounded_evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None or not evidence.grounded:
                raise ValueError(
                    "Visual grounded evidence must reference grounded SceneEvent evidence"
                )
        return self


class EmocioVisualState(FrozenArtifactModel):
    """Emocio's immutable current/desired/broken and option-rollout state."""

    schema_version: Literal["rei-native-emocio-visual-state-v1"] = (
        "rei-native-emocio-visual-state-v1"
    )
    visual_state_id: NonEmptyId
    source_scene_id: NonEmptyId
    source_packet_id: NonEmptyId
    current_scene: VisualSceneSpec
    desired_scene: VisualSceneSpec
    broken_scene: VisualSceneSpec
    option_rollouts: tuple[VisualSceneSpec, ...]
    option_valuations: tuple[EmocioOptionValuation, ...]

    @model_validator(mode="after")
    def validate_scene_roles(self) -> "EmocioVisualState":
        """Keep each scene in its declared role and each option rollout unique."""

        expected = (
            ("current_scene", self.current_scene, "current"),
            ("desired_scene", self.desired_scene, "desired"),
            ("broken_scene", self.broken_scene, "broken"),
        )
        for field_name, scene, scene_kind in expected:
            if scene.scene_kind != scene_kind:
                raise ValueError(f"{field_name} must have scene_kind={scene_kind!r}")

        option_ids = tuple(scene.option_id for scene in self.option_rollouts)
        if any(scene.scene_kind != "option_rollout" for scene in self.option_rollouts):
            raise ValueError("option_rollouts may contain only option_rollout scenes")
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("option_rollouts must have unique option_id values")
        canonical_option_ids = tuple(
            sorted(option_id for option_id in option_ids if option_id is not None)
        )
        if option_ids != canonical_option_ids:
            raise ValueError("option_rollouts must use canonical option_id order")
        all_scene_ids = (
            self.current_scene.scene_id,
            self.desired_scene.scene_id,
            self.broken_scene.scene_id,
            *(scene.scene_id for scene in self.option_rollouts),
        )
        if len(set(all_scene_ids)) != len(all_scene_ids):
            raise ValueError("EmocioVisualState scene IDs must be unique")
        valuation_option_ids = tuple(
            valuation.option_id for valuation in self.option_valuations
        )
        if valuation_option_ids != option_ids:
            raise ValueError(
                "option_valuations must follow and cover every option rollout"
            )
        rollout_scene_ids = tuple(scene.scene_id for scene in self.option_rollouts)
        valuation_scene_ids = tuple(
            valuation.rollout_scene_id for valuation in self.option_valuations
        )
        if valuation_scene_ids != rollout_scene_ids:
            raise ValueError("Each option valuation must reference its rollout scene")
        return self

    def validate_against(
        self,
        packet: EmocioInputPacket,
        scene: SceneEvent,
    ) -> Self:
        """Prove complete option coverage and grounded scene lineage."""

        packet.validate_against(scene)
        if self.source_scene_id != scene.event_id:
            raise ValueError("Emocio visual state belongs to another SceneEvent")
        if self.source_packet_id != packet.packet_id:
            raise ValueError("Emocio visual state belongs to another input packet")
        for visual_scene in (
            self.current_scene,
            self.desired_scene,
            self.broken_scene,
            *self.option_rollouts,
        ):
            visual_scene.validate_against(scene)
            if not set(visual_scene.grounded_evidence_ids).issubset(
                packet.evidence_ids
            ):
                raise ValueError(
                    "Visual scene evidence must stay within the Emocio packet scope"
                )
        rollout_option_ids = {rollout.option_id for rollout in self.option_rollouts}
        if rollout_option_ids != set(packet.allowed_option_ids):
            raise ValueError("Emocio visual state must include every allowed option rollout")
        return self


class ImageArtifact(FrozenArtifactModel):
    """Renderer output metadata; never a source of new grounded facts."""

    schema_version: Literal["rei-native-image-artifact-v1"] = (
        "rei-native-image-artifact-v1"
    )
    image_id: NonEmptyId
    request_id: NonEmptyId
    render_call_id: NonEmptyId
    source_spec_id: NonEmptyId
    provider_id: NonEmptyId
    model: NonEmptyId | None = None
    model_revision: NonEmptyId | None = None
    seed: int
    input_spec_hash: HashDigest
    content_sha256: HashDigest
    media_type: ImageMediaType
    grounded: Literal[False] = False
    prompt: str
    negative_prompt: str
    path: ArtifactRelativePath
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    generated_only_elements: tuple[str, ...]
    grounded_mask_path: ArtifactRelativePath | None = None

    @model_validator(mode="after")
    def validate_model_provenance_pair(self) -> "ImageArtifact":
        if (self.model is None) != (self.model_revision is None):
            raise ValueError("Image model and model_revision must be recorded together")
        return self


class EmocioNativeConclusion(FrozenArtifactModel):
    """Emocio's immutable native result, preceding any manifestation."""

    schema_version: Literal["rei-native-emocio-conclusion-v1"] = (
        "rei-native-emocio-conclusion-v1"
    )
    conclusion_id: NonEmptyId
    source_packet_id: NonEmptyId
    source_scene_id: NonEmptyId
    mind: Literal["E"] = "E"
    option_id: NonEmptyId | None
    desired_transformation: str
    current_scene_id: NonEmptyId
    desired_scene_id: NonEmptyId
    decisive_rollout_scene_id: NonEmptyId | None
    main_obstacle: str
    action_tendency: EmocioActionTendency
    valuation_dimensions: tuple[ValuationDimension, ...]
    intensity: Score01
    abstains: bool = False
    uncertainty: str

    @model_validator(mode="after")
    def validate_abstention(self) -> "EmocioNativeConclusion":
        if self.abstains and self.option_id is not None:
            raise ValueError("An abstaining native conclusion cannot select an option")
        if self.option_id is None and self.decisive_rollout_scene_id is not None:
            raise ValueError("A conclusion without an option cannot cite a decisive rollout")
        if self.option_id is not None and self.decisive_rollout_scene_id is None:
            raise ValueError("A selected Emocio option requires its decisive rollout scene")
        valuation_names = tuple(item.name for item in self.valuation_dimensions)
        if self.option_id is not None:
            if valuation_names != EMOCIO_VALUATION_DIMENSIONS:
                raise ValueError(
                    "Selected Emocio option requires all canonical valuation dimensions"
                )
        elif valuation_names:
            raise ValueError("A conclusion without an option cannot carry option valuation")
        return self

    def validate_against(
        self,
        packet: EmocioInputPacket,
        visual_state: EmocioVisualState,
    ) -> Self:
        """Bind native conclusion lineage to its packet and structured visual state."""

        self.validate_packet(packet)
        if self.current_scene_id != visual_state.current_scene.scene_id:
            raise ValueError("Emocio conclusion current scene differs from visual state")
        if self.desired_scene_id != visual_state.desired_scene.scene_id:
            raise ValueError("Emocio conclusion desired scene differs from visual state")
        if self.decisive_rollout_scene_id is not None:
            rollout_by_id = {
                rollout.scene_id: rollout for rollout in visual_state.option_rollouts
            }
            rollout = rollout_by_id.get(self.decisive_rollout_scene_id)
            if rollout is None or rollout.option_id != self.option_id:
                raise ValueError(
                    "Decisive Emocio rollout must exist and match the selected option"
                )
            valuation_by_option = {
                valuation.option_id: valuation
                for valuation in visual_state.option_valuations
            }
            valuation = valuation_by_option.get(self.option_id)
            if valuation is None or valuation.dimensions != self.valuation_dimensions:
                raise ValueError(
                    "Emocio conclusion valuation must match its decisive option rollout"
                )
        return self

    def validate_packet(self, packet: EmocioInputPacket) -> Self:
        """Verify packet identity, scene lineage, and option scope."""

        if self.source_packet_id != packet.packet_id:
            raise ValueError("Emocio conclusion belongs to another input packet")
        if self.source_scene_id != packet.scene_id:
            raise ValueError("Emocio conclusion scene differs from its packet")
        if self.option_id is not None and self.option_id not in packet.allowed_option_ids:
            raise ValueError("Emocio conclusion selected an option outside its packet")
        return self


__all__ = [
    "AttentionWeight",
    "EmocioActionTendency",
    "EmocioInputPacket",
    "EmocioNativeConclusion",
    "EmocioOptionValuation",
    "EmocioSceneKind",
    "EmocioVisualState",
    "EmocioWorld",
    "EMOCIO_VALUATION_DIMENSIONS",
    "ImageArtifact",
    "ImageMediaType",
    "ValuationDimension",
    "EmocioValuationDimensionName",
    "VisualSceneSpec",
]
