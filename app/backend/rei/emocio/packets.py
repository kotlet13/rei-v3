"""Profile-blind construction of Emocio's grounded visual packet."""

from __future__ import annotations

from ..ids import content_id
from ..models.emocio import EmocioInputPacket
from ..models.scene import SceneEvent


_VISUAL_MODALITIES = frozenset({"image", "video"})
_MOVEMENT_MODALITIES = frozenset({"video", "body"})


def _canonical_strings(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def build_emocio_packet(
    scene: SceneEvent,
    *,
    previous_emocio_projection_ids: tuple[str, ...] = (),
    previous_emocio_projection_hashes: tuple[str, ...] = (),
) -> EmocioInputPacket:
    """Route only supplied structure; never infer an Emocio preference.

    Text is not classified for visual or emotional keywords.  Visual and
    movement cues are admitted solely by the explicit evidence modality.  The
    event's actors provide identity scope, while option and evidence IDs remain
    complete and canonical.
    """

    grounded = tuple(item for item in scene.evidence if item.grounded)
    routed_grounded = tuple(
        item
        for item in grounded
        if item.modality in (_VISUAL_MODALITIES | _MOVEMENT_MODALITIES)
    )
    visual_cues = _canonical_strings(
        [item.content for item in grounded if item.modality in _VISUAL_MODALITIES]
    )
    movement_cues = _canonical_strings(
        [item.content for item in grounded if item.modality in _MOVEMENT_MODALITIES]
    )
    actors = _canonical_strings(list(scene.actors))
    evidence_ids = tuple(sorted(item.evidence_id for item in routed_grounded))
    option_ids = tuple(sorted(option.option_id for option in scene.options))
    if len(previous_emocio_projection_ids) != len(
        previous_emocio_projection_hashes
    ):
        raise ValueError("Emocio projection IDs and hashes must have equal length")
    base = {
        "schema_version": "rei-native-emocio-input-packet-v1",
        "scene_id": scene.event_id,
        "source_scene_hash": scene.scene_hash(),
        "grounded_visual_cues": visual_cues,
        "social_layout": actors,
        "actor_positions": (),
        "observed_attention": (),
        "movement_cues": movement_cues,
        "aesthetic_cues": visual_cues,
        "explicit_identity_cues": actors,
        "allowed_option_ids": option_ids,
        "evidence_ids": evidence_ids,
        "caveat": (
            "Profilno slep strukturiran paket. Vsebina besedila ni semanti\u010dno "
            "klasificirana in paket ne vsebuje Emocieve izbire."
        ),
    }
    if previous_emocio_projection_ids:
        base["previous_emocio_projection_ids"] = previous_emocio_projection_ids
        base["previous_emocio_projection_hashes"] = (
            previous_emocio_projection_hashes
        )
    packet = EmocioInputPacket(
        packet_id=content_id("emocio_packet", base),
        **base,
    )
    packet.validate_against(scene)
    return packet


__all__ = ["build_emocio_packet"]
