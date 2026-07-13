"""Run the B11 12 x 13 matrix over checked-in frozen native bundles.

This runner evaluates only character governance and the downstream B10 path.
It never invokes a native processor, model provider, renderer, LLM, or GPU.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei_next.profile_matrix import run_native_profile_matrix  # noqa: E402


DEFAULT_FIXTURE_DIRECTORY = ROOT / "tests" / "fixtures" / "native_bundles"


def _write_atomic(path: Path, payload: bytes) -> None:
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-directory",
        type=Path,
        default=DEFAULT_FIXTURE_DIRECTORY,
        help="Directory containing the 12 checked-in frozen native bundles.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write canonical JSON atomically to this path (default: stdout).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    matrix = run_native_profile_matrix(args.fixture_directory)
    payload = matrix.canonical_json_bytes()
    if args.output is None:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    else:
        _write_atomic(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
