from __future__ import annotations

from collections.abc import Iterator
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from pydantic import ValidationError
import pytest

import app.backend.rei.evaluation.resource_telemetry as telemetry_module
from app.backend.rei.evaluation.resource_telemetry import (
    RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES,
    RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES,
    RESOURCE_TELEMETRY_MAX_SOURCE_ARTIFACTS,
    BackgroundResourceTelemetrySampler,
    ResourceByteReading,
    ResourceTelemetryArtifact,
    ResourceTelemetryCudaDeviceIdentity,
    ResourceTelemetryLimitError,
    ResourceTelemetryMetricCoverage,
    ResourceTelemetryProcessTarget,
    ResourceTelemetryProvenance,
    ResourceTelemetryRuntimeIdentity,
    ResourceTelemetrySnapshot,
    ResourceTelemetryStateError,
    SystemResourceTelemetryProbe,
    UniformResourceTelemetryRecorder,
    capture_resource_telemetry_process_target,
    deserialize_resource_telemetry_artifact,
    serialize_resource_telemetry_artifact,
)


GPU_UUID = "GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
GPU_BUS = "00000000:01:00.0"


class SequenceProbe:
    def __init__(self, snapshots: list[ResourceTelemetrySnapshot]) -> None:
        self._snapshots = iter(snapshots)

    def snapshot(self) -> ResourceTelemetrySnapshot:
        return next(self._snapshots)


class RaisingProbe:
    def snapshot(self) -> ResourceTelemetrySnapshot:
        raise RuntimeError("secret probe detail")


def _clock(*values: int) -> Iterator[int]:
    return iter(values)


def _cuda_identity() -> ResourceTelemetryCudaDeviceIdentity:
    return ResourceTelemetryCudaDeviceIdentity.resolved(
        logical_device_index=0,
        physical_gpu_uuid=GPU_UUID,
        pci_bus_id=GPU_BUS,
    )


def _target(
    *, process_scope: str = "target_root_process"
) -> ResourceTelemetryProcessTarget:
    return ResourceTelemetryProcessTarget(
        root_process_id=42,
        root_process_start_token_hash=hashlib.sha256(
            b"test-start-token-42"
        ).hexdigest(),
        process_scope=process_scope,
    )


def _runtime(
    *, process_scope: str = "target_root_process"
) -> ResourceTelemetryRuntimeIdentity:
    return ResourceTelemetryRuntimeIdentity(
        platform_system="TestOS",
        platform_release="1",
        machine="test-machine",
        python_implementation="CPython",
        python_version="3.14.0",
        python_executable_path_hash=hashlib.sha256(b"python").hexdigest(),
        collector_process_id=99,
        target=_target(process_scope=process_scope),
        cuda_device=_cuda_identity(),
    )


def _provenance(
    workload: str = "racio_interpreter",
    *,
    process_scope: str = "target_root_process",
) -> ResourceTelemetryProvenance:
    return ResourceTelemetryProvenance(
        benchmark_id="c7-uniform-resources",
        run_id="run-1",
        workload=workload,
        arm_id="candidate",
        component_id="component-under-test",
        source_artifact_ids=("artifact-a", "artifact-b"),
        provider_id="provider-a",
        provider_revision="provider-revision-a",
        model_id="model-a",
        model_revision="model-revision-a",
        runtime=_runtime(process_scope=process_scope),
    )


def _measured(
    value: int,
    source: str = "test_probe",
    *,
    measurement_scope: str = "process_scope_rss",
    subject_id: str | None = None,
) -> ResourceByteReading:
    if subject_id is None:
        if measurement_scope == "process_scope_rss":
            subject_id = _target().measurement_subject_id
        elif measurement_scope == "system_physical_memory":
            subject_id = _runtime().system_memory_subject_id
        elif measurement_scope == "cuda_device_memory":
            subject_id = _cuda_identity().measurement_subject_id
    assert subject_id is not None
    return ResourceByteReading.measured(
        value,
        source=source,
        measurement_scope=measurement_scope,  # type: ignore[arg-type]
        subject_id=subject_id,
    )


def _snapshot(
    *,
    rss: int,
    ram_available: int,
    cuda_used: int,
    process_scope: str = "target_root_process",
) -> ResourceTelemetrySnapshot:
    return ResourceTelemetrySnapshot(
        process_scope_rss_bytes=_measured(
            rss,
            subject_id=_target(process_scope=process_scope).measurement_subject_id,
        ),
        system_ram_total_bytes=_measured(
            1_000,
            measurement_scope="system_physical_memory",
        ),
        system_ram_available_bytes=_measured(
            ram_available,
            measurement_scope="system_physical_memory",
        ),
        cuda_vram_used_bytes=_measured(
            cuda_used,
            "test_cuda_probe",
            measurement_scope="cuda_device_memory",
        ),
        cuda_vram_total_bytes=_measured(
            500,
            "test_cuda_probe",
            measurement_scope="cuda_device_memory",
        ),
    )


def _artifact() -> ResourceTelemetryArtifact:
    snapshots = [
        _snapshot(rss=100, ram_available=800, cuda_used=20),
        _snapshot(rss=250, ram_available=600, cuda_used=90),
        _snapshot(rss=200, ram_available=700, cuda_used=40),
    ]
    clock = _clock(
        0,
        100_000_000,
        1_000_000_000,
        1_200_000_000,
        3_500_000_000,
        3_600_000_000,
    )
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe(snapshots),
        clock_ns=lambda: next(clock),
        clock_source="test_monotonic_ns",
    )
    recorder.start()
    recorder.sample()
    return recorder.finish()


def _artifact_create_kwargs(
    artifact: ResourceTelemetryArtifact | None = None,
) -> dict[str, object]:
    value = artifact or _artifact()
    return {
        "provenance": value.provenance,
        "execution_status": value.execution_status,
        "failure_code": value.failure_code,
        "clock_source": value.clock_source,
        "sampling_cadence_target_seconds": (value.sampling_cadence_target_seconds),
        "probe_revision": value.probe_revision,
        "sample_count": value.sample_count,
        "workload_elapsed_monotonic_seconds": (
            value.workload_elapsed_monotonic_seconds
        ),
        "instrumented_interval_monotonic_seconds": (
            value.instrumented_interval_monotonic_seconds
        ),
        "sampling_overhead_monotonic_seconds": (
            value.sampling_overhead_monotonic_seconds
        ),
        "process_rss_start_bytes": value.process_rss_start_bytes,
        "process_rss_end_bytes": value.process_rss_end_bytes,
        "process_rss_peak_sampled_bytes": value.process_rss_peak_sampled_bytes,
        "process_memory_coverage": value.process_memory_coverage,
        "system_ram_total_bytes": value.system_ram_total_bytes,
        "system_ram_available_min_bytes": value.system_ram_available_min_bytes,
        "system_availability_coverage": value.system_availability_coverage,
        "system_capacity_coverage": value.system_capacity_coverage,
        "cuda_vram_start_bytes": value.cuda_vram_start_bytes,
        "cuda_vram_end_bytes": value.cuda_vram_end_bytes,
        "cuda_vram_peak_sampled_bytes": value.cuda_vram_peak_sampled_bytes,
        "cuda_vram_total_bytes": value.cuda_vram_total_bytes,
        "cuda_usage_coverage": value.cuda_usage_coverage,
        "cuda_capacity_coverage": value.cuda_capacity_coverage,
    }


def test_byte_reading_requires_exact_measured_or_unavailable_shape() -> None:
    assert _measured(0).status == "measured"
    assert ResourceByteReading.unavailable("not_supported").value_bytes is None

    with pytest.raises(ValidationError, match="require value, source, scope"):
        ResourceByteReading(status="measured")
    with pytest.raises(ValidationError, match="explicit reason"):
        ResourceByteReading(status="unavailable", value_bytes=0)


def test_cuda_identity_requires_exact_physical_uuid_and_bus_or_reason() -> None:
    assert _cuda_identity().physical_gpu_uuid == GPU_UUID
    unavailable = ResourceTelemetryCudaDeviceIdentity.unavailable(
        logical_device_index=0,
        reason="runtime_identity_unavailable",
    )
    assert unavailable.physical_gpu_uuid is None

    with pytest.raises(ValidationError, match="physical GPU UUID"):
        ResourceTelemetryCudaDeviceIdentity.resolved(
            logical_device_index=0,
            physical_gpu_uuid="MIG-not-accepted-as-physical-gpu",
            pci_bus_id=GPU_BUS,
        )
    with pytest.raises(ValidationError, match="only an explicit reason"):
        ResourceTelemetryCudaDeviceIdentity(
            status="unavailable",
            logical_device_index=0,
            physical_gpu_uuid=GPU_UUID,
            unavailable_reason="ambiguous",
        )


@pytest.mark.parametrize(
    "workload",
    [
        "racio_interpreter",
        "emocio_renderer",
        "vlm_interpreter",
        "semantic_motif",
    ],
)
def test_provenance_supports_each_arm_and_process_scope(workload: str) -> None:
    provenance = _provenance(workload, process_scope="process_tree")
    assert provenance.workload == workload
    assert provenance.runtime.collector_process_id == 99
    assert provenance.runtime.target.process_scope == "process_tree"
    assert (
        provenance.runtime.target.root_process_start_token_hash
        == hashlib.sha256(b"test-start-token-42").hexdigest()
    )


def test_provenance_rejects_ambiguous_or_unbounded_identity() -> None:
    payload = _provenance().model_dump(mode="python", round_trip=True)
    payload["source_artifact_ids"] = ("artifact-b", "artifact-a")
    with pytest.raises(ValidationError, match="sorted and unique"):
        ResourceTelemetryProvenance.model_validate(payload)

    payload = _provenance().model_dump(mode="python", round_trip=True)
    payload["model_revision"] = None
    with pytest.raises(ValidationError, match="model identity"):
        ResourceTelemetryProvenance.model_validate(payload)

    runtime_payload = _runtime().model_dump(mode="python", round_trip=True)
    runtime_payload["platform_system"] = "x" * 201
    with pytest.raises(ValidationError, match="at most 200"):
        ResourceTelemetryRuntimeIdentity.model_validate(runtime_payload)

    payload = _provenance().model_dump(mode="python", round_trip=True)
    payload["source_artifact_ids"] = tuple(
        f"artifact-{index:03d}"
        for index in range(RESOURCE_TELEMETRY_MAX_SOURCE_ARTIFACTS + 1)
    )
    with pytest.raises(ValidationError, match="at most 256"):
        ResourceTelemetryProvenance.model_validate(payload)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        (
            {
                "system_ram_total_bytes": _measured(
                    100,
                    measurement_scope="system_physical_memory",
                ),
                "system_ram_available_bytes": _measured(
                    101,
                    measurement_scope="system_physical_memory",
                ),
            },
            "Available system RAM",
        ),
        (
            {
                "cuda_vram_used_bytes": _measured(
                    501,
                    "cuda",
                    measurement_scope="cuda_device_memory",
                ),
                "cuda_vram_total_bytes": _measured(
                    500,
                    "cuda",
                    measurement_scope="cuda_device_memory",
                ),
            },
            "Used CUDA VRAM",
        ),
    ],
)
def test_snapshot_rejects_physically_impossible_pairs(
    updates: dict[str, ResourceByteReading],
    message: str,
) -> None:
    payload = _snapshot(
        rss=100,
        ram_available=800,
        cuda_used=20,
    ).model_dump(mode="python", round_trip=True)
    payload.update(updates)
    with pytest.raises(ValidationError, match=message):
        ResourceTelemetrySnapshot.model_validate(payload)


def test_snapshot_rejects_cross_subject_or_cross_source_metric_pairs() -> None:
    valid = _snapshot(rss=100, ram_available=800, cuda_used=20)
    payload = valid.model_dump(mode="python", round_trip=True)
    payload["system_ram_available_bytes"]["source"] = "other_system_probe"
    with pytest.raises(ValidationError, match="inconsistent measurement identity"):
        ResourceTelemetrySnapshot.model_validate(payload)

    payload = valid.model_dump(mode="python", round_trip=True)
    payload["cuda_vram_total_bytes"]["subject_id"] = "other_cuda_device"
    with pytest.raises(ValidationError, match="inconsistent measurement identity"):
        ResourceTelemetrySnapshot.model_validate(payload)


def test_nested_model_copy_and_model_construct_are_cold_revalidated() -> None:
    forged_reading = ResourceByteReading.model_construct(
        status="measured",
        value_bytes=-1,
        source="forged",
        measurement_scope="process_scope_rss",
        subject_id=_target().measurement_subject_id,
        unavailable_reason=None,
    )
    snapshot_payload = _snapshot(
        rss=100,
        ram_available=800,
        cuda_used=20,
    ).model_dump(mode="python", round_trip=True)
    snapshot_payload["process_scope_rss_bytes"] = forged_reading
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ResourceTelemetrySnapshot(**snapshot_payload)

    forged_cuda = _cuda_identity().model_copy(update={"pci_bus_id": "not-a-pci-bus"})
    runtime_payload = _runtime().model_dump(mode="python", round_trip=True)
    runtime_payload["cuda_device"] = forged_cuda
    with pytest.raises(ValidationError, match="PCI bus ID"):
        ResourceTelemetryRuntimeIdentity(**runtime_payload)

    forged_target = ResourceTelemetryProcessTarget.model_construct(
        root_process_id=0,
        root_process_start_token_hash="0" * 64,
        process_scope="target_root_process",
    )
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        SystemResourceTelemetryProbe(
            target=forged_target,
            cuda_device=ResourceTelemetryCudaDeviceIdentity.unavailable(
                logical_device_index=0,
                reason="not_needed",
            ),
        )

    with pytest.raises(ValidationError, match="physical GPU UUID"):
        SystemResourceTelemetryProbe(
            target=_target(),
            cuda_device=_cuda_identity().model_copy(
                update={"physical_gpu_uuid": "GPU-forged"}
            ),
        )


def test_artifact_create_cold_revalidates_provenance_and_coverage() -> None:
    kwargs = _artifact_create_kwargs()
    forged_provenance = _provenance().model_copy(update={"provider_revision": None})
    kwargs["provenance"] = forged_provenance
    with pytest.raises(ValidationError, match="provider identity"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["process_memory_coverage"] = ResourceTelemetryMetricCoverage.create(
        attempted_samples=3,
        measured_samples=3,
    ).model_copy(update={"measured_samples": 0})
    with pytest.raises(ValidationError, match="coverage status differs"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["process_rss_peak_sampled_bytes"] = ResourceByteReading.model_construct(
        status="measured",
        value_bytes=-5,
        source="forged",
        unavailable_reason=None,
    )
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]


def test_artifact_create_rejects_mixed_measurement_identities() -> None:
    kwargs = _artifact_create_kwargs()
    process_end = kwargs["process_rss_end_bytes"]
    assert isinstance(process_end, ResourceByteReading)
    kwargs["process_rss_end_bytes"] = process_end.model_copy(
        update={"source": "different_process_reader"}
    )
    with pytest.raises(ValueError, match="inconsistent identities"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    cuda_total = kwargs["cuda_vram_total_bytes"]
    assert isinstance(cuda_total, ResourceByteReading)
    kwargs["cuda_vram_total_bytes"] = cuda_total.model_copy(
        update={"subject_id": "different_cuda_subject"}
    )
    with pytest.raises(ValueError, match="inconsistent identities"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]


def test_recorder_includes_probe_time_in_child_wall_interval() -> None:
    artifact = _artifact()

    assert artifact.sample_count == 3
    assert artifact.instrumented_interval_monotonic_seconds == 3.6
    assert artifact.workload_elapsed_monotonic_seconds == 3.6
    assert artifact.sampling_overhead_monotonic_seconds == 0.4
    assert artifact.sampling_policy == "caller-driven-bounded-v1"
    assert artifact.sampling_cadence_target_seconds == 0.25
    assert artifact.probe_revision == "caller-supplied-resource-probe"
    assert artifact.process_rss_start_bytes.value_bytes == 100
    assert artifact.process_rss_end_bytes.value_bytes == 200
    assert artifact.process_rss_peak_sampled_bytes.value_bytes == 250
    assert artifact.process_peak_scope == "sampled_process_scope_rss_lower_bound"
    assert artifact.process_memory_coverage.status == "complete"
    assert artifact.system_ram_total_bytes.value_bytes == 1_000
    assert artifact.system_ram_available_min_bytes.value_bytes == 600
    assert artifact.system_availability_coverage.status == "complete"
    assert artifact.system_capacity_coverage.status == "complete"
    assert artifact.cuda_vram_start_bytes.value_bytes == 20
    assert artifact.cuda_vram_end_bytes.value_bytes == 40
    assert artifact.cuda_vram_peak_sampled_bytes.value_bytes == 90
    assert artifact.cuda_vram_total_bytes.value_bytes == 500
    assert artifact.cuda_vram_scope == "whole_device_sampled"
    assert artifact.cuda_usage_coverage.status == "complete"
    assert artifact.cuda_capacity_coverage.status == "complete"
    assert artifact.semantic_authority_granted is False
    assert artifact.production_authority_granted is False


def test_artifact_enforces_inclusive_timing_and_coverage_summaries() -> None:
    kwargs = _artifact_create_kwargs()
    kwargs["workload_elapsed_monotonic_seconds"] = 0.0
    with pytest.raises(ValidationError, match="inclusive instrumented interval"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["sampling_overhead_monotonic_seconds"] = 4.0
    with pytest.raises(ValidationError, match="Sampling overhead cannot exceed"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    unavailable = ResourceByteReading.unavailable("forged_missing_summary")
    kwargs["process_rss_start_bytes"] = unavailable
    kwargs["process_rss_end_bytes"] = unavailable
    kwargs["process_rss_peak_sampled_bytes"] = unavailable
    with pytest.raises(ValidationError, match="peak availability differs"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["system_ram_total_bytes"] = unavailable
    kwargs["system_ram_available_min_bytes"] = unavailable
    with pytest.raises(ValidationError, match="available-RAM minimum"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["cuda_vram_start_bytes"] = unavailable
    kwargs["cuda_vram_end_bytes"] = unavailable
    kwargs["cuda_vram_peak_sampled_bytes"] = unavailable
    kwargs["cuda_vram_total_bytes"] = unavailable
    with pytest.raises(ValidationError, match="usage peak availability differs"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    no_coverage = ResourceTelemetryMetricCoverage.create(
        attempted_samples=3,
        measured_samples=0,
    )
    kwargs = _artifact_create_kwargs()
    kwargs["system_availability_coverage"] = no_coverage
    with pytest.raises(ValidationError, match="requires complete availability"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["system_capacity_coverage"] = no_coverage
    with pytest.raises(ValidationError, match="requires complete capacity coverage"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["system_ram_total_bytes"] = unavailable
    with pytest.raises(ValidationError, match="Complete system capacity coverage"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["cuda_usage_coverage"] = no_coverage
    with pytest.raises(ValidationError, match="usage endpoint readings exceed"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["cuda_capacity_coverage"] = no_coverage
    with pytest.raises(ValidationError, match="requires complete capacity coverage"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]

    kwargs = _artifact_create_kwargs()
    kwargs["cuda_vram_total_bytes"] = unavailable
    with pytest.raises(ValidationError, match="Complete CUDA capacity coverage"):
        ResourceTelemetryArtifact.create(**kwargs)  # type: ignore[arg-type]


def test_terminated_target_keeps_pre_kill_peak_with_partial_coverage() -> None:
    available = _snapshot(
        rss=100,
        ram_available=800,
        cuda_used=20,
        process_scope="process_tree",
    )
    terminated = available.model_copy(
        update={
            "process_scope_rss_bytes": ResourceByteReading.unavailable(
                "target_process_terminated"
            )
        }
    )
    clock = _clock(0, 1, 10, 11)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(process_scope="process_tree"),
        probe=SequenceProbe([available, terminated]),
        clock_ns=lambda: next(clock),
    )
    recorder.start()
    artifact = recorder.finish(execution_status="failed", failure_code="hard_timeout")

    assert artifact.process_memory_coverage.status == "partial"
    assert artifact.process_memory_coverage.measured_samples == 1
    assert artifact.process_rss_peak_sampled_bytes.value_bytes == 100
    assert artifact.process_rss_end_bytes.unavailable_reason == (
        "target_process_terminated"
    )
    assert artifact.execution_status == "failed"


def test_any_missing_capacity_sample_is_explicit_and_cuda_peak_is_lower_bound() -> None:
    available = _snapshot(rss=100, ram_available=800, cuda_used=20)
    unavailable_cuda = available.model_copy(
        update={
            "cuda_vram_used_bytes": ResourceByteReading.unavailable(
                "cuda_vram_probe_unavailable"
            ),
            "cuda_vram_total_bytes": ResourceByteReading.unavailable(
                "cuda_vram_probe_unavailable"
            ),
        }
    )
    clock = _clock(0, 1, 10, 11)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([available, unavailable_cuda]),
        clock_ns=lambda: next(clock),
    )
    recorder.start()
    artifact = recorder.finish()

    assert artifact.cuda_usage_coverage.status == "partial"
    assert artifact.cuda_capacity_coverage.status == "partial"
    assert artifact.cuda_vram_peak_sampled_bytes.value_bytes == 20
    assert artifact.cuda_vram_total_bytes.status == "unavailable"
    assert artifact.cuda_vram_end_bytes.unavailable_reason == (
        "cuda_vram_probe_unavailable"
    )


def test_measured_cuda_usage_and_unavailable_capacity_have_separate_coverage() -> None:
    first = _snapshot(rss=100, ram_available=800, cuda_used=20).model_copy(
        update={
            "cuda_vram_total_bytes": ResourceByteReading.unavailable(
                "cuda_capacity_probe_unavailable"
            )
        }
    )
    final = _snapshot(rss=110, ram_available=790, cuda_used=40).model_copy(
        update={
            "cuda_vram_total_bytes": ResourceByteReading.unavailable(
                "cuda_capacity_probe_unavailable"
            )
        }
    )
    clock = _clock(0, 1, 10, 11)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([first, final]),
        clock_ns=lambda: next(clock),
    )
    recorder.start()
    artifact = recorder.finish()

    assert artifact.cuda_usage_coverage.status == "complete"
    assert artifact.cuda_usage_coverage.measured_samples == 2
    assert artifact.cuda_capacity_coverage.status == "unavailable"
    assert artifact.cuda_capacity_coverage.measured_samples == 0
    assert artifact.cuda_vram_start_bytes.value_bytes == 20
    assert artifact.cuda_vram_end_bytes.value_bytes == 40
    assert artifact.cuda_vram_peak_sampled_bytes.value_bytes == 40
    assert artifact.cuda_vram_total_bytes.status == "unavailable"
    assert artifact.cuda_vram_total_bytes.unavailable_reason == "no_measured_samples"
    assert (
        deserialize_resource_telemetry_artifact(
            serialize_resource_telemetry_artifact(artifact)
        )
        == artifact
    )


def test_measured_system_availability_and_unavailable_capacity_are_separate() -> None:
    first = _snapshot(rss=100, ram_available=800, cuda_used=20).model_copy(
        update={
            "system_ram_total_bytes": ResourceByteReading.unavailable(
                "system_capacity_probe_unavailable"
            )
        }
    )
    final = _snapshot(rss=110, ram_available=700, cuda_used=30).model_copy(
        update={
            "system_ram_total_bytes": ResourceByteReading.unavailable(
                "system_capacity_probe_unavailable"
            )
        }
    )
    clock = _clock(0, 1, 10, 11)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([first, final]),
        clock_ns=lambda: next(clock),
    )
    recorder.start()
    artifact = recorder.finish()

    assert artifact.system_availability_coverage.status == "complete"
    assert artifact.system_availability_coverage.measured_samples == 2
    assert artifact.system_capacity_coverage.status == "unavailable"
    assert artifact.system_capacity_coverage.measured_samples == 0
    assert artifact.system_ram_available_min_bytes.value_bytes == 700
    assert artifact.system_ram_total_bytes.status == "unavailable"
    assert artifact.system_ram_total_bytes.unavailable_reason == "no_measured_samples"


def test_probe_exception_is_sanitized_as_unavailable_not_zero() -> None:
    clock = _clock(0, 1, 2, 3)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=RaisingProbe(),
        clock_ns=lambda: next(clock),
    )
    recorder.start()
    artifact = recorder.finish(execution_status="failed", failure_code="arm_failed")

    assert artifact.process_memory_coverage.status == "unavailable"
    assert artifact.process_rss_start_bytes.unavailable_reason == "probe_exception"
    assert artifact.process_rss_peak_sampled_bytes.unavailable_reason == (
        "no_measured_samples"
    )
    assert "secret" not in serialize_resource_telemetry_artifact(artifact).decode()


def test_model_copy_cannot_bypass_snapshot_physical_bounds() -> None:
    valid = _snapshot(rss=100, ram_available=800, cuda_used=20)
    invalid = valid.model_copy(
        update={
            "cuda_vram_used_bytes": _measured(
                600,
                "test_cuda_probe",
                measurement_scope="cuda_device_memory",
            ),
            "cuda_vram_total_bytes": _measured(
                500,
                "test_cuda_probe",
                measurement_scope="cuda_device_memory",
            ),
        }
    )
    clock = _clock(0, 1, 2, 3)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([invalid, invalid]),
        clock_ns=lambda: next(clock),
    )
    recorder.start()
    artifact = recorder.finish(execution_status="failed", failure_code="invalid_probe")

    assert artifact.cuda_usage_coverage.status == "unavailable"
    assert artifact.cuda_capacity_coverage.status == "unavailable"
    assert artifact.cuda_vram_start_bytes.unavailable_reason == "invalid_probe_result"
    assert artifact.cuda_vram_peak_sampled_bytes.unavailable_reason == (
        "no_measured_samples"
    )


def test_recorder_reserves_final_slot_and_rejects_clock_regression() -> None:
    snapshot = _snapshot(rss=100, ram_available=800, cuda_used=20)
    clock = _clock(0, 1, 2, 3)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([snapshot, snapshot]),
        clock_ns=lambda: next(clock),
        max_samples=2,
    )
    recorder.start()
    with pytest.raises(ResourceTelemetryLimitError, match="final sample"):
        recorder.sample()
    artifact = recorder.finish()
    assert artifact.sample_count == 2

    backwards_clock = _clock(5, 6, 7, 4)
    backwards = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([snapshot, snapshot]),
        clock_ns=lambda: next(backwards_clock),
    )
    backwards.start()
    with pytest.raises(ResourceTelemetryStateError, match="moved backwards"):
        backwards.finish()
    with pytest.raises(ResourceTelemetryStateError, match="requires a running"):
        backwards.finish()


def test_post_probe_clock_failure_retains_final_snapshot_and_is_terminal() -> None:
    first = _snapshot(rss=100, ram_available=800, cuda_used=20)
    final = _snapshot(rss=200, ram_available=700, cuda_used=30)
    forbidden_retry = _snapshot(rss=999, ram_available=600, cuda_used=40)

    class CountingProbe:
        def __init__(self) -> None:
            self.snapshots = iter((first, final, forbidden_retry))
            self.calls = 0

        def snapshot(self) -> ResourceTelemetrySnapshot:
            self.calls += 1
            return next(self.snapshots)

    probe = CountingProbe()
    clock = _clock(0, 1, 2, 0, 3, 4)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=probe,
        clock_ns=lambda: next(clock),
    )
    recorder.start()

    with pytest.raises(ResourceTelemetryStateError, match="moved backwards"):
        recorder.finish()
    assert probe.calls == 2
    assert recorder._samples == [first, final]
    with pytest.raises(ResourceTelemetryStateError, match="requires a running"):
        recorder.finish()
    assert probe.calls == 2


def test_invalid_finish_is_retry_safe_and_does_not_consume_final_sample() -> None:
    snapshot = _snapshot(rss=100, ram_available=800, cuda_used=20)
    clock = _clock(0, 1, 2, 3)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([snapshot, snapshot]),
        clock_ns=lambda: next(clock),
    )
    recorder.start()
    with pytest.raises(ValueError, match="failed telemetry must identify"):
        recorder.finish(execution_status="failed")
    with pytest.raises(ValidationError, match="at most 200"):
        recorder.finish(execution_status="failed", failure_code="x" * 201)
    artifact = recorder.finish()
    assert artifact.sample_count == 2


def test_post_snapshot_finalization_failure_is_terminal() -> None:
    first = _snapshot(rss=100, ram_available=800, cuda_used=20)
    second = first.model_copy(
        update={
            "process_scope_rss_bytes": first.process_scope_rss_bytes.model_copy(
                update={"source": "changed_process_reader"}
            )
        }
    )
    clock = _clock(0, 1, 10, 11)
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([first, second]),
        clock_ns=lambda: next(clock),
    )
    recorder.start()

    with pytest.raises(ValueError, match="inconsistent identities"):
        recorder.finish()
    with pytest.raises(ResourceTelemetryStateError, match="requires a running"):
        recorder.finish()
    with pytest.raises(ResourceTelemetryStateError, match="before successful finish"):
        _ = recorder.artifact


def test_uniform_recorder_rejects_non_integral_sample_limit() -> None:
    with pytest.raises(ValueError, match="between 2 and 4096"):
        UniformResourceTelemetryRecorder(
            _provenance(),
            probe=SequenceProbe([]),
            max_samples=2.5,  # type: ignore[arg-type]
        )


def test_recorder_state_contract_prevents_partial_artifact_claims() -> None:
    recorder = UniformResourceTelemetryRecorder(
        _provenance(),
        probe=SequenceProbe([]),
    )
    with pytest.raises(ResourceTelemetryStateError, match="before successful finish"):
        _ = recorder.artifact
    with pytest.raises(ResourceTelemetryStateError, match="requires a running"):
        recorder.finish()


def test_artifact_serialization_is_bounded_canonical_and_content_addressed() -> None:
    artifact = _artifact()
    payload = serialize_resource_telemetry_artifact(artifact)

    assert len(payload) < RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES
    assert payload.endswith(b"\n")
    assert b"test-start-token-42" not in payload
    assert deserialize_resource_telemetry_artifact(payload) == artifact

    with pytest.raises(ValueError, match="canonical JSON"):
        deserialize_resource_telemetry_artifact(payload.rstrip(b"\n"))

    tampered = json.loads(payload)
    tampered["workload_elapsed_monotonic_seconds"] = 999.0
    with pytest.raises(ValidationError, match="inclusive instrumented interval"):
        ResourceTelemetryArtifact.model_validate_json(json.dumps(tampered))

    with pytest.raises(ValueError, match="empty or oversized"):
        deserialize_resource_telemetry_artifact(
            b"x" * (RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES + 1)
        )

    forged_runtime = artifact.provenance.runtime.model_copy(
        update={
            "target": artifact.provenance.runtime.target.model_copy(
                update={"root_process_id": 0}
            )
        }
    )
    forged = artifact.model_copy(
        update={
            "provenance": artifact.provenance.model_copy(
                update={"runtime": forged_runtime}
            )
        }
    )
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        serialize_resource_telemetry_artifact(forged)


def test_create_cold_validates_nested_content_before_content_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_runtime = _runtime().model_copy(
        update={"platform_system": "x" * RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES}
    )
    invalid_provenance = _provenance().model_copy(update={"runtime": invalid_runtime})
    reading = _measured(1)
    coverage = ResourceTelemetryMetricCoverage.create(
        attempted_samples=2,
        measured_samples=2,
    )

    def forbidden_hash(*args: object, **kwargs: object) -> str:
        raise AssertionError("content hash must not run for oversized input")

    monkeypatch.setattr(telemetry_module, "content_id", forbidden_hash)
    with pytest.raises(ValidationError, match="at most 200"):
        ResourceTelemetryArtifact.create(
            provenance=invalid_provenance,
            execution_status="completed",
            failure_code=None,
            clock_source="test_clock",
            sample_count=2,
            workload_elapsed_monotonic_seconds=1.0,
            instrumented_interval_monotonic_seconds=1.0,
            sampling_overhead_monotonic_seconds=0.1,
            process_rss_start_bytes=reading,
            process_rss_end_bytes=reading,
            process_rss_peak_sampled_bytes=reading,
            process_memory_coverage=coverage,
            system_ram_total_bytes=reading,
            system_ram_available_min_bytes=reading,
            system_availability_coverage=coverage,
            system_capacity_coverage=coverage,
            cuda_vram_start_bytes=reading,
            cuda_vram_end_bytes=reading,
            cuda_vram_peak_sampled_bytes=reading,
            cuda_vram_total_bytes=reading,
            cuda_usage_coverage=coverage,
            cuda_capacity_coverage=coverage,
        )


def test_system_probe_selects_cuda_only_by_exact_uuid_and_bus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                "GPU-11111111-2222-3333-4444-555555555555, "
                "00000000:02:00.0, 5, 24576\n"
                f"{GPU_UUID}, {GPU_BUS}, 123, 32768\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(telemetry_module, "_run_bounded_command", fake_runner)

    probe = SystemResourceTelemetryProbe(
        target=_target(process_scope="process_tree"),
        cuda_device=_cuda_identity(),
        process_memory_reader=lambda target: _measured(
            50,
            f"test_{target.process_scope}",
            subject_id=target.measurement_subject_id,
        ),
        nvidia_smi_executable=Path(sys.executable).resolve(),
    )
    snapshot = probe.snapshot()
    assert snapshot.cuda_vram_used_bytes.value_bytes == 123 * 1024 * 1024
    assert snapshot.cuda_vram_total_bytes.value_bytes == 32768 * 1024 * 1024
    assert snapshot.cuda_vram_used_bytes.source == "nvidia_smi_exact_gpu_uuid"
    assert "uuid,pci.bus_id" in calls[0][1]
    assert snapshot.process_scope_rss_bytes.value_bytes == 50


def test_system_probe_never_falls_back_on_uuid_or_bus_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"{GPU_UUID}, 00000000:03:00.0, 123, 32768\n",
            stderr="",
        )

    monkeypatch.setattr(telemetry_module, "_run_bounded_command", fake_runner)

    snapshot = SystemResourceTelemetryProbe(
        target=_target(),
        cuda_device=_cuda_identity(),
        process_memory_reader=lambda target: _measured(50),
        nvidia_smi_executable=Path(sys.executable).resolve(),
    ).snapshot()
    assert snapshot.cuda_vram_used_bytes.status == "unavailable"
    assert snapshot.cuda_vram_used_bytes.value_bytes is None
    assert snapshot.cuda_vram_used_bytes.unavailable_reason == (
        "cuda_vram_probe_unavailable"
    )


def test_nvidia_smi_output_and_rows_are_bounded_before_parsing() -> None:
    oversized = "x" * (RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES + 1)
    with pytest.raises(ValueError, match="empty or oversized"):
        telemetry_module._parse_nvidia_smi_rows(oversized)

    row = f"{GPU_UUID}, {GPU_BUS}, 1, 2\n"
    too_many_rows = row * (telemetry_module.RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_ROWS + 1)
    with pytest.raises(ValueError, match="row count"):
        telemetry_module._parse_nvidia_smi_rows(too_many_rows)


def test_command_output_is_hard_bounded_while_the_child_is_running() -> None:
    command = [
        str(Path(sys.executable).resolve()),
        "-c",
        (
            "import os\n"
            "chunk = b'x' * 8192\n"
            "for _ in range(1024):\n"
            "    os.write(1, chunk)\n"
        ),
    ]
    started = time.perf_counter()
    with pytest.raises(ValueError, match="output exceeded its byte limit"):
        telemetry_module._run_bounded_command(
            command,
            timeout_seconds=2.0,
            output_limit_bytes=1024,
        )
    assert time.perf_counter() - started < 1.5


@pytest.mark.parametrize("failure_index", (0, 1))
@pytest.mark.parametrize("start_side_effect", (False, True))
def test_bounded_command_reader_start_failure_closes_every_owned_resource(
    failure_index: int,
    start_side_effect: bool,
    tmp_path: Path,
) -> None:
    marker = tmp_path / (
        f"reader-start-failure-{failure_index}-{int(start_side_effect)}.txt"
    )
    command = [
        str(Path(sys.executable).resolve()),
        "-c",
        (
            "import pathlib, time\n"
            "time.sleep(5)\n"
            f"pathlib.Path({str(marker)!r}).write_text('escaped', encoding='utf-8')\n"
        ),
    ]
    processes: list[subprocess.Popen[bytes]] = []

    def popen_factory(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(*args, **kwargs)  # type: ignore[arg-type]
        processes.append(process)
        return process

    real_thread_factory = threading.Thread

    class ThreadProxy:
        def __init__(self, index: int, **kwargs: object) -> None:
            self.index = index
            self.thread = real_thread_factory(**kwargs)  # type: ignore[arg-type]
            self.start_succeeded = False
            self.join_calls = 0

        def start(self) -> None:
            if self.index == failure_index:
                if start_side_effect:
                    self.thread.start()
                    self.start_succeeded = True
                raise RuntimeError("secret thread-start detail")
            self.thread.start()
            self.start_succeeded = True

        def join(self, timeout: float | None = None) -> None:
            self.join_calls += 1
            self.thread.join(timeout=timeout)

        def is_alive(self) -> bool:
            return self.thread.is_alive()

    proxies: list[ThreadProxy] = []

    def thread_factory(**kwargs: object) -> ThreadProxy:
        proxy = ThreadProxy(len(proxies), **kwargs)
        proxies.append(proxy)
        return proxy

    with pytest.raises(
        RuntimeError,
        match="output readers could not start",
    ) as error:
        telemetry_module._run_bounded_command(
            command,
            timeout_seconds=1.0,
            output_limit_bytes=1024,
            _popen_factory=popen_factory,
            _thread_factory=thread_factory,  # type: ignore[arg-type]
        )

    assert "secret" not in str(error.value)
    assert len(processes) == 1
    process = processes[0]
    assert process.poll() is not None
    assert process.stdout is not None and process.stdout.closed
    assert process.stderr is not None and process.stderr.closed
    assert len(proxies) == 2
    assert all(not proxy.is_alive() for proxy in proxies)
    assert proxies[failure_index].start_succeeded is start_side_effect
    assert (proxies[failure_index].join_calls >= 1) is start_side_effect
    if failure_index == 1:
        assert proxies[0].start_succeeded is True
        assert proxies[0].join_calls >= 1
    assert not marker.exists()


def test_bounded_command_sanitizes_popen_failure() -> None:
    def failing_popen(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OSError("secret spawn detail")

    with pytest.raises(RuntimeError, match="could not start") as error:
        telemetry_module._run_bounded_command(
            [str(Path(sys.executable).resolve()), "-c", "pass"],
            _popen_factory=failing_popen,  # type: ignore[arg-type]
        )
    assert "secret" not in str(error.value)


def test_bounded_command_timeout_reaps_child_and_closes_pipes() -> None:
    processes: list[subprocess.Popen[bytes]] = []

    def popen_factory(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(*args, **kwargs)  # type: ignore[arg-type]
        processes.append(process)
        return process

    with pytest.raises(TimeoutError, match="wall-time limit"):
        telemetry_module._run_bounded_command(
            [str(Path(sys.executable).resolve()), "-c", "import time; time.sleep(5)"],
            timeout_seconds=0.02,
            output_limit_bytes=1024,
            _popen_factory=popen_factory,
        )
    assert len(processes) == 1
    process = processes[0]
    assert process.poll() is not None
    assert process.stdout is not None and process.stdout.closed
    assert process.stderr is not None and process.stderr.closed


def test_system_probe_rejects_forged_reader_and_oversized_command_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forged_reading = _measured(50).model_copy(update={"value_bytes": -1})

    def huge_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="x" * (RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES + 1),
            stderr="",
        )

    monkeypatch.setattr(telemetry_module, "_run_bounded_command", huge_runner)

    snapshot = SystemResourceTelemetryProbe(
        target=_target(),
        cuda_device=_cuda_identity(),
        process_memory_reader=lambda target: forged_reading,
        nvidia_smi_executable=Path(sys.executable).resolve(),
    ).snapshot()
    assert snapshot.process_scope_rss_bytes.unavailable_reason == (
        "invalid_process_memory_result"
    )
    assert snapshot.cuda_vram_used_bytes.unavailable_reason == (
        "cuda_vram_probe_unavailable"
    )


def test_unresolved_cuda_identity_never_invokes_nvidia_smi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_runner(*args: object, **kwargs: object) -> object:
        raise AssertionError("nvidia-smi must not run without exact CUDA identity")

    monkeypatch.setattr(telemetry_module, "_run_bounded_command", forbidden_runner)

    snapshot = SystemResourceTelemetryProbe(
        target=_target(),
        cuda_device=ResourceTelemetryCudaDeviceIdentity.unavailable(
            logical_device_index=0,
            reason="mig_identity_unsupported",
        ),
        process_memory_reader=lambda target: _measured(50),
    ).snapshot()
    assert snapshot.cuda_vram_used_bytes.unavailable_reason == (
        "cuda_identity_unavailable"
    )


def test_process_tree_scope_requires_explicit_reader() -> None:
    snapshot = SystemResourceTelemetryProbe(
        target=_target(process_scope="process_tree"),
        cuda_device=ResourceTelemetryCudaDeviceIdentity.unavailable(
            logical_device_index=0,
            reason="not_needed",
        ),
    ).snapshot()
    assert snapshot.process_scope_rss_bytes.unavailable_reason == (
        "process_tree_probe_not_configured"
    )


def test_background_sampler_poll_and_stop_do_not_wait_for_probe() -> None:
    entered = threading.Event()
    release = threading.Event()
    exited = threading.Event()

    class BlockingProbe:
        def snapshot(self) -> ResourceTelemetrySnapshot:
            entered.set()
            release.wait(timeout=2.0)
            try:
                return _snapshot(rss=100, ram_available=800, cuda_used=20)
            finally:
                exited.set()

    sampler = BackgroundResourceTelemetrySampler(
        BlockingProbe(),
        cadence_seconds=0.01,
        join_timeout_seconds=0.01,
    )
    sampler.start()
    assert entered.wait(timeout=1.0)

    started = time.perf_counter()
    assert sampler.poll().state == "running"
    assert sampler.request_stop().state == "stop_requested"
    assert time.perf_counter() - started < 0.25

    started = time.perf_counter()
    result = sampler.finish()
    assert time.perf_counter() - started < 0.25
    assert result.status.state == "join_timed_out"
    assert result.samples == ()
    release.set()
    assert exited.wait(timeout=1.0)
    assert sampler.poll().state == "join_timed_out"
    with pytest.raises(ResourceTelemetryStateError, match="only finish once"):
        sampler.finish()


def test_background_sampler_stop_state_cannot_regress_during_inflight_probe() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingProbe:
        def snapshot(self) -> ResourceTelemetrySnapshot:
            entered.set()
            assert release.wait(timeout=1.0)
            return _snapshot(rss=100, ram_available=800, cuda_used=20)

    sampler = BackgroundResourceTelemetrySampler(
        BlockingProbe(),
        cadence_seconds=0.01,
        join_timeout_seconds=0.5,
    )
    sampler.start()
    assert entered.wait(timeout=1.0)
    assert sampler.request_stop().state == "stop_requested"
    release.set()
    result = sampler.finish()

    assert result.status.state == "finished"
    assert result.status.sample_count == 1
    assert len(result.samples) == 1
    assert sampler.request_stop().state == "finished"


def test_background_sampler_skips_missed_cadence_slots_without_bursting() -> None:
    all_samples = threading.Event()

    class DelayedFirstProbe:
        def __init__(self) -> None:
            self.starts: list[float] = []

        def snapshot(self) -> ResourceTelemetrySnapshot:
            self.starts.append(time.monotonic())
            if len(self.starts) == 1:
                time.sleep(0.08)
            if len(self.starts) >= 4:
                all_samples.set()
            return _snapshot(rss=100, ram_available=800, cuda_used=20)

    probe = DelayedFirstProbe()
    sampler = BackgroundResourceTelemetrySampler(
        probe,
        cadence_seconds=0.03,
        max_samples=4,
        join_timeout_seconds=0.5,
    )
    sampler.start()
    assert all_samples.wait(timeout=1.0)
    result = sampler.finish()

    assert len(result.samples) == 4
    post_delay_intervals = [
        later - earlier
        for earlier, later in zip(probe.starts[1:-1], probe.starts[2:], strict=True)
    ]
    assert post_delay_intervals
    assert min(post_delay_intervals) >= 0.02


def test_background_sampler_has_one_probe_owner_and_bounded_result() -> None:
    two_samples = threading.Event()

    class ThreadRecordingProbe:
        def __init__(self) -> None:
            self.thread_ids: list[int] = []

        def snapshot(self) -> ResourceTelemetrySnapshot:
            self.thread_ids.append(threading.get_ident())
            if len(self.thread_ids) >= 2:
                two_samples.set()
            return _snapshot(rss=100, ram_available=800, cuda_used=20)

    probe = ThreadRecordingProbe()
    sampler = BackgroundResourceTelemetrySampler(
        probe,
        cadence_seconds=0.001,
        max_samples=4,
        join_timeout_seconds=0.5,
    )
    sampler.start()
    assert two_samples.wait(timeout=1.0)
    result = sampler.finish()

    assert result.status.state in {"finished", "sample_limit_reached"}
    assert 2 <= len(result.samples) <= 4
    assert len(set(probe.thread_ids)) == 1
    assert probe.thread_ids[0] != threading.get_ident()
    assert result.sampling_overhead_monotonic_ns >= 0


@pytest.mark.skipif(
    not (os.name == "nt" or os.path.exists("/proc/self/stat")),
    reason="PID start tokens are supported only on Windows and Linux",
)
def test_runtime_capture_binds_current_pid_start_token_and_actual_rss() -> None:
    target = capture_resource_telemetry_process_target(
        os.getpid(),
        process_scope="target_root_process",
    )
    runtime = ResourceTelemetryRuntimeIdentity.capture(
        target_root_process_id=target.root_process_id,
    )
    assert runtime.collector_process_id == os.getpid()
    assert runtime.target == target
    assert "python_executable_path_hash" in type(runtime).model_fields
    assert "python_executable_hash" not in type(runtime).model_fields
    assert (
        runtime.python_executable_path_hash
        == hashlib.sha256(
            str(Path(sys.executable).resolve()).encode("utf-8")
        ).hexdigest()
    )
    raw_start_token = telemetry_module._capture_process_start_token(os.getpid())
    assert (
        target.root_process_start_token_hash
        == hashlib.sha256(raw_start_token.encode("utf-8")).hexdigest()
    )

    snapshot = SystemResourceTelemetryProbe(
        target=target,
        cuda_device=runtime.cuda_device,
    ).snapshot()
    assert snapshot.process_scope_rss_bytes.status == "measured"
    assert (snapshot.process_scope_rss_bytes.value_bytes or 0) > 0


def test_runtime_capture_validates_and_rechecks_supplied_start_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_token = "windows-filetime-123456789"
    calls: list[int] = []

    def fake_capture(process_id: int) -> str:
        calls.append(process_id)
        return live_token

    monkeypatch.setattr(
        telemetry_module,
        "_capture_process_start_token",
        fake_capture,
    )
    runtime = ResourceTelemetryRuntimeIdentity.capture(
        target_root_process_id=42,
        target_root_process_start_token=live_token,
    )
    assert calls == [42]
    assert (
        runtime.target.root_process_start_token_hash
        == hashlib.sha256(live_token.encode("utf-8")).hexdigest()
    )

    with pytest.raises(ValueError, match="differs from the live process"):
        ResourceTelemetryRuntimeIdentity.capture(
            target_root_process_id=42,
            target_root_process_start_token="windows-filetime-987654321",
        )

    maximum_token = "x" * 512
    monkeypatch.setattr(
        telemetry_module,
        "_capture_process_start_token",
        lambda process_id: maximum_token,
    )
    maximum = ResourceTelemetryRuntimeIdentity.capture(
        target_root_process_id=42,
        target_root_process_start_token=maximum_token,
    )
    assert (
        maximum.target.root_process_start_token_hash
        == hashlib.sha256(maximum_token.encode("utf-8")).hexdigest()
    )


@pytest.mark.parametrize(
    "invalid_token",
    (
        "",
        "contains space",
        "contains/slash",
        "contains\x00nul",
        "žeton",
        "x" * 513,
        b"bytes-token",
        123,
    ),
)
def test_runtime_capture_rejects_unbounded_or_unsafe_supplied_start_token(
    invalid_token: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_capture(process_id: int) -> str:
        del process_id
        raise AssertionError("Invalid supplied tokens must fail before OS capture")

    monkeypatch.setattr(
        telemetry_module,
        "_capture_process_start_token",
        forbidden_capture,
    )
    with pytest.raises(ValueError, match="bounded safe label"):
        ResourceTelemetryRuntimeIdentity.capture(
            target_root_process_id=42,
            target_root_process_start_token=invalid_token,  # type: ignore[arg-type]
        )


def test_runtime_capture_rejects_unsafe_live_os_start_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        telemetry_module,
        "_capture_process_start_token",
        lambda process_id: "unsafe live token",
    )
    with pytest.raises(ValueError, match="bounded safe label"):
        ResourceTelemetryRuntimeIdentity.capture(target_root_process_id=42)


@pytest.mark.skipif(
    not (os.name == "nt" or os.path.exists("/proc/self/stat")),
    reason="PID start tokens are supported only on Windows and Linux",
)
def test_default_target_probe_rejects_pid_start_token_mismatch() -> None:
    target = capture_resource_telemetry_process_target(
        os.getpid(),
        process_scope="target_root_process",
    ).model_copy(update={"root_process_start_token_hash": "0" * 64})
    snapshot = SystemResourceTelemetryProbe(
        target=target,
        cuda_device=ResourceTelemetryCudaDeviceIdentity.unavailable(
            logical_device_index=0,
            reason="not_needed",
        ),
    ).snapshot()
    assert snapshot.process_scope_rss_bytes.unavailable_reason == (
        "target_process_identity_changed"
    )
