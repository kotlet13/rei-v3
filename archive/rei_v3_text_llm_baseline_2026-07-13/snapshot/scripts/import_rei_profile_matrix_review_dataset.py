from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))

from rei.ft_dataset import (  # noqa: E402
    DatasetExample,
    DatasetScenario,
    build_manifest,
    dataset_path,
    save_examples,
    save_scenarios,
    utc_now,
    write_manifest,
)
from rei.profiles import profile_weights  # noqa: E402


TARGET_PAYLOAD_KEYS = {
    "racio": ("signals", "racio"),
    "emocio": ("signals", "emocio_translated"),
    "instinkt": ("signals", "instinkt_translated"),
    "ego_resultant": ("ego_resultant",),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def profile_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "profile"


def target_payload(case: dict[str, Any], target: str) -> dict[str, Any]:
    output = case.get("output") or {}
    path = TARGET_PAYLOAD_KEYS[target]
    payload: Any = output
    for key in path:
        payload = (payload or {}).get(key)
    if not isinstance(payload, dict):
        payload = {}
    review = {
        "run_id": case.get("run_id"),
        "case_index": case.get("case_index"),
        "profile_input": case.get("profile_input"),
        "profile_normalized": case.get("profile_normalized"),
        "scenario_id": case.get("scenario_id"),
        "resultant_leader_under_pressure": case.get("resultant_leader_under_pressure"),
        "leading_mind": case.get("leading_mind"),
        "action_tendency_class": case.get("action_tendency_class"),
        "action_tendency": case.get("action_tendency"),
        "fallback_count": case.get("fallback_count"),
        "false_positive_flags": case.get("false_positive_flags"),
        "false_negative_flags": case.get("false_negative_flags"),
    }
    return {**payload, "_matrix_review": review}


def user_prompt(case: dict[str, Any], target: str) -> str:
    payload = {
        "review_task": "Review one imported REI profile-matrix output.",
        "target": target,
        "scenario": {
            "id": case.get("scenario_id"),
            "title": case.get("scenario_title"),
            "prompt": case.get("scenario_prompt"),
        },
        "profile_input": case.get("profile_input"),
        "profile_normalized": case.get("profile_normalized"),
        "action_tendency_class": case.get("action_tendency_class"),
        "action_tendency": case.get("action_tendency"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def import_dataset(cases_path: Path, dataset_id: str, overwrite: bool = False) -> Path:
    cases = read_jsonl(cases_path)
    if not cases:
        raise SystemExit(f"No cases found in {cases_path}")

    dataset_dir = dataset_path(dataset_id)
    if dataset_dir.exists() and any(dataset_dir.iterdir()) and not overwrite:
        raise SystemExit(f"Dataset already exists: {dataset_dir}. Use --overwrite.")
    dataset_dir.mkdir(parents=True, exist_ok=True)

    now = utc_now()
    scenarios_by_id: dict[str, DatasetScenario] = {}
    examples: list[DatasetExample] = []
    for case in cases:
        scenario_id = str(case.get("scenario_id") or "")
        if not scenario_id:
            continue
        if scenario_id not in scenarios_by_id:
            metadata = case.get("scenario_metadata") if isinstance(case.get("scenario_metadata"), dict) else {}
            category = str(metadata.get("category") or "")
            scenarios_by_id[scenario_id] = DatasetScenario(
                dataset_id=dataset_id,
                scenario_id=scenario_id,
                title=str(case.get("scenario_title") or scenario_id),
                prompt=str(case.get("scenario_prompt") or ""),
                category=category,
                tags=[category] if category else [],
                source_refs=[f"profile_matrix:{case.get('run_id') or 'unknown'}"],
                created_at=now,
            )
        profile_input = str(case.get("profile_input") or "")
        profile, weights = profile_weights(profile_input)
        base_id = f"{scenario_id}__{profile_slug(profile_input)}"
        for target in ("racio", "emocio", "instinkt", "ego_resultant"):
            examples.append(
                DatasetExample(
                    dataset_id=dataset_id,
                    example_id=f"{base_id}__{target}",
                    scenario_id=scenario_id,
                    target=target,  # type: ignore[arg-type]
                    status="draft",
                    system_prompt="Imported review-only profile-matrix output. Not for SFT export.",
                    user_prompt=user_prompt(case, target),
                    assistant_payload=target_payload(case, target),
                    character_profile=profile,
                    influence_weights=weights,
                    source_refs=[f"profile_matrix:{case.get('run_id') or 'unknown'}"],
                    model=str(case.get("model") or ""),
                    generation_settings={
                        "review_only": True,
                        "provider": case.get("provider"),
                        "run_id": case.get("run_id"),
                        "case_index": case.get("case_index"),
                        "profile_input": profile_input,
                        "elapsed_seconds": case.get("elapsed_seconds"),
                        "token_count": case.get("token_count"),
                    },
                    created_at=now,
                    updated_at=now,
                )
            )

    save_scenarios(dataset_dir, list(scenarios_by_id.values()))
    save_examples(dataset_dir, examples)
    manifest = build_manifest(
        dataset_id=dataset_id,
        dataset_dir=dataset_dir,
        teacher_model=str(cases[0].get("model") or ""),
        thinking_policy="review_only_profile_matrix_import",
        description=(
            "Review-only dataset imported from a REI profile matrix run. "
            "It is intended for GUI inspection and is skipped by SFT export."
        ),
    )
    write_manifest(dataset_dir, manifest)
    return dataset_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import REI profile matrix cases into GUI dataset review format.")
    parser.add_argument("cases_jsonl", type=Path)
    parser.add_argument("--dataset-id", default="rei_profile_matrix_review_20260627_121704")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir = import_dataset(args.cases_jsonl, args.dataset_id, args.overwrite)
    print(f"Imported review dataset: {dataset_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
