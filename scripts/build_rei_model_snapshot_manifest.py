"""Build a canonical byte inventory for one pre-populated local model snapshot.

The command never downloads model files.  It inventories an existing directory,
excludes Hugging Face's transient ``.cache`` metadata, and atomically writes the
manifest consumed by REI's fail-closed local model adapters.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.emocio.diffusers_renderer import (  # noqa: E402
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersSnapshotFile,
    DiffusersSnapshotManifest,
    canonical_snapshot_manifest_bytes,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _is_forbidden_link(path: Path) -> bool:
    metadata = os.lstat(path)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        reparse_attribute and file_attributes & reparse_attribute
    )


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def build_manifest(
    *,
    snapshot_directory: Path,
    repo_id: str,
    revision: str,
    output: Path | None = None,
) -> tuple[DiffusersSnapshotManifest, Path]:
    snapshot_root = snapshot_directory.expanduser().resolve(strict=True)
    if not snapshot_root.is_dir():
        raise ValueError("snapshot_directory must be a directory")
    target = (
        snapshot_root / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
        if output is None
        else output.expanduser().resolve()
    )
    if target.parent != snapshot_root:
        raise ValueError("The snapshot manifest must be written at the snapshot root")

    entries: list[DiffusersSnapshotFile] = []
    candidate_paths = sorted(
        snapshot_root.rglob("*"),
        key=lambda path: path.relative_to(snapshot_root).as_posix(),
    )
    for path in candidate_paths:
        relative_path = path.relative_to(snapshot_root)
        if _is_forbidden_link(path):
            raise ValueError(
                "Snapshot inventory forbids symbolic links and reparse points: "
                f"{relative_path}"
            )
        try:
            resolved_path = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError(
                f"Snapshot inventory entry is unreadable: {relative_path}"
            ) from exc
        if not resolved_path.is_relative_to(snapshot_root):
            raise ValueError(
                f"Snapshot inventory entry resolves outside its root: {relative_path}"
            )
        if relative_path.parts[0] == ".cache":
            continue
        if path == target:
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(
                f"Snapshot inventory contains an unsupported entry: {relative_path}"
            )
        entries.append(
            DiffusersSnapshotFile(
                relative_path=relative_path.as_posix(),
                sha256=_sha256(path),
                size_bytes=path.stat().st_size,
            )
        )
    manifest = DiffusersSnapshotManifest(
        repo_id=repo_id,
        revision=revision,
        files=tuple(entries),
    )
    _write_atomic(target, canonical_snapshot_manifest_bytes(manifest))
    return manifest, target


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-directory", type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Optional explicit output path; it must still resolve to "
            f"<snapshot>/{DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME}."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest, target = build_manifest(
        snapshot_directory=args.snapshot_directory,
        repo_id=args.repo_id,
        revision=args.revision,
        output=args.output,
    )
    manifest_bytes = canonical_snapshot_manifest_bytes(manifest)
    print(f"manifest_path={target}")
    print(f"manifest_sha256={hashlib.sha256(manifest_bytes).hexdigest()}")
    print(f"file_count={len(manifest.files)}")
    print(f"size_bytes={sum(item.size_bytes for item in manifest.files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
