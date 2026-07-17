"""Evaluator-only G1 contract for epistemic Racio interpretation v2.

Gold support aliases never enter the provider packet.  Structural validity is
the only hard pass; research dimensions stay independent and intentionally do
not collapse into one semantic score or pass boolean.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ..communication.epistemic_interpreter import (
    MotiveFamily,
    RacioEpistemicInterpretationV2,
    RacioEpistemicPacketV2,
    motive_subtype_belongs_to_family,
)
from ..communication.structured_interpreter import InterpreterActionTendency
from ..models.common import (
    FrozenModel,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
)


OptionDeterminacy = Literal["unique", "underdetermined"]
ActionSupportLevel = Literal["direct", "inferable", "unknown"]
MotiveSupportLevel = Literal[
    "unique",
    "overlapping",
    "hierarchical",
    "not_identifiable",
]
ForbiddenInference = Literal[
    "action_name_as_motive_evidence",
    "option_text_as_hidden_signal",
]
ActionAssessment = Literal[
    "supported",
    "supported_abstention",
    "unsupported",
    "missing",
]
OptionMappingAssessment = Literal[
    "mapped",
    "mapping_without_visible_support",
    "required_abstention",
    "overcommitted",
    "unnecessary_abstention",
    "mismatched",
    "missing",
]
AbstentionQuality = Literal[
    "required_and_observed",
    "missed",
    "unnecessary",
    "not_required",
    "missing",
]
MotiveAssessment = Literal[
    "supported",
    "partially_supported",
    "hierarchy_compatible",
    "unknown_preserved",
    "unsupported",
    "missing",
]


class EpistemicGoldMotiveHypothesis(FrozenModel):
    """Evaluator-only acceptable hypothesis and its required visible support."""

    family: MotiveFamily
    subtype: NonEmptyId
    supporting_observation_ids: tuple[NonEmptyId, ...]

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.subtype)

    @model_validator(mode="after")
    def validate_gold_hypothesis(self) -> Self:
        if not motive_subtype_belongs_to_family(self.family, self.subtype):
            raise ValueError("Gold motive subtype does not belong to its family")
        if not self.supporting_observation_ids:
            raise ValueError("Gold motive hypotheses require visible support IDs")
        if self.supporting_observation_ids != tuple(
            sorted(set(self.supporting_observation_ids))
        ):
            raise ValueError("Gold motive support IDs must be sorted and unique")
        return self


class EpistemicCaseGoldV2(FrozenModel):
    """Physically evaluator-only development expectations for one public case."""

    schema_version: Literal["rei-racio-epistemic-gold-v2"] = (
        "rei-racio-epistemic-gold-v2"
    )
    case_id: NonEmptyId
    bilingual_pair_id: NonEmptyId
    expected_source_mind: Literal["E", "I"]
    expected_language: LanguageCode

    option_determinacy: OptionDeterminacy
    acceptable_option_ids: tuple[NonEmptyId, ...]
    option_support_observation_ids: tuple[NonEmptyId, ...]

    expected_action_tendencies: tuple[InterpreterActionTendency, ...]
    action_support_level: ActionSupportLevel
    action_support_observation_ids: tuple[NonEmptyId, ...]

    acceptable_motive_hypotheses: tuple[EpistemicGoldMotiveHypothesis, ...]
    motive_support_level: MotiveSupportLevel

    maximum_action_confidence: Score01 | None = None
    maximum_option_confidence: Score01 | None = None
    maximum_motive_confidence: Score01 | None = None
    required_abstention: bool

    forbidden_inferences: tuple[ForbiddenInference, ...] = ()
    source_claim_ids: tuple[NonEmptyId, ...]
    native_truth_id: NonEmptyId
    profile_id: NonEmptyId
    evaluator_only_canary: NonEmptyText

    @property
    def hidden_provider_tokens(self) -> tuple[str, ...]:
        return (
            *self.source_claim_ids,
            self.native_truth_id,
            self.evaluator_only_canary,
        )

    @model_validator(mode="after")
    def validate_gold_contract(self) -> Self:
        canonical_fields = (
            "acceptable_option_ids",
            "option_support_observation_ids",
            "expected_action_tendencies",
            "action_support_observation_ids",
            "forbidden_inferences",
            "source_claim_ids",
        )
        for field_name in canonical_fields:
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"Gold {field_name} must be sorted and unique")

        if self.option_determinacy == "unique":
            if len(self.acceptable_option_ids) != 1 or self.required_abstention:
                raise ValueError(
                    "Unique option gold requires one option and no abstention"
                )
            if not self.option_support_observation_ids:
                raise ValueError("Unique option gold requires visible mapping support")
        else:
            if len(self.acceptable_option_ids) < 2 or not self.required_abstention:
                raise ValueError(
                    "Underdetermined option gold requires alternatives and abstention"
                )

        if self.action_support_level == "unknown":
            if (
                self.expected_action_tendencies != ("unknown",)
                or self.action_support_observation_ids
            ):
                raise ValueError(
                    "Unknown action gold cannot claim visible action support"
                )
        elif (
            not self.expected_action_tendencies
            or "unknown" in self.expected_action_tendencies
            or not self.action_support_observation_ids
        ):
            raise ValueError(
                "Supported action gold requires known actions and support IDs"
            )

        motive_keys = tuple(item.key for item in self.acceptable_motive_hypotheses)
        if motive_keys != tuple(sorted(set(motive_keys))):
            raise ValueError(
                "Acceptable motive hypotheses must be canonical and unique"
            )
        if self.motive_support_level == "not_identifiable":
            if self.acceptable_motive_hypotheses:
                raise ValueError("Unidentifiable motive gold cannot contain hypotheses")
        elif self.motive_support_level == "unique":
            if len(self.acceptable_motive_hypotheses) != 1:
                raise ValueError("Unique motive gold requires exactly one hypothesis")
        elif len(self.acceptable_motive_hypotheses) < 2:
            raise ValueError("Overlap or hierarchy gold requires multiple hypotheses")
        if self.motive_support_level == "hierarchical":
            motive_families = {
                hypothesis.family
                for hypothesis in self.acceptable_motive_hypotheses
            }
            if len(motive_families) != 1:
                raise ValueError(
                    "Hierarchical motive gold requires alternatives in one family"
                )

        action_support = set(self.action_support_observation_ids)
        for hypothesis in self.acceptable_motive_hypotheses:
            if not set(hypothesis.supporting_observation_ids).difference(
                action_support
            ):
                raise ValueError(
                    "Motive gold requires visible support beyond the action cue"
                )
        return self


class RacioEpistemicCaseEvaluation(FrozenModel):
    """Independent G1 dimensions; only the structural contract has a hard gate."""

    schema_version: Literal["rei-racio-epistemic-case-evaluation-v2"] = (
        "rei-racio-epistemic-case-evaluation-v2"
    )
    case_id: NonEmptyId
    bilingual_pair_id: NonEmptyId

    structural_output_valid: bool
    citation_scope_valid: bool
    hidden_truth_leakage_count: int = Field(ge=0)
    profile_leakage_count: int = Field(ge=0)
    input_packet_unchanged: bool
    hard_contract_pass: bool

    action_support: ActionAssessment
    action_citation_support: bool
    option_determinacy: OptionDeterminacy
    option_mapping: OptionMappingAssessment
    option_citation_support: bool
    abstention_quality: AbstentionQuality

    motive_support: MotiveAssessment
    motive_hypothesis_coverage: Score01
    motive_family_coverage: Score01
    unsupported_motive_overclaim_count: int = Field(ge=0)
    motive_citation_failure_count: int = Field(ge=0)

    action_confidence_within_bound: bool
    option_confidence_within_bound: bool
    motive_confidences_within_bound: bool
    research_observations: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_dimensions(self) -> Self:
        expected_hard_gate = (
            self.structural_output_valid
            and self.citation_scope_valid
            and self.hidden_truth_leakage_count == 0
            and self.profile_leakage_count == 0
            and self.input_packet_unchanged
        )
        if self.hard_contract_pass != expected_hard_gate:
            raise ValueError("Hard contract pass differs from structural dimensions")
        if self.research_observations != tuple(
            sorted(set(self.research_observations))
        ):
            raise ValueError("Research observations must be sorted and unique")
        return self


class RacioEpistemicBilingualEvaluation(FrozenModel):
    """Semantic pair comparison without requiring literal prose equality."""

    bilingual_pair_id: NonEmptyId
    source_mind_consistent: bool
    action_consistent: bool
    option_consistent: bool
    motive_family_consistent: bool
    motive_subtype_consistent: bool
    citation_consistent: bool
    ambiguity_presence_consistent: bool
    action_confidence_delta: Score01
    option_confidence_delta: Score01
    motive_confidence_delta: Score01
    action_confidence_consistent: bool
    option_confidence_consistent: bool
    motive_confidence_consistent: bool


def _validate_gold_against_packet(
    *,
    packet: RacioEpistemicPacketV2,
    gold: EpistemicCaseGoldV2,
) -> None:
    if (
        gold.expected_source_mind != packet.source_mind
        or gold.expected_language != packet.language
    ):
        raise ValueError("Epistemic gold mind or language differs from public packet")
    visible_ids = set(packet.visible_observation_ids)
    support_ids = {
        *gold.action_support_observation_ids,
        *gold.option_support_observation_ids,
        *(
            observation_id
            for hypothesis in gold.acceptable_motive_hypotheses
            for observation_id in hypothesis.supporting_observation_ids
        ),
    }
    if not support_ids.issubset(visible_ids):
        raise ValueError("Evaluator-only support aliases exceed the visible packet")
    if not set(gold.acceptable_option_ids).issubset(packet.public_option_ids):
        raise ValueError("Evaluator-only acceptable options exceed public scope")


def _within_bound(value: float, maximum: float | None) -> bool:
    return maximum is None or value <= maximum


def evaluate_racio_epistemic_case(
    *,
    packet: RacioEpistemicPacketV2,
    gold: EpistemicCaseGoldV2,
    output: RacioEpistemicInterpretationV2 | None,
    input_packet_unchanged: bool,
) -> RacioEpistemicCaseEvaluation:
    """Evaluate one output without producing an aggregate semantic pass."""

    _validate_gold_against_packet(packet=packet, gold=gold)
    encoded_packet = packet.provider_payload_bytes().decode("utf-8")
    hidden_leaks = sum(token in encoded_packet for token in gold.hidden_provider_tokens)
    profile_leaks = int(gold.profile_id in encoded_packet)

    structural_valid = output is not None
    citation_valid = False
    if output is not None:
        try:
            output.validate_against(packet)
        except ValueError:
            citation_valid = False
        else:
            citation_valid = True
    hard_contract = (
        structural_valid
        and citation_valid
        and hidden_leaks == 0
        and profile_leaks == 0
        and input_packet_unchanged
    )

    if output is None:
        action_support: ActionAssessment = "missing"
        action_citations = False
        option_mapping: OptionMappingAssessment = "missing"
        option_citations = False
        abstention: AbstentionQuality = "missing"
        motive_support: MotiveAssessment = "missing"
        motive_coverage = 0.0
        family_coverage = 0.0
        unsupported_motives = 0
        motive_citation_failures = 0
        action_confidence_ok = False
        option_confidence_ok = False
        motive_confidence_ok = False
    else:
        cited_ids = set(output.cited_observation_ids)
        required_action_citations = set(gold.action_support_observation_ids)
        action_citations = (
            not required_action_citations
            or required_action_citations.issubset(cited_ids)
        )
        if (
            gold.action_support_level == "unknown"
            and output.inferred_action_tendency == "unknown"
        ):
            action_support = "supported_abstention"
        elif (
            output.inferred_action_tendency in gold.expected_action_tendencies
            and action_citations
        ):
            action_support = "supported"
        else:
            action_support = "unsupported"

        if gold.required_abstention:
            if output.inferred_option_id is None:
                option_mapping = "required_abstention"
                option_citations = True
                abstention = "required_and_observed"
            else:
                option_mapping = "overcommitted"
                option_citations = False
                abstention = "missed"
        elif output.inferred_option_id is None:
            option_mapping = "unnecessary_abstention"
            option_citations = True
            abstention = "unnecessary"
        else:
            option_citations = set(gold.option_support_observation_ids).issubset(
                cited_ids
            )
            abstention = "not_required"
            if output.inferred_option_id not in gold.acceptable_option_ids:
                option_mapping = "mismatched"
            elif not option_citations:
                option_mapping = "mapping_without_visible_support"
            else:
                option_mapping = "mapped"

        acceptable_by_key = {
            item.key: item for item in gold.acceptable_motive_hypotheses
        }
        acceptable_families = {
            item.family for item in gold.acceptable_motive_hypotheses
        }
        exact_supported_keys: set[tuple[str, str]] = set()
        supported_families: set[str] = set()
        unsupported_motives = 0
        motive_citation_failures = 0
        for hypothesis in output.motive_hypotheses:
            expected = acceptable_by_key.get(hypothesis.key)
            if expected is not None:
                if set(expected.supporting_observation_ids).issubset(
                    hypothesis.cited_observation_ids
                ):
                    exact_supported_keys.add(hypothesis.key)
                    supported_families.add(hypothesis.family)
                else:
                    motive_citation_failures += 1
                continue
            unsupported_motives += 1

        acceptable_count = len(acceptable_by_key)
        if gold.motive_support_level == "hierarchical":
            motive_coverage = float(bool(exact_supported_keys))
        else:
            motive_coverage = (
                len(exact_supported_keys) / acceptable_count
                if acceptable_count
                else float(not output.motive_hypotheses)
            )
        family_coverage = (
            len(supported_families) / len(acceptable_families)
            if acceptable_families
            else float(not output.motive_hypotheses)
        )
        if gold.motive_support_level == "not_identifiable":
            motive_support = (
                "unknown_preserved"
                if not output.motive_hypotheses
                else "unsupported"
            )
        elif not output.motive_hypotheses:
            motive_support = "missing"
        elif (
            len(exact_supported_keys) == acceptable_count
            and unsupported_motives == 0
            and motive_citation_failures == 0
        ):
            motive_support = "supported"
        elif (
            gold.motive_support_level == "hierarchical"
            and exact_supported_keys
            and unsupported_motives == 0
            and motive_citation_failures == 0
        ):
            motive_support = "hierarchy_compatible"
        elif motive_coverage > 0.0:
            motive_support = "partially_supported"
        else:
            motive_support = "unsupported"

        action_confidence_ok = _within_bound(
            output.action_confidence, gold.maximum_action_confidence
        )
        option_confidence_ok = _within_bound(
            output.option_confidence, gold.maximum_option_confidence
        )
        motive_confidence_ok = all(
            _within_bound(item.confidence, gold.maximum_motive_confidence)
            for item in output.motive_hypotheses
        )

    observations: list[str] = []
    checks = (
        (structural_valid, "invalid_structured_output"),
        (citation_valid, "citation_scope_failure"),
        (hidden_leaks == 0, "hidden_truth_leakage"),
        (profile_leaks == 0, "profile_leakage"),
        (input_packet_unchanged, "input_packet_mutation"),
        (
            action_support in {"supported", "supported_abstention"},
            "action_support_failure",
        ),
        (
            option_mapping in {"mapped", "required_abstention"},
            "option_mapping_failure",
        ),
        (
            motive_support
            in {"supported", "hierarchy_compatible", "unknown_preserved"},
            "motive_support_failure",
        ),
        (unsupported_motives == 0, "unsupported_motive_overclaim"),
        (motive_citation_failures == 0, "motive_citation_failure"),
        (action_confidence_ok, "action_confidence_overclaim"),
        (option_confidence_ok, "option_confidence_overclaim"),
        (motive_confidence_ok, "motive_confidence_overclaim"),
    )
    observations.extend(code for ok, code in checks if not ok)
    return RacioEpistemicCaseEvaluation(
        case_id=gold.case_id,
        bilingual_pair_id=gold.bilingual_pair_id,
        structural_output_valid=structural_valid,
        citation_scope_valid=citation_valid,
        hidden_truth_leakage_count=hidden_leaks,
        profile_leakage_count=profile_leaks,
        input_packet_unchanged=input_packet_unchanged,
        hard_contract_pass=hard_contract,
        action_support=action_support,
        action_citation_support=action_citations,
        option_determinacy=gold.option_determinacy,
        option_mapping=option_mapping,
        option_citation_support=option_citations,
        abstention_quality=abstention,
        motive_support=motive_support,
        motive_hypothesis_coverage=round(motive_coverage, 12),
        motive_family_coverage=round(family_coverage, 12),
        unsupported_motive_overclaim_count=unsupported_motives,
        motive_citation_failure_count=motive_citation_failures,
        action_confidence_within_bound=action_confidence_ok,
        option_confidence_within_bound=option_confidence_ok,
        motive_confidences_within_bound=motive_confidence_ok,
        research_observations=tuple(sorted(set(observations))),
    )


def evaluate_racio_epistemic_bilingual_pair(
    *,
    bilingual_pair_id: str,
    sl_packet: RacioEpistemicPacketV2,
    sl_output: RacioEpistemicInterpretationV2,
    en_packet: RacioEpistemicPacketV2,
    en_output: RacioEpistemicInterpretationV2,
    confidence_tolerance: Score01,
) -> RacioEpistemicBilingualEvaluation:
    """Compare semantic fields and confidence, never literal explanations."""

    if sl_packet.language != "sl" or en_packet.language != "en":
        raise ValueError("Bilingual evaluation requires SL then EN packets")
    sl_output.validate_against(sl_packet)
    en_output.validate_against(en_packet)
    sl_keys = tuple(item.key for item in sl_output.motive_hypotheses)
    en_keys = tuple(item.key for item in en_output.motive_hypotheses)
    sl_families = tuple(sorted({item.family for item in sl_output.motive_hypotheses}))
    en_families = tuple(sorted({item.family for item in en_output.motive_hypotheses}))
    action_delta = round(
        abs(sl_output.action_confidence - en_output.action_confidence), 12
    )
    option_delta = round(
        abs(sl_output.option_confidence - en_output.option_confidence), 12
    )
    sl_confidence = {item.key: item.confidence for item in sl_output.motive_hypotheses}
    en_confidence = {item.key: item.confidence for item in en_output.motive_hypotheses}
    if set(sl_confidence) != set(en_confidence):
        motive_delta = 1.0
    else:
        motive_delta = round(
            max(
                (
                    abs(sl_confidence[key] - en_confidence[key])
                    for key in sl_confidence
                ),
                default=0.0,
            ),
            12,
        )
    return RacioEpistemicBilingualEvaluation(
        bilingual_pair_id=bilingual_pair_id,
        source_mind_consistent=(
            sl_packet.source_mind
            == en_packet.source_mind
            == sl_output.source_mind
            == en_output.source_mind
        ),
        action_consistent=(
            sl_output.inferred_action_tendency
            == en_output.inferred_action_tendency
        ),
        option_consistent=(
            sl_output.inferred_option_id == en_output.inferred_option_id
        ),
        motive_family_consistent=sl_families == en_families,
        motive_subtype_consistent=sl_keys == en_keys,
        citation_consistent=(
            sl_output.cited_observation_ids == en_output.cited_observation_ids
        ),
        ambiguity_presence_consistent=(
            (sl_output.unresolved_ambiguity is None)
            == (en_output.unresolved_ambiguity is None)
        ),
        action_confidence_delta=action_delta,
        option_confidence_delta=option_delta,
        motive_confidence_delta=motive_delta,
        action_confidence_consistent=action_delta <= confidence_tolerance,
        option_confidence_consistent=option_delta <= confidence_tolerance,
        motive_confidence_consistent=motive_delta <= confidence_tolerance,
    )


__all__ = [
    "AbstentionQuality",
    "ActionAssessment",
    "ActionSupportLevel",
    "EpistemicCaseGoldV2",
    "EpistemicGoldMotiveHypothesis",
    "ForbiddenInference",
    "MotiveAssessment",
    "MotiveSupportLevel",
    "OptionDeterminacy",
    "OptionMappingAssessment",
    "RacioEpistemicBilingualEvaluation",
    "RacioEpistemicCaseEvaluation",
    "evaluate_racio_epistemic_bilingual_pair",
    "evaluate_racio_epistemic_case",
]
