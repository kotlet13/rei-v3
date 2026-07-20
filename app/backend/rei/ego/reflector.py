"""Read-only Ego reflection over already-derived longitudinal composition."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import Field, model_validator

from .composition import derive_composition_snapshot
from ..ids import content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.ego import EgoCompositionSnapshot, EgoTrace, SourcedEgoClaim


_FIRST_PERSON_EGO = re.compile(
    r"(?:\bjaz\s*,?\s*ego\b|\bi\s*,?\s*ego\b)",
    re.IGNORECASE,
)
_REFLECTABLE_KINDS = frozenset(
    {
        "identity_motif",
        "recurring_conflict",
        "recurring_translation_error",
        "unresolved_tension",
        "resolved_tension",
        "spoznanje",
        "commitment",
        "relationship_pattern",
    }
)
_KIND_LABELS = {
    "identity_motif": "an identity motif",
    "recurring_conflict": "a recurring conflict",
    "recurring_translation_error": "a recurring translation gap",
    "unresolved_tension": "an unresolved tension",
    "resolved_tension": "a resolved tension",
    "spoznanje": "a recorded realization",
    "commitment": "a recorded commitment",
    "relationship_pattern": "a relationship pattern",
}


def _cold_revalidate(value: EgoTrace | EgoCompositionSnapshot | SourcedEgoClaim):
    model_type = type(value)
    cold = model_type.model_validate(
        value.model_dump(mode="python", round_trip=True)
    )
    if cold != value:
        raise ValueError("Reflection input changed during cold validation")
    return cold


class EgoReflectionHypothesis(FrozenArtifactModel):
    """A sourced observation only; it has no runtime-control surface."""

    schema_version: Literal["rei-ego-reflection-hypothesis-v1"] = (
        "rei-ego-reflection-hypothesis-v1"
    )
    hypothesis_id: NonEmptyId
    ego_id: NonEmptyId
    source_trace_hash: HashDigest
    source_snapshot_id: NonEmptyId
    source_snapshot_hash: HashDigest
    source_claim_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    statement: NonEmptyText
    confidence: Score01
    supporting_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    hypothesis_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: str,
        source_trace_hash: str,
        source_snapshot_id: str,
        source_snapshot_hash: str,
        source_claim_ids: tuple[str, ...],
        statement: str,
        confidence: float,
        supporting_measure_ids: tuple[str, ...],
    ) -> "EgoReflectionHypothesis":
        base = {
            "schema_version": "rei-ego-reflection-hypothesis-v1",
            "ego_id": ego_id,
            "source_trace_hash": source_trace_hash,
            "source_snapshot_id": source_snapshot_id,
            "source_snapshot_hash": source_snapshot_hash,
            "source_claim_ids": tuple(sorted(set(source_claim_ids))),
            "statement": statement,
            "confidence": confidence,
            "supporting_measure_ids": tuple(sorted(set(supporting_measure_ids))),
        }
        hypothesis_id = content_id("ego_reflection", base)
        payload = {"hypothesis_id": hypothesis_id, **base}
        return cls(**payload, hypothesis_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_hypothesis(self) -> Self:
        if self.source_claim_ids != tuple(sorted(set(self.source_claim_ids))):
            raise ValueError("Reflection source claims must be sorted and unique")
        if self.supporting_measure_ids != tuple(
            sorted(set(self.supporting_measure_ids))
        ):
            raise ValueError("Reflection measure citations must be sorted and unique")
        if _FIRST_PERSON_EGO.search(self.statement):
            raise ValueError("Reflection cannot use first-person Ego voice")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"hypothesis_id", "hypothesis_hash"},
        )
        if self.hypothesis_id != content_id("ego_reflection", base):
            raise ValueError("Reflection hypothesis ID differs from its content")
        payload = {"hypothesis_id": self.hypothesis_id, **base}
        if self.hypothesis_hash != sha256_hex(payload):
            raise ValueError("Reflection hypothesis hash differs from its content")
        return self


@runtime_checkable
class EgoReflector(Protocol):
    """Read-only port: derive hypotheses from immutable trace artifacts."""

    def reflect(
        self,
        *,
        trace: EgoTrace,
        snapshot: EgoCompositionSnapshot,
    ) -> tuple[EgoReflectionHypothesis, ...]: ...


def _validate_reflection_sources(
    trace: EgoTrace,
    snapshot: EgoCompositionSnapshot,
) -> None:
    trace = _cold_revalidate(trace)
    snapshot = _cold_revalidate(snapshot)
    trace_measure_ids = tuple(measure.measure_id for measure in trace.measures)
    if snapshot.ego_id != trace.ego_id:
        raise ValueError("Reflection snapshot belongs to another Ego trace")
    if snapshot.source_trace_hash != trace.trace_hash:
        raise ValueError("Reflection snapshot differs from the current trace")
    if snapshot.evidence_measure_ids != trace_measure_ids:
        raise ValueError("Reflection snapshot must cite the trace measures exactly")
    if not trace_measure_ids or snapshot.through_measure_id != trace_measure_ids[-1]:
        raise ValueError("Reflection snapshot does not reach the trace boundary")
    if snapshot != derive_composition_snapshot(trace):
        raise ValueError(
            "Reflection snapshot must equal deterministic composition replay"
        )


def _statement_for(claim: SourcedEgoClaim) -> str:
    if _FIRST_PERSON_EGO.search(claim.text):
        raise ValueError("Reflection source claim uses forbidden first-person Ego voice")
    label = _KIND_LABELS[claim.kind]
    return f"Hypothesis about {label}: {claim.text}."


@dataclass(frozen=True, slots=True)
class DeterministicEgoReflector:
    """A deterministic, model-free reference implementation of the port."""

    base_confidence: float = 0.55

    def __post_init__(self) -> None:
        if not 0.0 <= self.base_confidence <= 1.0:
            raise ValueError("Reflector base confidence must be between zero and one")

    def reflect(
        self,
        *,
        trace: EgoTrace,
        snapshot: EgoCompositionSnapshot,
    ) -> tuple[EgoReflectionHypothesis, ...]:
        trace = _cold_revalidate(trace)
        snapshot = _cold_revalidate(snapshot)
        _validate_reflection_sources(trace, snapshot)
        allowed_measure_ids = set(snapshot.evidence_measure_ids)
        hypotheses: list[EgoReflectionHypothesis] = []
        for claim in snapshot.sourced_claims:
            claim = _cold_revalidate(claim)
            if claim.kind not in _REFLECTABLE_KINDS:
                continue
            if not set(claim.evidence_measure_ids).issubset(allowed_measure_ids):
                raise ValueError("Reflection claim cites a measure outside the trace")
            confidence = min(
                0.95,
                self.base_confidence + 0.1 * (len(claim.evidence_measure_ids) - 1),
            )
            hypotheses.append(
                EgoReflectionHypothesis.create(
                    ego_id=trace.ego_id,
                    source_trace_hash=trace.trace_hash,
                    source_snapshot_id=snapshot.snapshot_id,
                    source_snapshot_hash=snapshot.composition_hash,
                    source_claim_ids=(claim.claim_id,),
                    statement=_statement_for(claim),
                    confidence=confidence,
                    supporting_measure_ids=claim.evidence_measure_ids,
                )
            )
        return tuple(hypotheses)


__all__ = [
    "DeterministicEgoReflector",
    "EgoReflectionHypothesis",
    "EgoReflector",
]
