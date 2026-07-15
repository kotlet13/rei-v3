"""Deterministic C6 longitudinal evaluation over the real REI engine.

The corpus is human-authored.  The evaluator uses the checked-in deterministic
end-to-end request as a typed template, executes every cycle through
``ReiNativeEngine``, and keeps persistence in a create-only in-memory store so
that a 100-cycle acceptance run remains fast without bypassing orchestration.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import struct
from typing import Literal, Self
import zlib

from pydantic import Field, model_validator

from .. import ego as ego_api
from ..ego.motifs import MotifObservation, ThreeStageMotifEngine, normalize_motif_token
from ..ego.narrative_composition import diagnose_narrative_composition
from ..ego.trace_store import InMemoryEgoTraceStore
from ..ego.world_updates import (
    EmocioLongitudinalVisualSignal,
    EmocioWorldUpdate,
    EmocioWorldUpdater,
    InstinktLongitudinalBodySignal,
    InstinktWorldUpdate,
    InstinktWorldUpdater,
    RacioWorldUpdate,
    RacioWorldUpdater,
)
from ..emocio.vector_encoding import canonical_l2_float32_le_vector
from ..emocio.visual_valuation import BoundVisualEmbedding
from ..engine import ReiNativeCycleRequest, ReiNativeEngine
from ..governance.profiles import parse_character_profile
from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.character import CHARACTER_PROFILE_ORDER, CharacterProfileId
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.communication import AcceptanceMode
from ..models.ego import EgoCompositionSnapshot, EgoTrace, OutcomeRecord
from ..models.longitudinal import (
    LongitudinalEventStep,
    LongitudinalPersonState,
    LongitudinalScenario,
)
from ..models.emocio import ImageArtifact, ImaginedVisualArtifact
from ..models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPolicy,
    ProviderIdentity,
)
from ..models.rendering import (
    ImagePipelineSpec,
    ImageRenderBatchOutcome,
    ImageRenderItemOutcome,
    ImageRenderRequest,
)
from ..models.scene import EvidenceItem
from ..profile_matrix import build_matrix_acceptance_state
from ..persistence.artifacts import validate_stored_artifact
from ..providers.deterministic import build_deterministic_native_providers
from ..providers.native import DeterministicExecutionClock
from ..providers.protocols import (
    IMAGE_ENCODER_NO_FALLBACK_REASON,
    ImageEncodingRequest,
    ImageEncodingSpec,
    StoredArtifact,
    VerifiedImageEncoding,
    build_image_encoding_call_spec,
)


LONGITUDINAL_REPORT_FILENAMES: tuple[str, ...] = (
    "longitudinal_evaluation.json",
    "dimensions.md",
)
LONGITUDINAL_EVALUATOR_REVISION = "c6-v2"
MAX_LONGITUDINAL_CORPUS_BYTES = 2 * 1024 * 1024
MAX_LONGITUDINAL_TEMPLATE_BYTES = 4 * 1024 * 1024
MAX_LONGITUDINAL_REPORT_BYTES = 32 * 1024 * 1024
MAX_LONGITUDINAL_SEQUENCES = 64
MAX_LONGITUDINAL_STEP_CHARS = 4096
MAX_LONGITUDINAL_METADATA_CHARS = 1024
MOTIF_PRECISION_THRESHOLD = 1.0
_MOTIF_CLAIM_KINDS = frozenset(
    {"identity_motif", "relationship_pattern", "recurring_translation_error"}
)
_EXPECTED_WORLD_CHANGE_KEYS = frozenset(
    {"racio:timeline", "emocio:visual_memory", "instinkt:recovery"}
)
_FORBIDDEN_EGO_DECISION_NAMES = frozenset(
    {"choose", "decide", "decision", "mandate", "propose", "resolve", "vote"}
)


class LongitudinalCorpusSequence(FrozenModel):
    sequence_id: NonEmptyId
    title: NonEmptyText
    profile_id: CharacterProfileId
    acceptance_mode: AcceptanceMode
    reverse_option_order_until_step: int | None = Field(default=None, ge=1, le=30)
    expected_simulated_spoznanje_cycle_count: int = Field(ge=0, le=30)
    outcome_effect: NonEmptyText | None = None
    expected_motifs: tuple[NonEmptyText, ...] = Field(min_length=1)
    expected_translation_patterns: tuple[NonEmptyText, ...] = ()
    expected_world_changes: tuple[NonEmptyText, ...] = Field(min_length=1)
    steps: tuple[NonEmptyText, ...] = Field(min_length=10, max_length=30)

    @model_validator(mode="after")
    def validate_gold(self) -> Self:
        if len(self.title) > MAX_LONGITUDINAL_METADATA_CHARS:
            raise ValueError("C6 sequence title exceeds its text bound")
        if (
            self.outcome_effect is not None
            and len(self.outcome_effect) > MAX_LONGITUDINAL_METADATA_CHARS
        ):
            raise ValueError("C6 outcome-effect text exceeds its bound")
        for field_name in (
            "expected_motifs",
            "expected_translation_patterns",
            "expected_world_changes",
            "steps",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        for field_name in (
            "expected_motifs",
            "expected_translation_patterns",
            "expected_world_changes",
        ):
            values = getattr(self, field_name)
            if values != tuple(sorted(values)):
                raise ValueError(f"{field_name} must use canonical sorted order")
        if any(value != normalize_motif_token(value) for value in self.expected_motifs):
            raise ValueError("Expected C6 motifs must use public motif normalization")
        if set(self.expected_world_changes) != _EXPECTED_WORLD_CHANGE_KEYS:
            raise ValueError(
                "Every C6 sequence must expect all three modality-owned world changes"
            )
        if (
            self.reverse_option_order_until_step is not None
            and self.reverse_option_order_until_step > len(self.steps)
        ):
            raise ValueError("C6 option-order transition must fall inside the sequence")
        if self.expected_simulated_spoznanje_cycle_count > len(self.steps):
            raise ValueError("Expected simulated_spoznanje count exceeds cycle count")
        if any(len(value) > MAX_LONGITUDINAL_STEP_CHARS for value in self.steps):
            raise ValueError("C6 step text exceeds its bounded length")
        if any(
            len(value) > MAX_LONGITUDINAL_METADATA_CHARS
            for values in (
                self.expected_motifs,
                self.expected_translation_patterns,
                self.expected_world_changes,
            )
            for value in values
        ):
            raise ValueError("C6 expected metadata text exceeds its bound")
        return self


class LongitudinalCorpus(FrozenModel):
    schema_version: Literal["rei-c6-longitudinal-corpus-v1"] = (
        "rei-c6-longitudinal-corpus-v1"
    )
    human_authored: Literal[True]
    model_generated_gold: Literal[False]
    training_export: Literal[False]
    template_fixture: NonEmptyText
    sequences: tuple[LongitudinalCorpusSequence, ...] = Field(
        min_length=10,
        max_length=MAX_LONGITUDINAL_SEQUENCES,
    )

    @model_validator(mode="after")
    def validate_corpus(self) -> Self:
        ids = tuple(item.sequence_id for item in self.sequences)
        if len(set(ids)) != len(ids):
            raise ValueError("C6 sequence IDs must be unique")
        if len(self.sequences) < 10:
            raise ValueError("C6 corpus requires at least ten longitudinal sequences")
        return self


class LongitudinalSequenceResult(FrozenArtifactModel):
    schema_version: Literal["rei-c6-longitudinal-sequence-result-v2"] = (
        "rei-c6-longitudinal-sequence-result-v2"
    )
    sequence_result_id: NonEmptyId
    sequence_id: NonEmptyId
    title: NonEmptyText
    scenario_id: NonEmptyId
    scenario_hash: HashDigest
    profile_id: CharacterProfileId
    character_id: NonEmptyId
    acceptance_mode: AcceptanceMode
    cycle_count: int = Field(ge=10, le=30)
    measure_ids: tuple[NonEmptyId, ...] = Field(min_length=10, max_length=30)
    final_trace_hash: HashDigest
    final_snapshot_id: NonEmptyId
    final_snapshot_hash: HashDigest
    final_racio_world_id: NonEmptyId
    final_emocio_world_id: NonEmptyId
    final_instinkt_world_id: NonEmptyId
    append_only_verified: bool
    character_constant: bool
    projection_citations_valid: bool
    expected_history_consumption_cycles: int = Field(ge=1)
    observed_history_consumption_cycles: int = Field(ge=0)
    expected_world_transfer_cycles: int = Field(ge=1)
    observed_world_transfer_cycles: int = Field(ge=0)
    modality_specific_world_updates: bool
    character_identifiers_absent_from_world_updates: bool
    history_counterfactual_influence: bool
    projection_signal_integration_complete: bool
    verified_visual_signal_cycle_count: int = Field(ge=0)
    predicted_body_signal_cycle_count: int = Field(ge=0)
    measured_body_signal_cycle_count: int = Field(ge=0)
    world_change_counts: tuple[tuple[NonEmptyText, int], ...]
    expected_motifs: tuple[NonEmptyText, ...]
    observed_motifs: tuple[NonEmptyText, ...]
    motif_true_positive_count: int = Field(ge=0)
    motif_false_positive_count: int = Field(ge=0)
    motif_false_negative_count: int = Field(ge=0)
    motif_precision: Score01
    motif_recall: Score01
    natural_language_motif_authority_granted: Literal[False] = False
    expected_translation_patterns: tuple[NonEmptyText, ...]
    observed_translation_patterns: tuple[NonEmptyText, ...]
    translation_patterns_match: bool
    narrative_divergence_cycle_count: int = Field(ge=0)
    self_narrative_divergence_cycle_count: int = Field(ge=0)
    expected_simulated_spoznanje_cycle_count: int = Field(ge=0)
    simulated_spoznanje_cycle_count: int = Field(ge=0)
    persisted_cycle_count: int = Field(ge=0)
    passes: bool
    result_hash: HashDigest

    @classmethod
    def create(cls, **values: object) -> "LongitudinalSequenceResult":
        values = dict(values)
        values.pop("passes", None)
        values.setdefault("natural_language_motif_authority_granted", False)
        values["passes"] = cls._recompute_passes(values)
        base = {
            "schema_version": "rei-c6-longitudinal-sequence-result-v2",
            **values,
        }
        result_id = content_id("longitudinal_sequence_result", base)
        payload = {"sequence_result_id": result_id, **base}
        return cls(**payload, result_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if len(self.measure_ids) != self.cycle_count:
            raise ValueError("C6 result must expose one measure per cycle")
        if len(set(self.measure_ids)) != len(self.measure_ids):
            raise ValueError("C6 result measure IDs must be unique")
        if self.expected_history_consumption_cycles != self.cycle_count - 1:
            raise ValueError("C6 history expectation must cover cycles two onward")
        if self.expected_world_transfer_cycles != self.cycle_count - 1:
            raise ValueError("C6 world-transfer expectation must cover cycles two onward")
        if tuple(key for key, _ in self.world_change_counts) != tuple(
            sorted(_EXPECTED_WORLD_CHANGE_KEYS)
        ):
            raise ValueError("C6 world-change dimensions are incomplete or unordered")
        expected_motifs = set(self.expected_motifs)
        observed_motifs = set(self.observed_motifs)
        if (
            len(expected_motifs) != len(self.expected_motifs)
            or len(observed_motifs) != len(self.observed_motifs)
        ):
            raise ValueError("C6 expected/observed motifs must be unique")
        for field_name in (
            "expected_motifs",
            "observed_motifs",
            "expected_translation_patterns",
            "observed_translation_patterns",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values) or values != tuple(sorted(values)):
                raise ValueError(
                    f"C6 {field_name} must be unique and canonically sorted"
                )
        expected_counts = (
            len(expected_motifs & observed_motifs),
            len(observed_motifs - expected_motifs),
            len(expected_motifs - observed_motifs),
        )
        actual_counts = (
            self.motif_true_positive_count,
            self.motif_false_positive_count,
            self.motif_false_negative_count,
        )
        if actual_counts != expected_counts:
            raise ValueError("C6 motif counts differ from expected/observed sets")
        precision_denominator = (
            self.motif_true_positive_count + self.motif_false_positive_count
        )
        recall_denominator = (
            self.motif_true_positive_count + self.motif_false_negative_count
        )
        expected_precision = (
            self.motif_true_positive_count / precision_denominator
            if precision_denominator
            else 0.0
        )
        expected_recall = (
            self.motif_true_positive_count / recall_denominator
            if recall_denominator
            else 0.0
        )
        if (
            self.motif_precision != expected_precision
            or self.motif_recall != expected_recall
            or self.translation_patterns_match
            != (
                set(self.observed_translation_patterns)
                == set(self.expected_translation_patterns)
            )
        ):
            raise ValueError("C6 sequence derived metrics differ from their dimensions")
        values = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"schema_version", "sequence_result_id", "result_hash", "passes"},
        )
        if self.passes != self._recompute_passes(values):
            raise ValueError("C6 sequence passes flag differs from its dimensions")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"sequence_result_id", "result_hash"},
        )
        if self.sequence_result_id != content_id("longitudinal_sequence_result", base):
            raise ValueError("C6 sequence result ID differs from canonical content")
        payload = {"sequence_result_id": self.sequence_result_id, **base}
        if self.result_hash != sha256_hex(payload):
            raise ValueError("C6 sequence result hash differs from canonical content")
        return self

    @staticmethod
    def _recompute_passes(values: dict[str, object]) -> bool:
        cycles = int(values["cycle_count"])
        return bool(
            values["append_only_verified"]
            and values["character_constant"]
            and values["projection_citations_valid"]
            and values["observed_history_consumption_cycles"] == cycles - 1
            and values["observed_world_transfer_cycles"] == cycles - 1
            and values["modality_specific_world_updates"]
            and values["character_identifiers_absent_from_world_updates"]
            and values["history_counterfactual_influence"]
            and values["projection_signal_integration_complete"]
            and values["verified_visual_signal_cycle_count"] == cycles
            and values["predicted_body_signal_cycle_count"] == cycles
            and values["measured_body_signal_cycle_count"] == 0
            and all(count > 0 for _, count in values["world_change_counts"])
            and float(values["motif_precision"]) >= MOTIF_PRECISION_THRESHOLD
            and float(values["motif_recall"]) == 1.0
            and values["motif_false_positive_count"] == 0
            and values["motif_false_negative_count"] == 0
            and values["translation_patterns_match"]
            and values["simulated_spoznanje_cycle_count"]
            == values["expected_simulated_spoznanje_cycle_count"]
            and values["persisted_cycle_count"] == cycles
        )


class LongitudinalEvaluationReport(FrozenArtifactModel):
    schema_version: Literal["rei-c6-longitudinal-evaluation-v2"] = (
        "rei-c6-longitudinal-evaluation-v2"
    )
    report_id: NonEmptyId
    evaluator_revision: Literal["c6-v2"] = "c6-v2"
    gate_kind: Literal["bounded_software_contract"] = "bounded_software_contract"
    review_status: Literal["internal_non_blind"] = "internal_non_blind"
    gold_status: Literal["implementation_hypothesis"] = "implementation_hypothesis"
    motif_gate_kind: Literal["structured_tag_motif_stage_1"] = (
        "structured_tag_motif_stage_1"
    )
    legacy_outcome_scope: Literal[
        "evaluation_only_no_c5_outcome_learning_closure"
    ] = "evaluation_only_no_c5_outcome_learning_closure"
    measured_body_outcome_status: Literal["open_no_verified_c5_replay"] = (
        "open_no_verified_c5_replay"
    )
    visual_signal_scope: Literal[
        "post_cycle_internal_evaluation_not_source_cycle_processing"
    ] = "post_cycle_internal_evaluation_not_source_cycle_processing"
    instinkt_learning_scope: Literal[
        "prediction_sidecar_only_world_mutation_open_until_verified_c5_replay"
    ] = "prediction_sidecar_only_world_mutation_open_until_verified_c5_replay"
    corpus_hash: HashDigest
    corpus_sha256: HashDigest
    template_request_hash: HashDigest
    full_corpus: bool
    sequences: tuple[LongitudinalSequenceResult, ...]
    sequence_count: int = Field(ge=1)
    total_cycle_count: int = Field(ge=10)
    minimum_cycle_count: int = Field(ge=10)
    passing_sequence_count: int = Field(ge=0)
    append_only_sequence_count: int = Field(ge=0)
    character_constant_sequence_count: int = Field(ge=0)
    projection_citation_sequence_count: int = Field(ge=0)
    history_consumption_cycle_count: int = Field(ge=0)
    world_transfer_cycle_count: int = Field(ge=0)
    modality_specific_world_sequence_count: int = Field(ge=0)
    character_identifier_absence_sequence_count: int = Field(ge=0)
    history_counterfactual_influence_sequence_count: int = Field(ge=0)
    verified_visual_signal_cycle_count: int = Field(ge=0)
    predicted_body_signal_cycle_count: int = Field(ge=0)
    measured_body_signal_cycle_count: int = Field(ge=0)
    motif_precision_threshold: Score01 = MOTIF_PRECISION_THRESHOLD
    motif_true_positive_count: int = Field(ge=0)
    motif_false_positive_count: int = Field(ge=0)
    motif_false_negative_count: int = Field(ge=0)
    motif_precision: Score01
    motif_recall: Score01
    narrative_divergence_cycle_count: int = Field(ge=0)
    self_narrative_divergence_cycle_count: int = Field(ge=0)
    expected_simulated_spoznanje_cycle_count: int = Field(ge=0)
    simulated_spoznanje_cycle_count: int = Field(ge=0)
    ego_decision_api_absent: bool
    projection_signal_integration_complete: bool
    pre_governance_character_invariance: bool
    technical_gate_passed: bool
    semantic_authority_granted: Literal[False] = False
    gate_passed: bool
    report_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        corpus_hash: str,
        corpus_sha256: str,
        template_request_hash: str,
        full_corpus: bool,
        sequences: tuple[LongitudinalSequenceResult, ...],
        ego_decision_api_absent: bool,
        projection_signal_integration_complete: bool,
        pre_governance_character_invariance: bool,
    ) -> "LongitudinalEvaluationReport":
        sequences = tuple(sorted(sequences, key=lambda item: item.sequence_id))
        derived = cls._derive_aggregates(
            full_corpus=full_corpus,
            sequences=sequences,
            ego_decision_api_absent=ego_decision_api_absent,
            projection_signal_integration_complete=(
                projection_signal_integration_complete
            ),
            pre_governance_character_invariance=(
                pre_governance_character_invariance
            ),
        )
        base = {
            "schema_version": "rei-c6-longitudinal-evaluation-v2",
            "evaluator_revision": LONGITUDINAL_EVALUATOR_REVISION,
            "gate_kind": "bounded_software_contract",
            "review_status": "internal_non_blind",
            "gold_status": "implementation_hypothesis",
            "motif_gate_kind": "structured_tag_motif_stage_1",
            "legacy_outcome_scope": (
                "evaluation_only_no_c5_outcome_learning_closure"
            ),
            "measured_body_outcome_status": "open_no_verified_c5_replay",
            "visual_signal_scope": (
                "post_cycle_internal_evaluation_not_source_cycle_processing"
            ),
            "instinkt_learning_scope": (
                "prediction_sidecar_only_world_mutation_open_until_verified_c5_replay"
            ),
            "corpus_hash": corpus_hash,
            "corpus_sha256": corpus_sha256,
            "template_request_hash": template_request_hash,
            "full_corpus": full_corpus,
            "sequences": sequences,
            "ego_decision_api_absent": ego_decision_api_absent,
            "projection_signal_integration_complete": (
                projection_signal_integration_complete
            ),
            "pre_governance_character_invariance": (
                pre_governance_character_invariance
            ),
            "semantic_authority_granted": False,
            **derived,
        }
        report_id = content_id("longitudinal_evaluation", base)
        payload = {"report_id": report_id, **base}
        return cls(**payload, report_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.sequence_count != len(self.sequences):
            raise ValueError("C6 report sequence count differs from its rows")
        ids = tuple(item.sequence_id for item in self.sequences)
        if len(set(ids)) != len(ids):
            raise ValueError("C6 report sequence IDs must be unique")
        if ids != tuple(sorted(ids)):
            raise ValueError("C6 report sequences must use canonical ID order")
        if "aggregate_score" in type(self).model_fields:
            raise ValueError("C6 report must preserve dimensions without aggregate score")
        cold_sequences = tuple(
            LongitudinalSequenceResult.model_validate(
                item.model_dump(mode="python", round_trip=True)
            )
            for item in self.sequences
        )
        if cold_sequences != self.sequences:
            raise ValueError("C6 report sequence changed during cold validation")
        if self.projection_signal_integration_complete != all(
            item.projection_signal_integration_complete for item in self.sequences
        ):
            raise ValueError(
                "C6 report projection integration differs from its sequence rows"
            )
        expected = self._derive_aggregates(
            full_corpus=self.full_corpus,
            sequences=self.sequences,
            ego_decision_api_absent=self.ego_decision_api_absent,
            projection_signal_integration_complete=(
                self.projection_signal_integration_complete
            ),
            pre_governance_character_invariance=(
                self.pre_governance_character_invariance
            ),
        )
        actual = {key: getattr(self, key) for key in expected}
        if actual != expected:
            raise ValueError("C6 report aggregates differ from its sequence dimensions")
        base = self.model_dump(
            mode="python", round_trip=True, exclude={"report_id", "report_hash"}
        )
        if self.report_id != content_id("longitudinal_evaluation", base):
            raise ValueError("C6 report ID differs from canonical content")
        payload = {"report_id": self.report_id, **base}
        if self.report_hash != sha256_hex(payload):
            raise ValueError("C6 report hash differs from canonical content")
        return self

    @staticmethod
    def _derive_aggregates(
        *,
        full_corpus: bool,
        sequences: tuple[LongitudinalSequenceResult, ...],
        ego_decision_api_absent: bool,
        projection_signal_integration_complete: bool,
        pre_governance_character_invariance: bool,
    ) -> dict[str, object]:
        true_positive = sum(item.motif_true_positive_count for item in sequences)
        false_positive = sum(item.motif_false_positive_count for item in sequences)
        false_negative = sum(item.motif_false_negative_count for item in sequences)
        precision_denominator = true_positive + false_positive
        recall_denominator = true_positive + false_negative
        precision = (
            true_positive / precision_denominator if precision_denominator else 0.0
        )
        recall = true_positive / recall_denominator if recall_denominator else 0.0
        total_cycles = sum(item.cycle_count for item in sequences)
        expected_history = sum(
            item.expected_history_consumption_cycles for item in sequences
        )
        expected_transfer = sum(
            item.expected_world_transfer_cycles for item in sequences
        )
        passing = sum(item.passes for item in sequences)
        append_only = sum(item.append_only_verified for item in sequences)
        character_constant = sum(item.character_constant for item in sequences)
        projection_citations = sum(item.projection_citations_valid for item in sequences)
        history_consumption = sum(
            item.observed_history_consumption_cycles for item in sequences
        )
        world_transfer = sum(item.observed_world_transfer_cycles for item in sequences)
        modality_specific = sum(
            item.modality_specific_world_updates for item in sequences
        )
        character_identifier_absence = sum(
            item.character_identifiers_absent_from_world_updates
            for item in sequences
        )
        counterfactual = sum(
            item.history_counterfactual_influence for item in sequences
        )
        narrative_divergence = sum(
            item.narrative_divergence_cycle_count for item in sequences
        )
        self_narrative_divergence = sum(
            item.self_narrative_divergence_cycle_count for item in sequences
        )
        spoznanje = sum(item.simulated_spoznanje_cycle_count for item in sequences)
        expected_spoznanje = sum(
            item.expected_simulated_spoznanje_cycle_count for item in sequences
        )
        technical_gate = bool(
            full_corpus
            and len(sequences) >= 10
            and total_cycles >= 100
            and passing == len(sequences)
            and append_only == len(sequences)
            and character_constant == len(sequences)
            and projection_citations == len(sequences)
            and history_consumption == expected_history
            and world_transfer == expected_transfer
            and modality_specific == len(sequences)
            and character_identifier_absence == len(sequences)
            and counterfactual == len(sequences)
            and precision >= MOTIF_PRECISION_THRESHOLD
            and false_positive == 0
            and false_negative == 0
            and self_narrative_divergence > 0
            and ego_decision_api_absent
            and pre_governance_character_invariance
        )
        return {
            "sequence_count": len(sequences),
            "total_cycle_count": total_cycles,
            "minimum_cycle_count": min(item.cycle_count for item in sequences),
            "passing_sequence_count": passing,
            "append_only_sequence_count": append_only,
            "character_constant_sequence_count": character_constant,
            "projection_citation_sequence_count": projection_citations,
            "history_consumption_cycle_count": history_consumption,
            "world_transfer_cycle_count": world_transfer,
            "modality_specific_world_sequence_count": modality_specific,
            "character_identifier_absence_sequence_count": (
                character_identifier_absence
            ),
            "history_counterfactual_influence_sequence_count": counterfactual,
            "verified_visual_signal_cycle_count": sum(
                item.verified_visual_signal_cycle_count for item in sequences
            ),
            "predicted_body_signal_cycle_count": sum(
                item.predicted_body_signal_cycle_count for item in sequences
            ),
            "measured_body_signal_cycle_count": sum(
                item.measured_body_signal_cycle_count for item in sequences
            ),
            "motif_precision_threshold": MOTIF_PRECISION_THRESHOLD,
            "motif_true_positive_count": true_positive,
            "motif_false_positive_count": false_positive,
            "motif_false_negative_count": false_negative,
            "motif_precision": precision,
            "motif_recall": recall,
            "narrative_divergence_cycle_count": narrative_divergence,
            "self_narrative_divergence_cycle_count": self_narrative_divergence,
            "expected_simulated_spoznanje_cycle_count": expected_spoznanje,
            "simulated_spoznanje_cycle_count": spoznanje,
            "technical_gate_passed": technical_gate,
            "gate_passed": technical_gate and projection_signal_integration_complete,
        }


class _InMemoryEvaluationArtifactStore:
    """Minimal create-only ArtifactStore used only by deterministic evaluation."""

    def __init__(self) -> None:
        identity_payload = {
            "kind": "artifact_store",
            "implementation": "rei.evaluation.InMemoryEvaluationArtifactStore",
            "implementation_revision": LONGITUDINAL_EVALUATOR_REVISION,
        }
        self._identity = ProviderIdentity(
            provider_id=content_id("provider", identity_payload),
            **identity_payload,
        )
        self._by_path: dict[tuple[str, str], StoredArtifact] = {}
        self._content: dict[str, bytes] = {}

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def write_json(
        self,
        run_id: str,
        relative_path: str,
        artifact: object,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact:
        return self.write_bytes(
            run_id,
            relative_path,
            canonical_json_bytes(artifact),
            overwrite=overwrite,
        )

    def write_bytes(
        self,
        run_id: str,
        relative_path: str,
        content: bytes,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact:
        if overwrite:
            raise ValueError("C6 evaluation artifact store is create-only")
        if type(content) is not bytes:
            raise TypeError("C6 evaluation artifacts must be immutable bytes")
        key = (run_id, relative_path)
        if key in self._by_path:
            raise FileExistsError(f"C6 evaluation artifact already exists: {key!r}")
        digest = hashlib.sha256(content).hexdigest()
        base = {
            "schema_version": "rei-native-stored-artifact-v1",
            "run_id": run_id,
            "relative_path": relative_path,
            "content_sha256": digest,
            "size_bytes": len(content),
        }
        stored = StoredArtifact(storage_id=content_id("stored", base), **base)
        self._by_path[key] = stored
        self._content[stored.storage_id] = content
        return stored

    def read_bytes(self, storage_id: str) -> bytes:
        try:
            return self._content[storage_id]
        except KeyError as exc:
            raise FileNotFoundError(storage_id) from exc

    def read_verified(self, artifact: StoredArtifact) -> bytes:
        validate_stored_artifact(artifact)
        stored = self._by_path.get((artifact.run_id, artifact.relative_path))
        if stored != artifact:
            raise ValueError("C6 stored artifact is absent from the create-only inventory")
        content = self.read_bytes(artifact.storage_id)
        if (
            len(content) != artifact.size_bytes
            or hashlib.sha256(content).hexdigest() != artifact.content_sha256
        ):
            raise ValueError("C6 stored bytes differ from their inventory receipt")
        return content


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def _evaluation_png(scene_hash: str) -> tuple[bytes, tuple[float, ...]]:
    """Create one valid 1x1 PNG and a deterministic pixel-derived vector."""

    color = bytes.fromhex(scene_hash[:6]) + b"\xff"
    header = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(b"\x00" + color))
        + _png_chunk(b"IEND", b"")
    )
    raw_vector = tuple(float(value + 1) for value in color)
    return png, raw_vector


def _provider_identity(*, kind: Literal["image_renderer", "image_encoder"]) -> ProviderIdentity:
    payload = {
        "kind": kind,
        "implementation": f"rei.evaluation.c6.ByteBacked{kind.title().replace('_', '')}",
        "implementation_revision": LONGITUDINAL_EVALUATOR_REVISION,
        "uses_model": False,
    }
    return ProviderIdentity(provider_id=content_id("provider", payload), **payload)


def _successful_call(
    spec: ProviderCallSpec,
    *,
    output_artifact_id: str,
    started_at: object,
) -> ProviderCallRecord:
    finished_at = started_at + timedelta(microseconds=1)
    return ProviderCallRecord(
        call_id=spec.call_id,
        spec_hash=spec.content_hash(),
        request_id=spec.request_id,
        input_artifact_ids=spec.input_artifact_ids,
        provider=spec.provider,
        seed=spec.seed,
        parameters=spec.parameters,
        timeout_seconds=spec.timeout_seconds,
        started_at=started_at,
        primary_finished_at=finished_at,
        finished_at=finished_at,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=(output_artifact_id,),
    )


def _materialize_visual_signal(
    *,
    result: object,
    artifact_store: _InMemoryEvaluationArtifactStore,
    evaluation_seed: int,
) -> EmocioLongitudinalVisualSignal:
    """Build and cold-read a full C4 BoundVisualEmbedding for C6 evaluation."""

    visual_state = result.emocio_execution.visual_state
    scene_spec = visual_state.current_scene
    renderer = _provider_identity(kind="image_renderer")
    pipeline = ImagePipelineSpec(
        implementation="rei.evaluation.c6.ByteBackedPngPipeline",
        implementation_revision=LONGITUDINAL_EVALUATOR_REVISION,
    )
    request = ImageRenderRequest.create(
        mode="text_to_image",
        source_spec=scene_spec,
        provider=renderer,
        pipeline=pipeline,
        seed=evaluation_seed,
        prompt=f"C6 deterministic current-scene fixture {scene_spec.scene_id}",
        negative_prompt="",
        width=1,
        height=1,
        num_inference_steps=1,
        guidance_scale=0.0,
        conditioning_method="none",
    )
    render_spec = ProviderCallSpec(
        call_id=content_id("render_call", {"request_id": request.request_id}),
        request_id=request.request_id,
        input_artifact_ids=request.input_artifact_ids,
        provider=renderer,
        seed=request.seed,
        parameters=request.provider_parameters,
        timeout_seconds=5.0,
        fallback_policy=ProviderFallbackPolicy(
            mode="none",
            no_fallback_reason="C6 byte-backed renderer fails closed",
        ),
    )
    png_bytes, raw_vector = _evaluation_png(scene_spec.content_hash())
    image_sha = hashlib.sha256(png_bytes).hexdigest()
    image_id = content_id(
        "image",
        {"request_id": request.request_id, "content_sha256": image_sha},
    )
    image = ImageArtifact(
        image_id=image_id,
        request_id=request.request_id,
        render_call_id=render_spec.call_id,
        source_spec_id=scene_spec.scene_id,
        provider_id=renderer.provider_id,
        seed=evaluation_seed,
        input_spec_hash=scene_spec.content_hash(),
        content_sha256=image_sha,
        media_type="image/png",
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        path=f"emocio/images/{image_id}.png",
        width=1,
        height=1,
        generated_only_elements=("c6_deterministic_fixture_pixels",),
    )
    render_record = _successful_call(
        render_spec,
        output_artifact_id=image.image_id,
        started_at=result.request.started_at,
    )
    render_item = ImageRenderItemOutcome.create(
        request=request,
        call_spec=render_spec,
        call_record=render_record,
        artifact=image,
    )
    render_batch = ImageRenderBatchOutcome.create(
        source_spec_ids=(scene_spec.scene_id,),
        root_seed=evaluation_seed,
        status="succeeded",
        items=(render_item,),
    )
    imagined = ImaginedVisualArtifact(
        artifact_id=image.image_id,
        originating_scene_spec_id=scene_spec.scene_id,
        option_id=None,
        seed=image.seed,
        model_identity=renderer,
        ungrounded_elements=image.generated_only_elements,
    )
    vector_bytes, vector, vector_hash = canonical_l2_float32_le_vector(raw_vector)
    encoder = _provider_identity(kind="image_encoder")
    encoding_request = ImageEncodingRequest.create(
        image=image,
        provider=encoder,
        spec=ImageEncodingSpec(
            implementation="rei.evaluation.c6.PixelVectorEncoder",
            implementation_revision=LONGITUDINAL_EVALUATOR_REVISION,
            dimensions=len(vector),
        ),
    )
    encoding_spec = build_image_encoding_call_spec(
        encoding_request,
        timeout_seconds=5.0,
    )
    vector_ref = f"emocio/embeddings/{vector_hash}.f32"
    encoding_id = VerifiedImageEncoding.derive_id(
        request=encoding_request,
        vector_ref=vector_ref,
        vector_hash=vector_hash,
        dimensions=len(vector),
    )
    encoding_record = _successful_call(
        encoding_spec,
        output_artifact_id=encoding_id,
        started_at=result.request.started_at + timedelta(microseconds=2),
    )
    encoding = VerifiedImageEncoding.create(
        request=encoding_request,
        vector_ref=vector_ref,
        vector_hash=vector_hash,
        dimensions=len(vector),
        call_spec=encoding_spec,
        call=encoding_record,
    )
    observation = BoundVisualEmbedding.create(
        role="current",
        evaluation_seed=evaluation_seed,
        render_batch=render_batch,
        scene_spec=scene_spec,
        image=image,
        imagined=imagined,
        encoding=encoding,
        vector=vector,
    )
    image_receipt = artifact_store.write_bytes(
        result.request.run_id,
        image.path,
        png_bytes,
    )
    embedding_receipt = artifact_store.write_bytes(
        result.request.run_id,
        vector_ref,
        vector_bytes,
    )
    signal = EmocioLongitudinalVisualSignal.create(
        measure=result.ego_measure,
        bundle=result.native_bundle,
        visual_state=visual_state,
        observation=observation,
        image_storage=image_receipt,
        embedding_storage=embedding_receipt,
        image_bytes=png_bytes,
        embedding_bytes=vector_bytes,
        embedding_vector=vector,
    )
    return signal.validate_stored_bytes(artifact_store)


def _is_reparse_stat(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(attributes & reparse_flag)


def _reject_reparse_components(path: Path, *, label: str) -> None:
    absolute = path.expanduser().absolute()
    for component in reversed((absolute, *absolute.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"{label} path metadata is unavailable") from exc
        if _is_reparse_stat(metadata):
            raise ValueError(f"{label} path cannot traverse a link or reparse point")


def _read_bounded(path: str | Path, *, maximum_bytes: int, label: str) -> bytes:
    source = Path(path).expanduser()
    _reject_reparse_components(source, label=label)
    try:
        before = source.lstat()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular non-link file")
    if before.st_size <= 0 or before.st_size > maximum_bytes:
        raise ValueError(f"{label} exceeds its bounded file size")

    descriptor: int | None = None
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(source, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
            or opened.st_size != before.st_size
        ):
            raise ValueError(f"{label} changed before it was opened")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            payload = handle.read(maximum_bytes + 1)
        after = source.lstat()
    except OSError as exc:
        raise ValueError(f"{label} could not be read safely") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if (
        _is_reparse_stat(after)
        or not stat.S_ISREG(after.st_mode)
        or not os.path.samestat(opened, after)
        or len(payload) != opened.st_size
        or len(payload) > maximum_bytes
    ):
        raise ValueError(f"{label} changed or exceeded bounds while reading")
    return payload


def parse_longitudinal_corpus(payload: bytes) -> LongitudinalCorpus:
    """Parse one already-read C6 corpus so its hash and execution share bytes."""

    if not payload or len(payload) > MAX_LONGITUDINAL_CORPUS_BYTES:
        raise ValueError("C6 corpus bytes are empty or exceed the size bound")
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("C6 corpus bytes are not valid UTF-8 JSON") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("sequences"), list):
        raise ValueError("C6 corpus must contain a sequence list")
    sequences = tuple(
        LongitudinalCorpusSequence.model_validate(
            {
                **item,
                "expected_motifs": tuple(item["expected_motifs"]),
                "expected_translation_patterns": tuple(
                    item["expected_translation_patterns"]
                ),
                "expected_world_changes": tuple(item["expected_world_changes"]),
                "steps": tuple(item["steps"]),
            }
        )
        for item in raw["sequences"]
    )
    return LongitudinalCorpus.model_validate({**raw, "sequences": sequences})


def load_longitudinal_corpus(path: str | Path) -> LongitudinalCorpus:
    payload = _read_bounded(
        path,
        maximum_bytes=MAX_LONGITUDINAL_CORPUS_BYTES,
        label="C6 corpus",
    )
    return parse_longitudinal_corpus(payload)


def _content_addressed_outcome(
    *,
    event_id: str,
    recorded_at: object,
    observed_effect: str,
    evidence_id: str,
) -> OutcomeRecord:
    base = {
        "schema_version": "rei-native-outcome-record-v1",
        "event_id": event_id,
        "recorded_at": recorded_at,
        "source": "external_observation",
        "observed_effects": (observed_effect,),
        "evidence_ids": (evidence_id,),
    }
    return OutcomeRecord(outcome_id=content_id("outcome", base), **base)


def _build_scenario(
    template: ReiNativeCycleRequest,
    corpus_sequence: LongitudinalCorpusSequence,
) -> LongitudinalScenario:
    character = parse_character_profile(
        corpus_sequence.profile_id,
        character_id=f"c6_character_{corpus_sequence.sequence_id}",
    )
    acceptance = build_matrix_acceptance_state(corpus_sequence.acceptance_mode)
    ego_id = f"c6_ego_{corpus_sequence.sequence_id}"
    person = LongitudinalPersonState.create(
        ego_id=ego_id,
        structural_character=character,
        acceptance_state=acceptance,
        racio_world=template.racio_world,
        emocio_world=template.emocio_world,
        instinkt_world=template.instinkt_world,
        body_state=template.body_state,
    )
    steps: list[LongitudinalEventStep] = []
    for index, prompt in enumerate(corpus_sequence.steps):
        event_id = f"c6_{corpus_sequence.sequence_id}_{index:02d}"
        evidence_base = {
            "schema_version": "rei-native-evidence-v1",
            "modality": "text",
            "content": prompt,
            "grounded": True,
            "source_ref": (
                f"c6-corpus:{corpus_sequence.sequence_id}:step:{index:02d}"
            ),
            "confidence": 1.0,
            "provenance_kind": "supplied",
            "inferred_by": None,
        }
        step_evidence = EvidenceItem(
            evidence_id=content_id("evidence", evidence_base),
            **evidence_base,
        )
        scene = template.scene.model_copy(
            update={
                "event_id": event_id,
                "raw_input": f"{prompt} {template.scene.raw_input}",
                "evidence": (*template.scene.evidence, step_evidence),
                "options": (
                    tuple(reversed(template.scene.options))
                    if corpus_sequence.reverse_option_order_until_step is not None
                    and index < corpus_sequence.reverse_option_order_until_step
                    else template.scene.options
                ),
            }
        )
        outcome = None
        mode: Literal["none", "external_observation"] = "none"
        if corpus_sequence.outcome_effect is not None:
            mode = "external_observation"
            outcome = _content_addressed_outcome(
                event_id=event_id,
                recorded_at=template.started_at + timedelta(seconds=index),
                observed_effect=corpus_sequence.outcome_effect,
                evidence_id=step_evidence.evidence_id,
            )
        steps.append(
            LongitudinalEventStep.create(
                sequence_index=index,
                scene=scene,
                expected_outcome_mode=mode,
                external_outcome=outcome,
            )
        )
    return LongitudinalScenario.create(
        sequence_id=corpus_sequence.sequence_id,
        initial_person_state=person,
        steps=tuple(steps),
        expected_motifs=tuple(
            dict.fromkeys(
                (
                    *corpus_sequence.expected_motifs,
                    *(
                        normalize_motif_token(value)
                        for value in corpus_sequence.expected_translation_patterns
                    ),
                )
            )
        ),
        expected_translation_patterns=corpus_sequence.expected_translation_patterns,
        expected_world_changes=corpus_sequence.expected_world_changes,
    )


def build_longitudinal_scenarios(
    *,
    corpus_path: str | Path,
    template_fixture_path: str | Path,
) -> tuple[LongitudinalScenario, ...]:
    corpus = load_longitudinal_corpus(corpus_path)
    template = ReiNativeCycleRequest.model_validate_json(
        _read_bounded(
            template_fixture_path,
            maximum_bytes=MAX_LONGITUDINAL_TEMPLATE_BYTES,
            label="C6 template fixture",
        )
    )
    return tuple(_build_scenario(template, item) for item in corpus.sequences)


def _projection_citations_are_valid(result: object) -> bool:
    trace = result.ego_trace
    allowed = {measure.measure_id for measure in trace.measures}
    projections = result.projections
    return all(
        projection.through_measure_id in allowed
        and set(projection.evidence_measure_ids).issubset(allowed)
        and all(
            set(claim.evidence_measure_ids).issubset(allowed)
            for claim in projection.sourced_claims
        )
        for projection in projections
    )


def _history_was_consumed(result: object, previous_result: object) -> bool:
    prior = result.prior_projections
    if prior is None:
        return False
    packet_links = (
        result.racio_packet.previous_racio_projection_ids
        == (prior.racio.projection_id,)
        and result.racio_packet.previous_racio_projection_hashes
        == (prior.racio.projection_hash,)
        and result.emocio_packet.previous_emocio_projection_ids
        == (prior.emocio.projection_id,)
        and result.emocio_packet.previous_emocio_projection_hashes
        == (prior.emocio.projection_hash,)
        and result.instinkt_packet.previous_instinkt_projection_ids
        == (prior.instinkt.projection_id,)
        and result.instinkt_packet.previous_instinkt_projection_hashes
        == (prior.instinkt.projection_hash,)
    )
    provider_links = (
        result.racio_packet.packet_id
        in result.racio_execution.call_spec.input_artifact_ids
        and result.emocio_packet.packet_id
        in result.emocio_execution.call_spec.input_artifact_ids
        and result.instinkt_packet.packet_id
        in result.instinkt_execution.call_spec.input_artifact_ids
    )
    emocio_signals = result.request.historical_emocio_signals
    instinkt_signals = result.request.historical_instinkt_signals
    if not emocio_signals or not instinkt_signals:
        return False
    visual_history = prior.emocio.visual_history
    body_history = prior.instinkt.body_history
    if (
        len(visual_history) != len(emocio_signals)
        or len(body_history) != len(instinkt_signals)
        or prior.emocio.visual_history_status != "complete"
        or prior.instinkt.body_history_status != "complete"
    ):
        return False
    sidecar_links = all(
        reference.source_signal_id == signal.signal_id
        and reference.source_signal_hash == signal.signal_hash
        and reference.source_run_id == signal.source_run_id
        and reference.source_measure_id == signal.source_measure_id
        and reference.source_measure_hash == signal.source_measure_hash
        and reference.source_bundle_id == signal.source_bundle_id
        and reference.source_bundle_hash == signal.source_bundle_hash
        for reference, signal in zip(visual_history, emocio_signals, strict=True)
    ) and all(
        reference.source_signal_id == signal.signal_id
        and reference.source_signal_hash == signal.signal_hash
        and reference.source_measure_id == signal.source_measure_id
        and reference.source_measure_hash == signal.source_measure_hash
        and reference.source_bundle_id == signal.source_bundle_id
        and reference.source_bundle_hash == signal.source_bundle_hash
        for reference, signal in zip(body_history, instinkt_signals, strict=True)
    )
    latest_links = (
        visual_history[-1].source_measure_id
        == previous_result.ego_measure.measure_id
        and body_history[-1].source_measure_id
        == previous_result.ego_measure.measure_id
        and emocio_signals[-1].source_measure_id
        == previous_result.ego_measure.measure_id
        and instinkt_signals[-1].source_measure_id
        == previous_result.ego_measure.measure_id
    )
    return (
        result.prior_snapshot == previous_result.composition_snapshot
        and prior.racio.through_measure_id == previous_result.ego_measure.measure_id
        and prior.emocio.through_measure_id == previous_result.ego_measure.measure_id
        and prior.instinkt.through_measure_id == previous_result.ego_measure.measure_id
        and packet_links
        and provider_links
        and sidecar_links
        and latest_links
    )


def _native_semantic_fingerprint(result: object) -> tuple[object, ...]:
    racio = result.native_bundle.racio
    emocio = result.native_bundle.emocio
    instinkt = result.native_bundle.instinkt
    decisive = next(
        (
            item
            for item in result.instinkt_execution.rollouts
            if item.rollout_id == instinkt.decisive_rollout_id
        ),
        None,
    )
    return (
        (
            racio.option_id,
            racio.facts_used,
            racio.causal_sequence,
            racio.uncertainty,
        ),
        (
            emocio.option_id,
            emocio.desired_transformation,
            emocio.main_obstacle,
            emocio.action_tendency,
            emocio.valuation_dimensions,
        ),
        (
            instinkt.option_id,
            instinkt.dominant_alarm,
            instinkt.danger_claims,
            instinkt.protected_targets,
            None if decisive is None else decisive.recoverability,
            None if decisive is None else decisive.association_match_ids,
        ),
    )


def _history_counterfactual_changed_native_semantics(
    *,
    request: ReiNativeCycleRequest,
    history_result: object,
    initial_state: LongitudinalPersonState,
) -> bool:
    """Compare the same current scene/character with accumulated history removed."""

    counterfactual = request.model_copy(
        update={
            "run_id": f"{request.run_id}-no-history-counterfactual",
            "ego_id": f"{request.ego_id}-no-history-counterfactual",
            "racio_world": initial_state.racio_world,
            "emocio_world": initial_state.emocio_world,
            "instinkt_world": initial_state.instinkt_world,
            "body_state": initial_state.body_state,
            "historical_bundles": (),
            "historical_emocio_signals": (),
            "historical_instinkt_signals": (),
        }
    )
    if (
        counterfactual.scene != request.scene
        or counterfactual.character != request.character
    ):
        raise ValueError("C6 history counterfactual changed scene or character")
    no_history = ReiNativeEngine(
        artifact_store=_InMemoryEvaluationArtifactStore(),
        ego_trace_store=InMemoryEgoTraceStore(),
        providers=build_deterministic_native_providers(),
        clock=DeterministicExecutionClock(counterfactual.started_at),
    ).run_cycle(counterfactual)
    return _native_semantic_fingerprint(history_result) != _native_semantic_fingerprint(
        no_history
    )


def _world_updates_are_modality_specific(
    racio_update: RacioWorldUpdate,
    emocio_update: EmocioWorldUpdate,
    instinkt_update: InstinktWorldUpdate,
) -> bool:
    owned_fields = (
        {
            "fact_additions",
            "explicit_belief_additions",
            "causal_link_additions",
            "timeline_additions",
            "commitment_additions",
            "self_narrative_additions",
        },
        {
            "visual_memory_additions",
            "desired_scene_additions",
            "broken_scene_additions",
            "social_identity_motif_additions",
            "attraction_pattern_additions",
            "motor_pattern_additions",
        },
        {
            "association_additions",
            "trusted_pattern_additions",
            "threat_pattern_additions",
            "attachment_object_additions",
            "unresolved_loss_additions",
            "boundary_pattern_additions",
            "recovery_pattern_additions",
        },
    )
    actual_fields = tuple(
        set(type(item).model_fields)
        for item in (racio_update, emocio_update, instinkt_update)
    )
    schema_is_modality_specific = (
        all(owned.issubset(actual) for owned, actual in zip(owned_fields, actual_fields))
        and all("summary" not in field for fields in actual_fields for field in fields)
        and owned_fields[0].isdisjoint(owned_fields[1] | owned_fields[2])
        and owned_fields[1].isdisjoint(owned_fields[2])
    )
    expected_social_positions = set(
        emocio_update.visual_signal.social_position_references
    )
    social_position_is_exact_and_stored = bool(expected_social_positions) and (
        expected_social_positions.issubset(
            set(emocio_update.updated_world.social_identity_motifs)
        )
        and set(emocio_update.social_identity_motif_additions).issubset(
            expected_social_positions
        )
    )
    rollout = instinkt_update.body_signal.selected_rollout
    association_lineage_is_exact = rollout.association_match_ids == tuple(
        match.match_id for match in rollout.association_matches
    )
    prediction_sidecar_is_complete = (
        instinkt_update.body_signal.epistemic_status == "predicted_rollout"
        and instinkt_update.body_signal.measured_outcome_update is None
        and instinkt_update.body_before == instinkt_update.body_signal.body_before
        and instinkt_update.predicted_body_after
        == instinkt_update.body_signal.predicted_body_after
        and instinkt_update.predicted_recoverability
        == instinkt_update.body_signal.predicted_recoverability
        and instinkt_update.predicted_body_after.trust
        == instinkt_update.body_signal.predicted_body_after.trust
        and rollout.predicted_loss >= 0.0
        and bool(rollout.trust_outcome.strip())
        and association_lineage_is_exact
        and instinkt_update.recovery_pattern_additions
        == (instinkt_update.body_signal.recovery_reference,)
    )
    prediction_is_not_promoted_to_measured_world_state = (
        instinkt_update.association_additions == ()
        and instinkt_update.trusted_pattern_additions == ()
        and instinkt_update.unresolved_loss_additions == ()
        and instinkt_update.updated_world.associations
        == instinkt_update.source_world.associations
        and instinkt_update.updated_world.trusted_patterns
        == instinkt_update.source_world.trusted_patterns
        and instinkt_update.updated_world.unresolved_losses
        == instinkt_update.source_world.unresolved_losses
    )
    racio_self_narrative_is_stored = bool(racio_update.self_narrative_additions) and set(
        racio_update.self_narrative_additions
    ).issubset(set(racio_update.updated_world.explicit_beliefs))
    return (
        schema_is_modality_specific
        and racio_self_narrative_is_stored
        and social_position_is_exact_and_stored
        and prediction_sidecar_is_complete
        and prediction_is_not_promoted_to_measured_world_state
    )


def _world_update_tokens_exclude_character_identifiers(
    updates: tuple[object, object, object],
    *,
    character_id: str,
    profile_id: str,
) -> bool:
    token_fields = (
        (
            "fact_additions",
            "explicit_belief_additions",
            "causal_link_additions",
            "timeline_additions",
            "commitment_additions",
            "self_narrative_additions",
        ),
        (
            "visual_memory_additions",
            "desired_scene_additions",
            "broken_scene_additions",
            "social_identity_motif_additions",
            "attraction_pattern_additions",
            "motor_pattern_additions",
        ),
        (
            "trusted_pattern_additions",
            "threat_pattern_additions",
            "attachment_object_additions",
            "unresolved_loss_additions",
            "boundary_pattern_additions",
            "recovery_pattern_additions",
        ),
    )
    forbidden = (character_id.casefold(), profile_id.casefold())
    return all(
        not any(value and value in token.casefold() for value in forbidden)
        for update, fields in zip(updates, token_fields, strict=True)
        for field in fields
        for token in getattr(update, field)
    )


def _structured_motifs(
    snapshot: EgoCompositionSnapshot,
) -> tuple[str, ...]:
    observations = tuple(
        MotifObservation.create(motif_token=claim.text, measure_id=measure_id)
        for claim in snapshot.sourced_claims
        if claim.kind in _MOTIF_CLAIM_KINDS
        for measure_id in claim.evidence_measure_ids
    )
    candidates = ThreeStageMotifEngine().derive_structured(observations)
    return tuple(sorted({item.canonical_motif for item in candidates}))


def _ego_decision_api_is_absent() -> bool:
    def exposes_decision_surface(name: str) -> bool:
        normalized = name.casefold()
        return any(token in normalized for token in _FORBIDDEN_EGO_DECISION_NAMES)

    public_names = set(getattr(ego_api, "__all__", ()))
    if any(exposes_decision_surface(name) for name in public_names):
        return False
    inspected_types = (
        EgoTrace,
        EgoCompositionSnapshot,
        ego_api.EgoModalityProjections,
        ego_api.DeterministicEgoReflector,
    )
    return all(
        not any(
            exposes_decision_surface(name)
            for name, member in inspect.getmembers(value)
            if callable(member) and not name.startswith("_")
        )
        for value in inspected_types
    )


def _paired_character_pre_governance_invariant(
    template: ReiNativeCycleRequest,
) -> bool:
    """Prove the same native inputs/outputs ignore structural Character."""

    alternate_profile = next(
        profile_id
        for profile_id in CHARACTER_PROFILE_ORDER
        if profile_id != template.character.profile_id
    )
    alternate_character = parse_character_profile(
        alternate_profile,
        character_id="c6_pre_governance_invariance_alternate",
    )

    def run(request: ReiNativeCycleRequest) -> object:
        return ReiNativeEngine(
            artifact_store=_InMemoryEvaluationArtifactStore(),
            ego_trace_store=InMemoryEgoTraceStore(),
            providers=build_deterministic_native_providers(),
            clock=DeterministicExecutionClock(request.started_at),
        ).run_cycle(request)

    first = run(template)
    alternate = run(template.model_copy(update={"character": alternate_character}))

    def native_surface(result: object) -> tuple[object, ...]:
        return (
            result.racio_packet,
            result.emocio_packet,
            result.instinkt_packet,
            result.racio_execution,
            result.emocio_execution,
            result.instinkt_execution,
            result.native_bundle,
        )

    return bool(
        first.request.character != alternate.request.character
        and first.ego_measure.structural_character
        != alternate.ego_measure.structural_character
        and native_surface(first) == native_surface(alternate)
    )


def _select_sequences(
    corpus: LongitudinalCorpus,
    sequence_ids: Iterable[str] | None,
) -> tuple[LongitudinalCorpusSequence, ...]:
    if sequence_ids is None:
        return corpus.sequences
    requested = tuple(sequence_ids)
    if not requested or len(set(requested)) != len(requested):
        raise ValueError("C6 sequence selection must be non-empty and unique")
    by_id = {item.sequence_id: item for item in corpus.sequences}
    unknown = tuple(value for value in requested if value not in by_id)
    if unknown:
        raise ValueError(f"Unknown C6 sequence IDs: {unknown!r}")
    requested_set = set(requested)
    return tuple(item for item in corpus.sequences if item.sequence_id in requested_set)


def _evaluate_sequence(
    *,
    template: ReiNativeCycleRequest,
    corpus_sequence: LongitudinalCorpusSequence,
) -> LongitudinalSequenceResult:
    scenario = _build_scenario(template, corpus_sequence)
    state = scenario.initial_person_state
    artifact_store = _InMemoryEvaluationArtifactStore()
    trace_store = InMemoryEgoTraceStore()
    providers = build_deterministic_native_providers()
    historical_bundles: list[object] = []
    historical_emocio_signals: list[EmocioLongitudinalVisualSignal] = []
    historical_instinkt_signals: list[InstinktLongitudinalBodySignal] = []
    racio_world = state.racio_world
    emocio_world = state.emocio_world
    instinkt_world = state.instinkt_world
    previous_result = None
    previous_trace = EgoTrace.create(ego_id=state.ego_id)
    append_only_verified = True
    character_constant = True
    projection_citations_valid = True
    history_consumption_cycles = 0
    world_transfer_cycles = 0
    modality_specific_updates = True
    character_identifiers_absent = True
    narrative_divergence_cycles = 0
    self_narrative_divergence_cycles = 0
    verified_visual_signal_cycles = 0
    predicted_body_signal_cycles = 0
    measured_body_signal_cycles = 0
    simulated_spoznanje_cycles = 0
    persisted_cycles = 0
    world_change_counts = {
        "racio:timeline": 0,
        "emocio:visual_memory": 0,
        "instinkt:recovery": 0,
    }

    for index, step in enumerate(scenario.steps):
        request = template.model_copy(
            update={
                "run_id": f"c6-{scenario.sequence_id}-{index:02d}",
                "ego_id": state.ego_id,
                "scene": step.scene,
                "racio_world": racio_world,
                "emocio_world": emocio_world,
                "instinkt_world": instinkt_world,
                "body_state": state.body_state,
                "character": state.structural_character,
                "acceptance_state": state.acceptance_state,
                "outcome": step.external_outcome,
                "historical_bundles": tuple(historical_bundles),
                "historical_emocio_signals": tuple(historical_emocio_signals),
                "historical_instinkt_signals": tuple(historical_instinkt_signals),
                "symbolic_and_language_cues": (
                    corpus_sequence.steps[index],
                    *(template.symbolic_and_language_cues or ()),
                ),
                "started_at": template.started_at + timedelta(seconds=index),
            }
        )
        engine = ReiNativeEngine(
            artifact_store=artifact_store,
            ego_trace_store=trace_store,
            providers=providers,
            clock=DeterministicExecutionClock(request.started_at),
        )
        result = engine.run_cycle(request)
        append_only_verified = append_only_verified and (
            result.prior_trace == previous_trace
            and result.ego_trace.measures[:-1] == previous_trace.measures
            and result.ego_trace.event_order[:-1] == previous_trace.event_order
            and result.ego_trace.measures[-1] == result.ego_measure
        )
        character_constant = character_constant and all(
            measure.structural_character == state.structural_character
            for measure in result.ego_trace.measures
        )
        projection_citations_valid = (
            projection_citations_valid and _projection_citations_are_valid(result)
        )
        if previous_result is not None:
            if _history_was_consumed(result, previous_result):
                history_consumption_cycles += 1
            if (
                result.request.racio_world == racio_world
                and result.request.emocio_world == emocio_world
                and result.request.instinkt_world == instinkt_world
            ):
                world_transfer_cycles += 1

        racio_update = RacioWorldUpdater().update(
            racio_world,
            result.ego_measure,
            result.native_bundle,
            result.narrative,
        )
        visual_signal = _materialize_visual_signal(
            result=result,
            artifact_store=artifact_store,
            evaluation_seed=index,
        )
        verified_visual_signal_cycles += 1
        emocio_update = EmocioWorldUpdater().update(
            emocio_world,
            result.ego_measure,
            result.native_bundle,
            visual_signal,
            artifact_store,
        )
        selected_rollout = next(
            item
            for item in result.instinkt_execution.rollouts
            if item.rollout_id == result.native_bundle.instinkt.decisive_rollout_id
        )
        body_signal = InstinktLongitudinalBodySignal.create(
            measure=result.ego_measure,
            bundle=result.native_bundle,
            rollout=selected_rollout,
        )
        predicted_body_signal_cycles += 1
        measured_body_signal_cycles += body_signal.measured_outcome_update is not None
        instinkt_update = InstinktWorldUpdater().update(
            instinkt_world,
            result.ego_measure,
            result.native_bundle,
            body_signal,
        )
        modality_specific_updates = (
            modality_specific_updates
            and _world_updates_are_modality_specific(
                racio_update, emocio_update, instinkt_update
            )
        )
        character_identifiers_absent = (
            character_identifiers_absent
            and _world_update_tokens_exclude_character_identifiers(
                (racio_update, emocio_update, instinkt_update),
                character_id=state.structural_character.character_id,
                profile_id=state.structural_character.profile_id,
            )
        )
        world_change_counts["racio:timeline"] += len(
            racio_update.timeline_additions
        )
        world_change_counts["emocio:visual_memory"] += len(
            emocio_update.visual_memory_additions
        )
        world_change_counts["instinkt:recovery"] += len(
            instinkt_update.recovery_pattern_additions
        )
        racio_world = racio_update.updated_world
        emocio_world = emocio_update.updated_world
        instinkt_world = instinkt_update.updated_world

        diagnostic = diagnose_narrative_composition(
            result.narrative, result.composition_snapshot
        )
        narrative_divergence_cycles += diagnostic.narrative_composition_diverges
        self_narrative_divergence_cycles += bool(
            set(diagnostic.divergence_facets)
            & {"claimed_motive_not_observed", "omitted_minds"}
        )
        simulated_spoznanje_cycles += (
            result.ego_measure.spoznanje_status == "simulated_spoznanje"
        )
        persisted_cycles += bool(result.manifest and result.stored_artifacts)
        historical_bundles.append(result.native_bundle)
        historical_emocio_signals.append(visual_signal)
        historical_instinkt_signals.append(body_signal)
        previous_trace = result.ego_trace
        previous_result = result

    assert previous_result is not None
    assert previous_result.request.scene == scenario.steps[-1].scene
    history_counterfactual_influence = _history_counterfactual_changed_native_semantics(
        request=previous_result.request,
        history_result=previous_result,
        initial_state=state,
    )
    observed_motifs = _structured_motifs(previous_result.composition_snapshot)
    expected_motifs = tuple(sorted(scenario.expected_motifs))
    expected_set = set(expected_motifs)
    observed_set = set(observed_motifs)
    true_positive = len(expected_set & observed_set)
    false_positive = len(observed_set - expected_set)
    false_negative = len(expected_set - observed_set)
    precision = true_positive / len(observed_set) if observed_set else 0.0
    recall = true_positive / len(expected_set) if expected_set else 0.0
    observed_translation = tuple(
        previous_result.composition_snapshot.recurring_translation_errors
    )
    expected_translation = scenario.expected_translation_patterns
    translations_match = set(observed_translation) == set(expected_translation)
    world_counts = tuple(sorted(world_change_counts.items()))
    world_changes_present = all(value > 0 for _, value in world_counts)
    cycles = len(scenario.steps)
    return LongitudinalSequenceResult.create(
        sequence_id=scenario.sequence_id,
        title=corpus_sequence.title,
        scenario_id=scenario.scenario_id,
        scenario_hash=scenario.scenario_hash,
        profile_id=state.structural_character.profile_id,
        character_id=state.structural_character.character_id,
        acceptance_mode=state.acceptance_state.overall_mode,
        cycle_count=cycles,
        measure_ids=tuple(measure.measure_id for measure in previous_trace.measures),
        final_trace_hash=previous_trace.trace_hash,
        final_snapshot_id=previous_result.composition_snapshot.snapshot_id,
        final_snapshot_hash=previous_result.composition_snapshot.composition_hash,
        final_racio_world_id=racio_world.world_id,
        final_emocio_world_id=emocio_world.world_id,
        final_instinkt_world_id=instinkt_world.world_id,
        append_only_verified=append_only_verified,
        character_constant=character_constant,
        projection_citations_valid=projection_citations_valid,
        expected_history_consumption_cycles=cycles - 1,
        observed_history_consumption_cycles=history_consumption_cycles,
        expected_world_transfer_cycles=cycles - 1,
        observed_world_transfer_cycles=world_transfer_cycles,
        modality_specific_world_updates=modality_specific_updates,
        character_identifiers_absent_from_world_updates=(
            character_identifiers_absent
        ),
        history_counterfactual_influence=history_counterfactual_influence,
        projection_signal_integration_complete=(
            history_consumption_cycles == cycles - 1
        ),
        verified_visual_signal_cycle_count=verified_visual_signal_cycles,
        predicted_body_signal_cycle_count=predicted_body_signal_cycles,
        measured_body_signal_cycle_count=measured_body_signal_cycles,
        world_change_counts=world_counts,
        expected_motifs=expected_motifs,
        observed_motifs=observed_motifs,
        motif_true_positive_count=true_positive,
        motif_false_positive_count=false_positive,
        motif_false_negative_count=false_negative,
        motif_precision=precision,
        motif_recall=recall,
        expected_translation_patterns=expected_translation,
        observed_translation_patterns=observed_translation,
        translation_patterns_match=translations_match,
        narrative_divergence_cycle_count=narrative_divergence_cycles,
        self_narrative_divergence_cycle_count=(
            self_narrative_divergence_cycles
        ),
        expected_simulated_spoznanje_cycle_count=(
            corpus_sequence.expected_simulated_spoznanje_cycle_count
        ),
        simulated_spoznanje_cycle_count=simulated_spoznanje_cycles,
        persisted_cycle_count=persisted_cycles,
    )


def evaluate_longitudinal_corpus(
    *,
    corpus_path: str | Path,
    template_fixture_path: str | Path,
    sequence_ids: Iterable[str] | None = None,
) -> LongitudinalEvaluationReport:
    corpus = load_longitudinal_corpus(corpus_path)
    template = ReiNativeCycleRequest.model_validate_json(
        _read_bounded(
            template_fixture_path,
            maximum_bytes=MAX_LONGITUDINAL_TEMPLATE_BYTES,
            label="C6 template fixture",
        )
    )
    selected = _select_sequences(corpus, sequence_ids)
    results = tuple(
        _evaluate_sequence(template=template, corpus_sequence=item)
        for item in selected
    )
    full_corpus = tuple(item.sequence_id for item in selected) == tuple(
        item.sequence_id for item in corpus.sequences
    )
    return LongitudinalEvaluationReport.create(
        corpus_hash=corpus.content_hash(),
        corpus_sha256=hashlib.sha256(
            _read_bounded(
                corpus_path,
                maximum_bytes=MAX_LONGITUDINAL_CORPUS_BYTES,
                label="C6 corpus",
            )
        ).hexdigest(),
        template_request_hash=template.content_hash(),
        full_corpus=full_corpus,
        sequences=results,
        ego_decision_api_absent=_ego_decision_api_is_absent(),
        projection_signal_integration_complete=all(
            item.projection_signal_integration_complete for item in results
        ),
        pre_governance_character_invariance=(
            _paired_character_pre_governance_invariant(template)
        ),
    )


def render_longitudinal_report(
    report: LongitudinalEvaluationReport,
) -> dict[str, bytes]:
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
    technical_status = "PASS" if report.technical_gate_passed else "FAIL"
    expected_history = sum(
        item.expected_history_consumption_cycles for item in report.sequences
    )
    expected_transfer = sum(
        item.expected_world_transfer_cycles for item in report.sequences
    )
    lines = [
        "# C6 longitudinal Ego dimensional report",
        "",
        f"Gate: **{status}**",
        "",
        f"Technical gate: **{technical_status}**",
        "",
        (
            "This deterministic acceptance run executes the real `ReiNativeEngine` "
            "against the human-authored C6 corpus. No aggregate score is computed; "
            "each required dimension remains visible."
        ),
        "",
        "## Authority boundary",
        "",
        f"- Gate kind: `{report.gate_kind}`",
        f"- Review status: `{report.review_status}`",
        f"- Gold status: `{report.gold_status}`",
        f"- Motif gate: `{report.motif_gate_kind}`",
        (
            "- Natural-language motif authority: not granted "
            "(stage 1 uses structured tags only)"
        ),
        "- Semantic authority: not granted",
        f"- Legacy outcome scope: `{report.legacy_outcome_scope}`",
        f"- Measured body outcome status: `{report.measured_body_outcome_status}`",
        f"- Visual signal scope: `{report.visual_signal_scope}`",
        f"- Instinkt learning scope: `{report.instinkt_learning_scope}`",
        "",
        "## Dimensions",
        "",
        f"- Named sequences: {report.sequence_count}",
        f"- Total cycles: {report.total_cycle_count}",
        f"- Minimum cycles per sequence: {report.minimum_cycle_count}",
        (
            "- Append-only sequences: "
            f"{report.append_only_sequence_count}/{report.sequence_count}"
        ),
        (
            "- Constant-character sequences: "
            f"{report.character_constant_sequence_count}/{report.sequence_count}"
        ),
        (
            "- Projection citation sequences: "
            f"{report.projection_citation_sequence_count}/{report.sequence_count}"
        ),
        (
            "- Cycles consuming prior projections and historical bundles: "
            f"{report.history_consumption_cycle_count}/{expected_history}"
        ),
        (
            "- Cycles receiving prior modality-specific world updates: "
            f"{report.world_transfer_cycle_count}/{expected_transfer}"
        ),
        (
            "- Modality-specific world-update sequences: "
            f"{report.modality_specific_world_sequence_count}/{report.sequence_count}"
        ),
        (
            "- World-update sequences without literal Character/profile identifiers: "
            f"{report.character_identifier_absence_sequence_count}/"
            f"{report.sequence_count}"
        ),
        (
            "- Paired Character pre-governance native invariance: "
            f"{'yes' if report.pre_governance_character_invariance else 'no'}"
        ),
        (
            "- History counterfactual semantic-influence sequences: "
            f"{report.history_counterfactual_influence_sequence_count}/"
            f"{report.sequence_count}"
        ),
        (
            "- Projection signal integration complete: "
            f"{'yes' if report.projection_signal_integration_complete else 'no'}"
        ),
        (
            "- Verified byte-backed visual signal cycles: "
            f"{report.verified_visual_signal_cycle_count}/{report.total_cycle_count}"
        ),
        (
            "- Predicted body signal cycles: "
            f"{report.predicted_body_signal_cycle_count}/{report.total_cycle_count}"
        ),
        (
            "- Measured body signal cycles: "
            f"{report.measured_body_signal_cycle_count}/{report.total_cycle_count}"
        ),
        (
            "- Structured motif precision: "
            f"{report.motif_precision:.3f} "
            f"(threshold {report.motif_precision_threshold:.3f}; "
            f"TP={report.motif_true_positive_count}, "
            f"FP={report.motif_false_positive_count}, "
            f"FN={report.motif_false_negative_count})"
        ),
        f"- Structured motif recall: {report.motif_recall:.3f}",
        (
            "- Narrative-composition divergence cycles: "
            f"{report.narrative_divergence_cycle_count}"
        ),
        (
            "- Self-narrative-specific divergence cycles: "
            f"{report.self_narrative_divergence_cycle_count}"
        ),
        (
            "- Simulated-spoznanje cycles: "
            f"{report.simulated_spoznanje_cycle_count}/"
            f"{report.expected_simulated_spoznanje_cycle_count}"
        ),
        f"- Ego decision API absent: {'yes' if report.ego_decision_api_absent else 'no'}",
        "",
        "## Sequence results",
        "",
        (
            "| Sequence | Profile | Acceptance | Cycles | History | World transfer | "
            "Motif precision | Narrative divergence | Spoznanje | Result |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report.sequences:
        lines.append(
            "| "
            + " | ".join(
                (
                    item.sequence_id,
                    item.profile_id,
                    item.acceptance_mode,
                    str(item.cycle_count),
                    (
                        f"{item.observed_history_consumption_cycles}/"
                        f"{item.expected_history_consumption_cycles}"
                    ),
                    (
                        f"{item.observed_world_transfer_cycles}/"
                        f"{item.expected_world_transfer_cycles}"
                    ),
                    f"{item.motif_precision:.3f}",
                    str(item.narrative_divergence_cycle_count),
                    (
                        f"{item.simulated_spoznanje_cycle_count}/"
                        f"{item.expected_simulated_spoznanje_cycle_count}"
                    ),
                    "pass" if item.passes else "fail",
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Interpretation boundary",
            "",
            (
                "The result validates a bounded deterministic software architecture "
                "and its synthetic fixtures. It is not a diagnosis of a person, and "
                "`simulated_spoznanje` remains a simulator status rather than a "
                "psychological claim."
            ),
            "",
        )
    )
    return {
        "longitudinal_evaluation.json": json_payload,
        "dimensions.md": "\n".join(lines).encode("utf-8"),
    }


def write_longitudinal_report(
    report: LongitudinalEvaluationReport,
    output_root: str | Path,
) -> tuple[Path, ...]:
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    rendered = render_longitudinal_report(report)
    actual_files = tuple(path.name for path in root.iterdir() if path.is_file())
    if actual_files:
        raise FileExistsError(f"C6 report directory is not empty: {actual_files!r}")
    written: list[Path] = []
    for name in LONGITUDINAL_REPORT_FILENAMES:
        path = root / name
        path.write_bytes(rendered[name])
        written.append(path)
    return tuple(written)


__all__ = [
    "LONGITUDINAL_REPORT_FILENAMES",
    "LongitudinalCorpus",
    "LongitudinalCorpusSequence",
    "LongitudinalEvaluationReport",
    "LongitudinalSequenceResult",
    "build_longitudinal_scenarios",
    "evaluate_longitudinal_corpus",
    "load_longitudinal_corpus",
    "parse_longitudinal_corpus",
    "render_longitudinal_report",
    "write_longitudinal_report",
]
