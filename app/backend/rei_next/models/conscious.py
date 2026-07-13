"""Conscious commitment, narration, and observable behavior contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from .common import FrozenArtifactModel, MindId, NonEmptyId, Score01


ConsciousDecisionStatus = Literal[
    "committed",
    "deferred",
    "oscillating",
    "blocked",
    "unknown",
]
BehaviorStatus = Literal[
    "executed",
    "delayed",
    "oscillating",
    "sabotaged",
    "blocked",
    "unresolved",
]
AlignmentStatus = Literal["aligned", "diverged", "unknown", "not_applicable"]


class ConsciousDecision(FrozenArtifactModel):
    """A conscious commitment made through Racio, not a governance mandate."""

    schema_version: Literal["rei-native-conscious-decision-v1"] = (
        "rei-native-conscious-decision-v1"
    )
    decision_id: NonEmptyId
    made_by: Literal["R"] = "R"
    option_id: NonEmptyId | None = None
    declared_reason: str
    conscious_confidence: Score01
    aligned_with_governance_mandate: bool | None = None
    decision_status: ConsciousDecisionStatus


class RacioSelfNarrative(FrozenArtifactModel):
    """A downstream self-narrative that cannot mutate decision or behavior."""

    schema_version: Literal["rei-native-racio-self-narrative-v1"] = (
        "rei-native-racio-self-narrative-v1"
    )
    narrative_id: NonEmptyId
    source_decision_id: NonEmptyId
    source_resultant_id: NonEmptyId | None = None
    explanation: str
    claimed_motive: str
    acknowledged_minds: tuple[MindId, ...] = ()
    omitted_minds: tuple[MindId, ...] = ()
    uncertainty: str

    @model_validator(mode="after")
    def validate_mind_sets(self) -> Self:
        if len(set(self.acknowledged_minds)) != len(self.acknowledged_minds):
            raise ValueError("acknowledged_minds must be unique")
        if len(set(self.omitted_minds)) != len(self.omitted_minds):
            raise ValueError("omitted_minds must be unique")
        overlap = set(self.acknowledged_minds) & set(self.omitted_minds)
        if overlap:
            raise ValueError("a mind cannot be both acknowledged and omitted")
        return self


class BehaviorResultant(FrozenArtifactModel):
    """Observable one-cycle behavior, separate from mandate and commitment."""

    schema_version: Literal["rei-native-behavior-resultant-v1"] = (
        "rei-native-behavior-resultant-v1"
    )
    resultant_id: NonEmptyId
    option_id: NonEmptyId | None = None
    status: BehaviorStatus
    governance_alignment: AlignmentStatus
    conscious_alignment: AlignmentStatus
    operational_controller: MindId | None = None
    residual_tensions: tuple[str, ...] = ()
    predicted_action: str


__all__ = [
    "BehaviorResultant",
    "BehaviorStatus",
    "AlignmentStatus",
    "ConsciousDecision",
    "ConsciousDecisionStatus",
    "RacioSelfNarrative",
]
