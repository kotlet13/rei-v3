"""Seal an already-rendered E1R bundle without touching visual media bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


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


def _media_tree(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.casefold() in {".png", ".mp4"}
    ]


def _tree_hash(entries: list[dict[str, Any]]) -> str:
    data = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _resolve_bundle(value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    allowed = (REPO_ROOT / "output" / "emocio_vwm_mvp").resolve()
    if resolved == allowed or allowed not in resolved.parents:
        raise ValueError(f"bundle must remain within {allowed}")
    return resolved


def _validate_review(record: dict[str, Any], mosaic_sha256: str) -> None:
    expected_source = "research_owner_supplied_external_assistant_review"
    bool_fields = (
        "body_orientation_readable", "gaze_attention_readable", "identity_stability",
        "no_response_attribution_retained", "immediate_results_pending",
        "self_official_only_in_non_authoritative_goal", "camera_expression_acceptable",
    )
    if record.get("review_source") != expected_source:
        raise ValueError("review source differs from owner-approved source")
    if record.get("reviewer_type") != "external_ai_assistant":
        raise ValueError("reviewer must remain explicitly non-human")
    if record.get("human_review_performed") is not False:
        raise ValueError("external review must not be represented as human review")
    if record.get("reviewed_artifact_sha256") != mosaic_sha256:
        raise ValueError("review cites a different mosaic")
    if not all(record.get(field) is True for field in bool_fields):
        raise ValueError("not all review items passed")
    if record.get("failed_items") != [] or record.get("partial_items") != []:
        raise ValueError("review has failed or partial items")
    if record.get("passed_items") != [1, 2, 3, 4, 5, 6, 7] or record.get("overall") != "pass":
        raise ValueError("review is not an exact seven-item pass")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    bundle = _resolve_bundle(args.bundle)
    if not (bundle / "bundle_manifest.json").is_file():
        raise SystemExit("bundle manifest missing")

    media_before = _media_tree(bundle)
    media_tree_sha256 = _tree_hash(media_before)
    mosaic = bundle / "contact_sheets" / "review_mosaic.png"
    mosaic_sha256 = _sha256(mosaic)
    review_source = RESEARCH_ROOT / "reviews" / "visual_review_attempt_3.json"
    review = read_json(review_source)
    _validate_review(review, mosaic_sha256)

    shutil.copy2(review_source, bundle / "visual_review_attempt_3.json")
    shutil.copy2(
        RESEARCH_ROOT / "reviews" / "external_ai_gate_approval_2026-08-10.json",
        bundle / "external_ai_gate_approval_2026-08-10.json",
    )
    (bundle / "visual_review.md").write_text(
        "# E1R independent visual review attempt 3\n\n"
        "Reviewer type: `external_ai_assistant` (not human)\n\n"
        f"Reviewer ID: `{review['reviewer_id']}`\n\n"
        f"Reviewed mosaic SHA-256: `{mosaic_sha256}`\n\n"
        "Overall: `pass`\n\n"
        f"Notes: {review['notes']}\n",
        encoding="utf-8",
    )

    metrics = read_json(bundle / "metrics.json")
    metrics["medium"]["independent_visual_review_passed"] = True
    metrics["medium"]["human_visual_review_performed"] = False
    metrics["checks"]["independent_visual_review"] = True
    metrics["independent_visual_review"] = {
        "status": "complete",
        "review_source": review["review_source"],
        "reviewer_type": review["reviewer_type"],
        "human_review_performed": False,
        "passed": True,
        "record": "visual_review_attempt_3.json",
        "reviewed_artifact_sha256": mosaic_sha256,
        "history": metrics.get("independent_visual_review", {}).get("history", []),
    }
    write_json(bundle / "metrics.json", metrics)

    verdict = read_json(bundle / "verdict.json")
    verdict["protocol_status"] = "protocol_correction_passed"
    verdict["review_gate"] = {
        "status": "passed",
        "reviewer_type": review["reviewer_type"],
        "human_review_performed": False,
    }
    write_json(bundle / "verdict.json", verdict)

    manifest = read_json(bundle / "bundle_manifest.json")
    manifest["independent_visual_review"] = "visual_review_attempt_3.json"
    manifest["external_ai_gate_approval"] = "external_ai_gate_approval_2026-08-10.json"
    manifest["review_seal_lineage"] = "review_seal_lineage.json"
    write_json(bundle / "bundle_manifest.json", manifest)

    media_after = _media_tree(bundle)
    if media_after != media_before:
        raise RuntimeError("visual media changed during review seal")
    write_json(
        bundle / "review_seal_lineage.json",
        {
            "schema_version": "rei-emocio-vwm-review-seal-lineage-v1",
            "review_attempt": 3,
            "reviewed_artifact_sha256": mosaic_sha256,
            "visual_media_file_count": len(media_before),
            "visual_media_tree_sha256_before": media_tree_sha256,
            "visual_media_tree_sha256_after": _tree_hash(media_after),
            "visual_media_unchanged": True,
            "rerender_performed": False,
            "human_review_performed": False,
        },
    )
    finalize_bundle(bundle)
    print(json.dumps({
        "bundle": str(bundle),
        "mosaic_sha256": mosaic_sha256,
        "visual_media_file_count": len(media_before),
        "visual_media_tree_sha256": media_tree_sha256,
        "protocol_status": "protocol_correction_passed",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
