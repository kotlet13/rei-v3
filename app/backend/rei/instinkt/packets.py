"""Profile-blind B11 packet routing and explicit Instinkt effect binding."""

from __future__ import annotations

from pydantic import model_validator

from ..ids import content_id
from ..models.common import FrozenModel, NonEmptyId, NonEmptyText, Score01
from ..models.instinkt import (
    BodyDelta,
    BodyState,
    InstinktActionTendency,
    InstinktCueEvidenceBinding,
    InstinktInputPacket,
    OptionBodyEffect,
)
from ..models.scene import SceneEvent


INSTINKT_PACKET_CAVEAT = (
    "Profile-blind protective packet containing only explicitly routed typed cues; "
    "no prose classification, character profile, or preferred option is inferred."
)


class InstinktEffectSpec(FrozenModel):
    """Caller-supplied effect semantics before binding to a packet ID/hash."""

    option_id: NonEmptyId
    body_deltas: tuple[BodyDelta, ...] = ()
    base_predicted_loss: Score01
    base_recoverability: Score01
    dominant_alarm: NonEmptyText
    protected_targets: tuple[NonEmptyText, ...]
    boundary_outcome: str
    trust_outcome: str
    attachment_outcome: str
    escape_outcome: str
    action_tendency: InstinktActionTendency
    minimum_safety_condition: NonEmptyText
    association_cue_tokens: tuple[NonEmptyText, ...] = ()
    triggering_evidence_ids: tuple[NonEmptyId, ...] = ()

    @model_validator(mode="after")
    def validate_spec(self) -> InstinktEffectSpec:
        dimensions = tuple(item.dimension for item in self.body_deltas)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("Instinkt effect dimensions must be unique")
        if len(set(self.triggering_evidence_ids)) != len(
            self.triggering_evidence_ids
        ):
            raise ValueError("Instinkt triggering evidence IDs must be unique")
        return self

    def bind(self, packet: InstinktInputPacket) -> OptionBodyEffect:
        return OptionBodyEffect.create(
            packet=packet,
            option_id=self.option_id,
            body_deltas=self.body_deltas,
            base_predicted_loss=self.base_predicted_loss,
            base_recoverability=self.base_recoverability,
            dominant_alarm=self.dominant_alarm,
            protected_targets=self.protected_targets,
            boundary_outcome=self.boundary_outcome,
            trust_outcome=self.trust_outcome,
            attachment_outcome=self.attachment_outcome,
            escape_outcome=self.escape_outcome,
            action_tendency=self.action_tendency,
            minimum_safety_condition=self.minimum_safety_condition,
            association_cue_tokens=self.association_cue_tokens,
            triggering_evidence_ids=self.triggering_evidence_ids,
        )


def _canonical(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def build_instinkt_packet(
    scene: SceneEvent,
    body_state: BodyState,
    *,
    physical_cues: tuple[str, ...] = (),
    uncertainty_cues: tuple[str, ...] = (),
    trust_cues: tuple[str, ...] = (),
    boundary_cues: tuple[str, ...] = (),
    attachment_cues: tuple[str, ...] = (),
    scarcity_cues: tuple[str, ...] = (),
    escape_cues: tuple[str, ...] = (),
    explicit_body_cues: tuple[str, ...] = (),
    evidence_ids: tuple[NonEmptyId, ...] = (),
    cue_evidence_bindings: tuple[InstinktCueEvidenceBinding, ...] = (),
    previous_instinkt_projection_ids: tuple[NonEmptyId, ...] = (),
    previous_instinkt_projection_hashes: tuple[str, ...] = (),
    caveat: str = INSTINKT_PACKET_CAVEAT,
) -> InstinktInputPacket:
    """Route explicit structured cues without deriving them from prose."""

    if len(previous_instinkt_projection_ids) != len(
        previous_instinkt_projection_hashes
    ):
        raise ValueError("Instinkt projection IDs and hashes must have equal length")
    canonical_bindings = tuple(
        sorted(cue_evidence_bindings, key=lambda item: item.binding_id)
    )
    base = {
        "schema_version": "rei-native-instinkt-input-packet-v1",
        "scene_id": scene.event_id,
        "source_body_state_id": body_state.body_state_id,
        "physical_cues": _canonical(physical_cues),
        "uncertainty_cues": _canonical(uncertainty_cues),
        "trust_cues": _canonical(trust_cues),
        "boundary_cues": _canonical(boundary_cues),
        "attachment_cues": _canonical(attachment_cues),
        "scarcity_cues": _canonical(scarcity_cues),
        "escape_cues": _canonical(escape_cues),
        "explicit_body_cues": _canonical(explicit_body_cues),
        "option_ids": tuple(sorted(option.option_id for option in scene.options)),
        "evidence_ids": _canonical(evidence_ids),
        "caveat": caveat,
    }
    if canonical_bindings:
        base["cue_evidence_bindings"] = canonical_bindings
    if previous_instinkt_projection_ids:
        base["previous_instinkt_projection_ids"] = (
            previous_instinkt_projection_ids
        )
        base["previous_instinkt_projection_hashes"] = (
            previous_instinkt_projection_hashes
        )
    packet = InstinktInputPacket(
        packet_id=content_id(
            "instinkt_packet",
            {
                "source_scene_hash": scene.scene_hash(),
                "source_body_state_hash": body_state.content_hash(),
                **base,
            },
        ),
        **base,
    )
    return packet.validate_against(scene, body_state)


def bind_instinkt_effects(
    packet: InstinktInputPacket,
    specs: tuple[InstinktEffectSpec, ...],
) -> tuple[OptionBodyEffect, ...]:
    """Bind exactly one explicit typed effect to every packet option."""

    by_option = {spec.option_id: spec for spec in specs}
    if len(by_option) != len(specs):
        raise ValueError("Instinkt effect specs must be unique by option")
    if set(by_option) != set(packet.option_ids):
        raise ValueError("Instinkt effect specs must cover every packet option exactly")
    packet_evidence = set(packet.evidence_ids)
    for spec in specs:
        if not set(spec.triggering_evidence_ids).issubset(packet_evidence):
            raise ValueError("Instinkt effect cites evidence outside its packet")
    return tuple(by_option[option_id].bind(packet) for option_id in packet.option_ids)


__all__ = [
    "INSTINKT_PACKET_CAVEAT",
    "InstinktEffectSpec",
    "bind_instinkt_effects",
    "build_instinkt_packet",
]
