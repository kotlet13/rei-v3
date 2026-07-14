"""Mandatory-CAS, cold-replayed persistence for Instinkt outcome learning."""

from __future__ import annotations

import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import BinaryIO, Callable, Iterator

from pydantic import ValidationError

from ..ids import sha256_hex
from ..models.common import HashDigest, NonEmptyId
from .outcome_learning import InstinktOutcomeLearningTrace, InstinktOutcomeUpdate


class InstinktOutcomeStoreError(RuntimeError):
    """Base class for outcome-learning persistence failures."""


class InstinktOutcomeStoreConflictError(InstinktOutcomeStoreError):
    """The append is stale, duplicated, or forks the learning chain."""


class InstinktOutcomeStoreTamperError(InstinktOutcomeStoreError):
    """Persisted trace bytes or cold source lineage failed validation."""


class InstinktOutcomeStoreVerificationRequiredError(InstinktOutcomeStoreError):
    """A non-empty trace cannot be loaded without a cold replay verifier."""


OutcomeUpdateVerifier = Callable[[InstinktOutcomeUpdate], None]

_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_MAX_TRACE_BYTES = 64 * 1024 * 1024
_LOCKS_GUARD = Lock()
_PATH_LOCKS: dict[Path, RLock] = {}


def _is_reparse_stat(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_reparse_ancestry(path: Path) -> None:
    absolute = _absolute_without_resolving(path)
    parts = absolute.parts
    if not parts:
        raise ValueError("Instinkt outcome store root must be absolute")
    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse_stat(current_stat):
            raise ValueError(
                "Instinkt outcome store ancestry cannot contain a reparse point"
            )


def _assert_safe_path(root: Path, path: Path, *, leaf_may_be_file: bool) -> None:
    if not path.is_relative_to(root):
        raise InstinktOutcomeStoreTamperError("Outcome store path escapes its root")
    current = root
    parts = path.relative_to(root).parts
    for index, part in enumerate(parts):
        current /= part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse_stat(current_stat):
            raise InstinktOutcomeStoreTamperError(
                "Outcome store path traverses a symlink or reparse point"
            )
        is_leaf = index == len(parts) - 1
        if (not is_leaf or not leaf_may_be_file) and not stat.S_ISDIR(
            current_stat.st_mode
        ):
            raise InstinktOutcomeStoreTamperError(
                "Outcome store path parent is not a directory"
            )
    if not path.resolve(strict=False).is_relative_to(root):
        raise InstinktOutcomeStoreTamperError(
            "Outcome store path resolves outside its configured root"
        )


def _thread_lock_for(path: Path) -> RLock:
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(path, RLock())


@contextmanager
def _safe_lock_file(root: Path, lock_path: Path) -> Iterator[BinaryIO]:
    _assert_safe_path(root, lock_path, leaf_may_be_file=True)
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise InstinktOutcomeStoreTamperError(
            "Outcome lock file could not be opened safely"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise InstinktOutcomeStoreTamperError(
                "Outcome lock target is not a regular file"
            )
        try:
            current = lock_path.lstat()
        except FileNotFoundError as exc:
            raise InstinktOutcomeStoreTamperError(
                "Outcome lock path changed during open"
            ) from exc
        if _is_reparse_stat(current) or not os.path.samestat(opened, current):
            raise InstinktOutcomeStoreTamperError(
                "Outcome lock path changed during open"
            )
        handle = os.fdopen(descriptor, "r+b", closefd=False)
        if opened.st_size == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(descriptor)
        handle.seek(0)
        try:
            yield handle
        finally:
            handle.close()
    finally:
        os.close(descriptor)


@contextmanager
def _platform_file_lock(root: Path, lock_path: Path) -> Iterator[None]:
    with _safe_lock_file(root, lock_path) as handle:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_and_sync(handle: BinaryIO, content: bytes) -> None:
    handle.write(content)
    handle.flush()
    os.fsync(handle.fileno())


def _sync_directory(directory: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _safe_read(root: Path, path: Path) -> bytes:
    _assert_safe_path(root, path, leaf_may_be_file=True)
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise InstinktOutcomeStoreTamperError("Outcome trace disappeared") from exc
    if _is_reparse_stat(before) or not stat.S_ISREG(before.st_mode):
        raise InstinktOutcomeStoreTamperError("Outcome trace is not a regular file")
    if before.st_size > _MAX_TRACE_BYTES:
        raise InstinktOutcomeStoreTamperError("Outcome trace exceeds safe read limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InstinktOutcomeStoreTamperError(
            "Outcome trace could not be opened safely"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(before, opened):
            raise InstinktOutcomeStoreTamperError(
                "Outcome trace changed before read"
            )
        if opened.st_size > _MAX_TRACE_BYTES:
            raise InstinktOutcomeStoreTamperError("Outcome trace exceeds safe read limit")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read(_MAX_TRACE_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(raw) > _MAX_TRACE_BYTES:
        raise InstinktOutcomeStoreTamperError("Outcome trace exceeds safe read limit")
    try:
        after = path.lstat()
    except FileNotFoundError as exc:
        raise InstinktOutcomeStoreTamperError(
            "Outcome trace changed during read"
        ) from exc
    if (
        _is_reparse_stat(after)
        or not os.path.samestat(opened, after)
        or opened.st_size != len(raw)
    ):
        raise InstinktOutcomeStoreTamperError("Outcome trace changed during read")
    return raw


class FileInstinktOutcomeLearningStore:
    """Locked read-modify-write store with mandatory cold replay and CAS."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        root_path = _absolute_without_resolving(Path(root).expanduser())
        _assert_no_reparse_ancestry(root_path)
        root_path.mkdir(parents=True, exist_ok=True)
        _assert_no_reparse_ancestry(root_path)
        root_stat = root_path.lstat()
        if _is_reparse_stat(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
            raise ValueError("Instinkt outcome store root must be a regular directory")
        self._root = root_path

    @property
    def root(self) -> Path:
        return self._root

    def trace_path(self, ego_id: NonEmptyId) -> Path:
        return self._root / f"ego-{sha256_hex(ego_id)}.instinkt-learning.json"

    def _lock_path(self, ego_id: NonEmptyId) -> Path:
        return self.trace_path(ego_id).with_suffix(".lock")

    @contextmanager
    def _locked(self, ego_id: NonEmptyId) -> Iterator[None]:
        trace_path = self.trace_path(ego_id)
        with _thread_lock_for(trace_path), _platform_file_lock(
            self._root, self._lock_path(ego_id)
        ):
            yield

    @staticmethod
    def _verify_updates(
        trace: InstinktOutcomeLearningTrace,
        verifier: OutcomeUpdateVerifier | None,
    ) -> None:
        if not trace.updates:
            return
        if verifier is None:
            raise InstinktOutcomeStoreVerificationRequiredError(
                "Non-empty outcome trace requires cold deterministic verifier"
            )
        try:
            for update in trace.updates:
                verifier(update)
        except InstinktOutcomeStoreError:
            raise
        except Exception as exc:
            raise InstinktOutcomeStoreTamperError(
                "Stored outcome update failed cold deterministic replay"
            ) from exc

    def _load_unlocked(
        self,
        ego_id: NonEmptyId,
        *,
        verifier: OutcomeUpdateVerifier | None,
    ) -> InstinktOutcomeLearningTrace:
        path = self.trace_path(ego_id)
        _assert_safe_path(self._root, path, leaf_may_be_file=True)
        try:
            path.lstat()
        except FileNotFoundError:
            return InstinktOutcomeLearningTrace.empty(ego_id=ego_id)
        try:
            raw = _safe_read(self._root, path)
            trace = InstinktOutcomeLearningTrace.model_validate_json(raw)
        except InstinktOutcomeStoreError:
            raise
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise InstinktOutcomeStoreTamperError(
                f"Stored Instinkt outcome trace for {ego_id!r} failed validation"
            ) from exc
        if trace.ego_id != ego_id:
            raise InstinktOutcomeStoreTamperError(
                "Stored Instinkt outcome trace identity differs from lookup key"
            )
        if trace.canonical_json_bytes() != raw:
            raise InstinktOutcomeStoreTamperError(
                "Stored Instinkt outcome trace is not canonical JSON"
            )
        self._verify_updates(trace, verifier)
        return trace

    def _write_unlocked(self, trace: InstinktOutcomeLearningTrace) -> None:
        destination = self.trace_path(trace.ego_id)
        _assert_safe_path(self._root, destination, leaf_may_be_file=True)
        content = trace.canonical_json_bytes()
        if len(content) > _MAX_TRACE_BYTES:
            raise InstinktOutcomeStoreError("Outcome trace exceeds safe write limit")
        try:
            existing = destination.lstat()
        except FileNotFoundError:
            existing = None
        if existing is not None and (
            _is_reparse_stat(existing) or not stat.S_ISREG(existing.st_mode)
        ):
            raise InstinktOutcomeStoreTamperError(
                "Outcome trace destination is not a regular file"
            )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=self._root,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                _write_and_sync(handle, content)
            temporary_stat = temporary.lstat()
            if _is_reparse_stat(temporary_stat) or not stat.S_ISREG(
                temporary_stat.st_mode
            ):
                raise InstinktOutcomeStoreTamperError(
                    "Outcome trace temporary is not a regular file"
                )
            _assert_safe_path(self._root, destination, leaf_may_be_file=True)
            os.replace(temporary, destination)
            final = destination.lstat()
            if _is_reparse_stat(final) or not stat.S_ISREG(final.st_mode):
                raise InstinktOutcomeStoreTamperError(
                    "Persisted outcome trace is not a regular file"
                )
            _sync_directory(self._root)
        finally:
            temporary.unlink(missing_ok=True)

    def load_trace(
        self,
        ego_id: NonEmptyId,
        *,
        verifier: OutcomeUpdateVerifier | None = None,
    ) -> InstinktOutcomeLearningTrace:
        with self._locked(ego_id):
            return self._load_unlocked(ego_id, verifier=verifier)

    def append_update(
        self,
        ego_id: NonEmptyId,
        update: InstinktOutcomeUpdate,
        *,
        expected_trace_hash: HashDigest,
        verifier: OutcomeUpdateVerifier,
    ) -> InstinktOutcomeLearningTrace:
        """CAS-append exactly one update; exact update retries are idempotent."""

        with self._locked(ego_id):
            trace = self._load_unlocked(ego_id, verifier=verifier)
            existing = next(
                (item for item in trace.updates if item.update_id == update.update_id),
                None,
            )
            if existing is not None:
                if existing != update:
                    raise InstinktOutcomeStoreConflictError(
                        "Outcome update ID collides with different content"
                    )
                return trace
            if trace.trace_hash != expected_trace_hash:
                raise InstinktOutcomeStoreConflictError(
                    "Instinkt outcome trace changed after it was read"
                )
            try:
                verifier(update)
                candidate = trace.append(update)
            except InstinktOutcomeStoreError:
                raise
            except ValueError as exc:
                raise InstinktOutcomeStoreConflictError(str(exc)) from exc
            except Exception as exc:
                raise InstinktOutcomeStoreTamperError(
                    "Outcome update failed cold deterministic replay"
                ) from exc
            self._write_unlocked(candidate)
            persisted = self._load_unlocked(ego_id, verifier=verifier)
            if persisted != candidate:
                raise InstinktOutcomeStoreTamperError(
                    "Persisted outcome trace differs from locked CAS candidate"
                )
            return persisted


__all__ = [
    "FileInstinktOutcomeLearningStore",
    "InstinktOutcomeStoreConflictError",
    "InstinktOutcomeStoreError",
    "InstinktOutcomeStoreTamperError",
    "InstinktOutcomeStoreVerificationRequiredError",
    "OutcomeUpdateVerifier",
]
