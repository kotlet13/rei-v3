"""Parent-owned, fail-closed orchestration for the C4 Stage 1 render screen.

This module is the only production entry point that may turn one prepared
attempt into child-process work.  It stores a per-worker authorization envelope
before spawn, owns the exact run-inventory ledger, finalizes telemetry and
process evidence on every terminal runner path, and publishes no member output
until both of that member's options have passed within the frozen deadline.

The resulting manifest is render-technical evidence only.  DINO and sealed
human review remain pending and no semantic or production authority is granted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import time
from typing import Annotated, Callable, Literal, Protocol, Self

from pydantic import Field, model_validator

from ..emocio.c4_stage1_editor import (
    C4Stage1WorkerRequest,
    C4Stage1WorkerResult,
    inspect_c4_stage1_png_bytes,
)
from ..ids import canonical_json_bytes, content_id, utc_now
from ..models.common import (
    FrozenArtifactModel,
    HashDigest,
    NonEmptyId,
)
from ..persistence.artifacts import FileArtifactStore, stored_artifact_id
from ..providers.protocols import StoredArtifact
from .c4_stage1_attempt import (
    C4_STAGE1_BOOTSTRAP_SCRIPT_PATH,
    C4_STAGE1_PREPARED_ANCHOR_PATH,
    C4Stage1PreparedAttempt,
    C4Stage1PreparedAttemptOutcome,
    C4Stage1PreparedWorker,
    C4Stage1ReviewServicePreflightPort,
    C4Stage1RepositoryGate,
    C4Stage1RuntimePaths,
    build_c4_stage1_worker_environment,
    capture_c4_stage1_repository_gate,
    cold_verify_c4_stage1_prepared_attempt,
    verify_c4_stage1_live_review_boundary,
    verify_c4_stage1_pre_spawn_runtime_bindings,
    verify_c4_stage1_staging_parent,
)
from .c4_stage1_staging import (
    C4Stage1PreparedStagingRoot,
    C4Stage1VerifiedStaging,
    prepare_c4_stage1_staging_root,
    verify_c4_stage1_staging,
)
from .c4_stage1_telemetry import (
    C4_STAGE1_PER_OPTION_HARD_TIMEOUT_SECONDS,
    C4Stage1ProcessRequestCommitment,
    C4Stage1TelemetryFinalizationOutcome,
    C4Stage1TelemetryFinalizer,
    C4Stage1TelemetryIntent,
    C4Stage1TelemetryLifecycleController,
    c4_stage1_zero_sample_failure_result,
    cold_verify_c4_stage1_telemetry_finalization,
    persist_c4_stage1_telemetry_intent,
)
from .process_tree_runner import (
    PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
    BoundedProcessRequest,
    BoundedProcessResult,
    BoundedProcessTreeRunner,
    ProcessOutputSummary,
    ProcessTreeExecutionRecord,
)
from .resource_telemetry import (
    BackgroundResourceTelemetrySamplerResult,
    ResourceTelemetryCudaDeviceIdentity,
)


C4_STAGE1_MEMBER_TIMEOUT_SECONDS = 420.0
C4_STAGE1_ATTEMPT_MANIFEST_PATH = "diagnostics/c4_stage1_render_attempt_manifest.json"
C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH = (
    "diagnostics/c4_stage1_render_attempt_inventory.json"
)
C4_STAGE1_LAUNCH_ENVELOPE_SUFFIX = "launch-envelope.json"

_MEMBER_TIMEOUT_NS = int(C4_STAGE1_MEMBER_TIMEOUT_SECONDS * 1_000_000_000)
_OPTION_TIMEOUT_NS = int(C4_STAGE1_PER_OPTION_HARD_TIMEOUT_SECONDS * 1_000_000_000)

FailureScope = Literal["none", "family", "global"]
MemberStatus = Literal["succeeded", "failed", "not_started"]
RenderAttemptStatus = Literal["evidence_ready", "failed"]


class C4Stage1RunError(RuntimeError):
    """A sanitized parent-orchestration failure."""


class C4Stage1ConfirmationError(C4Stage1RunError):
    """The operator did not confirm the exact prepared attempt."""


class C4Stage1RunIntegrityError(C4Stage1RunError):
    """The durable run tree or one of its cold bindings changed unexpectedly."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _commit_runtime_value(domain: str, value: object) -> str:
    return _canonical_sha256(
        {
            "domain": f"rei-c4-stage1-{domain}-commitment-v1",
            "value": value,
        }
    )


def _artifact_json_path(label: str, artifact_id: str) -> str:
    return f"diagnostics/{artifact_id}.{label}.json"


def c4_stage1_launch_envelope_relative_path(
    prepared_worker_id: str,
) -> str:
    return f"diagnostics/{prepared_worker_id}.{C4_STAGE1_LAUNCH_ENVELOPE_SUFFIX}"


def _pipeline_spec_id(request: C4Stage1WorkerRequest) -> str:
    return content_id("c4_stage1_pipeline_spec", request.editor_spec.pipeline)


def _snapshot_manifest_id(request: C4Stage1WorkerRequest) -> str:
    return content_id(
        "c4_stage1_snapshot_manifest",
        {
            "editor_role": request.editor_spec.editor_role,
            "verified_snapshot_id": request.verified_snapshot.verified_snapshot_id,
            "manifest_sha256": request.editor_spec.snapshot_manifest_sha256,
        },
    )


def _provider_slot_id(
    prepared: C4Stage1PreparedAttempt,
    worker: C4Stage1PreparedWorker,
) -> str:
    for policy in prepared.review_operator_policies:
        if policy.policy_id == worker.operator_policy_id:
            return policy.candidate_slot_id
    raise C4Stage1RunIntegrityError(
        "Stage 1 worker has no matching prepared provider slot"
    )


class C4Stage1LaunchEnvelope(FrozenArtifactModel):
    """Portable pre-spawn authorization plus hash-only runtime commitments."""

    schema_version: Literal["rei-c4-stage1-launch-envelope-v1"] = (
        "rei-c4-stage1-launch-envelope-v1"
    )
    launch_envelope_id: NonEmptyId
    launch_envelope_sha256: HashDigest
    run_id: NonEmptyId
    attempt_id: NonEmptyId
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    confirmed_prepared_attempt_id: NonEmptyId
    exact_prepared_attempt_confirmation: Literal[True] = True
    prepared_anchor_storage: StoredArtifact
    repository_gate_id: NonEmptyId
    repository_gate_sha256: HashDigest
    launch_policy_id: NonEmptyId
    launch_policy_sha256: HashDigest
    worker_runtime_id: NonEmptyId
    worker_runtime_sha256: HashDigest
    bootstrap_script_sha256: HashDigest
    bootstrap_script_size_bytes: Annotated[int, Field(gt=0)]
    worker_script_sha256: HashDigest
    worker_script_size_bytes: Annotated[int, Field(gt=0)]
    interpreter_isolation_flags: tuple[Literal["-I"], Literal["-S"]] = (
        "-I",
        "-S",
    )
    prepared_worker_id: NonEmptyId
    prepared_worker_sha256: HashDigest
    worker_request_id: NonEmptyId
    worker_request_sha256: HashDigest
    editor_role: Literal["primary", "alternate"]
    option_id: Literal["enter_circle", "remain_edge"]
    provider_slot_id: NonEmptyId
    provider_id: NonEmptyId
    editor_spec_id: NonEmptyId
    editor_spec_sha256: HashDigest
    pipeline_spec_id: NonEmptyId
    pipeline_spec_sha256: HashDigest
    verified_snapshot_id: NonEmptyId
    snapshot_manifest_id: NonEmptyId
    snapshot_manifest_sha256: HashDigest
    source_artifact_id: NonEmptyId
    source_sha256: HashDigest
    source_provenance_sha256: HashDigest
    cuda_device: ResourceTelemetryCudaDeviceIdentity
    telemetry_intent_id: NonEmptyId
    telemetry_intent_sha256: HashDigest
    telemetry_intent_storage: StoredArtifact
    process_request: C4Stage1ProcessRequestCommitment
    workload_id: NonEmptyId
    command_identity: NonEmptyId
    working_directory_identity: NonEmptyId
    environment_identity: NonEmptyId
    argument_count: Annotated[int, Field(ge=1, le=255)]
    raw_argv_commitment_sha256: HashDigest
    raw_environment_commitment_sha256: HashDigest
    raw_working_directory_commitment_sha256: HashDigest
    artifact_inventory_before_envelope: tuple[StoredArtifact, ...]
    local_paths_stored: Literal[False] = False
    raw_argv_stored: Literal[False] = False
    raw_environment_stored: Literal[False] = False
    raw_working_directory_stored: Literal[False] = False
    bootstrap_cold_verification_required: Literal[True] = True
    worker_cold_verification_required: Literal[True] = True
    model_calls_before_envelope: Literal[0] = 0
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        prepared: C4Stage1PreparedAttempt,
        prepared_anchor_storage: StoredArtifact,
        worker: C4Stage1PreparedWorker,
        intent: C4Stage1TelemetryIntent,
        intent_storage: StoredArtifact,
        process_request: BoundedProcessRequest,
        raw_argv_commitment_sha256: str,
        raw_environment_commitment_sha256: str,
        raw_working_directory_commitment_sha256: str,
        artifact_inventory_before_envelope: tuple[StoredArtifact, ...],
    ) -> C4Stage1LaunchEnvelope:
        request = worker.worker_request
        source = request.render_request.source_image
        if source is None:
            raise C4Stage1RunIntegrityError(
                "Stage 1 worker request has no frozen source"
            )
        process_commitment = C4Stage1ProcessRequestCommitment.from_request(
            process_request
        )
        body = {
            "schema_version": "rei-c4-stage1-launch-envelope-v1",
            "run_id": prepared.run_id,
            "attempt_id": prepared.attempt_id,
            "prepared_attempt_id": prepared.prepared_attempt_id,
            "prepared_attempt_sha256": prepared.prepared_attempt_sha256,
            "confirmed_prepared_attempt_id": prepared.prepared_attempt_id,
            "exact_prepared_attempt_confirmation": True,
            "prepared_anchor_storage": prepared_anchor_storage,
            "repository_gate_id": prepared.repository_gate.repository_gate_id,
            "repository_gate_sha256": (prepared.repository_gate.repository_gate_sha256),
            "launch_policy_id": prepared.launch_policy.launch_policy_id,
            "launch_policy_sha256": prepared.launch_policy.launch_policy_sha256,
            "worker_runtime_id": prepared.worker_runtime.worker_runtime_id,
            "worker_runtime_sha256": prepared.worker_runtime.worker_runtime_sha256,
            "bootstrap_script_sha256": (prepared.launch_policy.bootstrap_script_sha256),
            "bootstrap_script_size_bytes": (
                prepared.launch_policy.bootstrap_script_size_bytes
            ),
            "worker_script_sha256": prepared.launch_policy.worker_script_sha256,
            "worker_script_size_bytes": (
                prepared.launch_policy.worker_script_size_bytes
            ),
            "interpreter_isolation_flags": ("-I", "-S"),
            "prepared_worker_id": worker.prepared_worker_id,
            "prepared_worker_sha256": worker.content_hash(),
            "worker_request_id": request.worker_request_id,
            "worker_request_sha256": request.content_hash(),
            "editor_role": worker.editor_role,
            "option_id": worker.option_id,
            "provider_slot_id": _provider_slot_id(prepared, worker),
            "provider_id": request.editor_spec.provider.provider_id,
            "editor_spec_id": request.editor_spec.spec_id,
            "editor_spec_sha256": request.editor_spec.content_hash(),
            "pipeline_spec_id": _pipeline_spec_id(request),
            "pipeline_spec_sha256": request.editor_spec.pipeline.content_hash(),
            "verified_snapshot_id": request.verified_snapshot.verified_snapshot_id,
            "snapshot_manifest_id": _snapshot_manifest_id(request),
            "snapshot_manifest_sha256": (request.editor_spec.snapshot_manifest_sha256),
            "source_artifact_id": source.image_id,
            "source_sha256": source.content_sha256,
            "source_provenance_sha256": prepared.source_provenance_sha256,
            "cuda_device": prepared.cuda_device,
            "telemetry_intent_id": intent.intent_id,
            "telemetry_intent_sha256": intent.intent_sha256,
            "telemetry_intent_storage": intent_storage,
            "process_request": process_commitment,
            "workload_id": process_request.workload_id,
            "command_identity": process_request.command_identity,
            "working_directory_identity": (process_request.working_directory_identity),
            "environment_identity": process_request.environment_identity,
            "argument_count": len(process_request.command) - 1,
            "raw_argv_commitment_sha256": raw_argv_commitment_sha256,
            "raw_environment_commitment_sha256": (raw_environment_commitment_sha256),
            "raw_working_directory_commitment_sha256": (
                raw_working_directory_commitment_sha256
            ),
            "artifact_inventory_before_envelope": (artifact_inventory_before_envelope),
            "local_paths_stored": False,
            "raw_argv_stored": False,
            "raw_environment_stored": False,
            "raw_working_directory_stored": False,
            "bootstrap_cold_verification_required": True,
            "worker_cold_verification_required": True,
            "model_calls_before_envelope": 0,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(
            launch_envelope_id=content_id("c4_stage1_launch_envelope", body),
            launch_envelope_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        process = C4Stage1ProcessRequestCommitment.model_validate(
            self.process_request.model_dump(mode="python", round_trip=True)
        )
        intent_storage = StoredArtifact.model_validate(
            self.telemetry_intent_storage.model_dump(mode="python", round_trip=True)
        )
        paths = tuple(
            item.relative_path for item in self.artifact_inventory_before_envelope
        )
        if (
            self.confirmed_prepared_attempt_id != self.prepared_attempt_id
            or self.interpreter_isolation_flags != ("-I", "-S")
            or self.cuda_device.status != "resolved"
            or self.cuda_device.logical_device_index != 0
            or self.cuda_device.physical_gpu_uuid is None
            or intent_storage.run_id != self.run_id
            or intent_storage.relative_path
            != f"diagnostics/{self.telemetry_intent_id}.telemetry-intent.json"
            or process.workload_id != self.workload_id
            or process.command_identity != self.command_identity
            or process.working_directory_identity != self.working_directory_identity
            or process.environment_identity != self.environment_identity
            or process.argument_count != self.argument_count
            or paths != tuple(sorted(paths))
            or len(paths) != len(set(paths))
            or intent_storage not in self.artifact_inventory_before_envelope
            or self.prepared_anchor_storage
            not in self.artifact_inventory_before_envelope
        ):
            raise ValueError("Stage 1 launch envelope lineage is inconsistent")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"launch_envelope_id", "launch_envelope_sha256"},
        )
        if self.launch_envelope_id != content_id(
            "c4_stage1_launch_envelope", body
        ) or self.launch_envelope_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 launch envelope differs from content")
        return self


class C4Stage1PublishedCandidateReceipt(FrozenArtifactModel):
    """Parent-issued, path-safe lineage for one committed render candidate."""

    schema_version: Literal["rei-c4-stage1-published-candidate-receipt-v1"] = (
        "rei-c4-stage1-published-candidate-receipt-v1"
    )
    candidate_receipt_id: NonEmptyId
    candidate_receipt_sha256: HashDigest
    run_id: NonEmptyId
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    prepared_worker_id: NonEmptyId
    prepared_worker_sha256: HashDigest
    worker_request_id: NonEmptyId
    worker_request_sha256: HashDigest
    editor_role: Literal["primary", "alternate"]
    option_id: Literal["enter_circle", "remain_edge"]
    provider_slot_id: NonEmptyId
    provider_id: NonEmptyId
    launch_envelope_id: NonEmptyId
    launch_envelope_sha256: HashDigest
    launch_envelope_storage: StoredArtifact
    process_execution_record_id: NonEmptyId
    process_execution_record_sha256: HashDigest
    process_execution_storage: StoredArtifact
    telemetry_finalization_receipt_id: NonEmptyId
    telemetry_finalization_receipt_sha256: HashDigest
    telemetry_finalization_storage: StoredArtifact
    worker_result_id: NonEmptyId
    worker_result_sha256: HashDigest
    worker_result_storage: StoredArtifact
    image_evidence_id: NonEmptyId
    image_evidence_sha256: HashDigest
    direct_output_storage: StoredArtifact
    staged_output_storage: StoredArtifact
    direct_png_sha256: HashDigest
    direct_png_size_bytes: Annotated[int, Field(gt=0)]
    direct_width: Annotated[int, Field(gt=0)]
    direct_height: Annotated[int, Field(gt=0)]
    staged_png_sha256: HashDigest
    staged_png_size_bytes: Annotated[int, Field(gt=0)]
    staged_width: Literal[1024] = 1024
    staged_height: Literal[768] = 768
    process_status: Literal["succeeded"] = "succeeded"
    worker_status: Literal["succeeded"] = "succeeded"
    staging_verified: Literal[True] = True
    telemetry_cold_verified: Literal[True] = True
    telemetry_technical_passed: Literal[True] = True
    member_commit_required: Literal[True] = True
    generated_images_are_external_evidence: Literal[False] = False
    dino_gate_status: Literal["pending"] = "pending"
    human_review_status: Literal["pending"] = "pending"
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        prepared: C4Stage1PreparedAttempt,
        execution: _WorkerExecution,
    ) -> C4Stage1PublishedCandidateReceipt:
        outcome = execution.telemetry_outcome
        evidence = execution.worker_result.image_evidence
        if (
            not execution.technical_passed
            or execution.process_record.status != "succeeded"
            or execution.worker_result.status != "succeeded"
            or not execution.staging_verified
            or outcome is None
            or not execution.telemetry_cold_verified
            or not outcome.technical_passed
            or outcome.receipt_storage is None
            or execution.envelope_storage is None
            or execution.process_storage is None
            or execution.worker_result_storage is None
            or execution.direct_output_storage is None
            or execution.staged_output_storage is None
            or evidence is None
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 candidate receipt lacks complete passing evidence"
            )
        body = {
            "schema_version": "rei-c4-stage1-published-candidate-receipt-v1",
            "run_id": prepared.run_id,
            "prepared_attempt_id": prepared.prepared_attempt_id,
            "prepared_attempt_sha256": prepared.prepared_attempt_sha256,
            "prepared_worker_id": execution.worker.prepared_worker_id,
            "prepared_worker_sha256": execution.worker.content_hash(),
            "worker_request_id": execution.worker.worker_request.worker_request_id,
            "worker_request_sha256": execution.worker.worker_request.content_hash(),
            "editor_role": execution.worker.editor_role,
            "option_id": execution.worker.option_id,
            "provider_slot_id": _provider_slot_id(prepared, execution.worker),
            "provider_id": (
                execution.worker.worker_request.editor_spec.provider.provider_id
            ),
            "launch_envelope_id": execution.envelope.launch_envelope_id,
            "launch_envelope_sha256": execution.envelope.launch_envelope_sha256,
            "launch_envelope_storage": execution.envelope_storage,
            "process_execution_record_id": execution.process_record.record_id,
            "process_execution_record_sha256": _canonical_sha256(
                execution.process_record
            ),
            "process_execution_storage": execution.process_storage,
            "telemetry_finalization_receipt_id": (
                outcome.receipt.finalization_receipt_id
            ),
            "telemetry_finalization_receipt_sha256": (
                outcome.receipt.finalization_receipt_sha256
            ),
            "telemetry_finalization_storage": outcome.receipt_storage,
            "worker_result_id": execution.worker_result.worker_result_id,
            "worker_result_sha256": _canonical_sha256(execution.worker_result),
            "worker_result_storage": execution.worker_result_storage,
            "image_evidence_id": evidence.image_evidence_id,
            "image_evidence_sha256": _canonical_sha256(evidence),
            "direct_output_storage": execution.direct_output_storage,
            "staged_output_storage": execution.staged_output_storage,
            "direct_png_sha256": evidence.direct_png_sha256,
            "direct_png_size_bytes": evidence.direct_png_size_bytes,
            "direct_width": evidence.direct_width,
            "direct_height": evidence.direct_height,
            "staged_png_sha256": evidence.staged_png_sha256,
            "staged_png_size_bytes": evidence.staged_png_size_bytes,
            "staged_width": evidence.staged_width,
            "staged_height": evidence.staged_height,
            "process_status": "succeeded",
            "worker_status": "succeeded",
            "staging_verified": True,
            "telemetry_cold_verified": True,
            "telemetry_technical_passed": True,
            "member_commit_required": True,
            "generated_images_are_external_evidence": False,
            "dino_gate_status": "pending",
            "human_review_status": "pending",
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(
            candidate_receipt_id=content_id("c4_stage1_candidate_receipt", body),
            candidate_receipt_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_candidate_receipt(self) -> Self:
        if (
            self.direct_output_storage.run_id != self.run_id
            or self.staged_output_storage.run_id != self.run_id
            or self.direct_output_storage.relative_path
            != f"diagnostics/{self.worker_request_id}.direct.png"
            or self.staged_output_storage.relative_path
            != f"emocio/images/{self.worker_request_id}.png"
            or self.direct_output_storage.content_sha256 != self.direct_png_sha256
            or self.direct_output_storage.size_bytes != self.direct_png_size_bytes
            or self.staged_output_storage.content_sha256 != self.staged_png_sha256
            or self.staged_output_storage.size_bytes != self.staged_png_size_bytes
        ):
            raise ValueError("Stage 1 candidate publication descriptors are invalid")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"candidate_receipt_id", "candidate_receipt_sha256"},
        )
        if self.candidate_receipt_id != content_id(
            "c4_stage1_candidate_receipt", body
        ) or self.candidate_receipt_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 candidate receipt differs from content")
        return self


class C4Stage1MemberPublicationReceipt(FrozenArtifactModel):
    """Single create-only marker that commits both family candidates together."""

    schema_version: Literal["rei-c4-stage1-member-publication-receipt-v1"] = (
        "rei-c4-stage1-member-publication-receipt-v1"
    )
    member_publication_receipt_id: NonEmptyId
    member_publication_receipt_sha256: HashDigest
    run_id: NonEmptyId
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    editor_role: Literal["primary", "alternate"]
    provider_slot_id: NonEmptyId
    candidate_receipts: tuple[
        C4Stage1PublishedCandidateReceipt,
        C4Stage1PublishedCandidateReceipt,
    ]
    artifact_inventory_before_receipt: tuple[StoredArtifact, ...]
    both_options_technical_passed: Literal[True] = True
    publication_committed: Literal[True] = True
    generated_images_are_external_evidence: Literal[False] = False
    dino_gate_status: Literal["pending"] = "pending"
    human_review_status: Literal["pending"] = "pending"
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        prepared: C4Stage1PreparedAttempt,
        executions: tuple[_WorkerExecution, _WorkerExecution],
        artifact_inventory_before_receipt: tuple[StoredArtifact, ...],
    ) -> C4Stage1MemberPublicationReceipt:
        candidates = tuple(
            C4Stage1PublishedCandidateReceipt.create(
                prepared=prepared,
                execution=execution,
            )
            for execution in executions
        )
        first = executions[0].worker
        body = {
            "schema_version": "rei-c4-stage1-member-publication-receipt-v1",
            "run_id": prepared.run_id,
            "prepared_attempt_id": prepared.prepared_attempt_id,
            "prepared_attempt_sha256": prepared.prepared_attempt_sha256,
            "editor_role": first.editor_role,
            "provider_slot_id": _provider_slot_id(prepared, first),
            "candidate_receipts": candidates,
            "artifact_inventory_before_receipt": artifact_inventory_before_receipt,
            "both_options_technical_passed": True,
            "publication_committed": True,
            "generated_images_are_external_evidence": False,
            "dino_gate_status": "pending",
            "human_review_status": "pending",
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(
            member_publication_receipt_id=content_id("c4_stage1_member_publish", body),
            member_publication_receipt_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_member_publication_receipt(self) -> Self:
        inventory_paths = tuple(
            item.relative_path for item in self.artifact_inventory_before_receipt
        )
        output_descriptors = tuple(
            descriptor
            for candidate in self.candidate_receipts
            for descriptor in (
                candidate.direct_output_storage,
                candidate.staged_output_storage,
            )
        )
        if (
            tuple(item.option_id for item in self.candidate_receipts)
            != ("enter_circle", "remain_edge")
            or any(
                item.run_id != self.run_id
                or item.prepared_attempt_id != self.prepared_attempt_id
                or item.prepared_attempt_sha256 != self.prepared_attempt_sha256
                or item.editor_role != self.editor_role
                or item.provider_slot_id != self.provider_slot_id
                for item in self.candidate_receipts
            )
            or inventory_paths != tuple(sorted(inventory_paths))
            or len(inventory_paths) != len(set(inventory_paths))
            or any(
                item not in self.artifact_inventory_before_receipt
                for item in output_descriptors
            )
        ):
            raise ValueError("Stage 1 member publication receipt is inconsistent")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "member_publication_receipt_id",
                "member_publication_receipt_sha256",
            },
        )
        if self.member_publication_receipt_id != content_id(
            "c4_stage1_member_publish", body
        ) or self.member_publication_receipt_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 member publication receipt differs from content")
        return self


class C4Stage1WorkerTerminal(FrozenArtifactModel):
    """Sanitized terminal lineage for one attempted provider option."""

    schema_version: Literal["rei-c4-stage1-worker-terminal-v1"] = (
        "rei-c4-stage1-worker-terminal-v1"
    )
    worker_terminal_id: NonEmptyId
    worker_terminal_sha256: HashDigest
    prepared_worker_id: NonEmptyId
    worker_request_id: NonEmptyId
    editor_role: Literal["primary", "alternate"]
    option_id: Literal["enter_circle", "remain_edge"]
    launch_envelope_id: NonEmptyId
    launch_envelope_sha256: HashDigest
    launch_envelope_storage: StoredArtifact | None
    telemetry_intent_id: NonEmptyId
    telemetry_intent_sha256: HashDigest
    telemetry_intent_storage: StoredArtifact
    process_execution_record_id: NonEmptyId
    process_execution_record_sha256: HashDigest
    process_execution_storage: StoredArtifact | None
    telemetry_finalization_receipt_id: NonEmptyId | None
    telemetry_finalization_receipt_sha256: HashDigest | None
    telemetry_finalization_storage: StoredArtifact | None
    worker_result_id: NonEmptyId
    worker_result_sha256: HashDigest
    worker_result_storage: StoredArtifact | None
    process_status: Literal["succeeded", "failed", "timed_out"]
    worker_status: Literal["succeeded", "failed"]
    staging_verified: bool
    telemetry_cold_verified: bool
    telemetry_technical_passed: bool
    worker_technical_passed: bool
    failure_scope: FailureScope
    failure_codes: tuple[NonEmptyId, ...]
    direct_output_storage: StoredArtifact | None = None
    staged_output_storage: StoredArtifact | None = None
    published_candidate_receipt_id: NonEmptyId | None = None
    published_candidate_receipt_sha256: HashDigest | None = None
    member_publication_receipt_id: NonEmptyId | None = None
    member_publication_receipt_sha256: HashDigest | None = None
    member_publication_receipt_storage: StoredArtifact | None = None
    member_publication_completed: bool = False
    generated_images_are_external_evidence: Literal[False] = False
    dino_gate_status: Literal["pending"] = "pending"
    human_review_status: Literal["pending"] = "pending"
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        worker: C4Stage1PreparedWorker,
        envelope: C4Stage1LaunchEnvelope,
        envelope_storage: StoredArtifact | None,
        intent: C4Stage1TelemetryIntent,
        intent_storage: StoredArtifact,
        process_record: ProcessTreeExecutionRecord,
        process_storage: StoredArtifact | None,
        telemetry_outcome: C4Stage1TelemetryFinalizationOutcome | None,
        telemetry_cold_verified: bool,
        worker_result: C4Stage1WorkerResult,
        worker_result_storage: StoredArtifact | None,
        staging_verified: bool,
        worker_technical_passed: bool,
        failure_scope: FailureScope,
        failure_codes: tuple[str, ...],
        direct_output_storage: StoredArtifact | None = None,
        staged_output_storage: StoredArtifact | None = None,
        published_candidate_receipt: C4Stage1PublishedCandidateReceipt | None = None,
        member_publication_receipt: C4Stage1MemberPublicationReceipt | None = None,
        member_publication_receipt_storage: StoredArtifact | None = None,
        member_publication_completed: bool = False,
    ) -> C4Stage1WorkerTerminal:
        receipt = None if telemetry_outcome is None else telemetry_outcome.receipt
        receipt_storage = (
            None if telemetry_outcome is None else telemetry_outcome.receipt_storage
        )
        telemetry_passed = bool(
            telemetry_outcome is not None
            and telemetry_cold_verified
            and telemetry_outcome.technical_passed
        )
        capable = bool(
            process_record.status == "succeeded"
            and worker_result.status == "succeeded"
            and staging_verified
            and telemetry_passed
            and envelope_storage is not None
            and process_storage is not None
            and worker_result_storage is not None
        )
        body = {
            "schema_version": "rei-c4-stage1-worker-terminal-v1",
            "prepared_worker_id": worker.prepared_worker_id,
            "worker_request_id": worker.worker_request.worker_request_id,
            "editor_role": worker.editor_role,
            "option_id": worker.option_id,
            "launch_envelope_id": envelope.launch_envelope_id,
            "launch_envelope_sha256": envelope.launch_envelope_sha256,
            "launch_envelope_storage": envelope_storage,
            "telemetry_intent_id": intent.intent_id,
            "telemetry_intent_sha256": intent.intent_sha256,
            "telemetry_intent_storage": intent_storage,
            "process_execution_record_id": process_record.record_id,
            "process_execution_record_sha256": _canonical_sha256(process_record),
            "process_execution_storage": process_storage,
            "telemetry_finalization_receipt_id": (
                None if receipt is None else receipt.finalization_receipt_id
            ),
            "telemetry_finalization_receipt_sha256": (
                None if receipt is None else receipt.finalization_receipt_sha256
            ),
            "telemetry_finalization_storage": receipt_storage,
            "worker_result_id": worker_result.worker_result_id,
            "worker_result_sha256": _canonical_sha256(worker_result),
            "worker_result_storage": worker_result_storage,
            "process_status": process_record.status,
            "worker_status": worker_result.status,
            "staging_verified": staging_verified,
            "telemetry_cold_verified": telemetry_cold_verified,
            "telemetry_technical_passed": telemetry_passed,
            "worker_technical_passed": worker_technical_passed,
            "failure_scope": failure_scope,
            "failure_codes": tuple(sorted(set(failure_codes))),
            "direct_output_storage": direct_output_storage,
            "staged_output_storage": staged_output_storage,
            "published_candidate_receipt_id": (
                None
                if published_candidate_receipt is None
                else published_candidate_receipt.candidate_receipt_id
            ),
            "published_candidate_receipt_sha256": (
                None
                if published_candidate_receipt is None
                else published_candidate_receipt.candidate_receipt_sha256
            ),
            "member_publication_receipt_id": (
                None
                if member_publication_receipt is None
                else member_publication_receipt.member_publication_receipt_id
            ),
            "member_publication_receipt_sha256": (
                None
                if member_publication_receipt is None
                else member_publication_receipt.member_publication_receipt_sha256
            ),
            "member_publication_receipt_storage": (member_publication_receipt_storage),
            "member_publication_completed": member_publication_completed,
            "generated_images_are_external_evidence": False,
            "dino_gate_status": "pending",
            "human_review_status": "pending",
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        if worker_technical_passed and not capable:
            raise ValueError(
                "Stage 1 worker cannot pass without complete terminal evidence"
            )
        return cls(
            worker_terminal_id=content_id("c4_stage1_worker_terminal", body),
            worker_terminal_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_terminal(self) -> Self:
        telemetry_refs = (
            self.telemetry_finalization_receipt_id,
            self.telemetry_finalization_receipt_sha256,
            self.telemetry_finalization_storage,
        )
        publication_refs = (
            self.direct_output_storage,
            self.staged_output_storage,
            self.published_candidate_receipt_id,
            self.published_candidate_receipt_sha256,
            self.member_publication_receipt_id,
            self.member_publication_receipt_sha256,
            self.member_publication_receipt_storage,
        )
        capable = (
            self.process_status == "succeeded"
            and self.worker_status == "succeeded"
            and self.staging_verified
            and self.telemetry_technical_passed
            and self.process_execution_storage is not None
            and self.worker_result_storage is not None
        )
        if (
            self.worker_technical_passed
            and not capable
            or (self.failure_scope == "none") != self.worker_technical_passed
            or self.worker_technical_passed == bool(self.failure_codes)
            or any(item is None for item in telemetry_refs)
            != all(item is None for item in telemetry_refs)
            or self.telemetry_cold_verified
            and any(item is None for item in telemetry_refs)
            or self.telemetry_technical_passed
            and not self.telemetry_cold_verified
            or self.member_publication_completed
            != all(item is not None for item in publication_refs)
            or self.member_publication_completed
            and not self.worker_technical_passed
            or self.launch_envelope_storage is None
            and (
                self.worker_technical_passed
                or self.failure_scope != "global"
                or not {
                    "intent_persistence_verification_failed",
                    "intent_storage_descriptor_mismatch",
                    "launch_envelope_persistence_failed",
                }.intersection(self.failure_codes)
            )
            or not self.member_publication_completed
            and any(item is not None for item in publication_refs[2:])
        ):
            raise ValueError("Stage 1 worker terminal disposition is invalid")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"worker_terminal_id", "worker_terminal_sha256"},
        )
        if self.worker_terminal_id != content_id(
            "c4_stage1_worker_terminal", body
        ) or self.worker_terminal_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 worker terminal differs from content")
        return self


class C4Stage1MemberRun(FrozenArtifactModel):
    """One provider family, stopped after its first failed option."""

    schema_version: Literal["rei-c4-stage1-member-run-v1"] = (
        "rei-c4-stage1-member-run-v1"
    )
    member_run_id: NonEmptyId
    member_run_sha256: HashDigest
    editor_role: Literal["primary", "alternate"]
    provider_slot_id: NonEmptyId
    status: MemberStatus
    worker_terminals: tuple[C4Stage1WorkerTerminal, ...] = Field(max_length=2)
    worker_spawn_count: Annotated[int, Field(ge=0, le=2)]
    elapsed_monotonic_seconds: Annotated[float, Field(ge=0.0)]
    exact_member_timeout_seconds: Literal[420.0] = C4_STAGE1_MEMBER_TIMEOUT_SECONDS
    stopped_after_first_failure: Literal[True] = True
    publication_completed: bool
    failure_codes: tuple[NonEmptyId, ...]

    @classmethod
    def create(
        cls,
        *,
        editor_role: Literal["primary", "alternate"],
        provider_slot_id: str,
        status: MemberStatus,
        worker_terminals: tuple[C4Stage1WorkerTerminal, ...],
        elapsed_monotonic_seconds: float,
        failure_codes: tuple[str, ...],
    ) -> C4Stage1MemberRun:
        publication_completed = bool(
            status == "succeeded"
            and len(worker_terminals) == 2
            and all(item.member_publication_completed for item in worker_terminals)
        )
        body = {
            "schema_version": "rei-c4-stage1-member-run-v1",
            "editor_role": editor_role,
            "provider_slot_id": provider_slot_id,
            "status": status,
            "worker_terminals": worker_terminals,
            "worker_spawn_count": len(worker_terminals),
            "elapsed_monotonic_seconds": elapsed_monotonic_seconds,
            "exact_member_timeout_seconds": C4_STAGE1_MEMBER_TIMEOUT_SECONDS,
            "stopped_after_first_failure": True,
            "publication_completed": publication_completed,
            "failure_codes": tuple(sorted(set(failure_codes))),
        }
        return cls(
            member_run_id=content_id("c4_stage1_member_run", body),
            member_run_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_member(self) -> Self:
        expected_options = ("enter_circle", "remain_edge")[: len(self.worker_terminals)]
        if (
            self.worker_spawn_count != len(self.worker_terminals)
            or tuple(item.option_id for item in self.worker_terminals)
            != expected_options
            or any(
                item.editor_role != self.editor_role for item in self.worker_terminals
            )
            or len(self.worker_terminals) == 2
            and not self.worker_terminals[0].worker_technical_passed
        ):
            raise ValueError("Stage 1 member violated option order or stop policy")
        succeeded = (
            len(self.worker_terminals) == 2
            and self.elapsed_monotonic_seconds <= C4_STAGE1_MEMBER_TIMEOUT_SECONDS
            and all(
                item.worker_technical_passed and item.member_publication_completed
                for item in self.worker_terminals
            )
        )
        if (
            (self.status == "succeeded") != succeeded
            or self.publication_completed != succeeded
            or (self.status == "succeeded") == bool(self.failure_codes)
            or self.status == "not_started"
            and (bool(self.worker_terminals) or not self.failure_codes)
        ):
            raise ValueError("Stage 1 member disposition is inconsistent")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"member_run_id", "member_run_sha256"},
        )
        if self.member_run_id != content_id(
            "c4_stage1_member_run", body
        ) or self.member_run_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 member run differs from content")
        return self


class C4Stage1RenderAttemptManifest(FrozenArtifactModel):
    """Final render-only result written immediately before the inventory anchor."""

    schema_version: Literal["rei-c4-stage1-render-attempt-manifest-v1"] = (
        "rei-c4-stage1-render-attempt-manifest-v1"
    )
    render_attempt_manifest_id: NonEmptyId
    render_attempt_manifest_sha256: HashDigest
    run_id: NonEmptyId
    attempt_id: NonEmptyId
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    prepared_anchor_storage: StoredArtifact
    exact_prepared_attempt_confirmed: Literal[True] = True
    member_runs: tuple[C4Stage1MemberRun, C4Stage1MemberRun]
    status: RenderAttemptStatus
    render_technical_completed: bool
    both_families_required: Literal[True] = True
    global_stop_triggered: bool
    failure_codes: tuple[NonEmptyId, ...]
    artifact_inventory_before_manifest: tuple[StoredArtifact, ...]
    dino_gate_status: Literal["pending"] = "pending"
    human_review_status: Literal["pending"] = "pending"
    semantic_stage1_passed: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        prepared: C4Stage1PreparedAttempt,
        prepared_anchor_storage: StoredArtifact,
        member_runs: tuple[C4Stage1MemberRun, C4Stage1MemberRun],
        global_stop_triggered: bool,
        failure_codes: tuple[str, ...],
        artifact_inventory_before_manifest: tuple[StoredArtifact, ...],
    ) -> C4Stage1RenderAttemptManifest:
        completed = bool(
            not global_stop_triggered
            and all(item.status == "succeeded" for item in member_runs)
        )
        body = {
            "schema_version": "rei-c4-stage1-render-attempt-manifest-v1",
            "run_id": prepared.run_id,
            "attempt_id": prepared.attempt_id,
            "prepared_attempt_id": prepared.prepared_attempt_id,
            "prepared_attempt_sha256": prepared.prepared_attempt_sha256,
            "prepared_anchor_storage": prepared_anchor_storage,
            "exact_prepared_attempt_confirmed": True,
            "member_runs": member_runs,
            "status": "evidence_ready" if completed else "failed",
            "render_technical_completed": completed,
            "both_families_required": True,
            "global_stop_triggered": global_stop_triggered,
            "failure_codes": tuple(sorted(set(failure_codes))),
            "artifact_inventory_before_manifest": (artifact_inventory_before_manifest),
            "dino_gate_status": "pending",
            "human_review_status": "pending",
            "semantic_stage1_passed": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(
            render_attempt_manifest_id=content_id("c4_stage1_render_manifest", body),
            render_attempt_manifest_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        paths = tuple(
            item.relative_path for item in self.artifact_inventory_before_manifest
        )
        completed = bool(
            not self.global_stop_triggered
            and all(item.status == "succeeded" for item in self.member_runs)
        )
        if (
            tuple(item.editor_role for item in self.member_runs)
            != ("primary", "alternate")
            or self.render_technical_completed != completed
            or self.status != ("evidence_ready" if completed else "failed")
            or self.global_stop_triggered
            != ("global_stop_triggered" in self.failure_codes)
            or completed == bool(self.failure_codes)
            or paths != tuple(sorted(paths))
            or len(paths) != len(set(paths))
            or C4_STAGE1_ATTEMPT_MANIFEST_PATH in paths
        ):
            raise ValueError("Stage 1 render manifest disposition is invalid")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "render_attempt_manifest_id",
                "render_attempt_manifest_sha256",
            },
        )
        if self.render_attempt_manifest_id != content_id(
            "c4_stage1_render_manifest", body
        ) or self.render_attempt_manifest_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 render manifest differs from content")
        return self


class C4Stage1RenderInventoryAnchor(FrozenArtifactModel):
    """Last create-only artifact: exact inventory immediately before itself."""

    schema_version: Literal["rei-c4-stage1-render-inventory-anchor-v1"] = (
        "rei-c4-stage1-render-inventory-anchor-v1"
    )
    render_inventory_anchor_id: NonEmptyId
    render_inventory_anchor_sha256: HashDigest
    run_id: NonEmptyId
    prepared_attempt_id: NonEmptyId
    render_attempt_manifest_id: NonEmptyId
    render_attempt_manifest_sha256: HashDigest
    render_attempt_manifest_storage: StoredArtifact
    artifact_inventory_before_anchor: tuple[StoredArtifact, ...]
    exact_inventory_required: Literal[True] = True

    @classmethod
    def create(
        cls,
        manifest: C4Stage1RenderAttemptManifest,
        manifest_storage: StoredArtifact,
        *,
        artifact_inventory_before_anchor: tuple[StoredArtifact, ...],
    ) -> C4Stage1RenderInventoryAnchor:
        body = {
            "schema_version": "rei-c4-stage1-render-inventory-anchor-v1",
            "run_id": manifest.run_id,
            "prepared_attempt_id": manifest.prepared_attempt_id,
            "render_attempt_manifest_id": manifest.render_attempt_manifest_id,
            "render_attempt_manifest_sha256": (manifest.render_attempt_manifest_sha256),
            "render_attempt_manifest_storage": manifest_storage,
            "artifact_inventory_before_anchor": artifact_inventory_before_anchor,
            "exact_inventory_required": True,
        }
        return cls(
            render_inventory_anchor_id=content_id("c4_stage1_render_inventory", body),
            render_inventory_anchor_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_anchor(self) -> Self:
        paths = tuple(
            item.relative_path for item in self.artifact_inventory_before_anchor
        )
        if (
            self.render_attempt_manifest_storage.relative_path
            != C4_STAGE1_ATTEMPT_MANIFEST_PATH
            or self.render_attempt_manifest_storage
            not in self.artifact_inventory_before_anchor
            or paths != tuple(sorted(paths))
            or len(paths) != len(set(paths))
            or C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH in paths
        ):
            raise ValueError("Stage 1 render inventory anchor is invalid")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "render_inventory_anchor_id",
                "render_inventory_anchor_sha256",
            },
        )
        if self.render_inventory_anchor_id != content_id(
            "c4_stage1_render_inventory", body
        ) or self.render_inventory_anchor_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 render inventory anchor differs from content")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1RunOutcome:
    manifest: C4Stage1RenderAttemptManifest
    manifest_storage: StoredArtifact
    inventory_anchor: C4Stage1RenderInventoryAnchor
    inventory_anchor_storage: StoredArtifact


@dataclass(slots=True)
class _InventoryLedger:
    run_id: str
    _by_path: dict[str, StoredArtifact] = field(default_factory=dict)

    @classmethod
    def from_prepared(
        cls,
        outcome: C4Stage1PreparedAttemptOutcome,
    ) -> _InventoryLedger:
        ledger = cls(run_id=outcome.prepared_attempt.run_id)
        for descriptor in (
            *outcome.prepared_attempt.artifact_inventory_before_anchor,
            outcome.prepared_anchor_storage,
        ):
            ledger.add(descriptor)
        return ledger

    def add(self, descriptor: StoredArtifact | None) -> None:
        if descriptor is None:
            return
        value = StoredArtifact.model_validate(
            descriptor.model_dump(mode="python", round_trip=True)
        )
        if value.run_id != self.run_id:
            raise C4Stage1RunIntegrityError("Stage 1 artifact belongs to another run")
        previous = self._by_path.get(value.relative_path)
        if previous is not None and previous != value:
            raise C4Stage1RunIntegrityError(
                "Stage 1 create-only artifact path changed identity"
            )
        self._by_path[value.relative_path] = value

    def snapshot(self) -> tuple[StoredArtifact, ...]:
        return tuple(self._by_path[path] for path in sorted(self._by_path))

    def verify_exact(self, artifact_store: FileArtifactStore) -> None:
        try:
            actual = artifact_store.inspect_run_inventory_exact(self.run_id)
        except Exception as exc:
            raise C4Stage1RunIntegrityError(
                "Stage 1 run inventory cannot be inspected exactly"
            ) from exc
        if actual != self.snapshot():
            raise C4Stage1RunIntegrityError(
                "Stage 1 run inventory differs from the parent-owned ledger"
            )


def _recover_transient_post_intent_inventory_failure(
    artifact_store: FileArtifactStore,
    ledger: _InventoryLedger,
) -> BaseException | None:
    """Recheck a failed ledger read without hiding a real inventory mismatch."""

    try:
        ledger.verify_exact(artifact_store)
        return None
    except BaseException as failure:
        try:
            actual = artifact_store.inspect_run_inventory_exact(ledger.run_id)
        except BaseException as exc:
            raise C4Stage1RunIntegrityError(
                "Stage 1 post-intent inventory cannot be inspected"
            ) from exc
        if actual != ledger.snapshot():
            raise C4Stage1RunIntegrityError(
                "Stage 1 post-intent inventory differs from its ledger"
            ) from failure
        return failure


class _Runner(Protocol):
    @property
    def last_terminal_result(self) -> BoundedProcessResult: ...

    def run(self, request: BoundedProcessRequest) -> BoundedProcessResult: ...


ControllerFactory = Callable[
    [C4Stage1TelemetryIntent, ResourceTelemetryCudaDeviceIdentity], object
]
RunnerFactory = Callable[
    [object, C4Stage1PreparedWorker, Path],
    _Runner,
]
FinalizerFactory = Callable[
    [C4Stage1TelemetryIntent, FileArtifactStore],
    object,
]


def _default_controller_factory(
    intent: C4Stage1TelemetryIntent,
    cuda_device: ResourceTelemetryCudaDeviceIdentity,
) -> C4Stage1TelemetryLifecycleController:
    return C4Stage1TelemetryLifecycleController(
        intent,
        cuda_device=cuda_device,
    )


def _default_runner_factory(
    observer: object,
    worker: C4Stage1PreparedWorker,
    staging_root: Path,
) -> BoundedProcessTreeRunner:
    del worker, staging_root
    return BoundedProcessTreeRunner(observer=observer)  # type: ignore[arg-type]


def _default_finalizer_factory(
    intent: C4Stage1TelemetryIntent,
    artifact_store: FileArtifactStore,
) -> C4Stage1TelemetryFinalizer:
    return C4Stage1TelemetryFinalizer(intent, artifact_store=artifact_store)


def _verify_live_review_boundary(
    paths: C4Stage1RuntimePaths,
    prepared: C4Stage1PreparedAttempt,
    review_service: C4Stage1ReviewServicePreflightPort,
) -> None:
    verify_c4_stage1_live_review_boundary(
        repository_root=paths.repository_root,
        repository_gate=prepared.repository_gate,
        review_runtime_manifest=prepared.review_runtime_manifest,
        review_service_readiness=prepared.review_service_readiness,
        review_service=review_service,
        expected_completed_review_count=0,
    )


@dataclass(frozen=True, slots=True)
class _C4Stage1RunHooks:
    cold_prepared: Callable[..., C4Stage1PreparedAttemptOutcome] = (
        cold_verify_c4_stage1_prepared_attempt
    )
    capture_repository_gate: Callable[[Path], C4Stage1RepositoryGate] = (
        capture_c4_stage1_repository_gate
    )
    verify_runtime_bindings: Callable[..., None] = (
        verify_c4_stage1_pre_spawn_runtime_bindings
    )
    verify_review_boundary: Callable[..., None] = _verify_live_review_boundary
    controller_factory: ControllerFactory = _default_controller_factory
    runner_factory: RunnerFactory = _default_runner_factory
    finalizer_factory: FinalizerFactory = _default_finalizer_factory
    cold_telemetry: Callable[..., C4Stage1TelemetryFinalizationOutcome] = (
        cold_verify_c4_stage1_telemetry_finalization
    )
    monotonic_ns: Callable[[], int] = time.monotonic_ns


@dataclass(slots=True)
class _WorkerExecution:
    worker: C4Stage1PreparedWorker
    envelope: C4Stage1LaunchEnvelope
    envelope_storage: StoredArtifact | None
    intent: C4Stage1TelemetryIntent
    intent_storage: StoredArtifact
    process_record: ProcessTreeExecutionRecord
    process_storage: StoredArtifact | None
    telemetry_outcome: C4Stage1TelemetryFinalizationOutcome | None
    telemetry_cold_verified: bool
    worker_result: C4Stage1WorkerResult
    worker_result_storage: StoredArtifact | None
    staging_verified: bool
    verified_staging: C4Stage1VerifiedStaging | None = field(repr=False)
    technical_passed: bool
    failure_scope: FailureScope
    failure_codes: tuple[str, ...]
    pending_base_exception: BaseException | None = field(default=None, repr=False)
    direct_output_storage: StoredArtifact | None = None
    staged_output_storage: StoredArtifact | None = None
    published_candidate_receipt: C4Stage1PublishedCandidateReceipt | None = None
    member_publication_receipt: C4Stage1MemberPublicationReceipt | None = None
    member_publication_receipt_storage: StoredArtifact | None = None

    def terminal(self, *, member_publication_completed: bool) -> C4Stage1WorkerTerminal:
        return C4Stage1WorkerTerminal.create(
            worker=self.worker,
            envelope=self.envelope,
            envelope_storage=self.envelope_storage,
            intent=self.intent,
            intent_storage=self.intent_storage,
            process_record=self.process_record,
            process_storage=self.process_storage,
            telemetry_outcome=self.telemetry_outcome,
            telemetry_cold_verified=self.telemetry_cold_verified,
            worker_result=self.worker_result,
            worker_result_storage=self.worker_result_storage,
            staging_verified=self.staging_verified,
            worker_technical_passed=self.technical_passed,
            failure_scope=self.failure_scope,
            failure_codes=self.failure_codes,
            direct_output_storage=self.direct_output_storage,
            staged_output_storage=self.staged_output_storage,
            published_candidate_receipt=self.published_candidate_receipt,
            member_publication_receipt=self.member_publication_receipt,
            member_publication_receipt_storage=(
                self.member_publication_receipt_storage
            ),
            member_publication_completed=member_publication_completed,
        )


def _write_json(
    artifact_store: FileArtifactStore,
    ledger: _InventoryLedger,
    relative_path: str,
    value: object,
) -> StoredArtifact:
    try:
        storage = artifact_store.write_json(
            ledger.run_id,
            relative_path,
            value,
            overwrite=False,
        )
    except BaseException:
        raise
    ledger.add(storage)
    return storage


def _write_bytes(
    artifact_store: FileArtifactStore,
    ledger: _InventoryLedger,
    relative_path: str,
    value: bytes,
) -> StoredArtifact:
    try:
        storage = artifact_store.write_bytes(
            ledger.run_id,
            relative_path,
            value,
            overwrite=False,
        )
    except BaseException:
        raise
    ledger.add(storage)
    return storage


def _fresh_staging_root(
    paths: C4Stage1RuntimePaths,
    prepared: C4Stage1PreparedAttempt,
    worker: C4Stage1PreparedWorker,
) -> tuple[Path, C4Stage1PreparedStagingRoot]:
    parent = verify_c4_stage1_staging_parent(paths.staging_parent)
    name = _sha256_bytes(
        f"{prepared.run_id}:{worker.prepared_worker_id}".encode("utf-8")
    )[:32]
    root = parent / f"c4-stage1-{name}"
    try:
        root.mkdir(mode=0o700, parents=False, exist_ok=False)
    except OSError as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 could not create a fresh worker staging root"
        ) from exc
    return root, prepare_c4_stage1_staging_root(root)


def _request_artifact_path(
    artifact_store: FileArtifactStore,
    prepared: C4Stage1PreparedAttempt,
    worker: C4Stage1PreparedWorker,
) -> Path:
    return artifact_store.artifact_path(
        prepared.run_id,
        _artifact_json_path(
            "worker-request",
            worker.worker_request.worker_request_id,
        ),
    )


def _source_artifact_path(
    artifact_store: FileArtifactStore,
    prepared: C4Stage1PreparedAttempt,
    worker: C4Stage1PreparedWorker,
) -> Path:
    source = worker.worker_request.render_request.source_image
    if source is None:
        raise C4Stage1RunIntegrityError("Stage 1 worker source is missing")
    return artifact_store.artifact_path(prepared.run_id, source.path)


def _snapshot_path(
    paths: C4Stage1RuntimePaths,
    worker: C4Stage1PreparedWorker,
) -> Path:
    return (
        paths.primary_snapshot
        if worker.editor_role == "primary"
        else paths.alternate_snapshot
    )


def _launch_identities(
    prepared: C4Stage1PreparedAttempt,
    worker: C4Stage1PreparedWorker,
    *,
    argv_commitment: str,
    environment_commitment: str,
    working_directory_commitment: str,
) -> tuple[str, str, str, str]:
    request = worker.worker_request
    base = {
        "prepared_attempt_id": prepared.prepared_attempt_id,
        "prepared_attempt_sha256": prepared.prepared_attempt_sha256,
        "repository_gate_id": prepared.repository_gate.repository_gate_id,
        "repository_gate_sha256": prepared.repository_gate.repository_gate_sha256,
        "launch_policy_id": prepared.launch_policy.launch_policy_id,
        "worker_runtime_id": prepared.worker_runtime.worker_runtime_id,
        "prepared_worker_id": worker.prepared_worker_id,
        "prepared_worker_sha256": worker.content_hash(),
        "worker_request_id": request.worker_request_id,
        "worker_request_sha256": request.content_hash(),
        "provider_id": request.editor_spec.provider.provider_id,
        "editor_spec_id": request.editor_spec.spec_id,
        "editor_spec_sha256": request.editor_spec.content_hash(),
        "pipeline_spec_id": _pipeline_spec_id(request),
        "pipeline_spec_sha256": request.editor_spec.pipeline.content_hash(),
        "verified_snapshot_id": request.verified_snapshot.verified_snapshot_id,
        "snapshot_manifest_sha256": request.editor_spec.snapshot_manifest_sha256,
        "source_sha256": request.render_request.source_image.content_sha256,
        "cuda_device": prepared.cuda_device,
    }
    workload_id = content_id("c4_stage1_worker_workload", base)
    command_identity = content_id(
        "c4_stage1_worker_command_exact",
        {**base, "raw_argv_commitment_sha256": argv_commitment},
    )
    working_directory_identity = content_id(
        "c4_stage1_worker_cwd_exact",
        {
            **base,
            "raw_working_directory_commitment_sha256": (working_directory_commitment),
        },
    )
    environment_identity = content_id(
        "c4_stage1_worker_env_exact",
        {
            **base,
            "base_environment_identity": prepared.launch_policy.environment_identity,
            "raw_environment_commitment_sha256": environment_commitment,
        },
    )
    return (
        workload_id,
        command_identity,
        working_directory_identity,
        environment_identity,
    )


def _build_process_request(
    artifact_store: FileArtifactStore,
    prepared: C4Stage1PreparedAttempt,
    prepared_anchor_storage: StoredArtifact,
    worker: C4Stage1PreparedWorker,
    paths: C4Stage1RuntimePaths,
    staging_root: Path,
) -> tuple[BoundedProcessRequest, str, str, str]:
    envelope_path = artifact_store.artifact_path(
        prepared.run_id,
        c4_stage1_launch_envelope_relative_path(worker.prepared_worker_id),
    )
    command = (
        os.fspath(paths.worker_python),
        *prepared.launch_policy.interpreter_isolation_flags,
        os.fspath(paths.repository_root / C4_STAGE1_BOOTSTRAP_SCRIPT_PATH),
        "--launch-envelope",
        os.fspath(envelope_path),
        "--prepared-anchor-storage-id",
        prepared_anchor_storage.storage_id,
        "--request",
        os.fspath(_request_artifact_path(artifact_store, prepared, worker)),
        "--source-png",
        os.fspath(_source_artifact_path(artifact_store, prepared, worker)),
        "--snapshot",
        os.fspath(_snapshot_path(paths, worker)),
        "--staging-root",
        os.fspath(staging_root),
    )
    environment = build_c4_stage1_worker_environment(prepared.launch_policy)
    cuda_uuid = prepared.cuda_device.physical_gpu_uuid
    if (
        cuda_uuid is None
        or environment.get("CUDA_VISIBLE_DEVICES") != cuda_uuid
        or tuple(sorted(environment))
        != tuple(
            sorted(
                {
                    *prepared.launch_policy.inherited_environment_names,
                    *(name for name, _ in prepared.launch_policy.fixed_environment),
                }
                & set(environment)
            )
        )
    ):
        raise C4Stage1RunIntegrityError(
            "Stage 1 child environment differs from the closed CUDA policy"
        )
    argv_commitment = _commit_runtime_value("raw-argv", command)
    environment_commitment = _commit_runtime_value(
        "raw-environment", tuple(sorted(environment.items()))
    )
    cwd_commitment = _commit_runtime_value(
        "raw-working-directory", os.fspath(paths.repository_root)
    )
    workload, command_id, cwd_id, environment_id = _launch_identities(
        prepared,
        worker,
        argv_commitment=argv_commitment,
        environment_commitment=environment_commitment,
        working_directory_commitment=cwd_commitment,
    )
    return (
        BoundedProcessRequest(
            workload_id=workload,
            command_identity=command_id,
            working_directory_identity=cwd_id,
            environment_identity=environment_id,
            command=command,
            working_directory=paths.repository_root,
            environment=environment,
            timeout_seconds=C4_STAGE1_PER_OPTION_HARD_TIMEOUT_SECONDS,
            stdout_limit_bytes=PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
            stderr_limit_bytes=PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
        ),
        argv_commitment,
        environment_commitment,
        cwd_commitment,
    )


def _build_intent(
    prepared: C4Stage1PreparedAttempt,
    worker: C4Stage1PreparedWorker,
    process_request: BoundedProcessRequest,
) -> C4Stage1TelemetryIntent:
    request = worker.worker_request
    source = request.render_request.source_image
    if source is None:
        raise C4Stage1RunIntegrityError("Stage 1 worker source is missing")
    return C4Stage1TelemetryIntent.create(
        run_id=prepared.run_id,
        attempt_id=prepared.attempt_id,
        screen_contract_id=prepared.screen_contract.screen_contract_id,
        screen_contract_sha256=prepared.screen_contract.content_hash(),
        worker_request_id=request.worker_request_id,
        worker_request_sha256=request.content_hash(),
        option_id=worker.option_id,
        provider_slot_id=_provider_slot_id(prepared, worker),
        provider_id=request.editor_spec.provider.provider_id,
        source_artifact_id=source.image_id,
        source_sha256=source.content_sha256,
        snapshot_manifest_id=_snapshot_manifest_id(request),
        snapshot_manifest_sha256=request.editor_spec.snapshot_manifest_sha256,
        pipeline_spec_id=_pipeline_spec_id(request),
        pipeline_spec_sha256=request.editor_spec.pipeline.content_hash(),
        process_request=process_request,
        cuda_device=prepared.cuda_device,
    )


def _record_requires_global_stop(record: ProcessTreeExecutionRecord) -> bool:
    global_codes = {
        "process_containment_close_failure",
        "process_tree_inspection_failure",
        "process_tree_leak",
        "process_tree_termination_failure",
    }
    return bool(
        record.failure_code in global_codes
        or record.process_id is not None
        and (
            not record.containment_closed
            or not record.empty_tree_confirmed
            or record.target_identity_confirmed is not True
        )
    )


def _telemetry_requires_global_stop(
    outcome: C4Stage1TelemetryFinalizationOutcome | None,
    *,
    cold_verified: bool,
) -> bool:
    if outcome is None or not cold_verified or outcome.receipt_storage is None:
        return True
    return any(
        code != "process_execution_failed" for code in outcome.receipt.failure_codes
    )


def _effective_worker_result(
    worker: C4Stage1PreparedWorker,
    *,
    process_record: ProcessTreeExecutionRecord,
    telemetry_outcome: C4Stage1TelemetryFinalizationOutcome | None,
    telemetry_cold_verified: bool,
    verified_staging: C4Stage1VerifiedStaging | None,
) -> tuple[C4Stage1WorkerResult, bool, tuple[str, ...]]:
    failures: list[str] = []
    if process_record.status != "succeeded":
        failures.append("process_execution_failed")
    if (
        telemetry_outcome is None
        or not telemetry_cold_verified
        or not telemetry_outcome.technical_passed
    ):
        failures.append("telemetry_gate_failed")
    if verified_staging is None:
        failures.append("staging_verification_failed")
    elif verified_staging.worker_result.status != "succeeded":
        failures.append(verified_staging.worker_result.failure_code or "worker_failed")
    if not failures and verified_staging is not None:
        return verified_staging.worker_result, True, ()
    if (
        verified_staging is not None
        and verified_staging.worker_result.status == "failed"
    ):
        return verified_staging.worker_result, False, tuple(sorted(set(failures)))
    failure_code = (
        "telemetry_gate_failed"
        if "telemetry_gate_failed" in failures
        else "process_execution_failed"
        if "process_execution_failed" in failures
        else "staging_verification_failed"
    )
    return (
        C4Stage1WorkerResult.failed(
            worker.worker_request,
            failure_code=failure_code,
        ),
        False,
        tuple(sorted(set(failures))),
    )


def _try_finalizer_outcome(
    finalizer: object,
) -> C4Stage1TelemetryFinalizationOutcome | None:
    try:
        value = getattr(finalizer, "outcome")
    except BaseException:
        return None
    return value if isinstance(value, C4Stage1TelemetryFinalizationOutcome) else None


def _unspawned_process_result(
    request: BoundedProcessRequest,
    *,
    containment_closed: bool = True,
) -> BoundedProcessResult:
    """Create canonical terminal evidence when a final pre-spawn guard closes."""

    timestamp = utc_now()
    empty_sha256 = _sha256_bytes(b"")
    empty_output = ProcessOutputSummary(
        byte_count=0,
        captured_byte_count=0,
        sha256=empty_sha256,
        captured_sha256=empty_sha256,
        truncated=False,
        stream_complete=True,
    )
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
        "platform_system": "windows" if os.name == "nt" else "posix",
        "isolation_mode": (
            "windows_job_object_kill_on_close"
            if os.name == "nt"
            else "posix_process_group_non_authoritative"
        ),
        "target_start_token_hash": None,
        "target_process_group_id": None,
        "target_session_id": None,
        "started_at": timestamp,
        "finished_at": timestamp,
        "elapsed_monotonic_seconds": 0.0,
        "workload_elapsed_monotonic_seconds": 0.0,
        "workload_timing_scope": "not_observed_no_release_attempt",
        "process_id": None,
        "workload_released": False,
        "workload_release_status": "not_attempted",
        "exit_code": None,
        "status": "failed",
        "termination_trigger": "not_required",
        "failure_code": "process_start_failure",
        "failure_message": "Bounded process failed closed (process_start_failure)",
        "stdout": empty_output,
        "stderr": empty_output,
        "tree_termination_requested": False,
        "tree_termination_succeeded": None,
        "tree_termination_method": None,
        "tree_inspection_method": None,
        "final_active_processes": None,
        "target_identity_confirmed": None,
        "empty_tree_confirmed": False,
        "containment_closed": containment_closed,
        "observer_callback_failed": False,
        "fallback_used": False,
    }
    record = ProcessTreeExecutionRecord(
        record_id=content_id("process_execution", body),
        **body,
    )
    return BoundedProcessResult(record=record, stdout=b"", stderr=b"")


def _complete_post_intent_failure(
    *,
    artifact_store: FileArtifactStore,
    ledger: _InventoryLedger,
    worker: C4Stage1PreparedWorker,
    envelope: C4Stage1LaunchEnvelope,
    envelope_storage: StoredArtifact | None,
    intent: C4Stage1TelemetryIntent,
    intent_storage: StoredArtifact,
    controller: object,
    finalizer: object,
    hooks: _C4Stage1RunHooks,
    process_result: BoundedProcessResult,
    failure_code: str,
    cause: BaseException,
) -> _WorkerExecution:
    """Best-effort terminal evidence after intent but before a child can spawn."""

    pending_base = cause if not isinstance(cause, Exception) else None
    try:
        telemetry_result = controller.finish_after_runner()  # type: ignore[attr-defined]
    except BaseException as exc:
        telemetry_result = c4_stage1_zero_sample_failure_result(
            "stage1_parent_execution_failure"
        )
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc

    telemetry_outcome: C4Stage1TelemetryFinalizationOutcome | None = None
    telemetry_cold_verified = False
    try:
        telemetry_outcome = finalizer.finalize(  # type: ignore[attr-defined]
            process_execution_record=process_result.record,
            result=telemetry_result,
        )
    except BaseException as exc:
        telemetry_outcome = _try_finalizer_outcome(finalizer)
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc
    if telemetry_outcome is not None:
        ledger.add(telemetry_outcome.samples_storage)
        ledger.add(telemetry_outcome.receipt_storage)
        if telemetry_outcome.receipt_storage is not None:
            try:
                cold = hooks.cold_telemetry(
                    FileArtifactStore(artifact_store.root, create=False),
                    telemetry_outcome.receipt_storage,
                )
                telemetry_cold_verified = cold == telemetry_outcome
            except BaseException as exc:
                if pending_base is None and not isinstance(exc, Exception):
                    pending_base = exc

    process_storage: StoredArtifact | None = None
    try:
        process_storage = _write_json(
            artifact_store,
            ledger,
            _artifact_json_path(
                "process-execution",
                process_result.record.record_id,
            ),
            process_result.record,
        )
    except BaseException as exc:
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc

    worker_result = C4Stage1WorkerResult.failed(
        worker.worker_request,
        failure_code="parent_pre_spawn_failure",
    )
    worker_result_storage: StoredArtifact | None = None
    try:
        worker_result_storage = _write_json(
            artifact_store,
            ledger,
            _artifact_json_path("worker-result", worker_result.worker_result_id),
            worker_result,
        )
    except BaseException as exc:
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc

    failures = {
        "global_integrity_or_safety_failure",
        failure_code,
        "process_execution_failed",
        "staging_verification_failed",
        "telemetry_gate_failed",
    }
    if process_storage is None:
        failures.add("process_record_persistence_failed")
    if worker_result_storage is None:
        failures.add("worker_result_persistence_failed")
    inventory_failure = _recover_transient_post_intent_inventory_failure(
        artifact_store,
        ledger,
    )
    if inventory_failure is not None:
        failures.add("post_intent_inventory_verification_failed")
        if pending_base is None and not isinstance(inventory_failure, Exception):
            pending_base = inventory_failure
    return _WorkerExecution(
        worker=worker,
        envelope=envelope,
        envelope_storage=envelope_storage,
        intent=intent,
        intent_storage=intent_storage,
        process_record=process_result.record,
        process_storage=process_storage,
        telemetry_outcome=telemetry_outcome,
        telemetry_cold_verified=telemetry_cold_verified,
        worker_result=worker_result,
        worker_result_storage=worker_result_storage,
        staging_verified=False,
        verified_staging=None,
        technical_passed=False,
        failure_scope="global",
        failure_codes=tuple(sorted(failures)),
        pending_base_exception=pending_base,
    )


def _execute_worker(
    *,
    artifact_store: FileArtifactStore,
    ledger: _InventoryLedger,
    prepared: C4Stage1PreparedAttempt,
    prepared_anchor_storage: StoredArtifact,
    worker: C4Stage1PreparedWorker,
    paths: C4Stage1RuntimePaths,
    review_service: C4Stage1ReviewServicePreflightPort,
    hooks: _C4Stage1RunHooks,
    member_deadline_ns: int,
) -> _WorkerExecution:
    staging_root, prepared_staging = _fresh_staging_root(paths, prepared, worker)
    process_request, argv_hash, env_hash, cwd_hash = _build_process_request(
        artifact_store,
        prepared,
        prepared_anchor_storage,
        worker,
        paths,
        staging_root,
    )
    intent = _build_intent(prepared, worker, process_request)
    intent_payload = canonical_json_bytes(intent)
    intent_relative_path = f"diagnostics/{intent.intent_id}.telemetry-intent.json"
    predicted_intent_storage = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=prepared.run_id,
            relative_path=intent_relative_path,
            content_sha256=_sha256_bytes(intent_payload),
            size_bytes=len(intent_payload),
        ),
        run_id=prepared.run_id,
        relative_path=intent_relative_path,
        content_sha256=_sha256_bytes(intent_payload),
        size_bytes=len(intent_payload),
    )
    envelope_inventory = tuple(
        sorted(
            (*ledger.snapshot(), predicted_intent_storage),
            key=lambda item: item.relative_path,
        )
    )
    envelope = C4Stage1LaunchEnvelope.create(
        prepared=prepared,
        prepared_anchor_storage=prepared_anchor_storage,
        worker=worker,
        intent=intent,
        intent_storage=predicted_intent_storage,
        process_request=process_request,
        raw_argv_commitment_sha256=argv_hash,
        raw_environment_commitment_sha256=env_hash,
        raw_working_directory_commitment_sha256=cwd_hash,
        artifact_inventory_before_envelope=envelope_inventory,
    )

    if hooks.monotonic_ns() + _OPTION_TIMEOUT_NS > member_deadline_ns:
        raise C4Stage1RunError(
            "Stage 1 member lacks the exact 180-second option budget"
        )
    live_gate = hooks.capture_repository_gate(paths.repository_root)
    if live_gate != prepared.repository_gate:
        raise C4Stage1RunError(
            "Stage 1 live repository gate changed before worker spawn"
        )
    hooks.verify_runtime_bindings(
        paths,
        prepared,
        cuda_device=prepared.cuda_device,
    )
    hooks.verify_review_boundary(paths, prepared, review_service)
    ledger.verify_exact(artifact_store)
    controller = hooks.controller_factory(intent, prepared.cuda_device)
    finalizer = hooks.finalizer_factory(intent, artifact_store)
    runner = hooks.runner_factory(controller, worker, staging_root)
    if hooks.monotonic_ns() + _OPTION_TIMEOUT_NS > member_deadline_ns:
        raise C4Stage1RunError(
            "Stage 1 member lacks the exact 180-second option budget"
        )

    try:
        intent_storage = persist_c4_stage1_telemetry_intent(artifact_store, intent)
    except BaseException as exc:
        try:
            actual = artifact_store.inspect_run_inventory_exact(prepared.run_id)
            recovered = next(
                item for item in actual if item.relative_path == intent_relative_path
            )
        except (Exception, StopIteration):
            raise
        if recovered != predicted_intent_storage:
            raise C4Stage1RunIntegrityError(
                "Stage 1 intent persistence left an untrusted artifact"
            )
        ledger.add(recovered)
        return _complete_post_intent_failure(
            artifact_store=artifact_store,
            ledger=ledger,
            worker=worker,
            envelope=envelope,
            envelope_storage=None,
            intent=intent,
            intent_storage=recovered,
            controller=controller,
            finalizer=finalizer,
            hooks=hooks,
            process_result=_unspawned_process_result(process_request),
            failure_code="intent_persistence_verification_failed",
            cause=exc,
        )
    ledger.add(intent_storage)
    if intent_storage != predicted_intent_storage:
        return _complete_post_intent_failure(
            artifact_store=artifact_store,
            ledger=ledger,
            worker=worker,
            envelope=envelope,
            envelope_storage=None,
            intent=intent,
            intent_storage=intent_storage,
            controller=controller,
            finalizer=finalizer,
            hooks=hooks,
            process_result=_unspawned_process_result(process_request),
            failure_code="intent_storage_descriptor_mismatch",
            cause=C4Stage1RunIntegrityError(
                "Stage 1 intent descriptor differs from its prediction"
            ),
        )
    try:
        envelope_storage = _write_json(
            artifact_store,
            ledger,
            c4_stage1_launch_envelope_relative_path(worker.prepared_worker_id),
            envelope,
        )
    except BaseException as exc:
        return _complete_post_intent_failure(
            artifact_store=artifact_store,
            ledger=ledger,
            worker=worker,
            envelope=envelope,
            envelope_storage=None,
            intent=intent,
            intent_storage=intent_storage,
            controller=controller,
            finalizer=finalizer,
            hooks=hooks,
            process_result=_unspawned_process_result(process_request),
            failure_code="launch_envelope_persistence_failed",
            cause=exc,
        )

    try:
        ledger.verify_exact(artifact_store)
    except BaseException as exc:
        return _complete_post_intent_failure(
            artifact_store=artifact_store,
            ledger=ledger,
            worker=worker,
            envelope=envelope,
            envelope_storage=envelope_storage,
            intent=intent,
            intent_storage=intent_storage,
            controller=controller,
            finalizer=finalizer,
            hooks=hooks,
            process_result=_unspawned_process_result(process_request),
            failure_code="post_intent_inventory_verification_failed",
            cause=exc,
        )
    process_result: BoundedProcessResult
    pending_base: BaseException | None = None
    spawn_authorized = hooks.monotonic_ns() + _OPTION_TIMEOUT_NS <= member_deadline_ns
    if spawn_authorized:
        try:
            spawn_authorized = (
                hooks.capture_repository_gate(paths.repository_root)
                == prepared.repository_gate
            )
            if spawn_authorized:
                hooks.verify_runtime_bindings(
                    paths,
                    prepared,
                    cuda_device=prepared.cuda_device,
                )
        except BaseException as exc:
            spawn_authorized = False
            if not isinstance(exc, Exception):
                pending_base = exc
    try:
        ledger.verify_exact(artifact_store)
    except BaseException as exc:
        return _complete_post_intent_failure(
            artifact_store=artifact_store,
            ledger=ledger,
            worker=worker,
            envelope=envelope,
            envelope_storage=envelope_storage,
            intent=intent,
            intent_storage=intent_storage,
            controller=controller,
            finalizer=finalizer,
            hooks=hooks,
            process_result=_unspawned_process_result(process_request),
            failure_code="post_intent_inventory_verification_failed",
            cause=exc,
        )
    if not spawn_authorized:
        process_result = _unspawned_process_result(process_request)
    else:
        try:
            process_result = runner.run(process_request)
        except BaseException as exc:
            try:
                process_result = runner.last_terminal_result
            except BaseException as terminal_exc:
                return _complete_post_intent_failure(
                    artifact_store=artifact_store,
                    ledger=ledger,
                    worker=worker,
                    envelope=envelope,
                    envelope_storage=envelope_storage,
                    intent=intent,
                    intent_storage=intent_storage,
                    controller=controller,
                    finalizer=finalizer,
                    hooks=hooks,
                    process_result=_unspawned_process_result(
                        process_request,
                        containment_closed=False,
                    ),
                    failure_code="runner_terminal_unavailable",
                    cause=(exc if not isinstance(exc, Exception) else terminal_exc),
                )
            if not isinstance(exc, Exception):
                pending_base = exc
    if not isinstance(process_result, BoundedProcessResult):
        return _complete_post_intent_failure(
            artifact_store=artifact_store,
            ledger=ledger,
            worker=worker,
            envelope=envelope,
            envelope_storage=envelope_storage,
            intent=intent,
            intent_storage=intent_storage,
            controller=controller,
            finalizer=finalizer,
            hooks=hooks,
            process_result=_unspawned_process_result(
                process_request,
                containment_closed=False,
            ),
            failure_code="runner_terminal_invalid",
            cause=C4Stage1RunIntegrityError(
                "Stage 1 runner returned an invalid terminal result"
            ),
        )

    telemetry_result: BackgroundResourceTelemetrySamplerResult
    try:
        telemetry_result = controller.finish_after_runner()  # type: ignore[attr-defined]
    except BaseException as exc:
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc
        telemetry_result = c4_stage1_zero_sample_failure_result(
            "stage1_parent_execution_failure"
        )

    telemetry_outcome: C4Stage1TelemetryFinalizationOutcome | None = None
    telemetry_cold_verified = False
    try:
        telemetry_outcome = finalizer.finalize(  # type: ignore[attr-defined]
            process_execution_record=process_result.record,
            result=telemetry_result,
        )
    except BaseException as exc:
        telemetry_outcome = _try_finalizer_outcome(finalizer)
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc
    if telemetry_outcome is not None:
        ledger.add(telemetry_outcome.samples_storage)
        ledger.add(telemetry_outcome.receipt_storage)
        if telemetry_outcome.receipt_storage is not None:
            try:
                cold = hooks.cold_telemetry(
                    FileArtifactStore(artifact_store.root, create=False),
                    telemetry_outcome.receipt_storage,
                )
                telemetry_cold_verified = cold == telemetry_outcome
            except BaseException as exc:
                if pending_base is None and not isinstance(exc, Exception):
                    pending_base = exc

    process_storage: StoredArtifact | None = None
    try:
        process_storage = _write_json(
            artifact_store,
            ledger,
            _artifact_json_path("process-execution", process_result.record.record_id),
            process_result.record,
        )
    except BaseException as exc:
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc

    verified_staging: C4Stage1VerifiedStaging | None = None
    try:
        verified_staging = verify_c4_stage1_staging(
            prepared_staging,
            worker.worker_request,
        )
    except BaseException as exc:
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc

    worker_result, technical, failures = _effective_worker_result(
        worker,
        process_record=process_result.record,
        telemetry_outcome=telemetry_outcome,
        telemetry_cold_verified=telemetry_cold_verified,
        verified_staging=verified_staging,
    )
    worker_result_storage: StoredArtifact | None = None
    try:
        worker_result_storage = _write_json(
            artifact_store,
            ledger,
            _artifact_json_path("worker-result", worker_result.worker_result_id),
            worker_result,
        )
    except BaseException as exc:
        technical = False
        failures = tuple(sorted({*failures, "worker_result_persistence_failed"}))
        if pending_base is None and not isinstance(exc, Exception):
            pending_base = exc
    if process_storage is None:
        failures = tuple(sorted({*failures, "process_record_persistence_failed"}))

    global_stop = bool(
        pending_base is not None
        or process_storage is None
        or worker_result_storage is None
        or _record_requires_global_stop(process_result.record)
        or _telemetry_requires_global_stop(
            telemetry_outcome,
            cold_verified=telemetry_cold_verified,
        )
    )
    if global_stop:
        technical = False
        failures = tuple(sorted({*failures, "global_integrity_or_safety_failure"}))
    inventory_failure = _recover_transient_post_intent_inventory_failure(
        artifact_store,
        ledger,
    )
    if inventory_failure is not None:
        technical = False
        failures = tuple(
            sorted(
                {
                    *failures,
                    "global_integrity_or_safety_failure",
                    "post_intent_inventory_verification_failed",
                }
            )
        )
        if pending_base is None and not isinstance(inventory_failure, Exception):
            pending_base = inventory_failure
        global_stop = True
    return _WorkerExecution(
        worker=worker,
        envelope=envelope,
        envelope_storage=envelope_storage,
        intent=intent,
        intent_storage=intent_storage,
        process_record=process_result.record,
        process_storage=process_storage,
        telemetry_outcome=telemetry_outcome,
        telemetry_cold_verified=telemetry_cold_verified,
        worker_result=worker_result,
        worker_result_storage=worker_result_storage,
        staging_verified=verified_staging is not None,
        verified_staging=verified_staging,
        technical_passed=technical and not global_stop,
        failure_scope=("global" if global_stop else "none" if technical else "family"),
        failure_codes=failures,
        pending_base_exception=pending_base,
    )


def _publish_member(
    artifact_store: FileArtifactStore,
    ledger: _InventoryLedger,
    prepared: C4Stage1PreparedAttempt,
    executions: list[_WorkerExecution],
) -> None:
    ledger.verify_exact(artifact_store)
    for execution in executions:
        verified = execution.verified_staging
        if (
            not execution.technical_passed
            or verified is None
            or verified.direct_png is None
            or verified.staged_png is None
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 member publication lacks two verified outputs"
            )
    for execution in executions:
        verified = execution.verified_staging
        assert verified is not None and verified.direct_png is not None
        execution.direct_output_storage = _write_bytes(
            artifact_store,
            ledger,
            f"diagnostics/{execution.worker.worker_request.worker_request_id}.direct.png",
            verified.direct_png,
        )
    for execution in executions:
        verified = execution.verified_staging
        assert verified is not None and verified.staged_png is not None
        execution.staged_output_storage = _write_bytes(
            artifact_store,
            ledger,
            f"emocio/images/{execution.worker.worker_request.worker_request_id}.png",
            verified.staged_png,
        )
    if len(executions) != 2:
        raise C4Stage1RunIntegrityError(
            "Stage 1 member publication requires exactly two options"
        )
    receipt = C4Stage1MemberPublicationReceipt.create(
        prepared=prepared,
        executions=(executions[0], executions[1]),
        artifact_inventory_before_receipt=ledger.snapshot(),
    )
    receipt_storage = _write_json(
        artifact_store,
        ledger,
        _artifact_json_path(
            "member-publication",
            receipt.member_publication_receipt_id,
        ),
        receipt,
    )
    for execution, candidate in zip(
        executions,
        receipt.candidate_receipts,
        strict=True,
    ):
        execution.published_candidate_receipt = candidate
        execution.member_publication_receipt = receipt
        execution.member_publication_receipt_storage = receipt_storage
    ledger.verify_exact(artifact_store)


def _member_from_executions(
    *,
    prepared: C4Stage1PreparedAttempt,
    editor_role: Literal["primary", "alternate"],
    executions: list[_WorkerExecution],
    elapsed_seconds: float,
    member_failure_codes: tuple[str, ...],
    not_started: bool = False,
) -> C4Stage1MemberRun:
    worker = prepared.workers[0 if editor_role == "primary" else 2]
    terminals = tuple(
        item.terminal(
            member_publication_completed=(
                item.direct_output_storage is not None
                and item.staged_output_storage is not None
                and item.published_candidate_receipt is not None
                and item.member_publication_receipt is not None
                and item.member_publication_receipt_storage is not None
                and len(executions) == 2
                and all(execution.technical_passed for execution in executions)
            )
        )
        for item in executions
    )
    succeeded = bool(
        len(executions) == 2
        and elapsed_seconds <= C4_STAGE1_MEMBER_TIMEOUT_SECONDS
        and all(item.technical_passed for item in executions)
        and all(
            item.direct_output_storage is not None
            and item.staged_output_storage is not None
            and item.published_candidate_receipt is not None
            and item.member_publication_receipt is not None
            and item.member_publication_receipt_storage is not None
            for item in executions
        )
    )
    status: MemberStatus = (
        "not_started" if not_started else "succeeded" if succeeded else "failed"
    )
    failures = tuple(
        sorted(
            {
                *member_failure_codes,
                *(code for item in executions for code in item.failure_codes),
            }
        )
    )
    if status != "succeeded" and not failures:
        failures = ("member_not_completed",)
    return C4Stage1MemberRun.create(
        editor_role=editor_role,
        provider_slot_id=_provider_slot_id(prepared, worker),
        status=status,
        worker_terminals=terminals,
        elapsed_monotonic_seconds=elapsed_seconds,
        failure_codes=failures,
    )


def _persist_final_attempt(
    *,
    artifact_store: FileArtifactStore,
    ledger: _InventoryLedger,
    prepared: C4Stage1PreparedAttempt,
    prepared_anchor_storage: StoredArtifact,
    member_runs: tuple[C4Stage1MemberRun, C4Stage1MemberRun],
    global_stop_triggered: bool,
) -> C4Stage1RunOutcome:
    ledger.verify_exact(artifact_store)
    failures = tuple(
        sorted(
            {
                *(code for member in member_runs for code in member.failure_codes),
                *(("global_stop_triggered",) if global_stop_triggered else ()),
            }
        )
    )
    manifest = C4Stage1RenderAttemptManifest.create(
        prepared=prepared,
        prepared_anchor_storage=prepared_anchor_storage,
        member_runs=member_runs,
        global_stop_triggered=global_stop_triggered,
        failure_codes=failures,
        artifact_inventory_before_manifest=ledger.snapshot(),
    )
    manifest_storage = _write_json(
        artifact_store,
        ledger,
        C4_STAGE1_ATTEMPT_MANIFEST_PATH,
        manifest,
    )
    anchor = C4Stage1RenderInventoryAnchor.create(
        manifest,
        manifest_storage,
        artifact_inventory_before_anchor=ledger.snapshot(),
    )
    anchor_storage = _write_json(
        artifact_store,
        ledger,
        C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH,
        anchor,
    )
    return cold_verify_c4_stage1_run(
        FileArtifactStore(artifact_store.root, create=False),
        anchor_storage,
    )


def run_c4_stage1_attempt(
    *,
    artifact_store: FileArtifactStore,
    prepared_anchor_storage: StoredArtifact,
    confirmed_prepared_attempt_id: str,
    paths: C4Stage1RuntimePaths,
    review_service: C4Stage1ReviewServicePreflightPort,
) -> C4Stage1RunOutcome:
    """Execute the production parent path with no injectable runner/probe seam."""

    return _run_c4_stage1_attempt(
        artifact_store=artifact_store,
        prepared_anchor_storage=prepared_anchor_storage,
        confirmed_prepared_attempt_id=confirmed_prepared_attempt_id,
        paths=paths,
        review_service=review_service,
        hooks=_C4Stage1RunHooks(),
    )


def _run_c4_stage1_attempt(
    *,
    artifact_store: FileArtifactStore,
    prepared_anchor_storage: StoredArtifact,
    confirmed_prepared_attempt_id: str,
    paths: C4Stage1RuntimePaths,
    review_service: C4Stage1ReviewServicePreflightPort,
    hooks: _C4Stage1RunHooks,
) -> C4Stage1RunOutcome:
    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("Stage 1 run requires FileArtifactStore")
    if not isinstance(paths, C4Stage1RuntimePaths):
        raise TypeError("Stage 1 run requires exact runtime paths")
    cold_store = FileArtifactStore(artifact_store.root, create=False)
    prepared_outcome = hooks.cold_prepared(
        cold_store,
        prepared_anchor_storage,
        require_exact_pre_spawn_inventory=True,
    )
    prepared = prepared_outcome.prepared_attempt
    if (
        type(confirmed_prepared_attempt_id) is not str
        or confirmed_prepared_attempt_id != prepared.prepared_attempt_id
    ):
        raise C4Stage1ConfirmationError(
            "Stage 1 requires exact prepared_attempt_id confirmation"
        )
    ledger = _InventoryLedger.from_prepared(prepared_outcome)
    ledger.verify_exact(artifact_store)
    hooks.verify_review_boundary(paths, prepared, review_service)

    member_runs: list[C4Stage1MemberRun] = []
    global_stop = False
    pending_base: BaseException | None = None
    family_specs = (
        ("primary", prepared.workers[:2]),
        ("alternate", prepared.workers[2:]),
    )
    for role, workers in family_specs:
        editor_role: Literal["primary", "alternate"] = role
        if global_stop:
            member_runs.append(
                _member_from_executions(
                    prepared=prepared,
                    editor_role=editor_role,
                    executions=[],
                    elapsed_seconds=0.0,
                    member_failure_codes=("global_stop_before_member",),
                    not_started=True,
                )
            )
            continue
        started_ns = hooks.monotonic_ns()
        deadline_ns = started_ns + _MEMBER_TIMEOUT_NS
        executions: list[_WorkerExecution] = []
        member_failures: list[str] = []
        for option_index, worker in enumerate(workers):
            if (
                option_index == 1
                and hooks.monotonic_ns() + _OPTION_TIMEOUT_NS > deadline_ns
            ):
                member_failures.append("insufficient_member_time_for_second_option")
                break
            try:
                execution = _execute_worker(
                    artifact_store=artifact_store,
                    ledger=ledger,
                    prepared=prepared,
                    prepared_anchor_storage=prepared_outcome.prepared_anchor_storage,
                    worker=worker,
                    paths=paths,
                    review_service=review_service,
                    hooks=hooks,
                    member_deadline_ns=deadline_ns,
                )
            except C4Stage1RunIntegrityError:
                raise
            except BaseException as exc:
                if not isinstance(exc, Exception):
                    pending_base = exc
                member_failures.append("pre_spawn_or_parent_failure")
                global_stop = True
                break
            executions.append(execution)
            if execution.pending_base_exception is not None and pending_base is None:
                pending_base = execution.pending_base_exception
            if execution.failure_scope == "global":
                global_stop = True
            if not execution.technical_passed:
                break

        elapsed = max(0, hooks.monotonic_ns() - started_ns) / 1_000_000_000
        if (
            len(executions) == 2
            and all(item.technical_passed for item in executions)
            and elapsed <= C4_STAGE1_MEMBER_TIMEOUT_SECONDS
            and not global_stop
        ):
            try:
                _publish_member(artifact_store, ledger, prepared, executions)
            except C4Stage1RunIntegrityError:
                raise
            except BaseException as exc:
                member_failures.append("member_publication_failed")
                global_stop = True
                if pending_base is None and not isinstance(exc, Exception):
                    pending_base = exc
        elif len(executions) == 2 and elapsed > C4_STAGE1_MEMBER_TIMEOUT_SECONDS:
            member_failures.append("member_timeout_exceeded")

        member_runs.append(
            _member_from_executions(
                prepared=prepared,
                editor_role=editor_role,
                executions=executions,
                elapsed_seconds=elapsed,
                member_failure_codes=tuple(member_failures),
            )
        )

    if len(member_runs) != 2:
        raise C4Stage1RunIntegrityError("Stage 1 member accounting is incomplete")
    outcome = _persist_final_attempt(
        artifact_store=artifact_store,
        ledger=ledger,
        prepared=prepared,
        prepared_anchor_storage=prepared_outcome.prepared_anchor_storage,
        member_runs=(member_runs[0], member_runs[1]),
        global_stop_triggered=global_stop,
    )
    if pending_base is not None:
        raise pending_base
    return outcome


def cold_verify_c4_stage1_launch_envelope(
    artifact_store: FileArtifactStore,
    envelope_storage: StoredArtifact,
    prepared: C4Stage1PreparedAttempt,
    *,
    require_exact_launch_inventory: bool = True,
) -> C4Stage1LaunchEnvelope:
    """Cold-parse one envelope and its intent against the prepared attempt."""

    if type(require_exact_launch_inventory) is not bool:
        raise TypeError("Stage 1 launch inventory selector must be a boolean")
    storage = StoredArtifact.model_validate(
        envelope_storage.model_dump(mode="python", round_trip=True)
    )
    try:
        payload = artifact_store.read_bytes(storage.storage_id)
        envelope = C4Stage1LaunchEnvelope.model_validate_json(payload)
        actual_inventory = artifact_store.inspect_run_inventory_exact(prepared.run_id)
    except Exception as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 launch envelope failed cold verification"
        ) from exc
    workers = tuple(
        worker
        for worker in prepared.workers
        if worker.prepared_worker_id == envelope.prepared_worker_id
    )
    if len(workers) != 1:
        raise C4Stage1RunIntegrityError(
            "Stage 1 launch envelope does not select one prepared worker"
        )
    worker = workers[0]
    request = worker.worker_request
    source = request.render_request.source_image
    if source is None:
        raise C4Stage1RunIntegrityError(
            "Stage 1 launch envelope prepared source is missing"
        )
    actual_by_path = {item.relative_path: item for item in actual_inventory}
    expected_path = c4_stage1_launch_envelope_relative_path(worker.prepared_worker_id)
    expected_workload, expected_command, expected_cwd, expected_environment = (
        _launch_identities(
            prepared,
            worker,
            argv_commitment=envelope.raw_argv_commitment_sha256,
            environment_commitment=envelope.raw_environment_commitment_sha256,
            working_directory_commitment=(
                envelope.raw_working_directory_commitment_sha256
            ),
        )
    )
    if (
        canonical_json_bytes(envelope) != payload
        or storage.run_id != prepared.run_id
        or storage.relative_path != expected_path
        or storage.content_sha256 != _sha256_bytes(payload)
        or storage.size_bytes != len(payload)
        or actual_by_path.get(storage.relative_path) != storage
        or envelope.prepared_attempt_id != prepared.prepared_attempt_id
        or envelope.prepared_attempt_sha256 != prepared.prepared_attempt_sha256
        or envelope.confirmed_prepared_attempt_id != prepared.prepared_attempt_id
        or envelope.prepared_anchor_storage.relative_path
        != C4_STAGE1_PREPARED_ANCHOR_PATH
        or actual_by_path.get(C4_STAGE1_PREPARED_ANCHOR_PATH)
        != envelope.prepared_anchor_storage
        or envelope.repository_gate_id != prepared.repository_gate.repository_gate_id
        or envelope.repository_gate_sha256
        != prepared.repository_gate.repository_gate_sha256
        or envelope.launch_policy_id != prepared.launch_policy.launch_policy_id
        or envelope.launch_policy_sha256 != prepared.launch_policy.launch_policy_sha256
        or envelope.worker_runtime_id != prepared.worker_runtime.worker_runtime_id
        or envelope.worker_runtime_sha256
        != prepared.worker_runtime.worker_runtime_sha256
        or envelope.bootstrap_script_sha256
        != prepared.launch_policy.bootstrap_script_sha256
        or envelope.bootstrap_script_size_bytes
        != prepared.launch_policy.bootstrap_script_size_bytes
        or envelope.worker_script_sha256 != prepared.launch_policy.worker_script_sha256
        or envelope.worker_script_size_bytes
        != prepared.launch_policy.worker_script_size_bytes
        or envelope.interpreter_isolation_flags
        != prepared.launch_policy.interpreter_isolation_flags
        or envelope.prepared_worker_sha256 != worker.content_hash()
        or envelope.worker_request_id != request.worker_request_id
        or envelope.worker_request_sha256 != request.content_hash()
        or envelope.editor_role != worker.editor_role
        or envelope.option_id != worker.option_id
        or envelope.provider_slot_id != _provider_slot_id(prepared, worker)
        or envelope.provider_id != request.editor_spec.provider.provider_id
        or envelope.editor_spec_id != request.editor_spec.spec_id
        or envelope.editor_spec_sha256 != request.editor_spec.content_hash()
        or envelope.pipeline_spec_id != _pipeline_spec_id(request)
        or envelope.pipeline_spec_sha256 != request.editor_spec.pipeline.content_hash()
        or envelope.verified_snapshot_id
        != request.verified_snapshot.verified_snapshot_id
        or envelope.snapshot_manifest_id != _snapshot_manifest_id(request)
        or envelope.snapshot_manifest_sha256
        != request.editor_spec.snapshot_manifest_sha256
        or envelope.source_artifact_id != source.image_id
        or envelope.source_sha256 != source.content_sha256
        or envelope.source_provenance_sha256 != prepared.source_provenance_sha256
        or envelope.cuda_device != prepared.cuda_device
        or envelope.workload_id != expected_workload
        or envelope.command_identity != expected_command
        or envelope.working_directory_identity != expected_cwd
        or envelope.environment_identity != expected_environment
        or envelope.argument_count != 15
        or envelope.process_request.workload_id != expected_workload
        or envelope.process_request.command_identity != expected_command
        or envelope.process_request.working_directory_identity != expected_cwd
        or envelope.process_request.environment_identity != expected_environment
        or envelope.process_request.argument_count != 15
        or envelope.process_request.timeout_seconds
        != C4_STAGE1_PER_OPTION_HARD_TIMEOUT_SECONDS
        or envelope.process_request.stdout_limit_bytes
        != PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES
        or envelope.process_request.stderr_limit_bytes
        != PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES
        or any(
            item.run_id != prepared.run_id
            or actual_by_path.get(item.relative_path) != item
            for item in envelope.artifact_inventory_before_envelope
        )
        or storage in envelope.artifact_inventory_before_envelope
        or require_exact_launch_inventory
        and actual_inventory
        != tuple(
            sorted(
                (*envelope.artifact_inventory_before_envelope, storage),
                key=lambda item: item.relative_path,
            )
        )
    ):
        raise C4Stage1RunIntegrityError(
            "Stage 1 launch envelope differs from prepared lineage"
        )
    try:
        prepared_bytes = artifact_store.read_bytes(
            envelope.prepared_anchor_storage.storage_id
        )
        request_path = _artifact_json_path(
            "worker-request",
            request.worker_request_id,
        )
        request_storage = actual_by_path[request_path]
        request_bytes = artifact_store.read_bytes(request_storage.storage_id)
        cold_request = C4Stage1WorkerRequest.model_validate_json(request_bytes)
        source_storage = actual_by_path[source.path]
        source_bytes = artifact_store.read_bytes(source_storage.storage_id)
        intent_bytes = artifact_store.read_bytes(
            envelope.telemetry_intent_storage.storage_id
        )
        intent = C4Stage1TelemetryIntent.model_validate_json(intent_bytes)
    except Exception as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 launch envelope intent failed cold verification"
        ) from exc
    if (
        canonical_json_bytes(prepared) != prepared_bytes
        or envelope.prepared_anchor_storage.content_sha256
        != _sha256_bytes(prepared_bytes)
        or envelope.prepared_anchor_storage.size_bytes != len(prepared_bytes)
        or canonical_json_bytes(cold_request) != request_bytes
        or cold_request != request
        or request_storage not in envelope.artifact_inventory_before_envelope
        or request_storage.content_sha256 != _sha256_bytes(request_bytes)
        or request_storage.size_bytes != len(request_bytes)
        or source_storage not in envelope.artifact_inventory_before_envelope
        or source_storage.content_sha256 != _sha256_bytes(source_bytes)
        or source_storage.size_bytes != len(source_bytes)
        or _sha256_bytes(source_bytes) != source.content_sha256
        or canonical_json_bytes(intent) != intent_bytes
        or actual_by_path.get(envelope.telemetry_intent_storage.relative_path)
        != envelope.telemetry_intent_storage
        or envelope.telemetry_intent_storage.content_sha256
        != _sha256_bytes(intent_bytes)
        or envelope.telemetry_intent_storage.size_bytes != len(intent_bytes)
        or intent.intent_id != envelope.telemetry_intent_id
        or intent.intent_sha256 != envelope.telemetry_intent_sha256
        or intent.run_id != prepared.run_id
        or intent.attempt_id != prepared.attempt_id
        or intent.screen_contract_id != prepared.screen_contract.screen_contract_id
        or intent.screen_contract_sha256 != prepared.screen_contract.content_hash()
        or intent.worker_request_id != envelope.worker_request_id
        or intent.worker_request_sha256 != envelope.worker_request_sha256
        or intent.option_id != worker.option_id
        or intent.provider_slot_id != envelope.provider_slot_id
        or intent.provider_id != envelope.provider_id
        or intent.source_artifact_id != envelope.source_artifact_id
        or intent.source_sha256 != envelope.source_sha256
        or intent.snapshot_manifest_id != envelope.snapshot_manifest_id
        or intent.snapshot_manifest_sha256 != envelope.snapshot_manifest_sha256
        or intent.pipeline_spec_id != envelope.pipeline_spec_id
        or intent.pipeline_spec_sha256 != envelope.pipeline_spec_sha256
        or intent.cuda_device != prepared.cuda_device
        or intent.process_request != envelope.process_request
    ):
        raise C4Stage1RunIntegrityError(
            "Stage 1 launch envelope intent lineage is invalid"
        )
    return envelope


def cold_verify_c4_stage1_member_publication(
    artifact_store: FileArtifactStore,
    receipt_storage: StoredArtifact,
    prepared: C4Stage1PreparedAttempt,
) -> C4Stage1MemberPublicationReceipt:
    """Cold-verify one atomic family commit without requiring the final anchor."""

    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("Stage 1 member publication requires FileArtifactStore")
    storage = StoredArtifact.model_validate(
        receipt_storage.model_dump(mode="python", round_trip=True)
    )
    try:
        payload = artifact_store.read_bytes(storage.storage_id)
        receipt = C4Stage1MemberPublicationReceipt.model_validate_json(payload)
        actual_inventory = artifact_store.inspect_run_inventory_exact(prepared.run_id)
    except Exception as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 member publication receipt failed cold parsing"
        ) from exc
    expected_path = _artifact_json_path(
        "member-publication",
        receipt.member_publication_receipt_id,
    )
    actual_by_path = {item.relative_path: item for item in actual_inventory}
    if (
        canonical_json_bytes(receipt) != payload
        or storage.run_id != prepared.run_id
        or storage.relative_path != expected_path
        or storage.content_sha256 != _sha256_bytes(payload)
        or storage.size_bytes != len(payload)
        or actual_by_path.get(storage.relative_path) != storage
        or receipt.prepared_attempt_id != prepared.prepared_attempt_id
        or receipt.prepared_attempt_sha256 != prepared.prepared_attempt_sha256
        or storage in receipt.artifact_inventory_before_receipt
        or any(
            item.run_id != prepared.run_id
            or actual_by_path.get(item.relative_path) != item
            for item in receipt.artifact_inventory_before_receipt
        )
    ):
        raise C4Stage1RunIntegrityError(
            "Stage 1 member publication descriptor or prepared lineage is invalid"
        )

    for candidate in receipt.candidate_receipts:
        matches = tuple(
            worker
            for worker in prepared.workers
            if worker.prepared_worker_id == candidate.prepared_worker_id
        )
        if len(matches) != 1:
            raise C4Stage1RunIntegrityError(
                "Stage 1 publication candidate selects no unique prepared worker"
            )
        worker = matches[0]
        request = worker.worker_request
        support = (
            candidate.launch_envelope_storage,
            candidate.process_execution_storage,
            candidate.telemetry_finalization_storage,
            candidate.worker_result_storage,
            candidate.direct_output_storage,
            candidate.staged_output_storage,
        )
        if (
            candidate.prepared_worker_sha256 != worker.content_hash()
            or candidate.worker_request_id != request.worker_request_id
            or candidate.worker_request_sha256 != request.content_hash()
            or candidate.editor_role != worker.editor_role
            or candidate.option_id != worker.option_id
            or candidate.provider_slot_id != _provider_slot_id(prepared, worker)
            or candidate.provider_id != request.editor_spec.provider.provider_id
            or any(
                item not in receipt.artifact_inventory_before_receipt
                or actual_by_path.get(item.relative_path) != item
                for item in support
            )
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 publication candidate differs from prepared lineage"
            )
        envelope = cold_verify_c4_stage1_launch_envelope(
            artifact_store,
            candidate.launch_envelope_storage,
            prepared,
            require_exact_launch_inventory=False,
        )
        if (
            envelope.launch_envelope_id != candidate.launch_envelope_id
            or envelope.launch_envelope_sha256 != candidate.launch_envelope_sha256
            or envelope.prepared_worker_id != worker.prepared_worker_id
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 publication candidate cites another launch envelope"
            )
        intent = _cold_verify_terminal_intent(
            artifact_store,
            envelope.telemetry_intent_storage,
            prepared=prepared,
            worker=worker,
            actual_by_path=actual_by_path,
        )
        if (
            intent.intent_id != envelope.telemetry_intent_id
            or intent.intent_sha256 != envelope.telemetry_intent_sha256
            or intent.process_request != envelope.process_request
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 publication candidate intent differs from its envelope"
            )
        try:
            process_bytes = artifact_store.read_bytes(
                candidate.process_execution_storage.storage_id
            )
            process = ProcessTreeExecutionRecord.model_validate_json(process_bytes)
            worker_result_bytes = artifact_store.read_bytes(
                candidate.worker_result_storage.storage_id
            )
            worker_result = C4Stage1WorkerResult.model_validate_json(
                worker_result_bytes
            )
            direct = artifact_store.read_bytes(
                candidate.direct_output_storage.storage_id
            )
            staged = artifact_store.read_bytes(
                candidate.staged_output_storage.storage_id
            )
            telemetry = cold_verify_c4_stage1_telemetry_finalization(
                artifact_store,
                candidate.telemetry_finalization_storage,
            )
            worker_result.validate_against(request)
        except Exception as exc:
            raise C4Stage1RunIntegrityError(
                "Stage 1 publication candidate evidence failed cold parsing"
            ) from exc
        evidence = worker_result.image_evidence
        if (
            canonical_json_bytes(process) != process_bytes
            or candidate.process_execution_storage.content_sha256
            != _sha256_bytes(process_bytes)
            or candidate.process_execution_storage.size_bytes != len(process_bytes)
            or process.record_id != candidate.process_execution_record_id
            or _canonical_sha256(process) != candidate.process_execution_record_sha256
            or process.status != "succeeded"
            or process.workload_id != envelope.workload_id
            or process.command_identity != envelope.command_identity
            or process.working_directory_identity != envelope.working_directory_identity
            or process.environment_identity != envelope.environment_identity
            or canonical_json_bytes(worker_result) != worker_result_bytes
            or candidate.worker_result_storage.content_sha256
            != _sha256_bytes(worker_result_bytes)
            or candidate.worker_result_storage.size_bytes != len(worker_result_bytes)
            or worker_result.worker_result_id != candidate.worker_result_id
            or _canonical_sha256(worker_result) != candidate.worker_result_sha256
            or worker_result.status != "succeeded"
            or worker_result.worker_request_id != request.worker_request_id
            or worker_result.worker_request_hash != request.content_hash()
            or evidence is None
            or evidence.image_evidence_id != candidate.image_evidence_id
            or _canonical_sha256(evidence) != candidate.image_evidence_sha256
            or telemetry.receipt.finalization_receipt_id
            != candidate.telemetry_finalization_receipt_id
            or telemetry.receipt.finalization_receipt_sha256
            != candidate.telemetry_finalization_receipt_sha256
            or telemetry.receipt.intent != intent
            or not telemetry.technical_passed
            or telemetry.receipt.process_execution_record != process
            or _sha256_bytes(direct) != candidate.direct_png_sha256
            or len(direct) != candidate.direct_png_size_bytes
            or inspect_c4_stage1_png_bytes(direct)
            != (candidate.direct_width, candidate.direct_height)
            or _sha256_bytes(staged) != candidate.staged_png_sha256
            or len(staged) != candidate.staged_png_size_bytes
            or inspect_c4_stage1_png_bytes(staged)
            != (candidate.staged_width, candidate.staged_height)
            or candidate.direct_png_sha256 != evidence.direct_png_sha256
            or candidate.direct_png_size_bytes != evidence.direct_png_size_bytes
            or candidate.direct_width != evidence.direct_width
            or candidate.direct_height != evidence.direct_height
            or candidate.staged_png_sha256 != evidence.staged_png_sha256
            or candidate.staged_png_size_bytes != evidence.staged_png_size_bytes
            or candidate.staged_width != evidence.staged_width
            or candidate.staged_height != evidence.staged_height
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 publication candidate bytes or terminal lineage is invalid"
            )
    return receipt


def _cold_verify_terminal_intent(
    artifact_store: FileArtifactStore,
    storage: StoredArtifact,
    *,
    prepared: C4Stage1PreparedAttempt,
    worker: C4Stage1PreparedWorker,
    actual_by_path: dict[str, StoredArtifact],
) -> C4Stage1TelemetryIntent:
    request = worker.worker_request
    source = request.render_request.source_image
    if source is None:
        raise C4Stage1RunIntegrityError(
            "Stage 1 terminal prepared request has no source"
        )
    try:
        payload = artifact_store.read_bytes(storage.storage_id)
        intent = C4Stage1TelemetryIntent.model_validate_json(payload)
    except Exception as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 terminal intent failed cold parsing"
        ) from exc
    if (
        canonical_json_bytes(intent) != payload
        or storage.run_id != prepared.run_id
        or storage.relative_path
        != f"diagnostics/{intent.intent_id}.telemetry-intent.json"
        or storage.content_sha256 != _sha256_bytes(payload)
        or storage.size_bytes != len(payload)
        or actual_by_path.get(storage.relative_path) != storage
        or intent.run_id != prepared.run_id
        or intent.attempt_id != prepared.attempt_id
        or intent.screen_contract_id != prepared.screen_contract.screen_contract_id
        or intent.screen_contract_sha256 != prepared.screen_contract.content_hash()
        or intent.worker_request_id != request.worker_request_id
        or intent.worker_request_sha256 != request.content_hash()
        or intent.option_id != worker.option_id
        or intent.provider_slot_id != _provider_slot_id(prepared, worker)
        or intent.provider_id != request.editor_spec.provider.provider_id
        or intent.source_artifact_id != source.image_id
        or intent.source_sha256 != source.content_sha256
        or intent.snapshot_manifest_id != _snapshot_manifest_id(request)
        or intent.snapshot_manifest_sha256
        != request.editor_spec.snapshot_manifest_sha256
        or intent.pipeline_spec_id != _pipeline_spec_id(request)
        or intent.pipeline_spec_sha256 != request.editor_spec.pipeline.content_hash()
        or intent.cuda_device != prepared.cuda_device
    ):
        raise C4Stage1RunIntegrityError(
            "Stage 1 terminal intent differs from its prepared worker"
        )
    return intent


def _process_matches_commitment(
    process: ProcessTreeExecutionRecord,
    commitment: C4Stage1ProcessRequestCommitment,
) -> bool:
    return bool(
        process.workload_id == commitment.workload_id
        and process.command_identity == commitment.command_identity
        and process.argument_count == commitment.argument_count
        and process.working_directory_identity == commitment.working_directory_identity
        and process.environment_identity == commitment.environment_identity
        and process.timeout_seconds == commitment.timeout_seconds
        and process.stdout_limit_bytes == commitment.stdout_limit_bytes
        and process.stderr_limit_bytes == commitment.stderr_limit_bytes
    )


def cold_verify_c4_stage1_run(
    artifact_store: FileArtifactStore,
    inventory_anchor_storage: StoredArtifact,
) -> C4Stage1RunOutcome:
    """Restart-safe verification of the final manifest and exact run inventory."""

    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("Stage 1 cold run verification requires FileArtifactStore")
    anchor_storage = StoredArtifact.model_validate(
        inventory_anchor_storage.model_dump(mode="python", round_trip=True)
    )
    try:
        anchor_bytes = artifact_store.read_bytes(anchor_storage.storage_id)
        anchor = C4Stage1RenderInventoryAnchor.model_validate_json(anchor_bytes)
        manifest_bytes = artifact_store.read_bytes(
            anchor.render_attempt_manifest_storage.storage_id
        )
        manifest = C4Stage1RenderAttemptManifest.model_validate_json(manifest_bytes)
    except Exception as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 final render artifacts failed cold parsing"
        ) from exc
    if (
        canonical_json_bytes(anchor) != anchor_bytes
        or anchor_storage.relative_path != C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH
        or anchor_storage.run_id != anchor.run_id
        or anchor_storage.content_sha256 != _sha256_bytes(anchor_bytes)
        or anchor_storage.size_bytes != len(anchor_bytes)
        or canonical_json_bytes(manifest) != manifest_bytes
        or manifest.render_attempt_manifest_id != anchor.render_attempt_manifest_id
        or manifest.render_attempt_manifest_sha256
        != anchor.render_attempt_manifest_sha256
        or anchor.render_attempt_manifest_storage.relative_path
        != C4_STAGE1_ATTEMPT_MANIFEST_PATH
        or anchor.render_attempt_manifest_storage.content_sha256
        != _sha256_bytes(manifest_bytes)
        or anchor.render_attempt_manifest_storage.size_bytes != len(manifest_bytes)
        or manifest.artifact_inventory_before_manifest
        != tuple(
            item
            for item in anchor.artifact_inventory_before_anchor
            if item != anchor.render_attempt_manifest_storage
        )
    ):
        raise C4Stage1RunIntegrityError(
            "Stage 1 final manifest or inventory anchor is inconsistent"
        )
    try:
        actual = artifact_store.inspect_run_inventory_exact(anchor.run_id)
    except Exception as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 final run inventory cannot be inspected"
        ) from exc
    expected = tuple(
        sorted(
            (*anchor.artifact_inventory_before_anchor, anchor_storage),
            key=lambda item: item.relative_path,
        )
    )
    if actual != expected:
        raise C4Stage1RunIntegrityError(
            "Stage 1 final run inventory differs from its anchor"
        )
    actual_by_path = {item.relative_path: item for item in actual}

    try:
        prepared_outcome = cold_verify_c4_stage1_prepared_attempt(
            artifact_store,
            manifest.prepared_anchor_storage,
            require_exact_pre_spawn_inventory=False,
        )
        prepared = prepared_outcome.prepared_attempt
        prepared_storage = prepared_outcome.prepared_anchor_storage
    except Exception as exc:
        raise C4Stage1RunIntegrityError(
            "Stage 1 prepared attempt failed final cold verification"
        ) from exc
    if (
        manifest.run_id != prepared.run_id
        or anchor.run_id != prepared.run_id
        or manifest.attempt_id != prepared.attempt_id
        or anchor.prepared_attempt_id != prepared.prepared_attempt_id
        or manifest.prepared_attempt_id != prepared.prepared_attempt_id
        or prepared.prepared_attempt_sha256 != manifest.prepared_attempt_sha256
        or manifest.prepared_anchor_storage != prepared_storage
        or prepared_storage.run_id != prepared.run_id
        or prepared_storage.relative_path != C4_STAGE1_PREPARED_ANCHOR_PATH
        or actual_by_path.get(C4_STAGE1_PREPARED_ANCHOR_PATH) != prepared_storage
    ):
        raise C4Stage1RunIntegrityError(
            "Stage 1 final manifest cites another prepared attempt"
        )
    for member in manifest.member_runs:
        role_workers = tuple(
            worker
            for worker in prepared.workers
            if worker.editor_role == member.editor_role
        )
        expected_slots = {
            _provider_slot_id(prepared, worker) for worker in role_workers
        }
        if (
            len(role_workers) != 2
            or len(expected_slots) != 1
            or member.provider_slot_id not in expected_slots
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 member differs from its prepared provider slot"
            )
        publication_receipt: C4Stage1MemberPublicationReceipt | None = None
        if member.publication_completed:
            publication_storages = tuple(
                terminal.member_publication_receipt_storage
                for terminal in member.worker_terminals
            )
            if (
                len(publication_storages) != 2
                or publication_storages[0] is None
                or publication_storages[0] != publication_storages[1]
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 member publication marker is incomplete"
                )
            publication_receipt = cold_verify_c4_stage1_member_publication(
                artifact_store,
                publication_storages[0],
                prepared,
            )
            if (
                publication_receipt.editor_role != member.editor_role
                or publication_receipt.provider_slot_id != member.provider_slot_id
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 member cites another publication marker"
                )
        elif any(
            terminal.member_publication_completed
            or terminal.published_candidate_receipt_id is not None
            or terminal.published_candidate_receipt_sha256 is not None
            or terminal.member_publication_receipt_id is not None
            or terminal.member_publication_receipt_sha256 is not None
            or terminal.member_publication_receipt_storage is not None
            for terminal in member.worker_terminals
        ):
            raise C4Stage1RunIntegrityError(
                "Stage 1 unpublished member carries publication authority"
            )
        for terminal_index, terminal in enumerate(member.worker_terminals):
            worker = role_workers[terminal_index]
            request = worker.worker_request
            if (
                terminal.prepared_worker_id != worker.prepared_worker_id
                or terminal.worker_request_id != request.worker_request_id
                or terminal.editor_role != worker.editor_role
                or terminal.option_id != worker.option_id
                or terminal.editor_role != member.editor_role
                or _provider_slot_id(prepared, worker) != member.provider_slot_id
                or terminal.failure_scope == "global"
                and not manifest.global_stop_triggered
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 terminal differs from its prepared worker"
                )
            intent = _cold_verify_terminal_intent(
                artifact_store,
                terminal.telemetry_intent_storage,
                prepared=prepared,
                worker=worker,
                actual_by_path=actual_by_path,
            )
            if (
                intent.intent_id != terminal.telemetry_intent_id
                or intent.intent_sha256 != terminal.telemetry_intent_sha256
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 terminal cites another telemetry intent"
                )

            envelope: C4Stage1LaunchEnvelope | None = None
            if terminal.launch_envelope_storage is not None:
                envelope = cold_verify_c4_stage1_launch_envelope(
                    artifact_store,
                    terminal.launch_envelope_storage,
                    prepared,
                    require_exact_launch_inventory=False,
                )
                if (
                    envelope.launch_envelope_id != terminal.launch_envelope_id
                    or envelope.launch_envelope_sha256
                    != terminal.launch_envelope_sha256
                    or envelope.prepared_worker_id != worker.prepared_worker_id
                    or envelope.worker_request_id != request.worker_request_id
                    or envelope.editor_role != worker.editor_role
                    or envelope.option_id != worker.option_id
                    or envelope.provider_slot_id != member.provider_slot_id
                    or envelope.telemetry_intent_id != intent.intent_id
                    or envelope.telemetry_intent_sha256 != intent.intent_sha256
                    or envelope.process_request != intent.process_request
                ):
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 terminal cites another launch envelope"
                    )
            elif (
                terminal.failure_scope != "global"
                or not manifest.global_stop_triggered
                or terminal.worker_technical_passed
                or not {
                    "intent_persistence_verification_failed",
                    "intent_storage_descriptor_mismatch",
                    "launch_envelope_persistence_failed",
                }.intersection(terminal.failure_codes)
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 missing launch envelope has no durable failure lineage"
                )
            if publication_receipt is not None:
                candidates = tuple(
                    candidate
                    for candidate in publication_receipt.candidate_receipts
                    if candidate.prepared_worker_id == terminal.prepared_worker_id
                )
                if (
                    len(candidates) != 1
                    or terminal.published_candidate_receipt_id
                    != candidates[0].candidate_receipt_id
                    or terminal.published_candidate_receipt_sha256
                    != candidates[0].candidate_receipt_sha256
                    or terminal.member_publication_receipt_id
                    != publication_receipt.member_publication_receipt_id
                    or terminal.member_publication_receipt_sha256
                    != publication_receipt.member_publication_receipt_sha256
                ):
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 terminal publication receipt lineage is invalid"
                    )
            process: ProcessTreeExecutionRecord | None = None
            if terminal.process_execution_storage is not None:
                try:
                    process_bytes = artifact_store.read_bytes(
                        terminal.process_execution_storage.storage_id
                    )
                    process = ProcessTreeExecutionRecord.model_validate_json(
                        process_bytes
                    )
                except Exception as exc:
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 process record failed cold verification"
                    ) from exc
                if (
                    canonical_json_bytes(process) != process_bytes
                    or terminal.process_execution_storage.run_id != prepared.run_id
                    or terminal.process_execution_storage.relative_path
                    != _artifact_json_path(
                        "process-execution",
                        process.record_id,
                    )
                    or actual_by_path.get(
                        terminal.process_execution_storage.relative_path
                    )
                    != terminal.process_execution_storage
                    or terminal.process_execution_storage.content_sha256
                    != _sha256_bytes(process_bytes)
                    or terminal.process_execution_storage.size_bytes
                    != len(process_bytes)
                    or process.record_id != terminal.process_execution_record_id
                    or _canonical_sha256(process)
                    != terminal.process_execution_record_sha256
                    or process.status != terminal.process_status
                    or not _process_matches_commitment(
                        process,
                        intent.process_request,
                    )
                    or envelope is not None
                    and (
                        process.workload_id != envelope.workload_id
                        or process.command_identity != envelope.command_identity
                        or process.working_directory_identity
                        != envelope.working_directory_identity
                        or process.environment_identity != envelope.environment_identity
                    )
                ):
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 process record lineage is invalid"
                    )
            elif (
                terminal.failure_scope != "global"
                or not manifest.global_stop_triggered
                or "process_record_persistence_failed" not in terminal.failure_codes
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 missing process record has no persistence failure"
                )
            result: C4Stage1WorkerResult | None = None
            if terminal.worker_result_storage is not None:
                try:
                    result_bytes = artifact_store.read_bytes(
                        terminal.worker_result_storage.storage_id
                    )
                    result = C4Stage1WorkerResult.model_validate_json(result_bytes)
                    result.validate_against(request)
                except Exception as exc:
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 worker result failed cold verification"
                    ) from exc
                if (
                    canonical_json_bytes(result) != result_bytes
                    or terminal.worker_result_storage.run_id != prepared.run_id
                    or terminal.worker_result_storage.relative_path
                    != _artifact_json_path("worker-result", result.worker_result_id)
                    or actual_by_path.get(terminal.worker_result_storage.relative_path)
                    != terminal.worker_result_storage
                    or terminal.worker_result_storage.content_sha256
                    != _sha256_bytes(result_bytes)
                    or terminal.worker_result_storage.size_bytes != len(result_bytes)
                    or result.worker_result_id != terminal.worker_result_id
                    or _canonical_sha256(result) != terminal.worker_result_sha256
                    or result.status != terminal.worker_status
                    or result.worker_request_id != request.worker_request_id
                    or result.worker_request_hash != request.content_hash()
                ):
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 worker result lineage is invalid"
                    )
            elif (
                terminal.failure_scope != "global"
                or not manifest.global_stop_triggered
                or "worker_result_persistence_failed" not in terminal.failure_codes
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 missing worker result has no persistence failure"
                )
            output_storages = (
                terminal.direct_output_storage,
                terminal.staged_output_storage,
            )
            if (
                terminal.member_publication_completed
                and any(storage is None for storage in output_storages)
                or terminal.staged_output_storage is not None
                and terminal.direct_output_storage is None
                or any(storage is not None for storage in output_storages)
                and (result is None or result.image_evidence is None)
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 output storage has no complete worker evidence"
                )
            if result is not None and result.image_evidence is not None:
                evidence = result.image_evidence
                expected_outputs = (
                    (
                        terminal.direct_output_storage,
                        f"diagnostics/{request.worker_request_id}.direct.png",
                        evidence.direct_png_sha256,
                        evidence.direct_png_size_bytes,
                        evidence.direct_width,
                        evidence.direct_height,
                    ),
                    (
                        terminal.staged_output_storage,
                        f"emocio/images/{request.worker_request_id}.png",
                        evidence.staged_png_sha256,
                        evidence.staged_png_size_bytes,
                        evidence.staged_width,
                        evidence.staged_height,
                    ),
                )
                for (
                    output_storage,
                    expected_path,
                    expected_sha256,
                    expected_size,
                    expected_width,
                    expected_height,
                ) in expected_outputs:
                    if output_storage is None:
                        continue
                    try:
                        output_bytes = artifact_store.read_bytes(
                            output_storage.storage_id
                        )
                        dimensions = inspect_c4_stage1_png_bytes(output_bytes)
                    except Exception as exc:
                        raise C4Stage1RunIntegrityError(
                            "Stage 1 output bytes failed cold verification"
                        ) from exc
                    if (
                        output_storage.run_id != prepared.run_id
                        or output_storage.relative_path != expected_path
                        or actual_by_path.get(expected_path) != output_storage
                        or output_storage.content_sha256 != expected_sha256
                        or output_storage.size_bytes != expected_size
                        or _sha256_bytes(output_bytes) != expected_sha256
                        or len(output_bytes) != expected_size
                        or dimensions != (expected_width, expected_height)
                    ):
                        raise C4Stage1RunIntegrityError(
                            "Stage 1 output bytes differ from worker evidence"
                        )
            if terminal.telemetry_finalization_storage is not None:
                try:
                    telemetry = cold_verify_c4_stage1_telemetry_finalization(
                        artifact_store,
                        terminal.telemetry_finalization_storage,
                    )
                except Exception as exc:
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 telemetry receipt failed cold verification"
                    ) from exc
                embedded_process = telemetry.receipt.process_execution_record
                if (
                    actual_by_path.get(
                        terminal.telemetry_finalization_storage.relative_path
                    )
                    != terminal.telemetry_finalization_storage
                    or telemetry.receipt_storage
                    != terminal.telemetry_finalization_storage
                    or telemetry.receipt.intent != intent
                    or telemetry.receipt.finalization_receipt_id
                    != terminal.telemetry_finalization_receipt_id
                    or telemetry.receipt.finalization_receipt_sha256
                    != terminal.telemetry_finalization_receipt_sha256
                    or embedded_process.record_id
                    != terminal.process_execution_record_id
                    or telemetry.receipt.process_execution_record_sha256
                    != terminal.process_execution_record_sha256
                    or embedded_process.status != terminal.process_status
                    or not _process_matches_commitment(
                        embedded_process,
                        intent.process_request,
                    )
                    or process is not None
                    and embedded_process != process
                    or terminal.telemetry_technical_passed
                    != (terminal.telemetry_cold_verified and telemetry.technical_passed)
                    or not terminal.telemetry_cold_verified
                    and (
                        terminal.failure_scope != "global"
                        or not manifest.global_stop_triggered
                        or "telemetry_gate_failed" not in terminal.failure_codes
                    )
                ):
                    raise C4Stage1RunIntegrityError(
                        "Stage 1 telemetry receipt lineage is invalid"
                    )
            elif (
                terminal.telemetry_cold_verified
                or terminal.telemetry_technical_passed
                or terminal.failure_scope != "global"
                or not manifest.global_stop_triggered
                or "telemetry_gate_failed" not in terminal.failure_codes
            ):
                raise C4Stage1RunIntegrityError(
                    "Stage 1 missing telemetry receipt has no failure lineage"
                )
    return C4Stage1RunOutcome(
        manifest=manifest,
        manifest_storage=anchor.render_attempt_manifest_storage,
        inventory_anchor=anchor,
        inventory_anchor_storage=anchor_storage,
    )


__all__ = [
    "C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH",
    "C4_STAGE1_ATTEMPT_MANIFEST_PATH",
    "C4_STAGE1_LAUNCH_ENVELOPE_SUFFIX",
    "C4_STAGE1_MEMBER_TIMEOUT_SECONDS",
    "C4Stage1ConfirmationError",
    "C4Stage1LaunchEnvelope",
    "C4Stage1MemberRun",
    "C4Stage1MemberPublicationReceipt",
    "C4Stage1PublishedCandidateReceipt",
    "C4Stage1RenderAttemptManifest",
    "C4Stage1RenderInventoryAnchor",
    "C4Stage1RunError",
    "C4Stage1RunIntegrityError",
    "C4Stage1RunOutcome",
    "C4Stage1WorkerTerminal",
    "c4_stage1_launch_envelope_relative_path",
    "cold_verify_c4_stage1_launch_envelope",
    "cold_verify_c4_stage1_member_publication",
    "cold_verify_c4_stage1_run",
    "run_c4_stage1_attempt",
]
