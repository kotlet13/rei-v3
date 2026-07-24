"""Run one create-only stage of TRIAD-ISO-E1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.research.triad_iso_e1 import (
    cold_verify,
    finalize,
    initialize_execution,
    run_next,
    seal_e1,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("seal", "initialize", "run-next", "finalize", "verify"),
    )
    args = parser.parse_args()
    handlers = {
        "seal": seal_e1,
        "initialize": initialize_execution,
        "run-next": run_next,
        "finalize": finalize,
        "verify": cold_verify,
    }
    result = handlers[args.command](REPOSITORY_ROOT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
