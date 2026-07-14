from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from app.backend.rei.instinkt.association_memory import BoundedAssociativeMemory
from app.backend.rei.instinkt.effect_compiler import (
    EffectCompilationAbstainedError,
    compile_prediction_to_option_body_effect,
)
from app.backend.rei.instinkt.effect_mapper import (
    EmbodiedCueInterpreter,
    ModelBackedEffectInferenceDisabledError,
    ModelBackedEmbodiedCueInterpreterStub,
    RuleBasedEmbodiedCueInterpreter,
)
from app.backend.rei.instinkt.effect_rules import load_instinkt_effect_rules
from app.backend.rei.instinkt.packets import InstinktEffectSpec, build_instinkt_packet
from app.backend.rei.instinkt.processor import process_instinkt
from app.backend.rei.models.instinkt import (
    BODY_DIMENSIONS,
    BodyState,
    InstinktAssociation,
    InstinktCueEvidenceBinding,
    InstinktCueEvidenceCitation,
    InstinktWorld,
)
from app.backend.rei.models.instinkt_effects import (
    EMBODIED_CUE_CLASSES,
    BodyEffectEvidence,
    OptionBodyEffectCompilation,
    OptionBodyEffectPrediction,
)
from app.backend.rei.models.scene import DecisionOption, EvidenceItem, SceneEvent


def _body(body_state_id: str = "body_c5", **overrides: float) -> BodyState:
    values = {dimension: 0.5 for dimension in BODY_DIMENSIONS}
    values.update(overrides)
    return BodyState(body_state_id=body_state_id, **values)


def _scene(
    *,
    evidence_content: str,
    option_label: str,
    event_id: str = "event_c5",
    evidence_id: str = "evidence_c5",
) -> SceneEvent:
    return SceneEvent(
        event_id=event_id,
        raw_input=evidence_content,
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id=evidence_id,
                modality="text",
                content=evidence_content,
                grounded=True,
                source_ref=f"user:{event_id}",
                confidence=0.9,
            ),
        ),
        options=(
            DecisionOption(
                option_id="option_c5",
                label=option_label,
                description=f"Explicit option: {option_label}",
            ),
        ),
    )


def _binding(
    evidence: EvidenceItem,
    lane: str,
    cue_class: str,
    cue: str,
    *,
    cited_text: str | None = None,
    assertion_status: str = "asserted_positive",
) -> InstinktCueEvidenceBinding:
    needle = cited_text or cue
    start = evidence.content.casefold().index(needle.casefold())
    return InstinktCueEvidenceBinding.create(
        lane=lane,  # type: ignore[arg-type]
        cue_class=cue_class,  # type: ignore[arg-type]
        cue=cue,
        assertion_status=assertion_status,  # type: ignore[arg-type]
        citations=(
            InstinktCueEvidenceCitation.create(
                evidence=evidence,
                start_char=start,
                end_char=start + len(needle),
            ),
        ),
    )


def _mapped_threat(
    *,
    body: BodyState | None = None,
    world: InstinktWorld | None = None,
):
    body = body or _body()
    association_records = (
        InstinktAssociation(
            association_id="association_threat_c5",
            cue_signature=("threat",),
            body_state_before=body,
            felt_intensity=0.8,
            protected_target="virtual bodily integrity",
            experienced_loss="threat injury",
            action_taken="withdraw",
            outcome="safe exit used",
            trust_delta=0.0,
            attachment_delta=0.0,
            boundary_delta=0.0,
            decay=0.0,
        ),
        InstinktAssociation(
            association_id="association_exit_c5",
            cue_signature=("exit",),
            body_state_before=body,
            felt_intensity=0.6,
            protected_target="escape availability",
            experienced_loss=None,
            action_taken="leave",
            outcome="exit remained available",
            trust_delta=0.0,
            attachment_delta=0.0,
            boundary_delta=0.0,
            decay=0.0,
        ),
    )
    world = world or InstinktWorld.create(
        associations=tuple(item.association_id for item in association_records)
    )
    scene = _scene(
        evidence_content="A grounded threat is present and an exit route is visible.",
        option_label="leave through the exit",
    )
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=("threat",),
        escape_cues=("exit",),
        evidence_ids=("evidence_c5",),
        cue_evidence_bindings=(
            _binding(scene.evidence[0], "physical_cues", "physical_threat", "threat"),
            _binding(
                scene.evidence[0],
                "escape_cues",
                "escape_availability",
                "exit",
            ),
        ),
    )
    mapper = RuleBasedEmbodiedCueInterpreter(
        association_records=association_records
    )
    prediction = mapper.infer_effects(scene, packet, world, body, scene.options[0])
    return scene, packet, world, body, mapper, prediction


def test_rule_based_effects_have_provenance() -> None:
    scene, packet, world, body, mapper, prediction = _mapped_threat()

    assert prediction.abstains is False
    assert prediction.evidence
    assert all(item.source_evidence_ids == ("evidence_c5",) for item in prediction.evidence)
    assert all(item.rule_id in mapper.ruleset.by_rule_id for item in prediction.evidence)
    assert all(item.association_basis == "matched_association" for item in prediction.evidence)
    assert all(item.association_ids for item in prediction.evidence)
    assert prediction.source_scene_hash == scene.scene_hash()
    assert prediction.source_packet_hash == packet.content_hash()
    assert prediction.source_world_hash == world.content_hash()
    assert prediction.source_body_state_hash == body.content_hash()

    compilation = compile_prediction_to_option_body_effect(
        prediction=prediction,
        scene=scene,
        packet=packet,
        world=world,
        body=body,
        option=scene.options[0],
        ruleset=mapper.ruleset,
        association_records=mapper.association_records,
    )
    assert compilation.option_body_effect.body_deltas == prediction.combined_deltas
    assert compilation.option_body_effect.triggering_evidence_ids == ("evidence_c5",)
    assert compilation.validate_against(
        prediction=prediction, ruleset=mapper.ruleset, packet=packet
    ) == compilation


def test_compiler_transfers_exact_cue_signature_into_b8_memory_retrieval() -> None:
    scene, packet, world, body, mapper, prediction = _mapped_threat()
    compilation = compile_prediction_to_option_body_effect(
        prediction=prediction,
        scene=scene,
        packet=packet,
        world=world,
        body=body,
        option=scene.options[0],
        ruleset=mapper.ruleset,
        association_records=mapper.association_records,
    )
    effect = compilation.option_body_effect
    assert "threat" in effect.association_cue_tokens

    memory = BoundedAssociativeMemory()
    threat_record = next(
        item for item in mapper.association_records if item.cue_signature == ("threat",)
    )
    memory.add(threat_record)
    without_memory = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(effect,),
    )
    with_memory = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(effect,),
        memory=memory,
    )

    assert without_memory.association_matches[0].matches == ()
    assert with_memory.association_matches[0].matches
    assert with_memory.association_matches[0].matches[0].overlap_tokens == ("threat",)
    assert with_memory.rollouts[0].predicted_loss > without_memory.rollouts[0].predicted_loss
    assert with_memory.rollouts[0].rollout_id != without_memory.rollouts[0].rollout_id


def test_unsupported_event_abstains() -> None:
    body = _body()
    scene = _scene(
        evidence_content="A blue chair is present.",
        option_label="proceed",
    )
    packet = build_instinkt_packet(
        scene,
        body,
        uncertainty_cues=("unknown",),
        evidence_ids=(),
    )
    world = InstinktWorld.create()
    mapper = RuleBasedEmbodiedCueInterpreter()

    prediction = mapper.infer_effects(scene, packet, world, body, scene.options[0])

    assert prediction.abstains is True
    assert prediction.evidence == ()
    assert prediction.combined_deltas == ()
    assert prediction.unsupported_dimensions == BODY_DIMENSIONS
    assert "no default effect was emitted" in prediction.uncertainty
    with pytest.raises(EffectCompilationAbstainedError):
        compile_prediction_to_option_body_effect(
            prediction=prediction,
            scene=scene,
            packet=packet,
            world=world,
            body=body,
            option=scene.options[0],
            ruleset=mapper.ruleset,
        )


@pytest.mark.parametrize(
    "evidence_content,cited_text",
    (
        ("A poster displays the word THREAT.", "THREAT"),
        ("The film titled Threat begins at eight.", "Threat"),
        ('The catalog title is "THREAT".', "THREAT"),
        ('The witness only quoted "threat" from the script.', "threat"),
    ),
)
def test_typed_mentions_never_emit_physical_threat_effects(
    evidence_content: str,
    cited_text: str,
) -> None:
    body = _body()
    scene = _scene(evidence_content=evidence_content, option_label="leave")
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=("threat",),
        evidence_ids=(scene.evidence[0].evidence_id,),
        cue_evidence_bindings=(
            _binding(
                scene.evidence[0],
                "physical_cues",
                "physical_threat",
                "threat",
                cited_text=cited_text,
                assertion_status="mentioned",
            ),
        ),
    )

    prediction = RuleBasedEmbodiedCueInterpreter().infer_effects(
        scene, packet, InstinktWorld.create(), body, scene.options[0]
    )

    assert prediction.abstains is True
    assert prediction.combined_deltas == ()
    assert "cue_assertion_mentioned:physical_threat" in prediction.conflict_flags


@pytest.mark.parametrize(
    "option_label",
    (
        "do not immediately leave",
        "can't safely leave",
        "ne takoj odidi",
    ),
)
def test_clause_scoped_distant_option_negation_fails_closed(
    option_label: str,
) -> None:
    body = _body()
    scene = _scene(
        evidence_content="A physical threat is present.",
        option_label=option_label,
    )
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=("threat",),
        evidence_ids=(scene.evidence[0].evidence_id,),
        cue_evidence_bindings=(
            _binding(
                scene.evidence[0],
                "physical_cues",
                "physical_threat",
                "threat",
            ),
        ),
    )

    prediction = RuleBasedEmbodiedCueInterpreter().infer_effects(
        scene, packet, InstinktWorld.create(), body, scene.options[0]
    )

    assert prediction.abstains is True
    assert prediction.combined_deltas == ()
    assert "option_relation_negated:physical_threat" in prediction.conflict_flags


def test_positive_assertion_after_unrelated_negative_clause_still_emits() -> None:
    body = _body()
    scene = _scene(
        evidence_content="There is no chair; a physical threat is present.",
        option_label="leave",
    )
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=("threat",),
        evidence_ids=(scene.evidence[0].evidence_id,),
        cue_evidence_bindings=(
            _binding(
                scene.evidence[0],
                "physical_cues",
                "physical_threat",
                "threat",
                cited_text="physical threat",
            ),
        ),
    )

    prediction = RuleBasedEmbodiedCueInterpreter().infer_effects(
        scene, packet, InstinktWorld.create(), body, scene.options[0]
    )

    assert prediction.abstains is False
    assert prediction.combined_deltas
    assert {item.cue_class for item in prediction.evidence} == {"physical_threat"}


def test_citation_span_and_hash_tampering_is_rejected() -> None:
    scene = _scene(
        evidence_content="A physical threat is present.",
        option_label="leave",
    )
    valid = _binding(
        scene.evidence[0],
        "physical_cues",
        "physical_threat",
        "threat",
    ).citations[0]

    payload = valid.model_dump(mode="python", round_trip=True)
    payload["start_char"] += 1
    with pytest.raises(ValidationError, match="ID differs|hash differs"):
        InstinktCueEvidenceCitation.model_validate(payload)

    payload = valid.model_dump(mode="python", round_trip=True)
    payload["cited_text_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="text hash differs"):
        InstinktCueEvidenceCitation.model_validate(payload)


def test_character_never_enters_body_mapper() -> None:
    expected = ("self", "scene", "packet", "world", "body", "option")
    protocol_parameters = tuple(
        inspect.signature(EmbodiedCueInterpreter.infer_effects).parameters
    )
    implementation_parameters = tuple(
        inspect.signature(RuleBasedEmbodiedCueInterpreter.infer_effects).parameters
    )

    assert protocol_parameters == expected
    assert implementation_parameters == expected
    assert "character" not in inspect.getsource(
        RuleBasedEmbodiedCueInterpreter.infer_effects
    ).casefold()
    assert isinstance(RuleBasedEmbodiedCueInterpreter(), EmbodiedCueInterpreter)


def test_same_event_different_body_state_can_change_rollout() -> None:
    low_body = _body("body_c5_low", energy=0.2, tension=0.2)
    high_body = _body("body_c5_high", energy=0.8, tension=0.8)
    low = _mapped_threat(body=low_body)
    high = _mapped_threat(body=high_body)

    low_compilation = compile_prediction_to_option_body_effect(
        prediction=low[5], scene=low[0], packet=low[1], world=low[2],
        body=low_body, option=low[0].options[0], ruleset=low[4].ruleset,
        association_records=low[4].association_records,
    )
    high_compilation = compile_prediction_to_option_body_effect(
        prediction=high[5], scene=high[0], packet=high[1], world=high[2],
        body=high_body, option=high[0].options[0], ruleset=high[4].ruleset,
        association_records=high[4].association_records,
    )
    low_result = process_instinkt(
        scene=low[0], packet=low[1], source_body_state=low_body,
        option_effects=(low_compilation.option_body_effect,),
    )
    high_result = process_instinkt(
        scene=high[0], packet=high[1], source_body_state=high_body,
        option_effects=(high_compilation.option_body_effect,),
    )

    assert low_result.rollouts[0].trajectory != high_result.rollouts[0].trajectory
    assert low_result.rollouts[0].rollout_id != high_result.rollouts[0].rollout_id


def test_same_event_different_instinkt_world_can_change_association() -> None:
    with_association = _mapped_threat()[5]
    without_association = _mapped_threat(world=InstinktWorld.create())[5]

    assert all(item.association_ids for item in with_association.evidence)
    assert all(
        item.association_basis == "canonical_default_rule"
        for item in without_association.evidence
    )
    assert all(not item.association_ids for item in without_association.evidence)
    assert with_association.prediction_id != without_association.prediction_id


def test_typed_association_retrieval_scores_all_required_contexts() -> None:
    body = _body()
    scene = _scene(
        evidence_content="Dokazana izdaja je prekinila zaupanje.",
        option_label="zavrni in preveri",
    )
    packet = build_instinkt_packet(
        scene,
        body,
        trust_cues=("izdaja",),
        evidence_ids=("evidence_c5",),
        cue_evidence_bindings=(
            _binding(scene.evidence[0], "trust_cues", "betrayal", "izdaja"),
        ),
    )
    association = InstinktAssociation(
        association_id="association_betrayal_c5",
        cue_signature=("izdaja",),
        body_state_before=body,
        felt_intensity=0.8,
        protected_target="trust and boundary integrity",
        experienced_loss="izguba zaupanja",
        action_taken="zavrni",
        outcome="meja je ostala jasna",
        trust_delta=-0.2,
        attachment_delta=0.0,
        boundary_delta=0.2,
        decay=0.0,
    )
    mapper = RuleBasedEmbodiedCueInterpreter(
        association_records=(association,)
    )
    scoped_world = InstinktWorld.create(
        associations=(association.association_id,)
    )

    prediction = mapper.infer_effects(
        scene, packet, scoped_world, body, scene.options[0]
    )
    match = prediction.evidence[0].association_matches[0]

    assert match.association_id == association.association_id
    assert match.cue_signature_score == 1.0
    assert match.protected_target_score == 1.0
    assert match.body_state_similarity == 1.0
    assert match.loss_context_score == 1.0
    assert match.trust_context_score == 1.0
    assert match.boundary_context_score == 1.0
    assert match.retrieval_score == 1.0
    assert match.association_hash == association.content_hash()

    unscoped_prediction = mapper.infer_effects(
        scene, packet, InstinktWorld.create(), body, scene.options[0]
    )
    assert unscoped_prediction.evidence[0].association_matches == ()
    assert unscoped_prediction.evidence[0].association_ids == ()
    assert unscoped_prediction.evidence[0].association_basis == (
        "canonical_default_rule"
    )


def test_typed_loss_class_tags_are_exact_before_legacy_fuzzy_matching() -> None:
    body = _body()
    scene = _scene(
        evidence_content="A grounded physical threat is present.",
        option_label="leave",
    )
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=("physical threat",),
        evidence_ids=("evidence_c5",),
        cue_evidence_bindings=(
            _binding(
                scene.evidence[0],
                "physical_cues",
                "physical_threat",
                "physical threat",
            ),
        ),
    )

    def mapped_loss_score(experienced_loss: str) -> float:
        association = InstinktAssociation(
            association_id=f"association_{experienced_loss.replace(':', '_')}",
            cue_signature=("physical_threat",),
            body_state_before=body,
            felt_intensity=0.8,
            protected_target="virtual bodily integrity",
            experienced_loss=experienced_loss,
            action_taken="leave",
            outcome="recorded outcome",
            trust_delta=0.0,
            attachment_delta=0.0,
            boundary_delta=0.0,
            decay=0.0,
        )
        mapper = RuleBasedEmbodiedCueInterpreter(
            association_records=(association,)
        )
        prediction = mapper.infer_effects(
            scene,
            packet,
            InstinktWorld.create(associations=(association.association_id,)),
            body,
            scene.options[0],
        )
        return prediction.evidence[0].association_matches[0].loss_context_score

    assert mapped_loss_score("loss_class:physical_threat") == 1.0
    assert mapped_loss_score("loss_class:betrayal threat") == 0.0


def test_slovenian_semantic_cues_map_without_translation_layer() -> None:
    body = _body()
    scene = _scene(
        evidence_content="Prisotna je nevarnost, vendar je izhod jasno viden.",
        option_label="odidi skozi izhod",
    )
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=("nevarnost",),
        escape_cues=("izhod",),
        evidence_ids=("evidence_c5",),
        cue_evidence_bindings=(
            _binding(
                scene.evidence[0], "physical_cues", "physical_threat", "nevarnost"
            ),
            _binding(
                scene.evidence[0],
                "escape_cues",
                "escape_availability",
                "izhod",
            ),
        ),
    )
    mapper = RuleBasedEmbodiedCueInterpreter()

    prediction = mapper.infer_effects(
        scene, packet, InstinktWorld.create(), body, scene.options[0]
    )

    assert prediction.abstains is False
    assert {item.cue_class for item in prediction.evidence} == {
        "physical_threat", "escape_availability"
    }
    assert all(
        item.association_basis == "canonical_default_rule"
        for item in prediction.evidence
    )


def test_conflicting_cues_remain_multidimensional() -> None:
    body = _body()
    scene = _scene(
        evidence_content="The move creates family separation.",
        option_label="leave and move",
    )
    packet = build_instinkt_packet(
        scene,
        body,
        attachment_cues=("family", "separation"),
        evidence_ids=("evidence_c5",),
        cue_evidence_bindings=(
            _binding(scene.evidence[0], "attachment_cues", "attachment", "family"),
            _binding(
                scene.evidence[0],
                "attachment_cues",
                "abandonment",
                "separation",
            ),
        ),
    )
    world = InstinktWorld.create(associations=("family", "separation"))
    mapper = RuleBasedEmbodiedCueInterpreter()

    prediction = mapper.infer_effects(scene, packet, world, body, scene.options[0])
    dimensions = {item.dimension for item in prediction.combined_deltas}

    assert prediction.abstains is False
    assert {item.cue_class for item in prediction.evidence} == {
        "attachment", "abandonment"
    }
    assert "cue_conflict:attachment:abandonment" in prediction.conflict_flags
    assert dimensions == {"arousal", "uncertainty", "attachment_security"}
    assert not hasattr(prediction, "risk_score")


def test_manual_fixture_and_auto_mapper_can_be_compared() -> None:
    scene, packet, world, body, mapper, prediction = _mapped_threat()
    compilation = compile_prediction_to_option_body_effect(
        prediction=prediction,
        scene=scene,
        packet=packet,
        world=world,
        body=body,
        option=scene.options[0],
        ruleset=mapper.ruleset,
        association_records=mapper.association_records,
    )
    automatic = compilation.option_body_effect
    manual = InstinktEffectSpec(
        option_id=automatic.option_id,
        body_deltas=automatic.body_deltas,
        base_predicted_loss=automatic.base_predicted_loss,
        base_recoverability=automatic.base_recoverability,
        dominant_alarm=automatic.dominant_alarm,
        protected_targets=automatic.protected_targets,
        boundary_outcome=automatic.boundary_outcome,
        trust_outcome=automatic.trust_outcome,
        attachment_outcome=automatic.attachment_outcome,
        escape_outcome=automatic.escape_outcome,
        action_tendency=automatic.action_tendency,
        minimum_safety_condition=automatic.minimum_safety_condition,
        association_cue_tokens=automatic.association_cue_tokens,
        triggering_evidence_ids=automatic.triggering_evidence_ids,
    ).bind(packet)

    assert manual == automatic
    assert prediction.effect_source == "rule_based"


def test_no_medical_diagnosis_fields() -> None:
    forbidden = {"diagnosis", "disease", "disorder", "patient", "treatment"}
    models = (
        BodyEffectEvidence,
        OptionBodyEffectPrediction,
        OptionBodyEffectCompilation,
    )
    assert all(not (forbidden & set(model.model_fields)) for model in models)

    prediction = _mapped_threat()[5]
    all_keys: set[str] = set()

    def collect_keys(value) -> None:
        if isinstance(value, dict):
            all_keys.update(str(key).casefold() for key in value)
            for item in value.values():
                collect_keys(item)
        elif isinstance(value, list):
            for item in value:
                collect_keys(item)

    collect_keys(prediction.model_dump(mode="json"))
    assert not (forbidden & all_keys)


def test_all_sixteen_cue_classes_are_configured_and_content_addressed() -> None:
    ruleset = load_instinkt_effect_rules()
    assert tuple(rule.cue_class for rule in ruleset.rules) == EMBODIED_CUE_CLASSES
    assert len(ruleset.rules) == 16
    assert len({rule.rule_id for rule in ruleset.rules}) == 16
    assert len(ruleset.ruleset_hash) == 64


def test_prediction_hash_tampering_is_rejected() -> None:
    prediction = _mapped_threat()[5]
    tampered = prediction.model_dump(mode="python", round_trip=True)
    tampered["uncertainty"] = "tampered"
    with pytest.raises(ValidationError, match="prediction_id differs"):
        OptionBodyEffectPrediction.model_validate(tampered)


def test_content_addressed_instinkt_world_rejects_direct_content_tampering() -> None:
    world = InstinktWorld.create(threat_patterns=("grounded threat",))
    tampered = world.model_dump(mode="python", round_trip=True)
    tampered["threat_patterns"] = ("substituted threat",)

    with pytest.raises(ValidationError, match="ID differs from its content"):
        InstinktWorld.model_validate(tampered)

    legacy = InstinktWorld(
        world_id="legacy_opaque_instinkt_world",
        associations=(),
        trusted_patterns=(),
        threat_patterns=("legacy fixture value",),
        attachment_objects=(),
        unresolved_losses=(),
        boundary_patterns=(),
    )
    assert legacy.world_id == "legacy_opaque_instinkt_world"


def test_compiler_selects_dominant_rule_by_confidence_weighted_loss() -> None:
    body = _body()
    scene = SceneEvent(
        event_id="event_weighted_dominant_rule",
        raw_input="A threat is reported while the situation remains unknown.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="weak_threat_evidence",
                modality="text",
                content="A threat is reported.",
                grounded=True,
                source_ref="fixture:weak-threat",
                confidence=0.1,
            ),
            EvidenceItem(
                evidence_id="strong_unknown_evidence",
                modality="text",
                content="The outcome remains unknown.",
                grounded=True,
                source_ref="fixture:strong-unknown",
                confidence=0.9,
            ),
        ),
        options=(
            DecisionOption(
                option_id="leave_and_verify",
                label="leave and verify",
                description="Leave and verify the unknown situation.",
            ),
        ),
    )
    packet = build_instinkt_packet(
        scene,
        body,
        physical_cues=("threat",),
        uncertainty_cues=("unknown",),
        evidence_ids=("weak_threat_evidence", "strong_unknown_evidence"),
        cue_evidence_bindings=(
            _binding(
                scene.evidence[0], "physical_cues", "physical_threat", "threat"
            ),
            _binding(
                scene.evidence[1], "uncertainty_cues", "uncertainty", "unknown"
            ),
        ),
    )
    world = InstinktWorld.create()
    mapper = RuleBasedEmbodiedCueInterpreter()
    prediction = mapper.infer_effects(
        scene, packet, world, body, scene.options[0]
    )
    compilation = compile_prediction_to_option_body_effect(
        prediction=prediction,
        scene=scene,
        packet=packet,
        world=world,
        body=body,
        option=scene.options[0],
        ruleset=mapper.ruleset,
    )

    assert compilation.option_body_effect.base_predicted_loss == pytest.approx(0.315)
    assert compilation.option_body_effect.dominant_alarm == (
        "grounded uncertainty cue"
    )


def test_instinkt_packet_rejects_oversized_cue_lane_before_mapping() -> None:
    body = _body()
    scene = _scene(evidence_content="A bounded fixture.", option_label="proceed")

    with pytest.raises(ValidationError, match="cue lane exceeds"):
        build_instinkt_packet(
            scene,
            body,
            physical_cues=tuple(f"cue-{index}" for index in range(65)),
        )


def test_model_backed_mapper_is_an_explicitly_disabled_stub() -> None:
    scene, packet, world, body, _, _ = _mapped_threat()
    stub = ModelBackedEmbodiedCueInterpreterStub()
    assert isinstance(stub, EmbodiedCueInterpreter)
    with pytest.raises(ModelBackedEffectInferenceDisabledError, match="disabled C5 stub"):
        stub.infer_effects(scene, packet, world, body, scene.options[0])
