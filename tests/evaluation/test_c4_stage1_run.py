from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys
from typing import Literal

import pytest

from rei.emocio.c4_stage1_editor import (
    C4Stage1ChildRuntimeProvenance,
    C4Stage1ImageEvidence,
    C4Stage1WorkerResult,
)
from rei.evaluation import c4_stage1_run as run_module
from rei.evaluation.c4_stage1_attempt import (
    C4Stage1PreparedAttempt,
    C4Stage1PreparedAttemptOutcome,
    C4Stage1RuntimePaths,
)
from rei.evaluation.c4_stage1_run import (
    C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH,
    C4_STAGE1_ATTEMPT_MANIFEST_PATH,
    C4Stage1ConfirmationError,
    C4Stage1LaunchEnvelope,
    C4Stage1MemberPublicationReceipt,
    C4Stage1MemberRun,
    C4Stage1PublishedCandidateReceipt,
    C4Stage1RenderAttemptManifest,
    C4Stage1RenderInventoryAnchor,
    C4Stage1RunIntegrityError,
    C4Stage1WorkerTerminal,
    _C4Stage1RunHooks,
    _run_c4_stage1_attempt,
    cold_verify_c4_stage1_member_publication,
    cold_verify_c4_stage1_run,
)
from rei.evaluation.c4_stage1_telemetry import (
    C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES,
    C4Stage1TelemetryFinalizer,
    C4Stage1TelemetryIntent,
    C4Stage1TelemetrySamplesArtifact,
    _build_finalization_receipt,
    c4_stage1_zero_sample_failure_result,
    cold_verify_c4_stage1_telemetry_finalization,
)
from rei.evaluation.process_tree_runner import (
    BoundedProcessRequest,
    BoundedProcessResult,
    ProcessOutputSummary,
    ProcessTreeExecutionRecord,
)
from rei.evaluation.resource_telemetry import (
    BackgroundResourceTelemetrySample,
    BackgroundResourceTelemetrySamplerResult,
    BackgroundResourceTelemetrySamplerStatus,
    ResourceByteReading,
    ResourceTelemetryProcessTarget,
    ResourceTelemetrySnapshot,
)
from rei.ids import canonical_json_bytes, content_id
from rei.persistence.artifacts import FileArtifactStore
from rei.providers.protocols import StoredArtifact
from tests.evaluation.test_c4_stage1_attempt import _prepared_attempt
from tests.evaluation.test_c4_stage1_staging import _png


ROOT = Path(__file__).resolve().parents[2]
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class _InjectedFatal(BaseException):
    pass


class _FailingPublicationStore(FileArtifactStore):
    fail_relative_path: str | None = None

    def write_bytes(
        self,
        run_id: str,
        relative_path: str,
        payload: bytes,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact:
        if relative_path == self.fail_relative_path:
            raise OSError("injected publication failure")
        return super().write_bytes(
            run_id,
            relative_path,
            payload,
            overwrite=overwrite,
        )


@dataclass(slots=True)
class _Clock:
    now_ns: int = 1_000_000_000

    def __call__(self) -> int:
        return self.now_ns

    def advance(self, seconds: float) -> None:
        self.now_ns += int(seconds * 1_000_000_000)


def _empty_summary() -> ProcessOutputSummary:
    return ProcessOutputSummary(
        byte_count=0,
        captured_byte_count=0,
        sha256=EMPTY_SHA256,
        captured_sha256=EMPTY_SHA256,
        truncated=False,
        stream_complete=True,
    )


def _process_record(
    request: BoundedProcessRequest,
    *,
    index: int,
    succeeded: bool,
) -> ProcessTreeExecutionRecord:
    started = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    start_hash = hashlib.sha256(f"start-{index}".encode()).hexdigest()
    body = {
        "schema_version": "rei-process-tree-execution-v1",
        "runner_revision": "rei-process-tree-runner-v1",
        "workload_id": request.workload_id,
        "command_identity": request.command_identity,
        "argument_count": len(request.command) - 1,
        "working_directory_identity": request.working_directory_identity,
        "environment_identity": request.environment_identity,
        "timeout_seconds": request.timeout_seconds,
        "stdout_limit_bytes": request.stdout_limit_bytes,
        "stderr_limit_bytes": request.stderr_limit_bytes,
        "platform_system": "windows",
        "isolation_mode": "windows_job_object_kill_on_close",
        "target_start_token_hash": start_hash,
        "target_process_group_id": None,
        "target_session_id": None,
        "started_at": started,
        "finished_at": started + timedelta(seconds=1),
        "elapsed_monotonic_seconds": 1.0,
        "workload_elapsed_monotonic_seconds": 0.9,
        "workload_timing_scope": (
            "release_attempt_to_confirmed_empty_tree_upper_bound"
        ),
        "process_id": 10_000 + index,
        "workload_released": True,
        "workload_release_status": "released",
        "exit_code": 0 if succeeded else 7,
        "status": "succeeded" if succeeded else "failed",
        "termination_trigger": "not_required",
        "failure_code": None if succeeded else "process_exit_nonzero",
        "failure_message": (
            None
            if succeeded
            else "Bounded process failed closed (process_exit_nonzero)"
        ),
        "stdout": _empty_summary(),
        "stderr": _empty_summary(),
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
        record_id=content_id("process_execution", body),
        **body,
    )


def _reading(
    value: int,
    *,
    source: str,
    scope: Literal[
        "process_scope_rss",
        "system_physical_memory",
        "cuda_device_memory",
    ],
    subject: str,
) -> ResourceByteReading:
    return ResourceByteReading.measured(
        value,
        source=source,
        measurement_scope=scope,
        subject_id=subject,
    )


def _telemetry_result(
    record: ProcessTreeExecutionRecord,
    *,
    cuda_subject: str,
    breach: bool,
) -> BackgroundResourceTelemetrySamplerResult:
    if record.process_id is None or record.target_start_token_hash is None:
        return c4_stage1_zero_sample_failure_result("stage1_process_not_started")
    process_subject = ResourceTelemetryProcessTarget(
        root_process_id=record.process_id,
        root_process_start_token_hash=record.target_start_token_hash,
        process_scope="process_tree",
    ).measurement_subject_id
    cuda_used = (
        C4_STAGE1_SAMPLED_WHOLE_DEVICE_CUDA_STOP_BYTES + 1 if breach else 1024**3
    )
    snapshots = tuple(
        ResourceTelemetrySnapshot(
            process_scope_rss_bytes=_reading(
                500_000_000 + index,
                source="windows-job-working-set",
                scope="process_scope_rss",
                subject=process_subject,
            ),
            system_ram_total_bytes=_reading(
                64 * 1024**3,
                source="global-memory-status",
                scope="system_physical_memory",
                subject="system-memory",
            ),
            system_ram_available_bytes=_reading(
                32 * 1024**3,
                source="global-memory-status",
                scope="system_physical_memory",
                subject="system-memory",
            ),
            cuda_vram_used_bytes=_reading(
                cuda_used,
                source="nvidia-smi-exact-device",
                scope="cuda_device_memory",
                subject=cuda_subject,
            ),
            cuda_vram_total_bytes=_reading(
                48 * 1024**3,
                source="nvidia-smi-exact-device",
                scope="cuda_device_memory",
                subject=cuda_subject,
            ),
        )
        for index in range(2)
    )
    samples = tuple(
        BackgroundResourceTelemetrySample(
            snapshot=snapshot,
            probe_started_monotonic_ns=index * 10,
            probe_finished_monotonic_ns=index * 10 + 2,
        )
        for index, snapshot in enumerate(snapshots)
    )
    peak = samples[-1].snapshot.cuda_vram_used_bytes
    return BackgroundResourceTelemetrySamplerResult(
        status=BackgroundResourceTelemetrySamplerStatus(
            state="finished",
            sample_count=2,
            latest_sample=samples[-1],
            sampled_cuda_vram_peak=peak,
        ),
        samples=samples,
        sampling_overhead_monotonic_ns=4,
    )


def _success_result(worker, index: int):
    direct = _png(40 + index)
    if worker.editor_role == "primary":
        staged = _png(80 + index)
        normalization = "longcat_rgb_lanczos_1024x768"
        runtime = C4Stage1ChildRuntimeProvenance.create(
            worker.worker_request,
            pipeline_class="LongCatImageEditPipeline",
            placement="model_cpu_offload",
            model_cpu_offload_enabled=True,
            torch_peak_allocated_bytes=100,
            torch_peak_reserved_bytes=120,
        )
    else:
        staged = direct
        normalization = "omnigen_strict_identity_rgb_1024x768"
        runtime = C4Stage1ChildRuntimeProvenance.create(
            worker.worker_request,
            pipeline_class="OmniGenPipeline",
            placement="direct_cuda",
            model_cpu_offload_enabled=False,
            torch_peak_allocated_bytes=100,
            torch_peak_reserved_bytes=120,
        )
    evidence = C4Stage1ImageEvidence.create(
        direct_png=direct,
        staged_png=staged,
        normalization_policy=normalization,
    )
    return (
        C4Stage1WorkerResult.succeeded(worker.worker_request, evidence, runtime),
        direct,
        staged,
    )


def _write_worker_success(root: Path, worker, index: int) -> None:
    result, direct, staged = _success_result(worker, index)
    (root / "direct.png").write_bytes(direct)
    (root / "staged.png").write_bytes(staged)
    (root / "worker_result.json").write_bytes(canonical_json_bytes(result))


def _minimal_cold_envelope(
    artifact_store: FileArtifactStore,
    storage: StoredArtifact,
    prepared: C4Stage1PreparedAttempt,
    **_kwargs,
) -> C4Stage1LaunchEnvelope:
    payload = artifact_store.read_bytes(storage.storage_id)
    envelope = C4Stage1LaunchEnvelope.model_validate_json(payload)
    if (
        canonical_json_bytes(envelope) != payload
        or storage.content_sha256 != hashlib.sha256(payload).hexdigest()
        or storage.size_bytes != len(payload)
        or envelope.prepared_attempt_id != prepared.prepared_attempt_id
        or envelope.prepared_worker_id
        not in {item.prepared_worker_id for item in prepared.workers}
    ):
        raise C4Stage1RunIntegrityError("test launch envelope failed cold binding")
    return envelope


def _minimal_cold_prepared(
    artifact_store: FileArtifactStore,
    storage: StoredArtifact,
    *,
    require_exact_pre_spawn_inventory: bool,
) -> C4Stage1PreparedAttemptOutcome:
    """Cold-bind the deliberately narrow synthetic prepared fixture."""

    payload = artifact_store.read_bytes(storage.storage_id)
    prepared = C4Stage1PreparedAttempt.model_validate_json(payload)
    actual = artifact_store.inspect_run_inventory_exact(prepared.run_id)
    actual_by_path = {item.relative_path: item for item in actual}
    if (
        canonical_json_bytes(prepared) != payload
        or storage.run_id != prepared.run_id
        or storage.relative_path != "diagnostics/c4_stage1_prepared_attempt.json"
        or storage.content_sha256 != hashlib.sha256(payload).hexdigest()
        or storage.size_bytes != len(payload)
        or actual_by_path.get(storage.relative_path) != storage
        or require_exact_pre_spawn_inventory
        and actual
        != tuple(
            sorted(
                (*prepared.artifact_inventory_before_anchor, storage),
                key=lambda item: item.relative_path,
            )
        )
    ):
        raise C4Stage1RunIntegrityError(
            "synthetic Stage 1 prepared fixture failed cold binding"
        )
    return C4Stage1PreparedAttemptOutcome(
        prepared_attempt=prepared,
        prepared_anchor_storage=storage,
    )


@pytest.fixture(autouse=True)
def _bind_synthetic_prepared_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_prepared_attempt",
        _minimal_cold_prepared,
    )


def _prepared_store(
    tmp_path: Path,
    *,
    store_type: type[FileArtifactStore] = FileArtifactStore,
) -> tuple[
    FileArtifactStore,
    C4Stage1PreparedAttemptOutcome,
    C4Stage1RuntimePaths,
]:
    base = _prepared_attempt()
    store = store_type(tmp_path / "runs")
    descriptors = tuple(
        store.write_json(
            base.run_id,
            (
                "diagnostics/"
                f"{worker.worker_request.worker_request_id}.worker-request.json"
            ),
            worker.worker_request,
            overwrite=False,
        )
        for worker in base.workers
    )
    prepared = C4Stage1PreparedAttempt.create(
        run_id=base.run_id,
        repository_gate=base.repository_gate,
        launch_policy=base.launch_policy,
        worker_runtime=base.worker_runtime,
        cuda_device=base.cuda_device,
        source_provenance_sha256=base.source_provenance_sha256,
        telemetry_policy=base.telemetry_policy,
        review_schema=base.review_schema,
        review_operator_policies=base.review_operator_policies,
        display_policy=base.display_policy,
        screen_contract=base.screen_contract,
        workers=base.workers,
        artifact_inventory_before_anchor=tuple(
            sorted(descriptors, key=lambda item: item.relative_path)
        ),
    )
    anchor = store.write_json(
        prepared.run_id,
        "diagnostics/c4_stage1_prepared_attempt.json",
        prepared,
        overwrite=False,
    )
    runtime = (tmp_path / "runtime").resolve()
    staging = (runtime / "staging").resolve()
    primary = (runtime / "primary").resolve()
    alternate = (runtime / "alternate").resolve()
    for directory in (runtime, staging, primary, alternate):
        directory.mkdir(exist_ok=True)
    source = (runtime / "source.png").resolve()
    provenance = (runtime / "source.json").resolve()
    source.write_bytes(_png(1))
    provenance.write_bytes(b"{}")
    paths = C4Stage1RuntimePaths(
        repository_root=ROOT.resolve(),
        worker_python=Path(sys.executable).resolve(),
        source_png=source,
        source_provenance=provenance,
        primary_snapshot=primary,
        alternate_snapshot=alternate,
        staging_parent=staging,
    )
    return (
        store,
        C4Stage1PreparedAttemptOutcome(
            prepared_attempt=prepared,
            prepared_anchor_storage=anchor,
        ),
        paths,
    )


WorkerKey = tuple[
    Literal["primary", "alternate"], Literal["enter_circle", "remain_edge"]
]
WorkerMode = Literal[
    "success",
    "failed",
    "cuda_breach",
    "base_exception",
    "inject",
    "missing_terminal",
    "invalid_terminal",
]


@dataclass(slots=True)
class _FakeController:
    harness: _Harness
    key: WorkerKey
    record: ProcessTreeExecutionRecord | None = None

    def finish_after_runner(self) -> BackgroundResourceTelemetrySamplerResult:
        self.harness.events.append((self.key, "finish"))
        if self.record is None:
            return c4_stage1_zero_sample_failure_result("stage1_process_not_started")
        return _telemetry_result(
            self.record,
            cuda_subject=self.harness.prepared.cuda_device.measurement_subject_id,
            breach=self.harness.modes.get(self.key) == "cuda_breach",
        )


@dataclass(slots=True)
class _FinalizerProxy:
    harness: _Harness
    key: WorkerKey
    inner: C4Stage1TelemetryFinalizer

    @property
    def outcome(self):
        return self.inner.outcome

    def finalize(self, **kwargs):
        self.harness.events.append((self.key, "finalize"))
        return self.inner.finalize(**kwargs)


@dataclass(slots=True)
class _FakeRunner:
    harness: _Harness
    controller: _FakeController
    worker: object
    staging_root: Path
    _last: BoundedProcessResult | None = None

    @property
    def last_terminal_result(self) -> BoundedProcessResult:
        if self._last is None:
            raise RuntimeError("runner has no terminal result")
        return self._last

    def run(self, request: BoundedProcessRequest) -> BoundedProcessResult:
        key: WorkerKey = (self.worker.editor_role, self.worker.option_id)
        mode = self.harness.modes.get(key, "success")
        self.harness.events.append((key, "runner"))
        self.harness.commands.append(request.command)
        inventory = self.harness.store.inspect_run_inventory_exact(
            self.harness.prepared.run_id
        )
        self.harness.visible_direct_counts.append(
            sum(item.relative_path.endswith(".direct.png") for item in inventory)
        )
        succeeded = mode != "failed"
        record = _process_record(
            request,
            index=len(self.harness.commands),
            succeeded=succeeded,
        )
        self.controller.record = record
        if succeeded:
            _write_worker_success(
                self.staging_root,
                self.worker,
                len(self.harness.commands),
            )
        else:
            failed = C4Stage1WorkerResult.failed(
                self.worker.worker_request,
                failure_code="injected_worker_failure",
            )
            (self.staging_root / "worker_result.json").write_bytes(
                canonical_json_bytes(failed)
            )
        self._last = BoundedProcessResult(record=record, stdout=b"", stderr=b"")
        self.harness.clock.advance(self.harness.advances.get(key, 0.0))
        if mode == "inject":
            self.harness.store.write_bytes(
                self.harness.prepared.run_id,
                "diagnostics/injected-unknown.bin",
                b"unknown",
                overwrite=False,
            )
        if mode == "missing_terminal":
            self._last = None
            raise RuntimeError("injected runner lost its terminal result")
        if mode == "invalid_terminal":
            return object()  # type: ignore[return-value]
        if mode == "base_exception":
            raise _InjectedFatal("injected terminal BaseException")
        return self._last


@dataclass(slots=True)
class _Harness:
    store: FileArtifactStore
    prepared_outcome: C4Stage1PreparedAttemptOutcome
    modes: dict[WorkerKey, WorkerMode] = field(default_factory=dict)
    advances: dict[WorkerKey, float] = field(default_factory=dict)
    clock: _Clock = field(default_factory=_Clock)
    events: list[tuple[WorkerKey, str]] = field(default_factory=list)
    commands: list[tuple[str, ...]] = field(default_factory=list)
    visible_direct_counts: list[int] = field(default_factory=list)
    gate_capture_count: int = 0
    runtime_verification_count: int = 0

    @property
    def prepared(self) -> C4Stage1PreparedAttempt:
        return self.prepared_outcome.prepared_attempt

    def key_for_request(self, request_id: str) -> WorkerKey:
        for worker in self.prepared.workers:
            if worker.worker_request.worker_request_id == request_id:
                return (worker.editor_role, worker.option_id)
        raise AssertionError(request_id)

    def cold_prepared(self, *_args, **_kwargs) -> C4Stage1PreparedAttemptOutcome:
        return self.prepared_outcome

    def capture_gate(self, _root: Path):
        self.gate_capture_count += 1
        return self.prepared.repository_gate

    def verify_runtime(self, *_args, **_kwargs) -> None:
        self.runtime_verification_count += 1

    def controller_factory(self, intent, _cuda):
        return _FakeController(self, self.key_for_request(intent.worker_request_id))

    def runner_factory(self, controller, worker, staging_root):
        return _FakeRunner(self, controller, worker, staging_root)

    def finalizer_factory(self, intent, store):
        key = self.key_for_request(intent.worker_request_id)
        return _FinalizerProxy(
            self,
            key,
            C4Stage1TelemetryFinalizer(intent, artifact_store=store),
        )

    def cold_telemetry(self, store, storage):
        outcome = cold_verify_c4_stage1_telemetry_finalization(store, storage)
        key = self.key_for_request(outcome.receipt.intent.worker_request_id)
        self.events.append((key, "cold"))
        return outcome

    def hooks(self) -> _C4Stage1RunHooks:
        return _C4Stage1RunHooks(
            cold_prepared=self.cold_prepared,
            capture_repository_gate=self.capture_gate,
            verify_runtime_bindings=self.verify_runtime,
            controller_factory=self.controller_factory,
            runner_factory=self.runner_factory,
            finalizer_factory=self.finalizer_factory,
            cold_telemetry=self.cold_telemetry,
            monotonic_ns=self.clock,
        )


def _run(
    harness: _Harness,
    paths: C4Stage1RuntimePaths,
    *,
    confirmation: str | None = None,
):
    prepared = harness.prepared
    return _run_c4_stage1_attempt(
        artifact_store=harness.store,
        prepared_anchor_storage=harness.prepared_outcome.prepared_anchor_storage,
        confirmed_prepared_attempt_id=(
            prepared.prepared_attempt_id if confirmation is None else confirmation
        ),
        paths=paths,
        hooks=harness.hooks(),
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _readdress_worker_terminal(
    terminal: C4Stage1WorkerTerminal,
    **updates: object,
) -> C4Stage1WorkerTerminal:
    body = terminal.model_dump(
        mode="python",
        round_trip=True,
        exclude={"worker_terminal_id", "worker_terminal_sha256"},
    )
    body.update(updates)
    return C4Stage1WorkerTerminal(
        worker_terminal_id=content_id("c4_stage1_worker_terminal", body),
        worker_terminal_sha256=_canonical_sha256(body),
        **body,
    )


def _readdress_telemetry_intent(
    intent: C4Stage1TelemetryIntent,
    **updates: object,
) -> C4Stage1TelemetryIntent:
    body = intent.model_dump(
        mode="python",
        round_trip=True,
        exclude={"intent_id", "intent_sha256"},
    )
    body.update(updates)
    return C4Stage1TelemetryIntent(
        intent_id=content_id("c4_stage1_telemetry_intent", body),
        intent_sha256=_canonical_sha256(body),
        **body,
    )


def _readdress_runtime_provenance(
    provenance: C4Stage1ChildRuntimeProvenance,
    **updates: object,
) -> C4Stage1ChildRuntimeProvenance:
    body = provenance.model_dump(
        mode="python",
        round_trip=True,
        exclude={"runtime_provenance_id"},
    )
    body.update(updates)
    return C4Stage1ChildRuntimeProvenance(
        runtime_provenance_id=content_id("c4_stage1_child_runtime", body),
        **body,
    )


def _readdress_worker_result(
    result: C4Stage1WorkerResult,
    **updates: object,
) -> C4Stage1WorkerResult:
    body = result.model_dump(
        mode="python",
        round_trip=True,
        exclude={"worker_result_id"},
    )
    body.update(updates)
    return C4Stage1WorkerResult(
        worker_result_id=content_id("c4_stage1_worker_result", body),
        **body,
    )


def _readdress_candidate_receipt(
    candidate: C4Stage1PublishedCandidateReceipt,
    **updates: object,
) -> C4Stage1PublishedCandidateReceipt:
    body = candidate.model_dump(
        mode="python",
        round_trip=True,
        exclude={"candidate_receipt_id", "candidate_receipt_sha256"},
    )
    body.update(updates)
    return C4Stage1PublishedCandidateReceipt(
        candidate_receipt_id=content_id("c4_stage1_candidate_receipt", body),
        candidate_receipt_sha256=_canonical_sha256(body),
        **body,
    )


def _readdress_member_publication_receipt(
    receipt: C4Stage1MemberPublicationReceipt,
    **updates: object,
) -> C4Stage1MemberPublicationReceipt:
    body = receipt.model_dump(
        mode="python",
        round_trip=True,
        exclude={
            "member_publication_receipt_id",
            "member_publication_receipt_sha256",
        },
    )
    body.update(updates)
    return C4Stage1MemberPublicationReceipt(
        member_publication_receipt_id=content_id(
            "c4_stage1_member_publish",
            body,
        ),
        member_publication_receipt_sha256=_canonical_sha256(body),
        **body,
    )


def _readdress_member_run(
    member: C4Stage1MemberRun,
    **updates: object,
) -> C4Stage1MemberRun:
    body = member.model_dump(
        mode="python",
        round_trip=True,
        exclude={"member_run_id", "member_run_sha256"},
    )
    body.update(updates)
    return C4Stage1MemberRun(
        member_run_id=content_id("c4_stage1_member_run", body),
        member_run_sha256=_canonical_sha256(body),
        **body,
    )


def _readdress_manifest(
    manifest: C4Stage1RenderAttemptManifest,
    **updates: object,
) -> C4Stage1RenderAttemptManifest:
    body = manifest.model_dump(
        mode="python",
        round_trip=True,
        exclude={
            "render_attempt_manifest_id",
            "render_attempt_manifest_sha256",
        },
    )
    body.update(updates)
    return C4Stage1RenderAttemptManifest(
        render_attempt_manifest_id=content_id(
            "c4_stage1_render_manifest",
            body,
        ),
        render_attempt_manifest_sha256=_canonical_sha256(body),
        **body,
    )


def _readdress_anchor(
    anchor: C4Stage1RenderInventoryAnchor,
    **updates: object,
) -> C4Stage1RenderInventoryAnchor:
    body = anchor.model_dump(
        mode="python",
        round_trip=True,
        exclude={
            "render_inventory_anchor_id",
            "render_inventory_anchor_sha256",
        },
    )
    body.update(updates)
    return C4Stage1RenderInventoryAnchor(
        render_inventory_anchor_id=content_id(
            "c4_stage1_render_inventory",
            body,
        ),
        render_inventory_anchor_sha256=_canonical_sha256(body),
        **body,
    )


def _replace_terminal(
    manifest: C4Stage1RenderAttemptManifest,
    *,
    member_index: int,
    terminal_index: int,
    updates: dict[str, object],
) -> C4Stage1RenderAttemptManifest:
    members = list(manifest.member_runs)
    member = members[member_index]
    terminals = list(member.worker_terminals)
    terminals[terminal_index] = _readdress_worker_terminal(
        terminals[terminal_index],
        **updates,
    )
    members[member_index] = _readdress_member_run(
        member,
        worker_terminals=tuple(terminals),
    )
    return _readdress_manifest(manifest, member_runs=tuple(members))


def _clone_with_forged_final_artifacts(
    target: Path,
    source_store: FileArtifactStore,
    manifest: C4Stage1RenderAttemptManifest,
    *,
    anchor_updates: dict[str, object] | None = None,
) -> tuple[FileArtifactStore, StoredArtifact]:
    clone = FileArtifactStore(target)
    for descriptor in source_store.inspect_run_inventory_exact(manifest.run_id):
        if descriptor.relative_path in {
            C4_STAGE1_ATTEMPT_MANIFEST_PATH,
            C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH,
        }:
            continue
        copied = clone.write_bytes(
            descriptor.run_id,
            descriptor.relative_path,
            source_store.read_bytes(descriptor.storage_id),
            overwrite=False,
        )
        assert copied == descriptor
    manifest_storage = clone.write_json(
        manifest.run_id,
        C4_STAGE1_ATTEMPT_MANIFEST_PATH,
        manifest,
        overwrite=False,
    )
    anchor = C4Stage1RenderInventoryAnchor.create(
        manifest,
        manifest_storage,
        artifact_inventory_before_anchor=clone.inspect_run_inventory_exact(
            manifest.run_id
        ),
    )
    if anchor_updates:
        anchor = _readdress_anchor(anchor, **anchor_updates)
    anchor_storage = clone.write_json(
        manifest.run_id,
        C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH,
        anchor,
        overwrite=False,
    )
    return clone, anchor_storage


def test_success_commits_two_atomic_members_and_cold_verifies_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    model_modules_before = {
        name for name in sys.modules if name in {"torch", "diffusers"}
    }

    outcome = _run(harness, paths)

    assert outcome.manifest.status == "evidence_ready"
    assert outcome.manifest.render_technical_completed is True
    assert outcome.manifest.semantic_stage1_passed is False
    assert outcome.manifest.dino_gate_status == "pending"
    assert outcome.manifest.human_review_status == "pending"
    assert outcome.manifest.semantic_authority_granted is False
    assert outcome.manifest.production_authority_granted is False
    assert harness.visible_direct_counts == [0, 0, 2, 2]
    assert harness.gate_capture_count == 8
    assert harness.runtime_verification_count == 8
    assert len(harness.commands) == 4
    for command in harness.commands:
        assert command[1:3] == ("-I", "-S")
        assert Path(command[3]).name == "run_rei_c4_stage1_bootstrap.py"
        assert command[4::2] == (
            "--launch-envelope",
            "--prepared-anchor-storage-id",
            "--request",
            "--source-png",
            "--snapshot",
            "--staging-root",
        )
    for worker in prepared_outcome.prepared_attempt.workers:
        key = (worker.editor_role, worker.option_id)
        assert [event for event_key, event in harness.events if event_key == key] == [
            "runner",
            "finish",
            "finalize",
            "cold",
        ]
    for member in outcome.manifest.member_runs:
        assert member.status == "succeeded"
        receipt_storages = {
            terminal.member_publication_receipt_storage
            for terminal in member.worker_terminals
        }
        assert len(receipt_storages) == 1
        receipt_storage = receipt_storages.pop()
        assert receipt_storage is not None
        receipt = cold_verify_c4_stage1_member_publication(
            FileArtifactStore(store.root, create=False),
            receipt_storage,
            prepared_outcome.prepared_attempt,
        )
        assert receipt.publication_committed is True
        assert tuple(item.option_id for item in receipt.candidate_receipts) == (
            "enter_circle",
            "remain_edge",
        )
    assert {name for name in sys.modules if name in {"torch", "diffusers"}} == (
        model_modules_before
    )

    staged = outcome.manifest.member_runs[0].worker_terminals[0].staged_output_storage
    receipt_storage = (
        outcome.manifest.member_runs[0]
        .worker_terminals[0]
        .member_publication_receipt_storage
    )
    assert staged is not None and receipt_storage is not None
    store.artifact_path(staged.run_id, staged.relative_path).write_bytes(b"tampered")
    with pytest.raises(C4Stage1RunIntegrityError):
        cold_verify_c4_stage1_member_publication(
            FileArtifactStore(store.root, create=False),
            receipt_storage,
            prepared_outcome.prepared_attempt,
        )


def test_exact_confirmation_is_required_before_any_run_mutation(
    tmp_path: Path,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(store, prepared_outcome)
    before = store.inspect_run_inventory_exact(prepared_outcome.prepared_attempt.run_id)

    with pytest.raises(C4Stage1ConfirmationError):
        _run(harness, paths, confirmation="wrong-prepared-attempt")

    assert harness.commands == []
    assert (
        store.inspect_run_inventory_exact(prepared_outcome.prepared_attempt.run_id)
        == before
    )


def test_family_failure_stops_its_second_option_but_allows_alternate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(
        store,
        prepared_outcome,
        modes={("primary", "enter_circle"): "failed"},
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    outcome = _run(harness, paths)

    assert [member.status for member in outcome.manifest.member_runs] == [
        "failed",
        "succeeded",
    ]
    assert outcome.manifest.global_stop_triggered is False
    assert [
        (worker.editor_role, worker.option_id)
        for worker in prepared_outcome.prepared_attempt.workers
        if any(
            key == (worker.editor_role, worker.option_id) and event == "runner"
            for key, event in harness.events
        )
    ] == [
        ("primary", "enter_circle"),
        ("alternate", "enter_circle"),
        ("alternate", "remain_edge"),
    ]
    assert outcome.manifest.member_runs[0].publication_completed is False
    assert outcome.manifest.member_runs[1].publication_completed is True


def test_cuda_breach_is_global_and_prevents_all_later_spawns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(
        store,
        prepared_outcome,
        modes={("primary", "enter_circle"): "cuda_breach"},
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    outcome = _run(harness, paths)

    assert len(harness.commands) == 1
    assert outcome.manifest.global_stop_triggered is True
    assert outcome.manifest.member_runs[0].status == "failed"
    assert outcome.manifest.member_runs[1].status == "not_started"
    assert outcome.manifest.member_runs[0].publication_completed is False


def test_member_budget_never_starts_second_option_without_180_seconds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(
        store,
        prepared_outcome,
        advances={("primary", "enter_circle"): 241.0},
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    outcome = _run(harness, paths)

    runner_keys = [key for key, event in harness.events if event == "runner"]
    assert runner_keys == [
        ("primary", "enter_circle"),
        ("alternate", "enter_circle"),
        ("alternate", "remain_edge"),
    ]
    assert outcome.manifest.member_runs[0].status == "failed"
    assert "insufficient_member_time_for_second_option" in (
        outcome.manifest.member_runs[0].failure_codes
    )
    assert outcome.manifest.member_runs[1].status == "succeeded"


def test_unknown_inventory_injection_fails_before_next_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(
        store,
        prepared_outcome,
        modes={("primary", "enter_circle"): "inject"},
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    with pytest.raises(C4Stage1RunIntegrityError):
        _run(harness, paths)

    assert len(harness.commands) == 1
    paths_seen = {
        item.relative_path
        for item in store.inspect_run_inventory_exact(
            prepared_outcome.prepared_attempt.run_id
        )
    }
    assert "diagnostics/injected-unknown.bin" in paths_seen
    assert C4_STAGE1_ATTEMPT_MANIFEST_PATH not in paths_seen


def test_base_exception_after_runner_terminal_persists_final_failure_then_rethrows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(
        store,
        prepared_outcome,
        modes={("primary", "enter_circle"): "base_exception"},
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    with pytest.raises(_InjectedFatal):
        _run(harness, paths)

    inventory = store.inspect_run_inventory_exact(
        prepared_outcome.prepared_attempt.run_id
    )
    anchor = next(
        item
        for item in inventory
        if item.relative_path == C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH
    )
    cold = cold_verify_c4_stage1_run(
        FileArtifactStore(store.root, create=False),
        anchor,
    )
    assert cold.manifest.status == "failed"
    assert cold.manifest.global_stop_triggered is True
    assert len(harness.commands) == 1


def test_partial_output_writes_never_create_member_commit_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(
        tmp_path,
        store_type=_FailingPublicationStore,
    )
    second = prepared_outcome.prepared_attempt.workers[1]
    assert isinstance(store, _FailingPublicationStore)
    store.fail_relative_path = (
        f"emocio/images/{second.worker_request.worker_request_id}.png"
    )
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    outcome = _run(harness, paths)

    assert outcome.manifest.global_stop_triggered is True
    assert outcome.manifest.member_runs[0].publication_completed is False
    assert outcome.manifest.member_runs[1].status == "not_started"
    inventory_paths = {
        item.relative_path
        for item in store.inspect_run_inventory_exact(
            prepared_outcome.prepared_attempt.run_id
        )
    }
    assert not any(
        path.endswith(".member-publication.json") for path in inventory_paths
    )
    assert any(path.endswith(".direct.png") for path in inventory_paths)


def test_envelope_persistence_failure_after_intent_gets_full_terminal_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(
        tmp_path,
        store_type=_FailingPublicationStore,
    )
    first = prepared_outcome.prepared_attempt.workers[0]
    assert isinstance(store, _FailingPublicationStore)
    store.fail_relative_path = (
        f"diagnostics/{first.prepared_worker_id}.launch-envelope.json"
    )
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    outcome = _run(harness, paths)

    assert harness.commands == []
    assert outcome.manifest.global_stop_triggered is True
    assert outcome.manifest.member_runs[1].status == "not_started"
    terminal = outcome.manifest.member_runs[0].worker_terminals[0]
    assert terminal.launch_envelope_storage is None
    assert terminal.telemetry_intent_storage is not None
    assert terminal.process_execution_storage is not None
    assert terminal.telemetry_finalization_storage is not None
    assert terminal.worker_result_storage is not None
    assert terminal.process_status == "failed"
    assert terminal.worker_status == "failed"
    assert terminal.failure_scope == "global"
    assert "launch_envelope_persistence_failed" in terminal.failure_codes
    assert [event for _, event in harness.events] == [
        "finish",
        "finalize",
        "cold",
    ]


@pytest.mark.parametrize("envelope_failure", [False, True])
def test_transient_ledger_failure_after_terminal_writes_is_finalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    envelope_failure: bool,
) -> None:
    store_type = _FailingPublicationStore if envelope_failure else FileArtifactStore
    store, prepared_outcome, paths = _prepared_store(
        tmp_path,
        store_type=store_type,
    )
    first = prepared_outcome.prepared_attempt.workers[0]
    if envelope_failure:
        assert isinstance(store, _FailingPublicationStore)
        store.fail_relative_path = (
            f"diagnostics/{first.prepared_worker_id}.launch-envelope.json"
        )
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    original_verify = run_module._InventoryLedger.verify_exact
    injected = False

    def _fail_once_after_terminal_writes(ledger, artifact_store):
        nonlocal injected
        paths_seen = set(ledger._by_path)
        if (
            not injected
            and any(path.endswith(".process-execution.json") for path in paths_seen)
            and any(path.endswith(".worker-result.json") for path in paths_seen)
        ):
            injected = True
            raise C4Stage1RunIntegrityError(
                "injected transient post-intent ledger failure"
            )
        return original_verify(ledger, artifact_store)

    monkeypatch.setattr(
        run_module._InventoryLedger,
        "verify_exact",
        _fail_once_after_terminal_writes,
    )

    outcome = _run(harness, paths)

    assert injected is True
    assert outcome.manifest.status == "failed"
    assert outcome.manifest.global_stop_triggered is True
    terminal = outcome.manifest.member_runs[0].worker_terminals[0]
    assert "post_intent_inventory_verification_failed" in terminal.failure_codes
    cold = cold_verify_c4_stage1_run(
        FileArtifactStore(store.root, create=False),
        outcome.inventory_anchor_storage,
    )
    assert cold.manifest == outcome.manifest


@pytest.mark.parametrize("mode", ["missing_terminal", "invalid_terminal"])
def test_untrusted_runner_terminal_still_gets_conservative_durable_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: WorkerMode,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(
        store,
        prepared_outcome,
        modes={("primary", "enter_circle"): mode},
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )

    outcome = _run(harness, paths)

    assert len(harness.commands) == 1
    terminal = outcome.manifest.member_runs[0].worker_terminals[0]
    assert terminal.launch_envelope_storage is not None
    assert terminal.process_execution_storage is not None
    assert terminal.telemetry_finalization_storage is not None
    assert terminal.worker_result_storage is not None
    assert terminal.process_status == "failed"
    assert terminal.failure_scope == "global"
    expected = (
        "runner_terminal_unavailable"
        if mode == "missing_terminal"
        else "runner_terminal_invalid"
    )
    assert expected in terminal.failure_codes
    assert outcome.manifest.member_runs[1].status == "not_started"
    assert [event for _, event in harness.events] == [
        "runner",
        "finish",
        "finalize",
        "cold",
    ]


def test_cold_run_rejects_readdressed_success_lineage_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path / "source")
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    outcome = _run(harness, paths)
    manifest = outcome.manifest

    with pytest.raises(ValueError, match="manifest disposition"):
        _readdress_manifest(
            manifest,
            global_stop_triggered=True,
            failure_codes=("global_stop_triggered",),
        )

    first = manifest.member_runs[0].worker_terminals[0]
    second = manifest.member_runs[0].worker_terminals[1]
    worker_request_storage = next(
        item
        for item in manifest.artifact_inventory_before_manifest
        if item.relative_path.endswith(".worker-request.json")
    )
    forged_manifests = (
        _readdress_manifest(manifest, attempt_id="forged-attempt"),
        _readdress_manifest(
            manifest,
            prepared_anchor_storage=worker_request_storage,
        ),
        _replace_terminal(
            manifest,
            member_index=0,
            terminal_index=0,
            updates={
                "process_execution_record_id": (second.process_execution_record_id),
                "process_execution_record_sha256": (
                    second.process_execution_record_sha256
                ),
                "process_execution_storage": second.process_execution_storage,
                "process_status": second.process_status,
            },
        ),
        _replace_terminal(
            manifest,
            member_index=0,
            terminal_index=0,
            updates={
                "worker_result_id": second.worker_result_id,
                "worker_result_sha256": second.worker_result_sha256,
                "worker_result_storage": second.worker_result_storage,
                "worker_status": second.worker_status,
            },
        ),
        _replace_terminal(
            manifest,
            member_index=0,
            terminal_index=0,
            updates={
                "telemetry_finalization_receipt_id": (
                    second.telemetry_finalization_receipt_id
                ),
                "telemetry_finalization_receipt_sha256": (
                    second.telemetry_finalization_receipt_sha256
                ),
                "telemetry_finalization_storage": (
                    second.telemetry_finalization_storage
                ),
            },
        ),
        _replace_terminal(
            manifest,
            member_index=0,
            terminal_index=0,
            updates={"telemetry_intent_id": "forged-intent"},
        ),
    )
    for index, forged_manifest in enumerate(forged_manifests):
        clone, anchor_storage = _clone_with_forged_final_artifacts(
            tmp_path / f"forged-success-{index}",
            store,
            forged_manifest,
        )
        with pytest.raises(C4Stage1RunIntegrityError):
            cold_verify_c4_stage1_run(clone, anchor_storage)

    clone, anchor_storage = _clone_with_forged_final_artifacts(
        tmp_path / "forged-anchor",
        store,
        manifest,
        anchor_updates={"prepared_attempt_id": "forged-prepared-attempt"},
    )
    with pytest.raises(C4Stage1RunIntegrityError):
        cold_verify_c4_stage1_run(clone, anchor_storage)

    assert first.process_execution_storage != second.process_execution_storage
    assert first.worker_result_storage != second.worker_result_storage
    assert first.telemetry_finalization_storage != (
        second.telemetry_finalization_storage
    )


def test_member_marker_rejects_readdressed_telemetry_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path)
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    outcome = _run(harness, paths)
    marker_storage = (
        outcome.manifest.member_runs[0]
        .worker_terminals[0]
        .member_publication_receipt_storage
    )
    assert marker_storage is not None
    marker = cold_verify_c4_stage1_member_publication(
        store,
        marker_storage,
        prepared_outcome.prepared_attempt,
    )
    candidate = marker.candidate_receipts[0]
    telemetry = cold_verify_c4_stage1_telemetry_finalization(
        store,
        candidate.telemetry_finalization_storage,
    )
    second_worker = prepared_outcome.prepared_attempt.workers[1]
    forged_intent = _readdress_telemetry_intent(
        telemetry.receipt.intent,
        worker_request_id=second_worker.worker_request.worker_request_id,
        worker_request_sha256=second_worker.worker_request.content_hash(),
        option_id=second_worker.option_id,
    )
    sampler_result = _telemetry_result(
        telemetry.receipt.process_execution_record,
        cuda_subject=(
            prepared_outcome.prepared_attempt.cuda_device.measurement_subject_id
        ),
        breach=False,
    )
    forged_samples = C4Stage1TelemetrySamplesArtifact.from_result(
        intent=forged_intent,
        process_execution_record=telemetry.receipt.process_execution_record,
        result=sampler_result,
    )
    forged_samples_storage = store.write_json(
        forged_intent.run_id,
        f"diagnostics/{forged_intent.intent_id}.telemetry-samples.json",
        forged_samples,
        overwrite=False,
    )
    forged_receipt = _build_finalization_receipt(
        intent=forged_intent,
        process_execution_record=telemetry.receipt.process_execution_record,
        result=sampler_result,
        samples_artifact=forged_samples,
        samples_storage=forged_samples_storage,
        samples_persistence_status="persisted",
    )
    forged_receipt_storage = store.write_json(
        forged_intent.run_id,
        f"diagnostics/{forged_intent.intent_id}.telemetry-finalization.json",
        forged_receipt,
        overwrite=False,
    )
    forged_candidate = _readdress_candidate_receipt(
        candidate,
        telemetry_finalization_receipt_id=(forged_receipt.finalization_receipt_id),
        telemetry_finalization_receipt_sha256=(
            forged_receipt.finalization_receipt_sha256
        ),
        telemetry_finalization_storage=forged_receipt_storage,
    )
    forged_marker = _readdress_member_publication_receipt(
        marker,
        candidate_receipts=(forged_candidate, marker.candidate_receipts[1]),
        artifact_inventory_before_receipt=store.inspect_run_inventory_exact(
            marker.run_id
        ),
    )
    forged_marker_storage = store.write_json(
        marker.run_id,
        (
            "diagnostics/"
            f"{forged_marker.member_publication_receipt_id}."
            "member-publication.json"
        ),
        forged_marker,
        overwrite=False,
    )

    with pytest.raises(C4Stage1RunIntegrityError):
        cold_verify_c4_stage1_member_publication(
            store,
            forged_marker_storage,
            prepared_outcome.prepared_attempt,
        )

    original_result = C4Stage1WorkerResult.model_validate_json(
        store.read_bytes(candidate.worker_result_storage.storage_id)
    )
    assert original_result.runtime_provenance is not None
    forged_provenance = _readdress_runtime_provenance(
        original_result.runtime_provenance,
        effective_seed=original_result.runtime_provenance.effective_seed + 1,
    )
    forged_result = _readdress_worker_result(
        original_result,
        runtime_provenance=forged_provenance,
    )
    forged_result_storage = store.write_json(
        marker.run_id,
        f"diagnostics/{forged_result.worker_result_id}.worker-result.json",
        forged_result,
        overwrite=False,
    )
    forged_result_candidate = _readdress_candidate_receipt(
        candidate,
        worker_result_id=forged_result.worker_result_id,
        worker_result_sha256=_canonical_sha256(forged_result),
        worker_result_storage=forged_result_storage,
    )
    forged_result_marker = _readdress_member_publication_receipt(
        marker,
        candidate_receipts=(
            forged_result_candidate,
            marker.candidate_receipts[1],
        ),
        artifact_inventory_before_receipt=store.inspect_run_inventory_exact(
            marker.run_id
        ),
    )
    forged_result_marker_storage = store.write_json(
        marker.run_id,
        (
            "diagnostics/"
            f"{forged_result_marker.member_publication_receipt_id}."
            "member-publication.json"
        ),
        forged_result_marker,
        overwrite=False,
    )

    with pytest.raises(C4Stage1RunIntegrityError):
        cold_verify_c4_stage1_member_publication(
            store,
            forged_result_marker_storage,
            prepared_outcome.prepared_attempt,
        )


def test_cold_run_rejects_readdressed_envelope_none_failure_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(
        tmp_path / "source",
        store_type=_FailingPublicationStore,
    )
    first_worker, second_worker = prepared_outcome.prepared_attempt.workers[:2]
    assert isinstance(store, _FailingPublicationStore)
    store.fail_relative_path = (
        f"diagnostics/{first_worker.prepared_worker_id}.launch-envelope.json"
    )
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    outcome = _run(harness, paths)
    terminal = outcome.manifest.member_runs[0].worker_terminals[0]
    assert terminal.launch_envelope_storage is None
    assert "process_record_persistence_failed" not in terminal.failure_codes
    assert "worker_result_persistence_failed" not in terminal.failure_codes

    forged_manifests = (
        _replace_terminal(
            outcome.manifest,
            member_index=0,
            terminal_index=0,
            updates={
                "prepared_worker_id": second_worker.prepared_worker_id,
                "worker_request_id": (second_worker.worker_request.worker_request_id),
            },
        ),
        _replace_terminal(
            outcome.manifest,
            member_index=0,
            terminal_index=0,
            updates={"process_status": "timed_out"},
        ),
        _replace_terminal(
            outcome.manifest,
            member_index=0,
            terminal_index=0,
            updates={"process_execution_storage": None},
        ),
        _replace_terminal(
            outcome.manifest,
            member_index=0,
            terminal_index=0,
            updates={"worker_result_storage": None},
        ),
    )
    for index, forged_manifest in enumerate(forged_manifests):
        clone, anchor_storage = _clone_with_forged_final_artifacts(
            tmp_path / f"forged-envelope-none-{index}",
            store,
            forged_manifest,
        )
        with pytest.raises(C4Stage1RunIntegrityError):
            cold_verify_c4_stage1_run(clone, anchor_storage)
