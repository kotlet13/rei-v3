"""Deterministic C5 bounded-software contract with explicit vector gold."""

from __future__ import annotations

import hashlib
import inspect
import json
import shutil
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id, sha256_hex
from ..instinkt.effect_compiler import compile_prediction_to_option_body_effect
from ..instinkt.effect_mapper import RuleBasedEmbodiedCueInterpreter
from ..instinkt.packets import (
    InstinktEffectSpec,
    bind_instinkt_effects,
    build_instinkt_packet,
)
from ..instinkt.processor import process_instinkt
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.instinkt import (
    BodyDelta,
    BodyDimension,
    BodyState,
    EmbodiedCueClass,
    InstinktCueAssertionStatus,
    InstinktCueEvidenceBinding,
    InstinktCueEvidenceCitation,
    InstinktCueLane,
    InstinktWorld,
    UnitDelta,
)
from ..models.scene import DecisionOption, EvidenceItem, SceneEvent


PositiveCellMode = Literal["sl_primary", "sl_alternate", "en"]
CaseExpectedStatus = Literal["selected", "abstained_tie"]
PolicyStatus = Literal[
    "selected",
    "abstained_tie",
    "abstained_no_options",
    "mapper_abstained",
    "mapper_error",
    "manual_error",
]
NegativeActualStatus = Literal[
    "mapper_abstained",
    "mapper_emitted_effect",
    "mapper_error",
]
NegativeControlKind = Literal[
    "unrelated_evidence",
    "unbound_cue",
    "mixed_valid_invalid_binding",
    "negated_evidence_en",
    "negated_evidence_sl",
    "negated_option_dont",
    "negated_option_cant",
    "negated_option_sl_ne",
    "distant_option_negation_en",
    "distant_option_negation_sl",
    "ambiguous_option",
    "keyword_trap",
    "metalinguistic_mention",
    "missing_information",
]

_POSITIVE_MODES = frozenset({"sl_primary", "sl_alternate", "en"})
_REQUIRED_NEGATIVE_KINDS = frozenset(
    {
        "unrelated_evidence",
        "unbound_cue",
        "mixed_valid_invalid_binding",
        "negated_evidence_en",
        "negated_evidence_sl",
        "negated_option_dont",
        "negated_option_cant",
        "negated_option_sl_ne",
        "distant_option_negation_en",
        "distant_option_negation_sl",
        "ambiguous_option",
        "keyword_trap",
        "metalinguistic_mention",
        "missing_information",
    }
)
_LANES: tuple[InstinktCueLane, ...] = (
    "physical_cues",
    "uncertainty_cues",
    "trust_cues",
    "boundary_cues",
    "attachment_cues",
    "scarcity_cues",
    "escape_cues",
    "explicit_body_cues",
)
BODY_MAPPER_REPORT_FILENAMES = (
    "body_mapper_evaluation.json",
    "manual_vs_auto.md",
)


class BodyMapperCueBindingGold(FrozenModel):
    lane: InstinktCueLane
    cue_class: EmbodiedCueClass
    cue: NonEmptyText
    assertion_status: InstinktCueAssertionStatus
    cited_text: NonEmptyText
    source_evidence_ids: tuple[NonEmptyId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        if self.source_evidence_ids != tuple(sorted(set(self.source_evidence_ids))):
            raise ValueError("Gold cue-binding evidence IDs must be sorted and unique")
        return self


class BodyMapperPositiveCellGold(FrozenModel):
    cell_id: NonEmptyId
    mode: PositiveCellMode
    language: LanguageCode
    evidence_content: NonEmptyText
    cue_bindings: tuple[BodyMapperCueBindingGold, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cell(self) -> Self:
        pairs = tuple(
            (item.lane, item.cue_class, item.cue) for item in self.cue_bindings
        )
        if len(set(pairs)) != len(pairs):
            raise ValueError(
                "Positive gold cue bindings must be unique by lane, class, and cue"
            )
        return self


class BodyMapperExpectedDeltaGold(FrozenModel):
    """One manually annotated vector coordinate and its explicit tolerance."""

    dimension: BodyDimension
    delta: UnitDelta
    tolerance: float = Field(ge=0.0, le=0.25, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_delta(self) -> Self:
        if self.delta == 0.0:
            raise ValueError("Expected vector coordinates must have a non-zero sign")
        return self


class BodyMapperManualEffectGold(FrozenModel):
    option_id: NonEmptyId
    body_deltas: tuple[BodyMapperExpectedDeltaGold, ...] = Field(min_length=1)
    base_predicted_loss: Score01
    base_recoverability: Score01

    @model_validator(mode="after")
    def validate_effect(self) -> Self:
        dimensions = tuple(item.dimension for item in self.body_deltas)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("Manual gold body-effect dimensions must be unique")
        return self


class BodyMapperGoldFamily(FrozenModel):
    family_id: NonEmptyId
    manual_expected_option_id: NonEmptyId
    expected_auto_status: CaseExpectedStatus
    manual_effects: tuple[BodyMapperManualEffectGold, ...] = Field(min_length=1)
    positive_cells: tuple[BodyMapperPositiveCellGold, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_family(self) -> Self:
        effect_ids = tuple(item.option_id for item in self.manual_effects)
        if len(set(effect_ids)) != len(effect_ids):
            raise ValueError("Manual gold effects must be unique by option")
        cell_ids = tuple(item.cell_id for item in self.positive_cells)
        if len(set(cell_ids)) != len(cell_ids):
            raise ValueError("Positive gold cell IDs must be unique")
        modes = {item.mode for item in self.positive_cells}
        if len(self.positive_cells) != 3 or modes != _POSITIVE_MODES:
            raise ValueError(
                "Each semantic family requires SL primary, SL alternate, and EN cells"
            )
        if self.manual_expected_option_id not in effect_ids:
            raise ValueError("Manual expected option lacks an explicit numeric effect")
        return self


class BodyMapperNegativeEvidenceGold(FrozenModel):
    evidence_id: NonEmptyId
    content: NonEmptyText
    confidence: Score01 = 1.0


class BodyMapperLaneCueGold(FrozenModel):
    lane: InstinktCueLane
    cue: NonEmptyText


class BodyMapperNegativeOptionGold(FrozenModel):
    option_id: NonEmptyId
    label: NonEmptyText
    description: str = ""


class BodyMapperNegativeControlGold(FrozenModel):
    cell_id: NonEmptyId
    control_kind: NegativeControlKind
    language: LanguageCode
    evidence: tuple[BodyMapperNegativeEvidenceGold, ...] = Field(min_length=1)
    options: tuple[BodyMapperNegativeOptionGold, ...] = Field(min_length=1)
    lane_cues: tuple[BodyMapperLaneCueGold, ...] = Field(min_length=1)
    cue_bindings: tuple[BodyMapperCueBindingGold, ...] = ()
    expected_status: Literal["mapper_abstained"] = "mapper_abstained"

    @model_validator(mode="after")
    def validate_control(self) -> Self:
        evidence_ids = tuple(item.evidence_id for item in self.evidence)
        option_ids = tuple(item.option_id for item in self.options)
        lane_cues = tuple((item.lane, item.cue) for item in self.lane_cues)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("Negative-control evidence IDs must be unique")
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("Negative-control option IDs must be unique")
        if len(set(lane_cues)) != len(lane_cues):
            raise ValueError("Negative-control lane cues must be unique")
        if any(
            not set(binding.source_evidence_ids).issubset(evidence_ids)
            for binding in self.cue_bindings
        ):
            raise ValueError("Negative cue binding cites evidence outside its cell")
        return self


class BodyMapperGoldSuite(FrozenModel):
    schema_version: Literal["rei-c5-instinkt-body-mapper-gold-v3"]
    status: Literal["implementation_hypothesis"]
    review_status: Literal["internal_non_blind"]
    gate_kind: Literal["bounded_software_contract"]
    training_export: Literal[False]
    model_generated_gold: Literal[False]
    source_fixture_root: NonEmptyText
    families: tuple[BodyMapperGoldFamily, ...] = Field(min_length=12)
    negative_controls: tuple[BodyMapperNegativeControlGold, ...] = Field(min_length=17)

    @model_validator(mode="after")
    def validate_suite(self) -> Self:
        family_ids = tuple(item.family_id for item in self.families)
        if family_ids != tuple(sorted(set(family_ids))):
            raise ValueError("Gold semantic families must use canonical unique order")
        cell_ids = tuple(
            cell.cell_id for family in self.families for cell in family.positive_cells
        )
        negative_ids = tuple(item.cell_id for item in self.negative_controls)
        if len(set(cell_ids)) != len(cell_ids):
            raise ValueError("Positive gold cell IDs must be globally unique")
        if negative_ids != tuple(sorted(set(negative_ids))):
            raise ValueError("Negative controls must use canonical unique cell order")
        kinds = {item.control_kind for item in self.negative_controls}
        if not _REQUIRED_NEGATIVE_KINDS.issubset(kinds):
            missing = sorted(_REQUIRED_NEGATIVE_KINDS - kinds)
            raise ValueError(f"C5 gold lacks required negative controls: {missing}")
        if sum(
            item.control_kind == "metalinguistic_mention"
            for item in self.negative_controls
        ) < 4:
            raise ValueError("C5 gold requires poster, film, title, and quoted mentions")
        return self


# Compatibility name retained for callers that imported the v1 family model.
BodyMapperGoldCase = BodyMapperGoldFamily


class BodyMapperOptionResult(FrozenModel):
    option_id: NonEmptyId
    prediction_id: NonEmptyId
    prediction_hash: HashDigest
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
    evidence_ids: tuple[NonEmptyId, ...]
    evidence_hashes: tuple[HashDigest, ...]
    source_evidence_ids: tuple[NonEmptyId, ...]
    cue_binding_ids: tuple[NonEmptyId, ...]
    cue_classes: tuple[EmbodiedCueClass, ...]
    actual_deltas: tuple[BodyDelta, ...]
    delta_count: int = Field(ge=0)
    abstains: bool
    compilation_id: NonEmptyId | None = None
    compilation_hash: HashDigest | None = None
    effect_id: NonEmptyId | None = None
    effect_hash: HashDigest | None = None
    error: NonEmptyText | None = None

    @model_validator(mode="after")
    def validate_option_result(self) -> Self:
        if len(self.evidence_ids) != len(self.evidence_hashes):
            raise ValueError("Prediction evidence IDs and hashes must align")
        if self.source_evidence_ids != tuple(sorted(set(self.source_evidence_ids))):
            raise ValueError("Prediction source-evidence IDs must be canonical")
        if self.cue_binding_ids != tuple(sorted(set(self.cue_binding_ids))):
            raise ValueError("Prediction cue-binding IDs must be canonical")
        dimensions = tuple(item.dimension for item in self.actual_deltas)
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("Actual body-effect vector dimensions must be unique")
        if self.delta_count != len(self.actual_deltas):
            raise ValueError("Actual body-effect vector and delta count must align")
        compilation = (
            self.compilation_id,
            self.compilation_hash,
            self.effect_id,
            self.effect_hash,
        )
        if self.abstains:
            if self.delta_count != 0 or any(item is not None for item in compilation):
                raise ValueError("Abstention cannot emit or compile an effect")
        elif self.delta_count == 0:
            raise ValueError("Non-abstaining prediction must emit a delta")
        elif self.error is None and any(item is None for item in compilation):
            raise ValueError("Successful non-abstention requires complete compilation")
        return self


class BodyMapperEffectVectorAgreement(FrozenModel):
    """Exact dimension/sign comparison with bounded per-coordinate magnitude error."""

    option_id: NonEmptyId
    expected_deltas: tuple[BodyMapperExpectedDeltaGold, ...] = Field(min_length=1)
    actual_deltas: tuple[BodyDelta, ...]
    expected_vector_hash: HashDigest
    actual_vector_hash: HashDigest
    dimensions_match: bool
    signs_match: bool
    magnitudes_within_tolerance: bool
    passes: bool

    @classmethod
    def compare(
        cls,
        *,
        expected: BodyMapperManualEffectGold,
        actual: BodyMapperOptionResult,
    ) -> "BodyMapperEffectVectorAgreement":
        expected_deltas = expected.body_deltas
        actual_deltas = actual.actual_deltas
        expected_by_dimension = {
            item.dimension: item for item in expected_deltas
        }
        actual_by_dimension = {item.dimension: item for item in actual_deltas}
        dimensions_match = set(expected_by_dimension) == set(actual_by_dimension)
        signs_match = dimensions_match and all(
            actual_by_dimension[dimension].delta != 0.0
            and (expected_by_dimension[dimension].delta > 0)
            == (actual_by_dimension[dimension].delta > 0)
            for dimension in expected_by_dimension
        )
        magnitudes_match = signs_match and all(
            abs(
                abs(actual_by_dimension[dimension].delta)
                - abs(expected_by_dimension[dimension].delta)
            )
            <= expected_by_dimension[dimension].tolerance + 1e-12
            for dimension in expected_by_dimension
        )
        return cls(
            option_id=expected.option_id,
            expected_deltas=expected_deltas,
            actual_deltas=actual_deltas,
            expected_vector_hash=sha256_hex(
                tuple(
                    BodyDelta(dimension=item.dimension, delta=item.delta)
                    for item in expected_deltas
                )
            ),
            actual_vector_hash=sha256_hex(actual_deltas),
            dimensions_match=dimensions_match,
            signs_match=signs_match,
            magnitudes_within_tolerance=magnitudes_match,
            passes=dimensions_match and signs_match and magnitudes_match,
        )

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        expected_by_dimension = {
            item.dimension: item for item in self.expected_deltas
        }
        actual_by_dimension = {item.dimension: item for item in self.actual_deltas}
        dimensions_match = set(expected_by_dimension) == set(actual_by_dimension)
        signs_match = dimensions_match and all(
            actual_by_dimension[dimension].delta != 0.0
            and (expected_by_dimension[dimension].delta > 0)
            == (actual_by_dimension[dimension].delta > 0)
            for dimension in expected_by_dimension
        )
        magnitudes_match = signs_match and all(
            abs(
                abs(actual_by_dimension[dimension].delta)
                - abs(expected_by_dimension[dimension].delta)
            )
            <= expected_by_dimension[dimension].tolerance + 1e-12
            for dimension in expected_by_dimension
        )
        expected_hash = sha256_hex(
            tuple(
                BodyDelta(dimension=item.dimension, delta=item.delta)
                for item in self.expected_deltas
            )
        )
        actual_hash = sha256_hex(self.actual_deltas)
        passed = dimensions_match and signs_match and magnitudes_match
        if (
            self.expected_vector_hash != expected_hash
            or self.actual_vector_hash != actual_hash
            or self.dimensions_match != dimensions_match
            or self.signs_match != signs_match
            or self.magnitudes_within_tolerance != magnitudes_match
            or self.passes != passed
        ):
            raise ValueError("Body-effect vector comparison differs from replay")
        return self


class BodyMapperPolicyScore(FrozenModel):
    option_id: NonEmptyId
    rollout_id: NonEmptyId
    rollout_hash: HashDigest
    protective_cost: float = Field(ge=0.0, le=1.5, allow_inf_nan=False)


class BodyMapperCaseResult(FrozenArtifactModel):
    schema_version: Literal["rei-c5-body-mapper-case-result-v3"] = (
        "rei-c5-body-mapper-case-result-v3"
    )
    case_result_id: NonEmptyId
    family_id: NonEmptyId
    cell_id: NonEmptyId
    mode: PositiveCellMode
    language: LanguageCode
    fixture_sha256: HashDigest
    scene_hash: HashDigest
    packet_id: NonEmptyId
    packet_hash: HashDigest
    cue_binding_ids: tuple[NonEmptyId, ...]
    cue_binding_hashes: tuple[HashDigest, ...]
    option_ids: tuple[NonEmptyId, ...]
    manual_expected_option_id: NonEmptyId
    expected_auto_status: CaseExpectedStatus
    manual_effect_ids: tuple[NonEmptyId, ...]
    manual_effect_hashes: tuple[HashDigest, ...]
    manual_policy_status: PolicyStatus
    manual_option_id: NonEmptyId | None
    manual_policy_id: NonEmptyId | None
    manual_policy_hash: HashDigest | None
    manual_config_id: NonEmptyId | None
    manual_config_hash: HashDigest | None
    manual_policy_scores: tuple[BodyMapperPolicyScore, ...]
    auto_policy_status: PolicyStatus
    auto_option_id: NonEmptyId | None
    auto_policy_id: NonEmptyId | None
    auto_policy_hash: HashDigest | None
    auto_config_id: NonEmptyId | None
    auto_config_hash: HashDigest | None
    auto_policy_scores: tuple[BodyMapperPolicyScore, ...]
    option_results: tuple[BodyMapperOptionResult, ...]
    effect_vector_agreements: tuple[BodyMapperEffectVectorAgreement, ...]
    evaluation_errors: tuple[NonEmptyText, ...]
    all_deltas_have_provenance: bool
    no_silent_defaults: bool
    effect_vectors_agree: bool
    manual_auto_agrees: bool
    passes: bool
    result_hash: HashDigest

    @classmethod
    def create(cls, **values: object) -> "BodyMapperCaseResult":
        option_results = values["option_results"]
        option_ids = values["option_ids"]
        vector_agreements = values["effect_vector_agreements"]
        errors = values["evaluation_errors"]
        assert isinstance(option_results, tuple)
        assert isinstance(option_ids, tuple)
        assert isinstance(vector_agreements, tuple)
        assert isinstance(errors, tuple)
        all_provenanced = all(
            item.delta_count == 0
            or (bool(item.source_evidence_ids) and bool(item.cue_binding_ids))
            for item in option_results
        )
        no_defaults = (
            not errors
            and tuple(item.option_id for item in option_results) == option_ids
            and all(
                (
                    item.abstains
                    and item.delta_count == 0
                    and item.compilation_id is None
                )
                or (
                    not item.abstains
                    and item.delta_count > 0
                    and item.compilation_id is not None
                    and item.error is None
                )
                for item in option_results
            )
        )
        expected = values["expected_auto_status"]
        expected_option = values["manual_expected_option_id"]
        if expected == "selected":
            agreement = (
                values["manual_policy_status"] == "selected"
                and values["auto_policy_status"] == "selected"
                and values["manual_option_id"] == expected_option
                and values["auto_option_id"] == expected_option
            )
        else:
            agreement = (
                values["manual_policy_status"] == "abstained_tie"
                and values["auto_policy_status"] == "abstained_tie"
                and values["manual_option_id"] is None
                and values["auto_option_id"] is None
            )
        vector_option_ids = tuple(item.option_id for item in vector_agreements)
        vectors_agree = vector_option_ids == option_ids and all(
            item.passes for item in vector_agreements
        )
        passed = all_provenanced and no_defaults and vectors_agree and agreement
        base = {
            "schema_version": "rei-c5-body-mapper-case-result-v3",
            **values,
            "all_deltas_have_provenance": all_provenanced,
            "no_silent_defaults": no_defaults,
            "effect_vectors_agree": vectors_agree,
            "manual_auto_agrees": agreement,
            "passes": passed,
        }
        result_id = content_id("body_mapper_case_result", base)
        payload = {"case_result_id": result_id, **base}
        return cls(**payload, result_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.option_ids != tuple(sorted(set(self.option_ids))):
            raise ValueError("Case option IDs must use canonical unique order")
        result_option_ids = tuple(item.option_id for item in self.option_results)
        if result_option_ids != tuple(sorted(set(result_option_ids))):
            raise ValueError("Case option results must use canonical unique order")
        if len(self.cue_binding_ids) != len(self.cue_binding_hashes):
            raise ValueError("Cue-binding IDs and hashes must align")
        if len(self.manual_effect_ids) != len(self.manual_effect_hashes):
            raise ValueError("Manual effect IDs and hashes must align")
        vector_option_ids = tuple(
            item.option_id for item in self.effect_vector_agreements
        )
        if vector_option_ids != tuple(sorted(set(vector_option_ids))):
            raise ValueError("Vector comparisons must use canonical option order")
        manual_score_ids = tuple(item.option_id for item in self.manual_policy_scores)
        auto_score_ids = tuple(item.option_id for item in self.auto_policy_scores)
        if manual_score_ids != tuple(sorted(set(manual_score_ids))):
            raise ValueError("Manual policy scores must use canonical option order")
        if auto_score_ids != tuple(sorted(set(auto_score_ids))):
            raise ValueError("Auto policy scores must use canonical option order")
        manual_lineage = (
            self.manual_policy_id,
            self.manual_policy_hash,
            self.manual_config_id,
            self.manual_config_hash,
        )
        auto_lineage = (
            self.auto_policy_id,
            self.auto_policy_hash,
            self.auto_config_id,
            self.auto_config_hash,
        )
        if self.manual_policy_status == "manual_error":
            if any(item is not None for item in manual_lineage) or manual_score_ids:
                raise ValueError("Manual error cannot publish policy lineage")
        elif (
            any(item is None for item in manual_lineage)
            or manual_score_ids != self.option_ids
        ):
            raise ValueError("Manual B8 result requires complete policy/config lineage")
        if self.auto_policy_status in {"mapper_abstained", "mapper_error"}:
            if any(item is not None for item in auto_lineage) or auto_score_ids:
                raise ValueError("Mapper failure cannot publish an auto policy")
        elif any(item is None for item in auto_lineage) or auto_score_ids != self.option_ids:
            raise ValueError("Auto B8 result requires complete policy/config lineage")
        all_provenanced = all(
            item.delta_count == 0
            or (bool(item.source_evidence_ids) and bool(item.cue_binding_ids))
            for item in self.option_results
        )
        no_defaults = (
            not self.evaluation_errors
            and result_option_ids == self.option_ids
            and all(
                (
                    item.abstains
                    and item.delta_count == 0
                    and item.compilation_id is None
                )
                or (
                    not item.abstains
                    and item.delta_count > 0
                    and item.compilation_id is not None
                    and item.error is None
                )
                for item in self.option_results
            )
        )
        if self.expected_auto_status == "selected":
            agreement = (
                self.manual_policy_status == "selected"
                and self.auto_policy_status == "selected"
                and self.manual_option_id == self.manual_expected_option_id
                and self.auto_option_id == self.manual_expected_option_id
            )
        else:
            agreement = (
                self.manual_policy_status == "abstained_tie"
                and self.auto_policy_status == "abstained_tie"
                and self.manual_option_id is None
                and self.auto_option_id is None
            )
        vectors_agree = vector_option_ids == self.option_ids and all(
            item.passes for item in self.effect_vector_agreements
        )
        if (
            self.all_deltas_have_provenance != all_provenanced
            or self.no_silent_defaults != no_defaults
            or self.effect_vectors_agree != vectors_agree
            or self.manual_auto_agrees != agreement
            or self.passes
            != (all_provenanced and no_defaults and vectors_agree and agreement)
        ):
            raise ValueError("Body-mapper case derived fields differ from replay")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"case_result_id", "result_hash"},
        )
        if self.case_result_id != content_id("body_mapper_case_result", id_payload):
            raise ValueError("Body-mapper case ID differs from canonical content")
        if self.result_hash != self.content_hash(
            exclude_fields=frozenset({"result_hash"})
        ):
            raise ValueError("Body-mapper case hash differs from canonical content")
        return self


class BodyMapperNegativeResult(FrozenArtifactModel):
    schema_version: Literal["rei-c5-body-mapper-negative-result-v2"] = (
        "rei-c5-body-mapper-negative-result-v2"
    )
    negative_result_id: NonEmptyId
    cell_id: NonEmptyId
    control_kind: NegativeControlKind
    language: LanguageCode
    scene_hash: HashDigest
    packet_id: NonEmptyId
    packet_hash: HashDigest
    cue_binding_ids: tuple[NonEmptyId, ...]
    cue_binding_hashes: tuple[HashDigest, ...]
    option_ids: tuple[NonEmptyId, ...]
    option_results: tuple[BodyMapperOptionResult, ...]
    evaluation_errors: tuple[NonEmptyText, ...]
    expected_status: Literal["mapper_abstained"]
    actual_status: NegativeActualStatus
    no_emitted_effect: bool
    passes: bool
    result_hash: HashDigest

    @classmethod
    def create(cls, **values: object) -> "BodyMapperNegativeResult":
        results = values["option_results"]
        option_ids = values["option_ids"]
        errors = values["evaluation_errors"]
        assert isinstance(results, tuple)
        assert isinstance(option_ids, tuple)
        assert isinstance(errors, tuple)
        complete = tuple(item.option_id for item in results) == option_ids
        no_effect = complete and all(
            item.abstains and item.delta_count == 0 and item.compilation_id is None
            for item in results
        )
        actual: NegativeActualStatus = (
            "mapper_error"
            if errors or not complete
            else "mapper_abstained"
            if no_effect
            else "mapper_emitted_effect"
        )
        passed = actual == values["expected_status"] and no_effect
        base = {
            "schema_version": "rei-c5-body-mapper-negative-result-v2",
            **values,
            "actual_status": actual,
            "no_emitted_effect": no_effect,
            "passes": passed,
        }
        result_id = content_id("body_mapper_negative_result", base)
        payload = {"negative_result_id": result_id, **base}
        return cls(**payload, result_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.option_ids != tuple(sorted(set(self.option_ids))):
            raise ValueError("Negative-control option IDs must be canonical")
        result_ids = tuple(item.option_id for item in self.option_results)
        if result_ids != tuple(sorted(set(result_ids))):
            raise ValueError("Negative-control results must be canonical")
        if len(self.cue_binding_ids) != len(self.cue_binding_hashes):
            raise ValueError("Negative cue-binding IDs and hashes must align")
        complete = result_ids == self.option_ids
        no_effect = complete and all(
            item.abstains and item.delta_count == 0 and item.compilation_id is None
            for item in self.option_results
        )
        actual: NegativeActualStatus = (
            "mapper_error"
            if self.evaluation_errors or not complete
            else "mapper_abstained"
            if no_effect
            else "mapper_emitted_effect"
        )
        if (
            self.actual_status != actual
            or self.no_emitted_effect != no_effect
            or self.passes != (actual == self.expected_status and no_effect)
        ):
            raise ValueError("Negative result derived fields differ from replay")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"negative_result_id", "result_hash"},
        )
        if self.negative_result_id != content_id(
            "body_mapper_negative_result", id_payload
        ):
            raise ValueError("Negative result ID differs from canonical content")
        if self.result_hash != self.content_hash(
            exclude_fields=frozenset({"result_hash"})
        ):
            raise ValueError("Negative result hash differs from canonical content")
        return self


class BodyMapperEvaluationReport(FrozenArtifactModel):
    schema_version: Literal["rei-c5-body-mapper-evaluation-v3"] = (
        "rei-c5-body-mapper-evaluation-v3"
    )
    report_id: NonEmptyId
    evaluator_revision: Literal["c5-v3"] = "c5-v3"
    gate_kind: Literal["bounded_software_contract"]
    gold_status: Literal["implementation_hypothesis"]
    review_status: Literal["internal_non_blind"]
    gold_sha256: HashDigest
    gold_suite_hash: HashDigest
    ruleset_id: NonEmptyId
    ruleset_hash: HashDigest
    mapper_parameter_names: tuple[NonEmptyId, ...]
    cases: tuple[BodyMapperCaseResult, ...]
    negative_controls: tuple[BodyMapperNegativeResult, ...]
    semantic_family_count: int = Field(ge=0)
    positive_cell_count: int = Field(ge=0)
    passing_case_count: int = Field(ge=0)
    negative_control_count: int = Field(ge=0)
    passing_negative_control_count: int = Field(ge=0)
    emitted_delta_count: int = Field(ge=0)
    provenanced_delta_count: int = Field(ge=0)
    effect_vector_count: int = Field(ge=0)
    passing_effect_vector_count: int = Field(ge=0)
    mapper_abstention_count: int = Field(ge=0)
    manual_auto_selected_agreement_count: int = Field(ge=0)
    character_leakage_count: int = Field(ge=0)
    silent_default_count: int = Field(ge=0)
    contract_violation_count: int = Field(ge=0)
    gate_passed: bool
    report_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        mapper: RuleBasedEmbodiedCueInterpreter,
        gold_suite: BodyMapperGoldSuite,
        gold_sha256: HashDigest,
        gold_suite_hash: HashDigest,
        cases: tuple[BodyMapperCaseResult, ...],
        negative_controls: tuple[BodyMapperNegativeResult, ...],
    ) -> "BodyMapperEvaluationReport":
        family_count = len({item.family_id for item in cases})
        emitted = sum(
            option.delta_count
            for result in (*cases, *negative_controls)
            for option in result.option_results
        )
        provenanced = sum(
            option.delta_count
            for result in (*cases, *negative_controls)
            for option in result.option_results
            if option.delta_count == 0
            or (option.source_evidence_ids and option.cue_binding_ids)
        )
        parameter_names = tuple(inspect.signature(mapper.infer_effects).parameters)
        leakage = sum(
            name in {"character", "character_profile", "authority", "profile"}
            for name in parameter_names
        )
        silent_defaults = sum(not item.no_silent_defaults for item in cases)
        failed_positive = sum(not item.passes for item in cases)
        failed_negative = sum(not item.passes for item in negative_controls)
        provenance_violations = emitted - provenanced
        vector_count = sum(len(item.effect_vector_agreements) for item in cases)
        passing_vectors = sum(
            agreement.passes
            for item in cases
            for agreement in item.effect_vector_agreements
        )
        violations = (
            failed_positive
            + failed_negative
            + leakage
            + silent_defaults
            + provenance_violations
        )
        modes_by_family: dict[str, set[str]] = {}
        for item in cases:
            modes_by_family.setdefault(item.family_id, set()).add(item.mode)
        coverage_ok = (
            family_count >= 12
            and len(cases) >= 36
            and all(modes == _POSITIVE_MODES for modes in modes_by_family.values())
            and len(negative_controls) >= len(_REQUIRED_NEGATIVE_KINDS)
            and _REQUIRED_NEGATIVE_KINDS.issubset(
                {item.control_kind for item in negative_controls}
            )
            and vector_count == sum(len(item.option_ids) for item in cases)
        )
        vector_gate_passed = vector_count > 0 and passing_vectors == vector_count
        base = {
            "schema_version": "rei-c5-body-mapper-evaluation-v3",
            "evaluator_revision": "c5-v3",
            "gate_kind": gold_suite.gate_kind,
            "gold_status": gold_suite.status,
            "review_status": gold_suite.review_status,
            "gold_sha256": gold_sha256,
            "gold_suite_hash": gold_suite_hash,
            "ruleset_id": mapper.ruleset.ruleset_id,
            "ruleset_hash": mapper.ruleset.ruleset_hash,
            "mapper_parameter_names": parameter_names,
            "cases": cases,
            "negative_controls": negative_controls,
            "semantic_family_count": family_count,
            "positive_cell_count": len(cases),
            "passing_case_count": sum(item.passes for item in cases),
            "negative_control_count": len(negative_controls),
            "passing_negative_control_count": sum(
                item.passes for item in negative_controls
            ),
            "emitted_delta_count": emitted,
            "provenanced_delta_count": provenanced,
            "effect_vector_count": vector_count,
            "passing_effect_vector_count": passing_vectors,
            "mapper_abstention_count": sum(
                item.auto_policy_status == "mapper_abstained" for item in cases
            )
            + sum(
                item.actual_status == "mapper_abstained"
                for item in negative_controls
            ),
            "manual_auto_selected_agreement_count": sum(
                item.manual_auto_agrees and item.expected_auto_status == "selected"
                for item in cases
            ),
            "character_leakage_count": leakage,
            "silent_default_count": silent_defaults,
            "contract_violation_count": violations,
            "gate_passed": coverage_ok and vector_gate_passed and violations == 0,
        }
        report_id = content_id("body_mapper_evaluation", base)
        payload = {"report_id": report_id, **base}
        return cls(**payload, report_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        case_ids = tuple(item.cell_id for item in self.cases)
        negative_ids = tuple(item.cell_id for item in self.negative_controls)
        if case_ids != tuple(sorted(set(case_ids))):
            raise ValueError("Positive report cells must use canonical unique order")
        if negative_ids != tuple(sorted(set(negative_ids))):
            raise ValueError("Negative report cells must use canonical unique order")
        family_count = len({item.family_id for item in self.cases})
        emitted = sum(
            option.delta_count
            for result in (*self.cases, *self.negative_controls)
            for option in result.option_results
        )
        provenanced = sum(
            option.delta_count
            for result in (*self.cases, *self.negative_controls)
            for option in result.option_results
            if option.delta_count == 0
            or (option.source_evidence_ids and option.cue_binding_ids)
        )
        leakage = sum(
            name in {"character", "character_profile", "authority", "profile"}
            for name in self.mapper_parameter_names
        )
        silent_defaults = sum(not item.no_silent_defaults for item in self.cases)
        vector_count = sum(
            len(item.effect_vector_agreements) for item in self.cases
        )
        passing_vectors = sum(
            agreement.passes
            for item in self.cases
            for agreement in item.effect_vector_agreements
        )
        violations = (
            sum(not item.passes for item in self.cases)
            + sum(not item.passes for item in self.negative_controls)
            + leakage
            + silent_defaults
            + (emitted - provenanced)
        )
        modes_by_family: dict[str, set[str]] = {}
        for item in self.cases:
            modes_by_family.setdefault(item.family_id, set()).add(item.mode)
        coverage_ok = (
            family_count >= 12
            and len(self.cases) >= 36
            and all(modes == _POSITIVE_MODES for modes in modes_by_family.values())
            and len(self.negative_controls) >= len(_REQUIRED_NEGATIVE_KINDS)
            and _REQUIRED_NEGATIVE_KINDS.issubset(
                {item.control_kind for item in self.negative_controls}
            )
            and vector_count == sum(len(item.option_ids) for item in self.cases)
        )
        vector_gate_passed = vector_count > 0 and passing_vectors == vector_count
        expected = {
            "semantic_family_count": family_count,
            "positive_cell_count": len(self.cases),
            "passing_case_count": sum(item.passes for item in self.cases),
            "negative_control_count": len(self.negative_controls),
            "passing_negative_control_count": sum(
                item.passes for item in self.negative_controls
            ),
            "emitted_delta_count": emitted,
            "provenanced_delta_count": provenanced,
            "effect_vector_count": vector_count,
            "passing_effect_vector_count": passing_vectors,
            "mapper_abstention_count": sum(
                item.auto_policy_status == "mapper_abstained" for item in self.cases
            )
            + sum(
                item.actual_status == "mapper_abstained"
                for item in self.negative_controls
            ),
            "manual_auto_selected_agreement_count": sum(
                item.manual_auto_agrees and item.expected_auto_status == "selected"
                for item in self.cases
            ),
            "character_leakage_count": leakage,
            "silent_default_count": silent_defaults,
            "contract_violation_count": violations,
            "gate_passed": coverage_ok and vector_gate_passed and violations == 0,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("Body-mapper report derived fields differ from replay")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"report_id", "report_hash"},
        )
        if self.report_id != content_id("body_mapper_evaluation", id_payload):
            raise ValueError("Body-mapper report ID differs from canonical content")
        if self.report_hash != self.content_hash(
            exclude_fields=frozenset({"report_hash"})
        ):
            raise ValueError("Body-mapper report hash differs from canonical content")
        return self


def _standard_body(identity: str) -> BodyState:
    return BodyState(
        body_state_id=f"{identity}__c5_body",
        energy=0.6,
        fatigue=0.3,
        pain=0.1,
        arousal=0.4,
        tension=0.4,
        physical_integrity=0.9,
        uncertainty=0.5,
        trust=0.6,
        attachment_security=0.6,
        resource_security=0.6,
        boundary_integrity=0.7,
        escape_availability=0.6,
        predictability=0.5,
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_body_mapper_gold(
    path: str | Path,
) -> tuple[BodyMapperGoldSuite, HashDigest]:
    raw = Path(path).read_bytes()
    suite = BodyMapperGoldSuite.model_validate_json(raw)
    return suite, hashlib.sha256(raw).hexdigest()


def _cue_bindings(
    bindings: tuple[BodyMapperCueBindingGold, ...],
    scene: SceneEvent,
) -> tuple[InstinktCueEvidenceBinding, ...]:
    scene_evidence = {item.evidence_id: item for item in scene.evidence}

    def bind(item: BodyMapperCueBindingGold) -> InstinktCueEvidenceBinding:
        citations: list[InstinktCueEvidenceCitation] = []
        for evidence_id in item.source_evidence_ids:
            evidence = scene_evidence.get(evidence_id)
            if evidence is None:
                raise ValueError(
                    f"Gold cue binding cites missing evidence {evidence_id!r}"
                )
            start = evidence.content.find(item.cited_text)
            if start < 0:
                raise ValueError(
                    f"Gold cited text is not an exact span in {evidence_id!r}"
                )
            citations.append(
                InstinktCueEvidenceCitation.create(
                    evidence=evidence,
                    start_char=start,
                    end_char=start + len(item.cited_text),
                )
            )
        return InstinktCueEvidenceBinding.create(
            lane=item.lane,
            cue_class=item.cue_class,
            cue=item.cue,
            assertion_status=item.assertion_status,
            citations=tuple(citations),
        )

    return tuple(
        sorted(
            (bind(item) for item in bindings),
            key=lambda item: item.binding_id,
        )
    )


def _lane_values(
    cues: tuple[BodyMapperLaneCueGold, ...],
) -> dict[InstinktCueLane, tuple[str, ...]]:
    values: dict[InstinktCueLane, list[str]] = {lane: [] for lane in _LANES}
    for item in cues:
        values[item.lane].append(item.cue)
    return {lane: tuple(items) for lane, items in values.items()}


def _positive_scene(
    base_scene: SceneEvent,
    cell: BodyMapperPositiveCellGold,
) -> SceneEvent:
    cited_ids = {
        evidence_id
        for binding in cell.cue_bindings
        for evidence_id in binding.source_evidence_ids
    }
    scene_ids = {item.evidence_id for item in base_scene.evidence}
    if not cited_ids.issubset(scene_ids):
        raise ValueError(f"Gold cell {cell.cell_id} cites evidence outside its fixture")
    evidence = tuple(
        EvidenceItem.model_validate(
            {
                **item.model_dump(mode="python", round_trip=True),
                "content": cell.evidence_content,
                "source_ref": f"c5-gold:{cell.cell_id}",
            }
        )
        for item in base_scene.evidence
    )
    return SceneEvent.model_validate(
        {
            **base_scene.model_dump(mode="python", round_trip=True),
            "raw_input": cell.evidence_content,
            "language": cell.language,
            "evidence": evidence,
        }
    )


def _negative_scene(control: BodyMapperNegativeControlGold) -> SceneEvent:
    return SceneEvent(
        event_id=f"{control.cell_id}__scene",
        raw_input=" ".join(item.content for item in control.evidence),
        language=control.language,
        evidence=tuple(
            EvidenceItem(
                evidence_id=item.evidence_id,
                modality="text",
                content=item.content,
                grounded=True,
                source_ref=f"c5-gold:{control.cell_id}",
                confidence=item.confidence,
                provenance_kind="supplied",
            )
            for item in control.evidence
        ),
        options=tuple(
            DecisionOption(
                option_id=item.option_id,
                label=item.label,
                description=item.description,
            )
            for item in control.options
        ),
    )


def _manual_specs(
    *,
    family: BodyMapperGoldFamily,
    evidence_ids: tuple[str, ...],
) -> tuple[InstinktEffectSpec, ...]:
    return tuple(
        InstinktEffectSpec(
            option_id=item.option_id,
            body_deltas=tuple(
                BodyDelta(dimension=delta.dimension, delta=delta.delta)
                for delta in item.body_deltas
            ),
            base_predicted_loss=item.base_predicted_loss,
            base_recoverability=item.base_recoverability,
            dominant_alarm=f"manual_gold:{family.family_id}:{item.option_id}",
            protected_targets=(f"manual_gold:{family.family_id}",),
            boundary_outcome="manual_gold_numeric_effect",
            trust_outcome="manual_gold_numeric_effect",
            attachment_outcome="manual_gold_numeric_effect",
            escape_outcome="manual_gold_numeric_effect",
            action_tendency="unknown",
            minimum_safety_condition="manual semantic-gold comparison only",
            triggering_evidence_ids=evidence_ids,
        )
        for item in family.manual_effects
    )


def _policy_scores(processing) -> tuple[BodyMapperPolicyScore, ...]:
    return tuple(
        BodyMapperPolicyScore(
            option_id=item.option_id,
            rollout_id=item.rollout_id,
            rollout_hash=item.rollout_hash,
            protective_cost=item.protective_cost,
        )
        for item in processing.policy.option_scores
    )


def _evaluate_options(
    *,
    mapper: RuleBasedEmbodiedCueInterpreter,
    scene: SceneEvent,
    packet,
    world: InstinktWorld,
    body: BodyState,
) -> tuple[tuple[BodyMapperOptionResult, ...], tuple[object, ...], tuple[str, ...]]:
    results: list[BodyMapperOptionResult] = []
    compilations: list[object] = []
    errors: list[str] = []
    for option in sorted(scene.options, key=lambda item: item.option_id):
        try:
            prediction = mapper.infer_effects(scene, packet, world, body, option)
        except Exception as exc:  # quality failure must remain in the report
            errors.append(
                f"{option.option_id}:prediction:{type(exc).__name__}:{exc}"
            )
            continue
        compilation = None
        compilation_error: str | None = None
        if not prediction.abstains:
            try:
                compilation = compile_prediction_to_option_body_effect(
                    prediction=prediction,
                    scene=scene,
                    packet=packet,
                    world=world,
                    body=body,
                    option=option,
                    ruleset=mapper.ruleset,
                    association_records=mapper.association_records,
                )
                compilations.append(compilation)
            except Exception as exc:  # quality failure must remain in the report
                compilation_error = (
                    f"{option.option_id}:compilation:{type(exc).__name__}:{exc}"
                )
                errors.append(compilation_error)
        source_evidence_ids = tuple(
            sorted(
                {
                    evidence_id
                    for item in prediction.evidence
                    for evidence_id in item.source_evidence_ids
                }
            )
        )
        cue_binding_ids = tuple(
            sorted(
                {
                    binding_id
                    for item in prediction.evidence
                    for binding_id in item.cue_binding_ids
                }
            )
        )
        results.append(
            BodyMapperOptionResult(
                option_id=option.option_id,
                prediction_id=prediction.prediction_id,
                prediction_hash=prediction.prediction_hash,
                source_scene_id=prediction.source_scene_id,
                source_scene_hash=prediction.source_scene_hash,
                source_packet_id=prediction.source_packet_id,
                source_packet_hash=prediction.source_packet_hash,
                source_world_id=prediction.source_world_id,
                source_world_hash=prediction.source_world_hash,
                source_body_state_id=prediction.source_body_state_id,
                source_body_state_hash=prediction.source_body_state_hash,
                ruleset_id=prediction.ruleset_id,
                ruleset_hash=prediction.ruleset_hash,
                mapper_id=prediction.mapper_id,
                mapper_revision=prediction.mapper_revision,
                evidence_ids=tuple(item.evidence_id for item in prediction.evidence),
                evidence_hashes=tuple(
                    item.evidence_hash for item in prediction.evidence
                ),
                source_evidence_ids=source_evidence_ids,
                cue_binding_ids=cue_binding_ids,
                cue_classes=tuple(item.cue_class for item in prediction.evidence),
                actual_deltas=prediction.combined_deltas,
                delta_count=len(prediction.combined_deltas),
                abstains=prediction.abstains,
                compilation_id=(
                    None if compilation is None else compilation.compilation_id
                ),
                compilation_hash=(
                    None if compilation is None else compilation.compilation_hash
                ),
                effect_id=(
                    None
                    if compilation is None
                    else compilation.option_body_effect.effect_id
                ),
                effect_hash=(
                    None
                    if compilation is None
                    else compilation.option_body_effect.effect_hash
                ),
                error=compilation_error,
            )
        )
    return tuple(results), tuple(compilations), tuple(sorted(errors))


def _evaluate_positive_cell(
    *,
    family: BodyMapperGoldFamily,
    cell: BodyMapperPositiveCellGold,
    base_scene: SceneEvent,
    fixture_sha256: str,
    mapper: RuleBasedEmbodiedCueInterpreter,
) -> BodyMapperCaseResult:
    scene = _positive_scene(base_scene, cell)
    option_ids = tuple(sorted(item.option_id for item in scene.options))
    effect_ids = {item.option_id for item in family.manual_effects}
    if effect_ids != set(option_ids):
        raise ValueError(f"Manual gold effects do not exactly cover {family.family_id}")
    body = _standard_body(cell.cell_id)
    world = InstinktWorld.create()
    bindings = _cue_bindings(cell.cue_bindings, scene)
    lane_cues = tuple(
        BodyMapperLaneCueGold(lane=item.lane, cue=item.cue)
        for item in cell.cue_bindings
    )
    packet = build_instinkt_packet(
        scene,
        body,
        **_lane_values(lane_cues),
        evidence_ids=tuple(sorted(item.evidence_id for item in scene.evidence)),
        cue_evidence_bindings=bindings,
    )
    manual_status: PolicyStatus
    manual_option_id: str | None = None
    manual_policy_id: str | None = None
    manual_policy_hash: str | None = None
    manual_config_id: str | None = None
    manual_config_hash: str | None = None
    manual_policy_scores: tuple[BodyMapperPolicyScore, ...] = ()
    manual_effect_ids: tuple[str, ...] = ()
    manual_effect_hashes: tuple[str, ...] = ()
    errors: list[str] = []
    try:
        manual_effects = bind_instinkt_effects(
            packet,
            _manual_specs(
                family=family,
                evidence_ids=tuple(sorted(item.evidence_id for item in scene.evidence)),
            ),
        )
        manual_effect_ids = tuple(item.effect_id for item in manual_effects)
        manual_effect_hashes = tuple(item.effect_hash for item in manual_effects)
        manual = process_instinkt(
            scene=scene,
            packet=packet,
            source_body_state=body,
            option_effects=manual_effects,
        )
        manual_status = manual.policy.status
        manual_option_id = manual.policy.selected_option_id
        manual_policy_id = manual.policy.policy_decision_id
        manual_policy_hash = manual.policy.policy_hash
        manual_config_id = manual.config.config_id
        manual_config_hash = manual.config.config_hash
        manual_policy_scores = _policy_scores(manual)
    except Exception as exc:  # invalid gold remains a visible evaluation failure
        manual_status = "manual_error"
        errors.append(f"manual:{type(exc).__name__}:{exc}")
    option_results, compilations, option_errors = _evaluate_options(
        mapper=mapper,
        scene=scene,
        packet=packet,
        world=world,
        body=body,
    )
    errors.extend(option_errors)
    manual_by_option = {
        item.option_id: item for item in family.manual_effects
    }
    vector_agreements = tuple(
        BodyMapperEffectVectorAgreement.compare(
            expected=manual_by_option[item.option_id],
            actual=item,
        )
        for item in option_results
        if item.option_id in manual_by_option
    )
    if option_errors:
        auto_status: PolicyStatus = "mapper_error"
        auto_option_id = None
        auto_policy_id = None
        auto_policy_hash = None
        auto_config_id = None
        auto_config_hash = None
        auto_policy_scores: tuple[BodyMapperPolicyScore, ...] = ()
    elif len(compilations) != len(scene.options):
        auto_status = "mapper_abstained"
        auto_option_id = None
        auto_policy_id = None
        auto_policy_hash = None
        auto_config_id = None
        auto_config_hash = None
        auto_policy_scores = ()
    else:
        auto = process_instinkt(
            scene=scene,
            packet=packet,
            source_body_state=body,
            option_effects=tuple(
                item.option_body_effect
                for item in sorted(
                    compilations,
                    key=lambda value: value.option_body_effect.option_id,
                )
            ),
        )
        auto_status = auto.policy.status
        auto_option_id = auto.policy.selected_option_id
        auto_policy_id = auto.policy.policy_decision_id
        auto_policy_hash = auto.policy.policy_hash
        auto_config_id = auto.config.config_id
        auto_config_hash = auto.config.config_hash
        auto_policy_scores = _policy_scores(auto)
    return BodyMapperCaseResult.create(
        family_id=family.family_id,
        cell_id=cell.cell_id,
        mode=cell.mode,
        language=cell.language,
        fixture_sha256=fixture_sha256,
        scene_hash=scene.scene_hash(),
        packet_id=packet.packet_id,
        packet_hash=packet.content_hash(),
        cue_binding_ids=tuple(item.binding_id for item in bindings),
        cue_binding_hashes=tuple(item.binding_hash for item in bindings),
        option_ids=option_ids,
        manual_expected_option_id=family.manual_expected_option_id,
        expected_auto_status=family.expected_auto_status,
        manual_effect_ids=manual_effect_ids,
        manual_effect_hashes=manual_effect_hashes,
        manual_policy_status=manual_status,
        manual_option_id=manual_option_id,
        manual_policy_id=manual_policy_id,
        manual_policy_hash=manual_policy_hash,
        manual_config_id=manual_config_id,
        manual_config_hash=manual_config_hash,
        manual_policy_scores=manual_policy_scores,
        auto_policy_status=auto_status,
        auto_option_id=auto_option_id,
        auto_policy_id=auto_policy_id,
        auto_policy_hash=auto_policy_hash,
        auto_config_id=auto_config_id,
        auto_config_hash=auto_config_hash,
        auto_policy_scores=auto_policy_scores,
        option_results=option_results,
        effect_vector_agreements=vector_agreements,
        evaluation_errors=tuple(sorted(errors)),
    )


def _evaluate_negative_control(
    *,
    control: BodyMapperNegativeControlGold,
    mapper: RuleBasedEmbodiedCueInterpreter,
) -> BodyMapperNegativeResult:
    scene = _negative_scene(control)
    body = _standard_body(control.cell_id)
    world = InstinktWorld.create()
    bindings = _cue_bindings(control.cue_bindings, scene)
    packet = build_instinkt_packet(
        scene,
        body,
        **_lane_values(control.lane_cues),
        evidence_ids=tuple(sorted(item.evidence_id for item in scene.evidence)),
        cue_evidence_bindings=bindings,
    )
    results, _, errors = _evaluate_options(
        mapper=mapper,
        scene=scene,
        packet=packet,
        world=world,
        body=body,
    )
    return BodyMapperNegativeResult.create(
        cell_id=control.cell_id,
        control_kind=control.control_kind,
        language=control.language,
        scene_hash=scene.scene_hash(),
        packet_id=packet.packet_id,
        packet_hash=packet.content_hash(),
        cue_binding_ids=tuple(item.binding_id for item in bindings),
        cue_binding_hashes=tuple(item.binding_hash for item in bindings),
        option_ids=tuple(sorted(item.option_id for item in scene.options)),
        option_results=results,
        evaluation_errors=errors,
        expected_status=control.expected_status,
    )


def evaluate_body_mapper(
    *,
    fixtures_root: str | Path,
    gold_path: str | Path,
    mapper: RuleBasedEmbodiedCueInterpreter | None = None,
) -> BodyMapperEvaluationReport:
    active_mapper = mapper or RuleBasedEmbodiedCueInterpreter()
    gold, gold_sha256 = load_body_mapper_gold(gold_path)
    root = Path(fixtures_root)
    cases: list[BodyMapperCaseResult] = []
    for family in gold.families:
        fixture_path = root / f"{family.family_id}.json"
        raw_family = json.loads(fixture_path.read_text(encoding="utf-8"))
        base_scene = SceneEvent.model_validate_json(
            json.dumps(raw_family["grounded_scene"], ensure_ascii=False)
        )
        fixture_hash = _file_sha256(fixture_path)
        for cell in family.positive_cells:
            cases.append(
                _evaluate_positive_cell(
                    family=family,
                    cell=cell,
                    base_scene=base_scene,
                    fixture_sha256=fixture_hash,
                    mapper=active_mapper,
                )
            )
    negatives = tuple(
        _evaluate_negative_control(control=item, mapper=active_mapper)
        for item in gold.negative_controls
    )
    return BodyMapperEvaluationReport.create(
        mapper=active_mapper,
        gold_suite=gold,
        gold_sha256=gold_sha256,
        gold_suite_hash=sha256_hex(gold),
        cases=tuple(sorted(cases, key=lambda item: item.cell_id)),
        negative_controls=tuple(sorted(negatives, key=lambda item: item.cell_id)),
    )


def render_body_mapper_report(
    report: BodyMapperEvaluationReport,
) -> dict[str, bytes]:
    """Render deterministic, dimension-preserving C5 acceptance artifacts."""

    json_payload = (
        json.dumps(
            report.model_dump(mode="json", round_trip=True),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    status = "PASS" if report.gate_passed else "FAIL"
    lines = [
        "# C5 Instinkt body-mapper manual-vs-auto report",
        "",
        f"Gate: **{status}**",
        "",
        (
            "This internal, non-blind deterministic evaluation is a bounded software "
            "contract. It compares complete manually annotated effect vectors first, "
            "then replays B8 policy decisions as a secondary check."
        ),
        "",
        f"- Gate kind: `{report.gate_kind}`",
        f"- Gold status: `{report.gold_status}`",
        f"- Review status: `{report.review_status}`",
        f"- Gold SHA-256: `{report.gold_sha256}`",
        f"- Ruleset: `{report.ruleset_id}` (`{report.ruleset_hash}`)",
        f"- Semantic families: {report.semantic_family_count}",
        f"- Positive cells: {report.passing_case_count}/{report.positive_cell_count}",
        (
            "- Negative controls: "
            f"{report.passing_negative_control_count}/{report.negative_control_count}"
        ),
        (
            "- Provenanced deltas: "
            f"{report.provenanced_delta_count}/{report.emitted_delta_count}"
        ),
        (
            "- Complete effect-vector agreement: "
            f"{report.passing_effect_vector_count}/{report.effect_vector_count}"
        ),
        f"- Character leakage: {report.character_leakage_count}",
        f"- Silent defaults: {report.silent_default_count}",
        f"- Contract violations: {report.contract_violation_count}",
        "",
        "| Cell | Mode | Manual | Auto | Expected | Vector | Provenance | Result |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for case in report.cases:
        lines.append(
            "| "
            + " | ".join(
                (
                    case.cell_id,
                    case.mode,
                    case.manual_option_id or case.manual_policy_status,
                    case.auto_option_id or case.auto_policy_status,
                    case.manual_expected_option_id
                    if case.expected_auto_status == "selected"
                    else case.expected_auto_status,
                    "yes" if case.effect_vectors_agree else "no",
                    "yes" if case.all_deltas_have_provenance else "no",
                    "pass" if case.passes else "fail",
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Negative controls",
            "",
            "| Cell | Control | Actual | Result |",
            "|---|---|---|---|",
        )
    )
    for control in report.negative_controls:
        lines.append(
            f"| {control.cell_id} | {control.control_kind} | "
            f"{control.actual_status} | {'pass' if control.passes else 'fail'} |"
        )
    lines.extend(
        (
            "",
            "## Interpretation boundary",
            "",
            (
                "A passing result validates only this transparent bounded software path. "
                "It is not medical evidence, a character assessment, or permission to "
                "turn missing information into an implicit body effect."
            ),
            "",
        )
    )
    return {
        "body_mapper_evaluation.json": json_payload,
        "manual_vs_auto.md": "\n".join(lines).encode("utf-8"),
    }


def _existing_symlink(path: Path) -> bool:
    return path.is_symlink()


def _preflight_path_chain(path: Path) -> None:
    for candidate in (path, *path.parents):
        if _existing_symlink(candidate):
            raise FileExistsError(f"C5 report path traverses a symlink: {candidate}")


def write_body_mapper_report(
    report: BodyMapperEvaluationReport,
    output_root: str | Path,
) -> tuple[Path, ...]:
    """Atomically publish one immutable C5 report after full path preflight."""

    rendered = render_body_mapper_report(report)
    requested_root = Path(output_root).expanduser().absolute()
    parent = requested_root.parent
    staging = parent / f".{requested_root.name}.{report.report_id}.tmp"
    destination_targets = tuple(requested_root / name for name in BODY_MAPPER_REPORT_FILENAMES)
    staging_targets = tuple(staging / name for name in BODY_MAPPER_REPORT_FILENAMES)
    _preflight_path_chain(requested_root)
    _preflight_path_chain(staging)
    if requested_root.exists() or requested_root.is_symlink():
        raise FileExistsError(f"C5 report destination already exists: {requested_root}")
    if staging.exists() or staging.is_symlink():
        raise FileExistsError(f"C5 report staging path already exists: {staging}")
    for path in (*destination_targets, *staging_targets):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"C5 report target already exists: {path}")
    parent.mkdir(parents=True, exist_ok=True)
    try:
        staging.mkdir()
        for name in BODY_MAPPER_REPORT_FILENAMES:
            with (staging / name).open("xb") as stream:
                stream.write(rendered[name])
        staging.replace(requested_root)
    except Exception:
        if staging.exists() and not staging.is_symlink():
            shutil.rmtree(staging)
        raise
    return destination_targets


__all__ = [
    "BODY_MAPPER_REPORT_FILENAMES",
    "BodyMapperCaseResult",
    "BodyMapperEffectVectorAgreement",
    "BodyMapperEvaluationReport",
    "BodyMapperExpectedDeltaGold",
    "BodyMapperGoldFamily",
    "BodyMapperGoldCase",
    "BodyMapperGoldSuite",
    "BodyMapperNegativeResult",
    "BodyMapperOptionResult",
    "BodyMapperPolicyScore",
    "evaluate_body_mapper",
    "load_body_mapper_gold",
    "render_body_mapper_report",
    "write_body_mapper_report",
]
