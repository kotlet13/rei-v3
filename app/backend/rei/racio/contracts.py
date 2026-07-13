"""Strict structured-output boundary shared by Racio native processors."""

from __future__ import annotations

from typing import Self

from pydantic import model_validator

from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText, Score01
from ..models.racio import RacioInputPacket, RacioNativeConclusion


class RacioStructuredOutput(FrozenModel):
    """Untrusted provider output before it becomes a native conclusion."""

    option_id: NonEmptyId | None
    facts_used: tuple[NonEmptyText, ...]
    evidence_ids_used: tuple[NonEmptyId, ...]
    unknowns: tuple[NonEmptyText, ...]
    causal_sequence: tuple[NonEmptyText, ...]
    utility_structure: tuple[NonEmptyText, ...]
    explicit_goal: NonEmptyText
    main_objection: NonEmptyText
    confidence: Score01
    abstains: bool
    uncertainty: NonEmptyText

    @model_validator(mode="after")
    def validate_structure(self) -> Self:
        if (self.option_id is None) != self.abstains:
            raise ValueError(
                "Structured Racio output must abstain exactly when option_id is null"
            )
        for field_name in (
            "facts_used",
            "evidence_ids_used",
            "unknowns",
            "causal_sequence",
            "utility_structure",
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
        return self

    def validate_against(
        self,
        packet: RacioInputPacket,
        *,
        supporting_evidence_ids: tuple[NonEmptyId, ...] | None = None,
    ) -> Self:
        if (
            self.option_id is not None
            and self.option_id not in packet.allowed_option_ids
        ):
            raise ValueError("Structured Racio output selected an unknown option")
        permitted_facts = set(packet.explicit_facts).union(packet.world.facts)
        if not set(self.facts_used).issubset(permitted_facts):
            raise ValueError("Structured Racio output introduced a hallucinated fact")
        if not set(self.unknowns).issubset(packet.explicit_unknowns):
            raise ValueError("Structured Racio output introduced an unknown claim")
        if not set(self.evidence_ids_used).issubset(packet.evidence_ids):
            raise ValueError(
                "Structured Racio output cited evidence outside the packet"
            )
        if set(self.facts_used).intersection(packet.explicit_facts) and not (
            self.evidence_ids_used
        ):
            raise ValueError(
                "Explicit packet facts require at least one evidence citation"
            )
        packet.validate_fact_evidence_usage(
            self.facts_used,
            self.evidence_ids_used,
        )
        if supporting_evidence_ids is not None and not set(
            self.evidence_ids_used
        ).issubset(supporting_evidence_ids):
            raise ValueError(
                "Structured Racio evidence was not reported by the TextReasoner result"
            )
        return self

    def to_conclusion(
        self,
        packet: RacioInputPacket,
        *,
        reasoning_provider_result_id: NonEmptyId | None = None,
        reasoning_provider_result_hash: HashDigest | None = None,
    ) -> RacioNativeConclusion:
        self.validate_against(packet)
        return RacioNativeConclusion.create(
            packet=packet,
            option_id=self.option_id,
            facts_used=self.facts_used,
            evidence_ids_used=self.evidence_ids_used,
            unknowns=self.unknowns,
            causal_sequence=self.causal_sequence,
            utility_structure=self.utility_structure,
            explicit_goal=self.explicit_goal,
            main_objection=self.main_objection,
            confidence=self.confidence,
            abstains=self.abstains,
            uncertainty=self.uncertainty,
            reasoning_provider_result_id=reasoning_provider_result_id,
            reasoning_provider_result_hash=reasoning_provider_result_hash,
        )


__all__ = ["RacioStructuredOutput"]
