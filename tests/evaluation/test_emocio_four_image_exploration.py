from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from scripts import run_rei_emocio_four_image_exploration as exploration


def _png(color: tuple[int, int, int]) -> bytes:
    target = io.BytesIO()
    Image.new("RGB", (1024, 768), color).save(
        target, format="PNG", optimize=False, compress_level=9
    )
    return target.getvalue()


class FakeExecutor:
    def __init__(self, *, failing_key: str | None = None) -> None:
        self.failing_key = failing_key
        self.model_call_count = 0
        self.model_call_order: list[str] = []
        self.closed = False

    def execute(self, call, binding, source_png):
        assert hashlib.sha256(binding.prompt.encode("utf-8")).hexdigest() == (
            binding.prompt_sha256
        )
        assert len(source_png) > 0
        self.model_call_count += 1
        self.model_call_order.append(call.key)
        if call.key == self.failing_key:
            raise RuntimeError("bounded synthetic provider failure")
        colors = {
            "longcat:enter_circle": (180, 80, 60),
            "longcat:remain_edge": (80, 120, 180),
            "omnigen:enter_circle": (180, 150, 60),
            "omnigen:remain_edge": (70, 150, 110),
        }
        return exploration.ModelExecution(
            png=_png(colors[call.key]),
            peak_allocated_bytes=100 + call.order_index,
            peak_reserved_bytes=200 + call.order_index,
        )

    def close(self) -> None:
        self.closed = True


def _config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "frozen-source.png"
    source.write_bytes(_png((35, 45, 55)))
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(
        exploration, "C4_STAGE1_SOURCE_PNG_SHA256", source_hash
    )
    output_root = (
        tmp_path / "output" / "exploration" / "emocio_four_image_screen"
    )
    return exploration.ExplorationConfig(
        repo_root=tmp_path,
        source_path=source,
        longcat_snapshot=tmp_path / "read-only-longcat-snapshot",
        omnigen_snapshot=tmp_path / "read-only-omnigen-snapshot",
        output_root=output_root,
        run_id="x1_test",
        repo_commit_sha="a" * 40,
    )


def test_four_image_exploration_is_bounded_and_non_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path, monkeypatch)
    source_before = config.source_path.read_bytes()
    authority = tmp_path / "knowledge" / "visual_authority_registry.json"
    authority.parent.mkdir(parents=True)
    authority.write_text('{"authority":"unchanged"}\n', encoding="utf-8")
    authority_before = authority.read_bytes()
    executor = FakeExecutor()
    writes: list[Path] = []
    original_write_bytes = Path.write_bytes

    def tracked_write_bytes(path: Path, payload: bytes) -> int:
        writes.append(path.resolve())
        return original_write_bytes(path, payload)

    monkeypatch.setattr(Path, "write_bytes", tracked_write_bytes)

    result = exploration.run_exploration(config, executor=executor)

    assert result.passed
    assert result.model_call_count == 4
    assert executor.closed
    assert executor.model_call_order == [
        "longcat:enter_circle",
        "longcat:remain_edge",
        "omnigen:enter_circle",
        "omnigen:remain_edge",
    ]
    assert config.source_path.read_bytes() == source_before
    assert authority.read_bytes() == authority_before
    assert writes
    assert all(path.is_relative_to(result.run_dir) for path in writes)
    assert result.run_dir.is_relative_to(tmp_path / "output" / "exploration")
    assert {path.name for path in result.run_dir.iterdir()} == {
        "manifest.json",
        "source.png",
        "longcat_enter_circle.png",
        "longcat_remain_edge.png",
        "omnigen_enter_circle.png",
        "omnigen_remain_edge.png",
        "contact_sheet.png",
        "review_template.md",
    }
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["technical_status"] == "passed"
    assert manifest["call_attempt_count"] == 4
    assert manifest["model_call_count"] == 4
    assert manifest["exploratory_no_authority"] is True
    assert manifest["generated_images_are_external_evidence"] is False
    assert manifest["semantic_review_performed_by_codex"] is False
    assert manifest["semantic_authority_granted"] is False
    assert manifest["production_authority_granted"] is False
    assert manifest["external_evidence_authority_granted"] is False
    assert manifest["source_mutated"] is False
    assert [item["status"] for item in manifest["calls"]] == ["succeeded"] * 4
    review = (result.run_dir / "review_template.md").read_text(encoding="utf-8")
    for filename in (
        "longcat_enter_circle.png",
        "longcat_remain_edge.png",
        "omnigen_enter_circle.png",
        "omnigen_remain_edge.png",
    ):
        assert f"## {filename}" in review
    for field in (
        "source_subject_present: yes / partial / no",
        "identity_preserved: 0 / 1 / 2",
        "composition_preserved: 0 / 1 / 2",
        "option_action_correct: 0 / 1 / 2",
        "extra_actor_or_object: yes / no",
        "internally_useful_as_emocio_scene: yes / uncertain / no",
        "two_options_visibly_distinct: yes / uncertain / no",
        "same_underlying_scene: yes / uncertain / no",
        "promising_for_next_experiment: yes / no",
    ):
        assert field in review
    assert "## LongCat pair" in review
    assert "## OmniGen pair" in review


def test_provider_failure_is_recorded_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path, monkeypatch)
    executor = FakeExecutor(failing_key="longcat:remain_edge")

    result = exploration.run_exploration(config, executor=executor)

    assert not result.passed
    assert result.model_call_count == 2
    assert executor.model_call_order == [
        "longcat:enter_circle",
        "longcat:remain_edge",
    ]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert [item["status"] for item in manifest["calls"]] == [
        "succeeded",
        "failed",
        "not_attempted",
        "not_attempted",
    ]
    assert "bounded synthetic provider failure" in manifest["calls"][1]["error"]
    assert not (result.run_dir / "longcat_remain_edge.png").exists()
    assert (result.run_dir / "contact_sheet.png").is_file()


def test_output_root_cannot_escape_output_exploration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path, monkeypatch)
    outside = exploration.ExplorationConfig(
        repo_root=config.repo_root,
        source_path=config.source_path,
        longcat_snapshot=config.longcat_snapshot,
        omnigen_snapshot=config.omnigen_snapshot,
        output_root=tmp_path / "elsewhere",
        run_id=config.run_id,
        repo_commit_sha=config.repo_commit_sha,
    )

    with pytest.raises(ValueError, match="output/exploration"):
        exploration.run_exploration(outside, executor=FakeExecutor())

    assert not (tmp_path / "elsewhere").exists()
