"""Strict, restart-safe persistence for one REI run artifact tree."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Iterator

from pydantic import TypeAdapter, ValidationError

from ..ids import canonical_json_bytes, content_id
from ..models.common import ArtifactRelativePath
from ..models.provider import ProviderIdentity
from ..providers.protocols import ArtifactStore, StoredArtifact


DEFAULT_RUNS_ROOT = Path("output/runs")
RUN_TREE_DIRECTORIES: tuple[str, ...] = (
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
)
OPTIONAL_RUN_TREE_DIRECTORIES: tuple[str, ...] = (
    "emocio/embeddings",
)

_RUN_TOP_LEVEL = frozenset(path.split("/", 1)[0] for path in RUN_TREE_DIRECTORIES)
_ALLOWED_RUN_TREE_DIRECTORIES = frozenset(
    (*RUN_TREE_DIRECTORIES, *OPTIONAL_RUN_TREE_DIRECTORIES)
)
_RELATIVE_PATH_ADAPTER = TypeAdapter(ArtifactRelativePath)
_STORAGE_ID_PATTERN = re.compile(r"^stored_[0-9a-f]{32}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_FORBIDDEN = frozenset('<>:"|?*')
_WINDOWS_DEVICE_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CLOCK$",
        "CONIN$",
        "CONOUT$",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
        "COM¹",
        "COM²",
        "COM³",
        "LPT¹",
        "LPT²",
        "LPT³",
    }
)
_TEMP_PREFIX = ".rei-artifact-"
_TEMP_SUFFIX = ".tmp"
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_MAX_COMPONENT_UTF8_BYTES = 255
_MAX_COMPONENT_UTF16_UNITS = 255
_MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_HASH_CHUNK_BYTES = 1024 * 1024


class ArtifactStoreError(RuntimeError):
    """Base class for artifact persistence failures."""


class ArtifactExistsError(ArtifactStoreError):
    """A create-only artifact path already exists."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Stored bytes or metadata no longer match their immutable identity."""


class ArtifactNotFoundError(ArtifactIntegrityError):
    """No intact stored artifact has the requested content identity."""


def _windows_device_base(segment: str) -> str:
    return segment.split(".", 1)[0].rstrip(" .").upper()


def _reject_portability_hazards(value: str, *, field_name: str) -> None:
    try:
        utf8 = value.encode("utf-8")
        utf16 = value.encode("utf-16-le")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must be valid Unicode") from exc
    if len(utf8) > _MAX_COMPONENT_UTF8_BYTES:
        raise ValueError(f"{field_name} exceeds the portable UTF-8 component limit")
    if len(utf16) // 2 > _MAX_COMPONENT_UTF16_UNITS:
        raise ValueError(f"{field_name} exceeds the Windows component limit")
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{field_name} must use canonical NFC Unicode")
    if value != value.strip() or value.endswith("."):
        raise ValueError(f"{field_name} cannot have edge spaces or a trailing dot")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{field_name} cannot contain control characters")
    if any(character in _WINDOWS_FORBIDDEN for character in value):
        raise ValueError(f"{field_name} must be portable across supported platforms")
    if "~" in value:
        raise ValueError(f"{field_name} cannot use an NTFS short-name alias marker")


def validate_run_id(run_id: str) -> str:
    """Validate a run ID as one portable directory segment without normalization."""

    if type(run_id) is not str:
        raise TypeError("run_id must be a string")
    if not run_id or len(run_id) > 200:
        raise ValueError("run_id must contain between 1 and 200 characters")
    if run_id in {".", ".."} or "/" in run_id or "\\" in run_id:
        raise ValueError("run_id must be one relative path segment")
    if run_id.casefold() != run_id:
        raise ValueError("run_id must use lowercase canonical spelling")
    _reject_portability_hazards(run_id, field_name="run_id")
    if _windows_device_base(run_id) in _WINDOWS_DEVICE_NAMES:
        raise ValueError("run_id cannot use a reserved platform device name")
    return run_id


def validate_relative_path(relative_path: str) -> str:
    """Validate a canonical portable path relative to one run root."""

    try:
        canonical = _RELATIVE_PATH_ADAPTER.validate_python(relative_path, strict=True)
    except ValidationError as exc:
        raise ValueError("Artifact relative path is not canonical and portable") from exc
    for segment in canonical.split("/"):
        _reject_portability_hazards(segment, field_name="Artifact path segment")
        if segment.casefold() != segment:
            raise ValueError("Artifact path segments must use lowercase spelling")
        if _windows_device_base(segment) in _WINDOWS_DEVICE_NAMES:
            raise ValueError("Artifact path cannot use a reserved platform device name")
        if segment.startswith(_TEMP_PREFIX) and segment.endswith(_TEMP_SUFFIX):
            raise ValueError("Artifact path collides with the store's temporary namespace")
    if canonical != "run_manifest.json" and canonical.split("/", 1)[0] not in _RUN_TOP_LEVEL:
        raise ValueError("Artifact path is outside the canonical REI run tree")
    return canonical


def _metadata_payload(
    *,
    run_id: str,
    relative_path: str,
    content_sha256: str,
    size_bytes: int,
) -> dict[str, Any]:
    if type(content_sha256) is not str or not _SHA256_PATTERN.fullmatch(content_sha256):
        raise ValueError("content_sha256 must be one lowercase SHA-256 digest")
    if type(size_bytes) is not int or size_bytes < 0:
        raise ValueError("size_bytes must be a non-negative integer")
    return {
        "schema_version": "rei-native-stored-artifact-v1",
        "run_id": validate_run_id(run_id),
        "relative_path": validate_relative_path(relative_path),
        "content_sha256": content_sha256,
        "size_bytes": size_bytes,
    }


def stored_artifact_id(
    *,
    run_id: str,
    relative_path: str,
    content_sha256: str,
    size_bytes: int,
) -> str:
    """Return the canonical identity of immutable stored-artifact metadata."""

    return content_id(
        "stored",
        _metadata_payload(
            run_id=run_id,
            relative_path=relative_path,
            content_sha256=content_sha256,
            size_bytes=size_bytes,
        ),
    )


def validate_stored_artifact(artifact: StoredArtifact) -> StoredArtifact:
    """Reject metadata whose storage ID is not derived from its exact fields."""

    expected = stored_artifact_id(
        run_id=artifact.run_id,
        relative_path=artifact.relative_path,
        content_sha256=artifact.content_sha256,
        size_bytes=artifact.size_bytes,
    )
    if artifact.storage_id != expected:
        raise ArtifactIntegrityError("StoredArtifact ID does not match canonical metadata")
    return artifact


def _stored_artifact(run_id: str, relative_path: str, content: bytes) -> StoredArtifact:
    digest = hashlib.sha256(content).hexdigest()
    return _stored_artifact_from_digest(
        run_id,
        relative_path,
        content_sha256=digest,
        size_bytes=len(content),
    )


def _stored_artifact_from_digest(
    run_id: str,
    relative_path: str,
    *,
    content_sha256: str,
    size_bytes: int,
) -> StoredArtifact:
    payload = _metadata_payload(
        run_id=run_id,
        relative_path=relative_path,
        content_sha256=content_sha256,
        size_bytes=size_bytes,
    )
    return StoredArtifact(storage_id=content_id("stored", payload), **payload)


def _is_reparse_stat(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _path_exists_without_following(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _absolute_without_resolving(path: Path) -> Path:
    """Return an absolute lexical path without adopting symlink targets."""

    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_reparse_ancestry(path: Path) -> None:
    """Reject a configured root whose existing ancestry contains a reparse point."""

    absolute = _absolute_without_resolving(path)
    parts = absolute.parts
    if not parts:
        raise ValueError("Artifact store root must be an absolute path")
    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse_stat(current_stat):
            raise ValueError(
                "Artifact store root ancestry cannot contain a symlink or reparse point"
            )


def _assert_below_root(root: Path, path: Path) -> None:
    if not path.is_relative_to(root):
        raise ValueError("Artifact path escapes the configured runs root")


def _assert_no_reparse_components(
    root: Path,
    path: Path,
    *,
    leaf_may_be_file: bool = False,
) -> None:
    """Reject symlink/junction traversal for every currently existing component."""

    _assert_below_root(root, path)
    relative_parts = path.relative_to(root).parts
    current = root
    for index, part in enumerate(relative_parts):
        current /= part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse_stat(current_stat):
            raise ArtifactIntegrityError(
                "Artifact path traverses a symlink or reparse point"
            )
        is_leaf = index == len(relative_parts) - 1
        if (not is_leaf or not leaf_may_be_file) and not stat.S_ISDIR(current_stat.st_mode):
            raise ArtifactIntegrityError("Artifact path parent is not a directory")

    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ArtifactIntegrityError(
            "Artifact path resolves outside the configured runs root"
        )


def _sync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


_LOCKS_GUARD = Lock()
_PATH_LOCKS: dict[Path, RLock] = {}


def _thread_lock_for(path: Path) -> RLock:
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(path, RLock())


class FileArtifactStore:
    """Create-only artifact store rooted at ``output/runs/{run_id}``.

    Configured roots and all existing descendants reject symlink/reparse
    traversal. The containing filesystem is still an operational trust
    boundary: a hostile actor with concurrent mutation rights can race path
    checks, so run roots must not be shared with untrusted writers.
    """

    def __init__(
        self,
        root: str | os.PathLike[str] = DEFAULT_RUNS_ROOT,
        *,
        create: bool = True,
    ) -> None:
        if type(create) is not bool:
            raise TypeError("create must be a boolean")
        root_path = _absolute_without_resolving(Path(root).expanduser())
        _assert_no_reparse_ancestry(root_path)
        if root_path.exists() and not root_path.is_dir():
            raise ValueError("Artifact store root must be a directory")
        if create:
            root_path.mkdir(parents=True, exist_ok=True)
        elif not root_path.exists():
            raise ArtifactNotFoundError("Artifact store root is missing")
        _assert_no_reparse_ancestry(root_path)
        try:
            self._root = root_path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError("Artifact store root is missing") from exc
        self._records: dict[str, StoredArtifact] = {}
        self._records_lock = RLock()
        identity_payload = {
            "kind": "artifact_store",
            "implementation": "rei.persistence.FileArtifactStore",
            "implementation_revision": "b11-v1",
        }
        self._identity = ProviderIdentity(
            provider_id=content_id("provider", identity_payload),
            kind="artifact_store",
            implementation="rei.persistence.FileArtifactStore",
            implementation_revision="b11-v1",
        )

    @property
    def root(self) -> Path:
        return self._root

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def run_path(self, run_id: str) -> Path:
        canonical_run_id = validate_run_id(run_id)
        path = self._root / canonical_run_id
        _assert_no_reparse_components(self._root, path)
        return path

    def artifact_path(self, run_id: str, relative_path: str) -> Path:
        canonical_path = validate_relative_path(relative_path)
        path = self.run_path(run_id).joinpath(*canonical_path.split("/"))
        _assert_no_reparse_components(
            self._root,
            path,
            leaf_may_be_file=True,
        )
        return path

    def ensure_run_tree(self, run_id: str) -> Path:
        """Idempotently create only the directories declared by the B11 plan."""

        run_path = self.run_path(run_id)
        with _thread_lock_for(run_path):
            run_path.mkdir(parents=False, exist_ok=True)
            _assert_no_reparse_components(self._root, run_path)
            for relative_directory in RUN_TREE_DIRECTORIES:
                directory = run_path.joinpath(*relative_directory.split("/"))
                directory.mkdir(parents=True, exist_ok=True)
                _assert_no_reparse_components(self._root, directory)
            _sync_directory(run_path)
            _sync_directory(self._root)
        return run_path

    def _prepare_target(self, run_id: str, relative_path: str) -> tuple[str, str, Path]:
        canonical_run_id = validate_run_id(run_id)
        canonical_path = validate_relative_path(relative_path)
        self.ensure_run_tree(canonical_run_id)
        target = self.artifact_path(canonical_run_id, canonical_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        _assert_no_reparse_components(self._root, target.parent)
        _assert_no_reparse_components(
            self._root,
            target,
            leaf_may_be_file=True,
        )
        return canonical_run_id, canonical_path, target

    def _atomic_create(self, target: Path, content: bytes) -> None:
        if _path_exists_without_following(target):
            raise ArtifactExistsError(f"Artifact path already exists: {target.name}")

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=_TEMP_PREFIX,
            suffix=_TEMP_SUFFIX,
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        linked = False
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            _assert_no_reparse_components(self._root, target.parent)
            try:
                os.link(temporary, target, follow_symlinks=False)
                linked = True
            except FileExistsError as exc:
                raise ArtifactExistsError(
                    f"Artifact path already exists: {target.name}"
                ) from exc
            except OSError as exc:
                raise ArtifactStoreError("Atomic artifact creation failed") from exc
            _assert_no_reparse_components(
                self._root,
                target,
                leaf_may_be_file=True,
            )
            target_stat = target.lstat()
            if not stat.S_ISREG(target_stat.st_mode):
                raise ArtifactIntegrityError("Stored artifact is not a regular file")
            _sync_directory(target.parent)
        except Exception:
            if linked:
                try:
                    if os.path.samestat(temporary.stat(), target.lstat()):
                        target.unlink()
                except OSError:
                    pass
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def write_json(
        self,
        run_id: str,
        relative_path: str,
        artifact: Any,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact:
        """Write canonical UTF-8 JSON using the same B2 serializer as hashing."""

        return self.write_bytes(
            run_id,
            relative_path,
            canonical_json_bytes(artifact),
            overwrite=overwrite,
        )

    def write_bytes(
        self,
        run_id: str,
        relative_path: str,
        content: bytes,
        *,
        overwrite: bool = False,
    ) -> StoredArtifact:
        """Atomically create one immutable artifact and verify it from disk."""

        if overwrite is not False:
            raise ValueError("FileArtifactStore never permits overwrite")
        if type(content) is not bytes:
            raise TypeError("Artifact content must be immutable bytes")
        canonical_run_id, canonical_path, target = self._prepare_target(
            run_id,
            relative_path,
        )
        expected = _stored_artifact(canonical_run_id, canonical_path, content)
        with _thread_lock_for(target):
            self._atomic_create(target, content)
            persisted, inspected = self._read_target(
                canonical_run_id,
                canonical_path,
                target,
                expected_size=expected.size_bytes,
            )
            if persisted != content or inspected != expected:
                raise ArtifactIntegrityError(
                    "Persisted artifact differs from its create-only input"
                )
        with self._records_lock:
            self._records[expected.storage_id] = expected
        return expected

    def _read_target(
        self,
        run_id: str,
        relative_path: str,
        target: Path,
        *,
        expected_size: int | None = None,
        maximum_size: int | None = None,
    ) -> tuple[bytes, StoredArtifact]:
        relevant_limits = tuple(
            limit
            for limit in (expected_size, maximum_size)
            if limit is not None
        )
        _assert_no_reparse_components(
            self._root,
            target,
            leaf_may_be_file=True,
        )
        try:
            before = target.lstat()
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError("Stored artifact file is missing") from exc
        if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
            raise ArtifactIntegrityError("Stored artifact is not a regular file")
        if expected_size is not None and before.st_size != expected_size:
            raise ArtifactIntegrityError("Stored artifact size differs from metadata")
        if maximum_size is not None and before.st_size > maximum_size:
            raise ArtifactIntegrityError("Stored artifact exceeds the safe read limit")

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags)
        except OSError as exc:
            raise ArtifactIntegrityError("Stored artifact could not be opened safely") from exc
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise ArtifactIntegrityError("Opened artifact is not a regular file")
            if not os.path.samestat(before, opened):
                raise ArtifactIntegrityError("Stored artifact changed before it was read")
            if expected_size is not None and opened.st_size != expected_size:
                raise ArtifactIntegrityError("Stored artifact size differs from metadata")
            if maximum_size is not None and opened.st_size > maximum_size:
                raise ArtifactIntegrityError("Stored artifact exceeds the safe read limit")
            read_limit = min((opened.st_size, *relevant_limits))
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                content = handle.read(read_limit + 1)
        finally:
            os.close(descriptor)

        try:
            after = target.lstat()
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError("Stored artifact changed while it was read") from exc
        if (
            _is_reparse_stat(after)
            or not os.path.samestat(opened, after)
            or opened.st_size != len(content)
        ):
            raise ArtifactIntegrityError("Stored artifact changed while it was read")
        return content, _stored_artifact(run_id, relative_path, content)

    def inspect(
        self,
        run_id: str,
        relative_path: str,
        *,
        expected: StoredArtifact | None = None,
    ) -> StoredArtifact:
        """Re-read one path and return its freshly derived immutable metadata."""

        canonical_run_id = validate_run_id(run_id)
        canonical_path = validate_relative_path(relative_path)
        target = self.artifact_path(canonical_run_id, canonical_path)
        inspected = self._inspect_target_streaming(
            canonical_run_id,
            canonical_path,
            target,
            expected_size=None if expected is None else expected.size_bytes,
        )
        if expected is not None:
            validate_stored_artifact(expected)
            if inspected != expected:
                raise ArtifactIntegrityError("Stored bytes differ from expected metadata")
        with self._records_lock:
            self._records[inspected.storage_id] = inspected
        return inspected

    def _inspect_target_streaming(
        self,
        run_id: str,
        relative_path: str,
        target: Path,
        *,
        expected_size: int | None = None,
    ) -> StoredArtifact:
        """Derive immutable metadata without materializing an unknown artifact."""

        _assert_no_reparse_components(
            self._root,
            target,
            leaf_may_be_file=True,
        )
        try:
            before = target.lstat()
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError("Stored artifact file is missing") from exc
        if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
            raise ArtifactIntegrityError("Stored artifact is not a regular file")
        if expected_size is not None and before.st_size != expected_size:
            raise ArtifactIntegrityError("Stored artifact size differs from metadata")

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags)
        except OSError as exc:
            raise ArtifactIntegrityError("Stored artifact could not be opened safely") from exc
        digest = hashlib.sha256()
        total_size = 0
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise ArtifactIntegrityError("Opened artifact is not a regular file")
            if not os.path.samestat(before, opened):
                raise ArtifactIntegrityError("Stored artifact changed before it was read")
            if expected_size is not None and opened.st_size != expected_size:
                raise ArtifactIntegrityError("Stored artifact size differs from metadata")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                while chunk := handle.read(_HASH_CHUNK_BYTES):
                    digest.update(chunk)
                    total_size += len(chunk)
        finally:
            os.close(descriptor)

        try:
            after = target.lstat()
        except FileNotFoundError as exc:
            raise ArtifactIntegrityError("Stored artifact changed while it was read") from exc
        if (
            _is_reparse_stat(after)
            or not os.path.samestat(opened, after)
            or opened.st_size != total_size
        ):
            raise ArtifactIntegrityError("Stored artifact changed while it was read")
        return _stored_artifact_from_digest(
            run_id,
            relative_path,
            content_sha256=digest.hexdigest(),
            size_bytes=total_size,
        )

    def read_verified(self, artifact: StoredArtifact) -> bytes:
        """Read exactly the path named by metadata and verify every recorded field."""

        validate_stored_artifact(artifact)
        target = self.artifact_path(artifact.run_id, artifact.relative_path)
        content, inspected = self._read_target(
            artifact.run_id,
            artifact.relative_path,
            target,
            expected_size=artifact.size_bytes,
        )
        if inspected != artifact:
            raise ArtifactIntegrityError("Stored bytes differ from expected metadata")
        with self._records_lock:
            self._records[artifact.storage_id] = artifact
        return content

    def read_bounded_unverified(
        self,
        run_id: str,
        relative_path: str,
        *,
        maximum_size: int,
    ) -> bytes:
        """Safely read a bounded candidate before later manifest verification.

        The returned bytes are protected against traversal, reparse points and
        time-of-check/time-of-use replacement, but are not evidence until the
        caller resolves them through ``verify_run`` or ``verify_prepared_run``.
        """

        if type(maximum_size) is not int or maximum_size <= 0:
            raise ValueError("maximum_size must be a positive integer")
        canonical_run_id = validate_run_id(run_id)
        canonical_path = validate_relative_path(relative_path)
        content, _ = self._read_target(
            canonical_run_id,
            canonical_path,
            self.artifact_path(canonical_run_id, canonical_path),
            maximum_size=maximum_size,
        )
        return content

    def _iter_run_files(self, run_id: str, run_path: Path) -> Iterator[tuple[str, Path]]:
        manifest = run_path / "run_manifest.json"
        if _path_exists_without_following(manifest):
            yield "run_manifest.json", manifest

        def walk(directory: Path, relative_parts: tuple[str, ...]) -> Iterator[tuple[str, Path]]:
            try:
                entries = tuple(os.scandir(directory))
            except (FileNotFoundError, NotADirectoryError, PermissionError):
                return
            for entry in entries:
                path = Path(entry.path)
                try:
                    entry_stat = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if _is_reparse_stat(entry_stat):
                    continue
                parts = (*relative_parts, entry.name)
                if stat.S_ISDIR(entry_stat.st_mode):
                    yield from walk(path, parts)
                elif stat.S_ISREG(entry_stat.st_mode):
                    if entry.name.startswith(_TEMP_PREFIX) and entry.name.endswith(
                        _TEMP_SUFFIX
                    ):
                        continue
                    relative_path = "/".join(parts)
                    try:
                        canonical = validate_relative_path(relative_path)
                    except (TypeError, ValueError):
                        continue
                    yield canonical, path

        for top_level in sorted(_RUN_TOP_LEVEL):
            directory = run_path / top_level
            if not _path_exists_without_following(directory):
                continue
            try:
                directory_stat = directory.lstat()
            except OSError:
                continue
            if _is_reparse_stat(directory_stat) or not stat.S_ISDIR(directory_stat.st_mode):
                continue
            yield from walk(directory, (top_level,))

    def _discover_run_files_exact(self, run_id: str) -> dict[str, Path]:
        """Enumerate an entire run tree and fail closed on every unknown entry."""

        run_path = self.run_path(run_id)
        try:
            run_stat = run_path.lstat()
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError("Run directory is missing") from exc
        if _is_reparse_stat(run_stat) or not stat.S_ISDIR(run_stat.st_mode):
            raise ArtifactIntegrityError("Run root is not a trusted directory")

        files: dict[str, Path] = {}
        directories: set[str] = set()

        def walk(directory: Path, relative_parts: tuple[str, ...]) -> None:
            try:
                entries = tuple(os.scandir(directory))
            except OSError as exc:
                raise ArtifactIntegrityError("Run tree cannot be enumerated") from exc
            for entry in entries:
                path = Path(entry.path)
                relative = "/".join((*relative_parts, entry.name))
                try:
                    entry_stat = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise ArtifactIntegrityError("Run tree entry cannot be inspected") from exc
                if _is_reparse_stat(entry_stat):
                    raise ArtifactIntegrityError(
                        "Run tree contains a symlink or reparse point"
                    )
                if stat.S_ISDIR(entry_stat.st_mode):
                    if relative not in _ALLOWED_RUN_TREE_DIRECTORIES:
                        raise ArtifactIntegrityError(
                            "Run tree contains an undeclared directory"
                        )
                    directories.add(relative)
                    walk(path, (*relative_parts, entry.name))
                    continue
                if not stat.S_ISREG(entry_stat.st_mode):
                    raise ArtifactIntegrityError("Run tree contains a non-regular entry")
                try:
                    canonical = validate_relative_path(relative)
                except (TypeError, ValueError) as exc:
                    raise ArtifactIntegrityError(
                        "Run tree contains a non-canonical artifact path"
                    ) from exc
                if canonical != relative:
                    raise ArtifactIntegrityError(
                        "Run tree artifact spelling differs from its canonical path"
                    )
                if canonical in files:
                    raise ArtifactIntegrityError("Run tree contains an aliased artifact path")
                files[canonical] = path

        walk(run_path, ())
        expected_directories = set(RUN_TREE_DIRECTORIES)
        for optional_directory in OPTIONAL_RUN_TREE_DIRECTORIES:
            prefix = f"{optional_directory}/"
            if any(path.startswith(prefix) for path in files):
                expected_directories.add(optional_directory)
        if directories != expected_directories:
            raise ArtifactIntegrityError("Run tree directory inventory is incomplete")
        return files

    def _restart_lookup(self, storage_id: str) -> bytes:
        matches: list[StoredArtifact] = []
        try:
            run_entries = tuple(os.scandir(self._root))
        except OSError as exc:
            raise ArtifactIntegrityError("Artifact store root cannot be scanned") from exc
        for entry in run_entries:
            try:
                validate_run_id(entry.name)
                entry_stat = entry.stat(follow_symlinks=False)
            except (OSError, TypeError, ValueError):
                continue
            if _is_reparse_stat(entry_stat) or not stat.S_ISDIR(entry_stat.st_mode):
                continue
            run_path = Path(entry.path)
            for relative_path, target in self._iter_run_files(entry.name, run_path):
                try:
                    artifact = self._inspect_target_streaming(
                        entry.name,
                        relative_path,
                        target,
                    )
                except ArtifactStoreError:
                    continue
                if artifact.storage_id == storage_id:
                    matches.append(artifact)
        if not matches:
            raise ArtifactNotFoundError(
                "Stored artifact is missing or its bytes no longer match the requested ID"
            )
        first_artifact = matches[0]
        if any(artifact != first_artifact for artifact in matches[1:]):
            raise ArtifactIntegrityError("Storage ID resolves to multiple artifact records")
        return self.read_verified(first_artifact)

    def read_bytes(self, storage_id: str) -> bytes:
        """Read by content identity, including after constructing a fresh store instance."""

        if type(storage_id) is not str or not _STORAGE_ID_PATTERN.fullmatch(storage_id):
            raise ValueError("storage_id is not a FileArtifactStore content identity")
        with self._records_lock:
            known = self._records.get(storage_id)
        if known is not None:
            return self.read_verified(known)
        return self._restart_lookup(storage_id)

    def _load_manifest_anchor(
        self,
        run_id: str,
        relative_path: str,
    ):
        from ..models.run import RunManifest

        manifest_bytes, _ = self._read_target(
            run_id,
            relative_path,
            self.artifact_path(run_id, relative_path),
            maximum_size=_MAX_MANIFEST_BYTES,
        )
        try:
            manifest = RunManifest.model_validate_json(manifest_bytes)
        except (UnicodeError, ValidationError, ValueError) as exc:
            raise ArtifactIntegrityError("Run manifest failed integrity validation") from exc
        if (
            manifest.schema_version != "rei-native-run-manifest-v2"
            or manifest.run_id != run_id
            or manifest.status != "completed"
        ):
            raise ArtifactIntegrityError("Run requires its matching completed V2 manifest")
        if manifest.canonical_json_bytes() != manifest_bytes:
            raise ArtifactIntegrityError("Run manifest is not canonical JSON")
        return manifest, manifest_bytes

    def _verify_manifest_inventory(
        self,
        manifest: Any,
        *,
        anchor_paths: set[str],
    ) -> None:
        for record in manifest.artifact_inventory:
            self.read_verified(StoredArtifact(**record.model_dump(mode="python")))
        discovered = set(self._discover_run_files_exact(manifest.run_id))
        expected = {
            *(item.relative_path for item in manifest.artifact_inventory),
            *anchor_paths,
        }
        if discovered != expected:
            raise ArtifactIntegrityError("Run tree differs from its durable inventory")

    def _verify_emocio_execution(self, manifest: Any) -> None:
        """Cold-replay configured Emocio lineage and every materialized byte."""

        execution = manifest.emocio_execution
        if execution is None:
            return

        from ..emocio.artifacts import inspect_png
        from ..emocio.prompting import BilingualStructuredScenePromptCompiler
        from ..emocio.renderer import (
            StructuredScenePromptCompiler,
            build_render_call_spec,
            redact_render_batch_diagnostics,
        )
        from ..emocio.runtime import (
            EmocioProcessingArtifact,
            EmocioProcessorRuntimeConfig,
            validate_processing_runtime_closure,
        )
        from ..emocio.vector_encoding import (
            normalized_float32_le_bytes,
            verified_float32_le_vector,
        )
        from ..models.emocio import (
            EmocioInputPacket,
            EmocioNativeConclusion,
            EmocioVisualState,
            EmocioWorld,
            ImageArtifact,
            VisualSceneSpec,
        )
        from ..models.rendering import ImageSourceReference
        from ..models.scene import SceneEvent
        from ..providers.deterministic import DeterministicEmocioNativeProvider
        from ..providers.protocols import (
            ImageEncodingRequest,
            build_image_encoding_call_spec,
        )

        def load_canonical_model(path: str, model_type: Any) -> Any:
            raw = self._inventory_bytes(manifest, path)
            value = model_type.model_validate_json(raw)
            if value.canonical_json_bytes() != raw:
                raise ValueError("Configured Emocio JSON is not canonical")
            return value

        try:
            config = load_canonical_model(
                execution.processor_config_path,
                EmocioProcessorRuntimeConfig,
            )
            artifact = load_canonical_model(
                execution.processing_artifact_path,
                EmocioProcessingArtifact,
            )
            scene = load_canonical_model("scene/event.json", SceneEvent)
            world = load_canonical_model("scene/emocio_world.json", EmocioWorld)
            if (
                config.config_id != execution.processor_config_id
                or config.content_hash() != execution.processor_config_hash
                or artifact.result_id != execution.processing_artifact_id
                or artifact.content_hash() != execution.processing_artifact_hash
            ):
                raise ValueError(
                    "Configured Emocio artifacts differ from manifest lineage"
                )

            result = artifact.to_result(scene, world)
            packet_view = load_canonical_model(
                "scene/emocio_packet.json",
                EmocioInputPacket,
            )
            visual_state_view = load_canonical_model(
                "emocio/visual_state.json",
                EmocioVisualState,
            )
            conclusion_view = load_canonical_model(
                "native/emocio.json",
                EmocioNativeConclusion,
            )
            if (
                packet_view != result.packet
                or visual_state_view != result.visual_state
                or conclusion_view != result.native_conclusion
            ):
                raise ValueError(
                    "Durable Emocio views differ from processing replay"
                )

            replayed_scenes = {
                item.scene_id: item
                for item in (
                    result.visual_state.current_scene,
                    result.visual_state.desired_scene,
                    result.visual_state.broken_scene,
                    *result.visual_state.option_rollouts,
                )
            }
            expected_scene_paths = {
                f"emocio/scenes/{scene_id}.json"
                for scene_id in replayed_scenes
            }
            recorded_scene_paths = {
                item.relative_path
                for item in manifest.artifact_inventory
                if item.relative_path.startswith("emocio/scenes/")
            }
            if recorded_scene_paths != expected_scene_paths:
                raise ValueError(
                    "Durable Emocio scene paths differ from processing replay"
                )
            for scene_id, replayed_scene in replayed_scenes.items():
                scene_view = load_canonical_model(
                    f"emocio/scenes/{scene_id}.json",
                    VisualSceneSpec,
                )
                if scene_view != replayed_scene:
                    raise ValueError(
                        "Durable Emocio scene differs from processing replay"
                    )

            images_raw = self._inventory_bytes(
                manifest,
                "emocio/images/index.json",
            )
            images_view = TypeAdapter(tuple[ImageArtifact, ...]).validate_json(
                images_raw
            )
            if (
                canonical_json_bytes(images_view) != images_raw
                or images_view != result.rendered_images
            ):
                raise ValueError(
                    "Durable Emocio image index differs from processing replay"
                )
            if manifest.safety_flags not in {
                (),
                ("synthetic_execution_clock",),
            }:
                raise ValueError("Configured Emocio safety flags are not canonical")
            synthetic_warning = (
                "Deterministic logical execution clock; timestamps are synthetic."
                if manifest.safety_flags == ("synthetic_execution_clock",)
                else None
            )
            expected_manifest_warnings = tuple(
                dict.fromkeys(
                    item
                    for item in (
                        result.renderer_warning,
                        result.visual_warning,
                        synthetic_warning,
                    )
                    if item is not None
                )
            )
            if manifest.warnings != expected_manifest_warnings:
                raise ValueError(
                    "Configured Emocio manifest warnings differ from replay"
                )
            (
                nested_specs,
                nested_records,
                renderer_call_ids,
                encoder_call_ids,
            ) = validate_processing_runtime_closure(config, result)
            if (
                renderer_call_ids != execution.renderer_call_ids
                or encoder_call_ids != execution.encoder_call_ids
            ):
                raise ValueError(
                    "Cold-replayed Emocio provider calls differ from manifest"
                )
            manifest_specs = {
                item.call_id: item for item in manifest.provider_call_specs
            }
            manifest_records = {
                item.call_id: item for item in manifest.provider_calls
            }
            outer_spec = manifest_specs.get(execution.outer_call_id)
            outer_record = manifest_records.get(execution.outer_call_id)
            expected_outer_spec = (
                DeterministicEmocioNativeProvider().configured_call_spec(
                    scene,
                    world,
                    result.packet,
                    runtime_config=config,
                )
            )
            if (
                outer_spec is None
                or outer_record is None
                or outer_spec != expected_outer_spec
                or outer_record.output_artifact_ids
                != (
                    result.native_conclusion.conclusion_id,
                    artifact.result_id,
                )
                or outer_record.status != "succeeded"
                or outer_record.primary_status != "succeeded"
                or outer_record.fallback is not None
                or outer_record.warnings
            ):
                raise ValueError(
                    "Configured Emocio outer call differs from cold replay"
                )
            for spec, record in zip(
                nested_specs,
                nested_records,
                strict=True,
            ):
                if (
                    manifest_specs.get(spec.call_id) != spec
                    or manifest_records.get(record.call_id) != record
                ):
                    raise ValueError(
                        "Emocio processing artifact differs from provider ledger"
                    )

            renderer_binding = config.renderer_binding
            renderer_specs = tuple(
                spec
                for spec in nested_specs
                if spec.provider.kind == "image_renderer"
            )
            if renderer_binding is None:
                if renderer_specs or result.render_batch is not None:
                    raise ValueError(
                        "Unconfigured Emocio renderer appears in processing replay"
                    )
            else:
                if any(
                    spec.provider != renderer_binding.provider_identity
                    for spec in renderer_specs
                ):
                    raise ValueError(
                        "Nested renderer identity differs from runtime binding"
                    )
                if result.render_batch is not None:
                    if (
                        redact_render_batch_diagnostics(result.render_batch)
                        != result.render_batch
                    ):
                        raise ValueError(
                            "Render diagnostics differ from their canonical redaction"
                        )
                    settings = renderer_binding.render_settings
                    rollout = renderer_binding.rollout_config
                    scene_by_id = {
                        item.scene_id: item
                        for item in (
                            result.visual_state.current_scene,
                            result.visual_state.desired_scene,
                            result.visual_state.broken_scene,
                            *result.visual_state.option_rollouts,
                        )
                    }
                    current_images = tuple(
                        image
                        for image in result.rendered_images
                        if image.source_spec_id
                        == result.visual_state.current_scene.scene_id
                    )
                    for item in result.render_batch.items:
                        request = item.request
                        source_scene = scene_by_id.get(request.source_spec_id)
                        scene_kind = (
                            None if source_scene is None else source_scene.scene_kind
                        )
                        expected_mode = (
                            "image_to_image"
                            if scene_kind == "option_rollout"
                            else "text_to_image"
                        )
                        expected_pipeline = (
                            renderer_binding.text_to_image_pipeline
                            if expected_mode == "text_to_image"
                            else renderer_binding.image_to_image_pipeline
                        )
                        if (
                            scene_kind is None
                            or request.mode != expected_mode
                            or request.provider
                            != renderer_binding.provider_identity
                            or request.pipeline != expected_pipeline
                            or request.width != settings.width
                            or request.height != settings.height
                            or request.num_inference_steps
                            != settings.num_inference_steps
                            or request.guidance_scale != settings.guidance_scale
                            or request.negative_prompt != settings.negative_prompt
                            or item.call_spec
                            != build_render_call_spec(
                                request,
                                timeout_seconds=settings.timeout_seconds,
                            )
                            or item.call_record.fallback is not None
                        ):
                            raise ValueError(
                                "Render request differs from its runtime binding"
                            )
                        if request.mode == "image_to_image":
                            if len(current_images) != 1:
                                raise ValueError(
                                    "Rollout requires one exact current image"
                                )
                            expected_source = (
                                ImageSourceReference.from_artifact_with_scene_lineage(
                                    current_images[0]
                                )
                            )
                            if (
                                request.source_image != expected_source
                                or request.conditioning_method
                                != rollout.conditioning_method
                                or request.strength != rollout.classic_strength
                            ):
                                raise ValueError(
                                    "Rollout request differs from runtime binding"
                                )
                        compiler = renderer_binding.prompt_compiler_binding
                        profile = compiler.prompt_profile
                        if profile is None:
                            prompt_compiler = StructuredScenePromptCompiler()
                            prompt_provenance_matches = (
                                request.prompt_language is None
                                and request.style_id is None
                                and request.profile_hash is None
                            )
                        else:
                            prompt_compiler = (
                                BilingualStructuredScenePromptCompiler(profile)
                            )
                            prompt_provenance_matches = (
                                request.prompt_language == profile.language
                                and request.style_id == profile.style_id
                                and request.profile_hash == profile.content_hash()
                            )
                        if (
                            source_scene is None
                            or not prompt_provenance_matches
                            or request.prompt
                            != prompt_compiler.compile(source_scene)
                        ):
                            raise ValueError(
                                "Render prompt profile differs from runtime binding"
                            )

            encoder_specs = tuple(
                spec
                for spec in nested_specs
                if spec.provider.kind == "image_encoder"
            )
            if config.encoder_identity is None:
                if encoder_specs or result.visual_observations:
                    raise ValueError(
                        "Unconfigured Emocio encoder appears in processing replay"
                    )
            else:
                if any(
                    spec.provider != config.encoder_identity
                    for spec in encoder_specs
                ):
                    raise ValueError(
                        "Nested encoder identity differs from runtime config"
                    )
                if any(
                    observation.encoding.request.provider
                    != config.encoder_identity
                    or observation.encoding.request.spec != config.encoder_spec
                    or observation.encoding.call_spec
                    != build_image_encoding_call_spec(
                        observation.encoding.request,
                        timeout_seconds=config.encoding_timeout_seconds,
                    )
                    or observation.encoding.call.fallback is not None
                    or bool(observation.encoding.call.warnings)
                    for observation in result.visual_observations
                ):
                    raise ValueError(
                        "Visual encoding spec differs from runtime config"
                    )
                failure = result.visual_failure
                if failure is not None and failure.stage == "encoding":
                    failed_spec = failure.attempted_call_spec
                    if failed_spec is not None:
                        referenced_images = tuple(
                            image
                            for image in result.rendered_images
                            if image.image_id in failed_spec.input_artifact_ids
                        )
                        if len(referenced_images) != 1:
                            raise ValueError(
                                "Failed encoding must cite one rendered image"
                            )
                        expected_request = ImageEncodingRequest.create(
                            image=referenced_images[0],
                            provider=config.encoder_identity,
                            spec=config.encoder_spec,
                        )
                        if (
                            failed_spec
                            != build_image_encoding_call_spec(
                                expected_request,
                                timeout_seconds=config.encoding_timeout_seconds,
                            )
                        ):
                            raise ValueError(
                                "Failed encoding call differs from runtime config"
                            )

            expected_materialized: dict[str, tuple[str, str, str, object]] = {}
            for image in result.rendered_images:
                expected_materialized[image.image_id] = (
                    "image",
                    image.path,
                    image.content_sha256,
                    image,
                )
            for observation in result.visual_observations:
                encoding = observation.encoding
                expected_materialized[encoding.encoding_id] = (
                    "vector",
                    encoding.vector_ref,
                    encoding.vector_hash,
                    encoding,
                )
            expected_image_paths = {
                "emocio/images/index.json",
                *(
                    path
                    for role, path, _digest, _source in expected_materialized.values()
                    if role == "image"
                ),
            }
            expected_embedding_paths = {
                path
                for role, path, _digest, _source in expected_materialized.values()
                if role == "vector"
            }
            recorded_image_paths = {
                item.relative_path
                for item in manifest.artifact_inventory
                if item.relative_path.startswith("emocio/images/")
            }
            recorded_embedding_paths = {
                item.relative_path
                for item in manifest.artifact_inventory
                if item.relative_path.startswith("emocio/embeddings/")
            }
            if (
                recorded_image_paths != expected_image_paths
                or recorded_embedding_paths != expected_embedding_paths
            ):
                raise ValueError(
                    "Materialized Emocio namespaces differ from processing replay"
                )
            recorded_ids = {
                item.artifact_id for item in execution.materialized_artifacts
            }
            visual_observation_by_encoding_id = {
                observation.encoding.encoding_id: observation
                for observation in result.visual_observations
            }
            if recorded_ids != set(expected_materialized):
                raise ValueError(
                    "Materialized Emocio lineage differs from processing replay"
                )
            for item in execution.materialized_artifacts:
                role, path, digest, source = expected_materialized[item.artifact_id]
                if (
                    item.role != role
                    or item.relative_path != path
                    or item.content_sha256 != digest
                ):
                    raise ValueError(
                        "Materialized Emocio metadata differs from processing replay"
                    )
                raw = self._inventory_bytes(manifest, item.relative_path)
                if len(raw) != item.size_bytes:
                    raise ValueError(
                        "Materialized Emocio byte size differs from its record"
                    )
                if item.role == "image":
                    if (
                        hashlib.sha256(raw).hexdigest() != digest
                        or inspect_png(raw) != (source.width, source.height)
                    ):
                        raise ValueError(
                            "Materialized Emocio PNG bytes differ from replay"
                        )
                else:
                    _, vector_hash = verified_float32_le_vector(
                        raw,
                        expected_dimensions=source.dimensions,
                    )
                    observation = visual_observation_by_encoding_id[
                        item.artifact_id
                    ]
                    if (
                        vector_hash != source.vector_hash
                        or raw
                        != normalized_float32_le_bytes(
                            observation.vector,
                            expected_dimensions=source.dimensions,
                        )
                    ):
                        raise ValueError(
                            "Materialized Emocio vector differs from replay"
                        )
        except ArtifactIntegrityError:
            raise
        except (AttributeError, TypeError, UnicodeError, ValidationError, ValueError) as exc:
            raise ArtifactIntegrityError(
                "Configured Emocio execution failed cold replay"
            ) from exc

    def verify_prepared_run(self, run_id: str):
        """Cold-verify a fully prepared run whose EgoTrace commit is not assumed."""

        canonical_run_id = validate_run_id(run_id)
        prepared_path = "diagnostics/prepared_manifest.json"
        manifest, _ = self._load_manifest_anchor(canonical_run_id, prepared_path)
        self._verify_manifest_inventory(
            manifest,
            anchor_paths={prepared_path},
        )
        self._verify_emocio_execution(manifest)
        return manifest

    def verify_run(self, run_id: str):
        """Cold-discover and verify a completed V2 run from its fixed manifest anchor."""

        canonical_run_id = validate_run_id(run_id)
        manifest, manifest_bytes = self._load_manifest_anchor(
            canonical_run_id,
            "run_manifest.json",
        )
        prepared_path = "diagnostics/prepared_manifest.json"
        prepared_bytes, _ = self._read_target(
            canonical_run_id,
            prepared_path,
            self.artifact_path(canonical_run_id, prepared_path),
            maximum_size=_MAX_MANIFEST_BYTES,
        )
        if prepared_bytes != manifest_bytes:
            raise ArtifactIntegrityError("Prepared and committed manifests differ")
        self._verify_manifest_inventory(
            manifest,
            anchor_paths={prepared_path, "run_manifest.json"},
        )
        self._verify_emocio_execution(manifest)
        return manifest

    def _inventory_bytes(self, manifest: Any, relative_path: str) -> bytes:
        matches = tuple(
            item
            for item in manifest.artifact_inventory
            if item.relative_path == relative_path
        )
        if len(matches) != 1:
            raise ArtifactIntegrityError(
                f"Prepared run inventory is missing {relative_path!r}"
            )
        return self.read_verified(
            StoredArtifact(**matches[0].model_dump(mode="python"))
        )

    def recover_prepared_run(
        self,
        run_id: str,
        *,
        request_hash: str,
        ego_id: str,
        trace: Any,
    ):
        """Promote an exact trace-committed prepared run after a cold restart.

        Returns the completed manifest when a final manifest already exists or
        when recovery safely creates it. A merely prepared run whose measure is
        not the current trace tail is left untouched and returns ``None``.
        """

        from ..models.ego import EgoMeasure, EgoTrace

        canonical_run_id = validate_run_id(run_id)
        run_path = self.run_path(canonical_run_id)
        if not _path_exists_without_following(run_path):
            return None
        final_path = run_path / "run_manifest.json"
        if _path_exists_without_following(final_path):
            return self.verify_run(canonical_run_id)
        prepared_path = run_path / "diagnostics" / "prepared_manifest.json"
        if not _path_exists_without_following(prepared_path):
            return None

        manifest = self.verify_prepared_run(canonical_run_id)
        reservation_bytes = self._inventory_bytes(
            manifest, "diagnostics/run_reservation.json"
        )
        try:
            reservation = json.loads(reservation_bytes)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ArtifactIntegrityError("Run reservation is not valid JSON") from exc
        if canonical_json_bytes(reservation) != reservation_bytes:
            raise ArtifactIntegrityError("Run reservation is not canonical JSON")
        if (
            set(reservation)
            != {
                "schema_version",
                "run_id",
                "ego_id",
                "request_hash",
                "expected_trace_hash",
                "created_at",
            }
            or reservation.get("schema_version")
            != "rei-native-run-reservation-v1"
            or reservation.get("run_id") != canonical_run_id
        ):
            raise ArtifactIntegrityError("Run reservation contract is invalid")
        if (
            reservation.get("request_hash") != request_hash
            or reservation.get("ego_id") != ego_id
        ):
            raise ArtifactExistsError("Run ID is reserved by a different cycle request")

        try:
            measure = EgoMeasure.model_validate_json(
                self._inventory_bytes(manifest, "ego/measure.json")
            )
            prepared_trace = EgoTrace.model_validate_json(
                self._inventory_bytes(manifest, "ego/trace.json")
            )
        except (UnicodeError, ValidationError, ValueError) as exc:
            raise ArtifactIntegrityError("Prepared Ego artifacts are invalid") from exc
        if (
            not prepared_trace.event_order
            or prepared_trace.event_order[-1].event_kind != "measure"
            or prepared_trace.event_order[-1].event_id != measure.measure_id
        ):
            raise ArtifactIntegrityError("Prepared trace does not end with its run measure")
        predecessor = EgoTrace.create(
            ego_id=prepared_trace.ego_id,
            measures=prepared_trace.measures[:-1],
            corrections=prepared_trace.corrections,
            event_order=prepared_trace.event_order[:-1],
        )
        if reservation.get("expected_trace_hash") != predecessor.trace_hash:
            raise ArtifactIntegrityError(
                "Run reservation predecessor differs from the prepared trace"
            )
        if (
            prepared_trace.ego_id != ego_id
            or trace.ego_id != ego_id
            or not prepared_trace.measures
            or prepared_trace.measures[-1] != measure
            or trace.measures[: len(prepared_trace.measures)]
            != prepared_trace.measures
            or trace.corrections[: len(prepared_trace.corrections)]
            != prepared_trace.corrections
            or trace.event_order[: len(prepared_trace.event_order)]
            != prepared_trace.event_order
        ):
            return None

        _, manifest_bytes = self._load_manifest_anchor(
            canonical_run_id,
            "diagnostics/prepared_manifest.json",
        )
        try:
            self.write_bytes(canonical_run_id, "run_manifest.json", manifest_bytes)
        except ArtifactExistsError:
            pass
        return self.verify_run(canonical_run_id)


__all__ = [
    "ArtifactExistsError",
    "ArtifactIntegrityError",
    "ArtifactNotFoundError",
    "ArtifactStore",
    "ArtifactStoreError",
    "DEFAULT_RUNS_ROOT",
    "FileArtifactStore",
    "OPTIONAL_RUN_TREE_DIRECTORIES",
    "RUN_TREE_DIRECTORIES",
    "StoredArtifact",
    "stored_artifact_id",
    "validate_relative_path",
    "validate_run_id",
    "validate_stored_artifact",
]
