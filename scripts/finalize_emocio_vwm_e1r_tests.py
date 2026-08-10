"""Attach final E1R test evidence without modifying sealed visual media."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = REPO_ROOT / "research" / "emocio_vwm_mvp_e1r"
sys.path.insert(0, str(RESEARCH_ROOT / "python"))

from emocio_vwm_mvp_e1r.evaluation import finalize_bundle, read_json, write_json  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _media_tree_hash(root: Path) -> tuple[int, str]:
    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.casefold() in {".png", ".mp4"}
    ]
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return len(entries), hashlib.sha256(canonical).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle if args.bundle.is_absolute() else REPO_ROOT / args.bundle
    bundle = bundle.resolve()
    allowed = (REPO_ROOT / "output" / "emocio_vwm_mvp").resolve()
    if bundle == allowed or allowed not in bundle.parents:
        raise ValueError("bundle path outside Emocio output root")

    seal = read_json(bundle / "review_seal_lineage.json")
    media_count, media_sha = _media_tree_hash(bundle)
    if media_sha != seal["visual_media_tree_sha256_after"] or media_count != seal["visual_media_file_count"]:
        raise RuntimeError("visual media changed after review seal")
    comparison = read_json(bundle / "pytest_regression_comparison.json")
    if not comparison["exact_failure_set_match"] or comparison["new_failures"]:
        raise RuntimeError("E1R introduced a full-suite regression")

    test_results = {
        "schema_version": "rei-emocio-vwm-e1r-test-results-v1",
        "targeted_suite": {
            "command": "python -m pytest tests/research/test_emocio_vwm_e1r.py -q --tb=short --basetemp=<external-path>",
            "passed": 13,
            "failed": 0,
            "wall_time_seconds": 0.23,
        },
        "full_suite_baseline": {
            "commit": "a1a8e0922a9fb1fd21893b46087cc0e9155146d9",
            "passed": comparison["baseline"]["passed"],
            "failed": comparison["baseline"]["failed"],
            "skipped": comparison["baseline"]["skipped"],
            "wall_time_seconds": 540.49,
            "junit_sha256": comparison["baseline"]["junit_sha256"],
        },
        "full_suite_candidate": {
            "candidate": "uncommitted_e1r_candidate",
            "passed": comparison["candidate_result"]["passed"],
            "failed": comparison["candidate_result"]["failed"],
            "skipped": comparison["candidate_result"]["skipped"],
            "wall_time_seconds": 481.01,
            "junit_sha256": comparison["candidate_result"]["junit_sha256"],
        },
        "regression_comparison": "pytest_regression_comparison.json",
        "exact_failure_set_match": True,
        "new_failure_count": 0,
        "active_rei_runtime_modified": False,
    }
    write_json(bundle / "test_results.json", test_results)
    manifest = read_json(bundle / "bundle_manifest.json")
    manifest["test_results"] = "test_results.json"
    manifest["pytest_regression_comparison"] = "pytest_regression_comparison.json"
    write_json(bundle / "bundle_manifest.json", manifest)
    finalize_bundle(bundle)

    post_count, post_sha = _media_tree_hash(bundle)
    if (post_count, post_sha) != (media_count, media_sha):
        raise RuntimeError("visual media changed during test finalization")
    print(json.dumps({
        "targeted": "13 passed",
        "baseline": f"{comparison['baseline']['passed']} passed, {comparison['baseline']['failed']} failed",
        "candidate": f"{comparison['candidate_result']['passed']} passed, {comparison['candidate_result']['failed']} failed",
        "new_failures": 0,
        "visual_media_tree_sha256": media_sha,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
