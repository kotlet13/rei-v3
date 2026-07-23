"""Seal, execute, or cold-verify the bounded TRIAD-S2 development screen."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.research.triad_s2 import (  # noqa: E402
    cold_verify_s2,
    execute_s2,
    model_free_projection,
    seal_s2,
    verify_seal,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TRIAD-S2 distinguishable native-route development screen."
    )
    parser.add_argument(
        "command",
        choices=("seal", "verify-seal", "execute", "verify-evidence"),
    )
    args = parser.parse_args()
    if args.command == "seal":
        result = seal_s2(REPOSITORY_ROOT)
    elif args.command == "verify-seal":
        seal, prepared = verify_seal(REPOSITORY_ROOT)
        result = {
            "status": "verified",
            "pre_call_seal_sha256": seal["seal_sha256"],
            "case_count": len(prepared),
            "model_calls": 0,
        }
    elif args.command == "execute":
        result = execute_s2(REPOSITORY_ROOT)
    else:
        result = cold_verify_s2(REPOSITORY_ROOT)
    print(
        json.dumps(
            model_free_projection(result),
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
