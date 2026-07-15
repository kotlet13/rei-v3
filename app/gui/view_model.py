"""Presentation-only projection of a completed native REI cycle.

This module never executes a processor.  It converts the immutable B11 result
into explicit C8 modality and longitudinal panels while keeping evaluator-only
native communication truth out of the normal Racio response.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.backend.rei.engine import ReiNativeCycleResult

from .storage import ego_partition_id


WORKBENCH_SCHEMA_VERSION = "rei-semantic-native-workbench-v2"
RACIO_GROUND_TRUTH_WARNING_SL = "Racio ground trutha ni prejel."
COMMUNICATION_WARNING = (
    f"{RACIO_GROUND_TRUTH_WARNING_SL} Racio receives only observable "
    "manifestations; native Emocio/Instinkt meaning and evaluator comparisons "
    "are not interpreter inputs."
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


def _safe_translation_gap(gap: Any) -> dict[str, Any]:
    """Expose the existence/class of an Ego error without native comparison truth."""

    return {
        "translation_gap_id": gap.translation_gap_id,
        "source_mind": gap.source_mind,
        "interpretation_id": gap.interpretation_id,
        "gap_status": gap.gap_status,
        "distortion_type": gap.distortion_type,
        "evaluator_detail_visible": False,
        "detail": (
            "Native option, motive, action tendency, hashes, and fidelity components "
            "are available only through the local evaluator-debug switch."
        ),
    }


def _ego_measure_view(measure: Any, *, debug: bool) -> dict[str, Any]:
    payload = _dump(measure)
    if not debug:
        payload["translation_gaps"] = [
            _safe_translation_gap(gap) for gap in measure.translation_gaps
        ]
    return payload


def _safe_translation_error_text(value: Any) -> str:
    text = str(value)
    parts = text.split(":")
    if len(parts) >= 3 and parts[0] == "translation_gap":
        return ":".join(parts[:3])
    return "translation_gap:detail_withheld"


def _composition_snapshot_view(result: ReiNativeCycleResult, *, debug: bool) -> Any:
    payload = _dump(result.composition_snapshot)
    if debug:
        return payload
    payload["recurring_translation_errors"] = [
        _safe_translation_error_text(item)
        for item in payload.get("recurring_translation_errors", [])
    ]
    payload["sourced_claims"] = [
        (
            {
                **claim,
                "text": _safe_translation_error_text(claim.get("text")),
                "evaluator_detail_visible": False,
            }
            if claim.get("kind") == "recurring_translation_error"
            else claim
        )
        for claim in payload.get("sourced_claims", [])
    ]
    payload["translation_error_detail_visible"] = False
    return payload


def _self_narrative_view(result: ReiNativeCycleResult, *, debug: bool) -> Any:
    payload = _dump(result.narrative)
    if debug:
        return payload
    for field_name in ("recurrent_translation_gaps", "recurring_translation_errors"):
        if field_name in payload:
            payload[field_name] = [
                _safe_translation_error_text(item)
                for item in payload[field_name]
            ]
    if "translation_gaps" in payload:
        payload["translation_gaps"] = [
            _safe_translation_gap(item) for item in result.ego_measure.translation_gaps
        ]
    return payload


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
            encoded_partition_id = quote(
                ego_partition_id(result.request.ego_id), safe=""
            )
            encoded_run_id = quote(result.request.run_id, safe="")
            encoded_image_id = quote(artifact.image_id, safe="")
            slot.update(
                {
                    "status": "available",
                    "message": "Verified rendered image artifact.",
                    "url": (
                        f"/api/ego-runs/{encoded_partition_id}/{encoded_run_id}"
                        f"/images/{encoded_image_id}"
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


def _decisive_instinkt_rollout(result: ReiNativeCycleResult) -> Any:
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
    return decisive[0]


def _visual_observation_summary(observation: Any) -> dict[str, Any]:
    """Expose embedding lineage and identity without shipping the raw vector."""

    return {
        "observation_id": observation.observation_id,
        "role": observation.role,
        "evaluation_seed": observation.evaluation_seed,
        "scene_spec_id": observation.scene_spec.scene_id,
        "image": _dump(observation.image),
        "imagined": _dump(observation.imagined),
        "encoding_id": observation.encoding.encoding_id,
        "embedding": _dump(observation.embedding),
        "internal_only": observation.internal_only,
        "external_evidence_claim": observation.external_evidence_claim,
    }


def _racio_panel(
    result: ReiNativeCycleResult,
    *,
    debug: bool,
) -> dict[str, Any]:
    emocio_gap = result.emocio_communication.translation_gap
    instinkt_gap = result.instinkt_communication.translation_gap
    panel: dict[str, Any] = {
        "native_conclusion": _dump(result.native_bundle.racio),
        "visible_inputs": {
            "emocio": _dump(result.emocio_communication.request),
            "instinkt": _dump(result.instinkt_communication.request),
        },
        "manifestations": {
            "emocio": _dump(result.emocio_manifestation),
            "instinkt": _dump(result.instinkt_manifestation),
        },
        "interpretations": {
            "emocio": _dump(result.emocio_communication.interpretation),
            "instinkt": _dump(result.instinkt_communication.interpretation),
        },
        "ground_truth_visible": debug,
        "warning": (
            f"{RACIO_GROUND_TRUTH_WARNING_SL} {DEBUG_GROUND_TRUTH_WARNING}"
            if debug
            else COMMUNICATION_WARNING
        ),
    }
    if debug:
        panel["translation_gaps"] = {
            "emocio": _dump(emocio_gap),
            "instinkt": _dump(instinkt_gap),
        }
        panel["evaluator_labels"] = {
            "emocio": emocio_gap.gap_status,
            "instinkt": instinkt_gap.gap_status,
        }
        panel["evaluator_ground_truth"] = {
            "label": DEBUG_GROUND_TRUTH_LABEL,
            "warning": (
                f"{RACIO_GROUND_TRUTH_WARNING_SL} {DEBUG_GROUND_TRUTH_WARNING}"
            ),
            "emocio": _evaluator_ground_truth(emocio_gap),
            "instinkt": _evaluator_ground_truth(instinkt_gap),
        }
    return panel


def _emocio_panel(result: ReiNativeCycleResult) -> dict[str, Any]:
    execution = result.emocio_execution
    processing = execution.processing
    state = execution.visual_state
    scenes = (
        state.current_scene,
        state.desired_scene,
        state.broken_scene,
        *state.option_rollouts,
    )
    renderer_added = tuple(
        {
            "image_id": image.image_id,
            "source_spec_id": image.source_spec_id,
            "elements": list(image.generated_only_elements),
        }
        for image in execution.rendered_images
        if image.generated_only_elements
    )
    cognition_trace = getattr(processing, "cognition_trace", None)
    visual_observations = tuple(
        getattr(processing, "visual_observations", ())
    )
    visual_valuation = getattr(processing, "visual_valuation", None)
    return {
        "conclusion": _dump(result.native_bundle.emocio),
        "structured_conclusion": _dump(
            getattr(processing, "structured_native_conclusion", execution.conclusion)
        ),
        "cognition_trace": _dump(cognition_trace),
        "native_option_id": result.native_bundle.emocio.option_id,
        "visual_state": _dump(state),
        "scene_specs": [_dump(scene) for scene in scenes],
        "image_slots": _image_slots(result),
        "generated_images": [_dump(image) for image in execution.rendered_images],
        "visual_observations": [
            _visual_observation_summary(item)
            for item in visual_observations
        ],
        "structured_valuations": [
            _dump(item) for item in state.option_valuations
        ],
        "visual_valuation": _dump(visual_valuation),
        "renderer_added_ungrounded_elements": list(renderer_added),
        "visual_status": {
            "requested_mode": (
                None if cognition_trace is None else cognition_trace.requested_mode
            ),
            "effective_mode": (
                None if cognition_trace is None else cognition_trace.effective_mode
            ),
            "embedding_status": (
                "available"
                if visual_observations
                else "not_executed_in_this_cycle"
            ),
            "similarity_status": (
                "available"
                if visual_valuation is not None
                else "not_executed_in_this_cycle"
            ),
            "renderer_warning": execution.renderer_warning,
            "visual_warning": getattr(processing, "visual_warning", None),
        },
    }


def _instinkt_panel(result: ReiNativeCycleResult) -> dict[str, Any]:
    execution = result.instinkt_execution
    processing = execution.processing
    decisive = _decisive_instinkt_rollout(result)
    prediction_uncertainty = tuple(
        {
            "option_id": prediction.option_id,
            "abstains": prediction.abstains,
            "uncertainty": prediction.uncertainty,
            "conflict_flags": list(prediction.conflict_flags),
        }
        for prediction in result.instinkt_effect_predictions
    )
    policy = processing.policy
    return {
        "conclusion": _dump(result.native_bundle.instinkt),
        "body_before": _dump(result.request.body_state),
        "cue_evidence": [
            _dump(item) for item in result.instinkt_packet.cue_evidence_bindings
        ],
        "predicted_body_effects": [
            _dump(item) for item in result.instinkt_effect_predictions
        ],
        "manual_option_effects": (
            [_dump(item) for item in execution.option_effects]
            if result.instinkt_effect_source == "manual_fixture"
            else []
        ),
        "effect_compilations": [
            _dump(item) for item in result.instinkt_effect_compilations
        ],
        "effect_status": {
            "source": result.instinkt_effect_source,
            "prediction_status": (
                "available"
                if result.instinkt_effect_predictions
                else "not_executed_manual_fixture"
            ),
        },
        "association_matches": [
            _dump(item) for item in processing.association_matches
        ],
        "rollouts": [_dump(item) for item in execution.rollouts],
        "body_after": _body_after(result),
        "dominant_alarm": None if decisive is None else decisive.dominant_alarm,
        "policy": _dump(policy),
        "abstention": {
            "status": policy.status,
            "abstained": policy.status != "selected",
            "tied_option_ids": list(policy.tied_option_ids),
            "uncertainty_by_option": list(prediction_uncertainty),
        },
    }


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


def _ego_timeline(
    result: ReiNativeCycleResult,
    *,
    debug: bool,
) -> list[dict[str, Any]]:
    payload_by_key = {
        **{
            ("measure", item.measure_id): _ego_measure_view(item, debug=debug)
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
    """Build the stable workbench response envelope for one completed cycle."""

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
            "racio": _racio_panel(result, debug=debug),
            "emocio": _emocio_panel(result),
            "instinkt": _instinkt_panel(result),
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
                "measure": _ego_measure_view(result.ego_measure, debug=debug),
                "timeline": _ego_timeline(result, debug=debug),
                "composition_snapshot": _composition_snapshot_view(
                    result,
                    debug=debug,
                ),
                "self_narrative": _self_narrative_view(result, debug=debug),
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
    "RACIO_GROUND_TRUTH_WARNING_SL",
    "WORKBENCH_SCHEMA_VERSION",
    "build_workbench_view",
]
