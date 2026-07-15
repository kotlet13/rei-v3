from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

from pydantic import ValidationError
import pytest

from app.backend.rei.evaluation import process_tree_runner as process_tree_runner_module
from app.backend.rei.evaluation.process_tree_runner import (
    BoundedProcessRequest,
    BoundedProcessResult,
    BoundedProcessTreeRunner,
    CtypesWindowsJobApi,
    ManagedProcess,
    PlatformProcessTreeAdapter,
    ProcessStartGateReleaseError,
    PosixProcessTreeInspector,
    ProcessLifecycleContext,
    ProcessTarget,
    ProcessTreeExecutionRecord,
    TreeInspectionOutcome,
    TreeTerminationOutcome,
    _BoundedObserverDispatcher,
    _BoundedPipeCapture,
    _JobObjectBasicProcessIdList,
    _ProcessStartGate,
)
from app.backend.rei.ids import content_id


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="authoritative process-tree runner is intentionally Windows-only",
)


def _request(
    tmp_path: Path,
    *arguments: str,
    timeout_seconds: float = 5.0,
    stdout_limit_bytes: int = 65_536,
    stderr_limit_bytes: int = 65_536,
) -> BoundedProcessRequest:
    return BoundedProcessRequest(
        workload_id="c4-stage1-test",
        command_identity="c4-test-worker-v1",
        working_directory_identity="pytest-temp-directory",
        environment_identity="explicit-test-environment-v1",
        command=(str(Path(sys.executable).resolve()), *arguments),
        working_directory=tmp_path.resolve(),
        environment=dict(os.environ),
        timeout_seconds=timeout_seconds,
        stdout_limit_bytes=stdout_limit_bytes,
        stderr_limit_bytes=stderr_limit_bytes,
    )


def _rehash_execution_payload(payload: dict[str, Any]) -> dict[str, Any]:
    body = {key: value for key, value in payload.items() if key != "record_id"}
    payload["record_id"] = content_id("process_execution", body)
    return payload


def test_request_requires_explicit_absolute_bounded_launch_inputs(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, "-c", "pass")
    assert request.command[0] == str(Path(sys.executable).resolve())

    with pytest.raises(ValueError, match="absolute path"):
        BoundedProcessRequest(
            workload_id="test",
            command_identity="worker",
            working_directory_identity="cwd",
            environment_identity="environment",
            command=("python", "-c", "pass"),
            working_directory=tmp_path.resolve(),
            environment={},
            timeout_seconds=1.0,
        )
    with pytest.raises(ValueError, match=r"within \(0, 86400\]"):
        _request(tmp_path, "-c", "pass", timeout_seconds=float("inf"))
    with pytest.raises(ValueError, match="stdout_limit_bytes"):
        _request(tmp_path, "-c", "pass", stdout_limit_bytes=1_048_577)
    with pytest.raises(ValueError, match="argument-count"):
        _request(tmp_path, *("x" for _index in range(256)))
    with pytest.raises(ValueError, match="command exceeds.*UTF-8"):
        _request(tmp_path, "ž" * 65_537)
    with pytest.raises(ValueError, match="variable-count"):
        BoundedProcessRequest(
            workload_id="test",
            command_identity="worker",
            working_directory_identity="cwd",
            environment_identity="environment",
            command=(str(Path(sys.executable).resolve()), "-c", "pass"),
            working_directory=tmp_path.resolve(),
            environment={f"KEY_{index}": "x" for index in range(1_025)},
            timeout_seconds=1.0,
        )
    with pytest.raises(ValueError, match="environment exceeds.*UTF-8"):
        BoundedProcessRequest(
            workload_id="test",
            command_identity="worker",
            working_directory_identity="cwd",
            environment_identity="environment",
            command=(str(Path(sys.executable).resolve()), "-c", "pass"),
            working_directory=tmp_path.resolve(),
            environment={"OVERSIZED": "ž" * 131_073},
            timeout_seconds=1.0,
        )

    forged = _request(tmp_path, "-c", "pass")
    object.__setattr__(forged, "timeout_seconds", float("inf"))
    with pytest.raises(ValueError, match=r"within \(0, 86400\]"):
        BoundedProcessTreeRunner().run(forged)


@pytest.mark.parametrize(
    ("os_name", "expected_mode", "expected_option"),
    [
        ("nt", "windows_job_object_kill_on_close", "creationflags"),
    ],
)
def test_platform_adapter_never_uses_a_shell_and_selects_tree_isolation(
    tmp_path: Path,
    os_name: str,
    expected_mode: str,
    expected_option: str,
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []
    events: list[str] = []

    class FakeStdin:
        def __init__(self) -> None:
            self.data = bytearray()
            self.closed = False

        def write(self, value: bytes) -> int:
            events.append("payload_write")
            self.data.extend(value)
            return len(value)

        def flush(self) -> None:
            events.append("payload_flush")

        def close(self) -> None:
            self.closed = True
            events.append("payload_close")
            events.append("target")

    class FakeProcess:
        pid = 123
        stdin = FakeStdin()
        stdout = BytesIO()
        stderr = BytesIO()

        def kill(self) -> None:
            raise AssertionError("valid fake pipes must not require cleanup")

    def fake_popen(command: list[str], **options: Any) -> FakeProcess:
        events.append("popen")
        if options.get("start_new_session") is True:
            events.append("session")
        calls.append((command, options))
        return FakeProcess()

    class FakeJobApi:
        def create_kill_on_close_job(self) -> object:
            return object()

        def assign(self, job: object, process: FakeProcess) -> None:
            assert job is not None and process.pid == 123
            events.append("assign")

        def process_start_token(self, process: FakeProcess) -> str:
            assert process.pid == 123
            events.append("capture_start")
            return "windows-test-start-token"

        def terminate(self, job: object) -> None:
            del job

        def close(self, job: object) -> None:
            del job

    class FakePosixInspector:
        def create_target(self, pid: int) -> ProcessTarget:
            events.append("capture_start")
            token = "posix-test-start-token"
            return ProcessTarget(
                pid=pid,
                start_token=token,
                start_token_hash=hashlib.sha256(token.encode()).hexdigest(),
                process_group_id=pid,
                session_id=pid,
            )

    adapter = PlatformProcessTreeAdapter(
        os_name=os_name,
        popen_factory=fake_popen,
        windows_job_api=FakeJobApi(),
        posix_inspector=FakePosixInspector(),  # type: ignore[arg-type]
    )
    request = replace(
        _request(tmp_path, "-c", "requested-target-must-be-gated"),
        environment={
            **dict(os.environ),
            "REI_START_GATE_SECRET": "requested-environment-must-be-gated",
        },
    )
    managed = adapter.spawn(request)
    managed.start_gate.deadline_monotonic_ns = time.monotonic_ns() + 10_000_000_000
    events.append("observer")
    assert FakeProcess.stdin.closed is False
    adapter.release_start_gate(managed, request)

    assert adapter.isolation_mode == expected_mode
    assert len(calls) == 1
    _command, options = calls[0]
    assert options["shell"] is False
    assert options["stdout"] is subprocess.PIPE
    assert options["stderr"] is subprocess.PIPE
    assert options["stdin"] is subprocess.PIPE
    assert expected_option in options
    assert "requested-target-must-be-gated" not in _command
    assert "requested-target-must-be-gated" not in str(options["env"])
    assert "requested-environment-must-be-gated" not in str(options["env"])
    assert options["cwd"] != str(request.working_directory)
    assert options["creationflags"] & 0x00000200
    assert "start_new_session" not in options
    assert events.index("assign") < events.index("capture_start")
    assert events.index("capture_start") < events.index("observer")
    assert events.index("observer") < events.index("payload_write")
    assert events.index("payload_write") < events.index("target")
    assert FakeProcess.stdin.closed is True


def test_start_gate_write_side_effect_then_exception_is_launch_uncertain(
    tmp_path: Path,
) -> None:
    class SideEffectThenRaisePipe:
        def __init__(self) -> None:
            self.data = bytearray()
            self.closed = False

        def write(self, value: bytes) -> int:
            self.data.extend(value)
            raise OSError("synthetic post-write exception")

        def flush(self) -> None:
            raise AssertionError("failed write must not reach flush")

        def close(self) -> None:
            self.closed = True

    pipe = SideEffectThenRaisePipe()
    token = "windows-test-start-token"
    managed = ManagedProcess(
        process=object(),
        target=ProcessTarget(
            pid=123,
            start_token=token,
            start_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        ),
        start_gate=_ProcessStartGate(
            pipe,
            deadline_monotonic_ns=time.monotonic_ns() + 10_000_000_000,
        ),
    )

    with pytest.raises(ProcessStartGateReleaseError) as caught:
        PlatformProcessTreeAdapter(os_name="nt").release_start_gate(
            managed,
            _request(tmp_path, "-c", "pass"),
        )

    header, delivered_payload = bytes(pipe.data).split(b"\n", 1)
    assert int(header) == len(delivered_payload)
    assert caught.value.may_have_started is True
    assert pipe.closed is True


def test_posix_process_group_mode_refuses_non_authoritative_launch(
    tmp_path: Path,
) -> None:
    def forbidden_popen(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("POSIX refusal must happen before process creation")

    adapter = PlatformProcessTreeAdapter(
        os_name="posix",
        popen_factory=forbidden_popen,
    )

    assert adapter.isolation_mode == "posix_process_group_non_authoritative"
    with pytest.raises(RuntimeError, match="Authoritative POSIX"):
        adapter.spawn(_request(tmp_path, "-c", "pass"))


@pytest.mark.parametrize(
    ("assigned_count", "listed_count", "message"),
    [
        (2, 1, "incomplete"),
        (4_097, 4_096, "fixed bound"),
    ],
)
def test_windows_job_pid_list_rejects_partial_or_over_capacity_results(
    assigned_count: int,
    listed_count: int,
    message: str,
) -> None:
    information = _JobObjectBasicProcessIdList()
    information.NumberOfAssignedProcesses = assigned_count
    information.NumberOfProcessIdsInList = listed_count
    for index in range(min(listed_count, len(information.ProcessIdList))):
        information.ProcessIdList[index] = index + 1

    with pytest.raises(RuntimeError, match=message):
        CtypesWindowsJobApi._validated_process_ids(information)


def test_success_is_bounded_content_addressed_and_excludes_raw_launch_data(
    tmp_path: Path,
) -> None:
    secret_argument = "raw-secret-argument-must-not-enter-provenance"
    code = (
        "import sys; "
        "sys.stdout.buffer.write(b'bounded-output'); "
        "sys.stderr.buffer.write(b'bounded-warning')"
    )
    result = BoundedProcessTreeRunner().run(
        _request(tmp_path, "-c", code, secret_argument)
    )

    assert result.succeeded is True
    assert result.stdout == b"bounded-output"
    assert result.stderr == b"bounded-warning"
    assert result.record.exit_code == 0
    assert result.record.workload_released is True
    assert result.record.workload_release_status == "released"
    assert result.record.workload_timing_scope == (
        "release_attempt_to_confirmed_empty_tree_upper_bound"
    )
    assert 0.0 <= result.record.workload_elapsed_monotonic_seconds
    assert (
        result.record.workload_elapsed_monotonic_seconds
        <= result.record.elapsed_monotonic_seconds
    )
    assert result.record.target_start_token_hash is not None
    assert result.record.target_identity_confirmed is True
    assert result.record.final_active_processes == 0
    assert result.record.empty_tree_confirmed is True
    assert result.record.fallback_used is False
    assert result.record.stdout.sha256 == hashlib.sha256(result.stdout).hexdigest()
    assert result.record.stderr.sha256 == hashlib.sha256(result.stderr).hexdigest()
    assert result.record.stdout.stream_complete is True
    assert result.record.stderr.stream_complete is True
    serialized = result.record.canonical_json_bytes()
    assert secret_argument.encode() not in serialized
    assert str(tmp_path).encode() not in serialized

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["workload_released"] = False
    with pytest.raises(
        ValidationError,
        match="release boolean differs|Unreleased workload|Successful",
    ):
        ProcessTreeExecutionRecord.model_validate(payload)

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["elapsed_monotonic_seconds"] += 1.0
    with pytest.raises(ValidationError, match="ID differs"):
        ProcessTreeExecutionRecord.model_validate(payload)

    forged_summary = result.record.stdout.model_copy(
        update={"captured_sha256": "0" * 64}
    )
    forged_record = result.record.model_copy(update={"stdout": forged_summary})
    forged_base = forged_record.model_dump(
        mode="python",
        round_trip=True,
        exclude={"record_id"},
    )
    forged_record = forged_record.model_copy(
        update={"record_id": content_id("process_execution", forged_base)}
    )
    with pytest.raises((ValidationError, ValueError), match="summary|hash"):
        BoundedProcessResult(
            record=forged_record,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    mutated_stdout = b"X" + result.stdout[1:]
    with pytest.raises(ValueError, match="stdout hash"):
        BoundedProcessResult(
            record=result.record,
            stdout=mutated_stdout,
            stderr=result.stderr,
        )


def test_cold_validation_rejects_impossible_bounds_and_release_state(
    tmp_path: Path,
) -> None:
    result = BoundedProcessTreeRunner().run(
        _request(tmp_path, "-c", "print('abc', end='')")
    )
    assert result.succeeded is True

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["stdout_limit_bytes"] = 1
    with pytest.raises(ValidationError, match="configured byte limit"):
        ProcessTreeExecutionRecord.model_validate(_rehash_execution_payload(payload))

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["argument_count"] = 256
    with pytest.raises(ValidationError, match="less than or equal to 255"):
        ProcessTreeExecutionRecord.model_validate(_rehash_execution_payload(payload))

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["process_id"] = 0x1_0000_0000
    with pytest.raises(ValidationError, match="less than or equal"):
        ProcessTreeExecutionRecord.model_validate(_rehash_execution_payload(payload))

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["target_process_group_id"] = result.record.process_id
    with pytest.raises(ValidationError, match="must be paired"):
        ProcessTreeExecutionRecord.model_validate(_rehash_execution_payload(payload))

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["workload_released"] = False
    payload["workload_release_status"] = "uncertain"
    with pytest.raises(ValidationError, match="requires a start-gate failure"):
        ProcessTreeExecutionRecord.model_validate(_rehash_execution_payload(payload))

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["workload_timing_scope"] = (
        "release_attempt_to_runner_finish_unconfirmed_interval"
    )
    with pytest.raises(ValidationError, match="scope differs"):
        ProcessTreeExecutionRecord.model_validate(_rehash_execution_payload(payload))


def test_timeout_cold_validation_binds_termination_to_empty_tree(
    tmp_path: Path,
) -> None:
    result = BoundedProcessTreeRunner().run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(30)",
            timeout_seconds=0.1,
        )
    )
    assert result.record.failure_code == "process_timeout"

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["final_active_processes"] = 1
    payload["empty_tree_confirmed"] = False
    with pytest.raises(ValidationError, match="differs from final empty-tree"):
        ProcessTreeExecutionRecord.model_validate(_rehash_execution_payload(payload))


def test_execution_record_never_persists_the_raw_executable_basename(
    tmp_path: Path,
) -> None:
    secret_executable = tmp_path / "lowentropysecret.exe"

    class FailingAdapter:
        isolation_mode = "test_spawn_failure"

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            del request
            raise OSError("synthetic start failure")

    request = replace(
        _request(tmp_path, "-c", "pass"),
        command=(str(secret_executable.resolve()), "-c", "pass"),
    )
    result = BoundedProcessTreeRunner(adapter=FailingAdapter()).run(request)  # type: ignore[arg-type]

    assert result.record.failure_code == "process_start_failure"
    assert result.record.workload_release_status == "not_attempted"
    assert secret_executable.name.encode() not in result.record.canonical_json_bytes()


def test_forced_output_seal_cannot_mutate_the_published_observation() -> None:
    entered = threading.Event()
    released = threading.Event()

    class DelayedPipe:
        def read(self, size: int) -> bytes:
            assert size > 0
            entered.set()
            released.wait(timeout=1.0)
            return b"late-secret-bytes"

        def close(self) -> None:
            released.set()

    capture = _BoundedPipeCapture(DelayedPipe(), limit_bytes=4)
    capture.start()
    assert entered.wait(timeout=1.0)
    capture.seal_incomplete()
    capture.close_pipe()
    assert capture.join(1.0)
    summary, captured = capture.snapshot()

    assert summary.stream_complete is False
    assert summary.byte_count == 0
    assert summary.sha256 == hashlib.sha256(b"").hexdigest()
    assert captured == b""
    assert capture.io_failed.is_set()


def test_nonzero_exit_has_fixed_sanitized_failure_and_no_fallback(
    tmp_path: Path,
) -> None:
    sensitive_detail = "provider-secret-error-detail"
    code = f"import sys; sys.stderr.write('{sensitive_detail}'); raise SystemExit(7)"
    result = BoundedProcessTreeRunner().run(_request(tmp_path, "-c", code))

    assert result.record.status == "failed"
    assert result.record.failure_code == "process_exit_nonzero"
    assert result.record.failure_message == (
        "Bounded process failed closed (process_exit_nonzero)"
    )
    assert result.record.exit_code == 7
    assert result.record.workload_released is True
    assert result.record.workload_release_status == "released"
    assert result.record.tree_termination_requested is False
    assert result.record.fallback_used is False
    assert sensitive_detail.encode() in result.stderr
    assert sensitive_detail.encode() not in result.record.canonical_json_bytes()

    payload = result.record.model_dump(mode="python", round_trip=True)
    payload["workload_released"] = False
    with pytest.raises(
        ValidationError,
        match="release boolean differs|Unreleased workload",
    ):
        ProcessTreeExecutionRecord.model_validate(payload)


def test_start_exception_is_sanitized_into_a_closed_failure(tmp_path: Path) -> None:
    def failing_popen(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("local secret path and operating-system detail")

    adapter = PlatformProcessTreeAdapter(popen_factory=failing_popen)
    result = BoundedProcessTreeRunner(adapter=adapter).run(
        _request(tmp_path, "-c", "pass")
    )

    assert result.record.status == "failed"
    assert result.record.failure_code == "process_start_failure"
    assert result.record.process_id is None
    assert result.record.workload_released is False
    assert result.record.workload_elapsed_monotonic_seconds == 0.0
    assert result.record.workload_timing_scope == "not_observed_no_release_attempt"
    assert result.stdout == b""
    assert result.stderr == b""
    assert b"local secret" not in result.record.canonical_json_bytes()


def test_process_bootstrap_rejects_trailing_frame_bytes_without_launching(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "trailing-frame-target-launched.txt"
    payload = json.dumps(
        {
            "command": [
                str(Path(sys.executable).resolve()),
                "-c",
                "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
                str(marker),
            ],
            "deadline_monotonic_ns": time.monotonic_ns() + 10_000_000_000,
            "environment": dict(os.environ),
            "working_directory": str(tmp_path.resolve()),
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    frame = str(len(payload)).encode("ascii") + b"\n" + payload + b"trailing"
    bootstrap = (
        Path(__file__).parents[2]
        / "app/backend/rei/evaluation/process_start_bootstrap.py"
    ).resolve()
    bootstrap_python = Path(getattr(sys, "_base_executable", sys.executable)).resolve()

    completed = subprocess.run(
        [str(bootstrap_python), "-I", "-S", str(bootstrap)],
        input=frame,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
        timeout=5.0,
    )

    assert completed.returncode == 120
    assert not marker.exists()


def test_process_bootstrap_rejects_an_expired_deadline_without_launching(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "expired-bootstrap-target-launched.txt"
    payload = json.dumps(
        {
            "command": [
                str(Path(sys.executable).resolve()),
                "-c",
                "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
                str(marker),
            ],
            "deadline_monotonic_ns": 1,
            "environment": dict(os.environ),
            "working_directory": str(tmp_path.resolve()),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    frame = str(len(payload)).encode("ascii") + b"\n" + payload
    bootstrap = (
        Path(__file__).parents[2]
        / "app/backend/rei/evaluation/process_start_bootstrap.py"
    ).resolve()
    bootstrap_python = Path(getattr(sys, "_base_executable", sys.executable)).resolve()

    completed = subprocess.run(
        [str(bootstrap_python), "-I", "-S", str(bootstrap)],
        input=frame,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=5.0,
    )

    assert completed.returncode == 123
    assert not marker.exists()


@pytest.mark.parametrize("failure_stage", ["assign", "payload_pipe"])
def test_windows_bootstrap_setup_failure_never_exposes_requested_command(
    tmp_path: Path,
    failure_stage: str,
) -> None:
    launched_commands: list[list[str]] = []
    events: list[str] = []

    class FailingPipe:
        closed = False
        bytes_written = 0

        def write(self, value: bytes) -> int:
            events.append("payload_write")
            if failure_stage == "payload_pipe":
                raise OSError("synthetic pipe failure")
            self.bytes_written += len(value)
            return len(value)

        def flush(self) -> None:
            events.append("payload_flush")

        def close(self) -> None:
            self.closed = True
            events.append("stdin_close")

    class FakeProcess:
        pid = 876
        stdin = FailingPipe()
        stdout = BytesIO()
        stderr = BytesIO()
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            self.returncode = 1
            events.append("root_kill")

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            self.returncode = 1 if self.returncode is None else self.returncode
            return self.returncode

    process = FakeProcess()

    def fake_popen(command: list[str], **_options: Any) -> FakeProcess:
        launched_commands.append(command)
        return process

    class FakeJobApi:
        closed = False
        terminated = False

        def create_kill_on_close_job(self) -> object:
            return object()

        def assign(self, job: object, assigned: FakeProcess) -> None:
            del job, assigned
            events.append("assign")
            if failure_stage == "assign":
                raise OSError("synthetic assign failure")

        def process_start_token(self, assigned: FakeProcess) -> str:
            del assigned
            return "bootstrap-start-token"

        def active_processes(self, job: object) -> int:
            del job
            return 0

        def active_process_ids(self, job: object) -> tuple[int, ...]:
            del job
            return ()

        def terminate(self, job: object) -> None:
            del job
            self.terminated = True
            process.returncode = 1
            events.append("job_terminate")

        def close(self, job: object) -> None:
            del job
            self.closed = True
            events.append("job_close")

    job_api = FakeJobApi()
    adapter = PlatformProcessTreeAdapter(
        os_name="nt",
        popen_factory=fake_popen,
        windows_job_api=job_api,
    )
    requested_secret = "requested-target-must-never-launch"

    result = BoundedProcessTreeRunner(adapter=adapter).run(
        _request(tmp_path, "-c", requested_secret)
    )

    assert result.record.failure_code == (
        "process_start_failure"
        if failure_stage == "assign"
        else "process_start_gate_failure"
    )
    assert result.record.workload_released is False
    assert len(launched_commands) == 1
    assert requested_secret not in launched_commands[0]
    assert process.stdin.closed is True
    assert job_api.closed is True
    if failure_stage == "assign":
        assert result.record.process_id is None
        assert process.stdin.bytes_written == 0
        assert "payload_write" not in events
    else:
        assert result.record.process_id == 876
        assert result.record.termination_trigger == "start_gate_failure"
        assert result.record.tree_termination_succeeded is True
        assert result.record.empty_tree_confirmed is True
        assert events.index("assign") < events.index("payload_write")
        assert job_api.terminated is True


def test_unassigned_bootstrap_requires_proven_exit_before_closed_claim(
    tmp_path: Path,
) -> None:
    class NeverExitsProcess:
        pid = 877
        stdin = BytesIO()
        stdout = BytesIO()
        stderr = BytesIO()

        def poll(self) -> None:
            return None

        def kill(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            raise subprocess.TimeoutExpired("trusted-bootstrap", timeout)

    process = NeverExitsProcess()

    class AssignmentFailingJobApi:
        closed = False

        def create_kill_on_close_job(self) -> object:
            return object()

        def assign(self, job: object, assigned: NeverExitsProcess) -> None:
            del job, assigned
            raise OSError("synthetic assignment failure")

        def close(self, job: object) -> None:
            del job
            self.closed = True

    job_api = AssignmentFailingJobApi()
    adapter = PlatformProcessTreeAdapter(
        os_name="nt",
        popen_factory=lambda *_args, **_kwargs: process,
        windows_job_api=job_api,
    )

    result = BoundedProcessTreeRunner(adapter=adapter).run(
        _request(tmp_path, "-c", "requested-target-must-not-be-released")
    )

    assert result.record.failure_code == "process_start_failure"
    assert result.record.process_id is None
    assert result.record.workload_release_status == "not_attempted"
    assert result.record.workload_timing_scope == "not_observed_no_release_attempt"
    assert result.record.containment_closed is False
    assert job_api.closed is True
    assert process.poll() is None


def test_unassigned_bootstrap_eof_exit_never_uses_raw_pid_emergency_kill(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    emergency_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class EofExitProcess:
        pid = 878
        stdout = BytesIO()
        stderr = BytesIO()
        returncode: int | None = None

        def __init__(self) -> None:
            owner = self

            class EofStdin(BytesIO):
                def close(self) -> None:
                    owner.returncode = 120
                    events.append("stdin_eof_exit")
                    super().close()

            self.stdin = EofStdin()

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            raise AssertionError("EOF-proven exit must not be killed by PID")

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            assert self.returncode == 120
            return self.returncode

    process = EofExitProcess()

    class AssignmentFailingJobApi:
        def create_kill_on_close_job(self) -> object:
            return object()

        def assign(self, job: object, assigned: EofExitProcess) -> None:
            del job, assigned
            raise OSError("synthetic assignment failure")

        def close(self, job: object) -> None:
            del job
            events.append("job_close")

    def emergency_runner(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        emergency_calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=(), returncode=0)

    class TrackingSubprocess:
        def __getattr__(self, name: str) -> Any:
            return getattr(subprocess, name)

        run = staticmethod(emergency_runner)

    monkeypatch.setattr(process_tree_runner_module, "subprocess", TrackingSubprocess())
    adapter = PlatformProcessTreeAdapter(
        os_name="nt",
        popen_factory=lambda *_args, **_kwargs: process,
        windows_job_api=AssignmentFailingJobApi(),
    )

    result = BoundedProcessTreeRunner(adapter=adapter).run(
        _request(tmp_path, "-c", "requested-target-must-not-be-released")
    )

    assert result.record.failure_code == "process_start_failure"
    assert result.record.containment_closed is True
    assert process.returncode == 120
    assert events == ["stdin_eof_exit", "job_close"]
    assert emergency_calls == []


def test_unassigned_stubborn_bootstrap_uses_retained_process_handle_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    kill_calls = 0
    emergency_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class StubbornProcess:
        pid = 879
        stdin = BytesIO()
        stdout = BytesIO()
        stderr = BytesIO()
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            nonlocal kill_calls
            kill_calls += 1
            self.returncode = 1

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            assert self.returncode == 1
            return self.returncode

    process = StubbornProcess()

    class AssignmentFailingJobApi:
        def create_kill_on_close_job(self) -> object:
            return object()

        def assign(self, job: object, assigned: StubbornProcess) -> None:
            del job, assigned
            raise OSError("synthetic assignment failure")

        def close(self, job: object) -> None:
            del job

    def emergency_runner(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        emergency_calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=(), returncode=0)

    class TrackingSubprocess:
        def __getattr__(self, name: str) -> Any:
            return getattr(subprocess, name)

        run = staticmethod(emergency_runner)

    monkeypatch.setattr(process_tree_runner_module, "subprocess", TrackingSubprocess())
    adapter = PlatformProcessTreeAdapter(
        os_name="nt",
        popen_factory=lambda *_args, **_kwargs: process,
        windows_job_api=AssignmentFailingJobApi(),
    )

    result = BoundedProcessTreeRunner(adapter=adapter).run(
        _request(tmp_path, "-c", "requested-target-must-not-be-released")
    )

    assert result.record.failure_code == "process_start_failure"
    assert result.record.containment_closed is True
    assert kill_calls == 1
    assert emergency_calls == []


def test_output_limit_terminates_tree_and_retains_only_the_fixed_bound(
    tmp_path: Path,
) -> None:
    code = (
        "import sys,time; "
        "sys.stdout.buffer.write(b'x' * 131072); "
        "sys.stdout.buffer.flush(); "
        "time.sleep(30)"
    )
    result = BoundedProcessTreeRunner().run(
        _request(
            tmp_path,
            "-c",
            code,
            timeout_seconds=5.0,
            stdout_limit_bytes=1_024,
        )
    )

    assert result.record.status == "failed"
    assert result.record.failure_code == "process_stdout_limit_exceeded"
    assert result.record.termination_trigger == "stdout_limit"
    assert result.record.tree_termination_requested is True
    assert result.record.tree_termination_succeeded is True
    assert result.record.workload_released is True
    assert result.record.stdout.byte_count > 1_024
    assert result.record.stdout.captured_byte_count == 1_024
    assert result.record.stdout.truncated is True
    assert len(result.stdout) == 1_024
    assert (
        result.record.stdout.captured_sha256
        == hashlib.sha256(result.stdout).hexdigest()
    )


def test_fast_exit_cannot_race_past_a_late_output_limit(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.buffer.write(b'x' * 131072)"
    result = BoundedProcessTreeRunner().run(
        _request(
            tmp_path,
            "-c",
            code,
            stdout_limit_bytes=1_024,
        )
    )

    assert result.succeeded is False
    assert result.record.failure_code == "process_stdout_limit_exceeded"
    assert result.record.termination_trigger == "stdout_limit"
    assert result.record.empty_tree_confirmed is True
    assert result.record.containment_closed is True
    assert result.record.stdout.truncated is True
    assert result.record.stdout.captured_byte_count == 1_024


def test_hard_timeout_kills_the_spawned_process_tree(tmp_path: Path) -> None:
    marker = tmp_path / "grandchild-survived.txt"
    grandchild_code = (
        "from pathlib import Path; import sys,time; "
        "time.sleep(0.8); Path(sys.argv[1]).write_text('survived')"
    )
    parent_code = (
        "import subprocess,sys,time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL); "
        "time.sleep(30)"
    )
    result = BoundedProcessTreeRunner().run(
        _request(
            tmp_path,
            "-c",
            parent_code,
            grandchild_code,
            str(marker),
            timeout_seconds=0.2,
        )
    )

    assert result.record.status == "timed_out"
    assert result.record.failure_code == "process_timeout"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.tree_termination_requested is True
    assert result.record.tree_termination_succeeded is True
    assert result.record.fallback_used is False
    time.sleep(1.0)
    assert not marker.exists(), "hard timeout left a grandchild process alive"


def test_root_exit_settling_never_allows_a_descendant_past_hard_deadline(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "settling-descendant-survived.txt"
    grandchild_code = (
        "from pathlib import Path; import sys,time; "
        "time.sleep(0.3); Path(sys.argv[1]).touch()"
    )
    parent_code = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL)"
    )

    result = BoundedProcessTreeRunner().run(
        _request(
            tmp_path,
            "-c",
            parent_code,
            grandchild_code,
            str(marker),
            timeout_seconds=0.1,
        )
    )

    assert result.record.failure_code in {"process_timeout", "process_tree_leak"}
    assert result.record.termination_trigger in {"hard_timeout", "tree_leak"}
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    time.sleep(0.5)
    assert not marker.exists()


def test_clean_root_exit_with_lingering_grandchild_fails_closed_and_kills_tree(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "root-exit-grandchild-survived.txt"
    grandchild_code = (
        "from pathlib import Path; import sys,time; "
        "time.sleep(0.8); Path(sys.argv[1]).write_text('survived')"
    )
    parent_code = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL)"
    )
    result = BoundedProcessTreeRunner().run(
        _request(
            tmp_path,
            "-c",
            parent_code,
            grandchild_code,
            str(marker),
        )
    )

    assert result.record.status == "failed"
    assert result.record.failure_code == "process_tree_leak"
    assert result.record.termination_trigger == "tree_leak"
    assert result.record.tree_termination_succeeded is True
    assert result.record.final_active_processes == 0
    assert result.record.empty_tree_confirmed is True
    time.sleep(1.0)
    assert not marker.exists(), "clean root exit escaped process-tree containment"


@pytest.mark.skipif(os.name != "nt", reason="Win32 detached-process regression")
def test_windows_bootstrap_contains_immediate_detached_requested_child(
    tmp_path: Path,
) -> None:
    pythonw = Path(sys.executable).resolve().with_name("pythonw.exe")
    if not pythonw.is_file():
        pytest.skip("adjacent pythonw.exe is required for hidden detached regression")
    marker = tmp_path / "detached-requested-child-survived.txt"
    child_code = (
        "from pathlib import Path; import sys,time; "
        "time.sleep(0.8); Path(sys.argv[1]).write_text('survived')"
    )
    target_code = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.argv[1], '-c', sys.argv[2], sys.argv[3]], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL, close_fds=True, "
        "creationflags=subprocess.DETACHED_PROCESS | "
        "subprocess.CREATE_NEW_PROCESS_GROUP)"
    )

    result = BoundedProcessTreeRunner().run(
        _request(
            tmp_path,
            "-c",
            target_code,
            str(pythonw),
            child_code,
            str(marker),
        )
    )

    assert result.record.failure_code == "process_tree_leak"
    assert result.record.tree_termination_succeeded is True
    assert result.record.final_active_processes == 0
    assert result.record.empty_tree_confirmed is True
    time.sleep(1.0)
    assert not marker.exists(), "detached requested child escaped the Job Object"


def test_lifecycle_observer_order_exposes_runtime_only_target_for_telemetry(
    tmp_path: Path,
) -> None:
    events: list[tuple[str, object]] = []
    rss_readings: list[int] = []

    class Observer:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            events.append(("started", context.target.start_token_hash))
            assert context.process_tree_rss_available is True
            assert context.process_tree_rss_source == (
                "windows_job_object_working_set_sum"
            )
            rss_readings.append(context.read_process_tree_rss_bytes())

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            events.append(("poll", context.target.pid))

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context
            events.append(("before", trigger))

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context
            events.append(("after", outcome.succeeded))

    result = BoundedProcessTreeRunner(observer=Observer()).run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(30)",
            timeout_seconds=0.1,
        )
    )

    names = [name for name, _value in events]
    assert names[0] == "started"
    assert "poll" in names
    assert "before" not in names
    assert names[-1] == "after"
    assert result.record.failure_code == "process_timeout"
    assert rss_readings and rss_readings[0] > 0


def test_observer_polling_reuses_one_bounded_dispatcher_thread(
    tmp_path: Path,
) -> None:
    callback_thread_ids: set[int] = set()
    poll_calls = 0

    class ThreadRecordingObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context
            callback_thread_ids.add(threading.get_ident())

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            nonlocal poll_calls
            del context
            callback_thread_ids.add(threading.get_ident())
            poll_calls += 1

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context, trigger
            callback_thread_ids.add(threading.get_ident())

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome
            callback_thread_ids.add(threading.get_ident())

    result = BoundedProcessTreeRunner(
        observer=ThreadRecordingObserver(),
        poll_interval_seconds=0.005,
    ).run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(0.15)",
            timeout_seconds=1.0,
        )
    )

    assert result.succeeded is True
    assert poll_calls >= 5
    assert len(callback_thread_ids) == 1
    dispatcher_thread_id = next(iter(callback_thread_ids))
    assert all(thread.ident != dispatcher_thread_id for thread in threading.enumerate())


def test_poll_observer_crossing_deadline_is_immediately_a_hard_timeout(
    tmp_path: Path,
) -> None:
    class FakeMonotonic:
        value = 0

        def __call__(self) -> int:
            return self.value

        def advance_past_deadline(self) -> None:
            self.value = 2_000_000_000

    clock = FakeMonotonic()
    events: list[str] = []

    class AdvancingObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context
            events.append("started")

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context
            events.append("poll")
            clock.advance_past_deadline()

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context
            events.append(f"before:{trigger}")

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome
            events.append("after")

    result = BoundedProcessTreeRunner(
        observer=AdvancingObserver(),
        monotonic_ns=clock,
    ).run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(30)",
            timeout_seconds=1.0,
        )
    )

    assert events == ["started", "poll", "after"]
    assert result.record.status == "timed_out"
    assert result.record.failure_code == "process_timeout"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.workload_released is True
    assert result.record.tree_termination_succeeded is True


def test_blocking_on_poll_cannot_retain_live_workload_to_its_marker(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "blocking-on-poll-workload-survived.txt"
    entered = threading.Event()
    release = threading.Event()

    class BlockingPollObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context
            entered.set()
            release.wait(timeout=10.0)

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context, trigger

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome

    code = (
        "from pathlib import Path; import sys,time; "
        "time.sleep(0.5); Path(sys.argv[1]).touch()"
    )
    started = time.monotonic()
    result = BoundedProcessTreeRunner(observer=BlockingPollObserver()).run(
        _request(
            tmp_path,
            "-c",
            code,
            str(marker),
            timeout_seconds=0.2,
        )
    )
    elapsed = time.monotonic() - started
    release.set()

    assert entered.is_set()
    assert elapsed < 1.0
    assert result.record.failure_code == "process_observer_failure"
    assert result.record.termination_trigger == "observer_failure"
    assert result.record.observer_callback_failed is True
    assert result.record.workload_release_status == "released"
    assert result.record.tree_termination_succeeded is True
    time.sleep(0.6)
    assert not marker.exists()


def test_blocking_on_poll_is_capped_by_absolute_hard_deadline(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "hard-deadline-callback-marker.txt"
    poll_entered = threading.Event()

    class SlowPollObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context
            poll_entered.set()
            time.sleep(0.2)

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context, trigger

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome

    result = BoundedProcessTreeRunner(observer=SlowPollObserver()).run(
        _request(
            tmp_path,
            "-c",
            (
                "from pathlib import Path; import sys,time; time.sleep(0.08); "
                "Path(sys.argv[1]).touch()"
            ),
            str(marker),
            timeout_seconds=0.05,
        )
    )

    assert poll_entered.is_set()
    assert result.record.status == "timed_out"
    assert result.record.failure_code == "process_timeout"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.observer_callback_failed is True
    assert result.record.workload_release_status == "released"
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    time.sleep(0.3)
    assert not marker.exists()


def test_timed_out_dispatcher_is_retired_before_runner_reuse(
    tmp_path: Path,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    callback_finished = threading.Event()
    started_calls = 0
    block_first_poll = True

    class OneBlockingPollObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            nonlocal started_calls
            del context
            started_calls += 1

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            nonlocal block_first_poll
            del context
            if not block_first_poll:
                return
            block_first_poll = False
            entered.set()
            release.wait(timeout=10.0)
            callback_finished.set()

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context, trigger

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome

    runner = BoundedProcessTreeRunner(observer=OneBlockingPollObserver())
    first = runner.run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(0.5)",
            timeout_seconds=0.2,
        )
    )
    first_dispatcher = runner._observer_dispatcher

    assert entered.is_set()
    assert first.record.failure_code == "process_observer_failure"
    assert first_dispatcher is not None
    assert first_dispatcher._accepting is False
    assert first_dispatcher._retire_requested.is_set()

    release.set()
    assert callback_finished.wait(timeout=1.0)
    assert first_dispatcher._stopped.wait(timeout=1.0)

    second = runner.run(
        _request(
            tmp_path,
            "-c",
            "pass",
            timeout_seconds=1.0,
        )
    )

    assert second.succeeded is True
    assert started_calls == 2
    assert runner._observer_dispatcher is None


def test_on_started_failure_never_releases_the_requested_workload(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "on-started-target-launched.txt"

    class StartFailingObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context
            assert not marker.exists()
            raise RuntimeError("secret baseline failure")

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context
            assert trigger == "observer_failure"

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context
            assert outcome.succeeded is True

    result = BoundedProcessTreeRunner(observer=StartFailingObserver()).run(
        _request(
            tmp_path,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
            str(marker),
        )
    )

    assert result.record.failure_code == "process_observer_failure"
    assert result.record.termination_trigger == "observer_failure"
    assert result.record.workload_released is False
    assert result.record.tree_termination_requested is True
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert not marker.exists()
    assert b"secret baseline" not in result.record.canonical_json_bytes()


def test_blocking_on_started_is_bounded_and_never_releases_workload(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "blocking-on-started-target-launched.txt"
    entered = threading.Event()
    release = threading.Event()
    events: list[str] = []

    class BlockingStartObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context
            events.append("started")
            entered.set()
            release.wait(timeout=10.0)

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context
            events.append("poll")

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context, trigger
            events.append("before")

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome
            events.append("after")

    started = time.monotonic()
    result = BoundedProcessTreeRunner(observer=BlockingStartObserver()).run(
        _request(
            tmp_path,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
            str(marker),
            timeout_seconds=0.1,
        )
    )
    elapsed = time.monotonic() - started
    release.set()

    assert entered.is_set()
    assert elapsed < 1.0
    assert events == ["started"]
    assert result.record.status == "timed_out"
    assert result.record.failure_code == "process_timeout"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.observer_callback_failed is True
    assert result.record.workload_release_status == "not_attempted"
    assert result.record.tree_termination_succeeded is True
    assert not marker.exists()


def test_start_gate_release_failure_never_launches_target_and_closes_tree(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "release-failure-target-launched.txt"
    inner = PlatformProcessTreeAdapter()

    class ReleaseFailingAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            return inner.spawn(request)

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            del request
            managed.start_gate.close_safely()
            raise ProcessStartGateReleaseError(may_have_started=False)

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            return inner.inspect_tree(managed)

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            return inner.terminate_tree(managed, timeout_seconds=timeout_seconds)

        def close_containment(self, managed: ManagedProcess) -> bool:
            return inner.close_containment(managed)

    result = BoundedProcessTreeRunner(adapter=ReleaseFailingAdapter()).run(
        _request(
            tmp_path,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
            str(marker),
        )
    )

    assert result.record.failure_code == "process_start_gate_failure"
    assert result.record.termination_trigger == "start_gate_failure"
    assert result.record.workload_released is False
    assert result.record.workload_release_status == "not_attempted"
    assert result.record.workload_elapsed_monotonic_seconds == 0.0
    assert result.record.workload_timing_scope == "not_observed_no_release_attempt"
    assert result.record.tree_termination_requested is True
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert not marker.exists()
    assert b"secret release" not in result.record.canonical_json_bytes()


def test_ambiguous_start_gate_release_is_recorded_and_tree_is_closed(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "ambiguous-release-target-survived.txt"
    inner = PlatformProcessTreeAdapter()

    class AmbiguousReleaseAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            return inner.spawn(request)

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            inner.release_start_gate(managed, request)
            raise OSError("secret post-release failure")

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            return inner.inspect_tree(managed)

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            return inner.terminate_tree(managed, timeout_seconds=timeout_seconds)

        def close_containment(self, managed: ManagedProcess) -> bool:
            return inner.close_containment(managed)

    result = BoundedProcessTreeRunner(adapter=AmbiguousReleaseAdapter()).run(
        _request(
            tmp_path,
            "-c",
            (
                "from pathlib import Path; import sys,time; time.sleep(0.8); "
                "Path(sys.argv[1]).touch()"
            ),
            str(marker),
        )
    )

    assert result.record.failure_code == "process_start_gate_failure"
    assert result.record.termination_trigger == "start_gate_failure"
    assert result.record.workload_released is False
    assert result.record.workload_release_status == "uncertain"
    assert result.record.workload_elapsed_monotonic_seconds >= 0.0
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    time.sleep(1.0)
    assert not marker.exists()
    assert b"secret post-release" not in result.record.canonical_json_bytes()


def test_deadline_expiring_during_start_observer_never_releases_workload(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "expired-before-release-target-launched.txt"

    class SlowStartObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context
            time.sleep(0.05)

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context
            assert trigger == "hard_timeout"

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context
            assert outcome.succeeded is True

    result = BoundedProcessTreeRunner(observer=SlowStartObserver()).run(
        _request(
            tmp_path,
            "-c",
            "from pathlib import Path; import sys; Path(sys.argv[1]).touch()",
            str(marker),
            timeout_seconds=0.01,
        )
    )

    assert result.record.status == "timed_out"
    assert result.record.failure_code == "process_timeout"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.workload_released is False
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert not marker.exists()


def test_lifecycle_observer_failure_kills_tree_and_is_sanitized(
    tmp_path: Path,
) -> None:
    events: list[str] = []

    class FailingObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context
            events.append("started")

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context
            events.append("poll")
            raise RuntimeError("secret telemetry failure detail")

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context, trigger
            events.append("before")

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome
            events.append("after")

    result = BoundedProcessTreeRunner(observer=FailingObserver()).run(
        _request(tmp_path, "-c", "import time; time.sleep(30)")
    )

    assert events == ["started", "poll", "before", "after"]
    assert result.record.failure_code == "process_observer_failure"
    assert result.record.workload_released is True
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert b"secret telemetry" not in result.record.canonical_json_bytes()


def test_blocking_before_termination_cannot_delay_live_tree_kill(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "blocking-before-termination-workload-survived.txt"
    before_entered = threading.Event()
    release = threading.Event()

    class BlockingTerminationObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context
            assert trigger == "stdout_limit"
            before_entered.set()
            release.wait(timeout=10.0)

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome

    code = (
        "from pathlib import Path; import sys,time; "
        "sys.stdout.buffer.write(b'x' * 131072); sys.stdout.buffer.flush(); "
        "time.sleep(0.5); Path(sys.argv[1]).touch()"
    )
    started = time.monotonic()
    result = BoundedProcessTreeRunner(observer=BlockingTerminationObserver()).run(
        _request(
            tmp_path,
            "-c",
            code,
            str(marker),
            timeout_seconds=1.0,
            stdout_limit_bytes=1_024,
        )
    )
    elapsed = time.monotonic() - started
    release.set()

    assert before_entered.is_set()
    assert elapsed < 1.0
    assert result.record.failure_code == "process_stdout_limit_exceeded"
    assert result.record.termination_trigger == "stdout_limit"
    assert result.record.observer_callback_failed is True
    assert result.record.tree_termination_succeeded is True
    time.sleep(0.6)
    assert not marker.exists()


def test_termination_observer_failure_preserves_the_initial_timeout_trigger(
    tmp_path: Path,
) -> None:
    class FailingTerminationObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context
            assert trigger == "hard_timeout"
            raise RuntimeError("secret before-termination failure")

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context
            assert outcome.succeeded is True
            raise RuntimeError("secret after-termination failure")

    result = BoundedProcessTreeRunner(observer=FailingTerminationObserver()).run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(30)",
            timeout_seconds=0.1,
        )
    )

    assert result.record.status == "timed_out"
    assert result.record.failure_code == "process_timeout"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.observer_callback_failed is True
    assert result.record.tree_termination_succeeded is True
    canonical = result.record.canonical_json_bytes()
    assert b"secret before-termination" not in canonical
    assert b"secret after-termination" not in canonical


def test_posix_pid_reuse_guard_refuses_to_signal_an_unrelated_group() -> None:
    token = "original-posix-start-token"
    target = ProcessTarget(
        pid=321,
        start_token=token,
        start_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        process_group_id=321,
        session_id=321,
    )

    class ReusedPidInspector:
        def inspect(self, inspected: ProcessTarget) -> TreeInspectionOutcome:
            assert inspected == target
            return TreeInspectionOutcome(
                method="posix_session_membership",
                inspection_succeeded=True,
                target_identity_confirmed=False,
                active_processes=1,
                empty_tree_confirmed=False,
            )

    kill_calls: list[tuple[int, int]] = []
    adapter = PlatformProcessTreeAdapter(
        os_name="posix",
        posix_inspector=ReusedPidInspector(),  # type: ignore[arg-type]
        killpg=lambda pid, sig: kill_calls.append((pid, sig)),
    )
    managed = ManagedProcess(
        process=object(),
        target=target,
    )

    outcome = adapter.terminate_tree(managed, timeout_seconds=0.1)

    assert outcome.succeeded is False
    assert outcome.final_inspection.target_identity_confirmed is False
    assert kill_calls == []


@pytest.mark.parametrize(
    "probe_error",
    [None, PermissionError("group exists but cannot be signalled")],
)
def test_posix_empty_enumeration_requires_signal_zero_esrch(
    tmp_path: Path,
    probe_error: PermissionError | None,
) -> None:
    (tmp_path / "self").mkdir()
    (tmp_path / "self" / "stat").write_text("route through proc", encoding="utf-8")
    (tmp_path / "321").mkdir()
    probes: list[tuple[int, int]] = []

    def probe(process_group_id: int, sig: int) -> None:
        probes.append((process_group_id, sig))
        if probe_error is not None:
            raise probe_error

    inspector = PosixProcessTreeInspector(
        proc_root=tmp_path,
        process_group_probe=probe,
    )
    token = "missing-stat-start-token"
    target = ProcessTarget(
        pid=321,
        start_token=token,
        start_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        process_group_id=321,
        session_id=321,
    )

    inspection = inspector.inspect(target)

    assert probes == [(321, 0)]
    assert inspection.inspection_succeeded is False
    assert inspection.empty_tree_confirmed is False
    assert inspection.active_processes is None


def test_posix_empty_enumeration_and_signal_zero_esrch_confirms_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def missing_group(process_group_id: int, sig: int) -> None:
        assert (process_group_id, sig) == (321, 0)
        raise ProcessLookupError(process_group_id)

    inspector = PosixProcessTreeInspector(
        proc_root=tmp_path,
        process_group_probe=missing_group,
    )
    monkeypatch.setattr(inspector, "_entries", lambda: ())
    token = "finished-process-start-token"
    target = ProcessTarget(
        pid=321,
        start_token=token,
        start_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        process_group_id=321,
        session_id=321,
    )

    inspection = inspector.inspect(target)

    assert inspection.inspection_succeeded is True
    assert inspection.target_identity_confirmed is True
    assert inspection.active_processes == 0
    assert inspection.empty_tree_confirmed is True


def test_posix_reused_process_group_without_matching_session_is_not_signalled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class ReusedGroupEntry:
        pid = 999
        process_group_id = 321
        session_id = 999
        start_token = "unrelated-process-start-token"

    inspector = PosixProcessTreeInspector(
        proc_root=tmp_path,
        process_group_probe=lambda process_group_id, sig: None,
    )
    monkeypatch.setattr(inspector, "_entries", lambda: (ReusedGroupEntry(),))
    token = "original-posix-start-token"
    target = ProcessTarget(
        pid=321,
        start_token=token,
        start_token_hash=hashlib.sha256(token.encode()).hexdigest(),
        process_group_id=321,
        session_id=321,
    )
    kill_calls: list[tuple[int, int]] = []
    adapter = PlatformProcessTreeAdapter(
        os_name="posix",
        posix_inspector=inspector,
        killpg=lambda pid, sig: kill_calls.append((pid, sig)),
    )

    outcome = adapter.terminate_tree(
        ManagedProcess(process=object(), target=target),
        timeout_seconds=0.1,
    )

    assert outcome.succeeded is False
    assert outcome.final_inspection.inspection_succeeded is True
    assert outcome.final_inspection.target_identity_confirmed is False
    assert outcome.final_inspection.empty_tree_confirmed is False
    assert kill_calls == []


def test_termination_uncertainty_is_never_reported_as_a_plain_timeout(
    tmp_path: Path,
) -> None:
    inner = PlatformProcessTreeAdapter()

    class UncertainTerminationAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            return inner.spawn(request)

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            inner.release_start_gate(managed, request)

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            return inner.inspect_tree(managed)

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            actual = inner.terminate_tree(
                managed,
                timeout_seconds=timeout_seconds,
            )
            assert actual.succeeded is True
            return TreeTerminationOutcome(
                method="test_unverified_tree_termination",
                succeeded=False,
                final_inspection=TreeInspectionOutcome(
                    method=actual.final_inspection.method,
                    inspection_succeeded=True,
                    target_identity_confirmed=True,
                    active_processes=1,
                    empty_tree_confirmed=False,
                ),
            )

        def close_containment(self, managed: ManagedProcess) -> bool:
            return inner.close_containment(managed)

    result = BoundedProcessTreeRunner(adapter=UncertainTerminationAdapter()).run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(30)",
            timeout_seconds=0.1,
        )
    )

    assert result.record.status == "failed"
    assert result.record.failure_code == "process_tree_termination_failure"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.tree_termination_succeeded is False
    assert result.record.empty_tree_confirmed is False
    assert result.record.workload_timing_scope == (
        "release_attempt_to_runner_finish_unconfirmed_interval"
    )


def test_termination_and_inspection_exceptions_return_a_closed_record(
    tmp_path: Path,
) -> None:
    inner = PlatformProcessTreeAdapter()

    class ExplodingAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            return inner.spawn(request)

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            inner.release_start_gate(managed, request)

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            del managed
            raise RuntimeError("secret inspection exception")

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            del managed, timeout_seconds
            raise RuntimeError("secret termination exception")

        def close_containment(self, managed: ManagedProcess) -> bool:
            inner.close_containment(managed)
            raise RuntimeError("secret close exception")

    result = BoundedProcessTreeRunner(adapter=ExplodingAdapter()).run(
        _request(
            tmp_path,
            "-c",
            "import time; time.sleep(30)",
            timeout_seconds=0.1,
        )
    )

    assert result.record.failure_code == "process_tree_termination_failure"
    assert result.record.tree_termination_succeeded is False
    assert result.record.empty_tree_confirmed is False
    assert result.record.containment_closed is False
    assert b"secret termination" not in result.record.canonical_json_bytes()
    assert b"secret close" not in result.record.canonical_json_bytes()


def test_containment_close_exception_returns_fail_closed_record(tmp_path: Path) -> None:
    inner = PlatformProcessTreeAdapter()

    class CloseExplodingAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            return inner.spawn(request)

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            inner.release_start_gate(managed, request)

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            return inner.inspect_tree(managed)

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            return inner.terminate_tree(managed, timeout_seconds=timeout_seconds)

        def close_containment(self, managed: ManagedProcess) -> bool:
            inner.close_containment(managed)
            raise RuntimeError("secret close exception")

    result = BoundedProcessTreeRunner(adapter=CloseExplodingAdapter()).run(
        _request(tmp_path, "-c", "pass")
    )

    assert result.record.failure_code == "process_containment_close_failure"
    assert result.record.containment_closed is False
    assert result.record.empty_tree_confirmed is True
    assert b"secret close" not in result.record.canonical_json_bytes()


@pytest.mark.parametrize("failing_capture_start", [1, 2])
def test_capture_thread_start_failure_closes_unreleased_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failing_capture_start: int,
) -> None:
    marker = tmp_path / f"capture-start-{failing_capture_start}-escaped.txt"
    original_start = threading.Thread.start
    capture_start_count = 0

    def selective_start(thread: threading.Thread) -> None:
        nonlocal capture_start_count
        target = getattr(thread, "_target", None)
        if isinstance(getattr(target, "__self__", None), _BoundedPipeCapture):
            capture_start_count += 1
            if capture_start_count == failing_capture_start:
                raise RuntimeError("secret capture-thread startup failure")
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", selective_start)
    code = "from pathlib import Path; import sys; Path(sys.argv[1]).touch()"

    result = BoundedProcessTreeRunner().run(_request(tmp_path, "-c", code, str(marker)))

    assert result.record.failure_code == "process_io_failure"
    assert result.record.termination_trigger == "io_failure"
    assert result.record.workload_release_status == "not_attempted"
    assert result.record.workload_timing_scope == "not_observed_no_release_attempt"
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert result.record.containment_closed is True
    assert result.record.stdout.stream_complete is False
    assert result.record.stderr.stream_complete is False
    assert b"secret capture-thread" not in result.record.canonical_json_bytes()
    time.sleep(0.2)
    assert not marker.exists()


def test_observer_dispatcher_start_failure_closes_unreleased_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    marker = tmp_path / "observer-dispatcher-start-escaped.txt"
    original_start = threading.Thread.start

    def selective_start(thread: threading.Thread) -> None:
        if thread.name == "rei-process-lifecycle-observer":
            raise RuntimeError("secret observer-dispatcher startup failure")
        original_start(thread)

    class PassiveObserver:
        def on_started(self, context: ProcessLifecycleContext) -> None:
            del context

        def on_poll(self, context: ProcessLifecycleContext) -> None:
            del context

        def before_termination(
            self,
            context: ProcessLifecycleContext,
            trigger: str,
        ) -> None:
            del context, trigger

        def after_termination(
            self,
            context: ProcessLifecycleContext,
            outcome: TreeTerminationOutcome,
        ) -> None:
            del context, outcome

    monkeypatch.setattr(threading.Thread, "start", selective_start)
    code = "from pathlib import Path; import sys; Path(sys.argv[1]).touch()"

    result = BoundedProcessTreeRunner(observer=PassiveObserver()).run(
        _request(tmp_path, "-c", code, str(marker))
    )

    assert result.record.failure_code == "process_observer_failure"
    assert result.record.termination_trigger == "observer_failure"
    assert result.record.observer_callback_failed is True
    assert result.record.workload_release_status == "not_attempted"
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert result.record.containment_closed is True
    assert b"secret observer-dispatcher" not in result.record.canonical_json_bytes()
    time.sleep(0.2)
    assert not marker.exists()


def test_observer_dispatcher_side_effect_then_start_exception_retires_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_start = threading.Thread.start
    started_workers: list[threading.Thread] = []

    def side_effect_then_raise(thread: threading.Thread) -> None:
        original_start(thread)
        if thread.name == "rei-process-lifecycle-observer":
            started_workers.append(thread)
            raise RuntimeError("secret post-start dispatcher failure")

    monkeypatch.setattr(threading.Thread, "start", side_effect_then_raise)

    dispatcher = _BoundedObserverDispatcher()

    assert len(started_workers) == 1
    assert dispatcher.stopped is True
    assert started_workers[0].is_alive() is False
    assert dispatcher.call(lambda: None, wait_seconds=0.01) == "failed"
    assert dispatcher.close_if_idle() is True
    assert not any(
        thread is started_workers[0] and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_injected_monotonic_exception_after_spawn_uses_trusted_cleanup_clock(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "sequence-clock-escaped.txt"
    clock_calls = 0

    def sequence_clock() -> int:
        nonlocal clock_calls
        clock_calls += 1
        if clock_calls == 1:
            return 1
        raise RuntimeError("secret injected monotonic failure")

    code = "from pathlib import Path; import sys; Path(sys.argv[1]).touch()"
    result = BoundedProcessTreeRunner(monotonic_ns=sequence_clock).run(
        _request(tmp_path, "-c", code, str(marker))
    )

    assert result.record.failure_code == "process_io_failure"
    assert result.record.workload_release_status == "not_attempted"
    assert result.record.workload_elapsed_monotonic_seconds == 0.0
    assert 0.0 <= result.record.elapsed_monotonic_seconds < 10.0
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert result.record.containment_closed is True
    assert b"secret injected monotonic" not in result.record.canonical_json_bytes()
    time.sleep(0.2)
    assert not marker.exists()


def test_rss_source_property_exception_after_spawn_closes_unreleased_tree(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "rss-source-property-escaped.txt"
    inner = PlatformProcessTreeAdapter()

    class ExplodingRssSourceAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        @property
        def process_tree_rss_source(self) -> str:
            raise RuntimeError("secret RSS source property failure")

        def process_tree_rss_bytes(self, managed: ManagedProcess) -> int:
            return inner.process_tree_rss_bytes(managed)

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            return inner.spawn(request)

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            inner.release_start_gate(managed, request)

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            return inner.inspect_tree(managed)

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            return inner.terminate_tree(managed, timeout_seconds=timeout_seconds)

        def close_containment(self, managed: ManagedProcess) -> bool:
            return inner.close_containment(managed)

    code = "from pathlib import Path; import sys; Path(sys.argv[1]).touch()"
    result = BoundedProcessTreeRunner(adapter=ExplodingRssSourceAdapter()).run(
        _request(tmp_path, "-c", code, str(marker))
    )

    assert result.record.failure_code == "process_io_failure"
    assert result.record.workload_release_status == "not_attempted"
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert result.record.containment_closed is True
    assert b"secret RSS source" not in result.record.canonical_json_bytes()
    time.sleep(0.2)
    assert not marker.exists()


def test_poll_exception_after_release_closes_live_tree_before_delayed_marker(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "poll-exception-live-tree-escaped.txt"
    inner = PlatformProcessTreeAdapter()

    class PollOnceProcess:
        def __init__(self, process: Any) -> None:
            self._process = process
            self._failed = False

        def __getattr__(self, name: str) -> Any:
            return getattr(self._process, name)

        def poll(self) -> int | None:
            if not self._failed:
                self._failed = True
                raise RuntimeError("secret process poll failure")
            return self._process.poll()

    class PollExplodingAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            managed = inner.spawn(request)
            return ManagedProcess(
                process=PollOnceProcess(managed.process),
                target=managed.target,
                containment=managed.containment,
                start_gate=managed.start_gate,
            )

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            inner.release_start_gate(managed, request)

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            return inner.inspect_tree(managed)

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            return inner.terminate_tree(managed, timeout_seconds=timeout_seconds)

        def close_containment(self, managed: ManagedProcess) -> bool:
            return inner.close_containment(managed)

    code = (
        "from pathlib import Path; import sys,time; "
        "time.sleep(0.5); Path(sys.argv[1]).touch()"
    )
    result = BoundedProcessTreeRunner(adapter=PollExplodingAdapter()).run(
        _request(tmp_path, "-c", code, str(marker))
    )

    assert result.record.failure_code == "process_io_failure"
    assert result.record.workload_release_status == "released"
    assert result.record.workload_timing_scope == (
        "release_attempt_to_confirmed_empty_tree_upper_bound"
    )
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert result.record.containment_closed is True
    assert b"secret process poll" not in result.record.canonical_json_bytes()
    time.sleep(0.7)
    assert not marker.exists()


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(17)])
def test_base_exception_after_spawn_cleans_tree_then_propagates(
    tmp_path: Path,
    interrupt: BaseException,
) -> None:
    marker = tmp_path / f"base-exception-{type(interrupt).__name__}-escaped.txt"
    inner = PlatformProcessTreeAdapter()
    clock_calls = 0
    termination: TreeTerminationOutcome | None = None
    containment_closed: bool | None = None

    def interrupting_clock() -> int:
        nonlocal clock_calls
        clock_calls += 1
        if clock_calls == 1:
            return 1
        raise interrupt

    class TrackingAdapter:
        @property
        def isolation_mode(self) -> str:
            return inner.isolation_mode

        def spawn(self, request: BoundedProcessRequest) -> ManagedProcess:
            return inner.spawn(request)

        def release_start_gate(
            self,
            managed: ManagedProcess,
            request: BoundedProcessRequest,
        ) -> None:
            inner.release_start_gate(managed, request)

        def inspect_tree(self, managed: ManagedProcess) -> TreeInspectionOutcome:
            return inner.inspect_tree(managed)

        def terminate_tree(
            self,
            managed: ManagedProcess,
            *,
            timeout_seconds: float,
        ) -> TreeTerminationOutcome:
            nonlocal termination
            termination = inner.terminate_tree(
                managed,
                timeout_seconds=timeout_seconds,
            )
            return termination

        def close_containment(self, managed: ManagedProcess) -> bool:
            nonlocal containment_closed
            containment_closed = inner.close_containment(managed)
            return containment_closed

    code = "from pathlib import Path; import sys; Path(sys.argv[1]).touch()"
    with pytest.raises(type(interrupt)):
        BoundedProcessTreeRunner(
            adapter=TrackingAdapter(),
            monotonic_ns=interrupting_clock,
        ).run(_request(tmp_path, "-c", code, str(marker)))

    assert termination is not None
    assert termination.succeeded is True
    assert termination.final_inspection.empty_tree_confirmed is True
    assert containment_closed is True
    time.sleep(0.2)
    assert not marker.exists()
