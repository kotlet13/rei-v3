"""Run one create-only stage of TRIAD-ISO-E3."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.research.triad_iso_e3 import (  # noqa: E402
    cold_verify,
    finalize,
    initialize_execution,
    run_next,
    seal_e3,
    verify_seal,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "seal",
            "verify-seal",
            "initialize",
            "run-next",
            "finalize",
            "verify",
        ),
    )
    args = parser.parse_args()
    if args.command == "seal":
        result = seal_e3(REPOSITORY_ROOT)
    elif args.command == "verify-seal":
        result = verify_seal(REPOSITORY_ROOT)[0]
    elif args.command == "initialize":
        result = initialize_execution(REPOSITORY_ROOT)
    elif args.command == "run-next":
        result = run_next(REPOSITORY_ROOT)
    elif args.command == "finalize":
        result = finalize(REPOSITORY_ROOT)
    else:
        result = cold_verify(REPOSITORY_ROOT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
