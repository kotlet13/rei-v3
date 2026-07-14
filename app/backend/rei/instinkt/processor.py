"""Profile-blind bounded Instinkt native processor for B8."""

from __future__ import annotations

from typing import NamedTuple

from .association_memory import AssociationMatch, BoundedAssociativeMemory
from .dynamics import simulate_option_rollout
from .manifestation import build_instinkt_manifestation
from .policy import (
    ProtectivePolicyDecision,
    build_native_conclusion,
    resolve_protective_policy,
)
from ..models.common import FrozenModel, NonEmptyId
from ..models.communication import InstinktManifestation
from ..models.instinkt import (
    BodyState,
    InstinktInputPacket,
    InstinktNativeConclusion,
    InstinktOptionRollout,
    InstinktSimulationConfig,
    OptionBodyEffect,
    instinkt_projection_memory_token,
)
from ..models.scene import SceneEvent


class OptionAssociationMatches(FrozenModel):
    option_id: NonEmptyId
    matches: tuple[AssociationMatch, ...] = ()


class InstinktProcessResult(NamedTuple):
    config: InstinktSimulationConfig
    association_matches: tuple[OptionAssociationMatches, ...]
    rollouts: tuple[InstinktOptionRollout, ...]
    policy: ProtectivePolicyDecision
    conclusion: InstinktNativeConclusion
    manifestation: InstinktManifestation


def process_instinkt(
    *,
    scene: SceneEvent,
    packet: InstinktInputPacket,
    source_body_state: BodyState,
    option_effects: tuple[OptionBodyEffect, ...],
    config: InstinktSimulationConfig | None = None,
    memory: BoundedAssociativeMemory | None = None,
    body_locations: tuple[str, ...] = (),
) -> InstinktProcessResult:
    """Execute one bounded cycle without character, LLM, or keyword policy input."""

    active_config = config or InstinktSimulationConfig.create()
    packet.validate_against(scene, source_body_state)
    if len(packet.option_ids) > active_config.max_options:
        raise ValueError("Instinkt option count exceeds the configured finite bound")
    effect_by_option = {effect.option_id: effect for effect in option_effects}
    if len(effect_by_option) != len(option_effects):
        raise ValueError("Instinkt requires exactly one typed effect per option")
    if set(effect_by_option) != set(packet.option_ids):
        raise ValueError("Typed Instinkt effects must cover every packet option exactly")

    option_matches: list[OptionAssociationMatches] = []
    rollouts: list[InstinktOptionRollout] = []
    projection_query_tokens = tuple(
        instinkt_projection_memory_token(projection_id, projection_hash)
        for projection_id, projection_hash in zip(
            packet.previous_instinkt_projection_ids,
            packet.previous_instinkt_projection_hashes,
            strict=True,
        )
    )
    for option_id in sorted(effect_by_option):
        effect = effect_by_option[option_id]
        effect.validate_against(packet)
        matches = (
            memory.retrieve(
                tuple(
                    sorted(
                        {
                            *effect.association_cue_tokens,
                            *projection_query_tokens,
                        }
                    )
                )
            )
            if memory is not None
            else ()
        )
        option_matches.append(
            OptionAssociationMatches(option_id=option_id, matches=matches)
        )
        rollouts.append(
            simulate_option_rollout(
                packet=packet,
                source_body_state=source_body_state,
                effect=effect,
                config=active_config,
                association_matches=matches,
            )
        )

    frozen_rollouts = tuple(rollouts)
    policy = resolve_protective_policy(
        packet=packet,
        source_body_state=source_body_state,
        effects=tuple(effect_by_option[key] for key in sorted(effect_by_option)),
        rollouts=frozen_rollouts,
        config=active_config,
    )
    conclusion = build_native_conclusion(
        packet=packet,
        source_body_state=source_body_state,
        effects=tuple(effect_by_option[key] for key in sorted(effect_by_option)),
        rollouts=frozen_rollouts,
        policy=policy,
        config=active_config,
    )
    manifestation_body_state = source_body_state
    decisive_rollout: InstinktOptionRollout | None = None
    if policy.decisive_rollout_id is not None:
        decisive_rollout = next(
            rollout
            for rollout in frozen_rollouts
            if rollout.rollout_id == policy.decisive_rollout_id
        )
        manifestation_body_state = decisive_rollout.trajectory[-1]
    manifestation = build_instinkt_manifestation(
        conclusion=conclusion,
        body_state=manifestation_body_state,
        decisive_rollout=decisive_rollout,
        body_locations=body_locations,
    )
    return InstinktProcessResult(
        config=active_config,
        association_matches=tuple(option_matches),
        rollouts=frozen_rollouts,
        policy=policy,
        conclusion=conclusion,
        manifestation=manifestation,
    )


__all__ = [
    "InstinktProcessResult",
    "OptionAssociationMatches",
    "process_instinkt",
]
