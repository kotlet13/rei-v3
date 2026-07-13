"""Deterministic consciously observable projection of Instinkt state."""

from __future__ import annotations

from .body import clamp01
from ..ids import content_id, sha256_hex
from ..models.communication import InstinktManifestation
from ..models.instinkt import (
    BodyState,
    InstinktNativeConclusion,
    InstinktOptionRollout,
)


def build_instinkt_manifestation(
    *,
    conclusion: InstinktNativeConclusion,
    body_state: BodyState,
    decisive_rollout: InstinktOptionRollout | None = None,
    body_locations: tuple[str, ...] = (),
) -> InstinktManifestation:
    withdrawal_urge = (
        conclusion.intensity
        if conclusion.action_tendency in {"withdraw", "seek_safety"}
        else 0.0
    )
    freeze_intensity = (
        conclusion.intensity if conclusion.action_tendency == "freeze" else 0.0
    )
    if (conclusion.decisive_rollout_id is None) != (decisive_rollout is None):
        raise ValueError("Manifestation decisive rollout differs from its conclusion")
    base: dict[str, object] = {
        "schema_version": "rei-native-instinkt-manifestation-v1",
        "source_conclusion_id": conclusion.conclusion_id,
        "source_conclusion_hash": conclusion.content_hash(),
        "manifestation_status": "simulated_v1",
        "source_body_state_id": body_state.body_state_id,
        "source_body_state_hash": body_state.content_hash(),
        "body_locations": tuple(dict.fromkeys(body_locations)),
        "felt_tension": body_state.tension,
        "fear_intensity": clamp01(
            0.50 * conclusion.intensity
            + 0.30 * body_state.tension
            + 0.20 * body_state.arousal
        ),
        "attachment_pull": clamp01(
            (1.0 - body_state.attachment_security) * conclusion.intensity
        ),
        "withdrawal_urge": withdrawal_urge,
        "freeze_intensity": freeze_intensity,
        "boundary_alarm": clamp01(1.0 - body_state.boundary_integrity),
        "raw_urge": f"structured_tendency:{conclusion.action_tendency}",
    }
    if decisive_rollout is not None:
        if decisive_rollout.rollout_hash is None:
            raise ValueError("Decisive rollout must be a verified simulation artifact")
        base["source_decisive_rollout_id"] = decisive_rollout.rollout_id
        base["source_decisive_rollout_hash"] = decisive_rollout.rollout_hash
    manifestation_id = content_id("instinkt_manifestation", base)
    payload = {"manifestation_id": manifestation_id, **base}
    manifestation = InstinktManifestation(
        **payload,
        manifestation_hash=sha256_hex(payload),
    )
    manifestation.validate_against(conclusion, body_state, decisive_rollout)
    return manifestation


def build_instinkt_fixture_projection(
    *,
    conclusion: InstinktNativeConclusion,
    body_state: BodyState,
    body_locations: tuple[str, ...] = (),
) -> InstinktManifestation:
    """Project a frozen governance-only fixture without inventing B8 rollout lineage."""

    withdrawal_urge = (
        conclusion.intensity
        if conclusion.action_tendency in {"withdraw", "seek_safety"}
        else 0.0
    )
    freeze_intensity = (
        conclusion.intensity if conclusion.action_tendency == "freeze" else 0.0
    )
    base: dict[str, object] = {
        "schema_version": "rei-native-instinkt-manifestation-v1",
        "source_conclusion_id": conclusion.conclusion_id,
        "source_conclusion_hash": conclusion.content_hash(),
        "manifestation_status": "fixture_projection_b11",
        "source_body_state_id": body_state.body_state_id,
        "source_body_state_hash": body_state.content_hash(),
        "body_locations": tuple(dict.fromkeys(body_locations)),
        "felt_tension": body_state.tension,
        "fear_intensity": clamp01(
            0.50 * conclusion.intensity
            + 0.30 * body_state.tension
            + 0.20 * body_state.arousal
        ),
        "attachment_pull": clamp01(
            (1.0 - body_state.attachment_security) * conclusion.intensity
        ),
        "withdrawal_urge": withdrawal_urge,
        "freeze_intensity": freeze_intensity,
        "boundary_alarm": clamp01(1.0 - body_state.boundary_integrity),
        "raw_urge": f"structured_tendency:{conclusion.action_tendency}",
    }
    manifestation_id = content_id("instinkt_manifestation", base)
    payload = {"manifestation_id": manifestation_id, **base}
    manifestation = InstinktManifestation(
        **payload,
        manifestation_hash=sha256_hex(payload),
    )
    return manifestation.validate_against(conclusion, body_state)


__all__ = ["build_instinkt_fixture_projection", "build_instinkt_manifestation"]
