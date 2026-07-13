"""Strict append-only in-memory and atomic file Ego trace stores."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import BinaryIO, Iterator

from pydantic import ValidationError

from ..ids import content_id, sha256_hex
from ..models.common import HashDigest, NonEmptyId
from ..models.ego import EgoCorrectionEvent, EgoMeasure, EgoTrace
from ..models.provider import ProviderIdentity


class EgoTraceStoreError(RuntimeError):
    """Base class for trace persistence failures."""


class EgoTraceConflictError(EgoTraceStoreError):
    """The caller attempted a duplicate or stale append."""


class EgoTraceTamperError(EgoTraceStoreError):
    """Persisted bytes no longer validate as the expected immutable trace."""


def _provider_identity(
    *,
    implementation: str,
    discriminator: str,
) -> ProviderIdentity:
    base = {
        "kind": "ego_trace_store",
        "implementation": implementation,
        "implementation_revision": "b4-v1",
        "discriminator": discriminator,
    }
    return ProviderIdentity(
        provider_id=content_id("provider", base),
        kind="ego_trace_store",
        implementation=implementation,
        implementation_revision="b4-v1",
    )


def _check_expected_hash(trace: EgoTrace, expected: HashDigest | None) -> None:
    if expected is not None and trace.trace_hash != expected:
        raise EgoTraceConflictError(
            "EgoTrace changed after the caller read it; append must be retried"
        )


def _append_measure(trace: EgoTrace, measure: EgoMeasure) -> EgoTrace:
    if any(item.measure_id == measure.measure_id for item in trace.measures):
        raise EgoTraceConflictError("EgoMeasure is already present in the append-only trace")
    return trace.append_measure(measure)


def _append_correction(
    trace: EgoTrace,
    correction: EgoCorrectionEvent,
) -> EgoTrace:
    if correction.ego_id != trace.ego_id:
        raise EgoTraceConflictError("Correction belongs to another Ego trace")
    if any(item.correction_id == correction.correction_id for item in trace.corrections):
        raise EgoTraceConflictError(
            "Ego correction is already present in the append-only trace"
        )
    try:
        return trace.append_correction(correction)
    except ValueError as exc:
        raise EgoTraceConflictError(str(exc)) from exc


class InMemoryEgoTraceStore:
    """Thread-safe process-local store with optimistic conflict detection."""

    def __init__(self) -> None:
        self._identity = _provider_identity(
            implementation="rei_next.ego.InMemoryEgoTraceStore",
            discriminator="process-local",
        )
        self._traces: dict[str, EgoTrace] = {}
        self._lock = RLock()

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def load_trace(self, ego_id: NonEmptyId) -> EgoTrace:
        with self._lock:
            return self._traces.get(ego_id, EgoTrace.create(ego_id=ego_id))

    def append_measure(
        self,
        ego_id: NonEmptyId,
        measure: EgoMeasure,
        *,
        expected_trace_hash: HashDigest | None = None,
    ) -> None:
        with self._lock:
            trace = self._traces.get(ego_id, EgoTrace.create(ego_id=ego_id))
            _check_expected_hash(trace, expected_trace_hash)
            self._traces[ego_id] = _append_measure(trace, measure)

    def append_correction(
        self,
        ego_id: NonEmptyId,
        correction: EgoCorrectionEvent,
        *,
        expected_trace_hash: HashDigest | None = None,
    ) -> None:
        with self._lock:
            trace = self._traces.get(ego_id, EgoTrace.create(ego_id=ego_id))
            _check_expected_hash(trace, expected_trace_hash)
            self._traces[ego_id] = _append_correction(trace, correction)


_LOCKS_GUARD = Lock()
_PATH_LOCKS: dict[Path, RLock] = {}


def _thread_lock_for(path: Path) -> RLock:
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(path, RLock())


@contextmanager
def _platform_file_lock(lock_path: Path) -> Iterator[None]:
    """Hold a one-byte advisory lock across processes on Windows and POSIX."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
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


class FileEgoTraceStore:
    """Restart-safe JSON store with locked read-modify-write and atomic replace."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        root_path = Path(root).expanduser().resolve()
        if root_path.exists() and not root_path.is_dir():
            raise ValueError("Ego trace store root must be a directory")
        root_path.mkdir(parents=True, exist_ok=True)
        self._root = root_path
        self._identity = _provider_identity(
            implementation="rei_next.ego.FileEgoTraceStore",
            discriminator=str(root_path),
        )

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def trace_path(self, ego_id: NonEmptyId) -> Path:
        digest = sha256_hex(ego_id)
        return self._root / f"ego-{digest}.trace.json"

    def _lock_path(self, ego_id: NonEmptyId) -> Path:
        return self.trace_path(ego_id).with_suffix(".lock")

    def _load_unlocked(self, ego_id: NonEmptyId) -> EgoTrace:
        path = self.trace_path(ego_id)
        if not path.exists():
            return EgoTrace.create(ego_id=ego_id)
        try:
            with path.open("rb") as handle:
                raw = handle.read()
            trace = EgoTrace.model_validate_json(raw)
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise EgoTraceTamperError(
                f"Stored EgoTrace for {ego_id!r} failed integrity validation"
            ) from exc
        if trace.ego_id != ego_id:
            raise EgoTraceTamperError("Stored EgoTrace identity differs from its lookup key")
        return trace

    def _write_unlocked(self, trace: EgoTrace) -> None:
        destination = self.trace_path(trace.ego_id)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=self._root,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                _write_and_sync(handle, trace.canonical_json_bytes())
            os.replace(temporary, destination)
            _sync_directory(self._root)
        finally:
            temporary.unlink(missing_ok=True)

    @contextmanager
    def _locked(self, ego_id: NonEmptyId) -> Iterator[None]:
        path_lock = _thread_lock_for(self.trace_path(ego_id))
        with path_lock, _platform_file_lock(self._lock_path(ego_id)):
            yield

    def load_trace(self, ego_id: NonEmptyId) -> EgoTrace:
        with self._locked(ego_id):
            return self._load_unlocked(ego_id)

    def append_measure(
        self,
        ego_id: NonEmptyId,
        measure: EgoMeasure,
        *,
        expected_trace_hash: HashDigest | None = None,
    ) -> None:
        with self._locked(ego_id):
            trace = self._load_unlocked(ego_id)
            _check_expected_hash(trace, expected_trace_hash)
            self._write_unlocked(_append_measure(trace, measure))

    def append_correction(
        self,
        ego_id: NonEmptyId,
        correction: EgoCorrectionEvent,
        *,
        expected_trace_hash: HashDigest | None = None,
    ) -> None:
        with self._locked(ego_id):
            trace = self._load_unlocked(ego_id)
            _check_expected_hash(trace, expected_trace_hash)
            self._write_unlocked(_append_correction(trace, correction))


def _write_and_sync(handle: BinaryIO, content: bytes) -> None:
    handle.write(content)
    handle.flush()
    os.fsync(handle.fileno())


def _sync_directory(directory: Path) -> None:
    """Persist the rename metadata where directory fsync is supported."""

    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "EgoTraceConflictError",
    "EgoTraceStoreError",
    "EgoTraceTamperError",
    "FileEgoTraceStore",
    "InMemoryEgoTraceStore",
]
