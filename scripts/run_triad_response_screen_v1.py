from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.backend.rei.triad_screen import (  # noqa: E402
    cold_verify_screen,
    execute_screen,
    prepare_pre_call_screen,
    verify_pre_call_screen,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded TRIAD-S1 native response development screen."
    )
    parser.add_argument(
        "command",
        choices=("seal", "verify-pre-call", "execute", "verify-evidence"),
    )
    args = parser.parse_args()
    if args.command == "seal":
        result = prepare_pre_call_screen(REPOSITORY_ROOT)
    elif args.command == "verify-pre-call":
        prepared = verify_pre_call_screen(REPOSITORY_ROOT)
        result = {"verified_cases": len(prepared)}
    elif args.command == "execute":
        result = execute_screen(REPOSITORY_ROOT)
    else:
        result = cold_verify_screen(REPOSITORY_ROOT)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
