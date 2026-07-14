"""Strict adapter for the manually authored C2 semantic-evaluation fixtures.

The fixture envelope intentionally predates the typed runtime candidates.  This
module is the only compatibility boundary: it validates fixture and manifest
metadata, constructs the current typed evaluator inputs, invokes the existing
model-free evaluators, and reports exact gold-contract diagnostics.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from ..models.common import FrozenModel, HashDigest, MindId, NonEmptyId, NonEmptyText
from .bilingual_eval import evaluate_bilingual_pair
from .communication_eval import evaluate_interpretation
from .ego_eval import evaluate_ego_sequence
from .emocio_eval import evaluate_emocio_route
from .instinkt_eval import evaluate_instinkt_route
from .models import (
    BilingualCandidatePair,
    BilingualEvaluationCase,
    CandidateClaim,
    CandidateInterpretation,
    CandidateNativeRoute,
    EgoEvaluationCase,
    EgoEvaluationSample,
    EgoMotifCandidate,
    EvaluationDimension,
    InputExposureRecord,
    InterpretationClass,
    InterpretationDistortionEvidence,
    InterpretationEvaluationCase,
    NativeRouteEvaluationCase,
    SemanticEvaluationResult,
    TerminologyUse,
    TrustedSemanticSignature,
)
from .native_routes import (
    boolean_metric,
    evaluate_native_route,
    evaluate_native_route_payload,
    extend_result,
    issue,
)
from .racio_eval import evaluate_racio_route


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "semantic_evaluation_v1"
EXPECTED_SUBJECT_COUNTS = {
    "native_route": 16,
    "interpretation": 8,
    "bilingual_pair": 3,
    "ego_sequence": 5,
}
EXPECTED_FIXTURE_FILES = (
    ("native_routes.jsonl", 16),
    ("communication.jsonl", 8),
    ("bilingual.jsonl", 3),
    ("ego.jsonl", 5),
)
EXPECTED_REQUIRED_COVERAGE = {
    "schema_invalid": ("eval_schema_invalid_candidate",),
    "provenance": (
        "eval_racio_route_complete",
        "eval_provenance_incomplete",
        "eval_renderer_added_as_grounded_fact",
    ),
    "allowed_option": (
        "eval_racio_route_complete",
        "eval_option_outside_allowed_scope",
    ),
    "source_evidence": (
        "eval_racio_route_complete",
        "eval_source_evidence_incomplete",
    ),
    "unsupported_claim": (
        "eval_unsupported_claim",
        "eval_renderer_added_as_grounded_fact",
    ),
    "profile_leakage": ("eval_profile_leakage",),
    "hidden_ground_truth_leakage": ("eval_hidden_ground_truth_leakage",),
    "confidence_calibration": (
        "eval_calibration_correct_high_confidence",
        "eval_calibration_correct_low_confidence",
        "eval_interpretation_rationalization",
    ),
    "abstention": ("eval_abstention_correct", "eval_abstention_incorrect"),
    "slovenian_terminology": (
        "eval_slovenian_terminology_valid",
        "eval_slovenian_terminology_invalid",
        "eval_bilingual_terminology_drift",
    ),
    "accurate_vs_rationalization": (
        "eval_interpretation_accurate",
        "eval_interpretation_rationalization",
    ),
    "all_interpretation_labels": (
        "eval_interpretation_accurate",
        "eval_interpretation_partial",
        "eval_interpretation_omission",
        "eval_interpretation_rationalization",
        "eval_interpretation_minimization",
        "eval_interpretation_projection",
        "eval_interpretation_misclassification",
        "eval_interpretation_unknown",
    ),
    "bilingual": (
        "eval_bilingual_signature_consistent",
        "eval_bilingual_semantic_drift",
        "eval_bilingual_terminology_drift",
    ),
    "ego": (
        "eval_ego_grounded_recurring_motif",
        "eval_ego_false_motif",
        "eval_ego_missed_motif",
        "eval_ego_translation_and_tension_discontinuity",
        "eval_ego_projection_and_narrative_boundary",
    ),
}
EXPECTED_INTERPRETATION_LABELS: tuple[InterpretationClass, ...] = (
    "accurate",
    "partial",
    "omission",
    "rationalization",
    "minimization",
    "projection",
    "misclassification",
    "unknown",
)
EXPECTED_TERMINOLOGY_IDS = frozenset(
    {
        "REI_RACIO",
        "REI_EMOCIO",
        "REI_INSTINKT",
        "REI_EGO",
        "REI_TRANSLATION_GAP",
    }
)

CaseId = Annotated[
    str,
    StringConstraints(pattern=r"^eval_[a-z0-9_]+$", min_length=6, max_length=200),
]
ClaimId = Annotated[
    str,
    StringConstraints(pattern=r"^C-[A-Z]+-[0-9]{3}$", min_length=7, max_length=200),
]
FamilyId = Annotated[
    str,
    StringConstraints(pattern=r"^sf_[a-z0-9_]+$", min_length=4, max_length=200),
]
DimensionOutcome = Literal["pass", "fail", "not_applicable"]
SubjectKind = Literal[
    "native_route", "interpretation", "bilingual_pair", "ego_sequence"
]
FixtureDomain = Literal[
    "shared", "racio", "emocio", "instinkt", "communication", "bilingual", "ego"
]


class ManualInputScope(FrozenModel):
    actual_artifact_ids: tuple[NonEmptyId, ...]
    visible_observation_ids: tuple[NonEmptyId, ...]
    grounded_evidence_ids: tuple[NonEmptyId, ...]
    allowed_option_ids: tuple[NonEmptyId, ...]
    forbidden_native_truth_ids: tuple[NonEmptyId, ...]
    forbidden_profile_ids: tuple[NonEmptyId, ...]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        _require_unique_sequences(self)
        return self


class ManualDistortionEvidence(FrozenModel):
    evidence_kind: NonEmptyId
    visible_support_ids: tuple[NonEmptyId, ...]
    candidate_claim_ids: tuple[NonEmptyId, ...]
    contradicted_claim_ids: tuple[NonEmptyId, ...]
    expected_label: InterpretationClass

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        _require_unique_sequences(self)
        return self


class ManualTrustedExpectation(FrozenModel):
    expected_label: NonEmptyId
    expected_mind: MindId | None = None
    expected_option_id: NonEmptyId | None = None
    expected_abstains: bool
    expected_decisive_representation: NonEmptyText | None
    expected_sequence_id: NonEmptyId | None
    expected_measure_ids: tuple[NonEmptyId, ...]
    expected_route_tags: tuple[NonEmptyId, ...] = ()
    expected_evidence_ids: tuple[NonEmptyId, ...] = ()
    expected_source_claim_ids: tuple[NonEmptyId, ...] = ()
    expected_interpretation_class: InterpretationClass | None = None
    expected_motive_class: NonEmptyId | None = None
    expected_action_tendency: NonEmptyId | None = None
    expected_motif_ids: tuple[NonEmptyId, ...] = ()
    expected_translation_gap_ids: tuple[NonEmptyId, ...] = ()
    expected_unresolved_tension_ids: tuple[NonEmptyId, ...] = ()
    expected_projection_minds: tuple[MindId, ...] = ()
    expected_projection_facets: tuple[NonEmptyId, ...] = ()
    expected_semantic_signature: tuple[NonEmptyId, ...] = ()
    required_terminology_ids: tuple[NonEmptyId, ...] = ()
    distortion_evidence: ManualDistortionEvidence | None = None
    max_brier_error: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> Self:
        _require_unique_sequences(self)
        if self.expected_abstains != (self.expected_option_id is None):
            # Ego fixtures have no option but are not route-abstention cases.
            if self.expected_mind is not None:
                raise ValueError("Route abstention must correspond to a null option")
        return self


class ManualExpectedResult(FrozenModel):
    passed: bool
    observed_label: NonEmptyId
    issue_codes: tuple[NonEmptyId, ...]
    dimension_outcomes: dict[EvaluationDimension, DimensionOutcome]

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(set(self.issue_codes)) != len(self.issue_codes):
            raise ValueError("Expected issue codes must be unique")
        if not self.dimension_outcomes:
            raise ValueError("At least one expected dimension outcome is required")
        return self


class ManualEvaluationCase(FrozenModel):
    schema_version: Literal["rei-semantic-evaluation-case-v1"]
    case_id: CaseId
    subject_kind: SubjectKind
    domain: FixtureDomain
    polarity: Literal["positive", "negative"]
    family_id: FamilyId
    variant_id: NonEmptyId
    source_claim_ids: tuple[ClaimId, ...]
    policy_ids: tuple[NonEmptyId, ...]
    input_scope: ManualInputScope
    candidate_payload: dict[str, Any]
    trusted_expectation: ManualTrustedExpectation
    expected_result: ManualExpectedResult
    gold_origin: Literal["manually_authored"]
    model_generated_gold: Literal[False]
    review_status: Literal["c2_manual_reviewed"]
    notes_sl: NonEmptyText

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        _require_unique_sequences(self)
        subject_domain = {
            "interpretation": "communication",
            "bilingual_pair": "bilingual",
            "ego_sequence": "ego",
        }
        expected_domain = subject_domain.get(self.subject_kind)
        if expected_domain is not None and self.domain != expected_domain:
            raise ValueError("Fixture subject kind and domain disagree")
        if self.subject_kind == "native_route" and self.domain in {
            "communication",
            "bilingual",
            "ego",
        }:
            raise ValueError("Native route fixture uses a non-route domain")
        if self.expected_result.passed != (self.polarity == "positive"):
            raise ValueError("Fixture polarity and expected pass state disagree")
        trusted = self.trusted_expectation
        if self.subject_kind == "native_route":
            if trusted.expected_mind is None or trusted.expected_decisive_representation is None:
                raise ValueError("Native route gold requires mind and decisive representation")
            if trusted.expected_sequence_id is not None or trusted.expected_measure_ids:
                raise ValueError("Native route gold cannot carry Ego sequence truth")
        elif self.subject_kind == "ego_sequence":
            if trusted.expected_sequence_id is None or not trusted.expected_measure_ids:
                raise ValueError("Ego gold requires explicit sequence and measure IDs")
            if trusted.expected_decisive_representation is not None:
                raise ValueError("Ego gold cannot carry a native decisive representation")
        elif self.subject_kind == "interpretation":
            if trusted.expected_mind not in {"E", "I"}:
                raise ValueError("Interpretation gold requires an E or I source mind")
            if (
                trusted.expected_decisive_representation is not None
                or trusted.expected_sequence_id is not None
                or trusted.expected_measure_ids
            ):
                raise ValueError("Interpretation gold carries an unrelated oracle field")
        elif (
            trusted.expected_decisive_representation is not None
            or trusted.expected_sequence_id is not None
            or trusted.expected_measure_ids
        ):
            raise ValueError("Non-native/non-Ego gold carries an unrelated oracle field")
        distortion = self.trusted_expectation.distortion_evidence
        if distortion is not None:
            if distortion.expected_label != self.trusted_expectation.expected_interpretation_class:
                raise ValueError("Distortion evidence label disagrees with trusted label")
            candidate_claim_ids = {
                str(item.get("claim_id"))
                for item in self.candidate_payload.get("claims", ())
                if isinstance(item, Mapping) and item.get("claim_id")
            }
            if not set(distortion.candidate_claim_ids).issubset(candidate_claim_ids):
                raise ValueError("Distortion evidence cites a missing candidate claim")
        return self


class ManualDigestReference(FrozenModel):
    path: NonEmptyText
    sha256: HashDigest


class ManualPolicyReference(ManualDigestReference):
    path: Literal["knowledge/canon_v2/evaluation.json"]
    policy_id: Literal["rei-semantic-evaluation-c2-v1"]


class ManualSchemaReference(ManualDigestReference):
    path: Literal[
        "knowledge/semantic_lab_v1/schemas/evaluation_case.schema.json"
    ]
    schema_id: Literal[
        "https://rei.local/schemas/semantic-lab-v1/evaluation-case.json"
    ]


class ManualFixtureFile(FrozenModel):
    path: NonEmptyText
    case_count: int = Field(ge=1)
    sha256: HashDigest


class ManualReportingPolicy(FrozenModel):
    global_rei_score: Literal[False]
    dimensions_remain_separate: Literal[True]


class ManualCanonicalTermPair(FrozenModel):
    sl_surface: NonEmptyText
    en_surface: NonEmptyText


class ManualTerminologyPolicy(FrozenModel):
    policy_id: Literal["c2-slovenian-terminology-v1"]
    source: Literal["knowledge/canon_v2/glossary.yaml"]
    required_canonical_terms: dict[NonEmptyId, NonEmptyText]
    canonical_term_pairs: dict[NonEmptyId, ManualCanonicalTermPair]
    terminology_check_may_decide_native_route: Literal[False]

    @model_validator(mode="after")
    def validate_term_pairs(self) -> Self:
        if (
            set(self.required_canonical_terms) != EXPECTED_TERMINOLOGY_IDS
            or set(self.canonical_term_pairs) != EXPECTED_TERMINOLOGY_IDS
        ):
            raise ValueError("Canonical terminology IDs and pairs differ")
        if any(
            self.required_canonical_terms[term_id] != pair.sl_surface
            for term_id, pair in self.canonical_term_pairs.items()
        ):
            raise ValueError("Canonical Slovene term and pair surfaces differ")
        return self


class ManualFixtureManifest(FrozenModel):
    schema_version: Literal["rei-semantic-evaluation-fixture-manifest-v1"]
    fixture_set_id: Literal["rei-semantic-evaluation-v1"]
    policy: ManualPolicyReference
    case_schema: ManualSchemaReference
    gold_origin: Literal["manually_authored"]
    model_generated_gold: Literal[False]
    model_judge_calls: Literal[0]
    training_export: Literal[False]
    review_status: Literal["c2_manual_reviewed"]
    case_count: Literal[32]
    positive_case_count: Literal[8]
    negative_case_count: Literal[24]
    subject_counts: dict[SubjectKind, int]
    files: tuple[ManualFixtureFile, ...]
    required_coverage: dict[NonEmptyId, tuple[CaseId, ...]]
    interpretation_labels: tuple[InterpretationClass, ...]
    reporting: ManualReportingPolicy

    @model_validator(mode="after")
    def validate_manifest_totals(self) -> Self:
        if self.subject_counts != EXPECTED_SUBJECT_COUNTS:
            raise ValueError("Official manifest subject counts differ from C2 contract")
        actual_files = tuple((item.path, item.case_count) for item in self.files)
        if actual_files != EXPECTED_FIXTURE_FILES:
            raise ValueError("Official manifest files/counts differ from C2 contract")
        if self.required_coverage != EXPECTED_REQUIRED_COVERAGE:
            raise ValueError("Official manifest coverage groups differ from C2 contract")
        for coverage_id, case_ids in self.required_coverage.items():
            if not case_ids or len(set(case_ids)) != len(case_ids):
                raise ValueError(
                    f"Required coverage IDs must be non-empty and unique: {coverage_id}"
                )
        if self.interpretation_labels != EXPECTED_INTERPRETATION_LABELS:
            raise ValueError("Manifest must enumerate all eight interpretation labels")
        return self


class ManualCaseOutcome(FrozenModel):
    case_id: CaseId
    semantic_result: SemanticEvaluationResult
    candidate_passed: bool
    observed_label: NonEmptyId
    issue_codes: tuple[NonEmptyId, ...]
    dimension_outcomes: dict[EvaluationDimension, DimensionOutcome]
    expected_passed: bool
    expected_observed_label: NonEmptyId
    expected_issue_codes: tuple[NonEmptyId, ...]
    expected_dimension_outcomes: dict[EvaluationDimension, DimensionOutcome]
    failed_dimensions: tuple[EvaluationDimension, ...]
    unexpected_failed_dimensions: tuple[EvaluationDimension, ...]
    pass_matches: bool
    observed_label_matches: bool
    issue_codes_match: bool
    dimension_outcomes_match: bool
    exact_match: bool
    evaluator_model_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_replay(self) -> Self:
        expected_flags = (
            self.candidate_passed == self.expected_passed,
            self.observed_label == self.expected_observed_label,
            self.issue_codes == self.expected_issue_codes,
            self.dimension_outcomes == self.expected_dimension_outcomes,
            not self.unexpected_failed_dimensions,
        )
        recorded_flags = (
            self.pass_matches,
            self.observed_label_matches,
            self.issue_codes_match,
            self.dimension_outcomes_match,
            not self.unexpected_failed_dimensions,
        )
        if recorded_flags != expected_flags:
            raise ValueError("Manual case match flags differ from deterministic replay")
        declared_dimensions = set(self.expected_dimension_outcomes)
        replay_unexpected = tuple(
            sorted(set(self.failed_dimensions) - declared_dimensions)
        )
        if self.unexpected_failed_dimensions != replay_unexpected:
            raise ValueError("Unexpected failed dimensions differ from replay")
        if self.exact_match != all(expected_flags):
            raise ValueError("Manual case exact-match state differs from replay")
        return self


class ManualFixtureSetOutcome(FrozenModel):
    manifest: ManualFixtureManifest
    cases: tuple[ManualEvaluationCase, ...]
    outcomes: tuple[ManualCaseOutcome, ...]
    exact_match_count: int = Field(ge=0)
    evaluator_model_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_replay(self) -> Self:
        count = len(self.outcomes)
        if count != len(self.cases) or count != self.manifest.case_count:
            raise ValueError("Manual suite case/outcome counts differ from manifest")
        case_ids = tuple(case.case_id for case in self.cases)
        outcome_ids = tuple(outcome.case_id for outcome in self.outcomes)
        if case_ids != outcome_ids:
            raise ValueError("Manual suite outcomes are not aligned with cases")
        replay_count = sum(outcome.exact_match for outcome in self.outcomes)
        if self.exact_match_count != replay_count:
            raise ValueError("Manual suite exact-match count differs from replay")
        return self

    @property
    def exact_match(self) -> bool:
        return self.exact_match_count == len(self.outcomes)


def _require_unique_sequences(model: FrozenModel) -> None:
    for name in type(model).model_fields:
        values = getattr(model, name)
        if isinstance(values, tuple) and len(set(values)) != len(values):
            raise ValueError(f"{name} must contain unique values")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_fixture_root(fixture_root: str | Path | None) -> Path:
    return Path(fixture_root).resolve() if fixture_root else DEFAULT_FIXTURE_ROOT


def _validate_manifest_integrity(
    manifest: ManualFixtureManifest,
    fixture_root: Path,
) -> None:
    for reference in (manifest.policy, manifest.case_schema):
        source_path = (REPOSITORY_ROOT / reference.path).resolve()
        try:
            source_path.relative_to(REPOSITORY_ROOT)
        except ValueError as exc:
            raise ValueError(f"Manifest source path escapes repository: {reference.path}") from exc
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        if _sha256(source_path) != reference.sha256:
            raise ValueError(f"Manifest digest mismatch: {reference.path}")

    for entry in manifest.files:
        candidate_path = (fixture_root / entry.path).resolve()
        try:
            candidate_path.relative_to(fixture_root)
        except ValueError as exc:
            raise ValueError(f"Fixture path escapes fixture root: {entry.path}") from exc
        if not candidate_path.is_file():
            raise FileNotFoundError(candidate_path)
        if _sha256(candidate_path) != entry.sha256:
            raise ValueError(f"Fixture digest mismatch: {entry.path}")


def load_manual_fixture_manifest(
    fixture_root: str | Path | None = None,
) -> ManualFixtureManifest:
    """Load and cryptographically verify the C2 manual fixture manifest."""

    root = _resolve_fixture_root(fixture_root)
    manifest_path = root / "manifest.json"
    manifest = ManualFixtureManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    _validate_manifest_integrity(manifest, root)
    return manifest


def load_manual_terminology_policy() -> ManualTerminologyPolicy:
    """Load the trusted candidate-surface comparison policy from C2 canon."""

    policy_path = REPOSITORY_ROOT / "knowledge" / "canon_v2" / "evaluation.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "rei-semantic-evaluation-policy-v1":
        raise ValueError("Unexpected semantic evaluation policy schema")
    if payload.get("policy_id") != "rei-semantic-evaluation-c2-v1":
        raise ValueError("Unexpected semantic evaluation policy ID")
    return ManualTerminologyPolicy.model_validate(payload.get("terminology_policy"))


def _terminology_maps() -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    policy = load_manual_terminology_policy()
    native = {
        term_id: pair.sl_surface
        for term_id, pair in policy.canonical_term_pairs.items()
    }
    bilingual = {
        term_id: (pair.sl_surface, pair.en_surface)
        for term_id, pair in policy.canonical_term_pairs.items()
    }
    return native, bilingual


def load_manual_evaluation_cases(
    fixture_root: str | Path | None = None,
) -> tuple[ManualEvaluationCase, ...]:
    """Load all cases after strict envelope, digest, count and coverage checks."""

    root = _resolve_fixture_root(fixture_root)
    manifest = load_manual_fixture_manifest(root)
    cases: list[ManualEvaluationCase] = []
    for entry in manifest.files:
        path = root / entry.path
        file_cases: list[ManualEvaluationCase] = []
        for line_number, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not raw_line.strip():
                raise ValueError(f"Blank JSONL record in {entry.path}:{line_number}")
            try:
                case = ManualEvaluationCase.model_validate_json(raw_line)
            except Exception as exc:
                raise ValueError(
                    f"Invalid evaluation envelope in {entry.path}:{line_number}"
                ) from exc
            file_cases.append(case)
        if len(file_cases) != entry.case_count:
            raise ValueError(f"Fixture case count mismatch: {entry.path}")
        cases.extend(file_cases)

    if len(cases) != manifest.case_count:
        raise ValueError("Loaded case count differs from manifest")
    case_ids = tuple(case.case_id for case in cases)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Manual fixture case IDs must be unique")

    positive_count = sum(case.polarity == "positive" for case in cases)
    negative_count = len(cases) - positive_count
    if (positive_count, negative_count) != (
        manifest.positive_case_count,
        manifest.negative_case_count,
    ):
        raise ValueError("Loaded polarity counts differ from manifest")
    subject_counts: dict[str, int] = defaultdict(int)
    for case in cases:
        subject_counts[case.subject_kind] += 1
    if dict(subject_counts) != manifest.subject_counts:
        raise ValueError("Loaded subject counts differ from manifest")
    known_case_ids = set(case_ids)
    for coverage_id, covered_ids in manifest.required_coverage.items():
        if not covered_ids or not set(covered_ids).issubset(known_case_ids):
            raise ValueError(f"Invalid required coverage group: {coverage_id}")
    return tuple(cases)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _metric_dimensions(result: SemanticEvaluationResult) -> dict[str, DimensionOutcome]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for metric in result.metrics:
        grouped[metric.dimension].append(metric.status)
    for item in result.issues:
        if item.severity == "error":
            grouped[item.dimension].append("failed")
    outcomes: dict[str, DimensionOutcome] = {}
    for dimension, statuses in grouped.items():
        if "failed" in statuses:
            outcomes[dimension] = "fail"
        elif "passed" in statuses:
            outcomes[dimension] = "pass"
        else:
            outcomes[dimension] = "not_applicable"
    return outcomes


def _failed_dimensions(
    result: SemanticEvaluationResult,
    supplements: Mapping[str, DimensionOutcome],
) -> tuple[EvaluationDimension, ...]:
    failed = {
        metric.dimension for metric in result.metrics if metric.status == "failed"
    }
    failed.update(
        item.dimension for item in result.issues if item.severity == "error"
    )
    failed.update(
        dimension for dimension, outcome in supplements.items() if outcome == "fail"
    )
    return tuple(sorted(failed))


def _declared_dimensions(
    case: ManualEvaluationCase,
    result: SemanticEvaluationResult,
    *,
    supplements: Mapping[str, DimensionOutcome] | None = None,
) -> dict[EvaluationDimension, DimensionOutcome]:
    measured = _metric_dimensions(result)
    measured.update(supplements or {})
    return {
        dimension: measured.get(dimension, "not_applicable")
        for dimension in case.expected_result.dimension_outcomes
    }


def _exposure(
    case: ManualEvaluationCase,
    *,
    subject_id: str,
    cognition_mode: Literal["structured", "visual", "motor", "body", "mixed"] = (
        "structured"
    ),
) -> InputExposureRecord:
    scope = case.input_scope
    hidden = scope.forbidden_native_truth_ids
    allowed = tuple(
        artifact_id
        for artifact_id in scope.actual_artifact_ids
        if artifact_id not in set(hidden)
    )
    return InputExposureRecord.create(
        subject_id=subject_id,
        allowed_artifact_ids=allowed,
        actual_input_artifact_ids=scope.actual_artifact_ids,
        visible_observation_ids=scope.visible_observation_ids,
        visible_evidence_ids=scope.grounded_evidence_ids,
        visible_option_ids=scope.allowed_option_ids,
        forbidden_artifact_ids=hidden,
        profile_artifact_ids=scope.forbidden_profile_ids,
        evaluator_truth_artifact_ids=hidden,
        cognition_mode=cognition_mode,
    )


def _claim_provenance(raw_value: object) -> str:
    return {
        "grounded": "supplied",
        "simulated_from_grounded": "world_projection",
        "visible_observation": "visible_manifestation",
        "renderer_added_ungrounded": "renderer_added_ungrounded",
        "inferred": "candidate_inference",
        "hidden_native_truth": "candidate_inference",
        "unsupported_self_justification": "candidate_inference",
        "projected_self_state": "candidate_inference",
    }.get(str(raw_value), "candidate_inference")


def _claims(
    raw_claims: object,
) -> tuple[CandidateClaim, ...]:
    if not isinstance(raw_claims, list):
        return ()
    claims: list[CandidateClaim] = []
    for raw in raw_claims:
        if not isinstance(raw, Mapping):
            continue
        claims.append(
            CandidateClaim(
                claim_id=str(raw["claim_id"]),
                facet=str(raw["facet"]),
                value=str(raw.get("value_id", raw.get("value", "unknown"))),
                source_claim_ids=tuple(
                    str(value) for value in raw.get("source_claim_ids", ())
                ),
                evidence_ids=tuple(str(value) for value in raw.get("evidence_ids", ())),
                observation_ids=tuple(
                    str(value) for value in raw.get("observation_ids", ())
                ),
                provenance_kind=_claim_provenance(raw.get("provenance_kind")),
            )
        )
    return tuple(claims)


def _terminology_uses(raw_uses: object) -> tuple[TerminologyUse, ...]:
    if not isinstance(raw_uses, list):
        return ()
    uses: list[TerminologyUse] = []
    for raw in raw_uses:
        if not isinstance(raw, Mapping):
            continue
        uses.append(
            TerminologyUse(
                terminology_id=str(raw["terminology_id"]),
                language=str(raw["language"]),
                surface_form=str(raw["surface_form"]),
            )
        )
    return tuple(uses)


def _native_case(case: ManualEvaluationCase) -> NativeRouteEvaluationCase:
    trusted = case.trusted_expectation
    mind = trusted.expected_mind
    representation = trusted.expected_decisive_representation
    if mind is None or representation is None:
        raise ValueError(f"Native fixture lacks trusted route gold: {case.case_id}")
    canonical_claim_ids = _unique(
        (*case.source_claim_ids, *trusted.expected_source_claim_ids)
    )
    return NativeRouteEvaluationCase(
        case_id=case.case_id,
        family_id=case.family_id,
        variant_id=case.variant_id,
        expected_route_id=f"{case.case_id}__expected_route",
        mind=mind,
        allowed_option_ids=case.input_scope.allowed_option_ids,
        grounded_evidence_ids=case.input_scope.grounded_evidence_ids,
        allowed_observation_ids=case.input_scope.visible_observation_ids,
        canonical_claim_ids=canonical_claim_ids,
        expected_evidence_ids=trusted.expected_evidence_ids,
        expected_route_tags=trusted.expected_route_tags,
        expected_option_id=trusted.expected_option_id,
        expected_decisive_representation=representation,
        expected_abstention=trusted.expected_abstains,
        required_terminology_ids=trusted.required_terminology_ids,
        source_locator_refs=case.source_claim_ids,
        calibration_max_brier=trusted.max_brier_error,
    )


def _native_candidate(case: ManualEvaluationCase) -> CandidateNativeRoute:
    raw = case.candidate_payload
    candidate_id = str(raw["candidate_route_id"])
    return CandidateNativeRoute(
        candidate_route_id=candidate_id,
        family_id=str(raw["family_id"]),
        variant_id=str(raw["variant_id"]),
        mind=str(raw["mind"]),
        claims=_claims(raw.get("claims")),
        route_tags=tuple(str(value) for value in raw.get("route_tags", ())),
        option_id=raw.get("option_id"),
        decisive_representation=str(raw["decisive_representation"]),
        short_decision_bridge_sl=str(raw["short_decision_bridge_sl"]),
        terminology_uses=_terminology_uses(raw.get("terminology_uses")),
        confidence=float(raw["confidence"]),
        abstains=bool(raw["abstains"]),
        uncertainty=str(raw["uncertainty"]),
    )


def _evaluate_native(
    case: ManualEvaluationCase,
) -> tuple[SemanticEvaluationResult, str, tuple[str, ...], dict[str, DimensionOutcome]]:
    typed_case = _native_case(case)
    raw_candidate_id = str(
        case.candidate_payload.get(
            "candidate_route_id", f"{case.case_id}__invalid_payload"
        )
    )
    cognition_mode = {
        "racio": "structured",
        "emocio": "visual",
        "instinkt": "body",
    }.get(case.domain, "structured")
    trusted_exposure = _exposure(
        case,
        subject_id=raw_candidate_id,
        cognition_mode=cognition_mode,
    )
    native_terminology_policy, _ = _terminology_maps()
    if "schema_version" not in case.candidate_payload:
        result = evaluate_native_route_payload(
            case=typed_case,
            payload=case.candidate_payload,
            trusted_exposure=trusted_exposure,
            terminology_policy=native_terminology_policy,
        )
        return result, "schema_invalid", ("schema_invalid",), {}

    candidate = _native_candidate(case)
    evaluator = {
        "racio": evaluate_racio_route,
        "emocio": evaluate_emocio_route,
        "instinkt": evaluate_instinkt_route,
    }.get(case.domain, evaluate_native_route)
    result = evaluator(
        case=typed_case,
        candidate=candidate,
        trusted_exposure=trusted_exposure,
        terminology_policy=native_terminology_policy,
    )
    cited_source_artifacts = {
        str(value)
        for value in case.candidate_payload.get("source_artifact_ids", ())
    }
    outside_trusted_input = tuple(
        sorted(cited_source_artifacts - set(trusted_exposure.actual_input_artifact_ids))
    )
    if outside_trusted_input:
        result = extend_result(
            result,
            metrics=(
                boolean_metric(
                    "manual_trusted_source_artifact_scope",
                    "provenance_completeness",
                    False,
                    "Candidate source lineage is outside the trusted input exposure.",
                    policy_id="c2-input-exposure-v1",
                ),
            ),
            issues=(
                issue(
                    "incomplete_or_out_of_scope_provenance",
                    "provenance_completeness",
                    "Candidate cites source artifacts absent from trusted exposure.",
                    refs=outside_trusted_input,
                ),
            ),
            policies=("c2-input-exposure-v1",),
        )
    raw_issues = {item.issue_code for item in result.issues}
    renderer_claim = any(
        claim.provenance_kind == "renderer_added_ungrounded"
        for claim in candidate.claims
    )

    # These aliases collapse known downstream failures behind the first stable
    # contract violation.  They are derived from evaluator findings, never from
    # the expected issue list.
    if "hidden_ground_truth_leakage" in raw_issues:
        observed = "hidden_ground_truth_leakage"
        issue_codes = ("hidden_ground_truth_leakage",)
    elif "profile_leakage" in raw_issues:
        observed = "profile_leakage"
        issue_codes = ("profile_leakage",)
    elif renderer_claim:
        observed = "unsupported_renderer_fact"
        issue_codes = (
            "renderer_added_claim_treated_as_grounded",
            "unsupported_claim",
        )
    elif "incorrect_abstention" in raw_issues:
        observed = "abstention_mismatch"
        issue_codes = ("abstention_mismatch", "native_route_mismatch")
    elif "invalid_option_id" in raw_issues:
        observed = "invalid_option"
        issue_codes = ("option_outside_allowed_scope",)
    elif "missing_source_evidence" in raw_issues:
        observed = "evidence_incomplete"
        issue_codes = ("source_evidence_incomplete",)
    elif "unsupported_claim" in raw_issues:
        observed = "unsupported_claim"
        issue_codes = ("unsupported_claim",)
    elif "incomplete_or_out_of_scope_provenance" in raw_issues:
        observed = "provenance_incomplete"
        issue_codes = ("provenance_incomplete",)
    elif "slovenian_terminology_mismatch" in raw_issues:
        observed = "terminology_inconsistent"
        issue_codes = ("slovenian_terminology_inconsistent",)
    elif "miscalibrated_confidence" in raw_issues:
        observed = "confidence_miscalibrated"
        issue_codes = ("confidence_miscalibrated",)
    elif "native_route_mismatch" in raw_issues:
        observed = "native_route_mismatch"
        issue_codes = ("native_route_mismatch",)
    else:
        observed = "abstention" if candidate.abstains else "valid_route"
        issue_codes = ()
    return result, observed, issue_codes, {}


def _interpretation_operation(raw: Mapping[str, Any]) -> str:
    tags = set(str(value) for value in raw.get("route_tags", ()))
    justification = str(raw.get("justification_kind", "visible_evidence"))
    if justification == "omitted":
        return "omit_signal"
    if "downscaled_signal" in tags:
        return "downscale_signal"
    if "self_state_attribution" in tags:
        return "transfer_self_motive"
    if justification == "self_justification":
        return "self_justify"
    if justification == "alternative_hypothesis":
        if raw.get("inferred_motive_class") is None and "route_unknown" in tags:
            return "insufficient_information"
        return "alternative_hypothesis"
    if raw.get("unresolved_ambiguity") is True and (
        raw.get("inferred_option_id") is None
        or raw.get("inferred_motive_class") is None
    ):
        return "alternative_hypothesis"
    return "direct_inference"


def _interpretation_case(
    case: ManualEvaluationCase,
) -> InterpretationEvaluationCase:
    trusted = case.trusted_expectation
    expected_class = trusted.expected_interpretation_class
    if expected_class is None:
        raise ValueError(f"Interpretation fixture lacks a trusted class: {case.case_id}")
    distortion = trusted.distortion_evidence
    if distortion is None:
        raise ValueError(
            f"Interpretation fixture lacks distortion evidence: {case.case_id}"
        )
    if trusted.expected_mind not in {"E", "I"}:
        raise ValueError(f"Interpretation fixture lacks trusted source mind: {case.case_id}")
    return InterpretationEvaluationCase(
        case_id=case.case_id,
        family_id=case.family_id,
        variant_id=case.variant_id,
        source_mind=trusted.expected_mind,
        visible_manifestation_ids=case.input_scope.actual_artifact_ids,
        visible_observation_ids=case.input_scope.visible_observation_ids,
        allowed_option_ids=case.input_scope.allowed_option_ids,
        canonical_claim_ids=case.source_claim_ids,
        expected_option_id=trusted.expected_option_id,
        expected_motive_class=trusted.expected_motive_class,
        expected_action_tendency=trusted.expected_action_tendency,
        expected_interpretation_class=expected_class,
        distortion_evidence=InterpretationDistortionEvidence(
            evidence_kind=distortion.evidence_kind,
            visible_support_ids=distortion.visible_support_ids,
            candidate_claim_ids=distortion.candidate_claim_ids,
            contradicted_claim_ids=distortion.contradicted_claim_ids,
            expected_label=distortion.expected_label,
        ),
        evaluator_truth_artifact_ids=case.input_scope.forbidden_native_truth_ids,
    )


def _interpretation_candidate(
    case: ManualEvaluationCase,
) -> CandidateInterpretation:
    raw = case.candidate_payload
    candidate_id = str(raw["candidate_interpretation_id"])
    unresolved = raw.get("unresolved_ambiguity")
    if unresolved is True:
        unresolved_text: str | None = str(raw.get("uncertainty", "unresolved"))
    elif isinstance(unresolved, str) and unresolved.strip():
        unresolved_text = unresolved
    else:
        unresolved_text = None
    return CandidateInterpretation(
        candidate_interpretation_id=candidate_id,
        family_id=str(raw["family_id"]),
        variant_id=str(raw["variant_id"]),
        source_mind=str(raw["source_mind"]),
        claims=_claims(raw.get("claims")),
        cited_observation_ids=tuple(
            str(value) for value in raw.get("observed_observation_ids", ())
        ),
        route_tags=tuple(str(value) for value in raw.get("route_tags", ())),
        inferred_option_id=raw.get("inferred_option_id"),
        inferred_motive_class=raw.get("inferred_motive_class"),
        inferred_action_tendency=raw.get("inferred_action_tendency"),
        reasoning_operation=_interpretation_operation(raw),
        justification_kind=str(raw.get("justification_kind", "visible_evidence")),
        alternative_hypotheses=tuple(
            str(value) for value in raw.get("alternative_hypotheses", ())
        ),
        unresolved_ambiguity=unresolved_text,
        confidence=float(raw["confidence"]),
        uncertainty=str(raw["uncertainty"]),
    )


def _evaluate_interpretation_case(
    case: ManualEvaluationCase,
) -> tuple[SemanticEvaluationResult, str, tuple[str, ...], dict[str, DimensionOutcome]]:
    candidate = _interpretation_candidate(case)
    trusted_exposure = _exposure(
        case,
        subject_id=candidate.candidate_interpretation_id,
        cognition_mode="mixed",
    )
    result = evaluate_interpretation(
        case=_interpretation_case(case),
        candidate=candidate,
        trusted_exposure=trusted_exposure,
    )
    observed = result.observed_label
    issue_codes: list[str] = []
    if observed != "accurate":
        issue_codes.append(f"communication_distortion_{observed}")
    raw_issues = {item.issue_code for item in result.issues}
    if "overconfident_interpretation" in raw_issues:
        issue_codes.append("confidence_miscalibrated")

    visible_observations = set(case.input_scope.visible_observation_ids)
    unsupported = any(
        not claim.observation_ids
        or not set(claim.observation_ids).issubset(visible_observations)
        for claim in candidate.claims
    )
    if unsupported:
        issue_codes.append("unsupported_claim")
    supplements: dict[str, DimensionOutcome] = {
        "unsupported_claims": "fail" if unsupported else "pass",
        "provenance_completeness": "fail" if unsupported else "pass",
    }
    return result, observed, tuple(issue_codes), supplements


def _semantic_signature(raw_values: object) -> TrustedSemanticSignature:
    values = tuple(str(value) for value in raw_values or ())
    return TrustedSemanticSignature(
        concept_ids=tuple(
            value
            for value in values
            if not value.startswith("route:") and not value.startswith("option:")
        ),
        route_ids=tuple(
            value.removeprefix("route:")
            for value in values
            if value.startswith("route:")
        ),
        option_ids=tuple(
            value.removeprefix("option:") for value in values if value.startswith("option:")
        ),
    )


def _bilingual_terminology(raw_pairs: object) -> tuple[TerminologyUse, ...]:
    if not isinstance(raw_pairs, list):
        return ()
    uses: list[TerminologyUse] = []
    for raw in raw_pairs:
        if not isinstance(raw, Mapping):
            continue
        term_id = str(raw["terminology_id"])
        uses.extend(
            (
                TerminologyUse(
                    terminology_id=term_id,
                    language="sl",
                    surface_form=str(raw["sl_surface"]),
                ),
                TerminologyUse(
                    terminology_id=term_id,
                    language="en",
                    surface_form=str(raw["en_surface"]),
                ),
            )
        )
    return tuple(uses)


def _evaluate_bilingual(
    case: ManualEvaluationCase,
) -> tuple[SemanticEvaluationResult, str, tuple[str, ...], dict[str, DimensionOutcome]]:
    raw = case.candidate_payload
    trusted = case.trusted_expectation
    evaluation_case = BilingualEvaluationCase(
        case_id=case.case_id,
        family_id=case.family_id,
        trusted_signature=_semantic_signature(trusted.expected_semantic_signature),
        required_terminology_ids=trusted.required_terminology_ids,
    )
    candidate = BilingualCandidatePair(
        pair_id=str(raw["sample_id"]),
        family_id=str(raw["family_id"]),
        sl_variant_id=str(raw["sl_variant_id"]),
        en_variant_id=str(raw["en_variant_id"]),
        sl_text=str(raw["sl_text"]),
        en_text=str(raw["en_text"]),
        sl_signature=_semantic_signature(raw.get("semantic_signature_sl", ())),
        en_signature=_semantic_signature(raw.get("semantic_signature_en", ())),
        terminology_uses=_bilingual_terminology(raw.get("terminology_pairs")),
    )
    _, terminology_policy = _terminology_maps()
    result = evaluate_bilingual_pair(
        case=evaluation_case,
        candidate=candidate,
        terminology_policy=terminology_policy,
    )
    family_ok = candidate.family_id == evaluation_case.family_id
    raw_issues = {item.issue_code for item in result.issues}
    signature_mismatch = bool(
        raw_issues
        & {
            "sl_signature_mismatch",
            "en_signature_mismatch",
            "cross_language_semantic_mismatch",
        }
    )
    terminology_mismatch = "bilingual_terminology_mismatch" in raw_issues
    if not family_ok:
        observed = "semantic_drift"
        issue_codes = ("bilingual_family_mismatch",)
    elif signature_mismatch:
        observed = "semantic_drift"
        issue_codes = ("bilingual_signature_mismatch",)
    elif terminology_mismatch:
        observed = "terminology_drift"
        issue_codes = ("slovenian_terminology_inconsistent",)
    else:
        observed = "consistent"
        issue_codes = ()
    return result, observed, issue_codes, {}


def _evaluate_ego(
    case: ManualEvaluationCase,
) -> tuple[SemanticEvaluationResult, str, tuple[str, ...], dict[str, DimensionOutcome]]:
    raw = case.candidate_payload
    trusted = case.trusted_expectation
    if trusted.expected_sequence_id is None:
        raise ValueError(f"Ego fixture lacks trusted sequence: {case.case_id}")
    evaluation_case = EgoEvaluationCase(
        case_id=case.case_id,
        sequence_id=trusted.expected_sequence_id,
        measure_ids=trusted.expected_measure_ids,
        expected_motif_ids=trusted.expected_motif_ids,
        expected_translation_gap_ids=trusted.expected_translation_gap_ids,
        expected_unresolved_tension_ids=trusted.expected_unresolved_tension_ids,
        expected_projection_facets=trusted.expected_projection_facets,
        required_projection_minds=trusted.expected_projection_minds,
    )
    measure_ids = tuple(str(value) for value in raw.get("measure_ids", ()))
    projection_evidence = tuple(
        (
            str(item["mind"]),
            tuple(str(value) for value in item.get("measure_ids", ())),
        )
        for item in raw["projection_evidence"]
    )
    candidate = EgoEvaluationSample(
        sample_id=str(raw["sample_id"]),
        sequence_id=str(raw["sequence_id"]),
        measure_ids=measure_ids,
        motifs=tuple(
            EgoMotifCandidate(
                motif_id=str(item["motif_id"]),
                motif_kind=str(item["motif_kind"]),
                supporting_measure_ids=tuple(
                    str(value) for value in item.get("supporting_measure_ids", ())
                ),
            )
            for item in raw.get("motifs", ())
        ),
        recurring_translation_gap_ids=tuple(
            str(value) for value in raw.get("recurring_translation_gap_ids", ())
        ),
        unresolved_tension_ids=tuple(
            str(value) for value in raw.get("unresolved_tension_ids", ())
        ),
        projection_evidence=projection_evidence,
        projection_facets=tuple(
            str(value) for value in raw["projection_facets"]
        ),
        self_narrative_artifact_ids=tuple(
            str(value) for value in raw["self_narrative_artifact_ids"]
        ),
        composition_artifact_ids=tuple(
            str(value) for value in raw["composition_artifact_ids"]
        ),
    )
    result = evaluate_ego_sequence(case=evaluation_case, candidate=candidate)
    raw_issues = {item.issue_code for item in result.issues}
    if not candidate.motifs:
        # Empty prediction has no false positive; the evaluator's zero-precision
        # sentinel is normalized to the more specific missed-motif finding.
        raw_issues.discard("false_motif")
    issue_map = {
        "false_motif": "ego_false_motif",
        "motif_without_multi_measure_support": "ego_motif_support_below_threshold",
        "missed_motif": "ego_missed_motif",
        "translation_gap_continuity_mismatch": "ego_translation_gap_discontinuity",
        "unresolved_tension_continuity_mismatch": "ego_unresolved_tension_discontinuity",
        "modality_projection_mismatch": "ego_modality_projection_mismatch",
        "self_narrative_composition_conflation": "ego_self_narrative_used_as_composition",
        "ego_measure_scope_mismatch": "ego_measure_scope_mismatch",
    }
    issue_codes = tuple(
        alias for source, alias in issue_map.items() if source in raw_issues
    )
    if "false_motif" in raw_issues:
        observed = "false_motif"
    elif "missed_motif" in raw_issues:
        observed = "missed_motif"
    elif raw_issues & {
        "translation_gap_continuity_mismatch",
        "unresolved_tension_continuity_mismatch",
    }:
        observed = "history_discontinuity"
    elif raw_issues & {
        "modality_projection_mismatch",
        "self_narrative_composition_conflation",
    }:
        observed = "ego_boundary_failure"
    else:
        observed = "grounded_motif"
    supplements = {"provenance_completeness": "pass"}
    return result, observed, issue_codes, supplements


def evaluate_manual_case(case: ManualEvaluationCase) -> ManualCaseOutcome:
    """Evaluate one strict case and compare derived output with its gold contract."""

    dispatch = {
        "native_route": _evaluate_native,
        "interpretation": _evaluate_interpretation_case,
        "bilingual_pair": _evaluate_bilingual,
        "ego_sequence": _evaluate_ego,
    }
    result, observed, issue_codes, supplements = dispatch[case.subject_kind](case)
    dimension_outcomes = _declared_dimensions(
        case,
        result,
        supplements=supplements,
    )
    candidate_passed = result.passed
    actual_issues = tuple(sorted(issue_codes))
    expected_issues = tuple(sorted(case.expected_result.issue_codes))
    pass_matches = candidate_passed == case.expected_result.passed
    observed_matches = observed == case.expected_result.observed_label
    issues_match = actual_issues == expected_issues
    dimensions_match = dimension_outcomes == case.expected_result.dimension_outcomes
    failed_dimensions = _failed_dimensions(result, supplements)
    unexpected_failed_dimensions = tuple(
        sorted(
            set(failed_dimensions)
            - set(case.expected_result.dimension_outcomes)
        )
    )
    exact_match = all(
        (
            pass_matches,
            observed_matches,
            issues_match,
            dimensions_match,
            not unexpected_failed_dimensions,
        )
    )
    return ManualCaseOutcome(
        case_id=case.case_id,
        semantic_result=result,
        candidate_passed=candidate_passed,
        observed_label=observed,
        issue_codes=actual_issues,
        dimension_outcomes=dimension_outcomes,
        expected_passed=case.expected_result.passed,
        expected_observed_label=case.expected_result.observed_label,
        expected_issue_codes=expected_issues,
        expected_dimension_outcomes=case.expected_result.dimension_outcomes,
        failed_dimensions=failed_dimensions,
        unexpected_failed_dimensions=unexpected_failed_dimensions,
        pass_matches=pass_matches,
        observed_label_matches=observed_matches,
        issue_codes_match=issues_match,
        dimension_outcomes_match=dimensions_match,
        exact_match=exact_match,
        evaluator_model_calls=result.evaluator_model_calls,
    )


def evaluate_manual_fixture_set(
    fixture_root: str | Path | None = None,
) -> ManualFixtureSetOutcome:
    """Evaluate the complete manifest-bound set and return exact-match diagnostics."""

    root = _resolve_fixture_root(fixture_root)
    manifest = load_manual_fixture_manifest(root)
    cases = load_manual_evaluation_cases(root)
    outcomes = tuple(evaluate_manual_case(case) for case in cases)
    return ManualFixtureSetOutcome(
        manifest=manifest,
        cases=cases,
        outcomes=outcomes,
        exact_match_count=sum(outcome.exact_match for outcome in outcomes),
        evaluator_model_calls=0,
    )


__all__ = [
    "DEFAULT_FIXTURE_ROOT",
    "ManualCaseOutcome",
    "ManualEvaluationCase",
    "ManualFixtureManifest",
    "ManualFixtureSetOutcome",
    "evaluate_manual_case",
    "evaluate_manual_fixture_set",
    "load_manual_evaluation_cases",
    "load_manual_fixture_manifest",
]
