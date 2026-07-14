"""Profile-blind C5 contracts for grounded Instinkt body-effect inference.

The contracts in this module are a bounded software operationalization.  They
do not contain medical, diagnostic, physiological, character, or authority
fields.  Rule-backed predictions remain separate from the established B8 body
simulator until a validated compiler binds them to :class:`OptionBodyEffect`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
    SourceModality,
)
from .instinkt import (
    BODY_DIMENSIONS,
    EMBODIED_CUE_CLASSES,
    BodyDelta,
    BodyDimension,
    BodyState,
    EmbodiedCueClass,
    InstinktAssociation,
    InstinktCueEvidenceBinding,
    InstinktCueLane,
    InstinktActionTendency,
    InstinktInputPacket,
    InstinktWorld,
    OptionBodyEffect,
    instinkt_projection_memory_token,
)
from .scene import DecisionOption, SceneEvent


EffectPacketLane = InstinktCueLane
CanonicalSourceStatus = Literal["direct_source", "implementation_hypothesis"]
AssociationPolicy = Literal[
    "optional_with_explicit_default",
    "required",
]
AssociationBasis = Literal["matched_association", "canonical_default_rule"]
EffectSource = Literal["manual_fixture", "rule_based", "model_backed"]
OptionEffectRelation = Literal["protective", "adverse"]
EffectTermMatchStatus = Literal["absent", "positive", "negated"]
EffectOptionRelationStatus = Literal[
    "unambiguous",
    "no_match",
    "ambiguous",
    "negated",
]


_RULE_WORD_RE = re.compile(r"[^\w]+", flags=re.UNICODE)
_OPTION_CLAUSE_SPLIT_RE = re.compile(
    r"(?:[.;:!?]+|,\s+|\b(?:but|however|although|yet|vendar|ampak|toda)\b)",
    flags=re.IGNORECASE | re.UNICODE,
)
_NEGATION_TOKENS = frozenset(
    {
        "not",
        "no",
        "never",
        "without",
        "cannot",
        "ne",
        "ni",
        "nikoli",
        "brez",
    }
)
_ENGLISH_CONTRACTION_ROOTS = frozenset(
    {
        "ain",
        "aren",
        "can",
        "couldn",
        "didn",
        "doesn",
        "don",
        "hadn",
        "hasn",
        "haven",
        "isn",
        "mustn",
        "needn",
        "shan",
        "shouldn",
        "wasn",
        "weren",
        "won",
        "wouldn",
    }
)
_METALINGUISTIC_EVIDENCE_MARKERS = (
    "dictionary entry",
    "glossary entry",
    "training glossary",
    "training example",
    "is defined as",
    "definition",
    "dictionary",
    "glossary",
    "means",
    "word",
    "term",
    "učni primer",
    "slovarski vnos",
    "slovar",
    "definicija",
    "pomeni",
    "beseda",
    "izraz",
)


def _contains_negation(tokens: list[str]) -> bool:
    if any(token in _NEGATION_TOKENS for token in tokens):
        return True
    return any(
        first in _ENGLISH_CONTRACTION_ROOTS and second == "t"
        for first, second in zip(tokens, tokens[1:], strict=False)
    )


def normalize_effect_rule_text(value: str) -> str:
    return " ".join(part for part in _RULE_WORD_RE.split(value.casefold()) if part)


def is_effect_evidence_assertion(value: str) -> bool:
    """Reject definitional mentions that do not assert a scene-level event."""

    normalized = normalize_effect_rule_text(value)
    padded = f" {normalized} "
    return not any(
        f" {normalize_effect_rule_text(marker)} " in padded
        for marker in _METALINGUISTIC_EVIDENCE_MARKERS
    )


def effect_rule_term_match_status(
    value: str,
    terms: tuple[str, ...],
) -> EffectTermMatchStatus:
    normalized_value = normalize_effect_rule_text(value)
    tokens = normalized_value.split()
    contains_negation = _contains_negation(tokens)
    positive = False
    negated = False
    for raw_term in terms:
        term = raw_term.strip()
        if term.endswith("*"):
            stem = normalize_effect_rule_text(term[:-1])
            starts = tuple(
                index
                for index, token in enumerate(tokens)
                if stem and token.startswith(stem)
            )
        else:
            term_tokens = normalize_effect_rule_text(term).split()
            starts = tuple(
                index
                for index in range(len(tokens) - len(term_tokens) + 1)
                if tokens[index : index + len(term_tokens)] == term_tokens
            )
        for start in starts:
            if contains_negation:
                negated = True
            else:
                positive = True
    if negated:
        return "negated"
    return "positive" if positive else "absent"


def _option_term_match_status(
    value: str,
    terms: tuple[str, ...],
) -> EffectTermMatchStatus:
    positive = False
    negated = False
    for clause in _OPTION_CLAUSE_SPLIT_RE.split(value.casefold()):
        tokens = normalize_effect_rule_text(clause).split()
        if not tokens:
            continue
        for raw_term in terms:
            term = raw_term.strip()
            if term.endswith("*"):
                stem = normalize_effect_rule_text(term[:-1])
                starts = tuple(
                    index
                    for index, token in enumerate(tokens)
                    if stem and token.startswith(stem)
                )
            else:
                term_tokens = normalize_effect_rule_text(term).split()
                starts = tuple(
                    index
                    for index in range(len(tokens) - len(term_tokens) + 1)
                    if tokens[index : index + len(term_tokens)] == term_tokens
                )
            for start in starts:
                # A negative auxiliary may be separated from the action by adverbs
                # ("do not immediately leave", "can't safely leave", "ne takoj
                # odidi").  Restrict the scope to the current clause and fail closed.
                if _contains_negation(tokens[:start]):
                    negated = True
                else:
                    positive = True
    if negated:
        return "negated"
    return "positive" if positive else "absent"


def matches_effect_rule_terms(value: str, terms: tuple[str, ...]) -> bool:
    return effect_rule_term_match_status(value, terms) == "positive"


def classify_option_effect_relation(
    value: str,
    *,
    protective_terms: tuple[str, ...],
    adverse_terms: tuple[str, ...],
) -> tuple[OptionEffectRelation | None, EffectOptionRelationStatus]:
    protective = _option_term_match_status(value, protective_terms)
    adverse = _option_term_match_status(value, adverse_terms)
    if "negated" in {protective, adverse}:
        return None, "negated"
    if protective == "positive" and adverse == "positive":
        return None, "ambiguous"
    if protective == "positive":
        return "protective", "unambiguous"
    if adverse == "positive":
        return "adverse", "unambiguous"
    return None, "no_match"


def _canonical_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _canonical_deltas(values: tuple[BodyDelta, ...]) -> tuple[BodyDelta, ...]:
    by_dimension = {item.dimension: item for item in values}
    if len(by_dimension) != len(values):
        raise ValueError("Body-effect dimensions must be unique")
    return tuple(
        by_dimension[dimension]
        for dimension in BODY_DIMENSIONS
        if dimension in by_dimension
    )


def combine_body_effect_deltas(
    evidence: tuple[BodyEffectEvidence, ...],
) -> tuple[BodyDelta, ...]:
    """Combine independent cue deltas without reducing them to one risk score."""

    totals: dict[BodyDimension, float] = {}
    for item in evidence:
        for delta in item.predicted_deltas:
            totals[delta.dimension] = totals.get(delta.dimension, 0.0) + delta.delta
    combined: list[BodyDelta] = []
    for dimension in BODY_DIMENSIONS:
        if dimension not in totals:
            continue
        value = max(-1.0, min(1.0, totals[dimension]))
        if math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1e-12):
            continue
        combined.append(BodyDelta(dimension=dimension, delta=value))
    return tuple(combined)


class CueConflictPair(FrozenModel):
    first: EmbodiedCueClass
    second: EmbodiedCueClass

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        first_index = EMBODIED_CUE_CLASSES.index(self.first)
        second_index = EMBODIED_CUE_CLASSES.index(self.second)
        if first_index >= second_index:
            raise ValueError("Cue conflict pairs must use canonical cue order")
        return self


class EmbodiedCueRule(FrozenModel):
    """One transparent cue-to-body-effect rule loaded from canonical config."""

    rule_id: NonEmptyId
    cue_class: EmbodiedCueClass
    source_status: CanonicalSourceStatus
    source_claim_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    packet_lanes: tuple[EffectPacketLane, ...] = Field(min_length=1)
    supported_evidence_modalities: tuple[SourceModality, ...] = Field(min_length=1)
    allowed_body_dimensions: tuple[BodyDimension, ...] = Field(min_length=1)
    candidate_terms: tuple[NonEmptyText, ...] = Field(min_length=1)
    protective_option_terms: tuple[NonEmptyText, ...] = Field(min_length=1)
    adverse_option_terms: tuple[NonEmptyText, ...] = Field(min_length=1)
    protective_deltas: tuple[BodyDelta, ...] = Field(min_length=1)
    adverse_deltas: tuple[BodyDelta, ...] = Field(min_length=1)
    association_policy: AssociationPolicy
    confidence: Score01
    uncertainty_rule: NonEmptyText
    base_predicted_loss: Score01
    base_recoverability: Score01
    dominant_alarm: NonEmptyText
    protected_target: NonEmptyText
    action_tendency: InstinktActionTendency
    minimum_safety_condition: NonEmptyText

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        for field_name in (
            "source_claim_ids",
            "packet_lanes",
            "supported_evidence_modalities",
            "candidate_terms",
            "protective_option_terms",
            "adverse_option_terms",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        for field_name in (
            "candidate_terms",
            "protective_option_terms",
            "adverse_option_terms",
        ):
            for term in getattr(self, field_name):
                if "*" not in term:
                    continue
                stem = term[:-1].strip()
                if (
                    term.count("*") != 1
                    or not term.endswith("*")
                    or len(stem) < 3
                    or any(character.isspace() for character in stem)
                ):
                    raise ValueError(
                        f"{field_name} prefix terms must be one three-character "
                        "or longer token ending in '*'"
                    )
        allowed = tuple(dict.fromkeys(self.allowed_body_dimensions))
        if allowed != self.allowed_body_dimensions:
            raise ValueError("allowed_body_dimensions must be unique")
        allowed_set = set(allowed)
        for field_name in ("protective_deltas", "adverse_deltas"):
            deltas = getattr(self, field_name)
            if deltas != _canonical_deltas(deltas):
                raise ValueError(f"{field_name} must use canonical dimension order")
            if not {item.dimension for item in deltas}.issubset(allowed_set):
                raise ValueError(f"{field_name} contains a disallowed body dimension")
            if any(
                math.isclose(item.delta, 0.0, rel_tol=0.0, abs_tol=1e-12)
                for item in deltas
            ):
                raise ValueError(f"{field_name} cannot contain silent zero deltas")
        return self


class InstinktEffectRuleSet(FrozenArtifactModel):
    """Complete, content-addressed configuration for all initial cue classes."""

    schema_version: Literal["rei-native-instinkt-effect-rules-v1"] = (
        "rei-native-instinkt-effect-rules-v1"
    )
    ruleset_id: NonEmptyId
    revision: NonEmptyText
    canonical_source_status: Literal["implementation_hypothesis"] = (
        "implementation_hypothesis"
    )
    minimum_association_score: Score01
    rules: tuple[EmbodiedCueRule, ...]
    conflict_pairs: tuple[CueConflictPair, ...] = ()
    ruleset_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        revision: NonEmptyText,
        minimum_association_score: Score01,
        rules: tuple[EmbodiedCueRule, ...],
        conflict_pairs: tuple[CueConflictPair, ...] = (),
    ) -> InstinktEffectRuleSet:
        base = {
            "schema_version": "rei-native-instinkt-effect-rules-v1",
            "revision": revision,
            "canonical_source_status": "implementation_hypothesis",
            "minimum_association_score": minimum_association_score,
            "rules": rules,
            "conflict_pairs": conflict_pairs,
        }
        ruleset_id = content_id("instinkt_effect_rules", base)
        payload = {"ruleset_id": ruleset_id, **base}
        return cls(**payload, ruleset_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_ruleset(self) -> Self:
        cue_classes = tuple(item.cue_class for item in self.rules)
        if cue_classes != EMBODIED_CUE_CLASSES:
            raise ValueError("Rule set must contain all 16 cue classes in canonical order")
        rule_ids = tuple(item.rule_id for item in self.rules)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("Rule IDs must be unique")
        pair_values = tuple((item.first, item.second) for item in self.conflict_pairs)
        if len(set(pair_values)) != len(pair_values):
            raise ValueError("Cue conflict pairs must be unique")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"ruleset_id", "ruleset_hash"},
        )
        if self.ruleset_id != content_id("instinkt_effect_rules", id_payload):
            raise ValueError("ruleset_id differs from canonical rule-set content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"ruleset_hash"}))
        if self.ruleset_hash != expected_hash:
            raise ValueError("ruleset_hash differs from canonical rule-set content")
        return self

    @property
    def by_cue_class(self) -> Mapping[EmbodiedCueClass, EmbodiedCueRule]:
        return {item.cue_class: item for item in self.rules}

    @property
    def by_rule_id(self) -> Mapping[str, EmbodiedCueRule]:
        return {item.rule_id: item for item in self.rules}


_LOSS_CONTEXT_CUES: frozenset[EmbodiedCueClass] = frozenset(
    {
        "physical_threat",
        "pain_or_injury",
        "betrayal",
        "abandonment",
        "scarcity",
        "protected_other",
    }
)
_LOSS_CLASS_TERMS: Mapping[EmbodiedCueClass, tuple[str, ...]] = {
    "physical_threat": (
        "threat",
        "harm",
        "injury",
        "grožnja",
        "škoda",
        "poškodba",
    ),
    "pain_or_injury": ("pain", "injury", "bolečina", "poškodba"),
    "betrayal": (
        "trust",
        "betrayal",
        "zaupanje",
        "zaupanja",
        "izdaja",
        "prevara",
    ),
    "abandonment": (
        "attachment",
        "separation",
        "navezanost",
        "ločitev",
        "zapuščenost",
    ),
    "scarcity": (
        "resource",
        "money",
        "scarcity",
        "vir",
        "denar",
        "pomanjkanje",
    ),
    "protected_other": ("other", "child", "dependent", "oseba", "otrok"),
}


def _token_similarity(first: str, second: str) -> float:
    first_tokens = set(normalize_effect_rule_text(first).split())
    second_tokens = set(normalize_effect_rule_text(second).split())
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def _cue_signature_score(
    association: InstinktAssociation,
    *,
    rule: EmbodiedCueRule,
    typed_cues: tuple[str, ...],
) -> float:
    if rule.cue_class in association.cue_classes:
        return 1.0
    query = (*typed_cues, rule.cue_class, *rule.candidate_terms)
    return max(
        (
            _token_similarity(signature, candidate)
            for signature in association.cue_signature
            for candidate in query
        ),
        default=0.0,
    )


def _body_state_similarity(first: BodyState, second: BodyState) -> float:
    return sum(
        1.0 - abs(getattr(first, dimension) - getattr(second, dimension))
        for dimension in BODY_DIMENSIONS
    ) / len(BODY_DIMENSIONS)


def _delta_alignment(
    predicted_deltas: tuple[BodyDelta, ...],
    dimension: str,
    recorded_delta: float,
) -> float:
    predicted = next(
        (item.delta for item in predicted_deltas if item.dimension == dimension),
        None,
    )
    if predicted is None:
        return 0.0
    if recorded_delta == 0.0:
        return 0.5
    return 1.0 if (predicted > 0.0) == (recorded_delta > 0.0) else 0.0


def _loss_context_score(
    association: InstinktAssociation,
    rule: EmbodiedCueRule,
) -> float:
    if rule.cue_class in association.loss_classes:
        return 1.0
    typed_loss_classes = set(
        re.findall(
            r"(?<![a-z0-9_])loss_class:([a-z][a-z0-9_]*)(?![a-z0-9_])",
            (association.experienced_loss or "").casefold(),
        )
    )
    if typed_loss_classes:
        return 1.0 if rule.cue_class in typed_loss_classes else 0.0
    if (
        rule.cue_class not in _LOSS_CONTEXT_CUES
        or association.experienced_loss is None
    ):
        return 0.0
    terms = _LOSS_CLASS_TERMS[rule.cue_class]
    if matches_effect_rule_terms(association.experienced_loss, terms):
        return 1.0
    return max(
        (_token_similarity(association.experienced_loss, term) for term in terms),
        default=0.0,
    )


def _association_score_values(
    *,
    association: InstinktAssociation,
    body: BodyState,
    rule: EmbodiedCueRule,
    typed_cues: tuple[str, ...],
    predicted_deltas: tuple[BodyDelta, ...],
) -> dict[str, float]:
    cue_score = _cue_signature_score(
        association,
        rule=rule,
        typed_cues=typed_cues,
    )
    return {
        "cue_signature_score": cue_score,
        "protected_target_score": _token_similarity(
            association.protected_target,
            rule.protected_target,
        ),
        "body_state_similarity": _body_state_similarity(
            body,
            association.body_state_before,
        ),
        "loss_context_score": _loss_context_score(association, rule),
        "trust_context_score": _delta_alignment(
            predicted_deltas,
            "trust",
            association.trust_delta,
        ),
        "boundary_context_score": _delta_alignment(
            predicted_deltas,
            "boundary_integrity",
            association.boundary_delta,
        ),
    }


class BodyEffectAssociationMatch(FrozenArtifactModel):
    """Auditable score breakdown for one scoped associative-memory match."""

    schema_version: Literal["rei-native-body-effect-association-match-v1"] = (
        "rei-native-body-effect-association-match-v1"
    )
    match_id: NonEmptyId
    association_id: NonEmptyId
    association_hash: HashDigest
    source_body_state_id: NonEmptyId
    source_body_state_hash: HashDigest
    rule_id: NonEmptyId
    cue_class: EmbodiedCueClass
    cue_signature_score: Score01
    protected_target_score: Score01
    body_state_similarity: Score01
    loss_context_score: Score01
    trust_context_score: Score01
    boundary_context_score: Score01
    retrieval_score: Score01
    match_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        association: InstinktAssociation,
        body: BodyState,
        rule: EmbodiedCueRule,
        typed_cues: tuple[str, ...],
        predicted_deltas: tuple[BodyDelta, ...],
    ) -> BodyEffectAssociationMatch:
        scores = _association_score_values(
            association=association,
            body=body,
            rule=rule,
            typed_cues=typed_cues,
            predicted_deltas=predicted_deltas,
        )
        retrieval_score = round(
            0.35 * scores["cue_signature_score"]
            + 0.15 * scores["protected_target_score"]
            + 0.20 * scores["body_state_similarity"]
            + 0.10 * scores["loss_context_score"]
            + 0.10 * scores["trust_context_score"]
            + 0.10 * scores["boundary_context_score"],
            12,
        )
        base = {
            "schema_version": "rei-native-body-effect-association-match-v1",
            "association_id": association.association_id,
            "association_hash": association.content_hash(),
            "source_body_state_id": body.body_state_id,
            "source_body_state_hash": body.content_hash(),
            "rule_id": rule.rule_id,
            "cue_class": rule.cue_class,
            **scores,
            "retrieval_score": retrieval_score,
        }
        match_id = content_id("body_effect_association_match", base)
        payload = {"match_id": match_id, **base}
        return cls(**payload, match_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_match(self) -> Self:
        expected_score = round(
            0.35 * self.cue_signature_score
            + 0.15 * self.protected_target_score
            + 0.20 * self.body_state_similarity
            + 0.10 * self.loss_context_score
            + 0.10 * self.trust_context_score
            + 0.10 * self.boundary_context_score,
            12,
        )
        if not math.isclose(
            self.retrieval_score, expected_score, rel_tol=0.0, abs_tol=1e-12
        ):
            raise ValueError("Association retrieval score differs from its components")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"match_id", "match_hash"},
        )
        if self.match_id != content_id("body_effect_association_match", id_payload):
            raise ValueError("match_id differs from canonical association-match content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"match_hash"}))
        if self.match_hash != expected_hash:
            raise ValueError("match_hash differs from canonical association-match content")
        return self

    def validate_against(
        self,
        *,
        association: InstinktAssociation,
        body: BodyState,
        rule: EmbodiedCueRule,
        typed_cues: tuple[str, ...],
        predicted_deltas: tuple[BodyDelta, ...],
    ) -> Self:
        expected = type(self).create(
            association=association,
            body=body,
            rule=rule,
            typed_cues=typed_cues,
            predicted_deltas=predicted_deltas,
        )
        if self != expected:
            raise ValueError(
                "Association match differs from request-scoped deterministic replay"
            )
        return self


class BodyEffectEvidence(FrozenArtifactModel):
    """One content-addressed, source-grounded cue-effect assertion."""

    schema_version: Literal["rei-native-body-effect-evidence-v1"] = (
        "rei-native-body-effect-evidence-v1"
    )
    evidence_id: NonEmptyId
    rule_id: NonEmptyId
    cue_class: EmbodiedCueClass
    cue_binding_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    source_evidence_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    association_ids: tuple[NonEmptyId, ...] = ()
    association_matches: tuple[BodyEffectAssociationMatch, ...] = ()
    association_basis: AssociationBasis
    option_relation: OptionEffectRelation
    predicted_deltas: tuple[BodyDelta, ...] = Field(min_length=1)
    confidence: Score01
    uncertainty: NonEmptyText
    evidence_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        rule_id: NonEmptyId,
        cue_class: EmbodiedCueClass,
        cue_binding_ids: tuple[NonEmptyId, ...],
        source_evidence_ids: tuple[NonEmptyId, ...],
        association_ids: tuple[NonEmptyId, ...],
        association_matches: tuple[BodyEffectAssociationMatch, ...] = (),
        association_basis: AssociationBasis,
        option_relation: OptionEffectRelation,
        predicted_deltas: tuple[BodyDelta, ...],
        confidence: Score01,
        uncertainty: NonEmptyText,
    ) -> BodyEffectEvidence:
        canonical_matches = tuple(
            sorted(association_matches, key=lambda item: item.match_id)
        )
        base = {
            "schema_version": "rei-native-body-effect-evidence-v1",
            "rule_id": rule_id,
            "cue_class": cue_class,
            "cue_binding_ids": _canonical_ids(cue_binding_ids),
            "source_evidence_ids": _canonical_ids(source_evidence_ids),
            "association_ids": _canonical_ids(
                (*association_ids, *(item.association_id for item in canonical_matches))
            ),
            "association_matches": canonical_matches,
            "association_basis": association_basis,
            "option_relation": option_relation,
            "predicted_deltas": _canonical_deltas(predicted_deltas),
            "confidence": confidence,
            "uncertainty": uncertainty,
        }
        evidence_id = content_id("body_effect_evidence", base)
        payload = {"evidence_id": evidence_id, **base}
        return cls(**payload, evidence_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.cue_binding_ids != _canonical_ids(self.cue_binding_ids):
            raise ValueError("cue_binding_ids must be sorted and unique")
        if self.source_evidence_ids != _canonical_ids(self.source_evidence_ids):
            raise ValueError("source_evidence_ids must be sorted and unique")
        if self.association_ids != _canonical_ids(self.association_ids):
            raise ValueError("association_ids must be sorted and unique")
        if self.association_matches != tuple(
            sorted(self.association_matches, key=lambda item: item.match_id)
        ):
            raise ValueError("association_matches must use canonical match-ID order")
        match_ids = tuple(item.match_id for item in self.association_matches)
        if len(set(match_ids)) != len(match_ids):
            raise ValueError("association_matches must contain unique match IDs")
        if not {
            item.association_id for item in self.association_matches
        }.issubset(self.association_ids):
            raise ValueError("Association match records differ from association IDs")
        if self.predicted_deltas != _canonical_deltas(self.predicted_deltas):
            raise ValueError("predicted_deltas must use canonical dimension order")
        if self.association_basis == "matched_association" and not self.association_ids:
            raise ValueError("Matched association evidence requires association IDs")
        if (
            self.association_basis == "canonical_default_rule"
            and self.association_ids
        ):
            raise ValueError("Default-rule evidence cannot claim association matches")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"evidence_id", "evidence_hash"},
        )
        if self.evidence_id != content_id("body_effect_evidence", id_payload):
            raise ValueError("evidence_id differs from canonical evidence content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"evidence_hash"}))
        if self.evidence_hash != expected_hash:
            raise ValueError("evidence_hash differs from canonical evidence content")
        return self


class OptionBodyEffectPrediction(FrozenArtifactModel):
    """Auditable body-effect prediction for one option, including abstention."""

    schema_version: Literal["rei-native-option-body-effect-prediction-v1"] = (
        "rei-native-option-body-effect-prediction-v1"
    )
    prediction_id: NonEmptyId
    option_id: NonEmptyId
    effect_source: EffectSource
    source_scene_id: NonEmptyId
    source_scene_hash: HashDigest
    source_packet_id: NonEmptyId
    source_packet_hash: HashDigest
    source_world_id: NonEmptyId
    source_world_hash: HashDigest
    source_body_state_id: NonEmptyId
    source_body_state_hash: HashDigest
    ruleset_id: NonEmptyId
    ruleset_hash: HashDigest
    mapper_id: NonEmptyId
    mapper_revision: NonEmptyText
    evidence: tuple[BodyEffectEvidence, ...]
    combined_deltas: tuple[BodyDelta, ...]
    unsupported_dimensions: tuple[BodyDimension, ...]
    conflict_flags: tuple[NonEmptyText, ...]
    abstains: bool
    uncertainty: NonEmptyText
    prediction_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        option: DecisionOption,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        world: InstinktWorld,
        body: BodyState,
        ruleset: InstinktEffectRuleSet,
        mapper_id: NonEmptyId,
        mapper_revision: NonEmptyText,
        evidence: tuple[BodyEffectEvidence, ...],
        unsupported_dimensions: tuple[BodyDimension, ...] = (),
        conflict_flags: tuple[NonEmptyText, ...] = (),
        abstains: bool,
        uncertainty: NonEmptyText,
        effect_source: EffectSource = "rule_based",
    ) -> OptionBodyEffectPrediction:
        canonical_evidence = tuple(sorted(evidence, key=lambda item: item.evidence_id))
        base = {
            "schema_version": "rei-native-option-body-effect-prediction-v1",
            "option_id": option.option_id,
            "effect_source": effect_source,
            "source_scene_id": scene.event_id,
            "source_scene_hash": scene.scene_hash(),
            "source_packet_id": packet.packet_id,
            "source_packet_hash": packet.content_hash(),
            "source_world_id": world.world_id,
            "source_world_hash": world.content_hash(),
            "source_body_state_id": body.body_state_id,
            "source_body_state_hash": body.content_hash(),
            "ruleset_id": ruleset.ruleset_id,
            "ruleset_hash": ruleset.ruleset_hash,
            "mapper_id": mapper_id,
            "mapper_revision": mapper_revision,
            "evidence": canonical_evidence,
            "combined_deltas": combine_body_effect_deltas(canonical_evidence),
            "unsupported_dimensions": tuple(
                dimension
                for dimension in BODY_DIMENSIONS
                if dimension in set(unsupported_dimensions)
            ),
            "conflict_flags": tuple(sorted(set(conflict_flags))),
            "abstains": abstains,
            "uncertainty": uncertainty,
        }
        prediction_id = content_id("body_effect_prediction", base)
        payload = {"prediction_id": prediction_id, **base}
        return cls(**payload, prediction_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_prediction(self) -> Self:
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        if evidence_ids != tuple(sorted(set(evidence_ids))):
            raise ValueError("Prediction evidence must use unique canonical ID order")
        if self.combined_deltas != combine_body_effect_deltas(self.evidence):
            raise ValueError("combined_deltas differ from cited evidence")
        expected_unsupported = tuple(
            dimension
            for dimension in BODY_DIMENSIONS
            if dimension in set(self.unsupported_dimensions)
        )
        if self.unsupported_dimensions != expected_unsupported:
            raise ValueError("unsupported_dimensions must use canonical unique order")
        if self.conflict_flags != tuple(sorted(set(self.conflict_flags))):
            raise ValueError("conflict_flags must be sorted and unique")
        if self.abstains:
            if self.combined_deltas:
                raise ValueError("An abstaining prediction cannot emit combined deltas")
            if self.evidence and not self.conflict_flags:
                raise ValueError(
                    "Abstention with effect evidence requires an explicit conflict flag"
                )
        elif not self.evidence or not self.combined_deltas:
            raise ValueError("A non-abstaining prediction requires evidence and deltas")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"prediction_id", "prediction_hash"},
        )
        if self.prediction_id != content_id("body_effect_prediction", id_payload):
            raise ValueError("prediction_id differs from canonical prediction content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"prediction_hash"}))
        if self.prediction_hash != expected_hash:
            raise ValueError("prediction_hash differs from canonical prediction content")
        return self

    def validate_against(
        self,
        *,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        world: InstinktWorld,
        body: BodyState,
        option: DecisionOption,
        ruleset: InstinktEffectRuleSet,
        association_records: tuple[InstinktAssociation, ...] = (),
    ) -> Self:
        packet.validate_against(scene, body)
        scene_option = next(
            (item for item in scene.options if item.option_id == option.option_id),
            None,
        )
        if scene_option is None or scene_option != option:
            raise ValueError("Prediction option does not belong to the trusted scene")
        expected = (
            self.source_scene_id == scene.event_id,
            self.source_scene_hash == scene.scene_hash(),
            self.source_packet_id == packet.packet_id,
            self.source_packet_hash == packet.content_hash(),
            self.source_world_id == world.world_id,
            self.source_world_hash == world.content_hash(),
            self.source_body_state_id == body.body_state_id,
            self.source_body_state_hash == body.content_hash(),
            self.option_id == option.option_id,
            self.ruleset_id == ruleset.ruleset_id,
            self.ruleset_hash == ruleset.ruleset_hash,
        )
        if not all(expected):
            raise ValueError("Prediction source lineage differs from trusted inputs")
        scene_evidence = {item.evidence_id: item for item in scene.evidence}
        packet_evidence = set(packet.evidence_ids)
        packet_bindings = {
            item.binding_id: item for item in packet.cue_evidence_bindings
        }
        world_associations = set(world.associations)
        association_by_id = {
            item.association_id: item for item in association_records
        }
        if len(association_by_id) != len(association_records):
            raise ValueError("Association replay records must have unique IDs")
        rules = ruleset.by_rule_id
        option_text = f"{option.label}. {option.description}"
        for item in self.evidence:
            rule = rules.get(item.rule_id)
            if rule is None or rule.cue_class != item.cue_class:
                raise ValueError("Prediction evidence cites another effect rule")
            try:
                bindings = tuple(
                    packet_bindings[binding_id]
                    for binding_id in item.cue_binding_ids
                )
            except KeyError as exc:
                raise ValueError(
                    "Prediction evidence cites an unknown cue binding"
                ) from exc
            if any(
                binding.lane not in rule.packet_lanes
                or binding.cue_class != rule.cue_class
                or binding.assertion_status != "asserted_positive"
                for binding in bindings
            ):
                raise ValueError(
                    "Prediction cue binding lacks an asserted typed effect rule"
                )
            expected_source_ids = tuple(
                sorted(
                    {
                        evidence_id
                        for binding in bindings
                        for evidence_id in binding.evidence_ids
                    }
                )
            )
            if item.source_evidence_ids != expected_source_ids:
                raise ValueError(
                    "Prediction evidence differs from its cue-binding provenance"
                )
            if not set(item.source_evidence_ids).issubset(packet_evidence):
                raise ValueError("Prediction evidence is outside packet scope")
            for evidence_id in item.source_evidence_ids:
                source = scene_evidence.get(evidence_id)
                if (
                    source is None
                    or not source.grounded
                    or source.provenance_kind != "supplied"
                ):
                    raise ValueError(
                        "Prediction effects require supplied grounded scene evidence"
                    )
                if source.modality not in rule.supported_evidence_modalities:
                    raise ValueError("Prediction evidence uses an unsupported modality")
                for binding in bindings:
                    for citation in binding.citations:
                        if citation.evidence_id == evidence_id:
                            citation.validate_against(source)
            expected_relation, relation_status = classify_option_effect_relation(
                option_text,
                protective_terms=rule.protective_option_terms,
                adverse_terms=rule.adverse_option_terms,
            )
            if relation_status != "unambiguous" or expected_relation is None:
                raise ValueError(
                    "Prediction rule requires one unambiguous option relation"
                )
            if item.option_relation != expected_relation:
                raise ValueError("Prediction option relation differs from its rule")
            expected_deltas = (
                rule.protective_deltas
                if expected_relation == "protective"
                else rule.adverse_deltas
            )
            if item.predicted_deltas != expected_deltas:
                raise ValueError("Prediction deltas differ from the cited effect rule")
            expected_confidence = min(
                rule.confidence,
                *(scene_evidence[value].confidence for value in expected_source_ids),
            )
            if not math.isclose(
                item.confidence,
                expected_confidence,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("Prediction confidence differs from cited evidence")
            if item.uncertainty != rule.uncertainty_rule:
                raise ValueError("Prediction uncertainty differs from its effect rule")
            if not set(item.association_ids).issubset(world_associations):
                raise ValueError("Prediction association is outside InstinktWorld")
            typed_cues = tuple(binding.cue for binding in bindings)
            expected_matches = tuple(
                sorted(
                    (
                        match
                        for association_id, association in sorted(
                            association_by_id.items()
                        )
                        if association_id in world_associations
                        and (
                            match := BodyEffectAssociationMatch.create(
                                association=association,
                                body=body,
                                rule=rule,
                                typed_cues=typed_cues,
                                predicted_deltas=item.predicted_deltas,
                            )
                        ).cue_signature_score
                        > 0.0
                        and match.retrieval_score
                        >= ruleset.minimum_association_score
                    ),
                    key=lambda value: value.match_id,
                )
            )
            if item.association_matches != expected_matches:
                raise ValueError(
                    "Prediction association matches differ from canonical retrieval"
                )
            expected_association_ids = tuple(
                sorted(match.association_id for match in expected_matches)
            )
            if item.association_ids != expected_association_ids:
                raise ValueError(
                    "Prediction association IDs differ from their replay records"
                )
            expected_basis: AssociationBasis = (
                "matched_association"
                if expected_matches
                else "canonical_default_rule"
            )
            if item.association_basis != expected_basis:
                raise ValueError(
                    "Prediction association basis differs from canonical retrieval"
                )
            if (
                rule.association_policy == "required"
                and not item.association_matches
            ):
                raise ValueError("Prediction rule requires an association match")
            if not {
                delta.dimension for delta in item.predicted_deltas
            }.issubset(rule.allowed_body_dimensions):
                raise ValueError("Prediction rule emitted a disallowed body dimension")
        return self


def _compiled_outcome(
    prediction: OptionBodyEffectPrediction,
    dimension: str,
) -> str:
    delta = next(
        (
            item.delta
            for item in prediction.combined_deltas
            if item.dimension == dimension
        ),
        None,
    )
    if delta is None:
        return f"not_changed_by_cited_effect_rules:{dimension}"
    return f"predicted_delta:{dimension}:{delta:+.6f}"


def derive_compiled_option_body_effect(
    *,
    prediction: OptionBodyEffectPrediction,
    packet: InstinktInputPacket,
    ruleset: InstinktEffectRuleSet,
) -> OptionBodyEffect:
    """Replay the only C5 rule-prediction to B8-effect compilation policy."""

    if prediction.abstains or not prediction.evidence:
        raise ValueError("An abstaining prediction has no compiled body effect")
    rules = ruleset.by_rule_id
    try:
        cited_rules = tuple(rules[item.rule_id] for item in prediction.evidence)
    except KeyError as exc:
        raise ValueError("Prediction cites an unknown effect rule") from exc
    binding_by_id = {
        item.binding_id: item for item in packet.cue_evidence_bindings
    }
    try:
        cited_binding_cues = tuple(
            binding_by_id[binding_id].cue
            for evidence in prediction.evidence
            for binding_id in evidence.cue_binding_ids
        )
    except KeyError as exc:
        raise ValueError("Prediction cites an unknown packet cue binding") from exc
    weighted_rules = tuple(
        (rule, rule.base_predicted_loss * evidence.confidence)
        for rule, evidence in zip(
            cited_rules,
            prediction.evidence,
            strict=True,
        )
    )
    dominant = sorted(
        weighted_rules,
        key=lambda item: (-item[1], item[0].rule_id),
    )[0][0]
    return OptionBodyEffect.create(
        packet=packet,
        option_id=prediction.option_id,
        body_deltas=prediction.combined_deltas,
        base_predicted_loss=max(weighted_loss for _, weighted_loss in weighted_rules),
        base_recoverability=min(
            rule.base_recoverability for rule in cited_rules
        ),
        dominant_alarm=dominant.dominant_alarm,
        protected_targets=tuple(
            dict.fromkeys(rule.protected_target for rule in cited_rules)
        ),
        boundary_outcome=_compiled_outcome(
            prediction,
            "boundary_integrity",
        ),
        trust_outcome=_compiled_outcome(prediction, "trust"),
        attachment_outcome=_compiled_outcome(
            prediction,
            "attachment_security",
        ),
        escape_outcome=_compiled_outcome(
            prediction,
            "escape_availability",
        ),
        action_tendency=dominant.action_tendency,
        minimum_safety_condition=dominant.minimum_safety_condition,
        association_cue_tokens=tuple(
            {
                *(item.cue_class for item in prediction.evidence),
                *(
                    association
                    for item in prediction.evidence
                    for association in item.association_ids
                ),
                *cited_binding_cues,
                *(
                    instinkt_projection_memory_token(projection_id, projection_hash)
                    for projection_id, projection_hash in zip(
                        packet.previous_instinkt_projection_ids,
                        packet.previous_instinkt_projection_hashes,
                        strict=True,
                    )
                ),
            }
        ),
        triggering_evidence_ids=tuple(
            evidence_id
            for item in prediction.evidence
            for evidence_id in item.source_evidence_ids
        ),
    )


class OptionBodyEffectCompilation(FrozenArtifactModel):
    """Lineage wrapper around the established B8 ``OptionBodyEffect``."""

    schema_version: Literal["rei-native-option-body-effect-compilation-v1"] = (
        "rei-native-option-body-effect-compilation-v1"
    )
    compilation_id: NonEmptyId
    source_prediction_id: NonEmptyId
    source_prediction_hash: HashDigest
    ruleset_id: NonEmptyId
    ruleset_hash: HashDigest
    compiler_id: NonEmptyId
    compiler_revision: NonEmptyText
    option_body_effect: OptionBodyEffect
    compilation_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        prediction: OptionBodyEffectPrediction,
        ruleset: InstinktEffectRuleSet,
        compiler_id: NonEmptyId,
        compiler_revision: NonEmptyText,
        option_body_effect: OptionBodyEffect,
    ) -> OptionBodyEffectCompilation:
        base = {
            "schema_version": "rei-native-option-body-effect-compilation-v1",
            "source_prediction_id": prediction.prediction_id,
            "source_prediction_hash": prediction.prediction_hash,
            "ruleset_id": ruleset.ruleset_id,
            "ruleset_hash": ruleset.ruleset_hash,
            "compiler_id": compiler_id,
            "compiler_revision": compiler_revision,
            "option_body_effect": option_body_effect,
        }
        compilation_id = content_id("body_effect_compilation", base)
        payload = {"compilation_id": compilation_id, **base}
        return cls(**payload, compilation_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_compilation(self) -> Self:
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"compilation_id", "compilation_hash"},
        )
        if self.compilation_id != content_id("body_effect_compilation", id_payload):
            raise ValueError("compilation_id differs from canonical compilation content")
        expected_hash = self.content_hash(
            exclude_fields=frozenset({"compilation_hash"})
        )
        if self.compilation_hash != expected_hash:
            raise ValueError("compilation_hash differs from canonical compilation content")
        return self

    def validate_against(
        self,
        *,
        prediction: OptionBodyEffectPrediction,
        ruleset: InstinktEffectRuleSet,
        packet: InstinktInputPacket,
    ) -> Self:
        if (
            self.source_prediction_id != prediction.prediction_id
            or self.source_prediction_hash != prediction.prediction_hash
            or self.ruleset_id != ruleset.ruleset_id
            or self.ruleset_hash != ruleset.ruleset_hash
        ):
            raise ValueError("Compilation cites another prediction or rule set")
        self.option_body_effect.validate_against(packet)
        if self.option_body_effect.option_id != prediction.option_id:
            raise ValueError("Compiled effect belongs to another option")
        expected_effect = derive_compiled_option_body_effect(
            prediction=prediction,
            packet=packet,
            ruleset=ruleset,
        )
        if self.option_body_effect != expected_effect:
            raise ValueError(
                "Compiled effect differs from deterministic rule replay"
            )
        return self


__all__ = [
    "AssociationBasis",
    "AssociationPolicy",
    "BodyEffectAssociationMatch",
    "BodyEffectEvidence",
    "CanonicalSourceStatus",
    "CueConflictPair",
    "EMBODIED_CUE_CLASSES",
    "EffectPacketLane",
    "EffectSource",
    "EmbodiedCueClass",
    "EmbodiedCueRule",
    "InstinktEffectRuleSet",
    "OptionBodyEffectCompilation",
    "OptionBodyEffectPrediction",
    "combine_body_effect_deltas",
    "derive_compiled_option_body_effect",
    "is_effect_evidence_assertion",
    "matches_effect_rule_terms",
    "normalize_effect_rule_text",
]
