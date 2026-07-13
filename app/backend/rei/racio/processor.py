"""Independent native Racio processors, including a deterministic test policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from ..models.common import FrozenModel, Score01
from ..models.racio import RacioInputPacket, RacioNativeConclusion
from .contracts import RacioStructuredOutput


class DeterministicRacioPolicy(FrozenModel):
    """Transparent fixture policy; it deliberately performs no semantic scoring."""

    policy_id: Literal["first-allowed-option-v1"] = "first-allowed-option-v1"
    confidence: Score01 = 0.5


@runtime_checkable
class RacioNativeProcessor(Protocol):
    @property
    def processor_id(self) -> str: ...

    def process(self, packet: RacioInputPacket) -> RacioNativeConclusion: ...


def _deduplicate(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _distinct_sequence(
    values: tuple[str, ...],
    *,
    forbidden: set[str],
) -> tuple[str, ...]:
    if not values:
        values = ("inspect supplied packet fields", "select by packet option order")
    result: list[str] = []
    for index, value in enumerate(values):
        candidate = f"fixture-sequence[{index}]: {value}"
        while candidate in forbidden or candidate in result:
            candidate = f"fixture-sequence: {candidate}"
        result.append(candidate)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DeterministicRacioProvider:
    """First-option fixture provider used for reproducible infrastructure tests.

    The option rule is positional and explicit.  Labels, descriptions and cue
    keywords never influence selection, so this is not a semantic stand-in for
    the eventual model-backed processor.
    """

    policy: DeterministicRacioPolicy = field(default_factory=DeterministicRacioPolicy)

    @property
    def processor_id(self) -> str:
        return f"deterministic-racio:{self.policy.policy_id}"

    def process(self, packet: RacioInputPacket) -> RacioNativeConclusion:
        option_id = packet.allowed_option_ids[0] if packet.allowed_option_ids else None
        facts = _deduplicate((*packet.explicit_facts, *packet.world.facts))
        unknowns = _deduplicate(packet.explicit_unknowns)
        causal_sequence = _distinct_sequence(
            _deduplicate((*packet.world.timelines, *packet.time)),
            forbidden=set(facts).union(unknowns),
        )
        consequences = tuple(
            f"consequence[{index}]/{item.option_id}: {item.consequence}"
            for index, item in enumerate(packet.explicit_consequences)
            if item.option_id == option_id
        )
        utility_structure = consequences or (
            "fixture-policy: preserve packet option order without semantic scoring",
        )
        output = RacioStructuredOutput(
            option_id=option_id,
            facts_used=facts,
            evidence_ids_used=(packet.evidence_ids if packet.explicit_facts else ()),
            unknowns=unknowns,
            causal_sequence=causal_sequence,
            utility_structure=utility_structure,
            explicit_goal=(
                "Apply the first allowed option in packet order."
                if option_id is not None
                else "Record that the packet contains no allowed option."
            ),
            main_objection=(
                f"Explicit constraint: {packet.constraints[0]}"
                if packet.constraints
                else "No explicit constraint was supplied."
            ),
            confidence=self.policy.confidence,
            abstains=option_id is None,
            uncertainty=(
                "Explicit unknowns remain unresolved."
                if unknowns
                else "No explicit unknown was supplied."
            ),
        ).validate_against(packet)
        return output.to_conclusion(packet)


__all__ = [
    "DeterministicRacioPolicy",
    "DeterministicRacioProvider",
    "RacioNativeProcessor",
]
