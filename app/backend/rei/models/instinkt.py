"""Strict contracts for Instinkt's embodied and protective native route.

These models describe a bounded software simulator.  They are not medical or
physiological claims, and they contain no textual decision-provider behavior.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .scene import EvidenceItem, SceneEvent


InstinktActionTendency = Literal[
    "protect",
    "withdraw",
    "maintain",
    "set_boundary",
    "seek_safety",
    "seek_attachment",
    "conserve",
    "freeze",
    "unknown",
]
BodyDimension = Literal[
    "energy",
    "fatigue",
    "pain",
    "arousal",
    "tension",
    "physical_integrity",
    "uncertainty",
    "trust",
    "attachment_security",
    "resource_security",
    "boundary_integrity",
    "escape_availability",
    "predictability",
]
_BODY_DIMENSIONS: tuple[BodyDimension, ...] = (
    "energy",
    "fatigue",
    "pain",
    "arousal",
    "tension",
    "physical_integrity",
    "uncertainty",
    "trust",
    "attachment_security",
    "resource_security",
    "boundary_integrity",
    "escape_availability",
    "predictability",
)
BODY_DIMENSIONS = _BODY_DIMENSIONS
UnitDelta = Annotated[
    float,
    Field(ge=-1.0, le=1.0, allow_inf_nan=False),
]
PositiveUnit = Annotated[float, Field(gt=0.0, le=1.0, allow_inf_nan=False)]
SimulationArtifactStatus = Literal["unverified_contract", "simulated_v1"]
InstinktCueLane = Literal[
    "physical_cues",
    "uncertainty_cues",
    "trust_cues",
    "boundary_cues",
    "attachment_cues",
    "scarcity_cues",
    "escape_cues",
    "explicit_body_cues",
]
EmbodiedCueClass = Literal[
    "physical_threat",
    "pain_or_injury",
    "uncertainty",
    "predictability",
    "trust",
    "betrayal",
    "boundary",
    "attachment",
    "abandonment",
    "resource_security",
    "scarcity",
    "escape_availability",
    "social_safety",
    "protected_other",
    "fatigue",
    "temperature_or_environment",
]
EMBODIED_CUE_CLASSES: tuple[EmbodiedCueClass, ...] = (
    "physical_threat",
    "pain_or_injury",
    "uncertainty",
    "predictability",
    "trust",
    "betrayal",
    "boundary",
    "attachment",
    "abandonment",
    "resource_security",
    "scarcity",
    "escape_availability",
    "social_safety",
    "protected_other",
    "fatigue",
    "temperature_or_environment",
)
InstinktCueAssertionStatus = Literal[
    "asserted_positive",
    "negated",
    "mentioned",
    "uncertain",
]
INSTINKT_CUE_LANES: tuple[InstinktCueLane, ...] = (
    "physical_cues",
    "uncertainty_cues",
    "trust_cues",
    "boundary_cues",
    "attachment_cues",
    "scarcity_cues",
    "escape_cues",
    "explicit_body_cues",
)
MAX_INSTINKT_CUES_PER_LANE = 64
MAX_INSTINKT_TOTAL_CUES = 256
MAX_INSTINKT_CUE_TEXT_CHARS = 1_000
MAX_INSTINKT_EVIDENCE_IDS = 256
MAX_INSTINKT_CUE_BINDINGS = 256
MAX_INSTINKT_ASSOCIATION_RECORDS = 512
MAX_INSTINKT_ASSOCIATION_CUES = 64
MAX_INSTINKT_ASSOCIATION_TEXT_CHARS = 4_000
MAX_INSTINKT_CITED_TEXT_CHARS = 4_000
_BODY_TRANSITION_B8_FIELDS = frozenset(
    {
        "simulation_status",
        "source_packet_id",
        "source_packet_hash",
        "source_effect_id",
        "source_effect_hash",
        "source_config_id",
        "source_config_hash",
        "step_index",
        "transition_hash",
    }
)
_OPTION_ROLLOUT_B8_FIELDS = frozenset(
    {
        "simulation_status",
        "source_packet_id",
        "source_packet_hash",
        "source_body_state_id",
        "source_body_state_hash",
        "source_effect_id",
        "source_effect_hash",
        "source_config_id",
        "source_config_hash",
        "transitions",
        "association_match_ids",
        "association_matches",
        "rollout_hash",
    }
)


class InstinktWorld(FrozenArtifactModel):
    """Immutable snapshot of Instinkt's associative/protective world."""

    schema_version: Literal["rei-native-instinkt-world-v1"] = (
        "rei-native-instinkt-world-v1"
    )
    world_id: NonEmptyId
    associations: tuple[str, ...]
    trusted_patterns: tuple[str, ...]
    threat_patterns: tuple[str, ...]
    attachment_objects: tuple[str, ...]
    unresolved_losses: tuple[str, ...]
    boundary_patterns: tuple[str, ...]

    @classmethod
    def create(
        cls,
        *,
        associations: tuple[str, ...] = (),
        trusted_patterns: tuple[str, ...] = (),
        threat_patterns: tuple[str, ...] = (),
        attachment_objects: tuple[str, ...] = (),
        unresolved_losses: tuple[str, ...] = (),
        boundary_patterns: tuple[str, ...] = (),
    ) -> "InstinktWorld":
        """Build a stable profile-blind world snapshot from canonical fields."""

        base = {
            "schema_version": "rei-native-instinkt-world-v1",
            "associations": tuple(sorted(set(associations))),
            "trusted_patterns": tuple(sorted(set(trusted_patterns))),
            "threat_patterns": tuple(sorted(set(threat_patterns))),
            "attachment_objects": tuple(sorted(set(attachment_objects))),
            "unresolved_losses": tuple(sorted(set(unresolved_losses))),
            "boundary_patterns": tuple(sorted(set(boundary_patterns))),
        }
        return cls(world_id=content_id("instinkt_world", base), **base)

    @model_validator(mode="after")
    def validate_content_addressed_world(self) -> "InstinktWorld":
        """Validate C5 worlds while retaining pre-C5 opaque fixture IDs."""

        if self.world_id.startswith("instinkt_world_"):
            base = self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"world_id"},
            )
            if self.world_id != content_id("instinkt_world", base):
                raise ValueError(
                    "Content-addressed InstinktWorld ID differs from its content"
                )
        return self


class InstinktCueEvidenceCitation(FrozenArtifactModel):
    """Exact content-hashed span from one supplied grounded evidence item."""

    schema_version: Literal["rei-native-instinkt-cue-evidence-citation-v1"] = (
        "rei-native-instinkt-cue-evidence-citation-v1"
    )
    citation_id: NonEmptyId
    evidence_id: NonEmptyId
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    cited_text: NonEmptyText
    source_content_hash: HashDigest
    cited_text_hash: HashDigest
    citation_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        evidence: EvidenceItem,
        start_char: int,
        end_char: int,
    ) -> "InstinktCueEvidenceCitation":
        if start_char < 0 or end_char <= start_char or end_char > len(evidence.content):
            raise ValueError("Instinkt cue citation span is outside its evidence content")
        cited_text = evidence.content[start_char:end_char]
        if cited_text != cited_text.strip():
            raise ValueError("Instinkt cue citation must exclude surrounding whitespace")
        base = {
            "schema_version": "rei-native-instinkt-cue-evidence-citation-v1",
            "evidence_id": evidence.evidence_id,
            "start_char": start_char,
            "end_char": end_char,
            "cited_text": cited_text,
            "source_content_hash": sha256_hex(evidence.content),
            "cited_text_hash": sha256_hex(cited_text),
        }
        citation_id = content_id("instinkt_cue_citation", base)
        payload = {"citation_id": citation_id, **base}
        return cls(**payload, citation_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_citation(self) -> Self:
        if self.end_char <= self.start_char:
            raise ValueError("Instinkt cue citation end must follow its start")
        if len(self.cited_text) > MAX_INSTINKT_CITED_TEXT_CHARS:
            raise ValueError("Instinkt cue citation exceeds its bounded text limit")
        if self.cited_text_hash != sha256_hex(self.cited_text):
            raise ValueError("Instinkt cue citation text hash differs from its text")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"citation_id", "citation_hash"},
        )
        if self.citation_id != content_id("instinkt_cue_citation", base):
            raise ValueError("Instinkt cue citation ID differs from its content")
        payload = {"citation_id": self.citation_id, **base}
        if self.citation_hash != sha256_hex(payload):
            raise ValueError("Instinkt cue citation hash differs from its content")
        return self

    def validate_against(self, evidence: EvidenceItem) -> Self:
        if self.evidence_id != evidence.evidence_id:
            raise ValueError("Instinkt cue citation belongs to another evidence item")
        if not evidence.grounded or evidence.provenance_kind != "supplied":
            raise ValueError(
                "Instinkt cue citations require supplied grounded evidence"
            )
        if self.source_content_hash != sha256_hex(evidence.content):
            raise ValueError("Instinkt cue citation source-content hash differs")
        if self.end_char > len(evidence.content):
            raise ValueError("Instinkt cue citation span exceeds its evidence content")
        if evidence.content[self.start_char : self.end_char] != self.cited_text:
            raise ValueError("Instinkt cue citation is not the exact cited evidence span")
        return self


class InstinktCueEvidenceBinding(FrozenArtifactModel):
    """Typed assertion plus exact evidence spans for one caller-supplied cue."""

    schema_version: Literal["rei-native-instinkt-cue-evidence-binding-v2"] = (
        "rei-native-instinkt-cue-evidence-binding-v2"
    )
    binding_id: NonEmptyId
    lane: InstinktCueLane
    cue_class: EmbodiedCueClass
    cue: NonEmptyText
    assertion_status: InstinktCueAssertionStatus
    citations: tuple[InstinktCueEvidenceCitation, ...] = Field(min_length=1)
    binding_hash: HashDigest

    @property
    def evidence_ids(self) -> tuple[NonEmptyId, ...]:
        return tuple(item.evidence_id for item in self.citations)

    @classmethod
    def create(
        cls,
        *,
        lane: InstinktCueLane,
        cue_class: EmbodiedCueClass,
        cue: NonEmptyText,
        assertion_status: InstinktCueAssertionStatus,
        citations: tuple[InstinktCueEvidenceCitation, ...],
    ) -> "InstinktCueEvidenceBinding":
        canonical_citations = tuple(
            sorted(
                citations,
                key=lambda item: (
                    item.evidence_id,
                    item.start_char,
                    item.end_char,
                    item.citation_id,
                ),
            )
        )
        base = {
            "schema_version": "rei-native-instinkt-cue-evidence-binding-v2",
            "lane": lane,
            "cue_class": cue_class,
            "cue": cue.strip(),
            "assertion_status": assertion_status,
            "citations": canonical_citations,
        }
        binding_id = content_id("instinkt_cue_binding", base)
        payload = {"binding_id": binding_id, **base}
        return cls(**payload, binding_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        if self.cue != self.cue.strip():
            raise ValueError("Instinkt cue binding text must be stripped")
        expected_citations = tuple(
            sorted(
                self.citations,
                key=lambda item: (
                    item.evidence_id,
                    item.start_char,
                    item.end_char,
                    item.citation_id,
                ),
            )
        )
        if self.citations != expected_citations:
            raise ValueError("Instinkt cue citations must use canonical span order")
        citation_ids = tuple(item.citation_id for item in self.citations)
        if len(set(citation_ids)) != len(citation_ids):
            raise ValueError("Instinkt cue citation IDs must be unique")
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("Each cue binding may cite an evidence item once")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"binding_id", "binding_hash"},
        )
        if self.binding_id != content_id("instinkt_cue_binding", base):
            raise ValueError("Instinkt cue binding ID differs from its content")
        payload = {"binding_id": self.binding_id, **base}
        if self.binding_hash != sha256_hex(payload):
            raise ValueError("Instinkt cue binding hash differs from its content")
        return self


class InstinktInputPacket(FrozenArtifactModel):
    """Profile-blind grounded cues routed to Instinkt without a chosen action."""

    schema_version: Literal["rei-native-instinkt-input-packet-v1"] = (
        "rei-native-instinkt-input-packet-v1"
    )
    packet_id: NonEmptyId
    scene_id: NonEmptyId
    source_body_state_id: NonEmptyId
    physical_cues: tuple[str, ...]
    uncertainty_cues: tuple[str, ...]
    trust_cues: tuple[str, ...]
    boundary_cues: tuple[str, ...]
    attachment_cues: tuple[str, ...]
    scarcity_cues: tuple[str, ...]
    escape_cues: tuple[str, ...]
    explicit_body_cues: tuple[str, ...]
    option_ids: tuple[NonEmptyId, ...]
    evidence_ids: tuple[NonEmptyId, ...]
    cue_evidence_bindings: tuple[InstinktCueEvidenceBinding, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    previous_instinkt_projection_ids: tuple[NonEmptyId, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    previous_instinkt_projection_hashes: tuple[HashDigest, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    caveat: str

    @model_validator(mode="after")
    def validate_packet_references(self) -> "InstinktInputPacket":
        lane_sizes = tuple(len(getattr(self, lane)) for lane in INSTINKT_CUE_LANES)
        if any(size > MAX_INSTINKT_CUES_PER_LANE for size in lane_sizes):
            raise ValueError("Instinkt cue lane exceeds its bounded input limit")
        if sum(lane_sizes) > MAX_INSTINKT_TOTAL_CUES:
            raise ValueError("Instinkt packet exceeds its total cue limit")
        if any(
            len(cue) > MAX_INSTINKT_CUE_TEXT_CHARS
            for lane in INSTINKT_CUE_LANES
            for cue in getattr(self, lane)
        ):
            raise ValueError("Instinkt cue text exceeds its bounded input limit")
        if len(self.evidence_ids) > MAX_INSTINKT_EVIDENCE_IDS:
            raise ValueError("Instinkt packet exceeds its evidence-reference limit")
        if len(self.cue_evidence_bindings) > MAX_INSTINKT_CUE_BINDINGS:
            raise ValueError("Instinkt packet exceeds its cue-binding limit")
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("option_ids must be unique")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        expected_bindings = tuple(
            sorted(self.cue_evidence_bindings, key=lambda item: item.binding_id)
        )
        if self.cue_evidence_bindings != expected_bindings:
            raise ValueError("Instinkt cue bindings must use canonical ID order")
        binding_ids = tuple(item.binding_id for item in self.cue_evidence_bindings)
        if len(set(binding_ids)) != len(binding_ids):
            raise ValueError("Instinkt cue binding IDs must be unique")
        bound_cues: set[tuple[str, str, str]] = set()
        packet_evidence = set(self.evidence_ids)
        for binding in self.cue_evidence_bindings:
            key = (binding.lane, binding.cue_class, binding.cue)
            if key in bound_cues:
                raise ValueError(
                    "Each typed Instinkt cue class may have one lane/cue binding"
                )
            bound_cues.add(key)
            if binding.cue not in getattr(self, binding.lane):
                raise ValueError("Instinkt cue binding refers to an absent lane cue")
            if not set(binding.evidence_ids).issubset(packet_evidence):
                raise ValueError("Instinkt cue binding evidence escapes the packet")
        if len(self.previous_instinkt_projection_ids) != len(
            self.previous_instinkt_projection_hashes
        ):
            raise ValueError("Instinkt projection IDs and hashes must have equal length")
        if len(set(self.previous_instinkt_projection_ids)) != len(
            self.previous_instinkt_projection_ids
        ):
            raise ValueError("Instinkt projection IDs must be unique")
        return self

    def validate_against(self, scene: SceneEvent, body_state: BodyState) -> Self:
        """Bind protective cues to one event and one explicit virtual-body state."""

        self.validate_scene(scene)
        if self.source_body_state_id != body_state.body_state_id:
            raise ValueError("Instinkt packet belongs to another BodyState")
        return self

    def validate_scene(self, scene: SceneEvent) -> Self:
        """Bind packet option/evidence scope to the trusted event."""

        if self.scene_id != scene.event_id:
            raise ValueError("Instinkt packet belongs to another SceneEvent")
        scene_option_ids = {option.option_id for option in scene.options}
        if set(self.option_ids) != scene_option_ids:
            raise ValueError("Instinkt packet must preserve every SceneEvent option")
        scene_evidence_ids = {item.evidence_id for item in scene.evidence}
        if not set(self.evidence_ids).issubset(scene_evidence_ids):
            raise ValueError("Instinkt packet evidence must belong to the SceneEvent")
        scene_evidence = {item.evidence_id: item for item in scene.evidence}
        for binding in self.cue_evidence_bindings:
            for citation in binding.citations:
                source = scene_evidence[citation.evidence_id]
                citation.validate_against(source)
        return self


class BodyState(FrozenArtifactModel):
    """Normalized virtual-body state for one point in a bounded cycle."""

    schema_version: Literal["rei-native-body-state-v1"] = (
        "rei-native-body-state-v1"
    )
    body_state_id: NonEmptyId
    energy: Score01
    fatigue: Score01
    pain: Score01
    arousal: Score01
    tension: Score01
    physical_integrity: Score01
    uncertainty: Score01
    trust: Score01
    attachment_security: Score01
    resource_security: Score01
    boundary_integrity: Score01
    escape_availability: Score01
    predictability: Score01


class InstinktAssociation(FrozenArtifactModel):
    """One bounded, fallible associative-memory record."""

    schema_version: Literal["rei-native-instinkt-association-v1"] = (
        "rei-native-instinkt-association-v1"
    )
    association_id: NonEmptyId
    cue_signature: tuple[str, ...]
    cue_classes: tuple[NonEmptyText, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    loss_classes: tuple[NonEmptyText, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    body_state_before: BodyState
    felt_intensity: Score01
    protected_target: str
    experienced_loss: str | None
    action_taken: str
    outcome: str
    trust_delta: UnitDelta
    attachment_delta: UnitDelta
    boundary_delta: UnitDelta
    decay: Score01

    @model_validator(mode="after")
    def validate_typed_learning_context(self) -> "InstinktAssociation":
        if len(self.cue_signature) > MAX_INSTINKT_ASSOCIATION_CUES:
            raise ValueError("Association cue signature exceeds its bounded limit")
        if len(set(self.cue_signature)) != len(self.cue_signature):
            raise ValueError("Association cue signature must contain unique values")
        bounded_text = (
            *self.cue_signature,
            *self.cue_classes,
            *self.loss_classes,
            self.protected_target,
            *(value for value in (self.experienced_loss,) if value is not None),
            self.action_taken,
            self.outcome,
        )
        if any(len(value) > MAX_INSTINKT_ASSOCIATION_TEXT_CHARS for value in bounded_text):
            raise ValueError("Association text exceeds its bounded input limit")
        if self.cue_classes != tuple(sorted(set(self.cue_classes))):
            raise ValueError("Association cue classes must be sorted and unique")
        if self.loss_classes != tuple(sorted(set(self.loss_classes))):
            raise ValueError("Association loss classes must be sorted and unique")
        if not set(self.loss_classes).issubset(self.cue_classes):
            raise ValueError("Association loss classes must be a subset of cue classes")
        return self


InstinktProjectionObservationKind = Literal[
    "body_consequence",
    "danger",
    "loss",
    "trust",
    "attachment",
    "boundary",
    "scarcity",
    "recovery",
]


class InstinktProjectionObservation(FrozenArtifactModel):
    """Observation-only Ego projection admitted to associative retrieval.

    Unlike :class:`InstinktAssociation`, this record claims neither a concrete
    historical body state nor an experienced outcome. It can affect audit
    lineage and exact-token retrieval, but cannot activate experienced-loss
    dynamics.
    """

    schema_version: Literal["rei-native-instinkt-projection-observation-v1"] = (
        "rei-native-instinkt-projection-observation-v1"
    )
    observation_id: NonEmptyId
    source_projection_id: NonEmptyId
    source_projection_hash: HashDigest
    observation_kind: InstinktProjectionObservationKind
    observation: NonEmptyText
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    cue_signature: tuple[NonEmptyText, ...] = Field(min_length=1)
    felt_intensity: Score01
    protected_target: NonEmptyText
    predicted_recoverability: Score01 | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    decay: Score01 = 0.0

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.evidence_measure_ids != tuple(
            sorted(set(self.evidence_measure_ids))
        ):
            raise ValueError(
                "Projection observation evidence IDs must be sorted and unique"
            )
        if self.cue_signature != tuple(sorted(set(self.cue_signature))):
            raise ValueError(
                "Projection observation cue signature must be sorted and unique"
            )
        if (self.observation_kind == "recovery") != (
            self.predicted_recoverability is not None
        ):
            raise ValueError(
                "Only recovery projection observations carry predicted recoverability"
            )
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"observation_id"},
        )
        if self.observation_id != content_id(
            "instinkt_projection_observation", payload
        ):
            raise ValueError(
                "Instinkt projection observation ID differs from canonical content"
            )
        return self


InstinktMemoryRecord = InstinktAssociation | InstinktProjectionObservation


def instinkt_memory_record_id(record: InstinktMemoryRecord) -> NonEmptyId:
    if isinstance(record, InstinktAssociation):
        return record.association_id
    return record.observation_id


def instinkt_association_content_id(association: InstinktAssociation) -> NonEmptyId:
    """Derive the canonical ID for a content-addressed learned association."""

    base = association.model_dump(
        mode="python",
        round_trip=True,
        exclude={"association_id"},
    )
    return content_id("instinkt_association", base)


def instinkt_projection_memory_token(
    projection_id: NonEmptyId,
    projection_hash: HashDigest,
) -> NonEmptyText:
    """Build the exact, non-semantic B8 query token for one Ego projection.

    The token carries only immutable projection lineage.  It deliberately does
    not reinterpret projection prose as current-scene evidence.
    """

    return f"ego_projection_ref:{projection_id}:{projection_hash}"


class AssociationMatch(FrozenArtifactModel):
    """Content-addressed snapshot of one bounded memory retrieval result."""

    schema_version: Literal["rei-native-association-match-v1"] = (
        "rei-native-association-match-v1"
    )
    match_id: NonEmptyId
    association_id: NonEmptyId
    association_hash: HashDigest
    memory_cycle: int = Field(ge=0)
    age_cycles: int = Field(ge=0)
    overlap_tokens: tuple[str, ...] = Field(min_length=1)
    effective_strength: Score01
    retrieval_score: Score01
    carries_experienced_loss: bool
    protected_target: str
    predicted_recoverability: Score01 | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    source_record_kind: Literal[
        "experienced_association", "projection_observation"
    ] = Field(
        default="experienced_association",
        exclude_if=lambda value: value == "experienced_association",
    )

    @model_validator(mode="after")
    def validate_match(self) -> Self:
        canonical_overlap = tuple(sorted(set(self.overlap_tokens)))
        if self.overlap_tokens != canonical_overlap:
            raise ValueError("Association overlap tokens must be sorted and unique")
        if self.age_cycles > self.memory_cycle:
            raise ValueError("Association age cannot exceed the visible memory cycle")
        if self.retrieval_score > self.effective_strength:
            raise ValueError("Association retrieval score cannot exceed its strength")
        if (
            self.source_record_kind == "projection_observation"
            and self.carries_experienced_loss
        ):
            raise ValueError(
                "Projection observations cannot claim an experienced loss"
            )
        if (
            self.predicted_recoverability is not None
            and self.source_record_kind != "projection_observation"
        ):
            raise ValueError(
                "Only projection observations can carry predicted recoverability"
            )
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"match_id"},
        )
        if self.match_id != content_id("association_match", id_payload):
            raise ValueError("match_id does not match association retrieval content")
        return self

    @classmethod
    def create(
        cls,
        *,
        association: InstinktMemoryRecord,
        memory_cycle: int,
        age_cycles: int,
        overlap_tokens: tuple[str, ...],
        effective_strength: float,
        retrieval_score: float,
    ) -> AssociationMatch:
        is_experienced = isinstance(association, InstinktAssociation)
        base = {
            "schema_version": "rei-native-association-match-v1",
            "association_id": instinkt_memory_record_id(association),
            "association_hash": association.content_hash(),
            "memory_cycle": memory_cycle,
            "age_cycles": age_cycles,
            "overlap_tokens": overlap_tokens,
            "effective_strength": effective_strength,
            "retrieval_score": retrieval_score,
            "carries_experienced_loss": (
                is_experienced and association.experienced_loss is not None
            ),
            "protected_target": association.protected_target,
        }
        if not is_experienced:
            base["source_record_kind"] = "projection_observation"
            if association.predicted_recoverability is not None:
                base["predicted_recoverability"] = (
                    association.predicted_recoverability
                )
        return cls(match_id=content_id("association_match", base), **base)


class BodyDelta(FrozenModel):
    """One ordered dimension delta in a deterministic body transition."""

    dimension: BodyDimension
    delta: UnitDelta


class InstinktSimulationConfig(FrozenArtifactModel):
    """Content-addressed numeric policy for one bounded B8 simulation."""

    schema_version: Literal["rei-native-instinkt-simulation-config-v1"] = (
        "rei-native-instinkt-simulation-config-v1"
    )
    config_id: NonEmptyId
    rollout_steps: int = Field(ge=1, le=8)
    max_options: int = Field(ge=1, le=32)
    max_abs_delta_per_step: PositiveUnit
    loss_base_weight: Score01
    loss_integrity_weight: Score01
    loss_pain_weight: Score01
    loss_tension_weight: Score01
    loss_boundary_weight: Score01
    loss_resource_weight: Score01
    loss_attachment_weight: Score01
    recovery_base_weight: Score01
    recovery_energy_weight: Score01
    recovery_escape_weight: Score01
    recovery_predictability_weight: Score01
    recovery_trust_weight: Score01
    recovery_attachment_weight: Score01
    recovery_resource_weight: Score01
    association_loss_weight: Score01
    association_recovery_penalty: Score01
    policy_recoverability_penalty: Score01
    policy_tension_penalty: Score01
    policy_uncertainty_penalty: Score01
    intensity_loss_weight: Score01
    intensity_tension_weight: Score01
    intensity_arousal_weight: Score01
    tie_epsilon: Score01
    config_hash: HashDigest

    @classmethod
    def create(cls, **overrides: object) -> InstinktSimulationConfig:
        base: dict[str, object] = {
            "schema_version": "rei-native-instinkt-simulation-config-v1",
            "rollout_steps": 3,
            "max_options": 16,
            "max_abs_delta_per_step": 0.25,
            "loss_base_weight": 0.50,
            "loss_integrity_weight": 0.15,
            "loss_pain_weight": 0.10,
            "loss_tension_weight": 0.10,
            "loss_boundary_weight": 0.05,
            "loss_resource_weight": 0.05,
            "loss_attachment_weight": 0.05,
            "recovery_base_weight": 0.50,
            "recovery_energy_weight": 0.15,
            "recovery_escape_weight": 0.10,
            "recovery_predictability_weight": 0.10,
            "recovery_trust_weight": 0.05,
            "recovery_attachment_weight": 0.05,
            "recovery_resource_weight": 0.05,
            "association_loss_weight": 0.20,
            "association_recovery_penalty": 0.20,
            "policy_recoverability_penalty": 0.25,
            "policy_tension_penalty": 0.15,
            "policy_uncertainty_penalty": 0.10,
            "intensity_loss_weight": 0.60,
            "intensity_tension_weight": 0.25,
            "intensity_arousal_weight": 0.15,
            "tie_epsilon": 1e-12,
        }
        base.update(overrides)
        config_id = content_id("instinkt_config", base)
        payload = {"config_id": config_id, **base}
        return cls(**payload, config_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        weight_groups = (
            (
                self.loss_base_weight,
                self.loss_integrity_weight,
                self.loss_pain_weight,
                self.loss_tension_weight,
                self.loss_boundary_weight,
                self.loss_resource_weight,
                self.loss_attachment_weight,
            ),
            (
                self.recovery_base_weight,
                self.recovery_energy_weight,
                self.recovery_escape_weight,
                self.recovery_predictability_weight,
                self.recovery_trust_weight,
                self.recovery_attachment_weight,
                self.recovery_resource_weight,
            ),
            (
                self.intensity_loss_weight,
                self.intensity_tension_weight,
                self.intensity_arousal_weight,
            ),
        )
        if any(
            not math.isclose(sum(group), 1.0, rel_tol=0.0, abs_tol=1e-12)
            for group in weight_groups
        ):
            raise ValueError("Loss, recovery, and intensity weights must each sum to one")
        policy_penalty_sum = (
            self.policy_recoverability_penalty
            + self.policy_tension_penalty
            + self.policy_uncertainty_penalty
        )
        if policy_penalty_sum > 0.5:
            raise ValueError(
                "Protective-policy penalties must sum to at most 0.5"
            )
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"config_id", "config_hash"},
        )
        if self.config_id != content_id("instinkt_config", id_payload):
            raise ValueError("config_id does not match simulation configuration")
        expected_hash = self.content_hash(exclude_fields=frozenset({"config_hash"}))
        if self.config_hash != expected_hash:
            raise ValueError("config_hash does not match simulation configuration")
        return self


class OptionBodyEffect(FrozenArtifactModel):
    """Typed, explicitly supplied option effect; no cue text is classified."""

    schema_version: Literal["rei-native-option-body-effect-v1"] = (
        "rei-native-option-body-effect-v1"
    )
    effect_id: NonEmptyId
    source_packet_id: NonEmptyId
    source_packet_hash: HashDigest
    option_id: NonEmptyId
    body_deltas: tuple[BodyDelta, ...]
    base_predicted_loss: Score01
    base_recoverability: Score01
    dominant_alarm: NonEmptyText
    protected_targets: tuple[NonEmptyText, ...]
    boundary_outcome: str
    trust_outcome: str
    attachment_outcome: str
    escape_outcome: str
    action_tendency: InstinktActionTendency
    minimum_safety_condition: NonEmptyText
    association_cue_tokens: tuple[NonEmptyText, ...] = ()
    triggering_evidence_ids: tuple[NonEmptyId, ...] = ()
    effect_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        packet: InstinktInputPacket,
        option_id: NonEmptyId,
        body_deltas: tuple[BodyDelta, ...],
        base_predicted_loss: Score01,
        base_recoverability: Score01,
        dominant_alarm: NonEmptyText,
        protected_targets: tuple[NonEmptyText, ...],
        boundary_outcome: str,
        trust_outcome: str,
        attachment_outcome: str,
        escape_outcome: str,
        action_tendency: InstinktActionTendency,
        minimum_safety_condition: NonEmptyText,
        association_cue_tokens: tuple[NonEmptyText, ...] = (),
        triggering_evidence_ids: tuple[NonEmptyId, ...] = (),
    ) -> OptionBodyEffect:
        delta_by_dimension = {item.dimension: item for item in body_deltas}
        if len(delta_by_dimension) != len(body_deltas):
            raise ValueError("Option body effect dimensions must be unique")
        canonical_deltas = tuple(
            delta_by_dimension[dimension]
            for dimension in BODY_DIMENSIONS
            if dimension in delta_by_dimension
        )
        base = {
            "schema_version": "rei-native-option-body-effect-v1",
            "source_packet_id": packet.packet_id,
            "source_packet_hash": packet.content_hash(),
            "option_id": option_id,
            "body_deltas": canonical_deltas,
            "base_predicted_loss": base_predicted_loss,
            "base_recoverability": base_recoverability,
            "dominant_alarm": dominant_alarm,
            "protected_targets": tuple(dict.fromkeys(protected_targets)),
            "boundary_outcome": boundary_outcome,
            "trust_outcome": trust_outcome,
            "attachment_outcome": attachment_outcome,
            "escape_outcome": escape_outcome,
            "action_tendency": action_tendency,
            "minimum_safety_condition": minimum_safety_condition,
            "association_cue_tokens": tuple(
                sorted({token.strip().casefold() for token in association_cue_tokens})
            ),
            "triggering_evidence_ids": tuple(sorted(set(triggering_evidence_ids))),
        }
        effect_id = content_id("option_effect", base)
        payload = {"effect_id": effect_id, **base}
        return cls(**payload, effect_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_effect(self) -> Self:
        dimensions = tuple(item.dimension for item in self.body_deltas)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("Option body effect dimensions must be unique")
        expected_order = tuple(
            dimension for dimension in BODY_DIMENSIONS if dimension in dimensions
        )
        if dimensions != expected_order:
            raise ValueError("Option body effects must use canonical dimension order")
        if len(set(self.protected_targets)) != len(self.protected_targets):
            raise ValueError("Option protected targets must be unique")
        canonical_tokens = tuple(
            sorted({token.strip().casefold() for token in self.association_cue_tokens})
        )
        if self.association_cue_tokens != canonical_tokens:
            raise ValueError("Association cue tokens must be normalized, sorted, and unique")
        if self.triggering_evidence_ids != tuple(
            sorted(set(self.triggering_evidence_ids))
        ):
            raise ValueError("Effect evidence IDs must be sorted and unique")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"effect_id", "effect_hash"},
        )
        if self.effect_id != content_id("option_effect", id_payload):
            raise ValueError("effect_id does not match the typed option effect")
        expected_hash = self.content_hash(exclude_fields=frozenset({"effect_hash"}))
        if self.effect_hash != expected_hash:
            raise ValueError("effect_hash does not match the typed option effect")
        return self

    def validate_against(self, packet: InstinktInputPacket) -> Self:
        if self.source_packet_id != packet.packet_id:
            raise ValueError("Typed option effect belongs to another Instinkt packet")
        if self.source_packet_hash != packet.content_hash():
            raise ValueError("Typed option effect source packet hash differs")
        if self.option_id not in packet.option_ids:
            raise ValueError("Typed option effect targets an option outside its packet")
        if not set(self.triggering_evidence_ids).issubset(packet.evidence_ids):
            raise ValueError("Typed option effect evidence escapes its packet scope")
        return self


class BodyTransition(FrozenArtifactModel):
    """Auditable transition from one virtual-body state to the next."""

    schema_version: Literal["rei-native-body-transition-v1"] = (
        "rei-native-body-transition-v1"
    )
    transition_id: NonEmptyId
    from_state: BodyState
    to_state: BodyState
    deltas: tuple[BodyDelta, ...]
    triggering_evidence_ids: tuple[NonEmptyId, ...]
    simulation_status: SimulationArtifactStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_packet_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_packet_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_effect_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_effect_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_config_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_config_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    step_index: int | None = Field(
        default=None,
        ge=1,
        le=8,
        exclude_if=lambda value: value is None,
    )
    transition_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    def content_hash(self, *, exclude_fields: frozenset[str] = frozenset()) -> str:
        """Preserve hashes of frozen B2 transition contracts.

        B8 lineage participates in every simulated artifact hash.  Legacy
        ``unverified_contract`` instances predate those optional fields, so their
        established hashes intentionally omit the B8 extension fields.
        """

        if self.simulation_status == "unverified_contract":
            exclude_fields = exclude_fields | _BODY_TRANSITION_B8_FIELDS
        return super().content_hash(exclude_fields=exclude_fields)

    @classmethod
    def create_simulated(
        cls,
        *,
        from_state: BodyState,
        to_state: BodyState,
        deltas: tuple[BodyDelta, ...],
        triggering_evidence_ids: tuple[NonEmptyId, ...],
        packet: InstinktInputPacket,
        effect: OptionBodyEffect,
        config: InstinktSimulationConfig,
        step_index: int,
    ) -> BodyTransition:
        base = {
            "schema_version": "rei-native-body-transition-v1",
            "from_state": from_state,
            "to_state": to_state,
            "deltas": deltas,
            "triggering_evidence_ids": triggering_evidence_ids,
            "simulation_status": "simulated_v1",
            "source_packet_id": packet.packet_id,
            "source_packet_hash": packet.content_hash(),
            "source_effect_id": effect.effect_id,
            "source_effect_hash": effect.effect_hash,
            "source_config_id": config.config_id,
            "source_config_hash": config.config_hash,
            "step_index": step_index,
        }
        transition_id = content_id("body_transition", base)
        payload = {"transition_id": transition_id, **base}
        return cls(**payload, transition_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_unique_delta_dimensions(self) -> "BodyTransition":
        """Prevent ambiguous duplicate updates to the same body dimension."""

        dimensions = tuple(delta.dimension for delta in self.deltas)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("deltas must contain each body dimension at most once")
        if (
            self.from_state.body_state_id == self.to_state.body_state_id
            and self.from_state != self.to_state
        ):
            raise ValueError("Different body states cannot share one stable ID")
        delta_by_dimension = {item.dimension: item.delta for item in self.deltas}
        expected_deltas = {
            dimension: getattr(self.to_state, dimension)
            - getattr(self.from_state, dimension)
            for dimension in _BODY_DIMENSIONS
            if not math.isclose(
                getattr(self.to_state, dimension),
                getattr(self.from_state, dimension),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
        }
        expected_dimension_order = tuple(
            dimension for dimension in _BODY_DIMENSIONS if dimension in expected_deltas
        )
        if dimensions != expected_dimension_order:
            raise ValueError("deltas must record every and only changed body dimension")
        for dimension, expected in expected_deltas.items():
            if not math.isclose(
                delta_by_dimension[dimension],
                expected,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError(f"delta for {dimension} does not match the state change")
        if len(set(self.triggering_evidence_ids)) != len(self.triggering_evidence_ids):
            raise ValueError("triggering_evidence_ids must be unique")
        lineage_values = (
            self.source_packet_id,
            self.source_packet_hash,
            self.source_effect_id,
            self.source_effect_hash,
            self.source_config_id,
            self.source_config_hash,
            self.step_index,
            self.transition_hash,
        )
        if self.simulation_status == "unverified_contract":
            if any(value is not None for value in lineage_values):
                raise ValueError("Unverified BodyTransition cannot claim B8 lineage")
            return self
        if any(value is None for value in lineage_values):
            raise ValueError("Simulated BodyTransition requires complete B8 lineage")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"transition_id", "transition_hash"},
        )
        if self.transition_id != content_id("body_transition", id_payload):
            raise ValueError("transition_id does not match simulated transition content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"transition_hash"}))
        if self.transition_hash != expected_hash:
            raise ValueError("transition_hash does not match simulated transition content")
        return self

    def validate_against(
        self,
        packet: InstinktInputPacket,
        scene: SceneEvent,
    ) -> Self:
        """Keep triggering evidence within the routed Instinkt packet scope."""

        packet.validate_scene(scene)
        if not set(self.triggering_evidence_ids).issubset(packet.evidence_ids):
            raise ValueError("Body transition evidence must belong to its Instinkt packet")
        return self

    def validate_simulation_lineage(
        self,
        *,
        packet: InstinktInputPacket,
        effect: OptionBodyEffect,
        config: InstinktSimulationConfig,
    ) -> Self:
        from ..instinkt.body import body_values, clamp01, create_derived_body_state

        if self.simulation_status != "simulated_v1":
            raise ValueError("BodyTransition is not a verified B8 simulation artifact")
        effect.validate_against(packet)
        if self.source_packet_id != packet.packet_id:
            raise ValueError("BodyTransition belongs to another Instinkt packet")
        if self.source_packet_hash != packet.content_hash():
            raise ValueError("BodyTransition source packet hash differs")
        if (
            self.source_effect_id != effect.effect_id
            or self.source_effect_hash != effect.effect_hash
        ):
            raise ValueError("BodyTransition typed effect lineage differs")
        if (
            self.source_config_id != config.config_id
            or self.source_config_hash != config.config_hash
        ):
            raise ValueError("BodyTransition simulation config lineage differs")
        if self.triggering_evidence_ids != effect.triggering_evidence_ids:
            raise ValueError("BodyTransition evidence differs from its typed effect")
        if self.step_index is None or self.step_index > config.rollout_steps:
            raise ValueError("BodyTransition step is outside its configured rollout")
        requested_delta = {
            item.dimension: item.delta for item in effect.body_deltas
        }
        expected_values = body_values(self.from_state)
        for dimension in BODY_DIMENSIONS:
            total_delta = requested_delta.get(dimension, 0.0)
            step_delta = max(
                -config.max_abs_delta_per_step,
                min(
                    config.max_abs_delta_per_step,
                    total_delta / config.rollout_steps,
                ),
            )
            expected_values[dimension] = clamp01(
                expected_values[dimension] + step_delta
            )
        expected_to_state = create_derived_body_state(
            previous=self.from_state,
            values=expected_values,
            effect=effect,
            config=config,
            step_index=self.step_index,
        )
        if self.to_state != expected_to_state:
            raise ValueError(
                "BodyTransition does not replay from its effect and configuration"
            )
        return self


BodyTrajectory = Annotated[tuple[BodyState, ...], Field(min_length=1)]


class InstinktOptionRollout(FrozenArtifactModel):
    """A bounded virtual-body trajectory for one explicit decision option."""

    schema_version: Literal["rei-native-instinkt-option-rollout-v1"] = (
        "rei-native-instinkt-option-rollout-v1"
    )
    rollout_id: NonEmptyId
    option_id: NonEmptyId
    trajectory: BodyTrajectory
    dominant_alarm: str
    predicted_loss: Score01
    recoverability: Score01
    protected_targets: tuple[str, ...]
    boundary_outcome: str
    trust_outcome: str
    attachment_outcome: str
    escape_outcome: str
    simulation_status: SimulationArtifactStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_packet_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_packet_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_body_state_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_body_state_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_effect_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_effect_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_config_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_config_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    transitions: tuple[BodyTransition, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    association_match_ids: tuple[NonEmptyId, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    association_matches: tuple[AssociationMatch, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    rollout_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    def content_hash(self, *, exclude_fields: frozenset[str] = frozenset()) -> str:
        """Keep canonical fixture hashes stable while hashing all B8 lineage."""

        if self.simulation_status == "unverified_contract":
            exclude_fields = exclude_fields | _OPTION_ROLLOUT_B8_FIELDS
        return super().content_hash(exclude_fields=exclude_fields)

    @classmethod
    def create_simulated(
        cls,
        *,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        effect: OptionBodyEffect,
        config: InstinktSimulationConfig,
        transitions: tuple[BodyTransition, ...],
        association_matches: tuple[AssociationMatch, ...],
        predicted_loss: Score01,
        recoverability: Score01,
    ) -> InstinktOptionRollout:
        if not transitions:
            raise ValueError("A simulated rollout requires at least one transition")
        trajectory = (source_body_state, *(item.to_state for item in transitions))
        canonical_matches = tuple(
            sorted(association_matches, key=lambda match: match.match_id)
        )
        base: dict[str, object] = {
            "schema_version": "rei-native-instinkt-option-rollout-v1",
            "option_id": effect.option_id,
            "trajectory": trajectory,
            "dominant_alarm": effect.dominant_alarm,
            "predicted_loss": predicted_loss,
            "recoverability": recoverability,
            "protected_targets": effect.protected_targets,
            "boundary_outcome": effect.boundary_outcome,
            "trust_outcome": effect.trust_outcome,
            "attachment_outcome": effect.attachment_outcome,
            "escape_outcome": effect.escape_outcome,
            "simulation_status": "simulated_v1",
            "source_packet_id": packet.packet_id,
            "source_packet_hash": packet.content_hash(),
            "source_body_state_id": source_body_state.body_state_id,
            "source_body_state_hash": source_body_state.content_hash(),
            "source_effect_id": effect.effect_id,
            "source_effect_hash": effect.effect_hash,
            "source_config_id": config.config_id,
            "source_config_hash": config.config_hash,
            "transitions": transitions,
        }
        if canonical_matches:
            base["association_match_ids"] = tuple(
                match.match_id for match in canonical_matches
            )
            base["association_matches"] = canonical_matches
        rollout_id = content_id("instinkt_rollout", base)
        payload = {"rollout_id": rollout_id, **base}
        return cls(**payload, rollout_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_stable_body_state_ids(self) -> Self:
        states_by_id: dict[str, BodyState] = {}
        for state in self.trajectory:
            existing = states_by_id.get(state.body_state_id)
            if existing is not None and existing != state:
                raise ValueError(
                    "Different trajectory states cannot share one stable BodyState ID"
                )
            states_by_id[state.body_state_id] = state
        lineage_values = (
            self.source_packet_id,
            self.source_packet_hash,
            self.source_body_state_id,
            self.source_body_state_hash,
            self.source_effect_id,
            self.source_effect_hash,
            self.source_config_id,
            self.source_config_hash,
            self.rollout_hash,
        )
        if self.simulation_status == "unverified_contract":
            if any(value is not None for value in lineage_values):
                raise ValueError("Unverified rollout cannot claim B8 lineage")
            if (
                self.transitions
                or self.association_match_ids
                or self.association_matches
            ):
                raise ValueError("Unverified rollout cannot publish B8 audit records")
            return self
        if any(value is None for value in lineage_values):
            raise ValueError("Simulated rollout requires complete B8 lineage")
        if not self.transitions or len(self.transitions) > 8:
            raise ValueError("Simulated rollout must contain one through eight transitions")
        expected_steps = tuple(range(1, len(self.transitions) + 1))
        if tuple(item.step_index for item in self.transitions) != expected_steps:
            raise ValueError("Rollout transition steps must be contiguous from one")
        expected_trajectory = (
            self.transitions[0].from_state,
            *(transition.to_state for transition in self.transitions),
        )
        if self.trajectory != expected_trajectory:
            raise ValueError("Rollout trajectory must exactly match its transitions")
        if self.source_body_state_id != self.trajectory[0].body_state_id:
            raise ValueError("Rollout source BodyState differs from its trajectory")
        for previous, transition in zip(
            self.transitions,
            self.transitions[1:],
            strict=False,
        ):
            if previous.to_state != transition.from_state:
                raise ValueError("Rollout transitions must form one continuous chain")
        if any(
            transition.source_packet_id != self.source_packet_id
            or transition.source_packet_hash != self.source_packet_hash
            or transition.source_effect_id != self.source_effect_id
            or transition.source_effect_hash != self.source_effect_hash
            or transition.source_config_id != self.source_config_id
            or transition.source_config_hash != self.source_config_hash
            for transition in self.transitions
        ):
            raise ValueError("Rollout transitions must share its complete lineage")
        if self.association_match_ids != tuple(sorted(set(self.association_match_ids))):
            raise ValueError("Rollout association matches must be sorted and unique")
        expected_match_order = tuple(
            sorted(self.association_matches, key=lambda match: match.match_id)
        )
        if self.association_matches != expected_match_order:
            raise ValueError("Rollout association records must use canonical ID order")
        if self.association_match_ids != tuple(
            match.match_id for match in self.association_matches
        ):
            raise ValueError("Rollout association IDs differ from their records")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"rollout_id", "rollout_hash"},
        )
        if self.rollout_id != content_id("instinkt_rollout", id_payload):
            raise ValueError("rollout_id does not match simulated rollout content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"rollout_hash"}))
        if self.rollout_hash != expected_hash:
            raise ValueError("rollout_hash does not match simulated rollout content")
        return self

    def validate_simulation_lineage(
        self,
        *,
        packet: InstinktInputPacket,
        source_body_state: BodyState,
        effect: OptionBodyEffect,
        config: InstinktSimulationConfig,
        association_matches: tuple[AssociationMatch, ...],
    ) -> Self:
        from ..instinkt.dynamics import (
            predicted_loss,
            projection_recoverability_prior,
            recoverability,
        )

        if self.simulation_status != "simulated_v1":
            raise ValueError("Rollout is not a verified B8 simulation artifact")
        effect.validate_against(packet)
        if self.option_id != effect.option_id:
            raise ValueError("Rollout option differs from its typed effect")
        if self.source_packet_id != packet.packet_id:
            raise ValueError("Rollout belongs to another Instinkt packet")
        if self.source_packet_hash != packet.content_hash():
            raise ValueError("Rollout source packet hash differs")
        if self.source_body_state_id != source_body_state.body_state_id:
            raise ValueError("Rollout belongs to another source BodyState")
        if self.source_body_state_hash != source_body_state.content_hash():
            raise ValueError("Rollout source BodyState hash differs")
        if self.trajectory[0] != source_body_state:
            raise ValueError("Rollout trajectory does not start from its source BodyState")
        if (
            self.source_effect_id != effect.effect_id
            or self.source_effect_hash != effect.effect_hash
        ):
            raise ValueError("Rollout typed effect lineage differs")
        if (
            self.source_config_id != config.config_id
            or self.source_config_hash != config.config_hash
        ):
            raise ValueError("Rollout simulation config lineage differs")
        if len(self.transitions) != config.rollout_steps:
            raise ValueError("Rollout transition count differs from its configuration")
        canonical_matches = tuple(
            sorted(association_matches, key=lambda match: match.match_id)
        )
        if self.association_matches != canonical_matches:
            raise ValueError("Rollout association-memory lineage differs")
        if self.association_match_ids != tuple(
            match.match_id for match in canonical_matches
        ):
            raise ValueError("Rollout association-memory IDs differ")
        for transition in self.transitions:
            transition.validate_simulation_lineage(
                packet=packet,
                effect=effect,
                config=config,
            )
        loss_memory_strength = max(
            (
                match.retrieval_score
                for match in canonical_matches
                if match.carries_experienced_loss
            ),
            default=0.0,
        )
        expected_loss = predicted_loss(
            final_state=self.trajectory[-1],
            effect=effect,
            config=config,
            loss_memory_strength=loss_memory_strength,
        )
        expected_recoverability = recoverability(
            final_state=self.trajectory[-1],
            effect=effect,
            config=config,
            loss_memory_strength=loss_memory_strength,
            projection_recovery_prior=projection_recoverability_prior(
                canonical_matches
            ),
        )
        if not math.isclose(
            self.predicted_loss,
            expected_loss,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Rollout predicted_loss does not replay")
        if not math.isclose(
            self.recoverability,
            expected_recoverability,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Rollout recoverability does not replay")
        return self


class InstinktNativeConclusion(FrozenArtifactModel):
    """Instinkt's immutable structured result, preceding verbalization."""

    schema_version: Literal["rei-native-instinkt-conclusion-v1"] = (
        "rei-native-instinkt-conclusion-v1"
    )
    conclusion_id: NonEmptyId
    source_packet_id: NonEmptyId
    source_scene_id: NonEmptyId
    source_body_state_id: NonEmptyId
    mind: Literal["I"] = "I"
    option_id: NonEmptyId | None
    dominant_alarm: str
    danger_claims: tuple[str, ...]
    protected_targets: tuple[str, ...]
    action_tendency: InstinktActionTendency
    minimum_safety_condition: str
    decisive_rollout_id: NonEmptyId | None
    decisive_rollout_option_id: NonEmptyId | None
    intensity: Score01
    abstains: bool = False
    uncertainty: str

    @model_validator(mode="after")
    def validate_option_references(self) -> "InstinktNativeConclusion":
        if self.abstains != (self.option_id is None):
            raise ValueError(
                "Instinkt must abstain exactly when no option is selected"
            )
        if (self.decisive_rollout_id is None) != (
            self.decisive_rollout_option_id is None
        ):
            raise ValueError("Decisive rollout ID and option ID must be recorded together")
        if self.option_id is None and self.decisive_rollout_id is not None:
            raise ValueError("A conclusion without an option cannot cite a decisive rollout")
        if self.option_id is not None and self.decisive_rollout_id is None:
            raise ValueError("A selected Instinkt option requires a decisive rollout")
        if (
            self.decisive_rollout_option_id is not None
            and self.option_id != self.decisive_rollout_option_id
        ):
            raise ValueError("Decisive rollout option must match the selected option")
        return self

    def validate_against(
        self,
        packet: InstinktInputPacket,
        body_state: BodyState,
        rollouts: tuple[InstinktOptionRollout, ...] = (),
    ) -> Self:
        """Bind the native result to its packet, initial body, and decisive rollout."""

        self.validate_packet(packet)
        if self.source_body_state_id != body_state.body_state_id:
            raise ValueError("Instinkt conclusion belongs to another BodyState")
        if packet.source_body_state_id != body_state.body_state_id:
            raise ValueError("Instinkt packet and conclusion must share initial BodyState")
        rollout_ids = tuple(rollout.rollout_id for rollout in rollouts)
        if len(set(rollout_ids)) != len(rollout_ids):
            raise ValueError("Instinkt rollout IDs must be unique")
        rollout_option_ids = tuple(rollout.option_id for rollout in rollouts)
        if len(set(rollout_option_ids)) != len(rollout_option_ids):
            raise ValueError("Instinkt rollouts must use each option at most once")
        if set(rollout_option_ids) != set(packet.option_ids):
            raise ValueError("Instinkt rollouts must cover every packet option")
        states_by_id = {body_state.body_state_id: body_state}
        for rollout in rollouts:
            if rollout.trajectory[0] != body_state:
                raise ValueError(
                    "Every Instinkt rollout must start from the source BodyState"
                )
            for state in rollout.trajectory:
                existing = states_by_id.get(state.body_state_id)
                if existing is not None and existing != state:
                    raise ValueError(
                        "Different states across rollouts cannot share one BodyState ID"
                    )
                states_by_id[state.body_state_id] = state
        if self.decisive_rollout_id is not None:
            rollout_by_id = {rollout.rollout_id: rollout for rollout in rollouts}
            rollout = rollout_by_id.get(self.decisive_rollout_id)
            if rollout is None or rollout.option_id != self.decisive_rollout_option_id:
                raise ValueError(
                    "Decisive Instinkt rollout must exist and match the selected option"
                )
        return self

    def validate_packet(self, packet: InstinktInputPacket) -> Self:
        """Verify packet identity, source body, scene, and option scope."""

        if self.source_packet_id != packet.packet_id:
            raise ValueError("Instinkt conclusion belongs to another input packet")
        if self.source_scene_id != packet.scene_id:
            raise ValueError("Instinkt conclusion scene differs from its packet")
        if self.source_body_state_id != packet.source_body_state_id:
            raise ValueError("Instinkt conclusion body state differs from its packet")
        if self.option_id is not None and self.option_id not in packet.option_ids:
            raise ValueError("Instinkt conclusion selected an option outside its packet")
        return self


__all__ = [
    "AssociationMatch",
    "BODY_DIMENSIONS",
    "BodyDelta",
    "BodyDimension",
    "BodyState",
    "BodyTrajectory",
    "BodyTransition",
    "EMBODIED_CUE_CLASSES",
    "EmbodiedCueClass",
    "InstinktActionTendency",
    "InstinktAssociation",
    "InstinktCueAssertionStatus",
    "InstinktCueEvidenceBinding",
    "InstinktCueEvidenceCitation",
    "INSTINKT_CUE_LANES",
    "InstinktCueLane",
    "InstinktMemoryRecord",
    "InstinktProjectionObservation",
    "InstinktProjectionObservationKind",
    "InstinktInputPacket",
    "InstinktNativeConclusion",
    "InstinktOptionRollout",
    "InstinktSimulationConfig",
    "InstinktWorld",
    "MAX_INSTINKT_ASSOCIATION_RECORDS",
    "MAX_INSTINKT_ASSOCIATION_CUES",
    "MAX_INSTINKT_ASSOCIATION_TEXT_CHARS",
    "MAX_INSTINKT_CUES_PER_LANE",
    "MAX_INSTINKT_CUE_BINDINGS",
    "MAX_INSTINKT_CITED_TEXT_CHARS",
    "MAX_INSTINKT_CUE_TEXT_CHARS",
    "MAX_INSTINKT_EVIDENCE_IDS",
    "MAX_INSTINKT_TOTAL_CUES",
    "OptionBodyEffect",
    "PositiveUnit",
    "SimulationArtifactStatus",
    "UnitDelta",
    "instinkt_association_content_id",
    "instinkt_memory_record_id",
    "instinkt_projection_memory_token",
]
