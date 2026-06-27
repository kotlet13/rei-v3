from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "backend"))
sys.path.insert(0, str(ROOT))

from rei.contract_loader import ego_required_keys
from rei.ft_dataset import (
    DatasetExample,
    DatasetScenario,
    export_dataset,
    load_examples,
    save_examples,
    save_scenarios,
    validate_example,
)
from rei.processor_eval import deterministic_processor_signal
from rei.profiles import profile_weights


PROFILE_INPUTS = [
    "R",
    "E",
    "I",
    "RE",
    "RI",
    "EI",
    "R>E>I",
    "R>I>E",
    "E>R>I",
    "E>I>R",
    "I>R>E",
    "I>E>R",
    "REI",
]


def processor_trace() -> dict[str, object]:
    return {
        "input_gate_hits": ["known facts", "unknown cost", "reversible test"],
        "rejected_or_translated_inputs": ["raw image pressure"],
        "processing_route": ["separate facts", "name unknowns", "compare options"],
        "blind_spot_check": "This processor may flatten non-verbal pressure.",
        "decision_bridge": "The route supports a bounded next step.",
    }


def ego_trace() -> dict[str, object]:
    return {
        "signal_read": ["Racio checks facts.", "Emocio wants contact.", "Instinkt protects safety."],
        "profile_weighting_route": ["Use R=E=I as equal arbitration."],
        "conflict_resolution": ["Preserve all three objections before choosing a small step."],
        "situational_override_check": "The situation does not override the balanced profile in this fixture.",
        "acceptance_check": "The result keeps cooperation visible.",
        "decision_bridge": "The integration supports one reversible action.",
    }


def ego_payload(profile: str = "R=E=I", weights: dict[str, float] | None = None) -> dict[str, object]:
    if weights is None:
        _normalized, weights = profile_weights(profile)
    payload: dict[str, object] = {}
    for key in ego_required_keys():
        if key in {"influence_weights", "task_delegation"}:
            payload[key] = dict(weights)
        elif key in {"profile_leader_minds", "safety_flags"}:
            payload[key] = []
        else:
            payload[key] = f"{key} value"
    payload["character_profile"] = profile
    payload["process_trace"] = ego_trace()
    return payload


def payload_for_target(
    target: str,
    profile: str = "R=E=I",
    weights: dict[str, float] | None = None,
) -> dict[str, object]:
    if target == "ego_resultant":
        return ego_payload(profile, weights)
    payload = deterministic_processor_signal(target, "I need to choose a bounded next step.")
    payload["process_trace"] = processor_trace()
    return payload


def scenario(dataset_id: str, index: int) -> DatasetScenario:
    return DatasetScenario(
        dataset_id=dataset_id,
        scenario_id=f"scenario_{index:03d}",
        title=f"Scenario {index}",
        prompt=f"Prompt {index}",
        category="test",
        source_refs=["PSI-R"],
        created_at="2026-01-01T00:00:00+00:00",
    )


def profile_slug(profile_input: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in profile_input).strip("_")


def example(
    dataset_id: str,
    scenario_id: str,
    target: str,
    status: str = "approved",
    profile_input: str = "REI",
) -> DatasetExample:
    profile = ""
    weights: dict[str, float] = {}
    example_id = f"{scenario_id}__{target}"
    if target == "ego_resultant":
        profile, weights = profile_weights(profile_input)
        example_id = f"{scenario_id}__ego_resultant__{profile_slug(profile_input)}"
    return DatasetExample(
        dataset_id=dataset_id,
        example_id=example_id,
        scenario_id=scenario_id,
        target=target,
        status=status,
        system_prompt=f"system {target}",
        user_prompt=f"user {scenario_id}",
        assistant_payload=payload_for_target(target, profile, weights),
        character_profile=profile,
        influence_weights=weights,
        source_refs=["PSI-R"],
        model="test",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def write_dataset(dataset_dir: Path, dataset_id: str, scenario_count: int = 50) -> None:
    scenarios = [scenario(dataset_id, index) for index in range(scenario_count)]
    examples = []
    for item in scenarios:
        for target in ["racio", "emocio", "instinkt"]:
            examples.append(example(dataset_id, item.scenario_id, target))
        for profile_input in PROFILE_INPUTS:
            examples.append(example(dataset_id, item.scenario_id, "ego_resultant", profile_input=profile_input))
    save_scenarios(dataset_dir, scenarios)
    save_examples(dataset_dir, examples)


def test_process_trace_is_required() -> None:
    payload = deterministic_processor_signal("racio", "A decision is pending.")
    item = DatasetExample(
        dataset_id="test",
        example_id="scenario__racio",
        scenario_id="scenario",
        target="racio",
        status="draft",
        system_prompt="system",
        user_prompt="user",
        assistant_payload=payload,
    )

    validation = validate_example(item)

    assert validation["valid"] is False
    assert "missing:process_trace" in validation["process_trace_errors"]


def test_ten_scenarios_map_to_profile_expanded_examples_and_export_by_scenario(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "rei_ft_profile_pilot_v1"
    write_dataset(dataset_dir, "rei_ft_profile_pilot_v1", scenario_count=10)

    examples = load_examples(dataset_dir)
    summary = export_dataset(dataset_dir)

    assert len(examples) == 160
    assert summary["counts"] == {"train": 128, "validation": 16, "test": 16}
    train_lines = (dataset_dir / "exports" / "train.jsonl").read_text(encoding="utf-8").splitlines()
    exported = json.loads(train_lines[0])
    assert [message["role"] for message in exported["messages"]] == ["system", "user", "assistant"]
    assert exported["metadata"]["target"] in {"racio", "emocio", "instinkt", "ego_resultant"}
    ego_record = next(json.loads(line) for line in train_lines if "__ego_resultant__" in line)
    assert ego_record["metadata"]["character_profile"]
    assert set(ego_record["metadata"]["influence_weights"]) == {"racio", "emocio", "instinkt"}


def test_ego_profile_mismatch_is_invalid() -> None:
    item = example("test", "scenario_001", "ego_resultant", profile_input="R")
    payload = dict(item.assistant_payload)
    payload["character_profile"] = "E>(R=I)"
    item = item.model_copy(update={"assistant_payload": payload})

    validation = validate_example(item)

    assert validation["valid"] is False
    assert "ego payload character_profile must match example character_profile" in validation["invalid_constants"]


def test_rejected_examples_never_export(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "rei_ft_rejected"
    save_scenarios(dataset_dir, [scenario("rei_ft_rejected", 1)])
    save_examples(
        dataset_dir,
        [
            example("rei_ft_rejected", "scenario_001", "racio", status="approved"),
            example("rei_ft_rejected", "scenario_001", "emocio", status="rejected"),
        ],
    )

    summary = export_dataset(dataset_dir)

    assert summary["counts"]["train"] == 1
    content = (dataset_dir / "exports" / "train.jsonl").read_text(encoding="utf-8")
    assert "scenario_001__racio" in content
    assert "scenario_001__emocio" not in content


def test_gui_dataset_endpoints_use_validation_and_save_updates(tmp_path: Path, monkeypatch) -> None:
    from app.gui import server

    dataset_id = "rei_ft_api"
    dataset_dir = tmp_path / dataset_id
    write_dataset(dataset_dir, dataset_id, scenario_count=1)

    monkeypatch.setattr(server, "_dataset_dir", lambda _dataset_id: dataset_dir)
    monkeypatch.setattr(server, "_dataset_ids", lambda: [dataset_id])

    listing = server.datasets()
    assert listing["datasets"][0]["dataset_id"] == dataset_id

    detail = server.dataset_example(dataset_id, "scenario_000__racio")
    assert detail["example"]["validation"]["valid"] is True

    update = server.update_dataset_example(
        dataset_id,
        "scenario_000__racio",
        server.DatasetExampleUpdate(status="needs_edit", review_notes="tighten process trace"),
    )
    assert update["example"]["status"] == "needs_edit"
    assert update["validation"]["valid"] is True
