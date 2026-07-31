"""Render and evaluate the isolated model-free Emocio VWM exploration bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp"
sys.path.insert(0, str(RESEARCH_ROOT / "python"))

from emocio_vwm_mvp import evaluate_exploration_bundle  # noqa: E402


def _resolve_output(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    allowed = (REPO_ROOT / "output" / "emocio_vwm_mvp").resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"output must remain within {allowed}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="output/emocio_vwm_mvp/exploration",
        help="bundle output below output/emocio_vwm_mvp",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace the exact resolved bundle directory after safety checks",
    )
    args = parser.parse_args()
    output = _resolve_output(args.output)
    if output.exists():
        if not args.replace:
            raise SystemExit(f"output exists; pass --replace: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    relative_output = output.relative_to(REPO_ROOT)
    completed = subprocess.run(
        [
            "node",
            str(RESEARCH_ROOT / "tools" / "render_preview.mjs"),
            relative_output.as_posix(),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    spec_target = output / "specs"
    shutil.copytree(RESEARCH_ROOT / "specs", spec_target)
    result = evaluate_exploration_bundle(
        bundle_dir=output,
        research_root=RESEARCH_ROOT,
    )
    print(json.dumps(result["verdict"], indent=2))
    return 0 if result["verdict"]["verdict"] != "medium_failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
