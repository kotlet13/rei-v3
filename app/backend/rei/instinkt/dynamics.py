"""Bounded deterministic virtual-body transitions and option rollouts."""

from __future__ import annotations

import math

from .body import body_values, clamp01, create_derived_body_state
from ..models.instinkt import (
    AssociationMatch,
    BODY_DIMENSIONS,
    BodyDelta,
    BodyState,
    BodyTransition,
    InstinktInputPacket,
    InstinktOptionRollout,
    InstinktSimulationConfig,
    OptionBodyEffect,
)


def predicted_loss(
    *,
    final_state: BodyState,
    effect: OptionBodyEffect,
    config: InstinktSimulationConfig,
    loss_memory_strength: float,
) -> float:
    value = (
        config.loss_base_weight * effect.base_predicted_loss
        + config.loss_integrity_weight * (1.0 - final_state.physical_integrity)
        + config.loss_pain_weight * final_state.pain
        + config.loss_tension_weight * final_state.tension
        + config.loss_boundary_weight * (1.0 - final_state.boundary_integrity)
        + config.loss_resource_weight * (1.0 - final_state.resource_security)
        + config.loss_attachment_weight * (1.0 - final_state.attachment_security)
        + config.association_loss_weight * loss_memory_strength
    )
    return clamp01(value)


def recoverability(
    *,
    final_state: BodyState,
    effect: OptionBodyEffect,
    config: InstinktSimulationConfig,
    loss_memory_strength: float,
    projection_recovery_prior: float | None = None,
) -> float:
    value = (
        config.recovery_base_weight * effect.base_recoverability
        + config.recovery_energy_weight * final_state.energy
        + config.recovery_escape_weight * final_state.escape_availability
        + config.recovery_predictability_weight * final_state.predictability
        + config.recovery_trust_weight * final_state.trust
        + config.recovery_attachment_weight * final_state.attachment_security
        + config.recovery_resource_weight * final_state.resource_security
        - config.association_recovery_penalty * loss_memory_strength
    )
    if projection_recovery_prior is not None:
        memory_weight = config.association_recovery_penalty
        value = (
            (1.0 - memory_weight) * value
            + memory_weight * projection_recovery_prior
        )
    return clamp01(value)


def projection_recoverability_prior(
    association_matches: tuple[AssociationMatch, ...],
) -> float | None:
    """Weighted prediction-only prior; never an observed body outcome."""

    candidates = tuple(
        (match.predicted_recoverability, match.retrieval_score)
        for match in association_matches
        if match.predicted_recoverability is not None
        and match.source_record_kind == "projection_observation"
    )
    total_weight = sum(weight for _, weight in candidates)
    if not candidates or total_weight <= 0.0:
        return None
    return clamp01(
        sum(value * weight for value, weight in candidates) / total_weight
    )


def simulate_option_rollout(
    *,
    packet: InstinktInputPacket,
    source_body_state: BodyState,
    effect: OptionBodyEffect,
    config: InstinktSimulationConfig,
    association_matches: tuple[AssociationMatch, ...] = (),
) -> InstinktOptionRollout:
    """Apply at most eight fixed steps; no convergence or agent loop exists."""

    effect.validate_against(packet)
    if packet.source_body_state_id != source_body_state.body_state_id:
        raise ValueError("Instinkt packet belongs to another source BodyState")
    requested_delta = {item.dimension: item.delta for item in effect.body_deltas}
    current = source_body_state
    transitions: list[BodyTransition] = []
    for step_index in range(1, config.rollout_steps + 1):
        values = body_values(current)
        for dimension in BODY_DIMENSIONS:
            total_delta = requested_delta.get(dimension, 0.0)
            step_delta = max(
                -config.max_abs_delta_per_step,
                min(
                    config.max_abs_delta_per_step,
                    total_delta / config.rollout_steps,
                ),
            )
            values[dimension] = clamp01(values[dimension] + step_delta)
        next_state = create_derived_body_state(
            previous=current,
            values=values,
            effect=effect,
            config=config,
            step_index=step_index,
        )
        deltas = tuple(
            BodyDelta(
                dimension=dimension,
                delta=getattr(next_state, dimension) - getattr(current, dimension),
            )
            for dimension in BODY_DIMENSIONS
            if not math.isclose(
                getattr(next_state, dimension),
                getattr(current, dimension),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        )
        transition = BodyTransition.create_simulated(
            from_state=current,
            to_state=next_state,
            deltas=deltas,
            triggering_evidence_ids=effect.triggering_evidence_ids,
            packet=packet,
            effect=effect,
            config=config,
            step_index=step_index,
        )
        transition.validate_simulation_lineage(
            packet=packet,
            effect=effect,
            config=config,
        )
        transitions.append(transition)
        current = next_state

    loss_memory_strength = max(
        (
            match.retrieval_score
            for match in association_matches
            if match.carries_experienced_loss
        ),
        default=0.0,
    )
    recovery_prior = projection_recoverability_prior(association_matches)
    rollout = InstinktOptionRollout.create_simulated(
        packet=packet,
        source_body_state=source_body_state,
        effect=effect,
        config=config,
        transitions=tuple(transitions),
        association_matches=association_matches,
        predicted_loss=predicted_loss(
            final_state=current,
            effect=effect,
            config=config,
            loss_memory_strength=loss_memory_strength,
        ),
        recoverability=recoverability(
            final_state=current,
            effect=effect,
            config=config,
            loss_memory_strength=loss_memory_strength,
            projection_recovery_prior=recovery_prior,
        ),
    )
    rollout.validate_simulation_lineage(
        packet=packet,
        source_body_state=source_body_state,
        effect=effect,
        config=config,
        association_matches=association_matches,
    )
    return rollout


__all__ = [
    "predicted_loss",
    "projection_recoverability_prior",
    "recoverability",
    "simulate_option_rollout",
]
