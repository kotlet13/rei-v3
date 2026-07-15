"""C7 integrated semantic and longitudinal benchmark.

The runner in this module is deliberately model-free.  It replays current-tree
controlled/profile and person-causality contracts, cold-validates pinned C1--C6
evidence, preserves every metric as a separate dimension, and records open
model-backed quality gates as blockers instead of turning them into a score.
"""

from __future__ import annotations

from collections import Counter
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
)
from .body_mapper_eval import BodyMapperEvaluationReport
from .controlled_profile_eval import (
    ControlledProfileAcceptanceReport,
    evaluate_controlled_profile_acceptance,
)
from .longitudinal_eval import LongitudinalEvaluationReport
from .models import SemanticEvaluationResult, SemanticEvaluationRun
from .person_causality_eval import (
    PersonCausalityEvaluationReport,
    evaluate_person_causality,
)
from .racio_interpreter_benchmark import (
    C3BenchmarkCaseResult,
    C3BenchmarkRunMetrics,
    evaluate_c3_benchmark_run,
    load_c3_racio_interpreter_benchmark,
)
from .report import render_evaluation_report


C7_REPORT_FILENAMES: tuple[str, ...] = (
    "integrated_benchmark.json",
    "controlled_profile.json",
    "person_causality.json",
    "ablations.json",
    "failures.jsonl",
    "dimensions.md",
    "provenance.json",
)
C7_MAX_MANIFEST_BYTES = 256 * 1024
C7_MAX_SOURCE_ARTIFACT_BYTES = 2 * 1024 * 1024
C7_MAX_REPORT_ARTIFACT_BYTES = 32 * 1024 * 1024
C7_EVALUATOR_REVISION = "c7-v1"
C7_EXPECTED_MANIFEST_SHA256 = (
    "cfed2f5bafeb7cb8a47d04d580443df3b28cce90b876a46ce9de5ad8c072b5a7"
)
C7_EXPECTED_SOURCE_LAYOUT: tuple[tuple[str, str, str], ...] = (
    (
        "c1_fixture_manifest",
        "tests/fixtures/semantic_lab_v1/manifest.json",
        "current_tree_model_free",
    ),
    (
        "c2_metrics",
        "Docs/evals/semantic_lab_v1/c2-deterministic-2026-07-14/metrics.json",
        "current_tree_model_free",
    ),
    (
        "c3_baseline_results",
        "Docs/evals/semantic_lab_v1/c3-racio-interpreter-qwen3.5-27b-v5-2026-07-14/baseline_results.jsonl",
        "historical_model_backed_run",
    ),
    (
        "c3_metrics",
        "Docs/evals/semantic_lab_v1/c3-racio-interpreter-qwen3.5-27b-v5-2026-07-14/metrics.json",
        "historical_model_backed_run",
    ),
    (
        "c3_model_results",
        "Docs/evals/semantic_lab_v1/c3-racio-interpreter-qwen3.5-27b-v5-2026-07-14/results.jsonl",
        "historical_model_backed_run",
    ),
    (
        "c3_provenance",
        "Docs/evals/semantic_lab_v1/c3-racio-interpreter-qwen3.5-27b-v5-2026-07-14/provenance.json",
        "historical_model_backed_run",
    ),
    (
        "c4_dinov2_smoke",
        "Docs/evals/semantic_lab_v1/c4_dinov2_visual_valuation_smoke_2026-07-14.md",
        "historical_model_backed_run",
    ),
    (
        "c4_model_screen",
        "Docs/evals/semantic_lab_v1/c4_visual_model_selection_addendum_2026-07-14.md",
        "historical_model_backed_run",
    ),
    (
        "c4_runtime_acceptance",
        "Docs/evals/semantic_lab_v1/c4_runtime_integration_acceptance_2026-07-14.md",
        "current_tree_technical_contract",
    ),
    (
        "c5_body_mapper",
        "Docs/evals/semantic_lab_v1/c5-body-mapper-v3-2026-07-14/body_mapper_evaluation.json",
        "current_tree_bounded_contract",
    ),
    (
        "c6_longitudinal",
        "Docs/evals/semantic_lab_v1/c6-longitudinal-2026-07-14/longitudinal_evaluation.json",
        "current_tree_bounded_contract",
    ),
)
C7_EXPECTED_SOURCE_DIGESTS: tuple[tuple[str, str, int], ...] = (
    (
        "c1_fixture_manifest",
        "c22a299afc3063d7edf338d738396c18ca9298081d17374e4a1b153b3fad606e",
        5975,
    ),
    (
        "c2_metrics",
        "3cb01e0914919c6d266bbfc8572049108f51e9884246b66564ded52ce3bfc1c5",
        350293,
    ),
    (
        "c3_baseline_results",
        "1289834b0fddcb171554fd85ed328de32c139894a3108fb78dfd7017099cbc7f",
        217548,
    ),
    (
        "c3_metrics",
        "0c47be2249d379a289c5b0acfe348a0a2223ebde13427df4349411aef3fa21cc",
        714,
    ),
    (
        "c3_model_results",
        "ca7d6e3e20a6198bf2dd6316d1f694d2cb709eb2973892e1f364f8c137108a39",
        308823,
    ),
    (
        "c3_provenance",
        "46d27a501735cc7e2bf6a912ee495a7c6aa1342b52ab02da86193a723497127c",
        1511,
    ),
    (
        "c4_dinov2_smoke",
        "aaef9f79e7784b953c6f3aa38b28a0e782cec1226e83195d3c238e76bd99e8bf",
        9006,
    ),
    (
        "c4_model_screen",
        "9707967c903bf818f28b994e7f49f09828984cade23e81a8f69342ed90b35760",
        15066,
    ),
    (
        "c4_runtime_acceptance",
        "3c421502bc190cc833a62e15b65f930f2f6eba7edee28c9c71bcc161f6a08d5b",
        6820,
    ),
    (
        "c5_body_mapper",
        "e9e7dba13b1f65435ced65228894f862717dce2f0d33174743f9fb8a3890e72e",
        439601,
    ),
    (
        "c6_longitudinal",
        "b6ff3c5abee578661a638621ddb6b6299d5159e5dc1668ac844b784ddc7b2fdf",
        42742,
    ),
)

C7AblationFamily = Literal[
    "racio_provider",
    "emocio_cognition_mode",
    "instinkt_effect_source",
    "interpreter_input_mode",
    "ego_motif_mode",
    "acceptance_mode",
]
C7_ABLATION_FAMILIES: tuple[C7AblationFamily, ...] = (
    "racio_provider",
    "emocio_cognition_mode",
    "instinkt_effect_source",
    "interpreter_input_mode",
    "ego_motif_mode",
    "acceptance_mode",
)
C7_EXPECTED_ABLATION_ARMS: dict[C7AblationFamily, tuple[str, ...]] = {
    "racio_provider": ("deterministic", "qwen3.5_27b_v5"),
    "emocio_cognition_mode": (
        "structured_only",
        "render_observe",
        "visual_cognition",
    ),
    "instinkt_effect_source": ("manual_effects", "auto_mapper"),
    "interpreter_input_mode": ("structured_only", "vlm"),
    "ego_motif_mode": ("structured_motif", "semantic_motif_hypothesis"),
    "acceptance_mode": ("accepting", "mixed", "conflicted"),
}

C7MetricDimension = Literal[
    "processor_route_identity",
    "source_grounding",
    "option_choice",
    "abstention",
    "translation_fidelity",
    "character_causality",
    "conscious_behavior_divergence",
    "spoznanje",
    "cross_language_consistency",
    "visual_robustness",
    "body_mapper_agreement",
    "longitudinal_motif_precision",
    "latency",
    "vram",
    "ram",
    "artifact_size",
    "failure_mode",
]
C7_METRIC_DIMENSIONS: tuple[C7MetricDimension, ...] = (
    "processor_route_identity",
    "source_grounding",
    "option_choice",
    "abstention",
    "translation_fidelity",
    "character_causality",
    "conscious_behavior_divergence",
    "spoznanje",
    "cross_language_consistency",
    "visual_robustness",
    "body_mapper_agreement",
    "longitudinal_motif_precision",
    "latency",
    "vram",
    "ram",
    "artifact_size",
    "failure_mode",
)

C7MetricStatus = Literal[
    "passed",
    "failed",
    "blocked",
    "observed",
    "not_applicable",
    "not_measured",
]
C7ArmStatus = Literal["passed", "failed", "blocked", "observed"]
C7EvidenceScope = Literal[
    "current_tree_model_free",
    "current_tree_technical_contract",
    "current_tree_bounded_contract",
    "historical_model_backed_run",
]


class C7SourceArtifactSpec(FrozenModel):
    artifact_key: NonEmptyId
    path: NonEmptyText
    sha256: HashDigest
    size_bytes: int = Field(ge=1, le=C7_MAX_SOURCE_ARTIFACT_BYTES)
    evidence_scope: C7EvidenceScope

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        candidate = Path(self.path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError("C7 source paths must stay relative to the repository")
        if "\\" in self.path:
            raise ValueError("C7 source paths must use portable forward slashes")
        return self


class C7IntegratedManifest(FrozenModel):
    schema_version: Literal["rei-c7-integrated-benchmark-manifest-v1"]
    benchmark_id: Literal["rei-c7-integrated-semantic-longitudinal-v1"]
    evaluation_date: Literal["2026-07-15"]
    input_baseline_commit: Literal[
        "5f93731a03fd0bb2c72b0bcdf6aaa6257cbd583e"
    ]
    human_authored: Literal[True]
    model_generated_gold: Literal[False]
    training_export: Literal[False]
    current_model_calls_allowed: Literal[False]
    expected_research_quality_status: Literal["blocked"]
    semantic_authority_granted: Literal[False]
    production_authority_granted: Literal[False]
    required_ablation_families: tuple[C7AblationFamily, ...]
    required_metric_dimensions: tuple[C7MetricDimension, ...]
    source_artifacts: tuple[C7SourceArtifactSpec, ...] = Field(
        min_length=11,
        max_length=32,
    )

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if self.required_ablation_families != C7_ABLATION_FAMILIES:
            raise ValueError("C7 manifest must enumerate every ablation in plan order")
        if self.required_metric_dimensions != C7_METRIC_DIMENSIONS:
            raise ValueError("C7 manifest must enumerate all 17 metric dimensions")
        keys = tuple(item.artifact_key for item in self.source_artifacts)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("C7 source artifacts must use canonical unique key order")
        layout = tuple(
            (item.artifact_key, item.path, item.evidence_scope)
            for item in self.source_artifacts
        )
        if layout != C7_EXPECTED_SOURCE_LAYOUT:
            raise ValueError("C7 source artifact paths or scopes differ from contract")
        digests = tuple(
            (item.artifact_key, item.sha256, item.size_bytes)
            for item in self.source_artifacts
        )
        if digests != C7_EXPECTED_SOURCE_DIGESTS:
            raise ValueError("C7 source artifact digests differ from contract")
        return self


class C7EvidenceArtifactRef(FrozenArtifactModel):
    schema_version: Literal["rei-c7-evidence-artifact-ref-v1"] = (
        "rei-c7-evidence-artifact-ref-v1"
    )
    artifact_ref_id: NonEmptyId
    artifact_key: NonEmptyId
    path: NonEmptyText
    sha256: HashDigest
    size_bytes: int = Field(ge=1, le=C7_MAX_SOURCE_ARTIFACT_BYTES)
    evidence_scope: C7EvidenceScope
    cold_verified: Literal[True] = True
    artifact_ref_hash: HashDigest

    @classmethod
    def create(cls, spec: C7SourceArtifactSpec) -> "C7EvidenceArtifactRef":
        base = {
            "schema_version": "rei-c7-evidence-artifact-ref-v1",
            **spec.model_dump(mode="python", round_trip=True),
            "cold_verified": True,
        }
        artifact_ref_id = content_id("c7_evidence_ref", base)
        payload = {"artifact_ref_id": artifact_ref_id, **base}
        return cls(**payload, artifact_ref_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"artifact_ref_id", "artifact_ref_hash"},
        )
        if self.artifact_ref_id != content_id("c7_evidence_ref", base):
            raise ValueError("C7 evidence reference ID differs from its content")
        payload = {"artifact_ref_id": self.artifact_ref_id, **base}
        if self.artifact_ref_hash != sha256_hex(payload):
            raise ValueError("C7 evidence reference hash differs from its content")
        return self


class C7AblationArmResult(FrozenModel):
    arm_id: NonEmptyId
    status: C7ArmStatus
    execution_scope: Literal[
        "current_model_free",
        "current_technical_contract",
        "historical_model_backed",
        "not_executed",
    ]
    current_model_call_count: int = Field(ge=0)
    target_improvement_observed: bool | None = None
    semantic_gate_passed: bool | None = None
    evidence_artifact_keys: tuple[NonEmptyId, ...] = ()
    blocker_codes: tuple[NonEmptyId, ...] = ()
    limitation: NonEmptyText

    @model_validator(mode="after")
    def validate_arm(self) -> Self:
        if self.evidence_artifact_keys != tuple(
            sorted(set(self.evidence_artifact_keys))
        ):
            raise ValueError("C7 ablation evidence keys must be sorted and unique")
        if self.blocker_codes != tuple(sorted(set(self.blocker_codes))):
            raise ValueError("C7 ablation blocker codes must be sorted and unique")
        if self.execution_scope == "not_executed" and (
            self.status != "blocked"
            or self.current_model_call_count != 0
            or self.semantic_gate_passed is not None
        ):
            raise ValueError("A non-executed C7 arm must remain a zero-call blocker")
        if self.status in {"blocked", "failed"} and not self.blocker_codes:
            raise ValueError("Blocked/failed C7 arms require an explicit blocker")
        if self.status == "passed" and (
            self.blocker_codes or self.semantic_gate_passed is False
        ):
            raise ValueError("A passing C7 arm cannot retain a quality blocker")
        if (
            self.execution_scope == "historical_model_backed"
            and self.status == "passed"
        ):
            raise ValueError("Historical model evidence cannot pass a current C7 arm")
        return self


class C7AblationResult(FrozenModel):
    family: C7AblationFamily
    family_status: Literal["passed", "blocked", "observed"]
    one_factor_at_a_time: Literal[True] = True
    interaction_effects_measured: Literal[False] = False
    arms: tuple[C7AblationArmResult, ...]

    @model_validator(mode="after")
    def validate_family(self) -> Self:
        expected_arms = C7_EXPECTED_ABLATION_ARMS[self.family]
        if tuple(item.arm_id for item in self.arms) != expected_arms:
            raise ValueError("C7 ablation arms are incomplete or out of order")
        expected_status = (
            "blocked"
            if any(item.status in {"blocked", "failed"} for item in self.arms)
            else "passed"
            if all(item.status == "passed" for item in self.arms)
            else "observed"
        )
        if self.family_status != expected_status:
            raise ValueError("C7 ablation family status differs from its arms")
        return self


class C7MetricObservation(FrozenModel):
    dimension: C7MetricDimension
    status: C7MetricStatus
    value: Annotated[float, Field(allow_inf_nan=False)] | None = None
    numerator: int | None = Field(default=None, ge=0)
    denominator: int | None = Field(default=None, ge=1)
    unit: NonEmptyText | None = None
    evidence_artifact_keys: tuple[NonEmptyId, ...] = ()
    blocker_codes: tuple[NonEmptyId, ...] = ()
    limitation: NonEmptyText

    @model_validator(mode="after")
    def validate_metric(self) -> Self:
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("C7 metric numerator and denominator must be paired")
        if self.numerator is not None and self.numerator > self.denominator:
            raise ValueError("C7 metric numerator cannot exceed its denominator")
        if self.evidence_artifact_keys != tuple(
            sorted(set(self.evidence_artifact_keys))
        ):
            raise ValueError("C7 metric evidence keys must be sorted and unique")
        if self.blocker_codes != tuple(sorted(set(self.blocker_codes))):
            raise ValueError("C7 metric blocker codes must be sorted and unique")
        if self.status in {"blocked", "failed"} and not self.blocker_codes:
            raise ValueError("Blocked/failed C7 metrics require blocker codes")
        if self.status in {"not_measured", "not_applicable"} and (
            self.value is not None or self.numerator is not None
        ):
            raise ValueError("Unmeasured/not-applicable C7 metrics cannot claim values")
        if self.status == "passed" and self.blocker_codes:
            raise ValueError("A passing C7 metric cannot retain blocker codes")
        return self


class C7ResourceObservation(FrozenModel):
    observation_id: NonEmptyId
    component: NonEmptyId
    evidence_scope: Literal["historical_observation"]
    call_count: int = Field(ge=1)
    mean_latency_seconds: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    max_latency_seconds: Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
    max_vram_bytes: int = Field(ge=0)
    ram_bytes: None = None
    evidence_artifact_keys: tuple[NonEmptyId, ...]
    limitation: NonEmptyText

    @classmethod
    def create(
        cls,
        *,
        component: str,
        call_count: int,
        mean_latency_seconds: float,
        max_latency_seconds: float,
        max_vram_bytes: int,
        evidence_artifact_keys: tuple[str, ...],
        limitation: str,
    ) -> "C7ResourceObservation":
        base = {
            "component": component,
            "evidence_scope": "historical_observation",
            "call_count": call_count,
            "mean_latency_seconds": mean_latency_seconds,
            "max_latency_seconds": max_latency_seconds,
            "max_vram_bytes": max_vram_bytes,
            "ram_bytes": None,
            "evidence_artifact_keys": tuple(
                sorted(set(evidence_artifact_keys))
            ),
            "limitation": limitation,
        }
        return cls(
            observation_id=content_id("c7_resource_observation", base),
            **base,
        )

    @model_validator(mode="after")
    def validate_resource(self) -> Self:
        if self.max_latency_seconds < self.mean_latency_seconds:
            raise ValueError("C7 max latency cannot be lower than mean latency")
        if self.evidence_artifact_keys != tuple(
            sorted(set(self.evidence_artifact_keys))
        ):
            raise ValueError("C7 resource evidence keys must be sorted and unique")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"observation_id"},
        )
        if self.observation_id != content_id("c7_resource_observation", base):
            raise ValueError("C7 resource observation ID differs from content")
        return self


class C7FailureRecord(FrozenArtifactModel):
    schema_version: Literal["rei-c7-failure-record-v1"] = (
        "rei-c7-failure-record-v1"
    )
    failure_id: NonEmptyId
    blocker_code: NonEmptyId
    affected_ablation_families: tuple[C7AblationFamily, ...]
    affected_metric_dimensions: tuple[C7MetricDimension, ...]
    evidence_artifact_keys: tuple[NonEmptyId, ...]
    reproducible: Literal[True] = True
    current_tree_failure: bool
    detail: NonEmptyText
    failure_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        blocker_code: str,
        affected_ablation_families: tuple[C7AblationFamily, ...],
        affected_metric_dimensions: tuple[C7MetricDimension, ...],
        evidence_artifact_keys: tuple[str, ...],
        current_tree_failure: bool,
        detail: str,
    ) -> "C7FailureRecord":
        base = {
            "schema_version": "rei-c7-failure-record-v1",
            "blocker_code": blocker_code,
            "affected_ablation_families": tuple(
                family
                for family in C7_ABLATION_FAMILIES
                if family in set(affected_ablation_families)
            ),
            "affected_metric_dimensions": tuple(
                dimension
                for dimension in C7_METRIC_DIMENSIONS
                if dimension in set(affected_metric_dimensions)
            ),
            "evidence_artifact_keys": tuple(sorted(set(evidence_artifact_keys))),
            "reproducible": True,
            "current_tree_failure": current_tree_failure,
            "detail": detail,
        }
        failure_id = content_id("c7_failure", base)
        payload = {"failure_id": failure_id, **base}
        return cls(**payload, failure_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        if not self.affected_ablation_families and not self.affected_metric_dimensions:
            raise ValueError("A C7 failure must affect an ablation or metric")
        if self.affected_ablation_families != tuple(
            family
            for family in C7_ABLATION_FAMILIES
            if family in set(self.affected_ablation_families)
        ):
            raise ValueError("C7 failure ablation families must use plan order")
        if self.affected_metric_dimensions != tuple(
            dimension
            for dimension in C7_METRIC_DIMENSIONS
            if dimension in set(self.affected_metric_dimensions)
        ):
            raise ValueError("C7 failure metrics must use plan order")
        if self.evidence_artifact_keys != tuple(
            sorted(set(self.evidence_artifact_keys))
        ):
            raise ValueError("C7 failure evidence keys must be sorted and unique")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"failure_id", "failure_hash"},
        )
        if self.failure_id != content_id("c7_failure", base):
            raise ValueError("C7 failure ID differs from its content")
        payload = {"failure_id": self.failure_id, **base}
        if self.failure_hash != sha256_hex(payload):
            raise ValueError("C7 failure hash differs from its content")
        return self


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


def _read_bounded(path: Path, *, maximum_bytes: int) -> bytes:
    source = path.expanduser()
    _reject_reparse_components(source, label="C7 evidence")
    try:
        before = source.lstat()
    except OSError as exc:
        raise ValueError(f"C7 evidence is unavailable: {source}") from exc
    if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
        raise ValueError(f"C7 evidence must be a regular non-link file: {source}")
    if before.st_size <= 0 or before.st_size > maximum_bytes:
        raise ValueError(f"C7 evidence exceeds its bounded file size: {source}")

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
            raise ValueError(f"C7 evidence changed before it was opened: {source}")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            payload = handle.read(maximum_bytes + 1)
        after = source.lstat()
    except OSError as exc:
        raise ValueError(f"C7 evidence could not be read safely: {source}") from exc
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
        raise ValueError(f"C7 evidence changed while being read: {source}")
    return payload


def load_c7_manifest(path: str | Path) -> tuple[C7IntegratedManifest, str]:
    payload = _read_bounded(Path(path), maximum_bytes=C7_MAX_MANIFEST_BYTES)
    manifest = C7IntegratedManifest.model_validate_json(payload)
    manifest_sha256 = hashlib.sha256(payload).hexdigest()
    if manifest_sha256 != C7_EXPECTED_MANIFEST_SHA256:
        raise ValueError("C7 manifest bytes differ from the frozen contract")
    return manifest, manifest_sha256


def verify_c7_source_artifacts(
    *,
    repository_root: str | Path,
    manifest: C7IntegratedManifest,
) -> tuple[tuple[C7EvidenceArtifactRef, ...], dict[str, bytes]]:
    requested_root = Path(repository_root).expanduser()
    _reject_reparse_components(requested_root, label="C7 repository root")
    root = requested_root.resolve()
    if not root.is_dir():
        raise ValueError("C7 repository root must be an existing directory")
    payloads: dict[str, bytes] = {}
    refs: list[C7EvidenceArtifactRef] = []
    for spec in manifest.source_artifacts:
        candidate = root / spec.path
        source = candidate.resolve()
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise ValueError("C7 evidence escaped the repository root") from exc
        payload = _read_bounded(
            candidate,
            maximum_bytes=C7_MAX_SOURCE_ARTIFACT_BYTES,
        )
        if (
            len(payload) != spec.size_bytes
            or hashlib.sha256(payload).hexdigest() != spec.sha256
        ):
            raise ValueError(f"C7 pinned evidence differs: {spec.artifact_key}")
        payloads[spec.artifact_key] = payload
        refs.append(C7EvidenceArtifactRef.create(spec))
    return tuple(refs), payloads


class C7ImportedEvidenceSummary(FrozenModel):
    """Typed, cold-replayed facts imported from the pinned C1--C6 record."""

    schema_version: Literal["rei-c7-imported-evidence-summary-v1"] = (
        "rei-c7-imported-evidence-summary-v1"
    )
    c1_family_count: Literal[24]
    c1_variant_count: Literal[192]
    c1_review_status: Literal["canon_approved"]
    c1_model_generated_gold: Literal[False]
    c1_training_export: Literal[False]
    c2_result_count: Literal[32]
    c2_passing_result_count: Literal[8]
    c2_dimension_count: Literal[26]
    c2_evaluator_model_call_count: Literal[0]
    c2_dimensions_preserved_separately: Literal[True]
    c2_global_rei_score_present: Literal[False]
    c3_metrics: C3BenchmarkRunMetrics
    c3_model_id: Literal["qwen3.5:27b"]
    c3_model_digest: Literal[
        "7653528ba5cba4dd8e19da24aaddc7f4d0b5ecd93571c0825dfd4137958ec06e"
    ]
    c3_response_evidence_count: Literal[29]
    c3_missing_response_evidence_count: Literal[3]
    c3_full_gpu_offload_evidence_count: Literal[29]
    c4_runtime_technical_contract_passed: Literal[True]
    c4_visual_robustness_executed_cell_count: Literal[0]
    c4_visual_robustness_required_cell_count: Literal[48]
    c4_semantic_quality_gate_passed: Literal[False]
    c4_production_authority_granted: Literal[False]
    c4_generated_images_are_external_evidence: Literal[False]
    c5_semantic_family_count: Literal[12]
    c5_positive_case_count: Literal[36]
    c5_passing_case_count: Literal[36]
    c5_negative_control_count: Literal[17]
    c5_passing_negative_control_count: Literal[17]
    c5_effect_vector_count: Literal[72]
    c5_passing_effect_vector_count: Literal[72]
    c5_manual_auto_agreement_count: Literal[33]
    c5_manual_auto_all_case_agreement_count: Literal[36]
    c5_gate_passed: Literal[True]
    c6_sequence_count: Literal[10]
    c6_total_cycle_count: Literal[100]
    c6_passing_sequence_count: Literal[10]
    c6_corpus_sha256: Literal[
        "0013c4f16aab4737c9ecc0530145e486602c0e21fe3770bedb12397232453c7f"
    ]
    c6_corpus_hash: Literal[
        "dc621664dffe1ce96c877e0f6251d7d84e80a7d5b2e521e63cc8ddff13e9e0de"
    ]
    c6_template_request_hash: Literal[
        "6b0aba367a3b895f724b24d2b0ca1005d9530b8729c5766c12ec2f8f0529f88d"
    ]
    c6_visual_signal_cycle_count: Literal[100]
    c6_predicted_body_signal_cycle_count: Literal[100]
    c6_measured_body_signal_cycle_count: Literal[0]
    c6_motif_true_positive_count: Literal[40]
    c6_motif_false_positive_count: Literal[0]
    c6_motif_false_negative_count: Literal[0]
    c6_simulated_spoznanje_cycle_count: Literal[85]
    c6_technical_gate_passed: Literal[True]
    c6_semantic_authority_granted: Literal[False]

    @model_validator(mode="after")
    def validate_c3_gate(self) -> Self:
        expected = {
            "benchmark_id": "rei-c3-racio-interpreter-benchmark-v1",
            "provider_mode": "ollama",
            "case_count": 32,
            "model_call_count": 32,
            "structured_output_valid_count": 29,
            "citation_scope_failure_count": 3,
            "hidden_truth_leakage_count": 0,
            "profile_leakage_count": 0,
            "input_packet_mutation_count": 0,
            "provenance_scope_failure_count": 0,
            "unambiguous_count": 16,
            "unambiguous_exact_option_count": 16,
            "unambiguous_exact_action_count": 16,
            "unambiguous_exact_motive_count": 14,
            "ambiguous_count": 16,
            "ambiguous_gate_pass_count": 13,
            "bilingual_pair_count": 16,
            "bilingual_consistent_pair_count": 14,
            "passed_case_count": 27,
            "baseline_unambiguous_exact_option_count": 0,
            "model_outperforms_baseline": True,
            "structural_gate_pass": False,
            "quality_gate_pass": False,
        }
        if self.c3_metrics.model_dump(mode="python") != expected:
            raise ValueError("C7 imported C3 metrics differ from the pinned v5 run")
        return self


def _json_object(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"C7 {label} must be canonical JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"C7 {label} must contain a JSON object")
    return value


def _c3_results(payload: bytes, *, label: str) -> tuple[C3BenchmarkCaseResult, ...]:
    lines = tuple(line for line in payload.splitlines() if line.strip())
    if len(lines) != 32:
        raise ValueError(f"C7 {label} must contain exactly 32 C3 results")
    try:
        return tuple(C3BenchmarkCaseResult.model_validate_json(line) for line in lines)
    except ValueError as exc:
        raise ValueError(f"C7 {label} failed cold typed validation") from exc


def build_c7_resource_observations() -> tuple[C7ResourceObservation, ...]:
    historical_total_duration_ns = 88_897_727_545
    historical_response_count = 29
    return (
        C7ResourceObservation.create(
            component="c3_qwen3_5_27b_ollama",
            call_count=historical_response_count,
            mean_latency_seconds=(
                historical_total_duration_ns
                / historical_response_count
                / 1_000_000_000
            ),
            max_latency_seconds=14.974155042,
            max_vram_bytes=19_040_451_951,
            evidence_artifact_keys=("c3_model_results", "c3_provenance"),
            limitation=(
                "Historical response telemetry exists for 29 of 32 model calls; "
                "three failed calls emitted no response evidence and RAM was not measured."
            ),
        ),
    )


def validate_c7_imported_evidence(
    *,
    repository_root: str | Path,
    payloads: dict[str, bytes],
) -> tuple[C7ImportedEvidenceSummary, tuple[C7ResourceObservation, ...]]:
    """Cold-validate pinned evidence and recompute the C3 historical metrics."""

    required = {
        "c1_fixture_manifest",
        "c2_metrics",
        "c3_baseline_results",
        "c3_metrics",
        "c3_model_results",
        "c3_provenance",
        "c4_dinov2_smoke",
        "c4_model_screen",
        "c4_runtime_acceptance",
        "c5_body_mapper",
        "c6_longitudinal",
    }
    if set(payloads) != required:
        raise ValueError("C7 evidence payload set differs from the manifest contract")
    requested_root = Path(repository_root).expanduser()
    _reject_reparse_components(requested_root, label="C7 repository root")
    root = requested_root.resolve()
    if not root.is_dir():
        raise ValueError("C7 repository root must be an existing directory")

    c1 = _json_object(payloads["c1_fixture_manifest"], label="C1 manifest")
    c1_expected = {
        "family_count": 24,
        "variant_count": 192,
        "review_status": "canon_approved",
        "model_generated_gold": False,
        "training_export": False,
    }
    if any(c1.get(key) != value for key, value in c1_expected.items()):
        raise ValueError("C7 C1 corpus facts differ from the approved manifest")
    files = c1.get("files")
    if not isinstance(files, list) or len(files) != 24:
        raise ValueError("C7 C1 manifest must enumerate all 24 families")
    if sum(int(item["variant_count"]) for item in files) != 192:
        raise ValueError("C7 C1 family variant counts differ from the corpus total")
    expected_variant_modes = (
        "sl_canonical",
        "sl_paraphrase",
        "en_operational_gloss",
        "keyword_trap",
        "same_behavior_different_route",
        "same_route_different_behavior",
        "missing_information",
        "contradictory_surface_cue",
    )
    if tuple(c1.get("variant_modes", ())) != expected_variant_modes:
        raise ValueError("C7 C1 variant modes differ from the approved corpus")
    c1_fixture_root = root / "tests" / "fixtures" / "semantic_lab_v1"
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("C7 C1 family reference must be an object")
        relative = Path(str(item.get("path", "")))
        if relative.is_absolute() or len(relative.parts) != 1:
            raise ValueError("C7 C1 family fixture must stay directly below its root")
        child_payload = _read_bounded(
            c1_fixture_root / relative,
            maximum_bytes=C7_MAX_SOURCE_ARTIFACT_BYTES,
        )
        if hashlib.sha256(child_payload).hexdigest() != item.get("sha256"):
            raise ValueError("C7 C1 family fixture hash differs from its manifest")
        child = _json_object(child_payload, label="C1 family fixture")
        variants = child.get("variants")
        if (
            child.get("schema_version") != "rei-semantic-family-fixture-v1"
            or child.get("family_id") != item.get("family_id")
            or child.get("review_status") != "canon_approved"
            or child.get("model_generated_gold") is not False
            or child.get("training_export") is not False
            or item.get("variant_count") != 8
            or not isinstance(variants, list)
            or len(variants) != 8
        ):
            raise ValueError("C7 C1 family fixture differs from the approved contract")

    c2 = _json_object(payloads["c2_metrics"], label="C2 metrics")
    c2_results = c2.get("results")
    c2_dimensions = c2.get("dimensions")
    c2_policy = c2.get("report_policy")
    if (
        c2.get("schema_version") != "rei-semantic-metrics-report-v1"
        or c2.get("evaluator_version") != "c2-v1"
        or c2.get("result_count") != 32
        or c2.get("evaluator_model_calls") != 0
        or not isinstance(c2_results, list)
        or len(c2_results) != 32
        or sum(item.get("passed") is True for item in c2_results) != 8
        or not isinstance(c2_dimensions, dict)
        or len(c2_dimensions) != 26
        or c2_policy
        != {
            "dimensions_preserved_separately": True,
            "global_rei_score": False,
            "single_cross_dimension_rank": False,
        }
    ):
        raise ValueError("C7 C2 metrics differ from the deterministic replay record")
    typed_c2_results = tuple(
        SemanticEvaluationResult.model_validate_json(canonical_json_bytes(item))
        for item in c2_results
    )
    c2_run = SemanticEvaluationRun(
        run_id=c2["run_id"],
        source_manifest_hash=c2["source_manifest_hash"],
        evaluator_version=c2["evaluator_version"],
        results=typed_c2_results,
        manually_reviewed_case_ids=tuple(c2["manually_reviewed_case_ids"]),
        ablation_ids=tuple(c2["ablation_ids"]),
        resource_telemetry_artifact_ids=tuple(
            c2["resource_telemetry_artifact_ids"]
        ),
        evaluator_model_calls=c2["evaluator_model_calls"],
    )
    if render_evaluation_report(c2_run)["metrics.json"] != payloads["c2_metrics"]:
        raise ValueError("C7 C2 metrics fail byte-identical typed replay")

    suite = load_c3_racio_interpreter_benchmark(
        root
        / "knowledge"
        / "canon_v2"
        / "semantic_lab_v1"
        / "c3_racio_interpreter"
        / "manifest.json"
    )
    model_results = _c3_results(
        payloads["c3_model_results"], label="C3 model results"
    )
    baseline_results = _c3_results(
        payloads["c3_baseline_results"], label="C3 baseline results"
    )
    c3_metrics = C3BenchmarkRunMetrics.model_validate_json(payloads["c3_metrics"])
    recomputed_metrics = evaluate_c3_benchmark_run(
        suite=suite,
        provider_mode="ollama",
        results=model_results,
        model_call_count=32,
        baseline_results=baseline_results,
    )
    if recomputed_metrics != c3_metrics:
        raise ValueError("C7 C3 metrics differ from cold result replay")

    c3_provenance = _json_object(
        payloads["c3_provenance"], label="C3 provenance"
    )
    suite_files = {item.path: item.sha256 for item in suite.manifest.files}
    c3_hash_contract = {
        "benchmark_manifest_hash": suite.manifest_file_hash,
        "public_cases_hash": suite_files["public_cases.jsonl"],
        "gold_hash": suite_files["gold.jsonl"],
        "results_sha256": hashlib.sha256(
            payloads["c3_model_results"]
        ).hexdigest(),
        "baseline_results_sha256": hashlib.sha256(
            payloads["c3_baseline_results"]
        ).hexdigest(),
        "metrics_sha256": hashlib.sha256(payloads["c3_metrics"]).hexdigest(),
    }
    if any(
        c3_provenance.get(key) != value
        for key, value in c3_hash_contract.items()
    ):
        raise ValueError("C7 C3 provenance does not close over the pinned run")
    model_candidate = c3_provenance.get("model_candidate")
    if (
        c3_provenance.get("model_call_count") != 32
        or c3_provenance.get("quality_gate_pass") is not False
        or c3_provenance.get("provider_mode") != "ollama"
        or not isinstance(model_candidate, dict)
        or model_candidate.get("model_id") != "qwen3.5:27b"
    ):
        raise ValueError("C7 C3 provenance model identity or gate differs")

    response_evidence: list[dict[str, object]] = []
    for result in model_results:
        encoded = result.provenance.response_evidence_json
        if encoded is None:
            continue
        try:
            decoded = json.loads(encoded)
        except json.JSONDecodeError as exc:
            raise ValueError("C7 C3 response evidence is invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("C7 C3 response evidence must be an object")
        response_evidence.append(decoded)
    if len(response_evidence) != 29:
        raise ValueError("C7 C3 response evidence count differs from the model run")
    gpu_contract = tuple(
        item.get("requested_num_gpu") == 999
        and item.get("active_gpu_percent_rounded") == 100
        and item.get("requested_num_ctx") == 65536
        and item.get("active_context_length") == 65536
        for item in response_evidence
    )
    if not all(gpu_contract):
        raise ValueError("C7 C3 historical GPU-offload provenance is incomplete")
    latencies = tuple(int(item["total_duration_ns"]) / 1_000_000_000 for item in response_evidence)
    vram_values = tuple(int(item["active_size_vram_bytes"]) for item in response_evidence)
    if (
        sum(int(item["total_duration_ns"]) for item in response_evidence)
        != 88_897_727_545
        or max(latencies) != 14.974155042
        or max(vram_values) != 19_040_451_951
    ):
        raise ValueError("C7 C3 historical resource telemetry differs")

    runtime_text = payloads["c4_runtime_acceptance"].decode("utf-8")
    screen_text = payloads["c4_model_screen"].decode("utf-8")
    dinov2_text = payloads["c4_dinov2_smoke"].decode("utf-8")
    c4_markers = (
        "TECHNICAL C4 RUNTIME INTEGRATION PASSED" in runtime_text,
        "0/48" in screen_text,
        "semantic_quality_gate_passed=false" in screen_text,
        "production_authority_granted=false" in screen_text,
        "generated_images_are_external_evidence=false" in screen_text,
        "semantic quality gate: not passed" in dinov2_text,
        "generated images as external evidence: false" in dinov2_text,
    )
    if not all(c4_markers):
        raise ValueError("C7 C4 evidence no longer states its bounded gate status")

    c5 = BodyMapperEvaluationReport.model_validate_json(payloads["c5_body_mapper"])
    c5_expected = {
        "semantic_family_count": 12,
        "positive_cell_count": 36,
        "passing_case_count": 36,
        "negative_control_count": 17,
        "passing_negative_control_count": 17,
        "effect_vector_count": 72,
        "passing_effect_vector_count": 72,
        "manual_auto_selected_agreement_count": 33,
        "gate_passed": True,
    }
    if (
        any(getattr(c5, key) != value for key, value in c5_expected.items())
        or len(c5.cases) != 36
        or len(c5.negative_controls) != 17
        or not all(item.passes and item.manual_auto_agrees for item in c5.cases)
        or not all(item.passes for item in c5.negative_controls)
        or sum(item.expected_auto_status == "selected" for item in c5.cases) != 33
    ):
        raise ValueError("C7 C5 bounded body-mapper contract differs")

    c6 = LongitudinalEvaluationReport.model_validate_json(
        payloads["c6_longitudinal"]
    )
    c6_expected = {
        "sequence_count": 10,
        "total_cycle_count": 100,
        "passing_sequence_count": 10,
        "corpus_sha256": (
            "0013c4f16aab4737c9ecc0530145e486602c0e21fe3770bedb12397232453c7f"
        ),
        "corpus_hash": (
            "dc621664dffe1ce96c877e0f6251d7d84e80a7d5b2e521e63cc8ddff13e9e0de"
        ),
        "template_request_hash": (
            "6b0aba367a3b895f724b24d2b0ca1005d9530b8729c5766c12ec2f8f0529f88d"
        ),
        "verified_visual_signal_cycle_count": 100,
        "predicted_body_signal_cycle_count": 100,
        "measured_body_signal_cycle_count": 0,
        "motif_true_positive_count": 40,
        "motif_false_positive_count": 0,
        "motif_false_negative_count": 0,
        "simulated_spoznanje_cycle_count": 85,
        "technical_gate_passed": True,
        "semantic_authority_granted": False,
    }
    if any(getattr(c6, key) != value for key, value in c6_expected.items()):
        raise ValueError("C7 C6 bounded longitudinal contract differs")

    summary = C7ImportedEvidenceSummary(
        c1_family_count=24,
        c1_variant_count=192,
        c1_review_status="canon_approved",
        c1_model_generated_gold=False,
        c1_training_export=False,
        c2_result_count=32,
        c2_passing_result_count=8,
        c2_dimension_count=26,
        c2_evaluator_model_call_count=0,
        c2_dimensions_preserved_separately=True,
        c2_global_rei_score_present=False,
        c3_metrics=c3_metrics,
        c3_model_id="qwen3.5:27b",
        c3_model_digest=model_candidate["model_digest"],
        c3_response_evidence_count=29,
        c3_missing_response_evidence_count=3,
        c3_full_gpu_offload_evidence_count=sum(gpu_contract),
        c4_runtime_technical_contract_passed=True,
        c4_visual_robustness_executed_cell_count=0,
        c4_visual_robustness_required_cell_count=48,
        c4_semantic_quality_gate_passed=False,
        c4_production_authority_granted=False,
        c4_generated_images_are_external_evidence=False,
        c5_semantic_family_count=12,
        c5_positive_case_count=36,
        c5_passing_case_count=36,
        c5_negative_control_count=17,
        c5_passing_negative_control_count=17,
        c5_effect_vector_count=72,
        c5_passing_effect_vector_count=72,
        c5_manual_auto_agreement_count=33,
        c5_manual_auto_all_case_agreement_count=36,
        c5_gate_passed=True,
        c6_sequence_count=10,
        c6_total_cycle_count=100,
        c6_passing_sequence_count=10,
        c6_corpus_sha256=c6.corpus_sha256,
        c6_corpus_hash=c6.corpus_hash,
        c6_template_request_hash=c6.template_request_hash,
        c6_visual_signal_cycle_count=100,
        c6_predicted_body_signal_cycle_count=100,
        c6_measured_body_signal_cycle_count=0,
        c6_motif_true_positive_count=40,
        c6_motif_false_positive_count=0,
        c6_motif_false_negative_count=0,
        c6_simulated_spoznanje_cycle_count=85,
        c6_technical_gate_passed=True,
        c6_semantic_authority_granted=False,
    )
    resources = build_c7_resource_observations()
    return summary, resources


C7_CURRENT_EVIDENCE_KEYS: tuple[str, ...] = (
    "controlled_profile_current",
    "person_causality_current",
)


def _keys(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def build_c7_failures() -> tuple[C7FailureRecord, ...]:
    """Return explicit readiness blockers; none is collapsed into a score."""

    return (
        C7FailureRecord.create(
            blocker_code="c3_model_quality_gate_failed",
            affected_ablation_families=("racio_provider",),
            affected_metric_dimensions=(
                "source_grounding",
                "option_choice",
                "abstention",
                "translation_fidelity",
                "cross_language_consistency",
            ),
            evidence_artifact_keys=(
                "c3_metrics",
                "c3_model_results",
                "c3_provenance",
            ),
            current_tree_failure=False,
            detail=(
                "The pinned Qwen3.5 27B v5 run outperformed the deterministic "
                "baseline but failed structural and quality gates: 29/32 structured "
                "outputs, 13/16 ambiguity gates and 14/16 bilingual pairs."
            ),
        ),
        C7FailureRecord.create(
            blocker_code="c4_semantic_visual_gate_open",
            affected_ablation_families=("emocio_cognition_mode",),
            affected_metric_dimensions=("visual_robustness",),
            evidence_artifact_keys=(
                "c4_dinov2_smoke",
                "c4_model_screen",
                "c4_runtime_acceptance",
            ),
            current_tree_failure=True,
            detail=(
                "C4 technical integration passed, but the complete visual robustness "
                "matrix remains 0/48 and semantic, production and external-evidence "
                "authority remain closed."
            ),
        ),
        C7FailureRecord.create(
            blocker_code="vlm_interpreter_arm_not_executed",
            affected_ablation_families=("interpreter_input_mode",),
            affected_metric_dimensions=(
                "translation_fidelity",
                "cross_language_consistency",
                "visual_robustness",
            ),
            evidence_artifact_keys=("c4_model_screen",),
            current_tree_failure=True,
            detail=(
                "No authority-bearing structured-versus-VLM interpreter comparison "
                "exists; C7 performs no replacement model call."
            ),
        ),
        C7FailureRecord.create(
            blocker_code="semantic_motif_arm_not_executed",
            affected_ablation_families=("ego_motif_mode",),
            affected_metric_dimensions=("longitudinal_motif_precision",),
            evidence_artifact_keys=("c6_longitudinal",),
            current_tree_failure=True,
            detail=(
                "C6 validates structured-tag motifs only; a semantic motif hypothesis "
                "arm has not been executed or independently reviewed."
            ),
        ),
        C7FailureRecord.create(
            blocker_code="uniform_resource_telemetry_missing",
            affected_ablation_families=(),
            affected_metric_dimensions=("latency", "vram", "ram"),
            evidence_artifact_keys=("c3_model_results", "c3_provenance"),
            current_tree_failure=True,
            detail=(
                "Latency and VRAM are historical C3 observations for 29 responses; "
                "RAM and uniform telemetry across all ablation arms were not measured."
            ),
        ),
    )


def build_c7_ablations() -> tuple[C7AblationResult, ...]:
    return (
        C7AblationResult(
            family="racio_provider",
            family_status="blocked",
            arms=(
                C7AblationArmResult(
                    arm_id="deterministic",
                    status="observed",
                    execution_scope="historical_model_backed",
                    current_model_call_count=0,
                    target_improvement_observed=False,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=("c3_baseline_results",),
                    limitation=(
                        "Paired deterministic baseline from the frozen C3 run; it is "
                        "not a new model-backed semantic approval."
                    ),
                ),
                C7AblationArmResult(
                    arm_id="qwen3.5_27b_v5",
                    status="failed",
                    execution_scope="historical_model_backed",
                    current_model_call_count=0,
                    target_improvement_observed=True,
                    semantic_gate_passed=False,
                    evidence_artifact_keys=_keys(
                        "c3_metrics", "c3_model_results", "c3_provenance"
                    ),
                    blocker_codes=("c3_model_quality_gate_failed",),
                    limitation=(
                        "Historical 32-call evidence is replayed without contacting "
                        "Ollama; the original structural and quality gates failed."
                    ),
                ),
            ),
        ),
        C7AblationResult(
            family="emocio_cognition_mode",
            family_status="blocked",
            arms=(
                C7AblationArmResult(
                    arm_id="structured_only",
                    status="passed",
                    execution_scope="current_technical_contract",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=_keys(
                        "c6_longitudinal", "person_causality_current"
                    ),
                    limitation=(
                        "Current deterministic structured processing passes a bounded "
                        "software contract, not a population-level semantic claim."
                    ),
                ),
                C7AblationArmResult(
                    arm_id="render_observe",
                    status="failed",
                    execution_scope="historical_model_backed",
                    current_model_call_count=0,
                    semantic_gate_passed=False,
                    evidence_artifact_keys=_keys(
                        "c4_model_screen", "c4_runtime_acceptance"
                    ),
                    blocker_codes=("c4_semantic_visual_gate_open",),
                    limitation=(
                        "The renderer path is technically integrated but its reviewed "
                        "semantic stability gate remains open."
                    ),
                ),
                C7AblationArmResult(
                    arm_id="visual_cognition",
                    status="blocked",
                    execution_scope="not_executed",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=_keys(
                        "c4_dinov2_smoke", "c4_model_screen"
                    ),
                    blocker_codes=("c4_semantic_visual_gate_open",),
                    limitation=(
                        "DINOv2 correctly refused collapsed rollout influence and no "
                        "approved 48-cell robustness evidence exists."
                    ),
                ),
            ),
        ),
        C7AblationResult(
            family="instinkt_effect_source",
            family_status="passed",
            arms=(
                C7AblationArmResult(
                    arm_id="manual_effects",
                    status="passed",
                    execution_scope="current_technical_contract",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=("c5_body_mapper",),
                    limitation=(
                        "C5 manual effects are an internal non-blind implementation "
                        "hypothesis used only for bounded contract comparison."
                    ),
                ),
                C7AblationArmResult(
                    arm_id="auto_mapper",
                    status="passed",
                    execution_scope="current_technical_contract",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=("c5_body_mapper",),
                    limitation=(
                        "The auto mapper passes C5 coverage, negative-control and "
                        "provenance gates; it has no clinical or person authority."
                    ),
                ),
            ),
        ),
        C7AblationResult(
            family="interpreter_input_mode",
            family_status="blocked",
            arms=(
                C7AblationArmResult(
                    arm_id="structured_only",
                    status="observed",
                    execution_scope="historical_model_backed",
                    current_model_call_count=0,
                    semantic_gate_passed=False,
                    evidence_artifact_keys=_keys(
                        "c2_metrics", "c3_metrics", "c3_model_results"
                    ),
                    blocker_codes=("c3_model_quality_gate_failed",),
                    limitation=(
                        "Structured interpreter evidence is preserved, including its "
                        "failed C3 model quality gate."
                    ),
                ),
                C7AblationArmResult(
                    arm_id="vlm",
                    status="blocked",
                    execution_scope="not_executed",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=("c4_model_screen",),
                    blocker_codes=("vlm_interpreter_arm_not_executed",),
                    limitation=(
                        "No authority-bearing VLM interpreter arm exists in the pinned "
                        "corpus, so C7 records the missing comparison explicitly."
                    ),
                ),
            ),
        ),
        C7AblationResult(
            family="ego_motif_mode",
            family_status="blocked",
            arms=(
                C7AblationArmResult(
                    arm_id="structured_motif",
                    status="passed",
                    execution_scope="current_technical_contract",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=("c6_longitudinal",),
                    limitation=(
                        "The 1.0 precision is a stage-1 structured-tag motif contract, "
                        "not semantic motif authority."
                    ),
                ),
                C7AblationArmResult(
                    arm_id="semantic_motif_hypothesis",
                    status="blocked",
                    execution_scope="not_executed",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=("c6_longitudinal",),
                    blocker_codes=("semantic_motif_arm_not_executed",),
                    limitation=(
                        "No semantic hypothesis arm or independent semantic review is "
                        "available in C6."
                    ),
                ),
            ),
        ),
        C7AblationResult(
            family="acceptance_mode",
            family_status="passed",
            arms=tuple(
                C7AblationArmResult(
                    arm_id=mode,
                    status="passed",
                    execution_scope="current_model_free",
                    current_model_call_count=0,
                    semantic_gate_passed=None,
                    evidence_artifact_keys=("controlled_profile_current",),
                    limitation=(
                        "Synthetic acceptance counterfactual over an identical frozen "
                        "native bundle; no claim about a real person is granted."
                    ),
                )
                for mode in ("accepting", "mixed", "conflicted")
            ),
        ),
    )


def build_c7_metrics(
    *,
    imported: C7ImportedEvidenceSummary,
    controlled: ControlledProfileAcceptanceReport,
    person_case_count: int,
    person_passing_case_count: int,
    resources: tuple[C7ResourceObservation, ...],
    source_artifact_bytes: int,
    failure_count: int,
) -> tuple[C7MetricObservation, ...]:
    if person_case_count <= 0 or person_passing_case_count != person_case_count:
        raise ValueError("C7 person-causality cases must all pass the technical gate")
    if len(resources) != 1 or failure_count <= 0:
        raise ValueError("C7 metrics require one historical resource row and blockers")
    c3 = imported.c3_metrics
    controlled_divergence = sum(
        item.conscious_behavior_state_divergence_count
        for item in controlled.mode_results
    )
    resource = resources[0]
    return (
        C7MetricObservation(
            dimension="processor_route_identity",
            status="passed",
            value=1.0,
            numerator=controlled.total_row_count,
            denominator=controlled.total_row_count,
            unit="bounded_rows",
            evidence_artifact_keys=("controlled_profile_current",),
            limitation=(
                "All 468 rows reuse frozen native bundle and governance identities; "
                "native processors are not rerun in this controlled cohort."
            ),
        ),
        C7MetricObservation(
            dimension="source_grounding",
            status="blocked",
            value=c3.structured_output_valid_count / c3.case_count,
            numerator=c3.structured_output_valid_count,
            denominator=c3.case_count,
            unit="historical_structured_outputs",
            evidence_artifact_keys=_keys(
                "c3_metrics", "c3_model_results", "c3_provenance"
            ),
            blocker_codes=("c3_model_quality_gate_failed",),
            limitation=(
                "The historical model run produced 29/32 valid structured outputs and "
                "three citation-scope failures, so research grounding is not passed."
            ),
        ),
        C7MetricObservation(
            dimension="option_choice",
            status="blocked",
            value=c3.unambiguous_exact_option_count / c3.unambiguous_count,
            numerator=c3.unambiguous_exact_option_count,
            denominator=c3.unambiguous_count,
            unit="historical_unambiguous_cases",
            evidence_artifact_keys=_keys("c3_metrics", "c3_model_results"),
            blocker_codes=("c3_model_quality_gate_failed",),
            limitation=(
                "Exact option choice is 16/16 only on the unambiguous subset; the "
                "complete C3 structural and ambiguity gates remain failed."
            ),
        ),
        C7MetricObservation(
            dimension="abstention",
            status="blocked",
            value=c3.ambiguous_gate_pass_count / c3.ambiguous_count,
            numerator=c3.ambiguous_gate_pass_count,
            denominator=c3.ambiguous_count,
            unit="historical_ambiguous_cases",
            evidence_artifact_keys=_keys("c2_metrics", "c3_metrics"),
            blocker_codes=("c3_model_quality_gate_failed",),
            limitation=(
                "The frozen model-backed ambiguity gate passed 13/16; the C2 negative "
                "fixture taxonomy is preserved but is not relabeled as model quality."
            ),
        ),
        C7MetricObservation(
            dimension="translation_fidelity",
            status="blocked",
            value=c3.unambiguous_exact_motive_count / c3.unambiguous_count,
            numerator=c3.unambiguous_exact_motive_count,
            denominator=c3.unambiguous_count,
            unit="historical_unambiguous_motive_cases",
            evidence_artifact_keys=_keys("c2_metrics", "c3_metrics"),
            blocker_codes=_keys(
                "c3_model_quality_gate_failed", "vlm_interpreter_arm_not_executed"
            ),
            limitation=(
                "Motive fidelity is 14/16 in unambiguous C3 cases and no VLM arm was "
                "executed, so translation fidelity is not research-ready."
            ),
        ),
        C7MetricObservation(
            dimension="character_causality",
            status="passed",
            value=person_passing_case_count / person_case_count,
            numerator=person_passing_case_count,
            denominator=person_case_count,
            unit="deterministic_simulator_cases",
            evidence_artifact_keys=("person_causality_current",),
            limitation=(
                "Pass is limited to deterministic simulator intervention and same-world "
                "counterfactual probes; population and full-history claims are excluded."
            ),
        ),
        C7MetricObservation(
            dimension="conscious_behavior_divergence",
            status="passed",
            value=controlled_divergence / controlled.total_row_count,
            numerator=controlled_divergence,
            denominator=controlled.total_row_count,
            unit="synthetic_profile_rows",
            evidence_artifact_keys=("controlled_profile_current",),
            limitation=(
                "Divergence is reported as a categorical outcome distribution across "
                "three synthetic acceptance modes, not as a quality target."
            ),
        ),
        C7MetricObservation(
            dimension="spoznanje",
            status="passed",
            value=1.0,
            numerator=imported.c6_simulated_spoznanje_cycle_count,
            denominator=imported.c6_simulated_spoznanje_cycle_count,
            unit="expected_simulated_cycles",
            evidence_artifact_keys=_keys(
                "c6_longitudinal", "controlled_profile_current"
            ),
            limitation=(
                "All 85 expected C6 simulated spoznanje cycles were reproduced; this "
                "is a bounded deterministic contract."
            ),
        ),
        C7MetricObservation(
            dimension="cross_language_consistency",
            status="blocked",
            value=c3.bilingual_consistent_pair_count / c3.bilingual_pair_count,
            numerator=c3.bilingual_consistent_pair_count,
            denominator=c3.bilingual_pair_count,
            unit="historical_bilingual_pairs",
            evidence_artifact_keys=_keys("c2_metrics", "c3_metrics"),
            blocker_codes=_keys(
                "c3_model_quality_gate_failed", "vlm_interpreter_arm_not_executed"
            ),
            limitation=(
                "The best pinned C3 model run is consistent on 14/16 pairs and has no "
                "paired VLM comparator."
            ),
        ),
        C7MetricObservation(
            dimension="visual_robustness",
            status="blocked",
            value=0.0,
            numerator=0,
            denominator=48,
            unit="required_editor_member_cells",
            evidence_artifact_keys=_keys(
                "c4_dinov2_smoke", "c4_model_screen", "c4_runtime_acceptance"
            ),
            blocker_codes=_keys(
                "c4_semantic_visual_gate_open", "vlm_interpreter_arm_not_executed"
            ),
            limitation=(
                "The complete reviewed visual robustness matrix remains unexecuted "
                "at 0/48; technical one-cell smokes do not substitute for it."
            ),
        ),
        C7MetricObservation(
            dimension="body_mapper_agreement",
            status="passed",
            value=(
                imported.c5_manual_auto_all_case_agreement_count
                / imported.c5_positive_case_count
            ),
            numerator=imported.c5_manual_auto_all_case_agreement_count,
            denominator=imported.c5_positive_case_count,
            unit="bounded_positive_cases",
            evidence_artifact_keys=("c5_body_mapper",),
            limitation=(
                "Manual/auto outcomes agree on all 36 bounded cases; the selected "
                "subset is 33/33 and the remaining cases are matching abstentions."
            ),
        ),
        C7MetricObservation(
            dimension="longitudinal_motif_precision",
            status="passed",
            value=1.0,
            numerator=imported.c6_motif_true_positive_count,
            denominator=(
                imported.c6_motif_true_positive_count
                + imported.c6_motif_false_positive_count
            ),
            unit="structured_tag_motifs",
            evidence_artifact_keys=("c6_longitudinal",),
            blocker_codes=(),
            limitation=(
                "Precision 40/40 is restricted to stage-1 structured tags; the "
                "semantic motif hypothesis arm remains a separate explicit blocker."
            ),
        ),
        C7MetricObservation(
            dimension="latency",
            status="observed",
            value=resource.mean_latency_seconds,
            unit="historical_mean_seconds_per_response",
            evidence_artifact_keys=resource.evidence_artifact_keys,
            blocker_codes=("uniform_resource_telemetry_missing",),
            limitation=resource.limitation,
        ),
        C7MetricObservation(
            dimension="vram",
            status="observed",
            value=float(resource.max_vram_bytes),
            unit="historical_max_bytes",
            evidence_artifact_keys=resource.evidence_artifact_keys,
            blocker_codes=("uniform_resource_telemetry_missing",),
            limitation=resource.limitation,
        ),
        C7MetricObservation(
            dimension="ram",
            status="not_measured",
            evidence_artifact_keys=resource.evidence_artifact_keys,
            blocker_codes=("uniform_resource_telemetry_missing",),
            limitation=(
                "No trustworthy RAM measurement exists across the required ablation "
                "arms; C7 does not infer RAM from VRAM or model size."
            ),
        ),
        C7MetricObservation(
            dimension="artifact_size",
            status="observed",
            value=float(source_artifact_bytes),
            unit="pinned_source_bytes",
            evidence_artifact_keys=tuple(
                sorted(
                    {
                        "c1_fixture_manifest",
                        "c2_metrics",
                        "c3_baseline_results",
                        "c3_metrics",
                        "c3_model_results",
                        "c3_provenance",
                        "c4_dinov2_smoke",
                        "c4_model_screen",
                        "c4_runtime_acceptance",
                        "c5_body_mapper",
                        "c6_longitudinal",
                    }
                )
            ),
            limitation=(
                "Value is the exact byte sum of the 11 pinned input artifacts; each "
                "generated C7 artifact is reported separately in provenance."
            ),
        ),
        C7MetricObservation(
            dimension="failure_mode",
            status="passed",
            value=1.0,
            numerator=failure_count,
            denominator=failure_count,
            unit="typed_reproducible_blockers",
            evidence_artifact_keys=(),
            limitation=(
                "Every readiness blocker is emitted as a typed reproducible failure "
                "record; this does not mean the blocked quality dimensions passed."
            ),
        ),
    )


class C7IntegratedBenchmarkReport(FrozenArtifactModel):
    """One content-addressed, dimension-preserving C7 benchmark report."""

    schema_version: Literal["rei-c7-integrated-benchmark-report-v1"] = (
        "rei-c7-integrated-benchmark-report-v1"
    )
    report_id: NonEmptyId
    evaluator_revision: Literal["c7-v1"] = C7_EVALUATOR_REVISION
    manifest: C7IntegratedManifest
    manifest_sha256: Literal[
        "cfed2f5bafeb7cb8a47d04d580443df3b28cce90b876a46ce9de5ad8c072b5a7"
    ]
    source_artifacts: tuple[C7EvidenceArtifactRef, ...]
    imported_evidence: C7ImportedEvidenceSummary
    controlled_profile: ControlledProfileAcceptanceReport
    person_causality: PersonCausalityEvaluationReport
    ablations: tuple[C7AblationResult, ...]
    metrics: tuple[C7MetricObservation, ...]
    resource_observations: tuple[C7ResourceObservation, ...]
    failures: tuple[C7FailureRecord, ...]
    current_model_call_count: Literal[0] = 0
    historical_model_call_count: Literal[32] = 32
    aggregate_score_present: Literal[False] = False
    interaction_effects_measured: Literal[False] = False
    technical_contract_passed: Literal[True] = True
    research_quality_status: Literal["blocked"] = "blocked"
    research_readiness_blocker_codes: tuple[NonEmptyId, ...]
    passed_metric_count: int = Field(ge=0, le=17)
    blocked_metric_count: int = Field(ge=0, le=17)
    observed_metric_count: int = Field(ge=0, le=17)
    not_measured_metric_count: int = Field(ge=0, le=17)
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False
    report_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        manifest: C7IntegratedManifest,
        manifest_sha256: str,
        source_artifacts: tuple[C7EvidenceArtifactRef, ...],
        imported_evidence: C7ImportedEvidenceSummary,
        controlled_profile: ControlledProfileAcceptanceReport,
        person_causality: PersonCausalityEvaluationReport,
        ablations: tuple[C7AblationResult, ...],
        metrics: tuple[C7MetricObservation, ...],
        resource_observations: tuple[C7ResourceObservation, ...],
        failures: tuple[C7FailureRecord, ...],
    ) -> "C7IntegratedBenchmarkReport":
        status_counts = Counter(item.status for item in metrics)
        blocker_codes = tuple(item.blocker_code for item in failures)
        base = {
            "schema_version": "rei-c7-integrated-benchmark-report-v1",
            "evaluator_revision": C7_EVALUATOR_REVISION,
            "manifest": manifest,
            "manifest_sha256": manifest_sha256,
            "source_artifacts": source_artifacts,
            "imported_evidence": imported_evidence,
            "controlled_profile": controlled_profile,
            "person_causality": person_causality,
            "ablations": ablations,
            "metrics": metrics,
            "resource_observations": resource_observations,
            "failures": failures,
            "current_model_call_count": 0,
            "historical_model_call_count": 32,
            "aggregate_score_present": False,
            "interaction_effects_measured": False,
            "technical_contract_passed": True,
            "research_quality_status": "blocked",
            "research_readiness_blocker_codes": blocker_codes,
            "passed_metric_count": status_counts["passed"],
            "blocked_metric_count": status_counts["blocked"],
            "observed_metric_count": status_counts["observed"],
            "not_measured_metric_count": status_counts["not_measured"],
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        report_id = content_id("c7_integrated_benchmark", base)
        payload = {"report_id": report_id, **base}
        return cls(**payload, report_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        expected_refs = tuple(
            C7EvidenceArtifactRef.create(spec)
            for spec in self.manifest.source_artifacts
        )
        if self.source_artifacts != expected_refs:
            raise ValueError("C7 report source references differ from its manifest")
        if not (
            self.controlled_profile.technical_contract_passed
            and self.controlled_profile.native_processor_executions == 0
            and self.controlled_profile.semantic_authority_granted is False
            and self.person_causality.gate_passed
            and self.person_causality.passing_case_count
            == self.person_causality.case_count
            and self.person_causality.semantic_authority_granted is False
            and self.person_causality.source_corpus_sha256
            == self.imported_evidence.c6_corpus_sha256
            and self.person_causality.template_request_hash
            == self.imported_evidence.c6_template_request_hash
            and self.imported_evidence.c5_gate_passed
            and self.imported_evidence.c6_technical_gate_passed
            and self.imported_evidence.c3_metrics.quality_gate_pass is False
            and self.imported_evidence.c4_semantic_quality_gate_passed is False
        ):
            raise ValueError("C7 technical inputs or bounded authority flags differ")
        if tuple(item.family for item in self.ablations) != C7_ABLATION_FAMILIES:
            raise ValueError("C7 report ablations differ from plan order")
        if tuple(item.dimension for item in self.metrics) != C7_METRIC_DIMENSIONS:
            raise ValueError("C7 report metrics differ from plan order")
        if len(self.resource_observations) != 1 or len(self.failures) != 5:
            raise ValueError("C7 report requires one resource row and five blockers")
        blocker_codes = tuple(item.blocker_code for item in self.failures)
        if (
            self.research_readiness_blocker_codes != blocker_codes
            or len(set(blocker_codes)) != len(blocker_codes)
        ):
            raise ValueError("C7 research blocker index differs from failure records")
        known_keys = {
            *(item.artifact_key for item in self.source_artifacts),
            *C7_CURRENT_EVIDENCE_KEYS,
        }
        referenced_keys = {
            key
            for ablation in self.ablations
            for arm in ablation.arms
            for key in arm.evidence_artifact_keys
        } | {
            key
            for group in (
                self.metrics,
                self.resource_observations,
                self.failures,
            )
            for item in group
            for key in item.evidence_artifact_keys
        }
        if not referenced_keys.issubset(known_keys):
            raise ValueError("C7 report refers to an unknown evidence artifact")
        arm_calls = sum(
            arm.current_model_call_count
            for ablation in self.ablations
            for arm in ablation.arms
        )
        if arm_calls != self.current_model_call_count:
            raise ValueError("C7 current model-call count differs from its arms")
        expected_resources = build_c7_resource_observations()
        expected_failures = build_c7_failures()
        expected_ablations = build_c7_ablations()
        expected_metrics = build_c7_metrics(
            imported=self.imported_evidence,
            controlled=self.controlled_profile,
            person_case_count=self.person_causality.case_count,
            person_passing_case_count=self.person_causality.passing_case_count,
            resources=expected_resources,
            source_artifact_bytes=sum(
                item.size_bytes for item in self.source_artifacts
            ),
            failure_count=len(expected_failures),
        )
        if self.resource_observations != expected_resources:
            raise ValueError("C7 resource rows differ from pinned historical telemetry")
        if self.failures != expected_failures:
            raise ValueError("C7 failure records differ from readiness blockers")
        if self.ablations != expected_ablations:
            raise ValueError("C7 ablations differ from their canonical dispositions")
        if self.metrics != expected_metrics:
            raise ValueError("C7 metrics differ from their source-derived dimensions")
        status_counts = Counter(item.status for item in self.metrics)
        if (
            self.passed_metric_count != status_counts["passed"]
            or self.blocked_metric_count != status_counts["blocked"]
            or self.observed_metric_count != status_counts["observed"]
            or self.not_measured_metric_count != status_counts["not_measured"]
            or sum(status_counts.values()) != 17
            or self.blocked_metric_count == 0
        ):
            raise ValueError("C7 metric disposition counts differ from metric rows")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"report_id", "report_hash"},
        )
        if self.report_id != content_id("c7_integrated_benchmark", base):
            raise ValueError("C7 integrated report ID differs from content")
        payload = {"report_id": self.report_id, **base}
        if self.report_hash != sha256_hex(payload):
            raise ValueError("C7 integrated report hash differs from content")
        return self


def evaluate_c7_integrated_benchmark(
    repository_root: str | Path,
    *,
    manifest_path: str | Path | None = None,
) -> C7IntegratedBenchmarkReport:
    """Run C7 without model, renderer, VLM, network or Ollama execution."""

    requested_root = Path(repository_root).expanduser()
    _reject_reparse_components(requested_root, label="C7 repository root")
    root = requested_root.resolve()
    if not root.is_dir():
        raise ValueError("C7 repository root must be an existing directory")
    manifest_source = (
        Path(manifest_path).expanduser()
        if manifest_path is not None
        else root
        / "knowledge"
        / "canon_v2"
        / "semantic_lab_v1"
        / "c7_integrated"
        / "manifest.json"
    )
    manifest, manifest_sha256 = load_c7_manifest(manifest_source)
    refs, payloads = verify_c7_source_artifacts(
        repository_root=root,
        manifest=manifest,
    )
    imported, resources = validate_c7_imported_evidence(
        repository_root=root,
        payloads=payloads,
    )
    controlled = evaluate_controlled_profile_acceptance(
        root / "tests" / "fixtures" / "native_bundles"
    )
    person = evaluate_person_causality(
        corpus_path=(
            root
            / "knowledge"
            / "canon_v2"
            / "semantic_lab_v1"
            / "c6_longitudinal"
            / "corpus.json"
        ),
        template_fixture_path=(
            root / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
        ),
    )
    failures = build_c7_failures()
    ablations = build_c7_ablations()
    metrics = build_c7_metrics(
        imported=imported,
        controlled=controlled,
        person_case_count=person.case_count,
        person_passing_case_count=person.passing_case_count,
        resources=resources,
        source_artifact_bytes=sum(item.size_bytes for item in refs),
        failure_count=len(failures),
    )
    return C7IntegratedBenchmarkReport.create(
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        source_artifacts=refs,
        imported_evidence=imported,
        controlled_profile=controlled,
        person_causality=person,
        ablations=ablations,
        metrics=metrics,
        resource_observations=resources,
        failures=failures,
    )


class C7ReportError(RuntimeError):
    """Base class for deterministic C7 report materialization failures."""


class C7ReportExistsError(C7ReportError):
    """Raised when create-only C7 output would overwrite an artifact."""


class C7ReportMismatchError(C7ReportError):
    """Raised when a checked C7 report differs from a cold replay."""


def _dimensions_markdown(report: C7IntegratedBenchmarkReport) -> bytes:
    lines = [
        "# C7 integrated semantic and longitudinal benchmark",
        "",
        f"- Report ID: `{report.report_id}`",
        f"- Technical contract: **{'PASS' if report.technical_contract_passed else 'FAIL'}**",
        f"- Research quality: **{report.research_quality_status.upper()}**",
        "- Aggregate REI score: **absent by contract**",
        f"- Current model calls: **{report.current_model_call_count}**",
        "- Semantic authority: **false**",
        "- Production authority: **false**",
        "",
        "The dimensions below are intentionally not collapsed into a rank or score.",
        "Historical observations retain their original scope; bounded software passes",
        "do not become claims about people or semantic model approval.",
        "",
        "| Dimension | Status | Observation | Scope limitation |",
        "|---|---|---:|---|",
    ]
    for item in report.metrics:
        if item.numerator is not None:
            observation = f"{item.numerator}/{item.denominator} {item.unit or ''}".strip()
        elif item.value is not None:
            observation = f"{item.value:.12g} {item.unit or ''}".strip()
        else:
            observation = item.unit or "not measured"
        limitation = item.limitation.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{item.dimension}` | `{item.status}` | {observation} | {limitation} |"
        )
    lines.extend(
        [
            "",
            "## Research-readiness blockers",
            "",
            *(
                f"- `{item.blocker_code}`: {item.detail}"
                for item in report.failures
            ),
            "",
            "## Ablation disposition",
            "",
            "| Family | Status | Arms | Interaction effects |",
            "|---|---|---|---|",
            *(
                "| `{}` | `{}` | {} | not measured |".format(
                    item.family,
                    item.family_status,
                    ", ".join(
                        f"`{arm.arm_id}` ({arm.status})" for arm in item.arms
                    ),
                )
                for item in report.ablations
            ),
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def render_c7_report(
    report: C7IntegratedBenchmarkReport,
) -> dict[str, bytes]:
    """Render exactly seven deterministic C7 artifacts without filesystem I/O."""

    artifacts: dict[str, bytes] = {
        "integrated_benchmark.json": canonical_json_bytes(
            report.model_dump(mode="python", round_trip=True)
        ),
        "controlled_profile.json": canonical_json_bytes(
            report.controlled_profile.model_dump(mode="python", round_trip=True)
        ),
        "person_causality.json": canonical_json_bytes(
            report.person_causality.model_dump(mode="python", round_trip=True)
        ),
        "ablations.json": canonical_json_bytes(
            {
                "schema_version": "rei-c7-ablations-v1",
                "report_id": report.report_id,
                "aggregate_score_present": False,
                "interaction_effects_measured": False,
                "ablations": tuple(
                    item.model_dump(mode="python", round_trip=True)
                    for item in report.ablations
                ),
            }
        ),
        "failures.jsonl": b"".join(
            canonical_json_bytes(item.model_dump(mode="python", round_trip=True))
            + b"\n"
            for item in report.failures
        ),
        "dimensions.md": _dimensions_markdown(report),
    }
    generated = tuple(
        {
            "path": name,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for name, payload in artifacts.items()
    )
    provenance = {
        "schema_version": "rei-c7-report-provenance-v1",
        "report_id": report.report_id,
        "report_hash": report.report_hash,
        "evaluator_revision": report.evaluator_revision,
        "input_baseline_commit": report.manifest.input_baseline_commit,
        "manifest_sha256": report.manifest_sha256,
        "source_artifacts": tuple(
            item.model_dump(mode="python", round_trip=True)
            for item in report.source_artifacts
        ),
        "generated_artifacts_excluding_provenance": generated,
        "generated_artifact_set_hash": sha256_hex(generated),
        "current_model_call_count": report.current_model_call_count,
        "historical_model_call_count": report.historical_model_call_count,
        "technical_contract_passed": report.technical_contract_passed,
        "research_quality_status": report.research_quality_status,
        "semantic_authority_granted": report.semantic_authority_granted,
        "production_authority_granted": report.production_authority_granted,
    }
    artifacts["provenance.json"] = canonical_json_bytes(provenance)
    if tuple(artifacts) != C7_REPORT_FILENAMES:
        raise AssertionError("C7 report artifact set differs from its contract")
    oversized = tuple(
        name
        for name, payload in artifacts.items()
        if not payload or len(payload) > C7_MAX_REPORT_ARTIFACT_BYTES
    )
    if oversized:
        raise C7ReportError(
            "C7 rendered artifacts are empty or oversized: " + ", ".join(oversized)
        )
    return artifacts


def _write_exclusive(path: Path, payload: bytes) -> None:
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        created = True
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise C7ReportExistsError(
            f"C7 report artifact already exists: {path.name}"
        ) from exc
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        if created:
            path.unlink(missing_ok=True)
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def write_c7_report(
    report: C7IntegratedBenchmarkReport,
    report_root: str | Path,
) -> tuple[Path, ...]:
    """Materialize C7 create-only; partial files are removed on failure."""

    artifacts = render_c7_report(report)
    requested_root = Path(report_root).expanduser()
    try:
        _reject_reparse_components(requested_root, label="C7 report root")
    except ValueError as exc:
        raise C7ReportError(str(exc)) from exc
    root = requested_root.absolute()
    if root.exists() or root.is_symlink():
        raise C7ReportExistsError(
            f"C7 report is create-only; output root already exists: {root.name}"
        )
    parent = root.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        _reject_reparse_components(parent, label="C7 report parent")
        parent_metadata = parent.lstat()
    except (OSError, ValueError) as exc:
        raise C7ReportError("C7 report parent changed during preflight") from exc
    if _is_reparse_stat(parent_metadata) or not stat.S_ISDIR(parent_metadata.st_mode):
        raise C7ReportError("C7 report parent must be a regular directory")

    staging = Path(
        tempfile.mkdtemp(prefix=f".{root.name}.staging-", dir=parent)
    )
    created: list[Path] = []
    published = False
    try:
        staging_metadata = staging.lstat()
        if _is_reparse_stat(staging_metadata) or not stat.S_ISDIR(
            staging_metadata.st_mode
        ):
            raise C7ReportError("C7 staging root must be a regular directory")
        for name in C7_REPORT_FILENAMES:
            path = staging / name
            _write_exclusive(path, artifacts[name])
            created.append(path)
        _reject_reparse_components(staging, label="C7 staging root")
        if root.exists() or root.is_symlink():
            raise C7ReportExistsError(
                f"C7 report is create-only; output root appeared: {root.name}"
            )
        os.rename(staging, root)
        published = True
        final_root_metadata = root.lstat()
        if (
            _is_reparse_stat(final_root_metadata)
            or not stat.S_ISDIR(final_root_metadata.st_mode)
            or not os.path.samestat(staging_metadata, final_root_metadata)
        ):
            raise C7ReportError("C7 report root changed during publication")
    except Exception:
        if not published:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            try:
                staging.rmdir()
            except OSError:
                pass
        raise
    paths = tuple(root / name for name in C7_REPORT_FILENAMES)
    return paths


def check_c7_report(
    report: C7IntegratedBenchmarkReport,
    report_root: str | Path,
) -> tuple[Path, ...]:
    """Require an exact seven-file byte match against a cold C7 replay."""

    artifacts = render_c7_report(report)
    requested_root = Path(report_root).expanduser()
    try:
        _reject_reparse_components(requested_root, label="C7 checked report root")
    except ValueError as exc:
        raise C7ReportMismatchError(str(exc)) from exc
    root = requested_root.resolve()
    if not root.is_dir():
        raise C7ReportMismatchError("C7 checked report root is not a regular directory")
    entries = tuple(
        sorted(
            islice(root.iterdir(), len(C7_REPORT_FILENAMES) + 1),
            key=lambda item: item.name,
        )
    )
    expected_names = tuple(sorted(C7_REPORT_FILENAMES))
    actual_names = tuple(item.name for item in entries)
    if actual_names != expected_names:
        raise C7ReportMismatchError("C7 checked report artifact set differs")
    paths = tuple(root / name for name in C7_REPORT_FILENAMES)
    for path in paths:
        payload = _read_bounded(
            path,
            maximum_bytes=C7_MAX_REPORT_ARTIFACT_BYTES,
        )
        if payload != artifacts[path.name]:
            raise C7ReportMismatchError(
                f"C7 checked report bytes differ: {path.name}"
            )
    return paths


__all__ = [
    "C7_ABLATION_FAMILIES",
    "C7_EVALUATOR_REVISION",
    "C7_EXPECTED_MANIFEST_SHA256",
    "C7_METRIC_DIMENSIONS",
    "C7_REPORT_FILENAMES",
    "C7AblationArmResult",
    "C7AblationResult",
    "C7EvidenceArtifactRef",
    "C7FailureRecord",
    "C7ImportedEvidenceSummary",
    "C7IntegratedBenchmarkReport",
    "C7IntegratedManifest",
    "C7MetricObservation",
    "C7ReportError",
    "C7ReportExistsError",
    "C7ReportMismatchError",
    "C7ResourceObservation",
    "C7SourceArtifactSpec",
    "build_c7_ablations",
    "build_c7_failures",
    "build_c7_metrics",
    "check_c7_report",
    "evaluate_c7_integrated_benchmark",
    "load_c7_manifest",
    "render_c7_report",
    "validate_c7_imported_evidence",
    "verify_c7_source_artifacts",
    "write_c7_report",
]
