from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.backend.rei.ego import (
    derive_composition_snapshot,
    derive_modality_projections,
)
from app.backend.rei.ids import sha256_hex
from app.backend.rei.models.character import (
    CharacterAuthority,
    EffectiveAuthority,
    FunctionalOverride,
    ProcessorAvailability,
)
from app.backend.rei.models.communication import (
    AcceptanceState,
    DirectedMindRelation,
    EmocioManifestation,
    InstinktManifestation,
    ManifestationObservation,
    RacioInterpretation,
    TranslationGap,
)
from app.backend.rei.models.conscious import (
    BehaviorResultant,
    ConsciousDecision,
)
from app.backend.rei.models.ego import (
    EgoCompositionSnapshot,
    EgoCorrectionEvent,
    EgoMeasure,
    EgoTrace,
    EmocioProjection,
    InstinktProjection,
    RacioProjection,
    ReflectionHypothesis,
)
from app.backend.rei.models.emocio import (
    EMOCIO_VALUATION_DIMENSIONS,
    EmocioInputPacket,
    EmocioNativeConclusion,
    EmocioOptionValuation,
    EmocioVisualState,
    ImageArtifact,
    ValuationDimension,
    VisualSceneSpec,
)
from app.backend.rei.models.governance import (
    GovernanceMandate,
    MindOption,
    PairConflict,
)
from app.backend.rei.models.instinkt import (
    BodyDelta,
    BodyState,
    BodyTransition,
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


def _scene() -> SceneEvent:
    evidence = EvidenceItem(
        evidence_id="evidence_1",
        modality="text",
        content="Podani opis dogodka.",
        grounded=True,
        source_ref="user:event_1",
        confidence=1.0,
    )
    option = DecisionOption(option_id="option_a", label="Možnost A")
    return SceneEvent(
        event_id="event_1",
        raw_input="Dogodek z eno eksplicitno možnostjo.",
        language="sl",
        evidence=(evidence,),
        options=(option,),
        actors=("oseba",),
    )


def _body_state() -> BodyState:
    return BodyState(
        body_state_id="body_state_1",
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
        entities=("oseba",),
        self_position="observer",
        attention_structure=(),
        group_belonging="unspecified",
        status_relations=(),
        movement=(),
        composition=(),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=("evidence_1",),
        inferred_elements=(),
    )


def _emocio_visual_state() -> EmocioVisualState:
    dimensions = tuple(
        ValuationDimension(name=name, score=0.5)
        for name in EMOCIO_VALUATION_DIMENSIONS
    )
    return EmocioVisualState(
        visual_state_id="emocio_visual_state_1",
        source_scene_id="event_1",
        source_packet_id="emocio_packet_1",
        current_scene=_visual_scene("visual_current_1", "current"),
        desired_scene=_visual_scene("visual_desired_1", "desired"),
        broken_scene=_visual_scene("visual_broken_1", "broken"),
        option_rollouts=(
            _visual_scene(
                "visual_rollout_a",
                "option_rollout",
                option_id="option_a",
            ),
        ),
        option_valuations=(
            EmocioOptionValuation(
                option_id="option_a",
                rollout_scene_id="visual_rollout_a",
                dimensions=dimensions,
            ),
        ),
    )


def _instinkt_rollouts(body_state: BodyState) -> tuple[InstinktOptionRollout, ...]:
    return (
        InstinktOptionRollout(
            rollout_id="instinkt_rollout_a",
            option_id="option_a",
            trajectory=(body_state,),
            dominant_alarm="brez neposrednega alarma",
            predicted_loss=0.1,
            recoverability=0.9,
            protected_targets=("meja",),
            boundary_outcome="ohranjena",
            trust_outcome="nespremenjeno",
            attachment_outcome="nespremenjeno",
            escape_outcome="na voljo",
        ),
    )


def _native_packets(
    scene: SceneEvent,
) -> tuple[RacioInputPacket, EmocioInputPacket, InstinktInputPacket]:
    racio_packet = RacioInputPacket(
        packet_id="racio_packet_1",
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
        allowed_option_ids=("option_a",),
        evidence_ids=("evidence_1",),
        world=RacioWorld(
            world_id="racio_world_1",
            explicit_beliefs=(),
            facts=(),
            rules=(),
            timelines=(),
            commitments=(),
        ),
        previous_racio_projection_ids=(),
        caveat="Profile-blind packet.",
    )
    emocio_packet = EmocioInputPacket(
        packet_id="emocio_packet_1",
        scene_id=scene.event_id,
        grounded_visual_cues=(),
        social_layout=(),
        actor_positions=(),
        observed_attention=(),
        movement_cues=(),
        aesthetic_cues=(),
        explicit_identity_cues=(),
        allowed_option_ids=("option_a",),
        evidence_ids=("evidence_1",),
        caveat="Profile-blind packet.",
    )
    instinkt_packet = InstinktInputPacket(
        packet_id="instinkt_packet_1",
        scene_id=scene.event_id,
        source_body_state_id=_body_state().body_state_id,
        physical_cues=(),
        uncertainty_cues=(),
        trust_cues=(),
        boundary_cues=(),
        attachment_cues=(),
        scarcity_cues=(),
        escape_cues=(),
        explicit_body_cues=(),
        option_ids=("option_a",),
        evidence_ids=("evidence_1",),
        caveat="Conceptual virtual-body packet.",
    )
    return racio_packet, emocio_packet, instinkt_packet


def _native_bundle() -> NativeMindBundle:
    racio = RacioNativeConclusion(
        conclusion_id="racio_conclusion_1",
        source_packet_id="racio_packet_1",
        source_scene_id="event_1",
        option_id="option_a",
        facts_used=("dejstvo",),
        unknowns=(),
        causal_sequence=("vzrok -> posledica",),
        utility_structure=("korist",),
        explicit_goal="doseči cilj",
        main_objection="ni ugovora",
        confidence=0.8,
        uncertainty="omejena",
    )
    emocio = EmocioNativeConclusion(
        conclusion_id="emocio_conclusion_1",
        source_packet_id="emocio_packet_1",
        source_scene_id="event_1",
        option_id="option_a",
        desired_transformation="približanje želeni podobi",
        current_scene_id="visual_current_1",
        desired_scene_id="visual_desired_1",
        decisive_rollout_scene_id="visual_rollout_a",
        main_obstacle="ovira",
        action_tendency="approach",
        valuation_dimensions=tuple(
            ValuationDimension(name=name, score=0.5)
            for name in EMOCIO_VALUATION_DIMENSIONS
        ),
        intensity=0.7,
        uncertainty="omejena",
    )
    instinkt = InstinktNativeConclusion(
        conclusion_id="instinkt_conclusion_1",
        source_packet_id="instinkt_packet_1",
        source_scene_id="event_1",
        source_body_state_id="body_state_1",
        option_id="option_a",
        dominant_alarm="brez neposrednega alarma",
        danger_claims=(),
        protected_targets=("meja",),
        action_tendency="maintain",
        minimum_safety_condition="ohranjena možnost umika",
        decisive_rollout_id="instinkt_rollout_a",
        decisive_rollout_option_id="option_a",
        intensity=0.4,
        uncertainty="omejena",
    )
    scene = _scene()
    racio_packet, emocio_packet, instinkt_packet = _native_packets(scene)
    emocio_visual_state = _emocio_visual_state()
    instinkt_body_state = _body_state()
    instinkt_rollouts = _instinkt_rollouts(instinkt_body_state)
    return NativeMindBundle.create(
        scene=scene,
        racio_packet=racio_packet,
        emocio_packet=emocio_packet,
        instinkt_packet=instinkt_packet,
        emocio_visual_state=emocio_visual_state,
        instinkt_body_state=instinkt_body_state,
        instinkt_rollouts=instinkt_rollouts,
        racio=racio,
        emocio=emocio,
        instinkt=instinkt,
        created_at=NOW,
    )


def _acceptance() -> AcceptanceState:
    relation = DirectedMindRelation(
        visibility=0.8,
        interpretation_fidelity=0.7,
        tolerance=0.8,
        delegation_willingness=0.6,
        sabotage_risk=0.1,
    )
    return AcceptanceState(
        acceptance_state_id="acceptance_1",
        R_to_E=relation,
        R_to_I=relation,
        E_to_R=relation,
        E_to_I=relation,
        I_to_R=relation,
        I_to_E=relation,
        overall_mode="accepting",
    )


def _character() -> CharacterAuthority:
    return CharacterAuthority(
        character_id="character_1",
        profile_id="R>(E=I)",
        authority_tiers=(("R",), ("E", "I")),
        rule="single_top",
    )


def _ego_measure(bundle: NativeMindBundle) -> EgoMeasure:
    character = _character()
    effective = EffectiveAuthority(
        effective_authority_id="effective_1",
        structural_profile=character,
        effective_tiers=character.authority_tiers,
    )
    mandate = GovernanceMandate(
        mandate_id="mandate_1",
        status="resolved",
        structural_source_minds=("R",),
        option_id="option_a",
    )
    decision = ConsciousDecision(
        decision_id="decision_1",
        option_id="option_a",
        declared_reason="zavedna razlaga",
        conscious_confidence=0.8,
        aligned_with_governance_mandate=True,
        decision_status="committed",
    )
    behavior = BehaviorResultant(
        resultant_id="resultant_1",
        option_id="option_a",
        status="executed",
        governance_alignment="aligned",
        conscious_alignment="aligned",
        operational_controller="R",
        predicted_action="izvedi možnost A",
    )
    return EgoMeasure.create(
        event_id="event_1",
        native_bundle_id=bundle.bundle_id,
        native_bundle_hash=bundle.immutable_hash,
        governance_resolution_id="governance_resolution_fixture",
        governance_resolution_hash=mandate.content_hash(),
        structural_character=character,
        effective_authority=effective,
        acceptance_state=_acceptance(),
        governance_mandate=mandate,
        conscious_decision=decision,
        behavior_resultant=behavior,
        spoznanje_status="simulated_spoznanje",
        created_at=NOW,
    )


def test_scene_evidence_has_explicit_provenance() -> None:
    scene = _scene()

    assert scene.evidence[0].source_ref == "user:event_1"
    assert scene.evidence[0].grounded is True
    assert len(scene.scene_hash()) == 64


def test_scene_can_represent_an_event_without_predefined_options() -> None:
    scene = SceneEvent(
        event_id="event_without_options",
        raw_input="Odprt dogodek.",
        language="sl",
    )

    assert scene.options == ()


def test_inferred_evidence_cannot_be_marked_grounded() -> None:
    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="evidence_invalid",
            modality="text",
            content="Sklep modela.",
            grounded=True,
            source_ref="derived:event_1",
            confidence=0.5,
            provenance_kind="inferred",
            inferred_by="router_1",
        )

    with pytest.raises(ValidationError):
        EvidenceItem(
            evidence_id="evidence_without_producer",
            modality="text",
            content="Sklep brez sledljivega producenta.",
            grounded=False,
            source_ref="derived:event_1",
            confidence=0.5,
            provenance_kind="inferred",
        )


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        SceneEvent(
            event_id="event_extra",
            raw_input="Dogodek.",
            language="sl",
            character_profile="R=E=I",
        )


def test_native_bundle_is_hash_verified_and_immutable() -> None:
    bundle = _native_bundle()

    assert bundle.immutable_hash == bundle.content_hash(
        exclude_fields=frozenset({"immutable_hash"})
    )
    with pytest.raises(ValidationError):
        bundle.racio = bundle.racio
    with pytest.raises(ValidationError):
        bundle.racio.confidence = 0.1
    with pytest.raises(ValidationError):
        NativeMindBundle(
            bundle_id=bundle.bundle_id,
            scene_id=bundle.scene_id,
            scene_hash=bundle.scene_hash,
            allowed_option_ids=bundle.allowed_option_ids,
            racio_packet_hash=bundle.racio_packet_hash,
            emocio_packet_hash=bundle.emocio_packet_hash,
            instinkt_packet_hash=bundle.instinkt_packet_hash,
            emocio_visual_state_id=bundle.emocio_visual_state_id,
            emocio_visual_state_hash=bundle.emocio_visual_state_hash,
            instinkt_body_state_id=bundle.instinkt_body_state_id,
            instinkt_body_state_hash=bundle.instinkt_body_state_hash,
            instinkt_rollout_hashes=bundle.instinkt_rollout_hashes,
            racio=bundle.racio,
            emocio=bundle.emocio,
            instinkt=bundle.instinkt,
            created_at=bundle.created_at,
            immutable_hash="0" * 64,
        )


def test_native_bundle_option_scope_survives_deserialization() -> None:
    bundle = _native_bundle()
    untrusted_racio = bundle.racio.model_copy(update={"option_id": "option_external"})
    payload = {
        "schema_version": bundle.schema_version,
        "bundle_id": bundle.bundle_id,
        "scene_id": bundle.scene_id,
        "scene_hash": bundle.scene_hash,
        "allowed_option_ids": bundle.allowed_option_ids,
        "racio_packet_hash": bundle.racio_packet_hash,
        "emocio_packet_hash": bundle.emocio_packet_hash,
        "instinkt_packet_hash": bundle.instinkt_packet_hash,
        "emocio_visual_state_id": bundle.emocio_visual_state_id,
        "emocio_visual_state_hash": bundle.emocio_visual_state_hash,
        "instinkt_body_state_id": bundle.instinkt_body_state_id,
        "instinkt_body_state_hash": bundle.instinkt_body_state_hash,
        "instinkt_rollout_hashes": bundle.instinkt_rollout_hashes,
        "racio": untrusted_racio,
        "emocio": bundle.emocio,
        "instinkt": bundle.instinkt,
        "created_at": bundle.created_at,
    }

    with pytest.raises(ValidationError):
        NativeMindBundle(**payload, immutable_hash=sha256_hex(payload))

    bundle.validate_against(_scene())


def test_native_bundle_serializes_and_round_trips() -> None:
    bundle = _native_bundle()

    restored = NativeMindBundle.model_validate_json(bundle.model_dump_json())

    assert restored == bundle
    assert restored.immutable_hash == bundle.immutable_hash


def test_native_bundle_factory_rejects_unlinked_intermediate_artifacts() -> None:
    scene = _scene()
    racio_packet, emocio_packet, instinkt_packet = _native_packets(scene)
    body = _body_state()
    bundle = _native_bundle()
    unlinked_emocio = bundle.emocio.model_copy(
        update={"decisive_rollout_scene_id": "visual_rollout_missing"}
    )

    with pytest.raises(ValueError):
        NativeMindBundle.create(
            scene=scene,
            racio_packet=racio_packet,
            emocio_packet=emocio_packet,
            instinkt_packet=instinkt_packet,
            emocio_visual_state=_emocio_visual_state(),
            instinkt_body_state=body,
            instinkt_rollouts=_instinkt_rollouts(body),
            racio=bundle.racio,
            emocio=unlinked_emocio,
            instinkt=bundle.instinkt,
            created_at=NOW,
        )


def test_native_inputs_do_not_receive_character_or_authority() -> None:
    field_names = set(RacioInputPacket.model_fields)

    assert "character_profile" not in field_names
    assert "character_authority" not in field_names
    assert "authority_tiers" not in field_names


def test_native_packets_round_trip_and_preserve_scene_scope() -> None:
    scene = _scene()
    body = _body_state()
    racio_packet, emocio_packet, instinkt_packet = _native_packets(scene)

    racio_packet.validate_against(scene)
    emocio_packet.validate_against(scene)
    instinkt_packet.validate_against(scene, body)
    bundle = _native_bundle()
    bundle.validate_packets(
        scene=scene,
        racio_packet=racio_packet,
        emocio_packet=emocio_packet,
        instinkt_packet=instinkt_packet,
    )
    bundle.validate_native_lineage(
        scene=scene,
        racio_packet=racio_packet,
        emocio_packet=emocio_packet,
        instinkt_packet=instinkt_packet,
        emocio_visual_state=_emocio_visual_state(),
        instinkt_body_state=body,
        instinkt_rollouts=_instinkt_rollouts(body),
    )
    packet_with_foreign_evidence = racio_packet.model_copy(
        update={"evidence_ids": ("evidence_not_in_scene",)}
    )
    with pytest.raises(ValueError):
        bundle.validate_packets(
            scene=scene,
            racio_packet=packet_with_foreign_evidence,
            emocio_packet=emocio_packet,
            instinkt_packet=instinkt_packet,
        )

    for packet in (racio_packet, emocio_packet, instinkt_packet):
        assert type(packet).model_validate_json(packet.model_dump_json()) == packet


def test_emocio_visual_state_cannot_escape_packet_evidence_scope() -> None:
    scene = _scene()
    _, emocio_packet, _ = _native_packets(scene)
    packet_without_evidence = emocio_packet.model_copy(update={"evidence_ids": ()})

    with pytest.raises(ValueError):
        _emocio_visual_state().validate_against(packet_without_evidence, scene)
    foreign_state = _emocio_visual_state().model_copy(
        update={"source_scene_id": "event_foreign"}
    )
    with pytest.raises(ValueError):
        foreign_state.validate_against(emocio_packet, scene)


def test_emocio_valuation_dimensions_match_canon_order() -> None:
    assert EMOCIO_VALUATION_DIMENSIONS == (
        "desired_scene_match",
        "distance_from_broken_scene",
        "self_visibility",
        "belonging",
        "attention",
        "attraction",
        "novelty",
        "movement",
        "status",
        "competitive_success",
        "attack_or_breakthrough_affordance",
    )

    state = _emocio_visual_state()
    rollout_b = state.option_rollouts[0].model_copy(
        update={"scene_id": "visual_rollout_b", "option_id": "option_b"}
    )
    valuation_b = state.option_valuations[0].model_copy(
        update={"option_id": "option_b", "rollout_scene_id": "visual_rollout_b"}
    )
    with pytest.raises(ValidationError):
        EmocioVisualState(
            visual_state_id="emocio_visual_state_unsorted",
            source_scene_id=state.source_scene_id,
            source_packet_id=state.source_packet_id,
            current_scene=state.current_scene,
            desired_scene=state.desired_scene,
            broken_scene=state.broken_scene,
            option_rollouts=(rollout_b, state.option_rollouts[0]),
            option_valuations=(valuation_b, state.option_valuations[0]),
        )


def test_instinkt_rollout_rejects_conflicting_stable_body_state_ids() -> None:
    initial = _body_state()
    conflicting = initial.model_copy(update={"energy": 0.1})

    with pytest.raises(ValidationError):
        InstinktOptionRollout(
            rollout_id="instinkt_rollout_invalid",
            option_id="option_a",
            trajectory=(initial, conflicting),
            dominant_alarm="alarm",
            predicted_loss=0.5,
            recoverability=0.5,
            protected_targets=(),
            boundary_outcome="unknown",
            trust_outcome="unknown",
            attachment_outcome="unknown",
            escape_outcome="unknown",
        )

    scene = _scene()
    _, _, packet = _native_packets(scene)
    two_option_packet = packet.model_copy(
        update={"option_ids": ("option_a", "option_b")}
    )
    shared_a = initial.model_copy(
        update={"body_state_id": "shared_state", "energy": 0.5}
    )
    shared_b = initial.model_copy(
        update={"body_state_id": "shared_state", "energy": 0.4}
    )
    rollout_a = _instinkt_rollouts(initial)[0].model_copy(
        update={"trajectory": (initial, shared_a)}
    )
    rollout_b = rollout_a.model_copy(
        update={
            "rollout_id": "instinkt_rollout_b",
            "option_id": "option_b",
            "trajectory": (initial, shared_b),
        }
    )
    with pytest.raises(ValueError):
        _native_bundle().instinkt.validate_against(
            two_option_packet,
            initial,
            (rollout_a, rollout_b),
        )


def test_racio_is_the_only_conscious_decision_type() -> None:
    with pytest.raises(ValidationError):
        ConsciousDecision(
            decision_id="decision_invalid",
            made_by="E",
            option_id="option_a",
            declared_reason="neveljavno",
            conscious_confidence=0.5,
            decision_status="committed",
        )

    assert "made_by" not in EmocioNativeConclusion.model_fields
    assert "made_by" not in InstinktNativeConclusion.model_fields


def test_ego_trace_is_append_only_and_has_no_decision_api() -> None:
    measure = _ego_measure(_native_bundle())
    empty_trace = EgoTrace.create(ego_id="ego_1")
    trace = empty_trace.append_measure(measure)
    correction = EgoCorrectionEvent.create(
        ego_id="ego_1",
        target_measure_id=measure.measure_id,
        reason="nova zunanja evidenca",
        correction="prejšnji opis izida je nepopoln",
        recorded_at=NOW,
    )
    corrected_trace = trace.append_correction(correction)

    assert empty_trace.measures == ()
    assert trace.measures == (measure,)
    assert trace.corrections == ()
    assert corrected_trace.corrections == (correction,)
    assert tuple(item.event_kind for item in corrected_trace.event_order) == (
        "measure",
        "correction",
    )

    prohibited = {
        "vote",
        "ego_vote",
        "preferred_option",
        "ego_preferred_option",
        "leading_mind",
        "decision_maker",
    }
    ego_models = (
        EgoMeasure,
        EgoTrace,
        EgoCorrectionEvent,
        EgoCompositionSnapshot,
        RacioProjection,
        EmocioProjection,
        InstinktProjection,
        ReflectionHypothesis,
    )
    for model in ego_models:
        assert prohibited.isdisjoint(model.model_fields)
        for method_name in ("decide", "vote", "propose", "select"):
            assert not hasattr(model, method_name)


def test_character_profile_is_bound_to_its_canonical_tiers() -> None:
    with pytest.raises(ValidationError):
        CharacterAuthority(
            character_id="character_invalid",
            profile_id="R>(E=I)",
            authority_tiers=(("E",), ("R", "I")),
            rule="single_top",
        )


def test_effective_authority_requires_evidenced_functional_override() -> None:
    character = _character()
    with pytest.raises(ValidationError):
        EffectiveAuthority(
            effective_authority_id="effective_invalid",
            structural_profile=character,
            effective_tiers=(("R",), ("I",)),
        )

    override = FunctionalOverride(
        functional_override_id="functional_override_1",
        unavailable_minds=("E",),
        processor_availability=ProcessorAvailability(R=1.0, E=0.2, I=1.0),
        evidence_ids=("availability_evidence_1",),
    )
    effective = EffectiveAuthority(
        effective_authority_id="effective_1",
        structural_profile=character,
        effective_tiers=(("R",), ("I",)),
        override_reason="explicit_functional_unavailability",
        functional_override=override,
    )

    assert effective.structural_profile.authority_tiers == (("R",), ("E", "I"))
    assert effective.effective_tiers == (("R",), ("I",))


def test_pair_conflict_status_matches_top_mind_options() -> None:
    with pytest.raises(ValidationError):
        PairConflict(
            pair_conflict_id="pair_conflict_invalid_agreement",
            top_minds=("R", "E"),
            option_by_mind=(
                MindOption(mind="R", option_id="option_a"),
                MindOption(mind="E", option_id="option_a"),
            ),
            status="unresolved",
        )
    with pytest.raises(ValidationError):
        PairConflict(
            pair_conflict_id="pair_conflict_invalid_disagreement",
            top_minds=("R", "E"),
            option_by_mind=(
                MindOption(mind="R", option_id="option_a"),
                MindOption(mind="E", option_id="option_b"),
            ),
            status="resolved",
        )


def test_translation_gap_is_internally_consistent_and_linked_to_measure() -> None:
    with pytest.raises(ValidationError):
        TranslationGap(
            translation_gap_id="gap_contradictory",
            source_mind="E",
            source_conclusion_id="emocio_conclusion_1",
            interpretation_id="interpretation_1",
            native_option_id="option_a",
            interpreted_option_id="option_a",
            native_motive_summary="native",
            interpreted_motive="interpreted",
            option_match=False,
            motive_fidelity=0.5,
            distortion_type="minimization",
        )

    bundle = _native_bundle()
    base = _ego_measure(bundle)
    gap = TranslationGap(
        translation_gap_id="gap_1",
        source_mind="E",
        source_conclusion_id="emocio_conclusion_1",
        interpretation_id="interpretation_missing",
        native_option_id="option_a",
        interpreted_option_id="option_a",
        native_motive_summary="native",
        interpreted_motive="interpreted",
        option_match=True,
        motive_fidelity=0.8,
        distortion_type="none",
    )
    with pytest.raises(ValidationError):
        EgoMeasure.create(
            event_id=base.event_id,
            native_bundle_id=base.native_bundle_id,
            native_bundle_hash=base.native_bundle_hash,
            governance_resolution_id=base.governance_resolution_id,
            governance_resolution_hash=base.governance_resolution_hash,
            structural_character=base.structural_character,
            effective_authority=base.effective_authority,
            acceptance_state=base.acceptance_state,
            governance_mandate=base.governance_mandate,
            conscious_decision=base.conscious_decision,
            behavior_resultant=base.behavior_resultant,
            spoznanje_status=base.spoznanje_status,
            translation_gaps=(gap,),
            created_at=NOW,
        )


def test_renderer_added_observation_is_explicitly_ungrounded() -> None:
    with pytest.raises(ValidationError):
        ManifestationObservation(
            manifestation_id="emocio_manifestation_1",
            content="Podrobnost, ki jo je dodal renderer.",
            provenance="manifested",
            source_image_artifact_id="image_1",
        )

    observation = ManifestationObservation(
        manifestation_id="emocio_manifestation_1",
        content="Podrobnost, ki jo je dodal renderer.",
        provenance="renderer_added_ungrounded",
        source_image_artifact_id="image_1",
    )
    assert observation.provenance == "renderer_added_ungrounded"


def test_racio_interpretation_closes_manifestation_and_image_lineage() -> None:
    manifestation = EmocioManifestation(
        manifestation_id="emocio_manifestation_1",
        source_conclusion_id="emocio_conclusion_1",
        visible_image_artifact_ids=("image_1",),
        attraction_intensity=0.5,
        aversion_intensity=0.1,
        anger_intensity=0.0,
        motor_urge="approach",
        social_pull="connect",
    )
    image = ImageArtifact(
        image_id="image_1",
        request_id="render_request_1",
        render_call_id="render_call_1",
        source_spec_id="visual_current_1",
        provider_id="renderer_1",
        seed=17,
        input_spec_hash="a" * 64,
        content_sha256="b" * 64,
        media_type="image/png",
        prompt="presentation-only prompt",
        negative_prompt="",
        path="emocio/images/image_1.png",
        width=64,
        height=64,
        generated_only_elements=(),
    )
    manifestation.validate_against(_native_bundle().emocio, (image,))
    with pytest.raises(ValueError):
        manifestation.validate_against(
            _native_bundle().emocio,
            (image.model_copy(update={"source_spec_id": "visual_foreign"}),),
        )
    observation = ManifestationObservation(
        manifestation_id=manifestation.manifestation_id,
        content="Renderer-added presentation detail.",
        provenance="renderer_added_ungrounded",
        source_image_artifact_id="image_1",
    )
    interpretation = RacioInterpretation(
        interpretation_id="interpretation_1",
        source_mind="E",
        observed_manifestation_ids=(manifestation.manifestation_id,),
        observed_manifestations=(observation,),
        inferred_motive="connect",
        confidence=0.5,
    )

    interpretation.validate_against((manifestation,))

    spoofed = interpretation.model_copy(
        update={
            "observed_manifestations": (
                observation.model_copy(
                    update={"source_image_artifact_id": "image_not_visible"}
                ),
            ),
        }
    )
    with pytest.raises(ValueError):
        spoofed.validate_against((manifestation,))

    wrong_source = interpretation.model_copy(update={"source_mind": "I"})
    with pytest.raises(ValueError):
        wrong_source.validate_against((manifestation,))

    instinkt_manifestation = InstinktManifestation(
        manifestation_id="instinkt_manifestation_1",
        source_conclusion_id="instinkt_conclusion_1",
        felt_tension=0.2,
        fear_intensity=0.1,
        attachment_pull=0.1,
        withdrawal_urge=0.0,
        freeze_intensity=0.0,
        boundary_alarm=0.1,
        raw_urge="maintain",
    )
    instinkt_interpretation = RacioInterpretation(
        interpretation_id="interpretation_i_1",
        source_mind="I",
        observed_manifestation_ids=(instinkt_manifestation.manifestation_id,),
        observed_manifestations=(
            ManifestationObservation(
                manifestation_id=instinkt_manifestation.manifestation_id,
                content="Felt tension.",
                provenance="manifested",
            ),
        ),
        inferred_motive="maintain safety",
        confidence=0.5,
    )
    instinkt_interpretation.validate_against((instinkt_manifestation,))

def test_ego_hashes_reject_tampering() -> None:
    measure = _ego_measure(_native_bundle())
    measure_payload = {
        name: getattr(measure, name)
        for name in EgoMeasure.model_fields
        if name != "measure_hash"
    }
    with pytest.raises(ValidationError):
        EgoMeasure(**measure_payload, measure_hash="0" * 64)

    correction = EgoCorrectionEvent.create(
        ego_id="ego_1",
        target_measure_id=measure.measure_id,
        reason="reason",
        correction="correction",
        recorded_at=NOW,
    )
    correction_payload = {
        name: getattr(correction, name)
        for name in EgoCorrectionEvent.model_fields
        if name != "correction_hash"
    }
    with pytest.raises(ValidationError):
        EgoCorrectionEvent(**correction_payload, correction_hash="0" * 64)

    trace = EgoTrace.create(ego_id="ego_1").append_measure(measure)
    trace_payload = {
        name: getattr(trace, name)
        for name in EgoTrace.model_fields
        if name != "trace_hash"
    }
    with pytest.raises(ValidationError):
        EgoTrace(**trace_payload, trace_hash="0" * 64)


def test_ego_projection_must_cite_through_measure() -> None:
    with pytest.raises(ValidationError):
        RacioProjection(
            projection_id="projection_invalid",
            ego_id="ego_1",
            through_measure_id="measure_2",
            evidence_measure_ids=("measure_1",),
        )


def test_body_transition_records_exact_state_delta() -> None:
    before = BodyState(
        body_state_id="body_before_1",
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
    after = before.model_copy(
        update={"body_state_id": "body_after_1", "tension": 0.4}
    )
    transition = BodyTransition(
        transition_id="transition_1",
        from_state=before,
        to_state=after,
        deltas=(BodyDelta(dimension="tension", delta=0.2),),
        triggering_evidence_ids=("evidence_1",),
    )

    assert transition.deltas[0].delta == pytest.approx(0.2)
    scene = _scene()
    _, _, instinkt_packet = _native_packets(scene)
    transition.validate_against(instinkt_packet, scene)
    packet_without_evidence = instinkt_packet.model_copy(update={"evidence_ids": ()})
    with pytest.raises(ValueError):
        transition.validate_against(packet_without_evidence, scene)
    with pytest.raises(ValidationError):
        BodyTransition(
            transition_id="transition_invalid",
            from_state=before,
            to_state=after,
            deltas=(BodyDelta(dimension="tension", delta=0.1),),
            triggering_evidence_ids=("evidence_1",),
        )
    with pytest.raises(ValidationError):
        BodyTransition(
            transition_id="transition_reused_state_id",
            from_state=before,
            to_state=after.model_copy(update={"body_state_id": before.body_state_id}),
            deltas=(BodyDelta(dimension="tension", delta=0.2),),
            triggering_evidence_ids=("evidence_1",),
        )


def test_core_artifacts_serialize_and_round_trip() -> None:
    bundle = _native_bundle()
    measure = _ego_measure(bundle)
    correction = EgoCorrectionEvent.create(
        ego_id="ego_1",
        target_measure_id=measure.measure_id,
        reason="nova evidenca",
        correction="popravek",
        recorded_at=NOW,
    )
    trace = EgoTrace.create(ego_id="ego_1").append_measure(measure).append_correction(
        correction
    )
    snapshot = derive_composition_snapshot(trace)
    projections = derive_modality_projections(
        trace,
        {bundle.bundle_id: bundle},
    )
    hypothesis = ReflectionHypothesis(
        hypothesis_id="hypothesis_1",
        ego_id="ego_1",
        statement="izpeljana hipoteza",
        confidence=0.5,
        supporting_measure_ids=(measure.measure_id,),
        created_at=NOW,
    )

    artifacts = (
        _scene(),
        bundle,
        measure.structural_character,
        measure.effective_authority,
        measure.acceptance_state,
        measure.governance_mandate,
        measure.conscious_decision,
        measure.behavior_resultant,
        measure,
        correction,
        trace,
        snapshot,
        *projections,
        hypothesis,
    )
    for artifact in artifacts:
        restored = type(artifact).model_validate_json(artifact.model_dump_json())
        assert restored == artifact
