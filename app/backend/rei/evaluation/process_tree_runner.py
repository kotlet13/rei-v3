"""Bounded child-process execution with hard process-tree cancellation.

The C4 image-model screen cannot rely on an in-process cooperative deadline:
model loading and CUDA kernels may stop reaching Python interruption points.
This module therefore launches one isolated child process and owns the whole
tree until the child exits or a fixed wall-clock/output boundary is reached.

Arbitrary argv, environment values, working-directory paths, and child output
are deliberately excluded from the canonical execution record.  The caller
provides safe identities for those inputs and records exact model/provider
settings in the surrounding provider pipeline artifact.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import ctypes
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from types import MappingProxyType
from typing import Annotated, Any, Literal, Protocol, runtime_checkable

from pydantic import Field, StringConstraints, model_validator

from ..ids import content_id, utc_now
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    UtcTimestamp,
)


PROCESS_TREE_RUNNER_REVISION = "rei-process-tree-runner-v1"
PROCESS_TREE_MAX_TIMEOUT_SECONDS = 86_400.0
PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES = 65_536
PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES = 1_048_576
PROCESS_TREE_DEFAULT_TERMINATION_TIMEOUT_SECONDS = 10.0
_PROCESS_TREE_OBSERVER_SETUP_CALLBACK_MAX_SECONDS = 3.0
_PROCESS_TREE_OBSERVER_LIVE_CALLBACK_MAX_SECONDS = 0.05
_PROCESS_TREE_OBSERVER_POST_TERMINATION_CALLBACK_MAX_SECONDS = 3.0
PROCESS_TREE_MAX_COMMAND_ARGUMENTS = 256
PROCESS_TREE_MAX_COMMAND_UTF8_BYTES = 131_072
PROCESS_TREE_MAX_ENVIRONMENT_VARIABLES = 1_024
PROCESS_TREE_MAX_ENVIRONMENT_UTF8_BYTES = 262_144
PROCESS_TREE_MAX_WORKING_DIRECTORY_UTF8_BYTES = 8_192
PROCESS_TREE_MAX_BOOTSTRAP_PAYLOAD_BYTES = 524_288
_PIPE_CHUNK_BYTES = 65_536
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_SAFE_IDENTITY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,199}$")
_SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")

SafeProcessIdentity = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{0,199}$"),
]
SafeProcessLabel = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$"),
]

ProcessFailureCode = Literal[
    "process_start_failure",
    "process_start_gate_failure",
    "process_timeout",
    "process_stdout_limit_exceeded",
    "process_stderr_limit_exceeded",
    "process_io_failure",
    "process_observer_failure",
    "process_exit_nonzero",
    "process_tree_inspection_failure",
    "process_tree_leak",
    "process_tree_termination_failure",
    "process_containment_close_failure",
]
ProcessExecutionStatus = Literal["succeeded", "failed", "timed_out"]
WorkloadReleaseStatus = Literal["not_attempted", "released", "uncertain"]
ProcessTerminationTrigger = Literal[
    "not_required",
    "start_gate_failure",
    "hard_timeout",
    "stdout_limit",
    "stderr_limit",
    "io_failure",
    "observer_failure",
    "tree_inspection_failure",
    "tree_leak",
    "containment_close_failure",
]


class ProcessStartGateReleaseError(RuntimeError):
    """Sanitized release failure with conservative launch-state provenance."""

    def __init__(self, *, may_have_started: bool) -> None:
        super().__init__("Process start gate failed closed")
        self.may_have_started = may_have_started


class ProcessSpawnError(RuntimeError):
    """Sanitized spawn failure with explicit containment-cleanup state."""

    def __init__(self, *, containment_closed: bool) -> None:
        super().__init__("Process spawn failed closed")
        if type(containment_closed) is not bool:
            raise TypeError("Spawn containment state must be a strict boolean")
        self.containment_closed = containment_closed


def _require_safe_identity(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or _SAFE_IDENTITY.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a sanitized lowercase identity")


def _sanitized_label(value: str, *, fallback: str) -> str:
    return value if _SAFE_LABEL.fullmatch(value) is not None else fallback


def _utf8_size(value: str, *, field_name: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must be valid UTF-8 text") from exc


@dataclass(frozen=True, slots=True)
class BoundedProcessRequest:
    """Runtime-only launch request whose sensitive fields are never serialized.

    ``command_identity``, ``working_directory_identity`` and
    ``environment_identity`` must be sanitized, caller-owned references to
    separately frozen artifacts.  They are not inferred from raw launch data,
    because argv and environment values can contain local paths or secrets.
    """

    workload_id: str
    command_identity: str
    working_directory_identity: str
    environment_identity: str
    command: tuple[str, ...] = field(repr=False)
    working_directory: Path = field(repr=False)
    environment: Mapping[str, str] = field(repr=False)
    timeout_seconds: float
    stdout_limit_bytes: int = PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES
    stderr_limit_bytes: int = PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES

    def __post_init__(self) -> None:
        for field_name in (
            "workload_id",
            "command_identity",
            "working_directory_identity",
            "environment_identity",
        ):
            _require_safe_identity(getattr(self, field_name), field_name=field_name)

        if not isinstance(self.command, tuple) or not self.command:
            raise ValueError("command must be a non-empty tuple")
        if len(self.command) > PROCESS_TREE_MAX_COMMAND_ARGUMENTS:
            raise ValueError("command exceeds the fixed argument-count bound")
        command_size = 0
        for argument in self.command:
            if not isinstance(argument, str) or not argument or "\x00" in argument:
                raise ValueError("command arguments must be non-empty NUL-free strings")
            command_size += (
                _utf8_size(
                    argument,
                    field_name="command argument",
                )
                + 1
            )
        if command_size > PROCESS_TREE_MAX_COMMAND_UTF8_BYTES:
            raise ValueError("command exceeds the fixed UTF-8 byte bound")
        if not Path(self.command[0]).is_absolute():
            raise ValueError("command executable must be an absolute path")

        working_directory = Path(self.working_directory)
        if not working_directory.is_absolute():
            raise ValueError("working_directory must be absolute")
        if (
            _utf8_size(str(working_directory), field_name="working_directory")
            > PROCESS_TREE_MAX_WORKING_DIRECTORY_UTF8_BYTES
        ):
            raise ValueError("working_directory exceeds the fixed UTF-8 byte bound")
        object.__setattr__(self, "working_directory", working_directory)

        environment = dict(self.environment)
        if len(environment) > PROCESS_TREE_MAX_ENVIRONMENT_VARIABLES:
            raise ValueError("environment exceeds the fixed variable-count bound")
        environment_size = 0
        for key, value in environment.items():
            if (
                not isinstance(key, str)
                or not key
                or "\x00" in key
                or "=" in key
                or not isinstance(value, str)
                or "\x00" in value
            ):
                raise ValueError(
                    "environment must contain NUL-free string keys and values"
                )
            environment_size += (
                _utf8_size(
                    key,
                    field_name="environment key",
                )
                + _utf8_size(value, field_name="environment value")
                + 2
            )
        if environment_size > PROCESS_TREE_MAX_ENVIRONMENT_UTF8_BYTES:
            raise ValueError("environment exceeds the fixed UTF-8 byte bound")
        object.__setattr__(self, "environment", MappingProxyType(environment))

        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(float(self.timeout_seconds))
            or not 0.0 < float(self.timeout_seconds) <= PROCESS_TREE_MAX_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout_seconds must be finite and within (0, 86400]")
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))

        for field_name in ("stdout_limit_bytes", "stderr_limit_bytes"):
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES
            ):
                raise ValueError(
                    f"{field_name} must be within [1, "
                    f"{PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES}]"
                )


class ProcessOutputSummary(FrozenModel):
    """Bounded bytes observed by one drain thread.

    ``sha256`` covers every byte observed by the reader.  It is a whole-stream
    digest only when ``stream_complete`` is true; a forced seal deliberately
    preserves the stable observed prefix without claiming unseen bytes.
    """

    byte_count: int = Field(ge=0, le=0x7FFFFFFFFFFFFFFF)
    captured_byte_count: int = Field(
        ge=0,
        le=PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES,
    )
    sha256: HashDigest
    captured_sha256: HashDigest
    truncated: bool
    stream_complete: bool

    @model_validator(mode="after")
    def validate_summary(self) -> ProcessOutputSummary:
        if type(self.stream_complete) is not bool:
            raise TypeError("Process output completeness must be a strict boolean")
        if self.captured_byte_count > self.byte_count:
            raise ValueError("Captured process output cannot exceed total output")
        if self.truncated != (self.captured_byte_count < self.byte_count):
            raise ValueError("Process output truncation flag differs from byte counts")
        if not self.truncated and self.captured_sha256 != self.sha256:
            raise ValueError("Complete process output hashes must match")
        if self.captured_byte_count == 0 and self.captured_sha256 != _EMPTY_SHA256:
            raise ValueError("Empty captured process output has the wrong hash")
        if self.byte_count == 0 and self.sha256 != _EMPTY_SHA256:
            raise ValueError("Empty process output has the wrong hash")
        return self


class ProcessTreeExecutionRecord(FrozenArtifactModel):
    """Sanitized, content-addressed provenance for exactly one child attempt."""

    schema_version: Literal["rei-process-tree-execution-v1"] = (
        "rei-process-tree-execution-v1"
    )
    record_id: NonEmptyId
    runner_revision: Literal["rei-process-tree-runner-v1"] = (
        PROCESS_TREE_RUNNER_REVISION
    )
    workload_id: SafeProcessIdentity
    command_identity: SafeProcessIdentity
    argument_count: int = Field(ge=0, le=PROCESS_TREE_MAX_COMMAND_ARGUMENTS - 1)
    working_directory_identity: SafeProcessIdentity
    environment_identity: SafeProcessIdentity
    timeout_seconds: float = Field(gt=0.0, le=PROCESS_TREE_MAX_TIMEOUT_SECONDS)
    stdout_limit_bytes: int = Field(ge=1, le=PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES)
    stderr_limit_bytes: int = Field(ge=1, le=PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES)
    platform_system: SafeProcessLabel
    isolation_mode: SafeProcessIdentity
    target_start_token_hash: HashDigest | None = None
    target_process_group_id: int | None = Field(default=None, gt=0, le=0xFFFFFFFF)
    target_session_id: int | None = Field(default=None, gt=0, le=0xFFFFFFFF)
    started_at: UtcTimestamp
    finished_at: UtcTimestamp
    elapsed_monotonic_seconds: float = Field(ge=0.0)
    workload_elapsed_monotonic_seconds: float = Field(ge=0.0)
    workload_timing_scope: Literal[
        "not_observed_no_release_attempt",
        "release_attempt_to_confirmed_empty_tree_upper_bound",
        "release_attempt_to_runner_finish_unconfirmed_interval",
    ]
    process_id: int | None = Field(default=None, gt=0, le=0xFFFFFFFF)
    workload_released: bool
    workload_release_status: WorkloadReleaseStatus
    exit_code: int | None = Field(default=None, ge=-0x80000000, le=0xFFFFFFFF)
    status: ProcessExecutionStatus
    termination_trigger: ProcessTerminationTrigger
    failure_code: ProcessFailureCode | None = None
    failure_message: NonEmptyText | None = None
    stdout: ProcessOutputSummary
    stderr: ProcessOutputSummary
    tree_termination_requested: bool
    tree_termination_succeeded: bool | None = None
    tree_termination_method: SafeProcessIdentity | None = None
    tree_inspection_method: SafeProcessIdentity | None = None
    final_active_processes: int | None = Field(default=None, ge=0, le=4096)
    target_identity_confirmed: bool | None = None
    empty_tree_confirmed: bool
    containment_closed: bool
    observer_callback_failed: bool
    fallback_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_execution(self) -> ProcessTreeExecutionRecord:
        for label, summary in (("stdout", self.stdout), ("stderr", self.stderr)):
            try:
                ProcessOutputSummary.model_validate(
                    summary.model_dump(mode="python", round_trip=True)
                )
            except Exception as exc:
                raise ValueError(f"Process {label} summary is invalid") from exc
        if self.finished_at < self.started_at:
            raise ValueError("Process execution cannot finish before it starts")
        if self.workload_elapsed_monotonic_seconds > self.elapsed_monotonic_seconds:
            raise ValueError("Workload time cannot exceed total process-runner time")
        if self.workload_released != (self.workload_release_status == "released"):
            raise ValueError("Workload release boolean differs from release status")
        if self.workload_release_status == "not_attempted":
            if self.workload_elapsed_monotonic_seconds != 0:
                raise ValueError("Unattempted workload cannot contain workload time")
            if self.workload_timing_scope != "not_observed_no_release_attempt":
                raise ValueError(
                    "Unattempted workload requires a no-release timing scope"
                )
        else:
            expected_timing_scope = (
                "release_attempt_to_confirmed_empty_tree_upper_bound"
                if self.empty_tree_confirmed
                else "release_attempt_to_runner_finish_unconfirmed_interval"
            )
            if self.workload_timing_scope != expected_timing_scope:
                raise ValueError(
                    "Workload timing scope differs from final empty-tree evidence"
                )
        if (
            self.workload_release_status == "uncertain"
            and self.termination_trigger != "start_gate_failure"
        ):
            raise ValueError("Uncertain workload release requires a start-gate failure")
        if self.termination_trigger == "start_gate_failure" and (
            self.process_id is None or self.workload_release_status == "released"
        ):
            raise ValueError("Start-gate trigger requires an unreleased child")
        if self.argument_count < 0:
            raise ValueError("Process argument count cannot be negative")
        if self.stdout.captured_byte_count != min(
            self.stdout.byte_count,
            self.stdout_limit_bytes,
        ):
            raise ValueError("Captured stdout differs from its configured byte limit")
        if self.stderr.captured_byte_count != min(
            self.stderr.byte_count,
            self.stderr_limit_bytes,
        ):
            raise ValueError("Captured stderr differs from its configured byte limit")
        if (self.target_process_group_id is None) != (self.target_session_id is None):
            raise ValueError("Process group and session identity must be paired")
        if self.process_id is not None:
            if self.isolation_mode == "windows_job_object_kill_on_close" and (
                self.target_process_group_id is not None
                or self.target_session_id is not None
            ):
                raise ValueError("Windows Job targets cannot carry POSIX identity")
            if self.isolation_mode == "posix_process_group_non_authoritative":
                raise ValueError(
                    "Non-authoritative POSIX mode cannot publish a started process"
                )

        if self.status == "succeeded":
            if (
                self.exit_code != 0
                or self.process_id is None
                or not self.workload_released
                or self.failure_code is not None
                or self.failure_message is not None
                or self.termination_trigger != "not_required"
                or self.tree_termination_requested
                or not self.empty_tree_confirmed
                or self.target_identity_confirmed is not True
                or not self.containment_closed
                or self.observer_callback_failed
                or self.stdout.truncated
                or self.stderr.truncated
                or not self.stdout.stream_complete
                or not self.stderr.stream_complete
            ):
                raise ValueError("Successful process record contains failure state")
        else:
            if self.failure_code is None or self.failure_message != (
                f"Bounded process failed closed ({self.failure_code})"
            ):
                raise ValueError(
                    "Failed process record requires a fixed failure message"
                )

        if self.status == "timed_out" and (
            self.failure_code != "process_timeout"
            or self.termination_trigger != "hard_timeout"
        ):
            raise ValueError("Timed-out process record has inconsistent failure state")
        if self.failure_code == "process_timeout" and self.status != "timed_out":
            raise ValueError("Process timeout code requires timed_out status")

        if self.failure_code == "process_start_failure" and (
            self.process_id is not None
            or self.workload_released
            or self.exit_code is not None
            or self.termination_trigger != "not_required"
        ):
            raise ValueError("Process start failure contains child execution state")
        if self.failure_code == "process_start_gate_failure" and (
            self.process_id is None
            or self.workload_released
            or self.workload_release_status == "released"
            or self.termination_trigger != "start_gate_failure"
        ):
            raise ValueError("Process start-gate failure has inconsistent state")
        if self.failure_code == "process_exit_nonzero" and (
            self.process_id is None
            or self.exit_code in {None, 0}
            or self.termination_trigger != "not_required"
        ):
            raise ValueError("Nonzero process failure has inconsistent exit state")
        if self.failure_code == "process_stdout_limit_exceeded" and (
            self.termination_trigger != "stdout_limit"
            or not self.stdout.truncated
            or self.stdout.byte_count <= self.stdout_limit_bytes
        ):
            raise ValueError("Stdout-limit failure has inconsistent output state")
        if self.failure_code == "process_stderr_limit_exceeded" and (
            self.termination_trigger != "stderr_limit"
            or not self.stderr.truncated
            or self.stderr.byte_count <= self.stderr_limit_bytes
        ):
            raise ValueError("Stderr-limit failure has inconsistent output state")
        if self.failure_code == "process_io_failure" and (
            self.termination_trigger != "io_failure"
        ):
            raise ValueError("Process I/O failure has inconsistent trigger")
        if self.failure_code == "process_observer_failure" and (
            self.termination_trigger != "observer_failure"
            or not self.observer_callback_failed
        ):
            raise ValueError("Process observer failure has inconsistent trigger")
        if self.failure_code == "process_tree_inspection_failure" and (
            self.termination_trigger != "tree_inspection_failure"
        ):
            raise ValueError("Tree-inspection failure has inconsistent trigger")
        if self.failure_code == "process_tree_leak" and (
            self.termination_trigger != "tree_leak" or not self.empty_tree_confirmed
        ):
            raise ValueError("Process-tree leak was not closed and confirmed")
        if self.failure_code == "process_containment_close_failure" and (
            self.containment_closed
            or self.termination_trigger == "not_required"
            or (
                not self.tree_termination_requested
                and self.termination_trigger != "containment_close_failure"
            )
        ):
            raise ValueError("Containment-close failure has inconsistent state")
        if self.failure_code == "process_tree_termination_failure" and (
            not self.tree_termination_requested
            or self.tree_termination_succeeded is not False
        ):
            raise ValueError("Tree-termination failure is not proven")

        if self.termination_trigger == "stdout_limit" and (
            not self.stdout.truncated
            or self.stdout.byte_count <= self.stdout_limit_bytes
        ):
            raise ValueError("Stdout trigger lacks an observed byte-limit breach")
        if self.termination_trigger == "stderr_limit" and (
            not self.stderr.truncated
            or self.stderr.byte_count <= self.stderr_limit_bytes
        ):
            raise ValueError("Stderr trigger lacks an observed byte-limit breach")
        if (
            self.termination_trigger == "observer_failure"
            and not self.observer_callback_failed
        ):
            raise ValueError("Observer trigger lacks an observer-failure marker")

        if self.tree_termination_requested:
            if (
                self.termination_trigger == "not_required"
                or self.tree_termination_succeeded is None
                or self.tree_termination_method is None
            ):
                raise ValueError("Tree termination provenance is incomplete")
            if self.tree_termination_succeeded != self.empty_tree_confirmed:
                raise ValueError(
                    "Tree termination success differs from final empty-tree proof"
                )
        elif (
            self.tree_termination_succeeded is not None
            or self.tree_termination_method is not None
        ):
            raise ValueError("Unrequested tree termination contains termination state")

        if self.process_id is None:
            if self.workload_release_status != "not_attempted":
                raise ValueError("Unstarted process cannot release a workload")
            if any(
                value is not None
                for value in (
                    self.target_start_token_hash,
                    self.target_process_group_id,
                    self.target_session_id,
                    self.tree_inspection_method,
                    self.final_active_processes,
                    self.target_identity_confirmed,
                )
            ):
                raise ValueError("Unstarted process contains target or tree state")
        elif (
            self.target_start_token_hash is None
            or self.tree_inspection_method is None
            or self.target_identity_confirmed is None
        ):
            raise ValueError("Started process lacks PID-safe tree identity evidence")
        if self.empty_tree_confirmed != (
            self.final_active_processes == 0 and self.target_identity_confirmed is True
        ):
            raise ValueError(
                "Empty-tree confirmation differs from active process count"
            )
        if self.workload_release_status != "released" and self.process_id is not None:
            if not self.tree_termination_requested:
                raise ValueError("Unreleased workload lacks tree termination")
            if (
                self.tree_termination_succeeded is False
                and self.failure_code != "process_tree_termination_failure"
            ):
                raise ValueError("Unreleased workload termination is unproven")
            if (
                self.tree_termination_succeeded is True
                and not self.empty_tree_confirmed
            ):
                raise ValueError("Unreleased workload lacks empty-tree proof")

        expected_id = content_id(
            "process_execution",
            self.model_dump(mode="python", round_trip=True, exclude={"record_id"}),
        )
        if self.record_id != expected_id:
            raise ValueError("Process execution record ID differs from content")
        return self


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    record: ProcessTreeExecutionRecord
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.record, ProcessTreeExecutionRecord):
            raise TypeError("record must be a ProcessTreeExecutionRecord")
        ProcessTreeExecutionRecord.model_validate(
            self.record.model_dump(mode="python", round_trip=True)
        )
        if type(self.stdout) is not bytes or type(self.stderr) is not bytes:
            raise TypeError("Captured process output must use exact bytes")
        if len(self.stdout) != self.record.stdout.captured_byte_count:
            raise ValueError("Captured stdout differs from execution provenance")
        if len(self.stderr) != self.record.stderr.captured_byte_count:
            raise ValueError("Captured stderr differs from execution provenance")
        if (
            hashlib.sha256(self.stdout).hexdigest()
            != self.record.stdout.captured_sha256
        ):
            raise ValueError("Captured stdout hash differs from execution provenance")
        if (
            hashlib.sha256(self.stderr).hexdigest()
            != self.record.stderr.captured_sha256
        ):
            raise ValueError("Captured stderr hash differs from execution provenance")

    @property
    def succeeded(self) -> bool:
        return self.record.status == "succeeded"


@dataclass(frozen=True, slots=True)
class ProcessTarget:
    pid: int
    start_token: str = field(repr=False)
    start_token_hash: str
    process_group_id: int | None = None
    session_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.pid) is not int or not 0 < self.pid <= 0xFFFFFFFF:
            raise ValueError("Process target PID is outside the fixed platform bound")
        if (
            type(self.start_token) is not str
            or not self.start_token
            or len(self.start_token.encode("utf-8")) > 512
            or "\x00" in self.start_token
        ):
            raise ValueError("Process target requires a positive PID and start token")
        if _SAFE_LABEL.fullmatch(self.start_token) is None:
            raise ValueError("Process target start token must be a bounded safe label")
        if _SAFE_IDENTITY.fullmatch(self.start_token_hash) is None:
            raise ValueError("Process target start-token hash must be sanitized")
        expected = hashlib.sha256(self.start_token.encode("utf-8")).hexdigest()
        if self.start_token_hash != expected:
            raise ValueError("Process target start-token hash differs from content")
        if (self.process_group_id is None) != (self.session_id is None):
            raise ValueError("Process group and session identity must be paired")
        for value in (self.process_group_id, self.session_id):
            if value is not None and (
                type(value) is not int or not 0 < value <= 0xFFFFFFFF
            ):
                raise ValueError("Process group and session IDs are outside bounds")


@dataclass(slots=True)
class _ProcessStartGate:
    pipe: Any = field(repr=False)
    released: bool = False
    closed: bool = False
    deadline_monotonic_ns: int | None = field(default=None, repr=False)

    def close(self) -> None:
        if self.closed:
            return
        try:
            self.pipe.close()
        finally:
            self.closed = True

    def close_safely(self) -> None:
        try:
            self.close()
        except Exception:
            pass


@dataclass(frozen=True, slots=True)
class ManagedProcess:
    process: Any
    target: ProcessTarget
    containment: Any = field(repr=False, default=None)
    start_gate: Any = field(repr=False, default=None)


@dataclass(frozen=True, slots=True)
class TreeInspectionOutcome:
    method: str
    inspection_succeeded: bool
    target_identity_confirmed: bool
    active_processes: int | None
    empty_tree_confirmed: bool
    root_exit_accounting_pending: bool = False

    def __post_init__(self) -> None:
        _require_safe_identity(self.method, field_name="inspection method")
        for field_name in (
            "inspection_succeeded",
            "target_identity_confirmed",
            "empty_tree_confirmed",
            "root_exit_accounting_pending",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a strict boolean")
        if self.active_processes is not None and (
            type(self.active_processes) is not int or self.active_processes < 0
        ):
            raise ValueError("Active process count cannot be negative")
        if self.empty_tree_confirmed != (
            self.inspection_succeeded
            and self.target_identity_confirmed
            and self.active_processes == 0
        ):
            raise ValueError("Empty-tree confirmation lacks exact inspection evidence")
        if self.root_exit_accounting_pending and (
            not self.inspection_succeeded
            or not self.target_identity_confirmed
            or self.active_processes in {None, 0}
            or self.empty_tree_confirmed
        ):
            raise ValueError("Root-exit accounting state is inconsistent")


@dataclass(frozen=True, slots=True)
class TreeTerminationOutcome:
    method: str
    succeeded: bool
    final_inspection: TreeInspectionOutcome

    def __post_init__(self) -> None:
        _require_safe_identity(self.method, field_name="termination method")
        if type(self.succeeded) is not bool:
            raise TypeError("Tree termination success must be a strict boolean")
        if not isinstance(self.final_inspection, TreeInspectionOutcome):
            raise TypeError("Tree termination requires an inspection outcome")
        if self.succeeded != self.final_inspection.empty_tree_confirmed:
            raise ValueError("Tree termination success requires confirmed empty tree")


@dataclass(frozen=True, slots=True)
class ProcessLifecycleContext:
    workload_id: str
    target: ProcessTarget
    isolation_mode: str
    process_tree_rss_source: str | None = None
    _process_tree_rss_reader: Callable[[], int] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        _require_safe_identity(self.workload_id, field_name="workload ID")
        if not isinstance(self.target, ProcessTarget):
            raise TypeError("Lifecycle context requires a process target")
        _require_safe_identity(self.isolation_mode, field_name="isolation mode")
        if (self.process_tree_rss_source is None) != (
            self._process_tree_rss_reader is None
        ):
            raise ValueError(
                "Process-tree RSS source and runtime reader must be paired"
            )
        if self.process_tree_rss_source is not None:
            _require_safe_identity(
                self.process_tree_rss_source,
                field_name="process-tree RSS source",
            )
        if self._process_tree_rss_reader is not None and not callable(
            self._process_tree_rss_reader
        ):
            raise TypeError("Process-tree RSS reader must be callable")

    @property
    def process_tree_rss_available(self) -> bool:
        return self._process_tree_rss_reader is not None

    def read_process_tree_rss_bytes(self) -> int:
        """Return one bounded authoritative tree working-set observation."""

        if self._process_tree_rss_reader is None:
            raise RuntimeError("Authoritative process-tree RSS reader is unavailable")
        value = self._process_tree_rss_reader()
        if type(value) is not int or not 0 <= value <= 0x7FFFFFFFFFFFFFFF:
            raise ValueError("Process-tree RSS reading is outside the fixed byte bound")
        return value


@runtime_checkable
class ProcessLifecycleObserver(Protocol):
    """Trusted lifecycle callbacks executed behind a bounded daemon boundary.

    A callback that raises or exceeds the smaller of the fixed callback budget
    and the workload deadline fails closed.  Its daemon thread can finish later,
    but it cannot delay workload release or process-tree termination.
    """

    def on_started(self, context: ProcessLifecycleContext) -> None: ...

    def on_poll(self, context: ProcessLifecycleContext) -> None: ...

    def after_natural_completion(
        self,
        context: ProcessLifecycleContext,
        outcome: TreeInspectionOutcome,
    ) -> None: ...

    def before_termination(
        self,
        context: ProcessLifecycleContext,
        trigger: ProcessTerminationTrigger,
    ) -> None: ...

    def after_termination(
        self,
        context: ProcessLifecycleContext,
        outcome: TreeTerminationOutcome,
    ) -> None: ...


class NullProcessLifecycleObserver:
    def on_started(self, context: ProcessLifecycleContext) -> None:
        del context

    def on_poll(self, context: ProcessLifecycleContext) -> None:
        del context

    def after_natural_completion(
        self,
        context: ProcessLifecycleContext,
        outcome: TreeInspectionOutcome,
    ) -> None:
        del context, outcome

    def before_termination(
        self,
        context: ProcessLifecycleContext,
        trigger: ProcessTerminationTrigger,
    ) -> None:
        del context, trigger

    def after_termination(
        self,
        context: ProcessLifecycleContext,
        outcome: TreeTerminationOutcome,
    ) -> None:
        del context, outcome


@runtime_checkable
class ProcessTreeAdapter(Protocol):
    @property
    def isolation_mode(self) -> str: ...

    def spawn(self, request: BoundedProcessRequest) -> ManagedProcess: ...

    def release_start_gate(
        self,
        managed: ManagedProcess,
        request: BoundedProcessRequest,
    ) -> None: ...

    def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome: ...

    def terminate_tree(
        self,
        managed: ManagedProcess,
        *,
        timeout_seconds: float,
    ) -> TreeTerminationOutcome: ...

    def close_containment(self, managed: ManagedProcess) -> bool: ...


class _JobObjectBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JobObjectBasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", ctypes.c_uint32),
        ("TotalProcesses", ctypes.c_uint32),
        ("ActiveProcesses", ctypes.c_uint32),
        ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


class _JobObjectBasicProcessIdList(ctypes.Structure):
    _fields_ = [
        ("NumberOfAssignedProcesses", ctypes.c_uint32),
        ("NumberOfProcessIdsInList", ctypes.c_uint32),
        ("ProcessIdList", ctypes.c_size_t * 4096),
    ]


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
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


@dataclass(slots=True)
class _WindowsJobHandle:
    value: int
    closed: bool = False


class CtypesWindowsJobApi:
    """Small injectable Win32 Job Object boundary used by the runner."""

    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
    _JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _PROCESS_QUERY_INFORMATION = 0x0400
    _PROCESS_VM_READ = 0x0010

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Win32 Job Objects are available only on Windows")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._psapi = ctypes.WinDLL("psapi", use_last_error=True)
        self._kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        self._kernel32.SetInformationJobObject.restype = ctypes.c_int
        self._kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        self._kernel32.QueryInformationJobObject.restype = ctypes.c_int
        self._kernel32.TerminateJobObject.restype = ctypes.c_int
        self._kernel32.GetProcessTimes.restype = ctypes.c_int
        self._kernel32.OpenProcess.restype = ctypes.c_void_p
        self._kernel32.IsProcessInJob.restype = ctypes.c_int
        self._kernel32.CloseHandle.restype = ctypes.c_int
        self._psapi.GetProcessMemoryInfo.restype = ctypes.c_int

    @staticmethod
    def _raise_last_error(operation: str) -> None:
        error_code = ctypes.get_last_error()
        raise OSError(error_code, f"Win32 Job Object operation failed: {operation}")

    def create_kill_on_close_job(self) -> _WindowsJobHandle:
        raw_handle = self._kernel32.CreateJobObjectW(None, None)
        if not raw_handle:
            self._raise_last_error("create")
        job = _WindowsJobHandle(value=int(raw_handle))
        information = _JobObjectExtendedLimitInformation()
        information.BasicLimitInformation.LimitFlags = (
            self._JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if not self._kernel32.SetInformationJobObject(
            ctypes.c_void_p(job.value),
            self._JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            self.close(job)
            self._raise_last_error("set_kill_on_close")
        return job

    def assign(self, job: _WindowsJobHandle, process: Any) -> None:
        process_handle = ctypes.c_void_p(int(process._handle))
        if not self._kernel32.AssignProcessToJobObject(
            ctypes.c_void_p(job.value), process_handle
        ):
            self._raise_last_error("assign")

    def process_start_token(self, process: Any) -> str:
        creation = _FileTime()
        exit_time = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        if not self._kernel32.GetProcessTimes(
            ctypes.c_void_p(int(process._handle)),
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            self._raise_last_error("process_start_token")
        value = (int(creation.high) << 32) | int(creation.low)
        return f"windows-filetime-{value}"

    def active_processes(self, job: _WindowsJobHandle) -> int:
        information = _JobObjectBasicAccountingInformation()
        if not self._kernel32.QueryInformationJobObject(
            ctypes.c_void_p(job.value),
            self._JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
            None,
        ):
            self._raise_last_error("query_accounting")
        return int(information.ActiveProcesses)

    def active_process_ids(self, job: _WindowsJobHandle) -> tuple[int, ...]:
        information = _JobObjectBasicProcessIdList()
        if not self._kernel32.QueryInformationJobObject(
            ctypes.c_void_p(job.value),
            self._JOB_OBJECT_BASIC_PROCESS_ID_LIST,
            ctypes.byref(information),
            ctypes.sizeof(information),
            None,
        ):
            self._raise_last_error("query_process_ids")
        return self._validated_process_ids(information)

    @staticmethod
    def _validated_process_ids(
        information: _JobObjectBasicProcessIdList,
    ) -> tuple[int, ...]:
        assigned_count = int(information.NumberOfAssignedProcesses)
        listed_count = int(information.NumberOfProcessIdsInList)
        capacity = len(information.ProcessIdList)
        if assigned_count > capacity or listed_count > capacity:
            raise RuntimeError("Windows Job Object process list exceeds fixed bound")
        if assigned_count != listed_count:
            raise RuntimeError("Windows Job Object process list is incomplete")
        process_ids = tuple(
            int(information.ProcessIdList[index]) for index in range(listed_count)
        )
        if len(set(process_ids)) != len(process_ids) or any(
            not 0 < process_id <= 0xFFFFFFFF for process_id in process_ids
        ):
            raise RuntimeError("Windows Job Object returned invalid process IDs")
        return process_ids

    def _process_working_set_bytes(
        self,
        job: _WindowsJobHandle,
        process_id: int,
    ) -> int:
        raw_handle = self._kernel32.OpenProcess(
            self._PROCESS_QUERY_INFORMATION | self._PROCESS_VM_READ,
            False,
            process_id,
        )
        if not raw_handle:
            self._raise_last_error("open_process_for_working_set")
        process_handle = ctypes.c_void_p(raw_handle)
        try:
            in_job = ctypes.c_int()
            if not self._kernel32.IsProcessInJob(
                process_handle,
                ctypes.c_void_p(job.value),
                ctypes.byref(in_job),
            ):
                self._raise_last_error("verify_process_job_membership")
            if not in_job.value:
                raise RuntimeError("Process is no longer in the owned Job Object")
            counters = _ProcessMemoryCountersEx()
            counters.cb = ctypes.sizeof(counters)
            if not self._psapi.GetProcessMemoryInfo(
                process_handle,
                ctypes.byref(counters),
                counters.cb,
            ):
                self._raise_last_error("query_process_working_set")
            return int(counters.WorkingSetSize)
        finally:
            if not self._kernel32.CloseHandle(process_handle):
                self._raise_last_error("close_process_working_set_handle")

    def process_tree_rss_bytes(self, job: _WindowsJobHandle) -> int:
        """Sum current working sets for one stable, exact Job membership set."""

        before = tuple(sorted(self.active_process_ids(job)))
        total = sum(
            self._process_working_set_bytes(job, process_id) for process_id in before
        )
        after = tuple(sorted(self.active_process_ids(job)))
        if after != before:
            raise RuntimeError("Windows Job membership changed during RSS sampling")
        if not 0 <= total <= 0x7FFFFFFFFFFFFFFF:
            raise RuntimeError("Windows Job working-set sum exceeds the fixed bound")
        return total

    def terminate(self, job: _WindowsJobHandle) -> None:
        if not self._kernel32.TerminateJobObject(ctypes.c_void_p(job.value), 0xC4):
            self._raise_last_error("terminate")

    def close(self, job: _WindowsJobHandle) -> None:
        if job.closed:
            return
        if not self._kernel32.CloseHandle(ctypes.c_void_p(job.value)):
            self._raise_last_error("close")
        job.closed = True


@dataclass(frozen=True, slots=True)
class _PosixProcessEntry:
    pid: int
    process_group_id: int
    session_id: int
    start_token: str


class PosixProcessTreeInspector:
    """Diagnostic-only POSIX session inspection with PID-start protection.

    This helper never grants an authoritative launch or signal boundary; the
    platform adapter refuses POSIX workload creation before ``Popen``.
    """

    def __init__(
        self,
        *,
        proc_root: Path = Path("/proc"),
        process_group_probe: Callable[[int, int], None] | None = None,
    ) -> None:
        self._proc_root = proc_root
        self._process_group_probe = process_group_probe or getattr(os, "killpg", None)
        self._boot_id = self._read_boot_id()

    def _read_boot_id(self) -> str:
        try:
            value = (
                (self._proc_root / "sys/kernel/random/boot_id")
                .read_text(encoding="ascii")
                .strip()
            )
        except OSError:
            return "boot-id-unavailable"
        return value or "boot-id-unavailable"

    def create_target(self, pid: int) -> ProcessTarget:
        entries = self._entries()
        entry = next((item for item in entries if item.pid == pid), None)
        if entry is None:
            raise RuntimeError("Spawned POSIX process vanished before identity capture")
        if entry.process_group_id != pid or entry.session_id != pid:
            raise RuntimeError("Spawned POSIX process lacks isolated session identity")
        return ProcessTarget(
            pid=pid,
            start_token=entry.start_token,
            start_token_hash=hashlib.sha256(
                entry.start_token.encode("utf-8")
            ).hexdigest(),
            process_group_id=entry.process_group_id,
            session_id=entry.session_id,
        )

    def inspect(self, target: ProcessTarget) -> TreeInspectionOutcome:
        try:
            entries = self._entries()
        except Exception:
            return TreeInspectionOutcome(
                method="posix_session_membership",
                inspection_succeeded=False,
                target_identity_confirmed=False,
                active_processes=None,
                empty_tree_confirmed=False,
            )
        members = tuple(
            entry
            for entry in entries
            if entry.process_group_id == target.process_group_id
            and entry.session_id == target.session_id
        )
        reused_target = next(
            (
                entry
                for entry in entries
                if entry.pid == target.pid and entry.start_token != target.start_token
            ),
            None,
        )
        identity_confirmed = reused_target is None
        active = len(members)
        if active == 0:
            if self._process_group_probe is None:
                return TreeInspectionOutcome(
                    method="posix_session_membership",
                    inspection_succeeded=False,
                    target_identity_confirmed=identity_confirmed,
                    active_processes=None,
                    empty_tree_confirmed=False,
                )
            try:
                self._process_group_probe(target.process_group_id, 0)
            except ProcessLookupError:
                return TreeInspectionOutcome(
                    method="posix_session_membership_signal_zero",
                    inspection_succeeded=True,
                    target_identity_confirmed=identity_confirmed,
                    active_processes=0,
                    empty_tree_confirmed=identity_confirmed,
                )
            except OSError:
                return TreeInspectionOutcome(
                    method="posix_session_membership_signal_zero",
                    inspection_succeeded=False,
                    target_identity_confirmed=identity_confirmed,
                    active_processes=None,
                    empty_tree_confirmed=False,
                )

            # A live group with no member in the captured session either
            # escaped enumeration or is a reused PGID. A different enumerated
            # session proves reuse; an unenumerated group remains uncertain.
            group_reused = any(
                entry.process_group_id == target.process_group_id
                and entry.session_id != target.session_id
                for entry in entries
            )
            return TreeInspectionOutcome(
                method="posix_session_membership_signal_zero",
                inspection_succeeded=group_reused,
                target_identity_confirmed=False if group_reused else identity_confirmed,
                active_processes=0 if group_reused else None,
                empty_tree_confirmed=False,
            )
        return TreeInspectionOutcome(
            method="posix_session_membership",
            inspection_succeeded=True,
            target_identity_confirmed=identity_confirmed,
            active_processes=active,
            empty_tree_confirmed=identity_confirmed and active == 0,
        )

    def _entries(self) -> tuple[_PosixProcessEntry, ...]:
        if self._proc_root.is_dir() and (self._proc_root / "self/stat").exists():
            return self._proc_entries()
        raise RuntimeError(
            "POSIX process-tree proof requires /proc start-token semantics"
        )

    def _proc_entries(self) -> tuple[_PosixProcessEntry, ...]:
        entries: list[_PosixProcessEntry] = []
        for path in self._proc_root.iterdir():
            if not path.name.isdigit():
                continue
            try:
                raw = (path / "stat").read_text(encoding="utf-8")
                closing = raw.rfind(")")
                fields = raw[closing + 2 :].split()
                pid = int(raw[: raw.find("(")].strip())
                process_group_id = int(fields[2])
                session_id = int(fields[3])
                start_ticks = fields[19]
            except (OSError, ValueError, IndexError):
                continue
            entries.append(
                _PosixProcessEntry(
                    pid=pid,
                    process_group_id=process_group_id,
                    session_id=session_id,
                    start_token=f"linux-{self._boot_id}-{start_ticks}",
                )
            )
        return tuple(entries)


class PlatformProcessTreeAdapter:
    """Own an authoritative Win32 Job Object; refuse POSIX workload launch."""

    _WINDOWS_NEW_PROCESS_GROUP = 0x00000200
    _WINDOWS_NO_WINDOW = 0x08000000

    def __init__(
        self,
        *,
        os_name: str | None = None,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        windows_job_api: Any | None = None,
        posix_inspector: PosixProcessTreeInspector | None = None,
        killpg: Callable[[int, int], None] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        selected = os.name if os_name is None else os_name
        if selected not in {"nt", "posix"}:
            raise ValueError("Process-tree adapter supports only nt and posix")
        self._os_name = selected
        self._popen_factory = popen_factory
        self._windows_job_api = windows_job_api
        self._posix_inspector = posix_inspector
        self._killpg = killpg or getattr(os, "killpg", None)
        self._monotonic = monotonic

    @property
    def isolation_mode(self) -> str:
        return (
            "windows_job_object_kill_on_close"
            if self._os_name == "nt"
            else "posix_process_group_non_authoritative"
        )

    def _job_api(self) -> Any:
        if self._windows_job_api is None:
            self._windows_job_api = CtypesWindowsJobApi()
        return self._windows_job_api

    @property
    def process_tree_rss_source(self) -> str | None:
        if self._os_name == "nt":
            return "windows_job_object_working_set_sum"
        return None

    def process_tree_rss_bytes(self, managed: ManagedProcess) -> int:
        if self._os_name != "nt":
            raise RuntimeError("Authoritative POSIX process-tree RSS is unavailable")
        value = self._job_api().process_tree_rss_bytes(managed.containment)
        if type(value) is not int or not 0 <= value <= 0x7FFFFFFFFFFFFFFF:
            raise RuntimeError("Windows Job RSS probe returned an invalid value")
        return value

    def _inspector(self) -> PosixProcessTreeInspector:
        if self._posix_inspector is None:
            self._posix_inspector = PosixProcessTreeInspector()
        return self._posix_inspector

    def _bootstrap_environment(self) -> dict[str, str]:
        if self._os_name != "nt":
            return {}
        system_root = os.environ.get("SystemRoot")
        return {} if system_root is None else {"SystemRoot": system_root}

    def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
        # Sensitive workload launch data is deliberately unused until the
        # runner releases the explicit start gate after telemetry setup.
        del request
        if self._os_name != "nt":
            raise RuntimeError(
                "Authoritative POSIX process-tree containment is unavailable"
            )
        bootstrap_path = (
            Path(__file__).with_name("process_start_bootstrap.py").resolve()
        )
        bootstrap_python = Path(
            getattr(sys, "_base_executable", sys.executable)
        ).resolve()
        if not bootstrap_path.is_file() or not bootstrap_python.is_file():
            raise RuntimeError("Trusted process bootstrap is unavailable")
        options: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "shell": False,
            "text": False,
            "bufsize": 0,
            "close_fds": True,
            "cwd": str(bootstrap_path.parent),
            "env": self._bootstrap_environment(),
        }
        launch_command = [
            str(bootstrap_python),
            "-I",
            "-S",
            str(bootstrap_path),
        ]
        job = None
        process = None
        assigned = False
        try:
            if self._os_name == "nt":
                job = self._job_api().create_kill_on_close_job()
                options["creationflags"] = getattr(
                    subprocess,
                    "CREATE_NEW_PROCESS_GROUP",
                    self._WINDOWS_NEW_PROCESS_GROUP,
                ) | getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    self._WINDOWS_NO_WINDOW,
                )
            else:
                options["start_new_session"] = True
            process = self._popen_factory(launch_command, **options)
            if (
                process.stdin is None
                or process.stdout is None
                or process.stderr is None
            ):
                raise RuntimeError(
                    "Process runner requires start-gate and output pipes"
                )
            if self._os_name == "nt":
                self._job_api().assign(job, process)
                assigned = True
                start_token = self._job_api().process_start_token(process)
                target = ProcessTarget(
                    pid=process.pid,
                    start_token=start_token,
                    start_token_hash=hashlib.sha256(
                        start_token.encode("utf-8")
                    ).hexdigest(),
                )
            else:
                target = self._inspector().create_target(process.pid)
            return ManagedProcess(
                process=process,
                target=target,
                containment=job,
                start_gate=_ProcessStartGate(process.stdin),
            )
        except Exception as exc:
            containment_closed = job is None
            bootstrap_exit_confirmed = process is None
            if process is not None and process.stdin is not None:
                try:
                    process.stdin.close()
                except Exception:
                    pass
            if self._os_name == "nt" and job is not None:
                if assigned:
                    try:
                        self._job_api().terminate(job)
                    except Exception:
                        pass
                elif process is not None:
                    # The bootstrap is not yet in the Job. Never target its raw
                    # PID: closing stdin can make it exit and permit PID reuse.
                    # ``Popen.kill`` uses the retained process handle on Win32.
                    try:
                        bootstrap_already_exited = process.poll() is not None
                    except Exception:
                        bootstrap_already_exited = False
                    if not bootstrap_already_exited:
                        try:
                            process.kill()
                        except Exception:
                            pass
                try:
                    self._job_api().close(job)
                except Exception:
                    containment_closed = False
                else:
                    containment_closed = True
            elif process is not None:
                try:
                    if self._killpg is None:
                        raise OSError("POSIX killpg is unavailable")
                    self._killpg(process.pid, signal.SIGKILL)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            if process is not None:
                try:
                    process.wait(timeout=5.0)
                except Exception:
                    try:
                        bootstrap_exit_confirmed = process.poll() is not None
                    except Exception:
                        bootstrap_exit_confirmed = False
                else:
                    bootstrap_exit_confirmed = True
            if process is not None and not assigned and not bootstrap_exit_confirmed:
                # Before assignment the bootstrap is outside the Job Object.
                # Closing the empty Job cannot prove that process was killed.
                containment_closed = False
            raise ProcessSpawnError(
                containment_closed=containment_closed,
            ) from exc

    def release_start_gate(
        self,
        managed: ManagedProcess,
        request: BoundedProcessRequest,
    ) -> None:
        gate = managed.start_gate
        if not isinstance(gate, _ProcessStartGate) or gate.released or gate.closed:
            raise RuntimeError("Process start gate is unavailable")
        if (
            type(gate.deadline_monotonic_ns) is not int
            or not 0 < gate.deadline_monotonic_ns <= 0x7FFFFFFFFFFFFFFF
        ):
            gate.close_safely()
            raise ProcessStartGateReleaseError(may_have_started=False)
        payload = json.dumps(
            {
                "command": list(request.command),
                "deadline_monotonic_ns": gate.deadline_monotonic_ns,
                "environment": dict(request.environment),
                "working_directory": str(request.working_directory),
            },
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if not 1 <= len(payload) <= PROCESS_TREE_MAX_BOOTSTRAP_PAYLOAD_BYTES:
            gate.close_safely()
            raise ProcessStartGateReleaseError(may_have_started=False)
        frame = str(len(payload)).encode("ascii") + b"\n" + payload
        write_attempted = False
        try:
            remaining = memoryview(frame)
            while remaining:
                write_attempted = True
                written = gate.pipe.write(remaining)
                if not isinstance(written, int) or written <= 0:
                    raise OSError("Process bootstrap payload pipe closed early")
                remaining = remaining[written:]
            gate.pipe.flush()
            gate.close()
        except Exception as exc:
            gate.close_safely()
            raise ProcessStartGateReleaseError(
                may_have_started=write_attempted,
            ) from exc
        gate.released = True

    def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
        if self._os_name == "nt":
            try:
                current_token = self._job_api().process_start_token(managed.process)
                active = self._job_api().active_processes(managed.containment)
                active_ids = self._job_api().active_process_ids(managed.containment)
            except Exception:
                return TreeInspectionOutcome(
                    method="windows_job_accounting",
                    inspection_succeeded=False,
                    target_identity_confirmed=False,
                    active_processes=None,
                    empty_tree_confirmed=False,
                )
            identity_confirmed = current_token == managed.target.start_token
            if active != len(active_ids):
                return TreeInspectionOutcome(
                    method="windows_job_accounting",
                    inspection_succeeded=False,
                    target_identity_confirmed=identity_confirmed,
                    active_processes=active,
                    empty_tree_confirmed=False,
                )
            root_exited = managed.process.poll() is not None
            # A bootstrap root waits for its direct child before it exits, but
            # Job accounting can retain both exited PIDs briefly.  The runner
            # may therefore settle any post-root accounting state only while
            # repeatedly checking the hard deadline.  A genuinely live
            # descendant is still terminated at the deadline (or after the
            # short pre-deadline grace), never accepted as an empty tree.
            accounting_pending = root_exited and active > 0
            return TreeInspectionOutcome(
                method="windows_job_accounting",
                inspection_succeeded=True,
                target_identity_confirmed=identity_confirmed,
                active_processes=active,
                empty_tree_confirmed=identity_confirmed and active == 0,
                root_exit_accounting_pending=accounting_pending,
            )
        return self._inspector().inspect(managed.target)

    def terminate_tree(
        self,
        managed: ManagedProcess,
        *,
        timeout_seconds: float,
    ) -> TreeTerminationOutcome:
        if self._os_name == "nt":
            return self._terminate_windows_tree(managed, timeout_seconds)
        return self._terminate_posix_tree(managed, timeout_seconds)

    def _terminate_windows_tree(
        self,
        managed: ManagedProcess,
        timeout_seconds: float,
    ) -> TreeTerminationOutcome:
        deadline = self._monotonic() + timeout_seconds
        try:
            self._job_api().terminate(managed.containment)
        except Exception:
            inspection = self.inspect_tree(managed)
            return TreeTerminationOutcome(
                method="windows_terminate_job_object",
                succeeded=inspection.empty_tree_confirmed,
                final_inspection=inspection,
            )
        try:
            managed.process.wait(timeout=max(0.0, deadline - self._monotonic()))
        except Exception:
            pass
        inspection = self._wait_for_empty(
            managed,
            max(0.0, deadline - self._monotonic()),
        )
        return TreeTerminationOutcome(
            method="windows_terminate_job_object",
            succeeded=inspection.empty_tree_confirmed,
            final_inspection=inspection,
        )

    def _terminate_posix_tree(
        self,
        managed: ManagedProcess,
        timeout_seconds: float,
    ) -> TreeTerminationOutcome:
        del timeout_seconds
        inspection = self.inspect_tree(managed)
        return TreeTerminationOutcome(
            method="posix_non_authoritative_no_signal",
            succeeded=inspection.empty_tree_confirmed,
            final_inspection=inspection,
        )

    def _wait_for_empty(
        self,
        managed: ManagedProcess,
        timeout_seconds: float,
    ) -> TreeInspectionOutcome:
        deadline = self._monotonic() + timeout_seconds
        inspection = self.inspect_tree(managed)
        while (
            inspection.inspection_succeeded
            and inspection.target_identity_confirmed
            and not inspection.empty_tree_confirmed
            and self._monotonic() < deadline
        ):
            time.sleep(0.01)
            inspection = self.inspect_tree(managed)
        return inspection

    def close_containment(self, managed: ManagedProcess) -> bool:
        if self._os_name != "nt":
            return True
        try:
            self._job_api().close(managed.containment)
        except Exception:
            return False
        return True


class _BoundedPipeCapture:
    def __init__(self, pipe: Any, *, limit_bytes: int) -> None:
        self._pipe = pipe
        self._limit_bytes = limit_bytes
        self._captured = bytearray()
        self._digest = hashlib.sha256()
        self._byte_count = 0
        self._sealed = False
        self._stream_complete = False
        self._lock = threading.Lock()
        self.limit_exceeded = threading.Event()
        self.io_failed = threading.Event()
        self._thread = threading.Thread(target=self._read, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def join(self, timeout: float) -> bool:
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def close_pipe(self) -> None:
        try:
            self._pipe.close()
        except Exception:
            pass

    def _read(self) -> None:
        try:
            read = getattr(self._pipe, "read1", self._pipe.read)
            while True:
                chunk = read(_PIPE_CHUNK_BYTES)
                if not chunk:
                    with self._lock:
                        if not self._sealed:
                            self._stream_complete = True
                    break
                if not isinstance(chunk, bytes):
                    self.io_failed.set()
                    break
                with self._lock:
                    if self._sealed:
                        break
                    self._digest.update(chunk)
                    self._byte_count += len(chunk)
                    available = self._limit_bytes - len(self._captured)
                    if available > 0:
                        self._captured.extend(chunk[:available])
                    limit_exceeded = self._byte_count > self._limit_bytes
                if limit_exceeded:
                    self.limit_exceeded.set()
        except Exception:
            self.io_failed.set()
        finally:
            self.close_pipe()

    @property
    def byte_count(self) -> int:
        with self._lock:
            return self._byte_count

    def seal_incomplete(self) -> None:
        """Freeze a stable partial observation before forcing a pipe closed."""

        with self._lock:
            self._sealed = True
            self._stream_complete = False
        self.io_failed.set()

    def snapshot(self) -> tuple[ProcessOutputSummary, bytes]:
        with self._lock:
            self._sealed = True
            captured = bytes(self._captured)
            summary = ProcessOutputSummary(
                byte_count=self._byte_count,
                captured_byte_count=len(captured),
                sha256=self._digest.copy().hexdigest(),
                captured_sha256=hashlib.sha256(captured).hexdigest(),
                truncated=self._byte_count > len(captured),
                stream_complete=self._stream_complete,
            )
        return summary, captured


@dataclass(slots=True)
class _ObserverInvocation:
    callback: Callable[[], None] = field(repr=False)
    completed: threading.Event = field(default_factory=threading.Event, repr=False)
    succeeded: threading.Event = field(default_factory=threading.Event, repr=False)


class _BoundedObserverDispatcher:
    """Serialize callbacks on one reusable daemon thread per runner."""

    def __init__(self) -> None:
        self._queue: queue.Queue[_ObserverInvocation | None] = queue.Queue(maxsize=1)
        self._available = threading.Lock()
        self._accepting = True
        self._retire_requested = threading.Event()
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="rei-process-lifecycle-observer",
            daemon=True,
        )
        try:
            self._thread.start()
        except BaseException as exc:
            self._started = False
            self._accepting = False
            # ``Thread.start`` is not specified as transactional.  Poison and
            # join even when it reports failure: a hostile wrapper can start
            # the worker and then raise, otherwise leaving it blocked on get().
            self.retire()
            if not isinstance(exc, Exception):
                raise
        else:
            self._started = True

    def call(
        self,
        callback: Callable[[], None],
        *,
        wait_seconds: float,
    ) -> Literal["succeeded", "failed", "timed_out"]:
        if not self._started or not self._accepting:
            return "failed"
        if wait_seconds <= 0.0:
            return "timed_out"
        if not self._available.acquire(blocking=False):
            return "timed_out"
        invocation = _ObserverInvocation(callback=callback)
        try:
            self._queue.put_nowait(invocation)
        except Exception:
            self._available.release()
            return "failed"
        if not invocation.completed.wait(wait_seconds):
            self._accepting = False
            self._retire_requested.set()
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
            return "timed_out"
        return "succeeded" if invocation.succeeded.is_set() else "failed"

    def close_if_idle(self) -> bool:
        if self._stopped.is_set():
            return True
        if not self._started:
            self.retire()
            return self._thread.ident is None or self._stopped.is_set()
        if not self._available.acquire(blocking=False):
            return False
        self._accepting = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            self._accepting = True
            self._available.release()
            return False
        self._available.release()
        self._thread.join(timeout=0.25)
        return not self._thread.is_alive()

    def retire(self) -> None:
        """Permanently reject new callbacks and ask the daemon worker to exit."""

        self._accepting = False
        self._retire_requested.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        if threading.current_thread() is not self._thread:
            try:
                self._thread.join(timeout=0.25)
            except RuntimeError:
                # A definitively not-started thread needs no join; the queued
                # poison still covers an ambiguously delayed native start.
                pass

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()

    def _run(self) -> None:
        try:
            while True:
                invocation = self._queue.get()
                if invocation is None:
                    return
                try:
                    invocation.callback()
                except BaseException:
                    pass
                else:
                    invocation.succeeded.set()
                finally:
                    self._available.release()
                    invocation.completed.set()
                if self._retire_requested.is_set():
                    return
        finally:
            self._stopped.set()


@dataclass(slots=True)
class _PostSpawnCleanupState:
    request: BoundedProcessRequest | None = None
    started_at: datetime | None = None
    started_ns: int | None = None
    real_started_ns: int | None = None
    managed: ManagedProcess | None = None
    stdout_pipe: Any = field(default=None, repr=False)
    stderr_pipe: Any = field(default=None, repr=False)
    stdout_capture: _BoundedPipeCapture | None = field(default=None, repr=False)
    stderr_capture: _BoundedPipeCapture | None = field(default=None, repr=False)
    workload_released: bool = False
    workload_release_status: WorkloadReleaseStatus = "not_attempted"
    real_workload_started_ns: int | None = None
    observer_failed: bool = False


class BoundedProcessTreeRunner:
    """Execute one request without fallback and close its tree on hard failure."""

    def __init__(
        self,
        *,
        adapter: ProcessTreeAdapter | None = None,
        observer: ProcessLifecycleObserver | None = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        utc_clock: Callable[[], datetime] = utc_now,
        poll_interval_seconds: float = 0.01,
        termination_timeout_seconds: float = (
            PROCESS_TREE_DEFAULT_TERMINATION_TIMEOUT_SECONDS
        ),
    ) -> None:
        if (
            not math.isfinite(poll_interval_seconds)
            or not 0.0 < poll_interval_seconds <= 0.25
        ):
            raise ValueError("poll_interval_seconds must be within (0, 0.25]")
        if (
            not math.isfinite(termination_timeout_seconds)
            or not 0.0 < termination_timeout_seconds <= 60.0
        ):
            raise ValueError("termination_timeout_seconds must be within (0, 60]")
        self._adapter = adapter or PlatformProcessTreeAdapter()
        _require_safe_identity(
            self._adapter.isolation_mode,
            field_name="adapter isolation mode",
        )
        self._monotonic_ns = monotonic_ns
        self._utc_clock = utc_clock
        self._observer = observer or NullProcessLifecycleObserver()
        self._observer_dispatcher: _BoundedObserverDispatcher | None = None
        self._active_cleanup_state: _PostSpawnCleanupState | None = None
        self._last_terminal_result: BoundedProcessResult | None = None
        self._poll_interval_seconds = poll_interval_seconds
        self._termination_timeout_seconds = termination_timeout_seconds

    @property
    def last_terminal_result(self) -> BoundedProcessResult:
        """Return the sanitized result retained before a propagated BaseException."""

        if self._last_terminal_result is None:
            raise RuntimeError("Process-tree runner has no terminal result")
        return self._last_terminal_result

    def run(self, request: BoundedProcessRequest) -> BoundedProcessResult:
        if self._active_cleanup_state is not None:
            raise RuntimeError("Process-tree runner does not support concurrent runs")
        state = _PostSpawnCleanupState()
        state.real_started_ns = time.monotonic_ns()
        self._active_cleanup_state = state
        self._last_terminal_result = None
        try:
            result = self._run_once(request, state=state)
            self._last_terminal_result = result
            return result
        except BaseException as exc:
            if state.managed is not None and state.request is not None:
                result = self._abort_post_spawn_failure(state)
            elif (
                state.request is not None
                and state.started_at is not None
                and state.started_ns is not None
            ):
                result = self._start_failure(
                    state.request,
                    started_at=state.started_at,
                    started_ns=state.started_ns,
                    containment_closed=False,
                )
            else:
                raise
            self._last_terminal_result = result
            if not isinstance(exc, Exception):
                raise
            return result
        finally:
            self._active_cleanup_state = None

    def _run_once(
        self,
        request: BoundedProcessRequest,
        *,
        state: _PostSpawnCleanupState,
    ) -> BoundedProcessResult:
        if type(request) is not BoundedProcessRequest:
            raise TypeError("request must be an exact BoundedProcessRequest")
        request = BoundedProcessRequest(
            workload_id=request.workload_id,
            command_identity=request.command_identity,
            working_directory_identity=request.working_directory_identity,
            environment_identity=request.environment_identity,
            command=request.command,
            working_directory=request.working_directory,
            environment=request.environment,
            timeout_seconds=request.timeout_seconds,
            stdout_limit_bytes=request.stdout_limit_bytes,
            stderr_limit_bytes=request.stderr_limit_bytes,
        )
        state.request = request
        started_at = self._utc_clock()
        state.started_at = started_at
        started_ns = self._monotonic_ns()
        state.started_ns = started_ns
        try:
            managed = self._adapter.spawn(request)
        except Exception as exc:
            return self._start_failure(
                request,
                started_at=started_at,
                started_ns=started_ns,
                containment_closed=(
                    exc.containment_closed
                    if isinstance(exc, ProcessSpawnError)
                    else False
                ),
            )

        state.managed = managed
        process = managed.process
        process_tree_rss_reader = getattr(
            self._adapter,
            "process_tree_rss_bytes",
            None,
        )
        process_tree_rss_source = getattr(
            self._adapter,
            "process_tree_rss_source",
            None,
        )
        if not callable(process_tree_rss_reader):
            process_tree_rss_reader = None
            process_tree_rss_source = None
        elif (
            not isinstance(process_tree_rss_source, str)
            or _SAFE_IDENTITY.fullmatch(process_tree_rss_source) is None
        ):
            process_tree_rss_reader = None
            process_tree_rss_source = None
        context = ProcessLifecycleContext(
            workload_id=request.workload_id,
            target=managed.target,
            isolation_mode=self._adapter.isolation_mode,
            process_tree_rss_source=process_tree_rss_source,
            _process_tree_rss_reader=(
                None
                if process_tree_rss_reader is None
                else lambda: process_tree_rss_reader(managed)
            ),
        )
        stdout_pipe = process.stdout
        state.stdout_pipe = stdout_pipe
        stderr_pipe = process.stderr
        state.stderr_pipe = stderr_pipe
        stdout_capture = _BoundedPipeCapture(
            stdout_pipe,
            limit_bytes=request.stdout_limit_bytes,
        )
        state.stdout_capture = stdout_capture
        stderr_capture = _BoundedPipeCapture(
            stderr_pipe,
            limit_bytes=request.stderr_limit_bytes,
        )
        state.stderr_capture = stderr_capture
        stdout_capture.start()
        stderr_capture.start()

        deadline_ns = started_ns + int(request.timeout_seconds * 1_000_000_000)
        self._arm_start_gate_deadline(managed, deadline_ns=deadline_ns)
        workload_released = False
        workload_release_status: WorkloadReleaseStatus = "not_attempted"
        workload_started_ns: int | None = None
        workload_finished_ns: int | None = None
        start_gate_failed = False
        pre_release_timeout = False
        observer_outcome = self._call_observer(
            "on_started",
            context,
            deadline_ns=deadline_ns,
            max_wait_seconds=_PROCESS_TREE_OBSERVER_SETUP_CALLBACK_MAX_SECONDS,
        )
        observer_failed = observer_outcome != "succeeded"
        state.observer_failed = observer_failed
        observer_callbacks_disabled = observer_outcome in {
            "timed_out",
            "deadline_expired",
        }
        trigger: ProcessTerminationTrigger = "not_required"
        if observer_failed:
            if observer_outcome == "deadline_expired" or (
                observer_outcome == "timed_out" and self._monotonic_ns() >= deadline_ns
            ):
                trigger = "hard_timeout"
                pre_release_timeout = True
            else:
                trigger = "observer_failure"
        if trigger == "not_required":
            if self._monotonic_ns() >= deadline_ns:
                trigger = "hard_timeout"
                pre_release_timeout = True
            else:
                release_started_ns = self._monotonic_ns()
                release_started_real_ns = time.monotonic_ns()
                try:
                    self._adapter.release_start_gate(managed, request)
                except BaseException as exc:
                    trigger = "start_gate_failure"
                    start_gate_failed = True
                    may_have_started = (
                        not isinstance(
                            exc,
                            ProcessStartGateReleaseError,
                        )
                        or exc.may_have_started
                    )
                    if may_have_started:
                        workload_release_status = "uncertain"
                        workload_started_ns = release_started_ns
                        state.workload_release_status = workload_release_status
                        state.real_workload_started_ns = release_started_real_ns
                    if not isinstance(exc, Exception):
                        raise
                else:
                    workload_released = True
                    workload_release_status = "released"
                    workload_started_ns = release_started_ns
                    state.workload_released = workload_released
                    state.workload_release_status = workload_release_status
                    state.real_workload_started_ns = release_started_real_ns

        while trigger == "not_required" and process.poll() is None:
            now_ns = self._monotonic_ns()
            if now_ns >= deadline_ns:
                trigger = "hard_timeout"
                break
            observer_outcome = self._call_observer(
                "on_poll",
                context,
                deadline_ns=deadline_ns,
                max_wait_seconds=_PROCESS_TREE_OBSERVER_LIVE_CALLBACK_MAX_SECONDS,
            )
            now_ns = self._monotonic_ns()
            if observer_outcome != "succeeded":
                observer_failed = True
                state.observer_failed = True
                observer_callbacks_disabled = observer_callbacks_disabled or (
                    observer_outcome in {"timed_out", "deadline_expired"}
                )
                trigger = (
                    "hard_timeout"
                    if observer_outcome == "deadline_expired" or now_ns >= deadline_ns
                    else "observer_failure"
                )
                break
            if now_ns >= deadline_ns:
                trigger = "hard_timeout"
                break
            if stdout_capture.io_failed.is_set() or stderr_capture.io_failed.is_set():
                trigger = "io_failure"
                break
            if stdout_capture.limit_exceeded.is_set():
                trigger = "stdout_limit"
                break
            if stderr_capture.limit_exceeded.is_set():
                trigger = "stderr_limit"
                break
            remaining_seconds = (deadline_ns - now_ns) / 1_000_000_000
            try:
                process.wait(
                    timeout=min(self._poll_interval_seconds, remaining_seconds)
                )
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                trigger = "io_failure"
                break

        # Output may cross a limit immediately before a clean root exit.
        if trigger == "not_required":
            if self._monotonic_ns() >= deadline_ns:
                trigger = "hard_timeout"
            elif stdout_capture.io_failed.is_set() or stderr_capture.io_failed.is_set():
                trigger = "io_failure"
            elif stdout_capture.limit_exceeded.is_set():
                trigger = "stdout_limit"
            elif stderr_capture.limit_exceeded.is_set():
                trigger = "stderr_limit"

        final_inspection: TreeInspectionOutcome | None = None
        if trigger == "not_required":
            if self._monotonic_ns() >= deadline_ns:
                trigger = "hard_timeout"
            else:
                observer_outcome = self._call_observer(
                    "on_poll",
                    context,
                    deadline_ns=deadline_ns,
                    max_wait_seconds=_PROCESS_TREE_OBSERVER_LIVE_CALLBACK_MAX_SECONDS,
                )
                now_ns = self._monotonic_ns()
                if observer_outcome != "succeeded":
                    observer_failed = True
                    state.observer_failed = True
                    observer_callbacks_disabled = observer_callbacks_disabled or (
                        observer_outcome in {"timed_out", "deadline_expired"}
                    )
                    trigger = (
                        "hard_timeout"
                        if observer_outcome == "deadline_expired"
                        or now_ns >= deadline_ns
                        else "observer_failure"
                    )
                elif now_ns >= deadline_ns:
                    trigger = "hard_timeout"
                else:
                    final_inspection = self._inspect_settled_tree(
                        managed,
                        deadline_ns=deadline_ns,
                    )
                    if self._monotonic_ns() >= deadline_ns:
                        trigger = "hard_timeout"
                    elif (
                        not final_inspection.inspection_succeeded
                        or not final_inspection.target_identity_confirmed
                    ):
                        trigger = "tree_inspection_failure"
                    elif not final_inspection.empty_tree_confirmed:
                        trigger = "tree_leak"

        termination: TreeTerminationOutcome | None = None
        if trigger != "not_required":
            self._close_start_gate_safely(managed)
            if not observer_callbacks_disabled and self._monotonic_ns() < deadline_ns:
                observer_outcome = self._call_observer(
                    "before_termination",
                    context,
                    trigger,
                    deadline_ns=deadline_ns,
                    max_wait_seconds=_PROCESS_TREE_OBSERVER_LIVE_CALLBACK_MAX_SECONDS,
                )
                if observer_outcome != "succeeded":
                    observer_failed = True
                    state.observer_failed = True
                    observer_callbacks_disabled = observer_outcome in {
                        "timed_out",
                        "deadline_expired",
                    }
            try:
                termination = self._adapter.terminate_tree(
                    managed,
                    timeout_seconds=self._termination_timeout_seconds,
                )
            except Exception:
                inspection = self._safe_inspect_tree(managed)
                termination = TreeTerminationOutcome(
                    method="adapter_termination_exception",
                    succeeded=inspection.empty_tree_confirmed,
                    final_inspection=inspection,
                )
            final_inspection = termination.final_inspection
            if final_inspection.empty_tree_confirmed:
                workload_finished_ns = self._monotonic_ns()
            if not observer_callbacks_disabled and (
                termination.succeeded or self._monotonic_ns() < deadline_ns
            ):
                observer_outcome = self._call_observer(
                    "after_termination",
                    context,
                    termination,
                    deadline_ns=None if termination.succeeded else deadline_ns,
                    max_wait_seconds=(
                        _PROCESS_TREE_OBSERVER_POST_TERMINATION_CALLBACK_MAX_SECONDS
                        if termination.succeeded
                        else _PROCESS_TREE_OBSERVER_LIVE_CALLBACK_MAX_SECONDS
                    ),
                )
                if observer_outcome != "succeeded":
                    observer_failed = True
                    state.observer_failed = True
                    observer_callbacks_disabled = observer_outcome in {
                        "timed_out",
                        "deadline_expired",
                    }

        if final_inspection is None:
            final_inspection = self._safe_inspect_tree(managed)
        if final_inspection.empty_tree_confirmed and workload_finished_ns is None:
            workload_finished_ns = self._monotonic_ns()
        if trigger == "not_required" and final_inspection.empty_tree_confirmed:
            observer_outcome = self._call_optional_observer(
                "after_natural_completion",
                context,
                final_inspection,
                deadline_ns=None,
                max_wait_seconds=(
                    _PROCESS_TREE_OBSERVER_POST_TERMINATION_CALLBACK_MAX_SECONDS
                ),
            )
            if observer_outcome != "succeeded":
                observer_failed = True
                state.observer_failed = True
                observer_callbacks_disabled = observer_outcome in {
                    "timed_out",
                    "deadline_expired",
                }
                trigger = "observer_failure"

        self._close_observer_dispatcher()

        containment_closed: bool | None = None
        root_reap_attempted = False
        if termination is not None and not termination.succeeded:
            # Job close is the final documented Windows kill boundary. The
            # failure remains unconfirmed, but closing before drain prevents a
            # live failed tree from holding inherited pipes for the full wait.
            containment_closed = self._safe_close_containment(managed)
            self._safe_reap_root(process)
            root_reap_attempted = True

        drain_deadline = time.monotonic() + self._termination_timeout_seconds
        stdout_reader_closed = stdout_capture.join(self._termination_timeout_seconds)
        remaining_drain = max(0.0, drain_deadline - time.monotonic())
        stderr_reader_closed = stderr_capture.join(remaining_drain)
        if not stdout_reader_closed or not stderr_reader_closed:
            if not stdout_reader_closed:
                stdout_capture.seal_incomplete()
                stdout_capture.close_pipe()
                stdout_capture.join(0.25)
            if not stderr_reader_closed:
                stderr_capture.seal_incomplete()
                stderr_capture.close_pipe()
                stderr_capture.join(0.25)
            if trigger == "not_required":
                trigger = "io_failure"

        # A short-lived root can exit before the drain threads publish an
        # output breach. Re-check after EOF; the tree is already confirmed
        # empty, so a late breach is a closed failure without a second kill.
        if trigger == "not_required":
            if stdout_capture.io_failed.is_set() or stderr_capture.io_failed.is_set():
                trigger = "io_failure"
            elif stdout_capture.limit_exceeded.is_set():
                trigger = "stdout_limit"
            elif stderr_capture.limit_exceeded.is_set():
                trigger = "stderr_limit"

        if containment_closed is None:
            containment_closed = self._safe_close_containment(managed)
        self._close_start_gate_safely(managed)
        if not root_reap_attempted:
            self._safe_reap_root(process)
        if not containment_closed and trigger == "not_required":
            trigger = "containment_close_failure"

        finished_ns = self._monotonic_ns()
        finished_at = self._utc_clock()
        elapsed_seconds = max(0.0, (finished_ns - started_ns) / 1_000_000_000)
        workload_elapsed_seconds = 0.0
        if workload_started_ns is not None:
            observed_workload_end_ns = (
                workload_finished_ns
                if workload_finished_ns is not None
                else finished_ns
            )
            workload_elapsed_seconds = max(
                0.0,
                (observed_workload_end_ns - workload_started_ns) / 1_000_000_000,
            )
        exit_code = process.poll()
        stdout_summary, stdout_bytes = stdout_capture.snapshot()
        stderr_summary, stderr_bytes = stderr_capture.snapshot()

        failure_code: ProcessFailureCode | None
        status: ProcessExecutionStatus
        if termination is not None and not termination.succeeded:
            failure_code = "process_tree_termination_failure"
            status = "failed"
        elif not containment_closed:
            failure_code = "process_containment_close_failure"
            status = "failed"
        elif start_gate_failed:
            failure_code = "process_start_gate_failure"
            status = "failed"
        elif pre_release_timeout:
            failure_code = "process_timeout"
            status = "timed_out"
        elif trigger == "observer_failure":
            failure_code = "process_observer_failure"
            status = "failed"
        elif trigger == "hard_timeout":
            failure_code = "process_timeout"
            status = "timed_out"
        elif trigger == "stdout_limit":
            failure_code = "process_stdout_limit_exceeded"
            status = "failed"
        elif trigger == "stderr_limit":
            failure_code = "process_stderr_limit_exceeded"
            status = "failed"
        elif trigger == "io_failure":
            failure_code = "process_io_failure"
            status = "failed"
        elif trigger == "tree_inspection_failure":
            failure_code = "process_tree_inspection_failure"
            status = "failed"
        elif trigger == "tree_leak":
            failure_code = "process_tree_leak"
            status = "failed"
        elif exit_code != 0:
            failure_code = "process_exit_nonzero"
            status = "failed"
        else:
            failure_code = None
            status = "succeeded"

        record = self._record(
            request,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed_seconds,
            workload_elapsed_seconds=workload_elapsed_seconds,
            target=managed.target,
            workload_released=workload_released,
            workload_release_status=workload_release_status,
            exit_code=exit_code,
            status=status,
            trigger=trigger,
            failure_code=failure_code,
            stdout=stdout_summary,
            stderr=stderr_summary,
            termination=termination,
            final_inspection=final_inspection,
            containment_closed=containment_closed,
            observer_failed=observer_failed,
        )
        return BoundedProcessResult(
            record=record,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
        )

    def _call_observer(
        self,
        method: str,
        *arguments: Any,
        deadline_ns: int | None,
        max_wait_seconds: float,
    ) -> Literal["succeeded", "failed", "timed_out", "deadline_expired"]:
        """Run one callback without letting it retain a live workload.

        Python cannot safely terminate a blocked thread.  The callback is
        therefore isolated in a daemon thread, while the runner waits only for
        a fixed local budget additionally capped by the absolute workload
        deadline.  Late exceptions remain inside this sanitized boundary.
        """

        if type(self._observer) is NullProcessLifecycleObserver:
            return "succeeded"

        wait_seconds = max_wait_seconds
        real_deadline: float | None = None
        if deadline_ns is not None:
            remaining_ns = deadline_ns - self._monotonic_ns()
            if remaining_ns <= 0:
                return "timed_out"
            remaining_seconds = remaining_ns / 1_000_000_000
            if remaining_seconds <= wait_seconds:
                wait_seconds = remaining_seconds
                real_deadline = time.monotonic() + remaining_seconds

        def invoke() -> None:
            getattr(self._observer, method)(*arguments)

        if self._observer_dispatcher is None or self._observer_dispatcher.stopped:
            self._observer_dispatcher = _BoundedObserverDispatcher()
        outcome = self._observer_dispatcher.call(
            invoke,
            wait_seconds=wait_seconds,
        )
        if outcome == "timed_out" and real_deadline is not None:
            # ``Event.wait`` may wake fractionally early on Windows.  When the
            # absolute workload deadline, rather than the local callback cap,
            # supplied the budget, wait only the remaining real interval so
            # classification deterministically stays a hard timeout.
            while self._monotonic_ns() < deadline_ns:
                remaining_real = real_deadline - time.monotonic()
                if remaining_real <= 0.0:
                    break
                time.sleep(min(0.005, remaining_real))
            return "deadline_expired"
        return outcome

    def _call_optional_observer(
        self,
        method: str,
        *arguments: Any,
        deadline_ns: int | None,
        max_wait_seconds: float,
    ) -> Literal["succeeded", "failed", "timed_out", "deadline_expired"]:
        """Call one backwards-compatible optional lifecycle extension."""

        if not callable(getattr(self._observer, method, None)):
            return "succeeded"
        return self._call_observer(
            method,
            *arguments,
            deadline_ns=deadline_ns,
            max_wait_seconds=max_wait_seconds,
        )

    def _close_observer_dispatcher(self) -> None:
        dispatcher = self._observer_dispatcher
        if dispatcher is not None and dispatcher.close_if_idle():
            self._observer_dispatcher = None

    def _retire_observer_dispatcher(self) -> None:
        dispatcher = self._observer_dispatcher
        try:
            if dispatcher is not None:
                dispatcher.retire()
        finally:
            self._observer_dispatcher = None

    def _safe_inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
        try:
            return self._adapter.inspect_tree(managed)
        except Exception:
            return TreeInspectionOutcome(
                method="adapter_inspection_exception",
                inspection_succeeded=False,
                target_identity_confirmed=False,
                active_processes=None,
                empty_tree_confirmed=False,
            )

    def _safe_close_containment(self, managed: ManagedProcess) -> bool:
        try:
            return self._adapter.close_containment(managed) is True
        except Exception:
            return False

    @staticmethod
    def _arm_start_gate_deadline(
        managed: ManagedProcess,
        *,
        deadline_ns: int | None,
    ) -> None:
        gate = managed.start_gate
        if isinstance(gate, _ProcessStartGate):
            gate.deadline_monotonic_ns = deadline_ns

    @staticmethod
    def _close_start_gate_safely(managed: ManagedProcess) -> None:
        gate = managed.start_gate
        close_safely = getattr(gate, "close_safely", None)
        if callable(close_safely):
            close_safely()
            return
        close = getattr(gate, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def _safe_reap_root(self, process: Any) -> None:
        try:
            process.wait(timeout=self._termination_timeout_seconds)
        except Exception:
            pass

    def _inspect_settled_tree(
        self,
        managed: ManagedProcess,
        *,
        deadline_ns: int,
        grace_seconds: float = 0.1,
    ) -> TreeInspectionOutcome:
        """Allow root-exit accounting to settle without hiding descendants."""

        inspection = self._safe_inspect_tree(managed)
        real_deadline = time.monotonic() + grace_seconds
        while inspection.root_exit_accounting_pending:
            now_ns = self._monotonic_ns()
            if now_ns >= deadline_ns or time.monotonic() >= real_deadline:
                break
            remaining_seconds = (deadline_ns - now_ns) / 1_000_000_000
            time.sleep(min(0.005, remaining_seconds))
            inspection = self._safe_inspect_tree(managed)
        return inspection

    def _abort_post_spawn_failure(
        self,
        state: _PostSpawnCleanupState,
    ) -> BoundedProcessResult:
        """Close every owned runtime boundary after an unexpected exception."""

        request = state.request
        managed = state.managed
        if request is None or managed is None:
            raise RuntimeError("Post-spawn cleanup state is incomplete")

        try:
            self._close_start_gate_safely(managed)
        except BaseException:
            # Teardown is deliberately best-effort across every independent
            # boundary; a broken gate close must not skip tree termination.
            pass
        try:
            termination = self._adapter.terminate_tree(
                managed,
                timeout_seconds=self._termination_timeout_seconds,
            )
            if not isinstance(termination, TreeTerminationOutcome):
                raise TypeError("Adapter returned an invalid termination outcome")
        except BaseException:
            try:
                inspection = self._safe_inspect_tree(managed)
            except BaseException:
                inspection = TreeInspectionOutcome(
                    method="post_spawn_exception_inspection",
                    inspection_succeeded=False,
                    target_identity_confirmed=False,
                    active_processes=None,
                    empty_tree_confirmed=False,
                )
            termination = TreeTerminationOutcome(
                method="post_spawn_exception_termination",
                succeeded=inspection.empty_tree_confirmed,
                final_inspection=inspection,
            )
        final_inspection = termination.final_inspection
        try:
            containment_closed = self._safe_close_containment(managed)
        except BaseException:
            containment_closed = False
        try:
            self._safe_reap_root(managed.process)
        except BaseException:
            pass
        try:
            self._retire_observer_dispatcher()
        except BaseException:
            # ``_retire_observer_dispatcher`` clears the runner reference in a
            # finally block even if a hostile Thread.join implementation fails.
            pass

        if state.stdout_pipe is None:
            try:
                state.stdout_pipe = managed.process.stdout
            except BaseException:
                pass
        if state.stderr_pipe is None:
            try:
                state.stderr_pipe = managed.process.stderr
            except BaseException:
                pass

        stdout_summary, stdout_bytes = self._seal_failed_capture(
            state.stdout_capture,
            pipe=state.stdout_pipe,
        )
        stderr_summary, stderr_bytes = self._seal_failed_capture(
            state.stderr_capture,
            pipe=state.stderr_pipe,
        )

        started_at = state.started_at or utc_now()
        fallback_finished_at = utc_now()
        finished_at = max(started_at, fallback_finished_at)
        finished_ns = time.monotonic_ns()
        elapsed_seconds = 0.0
        if state.real_started_ns is not None and finished_ns >= state.real_started_ns:
            elapsed_seconds = (finished_ns - state.real_started_ns) / 1_000_000_000
        workload_elapsed_seconds = 0.0
        if (
            state.real_workload_started_ns is not None
            and finished_ns >= state.real_workload_started_ns
        ):
            workload_elapsed_seconds = (
                finished_ns - state.real_workload_started_ns
            ) / 1_000_000_000
        workload_elapsed_seconds = min(
            workload_elapsed_seconds,
            elapsed_seconds,
        )

        cleanup_trigger: ProcessTerminationTrigger = (
            "start_gate_failure"
            if state.workload_release_status == "uncertain"
            else "io_failure"
        )
        if not termination.succeeded:
            failure_code: ProcessFailureCode = "process_tree_termination_failure"
        elif not containment_closed:
            failure_code = "process_containment_close_failure"
        elif cleanup_trigger == "start_gate_failure":
            failure_code = "process_start_gate_failure"
        else:
            failure_code = "process_io_failure"

        record = self._record(
            request,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed_seconds,
            workload_elapsed_seconds=workload_elapsed_seconds,
            target=managed.target,
            workload_released=state.workload_released,
            workload_release_status=state.workload_release_status,
            exit_code=self._safe_poll_code(managed.process),
            status="failed",
            trigger=cleanup_trigger,
            failure_code=failure_code,
            stdout=stdout_summary,
            stderr=stderr_summary,
            termination=termination,
            final_inspection=final_inspection,
            containment_closed=containment_closed,
            observer_failed=state.observer_failed,
        )
        return BoundedProcessResult(
            record=record,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
        )

    @staticmethod
    def _seal_failed_capture(
        capture: _BoundedPipeCapture | None,
        *,
        pipe: Any,
    ) -> tuple[ProcessOutputSummary, bytes]:
        if capture is not None:
            try:
                capture.seal_incomplete()
            except BaseException:
                pass
            try:
                capture.close_pipe()
            except BaseException:
                pass
            try:
                capture.join(0.25)
            except BaseException:
                pass
            try:
                return capture.snapshot()
            except BaseException:
                pass
        elif pipe is not None:
            try:
                pipe.close()
            except BaseException:
                pass
        return (
            ProcessOutputSummary(
                byte_count=0,
                captured_byte_count=0,
                sha256=_EMPTY_SHA256,
                captured_sha256=_EMPTY_SHA256,
                truncated=False,
                stream_complete=False,
            ),
            b"",
        )

    @staticmethod
    def _safe_poll_code(process: Any) -> int | None:
        try:
            value = process.poll()
        except BaseException:
            return None
        if type(value) is not int or not -0x80000000 <= value <= 0xFFFFFFFF:
            return None
        return value

    def _start_failure(
        self,
        request: BoundedProcessRequest,
        *,
        started_at: datetime,
        started_ns: int,
        containment_closed: bool,
    ) -> BoundedProcessResult:
        finished_ns = self._monotonic_ns()
        finished_at = self._utc_clock()
        record = self._record(
            request,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=max(
                0.0,
                (finished_ns - started_ns) / 1_000_000_000,
            ),
            workload_elapsed_seconds=0.0,
            target=None,
            workload_released=False,
            workload_release_status="not_attempted",
            exit_code=None,
            status="failed",
            trigger="not_required",
            failure_code="process_start_failure",
            stdout=ProcessOutputSummary(
                byte_count=0,
                captured_byte_count=0,
                sha256=_EMPTY_SHA256,
                captured_sha256=_EMPTY_SHA256,
                truncated=False,
                stream_complete=True,
            ),
            stderr=ProcessOutputSummary(
                byte_count=0,
                captured_byte_count=0,
                sha256=_EMPTY_SHA256,
                captured_sha256=_EMPTY_SHA256,
                truncated=False,
                stream_complete=True,
            ),
            termination=None,
            final_inspection=None,
            containment_closed=containment_closed,
            observer_failed=False,
        )
        return BoundedProcessResult(record=record, stdout=b"", stderr=b"")

    def _record(
        self,
        request: BoundedProcessRequest,
        *,
        started_at: datetime,
        finished_at: datetime,
        elapsed_seconds: float,
        workload_elapsed_seconds: float,
        target: ProcessTarget | None,
        workload_released: bool,
        workload_release_status: WorkloadReleaseStatus,
        exit_code: int | None,
        status: ProcessExecutionStatus,
        trigger: ProcessTerminationTrigger,
        failure_code: ProcessFailureCode | None,
        stdout: ProcessOutputSummary,
        stderr: ProcessOutputSummary,
        termination: TreeTerminationOutcome | None,
        final_inspection: TreeInspectionOutcome | None,
        containment_closed: bool,
        observer_failed: bool,
    ) -> ProcessTreeExecutionRecord:
        payload: dict[str, Any] = {
            "schema_version": "rei-process-tree-execution-v1",
            "runner_revision": PROCESS_TREE_RUNNER_REVISION,
            "workload_id": request.workload_id,
            "command_identity": request.command_identity,
            "argument_count": len(request.command) - 1,
            "working_directory_identity": request.working_directory_identity,
            "environment_identity": request.environment_identity,
            "timeout_seconds": request.timeout_seconds,
            "stdout_limit_bytes": request.stdout_limit_bytes,
            "stderr_limit_bytes": request.stderr_limit_bytes,
            "platform_system": _sanitized_label(
                platform.system(),
                fallback="unknown",
            ),
            "isolation_mode": self._adapter.isolation_mode,
            "started_at": started_at,
            "finished_at": finished_at,
            "elapsed_monotonic_seconds": elapsed_seconds,
            "workload_elapsed_monotonic_seconds": workload_elapsed_seconds,
            "workload_timing_scope": (
                "not_observed_no_release_attempt"
                if workload_release_status == "not_attempted"
                else (
                    "release_attempt_to_confirmed_empty_tree_upper_bound"
                    if final_inspection is not None
                    and final_inspection.empty_tree_confirmed
                    else "release_attempt_to_runner_finish_unconfirmed_interval"
                )
            ),
            "process_id": None if target is None else target.pid,
            "workload_released": workload_released,
            "workload_release_status": workload_release_status,
            "target_start_token_hash": (
                None if target is None else target.start_token_hash
            ),
            "target_process_group_id": (
                None if target is None else target.process_group_id
            ),
            "target_session_id": None if target is None else target.session_id,
            "exit_code": exit_code,
            "status": status,
            "termination_trigger": trigger,
            "failure_code": failure_code,
            "failure_message": (
                None
                if failure_code is None
                else f"Bounded process failed closed ({failure_code})"
            ),
            "stdout": stdout,
            "stderr": stderr,
            "tree_termination_requested": termination is not None,
            "tree_termination_succeeded": (
                None if termination is None else termination.succeeded
            ),
            "tree_termination_method": (
                None if termination is None else termination.method
            ),
            "tree_inspection_method": (
                None if final_inspection is None else final_inspection.method
            ),
            "final_active_processes": (
                None if final_inspection is None else final_inspection.active_processes
            ),
            "target_identity_confirmed": (
                None
                if final_inspection is None
                else final_inspection.target_identity_confirmed
            ),
            "empty_tree_confirmed": (
                False
                if final_inspection is None
                else final_inspection.empty_tree_confirmed
            ),
            "containment_closed": containment_closed,
            "observer_callback_failed": observer_failed,
            "fallback_used": False,
        }
        return ProcessTreeExecutionRecord(
            record_id=content_id("process_execution", payload),
            **payload,
        )


__all__ = [
    "BoundedProcessRequest",
    "BoundedProcessResult",
    "BoundedProcessTreeRunner",
    "CtypesWindowsJobApi",
    "ManagedProcess",
    "NullProcessLifecycleObserver",
    "PlatformProcessTreeAdapter",
    "PosixProcessTreeInspector",
    "PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES",
    "PROCESS_TREE_MAX_BOOTSTRAP_PAYLOAD_BYTES",
    "PROCESS_TREE_MAX_COMMAND_ARGUMENTS",
    "PROCESS_TREE_MAX_COMMAND_UTF8_BYTES",
    "PROCESS_TREE_MAX_ENVIRONMENT_UTF8_BYTES",
    "PROCESS_TREE_MAX_ENVIRONMENT_VARIABLES",
    "PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES",
    "PROCESS_TREE_MAX_TIMEOUT_SECONDS",
    "PROCESS_TREE_MAX_WORKING_DIRECTORY_UTF8_BYTES",
    "PROCESS_TREE_RUNNER_REVISION",
    "ProcessOutputSummary",
    "ProcessSpawnError",
    "ProcessStartGateReleaseError",
    "ProcessLifecycleContext",
    "ProcessLifecycleObserver",
    "ProcessTarget",
    "ProcessTreeAdapter",
    "ProcessTreeExecutionRecord",
    "TreeInspectionOutcome",
    "TreeTerminationOutcome",
]
