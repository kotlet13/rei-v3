"""Deterministic, model-free blind human-review workflow for C2.

The first-pass packet contains only an opaque case/subject identity, neutral
presentation text, and salted opaque references.  Canonical source material
and the grounded scene are attached only after a valid first-pass session has
been recorded.  Expected labels and evaluator-only ground truth are not fields
of this workflow.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from itertools import combinations
from threading import RLock
from typing import Literal, Self

from pydantic import Field, TypeAdapter, model_validator

from ..ids import content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    MindId,
    NonEmptyId,
    NonEmptyText,
    Score01,
)


ReviewOrdinal = Literal[1, 2, 3, 4, 5]
ReviewFacet = Literal[
    "mind",
    "route",
    "reasoning_quality",
    "translation_quality",
    "uncertainty",
]
REVIEW_FACETS: tuple[ReviewFacet, ...] = (
    "mind",
    "route",
    "reasoning_quality",
    "translation_quality",
    "uncertainty",
)
BLINDING_POLICY = "c2-first-pass-blind-review-v1"
_NON_EMPTY_ID_ADAPTER = TypeAdapter(NonEmptyId)


def _validated_id(value: str) -> str:
    return _NON_EMPTY_ID_ADAPTER.validate_python(value, strict=True)


def _canonical_ids(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    canonical = tuple(sorted(_validated_id(value) for value in values))
    if len(set(canonical)) != len(canonical):
        raise ValueError(f"{field_name} must contain unique values")
    return canonical


def _blind_reference(*, blind_case_id: str, kind: str, value: str) -> str:
    """Salt a real reference with the opaque case identity before presentation."""

    return content_id(
        "blind_ref",
        {"blind_case_id": blind_case_id, "kind": kind, "value": value},
    )


class ReviewSourceExcerpt(FrozenModel):
    locator_ref: NonEmptyId
    excerpt_summary: NonEmptyText


class ReviewMaterialCommitment(FrozenArtifactModel):
    """Trusted, content-addressed material kept outside the blind packet."""

    schema_version: Literal["rei-semantic-review-material-commitment-v1"] = (
        "rei-semantic-review-material-commitment-v1"
    )
    commitment_id: NonEmptyId
    authority_id: NonEmptyId
    source_manifest_hash: HashDigest
    case_id: NonEmptyId
    subject_id: NonEmptyId
    blind_presented_text: NonEmptyText
    language: LanguageCode
    route_ids: tuple[NonEmptyId, ...] = ()
    visible_artifact_ids: tuple[NonEmptyId, ...] = ()
    visible_observation_ids: tuple[NonEmptyId, ...] = ()
    source_excerpts: tuple[ReviewSourceExcerpt, ...] = Field(min_length=1)
    grounded_scene_text: NonEmptyText
    grounded_scene_artifact_ids: tuple[NonEmptyId, ...] = ()
    grounded_evidence_ids: tuple[NonEmptyId, ...] = ()
    material_hash: HashDigest
    evaluator_model_calls: Literal[0] = 0

    def material_payload(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "subject_id": self.subject_id,
            "source_excerpts": self.source_excerpts,
            "grounded_scene_text": self.grounded_scene_text,
            "grounded_scene_artifact_ids": self.grounded_scene_artifact_ids,
            "grounded_evidence_ids": self.grounded_evidence_ids,
        }

    @model_validator(mode="after")
    def validate_commitment(self) -> Self:
        for field_name in (
            "route_ids",
            "visible_artifact_ids",
            "visible_observation_ids",
            "grounded_scene_artifact_ids",
            "grounded_evidence_ids",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        locator_refs = tuple(item.locator_ref for item in self.source_excerpts)
        if locator_refs != tuple(sorted(set(locator_refs))):
            raise ValueError("Source excerpts must use sorted unique locator refs")
        if self.material_hash != sha256_hex(self.material_payload()):
            raise ValueError("Review material hash differs from canonical material")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"commitment_id"}
        )
        if self.commitment_id != content_id("review_material", payload):
            raise ValueError("Review material commitment ID differs from content")
        return self


class BlindReviewPacket(FrozenArtifactModel):
    """First-pass material with no canonical labels, source, or ground truth."""

    schema_version: Literal["rei-semantic-blind-review-packet-v1"] = (
        "rei-semantic-blind-review-packet-v1"
    )
    packet_id: NonEmptyId
    material_commitment_id: NonEmptyId
    blind_case_id: NonEmptyId
    blind_subject_id: NonEmptyId
    presented_text: NonEmptyText
    language: LanguageCode
    blind_route_ids: tuple[NonEmptyId, ...] = ()
    blind_artifact_ids: tuple[NonEmptyId, ...] = ()
    blind_observation_ids: tuple[NonEmptyId, ...] = ()
    blinding_policy: Literal["c2-first-pass-blind-review-v1"] = BLINDING_POLICY
    evaluator_model_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_packet(self) -> Self:
        for field_name in (
            "blind_route_ids",
            "blind_artifact_ids",
            "blind_observation_ids",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field_name} must be sorted and unique")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"packet_id"}
        )
        if self.packet_id != content_id("blind_review_packet", payload):
            raise ValueError("Blind review packet ID differs from canonical content")
        return self


class ReviewJudgment(FrozenModel):
    """One explicit human judgment; no text-derived classification is performed."""

    selected_mind: MindId
    selected_route_id: NonEmptyId | None = None
    reasoning_quality: ReviewOrdinal
    translation_quality: ReviewOrdinal
    uncertainty: ReviewOrdinal
    notes: str = ""


class BlindReviewSession(FrozenArtifactModel):
    """Immutable proof that one reviewer completed the blind first pass."""

    schema_version: Literal["rei-semantic-blind-review-session-v1"] = (
        "rei-semantic-blind-review-session-v1"
    )
    session_id: NonEmptyId
    packet: BlindReviewPacket
    reviewer_id: NonEmptyId
    first_pass: ReviewJudgment
    state: Literal["first_pass_recorded"] = "first_pass_recorded"
    evaluator_model_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_session(self) -> Self:
        selected = self.first_pass.selected_route_id
        if selected is not None and selected not in self.packet.blind_route_ids:
            raise ValueError("First-pass route is outside the blind route scope")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"session_id"}
        )
        if self.session_id != content_id("blind_review_session", payload):
            raise ValueError("Blind review session ID differs from canonical content")
        return self


class RevealedReviewContext(FrozenArtifactModel):
    """Canonical context revealed only after a first-pass session exists."""

    schema_version: Literal["rei-semantic-revealed-review-context-v1"] = (
        "rei-semantic-revealed-review-context-v1"
    )
    reveal_id: NonEmptyId
    session: BlindReviewSession
    material_commitment: ReviewMaterialCommitment
    state: Literal["context_revealed"] = "context_revealed"
    evaluator_model_calls: Literal[0] = 0

    @property
    def case_id(self) -> str:
        return self.material_commitment.case_id

    @property
    def subject_id(self) -> str:
        return self.material_commitment.subject_id

    @property
    def source_excerpts(self) -> tuple[ReviewSourceExcerpt, ...]:
        return self.material_commitment.source_excerpts

    @property
    def grounded_scene_text(self) -> str:
        return self.material_commitment.grounded_scene_text

    @property
    def grounded_scene_artifact_ids(self) -> tuple[str, ...]:
        return self.material_commitment.grounded_scene_artifact_ids

    @property
    def grounded_evidence_ids(self) -> tuple[str, ...]:
        return self.material_commitment.grounded_evidence_ids

    @property
    def material_hash(self) -> str:
        return self.material_commitment.material_hash

    @model_validator(mode="after")
    def validate_reveal(self) -> Self:
        packet = self.session.packet
        commitment = self.material_commitment
        if packet.material_commitment_id != commitment.commitment_id:
            raise ValueError(
                "Revealed material does not match the blind packet commitment"
            )
        if packet != prepare_blind_review(commitment):
            raise ValueError(
                "Blind packet differs from its trusted commitment projection"
            )
        expected_blind_case = content_id("blind_case", {"case_id": self.case_id})
        expected_blind_subject = content_id(
            "blind_subject",
            {"case_id": self.case_id, "subject_id": self.subject_id},
        )
        if (
            packet.blind_case_id != expected_blind_case
            or packet.blind_subject_id != expected_blind_subject
        ):
            raise ValueError("Revealed context does not match the blinded case/subject")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"reveal_id"}
        )
        if self.reveal_id != content_id("review_reveal", payload):
            raise ValueError(
                "Revealed review context ID differs from canonical content"
            )
        return self


class FinalReviewRecord(FrozenArtifactModel):
    """Final reviewer judgment after the canonical context was revealed."""

    schema_version: Literal["rei-semantic-final-review-record-v1"] = (
        "rei-semantic-final-review-record-v1"
    )
    final_review_id: NonEmptyId
    revealed_context: RevealedReviewContext
    reviewer_id: NonEmptyId
    final_judgment: ReviewJudgment
    judgment_changed: bool
    state: Literal["final_review_recorded"] = "final_review_recorded"
    evaluator_model_calls: Literal[0] = 0

    @property
    def blind_packet_id(self) -> str:
        return self.revealed_context.session.packet.packet_id

    @model_validator(mode="after")
    def validate_final_record(self) -> Self:
        session = self.revealed_context.session
        if self.reviewer_id != session.reviewer_id:
            raise ValueError("Final review must use the first-pass reviewer")
        selected = self.final_judgment.selected_route_id
        if selected is not None and selected not in session.packet.blind_route_ids:
            raise ValueError("Final route is outside the blind route scope")
        if self.judgment_changed != (self.final_judgment != session.first_pass):
            raise ValueError("judgment_changed must replay from first and final passes")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"final_review_id"}
        )
        if self.final_review_id != content_id("final_review", payload):
            raise ValueError("Final review ID differs from canonical content")
        return self


class ReviewCategoryFrequency(FrozenModel):
    category: NonEmptyText
    count: int = Field(gt=0)


class ReviewerFacetAgreement(FrozenModel):
    reviewer_a_id: NonEmptyId
    reviewer_b_id: NonEmptyId
    facet: ReviewFacet
    shared_blind_packet_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    exact_agreement_count: int = Field(ge=0)
    observed_agreement: Score01
    reviewer_a_frequencies: tuple[ReviewCategoryFrequency, ...]
    reviewer_b_frequencies: tuple[ReviewCategoryFrequency, ...]
    expected_agreement: Score01
    cohen_kappa: float | None = Field(default=None, ge=-1.0, le=1.0)
    kappa_defined: bool
    kappa_undefined_reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_agreement(self) -> Self:
        if self.reviewer_a_id >= self.reviewer_b_id:
            raise ValueError("Reviewer pair must use canonical ID order")
        if self.shared_blind_packet_ids != tuple(
            sorted(set(self.shared_blind_packet_ids))
        ):
            raise ValueError("Shared packet IDs must be sorted and unique")
        count = len(self.shared_blind_packet_ids)
        if self.exact_agreement_count > count:
            raise ValueError("Exact agreement count cannot exceed shared reviews")
        expected_observed = self.exact_agreement_count / count
        if not math.isclose(
            self.observed_agreement,
            expected_observed,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Observed agreement differs from its exact count")
        frequency_maps: list[dict[str, int]] = []
        for frequencies, label in (
            (self.reviewer_a_frequencies, "reviewer A"),
            (self.reviewer_b_frequencies, "reviewer B"),
        ):
            categories = tuple(item.category for item in frequencies)
            if categories != tuple(sorted(set(categories))):
                raise ValueError(f"{label} categories must be sorted and unique")
            if sum(item.count for item in frequencies) != count:
                raise ValueError(f"{label} category frequencies must cover all reviews")
            frequency_maps.append({item.category: item.count for item in frequencies})
        categories = sorted(set(frequency_maps[0]) | set(frequency_maps[1]))
        expected = math.fsum(
            (frequency_maps[0].get(category, 0) / count)
            * (frequency_maps[1].get(category, 0) / count)
            for category in categories
        )
        if not math.isclose(
            self.expected_agreement,
            expected,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Expected agreement differs from reviewer marginals")
        denominator = 1.0 - expected
        if math.isclose(denominator, 0.0, rel_tol=0.0, abs_tol=1e-12):
            if (
                self.kappa_defined
                or self.cohen_kappa is not None
                or self.kappa_undefined_reason is None
            ):
                raise ValueError("Degenerate marginals require undefined Cohen kappa")
        else:
            expected_kappa = (expected_observed - expected) / denominator
            if (
                not self.kappa_defined
                or self.cohen_kappa is None
                or self.kappa_undefined_reason is not None
                or not math.isclose(
                    self.cohen_kappa,
                    expected_kappa,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ):
                raise ValueError("Cohen kappa differs from observed reviewer marginals")
        return self


class ReviewerAgreement(FrozenArtifactModel):
    """Pairwise exact agreement and Cohen kappa over final human reviews."""

    schema_version: Literal["rei-semantic-reviewer-agreement-v1"] = (
        "rei-semantic-reviewer-agreement-v1"
    )
    agreement_id: NonEmptyId
    final_reviews: tuple[FinalReviewRecord, ...] = Field(min_length=2)
    reviewer_ids: tuple[NonEmptyId, ...] = Field(min_length=2)
    reviewed_blind_packet_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    facet_agreements: tuple[ReviewerFacetAgreement, ...] = Field(min_length=5)
    evaluator_model_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_reviewer_agreement(self) -> Self:
        canonical_reviews = tuple(
            sorted(
                self.final_reviews,
                key=lambda item: (
                    item.blind_packet_id,
                    item.reviewer_id,
                    item.final_review_id,
                ),
            )
        )
        if self.final_reviews != canonical_reviews:
            raise ValueError("Final reviews must use canonical packet/reviewer order")
        review_ids = tuple(item.final_review_id for item in self.final_reviews)
        if len(set(review_ids)) != len(review_ids):
            raise ValueError("Final review IDs must be unique")
        keys = tuple(
            (item.blind_packet_id, item.reviewer_id) for item in self.final_reviews
        )
        if len(set(keys)) != len(keys):
            raise ValueError("A reviewer may submit one final review per blind packet")
        expected_reviewers = tuple(
            sorted({item.reviewer_id for item in self.final_reviews})
        )
        if self.reviewer_ids != expected_reviewers:
            raise ValueError("Reviewer IDs differ from final review records")
        by_packet: dict[str, list[FinalReviewRecord]] = defaultdict(list)
        for review in self.final_reviews:
            by_packet[review.blind_packet_id].append(review)
        for reviews in by_packet.values():
            material_hashes = {
                item.revealed_context.material_hash for item in reviews
            }
            if len(material_hashes) != 1:
                raise ValueError(
                    "Reviewers of one packet must see identical revealed material"
                )
        expected_packets = tuple(
            sorted(
                packet_id
                for packet_id, reviews in by_packet.items()
                if len(reviews) >= 2
            )
        )
        if self.reviewed_blind_packet_ids != expected_packets:
            raise ValueError("Reviewed packet scope differs from overlapping reviews")
        expected_facets = _facet_agreements(self.final_reviews)
        if self.facet_agreements != expected_facets:
            raise ValueError("Facet agreement differs from deterministic replay")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"agreement_id"}
        )
        if self.agreement_id != content_id("reviewer_agreement", payload):
            raise ValueError("Reviewer agreement ID differs from canonical content")
        return self


def commit_review_material(
    *,
    authority_id: str,
    source_manifest_hash: str,
    case_id: str,
    subject_id: str,
    blind_presented_text: str,
    language: LanguageCode,
    route_ids: Sequence[str] = (),
    visible_artifact_ids: Sequence[str] = (),
    visible_observation_ids: Sequence[str] = (),
    source_excerpts: Sequence[tuple[str, str]],
    grounded_scene_text: str,
    grounded_scene_artifact_ids: Sequence[str] = (),
    grounded_evidence_ids: Sequence[str] = (),
) -> ReviewMaterialCommitment:
    """Commit trusted canonical material before creating its blind projection."""

    case_id = _validated_id(case_id)
    subject_id = _validated_id(subject_id)
    excerpts = tuple(
        sorted(
            (
                ReviewSourceExcerpt(
                    locator_ref=locator_ref,
                    excerpt_summary=excerpt_summary,
                )
                for locator_ref, excerpt_summary in source_excerpts
            ),
            key=lambda item: item.locator_ref,
        )
    )
    route_scope = _canonical_ids(route_ids, "route_ids")
    artifact_scope = _canonical_ids(visible_artifact_ids, "visible_artifact_ids")
    observation_scope = _canonical_ids(
        visible_observation_ids, "visible_observation_ids"
    )
    scene_artifacts = _canonical_ids(
        grounded_scene_artifact_ids, "grounded_scene_artifact_ids"
    )
    evidence_ids = _canonical_ids(grounded_evidence_ids, "grounded_evidence_ids")
    material = {
        "case_id": case_id,
        "subject_id": subject_id,
        "source_excerpts": excerpts,
        "grounded_scene_text": grounded_scene_text,
        "grounded_scene_artifact_ids": scene_artifacts,
        "grounded_evidence_ids": evidence_ids,
    }
    base = {
        "schema_version": "rei-semantic-review-material-commitment-v1",
        "authority_id": authority_id,
        "source_manifest_hash": source_manifest_hash,
        "case_id": case_id,
        "subject_id": subject_id,
        "blind_presented_text": blind_presented_text,
        "language": language,
        "route_ids": route_scope,
        "visible_artifact_ids": artifact_scope,
        "visible_observation_ids": observation_scope,
        "source_excerpts": excerpts,
        "grounded_scene_text": grounded_scene_text,
        "grounded_scene_artifact_ids": scene_artifacts,
        "grounded_evidence_ids": evidence_ids,
        "material_hash": sha256_hex(material),
        "evaluator_model_calls": 0,
    }
    return ReviewMaterialCommitment(
        commitment_id=content_id("review_material", base), **base
    )


def prepare_blind_review(
    material_commitment: ReviewMaterialCommitment,
) -> BlindReviewPacket:
    """Project a trusted commitment without serializing its canonical material."""

    case_id = material_commitment.case_id
    subject_id = material_commitment.subject_id
    blind_case_id = content_id("blind_case", {"case_id": case_id})
    blind_subject_id = content_id(
        "blind_subject", {"case_id": case_id, "subject_id": subject_id}
    )

    def blinded(kind: str, values: Sequence[str]) -> tuple[str, ...]:
        raw = _canonical_ids(values, kind)
        return tuple(
            sorted(
                _blind_reference(
                    blind_case_id=blind_case_id,
                    kind=kind,
                    value=value,
                )
                for value in raw
            )
        )

    base = {
        "schema_version": "rei-semantic-blind-review-packet-v1",
        "material_commitment_id": material_commitment.commitment_id,
        "blind_case_id": blind_case_id,
        "blind_subject_id": blind_subject_id,
        "presented_text": material_commitment.blind_presented_text,
        "language": material_commitment.language,
        "blind_route_ids": blinded("route", material_commitment.route_ids),
        "blind_artifact_ids": blinded(
            "artifact", material_commitment.visible_artifact_ids
        ),
        "blind_observation_ids": blinded(
            "observation", material_commitment.visible_observation_ids
        ),
        "blinding_policy": BLINDING_POLICY,
        "evaluator_model_calls": 0,
    }
    return BlindReviewPacket(
        packet_id=content_id("blind_review_packet", base), **base
    )


def record_first_pass(
    packet: BlindReviewPacket,
    *,
    reviewer_id: str,
    selected_mind: MindId,
    selected_route_id: str | None,
    reasoning_quality: ReviewOrdinal,
    translation_quality: ReviewOrdinal,
    uncertainty: ReviewOrdinal,
    notes: str = "",
) -> BlindReviewSession:
    """Freeze the blind choice before any canonical context is available."""

    judgment = ReviewJudgment(
        selected_mind=selected_mind,
        selected_route_id=selected_route_id,
        reasoning_quality=reasoning_quality,
        translation_quality=translation_quality,
        uncertainty=uncertainty,
        notes=notes,
    )
    base = {
        "schema_version": "rei-semantic-blind-review-session-v1",
        "packet": packet,
        "reviewer_id": reviewer_id,
        "first_pass": judgment,
        "state": "first_pass_recorded",
        "evaluator_model_calls": 0,
    }
    return BlindReviewSession(
        session_id=content_id("blind_review_session", base), **base
    )


def reveal_review_context(
    session: BlindReviewSession,
    *,
    material_commitment: ReviewMaterialCommitment,
) -> RevealedReviewContext:
    """Reveal exactly the material committed before the blind first pass."""

    if session.packet.material_commitment_id != material_commitment.commitment_id:
        raise ValueError(
            "Revealed material does not match the blind packet commitment"
        )
    base = {
        "schema_version": "rei-semantic-revealed-review-context-v1",
        "session": session,
        "material_commitment": material_commitment,
        "state": "context_revealed",
        "evaluator_model_calls": 0,
    }
    return RevealedReviewContext(
        reveal_id=content_id("review_reveal", base), **base
    )


def record_final_review(
    revealed_context: RevealedReviewContext,
    *,
    selected_mind: MindId,
    selected_route_id: str | None,
    reasoning_quality: ReviewOrdinal,
    translation_quality: ReviewOrdinal,
    uncertainty: ReviewOrdinal,
    notes: str = "",
) -> FinalReviewRecord:
    """Record a post-reveal judgment without altering the blind first pass."""

    final_judgment = ReviewJudgment(
        selected_mind=selected_mind,
        selected_route_id=selected_route_id,
        reasoning_quality=reasoning_quality,
        translation_quality=translation_quality,
        uncertainty=uncertainty,
        notes=notes,
    )
    first_pass = revealed_context.session.first_pass
    base = {
        "schema_version": "rei-semantic-final-review-record-v1",
        "revealed_context": revealed_context,
        "reviewer_id": revealed_context.session.reviewer_id,
        "final_judgment": final_judgment,
        "judgment_changed": final_judgment != first_pass,
        "state": "final_review_recorded",
        "evaluator_model_calls": 0,
    }
    return FinalReviewRecord(
        final_review_id=content_id("final_review", base), **base
    )


class BlindReviewLedger:
    """Authoritative in-memory coordinator for one-way review transitions.

    Deterministic builder functions remain useful for replay.  New review work
    should pass through this ledger so that one reviewer cannot replace a
    committed first pass, branch a reveal, or submit competing final judgments.
    """

    def __init__(
        self,
        trusted_material_commitments: Sequence[ReviewMaterialCommitment],
    ) -> None:
        commitments = tuple(trusted_material_commitments)
        commitment_ids = tuple(item.commitment_id for item in commitments)
        if len(set(commitment_ids)) != len(commitment_ids):
            raise ValueError("Trusted review material commitment IDs must be unique")
        self._trusted_material = {
            item.commitment_id: item for item in commitments
        }
        self._sessions_by_key: dict[
            tuple[str, str], BlindReviewSession
        ] = {}
        self._sessions_by_id: dict[str, BlindReviewSession] = {}
        self._reveals_by_session: dict[str, RevealedReviewContext] = {}
        self._finals_by_session: dict[str, FinalReviewRecord] = {}
        self._lock = RLock()

    def record_first_pass(
        self,
        packet: BlindReviewPacket,
        *,
        reviewer_id: str,
        selected_mind: MindId,
        selected_route_id: str | None,
        reasoning_quality: ReviewOrdinal,
        translation_quality: ReviewOrdinal,
        uncertainty: ReviewOrdinal,
        notes: str = "",
    ) -> BlindReviewSession:
        candidate = record_first_pass(
            packet,
            reviewer_id=reviewer_id,
            selected_mind=selected_mind,
            selected_route_id=selected_route_id,
            reasoning_quality=reasoning_quality,
            translation_quality=translation_quality,
            uncertainty=uncertainty,
            notes=notes,
        )
        with self._lock:
            trusted = self._trusted_material.get(packet.material_commitment_id)
            if trusted is None:
                raise ValueError(
                    "Blind packet is not bound to trusted review material"
                )
            if packet != prepare_blind_review(trusted):
                raise ValueError(
                    "Blind packet differs from its trusted commitment projection"
                )
            key = (packet.packet_id, candidate.reviewer_id)
            existing = self._sessions_by_key.get(key)
            if existing is not None:
                if existing == candidate:
                    return existing
                raise ValueError(
                    "A different first pass is already recorded for this reviewer"
                )
            self._sessions_by_key[key] = candidate
            self._sessions_by_id[candidate.session_id] = candidate
            return candidate

    def reveal_review_context(
        self,
        session: BlindReviewSession,
        *,
        material_commitment: ReviewMaterialCommitment,
    ) -> RevealedReviewContext:
        with self._lock:
            registered = self._sessions_by_id.get(session.session_id)
            if registered != session:
                raise ValueError(
                    "Blind review session is not registered in this ledger"
                )
            trusted = self._trusted_material.get(material_commitment.commitment_id)
            if trusted != material_commitment:
                raise ValueError(
                    "Review material commitment is not trusted by this ledger"
                )
            candidate = reveal_review_context(
                session,
                material_commitment=material_commitment,
            )
            existing = self._reveals_by_session.get(session.session_id)
            if existing is not None:
                if existing == candidate:
                    return existing
                raise ValueError(
                    "A different reveal is already recorded for this session"
                )
            self._reveals_by_session[session.session_id] = candidate
            return candidate

    def record_final_review(
        self,
        revealed_context: RevealedReviewContext,
        *,
        selected_mind: MindId,
        selected_route_id: str | None,
        reasoning_quality: ReviewOrdinal,
        translation_quality: ReviewOrdinal,
        uncertainty: ReviewOrdinal,
        notes: str = "",
    ) -> FinalReviewRecord:
        with self._lock:
            session_id = revealed_context.session.session_id
            registered = self._reveals_by_session.get(session_id)
            if registered != revealed_context:
                raise ValueError("Revealed context is not registered in this ledger")
            candidate = record_final_review(
                revealed_context,
                selected_mind=selected_mind,
                selected_route_id=selected_route_id,
                reasoning_quality=reasoning_quality,
                translation_quality=translation_quality,
                uncertainty=uncertainty,
                notes=notes,
            )
            existing = self._finals_by_session.get(session_id)
            if existing is not None:
                if existing == candidate:
                    return existing
                raise ValueError(
                    "A different final review is already recorded for this session"
                )
            self._finals_by_session[session_id] = candidate
            return candidate


def _category(value: object) -> str:
    return "<none>" if value is None else str(value)


def _facet_value(review: FinalReviewRecord, facet: ReviewFacet) -> object:
    judgment = review.final_judgment
    if facet == "mind":
        return judgment.selected_mind
    if facet == "route":
        return judgment.selected_route_id
    if facet == "reasoning_quality":
        return judgment.reasoning_quality
    if facet == "translation_quality":
        return judgment.translation_quality
    return judgment.uncertainty


def _frequencies(values: Sequence[object]) -> tuple[ReviewCategoryFrequency, ...]:
    counts = Counter(_category(value) for value in values)
    return tuple(
        ReviewCategoryFrequency(category=category, count=counts[category])
        for category in sorted(counts)
    )


def _facet_agreements(
    final_reviews: Sequence[FinalReviewRecord],
) -> tuple[ReviewerFacetAgreement, ...]:
    by_reviewer: dict[str, dict[str, FinalReviewRecord]] = defaultdict(dict)
    for review in final_reviews:
        by_reviewer[review.reviewer_id][review.blind_packet_id] = review

    agreements: list[ReviewerFacetAgreement] = []
    for reviewer_a, reviewer_b in combinations(sorted(by_reviewer), 2):
        shared = tuple(
            sorted(set(by_reviewer[reviewer_a]) & set(by_reviewer[reviewer_b]))
        )
        if not shared:
            continue
        for facet in REVIEW_FACETS:
            values_a = tuple(
                _facet_value(by_reviewer[reviewer_a][packet_id], facet)
                for packet_id in shared
            )
            values_b = tuple(
                _facet_value(by_reviewer[reviewer_b][packet_id], facet)
                for packet_id in shared
            )
            exact = sum(left == right for left, right in zip(values_a, values_b))
            count = len(shared)
            observed = exact / count
            frequencies_a = _frequencies(values_a)
            frequencies_b = _frequencies(values_b)
            map_a = {item.category: item.count for item in frequencies_a}
            map_b = {item.category: item.count for item in frequencies_b}
            categories = sorted(set(map_a) | set(map_b))
            expected = math.fsum(
                (map_a.get(category, 0) / count)
                * (map_b.get(category, 0) / count)
                for category in categories
            )
            denominator = 1.0 - expected
            if math.isclose(denominator, 0.0, rel_tol=0.0, abs_tol=1e-12):
                kappa = None
                kappa_defined = False
                reason = "Cohen kappa is undefined for degenerate reviewer marginals."
            else:
                kappa = max(-1.0, min(1.0, (observed - expected) / denominator))
                kappa_defined = True
                reason = None
            agreements.append(
                ReviewerFacetAgreement(
                    reviewer_a_id=reviewer_a,
                    reviewer_b_id=reviewer_b,
                    facet=facet,
                    shared_blind_packet_ids=shared,
                    exact_agreement_count=exact,
                    observed_agreement=observed,
                    reviewer_a_frequencies=frequencies_a,
                    reviewer_b_frequencies=frequencies_b,
                    expected_agreement=expected,
                    cohen_kappa=kappa,
                    kappa_defined=kappa_defined,
                    kappa_undefined_reason=reason,
                )
            )
    return tuple(agreements)


def reviewer_agreement(
    final_reviews: Sequence[FinalReviewRecord],
) -> ReviewerAgreement:
    """Compute pairwise agreement over every shared final-review packet."""

    canonical_reviews = tuple(
        sorted(
            final_reviews,
            key=lambda item: (
                item.blind_packet_id,
                item.reviewer_id,
                item.final_review_id,
            ),
        )
    )
    if len(canonical_reviews) < 2:
        raise ValueError("Reviewer agreement requires at least two final reviews")
    reviewer_ids = tuple(sorted({item.reviewer_id for item in canonical_reviews}))
    if len(reviewer_ids) < 2:
        raise ValueError("Reviewer agreement requires at least two reviewers")
    facets = _facet_agreements(canonical_reviews)
    if not facets:
        raise ValueError("Reviewers have no shared blind packet to compare")
    by_packet = Counter(item.blind_packet_id for item in canonical_reviews)
    reviewed_packets = tuple(
        sorted(packet_id for packet_id, count in by_packet.items() if count >= 2)
    )
    base = {
        "schema_version": "rei-semantic-reviewer-agreement-v1",
        "final_reviews": canonical_reviews,
        "reviewer_ids": reviewer_ids,
        "reviewed_blind_packet_ids": reviewed_packets,
        "facet_agreements": facets,
        "evaluator_model_calls": 0,
    }
    return ReviewerAgreement(
        agreement_id=content_id("reviewer_agreement", base), **base
    )


__all__ = [
    "BLINDING_POLICY",
    "BlindReviewPacket",
    "BlindReviewLedger",
    "BlindReviewSession",
    "FinalReviewRecord",
    "REVIEW_FACETS",
    "RevealedReviewContext",
    "ReviewCategoryFrequency",
    "ReviewFacet",
    "ReviewJudgment",
    "ReviewMaterialCommitment",
    "ReviewOrdinal",
    "ReviewerAgreement",
    "ReviewerFacetAgreement",
    "ReviewSourceExcerpt",
    "commit_review_material",
    "prepare_blind_review",
    "record_final_review",
    "record_first_pass",
    "reveal_review_context",
    "reviewer_agreement",
]
