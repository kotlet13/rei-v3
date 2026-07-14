"""Transparent protective scoring with explicit abstention on ties."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from .body import clamp01
from ..ids import content_id, sha256_hex
from ..models.common import FrozenArtifactModel, FrozenModel, HashDigest, NonEmptyId
from ..models.instinkt import (
    BodyState,
    InstinktInputPacket,
    InstinktNativeConclusion,
    InstinktOptionRollout,
    InstinktSimulationConfig,
    OptionBodyEffect,
)


ProtectiveCost = Annotated[
    float,
    Field(ge=0.0, le=1.5, allow_inf_nan=False),
]


class ProtectiveOptionScore(FrozenModel):
    option_id: NonEmptyId
    rollout_id: NonEmptyId
    rollout_hash: HashDigest
    protective_cost: ProtectiveCost


class ProtectivePolicyDecision(FrozenArtifactModel):
    schema_version: Literal["rei-native-protective-policy-v1"] = (
        "rei-native-protective-policy-v1"
    )
    policy_decision_id: NonEmptyId
    source_packet_id: NonEmptyId
    source_packet_hash: HashDigest
    source_body_state_id: NonEmptyId
    source_body_state_hash: HashDigest
    source_config_id: NonEmptyId
    source_config_hash: HashDigest
    status: Literal["selected", "abstained_tie", "abstained_no_options"]
    selected_option_id: NonEmptyId | None = None
    decisive_rollout_id: NonEmptyId | None = None
    tied_option_ids: tuple[NonEmptyId, ...] = ()
    option_scores: tuple[ProtectiveOptionScore, ...]
    policy_hash: HashDigest

    @model_validator(mode="after")
    def validate_policy(self) -> ProtectivePolicyDecision:
        option_ids = tuple(item.option_id for item in self.option_scores)
        if option_ids != tuple(sorted(set(option_ids))):
            raise ValueError("Protective policy scores must use canonical option order")
        if self.status == "selected":
            if self.selected_option_id is None or self.decisive_rollout_id is None:
                raise ValueError("Selected policy requires one option and rollout")
            if self.tied_option_ids:
                raise ValueError("Selected policy cannot record a tie")
            by_option = {item.option_id: item for item in self.option_scores}
            selected = by_option.get(self.selected_option_id)
            if selected is None or selected.rollout_id != self.decisive_rollout_id:
                raise ValueError("Selected policy option must cite its scored rollout")
        elif self.status == "abstained_tie":
            if self.selected_option_id is not None or self.decisive_rollout_id is not None:
                raise ValueError("Tie abstention cannot select an option or rollout")
            if len(self.tied_option_ids) < 2:
                raise ValueError("Tie abstention must identify at least two options")
            if self.tied_option_ids != tuple(sorted(set(self.tied_option_ids))):
                raise ValueError("Tied option IDs must use canonical order")
            if not set(self.tied_option_ids).issubset(option_ids):
                raise ValueError("Tied options must belong to the scored option set")
        else:
            if self.option_scores:
                raise ValueError("No-option abstention cannot publish option scores")
            if (
                self.selected_option_id is not None
                or self.decisive_rollout_id is not None
                or self.tied_option_ids
            ):
                raise ValueError("No-option abstention cannot cite an option or rollout")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"policy_decision_id", "policy_hash"},
        )
        if self.policy_decision_id != content_id("instinkt_policy", id_payload):
            raise ValueError("policy_decision_id does not match policy content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"policy_hash"}))
        if self.policy_hash != expected_hash:
            raise ValueError("policy_hash does not match policy content")
        return self


def protective_cost(
    rollout: InstinktOptionRollout,
    config: InstinktSimulationConfig,
) -> float:
    final_state = rollout.trajectory[-1]
    return (
        rollout.predicted_loss
        + config.policy_recoverability_penalty * (1.0 - rollout.recoverability)
        + config.policy_tension_penalty * final_state.tension
        + config.policy_uncertainty_penalty * final_state.uncertainty
    )


def resolve_protective_policy(
    *,
    packet: InstinktInputPacket,
    source_body_state: BodyState,
    effects: tuple[OptionBodyEffect, ...],
    rollouts: tuple[InstinktOptionRollout, ...],
    config: InstinktSimulationConfig,
) -> ProtectivePolicyDecision:
    if packet.source_body_state_id != source_body_state.body_state_id:
        raise ValueError("Protective policy packet belongs to another BodyState")
    effect_by_option = {effect.option_id: effect for effect in effects}
    if len(effect_by_option) != len(effects):
        raise ValueError("Protective policy requires one typed effect per option")
    if set(effect_by_option) != set(packet.option_ids):
        raise ValueError("Protective policy effects must cover every packet option")
    rollout_by_option = {rollout.option_id: rollout for rollout in rollouts}
    if len(rollout_by_option) != len(rollouts):
        raise ValueError("Protective policy requires one rollout per option")
    if set(rollout_by_option) != set(packet.option_ids):
        raise ValueError("Protective policy must score every packet option exactly once")
    for option_id, rollout in rollout_by_option.items():
        rollout.validate_simulation_lineage(
            packet=packet,
            source_body_state=source_body_state,
            effect=effect_by_option[option_id],
            config=config,
            association_matches=rollout.association_matches,
        )
    scores = tuple(
        ProtectiveOptionScore(
            option_id=option_id,
            rollout_id=rollout_by_option[option_id].rollout_id,
            rollout_hash=rollout_by_option[option_id].rollout_hash,
            protective_cost=protective_cost(rollout_by_option[option_id], config),
        )
        for option_id in sorted(rollout_by_option)
    )
    if scores:
        minimum = min(item.protective_cost for item in scores)
        tied = tuple(
            item.option_id
            for item in scores
            if abs(item.protective_cost - minimum) <= config.tie_epsilon
        )
    else:
        tied = ()
    selected_option_id = tied[0] if len(tied) == 1 else None
    decisive_rollout_id = (
        rollout_by_option[selected_option_id].rollout_id
        if selected_option_id is not None
        else None
    )
    base = {
        "schema_version": "rei-native-protective-policy-v1",
        "source_packet_id": packet.packet_id,
        "source_packet_hash": packet.content_hash(),
        "source_body_state_id": source_body_state.body_state_id,
        "source_body_state_hash": source_body_state.content_hash(),
        "source_config_id": config.config_id,
        "source_config_hash": config.config_hash,
        "status": (
            "selected"
            if selected_option_id is not None
            else "abstained_tie"
            if tied
            else "abstained_no_options"
        ),
        "selected_option_id": selected_option_id,
        "decisive_rollout_id": decisive_rollout_id,
        "tied_option_ids": () if selected_option_id is not None else tied,
        "option_scores": scores,
    }
    policy_decision_id = content_id("instinkt_policy", base)
    payload = {"policy_decision_id": policy_decision_id, **base}
    return ProtectivePolicyDecision(**payload, policy_hash=sha256_hex(payload))


def build_native_conclusion(
    *,
    packet: InstinktInputPacket,
    source_body_state: BodyState,
    effects: tuple[OptionBodyEffect, ...],
    rollouts: tuple[InstinktOptionRollout, ...],
    policy: ProtectivePolicyDecision,
    config: InstinktSimulationConfig,
) -> InstinktNativeConclusion:
    expected_policy = resolve_protective_policy(
        packet=packet,
        source_body_state=source_body_state,
        effects=effects,
        rollouts=rollouts,
        config=config,
    )
    if policy != expected_policy:
        raise ValueError("Protective policy differs from the supplied B8 inputs")
    effect_by_option = {effect.option_id: effect for effect in effects}
    rollout_by_option = {rollout.option_id: rollout for rollout in rollouts}
    if policy.status == "abstained_no_options":
        base = {
            "schema_version": "rei-native-instinkt-conclusion-v1",
            "source_packet_id": packet.packet_id,
            "source_scene_id": packet.scene_id,
            "source_body_state_id": source_body_state.body_state_id,
            "mind": "I",
            "option_id": None,
            "dominant_alarm": "no_explicit_options",
            "danger_claims": (),
            "protected_targets": (),
            "action_tendency": "unknown",
            "minimum_safety_condition": "an explicit option is required for rollout",
            "decisive_rollout_id": None,
            "decisive_rollout_option_id": None,
            "intensity": 0.0,
            "abstains": True,
            "uncertainty": "no explicit decision options were supplied",
        }
    elif policy.selected_option_id is None:
        tied_rollouts = tuple(rollout_by_option[item] for item in policy.tied_option_ids)
        intensity = max(
            (
                _rollout_intensity(rollout, config)
                for rollout in tied_rollouts
            ),
            default=0.0,
        )
        base = {
            "schema_version": "rei-native-instinkt-conclusion-v1",
            "source_packet_id": packet.packet_id,
            "source_scene_id": packet.scene_id,
            "source_body_state_id": source_body_state.body_state_id,
            "mind": "I",
            "option_id": None,
            "dominant_alarm": "unresolved_equal_protective_cost",
            "danger_claims": tuple(
                f"{rollout.option_id}:predicted_loss={rollout.predicted_loss:.12g}"
                for rollout in tied_rollouts
            ),
            "protected_targets": tuple(
                dict.fromkeys(
                    target
                    for rollout in tied_rollouts
                    for target in rollout.protected_targets
                )
            ),
            "action_tendency": "unknown",
            "minimum_safety_condition": "additional differentiating evidence required",
            "decisive_rollout_id": None,
            "decisive_rollout_option_id": None,
            "intensity": intensity,
            "abstains": True,
            "uncertainty": "protective cost tie within configured epsilon",
        }
    else:
        option_id = policy.selected_option_id
        rollout = rollout_by_option[option_id]
        effect = effect_by_option[option_id]
        base = {
            "schema_version": "rei-native-instinkt-conclusion-v1",
            "source_packet_id": packet.packet_id,
            "source_scene_id": packet.scene_id,
            "source_body_state_id": source_body_state.body_state_id,
            "mind": "I",
            "option_id": option_id,
            "dominant_alarm": rollout.dominant_alarm,
            "danger_claims": (
                f"predicted_loss={rollout.predicted_loss:.12g}",
                f"recoverability={rollout.recoverability:.12g}",
            ),
            "protected_targets": rollout.protected_targets,
            "action_tendency": effect.action_tendency,
            "minimum_safety_condition": effect.minimum_safety_condition,
            "decisive_rollout_id": rollout.rollout_id,
            "decisive_rollout_option_id": option_id,
            "intensity": _rollout_intensity(rollout, config),
            "abstains": False,
            "uncertainty": "deterministic protective policy implementation hypothesis",
        }
    conclusion = InstinktNativeConclusion(
        conclusion_id=content_id(
            "instinkt_conclusion",
            {
                **base,
                "policy_decision_id": policy.policy_decision_id,
                "policy_hash": policy.policy_hash,
            },
        ),
        **base,
    )
    conclusion.validate_against(packet, source_body_state, rollouts)
    return conclusion


def _rollout_intensity(
    rollout: InstinktOptionRollout,
    config: InstinktSimulationConfig,
) -> float:
    final_state = rollout.trajectory[-1]
    return clamp01(
        config.intensity_loss_weight * rollout.predicted_loss
        + config.intensity_tension_weight * final_state.tension
        + config.intensity_arousal_weight * final_state.arousal
    )


__all__ = [
    "ProtectiveOptionScore",
    "ProtectivePolicyDecision",
    "build_native_conclusion",
    "protective_cost",
    "resolve_protective_policy",
]
