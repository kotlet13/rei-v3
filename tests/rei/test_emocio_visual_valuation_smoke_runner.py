from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts import run_rei_emocio_visual_valuation_smoke as runner
from rei.emocio.visual_valuation import VisualValuationPolicy


_BASE_ARGUMENTS = (
    "--renderer-output-directory",
    "renderer-output",
    "--snapshot-directory",
    "dinov2-snapshot",
    "--snapshot-manifest-sha256",
    "a" * 64,
    "--output-directory",
    "valuation-output",
)
_SOURCE_PINS = (
    ("--expected-render-batch-id", "render_batch_pinned"),
    ("--expected-render-batch-hash", "b" * 64),
    ("--expected-root-seed", "424242"),
    ("--expected-renderer-provider-id", "provider_pinned"),
    ("--expected-renderer-model", "renderer/model"),
    ("--expected-renderer-revision", "c" * 40),
    ("--expected-prompt-profile-hash", "d" * 64),
)


def _all_cli_arguments() -> list[str]:
    arguments = list(_BASE_ARGUMENTS)
    for flag, value in _SOURCE_PINS:
        arguments.extend((flag, value))
    return arguments


@pytest.mark.parametrize("missing_flag", tuple(flag for flag, _ in _SOURCE_PINS))
def test_parse_args_requires_every_explicit_source_pin(missing_flag: str) -> None:
    arguments = list(_BASE_ARGUMENTS)
    for flag, value in _SOURCE_PINS:
        if flag != missing_flag:
            arguments.extend((flag, value))

    with pytest.raises(SystemExit) as exc_info:
        runner.parse_args(arguments)

    assert exc_info.value.code == 2


def test_parse_args_accepts_and_preserves_all_explicit_source_pins() -> None:
    args = runner.parse_args(_all_cli_arguments())

    assert args.expected_render_batch_id == "render_batch_pinned"
    assert args.expected_render_batch_hash == "b" * 64
    assert args.expected_root_seed == 424242
    assert args.expected_renderer_provider_id == "provider_pinned"
    assert args.expected_renderer_model == "renderer/model"
    assert args.expected_renderer_revision == "c" * 40
    assert args.expected_prompt_profile_hash == "d" * 64


def _patch_main_arguments(
    monkeypatch: pytest.MonkeyPatch,
    output: Path,
) -> argparse.Namespace:
    args = argparse.Namespace(output_directory=output)
    monkeypatch.setattr(runner, "parse_args", lambda argv=None: args)
    return args


def test_main_rejects_an_existing_output_before_running_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "already-present"
    output.mkdir()
    _patch_main_arguments(monkeypatch, output)

    def unexpected_run(*args, **kwargs) -> int:
        raise AssertionError("_run_smoke must not run for an existing output")

    monkeypatch.setattr(runner, "_run_smoke", unexpected_run)

    with pytest.raises(FileExistsError, match="create-only"):
        runner.main([])

    assert output.is_dir()
    assert list(tmp_path.glob(f".{output.name}.tmp-*")) == []


def test_main_transactionally_publishes_only_the_completed_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "published"
    args = _patch_main_arguments(monkeypatch, output)
    observed_working: list[Path] = []

    def successful_run(
        received: argparse.Namespace,
        *,
        output: Path,
    ) -> int:
        assert received is args
        assert not (tmp_path / "published").exists()
        assert output.parent == tmp_path
        assert output.name.startswith(".published.tmp-")
        observed_working.append(output)
        (output / "nested").mkdir()
        (output / "nested" / "complete.json").write_bytes(b"{}")
        return 17

    monkeypatch.setattr(runner, "_run_smoke", successful_run)

    assert runner.main([]) == 17
    assert (output / "nested" / "complete.json").read_bytes() == b"{}"
    assert len(observed_working) == 1
    assert not observed_working[0].exists()
    assert list(tmp_path.glob(".published.tmp-*")) == []


def test_main_removes_every_partial_path_when_run_smoke_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "failed"
    _patch_main_arguments(monkeypatch, output)
    observed_working: list[Path] = []

    def failing_run(
        args: argparse.Namespace,
        *,
        output: Path,
    ) -> int:
        del args
        observed_working.append(output)
        (output / "artifacts").mkdir()
        (output / "artifacts" / "partial.f32").write_bytes(b"partial")
        raise RuntimeError("injected smoke failure")

    monkeypatch.setattr(runner, "_run_smoke", failing_run)

    with pytest.raises(RuntimeError, match="injected smoke failure"):
        runner.main([])

    assert not output.exists()
    assert len(observed_working) == 1
    assert not observed_working[0].exists()
    assert list(tmp_path.glob(".failed.tmp-*")) == []


def _policy() -> VisualValuationPolicy:
    return VisualValuationPolicy.create(
        structured_weight=0.4,
        desired_similarity_weight=0.4,
        broken_avoidance_weight=0.2,
        seed_consistency_penalty=0.15,
        uncertainty_penalty=0.1,
    )


def test_load_canonical_model_rejects_noncanonical_and_tampered_json(
    tmp_path: Path,
) -> None:
    policy = _policy()
    canonical = runner.canonical_json_bytes(policy)
    canonical_path = tmp_path / "canonical.json"
    canonical_path.write_bytes(canonical)
    assert runner._load_canonical_model(
        canonical_path,
        VisualValuationPolicy,
    ) == policy

    noncanonical_path = tmp_path / "noncanonical.json"
    noncanonical_path.write_bytes(canonical + b"\n")
    with pytest.raises(ValueError, match="not canonical JSON"):
        runner._load_canonical_model(
            noncanonical_path,
            VisualValuationPolicy,
        )

    tampered_payload = json.loads(canonical)
    tampered_payload["policy_id"] = "visual_valuation_policy_forged"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_bytes(runner.canonical_json_bytes(tampered_payload))
    with pytest.raises(ValidationError, match="differs from canonical content"):
        runner._load_canonical_model(
            tampered_path,
            VisualValuationPolicy,
        )
