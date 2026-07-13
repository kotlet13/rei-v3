"""Deterministic builders used only by the B3 governance tests.

The helpers build complete, hash-valid B2 native bundles without invoking a
provider, renderer, model, or processor implementation.  This lets the tests
vary only frozen native conclusions while retaining the domain lineage checks.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from app.backend.rei.ids import sha256_hex
from app.backend.rei.models.character import (
    CharacterAuthority,
    FunctionalOverride,
    ProcessorAvailability,
)
from app.backend.rei.models.emocio import (
    EMOCIO_VALUATION_DIMENSIONS,
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioOptionValuation,
    EmocioVisualState,
    ValuationDimension,
    VisualSceneSpec,
)
from app.backend.rei.models.instinkt import (
    BodyState,
    InstinktInputPacket,
    InstinktNativeConclusion,
    InstinktOptionRollout,
)
from app.backend.rei.models.racio import (
    RacioInputPacket,
    RacioNativeConclusion,
    RacioWorld,
)
from app.backend.rei.models.run import NativeMindBundle
from app.backend.rei.models.scene import DecisionOption, EvidenceItem, SceneEvent


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
OPTION_IDS = ("option_a", "option_b", "option_c")
MIND_IDS = ("R", "E", "I")


def _tag(payload: object) -> str:
    return sha256_hex(payload)[:16]


def _scene() -> SceneEvent:
    return SceneEvent(
        event_id="governance_event",
        raw_input="Deterministic governance truth-table event.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="governance_evidence",
                modality="text",
                content="Three explicit options are available.",
                grounded=True,
                source_ref="test:governance_event",
                confidence=1.0,
            ),
        ),
        options=tuple(
            DecisionOption(option_id=option_id, label=option_id)
            for option_id in OPTION_IDS
        ),
        actors=("simulated_actor",),
        constraints=("governance must remain ordinal",),
    )


def _body_state() -> BodyState:
    return BodyState(
        body_state_id="governance_body_state",
        energy=0.8,
        fatigue=0.2,
        pain=0.0,
        arousal=0.3,
        tension=0.2,
        physical_integrity=1.0,
        uncertainty=0.4,
        trust=0.6,
        attachment_security=0.6,
        resource_security=0.7,
        boundary_integrity=0.8,
        escape_availability=0.9,
        predictability=0.5,
    )


def _visual_scene(
    scene_id: str,
    scene_kind: str,
    *,
    option_id: str | None = None,
) -> VisualSceneSpec:
    return VisualSceneSpec(
        scene_id=scene_id,
        scene_kind=scene_kind,
        option_id=option_id,
        entities=("simulated_actor",),
        self_position="observer",
        attention_structure=(),
        group_belonging="unspecified",
        status_relations=(),
        movement=(),
        composition=(),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=("governance_evidence",),
        inferred_elements=(),
    )


def _visual_state() -> EmocioVisualState:
    dimensions = tuple(
        ValuationDimension(name=name, score=0.5)
        for name in EMOCIO_VALUATION_DIMENSIONS
    )
    return EmocioVisualState(
        visual_state_id="governance_visual_state",
        source_scene_id="governance_event",
        source_packet_id="governance_emocio_packet",
        current_scene=_visual_scene("governance_visual_current", "current"),
        desired_scene=_visual_scene("governance_visual_desired", "desired"),
        broken_scene=_visual_scene("governance_visual_broken", "broken"),
        option_rollouts=tuple(
            _visual_scene(
                f"governance_visual_rollout_{option_id}",
                "option_rollout",
                option_id=option_id,
            )
            for option_id in OPTION_IDS
        ),
        option_valuations=tuple(
            EmocioOptionValuation(
                option_id=option_id,
                rollout_scene_id=f"governance_visual_rollout_{option_id}",
                dimensions=dimensions,
            )
            for option_id in OPTION_IDS
        ),
    )


def _instinkt_rollouts(body: BodyState) -> tuple[InstinktOptionRollout, ...]:
    return tuple(
        InstinktOptionRollout(
            rollout_id=f"governance_instinkt_rollout_{option_id}",
            option_id=option_id,
            trajectory=(body,),
            dominant_alarm=f"alarm assessment for {option_id}",
            predicted_loss=0.2,
            recoverability=0.8,
            protected_targets=("boundary",),
            boundary_outcome="preserved",
            trust_outcome="stable",
            attachment_outcome="stable",
            escape_outcome="available",
        )
        for option_id in OPTION_IDS
    )


def _packets(
    scene: SceneEvent,
    body: BodyState,
) -> tuple[RacioInputPacket, EmocioInputPacket, InstinktInputPacket]:
    racio = RacioInputPacket(
        packet_id="governance_racio_packet",
        scene_id=scene.event_id,
        symbolic_and_language_cues=(scene.raw_input,),
        numeric_cues=(),
        explicit_facts=(scene.evidence[0].content,),
        explicit_unknowns=scene.unknowns,
        time=(),
        rules=(),
        explicit_options=scene.options,
        explicit_consequences=(),
        constraints=scene.constraints,
        allowed_option_ids=OPTION_IDS,
        evidence_ids=("governance_evidence",),
        world=RacioWorld(
            world_id="governance_racio_world",
            explicit_beliefs=(),
            facts=(),
            rules=(),
            timelines=(),
            commitments=(),
        ),
        previous_racio_projection_ids=(),
        caveat="Profile-blind deterministic test packet.",
    )
    emocio = EmocioInputPacket(
        packet_id="governance_emocio_packet",
        scene_id=scene.event_id,
        grounded_visual_cues=(),
        social_layout=(),
        actor_positions=(),
        observed_attention=(),
        movement_cues=(),
        aesthetic_cues=(),
        explicit_identity_cues=(),
        allowed_option_ids=OPTION_IDS,
        evidence_ids=("governance_evidence",),
        caveat="Profile-blind deterministic test packet.",
    )
    instinkt = InstinktInputPacket(
        packet_id="governance_instinkt_packet",
        scene_id=scene.event_id,
        source_body_state_id=body.body_state_id,
        physical_cues=(),
        uncertainty_cues=(),
        trust_cues=(),
        boundary_cues=(),
        attachment_cues=(),
        scarcity_cues=(),
        escape_cues=(),
        explicit_body_cues=(),
        option_ids=OPTION_IDS,
        evidence_ids=("governance_evidence",),
        caveat="Conceptual virtual-body deterministic test packet.",
    )
    return racio, emocio, instinkt


def make_native_bundle(
    options: Mapping[str, str | None],
    *,
    racio_confidence: float = 0.5,
    emocio_intensity: float = 0.5,
    instinkt_intensity: float = 0.5,
) -> NativeMindBundle:
    """Build a complete frozen bundle for one explicit R/E/I option pattern."""

    if set(options) != set(MIND_IDS):
        raise ValueError("options must provide exactly R, E, and I")
    unknown = {option for option in options.values() if option not in {*OPTION_IDS, None}}
    if unknown:
        raise ValueError(f"unknown option IDs: {sorted(unknown)}")

    tag = _tag(
        {
            "options": dict(options),
            "racio_confidence": racio_confidence,
            "emocio_intensity": emocio_intensity,
            "instinkt_intensity": instinkt_intensity,
        }
    )
    scene = _scene()
    body = _body_state()
    visual_state = _visual_state()
    instinkt_rollouts = _instinkt_rollouts(body)
    racio_packet, emocio_packet, instinkt_packet = _packets(scene, body)

    racio_option = options["R"]
    emocio_option = options["E"]
    instinkt_option = options["I"]
    valuation_dimensions = tuple(
        ValuationDimension(name=name, score=0.5)
        for name in EMOCIO_VALUATION_DIMENSIONS
    )

    racio = RacioNativeConclusion(
        conclusion_id=f"governance_racio_conclusion_{tag}",
        source_packet_id=racio_packet.packet_id,
        source_scene_id=scene.event_id,
        option_id=racio_option,
        facts_used=("three options exist",),
        unknowns=(),
        causal_sequence=("compare options",),
        utility_structure=("preserve explicit goal",),
        explicit_goal="exercise the Racio option",
        main_objection=f"Racio position is {racio_option}",
        confidence=racio_confidence,
        abstains=racio_option is None,
        uncertainty="explicit test position",
    )
    emocio = EmocioNativeConclusion(
        conclusion_id=f"governance_emocio_conclusion_{tag}",
        source_packet_id=emocio_packet.packet_id,
        source_scene_id=scene.event_id,
        option_id=emocio_option,
        desired_transformation="move toward the desired scene",
        current_scene_id=visual_state.current_scene.scene_id,
        desired_scene_id=visual_state.desired_scene.scene_id,
        decisive_rollout_scene_id=(
            None
            if emocio_option is None
            else f"governance_visual_rollout_{emocio_option}"
        ),
        main_obstacle=f"Emocio position is {emocio_option}",
        action_tendency="unknown" if emocio_option is None else "approach",
        valuation_dimensions=(
            () if emocio_option is None else valuation_dimensions
        ),
        intensity=emocio_intensity,
        abstains=emocio_option is None,
        uncertainty="explicit test position",
    )
    instinkt = InstinktNativeConclusion(
        conclusion_id=f"governance_instinkt_conclusion_{tag}",
        source_packet_id=instinkt_packet.packet_id,
        source_scene_id=scene.event_id,
        source_body_state_id=body.body_state_id,
        option_id=instinkt_option,
        dominant_alarm=f"Instinkt position is {instinkt_option}",
        danger_claims=(),
        protected_targets=("boundary",),
        action_tendency="unknown" if instinkt_option is None else "maintain",
        minimum_safety_condition="an exit remains available",
        decisive_rollout_id=(
            None
            if instinkt_option is None
            else f"governance_instinkt_rollout_{instinkt_option}"
        ),
        decisive_rollout_option_id=instinkt_option,
        intensity=instinkt_intensity,
        abstains=instinkt_option is None,
        uncertainty="explicit test position",
    )
    return NativeMindBundle.create(
        scene=scene,
        racio_packet=racio_packet,
        emocio_packet=emocio_packet,
        instinkt_packet=instinkt_packet,
        emocio_visual_state=visual_state,
        instinkt_body_state=body,
        instinkt_rollouts=instinkt_rollouts,
        racio=racio,
        emocio=emocio,
        instinkt=instinkt,
        created_at=NOW,
    )


def make_functional_override(
    structural: CharacterAuthority,
    unavailable_minds: tuple[str, ...],
    *,
    unavailable_score: float = 0.95,
) -> FunctionalOverride:
    """Create explicit override evidence; the score intentionally is not a threshold."""

    if not unavailable_minds:
        raise ValueError("an override must identify at least one unavailable mind")
    availability = ProcessorAvailability(
        R=unavailable_score if "R" in unavailable_minds else 1.0,
        E=unavailable_score if "E" in unavailable_minds else 1.0,
        I=unavailable_score if "I" in unavailable_minds else 1.0,
    )
    tag = _tag(
        {
            "character_id": structural.character_id,
            "unavailable_minds": unavailable_minds,
            "availability": availability,
        }
    )
    return FunctionalOverride(
        functional_override_id=f"functional_override_{tag}",
        unavailable_minds=unavailable_minds,
        processor_availability=availability,
        evidence_ids=(f"functional_unavailability_evidence_{tag}",),
        note="Explicit test evidence; no score threshold is inferred.",
    )
