"""Stdlib-only no-site bootstrap for one C4 Stage 1 DINO encoding.

The parent must invoke this file directly as ``python -I -S``.  The request,
checkout, executable and both committed scripts are byte-verified before the
verified site-packages directory is inserted manually.  Python's ``site``
module and ``.pth`` files are never executed.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import sysconfig
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = ROOT / "scripts" / "run_rei_c4_stage1_dino_bootstrap.py"
WORKER_PATH = ROOT / "scripts" / "run_rei_c4_stage1_dino_worker.py"
_SCHEMA = "rei-c4-stage1-dino-child-request-v1"
_MAX_REQUEST_BYTES = 4 * 1024 * 1024
_MAX_SCRIPT_BYTES = 4 * 1024 * 1024
_MAX_PYTHON_BYTES = 64 * 1024 * 1024
_MAX_RUNTIME_FILES = 2_000_000
_MAX_RUNTIME_DIRECTORIES = 500_000
_MAX_RUNTIME_BYTES = 128 * 1024 * 1024 * 1024
_READ_CHUNK_BYTES = 4 * 1024 * 1024
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_MODEL_ROOTS = {"accelerate", "diffusers", "safetensors", "torch", "transformers"}
_RUNTIME_INVENTORY_POLICY = "complete-venv-and-base-runtime-streaming-sha256-v1"
_RUNTIME_TREE_POLICY = "stable-streaming-sha256-all-regular-files-and-directories-v1"


class C4Stage1DinoBootstrapError(RuntimeError):
    """The isolated child was not authorized to import the runtime."""


def _fail() -> C4Stage1DinoBootstrapError:
    return C4Stage1DinoBootstrapError("C4 Stage 1 DINO bootstrap stopped")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


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


def _stable_regular(path: Path, *, maximum_bytes: int) -> bytes:
    _assert_unlinked_ancestry(path)
    try:
        before = os.lstat(path)
        value = path.read_bytes()
        after = os.lstat(path)
    except OSError as exc:
        raise _fail() from exc
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 < before.st_size <= maximum_bytes
        or len(value) != before.st_size
        or not os.path.samestat(before, after)
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise _fail()
    return value


def _stable_digest(path: Path, *, maximum_bytes: int) -> tuple[str, int]:
    """Hash one unchanged regular file without retaining large runtime bytes."""

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
    kind: str,
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
    """Reproduce the prepared complete-tree inventory before site activation."""

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
                    child,
                    maximum_bytes=_MAX_RUNTIME_BYTES,
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


def _runtime_pin_content(pin: dict[str, Any]) -> tuple[str, str]:
    body = {
        key: value
        for key, value in pin.items()
        if key not in {"worker_runtime_id", "worker_runtime_sha256"}
    }
    digest = _sha256(_canonical_json_bytes(body))
    return f"c4_stage1_worker_runtime_{digest[:32]}", digest


def _require_isolated_startup() -> None:
    if (
        not sys.flags.isolated
        or not sys.flags.no_site
        or "site" in sys.modules
        or any(name.split(".", 1)[0] in _MODEL_ROOTS for name in sys.modules)
    ):
        raise _fail()
    sys.dont_write_bytecode = True


def _assert_no_model_modules() -> None:
    if any(name.split(".", 1)[0] in _MODEL_ROOTS for name in sys.modules):
        raise _fail()


def _arguments(argv: list[str]) -> Path:
    if len(argv) != 2 or argv[0] != "--request":
        raise _fail()
    request = Path(argv[1])
    _assert_unlinked_ancestry(request)
    return request


def _load_request(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = _stable_regular(path, maximum_bytes=_MAX_REQUEST_BYTES)
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _fail() from exc
    if type(value) is not dict or _canonical_json_bytes(value) != raw:
        raise _fail()
    required = {
        "schema_version",
        "repository_root",
        "render_run_root",
        "staging_root",
        "snapshot_path",
        "worker_python_sha256",
        "worker_python_size_bytes",
        "worker_runtime_id",
        "worker_runtime_sha256",
        "worker_runtime",
        "bootstrap_script_sha256",
        "bootstrap_script_size_bytes",
        "worker_script_sha256",
        "worker_script_size_bytes",
        "snapshot_manifest_sha256",
        "cuda_physical_gpu_uuid",
        "image",
        "call",
    }
    if set(value) != required or value.get("schema_version") != _SCHEMA:
        raise _fail()
    return raw, value


def _verify_runtime(request: dict[str, Any]) -> tuple[Path, ...]:
    try:
        repository = Path(request["repository_root"])
        staging = Path(request["staging_root"])
        render = Path(request["render_run_root"])
        snapshot = Path(request["snapshot_path"])
    except (KeyError, TypeError) as exc:
        raise _fail() from exc
    for path in (repository, staging, render, snapshot):
        _assert_unlinked_ancestry(path)
    try:
        if repository.resolve(strict=True) != ROOT:
            raise _fail()
        staging_metadata = os.lstat(staging)
        if (
            _is_link_or_reparse(staging_metadata)
            or not stat.S_ISDIR(staging_metadata.st_mode)
            or tuple(os.scandir(staging))
        ):
            raise _fail()
    except OSError as exc:
        raise _fail() from exc

    bootstrap = _stable_regular(BOOTSTRAP_PATH, maximum_bytes=_MAX_SCRIPT_BYTES)
    worker = _stable_regular(WORKER_PATH, maximum_bytes=_MAX_SCRIPT_BYTES)
    executable_path = Path(sys.executable)
    executable = _stable_regular(executable_path, maximum_bytes=_MAX_PYTHON_BYTES)
    pin = request.get("worker_runtime")
    if type(pin) is not dict:
        raise _fail()
    expected_runtime_id, expected_runtime_sha256 = _runtime_pin_content(pin)
    if (
        request.get("bootstrap_script_sha256") != _sha256(bootstrap)
        or request.get("bootstrap_script_size_bytes") != len(bootstrap)
        or request.get("worker_script_sha256") != _sha256(worker)
        or request.get("worker_script_size_bytes") != len(worker)
        or request.get("worker_python_sha256") != _sha256(executable)
        or request.get("worker_python_size_bytes") != len(executable)
        or request.get("worker_runtime_id") != expected_runtime_id
        or request.get("worker_runtime_sha256") != expected_runtime_sha256
        or pin.get("worker_runtime_id") != expected_runtime_id
        or pin.get("worker_runtime_sha256") != expected_runtime_sha256
    ):
        raise _fail()

    if executable_path.parent.name.casefold() not in {"scripts", "bin"}:
        raise _fail()
    venv_root = executable_path.parent.parent
    base_root = Path(sys.base_prefix)
    _assert_unlinked_ancestry(base_root)
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
        or pin.get("worker_python_sha256") != _sha256(executable)
        or pin.get("worker_python_size_bytes") != len(executable)
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
        or pin.get("complete_runtime_trees_inventory_verified") is not True
        or pin.get("inventory_recapture_required_before_every_spawn") is not True
        or pin.get("runtime_reverification_required_before_spawn") is not True
        or pin.get("model_packages_imported_in_parent") is not False
        or pin.get("network_access_required") is not False
    ):
        raise _fail()
    variables = {"base": os.fspath(venv_root), "platbase": os.fspath(venv_root)}
    site_roots: list[Path] = []
    for site_root in (
        Path(sysconfig.get_path("purelib", vars=variables)),
        Path(sysconfig.get_path("platlib", vars=variables)),
    ):
        _assert_unlinked_ancestry(site_root)
        if not site_root.is_relative_to(venv_root):
            raise _fail()
        if site_root not in site_roots:
            site_roots.append(site_root)
    return tuple(site_roots)


def _load_worker(site_roots: tuple[Path, ...]) -> ModuleType:
    if "site" in sys.modules:
        raise _fail()
    for site_root in reversed(site_roots):
        sys.path.insert(0, os.fspath(site_root))
    sys.path.insert(0, os.fspath(ROOT / "app" / "backend"))
    spec = importlib.util.spec_from_file_location(
        "_rei_c4_stage1_dino_worker",
        WORKER_PATH,
    )
    if spec is None or spec.loader is None:
        raise _fail()
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        return 64
    try:
        _require_isolated_startup()
        request_path = _arguments(arguments)
        raw, request = _load_request(request_path)
        site_roots = _verify_runtime(request)
        worker = _load_worker(site_roots)
        _assert_no_model_modules()
        implementation = getattr(worker, "run_authorized_request", None)
        if not callable(implementation):
            raise _fail()
        return int(implementation(raw))
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
