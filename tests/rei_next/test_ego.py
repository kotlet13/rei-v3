from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.backend.rei_next.ego import (
    EgoTraceConflictError,
    EgoTraceTamperError,
    FileEgoTraceStore,
    InMemoryEgoTraceStore,
    build_ego_measure,
    derive_composition_snapshot,
    derive_modality_projections,
)
from app.backend.rei_next.governance.profiles import (
    derive_effective_authority,
    parse_character_profile,
)
from app.backend.rei_next.governance.resolver import resolve_governance
from app.backend.rei_next.models.communication import (
    AcceptanceState,
    DirectedMindRelation,
)
from app.backend.rei_next.models.conscious import BehaviorResultant, ConsciousDecision
from app.backend.rei_next.models.ego import (
    EgoCorrectionEvent,
    EgoTrace,
    RacioProjection,
)
from app.backend.rei_next.models.run import NativeMindBundle
from app.backend.rei_next.providers.protocols import EgoTraceStore
from tests.rei_next.governance_test_helpers import make_native_bundle


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _acceptance() -> AcceptanceState:
    relation = DirectedMindRelation(
        visibility=0.8,
        interpretation_fidelity=0.7,
        tolerance=0.8,
        delegation_willingness=0.6,
        sabotage_risk=0.1,
    )
    return AcceptanceState(
        acceptance_state_id="acceptance_b4",
        R_to_E=relation,
        R_to_I=relation,
        E_to_R=relation,
        E_to_I=relation,
        I_to_R=relation,
        I_to_E=relation,
        overall_mode="accepting",
    )


def _measure(index: int, *, tension: str = "shared tension"):
    bundle = make_native_bundle(
        {"R": "option_a", "E": "option_b", "I": "option_c"}
    )
    character = parse_character_profile("R>E>I")
    effective = derive_effective_authority(character)
    governance = resolve_governance(bundle, effective)
    decision = ConsciousDecision(
        decision_id=f"decision_b4_{index}",
        option_id="option_a",
        declared_reason="explicit reason",
        conscious_confidence=0.7,
        aligned_with_governance_mandate=True,
        decision_status="committed",
    )
    behavior = BehaviorResultant(
        resultant_id=f"resultant_b4_{index}",
        option_id="option_a",
        status="executed",
        governance_alignment="aligned",
        conscious_alignment="aligned",
        operational_controller="R",
        residual_tensions=(tension,),
        predicted_action="execute option A",
    )
    measure = build_ego_measure(
        bundle=bundle,
        governance=governance,
        structural_character=character,
        effective_authority=effective,
        acceptance_state=_acceptance(),
        conscious_decision=decision,
        behavior_resultant=behavior,
        unresolved_tensions=(tension,),
        created_at=NOW + timedelta(minutes=index),
    )
    return bundle, character, effective, governance, measure


def _trace(count: int = 2) -> tuple[EgoTrace, dict[str, NativeMindBundle]]:
    trace = EgoTrace.create(ego_id="ego_b4")
    bundles: dict[str, NativeMindBundle] = {}
    for index in range(count):
        bundle, _, _, _, measure = _measure(index)
        bundles[bundle.bundle_id] = bundle
        trace = trace.append_measure(measure)
    return trace, bundles


def test_measure_builder_closes_native_and_governance_lineage() -> None:
    bundle, character, effective, governance, measure = _measure(1)

    assert measure.event_id == bundle.scene_id
    assert measure.native_bundle_id == bundle.bundle_id
    assert measure.native_bundle_hash == bundle.immutable_hash
    assert measure.governance_resolution_id == governance.resolution_id
    assert measure.governance_resolution_hash == governance.resolution_hash
    assert measure.governance_mandate == governance.mandate
    assert measure.structural_character == character
    assert measure.effective_authority == effective
    assert measure.spoznanje_status == governance.spoznanje_status

    wrong_governance = governance.model_copy(update={"native_bundle_id": "bundle_other"})
    with pytest.raises(ValueError, match="another native bundle"):
        build_ego_measure(
            bundle=bundle,
            governance=wrong_governance,
            structural_character=character,
            effective_authority=effective,
            acceptance_state=_acceptance(),
            conscious_decision=measure.conscious_decision,
            behavior_resultant=measure.behavior_resultant,
            created_at=NOW,
        )


def test_snapshot_is_content_addressed_derived_and_every_claim_is_sourced() -> None:
    trace, _ = _trace()
    first = derive_composition_snapshot(trace)
    replay = derive_composition_snapshot(trace)

    assert first == replay
    assert first.derivation_status == "derived_from_trace"
    assert first.source_trace_hash == trace.trace_hash
    assert first.through_measure_id == trace.measures[-1].measure_id
    assert "shared tension" in first.unresolved_tensions
    assert first.relationship_patterns == ("acceptance_mode:accepting",)
    assert first.composition_hash is not None
    assert first.sourced_claims
    assert type(first).model_validate_json(first.model_dump_json()) == first
    for claim in first.sourced_claims:
        assert set(claim.evidence_measure_ids).issubset(first.evidence_measure_ids)

    payload = first.model_dump(mode="python", round_trip=True)
    payload["current_section"] = "tampered"
    with pytest.raises(ValidationError):
        type(first).model_validate(payload)


def test_correction_changes_derived_identity_without_rewriting_measure() -> None:
    trace, _ = _trace(1)
    original_measure = trace.measures[0]
    before = derive_composition_snapshot(trace)
    correction = EgoCorrectionEvent.create(
        ego_id=trace.ego_id,
        target_measure_id=original_measure.measure_id,
        reason="new evidence",
        correction="the prior outcome description was incomplete",
        recorded_at=NOW + timedelta(hours=1),
    )
    corrected = trace.append_correction(correction)
    after = derive_composition_snapshot(corrected)

    assert corrected.measures[0] == original_measure
    assert after.source_trace_hash == corrected.trace_hash
    assert after.snapshot_id != before.snapshot_id
    assert after.composition_hash != before.composition_hash


def test_modality_projections_are_deterministic_content_addressed_and_separate() -> None:
    trace, raw_bundles = _trace()
    bundles = {key: value for key, value in raw_bundles.items()}
    first = derive_modality_projections(trace, bundles)
    replay = derive_modality_projections(trace, bundles)

    assert first == replay
    assert first.racio.chronology
    assert first.emocio.recurring_scenes
    assert first.instinkt.body_consequences
    assert all(claim.kind.startswith("racio_") for claim in first.racio.sourced_claims)
    assert all(claim.kind.startswith("emocio_") for claim in first.emocio.sourced_claims)
    assert all(claim.kind.startswith("instinkt_") for claim in first.instinkt.sourced_claims)
    assert {
        first.racio.projection_id,
        first.emocio.projection_id,
        first.instinkt.projection_id,
    } == {
        replay.racio.projection_id,
        replay.emocio.projection_id,
        replay.instinkt.projection_id,
    }
    for projection in first:
        restored = type(projection).model_validate_json(projection.model_dump_json())
        assert restored == projection

    payload = first.racio.model_dump(mode="python", round_trip=True)
    payload["chronology"] = ("event:tampered",)
    with pytest.raises(ValidationError):
        RacioProjection.model_validate(payload)


def test_projection_requires_every_measure_bundle() -> None:
    trace, _ = _trace(1)
    with pytest.raises(ValueError, match="Missing native bundle"):
        derive_modality_projections(trace, {})


def test_in_memory_store_is_append_only_optimistic_and_thread_safe() -> None:
    store = InMemoryEgoTraceStore()
    assert isinstance(store, EgoTraceStore)
    genesis = store.load_trace("ego_b4")
    _, _, _, _, measure_0 = _measure(0)
    store.append_measure(
        "ego_b4",
        measure_0,
        expected_trace_hash=genesis.trace_hash,
    )
    with pytest.raises(EgoTraceConflictError, match="changed"):
        store.append_measure(
            "ego_b4",
            _measure(1)[-1],
            expected_trace_hash=genesis.trace_hash,
        )
    with pytest.raises(EgoTraceConflictError, match="already present"):
        store.append_measure("ego_b4", measure_0)

    concurrent_measures = tuple(_measure(index)[-1] for index in range(1, 9))
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(
            executor.map(
                lambda measure: store.append_measure("ego_b4", measure),
                concurrent_measures,
            )
        )
    loaded = store.load_trace("ego_b4")
    assert len(loaded.measures) == 9
    assert {measure.measure_id for measure in loaded.measures} == {
        measure_0.measure_id,
        *(measure.measure_id for measure in concurrent_measures),
    }
    correction = EgoCorrectionEvent.create(
        ego_id="ego_b4",
        target_measure_id=measure_0.measure_id,
        reason="new evidence",
        correction="append a correction without rewriting the measure",
        recorded_at=NOW + timedelta(hours=2),
    )
    store.append_correction(
        "ego_b4",
        correction,
        expected_trace_hash=loaded.trace_hash,
    )
    corrected = store.load_trace("ego_b4")
    assert corrected.measures[0] == measure_0
    assert corrected.corrections == (correction,)


def test_file_store_is_atomic_restart_safe_conflict_aware_and_tamper_evident(
    tmp_path,
) -> None:
    first_store = FileEgoTraceStore(tmp_path / "ego-store")
    second_store = FileEgoTraceStore(tmp_path / "ego-store")
    assert isinstance(first_store, EgoTraceStore)
    genesis = first_store.load_trace("ego_b4_file")
    measure_0 = _measure(0)[-1]
    first_store.append_measure(
        "ego_b4_file",
        measure_0,
        expected_trace_hash=genesis.trace_hash,
    )
    assert second_store.load_trace("ego_b4_file").measures == (measure_0,)

    concurrent_measures = (_measure(1)[-1], _measure(2)[-1])
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(first_store.append_measure, "ego_b4_file", concurrent_measures[0]),
            executor.submit(second_store.append_measure, "ego_b4_file", concurrent_measures[1]),
        )
        for future in futures:
            future.result()
    restarted = FileEgoTraceStore(tmp_path / "ego-store")
    loaded = restarted.load_trace("ego_b4_file")
    assert len(loaded.measures) == 3
    assert not tuple((tmp_path / "ego-store").glob("*.tmp"))
    assert restarted.trace_path("ego_b4_file").read_bytes() == loaded.canonical_json_bytes()

    correction = EgoCorrectionEvent.create(
        ego_id="ego_b4_file",
        target_measure_id=measure_0.measure_id,
        reason="new evidence",
        correction="append-only file correction",
        recorded_at=NOW + timedelta(hours=2),
    )
    restarted.append_correction(
        "ego_b4_file",
        correction,
        expected_trace_hash=loaded.trace_hash,
    )
    loaded = FileEgoTraceStore(tmp_path / "ego-store").load_trace("ego_b4_file")
    assert loaded.measures[0] == measure_0
    assert loaded.corrections == (correction,)

    stale_hash = genesis.trace_hash
    with pytest.raises(EgoTraceConflictError, match="changed"):
        restarted.append_measure(
            "ego_b4_file",
            _measure(3)[-1],
            expected_trace_hash=stale_hash,
        )

    trace_path = restarted.trace_path("ego_b4_file")
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    payload["trace_hash"] = "0" * 64
    trace_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EgoTraceTamperError):
        restarted.load_trace("ego_b4_file")


def test_file_store_never_uses_raw_ego_id_as_a_path(tmp_path) -> None:
    store = FileEgoTraceStore(tmp_path / "ego-store")
    path = store.trace_path("../../outside")
    assert path.parent == (tmp_path / "ego-store").resolve()
    assert ".." not in path.name
