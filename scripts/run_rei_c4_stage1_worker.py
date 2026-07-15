"""Execute one bootstrap-authorized C4 Stage 1 option create-only.

Direct CLI execution is deliberately inert.  The secure ``-I -S`` bootstrap
loads this source with a process-local capability and passes one already
verified authorization object.  REI and provider modules are imported only
inside that authorized path.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys
from typing import Any


sys.dont_write_bytecode = True

_RESULT_FILENAME = "worker_result.json"
_DIRECT_FILENAME = "direct.png"
_STAGED_FILENAME = "staged.png"
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_MAX_SCRIPT_BYTES = 4 * 1024 * 1024
_MODEL_MODULE_ROOTS = frozenset(
    {"accelerate", "diffusers", "safetensors", "torch", "transformers"}
)
_BOOTSTRAP_CAPABILITY = globals().pop("_REI_C4_STAGE1_BOOTSTRAP_CAPABILITY", None)
_AUTHORIZATION_CONSUMED = False


class C4Stage1WorkerAuthorizationError(RuntimeError):
    """Fixed, path-free rejection of a missing or inconsistent capability."""


def _fail() -> C4Stage1WorkerAuthorizationError:
    return C4Stage1WorkerAuthorizationError("C4 Stage 1 worker authorization failed")


def _assert_no_model_modules() -> None:
    if any(name.split(".", 1)[0] in _MODEL_MODULE_ROOTS for name in sys.modules):
        raise _fail()


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_unlinked_ancestry(path: Path) -> None:
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise _fail()
    parts = path.parts
    if not parts:
        raise _fail()
    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise _fail() from exc
        if _is_link_or_reparse(metadata):
            raise _fail()


def _stable_read(path: Path, *, maximum_bytes: int) -> bytes:
    _assert_unlinked_ancestry(path)
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise _fail() from exc
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size < 0
        or before.st_size > maximum_bytes
    ):
        raise _fail()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _fail() from exc
    payload = bytearray()
    opened: os.stat_result | None = None
    final_handle: os.stat_result | None = None
    try:
        opened = os.fstat(descriptor)
        if (
            _is_link_or_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or not os.path.samestat(before, opened)
        ):
            raise _fail()
        while True:
            chunk = os.read(
                descriptor, min(1024 * 1024, maximum_bytes + 1 - len(payload))
            )
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > maximum_bytes:
                raise _fail()
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise _fail() from exc
    if (
        opened is None
        or final_handle is None
        or _is_link_or_reparse(after)
        or not stat.S_ISREG(after.st_mode)
        or opened.st_nlink != 1
        or final_handle.st_nlink != 1
        or after.st_nlink != 1
        or not os.path.samestat(opened, final_handle)
        or not os.path.samestat(opened, after)
        or opened.st_size != len(payload)
    ):
        raise _fail()
    return bytes(payload)


def _fresh_staging_root(value: Path) -> Path:
    _assert_unlinked_ancestry(value)
    try:
        before = os.lstat(value)
        first = tuple(sorted(entry.name for entry in os.scandir(value)))
    except OSError as exc:
        raise _fail() from exc
    if _is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode) or first:
        raise _fail()
    try:
        after = os.lstat(value)
        second = tuple(sorted(entry.name for entry in os.scandir(value)))
    except OSError as exc:
        raise _fail() from exc
    if (
        _is_link_or_reparse(after)
        or not os.path.samestat(before, after)
        or first != second
    ):
        raise _fail()
    return value


def _write_new(path: Path, value: bytes) -> None:
    if type(value) is not bytes:
        raise TypeError("C4 Stage 1 staged output must be immutable bytes")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(path, flags, 0o600)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise _fail()
        view = memoryview(value)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("C4 Stage 1 create-only write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise _fail() from exc
    if (
        _is_link_or_reparse(after)
        or not stat.S_ISREG(after.st_mode)
        or after.st_nlink != 1
        or final_handle.st_nlink != 1
        or not os.path.samestat(final_handle, after)
        or final_handle.st_size != len(value)
    ):
        raise _fail()


def _execute(request: Any, source_png: bytes, snapshot_path: Path) -> Any:
    """Lazy provider dispatch; imports happen only after full authorization."""

    from rei.emocio.c4_stage1_editor import C4Stage1LocalSnapshotBinding

    binding = C4Stage1LocalSnapshotBinding.create(request.editor_spec, snapshot_path)
    if request.editor_spec.editor_role == "primary":
        from rei.emocio.longcat_turbo_editor import run_longcat_turbo_stage1_lazy

        _assert_no_model_modules()
        return run_longcat_turbo_stage1_lazy(
            request,
            source_png,
            binding=binding,
        )
    if request.editor_spec.editor_role == "alternate":
        from rei.emocio.omnigen_editor import run_omnigen_stage1_lazy

        _assert_no_model_modules()
        return run_omnigen_stage1_lazy(
            request,
            source_png,
            binding=binding,
        )
    raise _fail()


def _consume_authorization(authorization: object) -> None:
    global _AUTHORIZATION_CONSUMED
    if (
        _AUTHORIZATION_CONSUMED
        or _BOOTSTRAP_CAPABILITY is None
        or getattr(authorization, "_capability", None) is not _BOOTSTRAP_CAPABILITY
    ):
        raise _fail()
    _AUTHORIZATION_CONSUMED = True


def _validate_authorized_lineage(authorization: object) -> tuple[Any, ...]:
    if not sys.flags.isolated or not sys.flags.no_site or not sys.flags.safe_path:
        raise _fail()
    _assert_no_model_modules()

    from rei.emocio.c4_stage1_editor import (
        C4Stage1LocalSnapshotBinding,
        C4Stage1WorkerRequest,
        inspect_c4_stage1_png_bytes,
        verify_c4_stage1_snapshot,
    )
    from rei.evaluation.c4_stage1_attempt import C4Stage1PreparedAttempt
    from rei.evaluation.c4_stage1_run import C4Stage1LaunchEnvelope
    from rei.evaluation.c4_stage1_telemetry import C4Stage1TelemetryIntent

    _assert_no_model_modules()
    prepared = C4Stage1PreparedAttempt.model_validate(
        authorization.prepared.model_dump(mode="python", round_trip=True)
    )
    envelope = C4Stage1LaunchEnvelope.model_validate(
        authorization.envelope.model_dump(mode="python", round_trip=True)
    )
    intent = C4Stage1TelemetryIntent.model_validate(
        authorization.intent.model_dump(mode="python", round_trip=True)
    )
    request = C4Stage1WorkerRequest.model_validate(
        authorization.request.model_dump(mode="python", round_trip=True)
    )
    source_png = authorization.source_png
    snapshot_path = Path(authorization.snapshot_path)
    staging_root = Path(authorization.staging_root)
    repository_root = Path(authorization.repository_root)
    worker_path = Path(authorization.worker_path)
    if type(source_png) is not bytes:
        raise _fail()
    workers = [
        item
        for item in prepared.workers
        if item.prepared_worker_id == envelope.prepared_worker_id
    ]
    if len(workers) != 1:
        raise _fail()
    worker = workers[0]
    source = request.render_request.source_image
    provider_slots = [
        policy.candidate_slot_id
        for policy in prepared.review_operator_policies
        if policy.policy_id == worker.operator_policy_id
    ]
    if source is None or len(provider_slots) != 1:
        raise _fail()
    pipeline_id = __import__("rei.ids", fromlist=["content_id"]).content_id(
        "c4_stage1_pipeline_spec", request.editor_spec.pipeline
    )
    snapshot_manifest_id = __import__("rei.ids", fromlist=["content_id"]).content_id(
        "c4_stage1_snapshot_manifest",
        {
            "editor_role": request.editor_spec.editor_role,
            "verified_snapshot_id": request.verified_snapshot.verified_snapshot_id,
            "manifest_sha256": request.editor_spec.snapshot_manifest_sha256,
        },
    )
    if (
        prepared.prepared_attempt_id != envelope.prepared_attempt_id
        or prepared.prepared_attempt_sha256 != envelope.prepared_attempt_sha256
        or prepared.attempt_id != envelope.attempt_id
        or prepared.repository_gate.repository_gate_id != envelope.repository_gate_id
        or prepared.repository_gate.repository_gate_sha256
        != envelope.repository_gate_sha256
        or prepared.launch_policy.launch_policy_id != envelope.launch_policy_id
        or prepared.launch_policy.launch_policy_sha256 != envelope.launch_policy_sha256
        or prepared.worker_runtime.worker_runtime_id != envelope.worker_runtime_id
        or prepared.worker_runtime.worker_runtime_sha256
        != envelope.worker_runtime_sha256
        or prepared.cuda_device != envelope.cuda_device
        or prepared.source_provenance_sha256 != envelope.source_provenance_sha256
        or worker.worker_request != request
        or worker.content_hash() != envelope.prepared_worker_sha256
        or request.worker_request_id != envelope.worker_request_id
        or request.content_hash() != envelope.worker_request_sha256
        or worker.editor_role != envelope.editor_role
        or worker.option_id != envelope.option_id
        or provider_slots[0] != envelope.provider_slot_id
        or request.editor_spec.provider.provider_id != envelope.provider_id
        or request.editor_spec.spec_id != envelope.editor_spec_id
        or request.editor_spec.content_hash() != envelope.editor_spec_sha256
        or pipeline_id != envelope.pipeline_spec_id
        or request.editor_spec.pipeline.content_hash() != envelope.pipeline_spec_sha256
        or request.verified_snapshot.verified_snapshot_id
        != envelope.verified_snapshot_id
        or snapshot_manifest_id != envelope.snapshot_manifest_id
        or request.editor_spec.snapshot_manifest_sha256
        != envelope.snapshot_manifest_sha256
        or source.image_id != envelope.source_artifact_id
        or source.content_sha256 != envelope.source_sha256
        or intent.intent_id != envelope.telemetry_intent_id
        or intent.intent_sha256 != envelope.telemetry_intent_sha256
        or intent.worker_request_id != request.worker_request_id
        or intent.worker_request_sha256 != request.content_hash()
        or intent.process_request != envelope.process_request
        or os.environ.get("CUDA_VISIBLE_DEVICES")
        != envelope.cuda_device.physical_gpu_uuid
        or envelope.cuda_device.logical_device_index != 0
        or envelope.exact_prepared_attempt_confirmation is not True
    ):
        raise _fail()
    if hashlib.sha256(
        source_png
    ).hexdigest() != source.content_sha256 or inspect_c4_stage1_png_bytes(
        source_png
    ) != (source.width, source.height):
        raise _fail()
    _assert_unlinked_ancestry(repository_root)
    if worker_path != repository_root / "scripts" / "run_rei_c4_stage1_worker.py":
        raise _fail()
    worker_bytes = _stable_read(worker_path, maximum_bytes=_MAX_SCRIPT_BYTES)
    bootstrap_bytes = _stable_read(
        repository_root / "scripts" / "run_rei_c4_stage1_bootstrap.py",
        maximum_bytes=_MAX_SCRIPT_BYTES,
    )
    if (
        hashlib.sha256(worker_bytes).hexdigest() != authorization.worker_sha256
        or authorization.worker_sha256 != envelope.worker_script_sha256
        or len(worker_bytes) != envelope.worker_script_size_bytes
        or hashlib.sha256(bootstrap_bytes).hexdigest() != authorization.bootstrap_sha256
        or authorization.bootstrap_sha256 != envelope.bootstrap_script_sha256
        or len(bootstrap_bytes) != envelope.bootstrap_script_size_bytes
    ):
        raise _fail()
    binding = C4Stage1LocalSnapshotBinding.create(request.editor_spec, snapshot_path)
    if (
        verify_c4_stage1_snapshot(request.editor_spec, binding)
        != request.verified_snapshot
    ):
        raise _fail()
    staging = _fresh_staging_root(staging_root)
    _assert_no_model_modules()
    return request, source_png, snapshot_path, staging


def run_authorized(authorization: object) -> int:
    """Consume one bootstrap capability, validate again, and invoke one provider."""

    _consume_authorization(authorization)
    request: Any | None = None
    staging: Path | None = None
    try:
        request, source_png, snapshot_path, staging = _validate_authorized_lineage(
            authorization
        )
        execution = _execute(request, source_png, snapshot_path)
        result = execution.worker_result
        _write_new(staging / _DIRECT_FILENAME, execution.output.direct_png)
        _write_new(staging / _STAGED_FILENAME, execution.output.staged_png)
        _write_new(staging / _RESULT_FILENAME, result.canonical_json_bytes())
        return 0
    except BaseException as exc:
        if request is not None and staging is not None:
            try:
                from rei.emocio.c4_stage1_editor import C4Stage1WorkerResult

                failure = C4Stage1WorkerResult.failed(
                    request,
                    failure_code="provider_execution_failed",
                )
                _write_new(staging / _RESULT_FILENAME, failure.canonical_json_bytes())
            except BaseException:
                pass
        if not isinstance(exc, Exception):
            raise
        return 20


def main(argv: list[str] | None = None) -> int:
    """Reject every direct invocation without parsing paths or importing REI."""

    del argv
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
