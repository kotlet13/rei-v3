from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from .common import (
    FrozenArtifactModel,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
    SourceModality,
)


EvidenceProvenance = Literal["supplied", "inferred", "generated"]


class EvidenceItem(FrozenArtifactModel):
    schema_version: Literal["rei-native-evidence-v1"] = "rei-native-evidence-v1"
    evidence_id: NonEmptyId
    modality: SourceModality
    content: NonEmptyText
    grounded: bool
    source_ref: NonEmptyText
    confidence: Score01
    provenance_kind: EvidenceProvenance = "supplied"
    inferred_by: NonEmptyId | None = None

    @model_validator(mode="after")
    def validate_grounding_boundary(self) -> Self:
        if self.provenance_kind == "supplied":
            if self.inferred_by is not None:
                raise ValueError("Supplied evidence cannot name an inference producer")
            return self
        if self.grounded:
            raise ValueError("Inferred or generated evidence cannot be grounded")
        if self.inferred_by is None:
            raise ValueError("Inferred or generated evidence must identify its producer")
        return self


class DecisionOption(FrozenArtifactModel):
    schema_version: Literal["rei-native-decision-option-v1"] = (
        "rei-native-decision-option-v1"
    )
    option_id: NonEmptyId
    label: NonEmptyText
    description: str = ""


class SceneEvent(FrozenArtifactModel):
    schema_version: Literal["rei-native-scene-event-v1"] = "rei-native-scene-event-v1"
    event_id: NonEmptyId
    raw_input: str
    language: LanguageCode
    evidence: tuple[EvidenceItem, ...] = ()
    options: tuple[DecisionOption, ...] = ()
    actors: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        evidence_ids = [item.evidence_id for item in self.evidence]
        option_ids = [item.option_id for item in self.options]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Scene evidence IDs must be unique")
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Decision option IDs must be unique")
        return self

    def scene_hash(self) -> str:
        return self.content_hash()
