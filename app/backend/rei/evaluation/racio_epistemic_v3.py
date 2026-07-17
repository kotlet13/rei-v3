"""Model-free evaluator for the isolated Racio epistemic v3 contract.

The evaluator consumes only the public v3 packet, evaluator-only gold, and the
validated v3 interpretation.  It never consumes a provider sidecar and never
produces one aggregate semantic score or decision-authority signal.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from ..communication.epistemic_interpreter_v3 import (
    ActionFamilyFallbackV3,
    ActionFamilyV3,
    ActionHypothesisV3,
    ActionSubtypeV3,
    ActionSupportModeV3,
    LEGACY_AMBIGUOUS_ACTION_GOLD_RESOLUTIONS_V3,
    MotiveHypothesisV3,
    MotiveSupportModeV3,
    PresentationModeV3,
    RacioEpistemicInterpretationV3,
    RacioEpistemicPacketV3,
    action_fallback_belongs_to_family_v3,
    action_subtype_belongs_to_family_v3,
)
from ..communication.epistemic_interpreter import (
    MotiveFamily,
    RacioReportedUncertainty,
    motive_subtype_belongs_to_family,
)
from ..models.common import FrozenModel, NonEmptyId, NonEmptyText, Score01


OptionDeterminacyV3 = Literal["unique", "underdetermined"]
ActionGoldRoleV3 = Literal["exact", "acceptable_sibling", "parent_fallback"]
LegacyAmbiguousActionSourceV3 = Literal["withdraw"]
AcceptedActionSupportModeV3 = Literal[
    "direct_manifestation",
    "functional_inference",
]
MotiveReferenceSupportModeV3 = Literal[
    "directly_supported",
    "contextually_supported",
]
MotiveIdentifiabilityV3 = Literal[
    "identifiable",
    "contextually_bounded",
    "not_identifiable",
]

OptionMappingAssessmentV3 = Literal[
    "mapped",
    "mapping_without_visible_support",
    "required_abstention",
    "overcommitted",
    "unnecessary_abstention",
    "mismatched",
    "missing",
]
RequiredAbstentionAssessmentV3 = Literal[
    "required_and_observed",
    "missed",
    "unnecessary",
    "not_required",
    "missing",
]
UnknownPreservationAssessmentV3 = Literal[
    "preserved",
    "violated",
    "not_required",
    "missing_output",
]
ActionHypothesisAssessmentCodeV3 = Literal[
    "supported_exact",
    "supported_acceptable_sibling",
    "supported_parent_fallback",
    "family_only_unsupported_subtype",
    "wrong_family",
    "citation_insufficient",
    "support_mode_overclaim",
    "speculative_not_supported",
    "unaccepted_family_fallback",
]
MotiveHypothesisAssessmentCodeV3 = Literal[
    "supported_direct",
    "family_only_unsupported_subtype",
    "contextually_supported_not_reference",
    "speculative_not_supported",
    "redundant_nonminimal",
    "action_only_evidence",
    "citation_insufficient",
    "support_mode_overclaim",
    "unsupported_identity",
]


def _is_canonical(values: tuple[str, ...]) -> bool:
    return values == tuple(sorted(set(values)))


def _action_identity(
    *,
    family: str,
    subtype: str | None,
    family_fallback: str | None,
) -> tuple[str, str]:
    identity = (
        subtype
        if subtype is not None
        else f"<family_fallback:{family_fallback}>"
    )
    return (family, identity)


class EpistemicGoldActionHypothesisV3(FrozenModel):
    """One precommitted action target or explicitly accepted alternative."""

    family: ActionFamilyV3
    subtype: ActionSubtypeV3 | None
    family_fallback: ActionFamilyFallbackV3 | None = None
    role: ActionGoldRoleV3
    legacy_source_action: LegacyAmbiguousActionSourceV3 | None = None
    supporting_observation_ids: tuple[NonEmptyId, ...]
    accepted_support_modes: tuple[AcceptedActionSupportModeV3, ...]

    @property
    def key(self) -> tuple[str, str]:
        return _action_identity(
            family=self.family,
            subtype=self.subtype,
            family_fallback=self.family_fallback,
        )

    @model_validator(mode="after")
    def validate_action_gold(self) -> Self:
        exact = self.subtype is not None
        fallback = self.family_fallback is not None
        if exact == fallback:
            raise ValueError(
                "Action gold requires exactly one subtype or family fallback"
            )
        if exact and not action_subtype_belongs_to_family_v3(
            self.family, self.subtype or ""
        ):
            raise ValueError("Gold action subtype does not belong to its family")
        if fallback and not action_fallback_belongs_to_family_v3(
            self.family, self.family_fallback or ""
        ):
            raise ValueError("Gold action fallback does not belong to its family")
        if self.role in {"exact", "acceptable_sibling"} and not exact:
            raise ValueError("Exact and sibling action gold require a subtype")
        if self.role == "parent_fallback" and not fallback:
            raise ValueError("Parent action gold requires a family fallback")
        if self.legacy_source_action is not None:
            resolved_identity = (
                f"{self.family}/{self.subtype}" if self.subtype is not None else ""
            )
            if self.role != "exact" or resolved_identity not in set(
                LEGACY_AMBIGUOUS_ACTION_GOLD_RESOLUTIONS_V3[
                    self.legacy_source_action
                ]
            ):
                raise ValueError(
                    "Legacy ambiguous action gold requires an explicit allowed "
                    "exact resolution"
                )
        if not self.supporting_observation_ids or not _is_canonical(
            self.supporting_observation_ids
        ):
            raise ValueError("Action gold support IDs must be nonempty and canonical")
        if not self.accepted_support_modes or self.accepted_support_modes != tuple(
            sorted(set(self.accepted_support_modes))
        ):
            raise ValueError("Accepted action support modes must be canonical")
        return self


class EpistemicGoldMotiveHypothesisV3(FrozenModel):
    """One direct reference motive or one explicitly contextual alternative."""

    family: MotiveFamily
    subtype: NonEmptyId
    reference_support_mode: MotiveReferenceSupportModeV3
    supporting_observation_ids: tuple[NonEmptyId, ...]

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.subtype)

    @model_validator(mode="after")
    def validate_motive_gold(self) -> Self:
        if not motive_subtype_belongs_to_family(self.family, self.subtype):
            raise ValueError("Gold motive subtype does not belong to its family")
        if not self.supporting_observation_ids or not _is_canonical(
            self.supporting_observation_ids
        ):
            raise ValueError("Motive gold support IDs must be nonempty and canonical")
        return self


class EpistemicCaseGoldV3(FrozenModel):
    """Evaluator-only v3 expectations; never provider-visible."""

    schema_version: Literal["rei-racio-epistemic-gold-v3"] = (
        "rei-racio-epistemic-gold-v3"
    )
    case_id: NonEmptyId
    bilingual_pair_id: NonEmptyId
    expected_source_mind: Literal["E", "I"]
    expected_presentation_mode: PresentationModeV3

    option_determinacy: OptionDeterminacyV3
    acceptable_option_ids: tuple[NonEmptyId, ...]
    option_support_observation_ids: tuple[NonEmptyId, ...]
    required_abstention: bool

    expected_action_unknown: bool
    acceptable_action_hypotheses: tuple[EpistemicGoldActionHypothesisV3, ...]

    motive_identifiability: MotiveIdentifiabilityV3
    acceptable_motive_hypotheses: tuple[EpistemicGoldMotiveHypothesisV3, ...]
    action_only_observation_ids: tuple[NonEmptyId, ...]
    high_confidence_unsupported_threshold: Score01

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

    @property
    def exact_action_targets(self) -> tuple[EpistemicGoldActionHypothesisV3, ...]:
        return tuple(
            item for item in self.acceptable_action_hypotheses if item.role == "exact"
        )

    @property
    def direct_motive_targets(self) -> tuple[EpistemicGoldMotiveHypothesisV3, ...]:
        return tuple(
            item
            for item in self.acceptable_motive_hypotheses
            if item.reference_support_mode == "directly_supported"
        )

    @model_validator(mode="after")
    def validate_gold_contract(self) -> Self:
        canonical_fields = (
            "acceptable_option_ids",
            "option_support_observation_ids",
            "action_only_observation_ids",
            "source_claim_ids",
        )
        for field_name in canonical_fields:
            values = getattr(self, field_name)
            if not _is_canonical(values):
                raise ValueError(f"Gold {field_name} must be canonical")

        if self.option_determinacy == "unique":
            if len(self.acceptable_option_ids) != 1 or self.required_abstention:
                raise ValueError("Unique option gold requires one mapped option")
            if not self.option_support_observation_ids:
                raise ValueError("Unique option gold requires visible support")
        elif len(self.acceptable_option_ids) < 2 or not self.required_abstention:
            raise ValueError(
                "Underdetermined option gold requires alternatives and abstention"
            )

        action_keys = tuple(item.key for item in self.acceptable_action_hypotheses)
        if action_keys != tuple(sorted(set(action_keys))):
            raise ValueError("Action gold hypotheses must be canonical and unique")
        exact_targets = self.exact_action_targets
        if self.expected_action_unknown:
            if self.acceptable_action_hypotheses:
                raise ValueError("Unknown action gold cannot contain action targets")
        elif not exact_targets:
            raise ValueError("Known action gold requires at least one exact target")
        exact_families = {item.family for item in exact_targets}
        if any(
            item.role != "exact" and item.family not in exact_families
            for item in self.acceptable_action_hypotheses
        ):
            raise ValueError("Action alternatives require an exact target family")

        motive_keys = tuple(item.key for item in self.acceptable_motive_hypotheses)
        if motive_keys != tuple(sorted(set(motive_keys))):
            raise ValueError("Motive gold hypotheses must be canonical and unique")
        if self.motive_identifiability == "not_identifiable":
            if self.acceptable_motive_hypotheses:
                raise ValueError("Unidentifiable motive gold cannot contain targets")
        elif self.motive_identifiability == "contextually_bounded":
            if not self.acceptable_motive_hypotheses:
                raise ValueError(
                    "Contextually bounded motive gold requires contextual targets"
                )
            if self.direct_motive_targets:
                raise ValueError(
                    "Contextually bounded motive gold cannot contain direct targets"
                )
        elif not self.direct_motive_targets:
            raise ValueError(
                "Identifiable motive gold requires directly supported reference"
            )

        action_evidence = {
            *self.action_only_observation_ids,
            *(
                observation_id
                for item in self.acceptable_action_hypotheses
                for observation_id in item.supporting_observation_ids
            ),
        }
        for item in self.direct_motive_targets:
            if not set(item.supporting_observation_ids).difference(action_evidence):
                raise ValueError(
                    "Direct motive gold requires non-action observation support"
                )
        direct_non_action_support = {
            item.key: set(item.supporting_observation_ids).difference(
                action_evidence
            )
            for item in self.direct_motive_targets
        }
        for key, support_ids in direct_non_action_support.items():
            other_support_ids = {
                observation_id
                for other_key, other_ids in direct_non_action_support.items()
                if other_key != key
                for observation_id in other_ids
            }
            if len(direct_non_action_support) > 1 and not support_ids.difference(
                other_support_ids
            ):
                raise ValueError(
                    "Each direct motive gold target requires its own independent "
                    "non-action observation support"
                )
        return self


class ActionHypothesisAssessmentV3(FrozenModel):
    family: ActionFamilyV3
    subtype: ActionSubtypeV3 | None
    family_fallback: ActionFamilyFallbackV3 | None
    support_mode: ActionSupportModeV3
    confidence: Score01
    assessment: ActionHypothesisAssessmentCodeV3
    identity_precommitted: bool
    citation_support: bool
    support_mode_accepted: bool
    family_credit: bool
    subtype_credit: bool
    unsupported_overclaim: bool


class MotiveHypothesisAssessmentV3(FrozenModel):
    family: MotiveFamily
    subtype: NonEmptyId
    support_mode: MotiveSupportModeV3
    confidence: Score01
    assessment: MotiveHypothesisAssessmentCodeV3
    identity_precommitted: bool
    citation_support: bool
    action_evidence_cited: bool
    action_only_evidence: bool
    qualifying_non_action_observation_ids: tuple[NonEmptyId, ...]
    family_credit: bool
    subtype_credit: bool
    reference_supported: bool
    unsupported_overclaim: bool
    redundant_nonminimal: bool
    high_confidence_unsupported: bool


class UnknownPreservationV3(FrozenModel):
    action: UnknownPreservationAssessmentV3
    motive: UnknownPreservationAssessmentV3


class RacioEpistemicCaseEvaluationV3(FrozenModel):
    """Independent v3 dimensions with only a structural hard gate."""

    schema_version: Literal["rei-racio-epistemic-case-evaluation-v3"] = (
        "rei-racio-epistemic-case-evaluation-v3"
    )
    case_id: NonEmptyId
    bilingual_pair_id: NonEmptyId

    structural_output_valid: bool
    citation_scope_valid: bool
    hidden_truth_leakage_count: int = Field(ge=0)
    profile_leakage_count: int = Field(ge=0)
    input_packet_unchanged: bool
    hard_contract_pass: bool

    action_hypothesis_assessments: tuple[ActionHypothesisAssessmentV3, ...]
    action_family_support: Score01
    action_subtype_support: Score01
    action_unsupported_overclaims: int = Field(ge=0)

    option_mapping: OptionMappingAssessmentV3
    option_citation_support: bool
    required_abstention: RequiredAbstentionAssessmentV3

    motive_hypothesis_assessments: tuple[MotiveHypothesisAssessmentV3, ...]
    motive_family_coverage: Score01
    motive_subtype_coverage: Score01
    motive_precision: Score01
    motive_unsupported_overclaims: int = Field(ge=0)
    motive_redundant_nonminimal_count: int = Field(ge=0)
    high_confidence_unsupported_motive_count: int = Field(ge=0)
    contextual_motive_hypothesis_count: int = Field(ge=0)
    speculative_motive_hypothesis_count: int = Field(ge=0)
    unknown_preservation: UnknownPreservationV3
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
            raise ValueError("V3 hard gate differs from structural dimensions")
        if not _is_canonical(self.research_observations):
            raise ValueError("Research observations must be canonical")
        return self


class BilingualLayerConsistencyV3(FrozenModel):
    action: bool
    motive: bool


class BilingualUncertaintyConsistencyV3(FrozenModel):
    option: bool
    motive: bool


class RacioEpistemicBilingualEvaluationV3(FrozenModel):
    """Raw emitted pair comparison; speculative hypotheses remain visible."""

    schema_version: Literal["rei-racio-epistemic-bilingual-evaluation-v3"] = (
        "rei-racio-epistemic-bilingual-evaluation-v3"
    )
    bilingual_pair_id: NonEmptyId
    canonical_evidence_identity_consistent: Literal[True]
    source_mind_consistent: bool
    bilingual_family_consistency: BilingualLayerConsistencyV3
    bilingual_subtype_consistency: BilingualLayerConsistencyV3
    action_support_mode_consistency: bool
    motive_support_mode_consistency: bool
    option_mapping_consistency: bool
    citation_identity_consistency: bool
    uncertainty_consistency: BilingualUncertaintyConsistencyV3


def _validate_gold_against_packet(
    *,
    packet: RacioEpistemicPacketV3,
    gold: EpistemicCaseGoldV3,
) -> None:
    if (
        packet.source_mind != gold.expected_source_mind
        or packet.presentation_mode != gold.expected_presentation_mode
    ):
        raise ValueError("V3 gold mind or presentation differs from packet")
    visible_ids = set(packet.visible_observation_ids)
    support_ids = {
        *gold.option_support_observation_ids,
        *gold.action_only_observation_ids,
        *(
            observation_id
            for item in gold.acceptable_action_hypotheses
            for observation_id in item.supporting_observation_ids
        ),
        *(
            observation_id
            for item in gold.acceptable_motive_hypotheses
            for observation_id in item.supporting_observation_ids
        ),
    }
    if not support_ids.issubset(visible_ids):
        raise ValueError("V3 evaluator support aliases exceed the public packet")
    if not set(gold.acceptable_option_ids).issubset(packet.public_option_ids):
        raise ValueError("V3 acceptable options exceed the public packet")


def _assess_actions(
    *,
    output: RacioEpistemicInterpretationV3,
    gold: EpistemicCaseGoldV3,
) -> tuple[tuple[ActionHypothesisAssessmentV3, ...], float, float, int]:
    candidates = {item.key: item for item in gold.acceptable_action_hypotheses}
    exact_targets = gold.exact_action_targets
    expected_families = {item.family for item in exact_targets}
    supported_families: set[str] = set()
    supported_exact_keys: set[tuple[str, str]] = set()
    assessments: list[ActionHypothesisAssessmentV3] = []

    for hypothesis in output.action_hypotheses:
        expected = candidates.get(hypothesis.key)
        identity_precommitted = expected is not None
        citation_support = False
        support_mode_accepted = False
        family_credit = False
        subtype_credit = False
        unsupported = False
        if expected is not None:
            citation_support = set(expected.supporting_observation_ids).issubset(
                hypothesis.cited_observation_ids
            )
            support_mode_accepted = (
                hypothesis.support_mode in expected.accepted_support_modes
            )
            if not citation_support:
                assessment: ActionHypothesisAssessmentCodeV3 = (
                    "citation_insufficient"
                )
                unsupported = True
            elif hypothesis.support_mode == "speculative":
                assessment = "speculative_not_supported"
            elif not support_mode_accepted:
                assessment = "support_mode_overclaim"
                unsupported = True
            else:
                family_credit = True
                supported_families.add(hypothesis.family)
                if expected.role == "exact":
                    subtype_credit = True
                    supported_exact_keys.add(hypothesis.key)
                    assessment = "supported_exact"
                elif expected.role == "acceptable_sibling":
                    assessment = "supported_acceptable_sibling"
                else:
                    assessment = "supported_parent_fallback"
        elif hypothesis.family in expected_families:
            family_targets = [
                item for item in exact_targets if item.family == hypothesis.family
            ]
            cited_targets = [
                item
                for item in family_targets
                if set(item.supporting_observation_ids).issubset(
                    hypothesis.cited_observation_ids
                )
            ]
            citation_support = bool(cited_targets)
            support_mode_accepted = any(
                hypothesis.support_mode in item.accepted_support_modes
                for item in cited_targets
            )
            if hypothesis.family_fallback is not None:
                assessment = "unaccepted_family_fallback"
            elif not citation_support:
                assessment = "citation_insufficient"
            elif hypothesis.support_mode == "speculative":
                assessment = "family_only_unsupported_subtype"
            elif support_mode_accepted:
                family_credit = True
                supported_families.add(hypothesis.family)
                assessment = "family_only_unsupported_subtype"
            else:
                assessment = "support_mode_overclaim"
            unsupported = True
        else:
            assessment = "wrong_family"
            unsupported = True

        assessments.append(
            ActionHypothesisAssessmentV3(
                family=hypothesis.family,
                subtype=hypothesis.subtype,
                family_fallback=hypothesis.family_fallback,
                support_mode=hypothesis.support_mode,
                confidence=hypothesis.confidence,
                assessment=assessment,
                identity_precommitted=identity_precommitted,
                citation_support=citation_support,
                support_mode_accepted=support_mode_accepted,
                family_credit=family_credit,
                subtype_credit=subtype_credit,
                unsupported_overclaim=unsupported,
            )
        )

    family_support = (
        len(supported_families) / len(expected_families)
        if expected_families
        else float(not output.action_hypotheses)
    )
    subtype_support = (
        len(supported_exact_keys) / len(exact_targets)
        if exact_targets
        else float(not output.action_hypotheses)
    )
    unsupported_count = sum(item.unsupported_overclaim for item in assessments)
    return (
        tuple(assessments),
        round(family_support, 12),
        round(subtype_support, 12),
        unsupported_count,
    )


def _assess_option(
    *,
    output: RacioEpistemicInterpretationV3,
    gold: EpistemicCaseGoldV3,
) -> tuple[
    OptionMappingAssessmentV3,
    bool,
    RequiredAbstentionAssessmentV3,
]:
    if gold.required_abstention:
        if output.option_inference is None:
            return ("required_abstention", True, "required_and_observed")
        return ("overcommitted", False, "missed")
    if output.option_inference is None:
        return ("unnecessary_abstention", True, "unnecessary")
    citation_support = set(gold.option_support_observation_ids).issubset(
        output.option_inference.cited_observation_ids
    )
    if output.option_inference.option_id not in gold.acceptable_option_ids:
        return ("mismatched", citation_support, "not_required")
    if not citation_support:
        return ("mapping_without_visible_support", False, "not_required")
    return ("mapped", True, "not_required")


def _assess_motives(
    *,
    output: RacioEpistemicInterpretationV3,
    gold: EpistemicCaseGoldV3,
) -> tuple[
    tuple[MotiveHypothesisAssessmentV3, ...],
    float,
    float,
    float,
    int,
    int,
    int,
    int,
    int,
]:
    references = {item.key: item for item in gold.acceptable_motive_hypotheses}
    direct_targets = gold.direct_motive_targets
    direct_keys = {item.key for item in direct_targets}
    direct_families = {item.family for item in direct_targets}
    action_evidence = {
        *gold.action_only_observation_ids,
        *(
            observation_id
            for item in gold.acceptable_action_hypotheses
            for observation_id in item.supporting_observation_ids
        ),
    }
    consumed_non_action_ids: set[str] = set()
    supported_keys: set[tuple[str, str]] = set()
    supported_families: set[str] = set()
    assessments: list[MotiveHypothesisAssessmentV3] = []

    for index, hypothesis in enumerate(output.motive_hypotheses):
        expected = references.get(hypothesis.key)
        identity_precommitted = expected is not None
        cited = set(hypothesis.cited_observation_ids)
        action_evidence_cited = bool(cited.intersection(action_evidence))
        action_only_evidence = bool(cited) and not cited.difference(
            action_evidence
        )
        citation_support = False
        qualifying: set[str] = set()
        family_credit = False
        subtype_credit = False
        reference_supported = False
        unsupported = False
        redundant_nonminimal = False

        if expected is None:
            family_targets = tuple(
                item for item in direct_targets if item.family == hypothesis.family
            )
            cited_family_targets = tuple(
                item
                for item in family_targets
                if set(item.supporting_observation_ids).issubset(cited)
            )
            if not family_targets:
                assessment: MotiveHypothesisAssessmentCodeV3 = (
                    "unsupported_identity"
                )
            elif not cited_family_targets:
                assessment = (
                    "action_only_evidence"
                    if action_only_evidence
                    else "citation_insufficient"
                )
            else:
                citation_support = True
                qualifying = {
                    observation_id
                    for item in cited_family_targets
                    for observation_id in item.supporting_observation_ids
                    if observation_id not in action_evidence
                }
                if hypothesis.support_mode != "directly_supported":
                    assessment = "family_only_unsupported_subtype"
                elif not qualifying:
                    assessment = "action_only_evidence"
                elif consumed_non_action_ids and not qualifying.difference(
                    consumed_non_action_ids
                ):
                    assessment = "redundant_nonminimal"
                else:
                    assessment = "family_only_unsupported_subtype"
                    family_credit = True
                    supported_families.add(hypothesis.family)
            unsupported = True
        else:
            required = set(expected.supporting_observation_ids)
            citation_support = required.issubset(cited)
            qualifying = required.intersection(cited).difference(action_evidence)
            if not citation_support:
                if action_only_evidence:
                    assessment = "action_only_evidence"
                else:
                    assessment = "citation_insufficient"
                unsupported = True
            elif expected.reference_support_mode == "contextually_supported":
                if hypothesis.support_mode == "directly_supported":
                    assessment = "support_mode_overclaim"
                    unsupported = True
                elif consumed_non_action_ids and not qualifying.difference(
                    consumed_non_action_ids
                ):
                    assessment = "redundant_nonminimal"
                elif hypothesis.support_mode == "speculative":
                    assessment = "speculative_not_supported"
                else:
                    assessment = "contextually_supported_not_reference"
            elif hypothesis.support_mode == "speculative":
                if consumed_non_action_ids and not qualifying.difference(
                    consumed_non_action_ids
                ):
                    assessment = "redundant_nonminimal"
                else:
                    assessment = "speculative_not_supported"
            elif hypothesis.support_mode != "directly_supported":
                if consumed_non_action_ids and not qualifying.difference(
                    consumed_non_action_ids
                ):
                    assessment = "redundant_nonminimal"
                else:
                    assessment = "contextually_supported_not_reference"
            elif not qualifying:
                assessment = "action_only_evidence"
                unsupported = True
            elif index > 0 and not qualifying.difference(
                consumed_non_action_ids
            ):
                assessment = "redundant_nonminimal"
            else:
                assessment = "supported_direct"
                reference_supported = True
                family_credit = True
                subtype_credit = True
                supported_keys.add(hypothesis.key)
                supported_families.add(hypothesis.family)

        redundant_nonminimal = index > 0 and (
            not qualifying
            or not qualifying.difference(consumed_non_action_ids)
        )
        if redundant_nonminimal and assessment in {
            "contextually_supported_not_reference",
            "speculative_not_supported",
        }:
            assessment = "redundant_nonminimal"

        if (
            (identity_precommitted or family_credit)
            and citation_support
            and not redundant_nonminimal
        ):
            consumed_non_action_ids.update(qualifying)

        high_confidence_unsupported = (
            unsupported
            and hypothesis.confidence
            >= gold.high_confidence_unsupported_threshold
        )
        assessments.append(
            MotiveHypothesisAssessmentV3(
                family=hypothesis.family,
                subtype=hypothesis.subtype,
                support_mode=hypothesis.support_mode,
                confidence=hypothesis.confidence,
                assessment=assessment,
                identity_precommitted=identity_precommitted,
                citation_support=citation_support,
                action_evidence_cited=action_evidence_cited,
                action_only_evidence=action_only_evidence,
                qualifying_non_action_observation_ids=tuple(sorted(qualifying)),
                family_credit=family_credit,
                subtype_credit=subtype_credit,
                reference_supported=reference_supported,
                unsupported_overclaim=unsupported,
                redundant_nonminimal=redundant_nonminimal,
                high_confidence_unsupported=high_confidence_unsupported,
            )
        )

    family_coverage = (
        len(supported_families) / len(direct_families)
        if direct_families
        else 1.0
    )
    subtype_coverage = (
        len(supported_keys.intersection(direct_keys)) / len(direct_keys)
        if direct_keys
        else 1.0
    )
    precision = (
        len(supported_keys) / len(output.motive_hypotheses)
        if output.motive_hypotheses
        else float(gold.motive_identifiability != "identifiable")
    )
    unsupported_count = sum(item.unsupported_overclaim for item in assessments)
    redundant_count = sum(item.redundant_nonminimal for item in assessments)
    high_confidence_count = sum(
        item.high_confidence_unsupported for item in assessments
    )
    contextual_count = sum(
        item.support_mode == "contextually_supported" for item in assessments
    )
    speculative_count = sum(
        item.support_mode == "speculative" for item in assessments
    )
    return (
        tuple(assessments),
        round(family_coverage, 12),
        round(subtype_coverage, 12),
        round(precision, 12),
        unsupported_count,
        redundant_count,
        high_confidence_count,
        contextual_count,
        speculative_count,
    )


def evaluate_racio_epistemic_case_v3(
    *,
    packet: RacioEpistemicPacketV3,
    gold: EpistemicCaseGoldV3,
    output: RacioEpistemicInterpretationV3 | None,
    input_packet_unchanged: bool,
) -> RacioEpistemicCaseEvaluationV3:
    """Evaluate one v3 output without an aggregate semantic result."""

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
        action_assessments: tuple[ActionHypothesisAssessmentV3, ...] = ()
        action_family_support = 0.0
        action_subtype_support = 0.0
        action_unsupported = 0
        option_mapping: OptionMappingAssessmentV3 = "missing"
        option_citations = False
        abstention: RequiredAbstentionAssessmentV3 = "missing"
        motive_assessments: tuple[MotiveHypothesisAssessmentV3, ...] = ()
        motive_family_coverage = 0.0
        motive_subtype_coverage = 0.0
        motive_precision = 0.0
        motive_unsupported = 0
        redundant_count = 0
        high_confidence_count = 0
        contextual_count = 0
        speculative_count = 0
        unknown = UnknownPreservationV3(
            action="missing_output", motive="missing_output"
        )
    else:
        (
            action_assessments,
            action_family_support,
            action_subtype_support,
            action_unsupported,
        ) = _assess_actions(output=output, gold=gold)
        option_mapping, option_citations, abstention = _assess_option(
            output=output, gold=gold
        )
        (
            motive_assessments,
            motive_family_coverage,
            motive_subtype_coverage,
            motive_precision,
            motive_unsupported,
            redundant_count,
            high_confidence_count,
            contextual_count,
            speculative_count,
        ) = _assess_motives(output=output, gold=gold)
        unknown = UnknownPreservationV3(
            action=(
                "preserved"
                if gold.expected_action_unknown and not output.action_hypotheses
                else (
                    "violated"
                    if gold.expected_action_unknown
                    else "not_required"
                )
            ),
            motive=(
                "preserved"
                if (
                    gold.motive_identifiability == "not_identifiable"
                    and not output.motive_hypotheses
                )
                or (
                    gold.motive_identifiability == "contextually_bounded"
                    and all(
                        item.support_mode != "directly_supported"
                        for item in output.motive_hypotheses
                    )
                )
                else (
                    "violated"
                    if gold.motive_identifiability
                    in {"contextually_bounded", "not_identifiable"}
                    else "not_required"
                )
            ),
        )

    observations: list[str] = []
    checks = (
        (structural_valid, "invalid_structured_output"),
        (citation_valid, "citation_scope_failure"),
        (hidden_leaks == 0, "hidden_truth_leakage"),
        (profile_leaks == 0, "profile_leakage"),
        (input_packet_unchanged, "input_packet_mutation"),
        (action_family_support == 1.0, "action_family_support_failure"),
        (action_subtype_support == 1.0, "action_subtype_support_failure"),
        (action_unsupported == 0, "action_unsupported_overclaim"),
        (
            option_mapping in {"mapped", "required_abstention"},
            "option_mapping_failure",
        ),
        (motive_family_coverage == 1.0, "motive_family_coverage_failure"),
        (motive_subtype_coverage == 1.0, "motive_subtype_coverage_failure"),
        (motive_unsupported == 0, "motive_unsupported_overclaim"),
        (redundant_count == 0, "motive_nonminimal_redundancy"),
        (
            high_confidence_count == 0,
            "high_confidence_unsupported_motive",
        ),
        (
            unknown.action != "violated",
            "action_unknown_preservation_failure",
        ),
        (
            unknown.motive != "violated",
            "motive_unknown_preservation_failure",
        ),
    )
    observations.extend(code for ok, code in checks if not ok)

    return RacioEpistemicCaseEvaluationV3(
        case_id=gold.case_id,
        bilingual_pair_id=gold.bilingual_pair_id,
        structural_output_valid=structural_valid,
        citation_scope_valid=citation_valid,
        hidden_truth_leakage_count=hidden_leaks,
        profile_leakage_count=profile_leaks,
        input_packet_unchanged=input_packet_unchanged,
        hard_contract_pass=hard_contract,
        action_hypothesis_assessments=action_assessments,
        action_family_support=action_family_support,
        action_subtype_support=action_subtype_support,
        action_unsupported_overclaims=action_unsupported,
        option_mapping=option_mapping,
        option_citation_support=option_citations,
        required_abstention=abstention,
        motive_hypothesis_assessments=motive_assessments,
        motive_family_coverage=motive_family_coverage,
        motive_subtype_coverage=motive_subtype_coverage,
        motive_precision=motive_precision,
        motive_unsupported_overclaims=motive_unsupported,
        motive_redundant_nonminimal_count=redundant_count,
        high_confidence_unsupported_motive_count=high_confidence_count,
        contextual_motive_hypothesis_count=contextual_count,
        speculative_motive_hypothesis_count=speculative_count,
        unknown_preservation=unknown,
        research_observations=tuple(sorted(observations)),
    )


def _canonical_evidence_identity(packet: RacioEpistemicPacketV3) -> tuple[object, ...]:
    observations = tuple(
        (
            item.observation_id,
            item.atomic_evidence_unit_id,
            item.perceptual_unit_count,
            item.signal_alias,
            item.perception_status,
            None if item.text is None else item.text.canonical_sl,
            item.provenance,
        )
        for item in packet.visible_observations
    )
    options = tuple(
        (item.option_id, item.text.canonical_sl)
        for item in packet.public_option_scope
    )
    return (
        packet.source_mind,
        observations,
        packet.omitted_observation_ids,
        packet.degraded_observation_ids,
        options,
        packet.channel_quality,
        packet.uncertainty.text.canonical_sl,
    )


def _action_subtype_set(
    hypotheses: tuple[ActionHypothesisV3, ...],
) -> set[tuple[str, str]]:
    return {item.key for item in hypotheses}


def _motive_subtype_set(
    hypotheses: tuple[MotiveHypothesisV3, ...],
) -> set[tuple[str, str]]:
    return {item.key for item in hypotheses}


def evaluate_racio_epistemic_bilingual_pair_v3(
    *,
    bilingual_pair_id: NonEmptyId,
    sl_packet: RacioEpistemicPacketV3,
    sl_output: RacioEpistemicInterpretationV3,
    en_packet: RacioEpistemicPacketV3,
    en_output: RacioEpistemicInterpretationV3,
) -> RacioEpistemicBilingualEvaluationV3:
    """Compare raw v3 semantics after proving one canonical evidence identity."""

    if sl_packet.presentation_mode != "canonical_sl_only":
        raise ValueError("The SL pair member must use canonical Slovene presentation")
    if en_packet.presentation_mode != "operational_en_only":
        raise ValueError("The EN pair member must use audited English presentation")
    if _canonical_evidence_identity(sl_packet) != _canonical_evidence_identity(
        en_packet
    ):
        raise ValueError("Bilingual packets require the same canonical evidence")
    sl_output.validate_against(sl_packet)
    en_output.validate_against(en_packet)

    return RacioEpistemicBilingualEvaluationV3(
        bilingual_pair_id=bilingual_pair_id,
        canonical_evidence_identity_consistent=True,
        source_mind_consistent=sl_output.source_mind == en_output.source_mind,
        bilingual_family_consistency=BilingualLayerConsistencyV3(
            action=(
                {item.family for item in sl_output.action_hypotheses}
                == {item.family for item in en_output.action_hypotheses}
            ),
            motive=(
                {item.family for item in sl_output.motive_hypotheses}
                == {item.family for item in en_output.motive_hypotheses}
            ),
        ),
        bilingual_subtype_consistency=BilingualLayerConsistencyV3(
            action=(
                _action_subtype_set(sl_output.action_hypotheses)
                == _action_subtype_set(en_output.action_hypotheses)
            ),
            motive=(
                _motive_subtype_set(sl_output.motive_hypotheses)
                == _motive_subtype_set(en_output.motive_hypotheses)
            ),
        ),
        action_support_mode_consistency=(
            {(item.key, item.support_mode) for item in sl_output.action_hypotheses}
            == {(item.key, item.support_mode) for item in en_output.action_hypotheses}
        ),
        motive_support_mode_consistency=(
            {(item.key, item.support_mode) for item in sl_output.motive_hypotheses}
            == {(item.key, item.support_mode) for item in en_output.motive_hypotheses}
        ),
        option_mapping_consistency=(
            (
                None
                if sl_output.option_inference is None
                else sl_output.option_inference.option_id
            )
            == (
                None
                if en_output.option_inference is None
                else en_output.option_inference.option_id
            )
        ),
        citation_identity_consistency=(
            sl_output.cited_observation_ids == en_output.cited_observation_ids
            and (
                None
                if sl_output.option_inference is None
                else sl_output.option_inference.cited_observation_ids
            )
            == (
                None
                if en_output.option_inference is None
                else en_output.option_inference.cited_observation_ids
            )
            and {
                (item.key, item.cited_observation_ids)
                for item in sl_output.action_hypotheses
            }
            == {
                (item.key, item.cited_observation_ids)
                for item in en_output.action_hypotheses
            }
            and {
                (item.key, item.cited_observation_ids)
                for item in sl_output.motive_hypotheses
            }
            == {
                (item.key, item.cited_observation_ids)
                for item in en_output.motive_hypotheses
            }
        ),
        uncertainty_consistency=BilingualUncertaintyConsistencyV3(
            option=(
                sl_output.racio_reported_uncertainty.option_mapping
                == en_output.racio_reported_uncertainty.option_mapping
            ),
            motive=(
                sl_output.racio_reported_uncertainty.motive_interpretation
                == en_output.racio_reported_uncertainty.motive_interpretation
            ),
        ),
    )


__all__ = [
    "AcceptedActionSupportModeV3",
    "ActionGoldRoleV3",
    "ActionHypothesisAssessmentCodeV3",
    "ActionHypothesisAssessmentV3",
    "BilingualLayerConsistencyV3",
    "BilingualUncertaintyConsistencyV3",
    "EpistemicCaseGoldV3",
    "EpistemicGoldActionHypothesisV3",
    "EpistemicGoldMotiveHypothesisV3",
    "LegacyAmbiguousActionSourceV3",
    "MotiveHypothesisAssessmentCodeV3",
    "MotiveHypothesisAssessmentV3",
    "MotiveIdentifiabilityV3",
    "MotiveReferenceSupportModeV3",
    "OptionDeterminacyV3",
    "OptionMappingAssessmentV3",
    "RacioEpistemicBilingualEvaluationV3",
    "RacioEpistemicCaseEvaluationV3",
    "RequiredAbstentionAssessmentV3",
    "UnknownPreservationAssessmentV3",
    "UnknownPreservationV3",
    "evaluate_racio_epistemic_bilingual_pair_v3",
    "evaluate_racio_epistemic_case_v3",
]
