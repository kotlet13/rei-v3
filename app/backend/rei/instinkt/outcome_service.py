"""Cold, post-cycle admission and replay service for Instinkt outcome learning."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal

from pydantic import TypeAdapter, ValidationError

from ..ids import canonical_json_bytes, content_id, utc_now
from ..instinkt.association_memory import BoundedAssociativeMemory
from ..instinkt.dynamics import simulate_option_rollout
from ..models.common import FrozenModel, HashDigest, NonEmptyId, UtcTimestamp
from ..models.conscious import BehaviorResultant
from ..models.ego import OutcomeRecord
from ..models.instinkt import (
    BodyState,
    InstinktAssociation,
    InstinktInputPacket,
    InstinktMemoryRecord,
    InstinktOptionRollout,
    InstinktSimulationConfig,
    InstinktWorld,
    OptionBodyEffect,
    instinkt_association_content_id,
    instinkt_memory_record_id,
)
from ..models.instinkt_effects import (
    InstinktEffectRuleSet,
    OptionBodyEffectCompilation,
    OptionBodyEffectPrediction,
)
from ..models.run import RunManifest
from ..models.scene import DecisionOption, SceneEvent
from ..persistence.artifacts import FileArtifactStore
from ..providers.protocols import StoredArtifact
from .outcome_learning import (
    ExecutedActionReceipt,
    GroundedOutcomeEvidence,
    InstinktOutcomeLearningTrace,
    InstinktOutcomeObservation,
    InstinktOutcomeUpdate,
    NormalizedBodyMeasurement,
)
from .outcome_store import FileInstinktOutcomeLearningStore


class InstinktOutcomeAdmissionError(ValueError):
    """The completed run or later outcome cannot enter C5 learning."""


class _RunReservation(FrozenModel):
    schema_version: Literal["rei-native-run-reservation-v1"]
    run_id: NonEmptyId
    ego_id: NonEmptyId
    request_hash: HashDigest
    expected_trace_hash: HashDigest
    created_at: UtcTimestamp


class _EffectSourceRecord(FrozenModel):
    schema_version: Literal["rei-native-instinkt-effect-source-v1"]
    effect_source: Literal["manual_fixture", "rule_based", "model_backed"]


@dataclass(frozen=True, slots=True)
class InstinktOutcomeLearningResult:
    observation: InstinktOutcomeObservation
    update: InstinktOutcomeUpdate
    trace: InstinktOutcomeLearningTrace


@dataclass(frozen=True, slots=True)
class _ColdRunSources:
    manifest: RunManifest
    reservation: _RunReservation
    scene: SceneEvent
    packet: InstinktInputPacket
    world: InstinktWorld
    body_before: BodyState
    behavior: BehaviorResultant
    option: DecisionOption
    ruleset: InstinktEffectRuleSet
    prediction: OptionBodyEffectPrediction
    compilation: OptionBodyEffectCompilation
    effect: OptionBodyEffect
    rollout: InstinktOptionRollout
    typed_associations: tuple[InstinktAssociation, ...]


_PREDICTIONS = TypeAdapter(tuple[OptionBodyEffectPrediction, ...])
_COMPILATIONS = TypeAdapter(tuple[OptionBodyEffectCompilation, ...])
_EFFECTS = TypeAdapter(tuple[OptionBodyEffect, ...])
_ROLLOUTS = TypeAdapter(tuple[InstinktOptionRollout, ...])
_MEMORY = TypeAdapter(tuple[InstinktMemoryRecord, ...])


def _inventory_bytes(
    store: FileArtifactStore,
    manifest: RunManifest,
    relative_path: str,
) -> bytes:
    matches = tuple(
        item for item in manifest.artifact_inventory if item.relative_path == relative_path
    )
    if len(matches) != 1:
        raise InstinktOutcomeAdmissionError(
            f"Completed run inventory requires exactly one {relative_path!r}"
        )
    record = matches[0]
    return store.read_verified(
        StoredArtifact(**record.model_dump(mode="python", round_trip=True))
    )


def _load_model(
    store: FileArtifactStore,
    manifest: RunManifest,
    relative_path: str,
    model_type: type[FrozenModel],
) -> FrozenModel:
    raw = _inventory_bytes(store, manifest, relative_path)
    try:
        value = model_type.model_validate_json(raw)
    except (UnicodeError, ValidationError, ValueError) as exc:
        raise InstinktOutcomeAdmissionError(
            f"Completed run artifact {relative_path!r} failed validation"
        ) from exc
    if value.canonical_json_bytes() != raw:
        raise InstinktOutcomeAdmissionError(
            f"Completed run artifact {relative_path!r} is not canonical JSON"
        )
    return value


def _load_tuple(
    store: FileArtifactStore,
    manifest: RunManifest,
    relative_path: str,
    adapter: TypeAdapter,
) -> tuple[object, ...]:
    raw = _inventory_bytes(store, manifest, relative_path)
    try:
        value = adapter.validate_json(raw)
    except (UnicodeError, ValidationError, ValueError) as exc:
        raise InstinktOutcomeAdmissionError(
            f"Completed run artifact {relative_path!r} failed validation"
        ) from exc
    if canonical_json_bytes(value) != raw:
        raise InstinktOutcomeAdmissionError(
            f"Completed run artifact {relative_path!r} is not canonical JSON"
        )
    return value


def _single_for_option(values: tuple[object, ...], option_id: str, label: str):
    selected = tuple(
        item
        for item in values
        if (
            getattr(item, "option_id", None)
            or getattr(getattr(item, "option_body_effect", None), "option_id", None)
        )
        == option_id
    )
    if len(selected) != 1:
        raise InstinktOutcomeAdmissionError(
            f"Executed option requires exactly one persisted {label}"
        )
    return selected[0]


def _validate_association_closure(
    world: InstinktWorld,
    records: tuple[InstinktAssociation, ...],
) -> None:
    by_id = {item.association_id: item for item in records}
    if len(by_id) != len(records):
        raise InstinktOutcomeAdmissionError("Instinkt association records must be unique")
    if set(by_id) != set(world.associations):
        raise InstinktOutcomeAdmissionError(
            "InstinktWorld associations must have exact materialized memory closure"
        )
    for association in records:
        if association.association_id.startswith("instinkt_association_"):
            if association.association_id != instinkt_association_content_id(
                association
            ):
                raise InstinktOutcomeAdmissionError(
                    "Content-addressed learned association differs from its content"
                )


def _load_receipt_sources(
    *,
    run_id: NonEmptyId,
    artifact_store: FileArtifactStore,
) -> tuple[RunManifest, _RunReservation, SceneEvent, BehaviorResultant]:
    manifest = artifact_store.verify_run(run_id)
    if (
        manifest.manifest_id is None
        or manifest.manifest_hash is None
        or manifest.finished_at is None
    ):
        raise InstinktOutcomeAdmissionError(
            "Outcome learning requires a completed content-addressed run manifest"
        )
    reservation = _load_model(
        artifact_store,
        manifest,
        "diagnostics/run_reservation.json",
        _RunReservation,
    )
    scene = _load_model(
        artifact_store,
        manifest,
        "scene/event.json",
        SceneEvent,
    )
    behavior = _load_model(
        artifact_store,
        manifest,
        "behavior/resultant.json",
        BehaviorResultant,
    )
    assert isinstance(reservation, _RunReservation)
    assert isinstance(scene, SceneEvent)
    assert isinstance(behavior, BehaviorResultant)
    if reservation.run_id != run_id:
        raise InstinktOutcomeAdmissionError("Run reservation belongs to another run")
    return manifest, reservation, scene, behavior


def issue_executed_action_receipt(
    *,
    run_id: NonEmptyId,
    executor_kind: Literal["external_executor", "simulator"],
    executed_at: datetime,
    artifact_store: FileArtifactStore,
) -> ExecutedActionReceipt:
    """Issue a receipt from one explicitly selected completed run.

    Admission never calls this helper implicitly.  The caller must retain and
    later present the exact receipt with the outcome.
    """

    sources = _load_cold_run_sources(
        run_id=run_id,
        artifact_store=artifact_store,
    )
    manifest = sources.manifest
    assert manifest.manifest_id is not None
    assert manifest.manifest_hash is not None
    assert manifest.finished_at is not None
    try:
        return ExecutedActionReceipt.create(
            source_run_id=run_id,
            source_manifest_id=manifest.manifest_id,
            source_manifest_hash=manifest.manifest_hash,
            source_run_finished_at=manifest.finished_at,
            scene=sources.scene,
            behavior=sources.behavior,
            executor_kind=executor_kind,
            executed_at=executed_at,
        )
    except ValueError as exc:
        raise InstinktOutcomeAdmissionError("Completed run cannot issue action receipt") from exc


def _load_cold_run_sources(
    *,
    run_id: NonEmptyId,
    artifact_store: FileArtifactStore,
) -> _ColdRunSources:
    manifest, reservation, scene, behavior = _load_receipt_sources(
        run_id=run_id,
        artifact_store=artifact_store,
    )
    if (
        behavior.derivation_status != "derived_b10"
        or behavior.status != "executed"
        or behavior.option_id is None
        or behavior.source_scene_id != scene.event_id
    ):
        raise InstinktOutcomeAdmissionError(
            "Outcome learning requires a derived executed behavior option"
        )
    option = next(
        (item for item in scene.options if item.option_id == behavior.option_id),
        None,
    )
    if option is None:
        raise InstinktOutcomeAdmissionError(
            "Executed behavior option is absent from the completed scene"
        )

    packet = _load_model(
        artifact_store, manifest, "scene/instinkt_packet.json", InstinktInputPacket
    )
    world = _load_model(
        artifact_store, manifest, "scene/instinkt_world.json", InstinktWorld
    )
    body_before = _load_model(
        artifact_store, manifest, "instinkt/body_before.json", BodyState
    )
    effect_source = _load_model(
        artifact_store, manifest, "instinkt/effect_source.json", _EffectSourceRecord
    )
    ruleset = _load_model(
        artifact_store, manifest, "instinkt/effect_ruleset.json", InstinktEffectRuleSet
    )
    config = _load_model(
        artifact_store,
        manifest,
        "instinkt/simulation_config.json",
        InstinktSimulationConfig,
    )
    predictions = _load_tuple(
        artifact_store, manifest, "instinkt/effect_predictions.json", _PREDICTIONS
    )
    compilations = _load_tuple(
        artifact_store, manifest, "instinkt/effect_compilations.json", _COMPILATIONS
    )
    effects = _load_tuple(
        artifact_store, manifest, "instinkt/option_effects.json", _EFFECTS
    )
    rollouts = _load_tuple(
        artifact_store, manifest, "instinkt/option_rollouts.json", _ROLLOUTS
    )
    memory = _load_tuple(
        artifact_store, manifest, "instinkt/ego_memory.json", _MEMORY
    )
    assert isinstance(packet, InstinktInputPacket)
    assert isinstance(world, InstinktWorld)
    assert isinstance(body_before, BodyState)
    assert isinstance(effect_source, _EffectSourceRecord)
    assert isinstance(ruleset, InstinktEffectRuleSet)
    assert isinstance(config, InstinktSimulationConfig)
    if effect_source.effect_source != "rule_based":
        raise InstinktOutcomeAdmissionError(
            "Post-cycle outcome learning requires rule_based prediction lineage"
        )
    prediction = _single_for_option(
        predictions, behavior.option_id, "non-abstaining body prediction"
    )
    compilation = _single_for_option(
        compilations, behavior.option_id, "body-effect compilation"
    )
    effect = _single_for_option(effects, behavior.option_id, "typed body effect")
    rollout = _single_for_option(rollouts, behavior.option_id, "B8 option rollout")
    assert isinstance(prediction, OptionBodyEffectPrediction)
    assert isinstance(compilation, OptionBodyEffectCompilation)
    assert isinstance(effect, OptionBodyEffect)
    assert isinstance(rollout, InstinktOptionRollout)
    if prediction.abstains or prediction.effect_source != "rule_based":
        raise InstinktOutcomeAdmissionError(
            "Executed option requires one non-abstaining rule-based prediction"
        )
    typed_associations = tuple(
        item for item in memory if isinstance(item, InstinktAssociation)
    )
    _validate_association_closure(world, typed_associations)
    try:
        canonical_memory = tuple(sorted(memory, key=instinkt_memory_record_id))
        memory_ids = tuple(instinkt_memory_record_id(item) for item in canonical_memory)
        if memory != canonical_memory or len(set(memory_ids)) != len(memory_ids):
            raise ValueError(
                "Persisted Instinkt memory must use canonical unique record order"
            )
        bounded_memory = BoundedAssociativeMemory()
        for record in canonical_memory:
            bounded_memory.add(record)
        effect_by_option = {item.option_id: item for item in effects}
        rollout_by_option = {item.option_id: item for item in rollouts}
        if (
            len(effect_by_option) != len(effects)
            or len(rollout_by_option) != len(rollouts)
            or set(effect_by_option) != set(packet.option_ids)
            or set(rollout_by_option) != set(packet.option_ids)
        ):
            raise ValueError(
                "Persisted effects and rollouts must exactly cover packet options"
            )
        recomputed_matches_by_option = {
            option_id: bounded_memory.retrieve(
                effect_by_option[option_id].association_cue_tokens
            )
            for option_id in sorted(effect_by_option)
        }
        if any(
            rollout_by_option[option_id].association_matches
            != recomputed_matches_by_option[option_id]
            for option_id in sorted(effect_by_option)
        ):
            raise ValueError(
                "Persisted rollout association matches differ from canonical "
                "B8 memory retrieval"
            )
        packet.validate_against(scene, body_before)
        prediction.validate_against(
            scene=scene,
            packet=packet,
            world=world,
            body=body_before,
            option=option,
            ruleset=ruleset,
            association_records=typed_associations,
        )
        compilation.validate_against(
            prediction=prediction,
            ruleset=ruleset,
            packet=packet,
        )
        if compilation.option_body_effect != effect:
            raise ValueError("Persisted typed effect differs from compilation")
        rollout.validate_simulation_lineage(
            packet=packet,
            source_body_state=body_before,
            effect=effect,
            config=config,
            association_matches=recomputed_matches_by_option[effect.option_id],
        )
        replayed_rollout = simulate_option_rollout(
            packet=packet,
            source_body_state=body_before,
            effect=effect,
            config=config,
            association_matches=recomputed_matches_by_option[effect.option_id],
        )
        if replayed_rollout != rollout:
            raise ValueError("Persisted selected rollout differs from deterministic replay")
    except ValueError as exc:
        raise InstinktOutcomeAdmissionError(
            "Selected Instinkt outcome lineage failed cold deterministic replay"
        ) from exc
    return _ColdRunSources(
        manifest=manifest,
        reservation=reservation,
        scene=scene,
        packet=packet,
        world=world,
        body_before=body_before,
        behavior=behavior,
        option=option,
        ruleset=ruleset,
        prediction=prediction,
        compilation=compilation,
        effect=effect,
        rollout=rollout,
        typed_associations=typed_associations,
    )


def replay_instinkt_outcome_update(
    update: InstinktOutcomeUpdate,
    *,
    artifact_store: FileArtifactStore,
    verified_at: datetime,
) -> None:
    """Cold-replay one persisted update against its immutable completed run."""

    if update.created_at > verified_at:
        raise InstinktOutcomeAdmissionError("Outcome update is dated in the future")
    sources = _load_cold_run_sources(
        run_id=update.source_run_id,
        artifact_store=artifact_store,
    )
    manifest = sources.manifest
    assert manifest.manifest_id is not None
    assert manifest.manifest_hash is not None
    assert manifest.finished_at is not None
    receipt = update.observation.action_receipt
    try:
        receipt.validate_against(
            source_run_id=update.source_run_id,
            source_manifest_id=manifest.manifest_id,
            source_manifest_hash=manifest.manifest_hash,
            source_run_finished_at=manifest.finished_at,
            scene=sources.scene,
            behavior=sources.behavior,
        )
        update.observation.validate_against(
            scene=sources.scene,
            body_before=sources.body_before,
            action_receipt=receipt,
            outcome_record=update.observation.outcome_record,
        )
        update.validate_against(
            ego_id=sources.reservation.ego_id,
            prediction=sources.prediction,
            rollout=sources.rollout,
            outcome=update.observation,
            ruleset=sources.ruleset,
            world=sources.world,
            body_before=sources.body_before,
        )
    except ValueError as exc:
        raise InstinktOutcomeAdmissionError(
            "Persisted outcome update failed cold deterministic replay"
        ) from exc


def _replay_verifier(
    *, artifact_store: FileArtifactStore, verified_at: datetime
) -> Callable[[InstinktOutcomeUpdate], None]:
    return lambda update: replay_instinkt_outcome_update(
        update,
        artifact_store=artifact_store,
        verified_at=verified_at,
    )


def record_instinkt_outcome(
    *,
    run_id: NonEmptyId,
    action_receipt: ExecutedActionReceipt,
    outcome_record: OutcomeRecord,
    measurements: tuple[NormalizedBodyMeasurement, ...],
    outcome_evidence: tuple[GroundedOutcomeEvidence, ...],
    uncertainty: str,
    artifact_store: FileArtifactStore,
    learning_store: FileInstinktOutcomeLearningStore,
    admission_clock: Callable[[], datetime] = utc_now,
    association_decay: float = 0.05,
) -> InstinktOutcomeLearningResult:
    """Cold-verify one completed run and CAS-append a later actual outcome."""

    admitted_at = admission_clock()
    sources = _load_cold_run_sources(run_id=run_id, artifact_store=artifact_store)
    manifest = sources.manifest
    assert manifest.manifest_id is not None
    assert manifest.manifest_hash is not None
    assert manifest.finished_at is not None
    try:
        action_receipt.validate_against(
            source_run_id=run_id,
            source_manifest_id=manifest.manifest_id,
            source_manifest_hash=manifest.manifest_hash,
            source_run_finished_at=manifest.finished_at,
            scene=sources.scene,
            behavior=sources.behavior,
        )
    except ValueError as exc:
        raise InstinktOutcomeAdmissionError(
            "Presented action receipt differs from completed run"
        ) from exc
    if action_receipt.executed_at > admitted_at:
        raise InstinktOutcomeAdmissionError("Action receipt cannot be admitted from the future")
    expected_executor = (
        "simulator" if outcome_record.source == "simulator" else "external_executor"
    )
    if action_receipt.executor_kind != expected_executor:
        raise InstinktOutcomeAdmissionError(
            "Outcome source differs from action receipt executor"
        )
    validated_outcome = OutcomeRecord.model_validate(
        outcome_record.model_dump(mode="python", round_trip=True)
    )
    if validated_outcome.event_id != sources.scene.event_id:
        raise InstinktOutcomeAdmissionError("OutcomeRecord belongs to another event")
    if validated_outcome.recorded_at > admitted_at:
        raise InstinktOutcomeAdmissionError("OutcomeRecord cannot be admitted from the future")
    try:
        observation = InstinktOutcomeObservation.create(
            scene=sources.scene,
            body_before=sources.body_before,
            action_receipt=action_receipt,
            outcome_record=validated_outcome,
            measurements=measurements,
            outcome_evidence=outcome_evidence,
            uncertainty=uncertainty,
            admitted_at=admitted_at,
        ).validate_against(
            scene=sources.scene,
            body_before=sources.body_before,
            action_receipt=action_receipt,
            outcome_record=validated_outcome,
        )
        update = InstinktOutcomeUpdate.create(
            ego_id=sources.reservation.ego_id,
            prediction=sources.prediction,
            rollout=sources.rollout,
            outcome=observation,
            ruleset=sources.ruleset,
            world=sources.world,
            body_before=sources.body_before,
            association_decay=association_decay,
        ).validate_against(
            ego_id=sources.reservation.ego_id,
            prediction=sources.prediction,
            rollout=sources.rollout,
            outcome=observation,
            ruleset=sources.ruleset,
            world=sources.world,
            body_before=sources.body_before,
        )
    except (ValidationError, ValueError) as exc:
        raise InstinktOutcomeAdmissionError(
            "Outcome measurements failed typed deterministic admission"
        ) from exc

    verifier = _replay_verifier(artifact_store=artifact_store, verified_at=admitted_at)
    prior = learning_store.load_trace(
        sources.reservation.ego_id,
        verifier=verifier,
    )
    persisted = learning_store.append_update(
        sources.reservation.ego_id,
        update,
        expected_trace_hash=prior.trace_hash,
        verifier=verifier,
    )
    committed = next(
        (item for item in persisted.updates if item.update_id == update.update_id),
        None,
    )
    if committed != update:
        raise InstinktOutcomeAdmissionError(
            "Outcome learning store did not return the exact committed update"
        )
    return InstinktOutcomeLearningResult(
        observation=update.observation,
        update=update,
        trace=persisted,
    )


__all__ = [
    "InstinktOutcomeAdmissionError",
    "InstinktOutcomeLearningResult",
    "issue_executed_action_receipt",
    "record_instinkt_outcome",
    "replay_instinkt_outcome_update",
]
