from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

from rei.evaluation.c4_stage1_attempt import C4Stage1ReviewCommitments
from rei.providers.protocols import StoredArtifact


ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = ROOT / "scripts" / "run_rei_c4_stage1.py"


def _load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_rei_c4_stage1_cli_test", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _paths(tmp_path: Path) -> list[str]:
    values = {
        "artifact-root": tmp_path / "artifacts",
        "worker-python": tmp_path / "python.exe",
        "source-png": tmp_path / "source.png",
        "source-provenance": tmp_path / "source.json",
        "primary-snapshot": tmp_path / "primary",
        "alternate-snapshot": tmp_path / "alternate",
        "staging-parent": tmp_path / "staging",
    }
    arguments = ["--run-id", "c4-stage1-cli-test"]
    for name, value in values.items():
        arguments.extend((f"--{name}", str(value.resolve())))
    return arguments


def _commitments(path: Path) -> C4Stage1ReviewCommitments:
    value = C4Stage1ReviewCommitments(
        operator_hmac_key_commitments_sha256=("1" * 64, "2" * 64),
        display_policy_nonce="3" * 64,
        ui_bundle_sha256="4" * 64,
        content_security_policy="default-src 'self'; object-src 'none'",
        presenter_implementation_id="stage1-test-presenter",
        presenter_revision="stage1-test-v1",
        display_attester_id="stage1-test-attester",
        display_signing_key_commitment_sha256="5" * 64,
    )
    path.write_bytes(value.canonical_json_bytes())
    return value


def test_cli_defaults_to_model_free_preparation_and_emits_exact_confirmation(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    model_modules_before = {
        name
        for name in sys.modules
        if name in {"torch", "diffusers", "transformers", "accelerate", "safetensors"}
    }
    cli = _load_cli()
    commitments_path = (tmp_path / "commitments.json").resolve()
    commitments = _commitments(commitments_path)
    calls = []
    prepared = SimpleNamespace(
        prepared_attempt=SimpleNamespace(
            run_id="c4-stage1-cli-test",
            prepared_attempt_id="prepared_exact_123",
        ),
        prepared_anchor_storage=SimpleNamespace(storage_id="stored_anchor_123"),
    )
    monkeypatch.setattr(cli, "FileArtifactStore", lambda *_args, **_kwargs: object())

    def prepare(**kwargs):
        calls.append(kwargs)
        assert kwargs["review_commitments"] == commitments
        assert kwargs["cuda_device"].logical_device_index == 0
        return prepared

    monkeypatch.setattr(cli, "prepare_c4_stage1_attempt", prepare)
    monkeypatch.setattr(
        cli,
        "run_c4_stage1_attempt",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not execute")),
    )
    arguments = [
        *_paths(tmp_path),
        "--review-commitments",
        str(commitments_path),
        "--cuda-uuid",
        "GPU-11111111-2222-3333-4444-555555555555",
        "--cuda-pci-bus-id",
        "00000000:01:00.0",
    ]

    assert cli.main(arguments) == 0
    assert len(calls) == 1
    output = capsys.readouterr().out
    assert '"action":"prepared"' in output
    assert '"prepared_attempt_id":"prepared_exact_123"' in output
    assert '"model_calls":0' in output
    assert {
        name
        for name in sys.modules
        if name in {"torch", "diffusers", "transformers", "accelerate", "safetensors"}
    } == model_modules_before


def test_cli_execution_requires_flag_and_both_exact_ids(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    cli = _load_cli()
    monkeypatch.setattr(
        cli,
        "prepare_c4_stage1_attempt",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not prepare")),
    )
    monkeypatch.setattr(
        cli,
        "run_c4_stage1_attempt",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not execute")),
    )

    assert cli.main(["--execute", *_paths(tmp_path)]) == 2
    assert "C4 Stage 1 stopped" in capsys.readouterr().err


def test_cli_executes_only_the_exact_inventory_anchor(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    cli = _load_cli()
    anchor = StoredArtifact(
        storage_id="stored_anchor_exact",
        run_id="c4-stage1-cli-test",
        relative_path="diagnostics/c4_stage1_prepared_attempt.json",
        content_sha256="a" * 64,
        size_bytes=100,
    )

    class Store:
        def __init__(self, *_args, **_kwargs):
            pass

        def inspect_run_inventory_exact(self, run_id):
            assert run_id == "c4-stage1-cli-test"
            return (anchor,)

    calls = []

    def execute(**kwargs):
        calls.append(kwargs)
        assert kwargs["prepared_anchor_storage"] == anchor
        assert kwargs["confirmed_prepared_attempt_id"] == "prepared_exact_123"
        return SimpleNamespace(
            manifest=SimpleNamespace(
                run_id="c4-stage1-cli-test",
                prepared_attempt_id="prepared_exact_123",
                render_attempt_manifest_id="render_manifest_123",
                status="evidence_ready",
            ),
            inventory_anchor=SimpleNamespace(
                render_inventory_anchor_id="render_inventory_123"
            ),
        )

    monkeypatch.setattr(cli, "FileArtifactStore", Store)
    monkeypatch.setattr(cli, "run_c4_stage1_attempt", execute)
    arguments = [
        "--execute",
        *_paths(tmp_path),
        "--prepared-attempt-id",
        "prepared_exact_123",
        "--prepared-anchor-storage-id",
        "stored_anchor_exact",
    ]

    assert cli.main(arguments) == 0
    assert len(calls) == 1
    output = capsys.readouterr().out
    assert '"action":"executed"' in output
    assert '"semantic_authority_granted":false' in output
    assert '"production_authority_granted":false' in output
