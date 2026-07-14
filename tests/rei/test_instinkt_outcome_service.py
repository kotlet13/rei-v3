from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import ValidationError

from app.backend.rei.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei.ego.trace_store import FileEgoTraceStore
from app.backend.rei.ids import canonical_json_bytes, content_id, sha256_hex
from app.backend.rei.instinkt.dynamics import simulate_option_rollout
from app.backend.rei.instinkt.processor import process_instinkt
from app.backend.rei.instinkt.outcome_learning import (
    ExecutedActionReceipt,
    GroundedOutcomeEvidence,
    InstinktOutcomeLearningTrace,
    InstinktOutcomeUpdate,
    NormalizedBodyMeasurement,
)
from app.backend.rei.instinkt.outcome_service import (
    InstinktOutcomeAdmissionError,
    issue_executed_action_receipt,
    record_instinkt_outcome,
    replay_instinkt_outcome_update,
)
from app.backend.rei.instinkt.outcome_store import (
    FileInstinktOutcomeLearningStore,
    InstinktOutcomeStoreTamperError,
    InstinktOutcomeStoreVerificationRequiredError,
)
from app.backend.rei.models.ego import OutcomeRecord
from app.backend.rei.models.instinkt import (
    BODY_DIMENSIONS,
    BodyState,
    InstinktAssociation,
    InstinktCueEvidenceBinding,
    InstinktCueEvidenceCitation,
    InstinktWorld,
)
from app.backend.rei.models.scene import DecisionOption, EvidenceItem, SceneEvent
from app.backend.rei.models.run import RunArtifactRecord, RunManifest
from app.backend.rei.persistence.artifacts import FileArtifactStore
from app.backend.rei.providers.deterministic import (
    DeterministicInstinktNativeProvider,
    DeterministicNativeProviders,
    InstinktNativeExecution as DeterministicInstinktNativeExecution,
    build_deterministic_native_providers,
)
from app.backend.rei.providers.native import DeterministicExecutionClock


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"


class _OmittingAssociationMatchesProvider(DeterministicInstinktNativeProvider):
    """Return a self-consistent rollout that improperly ignores supplied memory."""

    def execute(self, **kwargs):
        honest = super().execute(**kwargs)
        assert any(item.association_matches for item in honest.rollouts)
        forged_processing = process_instinkt(
            scene=kwargs["scene"],
            packet=kwargs["packet"],
            source_body_state=kwargs["source_body_state"],
            option_effects=kwargs["option_effects"],
            config=kwargs["config"],
            memory=None,
        )
        forged_record = honest.call_record.model_copy(
            update={
                "output_artifact_ids": (
                    forged_processing.conclusion.conclusion_id,
                )
            }
        )
        return DeterministicInstinktNativeExecution(
            conclusion=forged_processing.conclusion,
            call_spec=honest.call_spec,
            call_record=forged_record,
            packet=honest.packet,
            source_body_state=honest.source_body_state,
            option_effects=honest.option_effects,
            associations=honest.associations,
            processing=forged_processing,
        )


def _request(
    *,
    run_id: str = "c5_outcome_service_run",
    ego_id: str = "c5_outcome_service_ego",
    tension: float = 0.3,
    world: InstinktWorld | None = None,
    body_state: BodyState | None = None,
    associations: tuple[InstinktAssociation, ...] = (),
) -> ReiNativeCycleRequest:
    base = ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())
    scene = SceneEvent(
        event_id="c5_service_threat_event",
        raw_input="A synthetic physical threat permits leaving or staying.",
        language="en",
        evidence=(
            EvidenceItem(
                evidence_id="c5_service_scene_e1",
                modality="text",
                content="A physical threat and immediate danger are visibly present.",
                grounded=True,
                source_ref="fixture:c5-service-scene",
                confidence=1.0,
            ),
        ),
        options=(
            DecisionOption(
                option_id="option_leave",
                label="leave",
                description="Leave and avoid the threat.",
            ),
            DecisionOption(
                option_id="option_stay",
                label="stay",
                description="Stay and approach the danger.",
            ),
        ),
        actors=("self",),
    )
    source_body = body_state or base.body_state.model_copy(
        update={"body_state_id": f"{run_id}_body", "tension": tension}
    )
    cue_start = scene.evidence[0].content.casefold().index("physical threat")
    cue_citation = InstinktCueEvidenceCitation.create(
        evidence=scene.evidence[0],
        start_char=cue_start,
        end_char=cue_start + len("physical threat"),
    )
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "run_id": run_id,
            "ego_id": ego_id,
            "scene": scene,
            "body_state": source_body,
            "instinkt_effect_source": "rule_based",
            "instinkt_effect_specs": (),
            "instinkt_world": world or InstinktWorld.create(),
            "instinkt_associations": associations,
            "instinkt_physical_cues": ("physical threat danger",),
            "instinkt_uncertainty_cues": (),
            "instinkt_boundary_cues": (),
            "instinkt_escape_cues": (),
            "instinkt_explicit_body_cues": (),
            "instinkt_evidence_ids": ("c5_service_scene_e1",),
            "instinkt_cue_evidence_bindings": (
                InstinktCueEvidenceBinding.create(
                    lane="physical_cues",
                    cue_class="physical_threat",
                    cue="physical threat danger",
                    assertion_status="asserted_positive",
                    citations=(cue_citation,),
                ),
            ),
            "symbolic_and_language_cues": None,
            "explicit_consequences": (),
            "historical_bundles": (),
        }
    )
    return ReiNativeCycleRequest.model_validate(payload)


def _completed_run(
    tmp_path: Path,
    *,
    request: ReiNativeCycleRequest | None = None,
    ego_traces_root: Path | None = None,
):
    active_request = request or _request()
    runs_root = tmp_path / "runs"
    ego_root = ego_traces_root or tmp_path / "ego"
    engine = ReiNativeEngine.with_file_stores(
        runs_root=runs_root,
        ego_traces_root=ego_root,
        clock=DeterministicExecutionClock(active_request.started_at),
    )
    result = engine.run_cycle(active_request)
    assert result.behavior_resultant.status == "executed"
    assert result.behavior_resultant.option_id is not None
    assert result.manifest.finished_at is not None
    return active_request, result, runs_root, ego_root


def _outcome_inputs(
    *,
    request: ReiNativeCycleRequest,
    cycle,
    artifact_store: FileArtifactStore,
    after_tension: float | None = None,
    status: str = "measured_change",
    outcome_id: str = "c5_service_outcome",
):
    finished = cycle.manifest.finished_at
    assert finished is not None
    receipt = issue_executed_action_receipt(
        run_id=request.run_id,
        executor_kind="external_executor",
        executed_at=finished + timedelta(seconds=1),
        artifact_store=artifact_store,
    )
    evidence_id = f"{outcome_id}_evidence"
    evidence = (
        GroundedOutcomeEvidence(
            evidence=EvidenceItem(
                evidence_id=evidence_id,
                modality="body",
                content="A normalized post-action tension measurement was observed.",
                grounded=True,
                source_ref="outcome-sensor:c5-service",
                confidence=0.9,
            ),
            observed_at=finished + timedelta(seconds=2),
        ),
    )
    target = (
        request.body_state.tension
        if after_tension is None and status == "measured_no_change"
        else (
            min(1.0, request.body_state.tension + 0.2)
            if after_tension is None
            else after_tension
        )
    )
    measurement = NormalizedBodyMeasurement.create(
        action_receipt=receipt,
        body_before=request.body_state,
        dimension="tension",
        status=status,
        after_value=target,
        evidence=evidence,
    )
    record = OutcomeRecord(
        outcome_id=outcome_id,
        event_id=request.scene.event_id,
        recorded_at=finished + timedelta(seconds=3),
        source="external_observation",
        observed_effects=("A typed normalized body measurement was recorded.",),
        evidence_ids=(evidence_id,),
    )
    admitted_at = finished + timedelta(seconds=4)
    return receipt, record, evidence, (measurement,), admitted_at


def _verifier(store: FileArtifactStore, verified_at):
    return lambda update: replay_instinkt_outcome_update(
        update,
        artifact_store=store,
        verified_at=verified_at,
    )


def _replace_run_artifact_and_resign(
    *,
    store: FileArtifactStore,
    manifest: RunManifest,
    relative_path: str,
    value,
) -> RunManifest:
    """Model a historically persisted, internally re-signed provider mutant."""

    raw = canonical_json_bytes(value)
    store.artifact_path(manifest.run_id, relative_path).write_bytes(raw)
    metadata = {
        "schema_version": "rei-native-stored-artifact-v1",
        "run_id": manifest.run_id,
        "relative_path": relative_path,
        "content_sha256": sha256_hex(value),
        "size_bytes": len(raw),
    }
    replacement = RunArtifactRecord(
        storage_id=content_id("stored", metadata),
        **metadata,
    )
    inventory = tuple(
        replacement if item.relative_path == relative_path else item
        for item in manifest.artifact_inventory
    )
    provisional_payload = manifest.model_dump(
        mode="python",
        round_trip=True,
        exclude={
            "manifest_id",
            "artifact_inventory",
            "artifact_inventory_hash",
            "manifest_hash",
        },
    )
    provisional_payload["schema_version"] = "rei-native-run-manifest-v1"
    provisional = RunManifest.model_validate(provisional_payload)
    resigned = RunManifest.finalize_v2(provisional, inventory)
    manifest_bytes = resigned.canonical_json_bytes()
    for anchor in (
        "diagnostics/prepared_manifest.json",
        "run_manifest.json",
    ):
        store.artifact_path(manifest.run_id, anchor).write_bytes(manifest_bytes)
    return resigned


def test_post_cycle_service_cold_loads_and_cas_appends_actual_outcome(
    tmp_path: Path,
) -> None:
    request, cycle, runs_root, _ = _completed_run(tmp_path)
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request,
        cycle=cycle,
        artifact_store=artifact_store,
    )
    learning_store = FileInstinktOutcomeLearningStore(tmp_path / "learning")
    learned = record_instinkt_outcome(
        run_id=request.run_id,
        action_receipt=receipt,
        outcome_record=record,
        measurements=measurements,
        outcome_evidence=evidence,
        uncertainty="One normalized post-run observation; no medical inference.",
        artifact_store=artifact_store,
        learning_store=learning_store,
        admission_clock=lambda: admitted_at,
    )
    assert learned.observation.source_action_receipt_id == receipt.receipt_id
    assert learned.observation.option_id == cycle.behavior_resultant.option_id
    assert learned.update.learned_association.action_taken == receipt.executed_option_id
    assert learned.update.learned_association.outcome == record.outcome_id
    assert learned.update.learned_association.cue_classes == ("physical_threat",)

    verifier = _verifier(artifact_store, admitted_at)
    cold_trace = FileInstinktOutcomeLearningStore(tmp_path / "learning").load_trace(
        request.ego_id,
        verifier=verifier,
    )
    assert cold_trace == learned.trace
    empty_hash = InstinktOutcomeLearningTrace.empty(ego_id=request.ego_id).trace_hash
    assert learning_store.append_update(
        request.ego_id,
        learned.update,
        expected_trace_hash=empty_hash,
        verifier=verifier,
    ) == learned.trace
    with pytest.raises(InstinktOutcomeStoreVerificationRequiredError):
        FileInstinktOutcomeLearningStore(tmp_path / "learning").load_trace(
            request.ego_id
        )


def test_wrong_run_or_self_consistent_wrong_action_receipt_is_rejected(
    tmp_path: Path,
) -> None:
    request_a, cycle_a, runs_root, _ = _completed_run(
        tmp_path,
        request=_request(run_id="c5_receipt_run_a", ego_id="c5_receipt_ego_a"),
    )
    request_b, cycle_b, _, _ = _completed_run(
        tmp_path,
        request=_request(run_id="c5_receipt_run_b", ego_id="c5_receipt_ego_b"),
    )
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request_a,
        cycle=cycle_a,
        artifact_store=artifact_store,
    )
    with pytest.raises(InstinktOutcomeAdmissionError, match="receipt"):
        record_instinkt_outcome(
            run_id=request_b.run_id,
            action_receipt=receipt,
            outcome_record=record.model_copy(
                update={"event_id": request_b.scene.event_id}
            ),
            measurements=measurements,
            outcome_evidence=evidence,
            uncertainty="Wrong run must fail.",
            artifact_store=artifact_store,
            learning_store=FileInstinktOutcomeLearningStore(tmp_path / "wrong-run"),
            admission_clock=lambda: admitted_at,
        )

    other_option = next(
        item.option_id
        for item in request_a.scene.options
        if item.option_id != receipt.executed_option_id
    )
    base = receipt.model_dump(
        mode="python", round_trip=True, exclude={"receipt_id", "receipt_hash"}
    )
    base["executed_option_id"] = other_option
    receipt_id = content_id("executed_action_receipt", base)
    payload = {"receipt_id": receipt_id, **base}
    forged = ExecutedActionReceipt.model_validate(
        {**payload, "receipt_hash": sha256_hex(payload)}
    )
    with pytest.raises(InstinktOutcomeAdmissionError, match="receipt"):
        record_instinkt_outcome(
            run_id=request_a.run_id,
            action_receipt=forged,
            outcome_record=record,
            measurements=measurements,
            outcome_evidence=evidence,
            uncertainty="Wrong action must fail.",
            artifact_store=artifact_store,
            learning_store=FileInstinktOutcomeLearningStore(tmp_path / "wrong-action"),
            admission_clock=lambda: admitted_at,
        )
    assert cycle_b.manifest.finished_at is not None


def test_measured_no_change_is_distinct_from_unobserved_dimensions(
    tmp_path: Path,
) -> None:
    request, cycle, runs_root, _ = _completed_run(tmp_path)
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request,
        cycle=cycle,
        artifact_store=artifact_store,
        status="measured_no_change",
    )
    learned = record_instinkt_outcome(
        run_id=request.run_id,
        action_receipt=receipt,
        outcome_record=record,
        measurements=measurements,
        outcome_evidence=evidence,
        uncertainty="Explicit evidence-backed no-change measurement.",
        artifact_store=artifact_store,
        learning_store=FileInstinktOutcomeLearningStore(tmp_path / "learning"),
        admission_clock=lambda: admitted_at,
    )
    assert tuple(item.dimension for item in learned.update.residuals) == ("tension",)
    assert learned.update.residuals[0].observed_delta == 0.0
    for dimension in BODY_DIMENSIONS:
        if dimension != "tension":
            assert getattr(learned.update.body_after, dimension) == getattr(
                request.body_state, dimension
            )


def test_admission_clock_rejects_future_receipt_and_outcome(tmp_path: Path) -> None:
    request, cycle, runs_root, _ = _completed_run(tmp_path)
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request,
        cycle=cycle,
        artifact_store=artifact_store,
    )
    with pytest.raises(InstinktOutcomeAdmissionError, match="receipt.*future"):
        record_instinkt_outcome(
            run_id=request.run_id,
            action_receipt=receipt,
            outcome_record=record,
            measurements=measurements,
            outcome_evidence=evidence,
            uncertainty="Future receipt must fail.",
            artifact_store=artifact_store,
            learning_store=FileInstinktOutcomeLearningStore(tmp_path / "learning"),
            admission_clock=lambda: receipt.executed_at - timedelta(microseconds=1),
        )
    assert admitted_at > record.recorded_at


def test_residual_uses_saturated_selected_rollout_delta(tmp_path: Path) -> None:
    request = _request(
        run_id="c5_saturation_run",
        ego_id="c5_saturation_ego",
        tension=0.05,
    )
    request, cycle, runs_root, _ = _completed_run(tmp_path, request=request)
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request,
        cycle=cycle,
        artifact_store=artifact_store,
        after_tension=0.0,
    )
    learned = record_instinkt_outcome(
        run_id=request.run_id,
        action_receipt=receipt,
        outcome_record=record,
        measurements=measurements,
        outcome_evidence=evidence,
        uncertainty="Saturated normalized body boundary.",
        artifact_store=artifact_store,
        learning_store=FileInstinktOutcomeLearningStore(tmp_path / "learning"),
        admission_clock=lambda: admitted_at,
    )
    residual = learned.update.residuals[0]
    assert residual.predicted_delta == pytest.approx(-0.05)
    assert residual.observed_delta == pytest.approx(-0.05)
    assert residual.residual == pytest.approx(0.0)


def test_cold_replay_rejects_recomputed_self_consistent_tamper(tmp_path: Path) -> None:
    request, cycle, runs_root, _ = _completed_run(tmp_path)
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request,
        cycle=cycle,
        artifact_store=artifact_store,
    )
    learning_store = FileInstinktOutcomeLearningStore(tmp_path / "learning")
    learned = record_instinkt_outcome(
        run_id=request.run_id,
        action_receipt=receipt,
        outcome_record=record,
        measurements=measurements,
        outcome_evidence=evidence,
        uncertainty="Tamper source.",
        artifact_store=artifact_store,
        learning_store=learning_store,
        admission_clock=lambda: admitted_at,
    )
    base = learned.update.model_dump(
        mode="python", round_trip=True, exclude={"update_id", "update_hash"}
    )
    base["body_after"]["tension"] = 0.99
    base["body_after"]["body_state_id"] = "forged_body_after"
    update_id = content_id("instinkt_outcome_update", base)
    payload = {"update_id": update_id, **base}
    forged_update = InstinktOutcomeUpdate.model_validate(
        {**payload, "update_hash": sha256_hex(payload)}
    )
    forged_trace = InstinktOutcomeLearningTrace.create(
        ego_id=request.ego_id,
        updates=(forged_update,),
    )
    learning_store.trace_path(request.ego_id).write_bytes(
        forged_trace.canonical_json_bytes()
    )
    with pytest.raises(InstinktOutcomeStoreTamperError, match="cold deterministic"):
        learning_store.load_trace(
            request.ego_id,
            verifier=_verifier(artifact_store, admitted_at),
        )


def test_engine_rejects_provider_that_omits_canonical_memory_match(
    tmp_path: Path,
) -> None:
    base = _request(
        run_id="c5_omitted_memory_match_run",
        ego_id="c5_omitted_memory_match_ego",
    )
    association = InstinktAssociation(
        association_id="c5_omitted_memory_match_association",
        cue_signature=("physical threat danger",),
        body_state_before=base.body_state,
        felt_intensity=0.8,
        protected_target="virtual bodily integrity",
        experienced_loss="threat harm",
        action_taken="leave",
        outcome="safe exit",
        trust_delta=0.0,
        attachment_delta=0.0,
        boundary_delta=0.0,
        decay=0.0,
    )
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "instinkt_world": InstinktWorld.create(
                associations=(association.association_id,)
            ),
            "instinkt_associations": (association,),
        }
    )
    request = ReiNativeCycleRequest.model_validate(payload)
    runs_root = tmp_path / "runs"
    ego_root = tmp_path / "ego"
    defaults = build_deterministic_native_providers()
    providers = DeterministicNativeProviders(
        racio=defaults.racio,
        emocio=defaults.emocio,
        instinkt=_OmittingAssociationMatchesProvider(),  # type: ignore[arg-type]
    )
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(runs_root),
        ego_trace_store=FileEgoTraceStore(ego_root),
        providers=providers,
        clock=DeterministicExecutionClock(request.started_at),
    )
    with pytest.raises(ValueError, match="canonical B8 memory retrieval"):
        engine.run_cycle(request)

    store = FileArtifactStore(runs_root)
    assert not store.artifact_path(request.run_id, "run_manifest.json").exists()
    assert not store.artifact_path(
        request.run_id, "diagnostics/prepared_manifest.json"
    ).exists()
    assert FileEgoTraceStore(ego_root).load_trace(request.ego_id).measures == ()


def test_cold_run_rejects_resigned_rollouts_with_omitted_memory_matches(
    tmp_path: Path,
) -> None:
    base = _request(
        run_id="c5_cold_omitted_match_run",
        ego_id="c5_cold_omitted_match_ego",
    )
    association = InstinktAssociation(
        association_id="c5_cold_omitted_match_association",
        cue_signature=("physical threat danger",),
        body_state_before=base.body_state,
        felt_intensity=0.8,
        protected_target="virtual bodily integrity",
        experienced_loss="threat harm",
        action_taken="leave",
        outcome="safe exit",
        trust_delta=0.0,
        attachment_delta=0.0,
        boundary_delta=0.0,
        decay=0.0,
    )
    payload = base.model_dump(mode="python", round_trip=True)
    payload.update(
        {
            "instinkt_world": InstinktWorld.create(
                associations=(association.association_id,)
            ),
            "instinkt_associations": (association,),
        }
    )
    request = ReiNativeCycleRequest.model_validate(payload)
    request, cycle, runs_root, _ = _completed_run(tmp_path, request=request)
    assert all(
        rollout.association_matches
        for rollout in cycle.instinkt_execution.rollouts
    )
    effects = {
        item.option_id: item for item in cycle.instinkt_execution.option_effects
    }
    forged_rollouts = tuple(
        simulate_option_rollout(
            packet=cycle.instinkt_packet,
            source_body_state=request.body_state,
            effect=effects[rollout.option_id],
            config=cycle.instinkt_execution.config,
            association_matches=(),
        )
        for rollout in cycle.instinkt_execution.rollouts
    )
    store = FileArtifactStore(runs_root)
    resigned = _replace_run_artifact_and_resign(
        store=store,
        manifest=cycle.manifest,
        relative_path="instinkt/option_rollouts.json",
        value=forged_rollouts,
    )
    assert store.verify_run(request.run_id) == resigned
    assert resigned.finished_at is not None

    with pytest.raises(InstinktOutcomeAdmissionError, match="cold deterministic replay"):
        issue_executed_action_receipt(
            run_id=request.run_id,
            executor_kind="external_executor",
            executed_at=resigned.finished_at + timedelta(seconds=1),
            artifact_store=store,
        )


def test_missing_world_association_materialization_is_rejected(tmp_path: Path) -> None:
    request, cycle, runs_root, _ = _completed_run(tmp_path)
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request,
        cycle=cycle,
        artifact_store=artifact_store,
    )
    learned = record_instinkt_outcome(
        run_id=request.run_id,
        action_receipt=receipt,
        outcome_record=record,
        measurements=measurements,
        outcome_evidence=evidence,
        uncertainty="Create learned association.",
        artifact_store=artifact_store,
        learning_store=FileInstinktOutcomeLearningStore(tmp_path / "learning"),
        admission_clock=lambda: admitted_at,
    )
    with pytest.raises(ValidationError, match="exact materialized record closure"):
        _request(
            run_id="c5_missing_materialization_run",
            ego_id="c5_missing_materialization_ego",
            world=learned.update.world_after,
            body_state=learned.update.body_after,
        )


def test_materialized_learned_association_supports_two_cycle_trace(
    tmp_path: Path,
) -> None:
    first_request, first_cycle, runs_root, _ = _completed_run(
        tmp_path,
        request=_request(
            run_id="c5_materialized_cycle_1",
            ego_id="c5_materialized_ego",
        ),
    )
    artifact_store = FileArtifactStore(runs_root)
    learning_store = FileInstinktOutcomeLearningStore(tmp_path / "learning")
    first_receipt, first_record, first_evidence, first_measurements, first_admitted = (
        _outcome_inputs(
            request=first_request,
            cycle=first_cycle,
            artifact_store=artifact_store,
            outcome_id="c5_materialized_outcome_1",
        )
    )
    first = record_instinkt_outcome(
        run_id=first_request.run_id,
        action_receipt=first_receipt,
        outcome_record=first_record,
        measurements=first_measurements,
        outcome_evidence=first_evidence,
        uncertainty="First evidence-backed outcome in a two-cycle trace.",
        artifact_store=artifact_store,
        learning_store=learning_store,
        admission_clock=lambda: first_admitted,
    )

    second_request = _request(
        run_id="c5_materialized_cycle_2",
        ego_id=first_request.ego_id,
        world=first.update.world_after,
        body_state=first.update.body_after,
        associations=(first.update.learned_association,),
    )
    second_request, second_cycle, _, _ = _completed_run(
        tmp_path,
        request=second_request,
        ego_traces_root=tmp_path / "ego-cycle-2",
    )
    second_receipt, second_record, second_evidence, second_measurements, second_admitted = (
        _outcome_inputs(
            request=second_request,
            cycle=second_cycle,
            artifact_store=artifact_store,
            outcome_id="c5_materialized_outcome_2",
        )
    )
    second = record_instinkt_outcome(
        run_id=second_request.run_id,
        action_receipt=second_receipt,
        outcome_record=second_record,
        measurements=second_measurements,
        outcome_evidence=second_evidence,
        uncertainty="Second evidence-backed outcome with materialized memory.",
        artifact_store=artifact_store,
        learning_store=learning_store,
        admission_clock=lambda: second_admitted,
    )

    assert second.trace.updates == (first.update, second.update)
    assert second.update.source_world_id == first.update.world_after.world_id
    assert second.update.source_body_state_id == first.update.body_after.body_state_id
    selected_rollout = next(
        item
        for item in second_cycle.instinkt_execution.rollouts
        if item.option_id == second.update.observation.option_id
    )
    assert tuple(
        item.association_id for item in selected_rollout.association_matches
    ) == (
        first.update.learned_association.association_id,
    )


def test_exact_update_retry_is_concurrency_safe(tmp_path: Path) -> None:
    request, cycle, runs_root, _ = _completed_run(tmp_path)
    artifact_store = FileArtifactStore(runs_root)
    receipt, record, evidence, measurements, admitted_at = _outcome_inputs(
        request=request,
        cycle=cycle,
        artifact_store=artifact_store,
    )
    store = FileInstinktOutcomeLearningStore(tmp_path / "learning")
    learned = record_instinkt_outcome(
        run_id=request.run_id,
        action_receipt=receipt,
        outcome_record=record,
        measurements=measurements,
        outcome_evidence=evidence,
        uncertainty="Concurrency source.",
        artifact_store=artifact_store,
        learning_store=store,
        admission_clock=lambda: admitted_at,
    )
    trace_path = store.trace_path(request.ego_id)
    trace_path.unlink()
    empty_hash = InstinktOutcomeLearningTrace.empty(ego_id=request.ego_id).trace_hash
    verifier = _verifier(artifact_store, admitted_at)
    barrier = Barrier(2)

    def append_once():
        barrier.wait()
        return store.append_update(
            request.ego_id,
            learned.update,
            expected_trace_hash=empty_hash,
            verifier=verifier,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda _: append_once(), range(2)))
    assert results[0] == results[1]
    assert results[0].updates == (learned.update,)


def test_store_rejects_symlink_trace_when_platform_supports_it(tmp_path: Path) -> None:
    store = FileInstinktOutcomeLearningStore(tmp_path / "learning")
    target = tmp_path / "outside.json"
    target.write_bytes(b"{}")
    trace_path = store.trace_path("symlink_ego")
    try:
        os.symlink(target, trace_path)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this Windows configuration")
    with pytest.raises(InstinktOutcomeStoreTamperError, match="symlink|reparse"):
        store.load_trace("symlink_ego")
