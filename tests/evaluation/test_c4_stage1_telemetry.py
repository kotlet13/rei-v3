from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import math
from pathlib import Path
import sys
import threading
import time

from pydantic import ValidationError
import pytest

from app.backend.rei.evaluation.c4_stage1_telemetry import (
    C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES,
    C4_STAGE1_TELEMETRY_CADENCE_SECONDS,
    C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS,
    C4_STAGE1_TELEMETRY_MAX_SAMPLES,
    C4Stage1TelemetryFinalizationOutcome,
    C4Stage1TelemetryFinalizationReceipt,
    C4Stage1TelemetryFinalizer,
    C4Stage1TelemetryIntent,
    C4Stage1TelemetryLifecycleController,
    C4Stage1TelemetryLifecycleError,
    C4Stage1TelemetryPersistenceError,
    C4Stage1TelemetryStateError,
    build_c4_stage1_bound_system_probe,
    c4_stage1_telemetry_policy,
    c4_stage1_zero_sample_failure_result,
    cold_verify_c4_stage1_telemetry_finalization,
    persist_c4_stage1_telemetry_intent,
)
from app.backend.rei.evaluation.process_tree_runner import (
    BoundedProcessRequest,
    ProcessLifecycleContext,
    ProcessOutputSummary,
    ProcessTarget,
    ProcessTreeExecutionRecord,
    TreeInspectionOutcome,
    TreeTerminationOutcome,
)
from app.backend.rei.evaluation.resource_telemetry import (
    BackgroundResourceTelemetrySample,
    BackgroundResourceTelemetrySamplerResult,
    BackgroundResourceTelemetrySamplerStatus,
    ResourceByteReading,
    ResourceTelemetryCudaDeviceIdentity,
    ResourceTelemetryProcessTarget,
    ResourceTelemetrySnapshot,
    SystemResourceTelemetryProbe,
)
from app.backend.rei.ids import canonical_json_bytes, content_id
from app.backend.rei.persistence import FileArtifactStore


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
CUDA_DEVICE_IDENTITY = ResourceTelemetryCudaDeviceIdentity.resolved(
    logical_device_index=0,
    physical_gpu_uuid="GPU-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    pci_bus_id="00000000:01:00.0",
)
CUDA_TOTAL_BYTES = C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES + 1024**3
PROCESS_TARGET_SUBJECT = ResourceTelemetryProcessTarget(
    root_process_id=1234,
    root_process_start_token_hash="4" * 64,
    process_scope="process_tree",
).measurement_subject_id


def _request(
    tmp_path: Path,
    *,
    timeout_seconds: float = 180.0,
) -> BoundedProcessRequest:
    return BoundedProcessRequest(
        workload_id="c4-stage1-workload",
        command_identity="pinned-provider-command",
        working_directory_identity="verified-snapshot-workdir",
        environment_identity="stage1-environment",
        command=(str(Path(sys.executable).resolve()), "-c", "pass"),
        working_directory=tmp_path.resolve(),
        environment={},
        timeout_seconds=timeout_seconds,
        stdout_limit_bytes=1024,
        stderr_limit_bytes=1024,
    )


def _intent(
    tmp_path: Path,
    *,
    timeout_seconds: float = 180.0,
    option_id: str = "enter_circle",
) -> C4Stage1TelemetryIntent:
    return C4Stage1TelemetryIntent.create(
        run_id="stage1-run",
        attempt_id="stage1-attempt-primary",
        screen_contract_id="stage1-screen-contract",
        screen_contract_sha256="0" * 64,
        worker_request_id="stage1-worker-request-primary-enter-circle",
        worker_request_sha256="9" * 64,
        option_id=option_id,
        provider_slot_id="primary",
        provider_id="longcat-pinned-snapshot",
        source_artifact_id="current-source-png",
        source_sha256="1" * 64,
        snapshot_manifest_id="snapshot-longcat-exact",
        snapshot_manifest_sha256="2" * 64,
        pipeline_spec_id="pipeline-longcat-stage1",
        pipeline_spec_sha256="3" * 64,
        process_request=_request(tmp_path, timeout_seconds=timeout_seconds),
        cuda_device=CUDA_DEVICE_IDENTITY,
    )


def _summary() -> ProcessOutputSummary:
    return ProcessOutputSummary(
        byte_count=0,
        captured_byte_count=0,
        sha256=EMPTY_SHA256,
        captured_sha256=EMPTY_SHA256,
        truncated=False,
        stream_complete=True,
    )


def _record(
    request: BoundedProcessRequest,
    *,
    command_identity: str | None = None,
    status: str = "succeeded",
) -> ProcessTreeExecutionRecord:
    started_at = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
    succeeded = status == "succeeded"
    payload = {
        "schema_version": "rei-process-tree-execution-v1",
        "runner_revision": "rei-process-tree-runner-v1",
        "workload_id": request.workload_id,
        "command_identity": command_identity or request.command_identity,
        "argument_count": len(request.command) - 1,
        "working_directory_identity": request.working_directory_identity,
        "environment_identity": request.environment_identity,
        "timeout_seconds": request.timeout_seconds,
        "stdout_limit_bytes": request.stdout_limit_bytes,
        "stderr_limit_bytes": request.stderr_limit_bytes,
        "platform_system": "windows",
        "isolation_mode": "windows_job_object_kill_on_close",
        "target_start_token_hash": "4" * 64,
        "target_process_group_id": None,
        "target_session_id": None,
        "started_at": started_at,
        "finished_at": started_at + timedelta(seconds=0.1),
        "elapsed_monotonic_seconds": 0.1,
        "workload_elapsed_monotonic_seconds": 0.05,
        "workload_timing_scope": (
            "release_attempt_to_confirmed_empty_tree_upper_bound"
        ),
        "process_id": 1234,
        "workload_released": True,
        "workload_release_status": "released",
        "exit_code": 0 if succeeded else 1,
        "status": status,
        "termination_trigger": "not_required",
        "failure_code": None if succeeded else "process_exit_nonzero",
        "failure_message": (
            None
            if succeeded
            else "Bounded process failed closed (process_exit_nonzero)"
        ),
        "stdout": _summary(),
        "stderr": _summary(),
        "tree_termination_requested": False,
        "tree_termination_succeeded": None,
        "tree_termination_method": None,
        "tree_inspection_method": "windows-job-active-processes",
        "final_active_processes": 0,
        "target_identity_confirmed": True,
        "empty_tree_confirmed": True,
        "containment_closed": True,
        "observer_callback_failed": False,
        "fallback_used": False,
    }
    return ProcessTreeExecutionRecord(
        record_id=content_id("process_execution", payload),
        **payload,
    )


def _reading(
    value: int,
    *,
    source: str,
    scope: str,
    subject: str,
) -> ResourceByteReading:
    return ResourceByteReading.measured(
        value,
        source=source,
        measurement_scope=scope,
        subject_id=subject,
    )


def _snapshot(
    *,
    rss: int,
    cuda_used: int,
    process_subject: str = PROCESS_TARGET_SUBJECT,
    cuda_subject: str = CUDA_DEVICE_IDENTITY.measurement_subject_id,
) -> ResourceTelemetrySnapshot:
    return ResourceTelemetrySnapshot(
        process_scope_rss_bytes=_reading(
            rss,
            source="windows-job-working-set",
            scope="process_scope_rss",
            subject=process_subject,
        ),
        system_ram_total_bytes=_reading(
            10_000,
            source="global-memory-status",
            scope="system_physical_memory",
            subject="system-memory-subject",
        ),
        system_ram_available_bytes=_reading(
            8_000,
            source="global-memory-status",
            scope="system_physical_memory",
            subject="system-memory-subject",
        ),
        cuda_vram_used_bytes=_reading(
            cuda_used,
            source="nvidia-smi-exact-device",
            scope="cuda_device_memory",
            subject=cuda_subject,
        ),
        cuda_vram_total_bytes=_reading(
            CUDA_TOTAL_BYTES,
            source="nvidia-smi-exact-device",
            scope="cuda_device_memory",
            subject=cuda_subject,
        ),
    )


def _cuda_identity() -> ResourceTelemetryCudaDeviceIdentity:
    return CUDA_DEVICE_IDENTITY


def _context(
    *,
    workload_id: str = "c4-stage1-workload",
    rss_reader=lambda: 123,
) -> ProcessLifecycleContext:
    start_token = "windows-filetime-123456"
    return ProcessLifecycleContext(
        workload_id=workload_id,
        target=ProcessTarget(
            pid=4321,
            start_token=start_token,
            start_token_hash=hashlib.sha256(start_token.encode("utf-8")).hexdigest(),
        ),
        isolation_mode="windows_job_object_kill_on_close",
        process_tree_rss_source="windows-job-working-set",
        _process_tree_rss_reader=rss_reader,
    )


def _sample(index: int, *, cuda_used: int = 100) -> BackgroundResourceTelemetrySample:
    started = index * 10
    return BackgroundResourceTelemetrySample(
        snapshot=_snapshot(rss=200 + index, cuda_used=cuda_used),
        probe_started_monotonic_ns=started,
        probe_finished_monotonic_ns=started + 2,
    )


def _result(
    *,
    state: str = "finished",
    samples: tuple[BackgroundResourceTelemetrySample, ...] | None = None,
    failure_code: str | None = None,
    status_sample_count: int | None = None,
    latest_sample: BackgroundResourceTelemetrySample | None = None,
) -> BackgroundResourceTelemetrySamplerResult:
    selected = (_sample(1), _sample(2)) if samples is None else samples
    count = len(selected) if status_sample_count is None else status_sample_count
    latest = (
        (selected[-1] if selected else None) if latest_sample is None else latest_sample
    )
    status = BackgroundResourceTelemetrySamplerStatus(
        state=state,
        sample_count=count,
        failure_code=failure_code,
        latest_sample=latest,
        sampled_cuda_vram_peak=(
            None
            if not selected
            else max(
                (sample.snapshot.cuda_vram_used_bytes for sample in selected),
                key=lambda reading: reading.value_bytes or 0,
            )
        ),
    )
    return BackgroundResourceTelemetrySamplerResult(
        status=status,
        samples=selected,
        sampling_overhead_monotonic_ns=sum(
            sample.sampling_overhead_monotonic_ns for sample in selected
        ),
    )


def test_stage1_telemetry_finalizer_persists_exact_pass_and_is_exactly_once(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    intent = _intent(tmp_path)
    store = FileArtifactStore(tmp_path / "runs")
    finalizer = C4Stage1TelemetryFinalizer(intent, artifact_store=store)

    outcome = finalizer.finalize(
        process_execution_record=_record(request),
        result=_result(),
    )

    assert outcome.durable_terminal_receipt is True
    assert outcome.technical_passed is True
    assert outcome.receipt.disposition == "passed"
    assert outcome.receipt.failure_codes == ()
    assert outcome.receipt.sampled_cuda_peak_is_lower_bound is True
    assert outcome.receipt.absence_of_transient_cuda_breach_proven is False
    assert outcome.receipt.intent.model_calls_before_intent == 0
    assert "model_calls" not in type(outcome.receipt).model_fields
    assert outcome.samples_artifact is not None
    assert "model_calls" not in type(outcome.samples_artifact).model_fields
    assert outcome.samples_storage is not None
    assert outcome.receipt_storage is not None
    assert store.read_bytes(outcome.samples_storage.storage_id) == canonical_json_bytes(
        outcome.samples_artifact
    )
    assert store.read_bytes(outcome.receipt_storage.storage_id) == canonical_json_bytes(
        outcome.receipt
    )
    assert finalizer.outcome == outcome
    assert (
        cold_verify_c4_stage1_telemetry_finalization(
            FileArtifactStore(tmp_path / "runs"),
            outcome.receipt_storage,
        )
        == outcome
    )
    with pytest.raises(C4Stage1TelemetryStateError, match="only once"):
        finalizer.finalize(
            process_execution_record=_record(request),
            result=_result(),
        )


def test_stage1_finalization_outcome_rejects_storage_descriptor_swap(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path)
    intent = _intent(tmp_path)
    store = FileArtifactStore(tmp_path / "runs")
    outcome = C4Stage1TelemetryFinalizer(intent, artifact_store=store).finalize(
        process_execution_record=_record(request),
        result=_result(),
    )
    wrong_storage = store.write_json(
        intent.run_id,
        "diagnostics/wrong-telemetry-samples.json",
        {"wrong": True},
        overwrite=False,
    )

    with pytest.raises(ValueError, match="storage differs"):
        C4Stage1TelemetryFinalizationOutcome(
            samples_artifact=outcome.samples_artifact,
            samples_storage=wrong_storage,
            receipt=outcome.receipt,
            receipt_storage=outcome.receipt_storage,
        )


def test_stage1_intent_is_create_only_and_verified_before_inference(
    tmp_path: Path,
) -> None:
    intent = _intent(tmp_path)
    store = FileArtifactStore(tmp_path / "runs")

    storage = persist_c4_stage1_telemetry_intent(store, intent)

    assert storage.run_id == intent.run_id
    assert storage.relative_path.endswith(".telemetry-intent.json")
    assert store.read_bytes(storage.storage_id) == canonical_json_bytes(intent)
    with pytest.raises(C4Stage1TelemetryPersistenceError, match="failed closed"):
        persist_c4_stage1_telemetry_intent(store, intent)


def test_stage1_policy_freezes_sampling_and_exact_cuda_identity(tmp_path: Path) -> None:
    policy = c4_stage1_telemetry_policy()
    intent = _intent(tmp_path)

    assert intent.telemetry_policy == policy
    assert intent.cadence_seconds == C4_STAGE1_TELEMETRY_CADENCE_SECONDS
    assert intent.max_samples == C4_STAGE1_TELEMETRY_MAX_SAMPLES
    assert (
        intent.max_samples
        == math.ceil(intent.process_request.timeout_seconds / intent.cadence_seconds)
        + 2
    )
    assert intent.join_timeout_seconds == C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS
    assert intent.cuda_vram_limit_bytes == (
        C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES
    )
    assert intent.cuda_device == CUDA_DEVICE_IDENTITY
    assert intent.screen_contract_id == "stage1-screen-contract"
    assert intent.worker_request_id == "stage1-worker-request-primary-enter-circle"
    assert intent.option_id == "enter_circle"
    assert policy.telemetry_policy_id.startswith("c4_stage1_telemetry_policy_")
    assert len(policy.content_hash()) == 64
    with pytest.raises(ValidationError, match="option_id"):
        _intent(tmp_path, option_id="wrong-option")


def test_stage1_initial_wait_and_cleanup_share_setup_callback_budget(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="callback budget"):
        C4Stage1TelemetryLifecycleController(
            _intent(tmp_path),
            cuda_device=_cuda_identity(),
            probe_factory=lambda context, target, cuda: None,
            initial_sample_timeout_seconds=0.6,
        )


@pytest.mark.parametrize(
    ("result", "expected_failure"),
    (
        (
            _result(
                state="failed",
                samples=(),
                failure_code="background_sampler_failure",
            ),
            "insufficient_telemetry_samples",
        ),
        (
            _result(state="finished", samples=(_sample(1),)),
            "final_telemetry_endpoint_missing",
        ),
        (
            _result(
                state="join_timed_out",
                samples=(),
                failure_code="sampler_join_timeout",
                status_sample_count=1,
                latest_sample=_sample(1),
            ),
            "sampler_join_timeout",
        ),
    ),
)
def test_stage1_telemetry_failure_paths_still_persist_terminal_receipt(
    tmp_path: Path,
    result: BackgroundResourceTelemetrySamplerResult,
    expected_failure: str,
) -> None:
    finalizer = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=FileArtifactStore(tmp_path / expected_failure),
    )

    outcome = finalizer.finalize(
        process_execution_record=_record(_request(tmp_path)),
        result=result,
    )

    assert outcome.durable_terminal_receipt is True
    assert outcome.technical_passed is False
    assert outcome.receipt.disposition == "failed"
    assert expected_failure in outcome.receipt.failure_codes
    assert outcome.receipt_storage is not None


class _FailingStore:
    def __init__(self, delegate: FileArtifactStore, *, fail_suffix: str) -> None:
        self._delegate = delegate
        self._fail_suffix = fail_suffix

    def write_json(
        self,
        run_id: str,
        relative_path: str,
        artifact: object,
        *,
        overwrite: bool = False,
    ):
        if relative_path.endswith(self._fail_suffix):
            raise OSError("secret persistence failure")
        return self._delegate.write_json(
            run_id,
            relative_path,
            artifact,
            overwrite=overwrite,
        )


def test_stage1_samples_persistence_failure_writes_durable_failed_receipt(
    tmp_path: Path,
) -> None:
    delegate = FileArtifactStore(tmp_path / "runs")
    store = _FailingStore(
        delegate,
        fail_suffix="telemetry-samples.json",
    )
    finalizer = C4Stage1TelemetryFinalizer(_intent(tmp_path), artifact_store=store)

    outcome = finalizer.finalize(
        process_execution_record=_record(_request(tmp_path)),
        result=_result(),
    )

    assert outcome.samples_artifact is not None
    assert outcome.samples_storage is None
    assert outcome.receipt.samples_persistence_status == "failed"
    assert "telemetry_samples_persistence_failure" in outcome.receipt.failure_codes
    assert outcome.durable_terminal_receipt is True
    assert outcome.technical_passed is False
    cold_outcome = cold_verify_c4_stage1_telemetry_finalization(
        delegate,
        outcome.receipt_storage,
    )
    assert cold_outcome.samples_artifact is None
    assert cold_outcome.receipt == outcome.receipt


def test_stage1_sample_execution_subject_mismatch_gets_terminal_failed_receipt(
    tmp_path: Path,
) -> None:
    bad_snapshot = _snapshot(rss=201, cuda_used=100).model_copy(
        update={
            "process_scope_rss_bytes": _reading(
                201,
                source="windows-job-working-set",
                scope="process_scope_rss",
                subject="wrong-process-tree-subject",
            )
        }
    )
    bad_sample = BackgroundResourceTelemetrySample(
        snapshot=bad_snapshot,
        probe_started_monotonic_ns=10,
        probe_finished_monotonic_ns=12,
    )
    finalizer = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=FileArtifactStore(tmp_path / "runs"),
    )

    outcome = finalizer.finalize(
        process_execution_record=_record(_request(tmp_path)),
        result=_result(samples=(bad_sample, _sample(2))),
    )

    assert outcome.samples_artifact is None
    assert outcome.durable_terminal_receipt is True
    assert outcome.technical_passed is False
    assert "telemetry_samples_persistence_failure" in outcome.receipt.failure_codes


def test_stage1_receipt_persistence_failure_returns_terminal_in_memory_receipt(
    tmp_path: Path,
) -> None:
    store = _FailingStore(
        FileArtifactStore(tmp_path / "runs"),
        fail_suffix="telemetry-finalization.json",
    )
    finalizer = C4Stage1TelemetryFinalizer(_intent(tmp_path), artifact_store=store)

    outcome = finalizer.finalize(
        process_execution_record=_record(_request(tmp_path)),
        result=_result(),
    )

    assert outcome.samples_storage is not None
    assert outcome.receipt_storage is None
    assert outcome.receipt.finalizer_failure_codes == (
        "telemetry_receipt_persistence_failure",
    )
    assert outcome.durable_terminal_receipt is False
    assert outcome.technical_passed is False


def test_stage1_persistence_base_exception_records_outcome_then_reraises(
    tmp_path: Path,
) -> None:
    class InterruptingStore:
        def write_json(self, *args: object, **kwargs: object) -> object:
            raise KeyboardInterrupt("stop persistence")

    finalizer = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=InterruptingStore(),
    )

    with pytest.raises(KeyboardInterrupt, match="stop persistence"):
        finalizer.finalize(
            process_execution_record=_record(_request(tmp_path)),
            result=_result(),
        )

    assert finalizer.outcome.receipt.technical_passed is False
    assert finalizer.outcome.receipt.finalizer_failure_codes == (
        "telemetry_receipt_persistence_failure",
    )
    with pytest.raises(C4Stage1TelemetryStateError, match="only once"):
        finalizer.finalize(
            process_execution_record=_record(_request(tmp_path)),
            result=_result(),
        )


def test_stage1_sampled_cuda_limit_is_a_fail_closed_lower_bound(tmp_path: Path) -> None:
    result = _result(
        samples=(
            _sample(
                1,
                cuda_used=C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES - 1,
            ),
            _sample(
                2,
                cuda_used=C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES + 1,
            ),
        )
    )
    outcome = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=FileArtifactStore(tmp_path / "runs"),
    ).finalize(
        process_execution_record=_record(_request(tmp_path)),
        result=result,
    )

    assert outcome.receipt.sampled_cuda_vram_limit_breached is True
    assert "sampled_cuda_vram_limit_breached" in outcome.receipt.failure_codes
    assert outcome.receipt.sampled_cuda_peak_is_lower_bound is True
    assert outcome.receipt.absence_of_transient_cuda_breach_proven is False
    assert outcome.technical_passed is False


def test_stage1_process_request_execution_mismatch_fails_closed(tmp_path: Path) -> None:
    outcome = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=FileArtifactStore(tmp_path / "runs"),
    ).finalize(
        process_execution_record=_record(
            _request(tmp_path),
            command_identity="different-pinned-command",
        ),
        result=_result(),
    )

    assert outcome.receipt.process_request_binding_verified is False
    assert "process_request_execution_binding_mismatch" in outcome.receipt.failure_codes
    assert outcome.technical_passed is False


def test_stage1_samples_from_different_physical_cuda_device_fail_closed(
    tmp_path: Path,
) -> None:
    wrong_cuda_subject = ResourceTelemetryCudaDeviceIdentity.resolved(
        logical_device_index=1,
        physical_gpu_uuid="GPU-bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        pci_bus_id="00000000:02:00.0",
    ).measurement_subject_id
    bad_snapshot = _snapshot(
        rss=201,
        cuda_used=100,
        cuda_subject=wrong_cuda_subject,
    )
    bad_sample = BackgroundResourceTelemetrySample(
        snapshot=bad_snapshot,
        probe_started_monotonic_ns=10,
        probe_finished_monotonic_ns=12,
    )
    outcome = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=FileArtifactStore(tmp_path / "runs"),
    ).finalize(
        process_execution_record=_record(_request(tmp_path)),
        result=_result(samples=(bad_sample, _sample(2))),
    )

    assert outcome.samples_artifact is None
    assert outcome.durable_terminal_receipt is True
    assert outcome.technical_passed is False
    assert "telemetry_samples_persistence_failure" in outcome.receipt.failure_codes


def test_stage1_receipt_rejects_model_copy_forged_pass(tmp_path: Path) -> None:
    breached_result = _result(
        samples=(
            _sample(1),
            _sample(
                2,
                cuda_used=C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES + 1,
            ),
        )
    )
    outcome = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=FileArtifactStore(tmp_path / "runs"),
    ).finalize(
        process_execution_record=_record(_request(tmp_path)),
        result=breached_result,
    )
    forged = outcome.receipt.model_copy(
        update={
            "technical_passed": True,
            "disposition": "passed",
            "failure_codes": (),
        }
    )

    with pytest.raises(ValidationError, match="inconsistent"):
        C4Stage1TelemetryFinalizationReceipt.model_validate(
            forged.model_dump(mode="python", round_trip=True)
        )


def test_stage1_concurrent_finalization_has_exactly_one_owner(tmp_path: Path) -> None:
    finalizer = C4Stage1TelemetryFinalizer(
        _intent(tmp_path),
        artifact_store=FileArtifactStore(tmp_path / "runs"),
    )
    record = _record(_request(tmp_path))
    result = _result()

    def finalize() -> object:
        try:
            return finalizer.finalize(
                process_execution_record=record,
                result=result,
            )
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(lambda _: finalize(), range(2)))

    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    errors = tuple(item for item in outcomes if isinstance(item, Exception))
    assert len(errors) == 1
    assert isinstance(errors[0], C4Stage1TelemetryStateError)


def test_stage1_default_probe_is_bound_to_exact_context_target(tmp_path: Path) -> None:
    del tmp_path
    context = _context()
    target = ResourceTelemetryProcessTarget(
        root_process_id=context.target.pid,
        root_process_start_token_hash=context.target.start_token_hash,
        process_scope="process_tree",
    )

    probe = build_c4_stage1_bound_system_probe(
        context,
        target,
        _cuda_identity(),
        nvidia_smi_executable=Path(sys.executable).resolve(),
    )

    assert isinstance(probe, SystemResourceTelemetryProbe)
    assert probe._target == target
    assert probe._process_memory_reader is not None


def test_stage1_controller_rejects_cuda_identity_different_from_intent(
    tmp_path: Path,
) -> None:
    other_cuda = ResourceTelemetryCudaDeviceIdentity.resolved(
        logical_device_index=1,
        physical_gpu_uuid="GPU-bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        pci_bus_id="00000000:02:00.0",
    )

    with pytest.raises(ValueError, match="pinned intent"):
        C4Stage1TelemetryLifecycleController(
            _intent(tmp_path),
            cuda_device=other_cuda,
        )


def test_stage1_spawn_failure_has_public_zero_sample_terminal_path(
    tmp_path: Path,
) -> None:
    controller = C4Stage1TelemetryLifecycleController(
        _intent(tmp_path),
        cuda_device=_cuda_identity(),
        probe_factory=lambda context, target, cuda: None,
    )

    result = controller.finish_after_runner()

    assert result == c4_stage1_zero_sample_failure_result()
    assert result.status.state == "failed"
    assert result.status.failure_code == "stage1_process_not_started"
    assert result.status.sample_count == 0
    assert result.samples == ()
    assert controller.finish_after_runner() == result


def test_stage1_lifecycle_controller_waits_initial_and_finishes_naturally(
    tmp_path: Path,
) -> None:
    probe_calls = 0

    class Probe:
        def __init__(
            self,
            target: ResourceTelemetryProcessTarget,
            cuda: ResourceTelemetryCudaDeviceIdentity,
        ) -> None:
            self._target = target
            self._cuda = cuda

        def snapshot(self) -> ResourceTelemetrySnapshot:
            nonlocal probe_calls
            probe_calls += 1
            return _snapshot(
                rss=200 + probe_calls,
                cuda_used=100 + probe_calls,
                process_subject=self._target.measurement_subject_id,
                cuda_subject=self._cuda.measurement_subject_id,
            )

    controller = C4Stage1TelemetryLifecycleController(
        _intent(tmp_path),
        cuda_device=_cuda_identity(),
        probe_factory=lambda context, target, cuda: Probe(target, cuda),
    )
    context = _context()

    controller.on_started(context)
    assert controller.process_target.root_process_id == context.target.pid
    assert probe_calls == 1
    for _ in range(20):
        controller.on_poll(context)
    assert probe_calls == 1

    controller.after_natural_completion(
        context,
        TreeInspectionOutcome(
            method="windows-job-active-processes",
            inspection_succeeded=True,
            target_identity_confirmed=True,
            active_processes=0,
            empty_tree_confirmed=True,
        ),
    )

    result = controller.terminal_result
    assert result.status.state == "finished"
    assert len(result.samples) == 2
    assert result.status.latest_sample == result.samples[-1]
    assert probe_calls == 2
    assert controller.finish_after_runner() == result


def test_stage1_poll_detects_superseded_sticky_cuda_breach(tmp_path: Path) -> None:
    probe_calls = 0

    class Probe:
        def __init__(
            self,
            target: ResourceTelemetryProcessTarget,
            cuda: ResourceTelemetryCudaDeviceIdentity,
        ) -> None:
            self._target = target
            self._cuda = cuda

        def snapshot(self) -> ResourceTelemetrySnapshot:
            nonlocal probe_calls
            probe_calls += 1
            return _snapshot(
                rss=200,
                cuda_used=100,
                process_subject=self._target.measurement_subject_id,
                cuda_subject=self._cuda.measurement_subject_id,
            )

    controller = C4Stage1TelemetryLifecycleController(
        _intent(tmp_path),
        cuda_device=_cuda_identity(),
        probe_factory=lambda context, target, cuda: Probe(target, cuda),
    )
    context = _context()
    controller.on_started(context)
    sampler = controller._sampler
    assert sampler is not None
    completed = sampler.finish()
    latest = completed.status.latest_sample
    assert latest is not None
    sticky_breach = _reading(
        C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES + 1,
        source="nvidia-smi-exact-device",
        scope="cuda_device_memory",
        subject=CUDA_DEVICE_IDENTITY.measurement_subject_id,
    )

    class StickyBreachSampler:
        def poll(self) -> BackgroundResourceTelemetrySamplerStatus:
            return BackgroundResourceTelemetrySamplerStatus(
                state="running",
                sample_count=completed.status.sample_count,
                latest_sample=latest,
                sampled_cuda_vram_peak=sticky_breach,
            )

    controller._sampler = StickyBreachSampler()
    calls_before_poll = probe_calls

    with pytest.raises(C4Stage1TelemetryLifecycleError, match="limit was breached"):
        controller.on_poll(context)

    assert probe_calls == calls_before_poll
    assert controller.sampled_cuda_limit_breached is True


def test_stage1_lifecycle_controller_sample_limit_fails_poll_without_poll_probe(
    tmp_path: Path,
) -> None:
    probe_calls = 0

    class Probe:
        def __init__(
            self,
            target: ResourceTelemetryProcessTarget,
            cuda: ResourceTelemetryCudaDeviceIdentity,
        ) -> None:
            self._target = target
            self._cuda = cuda

        def snapshot(self) -> ResourceTelemetrySnapshot:
            nonlocal probe_calls
            probe_calls += 1
            return _snapshot(
                rss=200,
                cuda_used=100,
                process_subject=self._target.measurement_subject_id,
                cuda_subject=self._cuda.measurement_subject_id,
            )

    controller = C4Stage1TelemetryLifecycleController(
        _intent(tmp_path),
        cuda_device=_cuda_identity(),
        probe_factory=lambda context, target, cuda: Probe(target, cuda),
    )
    context = _context()
    controller.on_started(context)
    sampler = controller._sampler
    assert sampler is not None
    completed = sampler.finish()

    class SampleLimitSampler:
        def poll(self) -> BackgroundResourceTelemetrySamplerStatus:
            return BackgroundResourceTelemetrySamplerStatus(
                state="sample_limit_reached",
                sample_count=completed.status.sample_count,
                latest_sample=completed.status.latest_sample,
                sampled_cuda_vram_peak=completed.status.sampled_cuda_vram_peak,
            )

    controller._sampler = SampleLimitSampler()
    calls_before_terminal_poll = probe_calls
    with pytest.raises(C4Stage1TelemetryLifecycleError, match="non-running"):
        controller.on_poll(context)
    assert probe_calls == calls_before_terminal_poll


def test_stage1_lifecycle_controller_probe_base_exception_fails_before_release(
    tmp_path: Path,
) -> None:
    class Probe:
        def snapshot(self) -> ResourceTelemetrySnapshot:
            raise KeyboardInterrupt("probe interrupted")

    controller = C4Stage1TelemetryLifecycleController(
        _intent(tmp_path),
        cuda_device=_cuda_identity(),
        probe_factory=lambda context, target, cuda: Probe(),
    )

    with pytest.raises(C4Stage1TelemetryLifecycleError, match="setup failed"):
        controller.on_started(_context())

    assert controller.terminal_result.status.state == "failed"
    assert controller.terminal_result.samples == ()


def test_stage1_lifecycle_controller_initial_probe_timeout_is_bounded(
    tmp_path: Path,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    exited = threading.Event()

    class Probe:
        def __init__(
            self,
            target: ResourceTelemetryProcessTarget,
            cuda: ResourceTelemetryCudaDeviceIdentity,
        ) -> None:
            self._target = target
            self._cuda = cuda

        def snapshot(self) -> ResourceTelemetrySnapshot:
            entered.set()
            try:
                release.wait(timeout=1.0)
                return _snapshot(
                    rss=200,
                    cuda_used=100,
                    process_subject=self._target.measurement_subject_id,
                    cuda_subject=self._cuda.measurement_subject_id,
                )
            finally:
                exited.set()

    controller = C4Stage1TelemetryLifecycleController(
        _intent(tmp_path),
        cuda_device=_cuda_identity(),
        probe_factory=lambda context, target, cuda: Probe(target, cuda),
        initial_sample_timeout_seconds=0.01,
    )
    release_timer = threading.Timer(0.05, release.set)
    release_timer.daemon = True
    release_timer.start()

    started = time.perf_counter()
    with pytest.raises(C4Stage1TelemetryLifecycleError, match="setup failed"):
        controller.on_started(_context())
    elapsed = time.perf_counter() - started

    assert entered.is_set()
    assert elapsed < 0.5
    assert controller.terminal_result.status.state == "failed"
    release.set()
    assert exited.wait(timeout=1.0)


def test_stage1_lifecycle_controller_termination_captures_final_endpoint(
    tmp_path: Path,
) -> None:
    class Probe:
        def __init__(
            self,
            target: ResourceTelemetryProcessTarget,
            cuda: ResourceTelemetryCudaDeviceIdentity,
        ) -> None:
            self._target = target
            self._cuda = cuda

        def snapshot(self) -> ResourceTelemetrySnapshot:
            return _snapshot(
                rss=200,
                cuda_used=100,
                process_subject=self._target.measurement_subject_id,
                cuda_subject=self._cuda.measurement_subject_id,
            )

    controller = C4Stage1TelemetryLifecycleController(
        _intent(tmp_path),
        cuda_device=_cuda_identity(),
        probe_factory=lambda context, target, cuda: Probe(target, cuda),
    )
    context = _context()
    controller.on_started(context)
    controller.before_termination(context, "hard_timeout")
    inspection = TreeInspectionOutcome(
        method="windows-job-active-processes",
        inspection_succeeded=True,
        target_identity_confirmed=True,
        active_processes=0,
        empty_tree_confirmed=True,
    )
    controller.after_termination(
        context,
        TreeTerminationOutcome(
            method="windows-job-terminate",
            succeeded=True,
            final_inspection=inspection,
        ),
    )

    assert controller.terminal_result.status.state == "finished"
    assert len(controller.terminal_result.samples) == 2
