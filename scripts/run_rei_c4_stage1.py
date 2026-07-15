"""Guarded operator CLI for the bounded C4 Stage 1 render screen.

The default action is model-free preparation.  Execution is impossible unless
the operator supplies ``--execute`` and repeats the exact prepared-attempt ID
and prepared-anchor storage ID emitted by a prior preparation command.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.evaluation.c4_stage1_attempt import (  # noqa: E402
    C4Stage1ReviewCommitments,
    C4Stage1RuntimePaths,
    prepare_c4_stage1_attempt,
)
from rei.evaluation.c4_stage1_run import run_c4_stage1_attempt  # noqa: E402
from rei.evaluation.resource_telemetry import (  # noqa: E402
    ResourceTelemetryCudaDeviceIdentity,
)
from rei.persistence.artifacts import FileArtifactStore  # noqa: E402


_MAX_COMMITMENTS_BYTES = 64 * 1024
_WINDOWS_REPARSE_ATTRIBUTE = 0x0400


def _is_link_or_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _assert_unlinked_ancestry(path: Path) -> None:
    for ancestor in reversed(path.parents):
        try:
            metadata = os.lstat(ancestor)
        except OSError as exc:
            raise ValueError("Stage 1 commitment ancestry is unavailable") from exc
        if _is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("Stage 1 commitment ancestry contains a link or reparse")


def _stable_read(path: Path, *, maximum_bytes: int) -> bytes:
    if not path.is_absolute():
        raise ValueError("Stage 1 commitment path must be absolute")
    _assert_unlinked_ancestry(path)
    before = os.lstat(path)
    if (
        _is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or not 0 < before.st_size <= maximum_bytes
    ):
        raise ValueError("Stage 1 commitment file is not one bounded ordinary file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or not os.path.samestat(before, opened)
        ):
            raise ValueError("Stage 1 commitment file changed while opening")
        value = bytearray()
        while True:
            chunk = os.read(
                descriptor, min(1024 * 1024, maximum_bytes + 1 - len(value))
            )
            if not chunk:
                break
            value.extend(chunk)
            if len(value) > maximum_bytes:
                raise ValueError("Stage 1 commitment file exceeds its byte limit")
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = os.lstat(path)
    if (
        _is_link_or_reparse(after)
        or after.st_nlink != 1
        or not os.path.samestat(opened, final_handle)
        or not os.path.samestat(opened, after)
        or opened.st_size != len(value)
    ):
        raise ValueError("Stage 1 commitment file changed while reading")
    return bytes(value)


def _absolute(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("Stage 1 paths must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--artifact-root", type=_absolute, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repository-root", type=_absolute, default=ROOT)
    parser.add_argument("--worker-python", type=_absolute, required=True)
    parser.add_argument("--source-png", type=_absolute, required=True)
    parser.add_argument("--source-provenance", type=_absolute, required=True)
    parser.add_argument("--primary-snapshot", type=_absolute, required=True)
    parser.add_argument("--alternate-snapshot", type=_absolute, required=True)
    parser.add_argument("--staging-parent", type=_absolute, required=True)
    parser.add_argument("--review-commitments", type=_absolute)
    parser.add_argument("--cuda-uuid")
    parser.add_argument("--cuda-pci-bus-id")
    parser.add_argument("--prepared-attempt-id")
    parser.add_argument("--prepared-anchor-storage-id")
    return parser


def _runtime_paths(arguments: argparse.Namespace) -> C4Stage1RuntimePaths:
    return C4Stage1RuntimePaths(
        repository_root=arguments.repository_root,
        worker_python=arguments.worker_python,
        source_png=arguments.source_png,
        source_provenance=arguments.source_provenance,
        primary_snapshot=arguments.primary_snapshot,
        alternate_snapshot=arguments.alternate_snapshot,
        staging_parent=arguments.staging_parent,
    )


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


def _prepare(arguments: argparse.Namespace) -> int:
    if (
        arguments.review_commitments is None
        or arguments.cuda_uuid is None
        or arguments.cuda_pci_bus_id is None
        or arguments.prepared_attempt_id is not None
        or arguments.prepared_anchor_storage_id is not None
    ):
        raise ValueError(
            "Preparation requires review commitments and exact CUDA identity, "
            "and forbids execution confirmations"
        )
    payload = _stable_read(
        arguments.review_commitments,
        maximum_bytes=_MAX_COMMITMENTS_BYTES,
    )
    commitments = C4Stage1ReviewCommitments.model_validate_json(payload)
    if commitments.canonical_json_bytes() != payload:
        raise ValueError("Stage 1 review commitments must be canonical JSON")
    cuda = ResourceTelemetryCudaDeviceIdentity.resolved(
        logical_device_index=0,
        physical_gpu_uuid=arguments.cuda_uuid,
        pci_bus_id=arguments.cuda_pci_bus_id,
    )
    store = FileArtifactStore(arguments.artifact_root)
    outcome = prepare_c4_stage1_attempt(
        run_id=arguments.run_id,
        paths=_runtime_paths(arguments),
        review_commitments=commitments,
        cuda_device=cuda,
        artifact_store=store,
    )
    _emit(
        {
            "action": "prepared",
            "run_id": outcome.prepared_attempt.run_id,
            "prepared_attempt_id": outcome.prepared_attempt.prepared_attempt_id,
            "prepared_anchor_storage_id": outcome.prepared_anchor_storage.storage_id,
            "model_calls": 0,
            "execute_requires_exact_confirmation": True,
        }
    )
    return 0


def _execute(arguments: argparse.Namespace) -> int:
    if (
        not arguments.prepared_attempt_id
        or not arguments.prepared_anchor_storage_id
        or arguments.review_commitments is not None
        or arguments.cuda_uuid is not None
        or arguments.cuda_pci_bus_id is not None
    ):
        raise ValueError(
            "Execution requires both exact prepared IDs and forbids preparation inputs"
        )
    store = FileArtifactStore(arguments.artifact_root, create=False)
    inventory = store.inspect_run_inventory_exact(arguments.run_id)
    matches = tuple(
        item
        for item in inventory
        if item.storage_id == arguments.prepared_anchor_storage_id
    )
    if len(matches) != 1:
        raise ValueError("Prepared anchor storage ID is absent or ambiguous")
    outcome = run_c4_stage1_attempt(
        artifact_store=store,
        prepared_anchor_storage=matches[0],
        confirmed_prepared_attempt_id=arguments.prepared_attempt_id,
        paths=_runtime_paths(arguments),
    )
    _emit(
        {
            "action": "executed",
            "run_id": outcome.manifest.run_id,
            "prepared_attempt_id": outcome.manifest.prepared_attempt_id,
            "render_attempt_manifest_id": outcome.manifest.render_attempt_manifest_id,
            "render_inventory_anchor_id": outcome.inventory_anchor.render_inventory_anchor_id,
            "status": outcome.manifest.status,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
    )
    return 0 if outcome.manifest.status == "evidence_ready" else 20


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        return _execute(arguments) if arguments.execute else _prepare(arguments)
    except Exception as exc:
        sys.stderr.write(f"C4 Stage 1 stopped: {type(exc).__name__}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
