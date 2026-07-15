"""Uniform, model-free resource telemetry for semantic benchmark arms.

The collector is owned by the parent benchmark process. It records bounded,
content-addressed summaries while keeping unavailable and partially sampled
measurements explicit. GPU readings are accepted only for an exact UUID and
PCI-bus identity; process readings are bound to a PID plus a start token so PID
reuse cannot silently redirect a measurement.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import ctypes
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Annotated, Literal, Protocol, Self, TypeVar

from pydantic import ConfigDict, Field, TypeAdapter, model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
)


RESOURCE_TELEMETRY_COLLECTOR_REVISION = "uniform-resource-telemetry-v1"
RESOURCE_TELEMETRY_MAX_SAMPLES = 4096
RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES = 128 * 1024
RESOURCE_TELEMETRY_MAX_SOURCE_ARTIFACTS = 256
RESOURCE_TELEMETRY_PROBE_REVISION = "system-resource-probe-v2"
RESOURCE_TELEMETRY_SAMPLING_POLICY = "caller-driven-bounded-v1"
RESOURCE_TELEMETRY_DEFAULT_CADENCE_SECONDS = 0.25
RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS = 60.0
RESOURCE_TELEMETRY_BACKGROUND_JOIN_MAX_SECONDS = 5.0
RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES = 64 * 1024
RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_ROWS = 128
RESOURCE_TELEMETRY_NVIDIA_SMI_TIMEOUT_SECONDS = 2.0
_RESOURCE_TELEMETRY_COMMAND_DRAIN_JOIN_SECONDS = 0.5
_STRICT_ADAPTER_CONFIG = ConfigDict(strict=True, allow_inf_nan=False)
_SAFE_PROCESS_START_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,511}$")
_NON_EMPTY_ID_ADAPTER = TypeAdapter(
    NonEmptyId,
    config=_STRICT_ADAPTER_CONFIG,
)
_ModelT = TypeVar("_ModelT", bound=FrozenModel)


def _cold_validate_exact(
    model_type: type[_ModelT],
    value: _ModelT,
    *,
    label: str,
) -> _ModelT:
    """Re-run validation for nested frozen instances and reject normalization.

    Pydantic intentionally trusts an already-constructed model instance by
    default.  That is unsafe at an artifact boundary because ``model_copy`` and
    ``model_construct`` can bypass validators.  Round-tripping through plain
    Python data forces every field and nested validator to run again.  Exact
    equality also rejects a forged instance that only becomes valid after
    whitespace or other normalization.
    """

    if not isinstance(value, model_type):
        raise TypeError(f"{label} must be a {model_type.__name__}")
    original = value.model_dump(mode="python", round_trip=True)
    validated = model_type.model_validate(original)
    if validated.model_dump(mode="python", round_trip=True) != original:
        raise ValueError(f"{label} is not in canonical validated form")
    return validated


def _validate_process_start_token(value: str) -> str:
    """Require the same bounded safe token contract at every capture boundary."""

    if (
        type(value) is not str
        or not value
        or "\x00" in value
        or len(value.encode("utf-8")) > 512
        or _SAFE_PROCESS_START_TOKEN.fullmatch(value) is None
    ):
        raise ValueError("Target process start token is not a bounded safe label")
    return value


def _run_bounded_command(
    command: Sequence[str],
    *,
    timeout_seconds: float = RESOURCE_TELEMETRY_NVIDIA_SMI_TIMEOUT_SECONDS,
    output_limit_bytes: int = RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES,
    _popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    _thread_factory: Callable[..., threading.Thread] = threading.Thread,
) -> subprocess.CompletedProcess[str]:
    """Run one trusted command while retaining at most a fixed output prefix.

    ``subprocess.run(capture_output=True)`` buffers both streams without a hard
    limit.  This helper instead drains OS pipes concurrently, stores at most
    ``limit + 1`` bytes per stream, and kills the child as soon as a reader
    observes a breach.  Reader threads continue draining discarded bytes until
    termination so the child cannot deadlock on a full pipe.
    """

    if (
        isinstance(command, (str, bytes))
        or not isinstance(command, Sequence)
        or not command
        or any(
            not isinstance(argument, str) or not argument or "\x00" in argument
            for argument in command
        )
    ):
        raise ValueError("Bounded command requires non-empty NUL-free arguments")
    executable = Path(command[0])
    if not executable.is_absolute():
        raise ValueError("Bounded command executable must be absolute")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not 0.0 < float(timeout_seconds) <= 60.0
    ):
        raise ValueError("Bounded command timeout is invalid")
    if (
        isinstance(output_limit_bytes, bool)
        or not isinstance(output_limit_bytes, int)
        or not 1 <= output_limit_bytes <= RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES
    ):
        raise ValueError("Bounded command output limit is invalid")

    if not callable(_popen_factory) or not callable(_thread_factory):
        raise TypeError("Bounded command factories must be callable")

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = _popen_factory(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
            creationflags=creationflags,
        )
    except Exception as exc:
        raise RuntimeError("Bounded command could not start") from exc

    stdout_pipe = getattr(process, "stdout", None)
    stderr_pipe = getattr(process, "stderr", None)
    deadline = time.monotonic() + float(timeout_seconds)

    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    output_exceeded = threading.Event()
    reader_failed = threading.Event()
    abort_requested = threading.Event()

    def drain(pipe: object, buffer: bytearray) -> None:
        try:
            read = getattr(pipe, "read")
            while True:
                chunk = read(8192)
                if not chunk:
                    return
                if not isinstance(chunk, bytes):
                    raise TypeError("Bounded command pipe returned non-bytes")
                retained_capacity = max(
                    0,
                    output_limit_bytes + 1 - len(buffer),
                )
                if retained_capacity:
                    buffer.extend(chunk[:retained_capacity])
                if len(chunk) > retained_capacity or len(buffer) > output_limit_bytes:
                    output_exceeded.set()
                    abort_requested.set()
        except Exception:
            reader_failed.set()
            abort_requested.set()

    reader_threads: list[threading.Thread] = []
    started_reader_threads: list[threading.Thread] = []
    reader_setup_failed = False
    timed_out = False
    forced_termination = False
    return_code: int | None = None
    primary_error: Exception | None = None
    cleanup_failed = False

    try:
        if stdout_pipe is None or stderr_pipe is None:
            raise RuntimeError("Bounded command pipes are unavailable")
        try:
            reader_threads = [
                _thread_factory(
                    target=drain,
                    args=(stdout_pipe, stdout_buffer),
                    name="rei-resource-command-stdout",
                    daemon=True,
                ),
                _thread_factory(
                    target=drain,
                    args=(stderr_pipe, stderr_buffer),
                    name="rei-resource-command-stderr",
                    daemon=True,
                ),
            ]
        except Exception as exc:
            reader_setup_failed = True
            raise RuntimeError(
                "Bounded command output readers could not start"
            ) from exc
        for thread in reader_threads:
            try:
                thread.start()
            except Exception as exc:
                reader_setup_failed = True
                # A custom/runtime Thread.start can fail after the OS thread was
                # created.  Track that ambiguous side effect conservatively so
                # cleanup closes its pipe and proves the reader has exited.
                try:
                    if thread.is_alive():
                        started_reader_threads.append(thread)
                except Exception:
                    started_reader_threads.append(thread)
                raise RuntimeError(
                    "Bounded command output readers could not start"
                ) from exc
            started_reader_threads.append(thread)

        while process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                timed_out = True
                forced_termination = True
                break
            if abort_requested.wait(timeout=min(0.01, remaining)):
                forced_termination = True
                break
        if forced_termination and process.poll() is None:
            process.kill()
        try:
            return_code = process.wait(
                timeout=_RESOURCE_TELEMETRY_COMMAND_DRAIN_JOIN_SECONDS
            )
        except subprocess.TimeoutExpired as exc:
            try:
                process.kill()
            finally:
                process.wait(timeout=_RESOURCE_TELEMETRY_COMMAND_DRAIN_JOIN_SECONDS)
            raise RuntimeError("Bounded command did not terminate after kill") from exc
    except (TimeoutError, ValueError, RuntimeError) as exc:
        primary_error = exc
    except Exception:
        primary_error = RuntimeError("Bounded command execution failed")
    finally:
        # Every path after a successful Popen owns the child until a bounded
        # reap, closes both pipes, and joins readers whose start returned or
        # whose failed start reported that it created a live thread.
        try:
            process_running = process.poll() is None
        except Exception:
            process_running = True
            cleanup_failed = True
        if process_running:
            try:
                process.kill()
            except Exception:
                cleanup_failed = True
        try:
            process.wait(timeout=_RESOURCE_TELEMETRY_COMMAND_DRAIN_JOIN_SECONDS)
        except Exception:
            cleanup_failed = True

        pipes = (stdout_pipe, stderr_pipe)

        def close_pipe(pipe: object | None) -> None:
            nonlocal cleanup_failed
            if pipe is None:
                return
            try:
                getattr(pipe, "close")()
            except Exception:
                cleanup_failed = True

        if reader_setup_failed:
            for pipe in pipes:
                close_pipe(pipe)
        else:
            for thread in started_reader_threads:
                try:
                    thread.join(timeout=_RESOURCE_TELEMETRY_COMMAND_DRAIN_JOIN_SECONDS)
                except Exception:
                    cleanup_failed = True
            for index, thread in enumerate(reader_threads):
                pipe = pipes[index]
                try:
                    reader_alive = (
                        thread in started_reader_threads and thread.is_alive()
                    )
                except Exception:
                    reader_alive = True
                    cleanup_failed = True
                if reader_alive:
                    close_pipe(pipe)

        for thread in started_reader_threads:
            try:
                thread.join(timeout=_RESOURCE_TELEMETRY_COMMAND_DRAIN_JOIN_SECONDS)
                if thread.is_alive():
                    cleanup_failed = True
            except Exception:
                cleanup_failed = True
        for pipe in pipes:
            close_pipe(pipe)

    if cleanup_failed:
        raise RuntimeError("Bounded command cleanup failed") from primary_error
    if primary_error is not None:
        raise primary_error
    if return_code is None:
        raise RuntimeError("Bounded command returned no exit status")
    if timed_out:
        raise TimeoutError("Bounded command exceeded its wall-time limit")
    if output_exceeded.is_set():
        raise ValueError("Bounded command output exceeded its byte limit")
    if reader_failed.is_set():
        raise RuntimeError("Bounded command output reader failed")
    try:
        stdout = bytes(stdout_buffer).decode("ascii")
        stderr = bytes(stderr_buffer).decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("Bounded command output must be ASCII") from exc
    return subprocess.CompletedProcess(
        args=list(command),
        returncode=return_code,
        stdout=stdout,
        stderr=stderr,
    )


ResourceTelemetryWorkload = Literal[
    "racio_interpreter",
    "emocio_renderer",
    "vlm_interpreter",
    "semantic_motif",
]
ResourceTelemetryExecutionStatus = Literal["completed", "failed"]
ResourceTelemetryCoverageStatus = Literal["complete", "partial", "unavailable"]
ResourceTelemetryProcessScope = Literal["target_root_process", "process_tree"]
ResourceTelemetryMeasurementScope = Literal[
    "process_scope_rss",
    "system_physical_memory",
    "cuda_device_memory",
]
_EXECUTION_STATUS_ADAPTER = TypeAdapter(
    ResourceTelemetryExecutionStatus,
    config=_STRICT_ADAPTER_CONFIG,
)
_SAMPLE_COUNT_ADAPTER = TypeAdapter(
    Annotated[int, Field(ge=2, le=RESOURCE_TELEMETRY_MAX_SAMPLES)],
    config=_STRICT_ADAPTER_CONFIG,
)
_NON_NEGATIVE_SECONDS_ADAPTER = TypeAdapter(
    Annotated[float, Field(ge=0.0, allow_inf_nan=False)],
    config=_STRICT_ADAPTER_CONFIG,
)
_CADENCE_SECONDS_ADAPTER = TypeAdapter(
    Annotated[
        float,
        Field(
            gt=0.0,
            le=RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS,
            allow_inf_nan=False,
        ),
    ],
    config=_STRICT_ADAPTER_CONFIG,
)


class ResourceByteReading(FrozenModel):
    """One byte-valued reading with explicit availability and probe identity."""

    status: Literal["measured", "unavailable"]
    value_bytes: int | None = Field(default=None, ge=0)
    source: NonEmptyId | None = None
    measurement_scope: ResourceTelemetryMeasurementScope | None = None
    subject_id: NonEmptyId | None = None
    unavailable_reason: NonEmptyId | None = None

    @classmethod
    def measured(
        cls,
        value_bytes: int,
        *,
        source: str,
        measurement_scope: ResourceTelemetryMeasurementScope,
        subject_id: str,
    ) -> "ResourceByteReading":
        return cls(
            status="measured",
            value_bytes=value_bytes,
            source=source,
            measurement_scope=measurement_scope,
            subject_id=subject_id,
        )

    @classmethod
    def unavailable(cls, reason: str) -> "ResourceByteReading":
        return cls(status="unavailable", unavailable_reason=reason)

    @model_validator(mode="after")
    def validate_disposition(self) -> Self:
        if self.status == "measured":
            if (
                self.value_bytes is None
                or self.source is None
                or self.measurement_scope is None
                or self.subject_id is None
            ):
                raise ValueError(
                    "Measured resource readings require value, source, scope, and subject"
                )
            if self.unavailable_reason is not None:
                raise ValueError("Measured resource readings cannot claim unavailable")
        elif (
            self.value_bytes is not None
            or self.source is not None
            or self.measurement_scope is not None
            or self.subject_id is not None
            or self.unavailable_reason is None
        ):
            raise ValueError(
                "Unavailable resource readings require only an explicit reason"
            )
        return self


class ResourceTelemetryCudaDeviceIdentity(FrozenModel):
    """Logical CUDA ordinal bound to one stable physical NVIDIA identity."""

    status: Literal["resolved", "unavailable"]
    logical_device_index: int = Field(ge=0, le=1023)
    physical_gpu_uuid: NonEmptyId | None = None
    pci_bus_id: NonEmptyId | None = None
    unavailable_reason: NonEmptyId | None = None

    @classmethod
    def resolved(
        cls,
        *,
        logical_device_index: int,
        physical_gpu_uuid: str,
        pci_bus_id: str,
    ) -> "ResourceTelemetryCudaDeviceIdentity":
        return cls(
            status="resolved",
            logical_device_index=logical_device_index,
            physical_gpu_uuid=physical_gpu_uuid,
            pci_bus_id=pci_bus_id,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        logical_device_index: int,
        reason: str,
    ) -> "ResourceTelemetryCudaDeviceIdentity":
        return cls(
            status="unavailable",
            logical_device_index=logical_device_index,
            unavailable_reason=reason,
        )

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.status == "resolved":
            if (
                self.physical_gpu_uuid is None
                or self.pci_bus_id is None
                or self.unavailable_reason is not None
            ):
                raise ValueError(
                    "Resolved CUDA identity requires only UUID and PCI bus ID"
                )
            if (
                re.fullmatch(
                    r"GPU-[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}",
                    self.physical_gpu_uuid,
                )
                is None
            ):
                raise ValueError("Resolved CUDA identity requires a physical GPU UUID")
            if (
                re.fullmatch(
                    r"(?:[0-9A-Fa-f]{8}:)?[0-9A-Fa-f]{2}:"
                    r"[0-9A-Fa-f]{2}\.[0-7]",
                    self.pci_bus_id,
                )
                is None
            ):
                raise ValueError("Resolved CUDA identity requires a PCI bus ID")
        elif (
            self.physical_gpu_uuid is not None
            or self.pci_bus_id is not None
            or self.unavailable_reason is None
        ):
            raise ValueError(
                "Unavailable CUDA identity requires only an explicit reason"
            )
        return self

    @property
    def measurement_subject_id(self) -> str | None:
        if self.status != "resolved":
            return None
        return content_id(
            "cuda_device",
            {
                "logical_device_index": self.logical_device_index,
                "physical_gpu_uuid": self.physical_gpu_uuid,
                "pci_bus_id": self.pci_bus_id,
            },
        )


class ResourceTelemetryProcessTarget(FrozenModel):
    """PID-reuse-safe identity for the root of a measured process scope."""

    root_process_id: int = Field(ge=1, le=4_294_967_295)
    root_process_start_token_hash: HashDigest
    process_scope: ResourceTelemetryProcessScope

    @property
    def measurement_subject_id(self) -> str:
        return content_id(
            "process_memory_subject",
            self.model_dump(mode="python", round_trip=True),
        )


class ResourceTelemetrySnapshot(FrozenModel):
    """One synchronous sample; missing dimensions are never inferred as zero."""

    process_scope_rss_bytes: ResourceByteReading
    system_ram_total_bytes: ResourceByteReading
    system_ram_available_bytes: ResourceByteReading
    cuda_vram_used_bytes: ResourceByteReading
    cuda_vram_total_bytes: ResourceByteReading

    @classmethod
    def unavailable(cls, reason: str) -> "ResourceTelemetrySnapshot":
        reading = ResourceByteReading.unavailable(reason)
        return cls(
            process_scope_rss_bytes=reading,
            system_ram_total_bytes=reading,
            system_ram_available_bytes=reading,
            cuda_vram_used_bytes=reading,
            cuda_vram_total_bytes=reading,
        )

    @model_validator(mode="after")
    def validate_physical_bounds(self) -> Self:
        for field_name in (
            "process_scope_rss_bytes",
            "system_ram_total_bytes",
            "system_ram_available_bytes",
            "cuda_vram_used_bytes",
            "cuda_vram_total_bytes",
        ):
            _cold_validate_exact(
                ResourceByteReading,
                getattr(self, field_name),
                label=f"Telemetry snapshot {field_name}",
            )
        expected_scopes = {
            "process_scope_rss_bytes": "process_scope_rss",
            "system_ram_total_bytes": "system_physical_memory",
            "system_ram_available_bytes": "system_physical_memory",
            "cuda_vram_used_bytes": "cuda_device_memory",
            "cuda_vram_total_bytes": "cuda_device_memory",
        }
        for field_name, expected_scope in expected_scopes.items():
            reading = getattr(self, field_name)
            if (
                reading.status == "measured"
                and reading.measurement_scope != expected_scope
            ):
                raise ValueError(
                    f"Telemetry snapshot {field_name} has the wrong measurement scope"
                )
        for first, second, label in (
            (
                self.system_ram_total_bytes,
                self.system_ram_available_bytes,
                "System memory",
            ),
            (
                self.cuda_vram_used_bytes,
                self.cuda_vram_total_bytes,
                "CUDA memory",
            ),
        ):
            if (
                first.status == "measured"
                and second.status == "measured"
                and (
                    first.source != second.source
                    or first.subject_id != second.subject_id
                )
            ):
                raise ValueError(
                    f"{label} readings have inconsistent measurement identity"
                )
        pairs = (
            (
                self.system_ram_available_bytes,
                self.system_ram_total_bytes,
                "Available system RAM cannot exceed total RAM",
            ),
            (
                self.cuda_vram_used_bytes,
                self.cuda_vram_total_bytes,
                "Used CUDA VRAM cannot exceed total VRAM",
            ),
        )
        for used, total, message in pairs:
            if (
                used.status == "measured"
                and total.status == "measured"
                and used.value_bytes is not None
                and total.value_bytes is not None
                and used.value_bytes > total.value_bytes
            ):
                raise ValueError(message)
        return self


class ResourceTelemetryProbe(Protocol):
    def snapshot(self) -> ResourceTelemetrySnapshot:
        """Return one typed sample without model or benchmark authority."""


class ResourceTelemetryRuntimeIdentity(FrozenModel):
    collector_revision: Literal["uniform-resource-telemetry-v1"] = (
        RESOURCE_TELEMETRY_COLLECTOR_REVISION
    )
    platform_system: NonEmptyId
    platform_release: NonEmptyId
    machine: NonEmptyId
    python_implementation: NonEmptyId
    python_version: NonEmptyId
    python_executable_path_hash: HashDigest
    collector_process_id: int = Field(ge=1, le=4_294_967_295)
    target: ResourceTelemetryProcessTarget
    cuda_device: ResourceTelemetryCudaDeviceIdentity

    @model_validator(mode="after")
    def validate_nested_identity(self) -> Self:
        _cold_validate_exact(
            ResourceTelemetryProcessTarget,
            self.target,
            label="Telemetry runtime process target",
        )
        _cold_validate_exact(
            ResourceTelemetryCudaDeviceIdentity,
            self.cuda_device,
            label="Telemetry runtime CUDA identity",
        )
        return self

    @property
    def system_memory_subject_id(self) -> str:
        return content_id(
            "system_memory_subject",
            {
                "platform_system": self.platform_system,
                "platform_release": self.platform_release,
                "machine": self.machine,
            },
        )

    @classmethod
    def capture(
        cls,
        *,
        target_root_process_id: int | None = None,
        target_root_process_start_token: str | None = None,
        process_scope: ResourceTelemetryProcessScope = "target_root_process",
        cuda_device: ResourceTelemetryCudaDeviceIdentity | None = None,
        cuda_logical_device_index: int = 0,
    ) -> "ResourceTelemetryRuntimeIdentity":
        def known(value: str) -> str:
            return value.strip() or "unknown"

        target_pid = (
            os.getpid() if target_root_process_id is None else target_root_process_id
        )
        supplied_start_token = (
            None
            if target_root_process_start_token is None
            else _validate_process_start_token(target_root_process_start_token)
        )
        live_start_token = _validate_process_start_token(
            _capture_process_start_token(target_pid)
        )
        if (
            supplied_start_token is not None
            and supplied_start_token != live_start_token
        ):
            raise ValueError(
                "Supplied target process start token differs from the live process"
            )
        return cls(
            platform_system=known(platform.system()),
            platform_release=known(platform.release()),
            machine=known(platform.machine()),
            python_implementation=known(platform.python_implementation()),
            python_version=known(platform.python_version()),
            python_executable_path_hash=hashlib.sha256(
                str(Path(sys.executable).resolve()).encode("utf-8")
            ).hexdigest(),
            collector_process_id=os.getpid(),
            target=ResourceTelemetryProcessTarget(
                root_process_id=target_pid,
                root_process_start_token_hash=hashlib.sha256(
                    live_start_token.encode("utf-8")
                ).hexdigest(),
                process_scope=process_scope,
            ),
            cuda_device=cuda_device
            or ResourceTelemetryCudaDeviceIdentity.unavailable(
                logical_device_index=cuda_logical_device_index,
                reason="cuda_identity_not_resolved",
            ),
        )


def _current_system_memory_subject_id() -> str:
    def known(value: str) -> str:
        return value.strip() or "unknown"

    return content_id(
        "system_memory_subject",
        {
            "platform_system": known(platform.system()),
            "platform_release": known(platform.release()),
            "machine": known(platform.machine()),
        },
    )


class ResourceTelemetryProvenance(FrozenModel):
    """Identity shared by C3, C4, VLM and semantic-motif telemetry arms."""

    benchmark_id: NonEmptyId
    run_id: NonEmptyId
    workload: ResourceTelemetryWorkload
    arm_id: NonEmptyId
    component_id: NonEmptyId
    source_artifact_ids: Annotated[
        tuple[NonEmptyId, ...],
        Field(max_length=RESOURCE_TELEMETRY_MAX_SOURCE_ARTIFACTS),
    ] = ()
    provider_id: NonEmptyId | None = None
    provider_revision: NonEmptyId | None = None
    model_id: NonEmptyId | None = None
    model_revision: NonEmptyId | None = None
    runtime: ResourceTelemetryRuntimeIdentity

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        _cold_validate_exact(
            ResourceTelemetryRuntimeIdentity,
            self.runtime,
            label="Telemetry provenance runtime identity",
        )
        if self.source_artifact_ids != tuple(sorted(set(self.source_artifact_ids))):
            raise ValueError("Telemetry source artifact IDs must be sorted and unique")
        if (self.provider_id is None) != (self.provider_revision is None):
            raise ValueError("Telemetry provider identity must be complete or absent")
        if (self.model_id is None) != (self.model_revision is None):
            raise ValueError("Telemetry model identity must be complete or absent")
        return self


class ResourceTelemetryMetricCoverage(FrozenModel):
    attempted_samples: int = Field(ge=2, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    measured_samples: int = Field(ge=0, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    status: ResourceTelemetryCoverageStatus

    @classmethod
    def create(
        cls,
        *,
        attempted_samples: int,
        measured_samples: int,
    ) -> "ResourceTelemetryMetricCoverage":
        if measured_samples == attempted_samples:
            status: ResourceTelemetryCoverageStatus = "complete"
        elif measured_samples == 0:
            status = "unavailable"
        else:
            status = "partial"
        return cls(
            attempted_samples=attempted_samples,
            measured_samples=measured_samples,
            status=status,
        )

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        if self.measured_samples > self.attempted_samples:
            raise ValueError("Measured telemetry samples cannot exceed attempts")
        expected = (
            "complete"
            if self.measured_samples == self.attempted_samples
            else "unavailable"
            if self.measured_samples == 0
            else "partial"
        )
        if self.status != expected:
            raise ValueError("Telemetry coverage status differs from sample counts")
        return self


def _validate_measurement_family(
    readings: Sequence[ResourceByteReading],
    *,
    expected_scope: ResourceTelemetryMeasurementScope,
    expected_subject_id: str | None,
    label: str,
) -> None:
    measured = tuple(reading for reading in readings if reading.status == "measured")
    if not measured:
        return
    if expected_subject_id is None:
        raise ValueError(f"{label} measurements lack a resolved subject identity")
    if any(reading.measurement_scope != expected_scope for reading in measured):
        raise ValueError(f"{label} measurements use the wrong metric scope")
    identities = {(reading.source, reading.subject_id) for reading in measured}
    if len(identities) != 1:
        raise ValueError(f"{label} measurements use inconsistent identities")
    (_source, subject_id) = next(iter(identities))
    if subject_id != expected_subject_id:
        raise ValueError(f"{label} measurements target the wrong subject")


class ResourceTelemetryArtifact(FrozenArtifactModel):
    """Content-addressed resource summary with no semantic authority."""

    schema_version: Literal["rei-resource-telemetry-v1"] = "rei-resource-telemetry-v1"
    telemetry_id: NonEmptyId
    provenance: ResourceTelemetryProvenance
    execution_status: ResourceTelemetryExecutionStatus
    failure_code: NonEmptyId | None = None
    clock_source: NonEmptyId
    sampling_policy: Literal["caller-driven-bounded-v1"] = (
        RESOURCE_TELEMETRY_SAMPLING_POLICY
    )
    sampling_cadence_target_seconds: float = Field(
        gt=0.0,
        le=RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS,
        allow_inf_nan=False,
    )
    probe_revision: NonEmptyId
    sample_count: int = Field(ge=2, le=RESOURCE_TELEMETRY_MAX_SAMPLES)
    workload_elapsed_monotonic_seconds: float = Field(ge=0.0, allow_inf_nan=False)
    instrumented_interval_monotonic_seconds: float = Field(ge=0.0, allow_inf_nan=False)
    sampling_overhead_monotonic_seconds: float = Field(ge=0.0, allow_inf_nan=False)
    process_rss_start_bytes: ResourceByteReading
    process_rss_end_bytes: ResourceByteReading
    process_rss_peak_sampled_bytes: ResourceByteReading
    process_peak_scope: Literal["sampled_process_scope_rss_lower_bound"] = (
        "sampled_process_scope_rss_lower_bound"
    )
    process_memory_coverage: ResourceTelemetryMetricCoverage
    system_ram_total_bytes: ResourceByteReading
    system_ram_available_min_bytes: ResourceByteReading
    system_availability_coverage: ResourceTelemetryMetricCoverage
    system_capacity_coverage: ResourceTelemetryMetricCoverage
    cuda_vram_start_bytes: ResourceByteReading
    cuda_vram_end_bytes: ResourceByteReading
    cuda_vram_peak_sampled_bytes: ResourceByteReading
    cuda_vram_total_bytes: ResourceByteReading
    cuda_vram_scope: Literal["whole_device_sampled"] = "whole_device_sampled"
    cuda_usage_coverage: ResourceTelemetryMetricCoverage
    cuda_capacity_coverage: ResourceTelemetryMetricCoverage
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False
    artifact_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        provenance: ResourceTelemetryProvenance,
        execution_status: ResourceTelemetryExecutionStatus,
        failure_code: str | None,
        clock_source: str,
        sampling_cadence_target_seconds: float = (
            RESOURCE_TELEMETRY_DEFAULT_CADENCE_SECONDS
        ),
        probe_revision: str = RESOURCE_TELEMETRY_PROBE_REVISION,
        sample_count: int,
        workload_elapsed_monotonic_seconds: float,
        instrumented_interval_monotonic_seconds: float,
        sampling_overhead_monotonic_seconds: float,
        process_rss_start_bytes: ResourceByteReading,
        process_rss_end_bytes: ResourceByteReading,
        process_rss_peak_sampled_bytes: ResourceByteReading,
        process_memory_coverage: ResourceTelemetryMetricCoverage,
        system_ram_total_bytes: ResourceByteReading,
        system_ram_available_min_bytes: ResourceByteReading,
        system_availability_coverage: ResourceTelemetryMetricCoverage,
        system_capacity_coverage: ResourceTelemetryMetricCoverage,
        cuda_vram_start_bytes: ResourceByteReading,
        cuda_vram_end_bytes: ResourceByteReading,
        cuda_vram_peak_sampled_bytes: ResourceByteReading,
        cuda_vram_total_bytes: ResourceByteReading,
        cuda_usage_coverage: ResourceTelemetryMetricCoverage,
        cuda_capacity_coverage: ResourceTelemetryMetricCoverage,
    ) -> "ResourceTelemetryArtifact":
        execution_status = _EXECUTION_STATUS_ADAPTER.validate_python(execution_status)
        if failure_code is not None:
            failure_code = _NON_EMPTY_ID_ADAPTER.validate_python(failure_code)
        if (execution_status == "completed") == (failure_code is not None):
            raise ValueError(
                "Completed telemetry cannot have a failure; failed telemetry must"
                " identify one"
            )
        sample_count = _SAMPLE_COUNT_ADAPTER.validate_python(sample_count)
        workload_elapsed_monotonic_seconds = (
            _NON_NEGATIVE_SECONDS_ADAPTER.validate_python(
                workload_elapsed_monotonic_seconds
            )
        )
        instrumented_interval_monotonic_seconds = (
            _NON_NEGATIVE_SECONDS_ADAPTER.validate_python(
                instrumented_interval_monotonic_seconds
            )
        )
        sampling_overhead_monotonic_seconds = (
            _NON_NEGATIVE_SECONDS_ADAPTER.validate_python(
                sampling_overhead_monotonic_seconds
            )
        )
        sampling_cadence_target_seconds = _CADENCE_SECONDS_ADAPTER.validate_python(
            sampling_cadence_target_seconds
        )
        provenance = _cold_validate_exact(
            ResourceTelemetryProvenance,
            provenance,
            label="Resource telemetry provenance",
        )
        readings = {
            field_name: _cold_validate_exact(
                ResourceByteReading,
                value,
                label=f"Resource telemetry {field_name}",
            )
            for field_name, value in {
                "process_rss_start_bytes": process_rss_start_bytes,
                "process_rss_end_bytes": process_rss_end_bytes,
                "process_rss_peak_sampled_bytes": process_rss_peak_sampled_bytes,
                "system_ram_total_bytes": system_ram_total_bytes,
                "system_ram_available_min_bytes": system_ram_available_min_bytes,
                "cuda_vram_start_bytes": cuda_vram_start_bytes,
                "cuda_vram_end_bytes": cuda_vram_end_bytes,
                "cuda_vram_peak_sampled_bytes": cuda_vram_peak_sampled_bytes,
                "cuda_vram_total_bytes": cuda_vram_total_bytes,
            }.items()
        }
        coverages = {
            field_name: _cold_validate_exact(
                ResourceTelemetryMetricCoverage,
                value,
                label=f"Resource telemetry {field_name}",
            )
            for field_name, value in {
                "process_memory_coverage": process_memory_coverage,
                "system_availability_coverage": system_availability_coverage,
                "system_capacity_coverage": system_capacity_coverage,
                "cuda_usage_coverage": cuda_usage_coverage,
                "cuda_capacity_coverage": cuda_capacity_coverage,
            }.items()
        }
        clock_source = _NON_EMPTY_ID_ADAPTER.validate_python(clock_source)
        probe_revision = _NON_EMPTY_ID_ADAPTER.validate_python(probe_revision)
        _validate_measurement_family(
            (
                readings["process_rss_start_bytes"],
                readings["process_rss_end_bytes"],
                readings["process_rss_peak_sampled_bytes"],
            ),
            expected_scope="process_scope_rss",
            expected_subject_id=provenance.runtime.target.measurement_subject_id,
            label="Process RSS",
        )
        _validate_measurement_family(
            (
                readings["system_ram_total_bytes"],
                readings["system_ram_available_min_bytes"],
            ),
            expected_scope="system_physical_memory",
            expected_subject_id=provenance.runtime.system_memory_subject_id,
            label="System memory",
        )
        _validate_measurement_family(
            (
                readings["cuda_vram_start_bytes"],
                readings["cuda_vram_end_bytes"],
                readings["cuda_vram_peak_sampled_bytes"],
                readings["cuda_vram_total_bytes"],
            ),
            expected_scope="cuda_device_memory",
            expected_subject_id=(provenance.runtime.cuda_device.measurement_subject_id),
            label="CUDA memory",
        )
        base = {
            "schema_version": "rei-resource-telemetry-v1",
            "provenance": provenance,
            "execution_status": execution_status,
            "failure_code": failure_code,
            "clock_source": clock_source,
            "sampling_policy": RESOURCE_TELEMETRY_SAMPLING_POLICY,
            "sampling_cadence_target_seconds": (sampling_cadence_target_seconds),
            "probe_revision": probe_revision,
            "sample_count": sample_count,
            "workload_elapsed_monotonic_seconds": (workload_elapsed_monotonic_seconds),
            "instrumented_interval_monotonic_seconds": (
                instrumented_interval_monotonic_seconds
            ),
            "sampling_overhead_monotonic_seconds": (
                sampling_overhead_monotonic_seconds
            ),
            "process_rss_start_bytes": readings["process_rss_start_bytes"],
            "process_rss_end_bytes": readings["process_rss_end_bytes"],
            "process_rss_peak_sampled_bytes": readings[
                "process_rss_peak_sampled_bytes"
            ],
            "process_peak_scope": "sampled_process_scope_rss_lower_bound",
            "process_memory_coverage": coverages["process_memory_coverage"],
            "system_ram_total_bytes": readings["system_ram_total_bytes"],
            "system_ram_available_min_bytes": readings[
                "system_ram_available_min_bytes"
            ],
            "system_availability_coverage": coverages["system_availability_coverage"],
            "system_capacity_coverage": coverages["system_capacity_coverage"],
            "cuda_vram_start_bytes": readings["cuda_vram_start_bytes"],
            "cuda_vram_end_bytes": readings["cuda_vram_end_bytes"],
            "cuda_vram_peak_sampled_bytes": readings["cuda_vram_peak_sampled_bytes"],
            "cuda_vram_total_bytes": readings["cuda_vram_total_bytes"],
            "cuda_vram_scope": "whole_device_sampled",
            "cuda_usage_coverage": coverages["cuda_usage_coverage"],
            "cuda_capacity_coverage": coverages["cuda_capacity_coverage"],
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        if (
            len(canonical_json_bytes(base))
            > RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES - 512
        ):
            raise ValueError("Resource telemetry content exceeds its byte limit")
        telemetry_id = content_id("resource_telemetry", base)
        payload = {"telemetry_id": telemetry_id, **base}
        artifact = cls(**payload, artifact_hash=sha256_hex(payload))
        if (
            len(artifact.canonical_json_bytes()) + 1
            > RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES
        ):
            raise ValueError("Resource telemetry artifact exceeds its byte limit")
        return artifact

    @model_validator(mode="after")
    def validate_artifact(self) -> Self:
        _cold_validate_exact(
            ResourceTelemetryProvenance,
            self.provenance,
            label="Resource telemetry artifact provenance",
        )
        for field_name in (
            "process_rss_start_bytes",
            "process_rss_end_bytes",
            "process_rss_peak_sampled_bytes",
            "system_ram_total_bytes",
            "system_ram_available_min_bytes",
            "cuda_vram_start_bytes",
            "cuda_vram_end_bytes",
            "cuda_vram_peak_sampled_bytes",
            "cuda_vram_total_bytes",
        ):
            _cold_validate_exact(
                ResourceByteReading,
                getattr(self, field_name),
                label=f"Resource telemetry artifact {field_name}",
            )
        _validate_measurement_family(
            (
                self.process_rss_start_bytes,
                self.process_rss_end_bytes,
                self.process_rss_peak_sampled_bytes,
            ),
            expected_scope="process_scope_rss",
            expected_subject_id=self.provenance.runtime.target.measurement_subject_id,
            label="Process RSS",
        )
        _validate_measurement_family(
            (
                self.system_ram_total_bytes,
                self.system_ram_available_min_bytes,
            ),
            expected_scope="system_physical_memory",
            expected_subject_id=self.provenance.runtime.system_memory_subject_id,
            label="System memory",
        )
        _validate_measurement_family(
            (
                self.cuda_vram_start_bytes,
                self.cuda_vram_end_bytes,
                self.cuda_vram_peak_sampled_bytes,
                self.cuda_vram_total_bytes,
            ),
            expected_scope="cuda_device_memory",
            expected_subject_id=(
                self.provenance.runtime.cuda_device.measurement_subject_id
            ),
            label="CUDA memory",
        )
        for field_name in (
            "process_memory_coverage",
            "system_availability_coverage",
            "system_capacity_coverage",
            "cuda_usage_coverage",
            "cuda_capacity_coverage",
        ):
            _cold_validate_exact(
                ResourceTelemetryMetricCoverage,
                getattr(self, field_name),
                label=f"Resource telemetry artifact {field_name}",
            )
        if (self.execution_status == "completed") == (self.failure_code is not None):
            raise ValueError(
                "Completed telemetry cannot have a failure; failed telemetry must"
                " identify one"
            )
        if (
            self.workload_elapsed_monotonic_seconds
            != self.instrumented_interval_monotonic_seconds
        ):
            raise ValueError(
                "Workload wall time must equal its inclusive instrumented interval"
            )
        if (
            self.sampling_overhead_monotonic_seconds
            > self.instrumented_interval_monotonic_seconds
        ):
            raise ValueError(
                "Sampling overhead cannot exceed its inclusive instrumented interval"
            )
        coverages = (
            self.process_memory_coverage,
            self.system_availability_coverage,
            self.system_capacity_coverage,
            self.cuda_usage_coverage,
            self.cuda_capacity_coverage,
        )
        if any(item.attempted_samples != self.sample_count for item in coverages):
            raise ValueError("Telemetry coverage attempts differ from sample count")
        process_endpoint_measurements = sum(
            reading.status == "measured"
            for reading in (
                self.process_rss_start_bytes,
                self.process_rss_end_bytes,
            )
        )
        if (
            process_endpoint_measurements
            > self.process_memory_coverage.measured_samples
        ):
            raise ValueError(
                "Process endpoint readings exceed measured process coverage"
            )
        process_peak_measured = self.process_rss_peak_sampled_bytes.status == "measured"
        if process_peak_measured != (self.process_memory_coverage.measured_samples > 0):
            raise ValueError(
                "Process peak availability differs from measured process coverage"
            )
        if self.process_memory_coverage.status == "complete" and (
            process_endpoint_measurements != 2
        ):
            raise ValueError(
                "Complete process coverage requires both endpoint readings"
            )
        if self.system_availability_coverage.status == "complete":
            if self.system_ram_available_min_bytes.status != "measured":
                raise ValueError(
                    "Complete system availability coverage requires an"
                    " available-RAM minimum"
                )
        elif self.system_ram_available_min_bytes.status == "measured":
            raise ValueError(
                "Measured available-RAM minimum requires complete availability coverage"
            )
        if self.system_capacity_coverage.status == "complete":
            if (
                self.system_ram_total_bytes.status == "unavailable"
                and self.system_ram_total_bytes.unavailable_reason
                != "inconsistent_capacity_value"
            ):
                raise ValueError(
                    "Complete system capacity coverage requires total RAM or an"
                    " explicit inconsistent-capacity result"
                )
        elif self.system_ram_total_bytes.status == "measured":
            raise ValueError(
                "Measured total system capacity requires complete capacity coverage"
            )
        cuda_endpoint_measurements = sum(
            reading.status == "measured"
            for reading in (
                self.cuda_vram_start_bytes,
                self.cuda_vram_end_bytes,
            )
        )
        if cuda_endpoint_measurements > self.cuda_usage_coverage.measured_samples:
            raise ValueError(
                "CUDA usage endpoint readings exceed measured usage coverage"
            )
        cuda_peak_measured = self.cuda_vram_peak_sampled_bytes.status == "measured"
        if cuda_peak_measured != (self.cuda_usage_coverage.measured_samples > 0):
            raise ValueError(
                "CUDA usage peak availability differs from measured usage coverage"
            )
        if (
            self.cuda_usage_coverage.status == "complete"
            and cuda_endpoint_measurements != 2
        ):
            raise ValueError(
                "Complete CUDA usage coverage requires both endpoint readings"
            )
        if self.cuda_capacity_coverage.status == "complete":
            if (
                self.cuda_vram_total_bytes.status == "unavailable"
                and self.cuda_vram_total_bytes.unavailable_reason
                != "inconsistent_capacity_value"
            ):
                raise ValueError(
                    "Complete CUDA capacity coverage requires total VRAM or an"
                    " explicit inconsistent-capacity result"
                )
        elif self.cuda_vram_total_bytes.status == "measured":
            raise ValueError(
                "Measured total CUDA capacity requires complete capacity coverage"
            )
        if (
            self.system_ram_available_min_bytes.status == "measured"
            and self.system_ram_total_bytes.status == "measured"
            and self.system_ram_available_min_bytes.value_bytes is not None
            and self.system_ram_total_bytes.value_bytes is not None
            and self.system_ram_available_min_bytes.value_bytes
            > self.system_ram_total_bytes.value_bytes
        ):
            raise ValueError("Available system RAM cannot exceed total RAM")
        process_values = [
            reading.value_bytes
            for reading in (
                self.process_rss_start_bytes,
                self.process_rss_end_bytes,
            )
            if reading.status == "measured" and reading.value_bytes is not None
        ]
        if (
            process_values
            and self.process_rss_peak_sampled_bytes.status == "measured"
            and self.process_rss_peak_sampled_bytes.value_bytes is not None
            and self.process_rss_peak_sampled_bytes.value_bytes < max(process_values)
        ):
            raise ValueError("Sampled process peak cannot be below an endpoint")
        cuda_values = [
            reading.value_bytes
            for reading in (
                self.cuda_vram_start_bytes,
                self.cuda_vram_end_bytes,
                self.cuda_vram_peak_sampled_bytes,
            )
            if reading.status == "measured" and reading.value_bytes is not None
        ]
        if (
            cuda_values
            and self.cuda_vram_total_bytes.status == "measured"
            and self.cuda_vram_total_bytes.value_bytes is not None
            and max(cuda_values) > self.cuda_vram_total_bytes.value_bytes
        ):
            raise ValueError("Sampled CUDA VRAM cannot exceed total VRAM")
        cuda_endpoints = [
            reading.value_bytes
            for reading in (
                self.cuda_vram_start_bytes,
                self.cuda_vram_end_bytes,
            )
            if reading.status == "measured" and reading.value_bytes is not None
        ]
        if (
            cuda_endpoints
            and self.cuda_vram_peak_sampled_bytes.status == "measured"
            and self.cuda_vram_peak_sampled_bytes.value_bytes is not None
            and self.cuda_vram_peak_sampled_bytes.value_bytes < max(cuda_endpoints)
        ):
            raise ValueError("Sampled CUDA peak cannot be below an endpoint")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"telemetry_id", "artifact_hash"},
        )
        if self.telemetry_id != content_id("resource_telemetry", base):
            raise ValueError("Resource telemetry ID differs from its content")
        payload = {"telemetry_id": self.telemetry_id, **base}
        if self.artifact_hash != sha256_hex(payload):
            raise ValueError("Resource telemetry hash differs from its content")
        return self


class ResourceTelemetryStateError(RuntimeError):
    """Raised when a bounded recorder is used outside its state contract."""


class ResourceTelemetryLimitError(ResourceTelemetryStateError):
    """Raised before an explicit sample would consume the reserved final slot."""


def _aggregate_readings(
    readings: Sequence[ResourceByteReading],
    *,
    selector: Callable[[Sequence[int]], int],
    require_constant: bool = False,
    allow_partial: bool = False,
) -> ResourceByteReading:
    measured = [reading for reading in readings if reading.status == "measured"]
    if not measured:
        return ResourceByteReading.unavailable("no_measured_samples")
    if not allow_partial and len(measured) != len(readings):
        return ResourceByteReading.unavailable("incomplete_sample_coverage")
    sources = {reading.source for reading in measured}
    scopes = {reading.measurement_scope for reading in measured}
    subjects = {reading.subject_id for reading in measured}
    if len(sources) != 1 or len(scopes) != 1 or len(subjects) != 1:
        return ResourceByteReading.unavailable("inconsistent_measurement_identity")
    values = [
        reading.value_bytes for reading in measured if reading.value_bytes is not None
    ]
    if len(values) != len(measured):
        return ResourceByteReading.unavailable("incomplete_sample_coverage")
    if require_constant and len(set(values)) != 1:
        return ResourceByteReading.unavailable("inconsistent_capacity_value")
    source = next(iter(sources))
    scope = next(iter(scopes))
    subject_id = next(iter(subjects))
    if source is None or scope is None or subject_id is None:
        return ResourceByteReading.unavailable("incomplete_sample_coverage")
    return ResourceByteReading.measured(
        selector(values),
        source=source,
        measurement_scope=scope,
        subject_id=subject_id,
    )


def _coverage(
    snapshots: Sequence[ResourceTelemetrySnapshot],
    predicate: Callable[[ResourceTelemetrySnapshot], bool],
) -> ResourceTelemetryMetricCoverage:
    return ResourceTelemetryMetricCoverage.create(
        attempted_samples=len(snapshots),
        measured_samples=sum(1 for snapshot in snapshots if predicate(snapshot)),
    )


class UniformResourceTelemetryRecorder:
    """Bounded sampler with inclusive child wall-time semantics.

    A benchmark child continues to run while a synchronous sample is collected,
    so probe time is never subtracted from the workload interval.  Sampling
    overhead remains separately visible as an instrumentation-cost measure.
    """

    def __init__(
        self,
        provenance: ResourceTelemetryProvenance,
        *,
        probe: ResourceTelemetryProbe | None = None,
        clock_ns: Callable[[], int] = time.monotonic_ns,
        clock_source: str = "time_monotonic_ns",
        max_samples: int = RESOURCE_TELEMETRY_MAX_SAMPLES,
        sampling_cadence_target_seconds: float = (
            RESOURCE_TELEMETRY_DEFAULT_CADENCE_SECONDS
        ),
        probe_revision: str | None = None,
    ) -> None:
        if (
            not isinstance(max_samples, int)
            or isinstance(max_samples, bool)
            or not 2 <= max_samples <= RESOURCE_TELEMETRY_MAX_SAMPLES
        ):
            raise ValueError("Telemetry max_samples must stay between 2 and 4096")
        if (
            not isinstance(sampling_cadence_target_seconds, float)
            or isinstance(sampling_cadence_target_seconds, bool)
            or not 0.0
            < sampling_cadence_target_seconds
            <= (RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS)
        ):
            raise ValueError(
                "Telemetry cadence target must be a bounded positive float"
            )
        self._provenance = _cold_validate_exact(
            ResourceTelemetryProvenance,
            provenance,
            label="Telemetry recorder provenance",
        )
        self._probe = probe or SystemResourceTelemetryProbe(
            target=self._provenance.runtime.target,
            cuda_device=self._provenance.runtime.cuda_device,
        )
        self._clock_ns = clock_ns
        self._clock_source = _NON_EMPTY_ID_ADAPTER.validate_python(clock_source)
        self._max_samples = max_samples
        self._sampling_cadence_target_seconds = sampling_cadence_target_seconds
        inferred_probe_revision = getattr(
            self._probe,
            "probe_revision",
            "caller-supplied-resource-probe",
        )
        self._probe_revision = _NON_EMPTY_ID_ADAPTER.validate_python(
            inferred_probe_revision if probe_revision is None else probe_revision
        )
        self._state: Literal["new", "running", "finished", "failed"] = "new"
        self._samples: list[ResourceTelemetrySnapshot] = []
        self._started_ns: int | None = None
        self._last_clock_ns: int | None = None
        self._sampling_overhead_ns = 0
        self._artifact: ResourceTelemetryArtifact | None = None

    def _read_clock(self) -> int:
        value = self._clock_ns()
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ResourceTelemetryStateError(
                "Telemetry monotonic clock must return a non-negative integer"
            )
        if self._last_clock_ns is not None and value < self._last_clock_ns:
            raise ResourceTelemetryStateError(
                "Telemetry monotonic clock moved backwards"
            )
        self._last_clock_ns = value
        return value

    def _safe_snapshot(self) -> ResourceTelemetrySnapshot:
        try:
            snapshot = self._probe.snapshot()
        except Exception:
            return ResourceTelemetrySnapshot.unavailable("probe_exception")
        if not isinstance(snapshot, ResourceTelemetrySnapshot):
            return ResourceTelemetrySnapshot.unavailable("invalid_probe_result")
        try:
            return ResourceTelemetrySnapshot.model_validate(
                snapshot.model_dump(mode="python", round_trip=True)
            )
        except Exception:
            return ResourceTelemetrySnapshot.unavailable("invalid_probe_result")

    def _timed_snapshot(self) -> tuple[ResourceTelemetrySnapshot, int, int]:
        started_ns = self._read_clock()
        snapshot = self._safe_snapshot()
        finished_ns = self._read_clock()
        return snapshot, started_ns, finished_ns

    def start(self) -> None:
        if self._state != "new":
            raise ResourceTelemetryStateError("Telemetry recorder can only start once")
        snapshot, probe_started_ns, probe_finished_ns = self._timed_snapshot()
        self._samples.append(snapshot)
        self._sampling_overhead_ns = probe_finished_ns - probe_started_ns
        self._started_ns = probe_started_ns
        self._state = "running"

    def sample(self) -> None:
        if self._state != "running":
            raise ResourceTelemetryStateError(
                "Telemetry sampling requires a running recorder"
            )
        if len(self._samples) >= self._max_samples - 1:
            raise ResourceTelemetryLimitError(
                "Telemetry sample limit reserves one slot for the final sample"
            )
        snapshot, probe_started_ns, probe_finished_ns = self._timed_snapshot()
        overhead = probe_finished_ns - probe_started_ns
        self._samples.append(snapshot)
        self._sampling_overhead_ns += overhead

    def finish(
        self,
        *,
        execution_status: ResourceTelemetryExecutionStatus = "completed",
        failure_code: str | None = None,
    ) -> ResourceTelemetryArtifact:
        if self._state != "running" or self._started_ns is None:
            raise ResourceTelemetryStateError(
                "Telemetry finish requires a running recorder"
            )
        if execution_status not in {"completed", "failed"}:
            raise ValueError("Telemetry execution status is invalid")
        if (execution_status == "completed") == (failure_code is not None):
            raise ValueError(
                "Completed telemetry cannot have a failure; failed telemetry must"
                " identify one"
            )
        if failure_code is not None:
            failure_code = _NON_EMPTY_ID_ADAPTER.validate_python(failure_code)

        # The first clock read happens before the final observation and is still
        # retry-safe.  Once the probe has returned, any clock, aggregation, or
        # validation failure is terminal: the acquired endpoint is retained and
        # can never be replaced by a later retry.
        probe_started_ns = self._read_clock()
        final_snapshot = self._safe_snapshot()
        total_probe_overhead_ns: int | None = None
        try:
            probe_finished_ns = self._read_clock()
            snapshots = (*self._samples, final_snapshot)
            instrumented_ns = probe_finished_ns - self._started_ns
            workload_ns = instrumented_ns
            total_probe_overhead_ns = (
                self._sampling_overhead_ns + probe_finished_ns - probe_started_ns
            )
            if total_probe_overhead_ns > instrumented_ns:
                raise ResourceTelemetryStateError(
                    "Telemetry sampling overhead exceeds its inclusive interval"
                )
            sample_count = len(snapshots)

            process_coverage = _coverage(
                snapshots,
                lambda item: item.process_scope_rss_bytes.status == "measured",
            )
            system_availability_coverage = _coverage(
                snapshots,
                lambda item: item.system_ram_available_bytes.status == "measured",
            )
            system_capacity_coverage = _coverage(
                snapshots,
                lambda item: item.system_ram_total_bytes.status == "measured",
            )
            cuda_usage_coverage = _coverage(
                snapshots,
                lambda item: item.cuda_vram_used_bytes.status == "measured",
            )
            cuda_capacity_coverage = _coverage(
                snapshots,
                lambda item: item.cuda_vram_total_bytes.status == "measured",
            )
            artifact = ResourceTelemetryArtifact.create(
                provenance=self._provenance,
                execution_status=execution_status,
                failure_code=failure_code,
                clock_source=self._clock_source,
                sampling_cadence_target_seconds=(self._sampling_cadence_target_seconds),
                probe_revision=self._probe_revision,
                sample_count=sample_count,
                workload_elapsed_monotonic_seconds=workload_ns / 1_000_000_000,
                instrumented_interval_monotonic_seconds=(
                    instrumented_ns / 1_000_000_000
                ),
                sampling_overhead_monotonic_seconds=(
                    total_probe_overhead_ns / 1_000_000_000
                ),
                process_rss_start_bytes=snapshots[0].process_scope_rss_bytes,
                process_rss_end_bytes=snapshots[-1].process_scope_rss_bytes,
                process_rss_peak_sampled_bytes=_aggregate_readings(
                    [snapshot.process_scope_rss_bytes for snapshot in snapshots],
                    selector=max,
                    allow_partial=True,
                ),
                process_memory_coverage=process_coverage,
                system_ram_total_bytes=_aggregate_readings(
                    [snapshot.system_ram_total_bytes for snapshot in snapshots],
                    selector=max,
                    require_constant=True,
                ),
                system_ram_available_min_bytes=_aggregate_readings(
                    [snapshot.system_ram_available_bytes for snapshot in snapshots],
                    selector=min,
                ),
                system_availability_coverage=system_availability_coverage,
                system_capacity_coverage=system_capacity_coverage,
                cuda_vram_start_bytes=snapshots[0].cuda_vram_used_bytes,
                cuda_vram_end_bytes=snapshots[-1].cuda_vram_used_bytes,
                cuda_vram_peak_sampled_bytes=_aggregate_readings(
                    [snapshot.cuda_vram_used_bytes for snapshot in snapshots],
                    selector=max,
                    allow_partial=True,
                ),
                cuda_vram_total_bytes=_aggregate_readings(
                    [snapshot.cuda_vram_total_bytes for snapshot in snapshots],
                    selector=max,
                    require_constant=True,
                ),
                cuda_usage_coverage=cuda_usage_coverage,
                cuda_capacity_coverage=cuda_capacity_coverage,
            )
        except Exception:
            # A final observation is never silently discarded. Once acquired,
            # any downstream aggregation/validation failure is terminal.
            self._samples.append(final_snapshot)
            if total_probe_overhead_ns is not None:
                self._sampling_overhead_ns = total_probe_overhead_ns
            self._state = "failed"
            raise
        self._samples.append(final_snapshot)
        self._sampling_overhead_ns = total_probe_overhead_ns
        self._state = "finished"
        self._artifact = artifact
        return artifact

    @property
    def artifact(self) -> ResourceTelemetryArtifact:
        if self._artifact is None:
            raise ResourceTelemetryStateError(
                "Telemetry artifact is unavailable before successful finish"
            )
        return self._artifact


BackgroundSamplerState = Literal[
    "new",
    "running",
    "stop_requested",
    "sample_limit_reached",
    "finished",
    "failed",
    "join_timed_out",
]


@dataclass(frozen=True, slots=True)
class BackgroundResourceTelemetrySample:
    """One sample and its bounded instrumentation interval."""

    snapshot: ResourceTelemetrySnapshot
    probe_started_monotonic_ns: int
    probe_finished_monotonic_ns: int

    def __post_init__(self) -> None:
        validated = _cold_validate_exact(
            ResourceTelemetrySnapshot,
            self.snapshot,
            label="Background telemetry snapshot",
        )
        if validated != self.snapshot:
            raise ValueError("Background telemetry snapshot changed on validation")
        if (
            isinstance(self.probe_started_monotonic_ns, bool)
            or isinstance(self.probe_finished_monotonic_ns, bool)
            or not isinstance(self.probe_started_monotonic_ns, int)
            or not isinstance(self.probe_finished_monotonic_ns, int)
            or self.probe_started_monotonic_ns < 0
            or self.probe_finished_monotonic_ns < self.probe_started_monotonic_ns
        ):
            raise ValueError("Background telemetry sample has invalid timing")

    @property
    def sampling_overhead_monotonic_ns(self) -> int:
        return self.probe_finished_monotonic_ns - self.probe_started_monotonic_ns


def _background_sampled_cuda_peak(
    samples: Sequence[BackgroundResourceTelemetrySample],
) -> ResourceByteReading | None:
    measured = tuple(
        sample.snapshot.cuda_vram_used_bytes
        for sample in samples
        if sample.snapshot.cuda_vram_used_bytes.status == "measured"
    )
    if not measured:
        return None
    return max(
        measured,
        key=lambda reading: (
            reading.value_bytes if reading.value_bytes is not None else -1
        ),
    )


@dataclass(frozen=True, slots=True)
class BackgroundResourceTelemetrySamplerStatus:
    """Immutable status published atomically by the single owner thread."""

    state: BackgroundSamplerState
    sample_count: int
    failure_code: str | None = None
    latest_sample: BackgroundResourceTelemetrySample | None = None
    sampled_cuda_vram_peak: ResourceByteReading | None = None

    def __post_init__(self) -> None:
        if self.state not in {
            "new",
            "running",
            "stop_requested",
            "sample_limit_reached",
            "finished",
            "failed",
            "join_timed_out",
        }:
            raise ValueError("Background telemetry status state is invalid")
        if (
            type(self.sample_count) is not int
            or not 0 <= self.sample_count <= RESOURCE_TELEMETRY_MAX_SAMPLES
        ):
            raise ValueError("Background telemetry status sample count is invalid")
        if (self.sample_count == 0) != (self.latest_sample is None):
            raise ValueError(
                "Background telemetry latest sample differs from its sample count"
            )
        if self.latest_sample is not None:
            validated_sample = BackgroundResourceTelemetrySample(
                snapshot=self.latest_sample.snapshot,
                probe_started_monotonic_ns=(
                    self.latest_sample.probe_started_monotonic_ns
                ),
                probe_finished_monotonic_ns=(
                    self.latest_sample.probe_finished_monotonic_ns
                ),
            )
            if validated_sample != self.latest_sample:
                raise ValueError("Background telemetry latest sample is not canonical")
        if self.sampled_cuda_vram_peak is not None:
            validated_peak = _cold_validate_exact(
                ResourceByteReading,
                self.sampled_cuda_vram_peak,
                label="Background telemetry sampled CUDA peak",
            )
            if (
                self.sample_count == 0
                or validated_peak.status != "measured"
                or validated_peak != self.sampled_cuda_vram_peak
            ):
                raise ValueError("Background telemetry sampled CUDA peak is invalid")
        failure_required = self.state in {"failed", "join_timed_out"}
        if failure_required != (self.failure_code is not None):
            raise ValueError("Background telemetry failure provenance is inconsistent")
        if self.failure_code is not None:
            validated = _NON_EMPTY_ID_ADAPTER.validate_python(self.failure_code)
            if validated != self.failure_code:
                raise ValueError("Background telemetry failure code is not canonical")


@dataclass(frozen=True, slots=True)
class BackgroundResourceTelemetrySamplerResult:
    """Bounded finalization result; samples are exposed only after thread exit."""

    status: BackgroundResourceTelemetrySamplerStatus
    samples: tuple[BackgroundResourceTelemetrySample, ...]
    sampling_overhead_monotonic_ns: int

    def __post_init__(self) -> None:
        if not isinstance(self.status, BackgroundResourceTelemetrySamplerStatus):
            raise TypeError("Background telemetry result requires a status")
        if not isinstance(self.samples, tuple) or any(
            not isinstance(sample, BackgroundResourceTelemetrySample)
            for sample in self.samples
        ):
            raise TypeError("Background telemetry result requires immutable samples")
        for sample in self.samples:
            validated_sample = BackgroundResourceTelemetrySample(
                snapshot=sample.snapshot,
                probe_started_monotonic_ns=sample.probe_started_monotonic_ns,
                probe_finished_monotonic_ns=sample.probe_finished_monotonic_ns,
            )
            if validated_sample != sample:
                raise ValueError("Background telemetry sample is not canonical")
        if (
            type(self.sampling_overhead_monotonic_ns) is not int
            or self.sampling_overhead_monotonic_ns < 0
        ):
            raise ValueError("Background telemetry overhead is invalid")
        if self.status.state == "join_timed_out":
            if self.samples or self.sampling_overhead_monotonic_ns != 0:
                raise ValueError("Timed-out sampler cannot expose mutable samples")
        elif self.status.state not in {"finished", "sample_limit_reached", "failed"}:
            raise ValueError("Background telemetry result is not terminal")
        elif self.status.sample_count != len(self.samples):
            raise ValueError("Background telemetry result count differs from samples")
        elif self.samples and self.status.latest_sample != self.samples[-1]:
            raise ValueError("Background telemetry result latest sample differs")
        if self.status.state != "join_timed_out" and (
            self.status.sampled_cuda_vram_peak
            != _background_sampled_cuda_peak(self.samples)
        ):
            raise ValueError("Background telemetry sampled CUDA peak differs")
        if any(
            current.probe_started_monotonic_ns < previous.probe_finished_monotonic_ns
            for previous, current in zip(self.samples, self.samples[1:], strict=False)
        ):
            raise ValueError("Background telemetry samples overlap or move backwards")
        if self.status.state != "join_timed_out" and (
            self.sampling_overhead_monotonic_ns
            != sum(sample.sampling_overhead_monotonic_ns for sample in self.samples)
        ):
            raise ValueError("Background telemetry overhead differs from samples")


class BackgroundResourceTelemetrySampler:
    """Single-owner sampler for hard-deadline runner integration.

    The worker thread is the only caller of ``probe.snapshot``.  ``poll`` and
    ``request_stop`` never wait for that call and return immutable published
    state.  ``finish`` performs the sole join and caps it at five seconds.  A
    timed-out daemon worker never exposes a concurrently mutating sample list.

    This class deliberately does not grant authority and is not wired into the
    process-tree runner here; integration must separately provide honest tree
    RSS and logical-to-physical CUDA identity.
    """

    sampling_policy = "background-start-deadline-cadence-v1"
    _TERMINAL_STATES = frozenset(
        {"sample_limit_reached", "finished", "failed", "join_timed_out"}
    )

    def __init__(
        self,
        probe: ResourceTelemetryProbe,
        *,
        cadence_seconds: float = RESOURCE_TELEMETRY_DEFAULT_CADENCE_SECONDS,
        max_samples: int = RESOURCE_TELEMETRY_MAX_SAMPLES,
        join_timeout_seconds: float = RESOURCE_TELEMETRY_BACKGROUND_JOIN_MAX_SECONDS,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if (
            not isinstance(cadence_seconds, float)
            or isinstance(cadence_seconds, bool)
            or not 0.0 < cadence_seconds <= RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS
        ):
            raise ValueError("Background telemetry cadence must be bounded")
        if (
            not isinstance(join_timeout_seconds, float)
            or isinstance(join_timeout_seconds, bool)
            or not 0.0
            < join_timeout_seconds
            <= RESOURCE_TELEMETRY_BACKGROUND_JOIN_MAX_SECONDS
        ):
            raise ValueError("Background telemetry join timeout must be bounded")
        if (
            not isinstance(max_samples, int)
            or isinstance(max_samples, bool)
            or not 2 <= max_samples <= RESOURCE_TELEMETRY_MAX_SAMPLES
        ):
            raise ValueError("Background telemetry sample limit is invalid")
        if not callable(getattr(probe, "snapshot", None)):
            raise TypeError("Background telemetry probe requires snapshot()")
        self._probe = probe
        self._cadence_seconds = cadence_seconds
        self._max_samples = max_samples
        self._join_timeout_seconds = join_timeout_seconds
        self._clock_ns = clock_ns
        self._stop_event = threading.Event()
        self._publication_lock = threading.Lock()
        self._samples: list[BackgroundResourceTelemetrySample] = []
        self._thread: threading.Thread | None = None
        self._last_clock_ns: int | None = None
        self._finish_called = False
        self._join_timed_out = False
        self._startup_poisoned = False
        self._initial_sample_published = threading.Event()
        self._status = BackgroundResourceTelemetrySamplerStatus(
            state="new",
            sample_count=0,
        )

    def _publish(
        self,
        state: BackgroundSamplerState,
        *,
        failure_code: str | None = None,
    ) -> None:
        with self._publication_lock:
            if self._join_timed_out:
                return
            if self._status.state in self._TERMINAL_STATES:
                return
            if state == "running" and self._status.state == "stop_requested":
                return
            self._status = BackgroundResourceTelemetrySamplerStatus(
                state=state,
                sample_count=len(self._samples),
                failure_code=failure_code,
                latest_sample=(self._samples[-1] if self._samples else None),
                sampled_cuda_vram_peak=self._status.sampled_cuda_vram_peak,
            )
            if state in self._TERMINAL_STATES:
                self._initial_sample_published.set()

    def _append_sample(
        self,
        sample: BackgroundResourceTelemetrySample,
        *,
        terminal_state: Literal["finished", "sample_limit_reached"] | None = None,
    ) -> bool:
        with self._publication_lock:
            if (
                self._startup_poisoned
                or self._join_timed_out
                or self._status.state in self._TERMINAL_STATES
            ):
                return False
            self._samples.append(sample)
            sampled_cuda_vram_peak = self._status.sampled_cuda_vram_peak
            current_cuda = sample.snapshot.cuda_vram_used_bytes
            if current_cuda.status == "measured" and (
                sampled_cuda_vram_peak is None
                or (
                    current_cuda.value_bytes is not None
                    and sampled_cuda_vram_peak.value_bytes is not None
                    and current_cuda.value_bytes > sampled_cuda_vram_peak.value_bytes
                )
            ):
                sampled_cuda_vram_peak = current_cuda
            if terminal_state == "sample_limit_reached" and self._stop_event.is_set():
                state: BackgroundSamplerState = "finished"
            else:
                state = terminal_state or (
                    "stop_requested"
                    if self._stop_event.is_set()
                    or self._status.state == "stop_requested"
                    else "running"
                )
            self._status = BackgroundResourceTelemetrySamplerStatus(
                state=state,
                sample_count=len(self._samples),
                latest_sample=sample,
                sampled_cuda_vram_peak=sampled_cuda_vram_peak,
            )
            self._initial_sample_published.set()
            return True

    def _read_clock(self) -> int:
        value = self._clock_ns()
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("background_clock_invalid")
        if self._last_clock_ns is not None and value < self._last_clock_ns:
            raise ValueError("background_clock_moved_backwards")
        self._last_clock_ns = value
        return value

    def _safe_snapshot(self) -> ResourceTelemetrySnapshot:
        try:
            result = self._probe.snapshot()
            return _cold_validate_exact(
                ResourceTelemetrySnapshot,
                result,
                label="Background telemetry probe result",
            )
        except Exception:
            return ResourceTelemetrySnapshot.unavailable("probe_exception")

    def _timed_sample(self) -> BackgroundResourceTelemetrySample:
        started_ns = self._read_clock()
        snapshot = self._safe_snapshot()
        finished_ns = self._read_clock()
        return BackgroundResourceTelemetrySample(
            snapshot=snapshot,
            probe_started_monotonic_ns=started_ns,
            probe_finished_monotonic_ns=finished_ns,
        )

    def _run(self) -> None:
        try:
            # ``start`` owns this lock until Thread.start() either returns or
            # fails.  A hostile implementation may start the worker and then
            # raise; the poison check prevents that worker from ever probing.
            with self._publication_lock:
                if self._startup_poisoned:
                    return

            sample_started_monotonic = time.monotonic()
            if not self._append_sample(self._timed_sample()):
                return

            while True:
                next_start_deadline = sample_started_monotonic + self._cadence_seconds
                remaining = max(0.0, next_start_deadline - time.monotonic())
                stop_requested = self._stop_event.wait(remaining)
                with self._publication_lock:
                    sample_count = len(self._samples)

                # One sample slot is always reserved for a worker-owned final
                # endpoint.  Stop requests therefore never turn the latest
                # cadence sample into an inferred end reading.
                if stop_requested:
                    self._append_sample(
                        self._timed_sample(),
                        terminal_state="finished",
                    )
                    return

                if sample_count >= self._max_samples - 1:
                    self._append_sample(
                        self._timed_sample(),
                        terminal_state="sample_limit_reached",
                    )
                    return

                sample_started_monotonic = time.monotonic()
                if not self._append_sample(self._timed_sample()):
                    return
        except BaseException:
            self._publish("failed", failure_code="background_sampler_failure")

    def start(self) -> None:
        start_failure: BaseException | None = None
        thread: threading.Thread
        with self._publication_lock:
            state = self._status.state
            if state != "new":
                raise ResourceTelemetryStateError(
                    "Background telemetry sampler can only start once"
                )
            thread = threading.Thread(
                target=self._run,
                name="rei-resource-telemetry-sampler",
                daemon=True,
            )
            self._thread = thread
            self._status = BackgroundResourceTelemetrySamplerStatus(
                state="running",
                sample_count=0,
            )
            try:
                # Holding the publication lock keeps finish() from observing an
                # assigned-but-not-yet-started thread.
                thread.start()
            except BaseException as exc:
                self._startup_poisoned = True
                self._stop_event.set()
                self._status = BackgroundResourceTelemetrySamplerStatus(
                    state="failed",
                    sample_count=0,
                    failure_code="sampler_thread_start_failure",
                )
                self._initial_sample_published.set()
                start_failure = exc

        if start_failure is not None:
            # Join only after releasing the publication lock: a worker started
            # as a side effect must acquire it to observe the poison state.
            try:
                thread.join(timeout=self._join_timeout_seconds)
            except BaseException:
                # A never-started Thread raises RuntimeError here.  The original
                # startup failure remains the authoritative exception.
                pass
            if isinstance(start_failure, Exception):
                raise ResourceTelemetryStateError(
                    "Background telemetry worker could not start"
                ) from start_failure
            raise start_failure

    def wait_for_initial_sample(
        self,
        *,
        timeout_seconds: float,
    ) -> BackgroundResourceTelemetrySamplerStatus:
        """Wait once for the initial immutable publication without probing."""

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or not 0.0
            < float(timeout_seconds)
            <= RESOURCE_TELEMETRY_BACKGROUND_JOIN_MAX_SECONDS
        ):
            raise ValueError("Background telemetry initial wait must be bounded")
        with self._publication_lock:
            if self._status.state == "new":
                raise ResourceTelemetryStateError(
                    "Background telemetry initial wait requires a started sampler"
                )
        if not self._initial_sample_published.wait(float(timeout_seconds)):
            raise ResourceTelemetryStateError(
                "Background telemetry initial sample was not published in time"
            )
        return self.poll()

    def poll(self) -> BackgroundResourceTelemetrySamplerStatus:
        """Return the last immutable publication without joining or probing."""

        with self._publication_lock:
            return self._status

    def request_stop(self) -> BackgroundResourceTelemetrySamplerStatus:
        """Signal termination without waiting for an in-flight probe."""

        with self._publication_lock:
            state = self._status.state
            if state == "new":
                raise ResourceTelemetryStateError(
                    "Background telemetry stop requires a started sampler"
                )
            self._stop_event.set()
            if state == "running":
                self._status = BackgroundResourceTelemetrySamplerStatus(
                    state="stop_requested",
                    sample_count=len(self._samples),
                    latest_sample=(self._samples[-1] if self._samples else None),
                    sampled_cuda_vram_peak=self._status.sampled_cuda_vram_peak,
                )
            return self._status

    def finish(self) -> BackgroundResourceTelemetrySamplerResult:
        """Request stop and perform one bounded final join."""

        with self._publication_lock:
            thread = self._thread
            if thread is None:
                raise ResourceTelemetryStateError(
                    "Background telemetry finish requires a started sampler"
                )
            if self._finish_called:
                raise ResourceTelemetryStateError(
                    "Background telemetry sampler can only finish once"
                )
            self._finish_called = True
        self.request_stop()
        try:
            thread.join(timeout=self._join_timeout_seconds)
        except RuntimeError:
            # A pre-start Thread failure is already represented by the frozen
            # terminal status published by start().
            pass
        if thread.is_alive():
            with self._publication_lock:
                self._join_timed_out = True
                self._status = BackgroundResourceTelemetrySamplerStatus(
                    state="join_timed_out",
                    sample_count=len(self._samples),
                    failure_code="sampler_join_timeout",
                    latest_sample=(self._samples[-1] if self._samples else None),
                    sampled_cuda_vram_peak=self._status.sampled_cuda_vram_peak,
                )
                status = self._status
            return BackgroundResourceTelemetrySamplerResult(
                status=status,
                samples=(),
                sampling_overhead_monotonic_ns=0,
            )
        with self._publication_lock:
            samples = tuple(self._samples)
            status = self._status
            if status.state not in self._TERMINAL_STATES:
                status = BackgroundResourceTelemetrySamplerStatus(
                    state="failed",
                    sample_count=len(samples),
                    failure_code="background_sampler_nonterminal_exit",
                    latest_sample=(samples[-1] if samples else None),
                    sampled_cuda_vram_peak=_background_sampled_cuda_peak(samples),
                )
                self._status = status
        return BackgroundResourceTelemetrySamplerResult(
            status=status,
            samples=samples,
            sampling_overhead_monotonic_ns=sum(
                sample.sampling_overhead_monotonic_ns for sample in samples
            ),
        )


def _linux_process_start_token(process_id: int) -> str:
    payload = Path(f"/proc/{process_id}/stat").read_text(encoding="ascii")
    closing_parenthesis = payload.rfind(")")
    if closing_parenthesis < 0:
        raise ValueError("invalid Linux process stat")
    fields_after_comm = payload[closing_parenthesis + 2 :].split()
    if len(fields_after_comm) <= 19:
        raise ValueError("incomplete Linux process stat")
    start_ticks = int(fields_after_comm[19])
    if start_ticks < 0:
        raise ValueError("negative Linux process start token")
    try:
        boot_id = (
            Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        )
    except OSError:
        boot_id = "boot-id-unavailable"
    if (
        not boot_id
        or len(boot_id) > 64
        or re.fullmatch(r"[A-Za-z0-9-]+", boot_id) is None
    ):
        boot_id = "boot-id-unavailable"
    return f"linux-{boot_id}-{start_ticks}"


def _windows_process_start_token(process_id: int) -> str:
    from ctypes import wintypes

    class FileTime(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not handle:
        raise OSError("OpenProcess failed")
    try:
        creation = FileTime()
        exit_time = FileTime()
        kernel = FileTime()
        user = FileTime()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise OSError("GetProcessTimes failed")
        value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
        return f"windows-filetime-{value}"
    finally:
        kernel32.CloseHandle(handle)


def _capture_process_start_token(process_id: int) -> str:
    if (
        not isinstance(process_id, int)
        or isinstance(process_id, bool)
        or not 1 <= process_id <= 4_294_967_295
    ):
        raise ValueError("Target process ID is invalid")
    try:
        if sys.platform == "win32":
            return _windows_process_start_token(process_id)
        if sys.platform.startswith("linux"):
            return _linux_process_start_token(process_id)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("Target process start token is unavailable") from exc
    raise ValueError("Target process start tokens are unsupported on this platform")


def capture_resource_telemetry_process_target(
    process_id: int,
    *,
    process_scope: ResourceTelemetryProcessScope,
) -> ResourceTelemetryProcessTarget:
    """Capture a PID-reuse-safe target identity for parent-owned telemetry."""

    live_start_token = _validate_process_start_token(
        _capture_process_start_token(process_id)
    )
    return ResourceTelemetryProcessTarget(
        root_process_id=process_id,
        root_process_start_token_hash=hashlib.sha256(
            live_start_token.encode("utf-8")
        ).hexdigest(),
        process_scope=process_scope,
    )


def _linux_kib_reading(
    path: Path,
    key: str,
    *,
    source: str,
    measurement_scope: ResourceTelemetryMeasurementScope,
    subject_id: str,
    unavailable_reason: str,
) -> ResourceByteReading:
    try:
        for line in path.read_text(encoding="ascii").splitlines():
            name, separator, raw_value = line.partition(":")
            if separator and name == key:
                fields = raw_value.split()
                if len(fields) != 2 or fields[1] != "kB":
                    break
                value = int(fields[0])
                if value < 0:
                    break
                return ResourceByteReading.measured(
                    value * 1024,
                    source=source,
                    measurement_scope=measurement_scope,
                    subject_id=subject_id,
                )
    except (OSError, UnicodeError, ValueError):
        pass
    return ResourceByteReading.unavailable(unavailable_reason)


def _linux_target_process_rss(
    target: ResourceTelemetryProcessTarget,
) -> ResourceByteReading:
    if target.process_scope != "target_root_process":
        return ResourceByteReading.unavailable("process_tree_probe_not_configured")
    try:
        if (
            hashlib.sha256(
                _linux_process_start_token(target.root_process_id).encode("utf-8")
            ).hexdigest()
            != target.root_process_start_token_hash
        ):
            return ResourceByteReading.unavailable("target_process_identity_changed")
        reading = _linux_kib_reading(
            Path(f"/proc/{target.root_process_id}/status"),
            "VmRSS",
            source="linux_procfs_target_process",
            measurement_scope="process_scope_rss",
            subject_id=target.measurement_subject_id,
            unavailable_reason="target_process_rss_probe_unavailable",
        )
        if (
            hashlib.sha256(
                _linux_process_start_token(target.root_process_id).encode("utf-8")
            ).hexdigest()
            != target.root_process_start_token_hash
        ):
            return ResourceByteReading.unavailable("target_process_identity_changed")
        return reading
    except (OSError, UnicodeError, ValueError):
        return ResourceByteReading.unavailable("target_process_rss_probe_unavailable")


def _linux_system_memory_snapshot() -> tuple[ResourceByteReading, ResourceByteReading]:
    path = Path("/proc/meminfo")
    return (
        _linux_kib_reading(
            path,
            "MemTotal",
            source="linux_procfs",
            measurement_scope="system_physical_memory",
            subject_id=_current_system_memory_subject_id(),
            unavailable_reason="system_ram_total_probe_unavailable",
        ),
        _linux_kib_reading(
            path,
            "MemAvailable",
            source="linux_procfs",
            measurement_scope="system_physical_memory",
            subject_id=_current_system_memory_subject_id(),
            unavailable_reason="system_ram_available_probe_unavailable",
        ),
    )


def _windows_target_process_rss(
    target: ResourceTelemetryProcessTarget,
) -> ResourceByteReading:
    if target.process_scope != "target_root_process":
        return ResourceByteReading.unavailable("process_tree_probe_not_configured")
    try:
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x0410, False, target.root_process_id)
        if not handle:
            raise OSError("OpenProcess failed")
        try:
            if (
                hashlib.sha256(
                    _windows_process_start_token(target.root_process_id).encode("utf-8")
                ).hexdigest()
                != target.root_process_start_token_hash
            ):
                return ResourceByteReading.unavailable(
                    "target_process_identity_changed"
                )
            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(
                handle,
                ctypes.byref(counters),
                counters.cb,
            ):
                raise OSError("GetProcessMemoryInfo failed")
            if (
                hashlib.sha256(
                    _windows_process_start_token(target.root_process_id).encode("utf-8")
                ).hexdigest()
                != target.root_process_start_token_hash
            ):
                return ResourceByteReading.unavailable(
                    "target_process_identity_changed"
                )
            return ResourceByteReading.measured(
                int(counters.WorkingSetSize),
                source="windows_psapi_target_process",
                measurement_scope="process_scope_rss",
                subject_id=target.measurement_subject_id,
            )
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return ResourceByteReading.unavailable("target_process_rss_probe_unavailable")


def _windows_system_memory_snapshot() -> tuple[
    ResourceByteReading, ResourceByteReading
]:
    try:
        from ctypes import wintypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MemoryStatusEx)]
        kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL
        memory = MemoryStatusEx()
        memory.dwLength = ctypes.sizeof(memory)
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError("GlobalMemoryStatusEx failed")
        return (
            ResourceByteReading.measured(
                int(memory.ullTotalPhys),
                source="windows_global_memory_status",
                measurement_scope="system_physical_memory",
                subject_id=_current_system_memory_subject_id(),
            ),
            ResourceByteReading.measured(
                int(memory.ullAvailPhys),
                source="windows_global_memory_status",
                measurement_scope="system_physical_memory",
                subject_id=_current_system_memory_subject_id(),
            ),
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return (
            ResourceByteReading.unavailable("system_ram_total_probe_unavailable"),
            ResourceByteReading.unavailable("system_ram_available_probe_unavailable"),
        )


def _portable_target_process_rss(
    target: ResourceTelemetryProcessTarget,
) -> ResourceByteReading:
    del target
    return ResourceByteReading.unavailable("target_process_rss_probe_unavailable")


def _portable_system_memory_snapshot() -> tuple[
    ResourceByteReading, ResourceByteReading
]:
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        total_value = int(os.sysconf("SC_PHYS_PAGES")) * page_size
        available_value = int(os.sysconf("SC_AVPHYS_PAGES")) * page_size
        if min(page_size, total_value, available_value) < 0:
            raise ValueError("negative sysconf memory value")
        return (
            ResourceByteReading.measured(
                total_value,
                source="posix_sysconf",
                measurement_scope="system_physical_memory",
                subject_id=_current_system_memory_subject_id(),
            ),
            ResourceByteReading.measured(
                available_value,
                source="posix_sysconf",
                measurement_scope="system_physical_memory",
                subject_id=_current_system_memory_subject_id(),
            ),
        )
    except (AttributeError, OSError, ValueError):
        return (
            ResourceByteReading.unavailable("system_ram_total_probe_unavailable"),
            ResourceByteReading.unavailable("system_ram_available_probe_unavailable"),
        )


@dataclass(frozen=True)
class _NvidiaSmiReading:
    physical_gpu_uuid: str
    pci_bus_id: str
    used_bytes: int
    total_bytes: int


def _trusted_nvidia_smi_executable() -> Path | None:
    """Resolve nvidia-smi only from a bounded set of system-owned locations."""

    candidates: list[Path] = []
    allowed_parents: set[Path] = set()
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot")
        program_files = os.environ.get("ProgramFiles")
        if system_root:
            system32 = Path(system_root) / "System32"
            candidates.append(system32 / "nvidia-smi.exe")
            allowed_parents.add(system32.resolve(strict=False))
        if program_files:
            nvsmi_dir = Path(program_files) / "NVIDIA Corporation" / "NVSMI"
            candidates.append(nvsmi_dir / "nvidia-smi.exe")
            allowed_parents.add(nvsmi_dir.resolve(strict=False))
    else:
        for parent in (Path("/usr/bin"), Path("/usr/local/bin")):
            candidates.append(parent / "nvidia-smi")
            allowed_parents.add(parent.resolve(strict=False))
    discovered = shutil.which("nvidia-smi")
    if discovered:
        candidates.append(Path(discovered))
    for candidate in candidates:
        try:
            if not candidate.is_absolute() or candidate.is_symlink():
                continue
            resolved = candidate.resolve(strict=True)
            if not resolved.is_file() or resolved.parent not in allowed_parents:
                continue
            return resolved
        except (OSError, RuntimeError):
            continue
    return None


def _validated_nvidia_smi_executable(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("nvidia-smi executable must be an absolute regular file")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("nvidia-smi executable is unavailable") from exc
    if not resolved.is_file():
        raise ValueError("nvidia-smi executable must be an absolute regular file")
    return resolved


def _parse_nvidia_smi_rows(payload: str) -> tuple[_NvidiaSmiReading, ...]:
    if not isinstance(payload, str):
        raise TypeError("nvidia-smi output must be text")
    try:
        encoded = payload.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("nvidia-smi output must be ASCII") from exc
    if not encoded or len(encoded) > RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES:
        raise ValueError("nvidia-smi output is empty or oversized")
    lines = payload.splitlines()
    if not 1 <= len(lines) <= RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_ROWS:
        raise ValueError("nvidia-smi row count is outside its bound")
    rows: list[_NvidiaSmiReading] = []
    for line in lines:
        if not line or len(line) > 512 or "\x00" in line:
            raise ValueError("nvidia-smi row is empty or oversized")
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 4:
            raise ValueError("unexpected nvidia-smi column count")
        physical_gpu_uuid, pci_bus_id, used_mib_text, total_mib_text = fields
        if (
            re.fullmatch(
                r"GPU-[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}",
                physical_gpu_uuid,
            )
            is None
        ):
            raise ValueError("nvidia-smi returned no physical GPU UUID")
        if (
            re.fullmatch(
                r"(?:[0-9A-Fa-f]{8}:)?[0-9A-Fa-f]{2}:"
                r"[0-9A-Fa-f]{2}\.[0-7]",
                pci_bus_id,
            )
            is None
        ):
            raise ValueError("nvidia-smi returned an invalid PCI bus ID")
        if (
            re.fullmatch(r"[0-9]{1,12}", used_mib_text) is None
            or re.fullmatch(r"[0-9]{1,12}", total_mib_text) is None
        ):
            raise ValueError("nvidia-smi returned an invalid memory value")
        used_mib = int(used_mib_text)
        total_mib = int(total_mib_text)
        if min(used_mib, total_mib) < 0 or used_mib > total_mib:
            raise ValueError("invalid nvidia-smi memory row")
        rows.append(
            _NvidiaSmiReading(
                physical_gpu_uuid=physical_gpu_uuid,
                pci_bus_id=pci_bus_id,
                used_bytes=used_mib * 1024 * 1024,
                total_bytes=total_mib * 1024 * 1024,
            )
        )
    uuids = {row.physical_gpu_uuid for row in rows}
    bus_ids = {row.pci_bus_id.lower() for row in rows}
    if not rows or len(uuids) != len(rows) or len(bus_ids) != len(rows):
        raise ValueError(
            "nvidia-smi rows must have unique physical UUID and PCI identities"
        )
    return tuple(rows)


ProcessMemoryReader = Callable[
    [ResourceTelemetryProcessTarget],
    ResourceByteReading,
]


class SystemResourceTelemetryProbe:
    """Cross-platform target probe with exact, optional NVIDIA identity."""

    probe_revision = RESOURCE_TELEMETRY_PROBE_REVISION

    def __init__(
        self,
        *,
        target: ResourceTelemetryProcessTarget,
        cuda_device: ResourceTelemetryCudaDeviceIdentity,
        process_memory_reader: ProcessMemoryReader | None = None,
        nvidia_smi_executable: str | Path | None = None,
    ) -> None:
        self._target = _cold_validate_exact(
            ResourceTelemetryProcessTarget,
            target,
            label="System telemetry process target",
        )
        self._cuda_device = _cold_validate_exact(
            ResourceTelemetryCudaDeviceIdentity,
            cuda_device,
            label="System telemetry CUDA identity",
        )
        if process_memory_reader is not None and not callable(process_memory_reader):
            raise TypeError("Process memory reader must be callable")
        self._process_memory_reader = process_memory_reader
        self._nvidia_smi_executable = (
            _trusted_nvidia_smi_executable()
            if nvidia_smi_executable is None
            else _validated_nvidia_smi_executable(nvidia_smi_executable)
        )

    def _process_rss(self) -> ResourceByteReading:
        try:
            if self._process_memory_reader is not None:
                reading = self._process_memory_reader(self._target)
            elif sys.platform == "win32":
                reading = _windows_target_process_rss(self._target)
            elif sys.platform.startswith("linux"):
                reading = _linux_target_process_rss(self._target)
            else:
                reading = _portable_target_process_rss(self._target)
        except Exception:
            return ResourceByteReading.unavailable("process_memory_reader_exception")
        if not isinstance(reading, ResourceByteReading):
            return ResourceByteReading.unavailable("invalid_process_memory_result")
        try:
            validated = _cold_validate_exact(
                ResourceByteReading,
                reading,
                label="Process memory reading",
            )
            if validated.status == "measured" and (
                validated.measurement_scope != "process_scope_rss"
                or validated.subject_id != self._target.measurement_subject_id
            ):
                return ResourceByteReading.unavailable(
                    "process_memory_subject_mismatch"
                )
            return validated
        except Exception:
            return ResourceByteReading.unavailable("invalid_process_memory_result")

    def _system_memory(self) -> tuple[ResourceByteReading, ResourceByteReading]:
        if sys.platform == "win32":
            return _windows_system_memory_snapshot()
        if sys.platform.startswith("linux"):
            return _linux_system_memory_snapshot()
        return _portable_system_memory_snapshot()

    def _cuda_readings(self) -> tuple[ResourceByteReading, ResourceByteReading]:
        if self._cuda_device.status != "resolved":
            unavailable = ResourceByteReading.unavailable("cuda_identity_unavailable")
            return unavailable, unavailable
        expected_uuid = self._cuda_device.physical_gpu_uuid
        expected_bus = self._cuda_device.pci_bus_id
        if expected_uuid is None or expected_bus is None:
            unavailable = ResourceByteReading.unavailable("cuda_identity_unavailable")
            return unavailable, unavailable
        executable = self._nvidia_smi_executable
        if executable is None:
            unavailable = ResourceByteReading.unavailable("cuda_vram_probe_unavailable")
            return unavailable, unavailable
        try:
            completed = _run_bounded_command(
                [
                    str(executable),
                    "--query-gpu=uuid,pci.bus_id,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ]
            )
            if (
                not isinstance(completed, subprocess.CompletedProcess)
                or not isinstance(completed.returncode, int)
                or isinstance(completed.returncode, bool)
                or not isinstance(completed.stdout, str)
                or not isinstance(completed.stderr, str)
                or len(completed.stderr.encode("utf-8", errors="replace"))
                > RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES
            ):
                raise ValueError("nvidia-smi returned an invalid process result")
            if completed.returncode != 0:
                raise ValueError("nvidia-smi failed")
            matches = [
                row
                for row in _parse_nvidia_smi_rows(completed.stdout)
                if row.physical_gpu_uuid == expected_uuid
            ]
            if len(matches) != 1:
                raise ValueError("configured CUDA UUID is absent or ambiguous")
            selected = matches[0]
            if selected.pci_bus_id.lower() != expected_bus.lower():
                raise ValueError("configured CUDA PCI bus differs")
        except Exception:
            unavailable = ResourceByteReading.unavailable("cuda_vram_probe_unavailable")
            return unavailable, unavailable
        return (
            ResourceByteReading.measured(
                selected.used_bytes,
                source="nvidia_smi_exact_gpu_uuid",
                measurement_scope="cuda_device_memory",
                subject_id=self._cuda_device.measurement_subject_id,
            ),
            ResourceByteReading.measured(
                selected.total_bytes,
                source="nvidia_smi_exact_gpu_uuid",
                measurement_scope="cuda_device_memory",
                subject_id=self._cuda_device.measurement_subject_id,
            ),
        )

    def snapshot(self) -> ResourceTelemetrySnapshot:
        rss = self._process_rss()
        total, available = self._system_memory()
        cuda_used, cuda_total = self._cuda_readings()
        return ResourceTelemetrySnapshot(
            process_scope_rss_bytes=rss,
            system_ram_total_bytes=total,
            system_ram_available_bytes=available,
            cuda_vram_used_bytes=cuda_used,
            cuda_vram_total_bytes=cuda_total,
        )


def serialize_resource_telemetry_artifact(
    artifact: ResourceTelemetryArtifact,
) -> bytes:
    """Return bounded canonical JSON bytes with one trailing newline."""

    validated = ResourceTelemetryArtifact.model_validate(
        artifact.model_dump(mode="python", round_trip=True)
    )
    payload = validated.canonical_json_bytes() + b"\n"
    if len(payload) > RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES:
        raise ValueError("Resource telemetry artifact exceeds its byte limit")
    return payload


def deserialize_resource_telemetry_artifact(
    payload: bytes,
) -> ResourceTelemetryArtifact:
    """Cold-validate bounded canonical bytes; reject equivalent reformatting."""

    if not payload or len(payload) > RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES:
        raise ValueError("Resource telemetry artifact bytes are empty or oversized")
    artifact = ResourceTelemetryArtifact.model_validate_json(payload)
    if serialize_resource_telemetry_artifact(artifact) != payload:
        raise ValueError("Resource telemetry artifact must use canonical JSON bytes")
    return artifact


__all__ = [
    "RESOURCE_TELEMETRY_BACKGROUND_JOIN_MAX_SECONDS",
    "RESOURCE_TELEMETRY_COLLECTOR_REVISION",
    "RESOURCE_TELEMETRY_DEFAULT_CADENCE_SECONDS",
    "RESOURCE_TELEMETRY_MAX_ARTIFACT_BYTES",
    "RESOURCE_TELEMETRY_MAX_CADENCE_SECONDS",
    "RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_OUTPUT_BYTES",
    "RESOURCE_TELEMETRY_MAX_NVIDIA_SMI_ROWS",
    "RESOURCE_TELEMETRY_MAX_SAMPLES",
    "RESOURCE_TELEMETRY_MAX_SOURCE_ARTIFACTS",
    "RESOURCE_TELEMETRY_NVIDIA_SMI_TIMEOUT_SECONDS",
    "RESOURCE_TELEMETRY_PROBE_REVISION",
    "RESOURCE_TELEMETRY_SAMPLING_POLICY",
    "BackgroundResourceTelemetrySample",
    "BackgroundResourceTelemetrySampler",
    "BackgroundResourceTelemetrySamplerResult",
    "BackgroundResourceTelemetrySamplerStatus",
    "BackgroundSamplerState",
    "ProcessMemoryReader",
    "ResourceByteReading",
    "ResourceTelemetryArtifact",
    "ResourceTelemetryCoverageStatus",
    "ResourceTelemetryCudaDeviceIdentity",
    "ResourceTelemetryExecutionStatus",
    "ResourceTelemetryLimitError",
    "ResourceTelemetryMeasurementScope",
    "ResourceTelemetryMetricCoverage",
    "ResourceTelemetryProbe",
    "ResourceTelemetryProcessScope",
    "ResourceTelemetryProcessTarget",
    "ResourceTelemetryProvenance",
    "ResourceTelemetryRuntimeIdentity",
    "ResourceTelemetrySnapshot",
    "ResourceTelemetryStateError",
    "ResourceTelemetryWorkload",
    "SystemResourceTelemetryProbe",
    "UniformResourceTelemetryRecorder",
    "capture_resource_telemetry_process_target",
    "deserialize_resource_telemetry_artifact",
    "serialize_resource_telemetry_artifact",
]
