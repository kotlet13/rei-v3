"""Strict domain contracts for Racio's native processing route.

The native input and conclusion deliberately contain no character profile or
authority rank. Interpretation and narration live in their downstream package
contracts and never expose hidden E/I native ground truth here.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import FrozenArtifactModel, FrozenModel, NonEmptyId, Score01
from .scene import DecisionOption, SceneEvent


NumericCue = int | Annotated[float, Field(allow_inf_nan=False)]


class RacioConsequence(FrozenModel):
    """An explicit, evidence-addressable consequence supplied to Racio."""

    option_id: NonEmptyId
    consequence: str
    evidence_ids: tuple[NonEmptyId, ...]


class RacioWorld(FrozenArtifactModel):
    """Immutable snapshot of Racio's modality-specific world projection."""

    schema_version: Literal["rei-native-racio-world-v1"] = (
        "rei-native-racio-world-v1"
    )
    world_id: NonEmptyId
    explicit_beliefs: tuple[str, ...]
    facts: tuple[str, ...]
    rules: tuple[str, ...]
    timelines: tuple[str, ...]
    commitments: tuple[str, ...]


class RacioInputPacket(FrozenArtifactModel):
    """Profile-blind symbolic input for one Racio native-processing pass."""

    schema_version: Literal["rei-native-racio-input-packet-v1"] = (
        "rei-native-racio-input-packet-v1"
    )
    packet_id: NonEmptyId
    scene_id: NonEmptyId
    symbolic_and_language_cues: tuple[str, ...]
    numeric_cues: tuple[NumericCue, ...]
    explicit_facts: tuple[str, ...]
    explicit_unknowns: tuple[str, ...]
    time: tuple[str, ...]
    rules: tuple[str, ...]
    explicit_options: tuple[DecisionOption, ...]
    explicit_consequences: tuple[RacioConsequence, ...]
    constraints: tuple[str, ...]
    allowed_option_ids: tuple[NonEmptyId, ...]
    evidence_ids: tuple[NonEmptyId, ...]
    world: RacioWorld
    previous_racio_projection_ids: tuple[NonEmptyId, ...]
    caveat: str

    @model_validator(mode="after")
    def validate_packet_references(self) -> "RacioInputPacket":
        explicit_ids = tuple(option.option_id for option in self.explicit_options)
        if len(set(explicit_ids)) != len(explicit_ids):
            raise ValueError("explicit option IDs must be unique")
        if len(set(self.allowed_option_ids)) != len(self.allowed_option_ids):
            raise ValueError("allowed_option_ids must be unique")
        if not set(self.allowed_option_ids).issubset(explicit_ids):
            raise ValueError("allowed options must refer to explicit options")
        consequence_ids = {item.option_id for item in self.explicit_consequences}
        if not consequence_ids.issubset(explicit_ids):
            raise ValueError("consequences must refer to explicit options")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        for consequence in self.explicit_consequences:
            if not set(consequence.evidence_ids).issubset(self.evidence_ids):
                raise ValueError("consequence evidence must belong to the packet")
        return self

    def validate_against(self, scene: SceneEvent) -> Self:
        """Bind packet option/evidence scope to a trusted normalized event."""

        if self.scene_id != scene.event_id:
            raise ValueError("Racio packet belongs to another SceneEvent")
        scene_options = {option.option_id: option for option in scene.options}
        packet_options = {option.option_id: option for option in self.explicit_options}
        if packet_options != scene_options:
            raise ValueError("Racio explicit options must match the SceneEvent")
        if set(self.allowed_option_ids) != set(scene_options):
            raise ValueError("Racio packet must preserve every SceneEvent option")
        scene_evidence_ids = {item.evidence_id for item in scene.evidence}
        if not set(self.evidence_ids).issubset(scene_evidence_ids):
            raise ValueError("Racio packet evidence must belong to the SceneEvent")
        return self


class RacioNativeConclusion(FrozenArtifactModel):
    """Racio's immutable native conclusion, produced before governance."""

    schema_version: Literal["rei-native-racio-conclusion-v1"] = (
        "rei-native-racio-conclusion-v1"
    )
    conclusion_id: NonEmptyId
    source_packet_id: NonEmptyId
    source_scene_id: NonEmptyId
    mind: Literal["R"] = "R"
    option_id: NonEmptyId | None
    facts_used: tuple[str, ...]
    unknowns: tuple[str, ...]
    causal_sequence: tuple[str, ...]
    utility_structure: tuple[str, ...]
    explicit_goal: str
    main_objection: str
    confidence: Score01
    abstains: bool = False
    uncertainty: str

    @model_validator(mode="after")
    def validate_abstention(self) -> "RacioNativeConclusion":
        if self.abstains and self.option_id is not None:
            raise ValueError("An abstaining native conclusion cannot select an option")
        return self

    def validate_against(self, packet: RacioInputPacket) -> Self:
        """Verify native conclusion lineage and selected-option scope."""

        if self.source_packet_id != packet.packet_id:
            raise ValueError("Racio conclusion belongs to another input packet")
        if self.source_scene_id != packet.scene_id:
            raise ValueError("Racio conclusion scene differs from its packet")
        if self.option_id is not None and self.option_id not in packet.allowed_option_ids:
            raise ValueError("Racio conclusion selected an option outside its packet")
        return self


__all__ = [
    "NumericCue",
    "RacioConsequence",
    "RacioInputPacket",
    "RacioNativeConclusion",
    "RacioWorld",
]
