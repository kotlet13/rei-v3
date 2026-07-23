"""Guarded CLI for the two sealed C4 Stage 1 human family reviews.

Direct invocation is inert.  ``--execute`` requires exact render/prepared
identities, two publication storage identities, a fresh separate review run,
and an authenticated loopback review service.  The command never grants
semantic or production authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"

_RUNTIME_MANIFEST_NAME = "review-runtime-files.json"
_BROWSER_MANIFEST_NAME = "review-browser-files.json"
_PROVENANCE_NAME = "review-runtime-provenance.json"
_RUNTIME_PYTHON_RELATIVE_PATH = "venv/Scripts/python.exe"
_RUNTIME_SITE_PACKAGES_RELATIVE_PATH = "venv/Lib/site-packages"
_COPIED_BASE_RELATIVE_PATH = "base-python"
_MAX_FILE_BYTES = 8 * 1024 * 1024 * 1024
_MAX_JSON_BYTES = 64 * 1024 * 1024
_MAX_FILES = 200_000
_MAX_DIRECTORIES = 50_000
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_EXECUTABLE_SUFFIXES = frozenset({".bat", ".cmd", ".com", ".exe", ".pyd"})
_BYTECODE_SUFFIXES = frozenset({".pyc", ".pyo"})
_CUSTOMIZATION_NAMES = frozenset({"sitecustomize.py", "usercustomize.py"})
_FORBIDDEN_SEED_NAMES = frozenset(
    {"_distutils_hack", "pip", "pkg_resources", "setuptools", "wheel"}
)
_EXPECTED_DISTRIBUTIONS = {
    "annotated-types": "0.7.0",
    "greenlet": "3.1.1",
    "playwright": "1.61.0",
    "pydantic": "2.13.4",
    "pydantic-core": "2.46.4",
    "pyee": "13.0.0",
    "typing-extensions": "4.16.0",
    "typing-inspection": "0.4.2",
}
_DISTRIBUTION_SEPARATOR = re.compile(r"[-_.]+")
_HEX = frozenset("0123456789abcdef")


class _ReviewRuntimePreflightError(RuntimeError):
    """The authority CLI was not launched by its sealed external runtime."""


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


def _assert_unlinked_ancestry(path: Path) -> None:
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise _ReviewRuntimePreflightError("Review runtime paths must be lexical")
    current = path
    while True:
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise _ReviewRuntimePreflightError(
                "Review runtime ancestry is unavailable"
            ) from exc
        if _is_link_or_reparse(metadata):
            raise _ReviewRuntimePreflightError(
                "Review runtime ancestry contains a link"
            )
        parent = current.parent
        if parent == current:
            return
        current = parent


def _ordinary_directory(path: Path) -> Path:
    _assert_unlinked_ancestry(path)
    try:
        metadata = os.lstat(path)
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise _ReviewRuntimePreflightError(
            "Review runtime directory is unavailable"
        ) from exc
    if (
        resolved != path
        or _is_link_or_reparse(metadata)
        or not stat.S_ISDIR(metadata.st_mode)
    ):
        raise _ReviewRuntimePreflightError(
            "Review runtime requires ordinary directories"
        )
    return path


def _stable_file_descriptor(
    path: Path,
    *,
    relative_path: str,
    maximum_bytes: int = _MAX_FILE_BYTES,
) -> dict[str, object]:
    _assert_unlinked_ancestry(path)
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise _ReviewRuntimePreflightError("Review runtime file is unavailable") from exc
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 <= before.st_size <= maximum_bytes
    ):
        raise _ReviewRuntimePreflightError(
            "Review runtime requires bounded one-link ordinary files"
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
        raise _ReviewRuntimePreflightError(
            "Review runtime file could not be opened"
        ) from exc
    digest = hashlib.sha256()
    observed = 0
    try:
        opened = os.fstat(handle)
        if not os.path.samestat(before, opened):
            raise _ReviewRuntimePreflightError("Review runtime file identity changed")
        while True:
            chunk = os.read(handle, 4 * 1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > maximum_bytes:
                raise _ReviewRuntimePreflightError(
                    "Review runtime file exceeds its bound"
                )
            digest.update(chunk)
        final_handle = os.fstat(handle)
    finally:
        os.close(handle)
    try:
        after = os.lstat(path)
    except OSError as exc:
        raise _ReviewRuntimePreflightError("Review runtime file disappeared") from exc
    if (
        _is_link_or_reparse(after)
        or after.st_nlink != 1
        or not os.path.samestat(before, final_handle)
        or not os.path.samestat(before, after)
        or before.st_size != observed
        or final_handle.st_size != observed
        or after.st_size != observed
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise _ReviewRuntimePreflightError("Review runtime file changed during hashing")
    return {
        "relative_path": relative_path,
        "sha256": digest.hexdigest(),
        "size_bytes": observed,
    }


def _stable_file(path: Path, *, maximum_bytes: int) -> bytes:
    descriptor = _stable_file_descriptor(
        path,
        relative_path=path.name,
        maximum_bytes=maximum_bytes,
    )
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise _ReviewRuntimePreflightError("Review runtime file is unreadable") from exc
    if (
        len(payload) != descriptor["size_bytes"]
        or _sha256(payload) != descriptor["sha256"]
    ):
        raise _ReviewRuntimePreflightError("Review runtime file changed after hashing")
    return payload


def _load_canonical(path: Path) -> tuple[bytes, dict[str, object]]:
    raw = _stable_file(path, maximum_bytes=_MAX_JSON_BYTES)
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise _ReviewRuntimePreflightError("Review runtime JSON is invalid") from exc
    if type(value) is not dict or _canonical_json_bytes(value) != raw:
        raise _ReviewRuntimePreflightError("Review runtime JSON is not canonical")
    return raw, value


def _contains(left: Path, right: Path) -> bool:
    try:
        return os.path.commonpath(
            (
                os.path.normcase(os.fspath(left)),
                os.path.normcase(os.fspath(right)),
            )
        ) == os.path.normcase(os.fspath(left))
    except ValueError:
        return False


def _capture_tree(root: Path, *, tree_role: str) -> dict[str, object]:
    root = _ordinary_directory(root)
    entries: list[dict[str, object]] = []
    executables: list[dict[str, object]] = []
    directory_count = 1
    total_size = 0

    def scan(directory: Path, parts: tuple[str, ...]) -> None:
        nonlocal directory_count, total_size
        try:
            before = os.lstat(directory)
            names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise _ReviewRuntimePreflightError(
                "Review runtime tree is unavailable"
            ) from exc
        if _is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise _ReviewRuntimePreflightError("Review runtime tree is not ordinary")
        for name in names:
            child = directory / name
            child_parts = (*parts, name)
            relative = "/".join(child_parts)
            try:
                relative.encode("utf-8", errors="strict")
                metadata = os.lstat(child)
            except (OSError, UnicodeError) as exc:
                raise _ReviewRuntimePreflightError(
                    "Review runtime tree entry is invalid"
                ) from exc
            if _is_link_or_reparse(metadata):
                raise _ReviewRuntimePreflightError("Review runtime tree contains a link")
            if name.casefold() == "__pycache__" or child.suffix.casefold() in (
                _BYTECODE_SUFFIXES
            ):
                raise _ReviewRuntimePreflightError(
                    "Review runtime tree contains mutable bytecode"
                )
            if stat.S_ISDIR(metadata.st_mode):
                directory_count += 1
                if directory_count > _MAX_DIRECTORIES:
                    raise _ReviewRuntimePreflightError(
                        "Review runtime tree has too many directories"
                    )
                entries.append({"kind": "directory", "relative_path": relative})
                scan(child, child_parts)
            elif stat.S_ISREG(metadata.st_mode):
                descriptor = _stable_file_descriptor(
                    child,
                    relative_path=relative,
                )
                total_size += int(descriptor["size_bytes"])
                if (
                    len(entries) >= _MAX_FILES + _MAX_DIRECTORIES
                    or total_size > _MAX_FILE_BYTES
                ):
                    raise _ReviewRuntimePreflightError(
                        "Review runtime tree exceeds fixed bounds"
                    )
                entry = {"kind": "file", **descriptor}
                entries.append(entry)
                if child.suffix.casefold() in _EXECUTABLE_SUFFIXES:
                    executables.append(dict(descriptor))
            else:
                raise _ReviewRuntimePreflightError(
                    "Review runtime tree contains a special entry"
                )
        try:
            after = os.lstat(directory)
            final_names = tuple(sorted(entry.name for entry in os.scandir(directory)))
        except OSError as exc:
            raise _ReviewRuntimePreflightError(
                "Review runtime tree changed during capture"
            ) from exc
        if not os.path.samestat(before, after) or names != final_names:
            raise _ReviewRuntimePreflightError(
                "Review runtime tree changed during capture"
            )

    scan(root, ())
    file_count = sum(entry["kind"] == "file" for entry in entries)
    content = {
        "tree_role": tree_role,
        "file_count": file_count,
        "directory_count": directory_count,
        "total_size_bytes": total_size,
        "entries": entries,
    }
    tree_sha256 = _sha256(_canonical_json_bytes(content))
    body = {
        "schema_version": "rei-c4-stage1-review-runtime-tree-manifest-v1",
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
        "total_size_bytes": total_size,
        "executable_count": len(executables),
        "executables": executables,
        "entries": entries,
    }
    return {"manifest_id": _content_id("c4_review_tree", body), **body}


def _canonical_distribution_name(value: str) -> str:
    normalized = _DISTRIBUTION_SEPARATOR.sub("-", value).casefold()
    if not normalized or normalized != normalized.strip("-"):
        raise _ReviewRuntimePreflightError("Distribution name is invalid")
    return normalized


def _metadata_identity(payload: bytes) -> tuple[str, str]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise _ReviewRuntimePreflightError("Distribution metadata is invalid") from exc
    names = [line[5:].strip() for line in text.splitlines() if line.startswith("Name:")]
    versions = [
        line[8:].strip() for line in text.splitlines() if line.startswith("Version:")
    ]
    if len(names) != 1 or len(versions) != 1 or not names[0] or not versions[0]:
        raise _ReviewRuntimePreflightError("Distribution identity is invalid")
    return names[0], versions[0]


def _verify_active_runtime_policy(
    runtime_root: Path,
    manifest: dict[str, object],
) -> None:
    entries = manifest.get("entries")
    if type(entries) is not list:
        raise _ReviewRuntimePreflightError("Runtime manifest entries are invalid")
    site_prefix = _RUNTIME_SITE_PACKAGES_RELATIVE_PATH.casefold() + "/"
    dist_directories: list[str] = []
    file_paths: set[str] = set()
    for entry in entries:
        if type(entry) is not dict or type(entry.get("relative_path")) is not str:
            raise _ReviewRuntimePreflightError("Runtime manifest entry is invalid")
        relative = entry["relative_path"]
        folded = relative.casefold()
        name = folded.rsplit("/", 1)[-1]
        if entry.get("kind") == "file":
            file_paths.add(folded)
            if (
                name.endswith((".pth", ".egg-link"))
                or name in _CUSTOMIZATION_NAMES
            ):
                raise _ReviewRuntimePreflightError(
                    "Runtime executable path customization is forbidden"
                )
        elif entry.get("kind") == "directory":
            if name.endswith(".dist-info"):
                dist_directories.append(relative)
            if name.endswith(".egg-info"):
                raise _ReviewRuntimePreflightError(
                    "Runtime legacy distribution metadata is forbidden"
                )
        else:
            raise _ReviewRuntimePreflightError("Runtime manifest kind is invalid")
        if folded.startswith(site_prefix):
            first = folded[len(site_prefix) :].split("/", 1)[0]
            if first.removesuffix(".py") in _FORBIDDEN_SEED_NAMES:
                raise _ReviewRuntimePreflightError(
                    "Runtime package-manager seed residue is forbidden"
                )
    if len(dist_directories) != len(_EXPECTED_DISTRIBUTIONS):
        raise _ReviewRuntimePreflightError("Runtime distribution count is not exact")
    discovered: dict[str, str] = {}
    for relative in dist_directories:
        folded = relative.casefold()
        if folded.rpartition("/")[0] != _RUNTIME_SITE_PACKAGES_RELATIVE_PATH.casefold():
            raise _ReviewRuntimePreflightError(
                "Distribution metadata is outside sealed site-packages"
            )
        required = {
            f"{folded}/metadata",
            f"{folded}/record",
            f"{folded}/wheel",
        }
        if not required <= file_paths:
            raise _ReviewRuntimePreflightError(
                "Distribution identity files are incomplete"
            )
        metadata = _stable_file(
            runtime_root.joinpath(*relative.split("/")) / "METADATA",
            maximum_bytes=8 * 1024 * 1024,
        )
        name, version = _metadata_identity(metadata)
        canonical_name = _canonical_distribution_name(name)
        if canonical_name in discovered:
            raise _ReviewRuntimePreflightError("Distribution identity is duplicated")
        discovered[canonical_name] = version
    if discovered != _EXPECTED_DISTRIBUTIONS:
        raise _ReviewRuntimePreflightError(
            "Runtime distributions differ from exact normalized pins"
        )


def _verify_venv_configuration(runtime_root: Path) -> None:
    path = runtime_root / "venv" / "pyvenv.cfg"
    raw = _stable_file(path, maximum_bytes=65_536)
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeError as exc:
        raise _ReviewRuntimePreflightError("pyvenv.cfg is invalid") from exc
    values: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        key, separator, value = line.partition("=")
        key = key.strip().casefold()
        if not separator or not key or key in values:
            raise _ReviewRuntimePreflightError("pyvenv.cfg shape is invalid")
        values[key] = value.strip()
    command = values.get("command", "").split()
    if (
        values.get("include-system-site-packages", "").casefold() != "false"
        or "--copies" not in command
        or "--without-pip" not in command
    ):
        raise _ReviewRuntimePreflightError("Runtime venv policy is not sealed")


def _valid_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _stdlib_runtime_preflight(arguments: argparse.Namespace) -> dict[str, object]:
    if (
        sys.flags.isolated != 1
        or sys.flags.no_site != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.dont_write_bytecode != 1
    ):
        raise _ReviewRuntimePreflightError(
            "Authority CLI requires the sealed interpreter with -I -S -B"
        )
    runtime_root = _ordinary_directory(
        _required(arguments, "review_runtime_root")
    )
    browser_root = _ordinary_directory(
        _required(arguments, "review_browser_root")
    )
    provenance_root = _ordinary_directory(
        _required(arguments, "review_runtime_provenance_root")
    )
    repository_root = _ordinary_directory(ROOT)
    for left, right in (
        (runtime_root, browser_root),
        (runtime_root, provenance_root),
        (browser_root, provenance_root),
    ):
        if _contains(left, right) or _contains(right, left):
            raise _ReviewRuntimePreflightError("Review runtime roots overlap")
    for external_root in (runtime_root, browser_root, provenance_root):
        if _contains(repository_root, external_root) or _contains(
            external_root, repository_root
        ):
            raise _ReviewRuntimePreflightError(
                "Review runtime roots must be external"
            )
    runtime_python = runtime_root.joinpath(
        *_RUNTIME_PYTHON_RELATIVE_PATH.split("/")
    )
    if os.path.normcase(sys.executable) != os.path.normcase(os.fspath(runtime_python)):
        raise _ReviewRuntimePreflightError(
            "Authority CLI was launched by the wrong interpreter"
        )
    try:
        provenance_inventory = tuple(
            sorted(entry.name for entry in os.scandir(provenance_root))
        )
    except OSError as exc:
        raise _ReviewRuntimePreflightError(
            "Runtime provenance inventory is unavailable"
        ) from exc
    if provenance_inventory != tuple(
        sorted((_RUNTIME_MANIFEST_NAME, _BROWSER_MANIFEST_NAME, _PROVENANCE_NAME))
    ):
        raise _ReviewRuntimePreflightError(
            "Runtime provenance inventory is not create-only exact"
        )
    provenance_raw, provenance = _load_canonical(
        provenance_root / _PROVENANCE_NAME
    )
    confirmed_id = _required(arguments, "confirmed_review_runtime_provenance_id")
    confirmed_sha256 = _required(
        arguments, "confirmed_review_runtime_provenance_sha256"
    )
    if (
        type(confirmed_id) is not str
        or not _valid_digest(confirmed_sha256)
        or provenance.get("provenance_id") != confirmed_id
        or _sha256(provenance_raw) != confirmed_sha256
    ):
        raise _ReviewRuntimePreflightError(
            "Confirmed provenance differs from canonical sealed bytes"
        )
    provenance_body = {
        key: value for key, value in provenance.items() if key != "provenance_id"
    }
    if (
        provenance.get("schema_version")
        != "rei-c4-stage1-review-runtime-provenance-v1"
        or provenance.get("provenance_id")
        != _content_id("c4_review_runtime", provenance_body)
        or provenance.get("installed_package_versions") != _EXPECTED_DISTRIBUTIONS
    ):
        raise _ReviewRuntimePreflightError(
            "Runtime provenance is not the sealed protocol"
        )
    bindings = provenance.get("path_bindings")
    if (
        type(bindings) is not dict
        or bindings.get("paths_stored") is not False
        or bindings.get("runtime_root_identity_sha256")
        != _path_identity(runtime_root)
        or bindings.get("browser_root_identity_sha256")
        != _path_identity(browser_root)
        or bindings.get("provenance_root_identity_sha256")
        != _path_identity(provenance_root)
    ):
        raise _ReviewRuntimePreflightError(
            "Runtime provenance path bindings differ from roots"
        )
    expected_layout = {
        "complete_runtime_root_manifested": True,
        "copied_base_relative_path": _COPIED_BASE_RELATIVE_PATH,
        "venv_relative_path": "venv",
        "runtime_python_relative_path": _RUNTIME_PYTHON_RELATIVE_PATH,
        "runtime_base_python_relative_path": "base-python/python.exe",
        "pyvenv_config_relative_path": "venv/pyvenv.cfg",
        "venv_link_mode": "copies",
        "venv_created_without_pip": True,
        "active_distribution_policy": "exact-eight-canonical-normalized-pins-v1",
        "active_distribution_count": len(_EXPECTED_DISTRIBUTIONS),
        "pip_setuptools_and_wheel_allowed": False,
        "pth_files_allowed": False,
        "runtime_customization_modules_allowed": False,
        "external_python_runtime_dependencies_allowed": False,
        "python_bytecode_writes_allowed": False,
    }
    if provenance.get("python_runtime_layout") != expected_layout:
        raise _ReviewRuntimePreflightError("Runtime layout policy differs from seal")
    runtime_raw, runtime_manifest = _load_canonical(
        provenance_root / _RUNTIME_MANIFEST_NAME
    )
    runtime_descriptor = {
        "relative_path": _RUNTIME_MANIFEST_NAME,
        "manifest_id": runtime_manifest.get("manifest_id"),
        "sha256": _sha256(runtime_raw),
        "size_bytes": len(runtime_raw),
    }
    confirmed_manifest_id = _required(
        arguments, "confirmed_review_runtime_manifest_id"
    )
    confirmed_manifest_sha256 = _required(
        arguments, "confirmed_review_runtime_manifest_sha256"
    )
    if (
        provenance.get("runtime_manifest") != runtime_descriptor
        or runtime_descriptor["manifest_id"] != confirmed_manifest_id
        or runtime_descriptor["sha256"] != confirmed_manifest_sha256
    ):
        raise _ReviewRuntimePreflightError(
            "Runtime manifest descriptor differs from sealed provenance"
        )
    live_manifest = _capture_tree(
        runtime_root,
        tree_role="review-complete-python-runtime",
    )
    if live_manifest != runtime_manifest:
        raise _ReviewRuntimePreflightError(
            "Active runtime tree differs from sealed manifest"
        )
    _verify_active_runtime_policy(runtime_root, live_manifest)
    _verify_venv_configuration(runtime_root)
    runtime_python_descriptor = _stable_file_descriptor(
        runtime_python,
        relative_path=_RUNTIME_PYTHON_RELATIVE_PATH,
    )
    confirmed_python_sha256 = _required(
        arguments, "confirmed_review_runtime_python_sha256"
    )
    if (
        provenance.get("runtime_python") != runtime_python_descriptor
        or runtime_python_descriptor["sha256"] != confirmed_python_sha256
    ):
        raise _ReviewRuntimePreflightError(
            "Active interpreter differs from sealed descriptor"
        )
    copied_base = runtime_root / _COPIED_BASE_RELATIVE_PATH
    for value in sys.path:
        if not value:
            continue
        path = Path(value)
        if (
            not path.is_absolute()
            or path != _absolute_lexical(path)
            or not _contains(copied_base, path)
        ):
            raise _ReviewRuntimePreflightError(
                "Interpreter search path escapes the sealed copied base"
            )
    return {
        "runtime_root": runtime_root,
        "browser_root": browser_root,
        "provenance_root": provenance_root,
        "site_packages": runtime_root.joinpath(
            *_RUNTIME_SITE_PACKAGES_RELATIVE_PATH.split("/")
        ),
        "provenance_id": confirmed_id,
        "provenance_sha256": confirmed_sha256,
        "runtime_manifest_id": confirmed_manifest_id,
        "runtime_manifest_sha256": confirmed_manifest_sha256,
    }


def _activate_verified_application_paths(preflight: dict[str, object]) -> None:
    site_packages = preflight["site_packages"]
    if not isinstance(site_packages, Path):
        raise _ReviewRuntimePreflightError("Verified site-packages path is invalid")
    sys.path[:0] = [os.fspath(BACKEND_ROOT), os.fspath(site_packages)]


def _load_application_modules() -> object:
    global C4Stage1ReviewServiceClient
    global FileArtifactStore
    global run_c4_stage1_human_review
    from rei.evaluation import c4_stage1_review_environment
    from rei.evaluation.c4_stage1_review_run import run_c4_stage1_human_review
    from rei.evaluation.c4_stage1_review_service import C4Stage1ReviewServiceClient
    from rei.persistence.artifacts import FileArtifactStore

    return c4_stage1_review_environment


def _verify_with_application(
    preflight: dict[str, object],
    review_environment: object,
) -> None:
    summary = review_environment.verify_presenter_runtime(
        preflight["provenance_root"],
        preflight["runtime_root"],
        preflight["browser_root"],
        checkpoint=lambda: None,
    )
    provenance = summary.get("provenance")
    runtime_manifest = summary.get("runtime_manifest")
    if (
        type(provenance) is not dict
        or type(runtime_manifest) is not dict
        or provenance.get("provenance_id") != preflight["provenance_id"]
        or provenance.get("canonical_sha256") != preflight["provenance_sha256"]
        or runtime_manifest.get("manifest_id") != preflight["runtime_manifest_id"]
        or runtime_manifest.get("canonical_sha256")
        != preflight["runtime_manifest_sha256"]
    ):
        raise _ReviewRuntimePreflightError(
            "Application verification differs from stdlib preflight"
        )


def _absolute(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or path != Path(os.path.abspath(os.fspath(path))):
        raise argparse.ArgumentTypeError("C4 Stage 1 review paths must be absolute")
    return path


def _bounded_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Review timeout must be numeric") from None
    if not 60.0 <= timeout <= 14_400.0:
        raise argparse.ArgumentTypeError(
            "Review timeout must be between 60 and 14400 seconds"
        )
    return timeout


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--review-runtime-root", type=_absolute)
    parser.add_argument("--review-browser-root", type=_absolute)
    parser.add_argument("--review-runtime-provenance-root", type=_absolute)
    parser.add_argument("--confirmed-review-runtime-provenance-id")
    parser.add_argument("--confirmed-review-runtime-provenance-sha256")
    parser.add_argument("--confirmed-review-runtime-manifest-id")
    parser.add_argument("--confirmed-review-runtime-manifest-sha256")
    parser.add_argument("--confirmed-review-runtime-python-sha256")
    parser.add_argument("--render-artifact-root", type=_absolute)
    parser.add_argument("--render-run-id")
    parser.add_argument("--render-inventory-anchor-storage-id")
    parser.add_argument("--confirmed-render-inventory-anchor-id")
    parser.add_argument("--confirmed-render-inventory-anchor-sha256")
    parser.add_argument("--prepared-anchor-storage-id")
    parser.add_argument("--confirmed-prepared-attempt-id")
    parser.add_argument("--confirmed-prepared-attempt-sha256")
    parser.add_argument("--primary-member-publication-storage-id")
    parser.add_argument("--alternate-member-publication-storage-id")
    parser.add_argument("--review-artifact-root", type=_absolute)
    parser.add_argument("--review-run-id")
    parser.add_argument("--repository-root", type=_absolute)
    parser.add_argument("--review-service-host")
    parser.add_argument("--review-service-port", type=int)
    parser.add_argument("--review-service-auth-secret", type=_absolute)
    parser.add_argument(
        "--service-timeout-seconds",
        type=_bounded_timeout,
        # The server owns the one-hour presenter deadline; leave a bounded six
        # seconds for cancellation and the authenticated loopback response.
        default=3606.0,
    )
    parser.add_argument("--presenter-timeout-ms", type=int, default=3_600_000)
    return parser


def _required(arguments: argparse.Namespace, name: str) -> object:
    value = getattr(arguments, name)
    if value is None or type(value) is str and not value:
        raise ValueError(f"Missing required C4 Stage 1 review argument: {name}")
    return value


def _descriptor(
    inventory: tuple[StoredArtifact, ...],
    storage_id: object,
    *,
    run_id: str,
) -> StoredArtifact:
    if type(storage_id) is not str:
        raise TypeError("C4 Stage 1 review storage identity must be a string")
    matches = tuple(
        item
        for item in inventory
        if item.storage_id == storage_id and item.run_id == run_id
    )
    if len(matches) != 1:
        raise ValueError("C4 Stage 1 review storage identity is absent or ambiguous")
    return matches[0]


def _emit(value: dict[str, object]) -> None:
    sys.stdout.write(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _execute(arguments: argparse.Namespace) -> int:
    render_root = _required(arguments, "render_artifact_root")
    render_run_id = _required(arguments, "render_run_id")
    render_anchor_storage_id = _required(
        arguments, "render_inventory_anchor_storage_id"
    )
    render_anchor_id = _required(arguments, "confirmed_render_inventory_anchor_id")
    render_anchor_sha256 = _required(
        arguments, "confirmed_render_inventory_anchor_sha256"
    )
    prepared_storage_id = _required(arguments, "prepared_anchor_storage_id")
    prepared_id = _required(arguments, "confirmed_prepared_attempt_id")
    prepared_sha256 = _required(arguments, "confirmed_prepared_attempt_sha256")
    primary_storage_id = _required(arguments, "primary_member_publication_storage_id")
    alternate_storage_id = _required(
        arguments, "alternate_member_publication_storage_id"
    )
    review_root = _required(arguments, "review_artifact_root")
    review_run_id = _required(arguments, "review_run_id")
    repository_root = _required(arguments, "repository_root")
    service_host = _required(arguments, "review_service_host")
    service_port = _required(arguments, "review_service_port")
    auth_secret = _required(arguments, "review_service_auth_secret")
    timeout_seconds = arguments.service_timeout_seconds
    if (
        not isinstance(render_root, Path)
        or type(render_run_id) is not str
        or not isinstance(review_root, Path)
        or type(review_run_id) is not str
        or not isinstance(repository_root, Path)
        or type(service_host) is not str
        or type(service_port) is not int
        or not isinstance(auth_secret, Path)
        or not isinstance(timeout_seconds, float)
        or type(render_anchor_id) is not str
        or type(render_anchor_sha256) is not str
        or type(prepared_id) is not str
        or type(prepared_sha256) is not str
    ):
        raise TypeError("C4 Stage 1 review CLI arguments have invalid types")
    if repository_root != ROOT:
        raise ValueError("C4 Stage 1 review repository root must equal CLI ROOT")

    render_store = FileArtifactStore(render_root, create=False)
    inventory = render_store.inspect_run_inventory_exact(render_run_id)
    render_anchor_storage = _descriptor(
        inventory, render_anchor_storage_id, run_id=render_run_id
    )
    prepared_storage = _descriptor(inventory, prepared_storage_id, run_id=render_run_id)
    primary_storage = _descriptor(inventory, primary_storage_id, run_id=render_run_id)
    alternate_storage = _descriptor(
        inventory, alternate_storage_id, run_id=render_run_id
    )
    review_store = FileArtifactStore(review_root)
    client = C4Stage1ReviewServiceClient(
        service_host,
        service_port,
        auth_secret_path=auth_secret,
        timeout_seconds=timeout_seconds,
        presenter_timeout_ms=arguments.presenter_timeout_ms,
    )
    outcome = run_c4_stage1_human_review(
        render_store,
        render_anchor_storage,
        prepared_storage,
        (primary_storage, alternate_storage),
        review_store,
        review_run_id=review_run_id,
        confirmed_render_inventory_anchor_id=render_anchor_id,
        confirmed_render_inventory_anchor_sha256=render_anchor_sha256,
        confirmed_prepared_attempt_id=prepared_id,
        confirmed_prepared_attempt_sha256=prepared_sha256,
        repository_root=repository_root,
        review_service=client,
    )
    _emit(
        {
            "action": "c4_stage1_human_review_completed",
            "review_run_id": outcome.anchor.review_run_id,
            "render_run_id": outcome.anchor.render_run_id,
            "prepared_attempt_id": outcome.anchor.prepared_attempt_id,
            "review_run_anchor_id": outcome.anchor.review_run_anchor_id,
            "review_run_anchor_storage_id": outcome.anchor_storage.storage_id,
            "family_review_count": outcome.anchor.family_review_count,
            "both_family_submissions_sealed": True,
            "all_human_reviews_passed": outcome.anchor.all_human_reviews_passed,
            "identity_reveal_status": outcome.anchor.identity_reveal_status,
            "dino_gate_evaluated": False,
            "semantic_stage1_passed": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
            "model_judge_calls": 0,
        }
    )
    return 0 if outcome.anchor.all_human_reviews_passed else 20


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if not arguments.execute:
        return 64
    try:
        preflight = _stdlib_runtime_preflight(arguments)
        _activate_verified_application_paths(preflight)
        review_environment = _load_application_modules()
        _verify_with_application(preflight, review_environment)
        return _execute(arguments)
    except Exception as exc:
        sys.stderr.write(f"C4 Stage 1 human review stopped: {type(exc).__name__}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
