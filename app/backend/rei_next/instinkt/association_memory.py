"""Bounded deterministic exact-token associative memory for B8."""

from __future__ import annotations

from dataclasses import dataclass
from pydantic import Field, model_validator

from ..models.common import FrozenModel, Score01
from ..models.instinkt import AssociationMatch, InstinktAssociation


class AssociationMemoryConfig(FrozenModel):
    capacity: int = Field(default=32, ge=1, le=256)
    retrieval_limit: int = Field(default=4, ge=1, le=32)
    minimum_effective_strength: Score01 = 0.05
    max_advance_cycles: int = Field(default=10_000, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def validate_limits(self) -> AssociationMemoryConfig:
        if self.retrieval_limit > self.capacity:
            raise ValueError("Association retrieval_limit cannot exceed capacity")
        return self


@dataclass(frozen=True, slots=True)
class _MemoryEntry:
    association: InstinktAssociation
    inserted_cycle: int
    insertion_index: int


def _tokens(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({value.strip().casefold() for value in values if value.strip()}))


class BoundedAssociativeMemory:
    """Finite memory with visible linear decay and no semantic classifier."""

    def __init__(self, config: AssociationMemoryConfig | None = None) -> None:
        self.config = config or AssociationMemoryConfig()
        self._cycle = 0
        self._next_insertion_index = 0
        self._entries: list[_MemoryEntry] = []

    @property
    def cycle(self) -> int:
        return self._cycle

    @property
    def associations(self) -> tuple[InstinktAssociation, ...]:
        ordered = sorted(self._entries, key=lambda entry: entry.insertion_index)
        return tuple(entry.association for entry in ordered)

    def advance(self, cycles: int = 1) -> None:
        if isinstance(cycles, bool) or not isinstance(cycles, int):
            raise TypeError("Association-memory cycle advance must be an integer")
        if cycles < 0 or cycles > self.config.max_advance_cycles:
            raise ValueError("Association-memory cycle advance is outside its bounded range")
        self._cycle += cycles

    def add(self, association: InstinktAssociation) -> None:
        if any(
            entry.association.association_id == association.association_id
            for entry in self._entries
        ):
            raise ValueError("Association IDs are immutable and cannot be replaced")
        self._entries.append(
            _MemoryEntry(
                association=association,
                inserted_cycle=self._cycle,
                insertion_index=self._next_insertion_index,
            )
        )
        self._next_insertion_index += 1
        if len(self._entries) > self.config.capacity:
            victim = min(
                self._entries,
                key=lambda entry: (
                    self._effective_strength(entry),
                    entry.insertion_index,
                    entry.association.association_id,
                ),
            )
            self._entries.remove(victim)

    def retrieve(self, cue_tokens: tuple[str, ...]) -> tuple[AssociationMatch, ...]:
        query = set(_tokens(cue_tokens))
        if not query:
            return ()
        matches: list[AssociationMatch] = []
        for entry in self._entries:
            signature = set(_tokens(entry.association.cue_signature))
            overlap = tuple(sorted(query & signature))
            if not overlap or not signature:
                continue
            strength = self._effective_strength(entry)
            if strength < self.config.minimum_effective_strength:
                continue
            overlap_ratio = len(overlap) / len(signature)
            score = strength * overlap_ratio
            matches.append(
                AssociationMatch.create(
                    association=entry.association,
                    memory_cycle=self._cycle,
                    age_cycles=self._cycle - entry.inserted_cycle,
                    overlap_tokens=overlap,
                    effective_strength=strength,
                    retrieval_score=score,
                )
            )
        matches.sort(
            key=lambda match: (
                -match.retrieval_score,
                -match.effective_strength,
                match.association_id,
            )
        )
        return tuple(matches[: self.config.retrieval_limit])

    def _effective_strength(self, entry: _MemoryEntry) -> float:
        age = self._cycle - entry.inserted_cycle
        return max(
            0.0,
            min(
                1.0,
                entry.association.felt_intensity - entry.association.decay * age,
            ),
        )


__all__ = [
    "AssociationMatch",
    "AssociationMemoryConfig",
    "BoundedAssociativeMemory",
]
