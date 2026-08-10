"""Build two independent E1R trees, compare them, and close the bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e1r"
sys.path.insert(0, str(RESEARCH_ROOT / "python"))

from emocio_vwm_mvp_e1r.evaluation import (  # noqa: E402
    artifact_tree,
    evaluate_run,
    finalize_bundle,
    read_json,
    write_json,
)


def _resolve_output(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    allowed = (REPO_ROOT / "output" / "emocio_vwm_mvp").resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"output must remain within {allowed}")
    return resolved


def _clear_exact(path: Path, allowed: Path) -> None:
    resolved = path.resolve()
    if allowed not in resolved.parents or resolved == allowed:
        raise ValueError(f"refusing unsafe cleanup target: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _render(target: Path) -> None:
    relative = target.relative_to(REPO_ROOT)
    completed = subprocess.run(
        ["node", str(RESEARCH_ROOT / "tools" / "render_e1r.mjs"), relative.as_posix()],
        cwd=REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    shutil.copytree(RESEARCH_ROOT / "specs", target / "specs")
    evaluate_run(bundle_dir=target, research_root=RESEARCH_ROOT)


def _tree_root(entries: list[dict[str, object]]) -> str:
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/emocio_vwm_mvp/e1r")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    output = _resolve_output(args.output)
    allowed = (REPO_ROOT / "output" / "emocio_vwm_mvp").resolve()
    run_a = output.parent / f".{output.name}_run_a"
    run_b = output.parent / f".{output.name}_run_b"
    for target in (output, run_a, run_b):
        if target.exists() and not args.replace:
            raise SystemExit(f"output exists; pass --replace: {target}")
        _clear_exact(target, allowed)
    try:
        _render(run_a)
        _render(run_b)
        tree_a = artifact_tree(run_a)
        tree_b = artifact_tree(run_b)
        by_path_a = {item["path"]: item for item in tree_a}
        by_path_b = {item["path"]: item for item in tree_b}
        all_paths = sorted(set(by_path_a) | set(by_path_b))
        comparisons = []
        for relative in all_paths:
            left = by_path_a.get(relative)
            right = by_path_b.get(relative)
            comparisons.append(
                {
                    "path": relative,
                    "run_a_sha256": None if left is None else left["sha256"],
                    "run_b_sha256": None if right is None else right["sha256"],
                    "run_a_bytes": None if left is None else left["bytes"],
                    "run_b_bytes": None if right is None else right["bytes"],
                    "match": left == right,
                }
            )
        full_match = all(item["match"] for item in comparisons)
        shutil.copytree(run_a, output)
        determinism = {
            "schema_version": "rei-emocio-vwm-two-run-artifact-tree-v1",
            "comparison_scope": "every_file_emitted_before_comparison_record_and_final_checksums",
            "run_a_file_count": len(tree_a),
            "run_b_file_count": len(tree_b),
            "run_a_tree_sha256": _tree_root(tree_a),
            "run_b_tree_sha256": _tree_root(tree_b),
            "matching_file_count": sum(item["match"] for item in comparisons),
            "mismatch_count": sum(not item["match"] for item in comparisons),
            "full_artifact_tree_match": full_match,
            "files": comparisons,
        }
        write_json(output / "two_run_determinism.json", determinism)
        metrics = read_json(output / "metrics.json")
        metrics["medium"]["two_run_artifact_tree_match"] = float(full_match)
        metrics["checks"]["two_run_artifact_tree"] = full_match
        write_json(output / "metrics.json", metrics)
        finalize_bundle(output)
        verdict = read_json(output / "verdict.json")
        print(json.dumps({"verdict": verdict, "two_run_determinism": {
            "file_count": len(comparisons), "full_match": full_match
        }}, indent=2))
        return 0 if full_match else 2
    finally:
        _clear_exact(run_a, allowed)
        _clear_exact(run_b, allowed)


if __name__ == "__main__":
    raise SystemExit(main())
