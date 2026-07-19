from __future__ import annotations

import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from scripts import run_rei_emocio_longcat_seed_exploration as screen


def _png(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    target = io.BytesIO()
    Image.new("RGB", size, color).save(target, format="PNG")
    return target.getvalue()


class FakeExecutor:
    def __init__(self) -> None:
        self.model_call_count = 0
        self.model_call_order: list[str] = []
        self.inputs: list[str] = []
        self.native_outputs: list[str] = []
        self.closed = False

    def execute(self, call, input_png):
        assert call == screen.CALL_PLAN[self.model_call_count]
        self.model_call_count += 1
        self.model_call_order.append(call.key)
        self.inputs.append(hashlib.sha256(input_png).hexdigest())
        color = (40 + call.order_index * 10, 70, 120)
        native = _png((1184, 896), color)
        review = _png((1024, 768), color)
        self.native_outputs.append(hashlib.sha256(native).hexdigest())
        return screen.ModelExecution(
            native_png=native,
            review_png=review,
            native_width=1184,
            native_height=896,
            peak_allocated_bytes=100 + call.order_index,
            peak_reserved_bytes=200 + call.order_index,
        )

    def close(self) -> None:
        self.closed = True


def _config(tmp_path: Path) -> tuple[screen.SeedScreenConfig, bytes]:
    source_png = _png((1024, 768), (25, 35, 45))
    source = tmp_path / "source.png"
    source.write_bytes(source_png)
    snapshot = tmp_path / "longcat"
    snapshot.mkdir()
    manifest = snapshot / screen.SNAPSHOT_MANIFEST_FILENAME
    manifest.write_bytes(b'{"test":"snapshot"}\n')
    output_root = tmp_path / "output/exploration/emocio_longcat_seed_screen"
    return (
        screen.SeedScreenConfig(
            repo_root=tmp_path,
            source_path=source,
            longcat_snapshot=snapshot,
            output_root=output_root,
            run_id="v1_test",
            repo_commit_sha="a" * 40,
            repo_branch=screen.REQUIRED_BRANCH,
            expected_source_sha256=hashlib.sha256(source_png).hexdigest(),
            expected_snapshot_manifest_sha256=hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest(),
        ),
        source_png,
    )


def test_seed_screen_is_bounded_lineaged_and_non_authoritative(tmp_path: Path) -> None:
    config, source_png = _config(tmp_path)
    authority = tmp_path / "knowledge/visual_authority_registry.json"
    authority.parent.mkdir(parents=True)
    authority.write_text('{"authority":"unchanged"}\n', encoding="utf-8")
    authority_before = authority.read_bytes()
    executor = FakeExecutor()

    result = screen.run_seed_screen(config, executor=executor)

    assert result.technical_passed
    assert result.model_call_count == 9
    assert executor.closed
    assert executor.model_call_order == [call.key for call in screen.CALL_PLAN]
    source_hash = hashlib.sha256(source_png).hexdigest()
    for offset in (0, 3, 6):
        assert executor.inputs[offset] == source_hash
        assert executor.inputs[offset + 1] == executor.native_outputs[offset]
        assert executor.inputs[offset + 2] == source_hash
    assert config.source_path.read_bytes() == source_png
    assert authority.read_bytes() == authority_before

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["technical_status"] == "passed"
    assert manifest["semantic_status"] == "pending_human_review"
    assert manifest["model_call_count"] == 9
    assert manifest["planned_model_call_count"] == 9
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
    assert [call["status"] for call in manifest["calls"]] == ["succeeded"] * 9

    for root_seed in screen.ROOT_SEEDS:
        for option in ("enter", "remain"):
            assert (result.run_dir / f"seed_{root_seed}_{option}.png").is_file()
        assert (result.run_dir / f"seed_{root_seed}_enter_pass1_native.png").is_file()
    assert (result.run_dir / "contact_sheet.png").is_file()
    review = (result.run_dir / "review_template.md").read_text(encoding="utf-8")
    assert review.count("source_subject_present: yes / partial / no") == 6
    assert review.count("two_options_visibly_distinct: yes / uncertain / no") == 3
    assert "authorize another phase: yes / no" in review


def test_seed_and_prompt_pins_and_output_containment(tmp_path: Path) -> None:
    assert len(screen.CALL_PLAN) == 9
    assert screen.REMAIN_PROMPT == "保持输入图像完全不变。"
    for stage, prompt in (
        ("enter_pass1", screen.ENTER_PROMPT),
        ("enter_cleanup", screen.CLEANUP_PROMPT),
        ("remain", screen.REMAIN_PROMPT),
    ):
        assert hashlib.sha256(prompt.encode("utf-8")).hexdigest() == (
            screen.PROMPT_SHA256[stage]
        )
    for root_seed in screen.ROOT_SEEDS:
        calls = [call for call in screen.CALL_PLAN if call.root_seed == root_seed]
        assert (calls[0].seed, calls[2].seed) == screen.PINNED_SEEDS[root_seed]
        assert calls[1].seed == calls[0].seed

    config, _ = _config(tmp_path)
    escaped = replace(config, output_root=tmp_path / "elsewhere")
    with pytest.raises(ValueError, match="output/exploration"):
        screen.run_seed_screen(escaped, executor=FakeExecutor())
    assert not (tmp_path / "elsewhere").exists()
