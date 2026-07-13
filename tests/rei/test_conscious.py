from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.backend.rei.communication.conscious_view import (
    build_racio_interpreter_request,
)
from app.backend.rei.communication.interpreter import ScriptedRacioInterpreter
from app.backend.rei.communication.manifestations import (
    build_emocio_manifestation,
)
from app.backend.rei.conscious import (
    DEFAULT_B10_COMMIT_POLICY,
    DEFAULT_B10_NARRATION_POLICY,
    ConsciousCommitPolicy,
    ConsciousDecision,
    ConsciousInterpretationInput,
    ConsciousMandateView,
    DeterministicRacioCommitter,
    DeterministicRacioNarrator,
    RacioSelfNarrative,
    validate_commitment_replay,
    validate_narration_replay,
)
from app.backend.rei.governance import (
    DEFAULT_B10_BEHAVIOR_POLICY,
    BehaviorResolutionPolicy,
    BehaviorResolutionRule,
    DeterministicBehaviorResolver,
    TaskDelegation,
    derive_effective_authority,
    parse_character_profile,
    resolve_governance,
    validate_behavior_replay,
)
from app.backend.rei.ids import content_id, sha256_hex
from app.backend.rei.models.character import (
    CharacterAuthority,
    EffectiveAuthority,
)
from app.backend.rei.models.communication import (
    AcceptanceMode,
    AcceptanceState,
    DirectedMindRelation,
    EmocioManifestation,
)
from app.backend.rei.models.conscious import BehaviorResultant
from app.backend.rei.models.governance import (
    GovernanceMandate,
    GovernanceResolution,
    MindStatement,
)
from app.backend.rei.models.run import NativeMindBundle
from tests.rei.governance_test_helpers import (
    make_functional_override,
    make_native_bundle,
)


EXPECTED_RULE_IDS = (
    "unknown_or_non_actionable",
    "accepting_actionable",
    "mixed_recognized_or_r_led",
    "mixed_unrecognized_with_racio_option",
    "mixed_unrecognized_without_racio_option",
    "conflicted_with_racio_option",
    "conflicted_without_racio_option",
)
HIDDEN_MOTIVE_CANARY = "B10_HIDDEN_NATIVE_MOTIVE_CANARY_DO_NOT_DISCLOSE"


@dataclass(frozen=True)
class B10Context:
    bundle: NativeMindBundle
    character: CharacterAuthority
    effective: EffectiveAuthority
    governance: GovernanceResolution
    acceptance: AcceptanceState
    manifestations: tuple[EmocioManifestation, ...]
    mandate_view: ConsciousMandateView
    interpretation_inputs: tuple[ConsciousInterpretationInput, ...]
    decision: ConsciousDecision
    behavior: BehaviorResultant


def _relation(value: float = 0.5) -> DirectedMindRelation:
    return DirectedMindRelation(
        visibility=value,
        interpretation_fidelity=value,
        tolerance=value,
        delegation_willingness=value,
        sabotage_risk=1.0 - value,
    )


def _acceptance(
    mode: AcceptanceMode,
    *,
    suffix: str,
    relation_value: float = 0.5,
) -> AcceptanceState:
    relation = _relation(relation_value)
    return AcceptanceState(
        acceptance_state_id=f"acceptance_b10_{suffix}",
        R_to_E=relation,
        R_to_I=relation,
        E_to_R=relation,
        E_to_I=relation,
        I_to_R=relation,
        I_to_E=relation,
        overall_mode=mode,
    )


def _emocio_interpretation_input(
    *,
    bundle: NativeMindBundle,
    acceptance: AcceptanceState,
    manifestation: EmocioManifestation,
    mandate_view: ConsciousMandateView,
    option_id: str | None,
    motive: str,
    observation_limit: int | None = None,
) -> ConsciousInterpretationInput:
    request = build_racio_interpreter_request(
        manifestations=(manifestation,),
        allowed_option_ids=bundle.allowed_option_ids,
        acceptance_state=acceptance,
    )
    interpretation = ScriptedRacioInterpreter(
        scripted_option_id=option_id,
        scripted_action_tendency=bundle.emocio.action_tendency,
        scripted_motive=motive,
        scripted_confidence=0.61,
        observation_limit=observation_limit,
    ).interpret(request)
    return ConsciousInterpretationInput.create_b10(
        mandate_view=mandate_view,
        request=request,
        interpretation=interpretation,
        acceptance_state=acceptance,
    )


def _derive(
    *,
    bundle: NativeMindBundle,
    character: CharacterAuthority,
    effective: EffectiveAuthority,
    governance: GovernanceResolution,
    acceptance: AcceptanceState,
    interpreted_option_id: str | None = "option_b",
    interpreted_motive: str = "visible interpreted motive",
    include_emocio_interpretation: bool = True,
    observation_limit: int | None = None,
) -> B10Context:
    manifestation = build_emocio_manifestation(conclusion=bundle.emocio)
    manifestations = (manifestation,)
    mandate_view = ConsciousMandateView.create_b10(
        governance=governance,
        bundle=bundle,
        manifestations=manifestations,
    )
    interpretation_inputs = (
        (
            _emocio_interpretation_input(
                bundle=bundle,
                acceptance=acceptance,
                manifestation=manifestation,
                mandate_view=mandate_view,
                option_id=interpreted_option_id,
                motive=interpreted_motive,
                observation_limit=observation_limit,
            ),
        )
        if include_emocio_interpretation
        else ()
    )
    decision = DeterministicRacioCommitter().commit(
        mandate_view=mandate_view,
        racio_conclusion=bundle.racio,
        acceptance_state=acceptance,
        interpretation_inputs=interpretation_inputs,
    )
    behavior = DeterministicBehaviorResolver().resolve(
        mandate_view=mandate_view,
        decision=decision,
        acceptance_state=acceptance,
        racio_conclusion=bundle.racio,
        interpretation_inputs=interpretation_inputs,
    )
    return B10Context(
        bundle=bundle,
        character=character,
        effective=effective,
        governance=governance,
        acceptance=acceptance,
        manifestations=manifestations,
        mandate_view=mandate_view,
        interpretation_inputs=interpretation_inputs,
        decision=decision,
        behavior=behavior,
    )


def _scenario(
    *,
    rule_id: str,
    mode: AcceptanceMode,
    options: dict[str, str | None],
    profile_id: str = "E>R>I",
    interpreted_option_id: str | None = "option_b",
    interpreted_motive: str = "visible interpreted motive",
    relation_value: float = 0.5,
) -> B10Context:
    bundle = make_native_bundle(options)
    character = parse_character_profile(profile_id)  # type: ignore[arg-type]
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    acceptance = _acceptance(
        mode,
        suffix=rule_id,
        relation_value=relation_value,
    )
    return _derive(
        bundle=bundle,
        character=character,
        effective=effective,
        governance=governance,
        acceptance=acceptance,
        interpreted_option_id=interpreted_option_id,
        interpreted_motive=interpreted_motive,
    )


@pytest.mark.parametrize(
    (
        "rule_id",
        "mode",
        "options",
        "interpreted_option",
        "decision_option",
        "decision_status",
        "behavior_option",
        "behavior_status",
        "governance_alignment",
    ),
    (
        (
            "unknown_or_non_actionable",
            "unknown",
            {"R": "option_a", "E": "option_b", "I": "option_c"},
            "option_b",
            None,
            "deferred",
            None,
            "unresolved",
            "not_applicable",
        ),
        (
            "accepting_actionable",
            "accepting",
            {"R": "option_a", "E": "option_b", "I": "option_c"},
            "option_a",
            "option_b",
            "committed",
            "option_b",
            "executed",
            "aligned",
        ),
        (
            "mixed_recognized_or_r_led",
            "mixed",
            {"R": "option_a", "E": "option_b", "I": "option_c"},
            "option_b",
            "option_b",
            "committed",
            "option_b",
            "executed",
            "aligned",
        ),
        (
            "mixed_unrecognized_with_racio_option",
            "mixed",
            {"R": "option_a", "E": "option_b", "I": "option_c"},
            "option_c",
            "option_a",
            "committed",
            "option_a",
            "oscillating",
            "diverged",
        ),
        (
            "mixed_unrecognized_without_racio_option",
            "mixed",
            {"R": None, "E": "option_b", "I": "option_c"},
            "option_c",
            None,
            "deferred",
            None,
            "delayed",
            "not_applicable",
        ),
        (
            "conflicted_with_racio_option",
            "conflicted",
            {"R": "option_a", "E": "option_b", "I": "option_c"},
            "option_b",
            "option_a",
            "committed",
            "option_a",
            "sabotaged",
            "diverged",
        ),
        (
            "conflicted_without_racio_option",
            "conflicted",
            {"R": None, "E": "option_b", "I": "option_c"},
            "option_b",
            None,
            "blocked",
            None,
            "blocked",
            "not_applicable",
        ),
    ),
)
def test_all_seven_b10_rows_are_executable_and_keep_divergence_visible(
    rule_id: str,
    mode: AcceptanceMode,
    options: dict[str, str | None],
    interpreted_option: str | None,
    decision_option: str | None,
    decision_status: str,
    behavior_option: str | None,
    behavior_status: str,
    governance_alignment: str,
) -> None:
    context = _scenario(
        rule_id=rule_id,
        mode=mode,
        options=options,
        interpreted_option_id=interpreted_option,
    )

    assert context.decision.made_by == "R"
    assert context.decision.applied_rule_id == rule_id
    assert context.behavior.applied_rule_id == rule_id
    assert context.decision.option_id == decision_option
    assert context.decision.decision_status == decision_status
    assert context.behavior.option_id == behavior_option
    assert context.behavior.status == behavior_status
    assert context.behavior.governance_alignment == governance_alignment
    assert context.behavior.conscious_alignment == (
        "aligned" if behavior_option is not None else "not_applicable"
    )
    assert context.decision.derivation_status == "derived_b10"
    assert context.behavior.derivation_status == "derived_b10"
    assert context.behavior.source_decision_id == context.decision.decision_id


def test_accepting_disagreement_executes_mandate_even_with_wrong_motive() -> None:
    context = _scenario(
        rule_id="accepting_wrong_motive",
        mode="accepting",
        options={"R": "option_a", "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_a",
        interpreted_motive="Racio's consciously visible but wrong motive",
    )

    assert context.governance.mandate.structural_source_minds == ("E",)
    assert context.governance.mandate.option_id == "option_b"
    assert context.decision.option_id == "option_b"
    assert context.decision.declared_reason == "Racio's consciously visible but wrong motive"
    assert context.decision.aligned_with_governance_mandate is True
    assert context.behavior.status == "executed"
    assert context.behavior.operational_controller == "E"
    assert any(item.mind == "R" for item in context.mandate_view.objections)


def test_mixed_recognition_executes_but_wrong_translation_oscillates() -> None:
    options = {"R": "option_a", "E": "option_b", "I": "option_c"}
    recognized = _scenario(
        rule_id="mixed_recognized_comparison",
        mode="mixed",
        options=options,
        interpreted_option_id="option_b",
    )
    unrecognized = _scenario(
        rule_id="mixed_unrecognized_comparison",
        mode="mixed",
        options=options,
        interpreted_option_id="option_c",
    )

    assert recognized.decision.option_id == "option_b"
    assert recognized.behavior.status == "executed"
    assert unrecognized.decision.option_id == "option_a"
    assert unrecognized.behavior.status == "oscillating"
    assert "mandate_not_consciously_recognized" in unrecognized.behavior.residual_tensions
    assert any(
        item.startswith("conscious_mandate_divergence:")
        for item in unrecognized.behavior.residual_tensions
    )


def test_mixed_r_led_mandate_executes_without_an_e_or_i_interpretation() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("R>E>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    acceptance = _acceptance("mixed", suffix="mixed_r_led")
    context = _derive(
        bundle=bundle,
        character=character,
        effective=effective,
        governance=governance,
        acceptance=acceptance,
        include_emocio_interpretation=False,
    )

    assert context.decision.applied_rule_id == "mixed_recognized_or_r_led"
    assert context.decision.option_id == "option_a"
    assert context.behavior.status == "executed"
    assert context.behavior.operational_controller == "R"


def test_e_led_accepting_requires_typed_b9_input_but_accepts_typed_omission() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("E>R>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    acceptance = _acceptance("accepting", suffix="typed_b9_omission")
    manifestation = build_emocio_manifestation(conclusion=bundle.emocio)
    mandate_view = ConsciousMandateView.create_b10(
        governance=governance,
        bundle=bundle,
        manifestations=(manifestation,),
    )
    committer = DeterministicRacioCommitter()

    with pytest.raises(ValueError, match="requires a typed B9 interpretation for: E"):
        committer.commit(
            mandate_view=mandate_view,
            racio_conclusion=bundle.racio,
            acceptance_state=acceptance,
            interpretation_inputs=(),
        )

    omitted_input = _emocio_interpretation_input(
        bundle=bundle,
        acceptance=acceptance,
        manifestation=manifestation,
        mandate_view=mandate_view,
        option_id="option_a",
        motive="this scripted content is discarded by typed omission",
        observation_limit=0,
    )
    decision = committer.commit(
        mandate_view=mandate_view,
        racio_conclusion=bundle.racio,
        acceptance_state=acceptance,
        interpretation_inputs=(omitted_input,),
    )

    assert omitted_input.interpretation.interpretation_status == "omitted_b9"
    assert omitted_input.interpretation.inferred_option_id is None
    assert decision.applied_rule_id == "accepting_actionable"
    assert decision.option_id == "option_b"


def test_current_cycle_rejects_foreign_bundle_and_manifestation_from_same_scene() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    foreign_bundle = make_native_bundle(
        {"R": "option_c", "E": "option_b", "I": "option_c"}
    )
    character = parse_character_profile("E>R>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    foreign_manifestation = build_emocio_manifestation(
        conclusion=foreign_bundle.emocio
    )

    assert bundle.scene_id == foreign_bundle.scene_id
    assert bundle.racio.conclusion_id != foreign_bundle.racio.conclusion_id
    assert bundle.emocio.conclusion_id != foreign_bundle.emocio.conclusion_id
    with pytest.raises(ValueError, match="another native bundle"):
        ConsciousMandateView.create_b10(
            governance=governance,
            bundle=bundle,
            manifestations=(foreign_manifestation,),
        )
    with pytest.raises(ValueError, match="another native bundle"):
        ConsciousMandateView.create_b10(
            governance=governance,
            bundle=foreign_bundle,
            manifestations=(foreign_manifestation,),
        )


@pytest.mark.parametrize(
    ("racio_option", "expected_alignment"),
    (("option_a", "diverged"), ("option_b", "aligned")),
)
def test_conflicted_behavior_is_sabotaged_even_when_options_agree(
    racio_option: str,
    expected_alignment: str,
) -> None:
    context = _scenario(
        rule_id=f"conflicted_same_or_different_{racio_option}",
        mode="conflicted",
        options={"R": racio_option, "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_b",
    )

    assert context.decision.option_id == racio_option
    assert context.behavior.option_id == racio_option
    assert context.behavior.status == "sabotaged"
    assert context.behavior.governance_alignment == expected_alignment
    assert context.behavior.conscious_alignment == "aligned"
    assert "conflicted_coordination_sabotage" in context.behavior.residual_tensions


def test_delegated_execution_preserves_authority_and_names_the_delegate() -> None:
    bundle = make_native_bundle({"R": "option_b", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("E>R>I")
    effective = derive_effective_authority(character)
    delegation = TaskDelegation(
        delegation_id="delegation_b10_e_to_r",
        delegating_minds=("E",),
        delegate_mind="R",
        task="Carry out the consciously coordinated option.",
        option_id="option_b",
        rationale="Explicit accepting delegation fixture.",
    )
    governance = resolve_governance(bundle, effective, delegation=delegation)
    acceptance = _acceptance("accepting", suffix="delegated")
    before = (character.content_hash(), effective.content_hash(), governance.content_hash())
    context = _derive(
        bundle=bundle,
        character=character,
        effective=effective,
        governance=governance,
        acceptance=acceptance,
        interpreted_option_id="option_a",
        interpreted_motive="wrong motive does not replace explicit delegation",
    )

    assert context.mandate_view.status == "delegated"
    assert context.behavior.status == "executed"
    assert context.behavior.operational_controller == "R"
    assert context.mandate_view.delegation == delegation
    assert before == (
        character.content_hash(),
        effective.content_hash(),
        governance.content_hash(),
    )
    assert effective.structural_profile == character


def test_functional_override_is_actionable_without_mutating_structural_character() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("R>E>I")
    override = make_functional_override(character, ("R",))
    effective = derive_effective_authority(character, override)
    governance = resolve_governance(bundle, effective)
    acceptance = _acceptance("accepting", suffix="functional_override")
    character_hash = character.content_hash()
    context = _derive(
        bundle=bundle,
        character=character,
        effective=effective,
        governance=governance,
        acceptance=acceptance,
        interpreted_option_id="option_b",
        interpreted_motive="visible E interpretation",
    )

    assert context.mandate_view.status == "functionally_overridden"
    assert context.decision.option_id == "option_b"
    assert context.behavior.status == "executed"
    assert context.behavior.operational_controller == "E"
    assert character.content_hash() == character_hash
    assert effective.structural_profile == character


def test_unresolved_mandate_has_priority_over_accepting_mode() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("(R=E)>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    acceptance = _acceptance("accepting", suffix="unresolved")
    context = _derive(
        bundle=bundle,
        character=character,
        effective=effective,
        governance=governance,
        acceptance=acceptance,
        interpreted_option_id="option_b",
        interpreted_motive="visible but non-resolving interpretation",
    )

    assert context.mandate_view.status == "unresolved"
    assert context.mandate_view.option_id is None
    assert context.decision.applied_rule_id == "unknown_or_non_actionable"
    assert context.decision.decision_status == "deferred"
    assert context.behavior.status == "unresolved"


def _mandate_with_hidden_canary(mandate: GovernanceMandate) -> GovernanceMandate:
    base = {
        "schema_version": mandate.schema_version,
        "status": mandate.status,
        "structural_source_minds": mandate.structural_source_minds,
        "option_id": mandate.option_id,
        "objections": mandate.objections,
        "delegation": mandate.delegation,
        "hidden_native_motives": (
            MindStatement(mind="E", statement=HIDDEN_MOTIVE_CANARY),
        ),
    }
    return GovernanceMandate(
        mandate_id=content_id("mandate", base),
        **base,
    )


def _resolution_with_mandate(
    governance: GovernanceResolution,
    mandate: GovernanceMandate,
) -> GovernanceResolution:
    return GovernanceResolution.create(
        native_bundle_id=governance.native_bundle_id,
        native_bundle_hash=governance.native_bundle_hash,
        character_id=governance.character_id,
        character_hash=governance.character_hash,
        profile_id=governance.profile_id,
        effective_authority_id=governance.effective_authority_id,
        effective_authority_hash=governance.effective_authority_hash,
        structural_top_minds=governance.structural_top_minds,
        effective_source_minds=governance.effective_source_minds,
        agreement_pattern=governance.agreement_pattern,
        mandate=mandate,
        pair_conflict=governance.pair_conflict,
    )


def test_hidden_native_motive_never_enters_conscious_or_narrative_artifacts() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("E>R>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    hidden_governance = _resolution_with_mandate(
        governance,
        _mandate_with_hidden_canary(governance.mandate),
    )
    manifestation = build_emocio_manifestation(conclusion=bundle.emocio)
    manifestations = (manifestation,)
    public_view = ConsciousMandateView.create_b10(
        governance=governance,
        bundle=bundle,
        manifestations=manifestations,
    )
    hidden_view = ConsciousMandateView.create_b10(
        governance=hidden_governance,
        bundle=bundle,
        manifestations=manifestations,
    )
    acceptance = _acceptance("accepting", suffix="hidden_canary")
    context = _derive(
        bundle=bundle,
        character=character,
        effective=effective,
        governance=hidden_governance,
        acceptance=acceptance,
        interpreted_option_id="option_a",
        interpreted_motive="consciously visible wrong motive",
    )
    narrative = DeterministicRacioNarrator().narrate(
        mandate_view=context.mandate_view,
        decision=context.decision,
        resultant=context.behavior,
        interpretation_inputs=context.interpretation_inputs,
    )

    assert governance.resolution_id != hidden_governance.resolution_id
    assert governance.resolution_hash != hidden_governance.resolution_hash
    assert public_view.mandate_view_id == hidden_view.mandate_view_id
    assert public_view.view_hash == hidden_view.view_hash
    assert public_view.content_hash() == hidden_view.content_hash()
    assert {
        "hidden_native_motives",
        "source_mandate_id",
        "source_mandate_hash",
    }.isdisjoint(ConsciousMandateView.model_fields)
    for artifact in (
        context.mandate_view,
        context.decision,
        context.behavior,
        narrative,
    ):
        assert HIDDEN_MOTIVE_CANARY not in artifact.model_dump_json()


def test_conscious_interpretation_input_rejects_cross_scene_and_acceptance() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("E>R>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    manifestation = build_emocio_manifestation(conclusion=bundle.emocio)
    mandate_view = ConsciousMandateView.create_b10(
        governance=governance,
        bundle=bundle,
        manifestations=(manifestation,),
    )
    acceptance_a = _acceptance("mixed", suffix="bound_a")
    acceptance_b = _acceptance("mixed", suffix="bound_b")
    bound_a = _emocio_interpretation_input(
        bundle=bundle,
        acceptance=acceptance_a,
        manifestation=manifestation,
        mandate_view=mandate_view,
        option_id="option_b",
        motive="scene-bound interpretation",
    )

    with pytest.raises(ValueError, match="uses another AcceptanceState"):
        ConsciousInterpretationInput.create_b10(
            mandate_view=mandate_view,
            request=bound_a.request,
            interpretation=bound_a.interpretation,
            acceptance_state=acceptance_b,
        )

    foreign_bundle = make_native_bundle(
        {"R": "option_c", "E": "option_b", "I": "option_a"}
    )
    foreign_governance = resolve_governance(foreign_bundle, effective)
    foreign_manifestation = build_emocio_manifestation(
        conclusion=foreign_bundle.emocio
    )
    foreign_view = ConsciousMandateView.create_b10(
        governance=foreign_governance,
        bundle=foreign_bundle,
        manifestations=(foreign_manifestation,),
    )
    foreign_cycle_input = _emocio_interpretation_input(
        bundle=foreign_bundle,
        acceptance=acceptance_a,
        manifestation=foreign_manifestation,
        mandate_view=foreign_view,
        option_id="option_b",
        motive="foreign-cycle interpretation",
    )
    with pytest.raises(ValueError, match="another conscious cycle"):
        DeterministicRacioCommitter().commit(
            mandate_view=mandate_view,
            racio_conclusion=bundle.racio,
            acceptance_state=acceptance_a,
            interpretation_inputs=(foreign_cycle_input,),
        )

    bound_b = _emocio_interpretation_input(
        bundle=bundle,
        acceptance=acceptance_b,
        manifestation=manifestation,
        mandate_view=mandate_view,
        option_id="option_b",
        motive="other-acceptance interpretation",
    )
    with pytest.raises(ValueError, match="another AcceptanceState"):
        DeterministicRacioCommitter().commit(
            mandate_view=mandate_view,
            racio_conclusion=bundle.racio,
            acceptance_state=acceptance_a,
            interpretation_inputs=(bound_b,),
        )


def _rehashed_payload(
    artifact: BaseModel,
    *,
    id_field: str,
    hash_field: str,
    prefix: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    base = artifact.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, hash_field},
    )
    base.update(updates)
    artifact_id = content_id(prefix, base)
    payload = {id_field: artifact_id, **base}
    return {**payload, hash_field: sha256_hex(payload)}


def test_ids_hashes_and_replay_reject_self_rehashed_tampering() -> None:
    context = _scenario(
        rule_id="replay",
        mode="mixed",
        options={"R": "option_a", "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_c",
    )
    committer = DeterministicRacioCommitter()
    resolver = DeterministicBehaviorResolver()
    narrator = DeterministicRacioNarrator()
    narrative = narrator.narrate(
        mandate_view=context.mandate_view,
        decision=context.decision,
        resultant=context.behavior,
        interpretation_inputs=context.interpretation_inputs,
    )

    assert validate_commitment_replay(
        committer=committer,
        decision=context.decision,
        mandate_view=context.mandate_view,
        racio_conclusion=context.bundle.racio,
        acceptance_state=context.acceptance,
        interpretation_inputs=context.interpretation_inputs,
    ) == context.decision
    assert validate_behavior_replay(
        resolver=resolver,
        resultant=context.behavior,
        mandate_view=context.mandate_view,
        decision=context.decision,
        acceptance_state=context.acceptance,
        racio_conclusion=context.bundle.racio,
        interpretation_inputs=context.interpretation_inputs,
    ) == context.behavior
    assert validate_narration_replay(
        narrator=narrator,
        narrative=narrative,
        mandate_view=context.mandate_view,
        decision=context.decision,
        resultant=context.behavior,
        interpretation_inputs=context.interpretation_inputs,
    ) == narrative

    tampered_decision = ConsciousDecision(
        **_rehashed_payload(
            context.decision,
            id_field="decision_id",
            hash_field="decision_hash",
            prefix="conscious_decision",
            updates={"declared_reason": "self-rehashed tampered reason"},
        )
    )
    with pytest.raises(ValueError, match="differs from deterministic replay"):
        validate_commitment_replay(
            committer=committer,
            decision=tampered_decision,
            mandate_view=context.mandate_view,
            racio_conclusion=context.bundle.racio,
            acceptance_state=context.acceptance,
            interpretation_inputs=context.interpretation_inputs,
        )

    tampered_behavior = BehaviorResultant(
        **_rehashed_payload(
            context.behavior,
            id_field="resultant_id",
            hash_field="resultant_hash",
            prefix="behavior_resultant",
            updates={"predicted_action": "self-rehashed tampered action"},
        )
    )
    with pytest.raises(ValueError, match="differs from deterministic replay"):
        validate_behavior_replay(
            resolver=resolver,
            resultant=tampered_behavior,
            mandate_view=context.mandate_view,
            decision=context.decision,
            acceptance_state=context.acceptance,
            racio_conclusion=context.bundle.racio,
            interpretation_inputs=context.interpretation_inputs,
        )

    tampered_narrative = RacioSelfNarrative(
        **_rehashed_payload(
            narrative,
            id_field="narrative_id",
            hash_field="narrative_hash",
            prefix="racio_self_narrative",
            updates={"claimed_motive": "self-rehashed tampered motive"},
        )
    )
    with pytest.raises(ValueError, match="differs from deterministic replay"):
        validate_narration_replay(
            narrator=narrator,
            narrative=tampered_narrative,
            mandate_view=context.mandate_view,
            decision=context.decision,
            resultant=context.behavior,
            interpretation_inputs=context.interpretation_inputs,
        )


def test_narrator_is_downstream_frozen_and_cannot_mutate_decision_or_behavior() -> None:
    context = _scenario(
        rule_id="narrator_frozen",
        mode="conflicted",
        options={"R": "option_a", "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_b",
    )
    decision_before = context.decision.content_hash()
    behavior_before = context.behavior.content_hash()
    narrative = DeterministicRacioNarrator().narrate(
        mandate_view=context.mandate_view,
        decision=context.decision,
        resultant=context.behavior,
        interpretation_inputs=context.interpretation_inputs,
    )

    assert narrative.claimed_motive == context.decision.declared_reason
    assert narrative.source_decision_id == context.decision.decision_id
    assert narrative.source_resultant_id == context.behavior.resultant_id
    assert context.decision.content_hash() == decision_before
    assert context.behavior.content_hash() == behavior_before
    assert "sabotaged" in narrative.explanation
    with pytest.raises(ValidationError, match="frozen"):
        narrative.explanation = "attempted mutation"  # type: ignore[misc]


def test_acceptance_changes_behavior_not_character_or_governance() -> None:
    bundle = make_native_bundle({"R": "option_a", "E": "option_b", "I": "option_c"})
    character = parse_character_profile("E>R>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    frozen_hashes = (
        bundle.immutable_hash,
        character.content_hash(),
        effective.content_hash(),
        governance.content_hash(),
    )
    contexts: list[B10Context] = []
    for mode in ("accepting", "conflicted"):
        acceptance = _acceptance(mode, suffix=f"authority_{mode}")
        contexts.append(
            _derive(
                bundle=bundle,
                character=character,
                effective=effective,
                governance=governance,
                acceptance=acceptance,
                interpreted_option_id="option_b",
                interpreted_motive="same visible interpretation",
            )
        )

    assert contexts[0].behavior.status == "executed"
    assert contexts[1].behavior.status == "sabotaged"
    assert frozen_hashes == (
        bundle.immutable_hash,
        character.content_hash(),
        effective.content_hash(),
        governance.content_hash(),
    )


def test_unverified_contract_conscious_artifacts_remain_backward_compatible() -> None:
    decision = ConsciousDecision(
        decision_id="legacy_conscious_decision",
        option_id=None,
        declared_reason="legacy caller-supplied reason",
        conscious_confidence=0.7,
        aligned_with_governance_mandate=True,
        decision_status="committed",
    )
    behavior = BehaviorResultant(
        resultant_id="legacy_behavior_resultant",
        option_id=None,
        status="executed",
        governance_alignment="aligned",
        conscious_alignment="aligned",
        operational_controller="R",
        predicted_action="legacy caller-supplied action",
    )
    narrative = RacioSelfNarrative(
        narrative_id="legacy_racio_self_narrative",
        source_decision_id=decision.decision_id,
        source_resultant_id=behavior.resultant_id,
        explanation="legacy caller-supplied explanation",
        claimed_motive="legacy caller-supplied motive",
        acknowledged_minds=("I", "R"),
        omitted_minds=("E",),
        uncertainty="legacy uncertainty",
    )

    for artifact in (decision, behavior, narrative):
        assert artifact.derivation_status == "unverified_contract"
        dumped = artifact.model_dump(mode="python", round_trip=True)
        assert "derivation_status" not in dumped
        assert "source_mandate_view_id" not in dumped
    assert decision.source_interpretations == ()
    assert decision.option_id is None
    assert behavior.option_id is None
    assert narrative.acknowledged_minds == ("I", "R")
    assert behavior.resultant_hash is None
    assert narrative.narrative_hash is None


def test_public_mandate_view_enforces_status_option_and_delegation_invariants() -> None:
    context = _scenario(
        rule_id="public_view_invariants",
        mode="accepting",
        options={"R": "option_a", "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_b",
    )
    view = context.mandate_view
    mandate = context.governance.mandate
    matching_delegation = TaskDelegation(
        delegation_id="public_view_matching_delegation",
        delegating_minds=("E",),
        delegate_mind="R",
        task="Execute the projected option.",
        option_id="option_b",
        rationale="Invariant fixture.",
    )
    mismatching_delegation = matching_delegation.model_copy(
        update={
            "delegation_id": "public_view_mismatching_delegation",
            "option_id": "option_c",
        }
    )

    assert (view.status, view.option_id, view.delegation) == (
        mandate.status,
        mandate.option_id,
        mandate.delegation,
    )
    payload = view.model_dump(mode="python", round_trip=True)
    invalid_cases = (
        (
            {"status": "delegated", "delegation": None},
            "delegated conscious view requires delegation",
        ),
        (
            {"delegation": matching_delegation},
            "Delegation is only valid for a delegated conscious view",
        ),
        (
            {"status": "unresolved"},
            "unresolved conscious view cannot select an option",
        ),
        (
            {"option_id": None},
            "resolved conscious view requires an option",
        ),
        (
            {"status": "delegated", "delegation": mismatching_delegation},
            "Delegation option must match the conscious mandate view",
        ),
    )
    for updates, message in invalid_cases:
        with pytest.raises(ValidationError, match=message):
            ConsciousMandateView(**{**payload, **updates})


def test_executed_behavior_rule_cannot_disable_controller_derivation() -> None:
    executed_rule = DEFAULT_B10_BEHAVIOR_POLICY.rule("accepting_actionable")
    payload = executed_rule.model_dump(mode="python", round_trip=True)

    with pytest.raises(
        ValidationError,
        match="Executed behavior must derive its operational controller",
    ):
        BehaviorResolutionRule(**{**payload, "controller_source": "none"})


def test_policy_tables_are_exhaustive_ordered_and_have_no_score_thresholds() -> None:
    assert tuple(
        rule.rule_id for rule in DEFAULT_B10_COMMIT_POLICY.ordered_rules
    ) == EXPECTED_RULE_IDS
    assert tuple(
        rule.rule_id for rule in DEFAULT_B10_BEHAVIOR_POLICY.ordered_rules
    ) == EXPECTED_RULE_IDS
    assert tuple(rule.priority for rule in DEFAULT_B10_COMMIT_POLICY.ordered_rules) == tuple(
        range(1, 8)
    )
    assert tuple(
        rule.priority for rule in DEFAULT_B10_BEHAVIOR_POLICY.ordered_rules
    ) == tuple(range(1, 8))
    assert DEFAULT_B10_BEHAVIOR_POLICY.uses_relation_thresholds is False
    assert DEFAULT_B10_BEHAVIOR_POLICY.uses_acceptance_fidelity_audit is False
    assert DEFAULT_B10_BEHAVIOR_POLICY.uses_character_weights is False
    assert DEFAULT_B10_BEHAVIOR_POLICY.uses_prose_keywords is False
    assert not any(
        field_name.endswith("_threshold")
        for field_name in type(DEFAULT_B10_BEHAVIOR_POLICY).model_fields
    )
    assert set(type(DEFAULT_B10_NARRATION_POLICY).model_fields) == {
        "policy_id",
        "revision",
        "basis",
        "acknowledge_governance_sources",
        "acknowledge_recorded_objections",
        "preserve_divergence_language",
        "may_mutate_decision_or_behavior",
    }

    with pytest.raises(ValidationError, match="complete and canonically ordered"):
        ConsciousCommitPolicy(
            ordered_rules=DEFAULT_B10_COMMIT_POLICY.ordered_rules[:-1]
        )
    with pytest.raises(ValidationError, match="complete and canonically ordered"):
        BehaviorResolutionPolicy(
            ordered_rules=tuple(reversed(DEFAULT_B10_BEHAVIOR_POLICY.ordered_rules))
        )


def test_canonical_policy_semantics_require_a_new_identity_when_changed() -> None:
    changed_commit = list(DEFAULT_B10_COMMIT_POLICY.ordered_rules)
    changed_commit[1] = changed_commit[1].model_copy(update={"option_source": "none"})
    with pytest.raises(ValidationError, match="semantics are immutable"):
        ConsciousCommitPolicy(ordered_rules=tuple(changed_commit))

    changed_behavior = list(DEFAULT_B10_BEHAVIOR_POLICY.ordered_rules)
    changed_behavior[5] = changed_behavior[5].model_copy(
        update={"behavior_status": "oscillating"}
    )
    with pytest.raises(ValidationError, match="semantics are immutable"):
        BehaviorResolutionPolicy(ordered_rules=tuple(changed_behavior))

    revised = ConsciousCommitPolicy(
        policy_id="test-revised-commit-policy",
        revision="2",
        ordered_rules=tuple(changed_commit),
    )
    assert revised.content_hash() != DEFAULT_B10_COMMIT_POLICY.content_hash()


def test_committer_rejects_racio_conclusion_from_another_native_cycle() -> None:
    context = _scenario(
        rule_id="foreign_racio",
        mode="accepting",
        options={"R": "option_a", "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_b",
    )
    foreign_bundle = make_native_bundle(
        {"R": "option_c", "E": "option_b", "I": "option_a"}
    )
    with pytest.raises(ValueError, match="one native cycle"):
        DeterministicRacioCommitter().commit(
            mandate_view=context.mandate_view,
            racio_conclusion=foreign_bundle.racio,
            acceptance_state=context.acceptance,
            interpretation_inputs=context.interpretation_inputs,
        )


def test_behavior_rejects_foreign_conclusion_or_interpretation_with_same_rule() -> None:
    context = _scenario(
        rule_id="behavior_exact_cycle",
        mode="accepting",
        options={"R": "option_a", "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_b",
    )
    foreign_bundle = make_native_bundle(
        {"R": "option_c", "E": "option_b", "I": "option_a"}
    )
    resolver = DeterministicBehaviorResolver()

    assert context.decision.applied_rule_id == "accepting_actionable"
    with pytest.raises(ValueError, match="another Racio conclusion"):
        resolver.resolve(
            mandate_view=context.mandate_view,
            decision=context.decision,
            acceptance_state=context.acceptance,
            racio_conclusion=foreign_bundle.racio,
            interpretation_inputs=context.interpretation_inputs,
        )

    foreign_interpretation = _emocio_interpretation_input(
        bundle=context.bundle,
        acceptance=context.acceptance,
        manifestation=context.manifestations[0],
        mandate_view=context.mandate_view,
        option_id="option_b",
        motive="different lineage that still selects the accepting row",
    )
    same_rule_decision = DeterministicRacioCommitter().commit(
        mandate_view=context.mandate_view,
        racio_conclusion=context.bundle.racio,
        acceptance_state=context.acceptance,
        interpretation_inputs=(foreign_interpretation,),
    )
    assert same_rule_decision.applied_rule_id == context.decision.applied_rule_id
    with pytest.raises(ValueError, match="interpretation lineage differs"):
        resolver.resolve(
            mandate_view=context.mandate_view,
            decision=context.decision,
            acceptance_state=context.acceptance,
            racio_conclusion=context.bundle.racio,
            interpretation_inputs=(foreign_interpretation,),
        )


def test_narrator_rejects_interpretations_not_cited_by_decision() -> None:
    context = _scenario(
        rule_id="narrator_lineage",
        mode="accepting",
        options={"R": "option_a", "E": "option_b", "I": "option_c"},
        interpreted_option_id="option_b",
    )
    unrelated = _emocio_interpretation_input(
        bundle=context.bundle,
        acceptance=context.acceptance,
        manifestation=context.manifestations[0],
        mandate_view=context.mandate_view,
        option_id="option_b",
        motive="a different downstream story",
    )
    with pytest.raises(ValueError, match="differ from the decision interpretations"):
        DeterministicRacioNarrator().narrate(
            mandate_view=context.mandate_view,
            decision=context.decision,
            resultant=context.behavior,
            interpretation_inputs=(unrelated,),
        )
