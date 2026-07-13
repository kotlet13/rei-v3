"""Strict domain contracts for Racio's native processing route.

The native input and conclusion deliberately contain no character profile or
authority rank. Interpretation and narration live in their downstream package
contracts and never expose hidden E/I native ground truth here.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    Score01,
)
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
    language: LanguageCode | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    source_scene_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
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
    previous_racio_projection_hashes: tuple[HashDigest, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
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
        if len(self.previous_racio_projection_ids) != len(
            self.previous_racio_projection_hashes
        ):
            raise ValueError("Racio projection IDs and hashes must have equal length")
        if len(set(self.previous_racio_projection_ids)) != len(
            self.previous_racio_projection_ids
        ):
            raise ValueError("Racio projection IDs must be unique")
        for consequence in self.explicit_consequences:
            if not set(consequence.evidence_ids).issubset(self.evidence_ids):
                raise ValueError("consequence evidence must belong to the packet")
        return self

    def validate_against(self, scene: SceneEvent) -> Self:
        """Bind packet option/evidence scope to a trusted normalized event."""

        if self.scene_id != scene.event_id:
            raise ValueError("Racio packet belongs to another SceneEvent")
        if self.language is not None and self.language != scene.language:
            raise ValueError("Racio packet language differs from the SceneEvent")
        if (
            self.source_scene_hash is not None
            and self.source_scene_hash != scene.scene_hash()
        ):
            raise ValueError("Racio packet source hash differs from the SceneEvent")
        scene_options = {option.option_id: option for option in scene.options}
        packet_options = {option.option_id: option for option in self.explicit_options}
        if packet_options != scene_options:
            raise ValueError("Racio explicit options must match the SceneEvent")
        if set(self.allowed_option_ids) != set(scene_options):
            raise ValueError("Racio packet must preserve every SceneEvent option")
        scene_evidence_ids = {item.evidence_id for item in scene.evidence}
        if not set(self.evidence_ids).issubset(scene_evidence_ids):
            raise ValueError("Racio packet evidence must belong to the SceneEvent")
        if self.source_scene_hash is not None:
            supplied_grounded = tuple(
                item
                for item in scene.evidence
                if item.grounded and item.provenance_kind == "supplied"
            )
            expected_facts = tuple(item.content for item in supplied_grounded)
            expected_evidence_ids = tuple(
                item.evidence_id for item in supplied_grounded
            )
            if self.explicit_facts != expected_facts:
                raise ValueError(
                    "Content-addressed Racio packet must preserve all supplied "
                    "and grounded facts"
                )
            if self.evidence_ids != expected_evidence_ids:
                raise ValueError(
                    "Content-addressed Racio packet evidence must match "
                    "its explicit facts"
                )
            if self.explicit_unknowns != scene.unknowns:
                raise ValueError(
                    "Content-addressed Racio packet must preserve SceneEvent unknowns"
                )
            expected_option_ids = tuple(
                option.option_id for option in scene.options
            )
            if (
                self.explicit_options != scene.options
                or self.allowed_option_ids != expected_option_ids
            ):
                raise ValueError(
                    "Content-addressed Racio packet must preserve "
                    "SceneEvent option order"
                )
            if self.constraints != scene.constraints:
                raise ValueError(
                    "Content-addressed Racio packet must preserve "
                    "SceneEvent constraints"
                )
            expected_packet_id = content_id(
                "racio_packet",
                self.model_dump(
                    mode="python",
                    round_trip=True,
                    exclude={"packet_id"},
                ),
            )
            if self.packet_id != expected_packet_id:
                raise ValueError("Racio packet ID does not match its canonical content")
        return self

    def validate_fact_evidence_usage(
        self,
        facts_used: tuple[str, ...],
        evidence_ids_used: tuple[NonEmptyId, ...],
    ) -> Self:
        """Require exact evidence support for facts from a B5 packet."""

        if self.source_scene_hash is None:
            return self
        evidence_by_fact: dict[str, set[str]] = {}
        for fact, evidence_id in zip(
            self.explicit_facts,
            self.evidence_ids,
            strict=True,
        ):
            evidence_by_fact.setdefault(fact, set()).add(evidence_id)
        used_explicit_facts = set(facts_used).intersection(self.explicit_facts)
        cited = set(evidence_ids_used)
        allowed_citations = set().union(
            *(evidence_by_fact[fact] for fact in used_explicit_facts)
        )
        if not cited.issubset(allowed_citations):
            raise ValueError("Racio evidence citation does not support a used fact")
        for fact in used_explicit_facts:
            if cited.isdisjoint(evidence_by_fact[fact]):
                raise ValueError("Every explicit fact used requires its own evidence")
        return self


class RacioNativeConclusion(FrozenArtifactModel):
    """Racio's immutable native conclusion, produced before governance."""

    schema_version: Literal["rei-native-racio-conclusion-v1"] = (
        "rei-native-racio-conclusion-v1"
    )
    conclusion_id: NonEmptyId
    source_packet_id: NonEmptyId
    source_scene_id: NonEmptyId
    source_packet_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    evidence_ids_used: tuple[NonEmptyId, ...] = Field(
        default=(),
        exclude_if=lambda value: not value,
    )
    reasoning_provider_result_id: NonEmptyId | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    reasoning_provider_result_hash: HashDigest | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
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

    @classmethod
    def create(
        cls,
        *,
        packet: RacioInputPacket,
        option_id: NonEmptyId | None,
        facts_used: tuple[str, ...],
        evidence_ids_used: tuple[NonEmptyId, ...],
        unknowns: tuple[str, ...],
        causal_sequence: tuple[str, ...],
        utility_structure: tuple[str, ...],
        explicit_goal: str,
        main_objection: str,
        confidence: Score01,
        abstains: bool,
        uncertainty: str,
        reasoning_provider_result_id: NonEmptyId | None = None,
        reasoning_provider_result_hash: HashDigest | None = None,
    ) -> "RacioNativeConclusion":
        """Create a content-addressed B5 conclusion bound to its exact packet."""

        base = {
            "schema_version": "rei-native-racio-conclusion-v1",
            "source_packet_id": packet.packet_id,
            "source_scene_id": packet.scene_id,
            "source_packet_hash": packet.content_hash(),
            "mind": "R",
            "option_id": option_id,
            "facts_used": facts_used,
            "unknowns": unknowns,
            "causal_sequence": causal_sequence,
            "utility_structure": utility_structure,
            "explicit_goal": explicit_goal,
            "main_objection": main_objection,
            "confidence": confidence,
            "abstains": abstains,
            "uncertainty": uncertainty,
        }
        if evidence_ids_used:
            base["evidence_ids_used"] = evidence_ids_used
        if reasoning_provider_result_id is not None:
            base["reasoning_provider_result_id"] = reasoning_provider_result_id
        if reasoning_provider_result_hash is not None:
            base["reasoning_provider_result_hash"] = reasoning_provider_result_hash
        conclusion = cls(
            conclusion_id=content_id("racio_conclusion", base),
            **base,
        )
        return conclusion.validate_against(packet)

    @model_validator(mode="after")
    def validate_abstention(self) -> "RacioNativeConclusion":
        if self.abstains and self.option_id is not None:
            raise ValueError("An abstaining native conclusion cannot select an option")
        if (self.reasoning_provider_result_id is None) != (
            self.reasoning_provider_result_hash is None
        ):
            raise ValueError("Racio provider result ID and hash must be recorded together")
        if self.source_packet_hash is None and (
            self.evidence_ids_used
            or self.reasoning_provider_result_id is not None
            or self.reasoning_provider_result_hash is not None
        ):
            raise ValueError(
                "B5 conclusion provenance requires an exact source packet hash"
            )
        if self.source_packet_hash is not None:
            if (self.option_id is None) != self.abstains:
                raise ValueError(
                    "A content-addressed conclusion must abstain exactly when "
                    "no option is selected"
                )
            for field_name in (
                "facts_used",
                "unknowns",
                "causal_sequence",
                "utility_structure",
                "evidence_ids_used",
            ):
                values = getattr(self, field_name)
                if len(set(values)) != len(values):
                    raise ValueError(f"{field_name} must contain unique values")
            if (
                set(self.facts_used).intersection(self.unknowns)
                or set(self.facts_used).intersection(self.causal_sequence)
                or set(self.unknowns).intersection(self.causal_sequence)
            ):
                raise ValueError(
                    "Facts, unknowns and causal sequence must remain distinct"
                )
            expected_id = content_id(
                "racio_conclusion",
                self.model_dump(
                    mode="python",
                    round_trip=True,
                    exclude={"conclusion_id"},
                ),
            )
            if self.conclusion_id != expected_id:
                raise ValueError(
                    "Racio conclusion ID does not match its canonical content"
                )
        return self

    def validate_against(self, packet: RacioInputPacket) -> Self:
        """Verify native conclusion lineage and selected-option scope."""

        if self.source_packet_id != packet.packet_id:
            raise ValueError("Racio conclusion belongs to another input packet")
        if self.source_scene_id != packet.scene_id:
            raise ValueError("Racio conclusion scene differs from its packet")
        if (
            self.option_id is not None
            and self.option_id not in packet.allowed_option_ids
        ):
            raise ValueError("Racio conclusion selected an option outside its packet")
        if self.source_packet_hash is not None:
            if self.source_packet_hash != packet.content_hash():
                raise ValueError("Racio conclusion source packet hash differs")
            if not set(self.evidence_ids_used).issubset(packet.evidence_ids):
                raise ValueError("Racio conclusion cites evidence outside its packet")
            permitted_facts = set(packet.explicit_facts).union(packet.world.facts)
            if not set(self.facts_used).issubset(permitted_facts):
                raise ValueError(
                    "Racio conclusion contains a fact absent from its packet"
                )
            if not set(self.unknowns).issubset(packet.explicit_unknowns):
                raise ValueError(
                    "Racio conclusion contains an unknown absent from its packet"
                )
            packet.validate_fact_evidence_usage(
                self.facts_used,
                self.evidence_ids_used,
            )
            expected_id = content_id(
                "racio_conclusion",
                self.model_dump(
                    mode="python",
                    round_trip=True,
                    exclude={"conclusion_id"},
                ),
            )
            if self.conclusion_id != expected_id:
                raise ValueError(
                    "Racio conclusion ID does not match its canonical content"
                )
        return self


__all__ = [
    "NumericCue",
    "RacioConsequence",
    "RacioInputPacket",
    "RacioNativeConclusion",
    "RacioWorld",
]
