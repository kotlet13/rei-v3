"""Durable, model-free C4 Stage 1 background-telemetry finalization.

The contracts in this module bind a pre-inference process request to one exact
attempt, provider, source, snapshot and pipeline.  Finalization is fail-closed:
sampled peaks are lower bounds, missing endpoint/coverage evidence never becomes
zero, and persistence failures can never produce a technical pass.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from threading import Lock
from typing import Callable, Literal, Self, TypeVar

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenArtifactModel, FrozenModel, HashDigest, NonEmptyId
from ..providers.protocols import ArtifactStore, StoredArtifact
from .process_tree_runner import (
    BoundedProcessRequest,
    ProcessLifecycleContext,
    ProcessTerminationTrigger,
    ProcessTreeExecutionRecord,
    TreeInspectionOutcome,
    TreeTerminationOutcome,
)
from .resource_telemetry import (
    RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS,
    RESOURCE_TELEMETRY_MAX_SAMPLES,
    BackgroundResourceTelemetrySample,
    BackgroundResourceTelemetrySampler,
    BackgroundResourceTelemetrySamplerResult,
    BackgroundResourceTelemetrySamplerStatus,
    BackgroundSamplerState,
    ResourceByteReading,
    ResourceTelemetryCudaDeviceIdentity,
    ResourceTelemetryProbe,
    ResourceTelemetryProcessTarget,
    ResourceTelemetrySnapshot,
    SystemResourceTelemetryProbe,
)


C4_STAGE1_TELEMETRY_SAMPLING_POLICY = (
    "background-start-deadline-cadence-final-endpoint-v1"
)
C4_STAGE1_TELEMETRY_MAX_SAMPLES_ARTIFACT_BYTES = 8 * 1024 * 1024
C4_STAGE1_TELEMETRY_MAX_RECEIPT_BYTES = 256 * 1024
C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS = 2.5
C4_STAGE1_PER_OPTION_HARD_TIMEOUT_SECONDS = 180.0
C4_STAGE1_TELEMETRY_CADENCE_SECONDS = 0.5
C4_STAGE1_TELEMETRY_MAX_SAMPLES = 362
C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS = 2.0
C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_MIB = 31_500
C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES = (
    C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_MIB * 1024 * 1024
)
C4_STAGE1_TELEMETRY_REQUIRED_METRICS = (
    "process_tree_rss",
    "system_ram_total",
    "system_ram_available",
    "cuda_vram_used",
    "cuda_vram_total",
)

SamplesPersistenceStatus = Literal["persisted", "not_created", "failed"]
TelemetryDisposition = Literal["passed", "failed"]
FinalizerFailureCode = Literal["telemetry_receipt_persistence_failure"]
_ModelT = TypeVar("_ModelT", bound=FrozenModel)


class C4Stage1TelemetryStateError(RuntimeError):
    """One Stage 1 telemetry owner was used outside its monotonic lifecycle."""


class C4Stage1TelemetryLifecycleError(RuntimeError):
    """Sanitized fail-closed lifecycle integration failure."""


class C4Stage1TelemetryPersistenceError(RuntimeError):
    """Sanitized durable telemetry read/write verification failure."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _content_addresses(namespace: str, payload: object) -> tuple[str, str]:
    return content_id(namespace, payload), _canonical_sha256(payload)


def _cold_validate_model(
    model_type: type[_ModelT],
    value: object,
    *,
    label: str,
) -> _ModelT:
    if not isinstance(value, model_type):
        raise TypeError(f"{label} must be a {model_type.__name__}")
    return model_type.model_validate(value.model_dump(mode="python", round_trip=True))


def _cold_validate_background_result(
    result: BackgroundResourceTelemetrySamplerResult,
) -> BackgroundResourceTelemetrySamplerResult:
    if not isinstance(result, BackgroundResourceTelemetrySamplerResult):
        raise TypeError("Stage 1 telemetry requires a background sampler result")
    latest = result.status.latest_sample
    status = BackgroundResourceTelemetrySamplerStatus(
        state=result.status.state,
        sample_count=result.status.sample_count,
        failure_code=result.status.failure_code,
        latest_sample=(
            None
            if latest is None
            else BackgroundResourceTelemetrySample(
                snapshot=latest.snapshot,
                probe_started_monotonic_ns=latest.probe_started_monotonic_ns,
                probe_finished_monotonic_ns=latest.probe_finished_monotonic_ns,
            )
        ),
        sampled_cuda_vram_peak=result.status.sampled_cuda_vram_peak,
    )
    samples = tuple(
        BackgroundResourceTelemetrySample(
            snapshot=sample.snapshot,
            probe_started_monotonic_ns=sample.probe_started_monotonic_ns,
            probe_finished_monotonic_ns=sample.probe_finished_monotonic_ns,
        )
        for sample in result.samples
    )
    return BackgroundResourceTelemetrySamplerResult(
        status=status,
        samples=samples,
        sampling_overhead_monotonic_ns=result.sampling_overhead_monotonic_ns,
    )


def _c4_stage1_telemetry_policy_body() -> dict[str, object]:
    return {
        "schema_version": "rei-c4-stage1-telemetry-policy-v1",
        "sampling_policy": C4_STAGE1_TELEMETRY_SAMPLING_POLICY,
        "required_metrics": C4_STAGE1_TELEMETRY_REQUIRED_METRICS,
        "per_option_hard_timeout_seconds": C4_STAGE1_PER_OPTION_HARD_TIMEOUT_SECONDS,
        "cadence_seconds": C4_STAGE1_TELEMETRY_CADENCE_SECONDS,
        "max_samples": C4_STAGE1_TELEMETRY_MAX_SAMPLES,
        "join_timeout_seconds": C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS,
        "sampled_whole_device_cuda_stop_mib": (
            C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_MIB
        ),
        "sampled_whole_device_cuda_stop_bytes": (
            C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES
        ),
        "callback_max_seconds": C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS,
        "exact_resolved_cuda_identity_required": True,
        "child_cuda_visible_devices_uuid_binding_required": True,
        "whole_device_cuda_measurement_required": True,
        "parent_owned_sampler_required": True,
        "initial_endpoint_before_release_required": True,
        "reserved_final_endpoint_required": True,
        "poll_probe_or_disk_io_allowed": False,
        "durable_samples_and_receipt_required": True,
        "sampled_cuda_peak_is_lower_bound": True,
        "absence_of_transient_cuda_breach_proven": False,
        "semantic_authority_granted": False,
        "production_authority_granted": False,
    }


class C4Stage1TelemetryPolicy(FrozenArtifactModel):
    """Canonical content-addressed parent telemetry policy for screen pinning."""

    schema_version: Literal["rei-c4-stage1-telemetry-policy-v1"] = (
        "rei-c4-stage1-telemetry-policy-v1"
    )
    telemetry_policy_id: NonEmptyId
    sampling_policy: Literal["background-start-deadline-cadence-final-endpoint-v1"] = (
        C4_STAGE1_TELEMETRY_SAMPLING_POLICY
    )
    required_metrics: tuple[NonEmptyId, ...] = C4_STAGE1_TELEMETRY_REQUIRED_METRICS
    per_option_hard_timeout_seconds: float = Field(
        gt=0.0,
        allow_inf_nan=False,
    )
    cadence_seconds: float = Field(gt=0.0, allow_inf_nan=False)
    max_samples: int = Field(ge=2, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    join_timeout_seconds: float = Field(
        gt=0.0,
        lt=C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS,
        allow_inf_nan=False,
    )
    sampled_whole_device_cuda_stop_mib: int = Field(ge=1)
    sampled_whole_device_cuda_stop_bytes: int = Field(ge=1)
    callback_max_seconds: float = Field(gt=0.0, allow_inf_nan=False)
    exact_resolved_cuda_identity_required: Literal[True] = True
    child_cuda_visible_devices_uuid_binding_required: Literal[True] = True
    whole_device_cuda_measurement_required: Literal[True] = True
    parent_owned_sampler_required: Literal[True] = True
    initial_endpoint_before_release_required: Literal[True] = True
    reserved_final_endpoint_required: Literal[True] = True
    poll_probe_or_disk_io_allowed: Literal[False] = False
    durable_samples_and_receipt_required: Literal[True] = True
    sampled_cuda_peak_is_lower_bound: Literal[True] = True
    absence_of_transient_cuda_breach_proven: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(cls) -> Self:
        body = _c4_stage1_telemetry_policy_body()
        return cls(
            telemetry_policy_id=content_id("c4_stage1_telemetry_policy", body),
            **body,
        )

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"telemetry_policy_id"},
        )
        if (
            payload != _c4_stage1_telemetry_policy_body()
            or self.telemetry_policy_id
            != content_id("c4_stage1_telemetry_policy", payload)
        ):
            raise ValueError("Stage 1 telemetry policy differs from canonical content")
        return self


def c4_stage1_telemetry_policy() -> C4Stage1TelemetryPolicy:
    """Return the exact artifact used by the screen telemetry content pin."""

    return C4Stage1TelemetryPolicy.create()


class C4Stage1ProcessRequestCommitment(FrozenArtifactModel):
    """Sanitized process request commitment; raw argv/env/path never serialize."""

    schema_version: Literal["rei-c4-stage1-process-request-v1"] = (
        "rei-c4-stage1-process-request-v1"
    )
    request_id: NonEmptyId
    request_sha256: HashDigest
    workload_id: NonEmptyId
    command_identity: NonEmptyId
    argument_count: int = Field(ge=0, le=255)
    working_directory_identity: NonEmptyId
    environment_identity: NonEmptyId
    timeout_seconds: float = Field(gt=0.0, le=86_400.0, allow_inf_nan=False)
    stdout_limit_bytes: int = Field(ge=1)
    stderr_limit_bytes: int = Field(ge=1)
    raw_command_stored: Literal[False] = False
    raw_environment_stored: Literal[False] = False
    raw_working_directory_stored: Literal[False] = False

    @classmethod
    def from_request(cls, request: BoundedProcessRequest) -> Self:
        if not isinstance(request, BoundedProcessRequest):
            raise TypeError("Stage 1 process commitment requires a bounded request")
        base = {
            "schema_version": "rei-c4-stage1-process-request-v1",
            "workload_id": request.workload_id,
            "command_identity": request.command_identity,
            "argument_count": len(request.command) - 1,
            "working_directory_identity": request.working_directory_identity,
            "environment_identity": request.environment_identity,
            "timeout_seconds": request.timeout_seconds,
            "stdout_limit_bytes": request.stdout_limit_bytes,
            "stderr_limit_bytes": request.stderr_limit_bytes,
            "raw_command_stored": False,
            "raw_environment_stored": False,
            "raw_working_directory_stored": False,
        }
        request_id, request_sha256 = _content_addresses(
            "c4_stage1_process_request",
            base,
        )
        return cls(
            request_id=request_id,
            request_sha256=request_sha256,
            **base,
        )

    @model_validator(mode="after")
    def validate_commitment(self) -> Self:
        if (
            self.raw_command_stored is not False
            or self.raw_environment_stored is not False
            or self.raw_working_directory_stored is not False
        ):
            raise ValueError("Stage 1 process commitment stores a raw launch value")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"request_id", "request_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_process_request",
            payload,
        )
        if self.request_id != expected_id or self.request_sha256 != expected_sha256:
            raise ValueError("Stage 1 process request commitment differs from content")
        return self


class C4Stage1TelemetryIntent(FrozenArtifactModel):
    """Create-only pre-inference telemetry commitment for one exact attempt."""

    schema_version: Literal["rei-c4-stage1-telemetry-intent-v1"] = (
        "rei-c4-stage1-telemetry-intent-v1"
    )
    intent_id: NonEmptyId
    intent_sha256: HashDigest
    run_id: NonEmptyId
    attempt_id: NonEmptyId
    screen_contract_id: NonEmptyId
    screen_contract_sha256: HashDigest
    worker_request_id: NonEmptyId
    worker_request_sha256: HashDigest
    option_id: Literal["enter_circle", "remain_edge"]
    provider_slot_id: NonEmptyId
    provider_id: NonEmptyId
    source_artifact_id: NonEmptyId
    source_sha256: HashDigest
    snapshot_manifest_id: NonEmptyId
    snapshot_manifest_sha256: HashDigest
    pipeline_spec_id: NonEmptyId
    pipeline_spec_sha256: HashDigest
    process_request: C4Stage1ProcessRequestCommitment
    telemetry_policy: C4Stage1TelemetryPolicy
    cuda_device: ResourceTelemetryCudaDeviceIdentity
    sampling_policy: Literal["background-start-deadline-cadence-final-endpoint-v1"] = (
        C4_STAGE1_TELEMETRY_SAMPLING_POLICY
    )
    cadence_seconds: float = Field(
        gt=0.0,
        le=RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS,
        allow_inf_nan=False,
    )
    max_samples: int = Field(ge=2, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    join_timeout_seconds: float = Field(
        gt=0.0,
        lt=C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS,
        allow_inf_nan=False,
    )
    cuda_vram_limit_bytes: int = Field(ge=1, le=0x7FFFFFFFFFFFFFFF)
    required_metrics: tuple[NonEmptyId, ...] = C4_STAGE1_TELEMETRY_REQUIRED_METRICS
    pre_inference_pin_required: Literal[True] = True
    durable_finalization_required: Literal[True] = True
    sampled_cuda_peak_is_lower_bound: Literal[True] = True
    absence_of_transient_cuda_breach_proven: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_calls_before_intent: Literal[0] = 0

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        attempt_id: str,
        screen_contract_id: str,
        screen_contract_sha256: str,
        worker_request_id: str,
        worker_request_sha256: str,
        option_id: Literal["enter_circle", "remain_edge"],
        provider_slot_id: str,
        provider_id: str,
        source_artifact_id: str,
        source_sha256: str,
        snapshot_manifest_id: str,
        snapshot_manifest_sha256: str,
        pipeline_spec_id: str,
        pipeline_spec_sha256: str,
        process_request: BoundedProcessRequest,
        cuda_device: ResourceTelemetryCudaDeviceIdentity,
    ) -> Self:
        request_commitment = C4Stage1ProcessRequestCommitment.from_request(
            process_request
        )
        telemetry_policy = c4_stage1_telemetry_policy()
        base = {
            "schema_version": "rei-c4-stage1-telemetry-intent-v1",
            "run_id": run_id,
            "attempt_id": attempt_id,
            "screen_contract_id": screen_contract_id,
            "screen_contract_sha256": screen_contract_sha256,
            "worker_request_id": worker_request_id,
            "worker_request_sha256": worker_request_sha256,
            "option_id": option_id,
            "provider_slot_id": provider_slot_id,
            "provider_id": provider_id,
            "source_artifact_id": source_artifact_id,
            "source_sha256": source_sha256,
            "snapshot_manifest_id": snapshot_manifest_id,
            "snapshot_manifest_sha256": snapshot_manifest_sha256,
            "pipeline_spec_id": pipeline_spec_id,
            "pipeline_spec_sha256": pipeline_spec_sha256,
            "process_request": request_commitment,
            "telemetry_policy": telemetry_policy,
            "cuda_device": cuda_device,
            "sampling_policy": telemetry_policy.sampling_policy,
            "cadence_seconds": telemetry_policy.cadence_seconds,
            "max_samples": telemetry_policy.max_samples,
            "join_timeout_seconds": telemetry_policy.join_timeout_seconds,
            "cuda_vram_limit_bytes": (
                telemetry_policy.sampled_whole_device_cuda_stop_bytes
            ),
            "required_metrics": telemetry_policy.required_metrics,
            "pre_inference_pin_required": True,
            "durable_finalization_required": True,
            "sampled_cuda_peak_is_lower_bound": True,
            "absence_of_transient_cuda_breach_proven": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
            "model_calls_before_intent": 0,
        }
        intent_id, intent_sha256 = _content_addresses(
            "c4_stage1_telemetry_intent",
            base,
        )
        return cls(intent_id=intent_id, intent_sha256=intent_sha256, **base)

    @model_validator(mode="after")
    def validate_intent(self) -> Self:
        C4Stage1ProcessRequestCommitment.model_validate(
            self.process_request.model_dump(mode="python", round_trip=True)
        )
        policy = C4Stage1TelemetryPolicy.model_validate(
            self.telemetry_policy.model_dump(mode="python", round_trip=True)
        )
        cuda_device = ResourceTelemetryCudaDeviceIdentity.model_validate(
            self.cuda_device.model_dump(mode="python", round_trip=True)
        )
        if (
            policy != c4_stage1_telemetry_policy()
            or cuda_device.status != "resolved"
            or self.sampling_policy != policy.sampling_policy
            or self.cadence_seconds != policy.cadence_seconds
            or self.max_samples != policy.max_samples
            or self.join_timeout_seconds != policy.join_timeout_seconds
            or self.required_metrics != policy.required_metrics
            or self.process_request.timeout_seconds
            != policy.per_option_hard_timeout_seconds
            or self.cuda_vram_limit_bytes != policy.sampled_whole_device_cuda_stop_bytes
            or self.pre_inference_pin_required is not True
            or self.durable_finalization_required is not True
            or self.sampled_cuda_peak_is_lower_bound is not True
            or self.absence_of_transient_cuda_breach_proven is not False
            or self.semantic_authority_granted is not False
            or self.production_authority_granted is not False
            or self.model_calls_before_intent != 0
        ):
            raise ValueError("Stage 1 telemetry intent weakens a frozen boundary")
        required_capacity = (
            math.ceil(self.process_request.timeout_seconds / self.cadence_seconds) + 2
        )
        if self.max_samples < required_capacity:
            raise ValueError(
                "Stage 1 telemetry sample limit cannot cover the hard deadline"
            )
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"intent_id", "intent_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_telemetry_intent",
            payload,
        )
        if self.intent_id != expected_id or self.intent_sha256 != expected_sha256:
            raise ValueError("Stage 1 telemetry intent differs from canonical content")
        return self


def c4_stage1_telemetry_intent_relative_path(
    intent: C4Stage1TelemetryIntent,
) -> str:
    intent = _cold_validate_model(
        C4Stage1TelemetryIntent,
        intent,
        label="Stage 1 telemetry intent",
    )
    return f"diagnostics/{intent.intent_id}.telemetry-intent.json"


def persist_c4_stage1_telemetry_intent(
    artifact_store: ArtifactStore,
    intent: C4Stage1TelemetryIntent,
) -> StoredArtifact:
    """Create and cold-read the pre-inference intent before child spawn."""

    if not callable(getattr(artifact_store, "write_json", None)) or not callable(
        getattr(artifact_store, "read_bytes", None)
    ):
        raise TypeError("Stage 1 intent persistence requires write_json/read_bytes")
    intent = _cold_validate_model(
        C4Stage1TelemetryIntent,
        intent,
        label="Stage 1 telemetry intent",
    )
    expected_bytes = canonical_json_bytes(intent)
    relative_path = c4_stage1_telemetry_intent_relative_path(intent)
    try:
        storage = artifact_store.write_json(
            intent.run_id,
            relative_path,
            intent,
            overwrite=False,
        )
        storage = StoredArtifact.model_validate(
            storage.model_dump(mode="python", round_trip=True)
        )
        persisted = artifact_store.read_bytes(storage.storage_id)
    except Exception as exc:
        raise C4Stage1TelemetryPersistenceError(
            "Stage 1 telemetry intent persistence failed closed"
        ) from exc
    if (
        storage.run_id != intent.run_id
        or storage.relative_path != relative_path
        or storage.content_sha256 != _sha256_bytes(expected_bytes)
        or storage.size_bytes != len(expected_bytes)
        or persisted != expected_bytes
    ):
        raise C4Stage1TelemetryPersistenceError(
            "Stage 1 telemetry intent differs after persistence"
        )
    return storage


class C4Stage1TelemetrySample(FrozenModel):
    snapshot: ResourceTelemetrySnapshot
    probe_started_monotonic_ns: int = Field(ge=0)
    probe_finished_monotonic_ns: int = Field(ge=0)

    @classmethod
    def from_background_sample(
        cls,
        sample: BackgroundResourceTelemetrySample,
    ) -> Self:
        if not isinstance(sample, BackgroundResourceTelemetrySample):
            raise TypeError("Stage 1 telemetry sample has the wrong type")
        return cls(
            snapshot=sample.snapshot,
            probe_started_monotonic_ns=sample.probe_started_monotonic_ns,
            probe_finished_monotonic_ns=sample.probe_finished_monotonic_ns,
        )

    @model_validator(mode="after")
    def validate_sample(self) -> Self:
        ResourceTelemetrySnapshot.model_validate(
            self.snapshot.model_dump(mode="python", round_trip=True)
        )
        if self.probe_finished_monotonic_ns < self.probe_started_monotonic_ns:
            raise ValueError("Stage 1 telemetry sample timing is reversed")
        return self

    @property
    def sampling_overhead_monotonic_ns(self) -> int:
        return self.probe_finished_monotonic_ns - self.probe_started_monotonic_ns


def _measured_count(
    samples: tuple[C4Stage1TelemetrySample, ...],
    field_name: str,
) -> int:
    return sum(
        getattr(sample.snapshot, field_name).status == "measured" for sample in samples
    )


def _require_consistent_measured_identity(
    samples: tuple[C4Stage1TelemetrySample, ...],
    field_name: str,
) -> None:
    measured = tuple(
        reading
        for sample in samples
        if (reading := getattr(sample.snapshot, field_name)).status == "measured"
    )
    identities = {
        (reading.source, reading.measurement_scope, reading.subject_id)
        for reading in measured
    }
    if len(identities) > 1:
        raise ValueError(f"Stage 1 telemetry {field_name} changes identity")


def _require_constant_measured_capacity(
    samples: tuple[C4Stage1TelemetrySample, ...],
    field_name: str,
) -> None:
    values = {
        getattr(sample.snapshot, field_name).value_bytes
        for sample in samples
        if getattr(sample.snapshot, field_name).status == "measured"
    }
    if len(values) > 1:
        raise ValueError(f"Stage 1 telemetry {field_name} changes capacity")


def _sampled_cuda_peak(
    samples: tuple[C4Stage1TelemetrySample, ...],
) -> ResourceByteReading:
    measured = tuple(
        sample.snapshot.cuda_vram_used_bytes
        for sample in samples
        if sample.snapshot.cuda_vram_used_bytes.status == "measured"
    )
    if not measured:
        return ResourceByteReading.unavailable("cuda_vram_not_measured")
    identities = {
        (reading.source, reading.measurement_scope, reading.subject_id)
        for reading in measured
    }
    if len(identities) != 1:
        raise ValueError("Stage 1 sampled CUDA readings change identity")
    source, scope, subject_id = next(iter(identities))
    if source is None or scope is None or subject_id is None:
        raise ValueError("Stage 1 sampled CUDA identity is incomplete")
    peak = max(
        reading.value_bytes for reading in measured if reading.value_bytes is not None
    )
    return ResourceByteReading.measured(
        peak,
        source=source,
        measurement_scope=scope,
        subject_id=subject_id,
    )


def _all_required_metrics_observed(
    samples: tuple[C4Stage1TelemetrySample, ...],
) -> bool:
    return bool(samples) and all(
        reading.status == "measured"
        for sample in samples
        for reading in (
            sample.snapshot.process_scope_rss_bytes,
            sample.snapshot.system_ram_total_bytes,
            sample.snapshot.system_ram_available_bytes,
            sample.snapshot.cuda_vram_used_bytes,
            sample.snapshot.cuda_vram_total_bytes,
        )
    )


def _require_process_sample_binding(
    samples: tuple[C4Stage1TelemetrySample, ...],
    record: ProcessTreeExecutionRecord,
) -> None:
    if record.process_id is None or record.target_start_token_hash is None:
        expected_subject_id = None
    else:
        expected_subject_id = ResourceTelemetryProcessTarget(
            root_process_id=record.process_id,
            root_process_start_token_hash=record.target_start_token_hash,
            process_scope="process_tree",
        ).measurement_subject_id
    for sample in samples:
        reading = sample.snapshot.process_scope_rss_bytes
        if reading.status == "measured" and reading.subject_id != expected_subject_id:
            raise ValueError(
                "Stage 1 process RSS sample differs from process execution"
            )


def _require_cuda_sample_binding(
    samples: tuple[C4Stage1TelemetrySample, ...],
    cuda_device: ResourceTelemetryCudaDeviceIdentity,
) -> None:
    if cuda_device.status != "resolved":
        raise ValueError("Stage 1 telemetry CUDA identity is unresolved")
    expected_subject_id = cuda_device.measurement_subject_id
    for sample in samples:
        for reading in (
            sample.snapshot.cuda_vram_used_bytes,
            sample.snapshot.cuda_vram_total_bytes,
        ):
            if (
                reading.status == "measured"
                and reading.subject_id != expected_subject_id
            ):
                raise ValueError(
                    "Stage 1 CUDA sample differs from intended physical device"
                )


class C4Stage1TelemetrySamplesArtifact(FrozenArtifactModel):
    """Durable exact background samples used to replay the Stage 1 summary."""

    schema_version: Literal["rei-c4-stage1-telemetry-samples-v1"] = (
        "rei-c4-stage1-telemetry-samples-v1"
    )
    samples_artifact_id: NonEmptyId
    samples_artifact_sha256: HashDigest
    intent: C4Stage1TelemetryIntent
    process_execution_record_id: NonEmptyId
    process_execution_record_sha256: HashDigest
    sampling_policy: Literal["background-start-deadline-cadence-final-endpoint-v1"] = (
        C4_STAGE1_TELEMETRY_SAMPLING_POLICY
    )
    sampler_terminal_state: BackgroundSamplerState
    sampler_failure_code: NonEmptyId | None = None
    samples: tuple[C4Stage1TelemetrySample, ...] = Field(
        min_length=1,
        max_length=RESOURCE_TELEMETRY_MAX_SAMPLES,
    )
    sample_count: int = Field(ge=1, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    sampling_overhead_monotonic_ns: int = Field(ge=0)
    initial_endpoint_observed: Literal[True] = True
    final_endpoint_observed: bool
    process_rss_measured_samples: int = Field(ge=0)
    system_ram_measured_samples: int = Field(ge=0)
    cuda_vram_measured_samples: int = Field(ge=0)
    all_required_metrics_observed: bool
    sampled_cuda_vram_peak_bytes: ResourceByteReading
    cuda_vram_limit_bytes: int = Field(ge=1, le=0x7FFFFFFFFFFFFFFF)
    sampled_cuda_vram_limit_breached: bool
    sampled_cuda_peak_is_lower_bound: Literal[True] = True
    absence_of_transient_cuda_breach_proven: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def from_result(
        cls,
        *,
        intent: C4Stage1TelemetryIntent,
        process_execution_record: ProcessTreeExecutionRecord,
        result: BackgroundResourceTelemetrySamplerResult,
    ) -> Self:
        intent = _cold_validate_model(
            C4Stage1TelemetryIntent,
            intent,
            label="Stage 1 telemetry intent",
        )
        record = _cold_validate_model(
            ProcessTreeExecutionRecord,
            process_execution_record,
            label="Stage 1 process execution record",
        )
        result = _cold_validate_background_result(result)
        if not result.samples:
            raise ValueError("Stage 1 samples artifact requires at least one sample")
        samples = tuple(
            C4Stage1TelemetrySample.from_background_sample(sample)
            for sample in result.samples
        )
        _require_process_sample_binding(samples, record)
        peak = _sampled_cuda_peak(samples)
        peak_value = peak.value_bytes if peak.status == "measured" else None
        base = {
            "schema_version": "rei-c4-stage1-telemetry-samples-v1",
            "intent": intent,
            "process_execution_record_id": record.record_id,
            "process_execution_record_sha256": _canonical_sha256(record),
            "sampling_policy": C4_STAGE1_TELEMETRY_SAMPLING_POLICY,
            "sampler_terminal_state": result.status.state,
            "sampler_failure_code": result.status.failure_code,
            "samples": samples,
            "sample_count": len(samples),
            "sampling_overhead_monotonic_ns": (result.sampling_overhead_monotonic_ns),
            "initial_endpoint_observed": True,
            "final_endpoint_observed": (
                result.status.state in {"finished", "sample_limit_reached"}
                and len(samples) >= 2
            ),
            "process_rss_measured_samples": _measured_count(
                samples,
                "process_scope_rss_bytes",
            ),
            "system_ram_measured_samples": min(
                _measured_count(samples, "system_ram_total_bytes"),
                _measured_count(samples, "system_ram_available_bytes"),
            ),
            "cuda_vram_measured_samples": min(
                _measured_count(samples, "cuda_vram_used_bytes"),
                _measured_count(samples, "cuda_vram_total_bytes"),
            ),
            "all_required_metrics_observed": _all_required_metrics_observed(samples),
            "sampled_cuda_vram_peak_bytes": peak,
            "cuda_vram_limit_bytes": intent.cuda_vram_limit_bytes,
            "sampled_cuda_vram_limit_breached": (
                peak_value is not None and peak_value > intent.cuda_vram_limit_bytes
            ),
            "sampled_cuda_peak_is_lower_bound": True,
            "absence_of_transient_cuda_breach_proven": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        artifact_id, artifact_sha256 = _content_addresses(
            "c4_stage1_telemetry_samples",
            base,
        )
        return cls(
            samples_artifact_id=artifact_id,
            samples_artifact_sha256=artifact_sha256,
            **base,
        )

    @model_validator(mode="after")
    def validate_samples_artifact(self) -> Self:
        C4Stage1TelemetryIntent.model_validate(
            self.intent.model_dump(mode="python", round_trip=True)
        )
        samples = tuple(
            C4Stage1TelemetrySample.model_validate(
                sample.model_dump(mode="python", round_trip=True)
            )
            for sample in self.samples
        )
        if self.sample_count != len(samples):
            raise ValueError("Stage 1 telemetry sample count differs from samples")
        if any(
            current.probe_started_monotonic_ns < previous.probe_finished_monotonic_ns
            for previous, current in zip(samples, samples[1:], strict=False)
        ):
            raise ValueError("Stage 1 telemetry samples overlap or move backwards")
        for field_name in (
            "process_scope_rss_bytes",
            "system_ram_total_bytes",
            "system_ram_available_bytes",
            "cuda_vram_used_bytes",
            "cuda_vram_total_bytes",
        ):
            _require_consistent_measured_identity(samples, field_name)
        _require_cuda_sample_binding(samples, self.intent.cuda_device)
        _require_constant_measured_capacity(samples, "system_ram_total_bytes")
        _require_constant_measured_capacity(samples, "cuda_vram_total_bytes")
        expected_peak = _sampled_cuda_peak(samples)
        expected_peak_value = (
            expected_peak.value_bytes if expected_peak.status == "measured" else None
        )
        if (
            self.sampling_policy != C4_STAGE1_TELEMETRY_SAMPLING_POLICY
            or self.sampled_cuda_peak_is_lower_bound is not True
            or self.absence_of_transient_cuda_breach_proven is not False
            or self.semantic_authority_granted is not False
            or self.production_authority_granted is not False
            or self.cuda_vram_limit_bytes != self.intent.cuda_vram_limit_bytes
            or self.sampling_overhead_monotonic_ns
            != sum(sample.sampling_overhead_monotonic_ns for sample in samples)
            or self.final_endpoint_observed
            != (
                self.sampler_terminal_state in {"finished", "sample_limit_reached"}
                and len(samples) >= 2
            )
            or self.process_rss_measured_samples
            != _measured_count(samples, "process_scope_rss_bytes")
            or self.system_ram_measured_samples
            != min(
                _measured_count(samples, "system_ram_total_bytes"),
                _measured_count(samples, "system_ram_available_bytes"),
            )
            or self.cuda_vram_measured_samples
            != min(
                _measured_count(samples, "cuda_vram_used_bytes"),
                _measured_count(samples, "cuda_vram_total_bytes"),
            )
            or self.all_required_metrics_observed
            != _all_required_metrics_observed(samples)
            or self.sampled_cuda_vram_peak_bytes != expected_peak
            or self.sampled_cuda_vram_limit_breached
            != (
                expected_peak_value is not None
                and expected_peak_value > self.cuda_vram_limit_bytes
            )
        ):
            raise ValueError("Stage 1 telemetry samples artifact is inconsistent")
        failure_required = self.sampler_terminal_state in {"failed", "join_timed_out"}
        if failure_required != (self.sampler_failure_code is not None):
            raise ValueError("Stage 1 sampler failure provenance is inconsistent")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"samples_artifact_id", "samples_artifact_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_telemetry_samples",
            payload,
        )
        if (
            self.samples_artifact_id != expected_id
            or self.samples_artifact_sha256 != expected_sha256
        ):
            raise ValueError("Stage 1 samples artifact differs from canonical content")
        if (
            len(canonical_json_bytes(self))
            > C4_STAGE1_TELEMETRY_MAX_SAMPLES_ARTIFACT_BYTES
        ):
            raise ValueError("Stage 1 telemetry samples artifact exceeds its bound")
        return self


def _process_request_matches_record(
    commitment: C4Stage1ProcessRequestCommitment,
    record: ProcessTreeExecutionRecord,
) -> bool:
    return (
        record.workload_id == commitment.workload_id
        and record.command_identity == commitment.command_identity
        and record.argument_count == commitment.argument_count
        and record.working_directory_identity == commitment.working_directory_identity
        and record.environment_identity == commitment.environment_identity
        and record.timeout_seconds == commitment.timeout_seconds
        and record.stdout_limit_bytes == commitment.stdout_limit_bytes
        and record.stderr_limit_bytes == commitment.stderr_limit_bytes
    )


def _derived_failure_codes(
    *,
    process_execution_record: ProcessTreeExecutionRecord,
    process_request_binding_verified: bool,
    sampler_terminal_state: BackgroundSamplerState,
    sampler_failure_code: str | None,
    sampler_sample_count: int,
    durable_sample_count: int,
    initial_endpoint_observed: bool,
    final_endpoint_observed: bool,
    all_required_metrics_observed: bool,
    sampled_cuda_vram_limit_breached: bool,
    samples_persistence_status: SamplesPersistenceStatus,
    finalizer_failure_codes: tuple[FinalizerFailureCode, ...],
) -> tuple[str, ...]:
    failures: set[str] = set(finalizer_failure_codes)
    if process_execution_record.status != "succeeded":
        failures.add("process_execution_failed")
    if not process_request_binding_verified:
        failures.add("process_request_execution_binding_mismatch")
    if sampler_terminal_state == "join_timed_out":
        failures.add("sampler_join_timeout")
    elif sampler_terminal_state == "sample_limit_reached":
        failures.add("sampler_sample_limit_reached")
    elif sampler_terminal_state == "failed":
        failures.add(sampler_failure_code or "background_sampler_failure")
    elif sampler_terminal_state != "finished":
        failures.add("sampler_nonterminal_result")
    if sampler_sample_count != durable_sample_count:
        failures.add("sampler_samples_not_durably_exposed")
    if durable_sample_count < 2:
        failures.add("insufficient_telemetry_samples")
    if not initial_endpoint_observed:
        failures.add("initial_telemetry_endpoint_missing")
    if not final_endpoint_observed:
        failures.add("final_telemetry_endpoint_missing")
    if not all_required_metrics_observed:
        failures.add("required_telemetry_unavailable")
    if sampled_cuda_vram_limit_breached:
        failures.add("sampled_cuda_vram_limit_breached")
    if samples_persistence_status != "persisted":
        failures.add(
            "telemetry_samples_missing"
            if samples_persistence_status == "not_created"
            else "telemetry_samples_persistence_failure"
        )
    return tuple(sorted(failures))


class C4Stage1TelemetryFinalizationReceipt(FrozenArtifactModel):
    """Terminal technical disposition; it grants no semantic authority."""

    schema_version: Literal["rei-c4-stage1-telemetry-finalization-v1"] = (
        "rei-c4-stage1-telemetry-finalization-v1"
    )
    finalization_receipt_id: NonEmptyId
    finalization_receipt_sha256: HashDigest
    intent: C4Stage1TelemetryIntent
    process_execution_record: ProcessTreeExecutionRecord
    process_execution_record_sha256: HashDigest
    process_request_binding_verified: bool
    sampler_terminal_state: BackgroundSamplerState
    sampler_failure_code: NonEmptyId | None = None
    sampler_sample_count: int = Field(ge=0, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    durable_sample_count: int = Field(ge=0, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    sampling_overhead_monotonic_ns: int = Field(ge=0)
    initial_endpoint_observed: bool
    final_endpoint_observed: bool
    all_required_metrics_observed: bool
    sampled_cuda_vram_peak_bytes: ResourceByteReading
    cuda_vram_limit_bytes: int = Field(ge=1, le=0x7FFFFFFFFFFFFFFF)
    sampled_cuda_vram_limit_breached: bool
    samples_artifact_id: NonEmptyId | None = None
    samples_artifact_sha256: HashDigest | None = None
    samples_artifact_content_sha256: HashDigest | None = None
    samples_artifact_size_bytes: int | None = Field(default=None, ge=1)
    samples_storage: StoredArtifact | None = None
    samples_persistence_status: SamplesPersistenceStatus
    finalizer_failure_codes: tuple[FinalizerFailureCode, ...] = Field(max_length=1)
    failure_codes: tuple[NonEmptyId, ...]
    disposition: TelemetryDisposition
    technical_passed: bool
    sampled_cuda_peak_is_lower_bound: Literal[True] = True
    absence_of_transient_cuda_breach_proven: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        intent = C4Stage1TelemetryIntent.model_validate(
            self.intent.model_dump(mode="python", round_trip=True)
        )
        record = ProcessTreeExecutionRecord.model_validate(
            self.process_execution_record.model_dump(mode="python", round_trip=True)
        )
        ResourceByteReading.model_validate(
            self.sampled_cuda_vram_peak_bytes.model_dump(
                mode="python",
                round_trip=True,
            )
        )
        binding = _process_request_matches_record(intent.process_request, record)
        refs = (
            self.samples_artifact_id,
            self.samples_artifact_sha256,
            self.samples_artifact_content_sha256,
            self.samples_artifact_size_bytes,
        )
        if any(item is None for item in refs) != all(item is None for item in refs):
            raise ValueError("Stage 1 samples artifact references are partial")
        if self.samples_persistence_status == "persisted":
            if self.samples_storage is None or any(item is None for item in refs):
                raise ValueError("Persisted Stage 1 samples require storage evidence")
            storage = StoredArtifact.model_validate(
                self.samples_storage.model_dump(mode="python", round_trip=True)
            )
            if (
                storage.run_id != intent.run_id
                or storage.relative_path
                != f"diagnostics/{intent.intent_id}.telemetry-samples.json"
                or storage.content_sha256 != self.samples_artifact_content_sha256
                or storage.size_bytes != self.samples_artifact_size_bytes
            ):
                raise ValueError(
                    "Stage 1 samples storage differs from artifact evidence"
                )
        elif self.samples_storage is not None:
            raise ValueError(
                "Unpersisted Stage 1 samples cannot carry storage evidence"
            )
        if self.samples_persistence_status == "not_created" and any(
            item is not None for item in refs
        ):
            raise ValueError("Missing Stage 1 samples cannot carry artifact references")
        if self.samples_persistence_status == "persisted":
            if (
                self.durable_sample_count == 0
                or self.durable_sample_count != self.sampler_sample_count
            ):
                raise ValueError("Persisted Stage 1 sample counts are inconsistent")
        elif self.durable_sample_count != 0:
            raise ValueError("Unpersisted Stage 1 samples cannot be counted as durable")
        failure_required = self.sampler_terminal_state in {"failed", "join_timed_out"}
        if failure_required != (self.sampler_failure_code is not None):
            raise ValueError("Stage 1 sampler failure provenance is inconsistent")
        peak_value = (
            self.sampled_cuda_vram_peak_bytes.value_bytes
            if self.sampled_cuda_vram_peak_bytes.status == "measured"
            else None
        )
        if self.sampled_cuda_vram_peak_bytes.status == "measured" and (
            self.sampled_cuda_vram_peak_bytes.measurement_scope != "cuda_device_memory"
            or self.sampled_cuda_vram_peak_bytes.subject_id
            != intent.cuda_device.measurement_subject_id
        ):
            raise ValueError("Stage 1 sampled CUDA peak has the wrong device identity")
        expected_failures = _derived_failure_codes(
            process_execution_record=record,
            process_request_binding_verified=binding,
            sampler_terminal_state=self.sampler_terminal_state,
            sampler_failure_code=self.sampler_failure_code,
            sampler_sample_count=self.sampler_sample_count,
            durable_sample_count=self.durable_sample_count,
            initial_endpoint_observed=self.initial_endpoint_observed,
            final_endpoint_observed=self.final_endpoint_observed,
            all_required_metrics_observed=self.all_required_metrics_observed,
            sampled_cuda_vram_limit_breached=(
                peak_value is not None and peak_value > self.cuda_vram_limit_bytes
            ),
            samples_persistence_status=self.samples_persistence_status,
            finalizer_failure_codes=self.finalizer_failure_codes,
        )
        if (
            self.process_execution_record_sha256 != _canonical_sha256(record)
            or self.process_request_binding_verified != binding
            or self.cuda_vram_limit_bytes != intent.cuda_vram_limit_bytes
            or self.sampled_cuda_vram_limit_breached
            != (peak_value is not None and peak_value > self.cuda_vram_limit_bytes)
            or self.failure_codes != expected_failures
            or self.technical_passed != (not expected_failures)
            or self.disposition != ("passed" if not expected_failures else "failed")
            or self.sampled_cuda_peak_is_lower_bound is not True
            or self.absence_of_transient_cuda_breach_proven is not False
            or self.semantic_authority_granted is not False
            or self.production_authority_granted is not False
        ):
            raise ValueError("Stage 1 telemetry finalization receipt is inconsistent")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"finalization_receipt_id", "finalization_receipt_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_telemetry_finalization",
            payload,
        )
        if (
            self.finalization_receipt_id != expected_id
            or self.finalization_receipt_sha256 != expected_sha256
        ):
            raise ValueError("Stage 1 finalization receipt differs from content")
        if len(canonical_json_bytes(self)) > C4_STAGE1_TELEMETRY_MAX_RECEIPT_BYTES:
            raise ValueError("Stage 1 telemetry finalization receipt exceeds its bound")
        return self


def _build_finalization_receipt(
    *,
    intent: C4Stage1TelemetryIntent,
    process_execution_record: ProcessTreeExecutionRecord,
    result: BackgroundResourceTelemetrySamplerResult,
    samples_artifact: C4Stage1TelemetrySamplesArtifact | None,
    samples_storage: StoredArtifact | None,
    samples_persistence_status: SamplesPersistenceStatus,
    finalizer_failure_codes: tuple[FinalizerFailureCode, ...] = (),
) -> C4Stage1TelemetryFinalizationReceipt:
    samples = () if samples_artifact is None else samples_artifact.samples
    durable_sample_count = (
        len(samples) if samples_persistence_status == "persisted" else 0
    )
    initial_endpoint_observed = bool(samples)
    final_endpoint_observed = (
        False if samples_artifact is None else samples_artifact.final_endpoint_observed
    )
    all_required_metrics_observed = (
        False
        if samples_artifact is None
        else samples_artifact.all_required_metrics_observed
    )
    if samples_artifact is not None:
        peak = samples_artifact.sampled_cuda_vram_peak_bytes
    else:
        status_peak = result.status.sampled_cuda_vram_peak
        peak = (
            status_peak
            if status_peak is not None
            and status_peak.measurement_scope == "cuda_device_memory"
            and status_peak.subject_id == intent.cuda_device.measurement_subject_id
            else ResourceByteReading.unavailable("cuda_vram_not_measured")
        )
    binding = _process_request_matches_record(
        intent.process_request,
        process_execution_record,
    )
    peak_value = peak.value_bytes if peak.status == "measured" else None
    failure_codes = _derived_failure_codes(
        process_execution_record=process_execution_record,
        process_request_binding_verified=binding,
        sampler_terminal_state=result.status.state,
        sampler_failure_code=result.status.failure_code,
        sampler_sample_count=result.status.sample_count,
        durable_sample_count=durable_sample_count,
        initial_endpoint_observed=initial_endpoint_observed,
        final_endpoint_observed=final_endpoint_observed,
        all_required_metrics_observed=all_required_metrics_observed,
        sampled_cuda_vram_limit_breached=(
            peak_value is not None and peak_value > intent.cuda_vram_limit_bytes
        ),
        samples_persistence_status=samples_persistence_status,
        finalizer_failure_codes=finalizer_failure_codes,
    )
    samples_bytes = (
        None if samples_artifact is None else canonical_json_bytes(samples_artifact)
    )
    base = {
        "schema_version": "rei-c4-stage1-telemetry-finalization-v1",
        "intent": intent,
        "process_execution_record": process_execution_record,
        "process_execution_record_sha256": _canonical_sha256(process_execution_record),
        "process_request_binding_verified": binding,
        "sampler_terminal_state": result.status.state,
        "sampler_failure_code": result.status.failure_code,
        "sampler_sample_count": result.status.sample_count,
        "durable_sample_count": durable_sample_count,
        "sampling_overhead_monotonic_ns": result.sampling_overhead_monotonic_ns,
        "initial_endpoint_observed": initial_endpoint_observed,
        "final_endpoint_observed": final_endpoint_observed,
        "all_required_metrics_observed": all_required_metrics_observed,
        "sampled_cuda_vram_peak_bytes": peak,
        "cuda_vram_limit_bytes": intent.cuda_vram_limit_bytes,
        "sampled_cuda_vram_limit_breached": (
            peak_value is not None and peak_value > intent.cuda_vram_limit_bytes
        ),
        "samples_artifact_id": (
            None if samples_artifact is None else samples_artifact.samples_artifact_id
        ),
        "samples_artifact_sha256": (
            None
            if samples_artifact is None
            else samples_artifact.samples_artifact_sha256
        ),
        "samples_artifact_content_sha256": (
            None if samples_bytes is None else _sha256_bytes(samples_bytes)
        ),
        "samples_artifact_size_bytes": (
            None if samples_bytes is None else len(samples_bytes)
        ),
        "samples_storage": samples_storage,
        "samples_persistence_status": samples_persistence_status,
        "finalizer_failure_codes": finalizer_failure_codes,
        "failure_codes": failure_codes,
        "disposition": "passed" if not failure_codes else "failed",
        "technical_passed": not failure_codes,
        "sampled_cuda_peak_is_lower_bound": True,
        "absence_of_transient_cuda_breach_proven": False,
        "semantic_authority_granted": False,
        "production_authority_granted": False,
    }
    receipt_id, receipt_sha256 = _content_addresses(
        "c4_stage1_telemetry_finalization",
        base,
    )
    return C4Stage1TelemetryFinalizationReceipt(
        finalization_receipt_id=receipt_id,
        finalization_receipt_sha256=receipt_sha256,
        **base,
    )


@dataclass(frozen=True, slots=True)
class C4Stage1TelemetryFinalizationOutcome:
    samples_artifact: C4Stage1TelemetrySamplesArtifact | None
    samples_storage: StoredArtifact | None
    receipt: C4Stage1TelemetryFinalizationReceipt
    receipt_storage: StoredArtifact | None

    def __post_init__(self) -> None:
        receipt = _cold_validate_model(
            C4Stage1TelemetryFinalizationReceipt,
            self.receipt,
            label="Stage 1 finalization receipt",
        )
        samples_artifact = (
            None
            if self.samples_artifact is None
            else _cold_validate_model(
                C4Stage1TelemetrySamplesArtifact,
                self.samples_artifact,
                label="Stage 1 finalization samples artifact",
            )
        )
        samples_storage = (
            None
            if self.samples_storage is None
            else StoredArtifact.model_validate(
                self.samples_storage.model_dump(mode="python", round_trip=True)
            )
        )
        artifact_referenced = receipt.samples_artifact_id is not None
        if samples_artifact is not None and not artifact_referenced:
            raise ValueError("Stage 1 finalization samples outcome is incomplete")
        if (
            receipt.samples_persistence_status == "persisted"
            and samples_artifact is None
        ):
            raise ValueError("Stage 1 persisted samples outcome is incomplete")
        if samples_artifact is not None:
            samples_bytes = canonical_json_bytes(samples_artifact)
            if (
                samples_artifact.intent != receipt.intent
                or samples_artifact.process_execution_record_id
                != receipt.process_execution_record.record_id
                or samples_artifact.process_execution_record_sha256
                != receipt.process_execution_record_sha256
                or samples_artifact.samples_artifact_id != receipt.samples_artifact_id
                or samples_artifact.samples_artifact_sha256
                != receipt.samples_artifact_sha256
                or _sha256_bytes(samples_bytes)
                != receipt.samples_artifact_content_sha256
                or len(samples_bytes) != receipt.samples_artifact_size_bytes
                or samples_artifact.sampler_terminal_state
                != receipt.sampler_terminal_state
                or samples_artifact.sampler_failure_code != receipt.sampler_failure_code
                or samples_artifact.sample_count != receipt.sampler_sample_count
                or (
                    receipt.samples_persistence_status == "persisted"
                    and samples_artifact.sample_count != receipt.durable_sample_count
                )
                or samples_artifact.sampling_overhead_monotonic_ns
                != receipt.sampling_overhead_monotonic_ns
                or samples_artifact.initial_endpoint_observed
                != receipt.initial_endpoint_observed
                or samples_artifact.final_endpoint_observed
                != receipt.final_endpoint_observed
                or samples_artifact.all_required_metrics_observed
                != receipt.all_required_metrics_observed
                or samples_artifact.sampled_cuda_vram_peak_bytes
                != receipt.sampled_cuda_vram_peak_bytes
                or samples_artifact.sampled_cuda_vram_limit_breached
                != receipt.sampled_cuda_vram_limit_breached
            ):
                raise ValueError("Stage 1 finalization samples lineage is invalid")
            _require_process_sample_binding(
                samples_artifact.samples,
                receipt.process_execution_record,
            )
        if samples_storage != receipt.samples_storage:
            raise ValueError(
                "Stage 1 finalization samples storage differs from receipt"
            )
        if samples_storage is not None:
            if samples_artifact is None:
                raise ValueError("Stage 1 persisted samples artifact is missing")
            samples_bytes = canonical_json_bytes(samples_artifact)
            if (
                samples_storage.run_id != receipt.intent.run_id
                or samples_storage.relative_path
                != f"diagnostics/{receipt.intent.intent_id}.telemetry-samples.json"
                or samples_storage.content_sha256 != _sha256_bytes(samples_bytes)
                or samples_storage.size_bytes != len(samples_bytes)
            ):
                raise ValueError("Stage 1 finalization samples storage is invalid")
        if self.receipt_storage is not None:
            storage = StoredArtifact.model_validate(
                self.receipt_storage.model_dump(mode="python", round_trip=True)
            )
            receipt_bytes = canonical_json_bytes(receipt)
            if (
                storage.run_id != receipt.intent.run_id
                or storage.relative_path
                != f"diagnostics/{receipt.intent.intent_id}.telemetry-finalization.json"
                or storage.content_sha256 != _sha256_bytes(receipt_bytes)
                or storage.size_bytes != len(receipt_bytes)
                or receipt.finalizer_failure_codes
            ):
                raise ValueError("Stage 1 finalization storage differs from receipt")

    @property
    def durable_terminal_receipt(self) -> bool:
        return self.receipt_storage is not None

    @property
    def technical_passed(self) -> bool:
        return self.durable_terminal_receipt and self.receipt.technical_passed


TelemetryProbeFactory = Callable[
    [
        ProcessLifecycleContext,
        ResourceTelemetryProcessTarget,
        ResourceTelemetryCudaDeviceIdentity,
    ],
    ResourceTelemetryProbe,
]


def _process_target_from_context(
    context: ProcessLifecycleContext,
) -> ResourceTelemetryProcessTarget:
    if not isinstance(context, ProcessLifecycleContext):
        raise TypeError("Stage 1 telemetry requires a lifecycle context")
    return ResourceTelemetryProcessTarget(
        root_process_id=context.target.pid,
        root_process_start_token_hash=context.target.start_token_hash,
        process_scope="process_tree",
    )


def build_c4_stage1_bound_system_probe(
    context: ProcessLifecycleContext,
    target: ResourceTelemetryProcessTarget,
    cuda_device: ResourceTelemetryCudaDeviceIdentity,
    *,
    nvidia_smi_executable: str | Path | None = None,
) -> SystemResourceTelemetryProbe:
    """Build the default exact Job-tree and physical-CUDA Stage 1 probe."""

    if not isinstance(context, ProcessLifecycleContext):
        raise TypeError("Stage 1 system probe requires a lifecycle context")
    expected_target = _process_target_from_context(context)
    target = _cold_validate_model(
        ResourceTelemetryProcessTarget,
        target,
        label="Stage 1 telemetry process target",
    )
    cuda_device = _cold_validate_model(
        ResourceTelemetryCudaDeviceIdentity,
        cuda_device,
        label="Stage 1 telemetry CUDA identity",
    )
    if (
        context.isolation_mode != "windows_job_object_kill_on_close"
        or not context.process_tree_rss_available
        or context.process_tree_rss_source is None
        or target != expected_target
        or cuda_device.status != "resolved"
    ):
        raise C4Stage1TelemetryLifecycleError(
            "Stage 1 telemetry requires exact Job-tree and CUDA identity"
        )

    def read_process_tree_rss(
        actual_target: ResourceTelemetryProcessTarget,
    ) -> ResourceByteReading:
        if actual_target != expected_target:
            return ResourceByteReading.unavailable("process_memory_subject_mismatch")
        try:
            value = context.read_process_tree_rss_bytes()
        except Exception:
            return ResourceByteReading.unavailable("process_tree_rss_unavailable")
        return ResourceByteReading.measured(
            value,
            source=context.process_tree_rss_source,
            measurement_scope="process_scope_rss",
            subject_id=expected_target.measurement_subject_id,
        )

    return SystemResourceTelemetryProbe(
        target=expected_target,
        cuda_device=cuda_device,
        process_memory_reader=read_process_tree_rss,
        nvidia_smi_executable=nvidia_smi_executable,
    )


def _snapshot_has_bound_required_metrics(
    snapshot: ResourceTelemetrySnapshot,
    *,
    target: ResourceTelemetryProcessTarget,
    cuda_device: ResourceTelemetryCudaDeviceIdentity,
) -> bool:
    return (
        all(
            reading.status == "measured"
            for reading in (
                snapshot.process_scope_rss_bytes,
                snapshot.system_ram_total_bytes,
                snapshot.system_ram_available_bytes,
                snapshot.cuda_vram_used_bytes,
                snapshot.cuda_vram_total_bytes,
            )
        )
        and snapshot.process_scope_rss_bytes.subject_id == target.measurement_subject_id
        and snapshot.cuda_vram_used_bytes.subject_id
        == cuda_device.measurement_subject_id
        and snapshot.cuda_vram_total_bytes.subject_id
        == cuda_device.measurement_subject_id
    )


def _status_breaches_cuda_limit(
    status: BackgroundResourceTelemetrySamplerStatus,
    *,
    limit_bytes: int,
) -> bool:
    peak = status.sampled_cuda_vram_peak
    return (
        peak is not None
        and peak.value_bytes is not None
        and peak.value_bytes > limit_bytes
    )


def _status_has_bound_cuda_peak(
    status: BackgroundResourceTelemetrySamplerStatus,
    *,
    cuda_device: ResourceTelemetryCudaDeviceIdentity,
) -> bool:
    peak = status.sampled_cuda_vram_peak
    return (
        peak is not None
        and peak.status == "measured"
        and peak.measurement_scope == "cuda_device_memory"
        and peak.subject_id == cuda_device.measurement_subject_id
    )


def _background_samples_cuda_peak(
    samples: tuple[BackgroundResourceTelemetrySample, ...],
) -> ResourceByteReading | None:
    measured = tuple(
        sample.snapshot.cuda_vram_used_bytes
        for sample in samples
        if sample.snapshot.cuda_vram_used_bytes.status == "measured"
    )
    return (
        None
        if not measured
        else max(
            measured,
            key=lambda reading: (
                reading.value_bytes if reading.value_bytes is not None else -1
            ),
        )
    )


def _snapshot_has_required_metrics(snapshot: ResourceTelemetrySnapshot) -> bool:
    return all(
        reading.status == "measured"
        for reading in (
            snapshot.process_scope_rss_bytes,
            snapshot.system_ram_total_bytes,
            snapshot.system_ram_available_bytes,
            snapshot.cuda_vram_used_bytes,
            snapshot.cuda_vram_total_bytes,
        )
    )


def _failed_background_result(
    failure_code: str,
    *,
    samples: tuple[BackgroundResourceTelemetrySample, ...] = (),
) -> BackgroundResourceTelemetrySamplerResult:
    return BackgroundResourceTelemetrySamplerResult(
        status=BackgroundResourceTelemetrySamplerStatus(
            state="failed",
            sample_count=len(samples),
            failure_code=failure_code,
            latest_sample=samples[-1] if samples else None,
            sampled_cuda_vram_peak=_background_samples_cuda_peak(samples),
        ),
        samples=samples,
        sampling_overhead_monotonic_ns=sum(
            sample.sampling_overhead_monotonic_ns for sample in samples
        ),
    )


def c4_stage1_zero_sample_failure_result(
    failure_code: Literal[
        "stage1_process_not_started",
        "stage1_process_spawn_failure",
        "stage1_parent_execution_failure",
    ] = "stage1_process_not_started",
) -> BackgroundResourceTelemetrySamplerResult:
    """Build a sanitized public terminal result when no child context existed."""

    if failure_code not in {
        "stage1_process_not_started",
        "stage1_process_spawn_failure",
        "stage1_parent_execution_failure",
    }:
        raise ValueError("Stage 1 zero-sample failure code is unsupported")
    return _failed_background_result(failure_code)


class C4Stage1TelemetryLifecycleController:
    """Public bounded observer/controller; polling performs no probe or disk I/O."""

    def __init__(
        self,
        intent: C4Stage1TelemetryIntent,
        *,
        cuda_device: ResourceTelemetryCudaDeviceIdentity,
        probe_factory: TelemetryProbeFactory | None = None,
        nvidia_smi_executable: str | Path | None = None,
        initial_sample_timeout_seconds: float | None = None,
    ) -> None:
        self._intent = _cold_validate_model(
            C4Stage1TelemetryIntent,
            intent,
            label="Stage 1 telemetry intent",
        )
        self._cuda_device = _cold_validate_model(
            ResourceTelemetryCudaDeviceIdentity,
            cuda_device,
            label="Stage 1 telemetry CUDA identity",
        )
        if (
            self._cuda_device.status != "resolved"
            or self._cuda_device != self._intent.cuda_device
        ):
            raise ValueError(
                "Stage 1 telemetry CUDA identity differs from its pinned intent"
            )
        if probe_factory is not None and not callable(probe_factory):
            raise TypeError("Stage 1 telemetry probe factory must be callable")
        self._probe_factory = probe_factory
        self._nvidia_smi_executable = nvidia_smi_executable
        remaining_setup_budget = (
            C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS - self._intent.join_timeout_seconds
        )
        timeout = (
            min(self._intent.join_timeout_seconds, remaining_setup_budget)
            if initial_sample_timeout_seconds is None
            else initial_sample_timeout_seconds
        )
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(float(timeout))
            or not 0.0 < float(timeout) <= C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS
            or float(timeout) + self._intent.join_timeout_seconds
            > C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS
        ):
            raise ValueError(
                "Stage 1 initial telemetry wait must fit its callback budget"
            )
        self._initial_sample_timeout_seconds = float(timeout)
        self._state_lock = Lock()
        self._finish_lock = Lock()
        self._state: Literal[
            "new",
            "starting",
            "running",
            "stop_requested",
            "finished",
            "failed",
        ] = "new"
        self._context: ProcessLifecycleContext | None = None
        self._target: ResourceTelemetryProcessTarget | None = None
        self._sampler: BackgroundResourceTelemetrySampler | None = None
        self._terminal_result: BackgroundResourceTelemetrySamplerResult | None = None
        self._sampled_cuda_limit_breached = False

    @property
    def process_target(self) -> ResourceTelemetryProcessTarget:
        with self._state_lock:
            if self._target is None:
                raise C4Stage1TelemetryStateError(
                    "Stage 1 process target is unavailable before on_started"
                )
            return self._target

    @property
    def sampled_cuda_limit_breached(self) -> bool:
        with self._state_lock:
            return self._sampled_cuda_limit_breached

    @property
    def terminal_result(self) -> BackgroundResourceTelemetrySamplerResult:
        with self._state_lock:
            if self._terminal_result is None:
                raise C4Stage1TelemetryStateError(
                    "Stage 1 telemetry result is not terminal"
                )
            return self._terminal_result

    def _require_matching_context(
        self,
        context: ProcessLifecycleContext,
    ) -> ResourceTelemetryProcessTarget:
        target = _process_target_from_context(context)
        if context.workload_id != self._intent.process_request.workload_id:
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 telemetry context differs from its process request"
            )
        with self._state_lock:
            expected = self._target
        if expected is not None and target != expected:
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 telemetry process target changed during execution"
            )
        return target

    def _make_probe(
        self,
        context: ProcessLifecycleContext,
        target: ResourceTelemetryProcessTarget,
    ) -> ResourceTelemetryProbe:
        if self._probe_factory is not None:
            probe = self._probe_factory(context, target, self._cuda_device)
            if not callable(getattr(probe, "snapshot", None)):
                raise TypeError(
                    "Stage 1 telemetry probe factory returned no snapshot()"
                )
            return probe
        return build_c4_stage1_bound_system_probe(
            context,
            target,
            self._cuda_device,
            nvidia_smi_executable=self._nvidia_smi_executable,
        )

    def _set_terminal_result(
        self,
        result: BackgroundResourceTelemetrySamplerResult,
    ) -> None:
        result = _cold_validate_background_result(result)
        breached = _status_breaches_cuda_limit(
            result.status,
            limit_bytes=self._intent.cuda_vram_limit_bytes,
        )
        with self._state_lock:
            self._terminal_result = result
            self._sampled_cuda_limit_breached = (
                self._sampled_cuda_limit_breached or breached
            )
            self._state = "finished" if result.status.state == "finished" else "failed"

    def _cleanup_setup_failure(
        self,
        sampler: BackgroundResourceTelemetrySampler | None,
        *,
        failure_code: str,
    ) -> None:
        result: BackgroundResourceTelemetrySamplerResult | None = None
        if sampler is not None:
            try:
                sampler.request_stop()
            except BaseException:
                pass
            try:
                result = sampler.finish()
            except BaseException:
                pass
        if result is None:
            result = _failed_background_result(failure_code)
        elif result.status.state in {"failed", "join_timed_out"}:
            pass
        else:
            result = _failed_background_result(
                failure_code,
                samples=result.samples,
            )
        self._set_terminal_result(result)

    def on_started(self, context: ProcessLifecycleContext) -> None:
        with self._state_lock:
            if self._state != "new":
                raise C4Stage1TelemetryStateError(
                    "Stage 1 telemetry on_started can run only once"
                )
            self._state = "starting"

        sampler: BackgroundResourceTelemetrySampler | None = None
        try:
            target = self._require_matching_context(context)
            if (
                context.isolation_mode != "windows_job_object_kill_on_close"
                or not context.process_tree_rss_available
            ):
                raise C4Stage1TelemetryLifecycleError(
                    "Stage 1 telemetry requires authoritative process-tree RSS"
                )
            probe = self._make_probe(context, target)
            sampler = BackgroundResourceTelemetrySampler(
                probe,
                cadence_seconds=self._intent.cadence_seconds,
                max_samples=self._intent.max_samples,
                join_timeout_seconds=self._intent.join_timeout_seconds,
            )
            with self._state_lock:
                self._context = context
                self._target = target
                self._sampler = sampler
            sampler.start()
            status = sampler.wait_for_initial_sample(
                timeout_seconds=self._initial_sample_timeout_seconds
            )
            initial_sample = status.latest_sample
            if (
                status.state != "running"
                or status.sample_count != 1
                or initial_sample is None
                or not _status_has_bound_cuda_peak(
                    status,
                    cuda_device=self._cuda_device,
                )
                or not _snapshot_has_bound_required_metrics(
                    initial_sample.snapshot,
                    target=target,
                    cuda_device=self._cuda_device,
                )
            ):
                raise C4Stage1TelemetryLifecycleError(
                    "Stage 1 initial telemetry sample failed closed"
                )
            if _status_breaches_cuda_limit(
                status,
                limit_bytes=self._intent.cuda_vram_limit_bytes,
            ):
                with self._state_lock:
                    self._sampled_cuda_limit_breached = True
                raise C4Stage1TelemetryLifecycleError(
                    "Stage 1 sampled CUDA limit was breached before release"
                )
        except BaseException as exc:
            self._cleanup_setup_failure(
                sampler,
                failure_code="stage1_telemetry_setup_failure",
            )
            if isinstance(exc, Exception):
                raise C4Stage1TelemetryLifecycleError(
                    "Stage 1 telemetry setup failed closed"
                ) from exc
            raise
        with self._state_lock:
            self._state = "running"

    def on_poll(self, context: ProcessLifecycleContext) -> None:
        self._require_matching_context(context)
        with self._state_lock:
            sampler = self._sampler
            state = self._state
        if sampler is None or state != "running":
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 telemetry poll requires a running sampler"
            )
        status = sampler.poll()
        if status.state != "running":
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 background telemetry became non-running"
            )
        if (
            status.latest_sample is None
            or not _status_has_bound_cuda_peak(
                status,
                cuda_device=self._cuda_device,
            )
            or not _snapshot_has_bound_required_metrics(
                status.latest_sample.snapshot,
                target=self.process_target,
                cuda_device=self._cuda_device,
            )
        ):
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 background telemetry lost required coverage"
            )
        if _status_breaches_cuda_limit(
            status,
            limit_bytes=self._intent.cuda_vram_limit_bytes,
        ):
            with self._state_lock:
                self._sampled_cuda_limit_breached = True
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 sampled CUDA limit was breached"
            )

    def before_termination(
        self,
        context: ProcessLifecycleContext,
        trigger: ProcessTerminationTrigger,
    ) -> None:
        del trigger
        self._require_matching_context(context)
        with self._state_lock:
            sampler = self._sampler
            if self._terminal_result is not None:
                return
            self._state = "stop_requested"
        if sampler is not None:
            sampler.request_stop()

    def _finish_sampler(
        self,
        context: ProcessLifecycleContext,
    ) -> BackgroundResourceTelemetrySamplerResult:
        with self._finish_lock:
            self._require_matching_context(context)
            with self._state_lock:
                if self._terminal_result is not None:
                    return self._terminal_result
                sampler = self._sampler
                self._state = "stop_requested"
            if sampler is None:
                result = _failed_background_result("stage1_sampler_missing")
            else:
                sampler.request_stop()
                try:
                    result = sampler.finish()
                except BaseException:
                    result = _failed_background_result("stage1_sampler_finish_failure")
                    self._set_terminal_result(result)
                    raise
            self._set_terminal_result(result)
            return result

    def _require_successful_terminal_result(
        self,
        result: BackgroundResourceTelemetrySamplerResult,
    ) -> None:
        target = self.process_target
        if (
            result.status.state != "finished"
            or len(result.samples) < 2
            or not _status_has_bound_cuda_peak(
                result.status,
                cuda_device=self._cuda_device,
            )
            or not _snapshot_has_bound_required_metrics(
                result.samples[0].snapshot,
                target=target,
                cuda_device=self._cuda_device,
            )
            or not _snapshot_has_bound_required_metrics(
                result.samples[-1].snapshot,
                target=target,
                cuda_device=self._cuda_device,
            )
            or self.sampled_cuda_limit_breached
        ):
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 telemetry terminal evidence failed closed"
            )

    def after_natural_completion(
        self,
        context: ProcessLifecycleContext,
        outcome: TreeInspectionOutcome,
    ) -> None:
        if (
            not isinstance(outcome, TreeInspectionOutcome)
            or not outcome.empty_tree_confirmed
        ):
            raise C4Stage1TelemetryLifecycleError(
                "Stage 1 natural completion lacks empty-tree evidence"
            )
        result = self._finish_sampler(context)
        self._require_successful_terminal_result(result)

    def after_termination(
        self,
        context: ProcessLifecycleContext,
        outcome: TreeTerminationOutcome,
    ) -> None:
        if not isinstance(outcome, TreeTerminationOutcome):
            raise TypeError("Stage 1 termination callback requires an outcome")
        if not outcome.succeeded:
            self.before_termination(context, "tree_inspection_failure")
            return
        result = self._finish_sampler(context)
        self._require_successful_terminal_result(result)

    def finish_after_runner(self) -> BackgroundResourceTelemetrySamplerResult:
        """Bounded fallback for paths whose terminal runner callback was disabled."""

        with self._state_lock:
            if self._terminal_result is not None:
                return self._terminal_result
            context = self._context
        if context is None:
            result = c4_stage1_zero_sample_failure_result("stage1_process_not_started")
            self._set_terminal_result(result)
            return result
        return self._finish_sampler(context)


class C4Stage1TelemetryFinalizer:
    """Exactly-once owner that persists samples before its terminal receipt."""

    def __init__(
        self,
        intent: C4Stage1TelemetryIntent,
        *,
        artifact_store: ArtifactStore | None,
    ) -> None:
        self._intent = _cold_validate_model(
            C4Stage1TelemetryIntent,
            intent,
            label="Stage 1 telemetry intent",
        )
        if artifact_store is not None and not callable(
            getattr(artifact_store, "write_json", None)
        ):
            raise TypeError("Stage 1 telemetry finalizer requires write_json()")
        self._artifact_store = artifact_store
        self._state: Literal["new", "finalizing", "finalized"] = "new"
        self._state_lock = Lock()
        self._outcome: C4Stage1TelemetryFinalizationOutcome | None = None

    @property
    def samples_relative_path(self) -> str:
        return f"diagnostics/{self._intent.intent_id}.telemetry-samples.json"

    @property
    def receipt_relative_path(self) -> str:
        return f"diagnostics/{self._intent.intent_id}.telemetry-finalization.json"

    @property
    def outcome(self) -> C4Stage1TelemetryFinalizationOutcome:
        with self._state_lock:
            if self._outcome is None:
                raise C4Stage1TelemetryStateError(
                    "Stage 1 telemetry outcome is unavailable before finalization"
                )
            return self._outcome

    def _publish_outcome(
        self,
        outcome: C4Stage1TelemetryFinalizationOutcome,
    ) -> None:
        with self._state_lock:
            self._outcome = outcome
            self._state = "finalized"

    def finalize(
        self,
        *,
        process_execution_record: ProcessTreeExecutionRecord,
        result: BackgroundResourceTelemetrySamplerResult,
    ) -> C4Stage1TelemetryFinalizationOutcome:
        with self._state_lock:
            if self._state != "new":
                raise C4Stage1TelemetryStateError(
                    "Stage 1 telemetry finalization can execute only once"
                )
            self._state = "finalizing"

        record = _cold_validate_model(
            ProcessTreeExecutionRecord,
            process_execution_record,
            label="Stage 1 process execution record",
        )
        result = _cold_validate_background_result(result)
        pending_base_exception: BaseException | None = None
        samples_artifact: C4Stage1TelemetrySamplesArtifact | None = None
        if result.samples:
            try:
                samples_artifact = C4Stage1TelemetrySamplesArtifact.from_result(
                    intent=self._intent,
                    process_execution_record=record,
                    result=result,
                )
            except BaseException as exc:
                if not isinstance(exc, Exception):
                    pending_base_exception = exc
        samples_storage: StoredArtifact | None = None
        samples_status: SamplesPersistenceStatus = (
            "failed" if result.samples else "not_created"
        )

        if (
            samples_artifact is not None
            and self._artifact_store is not None
            and pending_base_exception is None
        ):
            try:
                samples_bytes = canonical_json_bytes(samples_artifact)
                samples_storage = self._artifact_store.write_json(
                    self._intent.run_id,
                    self.samples_relative_path,
                    samples_artifact,
                    overwrite=False,
                )
                samples_storage = StoredArtifact.model_validate(
                    samples_storage.model_dump(mode="python", round_trip=True)
                )
                if (
                    samples_storage.run_id != self._intent.run_id
                    or samples_storage.relative_path != self.samples_relative_path
                    or samples_storage.content_sha256 != _sha256_bytes(samples_bytes)
                    or samples_storage.size_bytes != len(samples_bytes)
                ):
                    raise C4Stage1TelemetryPersistenceError(
                        "Stage 1 samples persistence descriptor is invalid"
                    )
                samples_status = "persisted"
            except BaseException as exc:
                samples_storage = None
                samples_status = "failed"
                if not isinstance(exc, Exception):
                    pending_base_exception = exc

        receipt = _build_finalization_receipt(
            intent=self._intent,
            process_execution_record=record,
            result=result,
            samples_artifact=samples_artifact,
            samples_storage=samples_storage,
            samples_persistence_status=samples_status,
            finalizer_failure_codes=(
                ("telemetry_receipt_persistence_failure",)
                if pending_base_exception is not None
                else ()
            ),
        )
        receipt_storage: StoredArtifact | None = None

        if pending_base_exception is None and self._artifact_store is not None:
            try:
                receipt_bytes = canonical_json_bytes(receipt)
                receipt_storage = self._artifact_store.write_json(
                    self._intent.run_id,
                    self.receipt_relative_path,
                    receipt,
                    overwrite=False,
                )
                receipt_storage = StoredArtifact.model_validate(
                    receipt_storage.model_dump(mode="python", round_trip=True)
                )
                if (
                    receipt_storage.run_id != self._intent.run_id
                    or receipt_storage.relative_path != self.receipt_relative_path
                    or receipt_storage.content_sha256 != _sha256_bytes(receipt_bytes)
                    or receipt_storage.size_bytes != len(receipt_bytes)
                ):
                    raise C4Stage1TelemetryPersistenceError(
                        "Stage 1 receipt persistence descriptor is invalid"
                    )
            except BaseException as exc:
                receipt_storage = None
                receipt = _build_finalization_receipt(
                    intent=self._intent,
                    process_execution_record=record,
                    result=result,
                    samples_artifact=samples_artifact,
                    samples_storage=samples_storage,
                    samples_persistence_status=samples_status,
                    finalizer_failure_codes=("telemetry_receipt_persistence_failure",),
                )
                if not isinstance(exc, Exception):
                    pending_base_exception = exc
        elif self._artifact_store is None and pending_base_exception is None:
            receipt = _build_finalization_receipt(
                intent=self._intent,
                process_execution_record=record,
                result=result,
                samples_artifact=samples_artifact,
                samples_storage=samples_storage,
                samples_persistence_status=samples_status,
                finalizer_failure_codes=("telemetry_receipt_persistence_failure",),
            )

        outcome = C4Stage1TelemetryFinalizationOutcome(
            samples_artifact=samples_artifact,
            samples_storage=samples_storage,
            receipt=receipt,
            receipt_storage=receipt_storage,
        )
        self._publish_outcome(outcome)
        if pending_base_exception is not None:
            raise pending_base_exception
        return outcome


def cold_verify_c4_stage1_telemetry_finalization(
    artifact_store: ArtifactStore,
    receipt_storage: StoredArtifact,
) -> C4Stage1TelemetryFinalizationOutcome:
    """Restart-safe replay of the receipt and its exact samples artifact."""

    if not callable(getattr(artifact_store, "read_bytes", None)):
        raise TypeError("Stage 1 cold verification requires read_bytes()")
    receipt_storage = StoredArtifact.model_validate(
        receipt_storage.model_dump(mode="python", round_trip=True)
    )
    try:
        receipt_bytes = artifact_store.read_bytes(receipt_storage.storage_id)
        receipt = C4Stage1TelemetryFinalizationReceipt.model_validate_json(
            receipt_bytes
        )
    except Exception as exc:
        raise C4Stage1TelemetryPersistenceError(
            "Stage 1 telemetry receipt failed cold verification"
        ) from exc
    if (
        canonical_json_bytes(receipt) != receipt_bytes
        or receipt_storage.run_id != receipt.intent.run_id
        or receipt_storage.relative_path
        != f"diagnostics/{receipt.intent.intent_id}.telemetry-finalization.json"
        or receipt_storage.content_sha256 != _sha256_bytes(receipt_bytes)
        or receipt_storage.size_bytes != len(receipt_bytes)
    ):
        raise C4Stage1TelemetryPersistenceError(
            "Stage 1 telemetry receipt storage binding is invalid"
        )

    samples_artifact: C4Stage1TelemetrySamplesArtifact | None = None
    samples_storage = receipt.samples_storage
    if receipt.samples_persistence_status == "persisted":
        if samples_storage is None:
            raise C4Stage1TelemetryPersistenceError(
                "Stage 1 persisted samples storage is missing"
            )
        try:
            samples_bytes = artifact_store.read_bytes(samples_storage.storage_id)
            samples_artifact = C4Stage1TelemetrySamplesArtifact.model_validate_json(
                samples_bytes
            )
        except Exception as exc:
            raise C4Stage1TelemetryPersistenceError(
                "Stage 1 telemetry samples failed cold verification"
            ) from exc
        if (
            canonical_json_bytes(samples_artifact) != samples_bytes
            or samples_storage.run_id != receipt.intent.run_id
            or samples_storage.relative_path
            != f"diagnostics/{receipt.intent.intent_id}.telemetry-samples.json"
            or samples_storage.content_sha256 != _sha256_bytes(samples_bytes)
            or samples_storage.size_bytes != len(samples_bytes)
            or samples_artifact.intent != receipt.intent
            or samples_artifact.process_execution_record_id
            != receipt.process_execution_record.record_id
            or samples_artifact.process_execution_record_sha256
            != receipt.process_execution_record_sha256
            or samples_artifact.samples_artifact_id != receipt.samples_artifact_id
            or samples_artifact.samples_artifact_sha256
            != receipt.samples_artifact_sha256
            or _sha256_bytes(samples_bytes) != receipt.samples_artifact_content_sha256
            or len(samples_bytes) != receipt.samples_artifact_size_bytes
        ):
            raise C4Stage1TelemetryPersistenceError(
                "Stage 1 telemetry samples lineage is invalid"
            )

    return C4Stage1TelemetryFinalizationOutcome(
        samples_artifact=samples_artifact,
        samples_storage=samples_storage,
        receipt=receipt,
        receipt_storage=receipt_storage,
    )


__all__ = [
    "C4_STAGE1_PER_OPTION_HARD_TIMEOUT_SECONDS",
    "C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES",
    "C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_MIB",
    "C4_STAGE1_TELEMETRY_CADENCE_SECONDS",
    "C4_STAGE1_TELEMETRY_CALLBACK_MAX_SECONDS",
    "C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS",
    "C4_STAGE1_TELEMETRY_MAX_SAMPLES",
    "C4_STAGE1_TELEMETRY_REQUIRED_METRICS",
    "C4_STAGE1_TELEMETRY_SAMPLING_POLICY",
    "C4Stage1ProcessRequestCommitment",
    "C4Stage1TelemetryFinalizationOutcome",
    "C4Stage1TelemetryFinalizationReceipt",
    "C4Stage1TelemetryFinalizer",
    "C4Stage1TelemetryIntent",
    "C4Stage1TelemetryLifecycleController",
    "C4Stage1TelemetryLifecycleError",
    "C4Stage1TelemetryPersistenceError",
    "C4Stage1TelemetryPolicy",
    "C4Stage1TelemetrySample",
    "C4Stage1TelemetrySamplesArtifact",
    "C4Stage1TelemetryStateError",
    "TelemetryProbeFactory",
    "build_c4_stage1_bound_system_probe",
    "c4_stage1_telemetry_intent_relative_path",
    "c4_stage1_telemetry_policy",
    "c4_stage1_zero_sample_failure_result",
    "cold_verify_c4_stage1_telemetry_finalization",
    "persist_c4_stage1_telemetry_intent",
]
