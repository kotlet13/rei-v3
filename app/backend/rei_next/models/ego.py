"""Temporal Ego composition records without an Ego decision API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex, utc_now
from .character import CharacterAuthority, EffectiveAuthority
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
    UtcTimestamp,
)
from .communication import AcceptanceState, RacioInterpretation, TranslationGap
from .conscious import BehaviorResultant, ConsciousDecision
from .governance import GovernanceMandate, SpoznanjeStatus


EgoClaimKind = Literal[
    "identity_motif",
    "recurring_conflict",
    "recurring_translation_error",
    "unresolved_tension",
    "resolved_tension",
    "spoznanje",
    "commitment",
    "relationship_pattern",
    "current_section",
    "racio_chronology",
    "racio_fact",
    "racio_statement",
    "racio_commitment",
    "racio_causal_link",
    "emocio_recurring_scene",
    "emocio_image_artifact",
    "emocio_status_pattern",
    "emocio_belonging_motif",
    "emocio_success_motif",
    "emocio_rupture_motif",
    "emocio_desire_motif",
    "instinkt_body_consequence",
    "instinkt_danger",
    "instinkt_loss",
    "instinkt_trust_pattern",
    "instinkt_attachment_pattern",
    "instinkt_boundary_pattern",
    "instinkt_scarcity_pattern",
    "instinkt_recovery_pattern",
]
DerivationStatus = Literal["derived_from_trace"]


class SourcedEgoClaim(FrozenArtifactModel):
    """One composition/projection assertion with measure-level provenance."""

    schema_version: Literal["rei-native-sourced-ego-claim-v1"] = (
        "rei-native-sourced-ego-claim-v1"
    )
    claim_id: NonEmptyId
    kind: EgoClaimKind
    text: NonEmptyText
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)

    @classmethod
    def create(
        cls,
        *,
        kind: EgoClaimKind,
        text: NonEmptyText,
        evidence_measure_ids: tuple[NonEmptyId, ...],
    ) -> SourcedEgoClaim:
        canonical_measure_ids = tuple(sorted(set(evidence_measure_ids)))
        base = {
            "schema_version": "rei-native-sourced-ego-claim-v1",
            "kind": kind,
            "text": text,
            "evidence_measure_ids": canonical_measure_ids,
        }
        return cls(claim_id=content_id("ego_claim", base), **base)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if self.evidence_measure_ids != tuple(sorted(set(self.evidence_measure_ids))):
            raise ValueError(
                "Sourced Ego claim evidence_measure_ids must be sorted and unique"
            )
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"claim_id"},
        )
        if self.claim_id != content_id("ego_claim", base):
            raise ValueError("claim_id does not match the sourced claim content")
        return self


class OutcomeRecord(FrozenArtifactModel):
    schema_version: Literal["rei-native-outcome-record-v1"] = (
        "rei-native-outcome-record-v1"
    )
    outcome_id: NonEmptyId
    event_id: NonEmptyId
    recorded_at: UtcTimestamp
    source: Literal["external_observation", "simulator"]
    observed_effects: tuple[str, ...] = ()
    evidence_ids: tuple[NonEmptyId, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_ids(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Outcome evidence IDs must be unique")
        return self


class EgoMeasure(FrozenArtifactModel):
    """One complete REI cycle; this record has no proposal or vote."""

    schema_version: Literal["rei-native-ego-measure-v2"] = (
        "rei-native-ego-measure-v2"
    )
    measure_id: NonEmptyId
    event_id: NonEmptyId
    native_bundle_id: NonEmptyId
    native_bundle_hash: HashDigest
    governance_resolution_id: NonEmptyId
    governance_resolution_hash: HashDigest
    structural_character: CharacterAuthority
    effective_authority: EffectiveAuthority
    acceptance_state: AcceptanceState
    governance_mandate: GovernanceMandate
    racio_interpretations: tuple[RacioInterpretation, ...] = ()
    conscious_decision: ConsciousDecision
    behavior_resultant: BehaviorResultant
    outcome: OutcomeRecord | None = None
    translation_gaps: tuple[TranslationGap, ...] = ()
    unresolved_tensions: tuple[str, ...] = ()
    spoznanje_status: SpoznanjeStatus
    created_at: UtcTimestamp
    measure_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        event_id: NonEmptyId,
        native_bundle_id: NonEmptyId,
        native_bundle_hash: HashDigest,
        governance_resolution_id: NonEmptyId,
        governance_resolution_hash: HashDigest,
        structural_character: CharacterAuthority,
        effective_authority: EffectiveAuthority,
        acceptance_state: AcceptanceState,
        governance_mandate: GovernanceMandate,
        conscious_decision: ConsciousDecision,
        behavior_resultant: BehaviorResultant,
        spoznanje_status: SpoznanjeStatus,
        racio_interpretations: tuple[RacioInterpretation, ...] = (),
        outcome: OutcomeRecord | None = None,
        translation_gaps: tuple[TranslationGap, ...] = (),
        unresolved_tensions: tuple[str, ...] = (),
        created_at: UtcTimestamp | None = None,
    ) -> EgoMeasure:
        timestamp = created_at or utc_now()
        base = {
            "schema_version": "rei-native-ego-measure-v2",
            "event_id": event_id,
            "native_bundle_id": native_bundle_id,
            "native_bundle_hash": native_bundle_hash,
            "governance_resolution_id": governance_resolution_id,
            "governance_resolution_hash": governance_resolution_hash,
            "structural_character": structural_character,
            "effective_authority": effective_authority,
            "acceptance_state": acceptance_state,
            "governance_mandate": governance_mandate,
            "racio_interpretations": racio_interpretations,
            "conscious_decision": conscious_decision,
            "behavior_resultant": behavior_resultant,
            "outcome": outcome,
            "translation_gaps": translation_gaps,
            "unresolved_tensions": unresolved_tensions,
            "spoznanje_status": spoznanje_status,
            "created_at": timestamp,
        }
        measure_id = content_id("measure", base)
        payload = {"measure_id": measure_id, **base}
        return cls(**payload, measure_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_measure(self) -> Self:
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"measure_id", "measure_hash"},
        )
        if self.measure_id != content_id("measure", id_payload):
            raise ValueError("measure_id does not match the canonical measure content")
        expected = self.content_hash(exclude_fields=frozenset({"measure_hash"}))
        if self.measure_hash != expected:
            raise ValueError("measure_hash does not match the canonical measure payload")
        if self.outcome is not None and self.outcome.event_id != self.event_id:
            raise ValueError("OutcomeRecord must refer to the same event as EgoMeasure")
        if self.effective_authority.structural_profile != self.structural_character:
            raise ValueError("EffectiveAuthority must retain EgoMeasure structural character")
        interpretation_by_id = {
            item.interpretation_id: item for item in self.racio_interpretations
        }
        if len(interpretation_by_id) != len(self.racio_interpretations):
            raise ValueError("Racio interpretation IDs must be unique within a measure")
        gap_ids = tuple(item.translation_gap_id for item in self.translation_gaps)
        if len(set(gap_ids)) != len(gap_ids):
            raise ValueError("Translation gap IDs must be unique within a measure")
        for gap in self.translation_gaps:
            interpretation = interpretation_by_id.get(gap.interpretation_id)
            if interpretation is None:
                raise ValueError("TranslationGap must reference a measure interpretation")
            if interpretation.source_mind != gap.source_mind:
                raise ValueError("TranslationGap and interpretation source minds must match")
        return self


class EgoCorrectionEvent(FrozenArtifactModel):
    """An append-only correction; the target measure remains unchanged."""

    schema_version: Literal["rei-native-ego-correction-v1"] = (
        "rei-native-ego-correction-v1"
    )
    correction_id: NonEmptyId
    ego_id: NonEmptyId
    target_measure_id: NonEmptyId
    recorded_at: UtcTimestamp
    reason: str
    correction: str
    evidence_ids: tuple[NonEmptyId, ...] = ()
    correction_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        target_measure_id: NonEmptyId,
        reason: str,
        correction: str,
        evidence_ids: tuple[NonEmptyId, ...] = (),
        recorded_at: UtcTimestamp | None = None,
    ) -> EgoCorrectionEvent:
        base = {
            "schema_version": "rei-native-ego-correction-v1",
            "ego_id": ego_id,
            "target_measure_id": target_measure_id,
            "recorded_at": recorded_at or utc_now(),
            "reason": reason,
            "correction": correction,
            "evidence_ids": evidence_ids,
        }
        correction_id = content_id("correction", base)
        payload = {"correction_id": correction_id, **base}
        return cls(**payload, correction_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_correction_hash(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Correction evidence IDs must be unique")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"correction_id", "correction_hash"},
        )
        if self.correction_id != content_id("correction", id_payload):
            raise ValueError(
                "correction_id does not match the canonical correction content"
            )
        expected = self.content_hash(exclude_fields=frozenset({"correction_hash"}))
        if self.correction_hash != expected:
            raise ValueError("correction_hash does not match its canonical payload")
        return self


TraceEventKind = Literal["measure", "correction"]


class EgoTraceEventRef(FrozenModel):
    sequence_index: int = Field(ge=0)
    event_kind: TraceEventKind
    event_id: NonEmptyId
    event_hash: HashDigest


class EgoTrace(FrozenArtifactModel):
    """Immutable representation of an append-only sequence of measures."""

    schema_version: Literal["rei-native-ego-trace-v1"] = "rei-native-ego-trace-v1"
    ego_id: NonEmptyId
    measures: tuple[EgoMeasure, ...] = ()
    corrections: tuple[EgoCorrectionEvent, ...] = ()
    event_order: tuple[EgoTraceEventRef, ...] = ()
    trace_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        measures: tuple[EgoMeasure, ...] = (),
        corrections: tuple[EgoCorrectionEvent, ...] = (),
        event_order: tuple[EgoTraceEventRef, ...] | None = None,
    ) -> EgoTrace:
        if event_order is None:
            event_order = tuple(
                EgoTraceEventRef(
                    sequence_index=index,
                    event_kind="measure",
                    event_id=measure.measure_id,
                    event_hash=measure.measure_hash,
                )
                for index, measure in enumerate(measures)
            ) + tuple(
                EgoTraceEventRef(
                    sequence_index=len(measures) + index,
                    event_kind="correction",
                    event_id=correction.correction_id,
                    event_hash=correction.correction_hash,
                )
                for index, correction in enumerate(corrections)
            )
        payload = {
            "schema_version": "rei-native-ego-trace-v1",
            "ego_id": ego_id,
            "measures": measures,
            "corrections": corrections,
            "event_order": event_order,
        }
        return cls(**payload, trace_hash=sha256_hex(payload))

    def append_measure(self, measure: EgoMeasure) -> EgoTrace:
        event_ref = EgoTraceEventRef(
            sequence_index=len(self.event_order),
            event_kind="measure",
            event_id=measure.measure_id,
            event_hash=measure.measure_hash,
        )
        return self.create(
            ego_id=self.ego_id,
            measures=(*self.measures, measure),
            corrections=self.corrections,
            event_order=(*self.event_order, event_ref),
        )

    def append_correction(self, correction: EgoCorrectionEvent) -> EgoTrace:
        event_ref = EgoTraceEventRef(
            sequence_index=len(self.event_order),
            event_kind="correction",
            event_id=correction.correction_id,
            event_hash=correction.correction_hash,
        )
        return self.create(
            ego_id=self.ego_id,
            measures=self.measures,
            corrections=(*self.corrections, correction),
            event_order=(*self.event_order, event_ref),
        )

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        measure_ids = tuple(measure.measure_id for measure in self.measures)
        correction_ids = tuple(item.correction_id for item in self.corrections)
        if len(set(measure_ids)) != len(measure_ids):
            raise ValueError("EgoTrace measure IDs must be unique")
        if len(set(correction_ids)) != len(correction_ids):
            raise ValueError("EgoTrace correction IDs must be unique")
        for correction in self.corrections:
            if correction.ego_id != self.ego_id:
                raise ValueError("Correction event belongs to another EgoTrace")
            if correction.target_measure_id not in measure_ids:
                raise ValueError("Correction event must target an existing measure")
        expected_indexes = tuple(range(len(self.event_order)))
        if tuple(item.sequence_index for item in self.event_order) != expected_indexes:
            raise ValueError("EgoTrace event_order must use contiguous append indexes")
        expected_events = {
            ("measure", measure.measure_id): measure.measure_hash
            for measure in self.measures
        }
        expected_events.update(
            {
                ("correction", correction.correction_id): correction.correction_hash
                for correction in self.corrections
            }
        )
        recorded_events = {
            (item.event_kind, item.event_id): item.event_hash for item in self.event_order
        }
        if len(recorded_events) != len(self.event_order):
            raise ValueError("EgoTrace event_order cannot repeat an event")
        if recorded_events != expected_events:
            raise ValueError("EgoTrace event_order must reference every stored event once")
        position_by_event = {
            (item.event_kind, item.event_id): item.sequence_index
            for item in self.event_order
        }
        for correction in self.corrections:
            measure_position = position_by_event[("measure", correction.target_measure_id)]
            correction_position = position_by_event[("correction", correction.correction_id)]
            if correction_position <= measure_position:
                raise ValueError("A correction must be appended after its target measure")
        expected = self.content_hash(exclude_fields=frozenset({"trace_hash"}))
        if self.trace_hash != expected:
            raise ValueError("trace_hash does not match its canonical payload")
        return self


def _validate_projection_evidence(
    through_measure_id: NonEmptyId,
    evidence_measure_ids: tuple[NonEmptyId, ...],
) -> None:
    if through_measure_id not in evidence_measure_ids:
        raise ValueError("through_measure_id must be included in evidence_measure_ids")
    if len(set(evidence_measure_ids)) != len(evidence_measure_ids):
        raise ValueError("evidence_measure_ids must be unique")


def _validate_claim_coverage(
    *,
    claims: tuple[SourcedEgoClaim, ...],
    field_values: Mapping[EgoClaimKind, tuple[str, ...]],
    evidence_measure_ids: tuple[NonEmptyId, ...],
) -> None:
    claim_ids = tuple(claim.claim_id for claim in claims)
    if len(set(claim_ids)) != len(claim_ids):
        raise ValueError("Sourced Ego claim IDs must be unique")
    expected = tuple(
        (kind, text)
        for kind, values in field_values.items()
        for text in values
    )
    actual = tuple((claim.kind, claim.text) for claim in claims)
    if actual != expected:
        raise ValueError(
            "Sourced Ego claims must exactly cover derived fields in canonical order"
        )
    allowed_evidence = set(evidence_measure_ids)
    cited_evidence: set[str] = set()
    for claim in claims:
        if not set(claim.evidence_measure_ids).issubset(allowed_evidence):
            raise ValueError("Sourced Ego claim cites a measure outside its artifact")
        cited_evidence.update(claim.evidence_measure_ids)
    if cited_evidence != allowed_evidence:
        raise ValueError("Every artifact evidence measure must support a sourced claim")


def _validate_derived_identity(
    artifact: FrozenArtifactModel,
    *,
    id_field: str,
    id_prefix: str,
    hash_field: str,
) -> None:
    id_payload = artifact.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, hash_field},
    )
    artifact_id = getattr(artifact, id_field)
    if artifact_id != content_id(id_prefix, id_payload):
        raise ValueError(f"{id_field} does not match the derived artifact content")
    expected_hash = artifact.content_hash(exclude_fields=frozenset({hash_field}))
    if getattr(artifact, hash_field) != expected_hash:
        raise ValueError(f"{hash_field} does not match the derived artifact payload")


class EgoCompositionSnapshot(FrozenArtifactModel):
    schema_version: Literal["rei-native-ego-composition-v2"] = (
        "rei-native-ego-composition-v2"
    )
    snapshot_id: NonEmptyId
    ego_id: NonEmptyId
    through_measure_id: NonEmptyId
    identity_motifs: tuple[str, ...] = ()
    recurring_conflicts: tuple[str, ...] = ()
    recurring_translation_errors: tuple[str, ...] = ()
    unresolved_tensions: tuple[str, ...] = ()
    resolved_tensions: tuple[str, ...] = ()
    spoznanja: tuple[str, ...] = ()
    commitments: tuple[str, ...] = ()
    relationship_patterns: tuple[str, ...] = ()
    current_section: str
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    created_at: UtcTimestamp
    derivation_status: DerivationStatus = "derived_from_trace"
    source_trace_hash: HashDigest
    sourced_claims: tuple[SourcedEgoClaim, ...]
    composition_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        through_measure_id: NonEmptyId,
        current_section: str,
        evidence_measure_ids: tuple[NonEmptyId, ...],
        created_at: UtcTimestamp,
        source_trace_hash: HashDigest,
        sourced_claims: tuple[SourcedEgoClaim, ...],
        identity_motifs: tuple[str, ...] = (),
        recurring_conflicts: tuple[str, ...] = (),
        recurring_translation_errors: tuple[str, ...] = (),
        unresolved_tensions: tuple[str, ...] = (),
        resolved_tensions: tuple[str, ...] = (),
        spoznanja: tuple[str, ...] = (),
        commitments: tuple[str, ...] = (),
        relationship_patterns: tuple[str, ...] = (),
    ) -> EgoCompositionSnapshot:
        base = {
            "schema_version": "rei-native-ego-composition-v2",
            "ego_id": ego_id,
            "through_measure_id": through_measure_id,
            "identity_motifs": identity_motifs,
            "recurring_conflicts": recurring_conflicts,
            "recurring_translation_errors": recurring_translation_errors,
            "unresolved_tensions": unresolved_tensions,
            "resolved_tensions": resolved_tensions,
            "spoznanja": spoznanja,
            "commitments": commitments,
            "relationship_patterns": relationship_patterns,
            "current_section": current_section,
            "evidence_measure_ids": evidence_measure_ids,
            "created_at": created_at,
            "derivation_status": "derived_from_trace",
            "source_trace_hash": source_trace_hash,
            "sourced_claims": sourced_claims,
        }
        snapshot_id = content_id("ego_snapshot", base)
        payload = {"snapshot_id": snapshot_id, **base}
        return cls(**payload, composition_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_evidence_boundary(self) -> Self:
        _validate_projection_evidence(self.through_measure_id, self.evidence_measure_ids)
        _validate_claim_coverage(
            claims=self.sourced_claims,
            field_values={
                "identity_motif": self.identity_motifs,
                "recurring_conflict": self.recurring_conflicts,
                "recurring_translation_error": self.recurring_translation_errors,
                "unresolved_tension": self.unresolved_tensions,
                "resolved_tension": self.resolved_tensions,
                "spoznanje": self.spoznanja,
                "commitment": self.commitments,
                "relationship_pattern": self.relationship_patterns,
                "current_section": (self.current_section,),
            },
            evidence_measure_ids=self.evidence_measure_ids,
        )
        _validate_derived_identity(
            self,
            id_field="snapshot_id",
            id_prefix="ego_snapshot",
            hash_field="composition_hash",
        )
        return self


class RacioProjection(FrozenArtifactModel):
    schema_version: Literal["rei-native-racio-projection-v2"] = (
        "rei-native-racio-projection-v2"
    )
    projection_id: NonEmptyId
    ego_id: NonEmptyId
    through_measure_id: NonEmptyId
    chronology: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    statements: tuple[str, ...] = ()
    commitments: tuple[str, ...] = ()
    causal_links: tuple[str, ...] = ()
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    derivation_status: DerivationStatus = "derived_from_trace"
    source_trace_hash: HashDigest
    sourced_claims: tuple[SourcedEgoClaim, ...]
    projection_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        through_measure_id: NonEmptyId,
        evidence_measure_ids: tuple[NonEmptyId, ...],
        source_trace_hash: HashDigest,
        sourced_claims: tuple[SourcedEgoClaim, ...],
        chronology: tuple[str, ...] = (),
        facts: tuple[str, ...] = (),
        statements: tuple[str, ...] = (),
        commitments: tuple[str, ...] = (),
        causal_links: tuple[str, ...] = (),
    ) -> RacioProjection:
        base = {
            "schema_version": "rei-native-racio-projection-v2",
            "ego_id": ego_id,
            "through_measure_id": through_measure_id,
            "chronology": chronology,
            "facts": facts,
            "statements": statements,
            "commitments": commitments,
            "causal_links": causal_links,
            "evidence_measure_ids": evidence_measure_ids,
            "derivation_status": "derived_from_trace",
            "source_trace_hash": source_trace_hash,
            "sourced_claims": sourced_claims,
        }
        projection_id = content_id("racio_projection", base)
        payload = {"projection_id": projection_id, **base}
        return cls(**payload, projection_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_evidence_boundary(self) -> Self:
        _validate_projection_evidence(self.through_measure_id, self.evidence_measure_ids)
        self._validate_derivation()
        return self

    def _validate_derivation(self) -> None:
        _validate_claim_coverage(
            claims=self.sourced_claims,
            field_values={
                "racio_chronology": self.chronology,
                "racio_fact": self.facts,
                "racio_statement": self.statements,
                "racio_commitment": self.commitments,
                "racio_causal_link": self.causal_links,
            },
            evidence_measure_ids=self.evidence_measure_ids,
        )
        _validate_derived_identity(
            self,
            id_field="projection_id",
            id_prefix="racio_projection",
            hash_field="projection_hash",
        )


class EmocioProjection(FrozenArtifactModel):
    schema_version: Literal["rei-native-emocio-projection-v2"] = (
        "rei-native-emocio-projection-v2"
    )
    projection_id: NonEmptyId
    ego_id: NonEmptyId
    through_measure_id: NonEmptyId
    recurring_scenes: tuple[str, ...] = ()
    image_artifact_ids: tuple[NonEmptyId, ...] = ()
    status_patterns: tuple[str, ...] = ()
    belonging_motifs: tuple[str, ...] = ()
    success_motifs: tuple[str, ...] = ()
    rupture_motifs: tuple[str, ...] = ()
    desire_motifs: tuple[str, ...] = ()
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    derivation_status: DerivationStatus = "derived_from_trace"
    source_trace_hash: HashDigest
    sourced_claims: tuple[SourcedEgoClaim, ...]
    projection_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        through_measure_id: NonEmptyId,
        evidence_measure_ids: tuple[NonEmptyId, ...],
        source_trace_hash: HashDigest,
        sourced_claims: tuple[SourcedEgoClaim, ...],
        recurring_scenes: tuple[str, ...] = (),
        image_artifact_ids: tuple[NonEmptyId, ...] = (),
        status_patterns: tuple[str, ...] = (),
        belonging_motifs: tuple[str, ...] = (),
        success_motifs: tuple[str, ...] = (),
        rupture_motifs: tuple[str, ...] = (),
        desire_motifs: tuple[str, ...] = (),
    ) -> EmocioProjection:
        base = {
            "schema_version": "rei-native-emocio-projection-v2",
            "ego_id": ego_id,
            "through_measure_id": through_measure_id,
            "recurring_scenes": recurring_scenes,
            "image_artifact_ids": image_artifact_ids,
            "status_patterns": status_patterns,
            "belonging_motifs": belonging_motifs,
            "success_motifs": success_motifs,
            "rupture_motifs": rupture_motifs,
            "desire_motifs": desire_motifs,
            "evidence_measure_ids": evidence_measure_ids,
            "derivation_status": "derived_from_trace",
            "source_trace_hash": source_trace_hash,
            "sourced_claims": sourced_claims,
        }
        projection_id = content_id("emocio_projection", base)
        payload = {"projection_id": projection_id, **base}
        return cls(**payload, projection_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_evidence_boundary(self) -> Self:
        _validate_projection_evidence(self.through_measure_id, self.evidence_measure_ids)
        _validate_claim_coverage(
            claims=self.sourced_claims,
            field_values={
                "emocio_recurring_scene": self.recurring_scenes,
                "emocio_image_artifact": self.image_artifact_ids,
                "emocio_status_pattern": self.status_patterns,
                "emocio_belonging_motif": self.belonging_motifs,
                "emocio_success_motif": self.success_motifs,
                "emocio_rupture_motif": self.rupture_motifs,
                "emocio_desire_motif": self.desire_motifs,
            },
            evidence_measure_ids=self.evidence_measure_ids,
        )
        _validate_derived_identity(
            self,
            id_field="projection_id",
            id_prefix="emocio_projection",
            hash_field="projection_hash",
        )
        return self


class InstinktProjection(FrozenArtifactModel):
    schema_version: Literal["rei-native-instinkt-projection-v2"] = (
        "rei-native-instinkt-projection-v2"
    )
    projection_id: NonEmptyId
    ego_id: NonEmptyId
    through_measure_id: NonEmptyId
    body_consequences: tuple[str, ...] = ()
    dangers: tuple[str, ...] = ()
    losses: tuple[str, ...] = ()
    trust_patterns: tuple[str, ...] = ()
    attachment_patterns: tuple[str, ...] = ()
    boundary_patterns: tuple[str, ...] = ()
    scarcity_patterns: tuple[str, ...] = ()
    recovery_patterns: tuple[str, ...] = ()
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    derivation_status: DerivationStatus = "derived_from_trace"
    source_trace_hash: HashDigest
    sourced_claims: tuple[SourcedEgoClaim, ...]
    projection_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        ego_id: NonEmptyId,
        through_measure_id: NonEmptyId,
        evidence_measure_ids: tuple[NonEmptyId, ...],
        source_trace_hash: HashDigest,
        sourced_claims: tuple[SourcedEgoClaim, ...],
        body_consequences: tuple[str, ...] = (),
        dangers: tuple[str, ...] = (),
        losses: tuple[str, ...] = (),
        trust_patterns: tuple[str, ...] = (),
        attachment_patterns: tuple[str, ...] = (),
        boundary_patterns: tuple[str, ...] = (),
        scarcity_patterns: tuple[str, ...] = (),
        recovery_patterns: tuple[str, ...] = (),
    ) -> InstinktProjection:
        base = {
            "schema_version": "rei-native-instinkt-projection-v2",
            "ego_id": ego_id,
            "through_measure_id": through_measure_id,
            "body_consequences": body_consequences,
            "dangers": dangers,
            "losses": losses,
            "trust_patterns": trust_patterns,
            "attachment_patterns": attachment_patterns,
            "boundary_patterns": boundary_patterns,
            "scarcity_patterns": scarcity_patterns,
            "recovery_patterns": recovery_patterns,
            "evidence_measure_ids": evidence_measure_ids,
            "derivation_status": "derived_from_trace",
            "source_trace_hash": source_trace_hash,
            "sourced_claims": sourced_claims,
        }
        projection_id = content_id("instinkt_projection", base)
        payload = {"projection_id": projection_id, **base}
        return cls(**payload, projection_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_evidence_boundary(self) -> Self:
        _validate_projection_evidence(self.through_measure_id, self.evidence_measure_ids)
        _validate_claim_coverage(
            claims=self.sourced_claims,
            field_values={
                "instinkt_body_consequence": self.body_consequences,
                "instinkt_danger": self.dangers,
                "instinkt_loss": self.losses,
                "instinkt_trust_pattern": self.trust_patterns,
                "instinkt_attachment_pattern": self.attachment_patterns,
                "instinkt_boundary_pattern": self.boundary_patterns,
                "instinkt_scarcity_pattern": self.scarcity_patterns,
                "instinkt_recovery_pattern": self.recovery_patterns,
            },
            evidence_measure_ids=self.evidence_measure_ids,
        )
        _validate_derived_identity(
            self,
            id_field="projection_id",
            id_prefix="instinkt_projection",
            hash_field="projection_hash",
        )
        return self


class ReflectionHypothesis(FrozenArtifactModel):
    """Optional sourced hypothesis; never an input to the current decision."""

    schema_version: Literal["rei-native-reflection-hypothesis-v1"] = (
        "rei-native-reflection-hypothesis-v1"
    )
    hypothesis_id: NonEmptyId
    ego_id: NonEmptyId
    statement: str
    confidence: Score01
    supporting_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    created_at: UtcTimestamp

    @model_validator(mode="after")
    def validate_supporting_measures(self) -> Self:
        if len(set(self.supporting_measure_ids)) != len(
            self.supporting_measure_ids
        ):
            raise ValueError("Supporting measure IDs must be unique")
        return self


__all__ = [
    "DerivationStatus",
    "EgoClaimKind",
    "EgoCompositionSnapshot",
    "EgoCorrectionEvent",
    "EgoMeasure",
    "EgoTrace",
    "EgoTraceEventRef",
    "EmocioProjection",
    "InstinktProjection",
    "OutcomeRecord",
    "RacioProjection",
    "ReflectionHypothesis",
    "SourcedEgoClaim",
    "SpoznanjeStatus",
]
