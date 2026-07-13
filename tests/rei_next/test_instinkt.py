from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel, ValidationError

from app.backend.rei_next.ids import content_id, sha256_hex
from app.backend.rei_next.instinkt import (
    AssociationMemoryConfig,
    BoundedAssociativeMemory,
    ProtectivePolicyDecision,
    build_native_conclusion,
    process_instinkt,
    protective_cost,
    simulate_option_rollout,
)
from app.backend.rei_next.models.communication import InstinktManifestation
from app.backend.rei_next.models.character import CharacterAuthority
from app.backend.rei_next.models.instinkt import (
    BODY_DIMENSIONS,
    BodyDelta,
    BodyState,
    BodyTransition,
    InstinktActionTendency,
    InstinktAssociation,
    InstinktInputPacket,
    InstinktNativeConclusion,
    InstinktOptionRollout,
    InstinktSimulationConfig,
    OptionBodyEffect,
)
from app.backend.rei_next.models.scene import (
    DecisionOption,
    EvidenceItem,
    SceneEvent,
)


def _scene(
    option_ids: tuple[str, ...] = ("option_calm", "option_replenish"),
    *,
    event_id: str = "event_b8",
    raw_input: str = "Explicit bounded decision event.",
) -> SceneEvent:
    return SceneEvent(
        event_id=event_id,
        raw_input=raw_input,
        language="sl",
        evidence=(
            EvidenceItem(
                evidence_id="evidence_b8",
                modality="text",
                content="Grounded event evidence.",
                grounded=True,
                source_ref=f"user:{event_id}",
                confidence=1.0,
            ),
        ),
        options=tuple(
            DecisionOption(option_id=option_id, label=option_id)
            for option_id in option_ids
        ),
    )


def _body(body_state_id: str = "body_b8", **overrides: float) -> BodyState:
    values = {
        "energy": 0.5,
        "fatigue": 0.5,
        "pain": 0.5,
        "arousal": 0.5,
        "tension": 0.5,
        "physical_integrity": 0.5,
        "uncertainty": 0.5,
        "trust": 0.5,
        "attachment_security": 0.5,
        "resource_security": 0.5,
        "boundary_integrity": 0.5,
        "escape_availability": 0.5,
        "predictability": 0.5,
    }
    values.update(overrides)
    return BodyState(body_state_id=body_state_id, **values)


def _packet(
    scene: SceneEvent,
    body: BodyState,
    *,
    packet_id: str = "packet_b8",
    physical_cues: tuple[str, ...] = (),
) -> InstinktInputPacket:
    return InstinktInputPacket(
        packet_id=packet_id,
        scene_id=scene.event_id,
        source_body_state_id=body.body_state_id,
        physical_cues=physical_cues,
        uncertainty_cues=(),
        trust_cues=(),
        boundary_cues=(),
        attachment_cues=(),
        scarcity_cues=(),
        escape_cues=(),
        explicit_body_cues=(),
        option_ids=tuple(option.option_id for option in scene.options),
        evidence_ids=("evidence_b8",),
        caveat="Conceptual bounded virtual-body simulation.",
    )


def _effect(
    packet: InstinktInputPacket,
    option_id: str,
    *,
    deltas: tuple[tuple[str, float], ...] = (),
    base_loss: float = 0.3,
    base_recoverability: float = 0.5,
    association_tokens: tuple[str, ...] = (),
    action_tendency: InstinktActionTendency = "protect",
) -> OptionBodyEffect:
    return OptionBodyEffect.create(
        packet=packet,
        option_id=option_id,
        body_deltas=tuple(
            BodyDelta(dimension=dimension, delta=delta)
            for dimension, delta in deltas
        ),
        base_predicted_loss=base_loss,
        base_recoverability=base_recoverability,
        dominant_alarm=f"alarm:{option_id}",
        protected_targets=("integrity",),
        boundary_outcome="explicitly supplied boundary outcome",
        trust_outcome="explicitly supplied trust outcome",
        attachment_outcome="explicitly supplied attachment outcome",
        escape_outcome="explicitly supplied escape outcome",
        action_tendency=action_tendency,
        minimum_safety_condition="explicitly supplied minimum safety condition",
        association_cue_tokens=association_tokens,
        triggering_evidence_ids=("evidence_b8",),
    )


def _flip_effects(packet: InstinktInputPacket) -> tuple[OptionBodyEffect, ...]:
    return (
        _effect(
            packet,
            "option_calm",
            deltas=(("energy", -1.0), ("tension", -1.0)),
            action_tendency="conserve",
        ),
        _effect(
            packet,
            "option_replenish",
            deltas=(("energy", 1.0),),
            action_tendency="seek_safety",
        ),
    )


def _association(
    association_id: str,
    body: BodyState,
    *,
    cue_signature: tuple[str, ...] = ("bridge",),
    strength: float = 0.8,
    decay: float = 0.0,
    experienced_loss: str | None = "recorded loss",
) -> InstinktAssociation:
    return InstinktAssociation(
        association_id=association_id,
        cue_signature=cue_signature,
        body_state_before=body,
        felt_intensity=strength,
        protected_target="integrity",
        experienced_loss=experienced_loss,
        action_taken="withdraw",
        outcome="bounded memory record",
        trust_delta=0.0,
        attachment_delta=0.0,
        boundary_delta=0.0,
        decay=decay,
    )


def _assert_normalized(state: BodyState) -> None:
    assert all(0.0 <= getattr(state, dimension) <= 1.0 for dimension in BODY_DIMENSIONS)


def _rehashed_artifact_payload(
    artifact: BaseModel,
    *,
    id_field: str,
    hash_field: str,
    id_prefix: str,
    updates: dict[str, object],
) -> dict[str, object]:
    base = artifact.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, hash_field},
    )
    base.update(updates)
    artifact_id = content_id(id_prefix, base)
    payload = {id_field: artifact_id, **base}
    return {**payload, hash_field: sha256_hex(payload)}


def test_simulation_config_is_content_addressed_and_bounded() -> None:
    config = InstinktSimulationConfig.create()

    assert config.rollout_steps == 3
    assert config.max_options == 16
    assert config.max_abs_delta_per_step == 0.25
    assert config.config_hash == config.content_hash(
        exclude_fields=frozenset({"config_hash"})
    )
    with pytest.raises(ValidationError, match="weights must each sum to one"):
        InstinktSimulationConfig.create(loss_base_weight=0.4)
    with pytest.raises(ValidationError):
        InstinktSimulationConfig.create(rollout_steps=9)
    with pytest.raises(ValidationError):
        InstinktSimulationConfig.create(max_options=33)

    payload = config.model_dump(mode="python", round_trip=True)
    payload["config_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="config_hash"):
        InstinktSimulationConfig(**payload)


def test_virtual_body_rollouts_are_deterministic_normalized_and_auditable() -> None:
    scene = _scene()
    body = _body("body_deterministic", energy=1.0, tension=1.0)
    packet = _packet(scene, body, packet_id="packet_deterministic")
    effects = _flip_effects(packet)
    config = InstinktSimulationConfig.create()

    first = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=effects,
        config=config,
        body_locations=("chest", "chest", "hands"),
    )
    second = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=effects,
        config=config,
        body_locations=("chest", "chest", "hands"),
    )

    assert first == second
    assert first.config == config
    assert first.conclusion.option_id == "option_calm"
    assert first.manifestation.source_conclusion_id == first.conclusion.conclusion_id
    assert first.manifestation.body_locations == ("chest", "hands")
    assert first.manifestation.raw_urge.startswith("structured_tendency:")
    for rollout in first.rollouts:
        assert rollout.simulation_status == "simulated_v1"
        assert rollout.source_packet_id == packet.packet_id
        assert rollout.source_packet_hash == packet.content_hash()
        assert rollout.source_body_state_id == body.body_state_id
        assert rollout.source_body_state_hash == body.content_hash()
        assert len(rollout.transitions) == config.rollout_steps
        assert len(rollout.trajectory) == config.rollout_steps + 1
        assert 0.0 <= rollout.predicted_loss <= 1.0
        assert 0.0 <= rollout.recoverability <= 1.0
        assert rollout.rollout_hash == rollout.content_hash(
            exclude_fields=frozenset({"rollout_hash"})
        )
        for state in rollout.trajectory:
            _assert_normalized(state)
        for transition in rollout.transitions:
            assert transition.simulation_status == "simulated_v1"
            assert transition.transition_hash == transition.content_hash(
                exclude_fields=frozenset({"transition_hash"})
            )
            assert all(
                abs(delta.delta) <= config.max_abs_delta_per_step
                for delta in transition.deltas
            )
            transition.validate_simulation_lineage(
                packet=packet,
                effect=next(
                    effect
                    for effect in effects
                    if effect.option_id == rollout.option_id
                ),
                config=config,
            )


def test_body_updates_clamp_values_and_per_step_deltas() -> None:
    scene = _scene(("option_clamp",))
    body = _body("body_clamp", energy=0.95, pain=0.95, tension=0.05)
    packet = _packet(scene, body, packet_id="packet_clamp")
    effect = _effect(
        packet,
        "option_clamp",
        deltas=(("energy", 1.0), ("pain", 1.0), ("tension", -1.0)),
    )
    config = InstinktSimulationConfig.create(
        rollout_steps=8,
        max_abs_delta_per_step=0.1,
    )

    rollout = simulate_option_rollout(
        packet=packet,
        source_body_state=body,
        effect=effect,
        config=config,
    )

    assert len(rollout.transitions) == 8
    assert rollout.trajectory[-1].energy == 1.0
    assert rollout.trajectory[-1].pain == 1.0
    assert rollout.trajectory[-1].tension == 0.0
    for transition in rollout.transitions:
        assert all(abs(delta.delta) <= 0.1 for delta in transition.deltas)
        _assert_normalized(transition.to_state)


def test_same_event_with_different_body_state_can_change_instinkt_choice() -> None:
    scene = _scene()
    high_tension = _body("body_high", energy=1.0, tension=1.0)
    depleted = _body("body_depleted", energy=0.0, tension=0.0)
    high_packet = _packet(scene, high_tension, packet_id="packet_high")
    depleted_packet = _packet(scene, depleted, packet_id="packet_depleted")

    high_result = process_instinkt(
        scene=scene,
        packet=high_packet,
        source_body_state=high_tension,
        option_effects=_flip_effects(high_packet),
    )
    depleted_result = process_instinkt(
        scene=scene,
        packet=depleted_packet,
        source_body_state=depleted,
        option_effects=_flip_effects(depleted_packet),
    )

    assert high_result.conclusion.option_id == "option_calm"
    assert depleted_result.conclusion.option_id == "option_replenish"
    assert high_result.conclusion.option_id != depleted_result.conclusion.option_id


def test_structural_character_is_neither_input_nor_mutable_by_instinkt() -> None:
    parameter_names = set(inspect.signature(process_instinkt).parameters)
    assert not parameter_names & {"character", "character_authority", "profile_id"}
    for model in (InstinktInputPacket, OptionBodyEffect, InstinktSimulationConfig):
        assert not set(model.model_fields) & {
            "character",
            "character_authority",
            "profile_id",
        }

    character = CharacterAuthority(
        character_id="character_b8",
        profile_id="R>E>I",
        authority_tiers=(("R",), ("E",), ("I",)),
        rule="ordered_top",
    )
    character_before = character.model_dump_json()
    scene = _scene()
    body = _body("body_character", energy=1.0, tension=1.0)
    packet = _packet(scene, body, packet_id="packet_character")
    process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=_flip_effects(packet),
    )

    assert character.model_dump_json() == character_before
    with pytest.raises(ValidationError, match="frozen"):
        character.profile_id = "I>E>R"  # type: ignore[misc]


def test_only_typed_effects_drive_scoring_not_raw_text_keywords() -> None:
    body = _body("body_text_independence", energy=1.0, tension=1.0)
    alarming_scene = _scene(
        event_id="event_b8_alarming",
        raw_input="DANGER DEATH PANIC WITHDRAW NOW",
    )
    neutral_scene = _scene(
        event_id="event_b8_neutral",
        raw_input="A quiet garden and ordinary weather.",
    )
    alarming_packet = _packet(
        alarming_scene,
        body,
        packet_id="packet_alarming_text",
        physical_cues=("DANGER DEATH PANIC",),
    )
    neutral_packet = _packet(
        neutral_scene,
        body,
        packet_id="packet_neutral_text",
        physical_cues=("quiet garden",),
    )

    alarming = process_instinkt(
        scene=alarming_scene,
        packet=alarming_packet,
        source_body_state=body,
        option_effects=_flip_effects(alarming_packet),
    )
    neutral = process_instinkt(
        scene=neutral_scene,
        packet=neutral_packet,
        source_body_state=body,
        option_effects=_flip_effects(neutral_packet),
    )

    assert alarming.conclusion.option_id == neutral.conclusion.option_id
    assert tuple(
        (rollout.predicted_loss, rollout.recoverability)
        for rollout in alarming.rollouts
    ) == tuple(
        (rollout.predicted_loss, rollout.recoverability)
        for rollout in neutral.rollouts
    )
    with pytest.raises(ValueError, match="cover every packet option"):
        process_instinkt(
            scene=alarming_scene,
            packet=alarming_packet,
            source_body_state=body,
            option_effects=(_flip_effects(alarming_packet)[0],),
        )


def test_associative_memory_uses_exact_tokens_and_visible_linear_decay() -> None:
    body = _body("body_memory_decay")
    memory = BoundedAssociativeMemory(
        AssociationMemoryConfig(
            capacity=3,
            retrieval_limit=2,
            minimum_effective_strength=0.05,
        )
    )
    memory.add(
        _association(
            "association_decay",
            body,
            cue_signature=("bridge", "noise"),
            strength=0.9,
            decay=0.1,
        )
    )

    initial = memory.retrieve(("BRIDGE",))
    assert len(initial) == 1
    assert initial[0].effective_strength == pytest.approx(0.9)
    assert initial[0].retrieval_score == pytest.approx(0.45)
    assert memory.retrieve(("bridges",)) == ()

    memory.advance(3)
    decayed = memory.retrieve((" bridge ",))
    assert decayed[0].age_cycles == 3
    assert decayed[0].effective_strength == pytest.approx(0.6)
    assert decayed[0].retrieval_score == pytest.approx(0.3)
    assert decayed[0].match_id != initial[0].match_id

    memory.advance(6)
    assert memory.retrieve(("bridge",)) == ()


def test_associative_memory_enforces_capacity_retrieval_limit_and_eviction() -> None:
    body = _body("body_memory_capacity")
    memory = BoundedAssociativeMemory(
        AssociationMemoryConfig(
            capacity=2,
            retrieval_limit=1,
            minimum_effective_strength=0.0,
        )
    )
    memory.add(_association("association_high", body, strength=0.8))
    memory.add(_association("association_weak", body, strength=0.1))
    memory.add(_association("association_mid", body, strength=0.5))

    assert tuple(item.association_id for item in memory.associations) == (
        "association_high",
        "association_mid",
    )
    matches = memory.retrieve(("bridge",))
    assert len(matches) == 1
    assert matches[0].association_id == "association_high"
    with pytest.raises(ValueError, match="cannot be replaced"):
        memory.add(_association("association_high", body, strength=0.9))
    with pytest.raises(ValueError, match="bounded range"):
        memory.advance(1_000_001)


def test_loss_memory_changes_loss_and_recoverability_with_auditable_lineage() -> None:
    scene = _scene(("option_bridge",))
    body = _body("body_memory_effect")
    packet = _packet(scene, body, packet_id="packet_memory_effect")
    effect = _effect(
        packet,
        "option_bridge",
        base_loss=0.1,
        base_recoverability=0.8,
        association_tokens=("bridge",),
    )
    memory = BoundedAssociativeMemory()
    memory.add(
        _association(
            "association_loss",
            body,
            strength=0.8,
            experienced_loss="visible prior loss",
        )
    )

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

    plain_rollout = without_memory.rollouts[0]
    memory_rollout = with_memory.rollouts[0]
    assert memory_rollout.predicted_loss - plain_rollout.predicted_loss == pytest.approx(
        0.2 * 0.8
    )
    assert plain_rollout.recoverability - memory_rollout.recoverability == pytest.approx(
        0.2 * 0.8
    )
    match = with_memory.association_matches[0].matches[0]
    assert memory_rollout.association_match_ids == (match.match_id,)
    assert match.association_hash == memory.associations[0].content_hash()
    assert match.carries_experienced_loss is True


def test_equal_protective_cost_abstains_independent_of_input_order() -> None:
    scene = _scene(("option_a", "option_b"))
    body = _body("body_tie")
    packet = _packet(scene, body, packet_id="packet_tie")
    effects = (
        _effect(packet, "option_a", deltas=()),
        _effect(packet, "option_b", deltas=()),
    )

    forward = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=effects,
    )
    reversed_input = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=tuple(reversed(effects)),
    )

    assert forward == reversed_input
    assert forward.policy.status == "abstained_tie"
    assert forward.policy.tied_option_ids == ("option_a", "option_b")
    assert forward.conclusion.abstains is True
    assert forward.conclusion.option_id is None
    assert forward.conclusion.decisive_rollout_id is None
    assert all(
        0.0 <= rollout.predicted_loss <= 1.0
        and 0.0 <= rollout.recoverability <= 1.0
        for rollout in forward.rollouts
    )


def test_rollout_and_transition_lineage_reject_tampering() -> None:
    scene = _scene(("option_a",))
    body = _body("body_tamper")
    packet = _packet(scene, body, packet_id="packet_tamper")
    effect = _effect(packet, "option_a")
    result = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(effect,),
    )
    rollout = result.rollouts[0]
    transition = rollout.transitions[0]

    transition_payload = transition.model_dump(mode="python", round_trip=True)
    transition_payload["transition_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="transition_hash"):
        BodyTransition(**transition_payload)

    rollout_payload = rollout.model_dump(mode="python", round_trip=True)
    rollout_payload["predicted_loss"] = rollout.predicted_loss / 2.0
    with pytest.raises(ValidationError, match="rollout_id|rollout_hash"):
        InstinktOptionRollout(**rollout_payload)


def test_all_loops_and_counts_are_explicitly_bounded() -> None:
    source = inspect.getsource(simulate_option_rollout)
    assert "while " not in source
    assert "range(1, config.rollout_steps + 1)" in source

    option_ids = tuple(f"option_{index:02d}" for index in range(17))
    scene = _scene(option_ids)
    body = _body("body_option_bound")
    packet = _packet(scene, body, packet_id="packet_option_bound")
    with pytest.raises(ValueError, match="finite bound"):
        process_instinkt(
            scene=scene,
            packet=packet,
            source_body_state=body,
            option_effects=(),
        )


def test_rehashed_wrong_transition_is_rejected_by_numeric_replay() -> None:
    scene = _scene(("option_replay",))
    body = _body("body_transition_replay", energy=0.2)
    packet = _packet(scene, body, packet_id="packet_transition_replay")
    effect = _effect(
        packet,
        "option_replay",
        deltas=(("energy", 0.3),),
    )
    config = InstinktSimulationConfig.create()
    rollout = simulate_option_rollout(
        packet=packet,
        source_body_state=body,
        effect=effect,
        config=config,
    )
    transition = rollout.transitions[0]
    wrong_state_payload = transition.to_state.model_dump(
        mode="python",
        round_trip=True,
    )
    wrong_state_payload.update(
        body_state_id="body_forged_transition",
        energy=0.4,
    )
    wrong_state = BodyState(**wrong_state_payload)
    forged = BodyTransition(
        **_rehashed_artifact_payload(
            transition,
            id_field="transition_id",
            hash_field="transition_hash",
            id_prefix="body_transition",
            updates={
                "to_state": wrong_state,
                "deltas": (BodyDelta(dimension="energy", delta=0.2),),
            },
        )
    )

    assert forged.transition_hash == forged.content_hash(
        exclude_fields=frozenset({"transition_hash"})
    )
    with pytest.raises(ValueError, match="does not replay"):
        forged.validate_simulation_lineage(
            packet=packet,
            effect=effect,
            config=config,
        )


@pytest.mark.parametrize(
    ("field_name", "error"),
    (
        ("predicted_loss", "predicted_loss does not replay"),
        ("recoverability", "recoverability does not replay"),
    ),
)
def test_rehashed_wrong_rollout_scores_are_rejected_by_numeric_replay(
    field_name: str,
    error: str,
) -> None:
    scene = _scene(("option_score_replay",))
    body = _body("body_score_replay")
    packet = _packet(scene, body, packet_id="packet_score_replay")
    effect = _effect(
        packet,
        "option_score_replay",
        base_loss=0.7,
        base_recoverability=0.2,
    )
    config = InstinktSimulationConfig.create()
    rollout = simulate_option_rollout(
        packet=packet,
        source_body_state=body,
        effect=effect,
        config=config,
    )
    original = getattr(rollout, field_name)
    wrong_value = 0.0 if original != 0.0 else 1.0
    forged = InstinktOptionRollout(
        **_rehashed_artifact_payload(
            rollout,
            id_field="rollout_id",
            hash_field="rollout_hash",
            id_prefix="instinkt_rollout",
            updates={field_name: wrong_value},
        )
    )

    assert forged.rollout_hash == forged.content_hash(
        exclude_fields=frozenset({"rollout_hash"})
    )
    with pytest.raises(ValueError, match=error):
        forged.validate_simulation_lineage(
            packet=packet,
            source_body_state=body,
            effect=effect,
            config=config,
            association_matches=(),
        )


def test_packet_and_rollout_reject_foreign_source_body_state() -> None:
    scene = _scene(("option_source",))
    body = _body("body_source")
    packet = _packet(scene, body, packet_id="packet_source")
    effect = _effect(packet, "option_source")
    config = InstinktSimulationConfig.create()

    with pytest.raises(ValueError, match="another source BodyState"):
        simulate_option_rollout(
            packet=packet,
            source_body_state=_body("body_foreign"),
            effect=effect,
            config=config,
        )

    rollout = simulate_option_rollout(
        packet=packet,
        source_body_state=body,
        effect=effect,
        config=config,
    )
    same_id_different_content = _body(body.body_state_id, energy=0.9)
    with pytest.raises(ValueError, match="BodyState hash differs"):
        rollout.validate_simulation_lineage(
            packet=packet,
            source_body_state=same_id_different_content,
            effect=effect,
            config=config,
            association_matches=(),
        )


def test_policy_penalty_sum_above_declared_cost_bound_is_rejected() -> None:
    config = InstinktSimulationConfig.create()
    assert (
        config.policy_recoverability_penalty
        + config.policy_tension_penalty
        + config.policy_uncertainty_penalty
        == pytest.approx(0.5)
    )

    with pytest.raises(ValidationError, match="penalties must sum to at most 0.5"):
        InstinktSimulationConfig.create(
            policy_recoverability_penalty=0.3,
            policy_tension_penalty=0.2,
            policy_uncertainty_penalty=0.1,
        )


def test_foreign_or_rehashed_tampered_policy_is_rejected() -> None:
    scene = _scene(("option_policy",))
    body = _body("body_policy")
    packet = _packet(scene, body, packet_id="packet_policy")
    effect = _effect(packet, "option_policy")
    result = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(effect,),
    )

    foreign_scene = _scene(("option_policy",), event_id="event_foreign_policy")
    foreign_body = _body("body_foreign_policy")
    foreign_packet = _packet(
        foreign_scene,
        foreign_body,
        packet_id="packet_foreign_policy",
    )
    foreign_effect = _effect(foreign_packet, "option_policy")
    foreign_policy = process_instinkt(
        scene=foreign_scene,
        packet=foreign_packet,
        source_body_state=foreign_body,
        option_effects=(foreign_effect,),
    ).policy
    tampered_policy = ProtectivePolicyDecision(
        **_rehashed_artifact_payload(
            result.policy,
            id_field="policy_decision_id",
            hash_field="policy_hash",
            id_prefix="instinkt_policy",
            updates={"source_packet_hash": "0" * 64},
        )
    )

    for invalid_policy in (foreign_policy, tampered_policy):
        with pytest.raises(ValueError, match="differs from the supplied B8 inputs"):
            build_native_conclusion(
                packet=packet,
                source_body_state=body,
                effects=(effect,),
                rollouts=result.rollouts,
                policy=invalid_policy,
                config=result.config,
            )


def test_no_options_returns_structured_abstention() -> None:
    scene = _scene(())
    body = _body("body_no_options", tension=0.7, arousal=0.3)
    packet = _packet(scene, body, packet_id="packet_no_options")

    result = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(),
    )

    assert result.rollouts == ()
    assert result.association_matches == ()
    assert result.policy.status == "abstained_no_options"
    assert result.policy.option_scores == ()
    assert result.conclusion.abstains is True
    assert result.conclusion.option_id is None
    assert result.conclusion.decisive_rollout_id is None
    assert result.conclusion.dominant_alarm == "no_explicit_options"
    assert result.conclusion.danger_claims == ()
    assert result.conclusion.action_tendency == "unknown"
    assert result.conclusion.intensity == 0.0
    assert result.manifestation.source_body_state_id == body.body_state_id
    assert result.manifestation.source_body_state_hash == body.content_hash()
    assert result.manifestation.source_decisive_rollout_id is None
    assert result.manifestation.raw_urge == "structured_tendency:unknown"


def test_manifestation_uses_decisive_final_body_and_replays_numeric_fields() -> None:
    scene = _scene(("option_manifest",))
    body = _body(
        "body_manifest_source",
        tension=0.2,
        arousal=0.6,
        attachment_security=0.25,
        boundary_integrity=0.4,
    )
    packet = _packet(scene, body, packet_id="packet_manifest")
    effect = _effect(
        packet,
        "option_manifest",
        deltas=(
            ("tension", 0.3),
            ("attachment_security", 0.3),
            ("boundary_integrity", 0.3),
        ),
        action_tendency="seek_safety",
    )
    result = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(effect,),
    )
    rollout = result.rollouts[0]
    final_body = rollout.trajectory[-1]
    manifestation = result.manifestation

    assert final_body != body
    assert manifestation.source_body_state_id == final_body.body_state_id
    assert manifestation.source_body_state_hash == final_body.content_hash()
    assert manifestation.source_decisive_rollout_id == rollout.rollout_id
    assert manifestation.source_decisive_rollout_hash == rollout.rollout_hash
    assert manifestation.felt_tension == pytest.approx(final_body.tension)
    assert manifestation.fear_intensity == pytest.approx(
        0.50 * result.conclusion.intensity
        + 0.30 * final_body.tension
        + 0.20 * final_body.arousal
    )
    assert manifestation.attachment_pull == pytest.approx(
        (1.0 - final_body.attachment_security) * result.conclusion.intensity
    )
    assert manifestation.withdrawal_urge == pytest.approx(result.conclusion.intensity)
    assert manifestation.freeze_intensity == 0.0
    assert manifestation.boundary_alarm == pytest.approx(
        1.0 - final_body.boundary_integrity
    )
    with pytest.raises(ValueError, match="BodyState lineage differs"):
        manifestation.validate_against(result.conclusion, body, rollout)

    wrong_fear = 0.0 if manifestation.fear_intensity != 0.0 else 1.0
    forged = InstinktManifestation(
        **_rehashed_artifact_payload(
            manifestation,
            id_field="manifestation_id",
            hash_field="manifestation_hash",
            id_prefix="instinkt_manifestation",
            updates={"fear_intensity": wrong_fear},
        )
    )
    with pytest.raises(ValueError, match="fear_intensity does not replay"):
        forged.validate_against(result.conclusion, final_body, rollout)


def test_association_influence_uses_retrieval_score_not_effective_strength() -> None:
    scene = _scene(("option_bridge",))
    body = _body("body_retrieval_score")
    packet = _packet(scene, body, packet_id="packet_retrieval_score")
    effect = _effect(
        packet,
        "option_bridge",
        base_loss=0.1,
        base_recoverability=0.8,
        association_tokens=("bridge",),
    )
    memory = BoundedAssociativeMemory()
    memory.add(
        _association(
            "association_partial_overlap",
            body,
            cue_signature=("bridge", "noise"),
            strength=0.8,
            experienced_loss="visible prior loss",
        )
    )

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

    match = with_memory.association_matches[0].matches[0]
    assert match.effective_strength == pytest.approx(0.8)
    assert match.retrieval_score == pytest.approx(0.4)
    assert with_memory.rollouts[0].association_matches == (match,)
    assert (
        with_memory.rollouts[0].predicted_loss
        - without_memory.rollouts[0].predicted_loss
        == pytest.approx(with_memory.config.association_loss_weight * 0.4)
    )
    assert (
        without_memory.rollouts[0].recoverability
        - with_memory.rollouts[0].recoverability
        == pytest.approx(with_memory.config.association_recovery_penalty * 0.4)
    )


def test_default_numeric_policy_has_independent_exact_expected_outputs() -> None:
    scene = _scene(("option_exact_numeric",))
    body = _body(
        "body_exact_numeric",
        energy=0.8,
        fatigue=0.2,
        pain=0.4,
        arousal=0.6,
        tension=0.3,
        physical_integrity=0.7,
        uncertainty=0.2,
        trust=0.9,
        attachment_security=0.5,
        resource_security=0.4,
        boundary_integrity=0.6,
        escape_availability=0.7,
        predictability=0.8,
    )
    packet = _packet(scene, body, packet_id="packet_exact_numeric")
    effect = _effect(
        packet,
        "option_exact_numeric",
        base_loss=0.2,
        base_recoverability=0.9,
    )

    result = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(effect,),
    )
    rollout = result.rollouts[0]

    # Independent arithmetic from the documented default coefficients:
    # loss=.50*.2 + .15*.3 + .10*.4 + .10*.3 + .05*.4 + .05*.6 + .05*.5
    # recovery=.50*.9 + .15*.8 + .10*.7 + .10*.8 + .05*.9 + .05*.5 + .05*.4
    assert rollout.predicted_loss == pytest.approx(0.29)
    assert rollout.recoverability == pytest.approx(0.81)
    assert protective_cost(rollout, result.config) == pytest.approx(0.4025)
    assert result.policy.option_scores[0].protective_cost == pytest.approx(0.4025)
    assert result.conclusion.intensity == pytest.approx(0.339)


def test_derived_body_state_id_includes_same_id_parent_content_hash() -> None:
    scene = _scene(("option_parent_hash",))
    first_parent = _body("shared_parent_id", energy=0.9)
    second_parent = _body("shared_parent_id", energy=1.0)
    packet = _packet(scene, first_parent, packet_id="packet_parent_hash")
    effect = _effect(
        packet,
        "option_parent_hash",
        deltas=(("energy", 1.0),),
    )
    config = InstinktSimulationConfig.create(rollout_steps=1)

    first_rollout = simulate_option_rollout(
        packet=packet,
        source_body_state=first_parent,
        effect=effect,
        config=config,
    )
    second_rollout = simulate_option_rollout(
        packet=packet,
        source_body_state=second_parent,
        effect=effect,
        config=config,
    )
    first_derived = first_rollout.trajectory[1]
    second_derived = second_rollout.trajectory[1]

    assert first_parent.body_state_id == second_parent.body_state_id
    assert first_parent.content_hash() != second_parent.content_hash()
    assert all(
        getattr(first_derived, dimension) == getattr(second_derived, dimension)
        for dimension in BODY_DIMENSIONS
    )
    assert first_derived.body_state_id != second_derived.body_state_id


def test_conclusion_abstention_and_decisive_rollout_invariants() -> None:
    scene = _scene(("option_conclusion_invariant",))
    body = _body("body_conclusion_invariant")
    packet = _packet(scene, body, packet_id="packet_conclusion_invariant")
    effect = _effect(packet, "option_conclusion_invariant")
    conclusion = process_instinkt(
        scene=scene,
        packet=packet,
        source_body_state=body,
        option_effects=(effect,),
    ).conclusion

    assert conclusion.option_id == "option_conclusion_invariant"
    assert conclusion.abstains is False
    assert conclusion.decisive_rollout_id is not None
    assert conclusion.decisive_rollout_option_id == conclusion.option_id

    selected_payload = conclusion.model_dump(mode="python", round_trip=True)
    for updates in (
        {"option_id": None, "abstains": False},
        {"abstains": True},
    ):
        invalid_payload = {**selected_payload, **updates}
        with pytest.raises(ValidationError, match="abstain exactly"):
            InstinktNativeConclusion(**invalid_payload)

    selected_without_rollout = {
        **selected_payload,
        "decisive_rollout_id": None,
        "decisive_rollout_option_id": None,
    }
    with pytest.raises(ValidationError, match="requires a decisive rollout"):
        InstinktNativeConclusion(**selected_without_rollout)


def test_association_memory_config_and_advance_edges_are_explicit() -> None:
    defaults = AssociationMemoryConfig()
    assert defaults.capacity == 32
    assert defaults.retrieval_limit == 4
    assert defaults.minimum_effective_strength == 0.05
    assert defaults.max_advance_cycles == 10_000
    with pytest.raises(ValidationError, match="cannot exceed capacity"):
        AssociationMemoryConfig(capacity=1, retrieval_limit=2)

    body = _body("body_memory_edges")
    memory = BoundedAssociativeMemory(
        AssociationMemoryConfig(
            capacity=2,
            retrieval_limit=2,
            minimum_effective_strength=0.0,
        )
    )
    memory.advance(0)
    assert memory.cycle == 0
    with pytest.raises(TypeError, match="must be an integer"):
        memory.advance(True)

    memory.add(_association("association_oldest", body, strength=0.5))
    memory.add(_association("association_second", body, strength=0.5))
    memory.add(_association("association_third", body, strength=0.5))
    assert tuple(item.association_id for item in memory.associations) == (
        "association_second",
        "association_third",
    )
