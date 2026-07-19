from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from scripts import run_rei_emocio_longcat_english_remain_exploration as remain


def _png(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    target = io.BytesIO()
    Image.new("RGB", size, color).save(target, format="PNG")
    return target.getvalue()


class FakeExecutor:
    def __init__(self) -> None:
        self.model_call_count = 0
        self.model_call_order: list[str] = []
        self.inputs: list[str] = []
        self.closed = False

    def execute(self, call, input_png):
        assert call == remain.CALL_PLAN[self.model_call_count]
        self.model_call_count += 1
        self.model_call_order.append(call.key)
        self.inputs.append(hashlib.sha256(input_png).hexdigest())
        color = (50 + call.order_index * 20, 80, 130)
        return remain.ModelExecution(
            native_png=_png((1184, 896), color),
            review_png=_png((1024, 768), color),
            native_width=1184,
            native_height=896,
            peak_allocated_bytes=100 + call.order_index,
            peak_reserved_bytes=200 + call.order_index,
        )

    def close(self) -> None:
        self.closed = True


class FailingExecutor:
    def __init__(self) -> None:
        self.model_call_count = 0
        self.model_call_order: list[str] = []
        self.closed = False

    def execute(self, call, input_png):
        self.model_call_count += 1
        self.model_call_order.append(call.key)
        raise RuntimeError("deliberate test failure")

    def close(self) -> None:
        self.closed = True


class FakeCuda:
    @staticmethod
    def is_available() -> bool:
        return False


class FakeGenerator:
    def __init__(self, device: str) -> None:
        self.device = device
        self.seed: int | None = None

    def manual_seed(self, seed: int):
        self.seed = seed
        return self


class FakeTorch:
    cuda = FakeCuda()

    @staticmethod
    def Generator(device: str) -> FakeGenerator:
        return FakeGenerator(device)


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(images=[Image.new("RGB", (1184, 896), (70, 90, 120))])


def _config(tmp_path: Path) -> tuple[remain.EnglishRemainConfig, bytes]:
    source_png = _png((1024, 768), (25, 35, 45))
    source = tmp_path / "source.png"
    source.write_bytes(source_png)
    snapshot = tmp_path / "longcat"
    snapshot.mkdir()
    snapshot_manifest = snapshot / remain.SNAPSHOT_MANIFEST_FILENAME
    snapshot_manifest.write_bytes(b'{"test":"snapshot"}\n')
    return (
        remain.EnglishRemainConfig(
            repo_root=tmp_path,
            source_path=source,
            longcat_snapshot=snapshot,
            output_root=(
                tmp_path / "output/exploration/emocio_longcat_english_remain"
            ),
            run_id="english_v1_test",
            repo_commit_sha="a" * 40,
            repo_branch=remain.REQUIRED_BRANCH,
            expected_source_sha256=hashlib.sha256(source_png).hexdigest(),
            expected_snapshot_manifest_sha256=hashlib.sha256(
                snapshot_manifest.read_bytes()
            ).hexdigest(),
        ),
        source_png,
    )


def test_english_remain_is_bounded_lineaged_and_non_authoritative(
    tmp_path: Path,
) -> None:
    config, source_png = _config(tmp_path)
    authority = tmp_path / "knowledge/visual_authority_registry.json"
    authority.parent.mkdir(parents=True)
    authority.write_text('{"authority":"unchanged"}\n', encoding="utf-8")
    authority_before = authority.read_bytes()
    executor = FakeExecutor()

    result = remain.run_english_remain_screen(config, executor=executor)

    source_hash = hashlib.sha256(source_png).hexdigest()
    assert result.technical_passed
    assert result.model_call_count == 3
    assert executor.closed
    assert executor.model_call_order == [call.key for call in remain.CALL_PLAN]
    assert executor.inputs == [source_hash] * 3
    assert config.source_path.read_bytes() == source_png
    assert authority.read_bytes() == authority_before

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["technical_status"] == "passed"
    assert manifest["semantic_status"] == "pending_human_review"
    assert manifest["human_review_status"] == "pending"
    assert manifest["planned_model_call_count"] == 3
    assert manifest["model_call_count"] == 3
    assert manifest["planned_model_call_order"] == executor.model_call_order
    assert manifest["retry_used"] is False
    assert manifest["fallback_used"] is False
    assert manifest["all_outputs_retained"] is True
    assert manifest["exploratory_no_authority"] is True
    assert manifest["generated_images_are_external_evidence"] is False
    assert manifest["semantic_review_performed_by_codex"] is False
    assert manifest["semantic_authority_granted"] is False
    assert manifest["production_authority_granted"] is False
    assert manifest["external_evidence_authority_granted"] is False
    assert manifest["goal_status_after_run"] == "blocked"
    assert manifest["source_mutated"] is False
    assert manifest["preflight_mutated"] is False
    assert manifest["script_mutated"] is False
    assert manifest["snapshot_manifest_mutated"] is False
    assert [call["status"] for call in manifest["calls"]] == ["succeeded"] * 3
    assert {call["input_png_sha256"] for call in manifest["calls"]} == {source_hash}

    for root_seed in remain.ROOT_SEEDS:
        assert (
            result.run_dir / f"seed_{root_seed}_remain_english_native.png"
        ).is_file()
        assert (result.run_dir / f"seed_{root_seed}_remain_english.png").is_file()
    assert (result.run_dir / "contact_sheet.png").is_file()
    assert (result.run_dir / "partial_calls.json").is_file()
    review = (result.run_dir / "review_template.md").read_text(encoding="utf-8")
    assert review.count("remain_state_accepted: yes / no") == 3
    assert review.count("both_sneakers_fully_on_corridor_side") == 3
    assert review.count("three_other_adults_still_inside_room") == 3
    assert review.count("- notes:\n") == 4
    assert "English REMAIN accepted in at least 2/3 seeds: yes / no" in review
    assert "[x]" not in review.lower()


def test_prompt_seed_pins_branch_and_output_containment(tmp_path: Path) -> None:
    assert len(remain.CALL_PLAN) == 3
    assert remain.ENGLISH_REMAIN_PROMPT.isascii()
    assert "on the corridor side of the silver threshold" in (
        remain.ENGLISH_REMAIN_PROMPT
    )
    assert hashlib.sha256(remain.ENGLISH_REMAIN_PROMPT.encode("utf-8")).hexdigest() == (
        remain.PROMPT_SHA256
    )
    assert [call.root_seed for call in remain.CALL_PLAN] == list(remain.ROOT_SEEDS)
    assert [call.seed for call in remain.CALL_PLAN] == [
        remain.PINNED_REMAIN_SEEDS[root_seed] for root_seed in remain.ROOT_SEEDS
    ]

    config, _ = _config(tmp_path)
    wrong_branch = replace(config, repo_branch="main")
    with pytest.raises(ValueError, match="must run on"):
        remain.run_english_remain_screen(wrong_branch, executor=FakeExecutor())

    wrong_root = replace(config, output_root=tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="output/exploration"):
        remain.run_english_remain_screen(wrong_root, executor=FakeExecutor())
    assert not (tmp_path / "elsewhere").exists()

    traversal = replace(config, run_id="../escaped")
    with pytest.raises(ValueError, match="direct child"):
        remain.run_english_remain_screen(traversal, executor=FakeExecutor())
    assert not (tmp_path / "output/exploration/escaped").exists()


def test_real_executor_pins_pipeline_arguments_and_failure_never_retries(
    tmp_path: Path,
) -> None:
    config, source_png = _config(tmp_path)
    pipeline = FakePipeline()
    executor = remain.RealEnglishRemainExecutor(config)
    executor._pipeline = pipeline
    executor._torch = FakeTorch()
    executor._image = Image

    execution = executor.execute(remain.CALL_PLAN[0], source_png)

    assert execution.native_width == 1184
    assert execution.native_height == 896
    assert len(pipeline.calls) == 1
    call = pipeline.calls[0]
    assert call["prompt"] == remain.ENGLISH_REMAIN_PROMPT
    assert call["negative_prompt"] == ""
    assert call["num_inference_steps"] == 8
    assert call["guidance_scale"] == 1.0
    assert call["num_images_per_prompt"] == 1
    assert call["generator"].device == "cpu"
    assert call["generator"].seed == remain.CALL_PLAN[0].seed
    assert call["output_type"] == "pil"
    assert call["return_dict"] is True
    executor.close()

    failing_config = replace(config, run_id="english_v1_failure")
    failing = FailingExecutor()
    result = remain.run_english_remain_screen(failing_config, executor=failing)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert not result.technical_passed
    assert failing.model_call_count == 1
    assert failing.closed
    assert [item["status"] for item in manifest["calls"]] == [
        "failed",
        "not_attempted",
        "not_attempted",
    ]
    assert manifest["retry_used"] is False
