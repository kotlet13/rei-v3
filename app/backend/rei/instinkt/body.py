"""Pure helpers for normalized virtual-body state construction."""

from __future__ import annotations

from collections.abc import Mapping

from ..ids import content_id
from ..models.instinkt import (
    BODY_DIMENSIONS,
    BodyState,
    InstinktSimulationConfig,
    OptionBodyEffect,
)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def body_values(state: BodyState) -> dict[str, float]:
    return {dimension: getattr(state, dimension) for dimension in BODY_DIMENSIONS}


def create_derived_body_state(
    *,
    previous: BodyState,
    values: Mapping[str, float],
    effect: OptionBodyEffect,
    config: InstinktSimulationConfig,
    step_index: int,
) -> BodyState:
    normalized = {
        dimension: clamp01(float(values[dimension])) for dimension in BODY_DIMENSIONS
    }
    identity_payload = {
        "previous_body_state_id": previous.body_state_id,
        "previous_body_state_hash": previous.content_hash(),
        "effect_id": effect.effect_id,
        "effect_hash": effect.effect_hash,
        "config_id": config.config_id,
        "config_hash": config.config_hash,
        "step_index": step_index,
        "values": normalized,
    }
    return BodyState(
        body_state_id=content_id("body_state", identity_payload),
        **normalized,
    )


__all__ = ["body_values", "clamp01", "create_derived_body_state"]
