"""Deterministic, profile-blind construction of Racio native input packets."""

from __future__ import annotations

from collections.abc import Iterable

from ..ids import content_id
from ..models.racio import (
    NumericCue,
    RacioConsequence,
    RacioInputPacket,
    RacioWorld,
)
from ..models.scene import SceneEvent


RACIO_PACKET_CAVEAT = (
    "Profile-blind verbal-analytical packet for the conceptual REI simulator; "
    "it contains no character authority or hidden Emocio/Instinkt motive."
)


def _as_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(values)


def build_racio_packet(
    scene: SceneEvent,
    world: RacioWorld,
    *,
    symbolic_and_language_cues: Iterable[str] | None = None,
    numeric_cues: Iterable[NumericCue] = (),
    time: Iterable[str] = (),
    rules: Iterable[str] = (),
    explicit_consequences: Iterable[RacioConsequence] = (),
    previous_racio_projection_ids: Iterable[str] = (),
    caveat: str = RACIO_PACKET_CAVEAT,
) -> RacioInputPacket:
    """Build a content-addressed packet without interpreting scene semantics.

    Only supplied, grounded evidence becomes an explicit fact.  Everything else
    is copied into its structurally designated field; this router never guesses
    goals, motives, authority, or a preferred option.
    """

    grounded = tuple(
        evidence
        for evidence in scene.evidence
        if evidence.grounded and evidence.provenance_kind == "supplied"
    )
    cues = (
        (scene.raw_input,) if symbolic_and_language_cues is None and scene.raw_input
        else () if symbolic_and_language_cues is None
        else _as_tuple(symbolic_and_language_cues)
    )
    payload = {
        "schema_version": "rei-native-racio-input-packet-v1",
        "scene_id": scene.event_id,
        "language": scene.language,
        "source_scene_hash": scene.scene_hash(),
        "symbolic_and_language_cues": cues,
        "numeric_cues": tuple(numeric_cues),
        "explicit_facts": tuple(evidence.content for evidence in grounded),
        "explicit_unknowns": scene.unknowns,
        "time": _as_tuple(time),
        "rules": _as_tuple(rules),
        "explicit_options": scene.options,
        "explicit_consequences": tuple(explicit_consequences),
        "constraints": scene.constraints,
        "allowed_option_ids": tuple(option.option_id for option in scene.options),
        "evidence_ids": tuple(evidence.evidence_id for evidence in grounded),
        "world": world,
        "previous_racio_projection_ids": tuple(previous_racio_projection_ids),
        "caveat": caveat,
    }
    packet = RacioInputPacket(
        packet_id=content_id("racio_packet", payload),
        **payload,
    )
    return packet.validate_against(scene)


__all__ = ["RACIO_PACKET_CAVEAT", "build_racio_packet"]
