from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import Field, ValidationError

from .contract_loader import ego_required_keys, runtime_required_keys_for
from .json_utils import validate_required_keys
from .models import ApiModel
from .processor_eval import score_processor_signal


DatasetTarget = Literal["racio", "emocio", "instinkt", "ego_resultant"]
ProcessorTarget = Literal["racio", "emocio", "instinkt"]
DatasetStatus = Literal["draft", "needs_edit", "approved", "rejected"]
DatasetSplit = Literal["train", "validation", "test"]

TARGETS: tuple[DatasetTarget, ...] = ("racio", "emocio", "instinkt", "ego_resultant")
PROCESSOR_TARGETS: tuple[ProcessorTarget, ...] = ("racio", "emocio", "instinkt")

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS_ROOT = REPO_ROOT / "datasets"


class ProcessorProcessTrace(ApiModel):
    input_gate_hits: list[str] = Field(min_length=1, max_length=8)
    rejected_or_translated_inputs: list[str] = Field(default_factory=list, max_length=6)
    processing_route: list[str] = Field(min_length=3, max_length=5)
    blind_spot_check: str = Field(min_length=1)
    decision_bridge: str = Field(min_length=1)


class EgoProcessTrace(ApiModel):
    signal_read: list[str] = Field(min_length=3, max_length=6)
    profile_weighting_route: list[str] = Field(min_length=1, max_length=5)
    conflict_resolution: list[str] = Field(min_length=1, max_length=5)
    acceptance_check: str = Field(min_length=1)
    decision_bridge: str = Field(min_length=1)


class DatasetScenario(ApiModel):
    dataset_id: str
    scenario_id: str
    title: str
    prompt: str
    category: str = ""
    stress_target: Optional[DatasetTarget] = None
    tags: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    created_at: str = ""


class DatasetExample(ApiModel):
    dataset_id: str
    example_id: str
    scenario_id: str
    target: DatasetTarget
    status: DatasetStatus = "draft"
    split: Optional[DatasetSplit] = None
    system_prompt: str
    user_prompt: str
    assistant_payload: dict[str, Any]
    source_refs: list[str] = Field(default_factory=list)
    model: str = ""
    generation_settings: dict[str, Any] = Field(default_factory=dict)
    review_notes: str = ""
    reviewer: str = ""
    created_at: str = ""
    updated_at: str = ""


class DatasetManifest(ApiModel):
    dataset_id: str
    version: str = "rei-ft-dataset-v1"
    language: Literal["en"] = "en"
    description: str = ""
    source_policy: str = "curated_canon"
    scenario_count: int = 0
    example_count: int = 0
    target_counts: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    teacher_model: str = ""
    thinking_policy: str = ""
    created_at: str = ""
    updated_at: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dataset_path(dataset_id: str, root: Path = DATASETS_ROOT) -> Path:
    if not dataset_id or any(part in dataset_id for part in ("..", "/", "\\")):
        raise ValueError(f"Invalid dataset_id: {dataset_id!r}")
    return root / dataset_id


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_scenarios(dataset_dir: Path) -> list[DatasetScenario]:
    return [DatasetScenario.model_validate(row) for row in read_jsonl(dataset_dir / "scenarios.jsonl")]


def load_examples(dataset_dir: Path) -> list[DatasetExample]:
    return [DatasetExample.model_validate(row) for row in read_jsonl(dataset_dir / "examples.jsonl")]


def save_scenarios(dataset_dir: Path, scenarios: list[DatasetScenario]) -> None:
    write_jsonl(dataset_dir / "scenarios.jsonl", [item.model_dump(mode="json") for item in scenarios])


def save_examples(dataset_dir: Path, examples: list[DatasetExample]) -> None:
    write_jsonl(dataset_dir / "examples.jsonl", [item.model_dump(mode="json") for item in examples])


def required_keys_for_target(target: DatasetTarget) -> list[str]:
    if target == "ego_resultant":
        return ego_required_keys()
    return runtime_required_keys_for(target)


def validate_process_trace(target: DatasetTarget, payload: dict[str, Any]) -> list[str]:
    trace = payload.get("process_trace")
    if not isinstance(trace, dict):
        return ["missing:process_trace"]
    try:
        if target == "ego_resultant":
            EgoProcessTrace.model_validate(trace)
        else:
            ProcessorProcessTrace.model_validate(trace)
    except ValidationError as exc:
        return [f"process_trace:{'.'.join(str(part) for part in err['loc'])}:{err['type']}" for err in exc.errors()]
    return []


def validate_example(example: DatasetExample) -> dict[str, Any]:
    required = required_keys_for_target(example.target)
    payload = example.assistant_payload
    missing = validate_required_keys(payload, required)
    trace_errors = validate_process_trace(example.target, payload)
    invalid_constants: list[str] = []
    warnings: list[str] = []

    if example.target in PROCESSOR_TARGETS:
        if payload.get("mind") != example.target:
            invalid_constants.append(f"mind must be {example.target!r}")
        expected_conscious = example.target == "racio"
        expected_translated = example.target != "racio"
        if payload.get("is_conscious") is not expected_conscious:
            invalid_constants.append(f"is_conscious must be {expected_conscious!r}")
        if payload.get("translated_by_racio") is not expected_translated:
            invalid_constants.append(f"translated_by_racio must be {expected_translated!r}")
        score = score_processor_signal(example.target, payload)
        warnings.extend(score.get("style_violations", []))
        warnings.extend(score.get("rei_violations", []))
    else:
        score = {}
        if payload.get("character_profile") in {"", None}:
            warnings.append("ego_character_profile_empty")

    valid = not missing and not trace_errors and not invalid_constants
    if example.status == "approved" and not valid:
        warnings.append("approved_but_invalid")

    return {
        "example_id": example.example_id,
        "scenario_id": example.scenario_id,
        "target": example.target,
        "status": example.status,
        "valid": valid,
        "missing_required_keys": missing,
        "process_trace_errors": trace_errors,
        "invalid_constants": invalid_constants,
        "warnings": warnings,
        "score": score,
    }


def validate_dataset(dataset_dir: Path) -> dict[str, Any]:
    scenarios = load_scenarios(dataset_dir)
    examples = load_examples(dataset_dir)
    scenario_ids = {item.scenario_id for item in scenarios}
    validations = [validate_example(example) for example in examples]
    orphaned = [example.example_id for example in examples if example.scenario_id not in scenario_ids]
    invalid = [item for item in validations if not item["valid"]]
    approved_invalid = [
        item for item in validations if item["status"] == "approved" and not item["valid"]
    ]
    target_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for example in examples:
        target_counts[example.target] = target_counts.get(example.target, 0) + 1
        status_counts[example.status] = status_counts.get(example.status, 0) + 1
    return {
        "dataset_dir": str(dataset_dir),
        "scenario_count": len(scenarios),
        "example_count": len(examples),
        "target_counts": target_counts,
        "status_counts": status_counts,
        "valid_example_count": len(examples) - len(invalid),
        "invalid_example_count": len(invalid),
        "approved_invalid_count": len(approved_invalid),
        "orphaned_example_ids": orphaned,
        "examples": validations,
    }


def scenario_split_map(scenarios: list[DatasetScenario]) -> dict[str, DatasetSplit]:
    ordered = [item.scenario_id for item in scenarios]
    count = len(ordered)
    if count == 0:
        return {}
    if count < 10:
        return {scenario_id: "train" for scenario_id in ordered}
    validation_count = max(1, round(count * 0.1))
    test_count = max(1, round(count * 0.1))
    train_cutoff = max(0, count - validation_count - test_count)
    validation_cutoff = train_cutoff + validation_count
    mapping: dict[str, DatasetSplit] = {}
    for index, scenario_id in enumerate(ordered):
        if index < train_cutoff:
            mapping[scenario_id] = "train"
        elif index < validation_cutoff:
            mapping[scenario_id] = "validation"
        else:
            mapping[scenario_id] = "test"
    return mapping


def approved_examples_by_split(dataset_dir: Path) -> dict[DatasetSplit, list[DatasetExample]]:
    scenarios = load_scenarios(dataset_dir)
    split_by_scenario = scenario_split_map(scenarios)
    grouped: dict[DatasetSplit, list[DatasetExample]] = {"train": [], "validation": [], "test": []}
    for example in load_examples(dataset_dir):
        if example.status != "approved":
            continue
        validation = validate_example(example)
        if not validation["valid"]:
            continue
        split = example.split or split_by_scenario.get(example.scenario_id, "train")
        grouped[split].append(example.model_copy(update={"split": split}))
    return grouped


def example_to_sft_record(example: DatasetExample) -> dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": example.system_prompt},
            {"role": "user", "content": example.user_prompt},
            {
                "role": "assistant",
                "content": json.dumps(example.assistant_payload, ensure_ascii=False),
            },
        ],
        "metadata": {
            "dataset_id": example.dataset_id,
            "example_id": example.example_id,
            "scenario_id": example.scenario_id,
            "target": example.target,
            "source_refs": example.source_refs,
            "split": example.split,
        },
    }


def export_dataset(dataset_dir: Path) -> dict[str, Any]:
    grouped = approved_examples_by_split(dataset_dir)
    export_dir = dataset_dir / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for split, examples in grouped.items():
        rows = [example_to_sft_record(example) for example in examples]
        write_jsonl(export_dir / f"{split}.jsonl", rows)
        counts[split] = len(rows)
    summary = {
        "dataset_dir": str(dataset_dir),
        "export_dir": str(export_dir),
        "counts": counts,
        "exported_at": utc_now(),
    }
    write_json(export_dir / "export_summary.json", summary)
    return summary


def build_manifest(
    *,
    dataset_id: str,
    dataset_dir: Path,
    teacher_model: str = "",
    thinking_policy: str = "",
    description: str = "",
) -> DatasetManifest:
    scenarios = load_scenarios(dataset_dir)
    examples = load_examples(dataset_dir)
    target_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for example in examples:
        target_counts[example.target] = target_counts.get(example.target, 0) + 1
        status_counts[example.status] = status_counts.get(example.status, 0) + 1
    return DatasetManifest(
        dataset_id=dataset_id,
        description=description,
        scenario_count=len(scenarios),
        example_count=len(examples),
        target_counts=target_counts,
        status_counts=status_counts,
        teacher_model=teacher_model,
        thinking_policy=thinking_policy,
        updated_at=utc_now(),
    )


def write_manifest(dataset_dir: Path, manifest: DatasetManifest) -> None:
    write_json(dataset_dir / "manifest.json", manifest.model_dump(mode="json"))
