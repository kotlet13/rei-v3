#!/usr/bin/env python3
"""Create a reproducible snapshot of the textual REI-v3 architecture.

The snapshot is assembled from blobs in ``--source-ref``.  It never copies
selected files from the working tree, so local edits cannot silently change a
baseline.  The working tree is inspected only to record whether it was dirty
when the archive was requested.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Mapping, Sequence


DEFAULT_SOURCE_REF = "HEAD"
SNAPSHOT_DIRECTORY = "snapshot"

INCLUDED_ROOT_FILES = frozenset(
    {
        ".gitignore",
        "CURRENT.md",
        "README.md",
        "app/backend/requirements.txt",
        "pytest.ini",
    }
)
INCLUDED_PREFIXES = (
    "app/backend/rei/",
    "app/gui/",
    "scripts/",
    "tests/",
    "knowledge/",
    "datasets/",
    "Docs/evals/",
    # This repository currently keeps plans at the root.  Docs/plans remains
    # accepted so the archiver also works after a layout-only move.
    "plans/",
    "Docs/plans/",
)

REQUIRED_PREFIX_GROUPS = (
    ("app/backend/rei/",),
    ("app/gui/",),
    ("scripts/",),
    ("tests/",),
    ("knowledge/",),
    ("datasets/",),
    ("Docs/evals/",),
    ("plans/", "Docs/plans/"),
)

SOURCE_DOCUMENT_SUFFIXES = frozenset({".docx", ".pdf"})
ARCHIVE_DOCUMENTATION_PATHS = (
    "README.md",
    "ARCHITECTURE.md",
    "BASELINE_VERIFICATION.md",
    "artifacts/README.md",
)

EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "cache",
        "caches",
        "checkpoint",
        "checkpoints",
        "dist",
        "log",
        "logs",
        "model",
        "models",
        "node_modules",
        "output",
        "temp",
        "temporary",
        "tmp",
        "venv",
        "weights",
    }
)
MODEL_FILE_SUFFIXES = frozenset(
    {".ckpt", ".ggml", ".gguf", ".h5", ".onnx", ".pb", ".pt", ".pth", ".safetensors"}
)
TEMPORARY_FILE_SUFFIXES = frozenset({".bak", ".log", ".swp", ".temp", ".tmp"})
LOCAL_PROMPT_OVERRIDE_NAMES = frozenset(
    {
        "prompt_override.json",
        "prompt_override.tmp",
        "prompt_overrides.json",
        "prompt_overrides.tmp",
    }
)

EXCLUSION_POLICY = (
    ".git/**",
    "archive/** (the repository-level pre-existing archive tree)",
    "**/output/**",
    "**/{cache,caches,*_cache,__pycache__}/**",
    "**/{log,logs}/** and *.log",
    "**/{model,models,weights,checkpoint,checkpoints}/** and model weight files",
    "**/{.venv,venv}/**",
    "**/{tmp,temp,temporary}/** and temporary files",
    "local prompt override files",
)

ARCHIVE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
FULL_OBJECT_ID_PATTERN = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
CHECKSUM_LINE_PATTERN = re.compile(r"([0-9a-f]{64})  ([^\r\n]+)\Z")
WINDOWS_RESERVED_NAMES = frozenset(
    {"AUX", "CON", "NUL", "PRN"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
WINDOWS_FORBIDDEN_PATH_CHARACTERS = frozenset('<>:"|?*')


class ArchiveError(RuntimeError):
    """Raised when a safe, complete archive cannot be produced."""


class ArchiveRecoveryError(ArchiveError):
    """Raised when verified recovery material must not be cleaned automatically."""


@dataclass(frozen=True)
class GitIndexEntry:
    source_path: str
    mode: str
    object_id: str


def _decode_utf8(data: bytes, *, context: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArchiveError(f"{context} is not valid UTF-8: {exc}") from exc


def _run_git(
    repo_root: Path,
    args: Sequence[str],
    *,
    extra_env: Mapping[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    # The archive always targets the discovered repository and its real index;
    # caller-provided Git plumbing overrides must not redirect it elsewhere.
    for variable in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        environment.pop(variable, None)
    environment.update({"GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if extra_env:
        environment.update(extra_env)

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ArchiveError("Git is not installed or is not available on PATH") from exc

    if check and result.returncode != 0:
        stderr = _decode_utf8(result.stderr, context="Git stderr").strip()
        command = "git " + " ".join(args)
        raise ArchiveError(f"{command} failed ({result.returncode}): {stderr or 'no error output'}")
    return result


def _find_repo_root() -> Path:
    candidates = (Path.cwd(), Path(__file__).resolve().parent)
    visited: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in visited:
            continue
        visited.add(candidate)
        result = _run_git(candidate, ("rev-parse", "--show-toplevel"), check=False)
        if result.returncode == 0:
            root_text = _decode_utf8(result.stdout, context="repository path").strip()
            if root_text:
                return Path(root_text).resolve()
    raise ArchiveError("could not locate the Git repository containing this script")


def _validate_ref(value: str, *, option_name: str) -> str:
    if not value or value.startswith("-") or "\x00" in value or "\n" in value or "\r" in value:
        raise ArchiveError(f"{option_name} is not a safe Git revision: {value!r}")
    return value


def _resolve_source_commit(repo_root: Path, source_ref: str) -> str:
    source_ref = _validate_ref(source_ref, option_name="--source-ref")
    result = _run_git(
        repo_root,
        ("rev-parse", "--verify", "--end-of-options", f"{source_ref}^{{commit}}"),
    )
    commit = _decode_utf8(result.stdout, context="source commit").strip().lower()
    if not FULL_OBJECT_ID_PATTERN.fullmatch(commit):
        raise ArchiveError(f"Git returned an invalid full commit object ID: {commit!r}")
    return commit


def _resolve_source_branch(
    repo_root: Path,
    source_ref: str,
    source_commit: str,
    explicit_branch: str | None,
) -> str | None:
    if explicit_branch is not None:
        branch = _validate_ref(explicit_branch, option_name="--source-branch")
        branch_ref = branch if branch.startswith("refs/heads/") else f"refs/heads/{branch}"
        branch_result = _run_git(
            repo_root,
            ("rev-parse", "--verify", "--end-of-options", f"{branch_ref}^{{commit}}"),
            check=False,
        )
        if branch_result.returncode != 0:
            raise ArchiveError(f"--source-branch does not name a local branch: {branch!r}")
        branch_commit = _decode_utf8(branch_result.stdout, context="source branch commit").strip().lower()
        contains_source = _run_git(
            repo_root,
            ("merge-base", "--is-ancestor", source_commit, branch_commit),
            check=False,
        )
        if contains_source.returncode != 0:
            raise ArchiveError(
                f"--source-branch {branch!r} does not contain source commit {source_commit}"
            )
        return branch.removeprefix("refs/heads/")

    symbolic = _run_git(
        repo_root,
        ("rev-parse", "--symbolic-full-name", "--verify", "--end-of-options", source_ref),
        check=False,
    )
    if symbolic.returncode == 0:
        full_name = _decode_utf8(symbolic.stdout, context="symbolic source ref").strip()
        if full_name.startswith("refs/heads/"):
            return full_name.removeprefix("refs/heads/")
    return None


def _source_timestamp(repo_root: Path, source_commit: str) -> tuple[str, str]:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is not None:
        try:
            epoch = int(source_date_epoch)
            created_at = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (ValueError, OverflowError, OSError) as exc:
            raise ArchiveError("SOURCE_DATE_EPOCH must be a valid Unix timestamp") from exc
        return created_at, "SOURCE_DATE_EPOCH"

    result = _run_git(
        repo_root,
        ("show", "-s", "--no-show-signature", "--format=%cI", source_commit, "--"),
    )
    created_at = _decode_utf8(result.stdout, context="source commit timestamp").strip()
    if not created_at:
        raise ArchiveError("source commit has no committer timestamp")
    return created_at, "source_commit_committer_timestamp"


def _working_tree_status(repo_root: Path) -> list[dict[str, str]]:
    result = _run_git(
        repo_root,
        ("-c", "core.quotePath=false", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
    )
    records = result.stdout.split(b"\x00")
    entries: list[dict[str, str]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            raise ArchiveError("could not parse `git status --porcelain=v1 -z` output")
        status = record[:2].decode("ascii", errors="strict")
        path = _decode_utf8(record[3:], context="dirty working-tree path")
        entry = {"status": status, "path": path}
        if status[0] in "RC" or status[1] in "RC":
            if index >= len(records) or not records[index]:
                raise ArchiveError("rename/copy entry in Git status is missing its original path")
            entry["original_path"] = _decode_utf8(
                records[index], context="dirty working-tree original path"
            )
            index += 1
        entries.append(entry)
    return entries


def _source_index_entries(repo_root: Path, source_commit: str) -> list[GitIndexEntry]:
    """List the exact source tree through a temporary index and git ls-files."""

    with tempfile.TemporaryDirectory(prefix="rei-archive-index-") as temporary_directory:
        index_path = Path(temporary_directory) / "source.index"
        git_environment = {"GIT_INDEX_FILE": str(index_path.resolve())}
        _run_git(repo_root, ("read-tree", source_commit), extra_env=git_environment)
        result = _run_git(
            repo_root,
            ("ls-files", "--cached", "--stage", "--full-name", "-z", "--"),
            extra_env=git_environment,
        )

    entries: list[GitIndexEntry] = []
    seen_paths: set[str] = set()
    for raw_record in result.stdout.split(b"\x00"):
        if not raw_record:
            continue
        try:
            raw_header, raw_path = raw_record.split(b"\t", 1)
            raw_mode, raw_object_id, raw_stage = raw_header.split()
        except ValueError as exc:
            raise ArchiveError("could not parse `git ls-files --stage -z` output") from exc
        if raw_stage != b"0":
            raise ArchiveError("source tree unexpectedly contains an unmerged index stage")
        mode = raw_mode.decode("ascii", errors="strict")
        object_id = raw_object_id.decode("ascii", errors="strict").lower()
        source_path = _decode_utf8(raw_path, context="tracked source path")
        if source_path in seen_paths:
            raise ArchiveError(f"source tree contains a duplicate path: {source_path!r}")
        seen_paths.add(source_path)
        entries.append(GitIndexEntry(source_path=source_path, mode=mode, object_id=object_id))

    return sorted(entries, key=lambda item: item.source_path.encode("utf-8"))


def _validate_git_path(path: str) -> PurePosixPath:
    if not path or path.startswith("/") or "\\" in path or "\x00" in path or "\r" in path or "\n" in path:
        raise ArchiveError(f"tracked path cannot be represented safely in this archive: {path!r}")
    pure_path = PurePosixPath(path)
    if (
        pure_path.is_absolute()
        or pure_path.as_posix() != path
        or any(part in {"", ".", ".."} for part in pure_path.parts)
    ):
        raise ArchiveError(f"tracked path escapes the archive root: {path!r}")
    for part in pure_path.parts:
        windows_basename = part.split(".", 1)[0].upper()
        if (
            part.endswith((" ", "."))
            or windows_basename in WINDOWS_RESERVED_NAMES
            or any(character in WINDOWS_FORBIDDEN_PATH_CHARACTERS for character in part)
            or any(ord(character) < 32 for character in part)
        ):
            raise ArchiveError(
                f"tracked path is not safely representable on Windows: {path!r}"
            )
    return pure_path


def _is_selected(path: str) -> bool:
    return path in INCLUDED_ROOT_FILES or any(path.startswith(prefix) for prefix in INCLUDED_PREFIXES)


def _exclusion_reason(path: str) -> str | None:
    pure_path = _validate_git_path(path)
    lowered_parts = tuple(part.casefold() for part in pure_path.parts)
    basename = lowered_parts[-1]
    suffix = PurePosixPath(basename).suffix

    if path.startswith("Docs/") and suffix in SOURCE_DOCUMENT_SUFFIXES:
        return "source_document_recorded_not_copied"
    blocked_part = next((part for part in lowered_parts[:-1] if part in EXCLUDED_DIRECTORY_NAMES), None)
    if blocked_part is not None:
        return f"excluded_directory:{blocked_part}"
    if any(part.endswith("_cache") for part in lowered_parts[:-1]):
        return "excluded_directory:cache"
    if basename in LOCAL_PROMPT_OVERRIDE_NAMES or "prompt_override" in basename:
        return "local_prompt_override"
    if basename == ".env" or (basename.startswith(".env.") and basename != ".env.example"):
        return "local_environment_configuration"
    if suffix in MODEL_FILE_SUFFIXES:
        return "model_weight_file"
    if suffix in TEMPORARY_FILE_SUFFIXES or basename.endswith("~"):
        return "temporary_or_log_file"
    return None


def _archive_path(source_path: str) -> str:
    if source_path.startswith("tests/"):
        return f"{SNAPSHOT_DIRECTORY}/reference_tests/{source_path.removeprefix('tests/')}"
    return f"{SNAPSHOT_DIRECTORY}/{source_path}"


def _read_git_blob(repo_root: Path, entry: GitIndexEntry) -> bytes:
    if entry.mode not in {"100644", "100755", "120000"}:
        raise ArchiveError(f"{entry.source_path!r} has unsupported Git mode {entry.mode}")
    return _run_git(repo_root, ("cat-file", "blob", entry.object_id)).stdout


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_bytes(path: Path, content: bytes, *, git_mode: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if os.name != "nt" and git_mode in {"100644", "100755"}:
        path.chmod(0o755 if git_mode == "100755" else 0o644)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _destination_path(archive_root: Path, archive_path: str) -> Path:
    pure_path = _validate_git_path(archive_path)
    destination = archive_root.joinpath(*pure_path.parts)
    try:
        destination.relative_to(archive_root)
    except ValueError as exc:
        raise ArchiveError(f"archive path escapes target directory: {archive_path!r}") from exc
    return destination


def _assert_required_scopes(selected_paths: set[str]) -> None:
    missing_root_files = sorted(INCLUDED_ROOT_FILES.difference(selected_paths))
    missing_prefix_groups = [
        " or ".join(group)
        for group in REQUIRED_PREFIX_GROUPS
        if not any(any(path.startswith(prefix) for prefix in group) for path in selected_paths)
    ]
    if missing_root_files or missing_prefix_groups:
        details: list[str] = []
        if missing_root_files:
            details.append("root files: " + ", ".join(missing_root_files))
        if missing_prefix_groups:
            details.append("subtrees: " + ", ".join(missing_prefix_groups))
        raise ArchiveError("source ref is missing required archive content (" + "; ".join(details) + ")")


def _assert_no_destination_collisions(paths: Sequence[str]) -> None:
    destinations: dict[str, str] = {}
    for path in paths:
        platform_path = str(PurePosixPath(path)).replace("/", os.sep)
        key = os.path.normcase(platform_path)
        if key in destinations:
            raise ArchiveError(
                f"archive paths collide on this platform: {destinations[key]!r} and {path!r}"
            )
        destinations[key] = path


def _source_documents(
    repo_root: Path,
    entries: Sequence[GitIndexEntry],
) -> list[dict[str, object]]:
    documents: list[dict[str, object]] = []
    for entry in entries:
        pure_path = _validate_git_path(entry.source_path)
        if (
            len(pure_path.parts) < 2
            or pure_path.parts[0] != "Docs"
            or pure_path.suffix.casefold() not in SOURCE_DOCUMENT_SUFFIXES
        ):
            continue
        content = _read_git_blob(repo_root, entry)
        documents.append(
            {
                "git_mode": entry.mode,
                "git_object_id": entry.object_id,
                "is_git_lfs_pointer": content.startswith(b"version https://git-lfs.github.com/spec/v1\n"),
                "sha256": _sha256_bytes(content),
                "size_bytes": len(content),
                "source_path": entry.source_path,
            }
        )
    return documents


def _checksum_file_bytes(checksums: Mapping[str, str]) -> bytes:
    lines = [f"{checksums[path]}  {path}\n" for path in sorted(checksums, key=lambda item: item.encode("utf-8"))]
    return "".join(lines).encode("utf-8")


def _archive_documentation(
    target: Path,
    *,
    source_commit: str,
    documentation_source: Path | None,
) -> tuple[dict[str, bytes], str]:
    """Load hand-authored docs from a complete archive with matching provenance."""

    if documentation_source is None:
        if not target.exists():
            raise ArchiveError(
                "a new archive requires --documentation-source pointing to a complete "
                "archive directory with matching SOURCE_COMMIT"
            )
        source = target
        source_label = "existing archive target"
    else:
        source = documentation_source.expanduser().resolve()
        source_label = "explicit --documentation-source"

    if source.is_symlink() or not source.is_dir():
        raise ArchiveError(
            "the archive documentation source must be a real directory"
        )

    source_commit_path = _destination_path(source, "SOURCE_COMMIT")
    if source_commit_path.is_symlink() or not source_commit_path.is_file():
        raise ArchiveError("archive documentation source is missing SOURCE_COMMIT")
    documented_commit = _decode_utf8(
        source_commit_path.read_bytes(), context="archive documentation SOURCE_COMMIT"
    ).strip().lower()
    if documented_commit != source_commit:
        raise ArchiveError(
            "archive documentation belongs to source commit "
            f"{documented_commit!r}, not requested commit {source_commit}"
        )

    documentation: dict[str, bytes] = {}
    missing: list[str] = []
    for archive_path in ARCHIVE_DOCUMENTATION_PATHS:
        path = _destination_path(source, archive_path)
        if path.is_symlink() or not path.is_file():
            missing.append(archive_path)
            continue
        documentation[archive_path] = path.read_bytes()
    if missing:
        raise ArchiveError(
            "existing archive target is missing required hand-authored documentation: "
            + ", ".join(missing)
        )
    return documentation, source_label


def _verify_written_archive(
    archive_root: Path,
    manifest: Mapping[str, object],
    expected_checksums: Mapping[str, str],
) -> None:
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list):
        raise ArchiveError("generated manifest has no valid files list")
    for file_record in manifest_files:
        if not isinstance(file_record, dict):
            raise ArchiveError("generated manifest contains an invalid file record")
        archive_path = file_record.get("archive_path")
        expected_hash = file_record.get("sha256")
        if not isinstance(archive_path, str) or not isinstance(expected_hash, str):
            raise ArchiveError("generated manifest file record is missing path or hash")
        actual_hash = _sha256_file(_destination_path(archive_root, archive_path))
        if actual_hash != expected_hash:
            raise ArchiveError(f"post-write SHA-256 mismatch for {archive_path}")

    checksum_path = archive_root / "FILES.sha256"
    parsed_checksums: dict[str, str] = {}
    checksum_text = _decode_utf8(checksum_path.read_bytes(), context="FILES.sha256")
    for line in checksum_text.splitlines():
        match = CHECKSUM_LINE_PATTERN.fullmatch(line)
        if match is None:
            raise ArchiveError(f"invalid FILES.sha256 line: {line!r}")
        digest, relative_path = match.groups()
        if relative_path in parsed_checksums:
            raise ArchiveError(f"duplicate FILES.sha256 path: {relative_path!r}")
        parsed_checksums[relative_path] = digest

    if parsed_checksums != dict(expected_checksums):
        raise ArchiveError("FILES.sha256 does not contain the expected path/hash set")
    for relative_path, expected_hash in parsed_checksums.items():
        actual_hash = _sha256_file(_destination_path(archive_root, relative_path))
        if actual_hash != expected_hash:
            raise ArchiveError(f"post-write SHA-256 mismatch for {relative_path}")


def _install_staging(staging: Path, target: Path, *, target_exists: bool) -> None:
    """Install a verified staging tree while retaining rollback material."""

    if not target_exists:
        staging.replace(target)
        return

    backup = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent)
    )
    backup.rmdir()
    try:
        target.replace(backup)
        staging.replace(target)
    except BaseException:
        if not target.exists() and backup.exists():
            try:
                backup.replace(target)
            except BaseException as rollback_error:
                raise ArchiveRecoveryError(
                    "archive installation and rollback both failed; preserve these paths "
                    f"for manual recovery: target={target}, backup={backup}, "
                    f"verified_staging={staging}"
                ) from rollback_error
        raise

    try:
        shutil.rmtree(backup)
    except OSError as exc:
        print(
            f"warning: installed archive but could not remove backup {backup}: {exc}",
            file=sys.stderr,
        )


def _validate_archive_id(archive_id: str) -> str:
    windows_basename = archive_id.split(".", 1)[0].upper()
    if (
        archive_id in {".", ".."}
        or archive_id.endswith(".")
        or ARCHIVE_ID_PATTERN.fullmatch(archive_id) is None
        or windows_basename in WINDOWS_RESERVED_NAMES
    ):
        raise ArchiveError(
            "--archive-id must use only ASCII letters, digits, dots, underscores, and hyphens"
        )
    return archive_id


def create_archive(
    *,
    archive_id: str,
    source_ref: str,
    source_branch: str | None,
    documentation_source: Path | None,
    force: bool,
    require_clean: bool,
) -> Path:
    repo_root = _find_repo_root()
    archive_id = _validate_archive_id(archive_id)
    source_commit = _resolve_source_commit(repo_root, source_ref)
    recorded_source_branch = _resolve_source_branch(
        repo_root, source_ref, source_commit, source_branch
    )
    dirty_entries = _working_tree_status(repo_root)
    if dirty_entries and require_clean:
        raise ArchiveError("working tree is dirty and --require-clean was requested")

    archive_parent = (repo_root / "archive").resolve()
    target = archive_parent / archive_id
    target_exists = target.exists() or target.is_symlink()
    if target_exists and not force:
        raise ArchiveError(f"archive target already exists: {target} (pass --force to replace it)")
    archive_documentation, documentation_source_label = _archive_documentation(
        target,
        source_commit=source_commit,
        documentation_source=documentation_source,
    )

    all_entries = _source_index_entries(repo_root, source_commit)
    source_documents = _source_documents(repo_root, all_entries)
    selected_entries: list[GitIndexEntry] = []
    excluded_files: list[dict[str, str]] = []
    for entry in all_entries:
        if not _is_selected(entry.source_path):
            continue
        reason = _exclusion_reason(entry.source_path)
        if reason is not None:
            excluded_files.append({"reason": reason, "source_path": entry.source_path})
            continue
        if entry.mode == "120000":
            raise ArchiveError(
                f"selected source path is a symbolic link and cannot be materialized safely: "
                f"{entry.source_path!r}"
            )
        if entry.mode not in {"100644", "100755"}:
            excluded_files.append(
                {"reason": f"unsupported_git_mode:{entry.mode}", "source_path": entry.source_path}
            )
            continue
        selected_entries.append(entry)

    selected_paths = {entry.source_path for entry in selected_entries}
    _assert_required_scopes(selected_paths)
    archive_paths = [
        *ARCHIVE_DOCUMENTATION_PATHS,
        *(_archive_path(entry.source_path) for entry in selected_entries),
        "SOURCE_COMMIT",
        "MANIFEST.json",
        "FILES.sha256",
    ]
    _assert_no_destination_collisions(archive_paths)
    created_at, created_at_basis = _source_timestamp(repo_root, source_commit)

    archive_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{archive_id}.tmp-", dir=archive_parent))
    try:
        file_records: list[dict[str, object]] = []
        for archive_path, content in archive_documentation.items():
            _write_bytes(_destination_path(staging, archive_path), content)
            file_records.append(
                {
                    "archive_path": archive_path,
                    "record_kind": "archive_documentation",
                    "sha256": _sha256_bytes(content),
                    "size_bytes": len(content),
                    "source_path": None,
                }
            )
        for entry in selected_entries:
            content = _read_git_blob(repo_root, entry)
            archive_path = _archive_path(entry.source_path)
            _write_bytes(
                _destination_path(staging, archive_path),
                content,
                git_mode=entry.mode,
            )
            file_records.append(
                {
                    "archive_path": archive_path,
                    "git_mode": entry.mode,
                    "git_object_id": entry.object_id,
                    "record_kind": "source_snapshot",
                    "sha256": _sha256_bytes(content),
                    "size_bytes": len(content),
                    "source_path": entry.source_path,
                }
            )

        source_commit_content = (source_commit + "\n").encode("ascii")
        _write_bytes(staging / "SOURCE_COMMIT", source_commit_content)

        manifest: dict[str, object] = {
            "archive_id": archive_id,
            "archive_schema_version": 1,
            "baseline": {
                "architecture": "textual-three-processor-plus-ego-llm",
                "entrypoint": "ReiEngine.run_rei_cycle",
                "matrix": "13 x 12 = 156",
                "runner": "scripts/run_rei_profile_matrix.py",
            },
            "checksum_manifest": {
                "algorithm": "sha256",
                "path": "FILES.sha256",
                "self_excluded": True,
            },
            "content_source": "raw Git blobs from source_commit; no working-tree file copies",
            "documentation_source": documentation_source_label,
            "created_at": created_at,
            "created_at_basis": created_at_basis,
            "dirty_tree_before_archive": bool(dirty_entries),
            "dirty_tree_entries": dirty_entries,
            "excluded_files": sorted(
                excluded_files, key=lambda item: item["source_path"].encode("utf-8")
            ),
            "excluded_paths": list(EXCLUSION_POLICY),
            "files": file_records,
            "known_designs": {
                "acceptance": "keyword heuristic",
                "processor_input": "same text plus profile and influence weights",
                "profiles": "continuous numeric weights",
                "synthesis": "EgoResultant LLM plus deterministic fallback",
            },
            "source_branch": recorded_source_branch,
            "source_commit": source_commit,
            "source_documents": source_documents,
            "source_ref_requested": source_ref,
            "verification": {
                "archive_hashes": "passed",
                "deterministic_smoke": "not run by archive script",
                "pytest_command": "python -m pytest -q",
                "pytest_result": "not run by archive script",
            },
        }
        manifest_content = _json_bytes(manifest)
        _write_bytes(staging / "MANIFEST.json", manifest_content)

        checksums = {record["archive_path"]: record["sha256"] for record in file_records}
        checksums["SOURCE_COMMIT"] = _sha256_bytes(source_commit_content)
        checksums["MANIFEST.json"] = _sha256_bytes(manifest_content)
        if not all(isinstance(path, str) and isinstance(digest, str) for path, digest in checksums.items()):
            raise ArchiveError("internal error while constructing archive checksums")
        typed_checksums = {str(path): str(digest) for path, digest in checksums.items()}
        _write_bytes(staging / "FILES.sha256", _checksum_file_bytes(typed_checksums))

        _verify_written_archive(staging, manifest, typed_checksums)

        _install_staging(staging, target, target_exists=target_exists)
    except BaseException as exc:
        if staging.exists() and not isinstance(exc, ArchiveRecoveryError):
            shutil.rmtree(staging, ignore_errors=True)
        raise

    if dirty_entries:
        print(
            "warning: the working tree was dirty; the snapshot still contains only "
            f"blobs from {source_commit}",
            file=sys.stderr,
        )
    print(f"archive created: {target}")
    print(f"source commit: {source_commit}")
    print(f"files archived: {len(selected_entries)}")
    print(f"source documents recorded (not copied): {len(source_documents)}")
    print("SHA-256 verification: passed")
    return target


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive the tracked textual REI-v3 baseline from a Git source ref."
    )
    parser.add_argument("--archive-id", required=True, help="target directory name below archive/")
    parser.add_argument(
        "--source-ref",
        default=DEFAULT_SOURCE_REF,
        help=f"commit-ish to archive (default: {DEFAULT_SOURCE_REF})",
    )
    parser.add_argument(
        "--source-branch",
        help=(
            "original local branch name to record; required when --source-ref is a raw SHA and "
            "the original branch cannot be inferred"
        ),
    )
    parser.add_argument(
        "--documentation-source",
        type=Path,
        help=(
            "complete archive directory supplying README.md, ARCHITECTURE.md, "
            "BASELINE_VERIFICATION.md, artifacts/README.md, and a matching SOURCE_COMMIT; "
            "defaults to the existing target when using --force"
        ),
    )
    parser.add_argument("--force", action="store_true", help="replace an existing archive target")
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="fail instead of recording and warning about a dirty working tree",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        create_archive(
            archive_id=arguments.archive_id,
            source_ref=arguments.source_ref,
            source_branch=arguments.source_branch,
            documentation_source=arguments.documentation_source,
            force=arguments.force,
            require_clean=arguments.require_clean,
        )
    except ArchiveError as exc:
        print(f"archive failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
