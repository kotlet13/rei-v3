"""Prepare or cold-verify TRIAD-ISO-R1 without model calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.research.triad_iso_r1 import (  # noqa: E402
    cold_verify_r1,
    formal_verify_e1,
    prepare_r1,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify-e1", "verify"))
    args = parser.parse_args()
    handler = {
        "prepare": prepare_r1,
        "verify-e1": formal_verify_e1,
        "verify": cold_verify_r1,
    }[args.command]
    result = handler(REPOSITORY_ROOT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
