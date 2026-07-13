"""Presentation-only projection of a completed native REI cycle.

This module never executes a processor.  It converts the immutable B11 result
into four explicit GUI panels and keeps evaluator-only native communication
truth out of the normal communication response.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.backend.rei_next.engine import ReiNativeCycleResult


WORKBENCH_SCHEMA_VERSION = "rei-native-workbench-v1"
COMMUNICATION_WARNING = (
    "Racio receives only observable manifestations. Native Emocio/Instinkt "
    "meaning and evaluator comparisons are not interpreter inputs."
)
DEBUG_GROUND_TRUTH_LABEL = "DEBUG / EVALUATOR GROUND TRUTH"
DEBUG_GROUND_TRUTH_WARNING = (
    "Evaluator-only native truth is visible for diagnosis. Racio did not see "
    "these values during interpretation or conscious commitment."
)
IMAGE_NOT_RENDERED_MESSAGE = (
    "No rendered image artifact — the structured scene remains authoritative."
)


def _dump(value: Any) -> Any:
    """Return a JSON-compatible dump of one strict REI artifact."""

    if value is None:
        return None
    model_dump = getattr(value, "model_dump", None)
    if model_dump is None:
        raise TypeError(f"Expected a REI model, got {type(value).__name__}")
    return model_dump(mode="json")


def _safe_translation_gap(gap: Any) -> dict[str, Any]:
    """Expose diagnostic scores without native evaluator values."""

    return {
        "translation_gap_id": gap.translation_gap_id,
        "gap_status": gap.gap_status,
        "source_mind": gap.source_mind,
        "interpretation_id": gap.interpretation_id,
        "interpretation_status": gap.interpretation_status,
        "interpreted_option_id": gap.interpreted_option_id,
        "interpreted_action_tendency": gap.interpreted_action_tendency,
        "interpreted_motive": gap.interpreted_motive,
        "option_match": gap.option_match,
        "option_comparison_applicable": gap.option_comparison_applicable,
        "motive_fidelity": gap.motive_fidelity,
        "distortion_type": gap.distortion_type,
        "metric_policy": gap.metric_policy,
        "metric_basis": gap.metric_basis,
        "distortion_policy": gap.distortion_policy,
        "translation_gap_hash": gap.translation_gap_hash,
    }


def _evaluator_ground_truth(gap: Any) -> dict[str, Any]:
    """Return the native side of a translation comparison for debug only."""

    return {
        "source_mind": gap.source_mind,
        "source_conclusion_id": gap.source_conclusion_id,
        "source_conclusion_hash": gap.source_conclusion_hash,
        "native_option_id": gap.native_option_id,
        "native_action_tendency": gap.native_action_tendency,
        "native_motive_summary": gap.native_motive_summary,
        "fidelity_components": [_dump(item) for item in gap.fidelity_components],
    }


def _image_slots(result: ReiNativeCycleResult) -> list[dict[str, Any]]:
    visual_state = result.emocio_execution.visual_state
    scenes = (
        visual_state.current_scene,
        visual_state.desired_scene,
        visual_state.broken_scene,
        *visual_state.option_rollouts,
    )
    images_by_scene: dict[str, list[Any]] = {}
    for image in result.emocio_execution.rendered_images:
        images_by_scene.setdefault(image.source_spec_id, []).append(image)

    inventory_by_path = {
        item.relative_path: item for item in result.manifest.artifact_inventory
    }
    slots: list[dict[str, Any]] = []
    for scene in scenes:
        images = images_by_scene.get(scene.scene_id, [])
        if len(images) > 1:
            raise ValueError("A GUI image slot may reference at most one image artifact")
        slot: dict[str, Any] = {
            "scene_id": scene.scene_id,
            "scene_kind": scene.scene_kind,
            "option_id": scene.option_id,
            "scene": _dump(scene),
        }
        if not images:
            slot.update(
                {
                    "status": "not_rendered",
                    "message": IMAGE_NOT_RENDERED_MESSAGE,
                }
            )
            slots.append(slot)
            continue

        artifact = images[0]
        inventory_record = inventory_by_path.get(artifact.path)
        slot["artifact"] = _dump(artifact)
        if inventory_record is None:
            slot.update(
                {
                    "status": "artifact_unavailable",
                    "message": (
                        "Image metadata exists, but its bytes are not in the verified "
                        "run manifest inventory."
                    ),
                }
            )
        else:
            if inventory_record.content_sha256 != artifact.content_sha256:
                raise ValueError(
                    "Image metadata hash differs from the run manifest inventory"
                )
            encoded_run_id = quote(result.request.run_id, safe="")
            encoded_image_id = quote(artifact.image_id, safe="")
            slot.update(
                {
                    "status": "available",
                    "message": "Verified rendered image artifact.",
                    "url": (
                        f"/api/runs/{encoded_run_id}/images/{encoded_image_id}"
                    ),
                }
            )
        slots.append(slot)
    return slots


def _body_after(result: ReiNativeCycleResult) -> Any:
    decisive_rollout_id = result.instinkt_execution.conclusion.decisive_rollout_id
    if decisive_rollout_id is None:
        return None
    decisive = tuple(
        rollout
        for rollout in result.instinkt_execution.rollouts
        if rollout.rollout_id == decisive_rollout_id
    )
    if len(decisive) != 1:
        raise ValueError("Instinkt decisive rollout must resolve to one trajectory")
    return _dump(decisive[0].trajectory[-1])


def _processor_availability(result: ReiNativeCycleResult) -> dict[str, Any]:
    override = result.effective_authority.functional_override
    if override is None:
        return {
            "explicit": False,
            "status": "all_processors_retained_no_functional_override",
            "unavailable_minds": [],
            "scores": None,
            "evidence_ids": [],
        }
    return {
        "explicit": True,
        "status": "explicit_functional_unavailability",
        "unavailable_minds": list(override.unavailable_minds),
        "scores": _dump(override.processor_availability),
        "evidence_ids": list(override.evidence_ids),
        "note": override.note,
    }


def _ego_timeline(result: ReiNativeCycleResult) -> list[dict[str, Any]]:
    payload_by_key = {
        **{
            ("measure", item.measure_id): _dump(item)
            for item in result.ego_trace.measures
        },
        **{
            ("correction", item.correction_id): _dump(item)
            for item in result.ego_trace.corrections
        },
    }
    timeline: list[dict[str, Any]] = []
    for event in result.ego_trace.event_order:
        key = (event.event_kind, event.event_id)
        if key not in payload_by_key:
            raise ValueError("EgoTrace event order references an absent event")
        timeline.append(
            {
                **_dump(event),
                "event": payload_by_key[key],
            }
        )
    return timeline


def build_workbench_view(
    result: ReiNativeCycleResult,
    *,
    debug: bool = False,
) -> dict[str, Any]:
    """Build the stable B12 response envelope for one completed cycle."""

    emocio_gap = result.emocio_communication.translation_gap
    instinkt_gap = result.instinkt_communication.translation_gap
    communication: dict[str, Any] = {
        "manifestations": {
            "emocio": _dump(result.emocio_manifestation),
            "instinkt": _dump(result.instinkt_manifestation),
        },
        "interpretations": {
            "emocio": _dump(result.emocio_communication.interpretation),
            "instinkt": _dump(result.instinkt_communication.interpretation),
        },
        "translation_gaps": {
            "emocio": _safe_translation_gap(emocio_gap),
            "instinkt": _safe_translation_gap(instinkt_gap),
        },
        "ground_truth_visible": debug,
        "warning": (
            DEBUG_GROUND_TRUTH_WARNING if debug else COMMUNICATION_WARNING
        ),
    }
    if debug:
        communication["evaluator_ground_truth"] = {
            "label": DEBUG_GROUND_TRUTH_LABEL,
            "warning": DEBUG_GROUND_TRUTH_WARNING,
            "emocio": _evaluator_ground_truth(emocio_gap),
            "instinkt": _evaluator_ground_truth(instinkt_gap),
        }

    character = result.request.character
    agreement = result.governance.agreement_pattern
    thirteenth_majority = {
        "applicable": character.profile_id == "R=E=I",
        "profile_rule": character.rule,
        "agreement_kind": agreement.agreement_kind,
        "winning_option_id": agreement.winning_option_id,
        "agreeing_minds": list(agreement.agreeing_minds),
        "spoznanje_status": agreement.spoznanje_status,
    }

    manifest_hash = result.manifest.manifest_hash or result.manifest.content_hash()
    return {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "run": {
            "run_id": result.request.run_id,
            "ego_id": result.request.ego_id,
            "scene_id": result.request.scene.event_id,
            "profile_id": character.profile_id,
            "mode": result.request.mode,
            "manifest_hash": manifest_hash,
            "all_invariants_passed": result.invariants.all_passed,
        },
        "panels": {
            "native": {
                "racio": _dump(result.native_bundle.racio),
                "emocio": {
                    "conclusion": _dump(result.native_bundle.emocio),
                    "visual_state": _dump(result.emocio_execution.visual_state),
                    "image_slots": _image_slots(result),
                },
                "instinkt": {
                    "conclusion": _dump(result.native_bundle.instinkt),
                    "body_before": _dump(result.request.body_state),
                    "rollouts": [
                        _dump(item) for item in result.instinkt_execution.rollouts
                    ],
                    "body_after": _body_after(result),
                },
            },
            "communication": communication,
            "character": {
                "structural_profile": _dump(character),
                "authority_tiers": [list(tier) for tier in character.authority_tiers],
                "processor_availability": _processor_availability(result),
                "effective_authority": _dump(result.effective_authority),
                "governance_mandate": _dump(result.governance.mandate),
                "pair_conflict": _dump(result.governance.pair_conflict),
                "thirteenth_majority": thirteenth_majority,
                "delegation": _dump(result.governance.mandate.delegation),
                "conscious_decision": _dump(result.conscious_decision),
                "behavior_resultant": _dump(result.behavior_resultant),
            },
            "ego": {
                "measure": _dump(result.ego_measure),
                "timeline": _ego_timeline(result),
                "composition_snapshot": _dump(result.composition_snapshot),
                "self_narrative": _dump(result.narrative),
                "projections": {
                    "racio": _dump(result.projections.racio),
                    "emocio": _dump(result.projections.emocio),
                    "instinkt": _dump(result.projections.instinkt),
                },
            },
        },
        "diagnostics": {
            "invariants": _dump(result.invariants),
        },
    }


__all__ = [
    "COMMUNICATION_WARNING",
    "DEBUG_GROUND_TRUTH_LABEL",
    "DEBUG_GROUND_TRUTH_WARNING",
    "IMAGE_NOT_RENDERED_MESSAGE",
    "WORKBENCH_SCHEMA_VERSION",
    "build_workbench_view",
]
