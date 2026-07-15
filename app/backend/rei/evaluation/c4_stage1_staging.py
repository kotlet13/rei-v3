"""Fail-closed parent verification for one C4 Stage 1 child staging root.

The child process may only leave one canonical worker result and, on success,
two unpublished PNG files.  A staging root is captured while it is fresh and
empty, then verified through stable same-handle reads and two exact inventory
passes.  Local paths never enter the portable result returned to callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import stat

from ..emocio.c4_stage1_editor import (
    C4_STAGE1_MAX_PNG_BYTES,
    C4Stage1WorkerRequest,
    C4Stage1WorkerResult,
    inspect_c4_stage1_png_bytes,
)


C4_STAGE1_WORKER_RESULT_FILENAME = "worker_result.json"
C4_STAGE1_DIRECT_FILENAME = "direct.png"
C4_STAGE1_STAGED_FILENAME = "staged.png"

_MAX_WORKER_RESULT_BYTES = 4 * 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_SUCCESS_INVENTORY = frozenset(
    {
        C4_STAGE1_WORKER_RESULT_FILENAME,
        C4_STAGE1_DIRECT_FILENAME,
        C4_STAGE1_STAGED_FILENAME,
    }
)
_FAILURE_INVENTORY = frozenset({C4_STAGE1_WORKER_RESULT_FILENAME})


@dataclass(frozen=True, slots=True)
class _RootIdentity:
    mode_type: int
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    mode_type: int
    device: int
    inode: int
    size: int
    mtime_ns: int
    ctime_ns: int
    link_count: int


@dataclass(frozen=True, slots=True)
class C4Stage1PreparedStagingRoot:
    """Runtime-only proof that a particular staging directory began empty."""

    _root: Path = field(repr=False)
    _root_identity: _RootIdentity = field(repr=False)


@dataclass(frozen=True, slots=True)
class C4Stage1VerifiedStaging:
    """Portable child result plus runtime-only unpublished output bytes."""

    worker_result: C4Stage1WorkerResult
    direct_png: bytes | None = field(default=None, repr=False)
    staged_png: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.worker_result.status == "failed":
            if self.direct_png is not None or self.staged_png is not None:
                raise ValueError("Failed Stage 1 staging cannot expose PNG bytes")
            return
        if type(self.direct_png) is not bytes or type(self.staged_png) is not bytes:
            raise ValueError("Successful Stage 1 staging requires immutable PNG bytes")
        evidence = self.worker_result.image_evidence
        if evidence is None:
            raise ValueError("Successful Stage 1 staging requires image evidence")
        _validate_png_evidence(
            self.direct_png,
            expected_sha256=evidence.direct_png_sha256,
            expected_size=evidence.direct_png_size_bytes,
            expected_dimensions=(evidence.direct_width, evidence.direct_height),
            label="direct",
        )
        _validate_png_evidence(
            self.staged_png,
            expected_sha256=evidence.staged_png_sha256,
            expected_size=evidence.staged_png_size_bytes,
            expected_dimensions=(evidence.staged_width, evidence.staged_height),
            label="staged",
        )


def _is_reparse_or_link(metadata: os.stat_result) -> bool:
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _root_identity(metadata: os.stat_result) -> _RootIdentity:
    return _RootIdentity(
        mode_type=stat.S_IFMT(metadata.st_mode),
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )


def _file_identity(metadata: os.stat_result) -> _FileIdentity:
    return _FileIdentity(
        mode_type=stat.S_IFMT(metadata.st_mode),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        size=metadata.st_size,
        mtime_ns=getattr(metadata, "st_mtime_ns", int(metadata.st_mtime * 1e9)),
        ctime_ns=getattr(metadata, "st_ctime_ns", int(metadata.st_ctime * 1e9)),
        link_count=metadata.st_nlink,
    )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_unlinked_ancestry(path: Path) -> None:
    parts = path.parts
    if not parts:
        raise ValueError("C4 Stage 1 staging root must be absolute")
    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise ValueError("C4 Stage 1 staging ancestry is unavailable") from exc
        if _is_reparse_or_link(metadata):
            raise ValueError(
                "C4 Stage 1 staging ancestry forbids links and reparse points"
            )


def _inspect_root(path: Path) -> _RootIdentity:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise ValueError("C4 Stage 1 staging root is unavailable") from exc
    if _is_reparse_or_link(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(
            "C4 Stage 1 staging root must be an ordinary non-reparse directory"
        )
    return _root_identity(metadata)


def _inventory(root: Path) -> dict[str, _FileIdentity]:
    try:
        entries = sorted(os.scandir(root), key=lambda entry: entry.name)
    except OSError as exc:
        raise ValueError("C4 Stage 1 staging root cannot be inventoried") from exc
    result: dict[str, _FileIdentity] = {}
    for entry in entries:
        try:
            metadata = os.lstat(entry.path)
        except OSError as exc:
            raise ValueError("C4 Stage 1 staging entry is unreadable") from exc
        if _is_reparse_or_link(metadata):
            raise ValueError("C4 Stage 1 staging forbids links and reparse points")
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("C4 Stage 1 staging permits regular files only")
        result[entry.name] = _file_identity(metadata)
    return result


def prepare_c4_stage1_staging_root(
    staging_root: str | Path,
) -> C4Stage1PreparedStagingRoot:
    """Capture an absolute, empty staging directory before a child is launched."""

    root = Path(staging_root)
    if not root.is_absolute() or root != _absolute_lexical(root):
        raise ValueError("C4 Stage 1 staging root must be an absolute lexical path")
    _assert_unlinked_ancestry(root)
    identity = _inspect_root(root)
    if _inventory(root):
        raise ValueError("C4 Stage 1 staging root must be fresh and empty")
    if _inspect_root(root) != identity or _inventory(root):
        raise ValueError("C4 Stage 1 staging root changed while being prepared")
    return C4Stage1PreparedStagingRoot(
        _root=root,
        _root_identity=identity,
    )


def _read_stable_regular(
    path: Path,
    *,
    inventory_identity: _FileIdentity,
    maximum_bytes: int,
) -> bytes:
    if inventory_identity.size > maximum_bytes:
        raise ValueError("C4 Stage 1 staged file exceeds its byte limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("C4 Stage 1 staged file cannot be opened safely") from exc
    payload = bytearray()
    try:
        opened = os.fstat(descriptor)
        if (
            _is_reparse_or_link(opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or _file_identity(opened) != inventory_identity
        ):
            raise ValueError("C4 Stage 1 staged file changed while opening")
        while True:
            remaining = maximum_bytes + 1 - len(payload)
            chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > maximum_bytes:
                raise ValueError("C4 Stage 1 staged file exceeds its byte limit")
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        final_path = os.lstat(path)
    except OSError as exc:
        raise ValueError("C4 Stage 1 staged file changed while reading") from exc
    if (
        _is_reparse_or_link(final_path)
        or not stat.S_ISREG(final_path.st_mode)
        or final_path.st_nlink != 1
        or _file_identity(final_handle) != inventory_identity
        or _file_identity(final_path) != inventory_identity
        or len(payload) != inventory_identity.size
    ):
        raise ValueError("C4 Stage 1 staged file changed while reading")
    return bytes(payload)


def _validate_png_evidence(
    payload: bytes,
    *,
    expected_sha256: str,
    expected_size: int,
    expected_dimensions: tuple[int, int],
    label: str,
) -> None:
    dimensions = inspect_c4_stage1_png_bytes(payload)
    if (
        hashlib.sha256(payload).hexdigest() != expected_sha256
        or len(payload) != expected_size
        or dimensions != expected_dimensions
    ):
        raise ValueError(f"C4 Stage 1 {label} PNG differs from exact evidence")


def _validate_distinct_files(inventory: dict[str, _FileIdentity]) -> None:
    if any(item.link_count != 1 for item in inventory.values()):
        raise ValueError("C4 Stage 1 staging forbids hard-linked files")
    identities = [(item.device, item.inode) for item in inventory.values()]
    if len(identities) != len(set(identities)):
        raise ValueError("C4 Stage 1 staged files must have distinct identities")


def _assert_direct_staged_are_distinct(root: Path) -> None:
    try:
        direct = os.lstat(root / C4_STAGE1_DIRECT_FILENAME)
        staged = os.lstat(root / C4_STAGE1_STAGED_FILENAME)
    except OSError as exc:
        raise ValueError("C4 Stage 1 staged PNG identity is unavailable") from exc
    if os.path.samestat(direct, staged):
        raise ValueError("C4 Stage 1 direct and staged PNGs cannot be hard links")


def verify_c4_stage1_staging(
    prepared: C4Stage1PreparedStagingRoot,
    parent_request: C4Stage1WorkerRequest,
) -> C4Stage1VerifiedStaging:
    """Verify exact child output without publishing or returning local paths."""

    if not isinstance(prepared, C4Stage1PreparedStagingRoot):
        raise TypeError("prepared must be a C4Stage1PreparedStagingRoot")
    if not isinstance(parent_request, C4Stage1WorkerRequest):
        raise TypeError("parent_request must be a C4Stage1WorkerRequest")
    root = prepared._root
    _assert_unlinked_ancestry(root)
    if _inspect_root(root) != prepared._root_identity:
        raise ValueError("C4 Stage 1 staging root differs from its prepared identity")

    initial = _inventory(root)
    names = frozenset(initial)
    if names not in {_SUCCESS_INVENTORY, _FAILURE_INVENTORY}:
        raise ValueError("C4 Stage 1 staging inventory is not exact")

    result_bytes = _read_stable_regular(
        root / C4_STAGE1_WORKER_RESULT_FILENAME,
        inventory_identity=initial[C4_STAGE1_WORKER_RESULT_FILENAME],
        maximum_bytes=_MAX_WORKER_RESULT_BYTES,
    )
    try:
        result = C4Stage1WorkerResult.model_validate_json(result_bytes)
    except Exception as exc:
        raise ValueError("C4 Stage 1 worker result is invalid") from exc
    if result.canonical_json_bytes() != result_bytes:
        raise ValueError("C4 Stage 1 worker result is not canonical JSON")
    result.validate_against(parent_request)

    expected_names = (
        _SUCCESS_INVENTORY if result.status == "succeeded" else _FAILURE_INVENTORY
    )
    if names != expected_names:
        raise ValueError("C4 Stage 1 staging inventory differs from worker status")

    direct_png: bytes | None = None
    staged_png: bytes | None = None
    if result.status == "succeeded":
        _assert_direct_staged_are_distinct(root)
        _validate_distinct_files(initial)
        direct_png = _read_stable_regular(
            root / C4_STAGE1_DIRECT_FILENAME,
            inventory_identity=initial[C4_STAGE1_DIRECT_FILENAME],
            maximum_bytes=C4_STAGE1_MAX_PNG_BYTES,
        )
        staged_png = _read_stable_regular(
            root / C4_STAGE1_STAGED_FILENAME,
            inventory_identity=initial[C4_STAGE1_STAGED_FILENAME],
            maximum_bytes=C4_STAGE1_MAX_PNG_BYTES,
        )
        evidence = result.image_evidence
        if evidence is None:
            raise ValueError("Successful Stage 1 result has no image evidence")
        _validate_png_evidence(
            direct_png,
            expected_sha256=evidence.direct_png_sha256,
            expected_size=evidence.direct_png_size_bytes,
            expected_dimensions=(evidence.direct_width, evidence.direct_height),
            label="direct",
        )
        _validate_png_evidence(
            staged_png,
            expected_sha256=evidence.staged_png_sha256,
            expected_size=evidence.staged_png_size_bytes,
            expected_dimensions=(evidence.staged_width, evidence.staged_height),
            label="staged",
        )
    else:
        _validate_distinct_files(initial)

    final = _inventory(root)
    if final != initial:
        raise ValueError("C4 Stage 1 staging inventory changed during verification")
    if _inspect_root(root) != prepared._root_identity:
        raise ValueError("C4 Stage 1 staging root changed during verification")
    return C4Stage1VerifiedStaging(
        worker_result=result,
        direct_png=direct_png,
        staged_png=staged_png,
    )


__all__ = [
    "C4_STAGE1_DIRECT_FILENAME",
    "C4_STAGE1_STAGED_FILENAME",
    "C4_STAGE1_WORKER_RESULT_FILENAME",
    "C4Stage1PreparedStagingRoot",
    "C4Stage1VerifiedStaging",
    "prepare_c4_stage1_staging_root",
    "verify_c4_stage1_staging",
]
