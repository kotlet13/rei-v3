"""Deterministic native Emocio option policy."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.emocio import EmocioOptionValuation
from .valuation import aggregate_option_valuation


@dataclass(frozen=True, slots=True)
class OptionAggregateScore:
    option_id: str
    score: float


@dataclass(frozen=True, slots=True)
class EmocioPolicyDecision:
    selected: EmocioOptionValuation | None
    aggregate_scores: tuple[OptionAggregateScore, ...]
    tied_option_ids: tuple[str, ...] = ()


def choose_native_option(
    valuations: tuple[EmocioOptionValuation, ...],
) -> EmocioPolicyDecision:
    """Choose only a unique maximum; an exact tie remains explicit abstention."""

    scores = tuple(
        OptionAggregateScore(
            option_id=valuation.option_id,
            score=aggregate_option_valuation(valuation),
        )
        for valuation in valuations
    )
    if not scores:
        return EmocioPolicyDecision(selected=None, aggregate_scores=())
    maximum = max(item.score for item in scores)
    tied = tuple(item.option_id for item in scores if item.score == maximum)
    if len(tied) != 1:
        return EmocioPolicyDecision(
            selected=None,
            aggregate_scores=scores,
            tied_option_ids=tied,
        )
    valuation_by_option = {
        valuation.option_id: valuation for valuation in valuations
    }
    return EmocioPolicyDecision(
        selected=valuation_by_option[tied[0]],
        aggregate_scores=scores,
    )


__all__ = [
    "EmocioPolicyDecision",
    "OptionAggregateScore",
    "choose_native_option",
]
