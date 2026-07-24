"""Prepare or cold-verify TRIAD-ISO-R2 model-free research artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.research.triad_iso_r2 import (  # noqa: E402
    cold_verify_r2,
    prepare_r2,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "verify"))
    args = parser.parse_args()
    result = (
        prepare_r2(REPOSITORY_ROOT)
        if args.command == "prepare"
        else cold_verify_r2(REPOSITORY_ROOT)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
