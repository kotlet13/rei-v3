"""Authorize one C4 Stage 1 worker before Python activates the model runtime.

This entry point is intentionally launched as ``python -I -S``.  Everything up
to :func:`_activate_verified_runtime` uses only the standard library.  The
bootstrap verifies the complete launch ledger, repository, scripts,
interpreter, virtual environment, base runtime, source and model snapshot
before it adds the already-verified site-packages directory to ``sys.path``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import sysconfig
import types
from typing import Any, Literal


sys.dont_write_bytecode = True

_MAX_JSON_BYTES = 16 * 1024 * 1024
_MAX_SOURCE_BYTES = 64 * 1024 * 1024
_MAX_SCRIPT_BYTES = 4 * 1024 * 1024
_MAX_EXECUTABLE_BYTES = 64 * 1024 * 1024
_MAX_SNAPSHOT_MANIFEST_BYTES = 16 * 1024 * 1024
_MAX_RUNTIME_FILES = 2_000_000
_MAX_RUNTIME_DIRECTORIES = 500_000
_MAX_RUNTIME_BYTES = 128 * 1024 * 1024 * 1024
_READ_CHUNK_BYTES = 4 * 1024 * 1024
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_ORIGIN_URL = "https://github.com/kotlet13/rei-v3.git"
_BOOTSTRAP_RELATIVE_PATH = "scripts/run_rei_c4_stage1_bootstrap.py"
_WORKER_RELATIVE_PATH = "scripts/run_rei_c4_stage1_worker.py"
_PREPARED_ANCHOR_RELATIVE_PATH = "diagnostics/c4_stage1_prepared_attempt.json"
_SNAPSHOT_MANIFEST_FILENAME = ".rei_snapshot_manifest.json"
_RUNTIME_INVENTORY_POLICY = "complete-venv-and-base-runtime-streaming-sha256-v1"
_RUNTIME_TREE_POLICY = "stable-streaming-sha256-all-regular-files-and-directories-v1"
_MODEL_MODULE_ROOTS = frozenset(
    {"accelerate", "diffusers", "safetensors", "torch", "transformers"}
)
_RUN_TREE_DIRECTORIES = frozenset(
    {
        "scene",
        "native",
        "emocio",
        "emocio/scenes",
        "emocio/images",
        "instinkt",
        "communication",
        "governance",
        "conscious",
        "behavior",
        "ego",
        "diagnostics",
    }
)
_OPTIONAL_RUN_TREE_DIRECTORIES = frozenset({"emocio/embeddings"})
_GIT_SCOPE_PATHS = (
    "app/backend/rei",
    ":(glob)scripts/run_rei_c4_stage1*.py",
    ":(glob)tests/evaluation/test_c4_stage1*.py",
    "tests/evaluation/test_process_tree_runner.py",
    "tests/evaluation/test_resource_telemetry.py",
    ":(glob)tests/rei/test_c4_stage1*.py",
    "Docs/evals/semantic_lab_v1/c4_visual_remediation_protocol_2026-07-15.md",
    "Docs/evals/semantic_lab_v1/c4_stage1_model_free_integration_addendum_2026-07-15.md",
    "Docs/evals/semantic_lab_v1/c4-stage1-preflight-2026-07-15/longcat_turbo_snapshot_manifest.json",
    "Docs/evals/semantic_lab_v1/c4-stage1-preflight-2026-07-15/omnigen_snapshot_manifest.json",
)
_EXPECTED_ARGUMENT_NAMES = (
    "--launch-envelope",
    "--prepared-anchor-storage-id",
    "--request",
    "--source-png",
    "--snapshot",
    "--staging-root",
)
_STORAGE_ID_PATTERN = re.compile(r"^stored_[0-9a-f]{32}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CONTENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class C4Stage1BootstrapError(RuntimeError):
    """A fixed, path-free bootstrap rejection."""


class _C4Stage1BootstrapAuthorization:
    """Single-use capability and independently validated worker inputs."""

    __slots__ = (
        "_capability",
        "prepared",
        "envelope",
        "intent",
        "request",
        "source_png",
        "snapshot_path",
        "staging_root",
        "repository_root",
        "worker_path",
        "bootstrap_sha256",
        "worker_sha256",
    )

    def __init__(
        self,
        *,
        capability: object,
        prepared: object,
        envelope: object,
        intent: object,
        request: object,
        source_png: bytes,
        snapshot_path: Path,
        staging_root: Path,
        repository_root: Path,
        worker_path: Path,
        bootstrap_sha256: str,
        worker_sha256: str,
    ) -> None:
        self._capability = capability
        self.prepared = prepared
        self.envelope = envelope
        self.intent = intent
        self.request = request
        self.source_png = source_png
        self.snapshot_path = snapshot_path
        self.staging_root = staging_root
        self.repository_root = repository_root
        self.worker_path = worker_path
        self.bootstrap_sha256 = bootstrap_sha256
        self.worker_sha256 = worker_sha256


class _StdlibVerifiedLaunch:
    """Path-bearing state that is never serialized into a portable artifact."""

    __slots__ = (
        "arguments",
        "repository_root",
        "run_root",
        "site_roots",
        "envelope_bytes",
        "envelope_data",
        "anchor_bytes",
        "anchor_data",
        "request_bytes",
        "request_data",
        "intent_bytes",
        "intent_data",
        "source_png",
        "bootstrap_bytes",
        "worker_bytes",
    )

    def __init__(self, **values: object) -> None:
        for name in self.__slots__:
            setattr(self, name, values[name])


def _fail() -> C4Stage1BootstrapError:
    return C4Stage1BootstrapError("C4 Stage 1 bootstrap authorization failed")


def _assert_no_model_modules() -> None:
    if any(name.split(".", 1)[0] in _MODEL_MODULE_ROOTS for name in sys.modules):
        raise _fail()


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise _fail() from exc


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if type(key) is not str or key in result:
            raise _fail()
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise _fail()


def _parse_canonical_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise _fail() from exc
    if type(value) is not dict or _canonical_json_bytes(value) != raw:
        raise _fail()
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _content_id(prefix: str, value: object) -> str:
    if not _CONTENT_ID_PATTERN.fullmatch(prefix):
        raise _fail()
    return f"{prefix}_{_sha256(_canonical_json_bytes(value))[:32]}"


def _content_body(
    value: dict[str, Any],
    *,
    id_name: str,
    hash_name: str | None,
    prefix: str,
) -> dict[str, Any]:
    body = dict(value)
    artifact_id = body.pop(id_name, None)
    artifact_hash = body.pop(hash_name, None) if hash_name is not None else None
    canonical_hash = _sha256(_canonical_json_bytes(body))
    if artifact_id != _content_id(prefix, body):
        raise _fail()
    if hash_name is not None and artifact_hash != canonical_hash:
        raise _fail()
    return body


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_absolute_lexical(path: Path) -> None:
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise _fail()


def _assert_unlinked_ancestry(path: Path) -> None:
    _assert_absolute_lexical(path)
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
            remaining = maximum_bytes + 1 - len(payload)
            chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, remaining))
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
        or before.st_nlink != 1
        or opened.st_nlink != 1
        or final_handle.st_nlink != 1
        or after.st_nlink != 1
        or not os.path.samestat(opened, final_handle)
        or not os.path.samestat(opened, after)
        or opened.st_size != len(payload)
        or final_handle.st_size != len(payload)
        or after.st_size != len(payload)
    ):
        raise _fail()
    return bytes(payload)


def _stable_hash(path: Path, *, expected_size: int, maximum_bytes: int) -> str:
    digest, size = _stable_digest(path, maximum_bytes=maximum_bytes)
    if size != expected_size:
        raise _fail()
    return digest


def _stable_digest(path: Path, *, maximum_bytes: int) -> tuple[str, int]:
    """Hash one stable regular file without retaining its potentially huge bytes."""

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
    digest = hashlib.sha256()
    size = 0
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
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
            if size > maximum_bytes:
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
        or opened.st_size != size
        or final_handle.st_size != size
        or after.st_size != size
    ):
        raise _fail()
    return digest.hexdigest(), size


def _parse_arguments(argv: list[str]) -> dict[str, object]:
    if len(argv) != 2 * len(_EXPECTED_ARGUMENT_NAMES):
        raise _fail()
    values: dict[str, object] = {}
    for index, expected in enumerate(_EXPECTED_ARGUMENT_NAMES):
        name, value = argv[index * 2 : index * 2 + 2]
        if name != expected or type(value) is not str or not value:
            raise _fail()
        key = expected.removeprefix("--").replace("-", "_")
        if expected == "--prepared-anchor-storage-id":
            if not _STORAGE_ID_PATTERN.fullmatch(value):
                raise _fail()
            values[key] = value
        else:
            path = Path(value)
            _assert_absolute_lexical(path)
            values[key] = path
    return values


def _runtime_commitment(domain: str, value: object) -> str:
    return _sha256(
        _canonical_json_bytes(
            {"domain": f"rei-c4-stage1-{domain}-commitment-v1", "value": value}
        )
    )


def _raw_command(argv: list[str]) -> tuple[str, ...]:
    if not sys.flags.isolated or not sys.flags.no_site or not sys.flags.safe_path:
        raise _fail()
    if sys.argv[0] != os.fspath(Path(__file__)):
        raise _fail()
    return (sys.executable, "-I", "-S", sys.argv[0], *argv)


def _validate_relative_path(value: object) -> str:
    if type(value) is not str or not value or len(value) > 4096:
        raise _fail()
    if (
        "\\" in value
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or any(ord(character) < 32 for character in value)
    ):
        raise _fail()
    return value


def _stored_artifact_id(descriptor: dict[str, Any]) -> str:
    payload = {
        "run_id": descriptor.get("run_id"),
        "relative_path": descriptor.get("relative_path"),
        "content_sha256": descriptor.get("content_sha256"),
        "size_bytes": descriptor.get("size_bytes"),
    }
    return _content_id("stored", payload)


def _validate_descriptor(
    descriptor: object,
    *,
    run_id: str,
    run_root: Path,
    expected_path: str | None = None,
    expected_bytes: bytes | None = None,
) -> tuple[dict[str, Any], bytes]:
    if type(descriptor) is not dict:
        raise _fail()
    value = descriptor
    relative = _validate_relative_path(value.get("relative_path"))
    if (
        set(value)
        != {
            "schema_version",
            "storage_id",
            "run_id",
            "relative_path",
            "content_sha256",
            "size_bytes",
        }
        or value.get("schema_version") != "rei-native-stored-artifact-v1"
        or value.get("run_id") != run_id
        or (expected_path is not None and relative != expected_path)
        or type(value.get("size_bytes")) is not int
        or value["size_bytes"] < 0
        or value["size_bytes"] > _MAX_SOURCE_BYTES
        or not isinstance(value.get("content_sha256"), str)
        or not _SHA256_PATTERN.fullmatch(value["content_sha256"])
        or value.get("storage_id") != _stored_artifact_id(value)
    ):
        raise _fail()
    path = run_root.joinpath(*relative.split("/"))
    raw = _stable_read(path, maximum_bytes=max(_MAX_JSON_BYTES, value["size_bytes"]))
    if (
        len(raw) != value["size_bytes"]
        or _sha256(raw) != value["content_sha256"]
        or (expected_bytes is not None and raw != expected_bytes)
    ):
        raise _fail()
    return value, raw


def _validate_envelope_shape(
    envelope: dict[str, Any],
    *,
    argv: list[str],
    environment: dict[str, str],
    cwd: str,
) -> None:
    _content_body(
        envelope,
        id_name="launch_envelope_id",
        hash_name="launch_envelope_sha256",
        prefix="c4_stage1_launch_envelope",
    )
    command = _raw_command(argv)
    process = envelope.get("process_request")
    cuda = envelope.get("cuda_device")
    if type(process) is not dict or type(cuda) is not dict:
        raise _fail()
    if (
        envelope.get("schema_version") != "rei-c4-stage1-launch-envelope-v1"
        or envelope.get("interpreter_isolation_flags") != ["-I", "-S"]
        or envelope.get("argument_count") != len(command) - 1
        or envelope.get("raw_argv_commitment_sha256")
        != _runtime_commitment("raw-argv", command)
        or envelope.get("raw_environment_commitment_sha256")
        != _runtime_commitment("raw-environment", sorted(environment.items()))
        or envelope.get("raw_working_directory_commitment_sha256")
        != _runtime_commitment("raw-working-directory", cwd)
        or process.get("workload_id") != envelope.get("workload_id")
        or process.get("command_identity") != envelope.get("command_identity")
        or process.get("working_directory_identity")
        != envelope.get("working_directory_identity")
        or process.get("environment_identity") != envelope.get("environment_identity")
        or process.get("argument_count") != envelope.get("argument_count")
        or cuda.get("status") != "resolved"
        or cuda.get("logical_device_index") != 0
        or not isinstance(cuda.get("physical_gpu_uuid"), str)
        or environment.get("CUDA_VISIBLE_DEVICES") != cuda.get("physical_gpu_uuid")
        or envelope.get("confirmed_prepared_attempt_id")
        != envelope.get("prepared_attempt_id")
        or envelope.get("exact_prepared_attempt_confirmation") is not True
        or envelope.get("bootstrap_cold_verification_required") is not True
        or envelope.get("worker_cold_verification_required") is not True
        or envelope.get("model_calls_before_envelope") != 0
        or envelope.get("semantic_authority_granted") is not False
        or envelope.get("production_authority_granted") is not False
        or envelope.get("local_paths_stored") is not False
        or envelope.get("raw_argv_stored") is not False
        or envelope.get("raw_environment_stored") is not False
        or envelope.get("raw_working_directory_stored") is not False
    ):
        raise _fail()


def _validate_prepared_shape(
    prepared: dict[str, Any],
    envelope: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    body = _content_body(
        prepared,
        id_name="prepared_attempt_id",
        hash_name="prepared_attempt_sha256",
        prefix="c4_stage1_prepared_attempt",
    )
    if (
        prepared.get("schema_version") != "rei-c4-stage1-prepared-attempt-v1"
        or prepared.get("prepared_attempt_id") != envelope.get("prepared_attempt_id")
        or prepared.get("prepared_attempt_sha256")
        != envelope.get("prepared_attempt_sha256")
        or prepared.get("run_id") != envelope.get("run_id")
        or prepared.get("attempt_id") != envelope.get("attempt_id")
        or prepared.get("source_provenance_sha256")
        != envelope.get("source_provenance_sha256")
        or prepared.get("source_provenance_storage_policy")
        != "hash-only-runtime-binding-v1"
        or prepared.get("source_provenance_bytes_stored") is not False
        or prepared.get("exact_inventory_required_before_spawn") is not True
        or prepared.get("runtime_bindings_reverification_required_before_spawn")
        is not True
        or prepared.get("first_model_call_requires_exact_prepared_attempt_confirmation")
        is not True
        or prepared.get("output_count") != 0
        or prepared.get("output_artifact_ids") != []
        or prepared.get("model_calls_before_prepared_anchor") != 0
        or prepared.get("semantic_authority_granted") is not False
        or prepared.get("production_authority_granted") is not False
        or _sha256(_canonical_json_bytes(body))
        != prepared.get("prepared_attempt_sha256")
    ):
        raise _fail()
    workers = prepared.get("workers")
    if type(workers) is not list:
        raise _fail()
    matches = [
        item
        for item in workers
        if type(item) is dict
        and item.get("prepared_worker_id") == envelope.get("prepared_worker_id")
    ]
    if len(matches) != 1:
        raise _fail()
    worker = matches[0]
    worker_body = _content_body(
        worker,
        id_name="prepared_worker_id",
        hash_name=None,
        prefix="c4_stage1_prepared_worker",
    )
    request = worker.get("worker_request")
    if type(request) is not dict:
        raise _fail()
    if (
        _sha256(_canonical_json_bytes(worker)) != envelope.get("prepared_worker_sha256")
        or worker.get("editor_role") != envelope.get("editor_role")
        or worker.get("option_id") != envelope.get("option_id")
        or worker.get("output_count") != 0
        or worker.get("output_artifact_ids") != []
        or worker.get("model_calls_before_preparation") != 0
        or not worker_body
    ):
        raise _fail()
    return worker, request


def _validate_request_shape(
    request: dict[str, Any],
    envelope: dict[str, Any],
) -> None:
    editor = request.get("editor_spec")
    verified = request.get("verified_snapshot")
    render = request.get("render_request")
    if (
        type(editor) is not dict
        or type(verified) is not dict
        or type(render) is not dict
    ):
        raise _fail()
    provider = editor.get("provider")
    pipeline = editor.get("pipeline")
    source = render.get("source_image")
    if (
        type(provider) is not dict
        or type(pipeline) is not dict
        or type(source) is not dict
    ):
        raise _fail()
    if (
        request.get("worker_request_id") != envelope.get("worker_request_id")
        or request.get("worker_request_id")
        != _content_id(
            "c4_stage1_worker_request",
            {
                key: value
                for key, value in request.items()
                if key != "worker_request_id"
            },
        )
        or _sha256(_canonical_json_bytes(request))
        != envelope.get("worker_request_sha256")
        or editor.get("editor_role") != envelope.get("editor_role")
        or editor.get("spec_id") != envelope.get("editor_spec_id")
        or _sha256(_canonical_json_bytes(editor)) != envelope.get("editor_spec_sha256")
        or provider.get("provider_id") != envelope.get("provider_id")
        or _content_id("c4_stage1_pipeline_spec", pipeline)
        != envelope.get("pipeline_spec_id")
        or _sha256(_canonical_json_bytes(pipeline))
        != envelope.get("pipeline_spec_sha256")
        or verified.get("verified_snapshot_id") != envelope.get("verified_snapshot_id")
        or editor.get("snapshot_manifest_sha256")
        != envelope.get("snapshot_manifest_sha256")
        or source.get("image_id") != envelope.get("source_artifact_id")
        or source.get("content_sha256") != envelope.get("source_sha256")
    ):
        raise _fail()


def _validate_intent_shape(
    intent: dict[str, Any],
    envelope: dict[str, Any],
) -> None:
    if (
        intent.get("intent_id") != envelope.get("telemetry_intent_id")
        or intent.get("intent_id")
        != _content_id(
            "c4_stage1_telemetry_intent",
            {
                key: value
                for key, value in intent.items()
                if key not in {"intent_id", "intent_sha256"}
            },
        )
        or intent.get("intent_sha256") != envelope.get("telemetry_intent_sha256")
        or intent.get("worker_request_id") != envelope.get("worker_request_id")
        or intent.get("worker_request_sha256") != envelope.get("worker_request_sha256")
        or intent.get("process_request") != envelope.get("process_request")
        or _sha256(
            _canonical_json_bytes(
                {
                    key: value
                    for key, value in intent.items()
                    if key not in {"intent_id", "intent_sha256"}
                }
            )
        )
        != intent.get("intent_sha256")
    ):
        raise _fail()


def _validate_closed_environment(
    prepared: dict[str, Any], environment: dict[str, str]
) -> None:
    policy = prepared.get("launch_policy")
    if type(policy) is not dict:
        raise _fail()
    fixed_raw = policy.get("fixed_environment")
    inherited_raw = policy.get("inherited_environment_names")
    if type(fixed_raw) is not list or type(inherited_raw) is not list:
        raise _fail()
    try:
        fixed = {name: value for name, value in fixed_raw}
    except (TypeError, ValueError) as exc:
        raise _fail() from exc
    if len(fixed) != len(fixed_raw) or any(
        type(name) is not str or type(value) is not str for name, value in fixed.items()
    ):
        raise _fail()
    if any(type(name) is not str for name in inherited_raw):
        raise _fail()
    allowed = set(fixed) | set(inherited_raw)
    if set(environment) - allowed or any(
        environment.get(key) != value for key, value in fixed.items()
    ):
        raise _fail()
    cuda = prepared.get("cuda_device")
    if type(cuda) is not dict or fixed.get("CUDA_VISIBLE_DEVICES") != cuda.get(
        "physical_gpu_uuid"
    ):
        raise _fail()


def _validate_repository_gate(repository_root: Path, gate: object) -> None:
    if type(gate) is not dict:
        raise _fail()
    gate_body = _content_body(
        gate,
        id_name="repository_gate_id",
        hash_name="repository_gate_sha256",
        prefix="c4_stage1_repository_gate",
    )
    git_runtime = gate.get("git_runtime")
    scopes = gate.get("scoped_paths")
    if (
        type(git_runtime) is not dict
        or type(scopes) is not list
        or scopes != list(_GIT_SCOPE_PATHS)
    ):
        raise _fail()
    _content_body(
        git_runtime,
        id_name="git_runtime_id",
        hash_name="git_runtime_sha256",
        prefix="c4_stage1_git_runtime",
    )
    if os.name == "nt":
        git_path = Path(r"C:\Program Files\Git\bin\git.exe")
        location_class = "windows-program-files-git-bin"
    elif os.name == "posix":
        git_path = Path("/usr/bin/git")
        location_class = "posix-usr-bin-git"
    else:
        raise _fail()
    git_bytes = _stable_read(git_path, maximum_bytes=_MAX_EXECUTABLE_BYTES)
    if (
        git_runtime.get("git_executable_sha256") != _sha256(git_bytes)
        or git_runtime.get("git_executable_size_bytes") != len(git_bytes)
        or git_runtime.get("trusted_location_class") != location_class
        or gate.get("origin_url") != _ORIGIN_URL
        or gate.get("branch") != "main"
        or gate.get("scoped_worktree_clean") is not True
        or gate.get("local_and_remote_main_equal_head") is not True
        or gate.get("remote_origin_queried_live") is not True
        or gate.get("tracked_scope_flags_verified") is not True
        or gate.get("skip_worktree_or_assume_unchanged_allowed") is not False
        or gate.get("model_calls_before_gate") != 0
        or not gate_body
    ):
        raise _fail()

    def run(*arguments: str) -> str:
        try:
            completed = subprocess.run(
                (os.fspath(git_path), *arguments),
                cwd=repository_root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30.0,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise _fail() from exc
        if completed.returncode != 0 or len(completed.stdout) > _MAX_JSON_BYTES:
            raise _fail()
        try:
            value = completed.stdout.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise _fail() from exc
        if "\x00" in value:
            raise _fail()
        return value

    version = run("--version").strip()
    branch = run("symbolic-ref", "--quiet", "--short", "HEAD").strip()
    head = run("rev-parse", "--verify", "HEAD^{commit}").strip()
    local = run("rev-parse", "--verify", "refs/remotes/origin/main^{commit}").strip()
    origin = run("remote", "get-url", "origin").strip()
    push_origin = run("remote", "get-url", "--push", "origin").strip()
    remote_lines = [
        line.strip()
        for line in run(
            "ls-remote", "--exit-code", _ORIGIN_URL, "refs/heads/main"
        ).splitlines()
        if line.strip()
    ]
    if len(remote_lines) != 1:
        raise _fail()
    remote_parts = remote_lines[0].split()
    remote = remote_parts[0] if len(remote_parts) == 2 else ""
    if (
        version != git_runtime.get("git_version")
        or branch != "main"
        or origin != _ORIGIN_URL
        or push_origin != _ORIGIN_URL
        or remote_parts[-1:] != ["refs/heads/main"]
        or not (head == local == remote == gate.get("head_commit"))
        or gate.get("local_origin_main_commit") != head
        or gate.get("remote_origin_main_commit") != head
    ):
        raise _fail()
    dirty = run("status", "--porcelain=v1", "--untracked-files=all", "--", *scopes)
    tracked = [
        line for line in run("ls-files", "-v", "--", *scopes).splitlines() if line
    ]
    if (
        dirty
        or not tracked
        or any(
            len(line) < 3 or line[1] != " " or line[0] == "S" or line[0].islower()
            for line in tracked
        )
    ):
        raise _fail()


def _runtime_relative_name(parts: tuple[str, ...]) -> str:
    value = "/".join(parts)
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise _fail() from exc
    if not value or value.startswith("/") or "\\" in value:
        raise _fail()
    return value


def _is_customization_name(parts: tuple[str, ...]) -> bool:
    return any(
        part.casefold().split(".", 1)[0] in {"sitecustomize", "usercustomize"}
        for part in parts
    )


def _update_tree_digest(
    digest: Any,
    *,
    kind: Literal["directory", "file"],
    relative_name: str,
    size_bytes: int | None = None,
    content_sha256: str | None = None,
) -> None:
    record: dict[str, object] = {"kind": kind, "relative_name": relative_name}
    if kind == "file":
        record.update({"size_bytes": size_bytes, "content_sha256": content_sha256})
    payload = _canonical_json_bytes(record)
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)


def _capture_runtime_tree(root: Path, *, tree_role: str) -> dict[str, object]:
    _assert_unlinked_ancestry(root)
    try:
        root_metadata = os.lstat(root)
    except OSError as exc:
        raise _fail() from exc
    if _is_link_or_reparse(root_metadata) or not stat.S_ISDIR(root_metadata.st_mode):
        raise _fail()
    digest = hashlib.sha256()
    digest.update(b"rei-c4-stage1-runtime-tree-inventory-v1\0")
    try:
        digest.update(tree_role.encode("ascii"))
    except UnicodeError as exc:
        raise _fail() from exc
    counters = {"files": 0, "directories": 1, "bytes": 0, "pth": 0}

    def scan(directory: Path, parts: tuple[str, ...]) -> None:
        try:
            before = os.lstat(directory)
            names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise _fail() from exc
        if _is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise _fail()
        for name in names:
            child = directory / name
            child_parts = (*parts, name)
            if _is_customization_name(child_parts):
                raise _fail()
            relative = _runtime_relative_name(child_parts)
            try:
                metadata = os.lstat(child)
            except OSError as exc:
                raise _fail() from exc
            if _is_link_or_reparse(metadata):
                raise _fail()
            if stat.S_ISDIR(metadata.st_mode):
                counters["directories"] += 1
                if counters["directories"] > _MAX_RUNTIME_DIRECTORIES:
                    raise _fail()
                _update_tree_digest(digest, kind="directory", relative_name=relative)
                scan(child, child_parts)
            elif stat.S_ISREG(metadata.st_mode):
                content_sha256, content_size = _stable_digest(
                    child, maximum_bytes=_MAX_RUNTIME_BYTES
                )
                counters["files"] += 1
                counters["bytes"] += content_size
                if (
                    counters["files"] > _MAX_RUNTIME_FILES
                    or counters["bytes"] > _MAX_RUNTIME_BYTES
                ):
                    raise _fail()
                if name.casefold().endswith(".pth"):
                    counters["pth"] += 1
                _update_tree_digest(
                    digest,
                    kind="file",
                    relative_name=relative,
                    size_bytes=content_size,
                    content_sha256=content_sha256,
                )
            else:
                raise _fail()
        try:
            after = os.lstat(directory)
            final_names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise _fail() from exc
        if (
            _is_link_or_reparse(after)
            or not os.path.samestat(before, after)
            or names != final_names
        ):
            raise _fail()

    scan(root, ())
    if counters["files"] == 0 or counters["bytes"] == 0:
        raise _fail()
    return {
        "schema_version": "rei-c4-stage1-runtime-tree-inventory-pin-v1",
        "tree_role": tree_role,
        "tree_content_sha256": digest.hexdigest(),
        "file_count": counters["files"],
        "directory_count": counters["directories"],
        "total_size_bytes": counters["bytes"],
        "pth_file_count": counters["pth"],
        "inventory_policy": _RUNTIME_TREE_POLICY,
        "relative_names_committed_in_digest": True,
        "relative_names_stored": False,
        "root_path_stored": False,
        "regular_files_only": True,
        "links_reparse_points_and_hardlinks_allowed": False,
        "sitecustomize_or_usercustomize_allowed": False,
        "pth_files_included_in_digest": True,
        "pth_files_executed": False,
    }


def _verify_runtime(prepared: dict[str, Any]) -> tuple[Path, ...]:
    pin = prepared.get("worker_runtime")
    if type(pin) is not dict:
        raise _fail()
    _content_body(
        pin,
        id_name="worker_runtime_id",
        hash_name="worker_runtime_sha256",
        prefix="c4_stage1_worker_runtime",
    )
    executable = Path(sys.executable)
    _assert_absolute_lexical(executable)
    executable_bytes = _stable_read(executable, maximum_bytes=_MAX_EXECUTABLE_BYTES)
    venv_root = executable.parent.parent
    base_root = Path(sys.base_prefix)
    _assert_absolute_lexical(base_root)
    if venv_root == base_root:
        raise _fail()
    worker_inventory = _capture_runtime_tree(venv_root, tree_role="worker-venv")
    base_inventory = _capture_runtime_tree(base_root, tree_role="base-runtime")
    inventory_body = {
        "policy": _RUNTIME_INVENTORY_POLICY,
        "worker_venv_inventory": worker_inventory,
        "base_runtime_inventory": base_inventory,
    }
    if (
        pin.get("schema_version") != "rei-c4-stage1-worker-runtime-pin-v2"
        or pin.get("worker_python_sha256") != _sha256(executable_bytes)
        or pin.get("worker_python_size_bytes") != len(executable_bytes)
        or pin.get("worker_venv_inventory") != worker_inventory
        or pin.get("base_runtime_inventory") != base_inventory
        or pin.get("runtime_inventory_policy") != _RUNTIME_INVENTORY_POLICY
        or pin.get("runtime_inventory_sha256")
        != _sha256(_canonical_json_bytes(inventory_body))
        or pin.get("runtime_inventory_file_count")
        != worker_inventory["file_count"] + base_inventory["file_count"]
        or pin.get("runtime_inventory_directory_count")
        != worker_inventory["directory_count"] + base_inventory["directory_count"]
        or pin.get("runtime_inventory_size_bytes")
        != worker_inventory["total_size_bytes"] + base_inventory["total_size_bytes"]
        or pin.get("runtime_tree_count") != 2
        or pin.get("runtime_paths_stored") is not False
        or pin.get("site_activation_disabled") is not True
        or pin.get("runtime_customization_modules_rejected") is not True
        or pin.get("pth_files_never_executed") is not True
        or pin.get("runtime_reverification_required_before_spawn") is not True
    ):
        raise _fail()
    variables = {"base": os.fspath(venv_root), "platbase": os.fspath(venv_root)}
    purelib = Path(sysconfig.get_path("purelib", vars=variables))
    platlib = Path(sysconfig.get_path("platlib", vars=variables))
    site_roots: list[Path] = []
    for site_root in (purelib, platlib):
        _assert_unlinked_ancestry(site_root)
        if not site_root.is_relative_to(venv_root):
            raise _fail()
        if site_root not in site_roots:
            site_roots.append(site_root)
    return tuple(site_roots)


def _file_identity(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int, int]:
    return (
        stat.S_IFMT(metadata.st_mode),
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        getattr(metadata, "st_mtime_ns", int(metadata.st_mtime * 1_000_000_000)),
        getattr(metadata, "st_ctime_ns", int(metadata.st_ctime * 1_000_000_000)),
        metadata.st_nlink,
    )


def _snapshot_inventory(
    root: Path,
) -> tuple[dict[str, tuple[int, int, int, int, int, int, int]], tuple[str, ...]]:
    files: dict[str, tuple[int, int, int, int, int, int, int]] = {}
    directories: list[str] = []
    stack: list[tuple[Path, tuple[str, ...]]] = [(root, ())]
    while stack:
        directory, parts = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise _fail() from exc
        for entry in entries:
            path = Path(entry.path)
            child_parts = (*parts, entry.name)
            relative = _runtime_relative_name(child_parts)
            try:
                metadata = os.lstat(path)
            except OSError as exc:
                raise _fail() from exc
            if _is_link_or_reparse(metadata):
                raise _fail()
            if not parts and entry.name == ".cache":
                if not stat.S_ISDIR(metadata.st_mode):
                    raise _fail()
                continue
            if stat.S_ISDIR(metadata.st_mode):
                directories.append(relative)
                stack.append((path, child_parts))
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise _fail()
                if not parts and entry.name == _SNAPSHOT_MANIFEST_FILENAME:
                    continue
                files[relative] = _file_identity(metadata)
            else:
                raise _fail()
    return files, tuple(sorted(directories))


def _verify_snapshot(
    snapshot: Path,
    *,
    request: dict[str, Any],
    prepared: dict[str, Any],
    run_id: str,
    run_root: Path,
) -> None:
    _assert_unlinked_ancestry(snapshot)
    editor = request["editor_spec"]
    role = editor.get("editor_role")
    if role not in {"primary", "alternate"}:
        raise _fail()
    descriptor_by_path = {
        item.get("relative_path"): item
        for item in prepared.get("artifact_inventory_before_anchor", [])
        if type(item) is dict
    }
    committed_path = f"diagnostics/{role}.snapshot-manifest.json"
    descriptor = descriptor_by_path.get(committed_path)
    _, committed = _validate_descriptor(
        descriptor,
        run_id=run_id,
        run_root=run_root,
        expected_path=committed_path,
    )
    local = _stable_read(
        snapshot / _SNAPSHOT_MANIFEST_FILENAME,
        maximum_bytes=_MAX_SNAPSHOT_MANIFEST_BYTES,
    )
    manifest = _parse_canonical_json(local)
    files = manifest.get("files")
    if type(files) is not list:
        raise _fail()
    paths: list[str] = []
    total = 0
    for item in files:
        if type(item) is not dict:
            raise _fail()
        relative = _validate_relative_path(item.get("relative_path"))
        if (
            relative == _SNAPSHOT_MANIFEST_FILENAME
            or relative.split("/", 1)[0] == ".cache"
            or not isinstance(item.get("sha256"), str)
            or not _SHA256_PATTERN.fullmatch(item["sha256"])
            or type(item.get("size_bytes")) is not int
            or item["size_bytes"] < 0
        ):
            raise _fail()
        paths.append(relative)
        total += item["size_bytes"]
    if (
        local != committed
        or _sha256(local) != editor.get("snapshot_manifest_sha256")
        or manifest.get("schema_version") != "rei-diffusers-snapshot-manifest-v1"
        or manifest.get("repo_id") != editor.get("repo_id")
        or manifest.get("revision") != editor.get("revision")
        or paths != sorted(paths)
        or len(paths) != len(set(paths))
        or len(paths) != editor.get("snapshot_file_count")
        or total != editor.get("snapshot_total_bytes")
    ):
        raise _fail()
    initial_files, initial_directories = _snapshot_inventory(snapshot)
    expected_directories = sorted(
        {
            "/".join(path.split("/")[:index])
            for path in paths
            for index in range(1, len(path.split("/")))
        }
    )
    if (
        sorted(initial_files) != paths
        or list(initial_directories) != expected_directories
    ):
        raise _fail()
    for item in files:
        path = snapshot.joinpath(*item["relative_path"].split("/"))
        if (
            initial_files[item["relative_path"]][3] != item["size_bytes"]
            or _stable_hash(
                path,
                expected_size=item["size_bytes"],
                maximum_bytes=max(item["size_bytes"], 1),
            )
            != item["sha256"]
        ):
            raise _fail()
    final_files, final_directories = _snapshot_inventory(snapshot)
    if (
        final_files != initial_files
        or final_directories != initial_directories
        or _stable_read(
            snapshot / _SNAPSHOT_MANIFEST_FILENAME,
            maximum_bytes=_MAX_SNAPSHOT_MANIFEST_BYTES,
        )
        != local
    ):
        raise _fail()


def _scan_run_files(run_root: Path) -> tuple[dict[str, Path], set[str]]:
    files: dict[str, Path] = {}
    directories: set[str] = set()

    def scan(directory: Path, parts: tuple[str, ...]) -> None:
        try:
            before = os.lstat(directory)
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
            names = tuple(item.name for item in entries)
        except OSError as exc:
            raise _fail() from exc
        if _is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise _fail()
        for entry in entries:
            path = Path(entry.path)
            child_parts = (*parts, entry.name)
            relative = _runtime_relative_name(child_parts)
            try:
                metadata = os.lstat(path)
            except OSError as exc:
                raise _fail() from exc
            if _is_link_or_reparse(metadata):
                raise _fail()
            if stat.S_ISDIR(metadata.st_mode):
                if (
                    relative
                    not in _RUN_TREE_DIRECTORIES | _OPTIONAL_RUN_TREE_DIRECTORIES
                ):
                    raise _fail()
                directories.add(relative)
                scan(path, child_parts)
            elif stat.S_ISREG(metadata.st_mode):
                if metadata.st_nlink != 1:
                    raise _fail()
                _validate_relative_path(relative)
                files[relative] = path
            else:
                raise _fail()
        try:
            after = os.lstat(directory)
            final_names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise _fail() from exc
        if not os.path.samestat(before, after) or names != final_names:
            raise _fail()

    scan(run_root, ())
    return files, directories


def _verify_exact_ledger(
    envelope: dict[str, Any], envelope_bytes: bytes, run_root: Path
) -> None:
    run_id = envelope.get("run_id")
    ledger = envelope.get("artifact_inventory_before_envelope")
    if type(run_id) is not str or type(ledger) is not list:
        raise _fail()
    paths: list[str] = []
    for descriptor in ledger:
        validated, _ = _validate_descriptor(
            descriptor, run_id=run_id, run_root=run_root
        )
        paths.append(validated["relative_path"])
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise _fail()
    envelope_path = (
        f"diagnostics/{envelope.get('prepared_worker_id')}.launch-envelope.json"
    )
    expected_paths = set(paths) | {envelope_path}
    files, directories = _scan_run_files(run_root)
    expected_directories = set(_RUN_TREE_DIRECTORIES)
    if any(path.startswith("emocio/embeddings/") for path in files):
        expected_directories.add("emocio/embeddings")
    if set(files) != expected_paths or directories != expected_directories:
        raise _fail()
    actual_envelope = _stable_read(files[envelope_path], maximum_bytes=_MAX_JSON_BYTES)
    if actual_envelope != envelope_bytes:
        raise _fail()


def _verify_source_png(raw: bytes, request: dict[str, Any]) -> None:
    source = request["render_request"]["source_image"]
    if _sha256(raw) != source.get("content_sha256"):
        raise _fail()
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise _fail()
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    if (width, height) != (source.get("width"), source.get("height")):
        raise _fail()


def _verify_script_pins(
    repository_root: Path,
    *,
    policy: dict[str, Any],
    envelope: dict[str, Any],
) -> tuple[bytes, bytes]:
    bootstrap_bytes = _stable_read(
        repository_root / _BOOTSTRAP_RELATIVE_PATH,
        maximum_bytes=_MAX_SCRIPT_BYTES,
    )
    worker_bytes = _stable_read(
        repository_root / _WORKER_RELATIVE_PATH,
        maximum_bytes=_MAX_SCRIPT_BYTES,
    )
    if (
        _sha256(bootstrap_bytes) != policy.get("bootstrap_script_sha256")
        or len(bootstrap_bytes) != policy.get("bootstrap_script_size_bytes")
        or _sha256(worker_bytes) != policy.get("worker_script_sha256")
        or len(worker_bytes) != policy.get("worker_script_size_bytes")
        or policy.get("bootstrap_script_sha256")
        != envelope.get("bootstrap_script_sha256")
        or policy.get("bootstrap_script_size_bytes")
        != envelope.get("bootstrap_script_size_bytes")
        or policy.get("worker_script_sha256") != envelope.get("worker_script_sha256")
        or policy.get("worker_script_size_bytes")
        != envelope.get("worker_script_size_bytes")
    ):
        raise _fail()
    return bootstrap_bytes, worker_bytes


def _stdlib_preflight(argv: list[str]) -> _StdlibVerifiedLaunch:
    _assert_no_model_modules()
    arguments = _parse_arguments(argv)
    envelope_path = arguments["launch_envelope"]
    assert isinstance(envelope_path, Path)
    envelope_bytes = _stable_read(envelope_path, maximum_bytes=_MAX_JSON_BYTES)
    envelope = _parse_canonical_json(envelope_bytes)
    environment = dict(os.environ)
    cwd = os.getcwd()
    _validate_envelope_shape(envelope, argv=argv, environment=environment, cwd=cwd)
    run_id = envelope.get("run_id")
    prepared_worker_id = envelope.get("prepared_worker_id")
    if type(run_id) is not str or type(prepared_worker_id) is not str:
        raise _fail()
    run_root = envelope_path.parent.parent
    repository_root = Path(cwd)
    _assert_unlinked_ancestry(run_root)
    _assert_unlinked_ancestry(repository_root)
    if (
        envelope_path.parent.name != "diagnostics"
        or envelope_path.name != f"{prepared_worker_id}.launch-envelope.json"
        or run_root.name != run_id
        or Path(__file__) != repository_root / _BOOTSTRAP_RELATIVE_PATH
    ):
        raise _fail()

    anchor_descriptor = envelope.get("prepared_anchor_storage")
    if type(anchor_descriptor) is not dict:
        raise _fail()
    validated_anchor, anchor_bytes = _validate_descriptor(
        anchor_descriptor,
        run_id=run_id,
        run_root=run_root,
        expected_path=_PREPARED_ANCHOR_RELATIVE_PATH,
    )
    if validated_anchor["storage_id"] != arguments["prepared_anchor_storage_id"]:
        raise _fail()
    prepared = _parse_canonical_json(anchor_bytes)
    worker, embedded_request = _validate_prepared_shape(prepared, envelope)
    _validate_closed_environment(prepared, environment)
    repository_gate = prepared.get("repository_gate")
    launch_policy = prepared.get("launch_policy")
    worker_runtime = prepared.get("worker_runtime")
    cuda_device = prepared.get("cuda_device")
    if (
        type(repository_gate) is not dict
        or type(launch_policy) is not dict
        or type(worker_runtime) is not dict
        or type(cuda_device) is not dict
        or repository_gate.get("repository_gate_id")
        != envelope.get("repository_gate_id")
        or repository_gate.get("repository_gate_sha256")
        != envelope.get("repository_gate_sha256")
        or launch_policy.get("launch_policy_id") != envelope.get("launch_policy_id")
        or launch_policy.get("launch_policy_sha256")
        != envelope.get("launch_policy_sha256")
        or worker_runtime.get("worker_runtime_id") != envelope.get("worker_runtime_id")
        or worker_runtime.get("worker_runtime_sha256")
        != envelope.get("worker_runtime_sha256")
        or cuda_device != envelope.get("cuda_device")
    ):
        raise _fail()

    descriptor_by_path = {
        item.get("relative_path"): item
        for item in prepared.get("artifact_inventory_before_anchor", [])
        if type(item) is dict
    }
    request_relative = (
        f"diagnostics/{envelope.get('worker_request_id')}.worker-request.json"
    )
    request_descriptor = descriptor_by_path.get(request_relative)
    _, request_bytes = _validate_descriptor(
        request_descriptor,
        run_id=run_id,
        run_root=run_root,
        expected_path=request_relative,
    )
    request_path = arguments["request"]
    assert isinstance(request_path, Path)
    if request_path != run_root.joinpath(*request_relative.split("/")):
        raise _fail()
    request = _parse_canonical_json(request_bytes)
    if request != embedded_request:
        raise _fail()
    _validate_request_shape(request, envelope)

    intent_descriptor = envelope.get("telemetry_intent_storage")
    intent_relative = (
        f"diagnostics/{envelope.get('telemetry_intent_id')}.telemetry-intent.json"
    )
    _, intent_bytes = _validate_descriptor(
        intent_descriptor,
        run_id=run_id,
        run_root=run_root,
        expected_path=intent_relative,
    )
    intent = _parse_canonical_json(intent_bytes)
    _validate_intent_shape(intent, envelope)

    source = request["render_request"]["source_image"]
    source_relative = _validate_relative_path(source.get("path"))
    source_descriptor = descriptor_by_path.get(source_relative)
    _, source_png = _validate_descriptor(
        source_descriptor,
        run_id=run_id,
        run_root=run_root,
        expected_path=source_relative,
    )
    source_path = arguments["source_png"]
    assert isinstance(source_path, Path)
    if source_path != run_root.joinpath(*source_relative.split("/")):
        raise _fail()
    _verify_source_png(source_png, request)

    policy = launch_policy
    bootstrap_bytes, worker_bytes = _verify_script_pins(
        repository_root,
        policy=policy,
        envelope=envelope,
    )

    _validate_repository_gate(repository_root, prepared.get("repository_gate"))
    site_roots = _verify_runtime(prepared)
    snapshot = arguments["snapshot"]
    assert isinstance(snapshot, Path)
    _verify_snapshot(
        snapshot,
        request=request,
        prepared=prepared,
        run_id=run_id,
        run_root=run_root,
    )
    _verify_exact_ledger(envelope, envelope_bytes, run_root)
    _assert_no_model_modules()
    return _StdlibVerifiedLaunch(
        arguments=arguments,
        repository_root=repository_root,
        run_root=run_root,
        site_roots=site_roots,
        envelope_bytes=envelope_bytes,
        envelope_data=envelope,
        anchor_bytes=anchor_bytes,
        anchor_data=prepared,
        request_bytes=request_bytes,
        request_data=request,
        intent_bytes=intent_bytes,
        intent_data=intent,
        source_png=source_png,
        bootstrap_bytes=bootstrap_bytes,
        worker_bytes=worker_bytes,
    )


def _activate_verified_runtime(launch: _StdlibVerifiedLaunch) -> int:
    _assert_no_model_modules()
    for root in reversed(launch.site_roots):
        sys.path.insert(0, os.fspath(root))
    backend_root = launch.repository_root / "app" / "backend"
    _assert_unlinked_ancestry(backend_root)
    sys.path.insert(0, os.fspath(backend_root))
    if "site" in sys.modules:
        raise _fail()

    from rei.emocio.c4_stage1_editor import (  # noqa: PLC0415
        C4Stage1LocalSnapshotBinding,
        C4Stage1WorkerRequest,
        inspect_c4_stage1_png_bytes,
        verify_c4_stage1_snapshot,
    )
    from rei.evaluation.c4_stage1_attempt import (  # noqa: PLC0415
        C4Stage1PreparedAttempt,
        capture_c4_stage1_repository_gate,
        cold_verify_c4_stage1_prepared_attempt,
    )
    from rei.evaluation.c4_stage1_run import (  # noqa: PLC0415
        C4Stage1LaunchEnvelope,
        cold_verify_c4_stage1_launch_envelope,
    )
    from rei.evaluation.c4_stage1_telemetry import (  # noqa: PLC0415
        C4Stage1TelemetryIntent,
    )
    from rei.persistence.artifacts import (  # noqa: PLC0415
        FileArtifactStore,
        stored_artifact_id,
    )
    from rei.providers.protocols import StoredArtifact  # noqa: PLC0415

    _assert_no_model_modules()
    prepared = C4Stage1PreparedAttempt.model_validate_json(launch.anchor_bytes)
    envelope = C4Stage1LaunchEnvelope.model_validate_json(launch.envelope_bytes)
    request = C4Stage1WorkerRequest.model_validate_json(launch.request_bytes)
    intent = C4Stage1TelemetryIntent.model_validate_json(launch.intent_bytes)
    if (
        prepared.canonical_json_bytes() != launch.anchor_bytes
        or envelope.canonical_json_bytes() != launch.envelope_bytes
        or request.canonical_json_bytes() != launch.request_bytes
        or intent.canonical_json_bytes() != launch.intent_bytes
    ):
        raise _fail()
    anchor_storage = StoredArtifact.model_validate(envelope.prepared_anchor_storage)
    store = FileArtifactStore(launch.run_root.parent, create=False)
    cold_prepared = cold_verify_c4_stage1_prepared_attempt(
        store,
        anchor_storage,
        require_exact_pre_spawn_inventory=False,
    ).prepared_attempt
    if cold_prepared != prepared:
        raise _fail()
    envelope_relative = (
        f"diagnostics/{envelope.prepared_worker_id}.launch-envelope.json"
    )
    envelope_storage = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=envelope.run_id,
            relative_path=envelope_relative,
            content_sha256=_sha256(launch.envelope_bytes),
            size_bytes=len(launch.envelope_bytes),
        ),
        run_id=envelope.run_id,
        relative_path=envelope_relative,
        content_sha256=_sha256(launch.envelope_bytes),
        size_bytes=len(launch.envelope_bytes),
    )
    cold_envelope = cold_verify_c4_stage1_launch_envelope(
        store, envelope_storage, prepared
    )
    if cold_envelope != envelope:
        raise _fail()
    workers = [
        item
        for item in prepared.workers
        if item.prepared_worker_id == envelope.prepared_worker_id
    ]
    if len(workers) != 1 or workers[0].worker_request != request:
        raise _fail()
    if (
        intent.intent_id != envelope.telemetry_intent_id
        or intent.intent_sha256 != envelope.telemetry_intent_sha256
        or intent.worker_request_id != request.worker_request_id
        or intent.process_request != envelope.process_request
        or capture_c4_stage1_repository_gate(launch.repository_root)
        != prepared.repository_gate
    ):
        raise _fail()
    snapshot_path = launch.arguments["snapshot"]
    assert isinstance(snapshot_path, Path)
    binding = C4Stage1LocalSnapshotBinding.create(request.editor_spec, snapshot_path)
    if (
        verify_c4_stage1_snapshot(request.editor_spec, binding)
        != request.verified_snapshot
    ):
        raise _fail()
    source = request.render_request.source_image
    if (
        source is None
        or _sha256(launch.source_png) != source.content_sha256
        or inspect_c4_stage1_png_bytes(launch.source_png)
        != (source.width, source.height)
    ):
        raise _fail()
    _assert_no_model_modules()

    capability = object()
    module_name = "_rei_c4_stage1_authorized_worker"
    worker_module = types.ModuleType(module_name)
    worker_path = launch.repository_root / _WORKER_RELATIVE_PATH
    worker_module.__file__ = os.fspath(worker_path)
    worker_module.__package__ = ""
    worker_module.__dict__["_REI_C4_STAGE1_BOOTSTRAP_CAPABILITY"] = capability
    sys.modules[module_name] = worker_module
    try:
        code = compile(launch.worker_bytes, os.fspath(worker_path), "exec")
        exec(code, worker_module.__dict__)
        _assert_no_model_modules()
        authorization = _C4Stage1BootstrapAuthorization(
            capability=capability,
            prepared=prepared,
            envelope=envelope,
            intent=intent,
            request=request,
            source_png=launch.source_png,
            snapshot_path=snapshot_path,
            staging_root=launch.arguments["staging_root"],
            repository_root=launch.repository_root,
            worker_path=worker_path,
            bootstrap_sha256=_sha256(launch.bootstrap_bytes),
            worker_sha256=_sha256(launch.worker_bytes),
        )
        return worker_module.run_authorized(authorization)
    finally:
        sys.modules.pop(module_name, None)


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    try:
        launch = _stdlib_preflight(values)
        return _activate_verified_runtime(launch)
    except BaseException as exc:
        if not isinstance(exc, Exception):
            raise
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
