"""Isolated, create-only C4 Stage 1 DINO collapse checks.

The render attempt is immutable input.  DINO vectors and diagnostics are
written to a separate, initially absent run tree.  Every real encoding runs in
its own ``python -I -S`` child held by the bounded process-tree runner, so the
120 second deadline is a hard wall-clock boundary rather than the encoder's
cooperative deadline alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Literal, Protocol, Self

from pydantic import model_validator

from ..emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersSnapshotManifest,
    build_diffusers_snapshot_manifest,
    canonical_snapshot_manifest_bytes,
)
from ..emocio.dinov2_encoder import (
    DINOV2_BASE_DIMENSIONS,
    DINOV2_BASE_MODEL_ID,
    DINOV2_BASE_MODEL_REVISION,
    dinov2_base_encoding_spec,
    dinov2_base_provider_identity,
)
from ..emocio.vector_encoding import verified_float32_le_vector
from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    CommitDigest,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
)
from ..models.emocio import ImageArtifact
from ..models.provider import ProviderCallSpec, ProviderIdentity
from ..persistence.artifacts import FileArtifactStore
from ..providers.protocols import (
    ImageEncodingRequest,
    ImageEncodingSpec,
    StoredArtifact,
    VerifiedImageEncoding,
    build_image_encoding_call_spec,
)
from . import c4_stage1_dino as dino_bridge
from .c4_stage1_attempt import (
    C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH,
    C4_STAGE1_DINO_WORKER_SCRIPT_PATH,
    C4Stage1DinoEntrypointPin,
    C4Stage1PreparedAttempt,
    C4Stage1WorkerRuntimePin,
    build_c4_stage1_worker_environment,
    capture_c4_stage1_repository_gate,
    capture_c4_stage1_worker_runtime,
    verify_c4_stage1_staging_parent,
)
from .c4_stage1_run import (
    C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH,
    C4Stage1MemberPublicationReceipt,
    C4Stage1RunOutcome,
    cold_verify_c4_stage1_run,
)
from .c4_stage1_screen import (
    C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
    C4Stage1DinoPairResult,
)
from .process_tree_runner import (
    PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
    BoundedProcessRequest,
    BoundedProcessTreeRunner,
    ProcessTreeExecutionRecord,
)


C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS = 120.0
C4_STAGE1_DINO_ANCHOR_PATH = "diagnostics/c4_stage1_dino_collapse_check.json"

_DINO_PAIR_SUFFIX = ".dino-pair.json"
_DINO_PROCESS_SUFFIX = ".dino-process-execution.json"
_DINO_VECTOR_PREFIX = "emocio/embeddings/"
_DINO_CHILD_RESULT_FILENAME = "result.json"
_DINO_CHILD_SCHEMA = "rei-c4-stage1-dino-child-request-v1"
_MODEL_MODULE_ROOTS = {
    "accelerate",
    "diffusers",
    "safetensors",
    "torch",
    "transformers",
}
_MAX_SCRIPT_BYTES = 4 * 1024 * 1024
_MAX_CHILD_RESULT_BYTES = 4 * 1024 * 1024
_DINO_BASE_RUNTIME_PROBE_TIMEOUT_SECONDS = 30.0
_DINO_BASE_RUNTIME_PROBE_OUTPUT_LIMIT_BYTES = 32_767
_DINO_BASE_RUNTIME_PROBE_CODE = (
    "import os,sys;"
    "sys.dont_write_bytecode=True;"
    "sys.stdout.write(os.path.abspath(sys.base_prefix))"
)
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_MODULE_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class C4Stage1DinoRunError(RuntimeError):
    """A Stage 1 collapse check failed closed."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256(canonical_json_bytes(value))


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_unlinked_ancestry(path: Path) -> None:
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise C4Stage1DinoRunError("DINO runtime path must be canonical and absolute")
    parts = path.parts
    if not parts:
        raise C4Stage1DinoRunError("DINO runtime path is empty")
    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise C4Stage1DinoRunError("DINO runtime ancestry is unavailable") from exc
        if _is_link_or_reparse(metadata):
            raise C4Stage1DinoRunError(
                "DINO runtime ancestry contains a link or reparse point"
            )


def _assert_plain_tree(root: Path) -> None:
    """Reject links, reparse points, hardlinks and special entries."""

    def walk(directory: Path) -> None:
        try:
            entries = tuple(os.scandir(directory))
        except OSError as exc:
            raise C4Stage1DinoRunError("DINO tree cannot be enumerated") from exc
        for entry in entries:
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise C4Stage1DinoRunError("DINO tree entry is unavailable") from exc
            if _is_link_or_reparse(metadata):
                raise C4Stage1DinoRunError("DINO tree contains a link or reparse point")
            path = Path(entry.path)
            if stat.S_ISDIR(metadata.st_mode):
                walk(path)
            elif not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise C4Stage1DinoRunError(
                    "DINO tree entries must be ordinary unlinked files"
                )

    walk(root)


def _stable_regular_bytes(path: Path, *, maximum_bytes: int) -> bytes:
    _assert_unlinked_ancestry(path)
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise C4Stage1DinoRunError("DINO script is unavailable") from exc
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 < before.st_size <= maximum_bytes
    ):
        raise C4Stage1DinoRunError("DINO script is not one bounded ordinary file")
    try:
        value = path.read_bytes()
        after = os.lstat(path)
    except OSError as exc:
        raise C4Stage1DinoRunError("DINO script cannot be read") from exc
    if (
        len(value) != before.st_size
        or not os.path.samestat(before, after)
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise C4Stage1DinoRunError("DINO script changed while it was read")
    return value


def _assert_no_model_modules() -> None:
    if any(name.split(".", 1)[0] in _MODEL_MODULE_ROOTS for name in sys.modules):
        raise C4Stage1DinoRunError(
            "Stage 1 DINO model modules were imported before child authorization"
        )


def verify_c4_stage1_dino_snapshot(snapshot_path: str | Path) -> Path:
    """Verify the exact pinned DINOv2 snapshot without importing model code."""

    lexical = Path(snapshot_path)
    _assert_unlinked_ancestry(lexical)
    try:
        root = lexical.resolve(strict=True)
    except OSError as exc:
        raise C4Stage1DinoRunError("DINO snapshot is unavailable") from exc
    if root != lexical or not root.is_dir():
        raise C4Stage1DinoRunError("DINO snapshot must be one canonical directory")
    _assert_plain_tree(root)
    manifest_path = root / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    try:
        payload = manifest_path.read_bytes()
        manifest = DiffusersSnapshotManifest.model_validate_json(payload)
    except Exception as exc:
        raise C4Stage1DinoRunError("DINO snapshot manifest is invalid") from exc
    actual = build_diffusers_snapshot_manifest(
        root,
        repo_id=DINOV2_BASE_MODEL_ID,
        revision=DINOV2_BASE_MODEL_REVISION,
    )
    if (
        _sha256(payload) != C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256
        or canonical_snapshot_manifest_bytes(manifest) != payload
        or manifest.repo_id != DINOV2_BASE_MODEL_ID
        or manifest.revision != DINOV2_BASE_MODEL_REVISION
        or canonical_snapshot_manifest_bytes(actual) != payload
    ):
        raise C4Stage1DinoRunError("DINO snapshot differs from its exact pin")
    return root


def _stored(value: StoredArtifact, *, label: str) -> StoredArtifact:
    if not isinstance(value, StoredArtifact):
        raise TypeError(f"{label} must be a StoredArtifact")
    return StoredArtifact.model_validate(
        value.model_dump(mode="python", round_trip=True)
    )


def _pair_path(result: C4Stage1DinoPairResult) -> str:
    return f"diagnostics/{result.dino_pair_result_id}{_DINO_PAIR_SUFFIX}"


class C4Stage1DinoSemanticChildRequest(FrozenArtifactModel):
    """Path-free commitment to every trusted input of one DINO child."""

    schema_version: Literal["rei-c4-stage1-dino-semantic-child-request-v1"] = (
        "rei-c4-stage1-dino-semantic-child-request-v1"
    )
    semantic_request_id: NonEmptyId
    semantic_request_sha256: HashDigest
    repository_gate_id: NonEmptyId
    repository_gate_sha256: HashDigest
    repository_head_commit: CommitDigest
    worker_runtime_id: NonEmptyId
    worker_runtime_sha256: HashDigest
    worker_python_sha256: HashDigest
    worker_python_size_bytes: int
    launch_policy_id: NonEmptyId
    launch_policy_sha256: HashDigest
    launch_environment_identity: NonEmptyId
    fixed_environment: tuple[tuple[str, str], ...]
    inherited_environment_names: tuple[str, ...]
    dino_entrypoint_pin: C4Stage1DinoEntrypointPin
    snapshot_manifest_sha256: Literal[
        "786481f81ca90d17eada5cd387835e457f1e531e93ec38a7671368dbb8249ba1"
    ] = C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256
    encoder_spec_sha256: HashDigest
    cuda_measurement_subject_id: NonEmptyId
    cuda_device_identity_sha256: HashDigest
    cuda_physical_gpu_uuid: NonEmptyId
    image: ImageArtifact
    call: ProviderCallSpec
    isolated_interpreter_flags: tuple[Literal["-I"], Literal["-S"]] = ("-I", "-S")
    hard_timeout_seconds: Literal[120.0] = C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS
    local_paths_stored: Literal[False] = False
    inherited_environment_values_stored: Literal[False] = False

    @classmethod
    def create(
        cls,
        prepared: C4Stage1PreparedAttempt,
        *,
        image: ImageArtifact,
        call: ProviderCallSpec,
    ) -> C4Stage1DinoSemanticChildRequest:
        prepared = C4Stage1PreparedAttempt.model_validate(
            prepared.model_dump(mode="python", round_trip=True)
        )
        image = ImageArtifact.model_validate(
            image.model_dump(mode="python", round_trip=True)
        )
        call = ProviderCallSpec.model_validate(
            call.model_dump(mode="python", round_trip=True)
        )
        entrypoint_pin = C4Stage1DinoEntrypointPin.model_validate(
            prepared.dino_entrypoint_pin.model_dump(mode="python", round_trip=True)
        )
        body = {
            "schema_version": "rei-c4-stage1-dino-semantic-child-request-v1",
            "repository_gate_id": prepared.repository_gate.repository_gate_id,
            "repository_gate_sha256": prepared.repository_gate.repository_gate_sha256,
            "repository_head_commit": prepared.repository_gate.head_commit,
            "worker_runtime_id": prepared.worker_runtime.worker_runtime_id,
            "worker_runtime_sha256": prepared.worker_runtime.worker_runtime_sha256,
            "worker_python_sha256": prepared.worker_runtime.worker_python_sha256,
            "worker_python_size_bytes": (
                prepared.worker_runtime.worker_python_size_bytes
            ),
            "launch_policy_id": prepared.launch_policy.launch_policy_id,
            "launch_policy_sha256": prepared.launch_policy.launch_policy_sha256,
            "launch_environment_identity": (
                prepared.launch_policy.environment_identity
            ),
            "fixed_environment": prepared.launch_policy.fixed_environment,
            "inherited_environment_names": (
                prepared.launch_policy.inherited_environment_names
            ),
            "dino_entrypoint_pin": entrypoint_pin,
            "snapshot_manifest_sha256": (
                C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256
            ),
            "encoder_spec_sha256": prepared.screen_contract.dino_policy.encoder_spec_sha256,
            "cuda_measurement_subject_id": (
                prepared.cuda_device.measurement_subject_id
            ),
            "cuda_device_identity_sha256": _canonical_sha256(prepared.cuda_device),
            "cuda_physical_gpu_uuid": prepared.cuda_device.physical_gpu_uuid,
            "image": image,
            "call": call,
            "isolated_interpreter_flags": ("-I", "-S"),
            "hard_timeout_seconds": C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS,
            "local_paths_stored": False,
            "inherited_environment_values_stored": False,
        }
        return cls(
            semantic_request_id=content_id("c4_stage1_dino_semantic_request", body),
            semantic_request_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_semantic_request(self) -> Self:
        entrypoint_pin = C4Stage1DinoEntrypointPin.model_validate(
            self.dino_entrypoint_pin.model_dump(mode="python", round_trip=True)
        )
        image = ImageArtifact.model_validate(
            self.image.model_dump(mode="python", round_trip=True)
        )
        call = ProviderCallSpec.model_validate(
            self.call.model_dump(mode="python", round_trip=True)
        )
        expected_spec = dinov2_base_encoding_spec(
            snapshot_manifest_sha256=C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
            device="cuda",
        )
        if (
            entrypoint_pin.repository_gate_id != self.repository_gate_id
            or entrypoint_pin.repository_gate_sha256 != self.repository_gate_sha256
            or entrypoint_pin.repository_head_commit != self.repository_head_commit
            or self.encoder_spec_sha256 != expected_spec.content_hash()
            or call != _build_encoding_call(image)
            or call.input_artifact_ids != (image.image_id,)
            or call.timeout_seconds != C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS
        ):
            raise ValueError("Stage 1 DINO semantic request inputs are inconsistent")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"semantic_request_id", "semantic_request_sha256"},
        )
        if self.semantic_request_id != content_id(
            "c4_stage1_dino_semantic_request", body
        ) or self.semantic_request_sha256 != _canonical_sha256(body):
            raise ValueError("Stage 1 DINO semantic request differs from content")
        return self


def _dino_workload_identity(semantic: C4Stage1DinoSemanticChildRequest) -> str:
    return content_id(
        "c4_stage1_dino_workload",
        {
            "semantic_request_id": semantic.semantic_request_id,
            "semantic_request_sha256": semantic.semantic_request_sha256,
            "image_id": semantic.image.image_id,
            "provider_call_id": semantic.call.call_id,
        },
    )


def _dino_command_identity(
    semantic: C4Stage1DinoSemanticChildRequest,
    *,
    transport_request_sha256: str,
) -> str:
    return content_id(
        "c4_stage1_dino_command",
        {
            "semantic_request_id": semantic.semantic_request_id,
            "semantic_request_sha256": semantic.semantic_request_sha256,
            "transport_request_sha256": transport_request_sha256,
            "isolated_interpreter_flags": semantic.isolated_interpreter_flags,
            "dino_entrypoint_pin_id": (
                semantic.dino_entrypoint_pin.dino_entrypoint_pin_id
            ),
            "dino_entrypoint_pin_sha256": (
                semantic.dino_entrypoint_pin.dino_entrypoint_pin_sha256
            ),
            "worker_runtime_id": semantic.worker_runtime_id,
            "worker_runtime_sha256": semantic.worker_runtime_sha256,
        },
    )


def _dino_working_directory_identity(
    semantic: C4Stage1DinoSemanticChildRequest,
) -> str:
    return content_id(
        "c4_stage1_dino_cwd",
        {
            "repository_gate_id": semantic.repository_gate_id,
            "repository_gate_sha256": semantic.repository_gate_sha256,
            "repository_head_commit": semantic.repository_head_commit,
        },
    )


def _dino_environment_policy_identity(
    semantic: C4Stage1DinoSemanticChildRequest,
) -> str:
    return content_id(
        "c4_stage1_dino_env_policy",
        {
            "launch_policy_id": semantic.launch_policy_id,
            "launch_policy_sha256": semantic.launch_policy_sha256,
            "launch_environment_identity": semantic.launch_environment_identity,
            "fixed_environment": semantic.fixed_environment,
            "inherited_environment_names": semantic.inherited_environment_names,
            "worker_runtime_id": semantic.worker_runtime_id,
            "worker_runtime_sha256": semantic.worker_runtime_sha256,
            "cuda_device_identity_sha256": semantic.cuda_device_identity_sha256,
        },
    )


class C4Stage1DinoProcessEvidence(FrozenModel):
    """One successful, hard-bounded isolated encoder process."""

    dino_run_id: NonEmptyId
    editor_role: Literal["primary", "alternate"]
    option_id: Literal["enter_circle", "remain_edge"]
    image_artifact_id: NonEmptyId
    provider_call_id: NonEmptyId
    encoding_artifact_id: NonEmptyId
    vector_sha256: HashDigest
    semantic_request: C4Stage1DinoSemanticChildRequest
    transport_request_sha256: HashDigest
    child_result_sha256: HashDigest
    bootstrap_script_sha256: HashDigest
    bootstrap_script_size_bytes: int
    worker_script_sha256: HashDigest
    worker_script_size_bytes: int
    process_execution_record: ProcessTreeExecutionRecord
    process_execution_storage: StoredArtifact
    hard_timeout_seconds: Literal[120.0] = C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS
    isolated_interpreter_flags: tuple[Literal["-I"], Literal["-S"]] = ("-I", "-S")
    process_tree_termination_enforced: Literal[True] = True
    parent_imported_model_packages: Literal[False] = False

    @model_validator(mode="after")
    def validate_process(self) -> Self:
        semantic = C4Stage1DinoSemanticChildRequest.model_validate(
            self.semantic_request.model_dump(mode="python", round_trip=True)
        )
        record = ProcessTreeExecutionRecord.model_validate(
            self.process_execution_record.model_dump(mode="python", round_trip=True)
        )
        storage = _stored(
            self.process_execution_storage,
            label="process_execution_storage",
        )
        payload = canonical_json_bytes(record)
        expected_path = f"diagnostics/{record.command_identity}{_DINO_PROCESS_SUFFIX}"
        bootstrap_pin, worker_pin = semantic.dino_entrypoint_pin.scripts
        if (
            semantic.image.image_id != self.image_artifact_id
            or semantic.call.call_id != self.provider_call_id
            or bootstrap_pin.role != "dino-bootstrap"
            or worker_pin.role != "dino-worker"
            or self.bootstrap_script_sha256 != bootstrap_pin.content_sha256
            or self.bootstrap_script_size_bytes != bootstrap_pin.size_bytes
            or self.worker_script_sha256 != worker_pin.content_sha256
            or self.worker_script_size_bytes != worker_pin.size_bytes
            or storage.run_id != self.dino_run_id
            or storage.relative_path != expected_path
            or storage.content_sha256 != _sha256(payload)
            or storage.size_bytes != len(payload)
            or record.status != "succeeded"
            or record.workload_id != _dino_workload_identity(semantic)
            or record.command_identity
            != _dino_command_identity(
                semantic,
                transport_request_sha256=self.transport_request_sha256,
            )
            or record.working_directory_identity
            != _dino_working_directory_identity(semantic)
            or record.environment_identity != _dino_environment_policy_identity(semantic)
            or record.argument_count != 5
            or record.exit_code != 0
            or record.failure_code is not None
            or record.timeout_seconds != C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS
            or record.stdout_limit_bytes != PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES
            or record.stderr_limit_bytes != PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES
            or record.termination_trigger != "not_required"
            or record.tree_termination_requested
            or not record.containment_closed
            or not record.empty_tree_confirmed
            or record.target_identity_confirmed is not True
            or self.isolated_interpreter_flags != semantic.isolated_interpreter_flags
        ):
            raise ValueError("Stage 1 DINO process evidence is inconsistent")
        return self


class C4Stage1DinoFamilyEvidence(FrozenModel):
    """One complete receipt-bound family comparison and its isolated calls."""

    dino_run_id: NonEmptyId
    editor_role: Literal["primary", "alternate"]
    member_publication_receipt_storage: StoredArtifact
    dino_pair_result: C4Stage1DinoPairResult
    dino_pair_result_storage: StoredArtifact
    processes: tuple[C4Stage1DinoProcessEvidence, C4Stage1DinoProcessEvidence]
    dino_gate_passed: bool
    action_collapse_detected: bool
    human_review_substitute: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        result: C4Stage1DinoPairResult,
        result_storage: StoredArtifact,
        processes: tuple[C4Stage1DinoProcessEvidence, C4Stage1DinoProcessEvidence],
        *,
        dino_run_id: str,
    ) -> C4Stage1DinoFamilyEvidence:
        return cls(
            dino_run_id=dino_run_id,
            editor_role=result.editor_role,
            member_publication_receipt_storage=result.member_publication_receipt_storage,
            dino_pair_result=result,
            dino_pair_result_storage=result_storage,
            processes=processes,
            dino_gate_passed=result.dino_gate_passed,
            action_collapse_detected=result.action_collapse_detected,
        )

    @model_validator(mode="after")
    def validate_family(self) -> Self:
        result = C4Stage1DinoPairResult.model_validate(
            self.dino_pair_result.model_dump(mode="python", round_trip=True)
        )
        storage = _stored(
            self.dino_pair_result_storage, label="dino_pair_result_storage"
        )
        payload = result.canonical_json_bytes()
        if (
            result.editor_role != self.editor_role
            or result.member_publication_receipt_storage
            != self.member_publication_receipt_storage
            or storage.run_id != self.dino_run_id
            or storage.relative_path != _pair_path(result)
            or storage.content_sha256 != _sha256(payload)
            or storage.size_bytes != len(payload)
            or tuple(item.editor_role for item in self.processes)
            != (self.editor_role, self.editor_role)
            or tuple(item.option_id for item in self.processes)
            != ("enter_circle", "remain_edge")
            or tuple(item.image_artifact_id for item in self.processes)
            != tuple(output.image_artifact_id for output in result.outputs)
            or tuple(item.encoding_artifact_id for item in self.processes)
            != tuple(output.embedding_artifact_id for output in result.outputs)
            or tuple(item.provider_call_id for item in self.processes)
            != tuple(output.encoding.call_spec.call_id for output in result.outputs)
            or tuple(item.vector_sha256 for item in self.processes)
            != tuple(output.vector_sha256 for output in result.outputs)
            or any(
                process.child_result_sha256
                != _sha256(
                    canonical_json_bytes(
                        {
                            "schema_version": "rei-c4-stage1-dino-child-result-v1",
                            "encoding": output.encoding,
                        }
                    )
                )
                for process, output in zip(
                    self.processes,
                    result.outputs,
                    strict=True,
                )
            )
            or any(item.dino_run_id != self.dino_run_id for item in self.processes)
            or self.dino_gate_passed != result.dino_gate_passed
            or self.action_collapse_detected != result.action_collapse_detected
        ):
            raise ValueError("Stage 1 DINO family evidence is inconsistent")
        return self


class C4Stage1DinoCollapseCheckAnchor(FrozenArtifactModel):
    """Final create-only commit for a separate DINO evidence run."""

    schema_version: Literal["rei-c4-stage1-dino-collapse-check-v2"] = (
        "rei-c4-stage1-dino-collapse-check-v2"
    )
    dino_collapse_check_id: NonEmptyId
    dino_run_id: NonEmptyId
    render_run_id: NonEmptyId
    render_inventory_anchor_id: NonEmptyId
    render_inventory_anchor_sha256: HashDigest
    render_inventory_anchor_storage: StoredArtifact
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    prepared_anchor_storage: StoredArtifact
    worker_runtime_id: NonEmptyId
    worker_runtime_sha256: HashDigest
    encoder: ProviderIdentity
    encoder_spec: ImageEncodingSpec
    encoder_spec_sha256: HashDigest
    encoder_snapshot_manifest_sha256: Literal[
        "786481f81ca90d17eada5cd387835e457f1e531e93ec38a7671368dbb8249ba1"
    ] = C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256
    render_artifact_inventory: tuple[StoredArtifact, ...]
    families: tuple[C4Stage1DinoFamilyEvidence, C4Stage1DinoFamilyEvidence]
    artifact_inventory_before_anchor: tuple[StoredArtifact, ...]
    render_evidence_cold_verified_before_first_encoding: Literal[True] = True
    render_evidence_cold_verified_after_dino: Literal[True] = True
    runtime_reverified_before_first_encoding: Literal[True] = True
    snapshot_reverified_before_first_encoding: Literal[True] = True
    separate_fresh_dino_run_required: Literal[True] = True
    local_paths_stored: Literal[False] = False
    family_comparison_count: Literal[2] = 2
    encoded_image_count: Literal[4] = 4
    isolated_child_process_count: Literal[4] = 4
    both_family_comparisons_complete: Literal[True] = True
    all_dino_gates_passed: bool
    any_action_collapse_detected: bool
    human_review_substitute: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        preflight: _DinoPreflight,
        families: tuple[C4Stage1DinoFamilyEvidence, C4Stage1DinoFamilyEvidence],
        artifact_inventory_before_anchor: tuple[StoredArtifact, ...],
    ) -> C4Stage1DinoCollapseCheckAnchor:
        prepared = preflight.prepared
        render_anchor = preflight.render_outcome.inventory_anchor
        spec = dinov2_base_encoding_spec(
            snapshot_manifest_sha256=C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
            device="cuda",
        )
        body = {
            "schema_version": "rei-c4-stage1-dino-collapse-check-v2",
            "dino_run_id": preflight.dino_run_id,
            "render_run_id": prepared.run_id,
            "render_inventory_anchor_id": render_anchor.render_inventory_anchor_id,
            "render_inventory_anchor_sha256": render_anchor.render_inventory_anchor_sha256,
            "render_inventory_anchor_storage": preflight.render_anchor_storage,
            "prepared_attempt_id": prepared.prepared_attempt_id,
            "prepared_attempt_sha256": prepared.prepared_attempt_sha256,
            "prepared_anchor_storage": preflight.prepared_storage,
            "worker_runtime_id": prepared.worker_runtime.worker_runtime_id,
            "worker_runtime_sha256": prepared.worker_runtime.worker_runtime_sha256,
            "encoder": dinov2_base_provider_identity(),
            "encoder_spec": spec,
            "encoder_spec_sha256": spec.content_hash(),
            "encoder_snapshot_manifest_sha256": C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
            "render_artifact_inventory": preflight.render_inventory,
            "families": families,
            "artifact_inventory_before_anchor": artifact_inventory_before_anchor,
            "render_evidence_cold_verified_before_first_encoding": True,
            "render_evidence_cold_verified_after_dino": True,
            "runtime_reverified_before_first_encoding": True,
            "snapshot_reverified_before_first_encoding": True,
            "separate_fresh_dino_run_required": True,
            "local_paths_stored": False,
            "family_comparison_count": 2,
            "encoded_image_count": 4,
            "isolated_child_process_count": 4,
            "both_family_comparisons_complete": True,
            "all_dino_gates_passed": all(item.dino_gate_passed for item in families),
            "any_action_collapse_detected": any(
                item.action_collapse_detected for item in families
            ),
            "human_review_substitute": False,
            "semantic_quality_gate_passed": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        return cls(
            dino_collapse_check_id=content_id("c4_stage1_dino_check", body),
            **body,
        )

    @model_validator(mode="after")
    def validate_anchor(self) -> Self:
        expected_spec = dinov2_base_encoding_spec(
            snapshot_manifest_sha256=C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
            device="cuda",
        )
        render_paths = tuple(
            item.relative_path for item in self.render_artifact_inventory
        )
        dino_paths = tuple(
            item.relative_path for item in self.artifact_inventory_before_anchor
        )
        if (
            self.dino_run_id == self.render_run_id
            or tuple(item.editor_role for item in self.families)
            != ("primary", "alternate")
            or self.encoder != dinov2_base_provider_identity()
            or self.encoder_spec != expected_spec
            or self.encoder_spec_sha256 != expected_spec.content_hash()
            or render_paths != tuple(sorted(render_paths))
            or len(render_paths) != len(set(render_paths))
            or dino_paths != tuple(sorted(dino_paths))
            or len(dino_paths) != len(set(dino_paths))
            or any(
                item.run_id != self.render_run_id
                for item in self.render_artifact_inventory
            )
            or any(
                item.run_id != self.dino_run_id
                for item in self.artifact_inventory_before_anchor
            )
            or self.render_inventory_anchor_storage
            not in self.render_artifact_inventory
            or self.render_inventory_anchor_storage.run_id != self.render_run_id
            or self.render_inventory_anchor_storage.relative_path
            != C4_STAGE1_ATTEMPT_INVENTORY_ANCHOR_PATH
            or self.prepared_anchor_storage not in self.render_artifact_inventory
            or self.prepared_anchor_storage.run_id != self.render_run_id
            or any(
                family.dino_run_id != self.dino_run_id
                or family.dino_pair_result.run_id != self.render_run_id
                or family.dino_pair_result.prepared_attempt_id
                != self.prepared_attempt_id
                or family.dino_pair_result.prepared_attempt_sha256
                != self.prepared_attempt_sha256
                or family.dino_pair_result.prepared_anchor_storage
                != self.prepared_anchor_storage
                for family in self.families
            )
            or self.all_dino_gates_passed
            != all(item.dino_gate_passed for item in self.families)
            or self.any_action_collapse_detected
            != any(item.action_collapse_detected for item in self.families)
        ):
            raise ValueError("Stage 1 DINO collapse-check anchor is inconsistent")

        expected_dino_paths: set[str] = set()
        before_by_path = {
            item.relative_path: item for item in self.artifact_inventory_before_anchor
        }
        for family in self.families:
            expected_dino_paths.add(family.dino_pair_result_storage.relative_path)
            if (
                family.dino_pair_result_storage
                not in self.artifact_inventory_before_anchor
            ):
                raise ValueError("Stage 1 DINO pair evidence is absent from inventory")
            for process, output in zip(
                family.processes,
                family.dino_pair_result.outputs,
                strict=True,
            ):
                expected_dino_paths.add(process.process_execution_storage.relative_path)
                expected_dino_paths.add(output.encoding.vector_ref)
                descriptor = before_by_path.get(output.encoding.vector_ref)
                if (
                    process.process_execution_storage
                    not in self.artifact_inventory_before_anchor
                    or descriptor is None
                    or descriptor.content_sha256 != output.vector_sha256
                    or descriptor.size_bytes != 4 * DINOV2_BASE_DIMENSIONS
                ):
                    raise ValueError(
                        "Stage 1 DINO process/vector inventory is inconsistent"
                    )
        if set(dino_paths) != expected_dino_paths:
            raise ValueError("Stage 1 DINO anchor contains undeclared side effects")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"dino_collapse_check_id"},
        )
        if self.dino_collapse_check_id != content_id("c4_stage1_dino_check", body):
            raise ValueError("Stage 1 DINO anchor ID differs from content")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1DinoRunOutcome:
    anchor: C4Stage1DinoCollapseCheckAnchor
    anchor_storage: StoredArtifact


@dataclass(frozen=True, slots=True)
class _DinoPreflight:
    render_store: FileArtifactStore
    dino_store: FileArtifactStore
    dino_run_id: str
    render_outcome: C4Stage1RunOutcome
    render_anchor_storage: StoredArtifact
    prepared: C4Stage1PreparedAttempt
    prepared_storage: StoredArtifact
    publications: tuple[
        C4Stage1MemberPublicationReceipt,
        C4Stage1MemberPublicationReceipt,
    ]
    publication_storages: tuple[StoredArtifact, StoredArtifact]
    images: tuple[
        tuple[ImageArtifact, ImageArtifact], tuple[ImageArtifact, ImageArtifact]
    ]
    render_inventory: tuple[StoredArtifact, ...]


@dataclass(slots=True)
class _DinoInventoryLedger:
    store: FileArtifactStore
    run_id: str
    descriptors: dict[str, StoredArtifact] = field(default_factory=dict)

    def add(self, descriptor: StoredArtifact) -> None:
        value = _stored(descriptor, label="dino_artifact")
        if value.run_id != self.run_id or value.relative_path in self.descriptors:
            raise C4Stage1DinoRunError("DINO create-only ledger rejected an artifact")
        self.descriptors[value.relative_path] = value
        self.verify()

    def snapshot(self) -> tuple[StoredArtifact, ...]:
        return tuple(self.descriptors[path] for path in sorted(self.descriptors))

    def verify(self) -> None:
        if self.store.inspect_run_inventory_exact(self.run_id) != self.snapshot():
            raise C4Stage1DinoRunError(
                "DINO run contains an undeclared filesystem side effect"
            )


def _run_path_absent(store: FileArtifactStore, run_id: str) -> bool:
    path = store.run_path(run_id)
    try:
        os.lstat(path)
    except FileNotFoundError:
        return True
    except OSError as exc:
        raise C4Stage1DinoRunError("DINO run path cannot be inspected") from exc
    return False


def _publication_storage(member: object) -> StoredArtifact:
    storages = tuple(
        terminal.member_publication_receipt_storage
        for terminal in member.worker_terminals
        if terminal.member_publication_receipt_storage is not None
    )
    if (
        not member.publication_completed
        or len(storages) != 2
        or storages[0] != storages[1]
    ):
        raise C4Stage1DinoRunError("Stage 1 render family is not atomically published")
    return storages[0]


def _preflight(
    render_artifact_store: FileArtifactStore,
    dino_artifact_store: FileArtifactStore,
    render_inventory_anchor_storage: StoredArtifact,
    member_publication_receipt_storages: tuple[StoredArtifact, StoredArtifact],
    *,
    dino_run_id: str,
    confirmed_prepared_attempt_id: str,
    confirmed_dino_policy_id: str,
) -> _DinoPreflight:
    if not isinstance(render_artifact_store, FileArtifactStore) or not isinstance(
        dino_artifact_store, FileArtifactStore
    ):
        raise TypeError("Stage 1 DINO requires two FileArtifactStore instances")
    if (
        type(member_publication_receipt_storages) is not tuple
        or len(member_publication_receipt_storages) != 2
    ):
        raise ValueError("Stage 1 DINO requires exactly two member receipts")
    render_store = FileArtifactStore(render_artifact_store.root, create=False)
    dino_store = FileArtifactStore(dino_artifact_store.root, create=False)
    render_anchor_storage = _stored(
        render_inventory_anchor_storage,
        label="render_inventory_anchor_storage",
    )

    # This exact final anchor is the first authority gate.  It rejects unknown
    # files, an incomplete family, and any post-render mutation before a child
    # can be constructed or spawned.
    try:
        render_outcome = cold_verify_c4_stage1_run(render_store, render_anchor_storage)
    except Exception as exc:
        raise C4Stage1DinoRunError(
            "Stage 1 final render anchor failed cold replay"
        ) from exc
    manifest = render_outcome.manifest
    if (
        render_outcome.inventory_anchor_storage != render_anchor_storage
        or not manifest.render_technical_completed
        or manifest.status != "evidence_ready"
        or manifest.global_stop_triggered
        or manifest.failure_codes
        or tuple(item.editor_role for item in manifest.member_runs)
        != ("primary", "alternate")
    ):
        raise C4Stage1DinoRunError("Stage 1 final render inventory is incomplete")
    exact_publication_storages = tuple(
        _publication_storage(member) for member in manifest.member_runs
    )
    supplied_publication_storages = tuple(
        _stored(item, label="member_publication_receipt_storage")
        for item in member_publication_receipt_storages
    )
    if exact_publication_storages != supplied_publication_storages:
        raise C4Stage1DinoRunError(
            "Stage 1 member receipts differ from the final anchor"
        )

    cold_results = tuple(
        dino_bridge._cold_publication(
            render_store,
            manifest.prepared_anchor_storage,
            storage,
        )
        for storage in exact_publication_storages
    )
    prepared = cold_results[0][1]
    prepared_storage = cold_results[0][2]
    publications = (cold_results[0][3], cold_results[1][3])
    render_inventory = render_store.inspect_run_inventory_exact(prepared.run_id)
    expected_render_inventory = tuple(
        sorted(
            (
                *render_outcome.inventory_anchor.artifact_inventory_before_anchor,
                render_anchor_storage,
            ),
            key=lambda item: item.relative_path,
        )
    )
    if (
        prepared != cold_results[1][1]
        or prepared_storage != cold_results[1][2]
        or tuple(item.editor_role for item in publications) != ("primary", "alternate")
        or len({item.provider_slot_id for item in publications}) != 2
        or render_inventory != expected_render_inventory
        or type(confirmed_prepared_attempt_id) is not str
        or confirmed_prepared_attempt_id != prepared.prepared_attempt_id
        or type(confirmed_dino_policy_id) is not str
        or confirmed_dino_policy_id
        != prepared.screen_contract.dino_policy.dino_policy_id
        or type(dino_run_id) is not str
        or dino_run_id == prepared.run_id
        or not _run_path_absent(dino_store, dino_run_id)
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO inputs are not exact and fresh")
    render_run_path = render_store.run_path(prepared.run_id).resolve(strict=True)
    dino_run_path = dino_store.run_path(dino_run_id).resolve(strict=False)
    if (
        dino_run_path == render_run_path
        or dino_run_path.is_relative_to(render_run_path)
        or render_run_path.is_relative_to(dino_run_path)
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO and render trees are not disjoint")

    image_families: list[tuple[ImageArtifact, ImageArtifact]] = []
    for cold_result, publication in zip(cold_results, publications, strict=True):
        images = tuple(
            dino_bridge._published_image(
                cold_result[0],
                dino_bridge._prepared_worker(prepared, candidate),
                candidate,
            )[0]
            for candidate in publication.candidate_receipts
        )
        if len(images) != 2:
            raise C4Stage1DinoRunError("Stage 1 DINO family is incomplete")
        image_families.append((images[0], images[1]))
    return _DinoPreflight(
        render_store=render_store,
        dino_store=dino_store,
        dino_run_id=dino_run_id,
        render_outcome=render_outcome,
        render_anchor_storage=render_anchor_storage,
        prepared=prepared,
        prepared_storage=prepared_storage,
        publications=publications,
        publication_storages=exact_publication_storages,  # type: ignore[arg-type]
        images=(image_families[0], image_families[1]),
        render_inventory=render_inventory,
    )


def _verify_actual_repository_root(
    repository_root: Path,
    prepared: C4Stage1PreparedAttempt,
) -> None:
    try:
        supplied = repository_root.resolve(strict=True)
    except OSError as exc:
        raise C4Stage1DinoRunError("Stage 1 DINO repository is unavailable") from exc
    if supplied != _MODULE_REPOSITORY_ROOT:
        raise C4Stage1DinoRunError(
            "Stage 1 DINO repository is not the checkout that loaded this module"
        )
    observed = capture_c4_stage1_repository_gate(supplied)
    if observed != prepared.repository_gate:
        raise C4Stage1DinoRunError("Stage 1 DINO repository changed after preparation")


def _verify_current_worker_runtime(
    worker_python: Path,
    expected: C4Stage1WorkerRuntimePin,
) -> Path:
    try:
        supplied = worker_python.resolve(strict=True)
    except OSError as exc:
        raise C4Stage1DinoRunError(
            "Stage 1 DINO worker runtime is unavailable"
        ) from exc
    observed = capture_c4_stage1_worker_runtime(supplied)
    if observed != expected:
        raise C4Stage1DinoRunError("Stage 1 DINO runtime changed after preparation")
    return supplied


def _worker_base_runtime_root(
    worker_python: Path,
    prepared: C4Stage1PreparedAttempt,
) -> Path:
    environment = build_c4_stage1_worker_environment(prepared.launch_policy)
    workload_id = content_id(
        "c4_dino_base_probe",
        {
            "worker_runtime_id": prepared.worker_runtime.worker_runtime_id,
            "worker_runtime_sha256": prepared.worker_runtime.worker_runtime_sha256,
        },
    )
    command_identity = content_id(
        "c4_dino_base_probe_command",
        {
            "worker_runtime_id": prepared.worker_runtime.worker_runtime_id,
            "worker_python_sha256": prepared.worker_runtime.worker_python_sha256,
            "isolated_interpreter_flags": ("-I", "-S"),
            "probe_sha256": _sha256(_DINO_BASE_RUNTIME_PROBE_CODE.encode("utf-8")),
        },
    )
    working_directory_identity = content_id(
        "c4_dino_base_probe_cwd",
        {
            "repository_gate_id": prepared.repository_gate.repository_gate_id,
            "repository_gate_sha256": prepared.repository_gate.repository_gate_sha256,
            "repository_head_commit": prepared.repository_gate.head_commit,
        },
    )
    environment_identity = content_id(
        "c4_dino_base_probe_env",
        {
            "launch_policy_id": prepared.launch_policy.launch_policy_id,
            "launch_policy_sha256": prepared.launch_policy.launch_policy_sha256,
            "launch_environment_identity": prepared.launch_policy.environment_identity,
            "fixed_environment": prepared.launch_policy.fixed_environment,
            "inherited_environment_names": (
                prepared.launch_policy.inherited_environment_names
            ),
        },
    )
    try:
        request = BoundedProcessRequest(
            workload_id=workload_id,
            command_identity=command_identity,
            working_directory_identity=working_directory_identity,
            environment_identity=environment_identity,
            command=(
                os.fspath(worker_python),
                "-I",
                "-S",
                "-c",
                _DINO_BASE_RUNTIME_PROBE_CODE,
            ),
            working_directory=_MODULE_REPOSITORY_ROOT,
            environment=environment,
            timeout_seconds=_DINO_BASE_RUNTIME_PROBE_TIMEOUT_SECONDS,
            stdout_limit_bytes=_DINO_BASE_RUNTIME_PROBE_OUTPUT_LIMIT_BYTES,
            stderr_limit_bytes=_DINO_BASE_RUNTIME_PROBE_OUTPUT_LIMIT_BYTES,
        )
        bounded = BoundedProcessTreeRunner().run(request)
    except Exception as exc:
        raise C4Stage1DinoRunError("Stage 1 DINO base runtime probe failed") from exc
    record = bounded.record
    if (
        not bounded.succeeded
        or record.workload_id != workload_id
        or record.command_identity != command_identity
        or record.working_directory_identity != working_directory_identity
        or record.environment_identity != environment_identity
        or record.argument_count != 4
        or record.timeout_seconds != _DINO_BASE_RUNTIME_PROBE_TIMEOUT_SECONDS
        or record.stdout_limit_bytes != _DINO_BASE_RUNTIME_PROBE_OUTPUT_LIMIT_BYTES
        or record.stderr_limit_bytes != _DINO_BASE_RUNTIME_PROBE_OUTPUT_LIMIT_BYTES
        or record.status != "succeeded"
        or record.exit_code != 0
        or record.failure_code is not None
        or record.termination_trigger != "not_required"
        or record.tree_termination_requested
        or record.target_identity_confirmed is not True
        or record.final_active_processes != 0
        or not record.empty_tree_confirmed
        or not record.containment_closed
        or not bounded.stdout
        or len(bounded.stdout) > _DINO_BASE_RUNTIME_PROBE_OUTPUT_LIMIT_BYTES
        or bounded.stderr
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO base runtime probe failed")
    try:
        value = bounded.stdout.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise C4Stage1DinoRunError("Stage 1 DINO base runtime probe failed") from exc
    root = Path(value)
    _assert_unlinked_ancestry(root)
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise C4Stage1DinoRunError("Stage 1 DINO base runtime is unavailable") from exc
    if resolved != root or not root.is_dir():
        raise C4Stage1DinoRunError("Stage 1 DINO base runtime path is invalid")
    return root


def _paths_overlap(left: Path, right: Path) -> bool:
    return bool(
        left == right or left.is_relative_to(right) or right.is_relative_to(left)
    )


def _verify_external_staging_parent(
    staging: Path,
    *,
    repository_root: Path,
    worker_python: Path,
    base_runtime_root: Path,
    snapshot: Path,
    preflight: _DinoPreflight,
) -> Path:
    staging_path = staging.resolve(strict=True)
    boundaries = (
        repository_root.resolve(strict=True),
        worker_python.parent.parent.resolve(strict=True),
        base_runtime_root.resolve(strict=True),
        snapshot.resolve(strict=True),
        preflight.render_store.root.resolve(strict=True),
        preflight.render_store.run_path(preflight.prepared.run_id).resolve(strict=True),
        preflight.dino_store.root.resolve(strict=True),
        preflight.dino_store.run_path(preflight.dino_run_id).resolve(strict=False),
    )
    if any(_paths_overlap(staging_path, boundary) for boundary in boundaries):
        raise C4Stage1DinoRunError(
            "Stage 1 DINO staging parent overlaps a trusted input or evidence tree"
        )
    return staging_path


def _build_encoding_call(image: ImageArtifact) -> ProviderCallSpec:
    request = ImageEncodingRequest.create(
        image=image,
        provider=dinov2_base_provider_identity(),
        spec=dinov2_base_encoding_spec(
            snapshot_manifest_sha256=C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
            device="cuda",
        ),
    )
    return build_image_encoding_call_spec(
        request,
        timeout_seconds=C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS,
    )


@dataclass(frozen=True, slots=True)
class _ChildExecution:
    record: ProcessTreeExecutionRecord
    semantic_request: C4Stage1DinoSemanticChildRequest
    transport_request_sha256: str
    child_result_sha256: str | None
    bootstrap_script_sha256: str
    bootstrap_script_size_bytes: int
    worker_script_sha256: str
    worker_script_size_bytes: int
    encoding: VerifiedImageEncoding | None
    vector_bytes: bytes | None = field(repr=False)


class _ChildExecutor(Protocol):
    def execute(
        self,
        *,
        image: ImageArtifact,
        call: ProviderCallSpec,
        editor_role: Literal["primary", "alternate"],
        option_id: Literal["enter_circle", "remain_edge"],
    ) -> _ChildExecution: ...


def _safe_write_new(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise C4Stage1DinoRunError("DINO child request cannot be staged") from exc


def _child_request_payload(
    *,
    repository_root: Path,
    worker_python: Path,
    render_run_root: Path,
    staging_root: Path,
    snapshot: Path,
    prepared: C4Stage1PreparedAttempt,
    image: ImageArtifact,
    call: ProviderCallSpec,
    bootstrap_bytes: bytes,
    worker_bytes: bytes,
) -> bytes:
    body = {
        "schema_version": _DINO_CHILD_SCHEMA,
        "repository_root": os.fspath(repository_root),
        "render_run_root": os.fspath(render_run_root),
        "staging_root": os.fspath(staging_root),
        "snapshot_path": os.fspath(snapshot),
        "worker_python_sha256": prepared.worker_runtime.worker_python_sha256,
        "worker_python_size_bytes": prepared.worker_runtime.worker_python_size_bytes,
        "worker_runtime_id": prepared.worker_runtime.worker_runtime_id,
        "worker_runtime_sha256": prepared.worker_runtime.worker_runtime_sha256,
        "worker_runtime": prepared.worker_runtime,
        "bootstrap_script_sha256": _sha256(bootstrap_bytes),
        "bootstrap_script_size_bytes": len(bootstrap_bytes),
        "worker_script_sha256": _sha256(worker_bytes),
        "worker_script_size_bytes": len(worker_bytes),
        "snapshot_manifest_sha256": C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
        "cuda_physical_gpu_uuid": prepared.cuda_device.physical_gpu_uuid,
        "image": image,
        "call": call,
    }
    return canonical_json_bytes(body)


def _child_process_request(
    *,
    repository_root: Path,
    worker_python: Path,
    bootstrap_path: Path,
    request_path: Path,
    transport_request_sha256: str,
    semantic_request: C4Stage1DinoSemanticChildRequest,
    environment: dict[str, str],
) -> BoundedProcessRequest:
    semantic_request = C4Stage1DinoSemanticChildRequest.model_validate(
        semantic_request.model_dump(mode="python", round_trip=True)
    )
    command = (
        os.fspath(worker_python),
        "-I",
        "-S",
        os.fspath(bootstrap_path),
        "--request",
        os.fspath(request_path),
    )
    return BoundedProcessRequest(
        workload_id=_dino_workload_identity(semantic_request),
        command_identity=_dino_command_identity(
            semantic_request,
            transport_request_sha256=transport_request_sha256,
        ),
        working_directory_identity=_dino_working_directory_identity(semantic_request),
        environment_identity=_dino_environment_policy_identity(semantic_request),
        command=command,
        working_directory=repository_root,
        environment=environment,
        timeout_seconds=C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS,
        stdout_limit_bytes=PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
        stderr_limit_bytes=PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
    )


def _inspect_child_output(
    staging_root: Path,
    *,
    image: ImageArtifact,
    call: ProviderCallSpec,
) -> tuple[VerifiedImageEncoding, bytes, str]:
    _assert_plain_tree(staging_root)
    result_path = staging_root / _DINO_CHILD_RESULT_FILENAME
    try:
        result_bytes = result_path.read_bytes()
    except OSError as exc:
        raise C4Stage1DinoRunError("DINO child result is unavailable") from exc
    if not 0 < len(result_bytes) <= _MAX_CHILD_RESULT_BYTES:
        raise C4Stage1DinoRunError("DINO child result exceeds its bound")
    try:
        payload = json.loads(result_bytes.decode("utf-8", errors="strict"))
        encoding = VerifiedImageEncoding.model_validate(payload["encoding"])
    except Exception as exc:
        raise C4Stage1DinoRunError("DINO child result is invalid") from exc
    if (
        set(payload) != {"schema_version", "encoding"}
        or payload.get("schema_version") != "rei-c4-stage1-dino-child-result-v1"
        or canonical_json_bytes(payload) != result_bytes
        or encoding.call_spec != call
        or encoding.call.call_id != call.call_id
        or encoding.image_id != image.image_id
        or encoding.request.image_content_sha256 != image.content_sha256
        or encoding.call.status != "succeeded"
        or encoding.call.primary_status != "succeeded"
        or encoding.call.timeout_seconds != C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS
    ):
        raise C4Stage1DinoRunError("DINO child encoding differs from its request")
    vector_path = staging_root.joinpath(*encoding.vector_ref.split("/"))
    try:
        vector_bytes = vector_path.read_bytes()
    except OSError as exc:
        raise C4Stage1DinoRunError("DINO child vector is unavailable") from exc
    _, digest = verified_float32_le_vector(
        vector_bytes,
        expected_dimensions=DINOV2_BASE_DIMENSIONS,
    )
    actual_files = {
        path.relative_to(staging_root).as_posix()
        for path in staging_root.rglob("*")
        if path.is_file()
    }
    if (
        encoding.vector_ref != f"{_DINO_VECTOR_PREFIX}{encoding.vector_hash}.f32"
        or digest != encoding.vector_hash
        or actual_files != {_DINO_CHILD_RESULT_FILENAME, encoding.vector_ref}
    ):
        raise C4Stage1DinoRunError("DINO child staging inventory is not exact")
    return encoding, vector_bytes, _sha256(result_bytes)


class _ProductionChildExecutor:
    def __init__(
        self,
        preflight: _DinoPreflight,
        *,
        repository_root: Path,
        worker_python: Path,
        snapshot: Path,
        staging_parent: Path,
    ) -> None:
        self._preflight = preflight
        self._repository_root = repository_root
        self._worker_python = worker_python
        self._snapshot = snapshot
        self._staging_parent = staging_parent
        self._bootstrap_path = repository_root / C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH
        self._worker_path = repository_root / C4_STAGE1_DINO_WORKER_SCRIPT_PATH
        self._bootstrap_bytes = _stable_regular_bytes(
            self._bootstrap_path,
            maximum_bytes=_MAX_SCRIPT_BYTES,
        )
        self._worker_bytes = _stable_regular_bytes(
            self._worker_path,
            maximum_bytes=_MAX_SCRIPT_BYTES,
        )
        bootstrap_pin, worker_pin = preflight.prepared.dino_entrypoint_pin.scripts
        if (
            bootstrap_pin.role != "dino-bootstrap"
            or bootstrap_pin.content_sha256 != _sha256(self._bootstrap_bytes)
            or bootstrap_pin.size_bytes != len(self._bootstrap_bytes)
            or worker_pin.role != "dino-worker"
            or worker_pin.content_sha256 != _sha256(self._worker_bytes)
            or worker_pin.size_bytes != len(self._worker_bytes)
        ):
            raise C4Stage1DinoRunError(
                "Stage 1 DINO entrypoints differ from prepared Git-byte pins"
            )

    def execute(
        self,
        *,
        image: ImageArtifact,
        call: ProviderCallSpec,
        editor_role: Literal["primary", "alternate"],
        option_id: Literal["enter_circle", "remain_edge"],
    ) -> _ChildExecution:
        del editor_role, option_id
        _assert_no_model_modules()
        with tempfile.TemporaryDirectory(
            prefix="rei-c4-stage1-dino-",
            dir=self._staging_parent,
        ) as temporary:
            temporary_root = Path(temporary).resolve(strict=True)
            output_root = temporary_root / "output"
            output_root.mkdir()
            request_path = temporary_root / "request.json"
            semantic_request = C4Stage1DinoSemanticChildRequest.create(
                self._preflight.prepared,
                image=image,
                call=call,
            )
            request_bytes = _child_request_payload(
                repository_root=self._repository_root,
                worker_python=self._worker_python,
                render_run_root=self._preflight.render_store.run_path(
                    self._preflight.prepared.run_id
                ),
                staging_root=output_root,
                snapshot=self._snapshot,
                prepared=self._preflight.prepared,
                image=image,
                call=call,
                bootstrap_bytes=self._bootstrap_bytes,
                worker_bytes=self._worker_bytes,
            )
            _safe_write_new(request_path, request_bytes)
            environment = build_c4_stage1_worker_environment(
                self._preflight.prepared.launch_policy
            )
            request = _child_process_request(
                repository_root=self._repository_root,
                worker_python=self._worker_python,
                bootstrap_path=self._bootstrap_path,
                request_path=request_path,
                transport_request_sha256=_sha256(request_bytes),
                semantic_request=semantic_request,
                environment=environment,
            )
            _assert_no_model_modules()
            bounded = BoundedProcessTreeRunner().run(request)
            encoding: VerifiedImageEncoding | None = None
            vector_bytes: bytes | None = None
            result_sha256: str | None = None
            if bounded.succeeded:
                try:
                    encoding, vector_bytes, result_sha256 = _inspect_child_output(
                        output_root,
                        image=image,
                        call=call,
                    )
                except Exception:
                    encoding = None
                    vector_bytes = None
                    result_sha256 = None
            return _ChildExecution(
                record=bounded.record,
                semantic_request=semantic_request,
                transport_request_sha256=_sha256(request_bytes),
                child_result_sha256=result_sha256,
                bootstrap_script_sha256=_sha256(self._bootstrap_bytes),
                bootstrap_script_size_bytes=len(self._bootstrap_bytes),
                worker_script_sha256=_sha256(self._worker_bytes),
                worker_script_size_bytes=len(self._worker_bytes),
                encoding=encoding,
                vector_bytes=vector_bytes,
            )


def _persist_child_execution(
    preflight: _DinoPreflight,
    ledger: _DinoInventoryLedger,
    execution: _ChildExecution,
    *,
    image: ImageArtifact,
    call: ProviderCallSpec,
    editor_role: Literal["primary", "alternate"],
    option_id: Literal["enter_circle", "remain_edge"],
) -> tuple[VerifiedImageEncoding, bytes, C4Stage1DinoProcessEvidence]:
    expected_semantic = C4Stage1DinoSemanticChildRequest.create(
        preflight.prepared,
        image=image,
        call=call,
    )
    bootstrap_pin, worker_pin = preflight.prepared.dino_entrypoint_pin.scripts
    record = execution.record
    try:
        transport_digest_is_valid = (
            len(execution.transport_request_sha256) == 64
            and int(execution.transport_request_sha256, 16) >= 0
        )
    except (TypeError, ValueError):
        transport_digest_is_valid = False
    if (
        execution.semantic_request != expected_semantic
        or not transport_digest_is_valid
        or execution.bootstrap_script_sha256 != bootstrap_pin.content_sha256
        or execution.bootstrap_script_size_bytes != bootstrap_pin.size_bytes
        or execution.worker_script_sha256 != worker_pin.content_sha256
        or execution.worker_script_size_bytes != worker_pin.size_bytes
        or record.workload_id != _dino_workload_identity(expected_semantic)
        or record.command_identity
        != _dino_command_identity(
            expected_semantic,
            transport_request_sha256=execution.transport_request_sha256,
        )
        or record.working_directory_identity
        != _dino_working_directory_identity(expected_semantic)
        or record.environment_identity
        != _dino_environment_policy_identity(expected_semantic)
        or record.argument_count != 5
    ):
        raise C4Stage1DinoRunError(
            "Stage 1 DINO child process differs from its semantic request"
        )
    process_storage = preflight.dino_store.write_json(
        preflight.dino_run_id,
        f"diagnostics/{execution.record.command_identity}{_DINO_PROCESS_SUFFIX}",
        execution.record,
        overwrite=False,
    )
    ledger.add(process_storage)
    encoding = execution.encoding
    vector_bytes = execution.vector_bytes
    if (
        execution.record.status != "succeeded"
        or execution.record.timeout_seconds != C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS
        or encoding is None
        or vector_bytes is None
        or execution.child_result_sha256 is None
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO isolated child did not complete")
    if (
        encoding.call_spec != call
        or encoding.call.call_id != call.call_id
        or encoding.image_id != image.image_id
        or encoding.request.image_content_sha256 != image.content_sha256
        or encoding.request.provider != dinov2_base_provider_identity()
        or encoding.request.spec
        != dinov2_base_encoding_spec(
            snapshot_manifest_sha256=C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
            device="cuda",
        )
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO child substituted its encoding")
    _, vector_sha256 = verified_float32_le_vector(
        vector_bytes,
        expected_dimensions=DINOV2_BASE_DIMENSIONS,
    )
    if (
        encoding.vector_ref != f"{_DINO_VECTOR_PREFIX}{encoding.vector_hash}.f32"
        or vector_sha256 != encoding.vector_hash
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO child vector differs from evidence")
    previous_vector = ledger.descriptors.get(encoding.vector_ref)
    if previous_vector is None:
        vector_storage = preflight.dino_store.write_bytes(
            preflight.dino_run_id,
            encoding.vector_ref,
            vector_bytes,
            overwrite=False,
        )
        ledger.add(vector_storage)
    elif preflight.dino_store.read_verified(previous_vector) != vector_bytes:
        raise C4Stage1DinoRunError("DINO content-addressed vector path changed bytes")
    evidence = C4Stage1DinoProcessEvidence(
        dino_run_id=preflight.dino_run_id,
        editor_role=editor_role,
        option_id=option_id,
        image_artifact_id=image.image_id,
        provider_call_id=call.call_id,
        encoding_artifact_id=encoding.encoding_id,
        vector_sha256=encoding.vector_hash,
        semantic_request=expected_semantic,
        transport_request_sha256=execution.transport_request_sha256,
        child_result_sha256=execution.child_result_sha256,
        bootstrap_script_sha256=execution.bootstrap_script_sha256,
        bootstrap_script_size_bytes=execution.bootstrap_script_size_bytes,
        worker_script_sha256=execution.worker_script_sha256,
        worker_script_size_bytes=execution.worker_script_size_bytes,
        process_execution_record=execution.record,
        process_execution_storage=process_storage,
    )
    return encoding, vector_bytes, evidence


def _verify_render_unchanged(preflight: _DinoPreflight) -> None:
    try:
        observed = cold_verify_c4_stage1_run(
            FileArtifactStore(preflight.render_store.root, create=False),
            preflight.render_anchor_storage,
        )
    except Exception as exc:
        raise C4Stage1DinoRunError(
            "Stage 1 render evidence changed during DINO"
        ) from exc
    if observed != preflight.render_outcome:
        raise C4Stage1DinoRunError("Stage 1 render cold replay changed during DINO")


def _run_with_child_executor(
    preflight: _DinoPreflight,
    executor: _ChildExecutor,
) -> C4Stage1DinoRunOutcome:
    """Testing seam entered only after all model-free production preconditions."""

    _assert_no_model_modules()
    if not _run_path_absent(preflight.dino_store, preflight.dino_run_id):
        raise C4Stage1DinoRunError("Stage 1 DINO run is no longer fresh")
    ledger = _DinoInventoryLedger(preflight.dino_store, preflight.dino_run_id)
    family_encodings: list[tuple[VerifiedImageEncoding, VerifiedImageEncoding]] = []
    family_vectors: list[tuple[bytes, bytes]] = []
    family_processes: list[
        tuple[C4Stage1DinoProcessEvidence, C4Stage1DinoProcessEvidence]
    ] = []
    for family_index, images in enumerate(preflight.images):
        role: Literal["primary", "alternate"] = ("primary", "alternate")[family_index]
        encodings: list[VerifiedImageEncoding] = []
        vectors: list[bytes] = []
        processes: list[C4Stage1DinoProcessEvidence] = []
        for option_index, image in enumerate(images):
            option: Literal["enter_circle", "remain_edge"] = (
                "enter_circle",
                "remain_edge",
            )[option_index]
            _assert_no_model_modules()
            call = _build_encoding_call(image)
            execution = executor.execute(
                image=image,
                call=call,
                editor_role=role,
                option_id=option,
            )
            encoding, vector, process = _persist_child_execution(
                preflight,
                ledger,
                execution,
                image=image,
                call=call,
                editor_role=role,
                option_id=option,
            )
            encodings.append(encoding)
            vectors.append(vector)
            processes.append(process)
            _verify_render_unchanged(preflight)
        family_encodings.append((encodings[0], encodings[1]))
        family_vectors.append((vectors[0], vectors[1]))
        family_processes.append((processes[0], processes[1]))

    results: list[C4Stage1DinoPairResult] = []
    for family_index in range(2):
        result = dino_bridge.build_c4_stage1_dino_pair_result(
            preflight.render_store,
            preflight.prepared_storage,
            preflight.publication_storages[family_index],
            encodings=family_encodings[family_index],
            vector_bytes=family_vectors[family_index],
        )
        if result.editor_role != ("primary", "alternate")[family_index]:
            raise C4Stage1DinoRunError("Stage 1 DINO comparison order changed")
        results.append(result)
    result_storages: list[StoredArtifact] = []
    for result in results:
        storage = preflight.dino_store.write_json(
            preflight.dino_run_id,
            _pair_path(result),
            result,
            overwrite=False,
        )
        ledger.add(storage)
        result_storages.append(storage)
    families = tuple(
        C4Stage1DinoFamilyEvidence.create(
            result,
            storage,
            family_processes[index],
            dino_run_id=preflight.dino_run_id,
        )
        for index, (result, storage) in enumerate(
            zip(results, result_storages, strict=True)
        )
    )
    before_anchor = ledger.snapshot()
    anchor = C4Stage1DinoCollapseCheckAnchor.create(
        preflight=preflight,
        families=(families[0], families[1]),
        artifact_inventory_before_anchor=before_anchor,
    )
    anchor_storage = preflight.dino_store.write_json(
        preflight.dino_run_id,
        C4_STAGE1_DINO_ANCHOR_PATH,
        anchor,
        overwrite=False,
    )
    ledger.add(anchor_storage)
    verified = cold_verify_c4_stage1_dino_collapse_check(
        preflight.render_store,
        preflight.dino_store,
        anchor_storage,
    )
    _verify_render_unchanged(preflight)
    if verified != anchor:
        raise C4Stage1DinoRunError("Stage 1 DINO cold replay changed the anchor")
    return C4Stage1DinoRunOutcome(anchor=anchor, anchor_storage=anchor_storage)


def run_c4_stage1_dino_collapse_check(
    render_artifact_store: FileArtifactStore,
    dino_artifact_store: FileArtifactStore,
    render_inventory_anchor_storage: StoredArtifact,
    member_publication_receipt_storages: tuple[StoredArtifact, StoredArtifact],
    *,
    dino_run_id: str,
    confirmed_prepared_attempt_id: str,
    confirmed_dino_policy_id: str,
    repository_root: str | Path,
    worker_python: str | Path,
    snapshot_path: str | Path,
    staging_parent: str | Path,
) -> C4Stage1DinoRunOutcome:
    """Execute four exact, isolated collapse-check encodings."""

    _assert_no_model_modules()
    preflight = _preflight(
        render_artifact_store,
        dino_artifact_store,
        render_inventory_anchor_storage,
        member_publication_receipt_storages,
        dino_run_id=dino_run_id,
        confirmed_prepared_attempt_id=confirmed_prepared_attempt_id,
        confirmed_dino_policy_id=confirmed_dino_policy_id,
    )
    repository = Path(repository_root)
    _verify_actual_repository_root(repository, preflight.prepared)
    runtime = _verify_current_worker_runtime(
        Path(worker_python),
        preflight.prepared.worker_runtime,
    )
    snapshot = verify_c4_stage1_dino_snapshot(snapshot_path)
    staging = verify_c4_stage1_staging_parent(staging_parent)
    base_runtime = _worker_base_runtime_root(runtime, preflight.prepared)
    staging_path = _verify_external_staging_parent(
        staging,
        repository_root=repository.resolve(strict=True),
        worker_python=runtime,
        base_runtime_root=base_runtime,
        snapshot=snapshot,
        preflight=preflight,
    )
    _verify_render_unchanged(preflight)
    _assert_no_model_modules()
    executor = _ProductionChildExecutor(
        preflight,
        repository_root=repository.resolve(strict=True),
        worker_python=runtime,
        snapshot=snapshot,
        staging_parent=staging_path,
    )
    return _run_with_child_executor(preflight, executor)


def cold_verify_c4_stage1_dino_collapse_check(
    render_artifact_store: FileArtifactStore,
    dino_artifact_store: FileArtifactStore,
    anchor_storage: StoredArtifact,
) -> C4Stage1DinoCollapseCheckAnchor:
    """Cold-replay the DINO run and its still-immutable render input."""

    if not isinstance(render_artifact_store, FileArtifactStore) or not isinstance(
        dino_artifact_store, FileArtifactStore
    ):
        raise TypeError("Stage 1 DINO replay requires two FileArtifactStore instances")
    storage = _stored(anchor_storage, label="anchor_storage")
    if storage.relative_path != C4_STAGE1_DINO_ANCHOR_PATH:
        raise C4Stage1DinoRunError("Stage 1 DINO anchor has the wrong path")
    render_store = FileArtifactStore(render_artifact_store.root, create=False)
    dino_store = FileArtifactStore(dino_artifact_store.root, create=False)
    try:
        payload = dino_store.read_verified(storage)
        anchor = C4Stage1DinoCollapseCheckAnchor.model_validate_json(payload)
        dino_inventory = dino_store.inspect_run_inventory_exact(anchor.dino_run_id)
        render_outcome = cold_verify_c4_stage1_run(
            render_store,
            anchor.render_inventory_anchor_storage,
        )
        render_inventory = render_store.inspect_run_inventory_exact(
            anchor.render_run_id
        )
    except Exception as exc:
        raise C4Stage1DinoRunError("Stage 1 DINO anchor failed cold parsing") from exc
    expected_dino_inventory = tuple(
        sorted(
            (*anchor.artifact_inventory_before_anchor, storage),
            key=lambda item: item.relative_path,
        )
    )
    if (
        canonical_json_bytes(anchor) != payload
        or storage.run_id != anchor.dino_run_id
        or storage.content_sha256 != _sha256(payload)
        or storage.size_bytes != len(payload)
        or dino_inventory != expected_dino_inventory
        or storage in anchor.artifact_inventory_before_anchor
        or render_outcome.inventory_anchor_storage
        != anchor.render_inventory_anchor_storage
        or render_outcome.inventory_anchor.render_inventory_anchor_id
        != anchor.render_inventory_anchor_id
        or render_outcome.inventory_anchor.render_inventory_anchor_sha256
        != anchor.render_inventory_anchor_sha256
        or render_inventory != anchor.render_artifact_inventory
        or render_outcome.manifest.run_id != anchor.render_run_id
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO final inventories differ from anchor")

    try:
        prepared = dino_bridge._cold_publication(
            render_store,
            anchor.prepared_anchor_storage,
            anchor.families[0].member_publication_receipt_storage,
        )[1]
    except Exception as exc:
        raise C4Stage1DinoRunError(
            "Stage 1 DINO prepared runtime lineage failed cold replay"
        ) from exc
    if (
        prepared.run_id != anchor.render_run_id
        or prepared.prepared_attempt_id != anchor.prepared_attempt_id
        or prepared.prepared_attempt_sha256 != anchor.prepared_attempt_sha256
        or prepared.worker_runtime.worker_runtime_id != anchor.worker_runtime_id
        or prepared.worker_runtime.worker_runtime_sha256 != anchor.worker_runtime_sha256
        or prepared.screen_contract.dino_policy.encoder != anchor.encoder
        or prepared.screen_contract.dino_policy.encoder_spec_sha256
        != anchor.encoder_spec_sha256
    ):
        raise C4Stage1DinoRunError("Stage 1 DINO anchor differs from prepared lineage")

    before_by_path = {
        item.relative_path: item for item in anchor.artifact_inventory_before_anchor
    }
    for family in anchor.families:
        try:
            result_payload = dino_store.read_verified(family.dino_pair_result_storage)
            result = C4Stage1DinoPairResult.model_validate_json(result_payload)
        except Exception as exc:
            raise C4Stage1DinoRunError("Stage 1 DINO pair failed cold parsing") from exc
        vector_payloads: list[bytes] = []
        for process, output in zip(family.processes, result.outputs, strict=True):
            expected_semantic_request = C4Stage1DinoSemanticChildRequest.create(
                prepared,
                image=output.image,
                call=output.encoding.call_spec,
            )
            if process.semantic_request != expected_semantic_request:
                raise C4Stage1DinoRunError(
                    "Stage 1 DINO semantic child request changed"
                )
            descriptor = before_by_path.get(output.encoding.vector_ref)
            if descriptor is None:
                raise C4Stage1DinoRunError("Stage 1 DINO vector is absent")
            vector_payloads.append(dino_store.read_verified(descriptor))
            try:
                process_payload = dino_store.read_verified(
                    process.process_execution_storage
                )
                observed_process = ProcessTreeExecutionRecord.model_validate_json(
                    process_payload
                )
            except Exception as exc:
                raise C4Stage1DinoRunError(
                    "Stage 1 DINO process record failed cold replay"
                ) from exc
            if (
                canonical_json_bytes(observed_process) != process_payload
                or observed_process != process.process_execution_record
            ):
                raise C4Stage1DinoRunError("Stage 1 DINO process record changed")
        encodings = tuple(output.encoding for output in result.outputs)
        replayed = dino_bridge.verify_c4_stage1_dino_pair_result(
            result,
            artifact_store=render_store,
            prepared_anchor_storage=anchor.prepared_anchor_storage,
            member_publication_receipt_storage=family.member_publication_receipt_storage,
            encodings=(encodings[0], encodings[1]),
            vector_bytes=(vector_payloads[0], vector_payloads[1]),
        )
        if (
            result_payload != result.canonical_json_bytes()
            or result != family.dino_pair_result
            or replayed != result
        ):
            raise C4Stage1DinoRunError("Stage 1 DINO pair differs from cold replay")
    return anchor


__all__ = [
    "C4_STAGE1_DINO_ANCHOR_PATH",
    "C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH",
    "C4_STAGE1_DINO_CALL_TIMEOUT_SECONDS",
    "C4_STAGE1_DINO_WORKER_SCRIPT_PATH",
    "C4Stage1DinoCollapseCheckAnchor",
    "C4Stage1DinoFamilyEvidence",
    "C4Stage1DinoProcessEvidence",
    "C4Stage1DinoRunError",
    "C4Stage1DinoRunOutcome",
    "C4Stage1DinoSemanticChildRequest",
    "cold_verify_c4_stage1_dino_collapse_check",
    "run_c4_stage1_dino_collapse_check",
    "verify_c4_stage1_dino_snapshot",
]
