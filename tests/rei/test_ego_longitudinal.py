from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.backend.rei.ego.composition import derive_composition_snapshot
from app.backend.rei.ego.narrative_composition import (
    NarrativeCompositionDiagnostic,
    diagnose_narrative_composition,
)
from app.backend.rei.ego.reflector import (
    DeterministicEgoReflector,
    EgoReflectionHypothesis,
    EgoReflector,
)
from app.backend.rei.models.conscious import RacioSelfNarrative
from app.backend.rei.models.ego import (
    EgoCompositionSnapshot,
    EgoMeasure,
    EgoTrace,
    SourcedEgoClaim,
)
from app.backend.rei.models.emocio import EmocioWorld
from app.backend.rei.models.instinkt import InstinktWorld
from app.backend.rei.models.longitudinal import (
    LongitudinalEventStep,
    LongitudinalPersonState,
    LongitudinalScenario,
)
from app.backend.rei.models.racio import RacioWorld
from tests.rei.governance_test_helpers import _body_state, _scene
from tests.rei.test_ego import _trace


def _person_state() -> LongitudinalPersonState:
    trace, _ = _trace(1)
    measure = trace.measures[0]
    return LongitudinalPersonState.create(
        ego_id=trace.ego_id,
        structural_character=measure.structural_character,
        acceptance_state=measure.acceptance_state,
        racio_world=RacioWorld(
            world_id="longitudinal_racio_world",
            explicit_beliefs=(),
            facts=(),
            rules=(),
            timelines=(),
            commitments=(),
        ),
        emocio_world=EmocioWorld(
            world_id="longitudinal_emocio_world",
            visual_memories=(),
            desired_scenes=(),
            broken_scenes=(),
            social_identity_motifs=(),
            attraction_patterns=(),
            motor_patterns=(),
        ),
        instinkt_world=InstinktWorld.create(),
        body_state=_body_state(),
    )


def _steps(count: int) -> tuple[LongitudinalEventStep, ...]:
    return tuple(
        LongitudinalEventStep.create(
            sequence_index=index,
            scene=_scene().model_copy(
                update={"event_id": f"longitudinal_event_{index}"}
            ),
        )
        for index in range(count)
    )


@pytest.mark.parametrize("count", (10, 30))
def test_longitudinal_scenario_accepts_only_bounded_content_addressed_sequences(
    count: int,
) -> None:
    scenario = LongitudinalScenario.create(
        sequence_id=f"sequence_{count}",
        initial_person_state=_person_state(),
        steps=_steps(count),
        expected_motifs=("boundary_pressure",),
        expected_translation_patterns=("E:option_b->option_a",),
        expected_world_changes=("racio:timeline", "instinkt:boundary"),
    )

    assert len(scenario.steps) == count
    assert tuple(step.sequence_index for step in scenario.steps) == tuple(range(count))
    assert LongitudinalScenario.model_validate_json(
        scenario.model_dump_json()
    ) == scenario


@pytest.mark.parametrize("count", (9, 31))
def test_longitudinal_scenario_rejects_sequences_outside_ten_to_thirty(
    count: int,
) -> None:
    with pytest.raises(ValidationError):
        LongitudinalScenario.create(
            sequence_id=f"invalid_sequence_{count}",
            initial_person_state=_person_state(),
            steps=_steps(count),
        )


def test_longitudinal_steps_reject_tampering_and_ambiguous_outcome_modes() -> None:
    step = _steps(1)[0]
    payload = step.model_dump(mode="python", round_trip=True)
    payload["sequence_index"] = 7
    with pytest.raises(ValidationError, match="ID differs"):
        LongitudinalEventStep.model_validate(payload)

    with pytest.raises(ValidationError, match="without an outcome"):
        LongitudinalEventStep.create(
            sequence_index=0,
            scene=_scene(),
            expected_outcome_mode="simulator",
        )

    steps = list(_steps(10))
    steps[5] = LongitudinalEventStep.create(
        sequence_index=8,
        scene=steps[5].scene,
    )
    with pytest.raises(ValidationError, match="contiguous"):
        LongitudinalScenario.create(
            sequence_id="non_contiguous_sequence",
            initial_person_state=_person_state(),
            steps=tuple(steps),
        )


def _narrative(
    *,
    claimed_motive: str,
    omitted_minds: tuple[str, ...],
) -> RacioSelfNarrative:
    acknowledged = tuple(
        mind for mind in ("R", "E", "I") if mind not in omitted_minds
    )
    return RacioSelfNarrative(
        narrative_id=f"narrative_{claimed_motive.replace(' ', '_')}",
        source_decision_id="source_decision",
        explanation="A downstream narrative for diagnostic comparison.",
        claimed_motive=claimed_motive,
        acknowledged_minds=acknowledged,
        omitted_minds=omitted_minds,
        uncertainty="The narrative is an unverified downstream account.",
    )


def test_narrative_composition_diagnostic_is_transparent_and_replayable() -> None:
    trace, _ = _trace(2)
    snapshot = derive_composition_snapshot(trace)
    diagnostic = diagnose_narrative_composition(
        _narrative(claimed_motive="unobserved motive", omitted_minds=("E", "I")),
        snapshot,
    )

    assert diagnostic.narrative_composition_diverges is True
    assert diagnostic.divergence_facets == (
        "claimed_motive_not_observed",
        "omitted_minds",
    )
    assert diagnostic.evidence_measure_ids == snapshot.evidence_measure_ids
    assert NarrativeCompositionDiagnostic.model_validate_json(
        diagnostic.model_dump_json()
    ) == diagnostic

    aligned = diagnose_narrative_composition(
        _narrative(claimed_motive="shared tension", omitted_minds=()),
        snapshot,
    )
    assert aligned.narrative_composition_diverges is False
    assert aligned.divergence_facets == ()

    payload = diagnostic.model_dump(mode="python", round_trip=True)
    payload["narrative_composition_diverges"] = False
    with pytest.raises(ValidationError, match="transparent replay"):
        NarrativeCompositionDiagnostic.model_validate(payload)


def _measure_with_tensions(
    source: EgoMeasure,
    *,
    unresolved_tensions: tuple[str, ...],
    spoznanje_status: str,
) -> EgoMeasure:
    return EgoMeasure.create(
        event_id=source.event_id,
        native_bundle_id=source.native_bundle_id,
        native_bundle_hash=source.native_bundle_hash,
        governance_resolution_id=source.governance_resolution_id,
        governance_resolution_hash=source.governance_resolution_hash,
        structural_character=source.structural_character,
        effective_authority=source.effective_authority,
        acceptance_state=source.acceptance_state,
        governance_mandate=source.governance_mandate,
        racio_interpretations=source.racio_interpretations,
        conscious_decision=source.conscious_decision,
        behavior_resultant=source.behavior_resultant,
        outcome=source.outcome,
        translation_gaps=source.translation_gaps,
        unresolved_tensions=unresolved_tensions,
        spoznanje_status=spoznanje_status,
        created_at=source.created_at,
    )


def test_spoznanje_closes_prior_tension_append_only_and_recurrence_reopens() -> None:
    base_trace, _ = _trace(3)
    first, second, third = base_trace.measures
    first = _measure_with_tensions(
        first,
        unresolved_tensions=("shared tension",),
        spoznanje_status="no_spoznanje",
    )
    closing = _measure_with_tensions(
        second,
        unresolved_tensions=(),
        spoznanje_status="simulated_spoznanje",
    )
    closed_trace = EgoTrace.create(ego_id=base_trace.ego_id).append_measure(first)
    closed_trace = closed_trace.append_measure(closing)
    before_bytes = closed_trace.measures[0].canonical_json_bytes()
    closed = derive_composition_snapshot(closed_trace)

    assert closed.unresolved_tensions == ()
    assert closed.resolved_tensions == ("shared tension",)
    resolved_claim = next(
        claim for claim in closed.sourced_claims if claim.kind == "resolved_tension"
    )
    assert resolved_claim.evidence_measure_ids == (
        first.measure_id,
        closing.measure_id,
    )
    assert closed_trace.measures[0].canonical_json_bytes() == before_bytes

    recurrence = _measure_with_tensions(
        third,
        unresolved_tensions=("shared tension",),
        spoznanje_status="no_spoznanje",
    )
    reopened_trace = closed_trace.append_measure(recurrence)
    reopened = derive_composition_snapshot(reopened_trace)
    assert reopened.resolved_tensions == ()
    assert reopened.unresolved_tensions == ("shared tension",)
    unresolved_claim = next(
        claim for claim in reopened.sourced_claims if claim.kind == "unresolved_tension"
    )
    assert unresolved_claim.evidence_measure_ids == (
        first.measure_id,
        recurrence.measure_id,
    )


def test_reflector_is_read_only_sourced_and_has_no_decision_surface() -> None:
    trace, _ = _trace(2)
    snapshot = derive_composition_snapshot(trace)
    before_trace = trace.canonical_json_bytes()
    before_snapshot = snapshot.canonical_json_bytes()
    reflector = DeterministicEgoReflector()

    assert isinstance(reflector, EgoReflector)
    hypotheses = reflector.reflect(trace=trace, snapshot=snapshot)

    assert hypotheses
    assert trace.canonical_json_bytes() == before_trace
    assert snapshot.canonical_json_bytes() == before_snapshot
    allowed_measure_ids = {measure.measure_id for measure in trace.measures}
    forbidden_surface = {
        "decision",
        "vote",
        "mandate",
        "mutation",
        "world_update",
        "runtime_action",
    }
    assert forbidden_surface.isdisjoint(EgoReflectionHypothesis.model_fields)
    for hypothesis in hypotheses:
        assert set(hypothesis.supporting_measure_ids).issubset(allowed_measure_ids)
        assert hypothesis.source_trace_hash == trace.trace_hash
        assert hypothesis.source_snapshot_id == snapshot.snapshot_id
        assert hypothesis.statement.startswith("Hypothesis about ")
        assert "jaz, ego" not in hypothesis.statement.casefold()
        assert "i, ego" not in hypothesis.statement.casefold()
        assert EgoReflectionHypothesis.model_validate_json(
            hypothesis.model_dump_json()
        ) == hypothesis


@pytest.mark.parametrize(
    "statement",
    (
        "Jaz, Ego odločam o naslednjem koraku.",
        "I, Ego decide the next step.",
    ),
)
def test_reflection_contract_rejects_first_person_ego_voice(statement: str) -> None:
    trace, _ = _trace(1)
    snapshot = derive_composition_snapshot(trace)
    with pytest.raises(ValidationError, match="first-person"):
        EgoReflectionHypothesis.create(
            ego_id=trace.ego_id,
            source_trace_hash=trace.trace_hash,
            source_snapshot_id=snapshot.snapshot_id,
            source_snapshot_hash=snapshot.composition_hash,
            source_claim_ids=(snapshot.sourced_claims[0].claim_id,),
            statement=statement,
            confidence=0.7,
            supporting_measure_ids=(trace.measures[0].measure_id,),
        )


def test_c6_boundaries_reject_model_copy_stale_identity_inputs() -> None:
    trace, _ = _trace(2)
    snapshot = derive_composition_snapshot(trace)
    stale_snapshot = snapshot.model_copy(
        update={"identity_motifs": ("forged motif",)}
    )
    narrative = _narrative(claimed_motive="shared tension", omitted_minds=())
    with pytest.raises(ValidationError, match="claims|snapshot_id|composition_hash"):
        diagnose_narrative_composition(narrative, stale_snapshot)
    with pytest.raises(ValidationError, match="claims|snapshot_id|composition_hash"):
        DeterministicEgoReflector().reflect(
            trace=trace,
            snapshot=stale_snapshot,
        )

    person = _person_state()
    steps = _steps(10)
    stale_step = steps[0].model_copy(update={"sequence_index": 9})
    with pytest.raises(ValidationError, match="ID differs"):
        LongitudinalScenario.create(
            sequence_id="stale_step_sequence",
            initial_person_state=person,
            steps=(stale_step, *steps[1:]),
        )


def test_reflector_rejects_content_addressed_snapshot_not_derived_from_trace() -> None:
    trace, _ = _trace(2)
    actual = derive_composition_snapshot(trace)
    forged_text = "forged_but_content_addressed_identity_motif"
    forged_claim = SourcedEgoClaim.create(
        kind="identity_motif",
        text=forged_text,
        evidence_measure_ids=(trace.measures[0].measure_id,),
    )
    identity_claims = tuple(
        claim for claim in actual.sourced_claims if claim.kind == "identity_motif"
    )
    other_claims = tuple(
        claim for claim in actual.sourced_claims if claim.kind != "identity_motif"
    )
    forged = EgoCompositionSnapshot.create(
        ego_id=actual.ego_id,
        through_measure_id=actual.through_measure_id,
        identity_motifs=(*actual.identity_motifs, forged_text),
        recurring_conflicts=actual.recurring_conflicts,
        recurring_translation_errors=actual.recurring_translation_errors,
        unresolved_tensions=actual.unresolved_tensions,
        resolved_tensions=actual.resolved_tensions,
        spoznanja=actual.spoznanja,
        commitments=actual.commitments,
        relationship_patterns=actual.relationship_patterns,
        current_section=actual.current_section,
        evidence_measure_ids=actual.evidence_measure_ids,
        created_at=actual.created_at,
        source_trace_hash=actual.source_trace_hash,
        sourced_claims=(*identity_claims, forged_claim, *other_claims),
    )
    assert forged.source_trace_hash == trace.trace_hash
    assert forged.snapshot_id != actual.snapshot_id
    with pytest.raises(ValueError, match="deterministic composition replay"):
        DeterministicEgoReflector().reflect(trace=trace, snapshot=forged)
