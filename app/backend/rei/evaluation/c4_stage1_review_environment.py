"""Path-private C4 Stage 1 review-runtime manifests and live verification.

This module is stdlib-only.  It never launches Python, Playwright, Chromium,
or a model.  The presenter supplies a checkpoint callback so its own absolute
deadline and cancellation policy applies to every bounded hashing interval.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Callable, Mapping


sys.dont_write_bytecode = True

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]

BOOTSTRAP_SCHEMA = "rei-c4-stage1-review-runtime-bootstrap-v1"
PROVENANCE_SCHEMA = "rei-c4-stage1-review-runtime-provenance-v1"
TREE_MANIFEST_SCHEMA = "rei-c4-stage1-review-runtime-tree-manifest-v1"
VERIFICATION_SCHEMA = "rei-c4-stage1-review-runtime-verification-v1"

RUNTIME_MANIFEST_NAME = "review-runtime-files.json"
BROWSER_MANIFEST_NAME = "review-browser-files.json"
PROVENANCE_NAME = "review-runtime-provenance.json"
BOOTSTRAP_RELATIVE_PATH = "scripts/run_rei_c4_stage1_review_runtime_bootstrap.py"
BOOTSTRAP_DATA_DIRECTORY = ".rei-c4-stage1-review-bootstrap"
WHEELHOUSE_DIRECTORY = "wheelhouse"
COPIED_BASE_DIRECTORY = "base-python"
VENV_DIRECTORY = "venv"
RUNTIME_BASE_PYTHON_RELATIVE_PATH = "base-python/python.exe"
RUNTIME_PYTHON_RELATIVE_PATH = "venv/Scripts/python.exe"
PYVENV_CONFIG_RELATIVE_PATH = "venv/pyvenv.cfg"
BROWSERS_JSON_RELATIVE_PATH = (
    "venv/Lib/site-packages/playwright/driver/package/browsers.json"
)

PLAYWRIGHT_VERSION = "1.61.0"
CHROMIUM_REVISION = "1228"
CHROMIUM_VERSION = "149.0.7827.55"
CHROMIUM_EXECUTABLE_RELATIVE_PATH = "chromium-1228/chrome-win64/chrome.exe"
CHROMIUM_MARKER_RELATIVE_PATH = "chromium-1228/INSTALLATION_COMPLETE"
PLAYWRIGHT_BROWSERS_JSON_SOURCE = (
    "https://raw.githubusercontent.com/microsoft/playwright/"
    "v1.61.0/packages/playwright-core/browsers.json"
)
PLAYWRIGHT_REGISTRY_SOURCE = (
    "https://raw.githubusercontent.com/microsoft/playwright/"
    "v1.61.0/packages/playwright-core/src/server/registry/index.ts"
)

REVIEW_RUNTIME_IMPORT_PROBE_MODULES = (
    "annotated_types",
    "greenlet",
    "pydantic",
    "pydantic_core",
    "pyee",
    "typing_extensions",
    "typing_inspection",
    "playwright.sync_api",
    "rei.evaluation.c4_stage1_review_presenter",
    "rei.evaluation.c4_stage1_review_run",
    "rei.evaluation.c4_stage1_review_service",
)

PACKAGE_PIN_RECORDS: tuple[dict[str, object], ...] = (
    {
        "name": "playwright",
        "version": "1.61.0",
        "filename": "playwright-1.61.0-py3-none-win_amd64.whl",
        "size_bytes": 37_844_846,
        "sha256": "35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/6c/fd/"
            "2b78036e5fbe9d5f5645bbe08a1eac7160c51243c0093963edbcf67c35d9/"
            "playwright-1.61.0-py3-none-win_amd64.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/playwright/1.61.0/json",
        "selection_policy": "phase-required-exact-release",
    },
    {
        "name": "greenlet",
        "version": "3.1.1",
        "filename": "greenlet-3.1.1-cp311-cp311-win_amd64.whl",
        "size_bytes": 298_930,
        "sha256": "48ca08c771c268a768087b408658e216133aecd835c0ded47ce955381105ba39",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/12/da/"
            "b9ed5e310bb8b89661b80cbcd4db5a067903bbcd7fc854923f5ebb4144f0/"
            "greenlet-3.1.1-cp311-cp311-win_amd64.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/greenlet/3.1.1/json",
        "selection_policy": "playwright-supported-range-lower-bound",
    },
    {
        "name": "pyee",
        "version": "13.0.0",
        "filename": "pyee-13.0.0-py3-none-any.whl",
        "size_bytes": 15_730,
        "sha256": "48195a3cddb3b1515ce0695ed76036b5ccc2ef3a9f963ff9f77aec0139845498",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/9b/4d/"
            "b9add7c84060d4c1906abe9a7e5359f2a60f7a9a4f67268b2766673427d8/"
            "pyee-13.0.0-py3-none-any.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/pyee/13.0.0/json",
        "selection_policy": "playwright-supported-range-lower-bound",
    },
    {
        "name": "typing-extensions",
        "version": "4.16.0",
        "filename": "typing_extensions-4.16.0-py3-none-any.whl",
        "size_bytes": 45_571,
        "sha256": "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/49/d3/"
            "b8441a820a491ddfc024b0b0cf0393375b75ea13866d9c66727e54c2fc80/"
            "typing_extensions-4.16.0-py3-none-any.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/typing-extensions/4.16.0/json",
        "selection_policy": "pyee-runtime-dependency-current-at-protocol-freeze",
    },
    {
        "name": "pydantic",
        "version": "2.13.4",
        "filename": "pydantic-2.13.4-py3-none-any.whl",
        "size_bytes": 472_262,
        "sha256": "45a282cde31d808236fd7ea9d919b128653c8b38b393d1c4ab335c62924d9aba",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/fd/7b/"
            "122376b1fd3c62c1ed9dc80c931ace4844b3c55407b6fb2d199377c9736f/"
            "pydantic-2.13.4-py3-none-any.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/pydantic/2.13.4/json",
        "selection_policy": "review-runtime-import-contract-exact-release",
    },
    {
        "name": "pydantic-core",
        "version": "2.46.4",
        "filename": "pydantic_core-2.46.4-cp311-cp311-win_amd64.whl",
        "size_bytes": 2_071_114,
        "sha256": "6f2eeda33a839975441c86a4119e1383c50b47faf0cbb5176985565c6bb02c33",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/aa/e6/"
            "c505f83dfeda9a2e5c995cfd872949e4d05e12f7feb3dca72f633daefa94/"
            "pydantic_core-2.46.4-cp311-cp311-win_amd64.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/pydantic-core/2.46.4/json",
        "selection_policy": "pydantic-2.13.4-exact-runtime-dependency",
    },
    {
        "name": "annotated-types",
        "version": "0.7.0",
        "filename": "annotated_types-0.7.0-py3-none-any.whl",
        "size_bytes": 13_643,
        "sha256": "1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/78/b6/"
            "6307fbef88d9b5ee7421e68d78a9f162e0da4900bc5f5793f6d3d0e34fb8/"
            "annotated_types-0.7.0-py3-none-any.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/annotated-types/0.7.0/json",
        "selection_policy": "pydantic-runtime-dependency-current-at-protocol-freeze",
    },
    {
        "name": "typing-inspection",
        "version": "0.4.2",
        "filename": "typing_inspection-0.4.2-py3-none-any.whl",
        "size_bytes": 14_611,
        "sha256": "4ed1cacbdc298c220f1bd249ed5287caa16f34d44ef4e9c3d0cbad5b521545e7",
        "artifact_url": (
            "https://files.pythonhosted.org/packages/dc/9b/"
            "47798a6c91d8bdb567fe2698fe81e0c6b7cb7ef4d13da4114b41d239f65d/"
            "typing_inspection-0.4.2-py3-none-any.whl"
        ),
        "metadata_url": "https://pypi.org/pypi/typing-inspection/0.4.2/json",
        "selection_policy": "pydantic-supported-range-lower-bound",
    },
)
EXPECTED_PACKAGE_VERSIONS = {
    str(record["name"]): str(record["version"]) for record in PACKAGE_PIN_RECORDS
}

_READ_CHUNK_BYTES = 4 * 1024 * 1024
_MAX_FILES = 200_000
_MAX_DIRECTORIES = 50_000
_MAX_BYTES = 8 * 1024 * 1024 * 1024
_MAX_PROVENANCE_BYTES = 64 * 1024 * 1024
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_EXECUTABLE_SUFFIXES = frozenset({".bat", ".cmd", ".com", ".exe", ".pyd"})
_BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})
_HEX = frozenset("0123456789abcdef")
_DISTRIBUTION_NAME_SEPARATOR = re.compile(r"[-_.]+")
_CUSTOMIZATION_FILENAMES = frozenset(
    {"sitecustomize.py", "usercustomize.py"}
)
_FORBIDDEN_SEED_PACKAGE_NAMES = frozenset(
    {"_distutils_hack", "pip", "pkg_resources", "setuptools", "wheel"}
)
_PROVENANCE_KEYS = frozenset(
    {
        "provenance_id",
        "schema_version",
        "bootstrap_schema",
        "bootstrap_script",
        "path_bindings",
        "source_base_python",
        "base_runtime_copy",
        "runtime_base_python",
        "runtime_python",
        "python_runtime_layout",
        "packages",
        "verified_wheels",
        "installed_package_versions",
        "installed_distributions",
        "browser",
        "runtime_manifest",
        "browser_manifest",
        "bounded_process_records",
        "wheel_download_verified_before_offline_install",
        "matching_playwright_chromium_install_completed",
        "install_verification_completed",
        "install_verification_scope",
        "browser_process_launch_performed",
        "headed_full_ui_smoke_performed",
        "headed_full_ui_smoke_authority",
        "network_access_during_execution",
        "network_access_during_verification",
        "model_calls",
        "secrets_stored",
        "semantic_authority_granted",
        "production_authority_granted",
    }
)
_EXPECTED_WORKLOADS = (
    "c4-review-bootstrap-base-python-probe",
    "c4-review-bootstrap-copied-base-python-probe",
    "c4-review-bootstrap-create-copy-venv",
    "c4-review-bootstrap-runtime-python-layout-probe",
    "c4-review-bootstrap-download-hash-pinned-wheels",
    "c4-review-bootstrap-install-offline-wheelhouse",
    "c4-review-bootstrap-installed-package-probe",
    "c4-review-bootstrap-review-import-contract-probe",
    "c4-review-bootstrap-install-matching-chromium",
)
_PROCESS_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "record_id",
        "runner_revision",
        "workload_id",
        "command_identity",
        "argument_count",
        "working_directory_identity",
        "environment_identity",
        "timeout_seconds",
        "stdout_limit_bytes",
        "stderr_limit_bytes",
        "platform_system",
        "isolation_mode",
        "target_start_token_hash",
        "target_process_group_id",
        "target_session_id",
        "started_at",
        "finished_at",
        "elapsed_monotonic_seconds",
        "workload_elapsed_monotonic_seconds",
        "workload_timing_scope",
        "process_id",
        "workload_released",
        "workload_release_status",
        "exit_code",
        "status",
        "termination_trigger",
        "failure_code",
        "failure_message",
        "stdout",
        "stderr",
        "tree_termination_requested",
        "tree_termination_succeeded",
        "tree_termination_method",
        "tree_inspection_method",
        "final_active_processes",
        "target_identity_confirmed",
        "empty_tree_confirmed",
        "containment_closed",
        "observer_callback_failed",
        "fallback_used",
    }
)
_OUTPUT_SUMMARY_KEYS = frozenset(
    {
        "byte_count",
        "captured_byte_count",
        "sha256",
        "captured_sha256",
        "truncated",
        "stream_complete",
    }
)


class C4Stage1ReviewEnvironmentError(RuntimeError):
    """The path-private review runtime differs from its sealed provenance."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _content_id(prefix: str, value: object) -> str:
    return f"{prefix}_{_sha256(canonical_json_bytes(value))[:32]}"


def _checkpoint(callback: Callable[[], None]) -> None:
    if not callable(callback):
        raise C4Stage1ReviewEnvironmentError("Runtime checkpoint is not callable")
    callback()


def _valid_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _path_identity(path: Path) -> str:
    value = os.path.normcase(os.path.abspath(os.fspath(path))).replace("\\", "/")
    return _sha256(value.encode("utf-8", errors="strict"))


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _require_absolute(path: Path) -> None:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path != Path(os.path.abspath(os.fspath(path)))
    ):
        raise C4Stage1ReviewEnvironmentError("Review runtime paths must be absolute")


def _assert_unlinked_ancestry(path: Path) -> None:
    _require_absolute(path)
    current = path
    while True:
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise C4Stage1ReviewEnvironmentError(
                "Review runtime ancestry is unavailable"
            ) from exc
        if _is_link_or_reparse(metadata):
            raise C4Stage1ReviewEnvironmentError(
                "Review runtime ancestry contains a link or reparse point"
            )
        parent = current.parent
        if parent == current:
            return
        current = parent


def _existing_directory(path: Path) -> Path:
    _assert_unlinked_ancestry(path)
    try:
        resolved = path.resolve(strict=True)
        metadata = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime directory is unavailable"
        ) from exc
    if _is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime requires an ordinary directory"
        )
    return resolved


def _contains(left: Path, right: Path) -> bool:
    left_value = os.path.normcase(os.path.abspath(os.fspath(left)))
    right_value = os.path.normcase(os.path.abspath(os.fspath(right)))
    try:
        return os.path.commonpath((left_value, right_value)) == left_value
    except ValueError:
        return False


def _reject_overlap(left: Path, right: Path) -> None:
    if _contains(left, right) or _contains(right, left):
        raise C4Stage1ReviewEnvironmentError("Review runtime roots overlap")


def _stable_file(
    path: Path,
    *,
    maximum_bytes: int,
    checkpoint: Callable[[], None],
) -> bytes:
    _checkpoint(checkpoint)
    _assert_unlinked_ancestry(path)
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime file is unavailable"
        ) from exc
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 <= before.st_size <= maximum_bytes
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime file is not an ordinary one-link file"
        )
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        handle = os.open(path, flags)
    except OSError as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime file could not be opened"
        ) from exc
    chunks: list[bytes] = []
    size = 0
    try:
        opened = os.fstat(handle)
        if not os.path.samestat(before, opened):
            raise C4Stage1ReviewEnvironmentError("Review runtime file identity changed")
        while True:
            _checkpoint(checkpoint)
            chunk = os.read(handle, _READ_CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if size > maximum_bytes:
                raise C4Stage1ReviewEnvironmentError(
                    "Review runtime file exceeds its byte bound"
                )
            chunks.append(chunk)
        final_handle = os.fstat(handle)
    finally:
        os.close(handle)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewEnvironmentError("Review runtime file disappeared") from exc
    if (
        _is_link_or_reparse(after)
        or after.st_nlink != 1
        or not os.path.samestat(before, final_handle)
        or not os.path.samestat(before, after)
        or before.st_size != size
        or final_handle.st_size != size
        or after.st_size != size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime file changed during capture"
        )
    _checkpoint(checkpoint)
    return b"".join(chunks)


def _file_descriptor(
    path: Path,
    *,
    relative_path: str,
    checkpoint: Callable[[], None],
    maximum_bytes: int = _MAX_BYTES,
) -> dict[str, object]:
    payload = _stable_file(
        path,
        maximum_bytes=maximum_bytes,
        checkpoint=checkpoint,
    )
    return {
        "relative_path": relative_path,
        "sha256": _sha256(payload),
        "size_bytes": len(payload),
    }


def capture_c4_stage1_review_tree(
    root: Path,
    *,
    tree_role: str,
    checkpoint: Callable[[], None],
) -> dict[str, object]:
    """Capture sorted canonical relative-path records for one complete tree."""

    _checkpoint(checkpoint)
    root = _existing_directory(root)
    entries: list[dict[str, object]] = []
    executables: list[dict[str, object]] = []
    total_bytes = 0
    directory_count = 1

    def scan(directory: Path, parts: tuple[str, ...]) -> None:
        nonlocal total_bytes, directory_count
        _checkpoint(checkpoint)
        try:
            before = os.lstat(directory)
            names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise C4Stage1ReviewEnvironmentError(
                "Review runtime tree is unavailable"
            ) from exc
        if _is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise C4Stage1ReviewEnvironmentError(
                "Review runtime tree contains a non-directory"
            )
        for name in names:
            _checkpoint(checkpoint)
            child = directory / name
            child_parts = (*parts, name)
            relative = "/".join(child_parts)
            try:
                relative.encode("utf-8", errors="strict")
                metadata = os.lstat(child)
            except (OSError, UnicodeError) as exc:
                raise C4Stage1ReviewEnvironmentError(
                    "Review runtime tree entry is invalid"
                ) from exc
            if _is_link_or_reparse(metadata):
                raise C4Stage1ReviewEnvironmentError(
                    "Review runtime tree contains a link or reparse point"
                )
            if name.casefold() == "__pycache__" or child.suffix.casefold() in (
                _BYTECODE_SUFFIXES
            ):
                raise C4Stage1ReviewEnvironmentError(
                    "Review runtime tree contains mutable Python bytecode"
                )
            if stat.S_ISDIR(metadata.st_mode):
                directory_count += 1
                if directory_count > _MAX_DIRECTORIES:
                    raise C4Stage1ReviewEnvironmentError(
                        "Review runtime tree has too many directories"
                    )
                entries.append({"kind": "directory", "relative_path": relative})
                scan(child, child_parts)
            elif stat.S_ISREG(metadata.st_mode):
                descriptor = _file_descriptor(
                    child,
                    relative_path=relative,
                    checkpoint=checkpoint,
                )
                total_bytes += int(descriptor["size_bytes"])
                if (
                    len(entries) >= _MAX_FILES + _MAX_DIRECTORIES
                    or total_bytes > _MAX_BYTES
                ):
                    raise C4Stage1ReviewEnvironmentError(
                        "Review runtime tree exceeds its fixed bounds"
                    )
                entry = {"kind": "file", **descriptor}
                entries.append(entry)
                if child.suffix.casefold() in _EXECUTABLE_SUFFIXES:
                    executables.append(dict(descriptor))
            else:
                raise C4Stage1ReviewEnvironmentError(
                    "Review runtime tree contains a special file"
                )
        try:
            after = os.lstat(directory)
            final_names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise C4Stage1ReviewEnvironmentError(
                "Review runtime tree changed during capture"
            ) from exc
        if not os.path.samestat(before, after) or names != final_names:
            raise C4Stage1ReviewEnvironmentError(
                "Review runtime tree changed during capture"
            )
        _checkpoint(checkpoint)

    scan(root, ())
    file_count = sum(entry["kind"] == "file" for entry in entries)
    if file_count == 0 or total_bytes == 0:
        raise C4Stage1ReviewEnvironmentError("Review runtime tree is empty")
    content = {
        "tree_role": tree_role,
        "file_count": file_count,
        "directory_count": directory_count,
        "total_size_bytes": total_bytes,
        "entries": entries,
    }
    tree_sha256 = _sha256(canonical_json_bytes(content))
    body = {
        "schema_version": TREE_MANIFEST_SCHEMA,
        "tree_role": tree_role,
        "tree_content_id": f"c4_review_tree_content_{tree_sha256[:32]}",
        "tree_content_sha256": tree_sha256,
        "tree_content_encoding": "sorted-canonical-relative-path-records-v1",
        "root_path_stored": False,
        "root_path_identity_sha256": _path_identity(root),
        "regular_files_only": True,
        "links_reparse_points_and_hardlinks_allowed": False,
        "python_bytecode_and_cache_directories_allowed": False,
        "file_count": file_count,
        "directory_count": directory_count,
        "total_size_bytes": total_bytes,
        "executable_count": len(executables),
        "executables": executables,
        "entries": entries,
    }
    return {"manifest_id": _content_id("c4_review_tree", body), **body}


def _load_canonical(
    path: Path,
    *,
    checkpoint: Callable[[], None],
) -> tuple[bytes, dict[str, object]]:
    raw = _stable_file(
        path,
        maximum_bytes=_MAX_PROVENANCE_BYTES,
        checkpoint=checkpoint,
    )
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime provenance JSON is invalid"
        ) from exc
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime provenance JSON is not canonical"
        )
    return raw, value


def _manifest_descriptor(
    name: str,
    raw: bytes,
    manifest: Mapping[str, object],
) -> dict[str, object]:
    return {
        "relative_path": name,
        "manifest_id": manifest["manifest_id"],
        "sha256": _sha256(raw),
        "size_bytes": len(raw),
    }


def _runtime_layout() -> dict[str, object]:
    return {
        "complete_runtime_root_manifested": True,
        "copied_base_relative_path": COPIED_BASE_DIRECTORY,
        "venv_relative_path": VENV_DIRECTORY,
        "runtime_python_relative_path": RUNTIME_PYTHON_RELATIVE_PATH,
        "runtime_base_python_relative_path": RUNTIME_BASE_PYTHON_RELATIVE_PATH,
        "pyvenv_config_relative_path": PYVENV_CONFIG_RELATIVE_PATH,
        "venv_link_mode": "copies",
        "venv_created_without_pip": True,
        "active_distribution_policy": "exact-eight-canonical-normalized-pins-v1",
        "active_distribution_count": len(PACKAGE_PIN_RECORDS),
        "pip_setuptools_and_wheel_allowed": False,
        "pth_files_allowed": False,
        "runtime_customization_modules_allowed": False,
        "external_python_runtime_dependencies_allowed": False,
        "python_bytecode_writes_allowed": False,
    }


def _validate_path_bindings(
    value: object,
    *,
    runtime_root: Path,
    browser_root: Path,
    provenance_root: Path,
) -> None:
    expected_keys = {
        "paths_stored",
        "runtime_root_identity_sha256",
        "browser_root_identity_sha256",
        "provenance_root_identity_sha256",
        "artifact_root_identity_sha256",
        "model_root_identity_sha256",
        "state_root_identity_sha256",
    }
    if type(value) is not dict or set(value) != expected_keys:
        raise C4Stage1ReviewEnvironmentError("Review path bindings are invalid")
    if (
        value["paths_stored"] is not False
        or value["runtime_root_identity_sha256"] != _path_identity(runtime_root)
        or value["browser_root_identity_sha256"] != _path_identity(browser_root)
        or value["provenance_root_identity_sha256"] != _path_identity(provenance_root)
    ):
        raise C4Stage1ReviewEnvironmentError("Review path bindings differ from roots")
    for name in (
        "artifact_root_identity_sha256",
        "model_root_identity_sha256",
        "state_root_identity_sha256",
    ):
        identities = value[name]
        if (
            type(identities) is not list
            or not identities
            or identities != sorted(set(identities))
            or not all(_valid_digest(item) for item in identities)
        ):
            raise C4Stage1ReviewEnvironmentError(
                "Review forbidden-root bindings are invalid"
            )


def _installed_distributions(
    runtime_root: Path,
    *,
    checkpoint: Callable[[], None],
) -> list[dict[str, object]]:
    site_packages = runtime_root / VENV_DIRECTORY / "Lib" / "site-packages"
    _existing_directory(site_packages)
    expected = {
        _canonical_distribution_name(str(pin["name"])): pin
        for pin in PACKAGE_PIN_RECORDS
    }
    discovered: dict[str, tuple[dict[str, object], Path]] = {}
    customization_count = 0
    distribution_directory_count = 0
    entry_count = 0
    directory_count = 0

    def scan(directory: Path) -> None:
        nonlocal customization_count, directory_count, distribution_directory_count
        nonlocal entry_count
        _checkpoint(checkpoint)
        directory_count += 1
        if directory_count > _MAX_DIRECTORIES:
            raise C4Stage1ReviewEnvironmentError(
                "Review active runtime has too many directories"
            )
        try:
            names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise C4Stage1ReviewEnvironmentError(
                "Review active runtime inventory is unavailable"
            ) from exc
        for name in names:
            _checkpoint(checkpoint)
            entry_count += 1
            if entry_count > _MAX_FILES + _MAX_DIRECTORIES:
                raise C4Stage1ReviewEnvironmentError(
                    "Review active runtime has too many entries"
                )
            path = directory / name
            try:
                metadata = os.lstat(path)
            except OSError as exc:
                raise C4Stage1ReviewEnvironmentError(
                    "Review active runtime inventory changed"
                ) from exc
            if _is_link_or_reparse(metadata):
                raise C4Stage1ReviewEnvironmentError(
                    "Review active runtime contains a link or reparse point"
                )
            folded = name.casefold()
            if stat.S_ISREG(metadata.st_mode):
                if (
                    folded.endswith((".pth", ".egg-link"))
                    or folded in _CUSTOMIZATION_FILENAMES
                ):
                    customization_count += 1
                if (
                    path.parent == site_packages
                    and Path(folded).stem in _FORBIDDEN_SEED_PACKAGE_NAMES
                ):
                    raise C4Stage1ReviewEnvironmentError(
                        "Review runtime contains package-manager seed residue"
                    )
                continue
            if not stat.S_ISDIR(metadata.st_mode):
                raise C4Stage1ReviewEnvironmentError(
                    "Review active runtime contains a special entry"
                )
            if folded.endswith(".dist-info"):
                distribution_directory_count += 1
                if path.parent != site_packages:
                    raise C4Stage1ReviewEnvironmentError(
                        "Review distribution metadata is outside sealed site-packages"
                    )
                metadata_bytes = _stable_file(
                    path / "METADATA",
                    maximum_bytes=8 * 1024 * 1024,
                    checkpoint=checkpoint,
                )
                distribution_name, distribution_version = _metadata_identity(
                    metadata_bytes
                )
                canonical_name = _canonical_distribution_name(distribution_name)
                pin = expected.get(canonical_name)
                if (
                    pin is None
                    or distribution_version != str(pin["version"])
                    or canonical_name in discovered
                ):
                    raise C4Stage1ReviewEnvironmentError(
                        "Review installed distribution set differs from exact pins"
                    )
                discovered[canonical_name] = (pin, path)
            elif path.parent == site_packages and (
                folded in _FORBIDDEN_SEED_PACKAGE_NAMES
                or folded.endswith(".egg-info")
                or folded.endswith(".egg-link")
            ):
                raise C4Stage1ReviewEnvironmentError(
                    "Review runtime contains package-manager seed residue"
                )
            scan(path)

    scan(runtime_root)
    if customization_count:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime contains executable path customization"
        )
    if (
        distribution_directory_count != len(PACKAGE_PIN_RECORDS)
        or set(discovered) != set(expected)
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review installed distribution inventory is not exact"
        )

    result = []
    for pin in PACKAGE_PIN_RECORDS:
        name = str(pin["name"])
        version = str(pin["version"])
        _, directory = discovered[_canonical_distribution_name(name)]
        directory_name = directory.name
        descriptors = []
        for filename in ("METADATA", "RECORD", "WHEEL"):
            relative = f"{VENV_DIRECTORY}/Lib/site-packages/{directory_name}/{filename}"
            descriptors.append(
                _file_descriptor(
                    directory / filename,
                    relative_path=relative,
                    checkpoint=checkpoint,
                )
            )
        body = {
            "name": name,
            "version": version,
            "dist_info_relative_path": (
                f"{VENV_DIRECTORY}/Lib/site-packages/{directory_name}"
            ),
            "identity_files": descriptors,
        }
        result.append(
            {
                "distribution_id": _content_id("c4_review_distribution", body),
                "distribution_sha256": _sha256(canonical_json_bytes(body)),
                **body,
            }
        )
    return result


def _canonical_distribution_name(value: str) -> str:
    normalized = _DISTRIBUTION_NAME_SEPARATOR.sub("-", value).casefold()
    if not normalized or normalized != normalized.strip("-"):
        raise C4Stage1ReviewEnvironmentError(
            "Review distribution name cannot be normalized"
        )
    return normalized


def _metadata_identity(payload: bytes) -> tuple[str, str]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Review distribution metadata is not UTF-8"
        ) from exc
    names = [line[5:].strip() for line in text.splitlines() if line.startswith("Name:")]
    versions = [
        line[8:].strip() for line in text.splitlines() if line.startswith("Version:")
    ]
    if (
        len(names) != 1
        or len(versions) != 1
        or not names[0]
        or not versions[0]
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review distribution metadata identity is invalid"
        )
    return names[0], versions[0]


def _browsers_json_descriptor(
    runtime_root: Path,
    *,
    checkpoint: Callable[[], None],
) -> dict[str, object]:
    path = runtime_root.joinpath(*BROWSERS_JSON_RELATIVE_PATH.split("/"))
    raw = _stable_file(path, maximum_bytes=4 * 1024 * 1024, checkpoint=checkpoint)
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Installed Playwright browsers.json is invalid"
        ) from exc
    if type(value) is not dict or type(value.get("browsers")) is not list:
        raise C4Stage1ReviewEnvironmentError(
            "Installed Playwright browsers.json has an invalid shape"
        )
    matches = [
        item
        for item in value["browsers"]
        if type(item) is dict and item.get("name") == "chromium"
    ]
    if len(matches) != 1 or matches[0] != {
        "name": "chromium",
        "revision": CHROMIUM_REVISION,
        "installByDefault": True,
        "browserVersion": CHROMIUM_VERSION,
        "title": "Chrome for Testing",
    }:
        raise C4Stage1ReviewEnvironmentError(
            "Installed Playwright Chromium descriptor differs from its pin"
        )
    return {
        "relative_path": BROWSERS_JSON_RELATIVE_PATH,
        "sha256": _sha256(raw),
        "size_bytes": len(raw),
    }


def _verified_wheels(
    runtime_root: Path,
    *,
    checkpoint: Callable[[], None],
) -> list[dict[str, object]]:
    wheelhouse = runtime_root / BOOTSTRAP_DATA_DIRECTORY / WHEELHOUSE_DIRECTORY
    wheelhouse = _existing_directory(wheelhouse)
    expected = {str(pin["filename"]): pin for pin in PACKAGE_PIN_RECORDS}
    try:
        names = tuple(sorted(entry.name for entry in os.scandir(wheelhouse)))
    except OSError as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime wheelhouse is unavailable"
        ) from exc
    if names != tuple(sorted(expected)):
        raise C4Stage1ReviewEnvironmentError("Review runtime wheelhouse is not exact")
    result = []
    for name in names:
        pin = expected[name]
        descriptor = _file_descriptor(
            wheelhouse / name,
            relative_path=name,
            checkpoint=checkpoint,
        )
        if (
            descriptor["sha256"] != pin["sha256"]
            or descriptor["size_bytes"] != pin["size_bytes"]
        ):
            raise C4Stage1ReviewEnvironmentError(
                "Review runtime wheel differs from its official pin"
            )
        result.append(descriptor)
    return result


def _validate_base_copy(
    value: object,
    runtime_manifest: Mapping[str, object],
) -> None:
    if type(value) is not dict or not _valid_digest(
        value.get("source_root_path_identity_sha256")
    ):
        raise C4Stage1ReviewEnvironmentError("Review base-copy evidence is invalid")
    records = []
    entries = runtime_manifest.get("entries")
    if type(entries) is not list:
        raise C4Stage1ReviewEnvironmentError("Review runtime entries are invalid")
    prefix = f"{COPIED_BASE_DIRECTORY}/"
    for entry in entries:
        if type(entry) is not dict or type(entry.get("relative_path")) is not str:
            raise C4Stage1ReviewEnvironmentError("Review runtime entry is invalid")
        relative = entry["relative_path"]
        if relative == COPIED_BASE_DIRECTORY:
            if entry != {"kind": "directory", "relative_path": COPIED_BASE_DIRECTORY}:
                raise C4Stage1ReviewEnvironmentError("Copied base root is invalid")
            continue
        if relative.startswith(prefix):
            projected = dict(entry)
            projected["relative_path"] = relative[len(prefix) :]
            records.append(projected)
    files = [record for record in records if record.get("kind") == "file"]
    directories = [record for record in records if record.get("kind") == "directory"]
    projection = {
        "copy_policy": "complete-ordinary-files-excluding-python-bytecode-v1",
        "file_count": len(files),
        "directory_count": len(directories) + 1,
        "total_size_bytes": sum(int(record["size_bytes"]) for record in files),
        "records": records,
    }
    digest = _sha256(canonical_json_bytes(projection))
    expected = {
        "schema_version": "rei-c4-stage1-review-base-copy-v1",
        "copy_policy": projection["copy_policy"],
        "source_root_path_stored": False,
        "source_root_path_identity_sha256": value["source_root_path_identity_sha256"],
        "destination_relative_path": COPIED_BASE_DIRECTORY,
        "file_count": projection["file_count"],
        "directory_count": projection["directory_count"],
        "total_size_bytes": projection["total_size_bytes"],
        "source_projection_content_sha256": digest,
        "source_projection_content_id": f"c4_review_base_copy_{digest[:32]}",
        "links_reparse_points_and_hardlinks_copied": False,
        "python_bytecode_and_cache_directories_copied": False,
    }
    if value != expected:
        raise C4Stage1ReviewEnvironmentError(
            "Review copied-base evidence differs from the complete runtime tree"
        )


def _validate_source_and_bootstrap_descriptors(
    provenance: Mapping[str, object],
) -> None:
    bootstrap = provenance.get("bootstrap_script")
    if (
        type(bootstrap) is not dict
        or set(bootstrap) != {"relative_path", "sha256", "size_bytes"}
        or bootstrap.get("relative_path") != BOOTSTRAP_RELATIVE_PATH
        or not _valid_digest(bootstrap.get("sha256"))
        or type(bootstrap.get("size_bytes")) is not int
        or bootstrap["size_bytes"] <= 0
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review bootstrap script descriptor is invalid"
        )
    source = provenance.get("source_base_python")
    source_keys = {
        "relative_path",
        "sha256",
        "size_bytes",
        "path_stored",
        "path_identity_sha256",
        "interpreter",
    }
    interpreter_keys = {
        "implementation",
        "version",
        "version_info",
        "cache_tag",
        "machine",
        "pointer_bits",
        "platform_tag",
        "is_venv",
    }
    if (
        type(source) is not dict
        or set(source) != source_keys
        or source.get("relative_path") != "base-python.exe"
        or not _valid_digest(source.get("sha256"))
        or type(source.get("size_bytes")) is not int
        or source["size_bytes"] <= 0
        or source.get("path_stored") is not False
        or not _valid_digest(source.get("path_identity_sha256"))
        or type(source.get("interpreter")) is not dict
        or set(source["interpreter"]) != interpreter_keys
        or source["interpreter"].get("implementation") != "CPython"
        or type(source["interpreter"].get("version_info")) is not list
        or len(source["interpreter"]["version_info"]) != 3
        or source["interpreter"]["version_info"][:2] != [3, 11]
        or not all(type(item) is int for item in source["interpreter"]["version_info"])
        or source["interpreter"].get("version")
        != ".".join(str(item) for item in source["interpreter"]["version_info"])
        or source["interpreter"].get("cache_tag") != "cpython-311"
        or str(source["interpreter"].get("machine")).casefold()
        not in {"amd64", "x86_64"}
        or source["interpreter"].get("pointer_bits") != 64
        or str(source["interpreter"].get("platform_tag")).casefold() != "win-amd64"
        or source["interpreter"].get("is_venv") is not False
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review source Python descriptor is invalid"
        )


def _verify_venv_configuration(
    runtime_root: Path,
    *,
    checkpoint: Callable[[], None],
) -> dict[str, object]:
    path = runtime_root.joinpath(*PYVENV_CONFIG_RELATIVE_PATH.split("/"))
    raw = _stable_file(path, maximum_bytes=65_536, checkpoint=checkpoint)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise C4Stage1ReviewEnvironmentError("Review pyvenv.cfg is not UTF-8") from exc
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition("=")
        normalized_key = key.strip().casefold()
        if not separator or not normalized_key or normalized_key in values:
            raise C4Stage1ReviewEnvironmentError(
                "Review pyvenv.cfg has an invalid shape"
            )
        values[normalized_key] = value.strip()
    copied_base = runtime_root / COPIED_BASE_DIRECTORY
    runtime_venv = runtime_root / VENV_DIRECTORY
    runtime_base_python = runtime_root.joinpath(
        *RUNTIME_BASE_PYTHON_RELATIVE_PATH.split("/")
    )
    command = values.get("command", "")
    if (
        os.path.normcase(values.get("home", ""))
        != os.path.normcase(os.fspath(copied_base))
        or values.get("include-system-site-packages", "").casefold() != "false"
        or os.path.normcase(values.get("executable", ""))
        != os.path.normcase(os.fspath(runtime_base_python))
        or os.path.normcase(os.fspath(copied_base)) not in os.path.normcase(command)
        or os.path.normcase(os.fspath(runtime_venv)) not in os.path.normcase(command)
        or "--copies" not in command.split()
        or "--without-pip" not in command.split()
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review venv does not bind the copied standalone base"
        )
    return {
        "relative_path": PYVENV_CONFIG_RELATIVE_PATH,
        "sha256": _sha256(raw),
        "size_bytes": len(raw),
    }


def _validate_process_records(value: object) -> None:
    if type(value) is not list or len(value) != len(_EXPECTED_WORKLOADS):
        raise C4Stage1ReviewEnvironmentError(
            "Review bootstrap process inventory is not exact"
        )
    forbidden = {
        "command",
        "environment",
        "working_directory",
        "stdout_bytes",
        "stderr_bytes",
    }
    for record, workload in zip(value, _EXPECTED_WORKLOADS, strict=True):
        stdout = record.get("stdout") if type(record) is dict else None
        stderr = record.get("stderr") if type(record) is dict else None
        if (
            type(record) is not dict
            or set(record) != _PROCESS_RECORD_KEYS
            or record.get("schema_version") != "rei-process-tree-execution-v1"
            or record.get("workload_id") != workload
            or record.get("status") != "succeeded"
            or forbidden.intersection(record)
            or type(stdout) is not dict
            or set(stdout) != _OUTPUT_SUMMARY_KEYS
            or not _valid_digest(stdout.get("sha256"))
            or not _valid_digest(stdout.get("captured_sha256"))
            or type(stderr) is not dict
            or set(stderr) != _OUTPUT_SUMMARY_KEYS
            or not _valid_digest(stderr.get("sha256"))
            or not _valid_digest(stderr.get("captured_sha256"))
        ):
            raise C4Stage1ReviewEnvironmentError(
                "Review bootstrap process evidence is invalid"
            )


def _manifest_summary(
    descriptor: Mapping[str, object],
    manifest: Mapping[str, object],
) -> dict[str, object]:
    return {
        "manifest_id": manifest["manifest_id"],
        "canonical_sha256": descriptor["sha256"],
        "canonical_size_bytes": descriptor["size_bytes"],
        "tree_content_id": manifest["tree_content_id"],
        "tree_content_sha256": manifest["tree_content_sha256"],
        "file_count": manifest["file_count"],
        "directory_count": manifest["directory_count"],
        "executable_count": manifest["executable_count"],
        "total_size_bytes": manifest["total_size_bytes"],
        "regular_files_only": True,
        "links_reparse_points_and_hardlinks_allowed": False,
        "python_bytecode_and_cache_directories_allowed": False,
    }


def verify_presenter_runtime(
    provenance_root: Path,
    runtime_root: Path,
    browser_root: Path,
    *,
    checkpoint: Callable[[], None],
) -> dict[str, object]:
    """Independently recapture and verify the exact presenter environment."""

    _checkpoint(checkpoint)
    provenance_root = _existing_directory(provenance_root)
    runtime_root = _existing_directory(runtime_root)
    browser_root = _existing_directory(browser_root)
    for left, right in (
        (provenance_root, runtime_root),
        (provenance_root, browser_root),
        (runtime_root, browser_root),
    ):
        _reject_overlap(left, right)
    repository_root = _existing_directory(REPOSITORY_ROOT)
    for external_root in (provenance_root, runtime_root, browser_root):
        _reject_overlap(external_root, repository_root)
    try:
        names = tuple(sorted(entry.name for entry in os.scandir(provenance_root)))
    except OSError as exc:
        raise C4Stage1ReviewEnvironmentError(
            "Review provenance inventory is unavailable"
        ) from exc
    if names != tuple(
        sorted((RUNTIME_MANIFEST_NAME, BROWSER_MANIFEST_NAME, PROVENANCE_NAME))
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review provenance inventory is not create-only exact"
        )
    provenance_raw, provenance = _load_canonical(
        provenance_root / PROVENANCE_NAME,
        checkpoint=checkpoint,
    )
    runtime_raw, runtime_manifest = _load_canonical(
        provenance_root / RUNTIME_MANIFEST_NAME,
        checkpoint=checkpoint,
    )
    browser_raw, browser_manifest = _load_canonical(
        provenance_root / BROWSER_MANIFEST_NAME,
        checkpoint=checkpoint,
    )
    _validate_path_bindings(
        provenance.get("path_bindings"),
        runtime_root=runtime_root,
        browser_root=browser_root,
        provenance_root=provenance_root,
    )
    if (
        set(provenance) != _PROVENANCE_KEYS
        or provenance.get("schema_version") != PROVENANCE_SCHEMA
        or provenance.get("bootstrap_schema") != BOOTSTRAP_SCHEMA
        or provenance.get("python_runtime_layout") != _runtime_layout()
        or provenance.get("packages") != list(PACKAGE_PIN_RECORDS)
        or provenance.get("installed_package_versions") != EXPECTED_PACKAGE_VERSIONS
        or provenance.get("wheel_download_verified_before_offline_install") is not True
        or provenance.get("matching_playwright_chromium_install_completed") is not True
        or provenance.get("install_verification_completed") is not True
        or provenance.get("install_verification_scope")
        != "hash-pinned-packages-browsers-json-marker-executable-and-full-trees"
        or provenance.get("browser_process_launch_performed") is not False
        or provenance.get("headed_full_ui_smoke_performed") is not False
        or provenance.get("headed_full_ui_smoke_authority")
        != "authenticated-review-service-only"
        or provenance.get("network_access_during_execution") is not True
        or provenance.get("network_access_during_verification") is not False
        or provenance.get("model_calls") != 0
        or provenance.get("secrets_stored") is not False
        or provenance.get("semantic_authority_granted") is not False
        or provenance.get("production_authority_granted") is not False
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime provenance differs from the frozen protocol"
        )
    _validate_source_and_bootstrap_descriptors(provenance)
    body = {key: value for key, value in provenance.items() if key != "provenance_id"}
    if provenance.get("provenance_id") != _content_id("c4_review_runtime", body):
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime provenance identity differs from content"
        )
    runtime_descriptor = _manifest_descriptor(
        RUNTIME_MANIFEST_NAME,
        runtime_raw,
        runtime_manifest,
    )
    browser_descriptor = _manifest_descriptor(
        BROWSER_MANIFEST_NAME,
        browser_raw,
        browser_manifest,
    )
    if (
        provenance.get("runtime_manifest") != runtime_descriptor
        or provenance.get("browser_manifest") != browser_descriptor
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review manifest descriptor differs from canonical bytes"
        )
    live_runtime = capture_c4_stage1_review_tree(
        runtime_root,
        tree_role="review-complete-python-runtime",
        checkpoint=checkpoint,
    )
    live_browser = capture_c4_stage1_review_tree(
        browser_root,
        tree_role="review-browser-runtime",
        checkpoint=checkpoint,
    )
    if live_runtime != runtime_manifest or live_browser != browser_manifest:
        raise C4Stage1ReviewEnvironmentError(
            "Review runtime tree differs from its sealed manifest"
        )
    _validate_base_copy(provenance.get("base_runtime_copy"), runtime_manifest)
    if provenance.get("verified_wheels") != _verified_wheels(
        runtime_root,
        checkpoint=checkpoint,
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review wheelhouse differs from official package pins"
        )
    distributions = _installed_distributions(runtime_root, checkpoint=checkpoint)
    if provenance.get("installed_distributions") != distributions:
        raise C4Stage1ReviewEnvironmentError(
            "Review installed distributions differ from provenance"
        )
    runtime_base = runtime_root.joinpath(*RUNTIME_BASE_PYTHON_RELATIVE_PATH.split("/"))
    runtime_python = runtime_root.joinpath(*RUNTIME_PYTHON_RELATIVE_PATH.split("/"))
    runtime_base_descriptor = _file_descriptor(
        runtime_base,
        relative_path=RUNTIME_BASE_PYTHON_RELATIVE_PATH,
        checkpoint=checkpoint,
    )
    runtime_python_descriptor = _file_descriptor(
        runtime_python,
        relative_path=RUNTIME_PYTHON_RELATIVE_PATH,
        checkpoint=checkpoint,
    )
    if (
        provenance.get("runtime_base_python") != runtime_base_descriptor
        or provenance.get("runtime_python") != runtime_python_descriptor
    ):
        raise C4Stage1ReviewEnvironmentError(
            "Review Python executable identity differs from provenance"
        )
    venv_configuration = _verify_venv_configuration(
        runtime_root,
        checkpoint=checkpoint,
    )
    browsers_json = _browsers_json_descriptor(runtime_root, checkpoint=checkpoint)
    chromium_path = browser_root.joinpath(*CHROMIUM_EXECUTABLE_RELATIVE_PATH.split("/"))
    marker_path = browser_root.joinpath(*CHROMIUM_MARKER_RELATIVE_PATH.split("/"))
    chromium_descriptor = _file_descriptor(
        chromium_path,
        relative_path=CHROMIUM_EXECUTABLE_RELATIVE_PATH,
        checkpoint=checkpoint,
    )
    marker_descriptor = _file_descriptor(
        marker_path,
        relative_path=CHROMIUM_MARKER_RELATIVE_PATH,
        checkpoint=checkpoint,
    )
    expected_browser = {
        "playwright_version": PLAYWRIGHT_VERSION,
        "name": "chromium",
        "revision": CHROMIUM_REVISION,
        "browser_version": CHROMIUM_VERSION,
        "browsers_json_source": PLAYWRIGHT_BROWSERS_JSON_SOURCE,
        "registry_source": PLAYWRIGHT_REGISTRY_SOURCE,
        "installed_browsers_json": browsers_json,
        "installation_marker": marker_descriptor,
        "executable": chromium_descriptor,
    }
    if provenance.get("browser") != expected_browser:
        raise C4Stage1ReviewEnvironmentError(
            "Review Chromium identity differs from provenance"
        )
    _validate_process_records(provenance.get("bounded_process_records"))
    summary_body = {
        "schema_version": VERIFICATION_SCHEMA,
        "provenance": {
            "provenance_id": provenance["provenance_id"],
            "canonical_sha256": _sha256(provenance_raw),
            "canonical_size_bytes": len(provenance_raw),
            "create_only_inventory_verified": True,
        },
        "runtime_manifest": _manifest_summary(runtime_descriptor, runtime_manifest),
        "browser_manifest": _manifest_summary(browser_descriptor, browser_manifest),
        "runtime_base_python": runtime_base_descriptor,
        "runtime_python": runtime_python_descriptor,
        "venv_configuration": venv_configuration,
        "installed_browsers_json": browsers_json,
        "installed_distributions": distributions,
        "chromium_executable": chromium_descriptor,
        "checkpoint_applied_during_all_file_and_tree_hashing": True,
        "paths_stored": False,
        "browser_process_launch_performed": False,
        "headed_full_ui_smoke_performed": False,
        "model_calls": 0,
    }
    _checkpoint(checkpoint)
    return {
        "verification_id": _content_id("c4_review_runtime_verification", summary_body),
        **summary_body,
    }


__all__ = [
    "BOOTSTRAP_DATA_DIRECTORY",
    "BROWSER_MANIFEST_NAME",
    "BROWSERS_JSON_RELATIVE_PATH",
    "CHROMIUM_EXECUTABLE_RELATIVE_PATH",
    "CHROMIUM_MARKER_RELATIVE_PATH",
    "CHROMIUM_REVISION",
    "CHROMIUM_VERSION",
    "COPIED_BASE_DIRECTORY",
    "C4Stage1ReviewEnvironmentError",
    "PACKAGE_PIN_RECORDS",
    "PLAYWRIGHT_VERSION",
    "PROVENANCE_NAME",
    "PYVENV_CONFIG_RELATIVE_PATH",
    "REVIEW_RUNTIME_IMPORT_PROBE_MODULES",
    "RUNTIME_BASE_PYTHON_RELATIVE_PATH",
    "RUNTIME_MANIFEST_NAME",
    "RUNTIME_PYTHON_RELATIVE_PATH",
    "VENV_DIRECTORY",
    "WHEELHOUSE_DIRECTORY",
    "canonical_json_bytes",
    "capture_c4_stage1_review_tree",
    "verify_presenter_runtime",
]
