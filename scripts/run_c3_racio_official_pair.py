"""Stdlib-only bootstrap for the sealed official C3 Ollama pair.

No project or third-party module is imported until Git identity, ancestry,
source cleanliness, the exact seal delta, and required GPU environment have
been checked with replacement refs and inherited Git redirection disabled.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import secrets
import stat
import subprocess
import sys
import tempfile
from importlib.machinery import BYTECODE_SUFFIXES, EXTENSION_SUFFIXES, ModuleSpec
from pathlib import Path, PurePosixPath
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_FREEZE_COMMIT = "d74891cdeed407a50098d28d6f4e9024b28156e7"
TRUSTED_WINDOWS_GIT_EXECUTABLE = Path(r"C:\Program Files\Git\mingw64\bin\git.exe")
TRUSTED_WINDOWS_GIT_SHA256 = (
    "cab4c4eea1d869cf9f7be73868dc9a90ad2df1b1b673e5f8c8714a576c25ea96"
)
EXPECTED_SEAL_DELTA = (
    "Docs/evals/semantic_lab_v1/c3_holdout_seal_2026-07-15.md",
    "app/backend/rei/evaluation/c3_official_suite.py",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1/gold.jsonl",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1/manifest.json",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1/public_cases.jsonl",
    "scripts/c3_racio_official_pair.py",
    "scripts/run_c3_racio_official_pair.py",
    "tests/evaluation/test_c3_holdout_protocol.py",
    "tests/evaluation/test_c3_official_pair.py",
)
SCOPED_EXECUTION_PATHS = (
    "app/backend/rei",
    "config/racio_interpreter_models.yaml",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1",
    "scripts/build_c3_racio_holdout.py",
    "scripts/c3_racio_official_pair.py",
    "scripts/run_c3_racio_official_pair.py",
    "scripts/run_racio_interpreter_benchmark.py",
    "tests/fixtures/semantic_lab_v1",
    "Docs/evals/semantic_lab_v1/c3_remediation_protocol_2026-07-15.md",
    "Docs/evals/semantic_lab_v1/c3_holdout_seal_2026-07-15.md",
)
SCOPED_DIRECTORY_ROOTS = (
    "app/backend/rei",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter",
    "knowledge/canon_v2/semantic_lab_v1/c3_racio_interpreter_holdout_v1",
    "tests/fixtures/semantic_lab_v1",
)
MAX_SCOPED_SOURCE_BYTES = 64 * 1024 * 1024
EXECUTION_SCRIPT_MODULES = (
    "run_c3_racio_official_pair",
    "c3_racio_official_pair",
    "run_racio_interpreter_benchmark",
)


def _sanitized_git_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_ATTR_NOSYSTEM"] = "1"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment


def _git_text(environment: dict[str, str], *args: str) -> str:
    completed = subprocess.run(
        [
            os.fspath(_trusted_git_executable()),
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            *args,
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_bytes(environment: dict[str, str], *args: str) -> bytes:
    completed = subprocess.run(
        [
            os.fspath(_trusted_git_executable()),
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            *args,
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _metadata_is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _bounded_regular_file_bytes(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
) -> bytes:
    before = os.lstat(path)
    if (
        not stat.S_ISREG(before.st_mode)
        or _metadata_is_reparse(before)
        or before.st_size > maximum_bytes
    ):
        raise ValueError(f"{label} is not a bounded regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > maximum_bytes:
                raise ValueError(f"{label} exceeds its byte ceiling")
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    final_path = os.lstat(path)
    if (
        opened.st_dev != before.st_dev
        or opened.st_ino != before.st_ino
        or opened.st_size != before.st_size
        or opened.st_mtime_ns != before.st_mtime_ns
        or opened.st_ctime_ns != before.st_ctime_ns
        or after.st_dev != opened.st_dev
        or after.st_ino != opened.st_ino
        or after.st_size != opened.st_size
        or after.st_mtime_ns != opened.st_mtime_ns
        or after.st_ctime_ns != opened.st_ctime_ns
        or final_path.st_dev != opened.st_dev
        or final_path.st_ino != opened.st_ino
        or final_path.st_size != opened.st_size
        or final_path.st_mtime_ns != opened.st_mtime_ns
        or final_path.st_ctime_ns != opened.st_ctime_ns
        or _metadata_is_reparse(final_path)
    ):
        raise ValueError(f"{label} changed during validation")
    return b"".join(chunks)


def _bounded_regular_file_sha256(
    path: Path,
    *,
    maximum_bytes: int,
    label: str,
) -> str:
    return hashlib.sha256(
        _bounded_regular_file_bytes(
            path,
            maximum_bytes=maximum_bytes,
            label=label,
        )
    ).hexdigest()


def _trusted_git_executable() -> Path:
    for candidate_name in ("git", "git.exe", "git.com", "git.cmd", "git.bat"):
        if os.path.lexists(ROOT / candidate_name):
            raise ValueError("Official C3 repository contains a Git shadow candidate")
    if os.name == "nt":
        candidate = TRUSTED_WINDOWS_GIT_EXECUTABLE
        expected_sha256 = TRUSTED_WINDOWS_GIT_SHA256
    else:
        candidate = next(
            (
                item
                for item in (Path("/usr/bin/git"), Path("/usr/local/bin/git"))
                if os.path.lexists(item)
            ),
            None,
        )
        if candidate is None:
            raise ValueError("Official C3 trusted Git executable is unavailable")
        expected_sha256 = None
    metadata = os.lstat(candidate)
    if not stat.S_ISREG(metadata.st_mode) or _metadata_is_reparse(metadata):
        raise ValueError("Official C3 trusted Git executable is not a regular file")
    actual_sha256 = _bounded_regular_file_sha256(
        candidate,
        maximum_bytes=64 * 1024 * 1024,
        label="Official C3 trusted Git executable",
    )
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ValueError("Official C3 trusted Git executable hash differs from its pin")
    return candidate


def _validated_local_git_directory() -> Path:
    git_entry = ROOT / ".git"
    metadata = os.lstat(git_entry)
    if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
        raise ValueError("Official C3 Git directory differs from the repository")
    return git_entry


def _require_reported_git_directory(git_directory: Path, expected: Path) -> None:
    reported = os.path.normcase(os.path.abspath(os.fspath(git_directory)))
    required = os.path.normcase(os.path.abspath(os.fspath(expected)))
    if reported != required:
        raise ValueError("Official C3 Git directory differs from the repository")


def _require_regular_import_directory(path: Path, *, label: str) -> None:
    metadata = os.lstat(path)
    if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
        raise ValueError(
            f"Official C3 {label} import anchor is not a regular directory"
        )


def _require_regular_import_file(path: Path, *, label: str) -> None:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or _metadata_is_reparse(metadata):
        raise ValueError(f"Official C3 {label} import anchor is not a regular file")


def _require_no_execution_import_collisions() -> None:
    for module_name in EXECUTION_SCRIPT_MODULES:
        module_path = ROOT / "scripts" / f"{module_name}.py"
        _require_regular_import_file(module_path, label=f"scripts.{module_name}")
        if os.path.lexists(ROOT / "scripts" / module_name):
            raise ValueError(
                f"Official C3 scripts.{module_name} import anchor is ambiguous"
            )
        for suffix in (*BYTECODE_SUFFIXES, *EXTENSION_SUFFIXES):
            collision = ROOT / "scripts" / f"{module_name}{suffix}"
            if os.path.lexists(collision):
                raise ValueError(
                    f"Official C3 scripts.{module_name} import anchor is ambiguous"
                )
    for suffix in (".py", *BYTECODE_SUFFIXES, *EXTENSION_SUFFIXES):
        rei_collision = ROOT / "app" / "backend" / f"rei{suffix}"
        if os.path.lexists(rei_collision):
            raise ValueError("Official C3 app.backend.rei import anchor is ambiguous")


def _canonical_git_path(raw_path: str) -> str:
    if not raw_path or "\\" in raw_path or "\x00" in raw_path:
        raise ValueError("Official C3 Git tree contains an invalid scoped path")
    path = PurePosixPath(raw_path)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != raw_path
    ):
        raise ValueError("Official C3 Git tree contains an invalid scoped path")
    return raw_path


def _is_path_at_or_below(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")


def _is_scoped_tree_path(path: str) -> bool:
    exact_paths = set(SCOPED_EXECUTION_PATHS) - set(SCOPED_DIRECTORY_ROOTS)
    return path in exact_paths or any(
        _is_path_at_or_below(path, root) for root in SCOPED_DIRECTORY_ROOTS
    )


def _is_tracked_bytecode_cache(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return "__pycache__" in parts or parts[-1].endswith(".pyc")


def _parse_scoped_ls_tree(payload: bytes) -> dict[str, tuple[str, str]]:
    if len(payload) > 32 * 1024 * 1024 or (payload and not payload.endswith(b"\x00")):
        raise ValueError("Official C3 Git tree inventory is malformed")
    entries: dict[str, tuple[str, str]] = {}
    normalized_paths: set[str] = set()
    for record in payload.split(b"\x00"):
        if not record:
            continue
        try:
            header, separator, encoded_path = record.partition(b"\t")
            if separator != b"\t" or not encoded_path:
                raise ValueError
            mode, object_type, encoded_oid = header.split(b" ")
            path = os.fsdecode(encoded_path)
            if os.fsencode(path) != encoded_path:
                raise ValueError
            oid = encoded_oid.decode("ascii", errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Official C3 Git tree inventory is malformed") from exc
        path = _canonical_git_path(path)
        normalized_path = os.path.normcase(path)
        if (
            mode not in {b"100644", b"100755"}
            or object_type != b"blob"
            or len(oid) != 40
            or oid != oid.lower()
            or any(character not in "0123456789abcdef" for character in oid)
            or not _is_scoped_tree_path(path)
            or _is_tracked_bytecode_cache(path)
            or path in entries
            or normalized_path in normalized_paths
        ):
            raise ValueError("Official C3 Git tree inventory is malformed")
        entries[path] = (mode.decode("ascii"), oid)
        normalized_paths.add(normalized_path)
    return entries


def _parse_scoped_ls_files(payload: bytes) -> dict[str, tuple[str, str]]:
    if len(payload) > 32 * 1024 * 1024 or (payload and not payload.endswith(b"\x00")):
        raise ValueError("Official C3 Git index inventory is malformed")
    entries: dict[str, tuple[str, str]] = {}
    normalized_paths: set[str] = set()
    for record in payload.split(b"\x00"):
        if not record:
            continue
        try:
            header, separator, encoded_path = record.partition(b"\t")
            if separator != b"\t" or not encoded_path:
                raise ValueError
            mode, encoded_oid, stage = header.split(b" ")
            path = os.fsdecode(encoded_path)
            if os.fsencode(path) != encoded_path:
                raise ValueError
            oid = encoded_oid.decode("ascii", errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Official C3 Git index inventory is malformed") from exc
        path = _canonical_git_path(path)
        normalized_path = os.path.normcase(path)
        if (
            mode not in {b"100644", b"100755"}
            or stage != b"0"
            or len(oid) != 40
            or oid != oid.lower()
            or any(character not in "0123456789abcdef" for character in oid)
            or not _is_scoped_tree_path(path)
            or _is_tracked_bytecode_cache(path)
            or path in entries
            or normalized_path in normalized_paths
        ):
            raise ValueError("Official C3 Git index inventory is malformed")
        entries[path] = (mode.decode("ascii"), oid)
        normalized_paths.add(normalized_path)
    return entries


def _require_regular_directory_chain(relative_file: str) -> None:
    current = ROOT
    root_metadata = os.lstat(current)
    if not stat.S_ISDIR(root_metadata.st_mode) or _metadata_is_reparse(root_metadata):
        raise ValueError("Official C3 repository root is not a regular directory")
    for part in PurePosixPath(relative_file).parts[:-1]:
        current /= part
        metadata = os.lstat(current)
        if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
            raise ValueError(
                "Official C3 scoped source parent is not a regular directory"
            )


def _git_blob_oid(payload: bytes, *, oid_length: int) -> str:
    if oid_length != 40:
        raise ValueError("Official C3 Git object format is unsupported")
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(b"blob ")
    digest.update(str(len(payload)).encode("ascii"))
    digest.update(b"\x00")
    digest.update(payload)
    return digest.hexdigest()


def _validate_tracked_file(path: str, *, expected_oid: str) -> None:
    _require_regular_directory_chain(path)
    payload = _bounded_regular_file_bytes(
        ROOT.joinpath(*PurePosixPath(path).parts),
        maximum_bytes=MAX_SCOPED_SOURCE_BYTES,
        label=f"Official C3 scoped source {path}",
    )
    if _git_blob_oid(payload, oid_length=len(expected_oid)) != expected_oid:
        raise ValueError(f"Official C3 scoped source differs from HEAD: {path}")


def _expected_directories_for_root(
    root: str,
    expected_files: set[str],
) -> set[str]:
    root_path = PurePosixPath(root)
    expected_directories = {root}
    for file_path in expected_files:
        tail = PurePosixPath(file_path).relative_to(root_path)
        current = root_path
        for part in tail.parts[:-1]:
            current /= part
            expected_directories.add(current.as_posix())
    return expected_directories


def _validate_ignored_pycache(path: Path) -> None:
    metadata = os.lstat(path)
    if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
        raise ValueError("Official C3 scoped filesystem inventory differs from HEAD")
    with os.scandir(path) as iterator:
        for entry in iterator:
            entry_metadata = entry.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(entry_metadata.st_mode)
                or _metadata_is_reparse(entry_metadata)
                or not entry.name.endswith(".pyc")
                or entry_metadata.st_size > MAX_SCOPED_SOURCE_BYTES
            ):
                raise ValueError(
                    "Official C3 scoped filesystem inventory differs from HEAD"
                )


def _validate_directory_inventory(
    root: str,
    *,
    expected_files: set[str],
) -> None:
    expected_directories = _expected_directories_for_root(root, expected_files)
    observed_files: set[str] = set()
    observed_directories: set[str] = set()

    def visit(relative_directory: str) -> None:
        directory = ROOT.joinpath(*PurePosixPath(relative_directory).parts)
        metadata = os.lstat(directory)
        if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
            raise ValueError(
                "Official C3 scoped filesystem inventory differs from HEAD"
            )
        observed_directories.add(relative_directory)
        with os.scandir(directory) as iterator:
            entries = tuple(iterator)
        for entry in entries:
            relative_path = (PurePosixPath(relative_directory) / entry.name).as_posix()
            entry_metadata = entry.stat(follow_symlinks=False)
            if _metadata_is_reparse(entry_metadata):
                raise ValueError(
                    "Official C3 scoped filesystem inventory differs from HEAD"
                )
            if stat.S_ISDIR(entry_metadata.st_mode):
                if entry.name == "__pycache__" and (
                    relative_path not in expected_directories
                ):
                    _validate_ignored_pycache(Path(entry.path))
                elif relative_path in expected_directories:
                    visit(relative_path)
                else:
                    raise ValueError(
                        "Official C3 scoped filesystem inventory differs from HEAD"
                    )
            elif stat.S_ISREG(entry_metadata.st_mode) and (
                relative_path in expected_files
            ):
                observed_files.add(relative_path)
            else:
                raise ValueError(
                    "Official C3 scoped filesystem inventory differs from HEAD"
                )

    visit(root)
    if observed_files != expected_files or observed_directories != expected_directories:
        raise ValueError("Official C3 scoped filesystem inventory differs from HEAD")


def _validate_worktree_against_head(
    source_commit: str,
    *,
    environment: dict[str, str] | None = None,
) -> None:
    """Bind every execution byte and runtime directory entry to ``HEAD``."""

    if (
        len(source_commit) != 40
        or source_commit != source_commit.lower()
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ValueError("Official C3 source commit is malformed")
    for path in (*SCOPED_EXECUTION_PATHS, *SCOPED_DIRECTORY_ROOTS):
        _canonical_git_path(path)
    if not set(SCOPED_DIRECTORY_ROOTS) <= set(SCOPED_EXECUTION_PATHS):
        raise ValueError("Official C3 scoped directory roots are malformed")
    git_environment = (
        environment if environment is not None else _sanitized_git_environment()
    )
    tree_payload = _git_bytes(
        git_environment,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        "--abbrev=40",
        source_commit,
        "--",
        *SCOPED_EXECUTION_PATHS,
    )
    entries = _parse_scoped_ls_tree(tree_payload)
    index_payload = _git_bytes(
        git_environment,
        "ls-files",
        "--stage",
        "-z",
        "--full-name",
        "--",
        *SCOPED_EXECUTION_PATHS,
    )
    if _parse_scoped_ls_files(index_payload) != entries:
        raise ValueError("Official C3 scoped Git index differs from HEAD")
    exact_paths = set(SCOPED_EXECUTION_PATHS) - set(SCOPED_DIRECTORY_ROOTS)
    missing_exact_paths = exact_paths - set(entries)
    if missing_exact_paths:
        raise ValueError("Official C3 exact scoped source is absent from HEAD")
    for root in SCOPED_DIRECTORY_ROOTS:
        if not any(_is_path_at_or_below(path, root) for path in entries):
            raise ValueError("Official C3 scoped directory is absent from HEAD")
    for path, (_mode, expected_oid) in entries.items():
        _validate_tracked_file(path, expected_oid=expected_oid)
    for root in SCOPED_DIRECTORY_ROOTS:
        expected_files = {path for path in entries if _is_path_at_or_below(path, root)}
        _validate_directory_inventory(root, expected_files=expected_files)


def _install_namespace_package(name: str, path: Path) -> None:
    """Install an exact namespace path without adding the repository to sys.path."""

    _require_regular_import_directory(path, label=name)
    if name in sys.modules:
        raise ValueError(
            f"Official C3 {name} import anchor was loaded before preflight"
        )
    module = ModuleType(name)
    spec = ModuleSpec(name, loader=None, is_package=True)
    spec.submodule_search_locations = [str(path)]
    module.__package__ = name
    module.__path__ = [str(path)]
    module.__spec__ = spec
    sys.modules[name] = module
    parent_name, _, child_name = name.rpartition(".")
    if parent_name:
        setattr(sys.modules[parent_name], child_name, module)


def _path_entry_is_repository_root(entry: object, repository_root: Path) -> bool:
    try:
        candidate = Path.cwd() if not entry else Path(os.fspath(entry))
        return candidate.resolve(strict=True) == repository_root
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


class _ProtectedImportPath(list[str]):
    """Hide the repository from import traversal while satisfying legacy checks."""

    def __init__(self, values: tuple[str, ...], *, repository_root: Path) -> None:
        super().__init__(values)
        self._repository_root = repository_root

    def __contains__(self, value: object) -> bool:
        if _path_entry_is_repository_root(value, self._repository_root):
            return True
        return super().__contains__(value)

    def _reject_mutation(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise ValueError("Official C3 import path mutation is forbidden")

    append = _reject_mutation
    clear = _reject_mutation
    extend = _reject_mutation
    insert = _reject_mutation
    pop = _reject_mutation
    remove = _reject_mutation
    reverse = _reject_mutation
    sort = _reject_mutation
    __delitem__ = _reject_mutation
    __iadd__ = _reject_mutation
    __imul__ = _reject_mutation
    __setitem__ = _reject_mutation


def _require_repository_absent_from_sys_path() -> None:
    repository_root = ROOT.resolve(strict=True)
    for entry in sys.path:
        if _path_entry_is_repository_root(entry, repository_root):
            raise ValueError("Official C3 repository root leaked into the import path")


def _install_execution_namespaces() -> None:
    _require_repository_absent_from_sys_path()
    _require_no_execution_import_collisions()
    _install_namespace_package("scripts", ROOT / "scripts")
    _install_namespace_package("app", ROOT / "app")
    _install_namespace_package("app.backend", ROOT / "app" / "backend")


def _validate_installed_namespaces(expected: dict[str, ModuleType]) -> None:
    unexpected = sorted(
        name
        for name in sys.modules
        if (name.startswith("scripts.") or name.startswith("app."))
        and name not in expected
    )
    if unexpected or any(
        sys.modules.get(name) is not module for name, module in expected.items()
    ):
        raise ValueError("Official C3 protected imports changed during site activation")


def _isolate_project_bytecode() -> Path:
    temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    repository_root = ROOT.resolve(strict=True)
    if temporary_root == repository_root or temporary_root.is_relative_to(
        repository_root
    ):
        raise ValueError("Official C3 bytecode cache root is inside the repository")
    for _ in range(32):
        prefix = temporary_root / f"rei-c3-empty-pycache-{secrets.token_hex(16)}"
        if not os.path.lexists(prefix):
            sys.dont_write_bytecode = True
            sys.pycache_prefix = os.fspath(prefix)
            return prefix
    raise FileExistsError("Official C3 could not reserve an empty bytecode namespace")


def bootstrap_preflight() -> str:
    environment = _sanitized_git_environment()
    expected_git_directory = _validated_local_git_directory()
    repository_root = Path(_git_text(environment, "rev-parse", "--show-toplevel"))
    git_directory = Path(_git_text(environment, "rev-parse", "--absolute-git-dir"))
    if repository_root.resolve(strict=True) != ROOT.resolve(strict=True):
        raise ValueError("Official C3 Git toplevel differs from the script repository")
    _require_reported_git_directory(git_directory, expected_git_directory)
    if _git_text(environment, "branch", "--show-current") != "main":
        raise ValueError("Official C3 pair must execute directly on main")
    source_commit = _git_text(environment, "rev-parse", "HEAD")
    if len(source_commit) != 40:
        raise ValueError("Official C3 pair requires a full Git source commit")
    if _git_text(environment, "rev-parse", "--verify", "origin/main") != source_commit:
        raise ValueError("Official C3 pair requires HEAD to equal origin/main")
    _git_text(environment, "cat-file", "-e", f"{PROTOCOL_FREEZE_COMMIT}^{{commit}}")
    parents = _git_text(environment, "show", "-s", "--format=%P", source_commit).split()
    if parents != [PROTOCOL_FREEZE_COMMIT]:
        raise ValueError(
            "Official C3 execution commit must be the single direct child of "
            "the protocol-freeze commit"
        )
    changed = tuple(
        sorted(
            item
            for item in _git_text(
                environment,
                "diff",
                "--name-only",
                "--no-renames",
                PROTOCOL_FREEZE_COMMIT,
                source_commit,
                "--",
            ).splitlines()
            if item
        )
    )
    if changed != EXPECTED_SEAL_DELTA:
        raise ValueError("Official C3 seal commit delta differs from its allowlist")
    status = _git_text(
        environment,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *SCOPED_EXECUTION_PATHS,
    )
    if status:
        raise ValueError("Official C3 runtime, corpus, and seal sources must be clean")
    _validate_worktree_against_head(source_commit, environment=environment)
    _require_no_execution_import_collisions()
    if os.environ.get("REI_OLLAMA_NUM_CTX", "").strip() != "65536":
        raise ValueError("REI_OLLAMA_NUM_CTX must be explicitly set to 65536")
    if os.environ.get("REI_OLLAMA_NUM_GPU", "").strip() != "999":
        raise ValueError("REI_OLLAMA_NUM_GPU must be explicitly set to 999")
    return source_commit


def _require_isolated_startup() -> None:
    if not sys.flags.isolated or not sys.flags.no_site:
        raise ValueError(
            "Official C3 bootstrap requires Python flags -I -S before any site import"
        )


def main(argv: list[str] | None = None) -> int:
    _require_isolated_startup()
    source_commit = bootstrap_preflight()
    _install_execution_namespaces()
    protected_namespaces = {
        name: sys.modules[name] for name in ("scripts", "app", "app.backend")
    }
    protected_meta_path = tuple(sys.meta_path)
    protected_path_hooks = tuple(sys.path_hooks)
    import site

    site.main()
    sys.meta_path[:] = protected_meta_path
    sys.path_hooks[:] = protected_path_hooks
    sys.path_importer_cache.clear()
    _require_repository_absent_from_sys_path()
    _validate_installed_namespaces(protected_namespaces)
    _isolate_project_bytecode()
    if bootstrap_preflight() != source_commit:
        raise ValueError("Official C3 source changed during site activation")
    if type(sys.path) is not list:
        raise ValueError("Official C3 import path container differs")
    original_sys_path = sys.path
    protected_sys_path_snapshot = tuple(original_sys_path)
    guarded_sys_path = _ProtectedImportPath(
        protected_sys_path_snapshot,
        repository_root=ROOT.resolve(strict=True),
    )
    sys.path = guarded_sys_path
    try:
        implementation = importlib.import_module("scripts.c3_racio_official_pair")
        if sys.path is not guarded_sys_path or tuple(guarded_sys_path) != (
            protected_sys_path_snapshot
        ):
            raise ValueError("Official C3 import path changed during project import")
    finally:
        sys.path = original_sys_path
        original_sys_path[:] = protected_sys_path_snapshot
        sys.path_importer_cache.clear()
    _require_repository_absent_from_sys_path()
    implementation_path = ROOT / "scripts" / "c3_racio_official_pair.py"
    _require_regular_import_file(implementation_path, label="official implementation")
    if Path(implementation.__file__).resolve(
        strict=True
    ) != implementation_path.resolve(strict=True):
        raise ValueError("Official C3 implementation import escaped its frozen path")
    implementation_main = implementation.main

    return implementation_main(argv, bootstrap_source_commit=source_commit)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
