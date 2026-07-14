"""Provenance-closed, post-cycle C5 Instinkt outcome learning.

The admission path deliberately consumes an externally presented action receipt
and typed normalized measurements.  Numeric body deltas are always derived from
those measurements; callers cannot submit a parallel, untyped delta channel.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
    UtcTimestamp,
)
from ..models.conscious import BehaviorResultant
from ..models.ego import OutcomeRecord
from ..models.instinkt import (
    BODY_DIMENSIONS,
    BodyDelta,
    BodyDimension,
    BodyState,
    InstinktAssociation,
    InstinktOptionRollout,
    InstinktWorld,
)
from ..models.instinkt_effects import (
    InstinktEffectRuleSet,
    OptionBodyEffectPrediction,
)
from ..models.scene import EvidenceItem, SceneEvent


ResidualValue = Annotated[float, Field(ge=-2.0, le=2.0, allow_inf_nan=False)]
MeasurementStatus = Literal["measured_change", "measured_no_change"]
ActionExecutorKind = Literal["external_executor", "simulator"]

MAX_OUTCOME_EVIDENCE_ITEMS = 32
MAX_OUTCOME_EVIDENCE_CONTENT_CHARS = 16_384
NORMALIZED_MEASUREMENT_POLICY_ID = "c5-normalized-body-measurement-v1"
NORMALIZED_MEASUREMENT_POLICY_REVISION = "1"
NORMALIZED_MEASUREMENT_POLICY_HASH = sha256_hex(
    {
        "policy_id": NORMALIZED_MEASUREMENT_POLICY_ID,
        "revision": NORMALIZED_MEASUREMENT_POLICY_REVISION,
        "scale": "rei_body_score_0_1",
        "delta_rule": "after_value-minus-baseline_value",
        "zero_rule": "explicit-measured-no-change-only",
    }
)


def _canonical_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _canonical_measurements(
    values: tuple["NormalizedBodyMeasurement", ...],
) -> tuple["NormalizedBodyMeasurement", ...]:
    by_dimension = {item.dimension: item for item in values}
    if len(by_dimension) != len(values):
        raise ValueError("Outcome measurements must be unique by body dimension")
    return tuple(
        by_dimension[dimension]
        for dimension in BODY_DIMENSIONS
        if dimension in by_dimension
    )


class GroundedOutcomeEvidence(FrozenModel):
    """One supplied post-action evidence item and its observation time."""

    evidence: EvidenceItem
    observed_at: UtcTimestamp

    @model_validator(mode="after")
    def validate_grounded_evidence(self) -> Self:
        if not self.evidence.grounded or self.evidence.provenance_kind != "supplied":
            raise ValueError("Outcome learning requires supplied grounded evidence")
        if len(self.evidence.content) > MAX_OUTCOME_EVIDENCE_CONTENT_CHARS:
            raise ValueError("Outcome evidence content exceeds the bounded limit")
        return self


class OutcomeEvidenceRef(FrozenModel):
    evidence_id: NonEmptyId
    evidence_hash: HashDigest

    @classmethod
    def create(cls, evidence: GroundedOutcomeEvidence) -> "OutcomeEvidenceRef":
        return cls(
            evidence_id=evidence.evidence.evidence_id,
            evidence_hash=evidence.evidence.content_hash(),
        )


class ExecutedActionReceipt(FrozenArtifactModel):
    """Caller-presented receipt for the exact completed-run behavior action."""

    schema_version: Literal["rei-native-executed-action-receipt-v1"] = (
        "rei-native-executed-action-receipt-v1"
    )
    receipt_id: NonEmptyId
    source_run_id: NonEmptyId
    source_manifest_id: NonEmptyId
    source_manifest_hash: HashDigest
    source_run_finished_at: UtcTimestamp
    source_scene_id: NonEmptyId
    source_scene_hash: HashDigest
    source_behavior_resultant_id: NonEmptyId
    source_behavior_resultant_hash: HashDigest
    executed_option_id: NonEmptyId
    executor_kind: ActionExecutorKind
    executed_at: UtcTimestamp
    receipt_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        source_run_id: NonEmptyId,
        source_manifest_id: NonEmptyId,
        source_manifest_hash: HashDigest,
        source_run_finished_at: datetime,
        scene: SceneEvent,
        behavior: BehaviorResultant,
        executor_kind: ActionExecutorKind,
        executed_at: datetime,
    ) -> "ExecutedActionReceipt":
        if behavior.derivation_status != "derived_b10":
            raise ValueError("Action receipt requires a derived B10 behavior resultant")
        if (
            behavior.status != "executed"
            or behavior.option_id is None
            or behavior.source_scene_id != scene.event_id
        ):
            raise ValueError("Action receipt requires an executed option for its scene")
        if executed_at < source_run_finished_at:
            raise ValueError("Post-cycle action receipt cannot predate run completion")
        base = {
            "schema_version": "rei-native-executed-action-receipt-v1",
            "source_run_id": source_run_id,
            "source_manifest_id": source_manifest_id,
            "source_manifest_hash": source_manifest_hash,
            "source_run_finished_at": source_run_finished_at,
            "source_scene_id": scene.event_id,
            "source_scene_hash": scene.scene_hash(),
            "source_behavior_resultant_id": behavior.resultant_id,
            "source_behavior_resultant_hash": behavior.content_hash(),
            "executed_option_id": behavior.option_id,
            "executor_kind": executor_kind,
            "executed_at": executed_at,
        }
        receipt_id = content_id("executed_action_receipt", base)
        payload = {"receipt_id": receipt_id, **base}
        return cls(**payload, receipt_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.executed_at < self.source_run_finished_at:
            raise ValueError("Post-cycle action receipt cannot predate run completion")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"receipt_id", "receipt_hash"},
        )
        if self.receipt_id != content_id("executed_action_receipt", base):
            raise ValueError("receipt_id differs from canonical action content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"receipt_hash"}))
        if self.receipt_hash != expected_hash:
            raise ValueError("receipt_hash differs from canonical action content")
        return self

    def validate_against(
        self,
        *,
        source_run_id: NonEmptyId,
        source_manifest_id: NonEmptyId,
        source_manifest_hash: HashDigest,
        source_run_finished_at: datetime,
        scene: SceneEvent,
        behavior: BehaviorResultant,
    ) -> Self:
        expected = type(self).create(
            source_run_id=source_run_id,
            source_manifest_id=source_manifest_id,
            source_manifest_hash=source_manifest_hash,
            source_run_finished_at=source_run_finished_at,
            scene=scene,
            behavior=behavior,
            executor_kind=self.executor_kind,
            executed_at=self.executed_at,
        )
        if self != expected:
            raise ValueError("Action receipt differs from completed-run behavior lineage")
        return self


class NormalizedBodyMeasurement(FrozenArtifactModel):
    """Evidence-bound normalized before/after measurement for one body dimension."""

    schema_version: Literal["rei-native-normalized-body-measurement-v1"] = (
        "rei-native-normalized-body-measurement-v1"
    )
    measurement_id: NonEmptyId
    source_action_receipt_id: NonEmptyId
    source_action_receipt_hash: HashDigest
    source_body_state_id: NonEmptyId
    source_body_state_hash: HashDigest
    dimension: BodyDimension
    status: MeasurementStatus
    baseline_value: Score01
    after_value: Score01
    measured_at: UtcTimestamp
    evidence_refs: tuple[OutcomeEvidenceRef, ...] = Field(min_length=1)
    normalization_policy_id: Literal["c5-normalized-body-measurement-v1"] = (
        NORMALIZED_MEASUREMENT_POLICY_ID
    )
    normalization_policy_revision: Literal["1"] = (
        NORMALIZED_MEASUREMENT_POLICY_REVISION
    )
    normalization_policy_hash: HashDigest = NORMALIZED_MEASUREMENT_POLICY_HASH
    measurement_hash: HashDigest

    @property
    def delta(self) -> float:
        return self.after_value - self.baseline_value

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence_id for item in self.evidence_refs)

    @classmethod
    def create(
        cls,
        *,
        action_receipt: ExecutedActionReceipt,
        body_before: BodyState,
        dimension: BodyDimension,
        status: MeasurementStatus,
        after_value: float,
        evidence: tuple[GroundedOutcomeEvidence, ...],
    ) -> "NormalizedBodyMeasurement":
        if not evidence:
            raise ValueError("Normalized body measurement requires outcome evidence")
        canonical_evidence = tuple(
            sorted(evidence, key=lambda item: item.evidence.evidence_id)
        )
        if len({item.evidence.evidence_id for item in canonical_evidence}) != len(
            canonical_evidence
        ):
            raise ValueError("Measurement evidence IDs must be unique")
        baseline = getattr(body_before, dimension)
        refs = tuple(OutcomeEvidenceRef.create(item) for item in canonical_evidence)
        base = {
            "schema_version": "rei-native-normalized-body-measurement-v1",
            "source_action_receipt_id": action_receipt.receipt_id,
            "source_action_receipt_hash": action_receipt.receipt_hash,
            "source_body_state_id": body_before.body_state_id,
            "source_body_state_hash": body_before.content_hash(),
            "dimension": dimension,
            "status": status,
            "baseline_value": baseline,
            "after_value": after_value,
            "measured_at": max(item.observed_at for item in canonical_evidence),
            "evidence_refs": refs,
            "normalization_policy_id": NORMALIZED_MEASUREMENT_POLICY_ID,
            "normalization_policy_revision": NORMALIZED_MEASUREMENT_POLICY_REVISION,
            "normalization_policy_hash": NORMALIZED_MEASUREMENT_POLICY_HASH,
        }
        measurement_id = content_id("normalized_body_measurement", base)
        payload = {"measurement_id": measurement_id, **base}
        return cls(**payload, measurement_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_measurement(self) -> Self:
        if self.evidence_refs != tuple(
            sorted(self.evidence_refs, key=lambda item: item.evidence_id)
        ):
            raise ValueError("Measurement evidence refs must use canonical ID order")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Measurement evidence refs must be unique")
        unchanged = math.isclose(
            self.after_value,
            self.baseline_value,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        if self.status == "measured_no_change" and not unchanged:
            raise ValueError("measured_no_change requires equal before/after values")
        if self.status == "measured_change" and unchanged:
            raise ValueError("measured_change requires a non-zero normalized delta")
        if self.normalization_policy_hash != NORMALIZED_MEASUREMENT_POLICY_HASH:
            raise ValueError("Measurement normalization policy hash differs")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"measurement_id", "measurement_hash"},
        )
        if self.measurement_id != content_id("normalized_body_measurement", base):
            raise ValueError("measurement_id differs from canonical measurement")
        expected_hash = self.content_hash(exclude_fields=frozenset({"measurement_hash"}))
        if self.measurement_hash != expected_hash:
            raise ValueError("measurement_hash differs from canonical measurement")
        return self

    def validate_against(
        self,
        *,
        action_receipt: ExecutedActionReceipt,
        body_before: BodyState,
        evidence_by_id: dict[str, GroundedOutcomeEvidence],
    ) -> Self:
        try:
            evidence = tuple(evidence_by_id[value] for value in self.evidence_ids)
        except KeyError as exc:
            raise ValueError("Measurement cites unavailable outcome evidence") from exc
        expected = type(self).create(
            action_receipt=action_receipt,
            body_before=body_before,
            dimension=self.dimension,
            status=self.status,
            after_value=self.after_value,
            evidence=evidence,
        )
        if self != expected:
            raise ValueError("Normalized measurement differs from source lineage")
        return self


class InstinktOutcomeObservation(FrozenArtifactModel):
    """Typed interpretation of an actual outcome bound to one action receipt."""

    schema_version: Literal["rei-native-instinkt-outcome-observation-v3"] = (
        "rei-native-instinkt-outcome-observation-v3"
    )
    observation_id: NonEmptyId
    source_run_id: NonEmptyId
    source_manifest_id: NonEmptyId
    source_manifest_hash: HashDigest
    source_run_finished_at: UtcTimestamp
    source_scene_id: NonEmptyId
    source_scene_hash: HashDigest
    source_scene_evidence_ids: tuple[NonEmptyId, ...]
    source_action_receipt_id: NonEmptyId
    source_action_receipt_hash: HashDigest
    action_receipt: ExecutedActionReceipt
    source_body_state_id: NonEmptyId
    source_body_state_hash: HashDigest
    source_outcome_id: NonEmptyId
    source_outcome_hash: HashDigest
    outcome_record: OutcomeRecord
    event_id: NonEmptyId
    option_id: NonEmptyId
    measurements: tuple[NormalizedBodyMeasurement, ...] = Field(min_length=1)
    outcome_evidence: tuple[GroundedOutcomeEvidence, ...] = Field(
        min_length=1,
        max_length=MAX_OUTCOME_EVIDENCE_ITEMS,
    )
    uncertainty: NonEmptyText
    admitted_at: UtcTimestamp
    observation_hash: HashDigest

    @property
    def source(self) -> Literal["external_observation", "simulator"]:
        return self.outcome_record.source

    @property
    def recorded_at(self) -> datetime:
        return self.outcome_record.recorded_at

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(item.evidence.evidence_id for item in self.outcome_evidence)

    @property
    def observed_body_deltas(self) -> tuple[BodyDelta, ...]:
        return tuple(
            BodyDelta(dimension=item.dimension, delta=item.delta)
            for item in self.measurements
        )

    @classmethod
    def create(
        cls,
        *,
        scene: SceneEvent,
        body_before: BodyState,
        action_receipt: ExecutedActionReceipt,
        outcome_record: OutcomeRecord,
        measurements: tuple[NormalizedBodyMeasurement, ...],
        outcome_evidence: tuple[GroundedOutcomeEvidence, ...],
        uncertainty: NonEmptyText,
        admitted_at: datetime,
    ) -> "InstinktOutcomeObservation":
        canonical_evidence = tuple(
            sorted(outcome_evidence, key=lambda item: item.evidence.evidence_id)
        )
        canonical_measurements = _canonical_measurements(measurements)
        base = {
            "schema_version": "rei-native-instinkt-outcome-observation-v3",
            "source_run_id": action_receipt.source_run_id,
            "source_manifest_id": action_receipt.source_manifest_id,
            "source_manifest_hash": action_receipt.source_manifest_hash,
            "source_run_finished_at": action_receipt.source_run_finished_at,
            "source_scene_id": scene.event_id,
            "source_scene_hash": scene.scene_hash(),
            "source_scene_evidence_ids": _canonical_ids(
                tuple(item.evidence_id for item in scene.evidence)
            ),
            "source_action_receipt_id": action_receipt.receipt_id,
            "source_action_receipt_hash": action_receipt.receipt_hash,
            "action_receipt": action_receipt,
            "source_body_state_id": body_before.body_state_id,
            "source_body_state_hash": body_before.content_hash(),
            "source_outcome_id": outcome_record.outcome_id,
            "source_outcome_hash": outcome_record.content_hash(),
            "outcome_record": outcome_record,
            "event_id": outcome_record.event_id,
            "option_id": action_receipt.executed_option_id,
            "measurements": canonical_measurements,
            "outcome_evidence": canonical_evidence,
            "uncertainty": uncertainty,
            "admitted_at": admitted_at,
        }
        observation_id = content_id("instinkt_outcome_observation", base)
        payload = {"observation_id": observation_id, **base}
        return cls(**payload, observation_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        receipt_lineage = (
            self.source_run_id == self.action_receipt.source_run_id,
            self.source_manifest_id == self.action_receipt.source_manifest_id,
            self.source_manifest_hash == self.action_receipt.source_manifest_hash,
            self.source_run_finished_at == self.action_receipt.source_run_finished_at,
            self.source_scene_id == self.action_receipt.source_scene_id,
            self.source_scene_hash == self.action_receipt.source_scene_hash,
            self.source_action_receipt_id == self.action_receipt.receipt_id,
            self.source_action_receipt_hash == self.action_receipt.receipt_hash,
            self.option_id == self.action_receipt.executed_option_id,
        )
        if not all(receipt_lineage):
            raise ValueError("Outcome observation differs from action-receipt lineage")
        if (
            self.source_outcome_id != self.outcome_record.outcome_id
            or self.source_outcome_hash != self.outcome_record.content_hash()
        ):
            raise ValueError("Outcome observation differs from its OutcomeRecord")
        if self.event_id != self.outcome_record.event_id or self.source_scene_id != self.event_id:
            raise ValueError("OutcomeRecord belongs to another source scene")
        if self.outcome_record.recorded_at < self.action_receipt.executed_at:
            raise ValueError("OutcomeRecord cannot predate executed action receipt")
        if self.outcome_record.recorded_at > self.admitted_at:
            raise ValueError("OutcomeRecord cannot be admitted from the future")
        if self.source_scene_evidence_ids != _canonical_ids(self.source_scene_evidence_ids):
            raise ValueError("Source scene evidence IDs must be sorted and unique")
        if self.measurements != _canonical_measurements(self.measurements):
            raise ValueError("Outcome measurements must use canonical body order")

        evidence_ids = self.evidence_ids
        if evidence_ids != tuple(sorted(set(evidence_ids))):
            raise ValueError("Outcome evidence must use canonical unique ID order")
        if set(evidence_ids) != set(self.outcome_record.evidence_ids):
            raise ValueError("Grounded evidence IDs must exactly match OutcomeRecord")
        if set(evidence_ids) & set(self.source_scene_evidence_ids):
            raise ValueError("Post-action outcome evidence cannot reuse source-scene evidence")
        evidence_by_id = {
            item.evidence.evidence_id: item for item in self.outcome_evidence
        }
        for item in self.outcome_evidence:
            if (
                item.observed_at < self.action_receipt.executed_at
                or item.observed_at > self.outcome_record.recorded_at
                or item.observed_at > self.admitted_at
            ):
                raise ValueError(
                    "Outcome evidence must follow execution and precede admission"
                )
        cited_ids: set[str] = set()
        for measurement in self.measurements:
            if (
                measurement.source_action_receipt_id != self.action_receipt.receipt_id
                or measurement.source_action_receipt_hash != self.action_receipt.receipt_hash
                or measurement.source_body_state_id != self.source_body_state_id
                or measurement.source_body_state_hash != self.source_body_state_hash
            ):
                raise ValueError("Outcome measurement differs from action/body lineage")
            for ref in measurement.evidence_refs:
                evidence = evidence_by_id.get(ref.evidence_id)
                if evidence is None or ref.evidence_hash != evidence.evidence.content_hash():
                    raise ValueError("Measurement evidence hash differs from observation")
                cited_ids.add(ref.evidence_id)
            if measurement.measured_at > self.outcome_record.recorded_at:
                raise ValueError("Body measurement cannot postdate OutcomeRecord")
        if cited_ids != set(evidence_ids):
            raise ValueError("Every OutcomeRecord evidence item must support a measurement")

        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"observation_id", "observation_hash"},
        )
        if self.observation_id != content_id("instinkt_outcome_observation", base):
            raise ValueError("observation_id differs from canonical observation content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"observation_hash"}))
        if self.observation_hash != expected_hash:
            raise ValueError("observation_hash differs from canonical observation content")
        return self

    def validate_against(
        self,
        *,
        scene: SceneEvent,
        body_before: BodyState,
        action_receipt: ExecutedActionReceipt,
        outcome_record: OutcomeRecord,
    ) -> Self:
        evidence_by_id = {
            item.evidence.evidence_id: item for item in self.outcome_evidence
        }
        for measurement in self.measurements:
            measurement.validate_against(
                action_receipt=action_receipt,
                body_before=body_before,
                evidence_by_id=evidence_by_id,
            )
        expected = type(self).create(
            scene=scene,
            body_before=body_before,
            action_receipt=action_receipt,
            outcome_record=outcome_record,
            measurements=self.measurements,
            outcome_evidence=self.outcome_evidence,
            uncertainty=self.uncertainty,
            admitted_at=self.admitted_at,
        )
        if self != expected:
            raise ValueError("Outcome observation differs from its cold source lineage")
        return self


class BodyPredictionResidual(FrozenModel):
    """Per-measured-dimension difference between rollout and experience."""

    dimension: BodyDimension
    predicted_delta: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    observed_delta: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    residual: ResidualValue

    @model_validator(mode="after")
    def validate_residual(self) -> Self:
        expected = self.observed_delta - self.predicted_delta
        if not math.isclose(self.residual, expected, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("Prediction residual does not replay")
        return self


def _loss_classes(
    *,
    prediction: OptionBodyEffectPrediction,
    ruleset: InstinktEffectRuleSet,
    observed: dict[str, float],
) -> tuple[str, ...]:
    classes: set[str] = set()
    for evidence in prediction.evidence:
        rule = ruleset.by_rule_id[evidence.rule_id]
        if any(
            (value := observed.get(delta.dimension)) is not None
            and not math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1e-12)
            and value * delta.delta > 0.0
            for delta in rule.adverse_deltas
        ):
            classes.add(evidence.cue_class)
    return tuple(sorted(classes))


class InstinktOutcomeUpdate(FrozenArtifactModel):
    """One immutable learned association plus next body/world snapshots."""

    schema_version: Literal["rei-native-instinkt-outcome-update-v3"] = (
        "rei-native-instinkt-outcome-update-v3"
    )
    update_id: NonEmptyId
    ego_id: NonEmptyId
    source_run_id: NonEmptyId
    source_manifest_id: NonEmptyId
    source_manifest_hash: HashDigest
    source_prediction_id: NonEmptyId
    source_prediction_hash: HashDigest
    source_rollout_id: NonEmptyId
    source_rollout_hash: HashDigest
    source_observation_id: NonEmptyId
    source_observation_hash: HashDigest
    source_action_receipt_id: NonEmptyId
    source_action_receipt_hash: HashDigest
    source_outcome_id: NonEmptyId
    source_outcome_hash: HashDigest
    observation: InstinktOutcomeObservation
    source_world_id: NonEmptyId
    source_world_hash: HashDigest
    source_body_state_id: NonEmptyId
    source_body_state_hash: HashDigest
    learned_association: InstinktAssociation
    body_after: BodyState
    world_after: InstinktWorld
    residuals: tuple[BodyPredictionResidual, ...]
    created_at: UtcTimestamp
    update_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        prediction: OptionBodyEffectPrediction,
        rollout: InstinktOptionRollout,
        outcome: InstinktOutcomeObservation,
        ruleset: InstinktEffectRuleSet,
        world: InstinktWorld,
        body_before: BodyState,
        association_decay: float = 0.05,
    ) -> "InstinktOutcomeUpdate":
        if prediction.abstains:
            raise ValueError("An abstaining prediction cannot be learned as an effect")
        if prediction.option_id != outcome.option_id or rollout.option_id != outcome.option_id:
            raise ValueError("Outcome option differs from prediction or rollout")
        if prediction.source_scene_id != outcome.event_id:
            raise ValueError("Outcome event differs from its source prediction")
        if (
            prediction.source_world_id != world.world_id
            or prediction.source_world_hash != world.content_hash()
            or prediction.source_body_state_id != body_before.body_state_id
            or prediction.source_body_state_hash != body_before.content_hash()
        ):
            raise ValueError("Outcome learning received swapped body or world input")
        if (
            prediction.ruleset_id != ruleset.ruleset_id
            or prediction.ruleset_hash != ruleset.ruleset_hash
        ):
            raise ValueError("Outcome learning received another effect rule set")
        if (
            rollout.source_body_state_id != body_before.body_state_id
            or rollout.source_body_state_hash != body_before.content_hash()
            or rollout.trajectory[0] != body_before
        ):
            raise ValueError("Outcome rollout belongs to another source body")

        final_state = rollout.trajectory[-1]
        measurements = {item.dimension: item for item in outcome.measurements}
        residuals = tuple(
            BodyPredictionResidual(
                dimension=dimension,
                predicted_delta=getattr(final_state, dimension)
                - getattr(body_before, dimension),
                observed_delta=measurements[dimension].delta,
                residual=measurements[dimension].delta
                - (
                    getattr(final_state, dimension)
                    - getattr(body_before, dimension)
                ),
            )
            for dimension in BODY_DIMENSIONS
            if dimension in measurements
        )
        values = {
            dimension: (
                measurements[dimension].after_value
                if dimension in measurements
                else getattr(body_before, dimension)
            )
            for dimension in BODY_DIMENSIONS
        }
        body_base = {"schema_version": "rei-native-body-state-v1", **values}
        body_after = BodyState(
            body_state_id=content_id(
                "learned_body_state",
                {
                    "source_body_state_id": body_before.body_state_id,
                    "source_body_state_hash": body_before.content_hash(),
                    "source_observation_id": outcome.observation_id,
                    **body_base,
                },
            ),
            **body_base,
        )

        observed = {item.dimension: item.delta for item in outcome.measurements}
        rule_by_id = ruleset.by_rule_id
        cue_classes = tuple(sorted({item.cue_class for item in prediction.evidence}))
        loss_classes = _loss_classes(
            prediction=prediction,
            ruleset=ruleset,
            observed=observed,
        )
        protected_targets = tuple(
            sorted({rule_by_id[item.rule_id].protected_target for item in prediction.evidence})
        )
        felt_intensity = min(1.0, max(abs(item.delta) for item in outcome.measurements))
        experienced_loss = (
            " ".join(f"loss_class:{value}" for value in loss_classes)
            if loss_classes
            else None
        )
        association_base: dict[str, object] = {
            "schema_version": "rei-native-instinkt-association-v1",
            "cue_signature": cue_classes,
            "cue_classes": cue_classes,
            "body_state_before": body_before,
            "felt_intensity": felt_intensity,
            "protected_target": ",".join(protected_targets) or "unspecified_target",
            "experienced_loss": experienced_loss,
            "action_taken": outcome.option_id,
            "outcome": outcome.source_outcome_id,
            "trust_delta": observed.get("trust", 0.0),
            "attachment_delta": observed.get("attachment_security", 0.0),
            "boundary_delta": observed.get("boundary_integrity", 0.0),
            "decay": association_decay,
        }
        if loss_classes:
            association_base["loss_classes"] = loss_classes
        learned_association = InstinktAssociation(
            association_id=content_id("instinkt_association", association_base),
            **association_base,
        )

        threat_cues = tuple(
            cue
            for cue in cue_classes
            if cue
            in {
                "physical_threat",
                "pain_or_injury",
                "betrayal",
                "abandonment",
                "scarcity",
            }
        )
        next_world = InstinktWorld.create(
            associations=(*world.associations, learned_association.association_id),
            trusted_patterns=(
                *world.trusted_patterns,
                *((outcome.option_id,) if observed.get("trust", 0.0) > 0 else ()),
            ),
            threat_patterns=(*world.threat_patterns, *threat_cues),
            attachment_objects=(*world.attachment_objects, *protected_targets),
            unresolved_losses=(
                *world.unresolved_losses,
                *((outcome.source_outcome_id,) if experienced_loss is not None else ()),
            ),
            boundary_patterns=(
                *world.boundary_patterns,
                *((outcome.option_id,) if "boundary" in cue_classes else ()),
            ),
        )
        base = {
            "schema_version": "rei-native-instinkt-outcome-update-v3",
            "ego_id": ego_id,
            "source_run_id": outcome.source_run_id,
            "source_manifest_id": outcome.source_manifest_id,
            "source_manifest_hash": outcome.source_manifest_hash,
            "source_prediction_id": prediction.prediction_id,
            "source_prediction_hash": prediction.prediction_hash,
            "source_rollout_id": rollout.rollout_id,
            "source_rollout_hash": rollout.rollout_hash,
            "source_observation_id": outcome.observation_id,
            "source_observation_hash": outcome.observation_hash,
            "source_action_receipt_id": outcome.source_action_receipt_id,
            "source_action_receipt_hash": outcome.source_action_receipt_hash,
            "source_outcome_id": outcome.source_outcome_id,
            "source_outcome_hash": outcome.source_outcome_hash,
            "observation": outcome,
            "source_world_id": world.world_id,
            "source_world_hash": world.content_hash(),
            "source_body_state_id": body_before.body_state_id,
            "source_body_state_hash": body_before.content_hash(),
            "learned_association": learned_association,
            "body_after": body_after,
            "world_after": next_world,
            "residuals": residuals,
            "created_at": outcome.admitted_at,
        }
        update_id = content_id("instinkt_outcome_update", base)
        payload = {"update_id": update_id, **base}
        return cls(**payload, update_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_update(self) -> Self:
        lineage = (
            self.source_run_id == self.observation.source_run_id,
            self.source_manifest_id == self.observation.source_manifest_id,
            self.source_manifest_hash == self.observation.source_manifest_hash,
            self.source_observation_id == self.observation.observation_id,
            self.source_observation_hash == self.observation.observation_hash,
            self.source_action_receipt_id == self.observation.source_action_receipt_id,
            self.source_action_receipt_hash == self.observation.source_action_receipt_hash,
            self.source_outcome_id == self.observation.source_outcome_id,
            self.source_outcome_hash == self.observation.source_outcome_hash,
            self.created_at == self.observation.admitted_at,
        )
        if not all(lineage):
            raise ValueError("Outcome update differs from embedded observation lineage")
        if self.learned_association.association_id not in self.world_after.associations:
            raise ValueError("Updated InstinktWorld omits its learned association")
        if tuple(item.dimension for item in self.residuals) != tuple(
            item.dimension for item in self.observation.measurements
        ):
            raise ValueError("Residual dimensions must equal measured dimensions")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"update_id", "update_hash"},
        )
        if self.update_id != content_id("instinkt_outcome_update", base):
            raise ValueError("update_id differs from canonical update content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"update_hash"}))
        if self.update_hash != expected_hash:
            raise ValueError("update_hash differs from canonical update content")
        return self

    def validate_against(
        self,
        *,
        ego_id: NonEmptyId,
        prediction: OptionBodyEffectPrediction,
        rollout: InstinktOptionRollout,
        outcome: InstinktOutcomeObservation,
        ruleset: InstinktEffectRuleSet,
        world: InstinktWorld,
        body_before: BodyState,
    ) -> Self:
        expected = type(self).create(
            ego_id=ego_id,
            prediction=prediction,
            rollout=rollout,
            outcome=outcome,
            ruleset=ruleset,
            world=world,
            body_before=body_before,
            association_decay=self.learned_association.decay,
        )
        if self != expected:
            raise ValueError("Outcome update differs from deterministic source replay")
        return self


class InstinktOutcomeLearningTrace(FrozenArtifactModel):
    """Ego-keyed append-only ledger of deterministic outcome updates."""

    schema_version: Literal["rei-native-instinkt-outcome-learning-trace-v3"] = (
        "rei-native-instinkt-outcome-learning-trace-v3"
    )
    trace_id: NonEmptyId
    ego_id: NonEmptyId
    updates: tuple[InstinktOutcomeUpdate, ...] = ()
    trace_hash: HashDigest

    @classmethod
    def empty(cls, *, ego_id: NonEmptyId) -> "InstinktOutcomeLearningTrace":
        return cls.create(ego_id=ego_id, updates=())

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        updates: tuple[InstinktOutcomeUpdate, ...],
    ) -> "InstinktOutcomeLearningTrace":
        base = {
            "schema_version": "rei-native-instinkt-outcome-learning-trace-v3",
            "ego_id": ego_id,
            "updates": updates,
        }
        trace_id = content_id("instinkt_learning_trace", base)
        payload = {"trace_id": trace_id, **base}
        return cls(**payload, trace_hash=sha256_hex(payload))

    def append(self, update: InstinktOutcomeUpdate) -> "InstinktOutcomeLearningTrace":
        if update.ego_id != self.ego_id:
            raise ValueError("Outcome update belongs to another Ego learning trace")
        return self.create(ego_id=self.ego_id, updates=(*self.updates, update))

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        if any(item.ego_id != self.ego_id for item in self.updates):
            raise ValueError("Outcome update belongs to another Ego learning trace")
        unique_fields = {
            "update": tuple(item.update_id for item in self.updates),
            "run": tuple(item.source_run_id for item in self.updates),
            "action receipt": tuple(item.source_action_receipt_id for item in self.updates),
            "observation": tuple(item.source_observation_id for item in self.updates),
            "OutcomeRecord": tuple(item.source_outcome_id for item in self.updates),
        }
        for label, values in unique_fields.items():
            if len(set(values)) != len(values):
                raise ValueError(f"Outcome learning {label} IDs must be unique")
        for previous, current in zip(self.updates, self.updates[1:]):
            if current.created_at < previous.created_at:
                raise ValueError("Outcome learning updates must use chronological order")
            if (
                current.source_world_id != previous.world_after.world_id
                or current.source_world_hash != previous.world_after.content_hash()
                or current.source_body_state_id != previous.body_after.body_state_id
                or current.source_body_state_hash != previous.body_after.content_hash()
            ):
                raise ValueError("Outcome learning update forks the body/world chain")
        base = self.model_dump(
            mode="python", round_trip=True, exclude={"trace_id", "trace_hash"}
        )
        if self.trace_id != content_id("instinkt_learning_trace", base):
            raise ValueError("trace_id differs from canonical learning trace")
        expected_hash = self.content_hash(exclude_fields=frozenset({"trace_hash"}))
        if self.trace_hash != expected_hash:
            raise ValueError("trace_hash differs from canonical learning trace")
        return self


__all__ = [
    "BodyPredictionResidual",
    "ExecutedActionReceipt",
    "GroundedOutcomeEvidence",
    "InstinktOutcomeLearningTrace",
    "InstinktOutcomeObservation",
    "InstinktOutcomeUpdate",
    "NormalizedBodyMeasurement",
    "OutcomeEvidenceRef",
]
