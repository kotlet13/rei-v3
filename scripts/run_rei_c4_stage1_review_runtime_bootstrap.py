"""Plan, install, or verify the external C4 Stage 1 review browser runtime.

The install path is deliberately explicit: direct invocation is inert, and
the ``execute`` mode additionally requires ``--execute``.  Installation uses
an exact, hash-pinned Windows wheelhouse and Playwright's matching Chromium
installer under a dedicated ``PLAYWRIGHT_BROWSERS_PATH``.  Verification is
file based; this command never launches a browser or performs a model call.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import sys
from typing import Callable, Mapping


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.evaluation.process_tree_runner import (  # noqa: E402
    PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES,
    BoundedProcessRequest,
    BoundedProcessTreeRunner,
    ProcessTreeExecutionRecord,
)
from rei.evaluation import c4_stage1_review_environment as review_environment  # noqa: E402


BOOTSTRAP_SCHEMA = review_environment.BOOTSTRAP_SCHEMA
PLAN_SCHEMA = "rei-c4-stage1-review-runtime-bootstrap-plan-v1"
PROVENANCE_SCHEMA = review_environment.PROVENANCE_SCHEMA
TREE_MANIFEST_SCHEMA = review_environment.TREE_MANIFEST_SCHEMA
BOOTSTRAP_RELATIVE_PATH = "scripts/run_rei_c4_stage1_review_runtime_bootstrap.py"
RUNTIME_MANIFEST_NAME = review_environment.RUNTIME_MANIFEST_NAME
BROWSER_MANIFEST_NAME = review_environment.BROWSER_MANIFEST_NAME
PROVENANCE_NAME = review_environment.PROVENANCE_NAME
BOOTSTRAP_DATA_DIRECTORY = review_environment.BOOTSTRAP_DATA_DIRECTORY
WHEELHOUSE_DIRECTORY = review_environment.WHEELHOUSE_DIRECTORY
COPIED_BASE_DIRECTORY = review_environment.COPIED_BASE_DIRECTORY
VENV_DIRECTORY = review_environment.VENV_DIRECTORY
RUNTIME_BASE_PYTHON_RELATIVE_PATH = review_environment.RUNTIME_BASE_PYTHON_RELATIVE_PATH
RUNTIME_PYTHON_RELATIVE_PATH = review_environment.RUNTIME_PYTHON_RELATIVE_PATH
PYVENV_CONFIG_RELATIVE_PATH = review_environment.PYVENV_CONFIG_RELATIVE_PATH
BROWSERS_JSON_RELATIVE_PATH = review_environment.BROWSERS_JSON_RELATIVE_PATH
REVIEW_RUNTIME_IMPORT_PROBE_MODULES = (
    review_environment.REVIEW_RUNTIME_IMPORT_PROBE_MODULES
)

PLAYWRIGHT_VERSION = review_environment.PLAYWRIGHT_VERSION
CHROMIUM_REVISION = review_environment.CHROMIUM_REVISION
CHROMIUM_VERSION = review_environment.CHROMIUM_VERSION
CHROMIUM_EXECUTABLE_RELATIVE_PATH = review_environment.CHROMIUM_EXECUTABLE_RELATIVE_PATH
CHROMIUM_MARKER_RELATIVE_PATH = review_environment.CHROMIUM_MARKER_RELATIVE_PATH
PLAYWRIGHT_BROWSERS_JSON_SOURCE = review_environment.PLAYWRIGHT_BROWSERS_JSON_SOURCE
PLAYWRIGHT_REGISTRY_SOURCE = review_environment.PLAYWRIGHT_REGISTRY_SOURCE

_READ_CHUNK_BYTES = 4 * 1024 * 1024
_MAX_MANIFEST_FILES = 200_000
_MAX_MANIFEST_DIRECTORIES = 50_000
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024 * 1024
_MAX_PROVENANCE_BYTES = 64 * 1024 * 1024
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_EXECUTABLE_SUFFIXES = frozenset({".bat", ".cmd", ".com", ".exe", ".pyd"})
_BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})


@dataclass(frozen=True, slots=True)
class PackagePin:
    name: str
    version: str
    filename: str
    size_bytes: int
    sha256: str
    artifact_url: str
    metadata_url: str
    selection_policy: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "artifact_url": self.artifact_url,
            "metadata_url": self.metadata_url,
            "selection_policy": self.selection_policy,
        }


PACKAGE_PINS = tuple(
    PackagePin(**record) for record in review_environment.PACKAGE_PIN_RECORDS
)

_EXPECTED_PACKAGE_VERSIONS = {pin.name: pin.version for pin in PACKAGE_PINS}
_EXPECTED_PACKAGE_DISTRIBUTIONS = sorted(
    [
        {
            "canonical_name": pin.name.replace("_", "-").casefold(),
            "version": pin.version,
        }
        for pin in PACKAGE_PINS
    ],
    key=lambda item: (item["canonical_name"], item["version"]),
)
_STEP_TIMEOUTS = {
    "base_python_probe": 30.0,
    "copied_base_python_probe": 30.0,
    "create_copy_venv": 180.0,
    "runtime_python_layout_probe": 30.0,
    "download_hash_pinned_wheels": 900.0,
    "install_offline_wheelhouse": 600.0,
    "installed_package_probe": 30.0,
    "review_import_contract_probe": 30.0,
    "install_matching_chromium": 2_400.0,
}


class C4Stage1ReviewRuntimeBootstrapError(RuntimeError):
    """The external review runtime did not satisfy its frozen protocol."""


@dataclass(frozen=True, slots=True)
class _ProcessOutcome:
    stdout: bytes
    record: dict[str, object]


@dataclass(frozen=True, slots=True)
class _Roots:
    runtime: Path
    browser: Path
    provenance: Path
    artifacts: tuple[Path, ...]
    models: tuple[Path, ...]
    states: tuple[Path, ...]


def _canonical_json_bytes(value: object) -> bytes:
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
    return f"{prefix}_{_sha256(_canonical_json_bytes(value))[:32]}"


def _path_identity(path: Path) -> str:
    normalized = os.path.normcase(os.path.abspath(os.fspath(path))).replace("\\", "/")
    return _sha256(normalized.encode("utf-8", errors="strict"))


def _is_link_or_reparse(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _require_absolute_lexical(path: Path) -> None:
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap paths must be lexical absolute paths"
        )


def _assert_unlinked_ancestry(path: Path) -> None:
    _require_absolute_lexical(path)
    current = path
    while True:
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap ancestry is unavailable"
            ) from exc
        if _is_link_or_reparse(metadata):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap rejects links and reparse points"
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
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap directory is unavailable"
        ) from exc
    if _is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap requires ordinary directories"
        )
    return resolved


def _fresh_target(path: Path) -> Path:
    _require_absolute_lexical(path)
    if path.exists() or path.is_symlink():
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap roots must be fresh"
        )
    parent = _existing_directory(path.parent)
    target = parent / path.name
    if target.exists() or target.is_symlink():
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap roots must remain absent"
        )
    return target


def _contains(left: Path, right: Path) -> bool:
    left_value = os.path.normcase(os.path.abspath(os.fspath(left)))
    right_value = os.path.normcase(os.path.abspath(os.fspath(right)))
    try:
        return os.path.commonpath((left_value, right_value)) == left_value
    except ValueError:
        return False


def _reject_overlap(left: Path, right: Path) -> None:
    if _contains(left, right) or _contains(right, left):
        raise C4Stage1ReviewRuntimeBootstrapError("C4 review bootstrap roots overlap")


def _normalize_roots(
    arguments: argparse.Namespace,
    *,
    fresh: bool,
    provenance_fresh: bool | None = None,
) -> _Roots:
    converter = _fresh_target if fresh else _existing_directory
    runtime = converter(arguments.runtime_root)
    browser = converter(arguments.browser_root)
    provenance_converter = (
        converter
        if provenance_fresh is None
        else (_fresh_target if provenance_fresh else _existing_directory)
    )
    provenance = provenance_converter(arguments.provenance_root)
    artifacts = tuple(_existing_directory(path) for path in arguments.artifact_root)
    models = tuple(_existing_directory(path) for path in arguments.model_root)
    states = tuple(_existing_directory(path) for path in arguments.state_root)
    roots = _Roots(
        runtime=runtime,
        browser=browser,
        provenance=provenance,
        artifacts=artifacts,
        models=models,
        states=states,
    )
    isolated = (runtime, browser, provenance)
    for index, left in enumerate(isolated):
        for right in isolated[index + 1 :]:
            _reject_overlap(left, right)
    repository = _existing_directory(ROOT)
    for target in isolated:
        _reject_overlap(target, repository)
        for forbidden in (*artifacts, *models, *states):
            _reject_overlap(target, forbidden)
    return roots


def _rollback_fresh_roots(roots: _Roots) -> None:
    """Remove only roots that this failed create-only execution could own."""

    def remove(path: Path) -> None:
        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap rollback could not inspect its root"
            ) from exc
        if _is_link_or_reparse(metadata):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap rollback rejects replaced roots"
            )
        if stat.S_ISDIR(metadata.st_mode):
            try:
                children = tuple(entry.name for entry in os.scandir(path))
            except OSError as exc:
                raise C4Stage1ReviewRuntimeBootstrapError(
                    "C4 review bootstrap rollback inventory is unavailable"
                ) from exc
            for name in children:
                remove(path / name)
            try:
                os.rmdir(path)
            except OSError as exc:
                raise C4Stage1ReviewRuntimeBootstrapError(
                    "C4 review bootstrap rollback could not remove a directory"
                ) from exc
            return
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap rollback rejects special entries"
            )
        try:
            os.unlink(path)
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap rollback could not remove a file"
            ) from exc

    for path in (roots.provenance, roots.browser, roots.runtime):
        remove(path)


def _checkpoint(checkpoint: Callable[[], None] | None) -> None:
    if checkpoint is not None:
        checkpoint()


def _stable_file(
    path: Path,
    *,
    maximum_bytes: int = _MAX_MANIFEST_BYTES,
    checkpoint: Callable[[], None] | None = None,
) -> bytes:
    _checkpoint(checkpoint)
    _assert_unlinked_ancestry(path)
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap file is unavailable"
        ) from exc
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 <= before.st_size <= maximum_bytes
    ):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap requires one-link ordinary files"
        )
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap file could not be opened"
        ) from exc
    chunks: list[bytes] = []
    size = 0
    try:
        opened = os.fstat(descriptor)
        if not os.path.samestat(before, opened):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap file identity changed"
            )
        while True:
            _checkpoint(checkpoint)
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if size > maximum_bytes:
                raise C4Stage1ReviewRuntimeBootstrapError(
                    "C4 review bootstrap file exceeds its bound"
                )
            chunks.append(chunk)
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap file disappeared"
        ) from exc
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
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap file changed during capture"
        )
    _checkpoint(checkpoint)
    return b"".join(chunks)


def _file_descriptor(
    path: Path,
    *,
    relative_path: str,
    checkpoint: Callable[[], None] | None = None,
) -> dict[str, object]:
    payload = _stable_file(path, checkpoint=checkpoint)
    return {
        "relative_path": relative_path,
        "sha256": _sha256(payload),
        "size_bytes": len(payload),
    }


def _capture_tree(
    root: Path,
    *,
    tree_role: str,
    checkpoint: Callable[[], None] | None = None,
) -> dict[str, object]:
    return review_environment.capture_c4_stage1_review_tree(
        root,
        tree_role=tree_role,
        checkpoint=(checkpoint if checkpoint is not None else lambda: None),
    )


def _copy_base_runtime(source_root: Path, runtime_root: Path) -> dict[str, object]:
    """Create an ordinary-file, bytecode-free standalone CPython base copy."""

    source_root = _existing_directory(source_root)
    runtime_root = _fresh_target(runtime_root)
    copied_base = runtime_root / COPIED_BASE_DIRECTORY
    try:
        os.mkdir(runtime_root)
        os.mkdir(copied_base)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap base-copy root could not be created"
        ) from exc
    records: list[dict[str, object]] = []
    counters = {"files": 0, "directories": 1, "bytes": 0}

    def copy_file(source: Path, destination: Path, relative: str) -> None:
        try:
            before = os.lstat(source)
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap source runtime file is unavailable"
            ) from exc
        if (
            _is_link_or_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not 0 <= before.st_size <= _MAX_MANIFEST_BYTES
        ):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap source runtime file is not ordinary"
            )
        source_flags = (
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        destination_flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            source_handle = os.open(source, source_flags)
            destination_handle = os.open(destination, destination_flags, 0o600)
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap base-copy file could not be opened"
            ) from exc
        digest = hashlib.sha256()
        size = 0
        try:
            opened = os.fstat(source_handle)
            if not os.path.samestat(before, opened):
                raise C4Stage1ReviewRuntimeBootstrapError(
                    "C4 review bootstrap source runtime identity changed"
                )
            while True:
                chunk = os.read(source_handle, _READ_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                counters["bytes"] += len(chunk)
                if (
                    size > _MAX_MANIFEST_BYTES
                    or counters["bytes"] > _MAX_MANIFEST_BYTES
                ):
                    raise C4Stage1ReviewRuntimeBootstrapError(
                        "C4 review bootstrap base copy exceeds its byte bound"
                    )
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(destination_handle, view)
                    if written <= 0:
                        raise C4Stage1ReviewRuntimeBootstrapError(
                            "C4 review bootstrap base copy stopped short"
                        )
                    view = view[written:]
            os.fsync(destination_handle)
            final_source = os.fstat(source_handle)
            final_destination = os.fstat(destination_handle)
        finally:
            os.close(source_handle)
            os.close(destination_handle)
        try:
            after = os.lstat(source)
            copied = os.lstat(destination)
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap base copy changed during capture"
            ) from exc
        if (
            not os.path.samestat(before, final_source)
            or not os.path.samestat(before, after)
            or before.st_size != size
            or final_source.st_size != size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or _is_link_or_reparse(copied)
            or not stat.S_ISREG(copied.st_mode)
            or copied.st_nlink != 1
            or not os.path.samestat(final_destination, copied)
            or copied.st_size != size
        ):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap base copy was not stable"
            )
        counters["files"] += 1
        if counters["files"] > _MAX_MANIFEST_FILES:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap base copy has too many files"
            )
        records.append(
            {
                "kind": "file",
                "relative_path": relative,
                "sha256": digest.hexdigest(),
                "size_bytes": size,
            }
        )

    def scan(source: Path, destination: Path, parts: tuple[str, ...]) -> None:
        try:
            before = os.lstat(source)
            names = tuple(sorted(entry.name for entry in os.scandir(source)))
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap source runtime tree is unavailable"
            ) from exc
        if _is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap source runtime tree is invalid"
            )
        for name in names:
            source_child = source / name
            child_parts = (*parts, name)
            relative = "/".join(child_parts)
            try:
                relative.encode("utf-8", errors="strict")
                metadata = os.lstat(source_child)
            except (OSError, UnicodeError) as exc:
                raise C4Stage1ReviewRuntimeBootstrapError(
                    "C4 review bootstrap source runtime entry is invalid"
                ) from exc
            if _is_link_or_reparse(metadata):
                raise C4Stage1ReviewRuntimeBootstrapError(
                    "C4 review bootstrap source runtime contains a link"
                )
            if name.casefold() == "__pycache__" or source_child.suffix.casefold() in (
                _BYTECODE_SUFFIXES
            ):
                continue
            destination_child = destination / name
            if stat.S_ISDIR(metadata.st_mode):
                counters["directories"] += 1
                if counters["directories"] > _MAX_MANIFEST_DIRECTORIES:
                    raise C4Stage1ReviewRuntimeBootstrapError(
                        "C4 review bootstrap base copy has too many directories"
                    )
                try:
                    os.mkdir(destination_child)
                except OSError as exc:
                    raise C4Stage1ReviewRuntimeBootstrapError(
                        "C4 review bootstrap base-copy directory could not be created"
                    ) from exc
                records.append({"kind": "directory", "relative_path": relative})
                scan(source_child, destination_child, child_parts)
            elif stat.S_ISREG(metadata.st_mode):
                copy_file(source_child, destination_child, relative)
            else:
                raise C4Stage1ReviewRuntimeBootstrapError(
                    "C4 review bootstrap source runtime contains a special file"
                )
        try:
            after = os.lstat(source)
            final_names = tuple(sorted(entry.name for entry in os.scandir(source)))
        except OSError as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap source runtime changed during copy"
            ) from exc
        if not os.path.samestat(before, after) or names != final_names:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap source runtime changed during copy"
            )

    scan(source_root, copied_base, ())
    if counters["files"] == 0 or counters["bytes"] == 0:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap source runtime projection is empty"
        )
    projection = {
        "copy_policy": "complete-ordinary-files-excluding-python-bytecode-v1",
        "file_count": counters["files"],
        "directory_count": counters["directories"],
        "total_size_bytes": counters["bytes"],
        "records": records,
    }
    projection_sha256 = _sha256(_canonical_json_bytes(projection))
    return {
        "schema_version": "rei-c4-stage1-review-base-copy-v1",
        "copy_policy": projection["copy_policy"],
        "source_root_path_stored": False,
        "source_root_path_identity_sha256": _path_identity(source_root),
        "destination_relative_path": COPIED_BASE_DIRECTORY,
        "file_count": counters["files"],
        "directory_count": counters["directories"],
        "total_size_bytes": counters["bytes"],
        "source_projection_content_sha256": projection_sha256,
        "source_projection_content_id": (
            f"c4_review_base_copy_{projection_sha256[:32]}"
        ),
        "links_reparse_points_and_hardlinks_copied": False,
        "python_bytecode_and_cache_directories_copied": False,
    }


def _run_bounded(
    *,
    step: str,
    command: tuple[str, ...],
    working_directory: Path,
    environment: Mapping[str, str],
) -> _ProcessOutcome:
    command_body = {"step": step, "argv": command}
    environment_policy = {
        "policy": "c4-review-bootstrap-minimal-environment-v1",
        "variable_names": sorted(environment),
        "raw_values_stored": False,
    }
    request = BoundedProcessRequest(
        workload_id=f"c4-review-bootstrap-{step.replace('_', '-')}",
        command_identity=f"command-{_sha256(_canonical_json_bytes(command_body))[:32]}",
        working_directory_identity=f"cwd-{_path_identity(working_directory)[:32]}",
        environment_identity=(
            f"environment-{_sha256(_canonical_json_bytes(environment_policy))[:32]}"
        ),
        command=command,
        working_directory=working_directory,
        environment=environment,
        timeout_seconds=_STEP_TIMEOUTS[step],
        stdout_limit_bytes=PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES,
        stderr_limit_bytes=PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES,
    )
    result = BoundedProcessTreeRunner().run(request)
    if not result.succeeded:
        raise C4Stage1ReviewRuntimeBootstrapError(
            f"C4 review bootstrap process failed closed ({step})"
        )
    return _ProcessOutcome(
        stdout=result.stdout,
        record=result.record.model_dump(mode="json", round_trip=True),
    )


def _base_environment(*, browser_root: Path | None = None) -> dict[str, str]:
    allowed = {
        "ALL_PROXY",
        "APPDATA",
        "COMSPEC",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "LOCALAPPDATA",
        "NO_PROXY",
        "PATH",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
    environment = {
        key: value for key, value in os.environ.items() if key.upper() in allowed
    }
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    if browser_root is not None:
        environment["PLAYWRIGHT_BROWSERS_PATH"] = os.fspath(browser_root)
    return environment


_PYTHON_PROBE = (
    "import json,platform,struct,sys,sysconfig;"
    "print(json.dumps({"
    "'implementation':platform.python_implementation(),"
    "'version':platform.python_version(),"
    "'version_info':list(sys.version_info[:3]),"
    "'cache_tag':sys.implementation.cache_tag,"
    "'machine':platform.machine(),"
    "'pointer_bits':struct.calcsize('P')*8,"
    "'platform_tag':sysconfig.get_platform(),"
    "'executable':sys.executable,"
    "'prefix':sys.prefix,"
    "'base_prefix':sys.base_prefix,"
    "'is_venv':sys.prefix!=sys.base_prefix},"
    "sort_keys=True,separators=(',',':')))"
)

_PACKAGE_PROBE = (
    "import importlib.metadata as m,json,re,sys;"
    "norm=lambda v:re.sub(r'[-_.]+','-',v).casefold();"
    "items=sorted((norm(d.metadata['Name']),d.version) "
    "for d in m.distributions(path=[sys.argv[1]]));"
    "print(json.dumps({'distributions':[{'canonical_name':n,'version':v} "
    "for n,v in items]},sort_keys=True,separators=(',',':')))"
)

_REVIEW_IMPORT_PROBE = (
    "import importlib,json,sys;"
    "sys.path[:0]=[sys.argv[2],sys.argv[1]];"
    f"names={REVIEW_RUNTIME_IMPORT_PROBE_MODULES!r};"
    "[importlib.import_module(name) for name in names];"
    "print(json.dumps({'imported':list(names)},"
    "sort_keys=True,separators=(',',':')))"
)

_STDLIB_WHEEL_DOWNLOADER = r"""
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.parse
import urllib.request

manifest_path = Path(sys.argv[1])
if sys.argv[2] != "--dest":
    raise SystemExit(64)
wheelhouse = Path(sys.argv[3])
raw = manifest_path.read_bytes()
manifest = json.loads(raw.decode("utf-8", errors="strict"))
if json.dumps(manifest, ensure_ascii=False, allow_nan=False, sort_keys=True,
              separators=(",", ":")).encode("utf-8") != raw:
    raise RuntimeError("non-canonical wheel manifest")
records = manifest.get("packages")
if manifest.get("schema_version") != "rei-c4-review-wheel-download-v1" or not isinstance(records, list) or len(records) != 8:
    raise RuntimeError("invalid wheel manifest")
if sorted(path.name for path in wheelhouse.iterdir()):
    raise RuntimeError("wheelhouse is not fresh")
context = ssl.create_default_context()
for record in records:
    if set(record) != {"artifact_url", "filename", "sha256", "size_bytes"}:
        raise RuntimeError("invalid wheel record")
    url = record["artifact_url"]
    filename = record["filename"]
    digest = record["sha256"]
    size = record["size_bytes"]
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme, parsed.hostname) != ("https", "files.pythonhosted.org") or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("untrusted wheel URL")
    if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith(".whl"):
        raise RuntimeError("invalid wheel filename")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError("invalid wheel digest")
    if not isinstance(size, int) or not 0 < size <= 128 * 1024 * 1024:
        raise RuntimeError("invalid wheel size")
    target = wheelhouse / filename
    request = urllib.request.Request(url, headers={"User-Agent": "REI-C4-review-bootstrap/1"})
    handle = None
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            if response.geturl() != url or getattr(response, "status", 200) != 200:
                raise RuntimeError("wheel URL redirected or failed")
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) != size:
                raise RuntimeError("wheel length differs from pin")
            handle = target.open("xb")
            sha = hashlib.sha256()
            observed = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                observed += len(chunk)
                if observed > size:
                    raise RuntimeError("wheel exceeds pin")
                sha.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if observed != size or sha.hexdigest() != digest:
            raise RuntimeError("wheel differs from pin")
    except Exception:
        if handle is not None:
            handle.close()
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        if handle is not None and not handle.closed:
            handle.close()
"""

_STDLIB_WHEEL_MEMBER_POLICY = r"""
from pathlib import PurePosixPath

_WINDOWS_RESERVED_WHEEL_BASENAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

def validated_wheel_member_parts(name):
    if not isinstance(name, str) or "\\" in name or "\x00" in name or name.startswith("/"):
        raise RuntimeError("unsafe wheel member")
    parts = PurePosixPath(name).parts
    if not parts:
        raise RuntimeError("unsafe wheel member")
    for part in parts:
        if part in {"", ".", ".."} or ":" in part or part.endswith((" ", ".")):
            raise RuntimeError("unsafe Windows wheel member")
        device_basename = part.split(".", 1)[0].rstrip(" .").upper()
        if device_basename in _WINDOWS_RESERVED_WHEEL_BASENAMES:
            raise RuntimeError("reserved Windows wheel member")
    return parts
"""

_STDLIB_WHEEL_INSTALLER = _STDLIB_WHEEL_MEMBER_POLICY + r"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

manifest_path = Path(sys.argv[1])
if sys.argv[2] != "--wheelhouse" or sys.argv[4] != "--venv-root":
    raise SystemExit(64)
wheelhouse = Path(sys.argv[3])
venv_root = Path(sys.argv[5])
site_packages = venv_root / "Lib" / "site-packages"
scripts = venv_root / "Scripts"
raw = manifest_path.read_bytes()
manifest = json.loads(raw.decode("utf-8", errors="strict"))
if json.dumps(manifest, ensure_ascii=False, allow_nan=False, sort_keys=True,
              separators=(",", ":")).encode("utf-8") != raw:
    raise RuntimeError("non-canonical wheel manifest")
records = manifest.get("packages")
if manifest.get("schema_version") != "rei-c4-review-wheel-install-v1" or not isinstance(records, list) or len(records) != 8:
    raise RuntimeError("invalid wheel manifest")
expected_names = sorted(record["filename"] for record in records)
if sorted(path.name for path in wheelhouse.iterdir()) != expected_names:
    raise RuntimeError("wheelhouse inventory differs from manifest")
seen_targets = set()
file_count = 0
total_uncompressed = 0

def target_for(name):
    parts = validated_wheel_member_parts(name)
    if parts[0].endswith(".data"):
        if len(parts) < 3 or parts[1] not in {"purelib", "platlib", "scripts"}:
            raise RuntimeError("unsupported wheel data scheme")
        base = scripts if parts[1] == "scripts" else site_packages
        relative = Path(*parts[2:])
    else:
        base = site_packages
        relative = Path(*parts)
    target = base / relative
    key = os.path.normcase(os.path.abspath(os.fspath(target)))
    venv_key = os.path.normcase(os.path.abspath(os.fspath(venv_root)))
    if os.path.commonpath((venv_key, key)) != venv_key:
        raise RuntimeError("wheel member escapes venv")
    return target, key

def safe_parent(parent):
    relative = parent.relative_to(venv_root)
    current = venv_root
    for part in relative.parts:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            current.mkdir()
            metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError("wheel target ancestry is unsafe")

for record in records:
    if set(record) != {"filename", "sha256", "size_bytes"}:
        raise RuntimeError("invalid wheel record")
    wheel = wheelhouse / record["filename"]
    payload_sha = hashlib.sha256()
    observed = 0
    with wheel.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            payload_sha.update(chunk)
    if observed != record["size_bytes"] or payload_sha.hexdigest() != record["sha256"]:
        raise RuntimeError("wheel differs from manifest")
    with zipfile.ZipFile(wheel) as archive:
        archive_names = [item.filename for item in archive.infolist()]
        if len(archive_names) != len(set(archive_names)):
            raise RuntimeError("wheel contains duplicate members")
        for item in archive.infolist():
            target, key = target_for(item.filename.rstrip("/"))
            mode = item.external_attr >> 16
            kind = stat.S_IFMT(mode)
            is_directory = item.is_dir()
            if kind not in {0, stat.S_IFREG, stat.S_IFDIR} or (kind == stat.S_IFDIR) != is_directory:
                raise RuntimeError("wheel contains link or special member")
            if key in seen_targets:
                raise RuntimeError("wheel target collision")
            seen_targets.add(key)
            if is_directory:
                safe_parent(target.parent)
                target.mkdir(exist_ok=False)
                continue
            file_count += 1
            total_uncompressed += item.file_size
            if file_count > 100000 or item.file_size > 512 * 1024 * 1024 or total_uncompressed > 2 * 1024 * 1024 * 1024:
                raise RuntimeError("wheel extraction bound exceeded")
            safe_parent(target.parent)
            with archive.open(item, "r") as source, target.open("xb") as destination:
                remaining = item.file_size
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError("short wheel member")
                    destination.write(chunk)
                    remaining -= len(chunk)
                if source.read(1):
                    raise RuntimeError("long wheel member")
                destination.flush()
                os.fsync(destination.fileno())
"""

_PLAYWRIGHT_INSTALL = (
    "import runpy,sys;"
    "sys.path.insert(0,sys.argv.pop(1));"
    "runpy.run_module('playwright',run_name='__main__')"
)


def _parse_probe(stdout: bytes) -> dict[str, object]:
    if not 0 < len(stdout) <= 16_384:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap probe output has an invalid size"
        )
    try:
        value = json.loads(stdout.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap probe output is invalid"
        ) from exc
    if type(value) is not dict:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap probe output has an invalid shape"
        )
    return value


def _probe_base_python(
    base_python: Path,
    *,
    step: str = "base_python_probe",
    relative_path: str = "base-python.exe",
) -> tuple[dict[str, object], dict[str, object]]:
    base_descriptor = _file_descriptor(base_python, relative_path=relative_path)
    outcome = _run_bounded(
        step=step,
        command=(os.fspath(base_python), "-I", "-S", "-B", "-c", _PYTHON_PROBE),
        working_directory=ROOT,
        environment=_base_environment(),
    )
    probe = _parse_probe(outcome.stdout)
    required = {
        "implementation",
        "version",
        "version_info",
        "cache_tag",
        "machine",
        "pointer_bits",
        "platform_tag",
        "executable",
        "prefix",
        "base_prefix",
        "is_venv",
    }
    if (
        set(probe) != required
        or probe["implementation"] != "CPython"
        or type(probe["version_info"]) is not list
        or probe["version_info"][:2] != [3, 11]
        or probe["cache_tag"] != "cpython-311"
        or str(probe["machine"]).casefold() not in {"amd64", "x86_64"}
        or probe["pointer_bits"] != 64
        or str(probe["platform_tag"]).casefold() != "win-amd64"
        or probe["is_venv"] is not False
        or os.path.normcase(str(probe["prefix"]))
        != os.path.normcase(os.fspath(base_python.parent))
        or os.path.normcase(str(probe["base_prefix"]))
        != os.path.normcase(os.fspath(base_python.parent))
        or os.path.normcase(str(probe["executable"]))
        != os.path.normcase(os.fspath(base_python))
    ):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap requires ordinary 64-bit CPython 3.11 on Windows"
        )
    public_probe = {
        key: value
        for key, value in probe.items()
        if key not in {"executable", "prefix", "base_prefix"}
    }
    return (
        {
            **base_descriptor,
            "path_stored": False,
            "path_identity_sha256": _path_identity(base_python),
            "interpreter": public_probe,
        },
        outcome.record,
    )


def _probe_runtime_python(
    runtime_python: Path,
    *,
    copied_base_root: Path,
    runtime_venv_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    descriptor = _file_descriptor(
        runtime_python,
        relative_path=RUNTIME_PYTHON_RELATIVE_PATH,
    )
    outcome = _run_bounded(
        step="runtime_python_layout_probe",
        command=(
            os.fspath(runtime_python),
            "-I",
            "-S",
            "-B",
            "-c",
            _PYTHON_PROBE,
        ),
        working_directory=ROOT,
        environment=_base_environment(),
    )
    probe = _parse_probe(outcome.stdout)
    if (
        probe.get("implementation") != "CPython"
        or probe.get("version_info", [None, None])[:2] != [3, 11]
        or probe.get("cache_tag") != "cpython-311"
        or probe.get("pointer_bits") != 64
        or probe.get("is_venv") is not True
        or os.path.normcase(str(probe.get("executable")))
        != os.path.normcase(os.fspath(runtime_python))
        or os.path.normcase(str(probe.get("prefix")))
        != os.path.normcase(os.fspath(runtime_venv_root))
        or os.path.normcase(str(probe.get("base_prefix")))
        != os.path.normcase(os.fspath(copied_base_root))
    ):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review runtime Python does not bind the copied standalone base"
        )
    return descriptor, outcome.record


def _write_create_only(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap provenance is create-only"
        ) from exc


def _write_lockfiles(runtime_root: Path) -> tuple[Path, Path, Path]:
    data_root = runtime_root / BOOTSTRAP_DATA_DIRECTORY
    wheelhouse = data_root / WHEELHOUSE_DIRECTORY
    try:
        data_root.mkdir()
        wheelhouse.mkdir()
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap lock directory could not be created"
        ) from exc
    download_lock = data_root / "download.lock"
    install_lock = data_root / "install.lock"
    download_manifest = {
        "schema_version": "rei-c4-review-wheel-download-v1",
        "packages": [
            {
                "artifact_url": pin.artifact_url,
                "filename": pin.filename,
                "sha256": pin.sha256,
                "size_bytes": pin.size_bytes,
            }
            for pin in PACKAGE_PINS
        ],
    }
    install_manifest = {
        "schema_version": "rei-c4-review-wheel-install-v1",
        "packages": [
            {
                "filename": pin.filename,
                "sha256": pin.sha256,
                "size_bytes": pin.size_bytes,
            }
            for pin in PACKAGE_PINS
        ],
    }
    _write_create_only(download_lock, _canonical_json_bytes(download_manifest))
    _write_create_only(install_lock, _canonical_json_bytes(install_manifest))
    return download_lock, install_lock, wheelhouse


def _verify_wheelhouse(
    wheelhouse: Path,
    *,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[dict[str, object], ...]:
    expected = {pin.filename: pin for pin in PACKAGE_PINS}
    try:
        names = tuple(sorted(entry.name for entry in os.scandir(wheelhouse)))
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap wheelhouse is unavailable"
        ) from exc
    if names != tuple(sorted(expected)):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap wheelhouse is not exact"
        )
    descriptors = []
    for name in names:
        _checkpoint(checkpoint)
        pin = expected[name]
        descriptor = _file_descriptor(
            wheelhouse / name,
            relative_path=name,
            checkpoint=checkpoint,
        )
        if (
            descriptor["sha256"] != pin.sha256
            or descriptor["size_bytes"] != pin.size_bytes
        ):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap wheel differs from its official pin"
            )
        descriptors.append(descriptor)
    return tuple(descriptors)


def _verify_installed_packages(
    runtime_python: Path,
    *,
    browser_root: Path,
) -> dict[str, object]:
    outcome = _run_bounded(
        step="installed_package_probe",
        command=(
            os.fspath(runtime_python),
            "-I",
            "-S",
            "-B",
            "-c",
            _PACKAGE_PROBE,
            os.fspath(runtime_python.parents[1] / "Lib" / "site-packages"),
        ),
        working_directory=ROOT,
        environment=_base_environment(browser_root=browser_root),
    )
    versions = _parse_probe(outcome.stdout)
    if versions != {"distributions": _EXPECTED_PACKAGE_DISTRIBUTIONS}:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap installed package versions differ from pins"
        )
    return outcome.record


def _verify_review_import_contract(
    runtime_python: Path,
    *,
    browser_root: Path,
) -> dict[str, object]:
    outcome = _run_bounded(
        step="review_import_contract_probe",
        command=(
            os.fspath(runtime_python),
            "-I",
            "-S",
            "-B",
            "-c",
            _REVIEW_IMPORT_PROBE,
            os.fspath(runtime_python.parents[1] / "Lib" / "site-packages"),
            os.fspath(BACKEND_ROOT),
        ),
        working_directory=ROOT,
        environment=_base_environment(browser_root=browser_root),
    )
    imported = _parse_probe(outcome.stdout)
    if imported != {"imported": list(REVIEW_RUNTIME_IMPORT_PROBE_MODULES)}:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review runtime cannot import its sealed service contract"
        )
    return outcome.record


def _verify_installed_browser_descriptor(
    runtime_root: Path,
    *,
    checkpoint: Callable[[], None] | None = None,
) -> dict[str, object]:
    browsers_json = runtime_root.joinpath(*BROWSERS_JSON_RELATIVE_PATH.split("/"))
    raw = _stable_file(
        browsers_json,
        maximum_bytes=4 * 1024 * 1024,
        checkpoint=checkpoint,
    )
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "Installed Playwright browsers.json is invalid"
        ) from exc
    if type(value) is not dict or type(value.get("browsers")) is not list:
        raise C4Stage1ReviewRuntimeBootstrapError(
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
        raise C4Stage1ReviewRuntimeBootstrapError(
            "Installed Playwright browser descriptor differs from the frozen pin"
        )
    return {
        "relative_path": BROWSERS_JSON_RELATIVE_PATH,
        "sha256": _sha256(raw),
        "size_bytes": len(raw),
    }


def _capture_installed_distributions(
    runtime_root: Path,
    *,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[dict[str, object], ...]:
    try:
        return tuple(
            review_environment._installed_distributions(  # noqa: SLF001
                runtime_root,
                checkpoint=checkpoint or (lambda: None),
            )
        )
    except review_environment.C4Stage1ReviewEnvironmentError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review active runtime distribution policy failed"
        ) from exc


def _manifest_descriptor(
    name: str, payload: bytes, manifest: Mapping[str, object]
) -> dict[str, object]:
    return {
        "relative_path": name,
        "manifest_id": manifest["manifest_id"],
        "sha256": _sha256(payload),
        "size_bytes": len(payload),
    }


def _path_bindings(roots: _Roots) -> dict[str, object]:
    return {
        "paths_stored": False,
        "runtime_root_identity_sha256": _path_identity(roots.runtime),
        "browser_root_identity_sha256": _path_identity(roots.browser),
        "provenance_root_identity_sha256": _path_identity(roots.provenance),
        "artifact_root_identity_sha256": sorted(
            _path_identity(p) for p in roots.artifacts
        ),
        "model_root_identity_sha256": sorted(_path_identity(p) for p in roots.models),
        "state_root_identity_sha256": sorted(_path_identity(p) for p in roots.states),
    }


def _plan_value(roots: _Roots, base_python: dict[str, object]) -> dict[str, object]:
    body = {
        "schema_version": PLAN_SCHEMA,
        "bootstrap_schema": BOOTSTRAP_SCHEMA,
        "windows_only": True,
        "copy_venv_required": True,
        "dedicated_playwright_browsers_path_required": True,
        "path_bindings": _path_bindings(roots),
        "base_python": base_python,
        "python_runtime_layout": {
            "copied_base_relative_path": COPIED_BASE_DIRECTORY,
            "venv_relative_path": VENV_DIRECTORY,
            "runtime_python_relative_path": RUNTIME_PYTHON_RELATIVE_PATH,
            "complete_base_and_venv_tree_manifest_required": True,
            "pyvenv_config_relative_path": PYVENV_CONFIG_RELATIVE_PATH,
            "venv_created_without_pip": True,
            "active_distribution_policy": (
                "exact-eight-canonical-normalized-pins-v1"
            ),
            "active_distribution_count": len(PACKAGE_PINS),
            "pip_setuptools_and_wheel_allowed": False,
            "pth_files_allowed": False,
            "runtime_customization_modules_allowed": False,
            "python_bytecode_writes_allowed": False,
        },
        "packages": [pin.as_dict() for pin in PACKAGE_PINS],
        "browser": {
            "playwright_version": PLAYWRIGHT_VERSION,
            "name": "chromium",
            "revision": CHROMIUM_REVISION,
            "browser_version": CHROMIUM_VERSION,
            "browsers_json_source": PLAYWRIGHT_BROWSERS_JSON_SOURCE,
            "registry_source": PLAYWRIGHT_REGISTRY_SOURCE,
            "executable_relative_path": CHROMIUM_EXECUTABLE_RELATIVE_PATH,
        },
        "steps": [
            "copy-complete-bytecode-free-standalone-python-base",
            "create-copy-only-pip-free-venv-against-copied-base",
            "stdlib-download-and-verify-hash-pinned-wheelhouse",
            "stdlib-extract-offline-exact-package-set",
            "verify-installed-package-and-browsers-json-pins",
            "verify-sealed-review-service-import-contract",
            "install-matching-chromium-in-dedicated-browser-root",
            "capture-stable-runtime-and-browser-manifests",
            "write-create-only-external-provenance",
        ],
        "network_access_in_plan_mode": False,
        "network_access_in_execute_mode": True,
        "browser_process_launch_performed": False,
        "headed_full_ui_smoke_performed": False,
        "model_calls": 0,
    }
    return {"plan_id": _content_id("c4_review_runtime_plan", body), **body}


def _execute_owned(arguments: argparse.Namespace) -> dict[str, object]:
    if not arguments.execute:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review runtime execution requires --execute"
        )
    roots = _normalize_roots(arguments, fresh=True)
    base_python = arguments.base_python
    base_python_bytes_before = _stable_file(
        base_python, maximum_bytes=128 * 1024 * 1024
    )
    base_descriptor, base_probe_record = _probe_base_python(base_python)
    source_base_root = _existing_directory(base_python.parent)
    for isolated_root in (roots.runtime, roots.browser, roots.provenance):
        _reject_overlap(isolated_root, source_base_root)
    bootstrap_descriptor = _file_descriptor(
        ROOT / BOOTSTRAP_RELATIVE_PATH,
        relative_path=BOOTSTRAP_RELATIVE_PATH,
    )
    process_records = [base_probe_record]

    base_copy_evidence = _copy_base_runtime(source_base_root, roots.runtime)
    copied_base_root = roots.runtime / COPIED_BASE_DIRECTORY
    copied_base_python = copied_base_root / "python.exe"
    _, copied_base_probe_record = _probe_base_python(
        copied_base_python,
        step="copied_base_python_probe",
        relative_path=RUNTIME_BASE_PYTHON_RELATIVE_PATH,
    )
    copied_base_descriptor = _file_descriptor(
        copied_base_python,
        relative_path=RUNTIME_BASE_PYTHON_RELATIVE_PATH,
    )
    process_records.append(copied_base_probe_record)
    runtime_venv_root = roots.runtime / VENV_DIRECTORY

    outcome = _run_bounded(
        step="create_copy_venv",
        command=(
            os.fspath(copied_base_python),
            "-I",
            "-S",
            "-B",
            "-m",
            "venv",
            "--copies",
            "--without-pip",
            os.fspath(runtime_venv_root),
        ),
        working_directory=ROOT,
        environment=_base_environment(),
    )
    process_records.append(outcome.record)
    runtime_python = runtime_venv_root / "Scripts" / "python.exe"
    runtime_python_before, runtime_layout_probe_record = _probe_runtime_python(
        runtime_python,
        copied_base_root=copied_base_root,
        runtime_venv_root=runtime_venv_root,
    )
    process_records.append(runtime_layout_probe_record)
    download_lock, install_lock, wheelhouse = _write_lockfiles(roots.runtime)

    outcome = _run_bounded(
        step="download_hash_pinned_wheels",
        command=(
            os.fspath(runtime_python),
            "-I",
            "-S",
            "-B",
            "-c",
            _STDLIB_WHEEL_DOWNLOADER,
            os.fspath(download_lock),
            "--dest",
            os.fspath(wheelhouse),
        ),
        working_directory=ROOT,
        environment=_base_environment(),
    )
    process_records.append(outcome.record)
    wheel_descriptors = _verify_wheelhouse(wheelhouse)

    outcome = _run_bounded(
        step="install_offline_wheelhouse",
        command=(
            os.fspath(runtime_python),
            "-I",
            "-S",
            "-B",
            "-c",
            _STDLIB_WHEEL_INSTALLER,
            os.fspath(install_lock),
            "--wheelhouse",
            os.fspath(wheelhouse),
            "--venv-root",
            os.fspath(runtime_venv_root),
        ),
        working_directory=ROOT,
        environment=_base_environment(),
    )
    process_records.append(outcome.record)
    installed_distributions = _capture_installed_distributions(roots.runtime)
    process_records.append(
        _verify_installed_packages(runtime_python, browser_root=roots.browser)
    )
    process_records.append(
        _verify_review_import_contract(runtime_python, browser_root=roots.browser)
    )
    browsers_json_descriptor = _verify_installed_browser_descriptor(roots.runtime)
    if roots.browser.exists() or roots.browser.is_symlink():
        raise C4Stage1ReviewRuntimeBootstrapError(
            "Dedicated browser root was populated before the authorized install"
        )

    outcome = _run_bounded(
        step="install_matching_chromium",
        command=(
            os.fspath(runtime_python),
            "-I",
            "-S",
            "-B",
            "-c",
            _PLAYWRIGHT_INSTALL,
            os.fspath(runtime_venv_root / "Lib" / "site-packages"),
            "install",
            "chromium",
        ),
        working_directory=ROOT,
        environment=_base_environment(browser_root=roots.browser),
    )
    process_records.append(outcome.record)

    _existing_directory(roots.browser)
    marker = roots.browser.joinpath(*CHROMIUM_MARKER_RELATIVE_PATH.split("/"))
    marker_descriptor = _file_descriptor(
        marker,
        relative_path=CHROMIUM_MARKER_RELATIVE_PATH,
    )
    chromium = roots.browser.joinpath(*CHROMIUM_EXECUTABLE_RELATIVE_PATH.split("/"))
    chromium_descriptor = _file_descriptor(
        chromium,
        relative_path=CHROMIUM_EXECUTABLE_RELATIVE_PATH,
    )
    runtime_python_after = _file_descriptor(
        runtime_python,
        relative_path=RUNTIME_PYTHON_RELATIVE_PATH,
    )
    if runtime_python_after != runtime_python_before:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "Runtime Python executable changed during installation"
        )
    if (
        _stable_file(base_python, maximum_bytes=128 * 1024 * 1024)
        != base_python_bytes_before
    ):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "Base Python executable changed during installation"
        )
    roots = _normalize_roots(arguments, fresh=False, provenance_fresh=True)

    final_installed_distributions = _capture_installed_distributions(roots.runtime)
    if final_installed_distributions != installed_distributions:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review installed distributions changed during browser install"
        )
    runtime_manifest = _capture_tree(
        roots.runtime,
        tree_role="review-complete-python-runtime",
    )
    browser_manifest = _capture_tree(roots.browser, tree_role="review-browser-runtime")
    runtime_manifest_bytes = _canonical_json_bytes(runtime_manifest)
    browser_manifest_bytes = _canonical_json_bytes(browser_manifest)
    provenance_body = {
        "schema_version": PROVENANCE_SCHEMA,
        "bootstrap_schema": BOOTSTRAP_SCHEMA,
        "bootstrap_script": bootstrap_descriptor,
        "path_bindings": _path_bindings(roots),
        "source_base_python": base_descriptor,
        "base_runtime_copy": base_copy_evidence,
        "runtime_base_python": copied_base_descriptor,
        "runtime_python": runtime_python_after,
        "python_runtime_layout": {
            "complete_runtime_root_manifested": True,
            "copied_base_relative_path": COPIED_BASE_DIRECTORY,
            "venv_relative_path": VENV_DIRECTORY,
            "runtime_python_relative_path": RUNTIME_PYTHON_RELATIVE_PATH,
            "runtime_base_python_relative_path": RUNTIME_BASE_PYTHON_RELATIVE_PATH,
            "pyvenv_config_relative_path": PYVENV_CONFIG_RELATIVE_PATH,
            "venv_link_mode": "copies",
            "venv_created_without_pip": True,
            "active_distribution_policy": (
                "exact-eight-canonical-normalized-pins-v1"
            ),
            "active_distribution_count": len(PACKAGE_PINS),
            "pip_setuptools_and_wheel_allowed": False,
            "pth_files_allowed": False,
            "runtime_customization_modules_allowed": False,
            "external_python_runtime_dependencies_allowed": False,
            "python_bytecode_writes_allowed": False,
        },
        "packages": [pin.as_dict() for pin in PACKAGE_PINS],
        "verified_wheels": list(wheel_descriptors),
        "installed_package_versions": _EXPECTED_PACKAGE_VERSIONS,
        "installed_distributions": list(installed_distributions),
        "browser": {
            "playwright_version": PLAYWRIGHT_VERSION,
            "name": "chromium",
            "revision": CHROMIUM_REVISION,
            "browser_version": CHROMIUM_VERSION,
            "browsers_json_source": PLAYWRIGHT_BROWSERS_JSON_SOURCE,
            "registry_source": PLAYWRIGHT_REGISTRY_SOURCE,
            "installed_browsers_json": browsers_json_descriptor,
            "installation_marker": marker_descriptor,
            "executable": chromium_descriptor,
        },
        "runtime_manifest": _manifest_descriptor(
            RUNTIME_MANIFEST_NAME,
            runtime_manifest_bytes,
            runtime_manifest,
        ),
        "browser_manifest": _manifest_descriptor(
            BROWSER_MANIFEST_NAME,
            browser_manifest_bytes,
            browser_manifest,
        ),
        "bounded_process_records": process_records,
        "wheel_download_verified_before_offline_install": True,
        "matching_playwright_chromium_install_completed": True,
        "install_verification_completed": True,
        "install_verification_scope": (
            "hash-pinned-packages-browsers-json-marker-executable-and-full-trees"
        ),
        "browser_process_launch_performed": False,
        "headed_full_ui_smoke_performed": False,
        "headed_full_ui_smoke_authority": "authenticated-review-service-only",
        "network_access_during_execution": True,
        "network_access_during_verification": False,
        "model_calls": 0,
        "secrets_stored": False,
        "semantic_authority_granted": False,
        "production_authority_granted": False,
    }
    provenance = {
        "provenance_id": _content_id("c4_review_runtime", provenance_body),
        **provenance_body,
    }
    provenance_bytes = _canonical_json_bytes(provenance)
    try:
        os.mkdir(roots.provenance)
    except OSError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "Create-only provenance root could not be created"
        ) from exc
    _write_create_only(roots.provenance / RUNTIME_MANIFEST_NAME, runtime_manifest_bytes)
    _write_create_only(roots.provenance / BROWSER_MANIFEST_NAME, browser_manifest_bytes)
    _write_create_only(roots.provenance / PROVENANCE_NAME, provenance_bytes)
    return {
        "action": "c4_stage1_review_runtime_bootstrap_completed",
        "provenance_id": provenance["provenance_id"],
        "runtime_manifest_id": runtime_manifest["manifest_id"],
        "browser_manifest_id": browser_manifest["manifest_id"],
        "playwright_version": PLAYWRIGHT_VERSION,
        "chromium_revision": CHROMIUM_REVISION,
        "chromium_version": CHROMIUM_VERSION,
        "browser_process_launch_performed": False,
        "headed_full_ui_smoke_performed": False,
        "model_calls": 0,
    }


def _execute(arguments: argparse.Namespace) -> dict[str, object]:
    if not arguments.execute:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review runtime execution requires --execute"
        )
    fresh_roots = _normalize_roots(arguments, fresh=True)
    try:
        return _execute_owned(arguments)
    except BaseException as execution_error:
        try:
            _rollback_fresh_roots(fresh_roots)
        except Exception as rollback_error:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap failed and rollback was incomplete"
            ) from rollback_error
        raise execution_error


def _load_canonical(
    path: Path,
    *,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[bytes, dict[str, object]]:
    raw = _stable_file(
        path,
        maximum_bytes=_MAX_PROVENANCE_BYTES,
        checkpoint=checkpoint,
    )
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap provenance is invalid"
        ) from exc
    if type(value) is not dict or _canonical_json_bytes(value) != raw:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap provenance is not canonical"
        )
    return raw, value


def _verify_manifest_descriptor(
    descriptor: object,
    *,
    expected_name: str,
    raw: bytes,
    manifest: Mapping[str, object],
) -> None:
    if descriptor != _manifest_descriptor(expected_name, raw, manifest):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap manifest descriptor differs from content"
        )


def _verify_process_records(records: object) -> None:
    expected_workloads = (
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
    if type(records) is not list or len(records) != len(expected_workloads):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap process inventory is not exact"
        )
    for raw, workload in zip(records, expected_workloads, strict=True):
        try:
            validated = ProcessTreeExecutionRecord.model_validate_json(
                _canonical_json_bytes(raw)
            )
        except Exception as exc:
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap process evidence is invalid"
            ) from exc
        if (
            validated.model_dump(mode="json", round_trip=True) != raw
            or validated.workload_id != workload
            or validated.status != "succeeded"
        ):
            raise C4Stage1ReviewRuntimeBootstrapError(
                "C4 review bootstrap process evidence differs from execution"
            )


def _verify(arguments: argparse.Namespace) -> dict[str, object]:
    """Run the shared live verifier, then the CLI-only process checks."""

    roots = _normalize_roots(arguments, fresh=False)
    source_base_descriptor, _ = _probe_base_python(arguments.base_python)
    source_base_root = _existing_directory(arguments.base_python.parent)
    for isolated_root in (roots.runtime, roots.browser, roots.provenance):
        _reject_overlap(isolated_root, source_base_root)
    try:
        summary = review_environment.verify_presenter_runtime(
            roots.provenance,
            roots.runtime,
            roots.browser,
            checkpoint=lambda: None,
        )
    except review_environment.C4Stage1ReviewEnvironmentError as exc:
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review shared runtime verification failed"
        ) from exc
    _, provenance = _load_canonical(roots.provenance / PROVENANCE_NAME)
    source_root_identity = _path_identity(arguments.base_python.parent)
    base_copy = provenance.get("base_runtime_copy")
    if (
        provenance.get("path_bindings") != _path_bindings(roots)
        or provenance.get("source_base_python") != source_base_descriptor
        or type(base_copy) is not dict
        or base_copy.get("source_root_path_identity_sha256") != source_root_identity
        or provenance.get("bootstrap_script")
        != _file_descriptor(
            ROOT / BOOTSTRAP_RELATIVE_PATH,
            relative_path=BOOTSTRAP_RELATIVE_PATH,
        )
    ):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review bootstrap CLI bindings differ from provenance"
        )
    runtime_python = roots.runtime.joinpath(*RUNTIME_PYTHON_RELATIVE_PATH.split("/"))
    _probe_runtime_python(
        runtime_python,
        copied_base_root=roots.runtime / COPIED_BASE_DIRECTORY,
        runtime_venv_root=roots.runtime / VENV_DIRECTORY,
    )
    _verify_installed_packages(runtime_python, browser_root=roots.browser)
    _verify_review_import_contract(runtime_python, browser_root=roots.browser)
    _verify_process_records(provenance.get("bounded_process_records"))
    runtime_summary = summary["runtime_manifest"]
    browser_summary = summary["browser_manifest"]
    provenance_summary = summary["provenance"]
    if (
        type(runtime_summary) is not dict
        or type(browser_summary) is not dict
        or type(provenance_summary) is not dict
    ):
        raise C4Stage1ReviewRuntimeBootstrapError(
            "C4 review shared verification summary is invalid"
        )
    return {
        "action": "c4_stage1_review_runtime_verified",
        "verification_id": summary["verification_id"],
        "provenance_id": provenance_summary["provenance_id"],
        "provenance_sha256": provenance_summary["canonical_sha256"],
        "runtime_manifest_id": runtime_summary["manifest_id"],
        "runtime_tree_content_sha256": runtime_summary["tree_content_sha256"],
        "browser_manifest_id": browser_summary["manifest_id"],
        "browser_tree_content_sha256": browser_summary["tree_content_sha256"],
        "playwright_version": PLAYWRIGHT_VERSION,
        "chromium_revision": CHROMIUM_REVISION,
        "chromium_version": CHROMIUM_VERSION,
        "browser_process_launch_performed": False,
        "headed_full_ui_smoke_performed": False,
        "model_calls": 0,
    }


def _absolute_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise argparse.ArgumentTypeError("C4 review bootstrap paths must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "execute", "verify"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--base-python", type=_absolute_path, required=True)
    parser.add_argument("--runtime-root", type=_absolute_path, required=True)
    parser.add_argument("--browser-root", type=_absolute_path, required=True)
    parser.add_argument("--provenance-root", type=_absolute_path, required=True)
    parser.add_argument(
        "--artifact-root", type=_absolute_path, action="append", required=True
    )
    parser.add_argument(
        "--model-root", type=_absolute_path, action="append", required=True
    )
    parser.add_argument(
        "--state-root", type=_absolute_path, action="append", required=True
    )
    return parser


def _emit(value: object) -> None:
    sys.stdout.buffer.write(_canonical_json_bytes(value) + b"\n")
    sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values:
        return 64
    arguments = _parser().parse_args(values)
    if os.name != "nt" or platform.system() != "Windows":
        sys.stderr.write("C4 review runtime bootstrap stopped: WindowsRequired\n")
        return 2
    if arguments.mode != "execute" and arguments.execute:
        return 64
    try:
        if arguments.mode == "execute":
            result = _execute(arguments)
        elif arguments.mode == "verify":
            result = _verify(arguments)
        else:
            roots = _normalize_roots(arguments, fresh=True)
            base_descriptor, _ = _probe_base_python(arguments.base_python)
            source_base_root = _existing_directory(arguments.base_python.parent)
            for isolated_root in (roots.runtime, roots.browser, roots.provenance):
                _reject_overlap(isolated_root, source_base_root)
            result = _plan_value(roots, base_descriptor)
        _emit(result)
        return 0
    except Exception as exc:
        sys.stderr.write(f"C4 review runtime bootstrap stopped: {type(exc).__name__}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
