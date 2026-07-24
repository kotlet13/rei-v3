"""Seal, execute, or cold-verify TRIAD-VIS-O2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.research.triad_vis_o2 import (  # noqa: E402
    cold_verify,
    execute,
    seal,
    verify_seal,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("seal", "verify-seal", "execute", "verify"),
    )
    parser.add_argument("--snapshot-directory", type=Path, required=True)
    parser.add_argument("--runtime-artifact-root", type=Path)
    args = parser.parse_args()
    if args.command == "seal":
        result = seal(
            REPOSITORY_ROOT,
            snapshot_directory=args.snapshot_directory,
        )
    elif args.command == "verify-seal":
        result = verify_seal(
            REPOSITORY_ROOT,
            snapshot_directory=args.snapshot_directory,
        )
    elif args.command == "execute":
        if args.runtime_artifact_root is None:
            parser.error("--runtime-artifact-root is required for execute")
        result = execute(
            REPOSITORY_ROOT,
            snapshot_directory=args.snapshot_directory,
            runtime_artifact_root=args.runtime_artifact_root,
        )
    else:
        result = cold_verify(
            REPOSITORY_ROOT,
            snapshot_directory=args.snapshot_directory,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
