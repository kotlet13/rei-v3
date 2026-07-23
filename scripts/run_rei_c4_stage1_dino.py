"""Guarded production CLI for the two C4 Stage 1 DINO collapse checks.

Direct invocation is inert.  ``--execute`` requires the exact final render
inventory anchor, two atomic member-publication identities, and a distinct
fresh DINO run ID.  The command is offline and never grants authority.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.evaluation.c4_stage1_dino_run import (  # noqa: E402
    run_c4_stage1_dino_collapse_check,
)
from rei.persistence.artifacts import FileArtifactStore  # noqa: E402
from rei.providers.protocols import StoredArtifact  # noqa: E402


def _absolute(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute() or path != Path(os.path.abspath(os.fspath(path))):
        raise argparse.ArgumentTypeError("C4 Stage 1 DINO paths must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--render-artifact-root", type=_absolute)
    parser.add_argument("--render-run-id")
    parser.add_argument("--dino-artifact-root", type=_absolute)
    parser.add_argument("--dino-run-id")
    parser.add_argument("--repository-root", type=_absolute)
    parser.add_argument("--worker-python", type=_absolute)
    parser.add_argument("--snapshot", type=_absolute)
    parser.add_argument("--staging-parent", type=_absolute)
    parser.add_argument("--render-inventory-anchor-storage-id")
    parser.add_argument("--confirmed-prepared-attempt-id")
    parser.add_argument("--confirmed-dino-policy-id")
    parser.add_argument("--primary-member-publication-storage-id")
    parser.add_argument("--alternate-member-publication-storage-id")
    return parser


def _required(arguments: argparse.Namespace, name: str) -> object:
    value = getattr(arguments, name)
    if value is None or type(value) is str and not value:
        raise ValueError(f"Missing required C4 Stage 1 DINO argument: {name}")
    return value


def _descriptor(
    inventory: tuple[StoredArtifact, ...],
    storage_id: object,
    *,
    run_id: str,
) -> StoredArtifact:
    if type(storage_id) is not str:
        raise TypeError("Stage 1 DINO storage identity must be a string")
    matches = tuple(
        item
        for item in inventory
        if item.storage_id == storage_id and item.run_id == run_id
    )
    if len(matches) != 1:
        raise ValueError("Stage 1 DINO storage identity is absent or ambiguous")
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
    render_artifact_root = _required(arguments, "render_artifact_root")
    render_run_id = _required(arguments, "render_run_id")
    dino_artifact_root = _required(arguments, "dino_artifact_root")
    dino_run_id = _required(arguments, "dino_run_id")
    repository_root = _required(arguments, "repository_root")
    worker_python = _required(arguments, "worker_python")
    snapshot = _required(arguments, "snapshot")
    staging_parent = _required(arguments, "staging_parent")
    render_anchor_storage_id = _required(
        arguments,
        "render_inventory_anchor_storage_id",
    )
    confirmed_attempt = _required(arguments, "confirmed_prepared_attempt_id")
    confirmed_policy = _required(arguments, "confirmed_dino_policy_id")
    primary_storage_id = _required(
        arguments,
        "primary_member_publication_storage_id",
    )
    alternate_storage_id = _required(
        arguments,
        "alternate_member_publication_storage_id",
    )
    if (
        not isinstance(render_artifact_root, Path)
        or type(render_run_id) is not str
        or not isinstance(dino_artifact_root, Path)
        or type(dino_run_id) is not str
        or not isinstance(repository_root, Path)
        or not isinstance(worker_python, Path)
        or not isinstance(snapshot, Path)
        or not isinstance(staging_parent, Path)
        or type(confirmed_attempt) is not str
        or type(confirmed_policy) is not str
    ):
        raise TypeError("Stage 1 DINO CLI arguments have invalid types")
    if repository_root.resolve(strict=True) != ROOT:
        raise ValueError("Stage 1 DINO repository root is not this script checkout")

    render_store = FileArtifactStore(render_artifact_root, create=False)
    dino_store = FileArtifactStore(dino_artifact_root, create=True)
    inventory = render_store.inspect_run_inventory_exact(render_run_id)
    render_anchor_storage = _descriptor(
        inventory,
        render_anchor_storage_id,
        run_id=render_run_id,
    )
    primary_storage = _descriptor(
        inventory,
        primary_storage_id,
        run_id=render_run_id,
    )
    alternate_storage = _descriptor(
        inventory,
        alternate_storage_id,
        run_id=render_run_id,
    )
    outcome = run_c4_stage1_dino_collapse_check(
        render_store,
        dino_store,
        render_anchor_storage,
        (primary_storage, alternate_storage),
        dino_run_id=dino_run_id,
        confirmed_prepared_attempt_id=confirmed_attempt,
        confirmed_dino_policy_id=confirmed_policy,
        repository_root=repository_root,
        worker_python=worker_python,
        snapshot_path=snapshot,
        staging_parent=staging_parent,
    )
    _emit(
        {
            "action": "c4_stage1_dino_collapse_check_completed",
            "render_run_id": outcome.anchor.render_run_id,
            "dino_run_id": outcome.anchor.dino_run_id,
            "prepared_attempt_id": outcome.anchor.prepared_attempt_id,
            "dino_collapse_check_id": outcome.anchor.dino_collapse_check_id,
            "anchor_storage_id": outcome.anchor_storage.storage_id,
            "family_comparison_count": outcome.anchor.family_comparison_count,
            "encoded_image_count": outcome.anchor.encoded_image_count,
            "all_dino_gates_passed": outcome.anchor.all_dino_gates_passed,
            "any_action_collapse_detected": (
                outcome.anchor.any_action_collapse_detected
            ),
            "human_review_substitute": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
    )
    return 0 if outcome.anchor.all_dino_gates_passed else 20


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if not arguments.execute:
        return 64
    try:
        return _execute(arguments)
    except Exception as exc:
        sys.stderr.write(f"C4 Stage 1 DINO stopped: {type(exc).__name__}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
