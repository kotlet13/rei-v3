"""Explicit three-stage motif derivation with measure-level provenance.

Exact recurrence and source-grounded canonical rules are deterministic.  An
embedding result remains only a hypothesis until a separate typed validation
artifact accepts it; similarity alone can never become canonical Ego memory.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)


MotifStage = Literal["exact", "canonical", "embedding_hypothesis"]
HypothesisDecision = Literal["accepted", "rejected"]


def _cold_revalidate(value):
    model_type = type(value)
    cold = model_type.model_validate(
        value.model_dump(mode="python", round_trip=True)
    )
    if cold != value:
        raise ValueError("Motif input changed during cold validation")
    return cold


def normalize_motif_token(value: str) -> str:
    """Apply the public lexical normalization used by stages one and two."""

    normalized = re.sub(r"[\s-]+", "_", value.strip().casefold())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        raise ValueError("Motif tokens cannot normalize to an empty value")
    return normalized


def _sorted_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _validate_identity(
    artifact: FrozenArtifactModel,
    *,
    id_field: str,
    id_prefix: str,
    hash_field: str,
) -> None:
    base = artifact.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, hash_field},
    )
    artifact_id = getattr(artifact, id_field)
    if artifact_id != content_id(id_prefix, base):
        raise ValueError(f"{id_field} differs from canonical motif content")
    payload = {id_field: artifact_id, **base}
    if getattr(artifact, hash_field) != sha256_hex(payload):
        raise ValueError(f"{hash_field} differs from canonical motif content")


class MotifObservation(FrozenModel):
    """One already-recorded motif token and the measure that exposes it."""

    motif_token: NonEmptyText
    measure_id: NonEmptyId

    @classmethod
    def create(cls, *, motif_token: str, measure_id: str) -> "MotifObservation":
        return cls(
            motif_token=normalize_motif_token(motif_token),
            measure_id=measure_id,
        )

    @model_validator(mode="after")
    def validate_normalized(self) -> Self:
        if self.motif_token != normalize_motif_token(self.motif_token):
            raise ValueError("Motif observations must use normalized tokens")
        return self


class CanonicalMotifRule(FrozenArtifactModel):
    """A reviewable alias map grounded in explicit source claims."""

    schema_version: Literal["rei-canonical-motif-rule-v1"] = (
        "rei-canonical-motif-rule-v1"
    )
    rule_id: NonEmptyId
    canonical_motif: NonEmptyText
    aliases: tuple[NonEmptyText, ...] = Field(min_length=1)
    source_claim_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    rule_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        canonical_motif: str,
        aliases: tuple[str, ...],
        source_claim_ids: tuple[str, ...],
    ) -> "CanonicalMotifRule":
        canonical = normalize_motif_token(canonical_motif)
        canonical_aliases = _sorted_unique(
            (canonical, *(normalize_motif_token(value) for value in aliases))
        )
        sources = _sorted_unique(source_claim_ids)
        base = {
            "schema_version": "rei-canonical-motif-rule-v1",
            "canonical_motif": canonical,
            "aliases": canonical_aliases,
            "source_claim_ids": sources,
        }
        rule_id = content_id("motif_rule", base)
        payload = {"rule_id": rule_id, **base}
        return cls(**payload, rule_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        if self.canonical_motif != normalize_motif_token(self.canonical_motif):
            raise ValueError("Canonical motif must use the public normalization")
        if self.aliases != _sorted_unique(self.aliases):
            raise ValueError("Canonical motif aliases must be sorted and unique")
        if self.canonical_motif not in self.aliases:
            raise ValueError("Canonical motif must be included in its aliases")
        if any(alias != normalize_motif_token(alias) for alias in self.aliases):
            raise ValueError("Canonical motif aliases must be normalized")
        if self.source_claim_ids != _sorted_unique(self.source_claim_ids):
            raise ValueError("Canonical rule source claims must be sorted and unique")
        _validate_identity(
            self,
            id_field="rule_id",
            id_prefix="motif_rule",
            hash_field="rule_hash",
        )
        return self


class EmbeddingMotifHypothesis(FrozenArtifactModel):
    """A non-canonical similarity proposal with exact embedding lineage."""

    schema_version: Literal["rei-embedding-motif-hypothesis-v1"] = (
        "rei-embedding-motif-hypothesis-v1"
    )
    hypothesis_id: NonEmptyId
    proposed_motif: NonEmptyText
    observed_tokens: tuple[NonEmptyText, ...] = Field(min_length=2)
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=2)
    embedding_artifact_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    embedding_artifact_hashes: tuple[HashDigest, ...] = Field(min_length=1)
    similarity: Score01
    hypothesis_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        proposed_motif: str,
        observed_tokens: tuple[str, ...],
        evidence_measure_ids: tuple[str, ...],
        embedding_artifact_ids: tuple[str, ...],
        embedding_artifact_hashes: tuple[str, ...],
        similarity: float,
    ) -> "EmbeddingMotifHypothesis":
        if len(embedding_artifact_ids) != len(embedding_artifact_hashes):
            raise ValueError("Embedding artifact IDs and hashes must be paired")
        embedding_artifacts = tuple(
            sorted(zip(embedding_artifact_ids, embedding_artifact_hashes, strict=True))
        )
        base = {
            "schema_version": "rei-embedding-motif-hypothesis-v1",
            "proposed_motif": normalize_motif_token(proposed_motif),
            "observed_tokens": _sorted_unique(
                tuple(normalize_motif_token(value) for value in observed_tokens)
            ),
            "evidence_measure_ids": _sorted_unique(evidence_measure_ids),
            "embedding_artifact_ids": tuple(item[0] for item in embedding_artifacts),
            "embedding_artifact_hashes": tuple(item[1] for item in embedding_artifacts),
            "similarity": similarity,
        }
        hypothesis_id = content_id("motif_hypothesis", base)
        payload = {"hypothesis_id": hypothesis_id, **base}
        return cls(**payload, hypothesis_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_hypothesis(self) -> Self:
        if self.proposed_motif != normalize_motif_token(self.proposed_motif):
            raise ValueError("Proposed motif must be normalized")
        if self.observed_tokens != _sorted_unique(self.observed_tokens):
            raise ValueError("Observed motif tokens must be sorted and unique")
        if any(
            token != normalize_motif_token(token) for token in self.observed_tokens
        ):
            raise ValueError("Observed motif tokens must be normalized")
        if self.evidence_measure_ids != _sorted_unique(self.evidence_measure_ids):
            raise ValueError("Hypothesis evidence must be sorted and unique")
        if len(self.embedding_artifact_ids) != len(
            self.embedding_artifact_hashes
        ):
            raise ValueError("Embedding artifact IDs and hashes must be paired")
        if len(set(self.embedding_artifact_ids)) != len(
            self.embedding_artifact_ids
        ):
            raise ValueError("Embedding artifact IDs must be unique")
        _validate_identity(
            self,
            id_field="hypothesis_id",
            id_prefix="motif_hypothesis",
            hash_field="hypothesis_hash",
        )
        return self


class MotifHypothesisValidation(FrozenArtifactModel):
    """An explicit typed verdict; it is never inferred from similarity."""

    schema_version: Literal["rei-motif-hypothesis-validation-v1"] = (
        "rei-motif-hypothesis-validation-v1"
    )
    validation_id: NonEmptyId
    hypothesis: EmbeddingMotifHypothesis
    validator_id: NonEmptyId
    validator_revision: NonEmptyText
    decision: HypothesisDecision
    cited_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=2)
    rationale: NonEmptyText
    validation_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        hypothesis: EmbeddingMotifHypothesis,
        validator_id: str,
        validator_revision: str,
        decision: HypothesisDecision,
        cited_measure_ids: tuple[str, ...],
        rationale: str,
    ) -> "MotifHypothesisValidation":
        base = {
            "schema_version": "rei-motif-hypothesis-validation-v1",
            "hypothesis": hypothesis,
            "validator_id": validator_id,
            "validator_revision": validator_revision,
            "decision": decision,
            "cited_measure_ids": _sorted_unique(cited_measure_ids),
            "rationale": rationale,
        }
        validation_id = content_id("motif_validation", base)
        payload = {"validation_id": validation_id, **base}
        return cls(**payload, validation_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_verdict(self) -> Self:
        if self.cited_measure_ids != self.hypothesis.evidence_measure_ids:
            raise ValueError(
                "Motif validation must cite the hypothesis evidence exactly"
            )
        _validate_identity(
            self,
            id_field="validation_id",
            id_prefix="motif_validation",
            hash_field="validation_hash",
        )
        return self


class MotifCandidate(FrozenArtifactModel):
    """One admitted motif and the complete stage-specific proof for it."""

    schema_version: Literal["rei-motif-candidate-v1"] = "rei-motif-candidate-v1"
    candidate_id: NonEmptyId
    stage: MotifStage
    canonical_motif: NonEmptyText
    observed_tokens: tuple[NonEmptyText, ...] = Field(min_length=1)
    evidence_measure_ids: tuple[NonEmptyId, ...] = Field(min_length=2)
    canonical_rule: CanonicalMotifRule | None = None
    hypothesis_validation: MotifHypothesisValidation | None = None
    candidate_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        stage: MotifStage,
        canonical_motif: str,
        observed_tokens: tuple[str, ...],
        evidence_measure_ids: tuple[str, ...],
        canonical_rule: CanonicalMotifRule | None = None,
        hypothesis_validation: MotifHypothesisValidation | None = None,
    ) -> "MotifCandidate":
        base = {
            "schema_version": "rei-motif-candidate-v1",
            "stage": stage,
            "canonical_motif": normalize_motif_token(canonical_motif),
            "observed_tokens": _sorted_unique(
                tuple(normalize_motif_token(value) for value in observed_tokens)
            ),
            "evidence_measure_ids": _sorted_unique(evidence_measure_ids),
            "canonical_rule": canonical_rule,
            "hypothesis_validation": hypothesis_validation,
        }
        candidate_id = content_id("motif_candidate", base)
        payload = {"candidate_id": candidate_id, **base}
        return cls(**payload, candidate_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if self.canonical_motif != normalize_motif_token(self.canonical_motif):
            raise ValueError("Candidate motif must be normalized")
        if self.observed_tokens != _sorted_unique(self.observed_tokens):
            raise ValueError("Candidate observations must be sorted and unique")
        if self.evidence_measure_ids != _sorted_unique(self.evidence_measure_ids):
            raise ValueError("Candidate evidence must be sorted and unique")

        if self.stage == "exact":
            if self.canonical_rule is not None or self.hypothesis_validation is not None:
                raise ValueError("Exact motifs cannot carry later-stage evidence")
            if self.observed_tokens != (self.canonical_motif,):
                raise ValueError("Exact motif observations must equal the motif")
        elif self.stage == "canonical":
            rule = self.canonical_rule
            if rule is None or self.hypothesis_validation is not None:
                raise ValueError("Canonical motifs require exactly one canonical rule")
            if self.canonical_motif != rule.canonical_motif:
                raise ValueError("Candidate motif differs from its canonical rule")
            if len(self.observed_tokens) < 2:
                raise ValueError("Canonical normalization must join distinct aliases")
            if not set(self.observed_tokens).issubset(rule.aliases):
                raise ValueError("Candidate observations fall outside the rule aliases")
        else:
            validation = self.hypothesis_validation
            if self.canonical_rule is not None or validation is None:
                raise ValueError(
                    "Embedding motifs require an explicit hypothesis validation"
                )
            if validation.decision != "accepted":
                raise ValueError("Only an accepted embedding hypothesis is admissible")
            hypothesis = validation.hypothesis
            if (
                self.canonical_motif != hypothesis.proposed_motif
                or self.observed_tokens != hypothesis.observed_tokens
                or self.evidence_measure_ids != hypothesis.evidence_measure_ids
            ):
                raise ValueError("Embedding candidate differs from its hypothesis")

        _validate_identity(
            self,
            id_field="candidate_id",
            id_prefix="motif_candidate",
            hash_field="candidate_hash",
        )
        return self


@dataclass(frozen=True, slots=True)
class ThreeStageMotifEngine:
    """Deterministic stages one/two plus an explicit stage-three gate."""

    canonical_rules: tuple[CanonicalMotifRule, ...] = ()

    def __post_init__(self) -> None:
        seen_aliases: dict[str, str] = {}
        for supplied_rule in self.canonical_rules:
            rule = _cold_revalidate(supplied_rule)
            for alias in rule.aliases:
                owner = seen_aliases.get(alias)
                if owner is not None and owner != rule.rule_id:
                    raise ValueError(
                        f"Canonical motif alias {alias!r} belongs to multiple rules"
                    )
                seen_aliases[alias] = rule.rule_id

    def derive_exact(
        self,
        observations: tuple[MotifObservation, ...],
    ) -> tuple[MotifCandidate, ...]:
        evidence_by_token: defaultdict[str, set[str]] = defaultdict(set)
        for supplied_observation in observations:
            observation = _cold_revalidate(supplied_observation)
            evidence_by_token[observation.motif_token].add(observation.measure_id)
        candidates = [
            MotifCandidate.create(
                stage="exact",
                canonical_motif=token,
                observed_tokens=(token,),
                evidence_measure_ids=tuple(sorted(measure_ids)),
            )
            for token, measure_ids in sorted(evidence_by_token.items())
            if len(measure_ids) >= 2
        ]
        return tuple(candidates)

    def derive_canonical(
        self,
        observations: tuple[MotifObservation, ...],
    ) -> tuple[MotifCandidate, ...]:
        observations = tuple(_cold_revalidate(item) for item in observations)
        candidates: list[MotifCandidate] = []
        for rule in sorted(self.canonical_rules, key=lambda value: value.rule_id):
            matched = tuple(
                observation
                for observation in observations
                if observation.motif_token in rule.aliases
            )
            tokens = tuple(sorted({item.motif_token for item in matched}))
            measure_ids = tuple(sorted({item.measure_id for item in matched}))
            if len(tokens) < 2 or len(measure_ids) < 2:
                continue
            candidates.append(
                MotifCandidate.create(
                    stage="canonical",
                    canonical_motif=rule.canonical_motif,
                    observed_tokens=tokens,
                    evidence_measure_ids=measure_ids,
                    canonical_rule=rule,
                )
            )
        return tuple(candidates)

    def derive_structured(
        self,
        observations: tuple[MotifObservation, ...],
    ) -> tuple[MotifCandidate, ...]:
        """Run only deterministic stages; embeddings are never auto-admitted."""

        return (*self.derive_exact(observations), *self.derive_canonical(observations))

    @staticmethod
    def admit_embedding_hypothesis(
        hypothesis: EmbeddingMotifHypothesis,
        validation: MotifHypothesisValidation,
    ) -> MotifCandidate:
        hypothesis = _cold_revalidate(hypothesis)
        validation = _cold_revalidate(validation)
        if validation.hypothesis != hypothesis:
            raise ValueError("Validation belongs to another embedding hypothesis")
        if validation.decision != "accepted":
            raise ValueError("Rejected embedding hypotheses cannot become motifs")
        return MotifCandidate.create(
            stage="embedding_hypothesis",
            canonical_motif=hypothesis.proposed_motif,
            observed_tokens=hypothesis.observed_tokens,
            evidence_measure_ids=hypothesis.evidence_measure_ids,
            hypothesis_validation=validation,
        )


__all__ = [
    "CanonicalMotifRule",
    "EmbeddingMotifHypothesis",
    "HypothesisDecision",
    "MotifCandidate",
    "MotifHypothesisValidation",
    "MotifObservation",
    "MotifStage",
    "ThreeStageMotifEngine",
    "normalize_motif_token",
]
