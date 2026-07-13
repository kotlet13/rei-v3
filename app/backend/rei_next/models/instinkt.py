"""Strict contracts for Instinkt's embodied and protective native route.

These models describe a bounded software simulator.  They are not medical or
physiological claims, and they contain no textual decision-provider behavior.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import FrozenArtifactModel, FrozenModel, NonEmptyId, Score01
from .scene import SceneEvent


InstinktActionTendency = Literal[
    "protect",
    "withdraw",
    "maintain",
    "set_boundary",
    "seek_safety",
    "seek_attachment",
    "conserve",
    "freeze",
    "unknown",
]
BodyDimension = Literal[
    "energy",
    "fatigue",
    "pain",
    "arousal",
    "tension",
    "physical_integrity",
    "uncertainty",
    "trust",
    "attachment_security",
    "resource_security",
    "boundary_integrity",
    "escape_availability",
    "predictability",
]
_BODY_DIMENSIONS: tuple[BodyDimension, ...] = (
    "energy",
    "fatigue",
    "pain",
    "arousal",
    "tension",
    "physical_integrity",
    "uncertainty",
    "trust",
    "attachment_security",
    "resource_security",
    "boundary_integrity",
    "escape_availability",
    "predictability",
)
UnitDelta = Annotated[
    float,
    Field(ge=-1.0, le=1.0, allow_inf_nan=False),
]


class InstinktWorld(FrozenArtifactModel):
    """Immutable snapshot of Instinkt's associative/protective world."""

    schema_version: Literal["rei-native-instinkt-world-v1"] = (
        "rei-native-instinkt-world-v1"
    )
    world_id: NonEmptyId
    associations: tuple[str, ...]
    trusted_patterns: tuple[str, ...]
    threat_patterns: tuple[str, ...]
    attachment_objects: tuple[str, ...]
    unresolved_losses: tuple[str, ...]
    boundary_patterns: tuple[str, ...]


class InstinktInputPacket(FrozenArtifactModel):
    """Profile-blind grounded cues routed to Instinkt without a chosen action."""

    schema_version: Literal["rei-native-instinkt-input-packet-v1"] = (
        "rei-native-instinkt-input-packet-v1"
    )
    packet_id: NonEmptyId
    scene_id: NonEmptyId
    source_body_state_id: NonEmptyId
    physical_cues: tuple[str, ...]
    uncertainty_cues: tuple[str, ...]
    trust_cues: tuple[str, ...]
    boundary_cues: tuple[str, ...]
    attachment_cues: tuple[str, ...]
    scarcity_cues: tuple[str, ...]
    escape_cues: tuple[str, ...]
    explicit_body_cues: tuple[str, ...]
    option_ids: tuple[NonEmptyId, ...]
    evidence_ids: tuple[NonEmptyId, ...]
    caveat: str

    @model_validator(mode="after")
    def validate_packet_references(self) -> "InstinktInputPacket":
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("option_ids must be unique")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        return self

    def validate_against(self, scene: SceneEvent, body_state: BodyState) -> Self:
        """Bind protective cues to one event and one explicit virtual-body state."""

        self.validate_scene(scene)
        if self.source_body_state_id != body_state.body_state_id:
            raise ValueError("Instinkt packet belongs to another BodyState")
        return self

    def validate_scene(self, scene: SceneEvent) -> Self:
        """Bind packet option/evidence scope to the trusted event."""

        if self.scene_id != scene.event_id:
            raise ValueError("Instinkt packet belongs to another SceneEvent")
        scene_option_ids = {option.option_id for option in scene.options}
        if set(self.option_ids) != scene_option_ids:
            raise ValueError("Instinkt packet must preserve every SceneEvent option")
        scene_evidence_ids = {item.evidence_id for item in scene.evidence}
        if not set(self.evidence_ids).issubset(scene_evidence_ids):
            raise ValueError("Instinkt packet evidence must belong to the SceneEvent")
        return self


class BodyState(FrozenArtifactModel):
    """Normalized virtual-body state for one point in a bounded cycle."""

    schema_version: Literal["rei-native-body-state-v1"] = (
        "rei-native-body-state-v1"
    )
    body_state_id: NonEmptyId
    energy: Score01
    fatigue: Score01
    pain: Score01
    arousal: Score01
    tension: Score01
    physical_integrity: Score01
    uncertainty: Score01
    trust: Score01
    attachment_security: Score01
    resource_security: Score01
    boundary_integrity: Score01
    escape_availability: Score01
    predictability: Score01


class InstinktAssociation(FrozenArtifactModel):
    """One bounded, fallible associative-memory record."""

    schema_version: Literal["rei-native-instinkt-association-v1"] = (
        "rei-native-instinkt-association-v1"
    )
    association_id: NonEmptyId
    cue_signature: tuple[str, ...]
    body_state_before: BodyState
    felt_intensity: Score01
    protected_target: str
    experienced_loss: str | None
    action_taken: str
    outcome: str
    trust_delta: UnitDelta
    attachment_delta: UnitDelta
    boundary_delta: UnitDelta
    decay: Score01


class BodyDelta(FrozenModel):
    """One ordered dimension delta in a deterministic body transition."""

    dimension: BodyDimension
    delta: UnitDelta


class BodyTransition(FrozenArtifactModel):
    """Auditable transition from one virtual-body state to the next."""

    schema_version: Literal["rei-native-body-transition-v1"] = (
        "rei-native-body-transition-v1"
    )
    transition_id: NonEmptyId
    from_state: BodyState
    to_state: BodyState
    deltas: tuple[BodyDelta, ...]
    triggering_evidence_ids: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_unique_delta_dimensions(self) -> "BodyTransition":
        """Prevent ambiguous duplicate updates to the same body dimension."""

        dimensions = tuple(delta.dimension for delta in self.deltas)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("deltas must contain each body dimension at most once")
        if (
            self.from_state.body_state_id == self.to_state.body_state_id
            and self.from_state != self.to_state
        ):
            raise ValueError("Different body states cannot share one stable ID")
        delta_by_dimension = {item.dimension: item.delta for item in self.deltas}
        expected_deltas = {
            dimension: getattr(self.to_state, dimension)
            - getattr(self.from_state, dimension)
            for dimension in _BODY_DIMENSIONS
            if not math.isclose(
                getattr(self.to_state, dimension),
                getattr(self.from_state, dimension),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        }
        expected_dimension_order = tuple(
            dimension for dimension in _BODY_DIMENSIONS if dimension in expected_deltas
        )
        if dimensions != expected_dimension_order:
            raise ValueError("deltas must record every and only changed body dimension")
        for dimension, expected in expected_deltas.items():
            if not math.isclose(
                delta_by_dimension[dimension],
                expected,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError(f"delta for {dimension} does not match the state change")
        if len(set(self.triggering_evidence_ids)) != len(self.triggering_evidence_ids):
            raise ValueError("triggering_evidence_ids must be unique")
        return self

    def validate_against(
        self,
        packet: InstinktInputPacket,
        scene: SceneEvent,
    ) -> Self:
        """Keep triggering evidence within the routed Instinkt packet scope."""

        packet.validate_scene(scene)
        if not set(self.triggering_evidence_ids).issubset(packet.evidence_ids):
            raise ValueError("Body transition evidence must belong to its Instinkt packet")
        return self


BodyTrajectory = Annotated[tuple[BodyState, ...], Field(min_length=1)]


class InstinktOptionRollout(FrozenArtifactModel):
    """A bounded virtual-body trajectory for one explicit decision option."""

    schema_version: Literal["rei-native-instinkt-option-rollout-v1"] = (
        "rei-native-instinkt-option-rollout-v1"
    )
    rollout_id: NonEmptyId
    option_id: NonEmptyId
    trajectory: BodyTrajectory
    dominant_alarm: str
    predicted_loss: Score01
    recoverability: Score01
    protected_targets: tuple[str, ...]
    boundary_outcome: str
    trust_outcome: str
    attachment_outcome: str
    escape_outcome: str

    @model_validator(mode="after")
    def validate_stable_body_state_ids(self) -> Self:
        states_by_id: dict[str, BodyState] = {}
        for state in self.trajectory:
            existing = states_by_id.get(state.body_state_id)
            if existing is not None and existing != state:
                raise ValueError(
                    "Different trajectory states cannot share one stable BodyState ID"
                )
            states_by_id[state.body_state_id] = state
        return self


class InstinktNativeConclusion(FrozenArtifactModel):
    """Instinkt's immutable structured result, preceding verbalization."""

    schema_version: Literal["rei-native-instinkt-conclusion-v1"] = (
        "rei-native-instinkt-conclusion-v1"
    )
    conclusion_id: NonEmptyId
    source_packet_id: NonEmptyId
    source_scene_id: NonEmptyId
    source_body_state_id: NonEmptyId
    mind: Literal["I"] = "I"
    option_id: NonEmptyId | None
    dominant_alarm: str
    danger_claims: tuple[str, ...]
    protected_targets: tuple[str, ...]
    action_tendency: InstinktActionTendency
    minimum_safety_condition: str
    decisive_rollout_id: NonEmptyId | None
    decisive_rollout_option_id: NonEmptyId | None
    intensity: Score01
    abstains: bool = False
    uncertainty: str

    @model_validator(mode="after")
    def validate_option_references(self) -> "InstinktNativeConclusion":
        if self.abstains and self.option_id is not None:
            raise ValueError("An abstaining native conclusion cannot select an option")
        if self.option_id is None and (
            self.decisive_rollout_id is not None
            or self.decisive_rollout_option_id is not None
        ):
            raise ValueError("A conclusion without an option cannot cite a decisive rollout")
        if (self.decisive_rollout_id is None) != (
            self.decisive_rollout_option_id is None
        ):
            raise ValueError("Decisive rollout ID and option ID must be recorded together")
        if (
            self.decisive_rollout_option_id is not None
            and self.option_id != self.decisive_rollout_option_id
        ):
            raise ValueError("Decisive rollout option must match the selected option")
        return self

    def validate_against(
        self,
        packet: InstinktInputPacket,
        body_state: BodyState,
        rollouts: tuple[InstinktOptionRollout, ...] = (),
    ) -> Self:
        """Bind the native result to its packet, initial body, and decisive rollout."""

        self.validate_packet(packet)
        if self.source_body_state_id != body_state.body_state_id:
            raise ValueError("Instinkt conclusion belongs to another BodyState")
        if packet.source_body_state_id != body_state.body_state_id:
            raise ValueError("Instinkt packet and conclusion must share initial BodyState")
        rollout_ids = tuple(rollout.rollout_id for rollout in rollouts)
        if len(set(rollout_ids)) != len(rollout_ids):
            raise ValueError("Instinkt rollout IDs must be unique")
        rollout_option_ids = tuple(rollout.option_id for rollout in rollouts)
        if len(set(rollout_option_ids)) != len(rollout_option_ids):
            raise ValueError("Instinkt rollouts must use each option at most once")
        if set(rollout_option_ids) != set(packet.option_ids):
            raise ValueError("Instinkt rollouts must cover every packet option")
        states_by_id = {body_state.body_state_id: body_state}
        for rollout in rollouts:
            if rollout.trajectory[0] != body_state:
                raise ValueError(
                    "Every Instinkt rollout must start from the source BodyState"
                )
            for state in rollout.trajectory:
                existing = states_by_id.get(state.body_state_id)
                if existing is not None and existing != state:
                    raise ValueError(
                        "Different states across rollouts cannot share one BodyState ID"
                    )
                states_by_id[state.body_state_id] = state
        if self.decisive_rollout_id is not None:
            rollout_by_id = {rollout.rollout_id: rollout for rollout in rollouts}
            rollout = rollout_by_id.get(self.decisive_rollout_id)
            if rollout is None or rollout.option_id != self.decisive_rollout_option_id:
                raise ValueError(
                    "Decisive Instinkt rollout must exist and match the selected option"
                )
        return self

    def validate_packet(self, packet: InstinktInputPacket) -> Self:
        """Verify packet identity, source body, scene, and option scope."""

        if self.source_packet_id != packet.packet_id:
            raise ValueError("Instinkt conclusion belongs to another input packet")
        if self.source_scene_id != packet.scene_id:
            raise ValueError("Instinkt conclusion scene differs from its packet")
        if self.source_body_state_id != packet.source_body_state_id:
            raise ValueError("Instinkt conclusion body state differs from its packet")
        if self.option_id is not None and self.option_id not in packet.option_ids:
            raise ValueError("Instinkt conclusion selected an option outside its packet")
        return self


__all__ = [
    "BodyDelta",
    "BodyDimension",
    "BodyState",
    "BodyTrajectory",
    "BodyTransition",
    "InstinktActionTendency",
    "InstinktAssociation",
    "InstinktInputPacket",
    "InstinktNativeConclusion",
    "InstinktOptionRollout",
    "InstinktWorld",
    "UnitDelta",
]
