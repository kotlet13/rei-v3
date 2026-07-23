from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

from rei.evaluation.c4_stage1_attempt import C4Stage1ReviewCommitments
from tests.evaluation.test_c4_stage1_attempt import (
    _repository_gate,
    _ReviewService,
    _review_boundary,
)


ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = ROOT / "scripts" / "run_rei_c4_stage1_review_commitments.py"


def _load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_rei_c4_stage1_review_commitments_cli_test", CLI_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime_arguments(tmp_path: Path) -> list[str]:
    roots = []
    for name in ("runtime", "browser", "provenance"):
        path = (tmp_path / name).resolve()
        path.mkdir()
        roots.append(path)
    return [
        "--review-runtime-root",
        str(roots[0]),
        "--review-browser-root",
        str(roots[1]),
        "--review-runtime-provenance-root",
        str(roots[2]),
        "--confirmed-review-runtime-provenance-id",
        "c4_review_runtime_test",
        "--confirmed-review-runtime-provenance-sha256",
        "a" * 64,
        "--confirmed-review-runtime-manifest-id",
        "c4_review_tree_test",
        "--confirmed-review-runtime-manifest-sha256",
        "b" * 64,
        "--confirmed-review-runtime-python-sha256",
        "c" * 64,
    ]


def _bypass_runtime_preflight(cli: ModuleType, monkeypatch) -> None:
    class Support:
        @staticmethod
        def _stdlib_runtime_preflight(_arguments):
            return {}

        @staticmethod
        def _activate_verified_application_paths(_preflight):
            return None

        @staticmethod
        def _verify_with_application(_preflight, _environment):
            return None

    monkeypatch.setattr(cli, "_load_stdlib_preflight_support", lambda: Support())
    monkeypatch.setattr(cli, "_load_application_modules", lambda: object())


def test_commitment_cli_writes_one_canonical_public_file(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    model_modules_before = {
        name
        for name in sys.modules
        if name in {"torch", "diffusers", "transformers", "accelerate", "safetensors"}
    }
    runtime, readiness = _review_boundary()
    service = _ReviewService(readiness)
    cli = _load_cli()
    runtime_arguments = _runtime_arguments(tmp_path)
    _bypass_runtime_preflight(cli, monkeypatch)
    auth = (tmp_path / "ipc-auth.key").resolve()
    auth.write_bytes(b"a" * 32)
    output = (tmp_path / "review-commitments.json").resolve()
    client_calls = []

    def client_factory(*args, **kwargs):
        client_calls.append((args, kwargs))
        return service

    monkeypatch.setattr(
        cli,
        "C4Stage1ReviewServiceClient",
        client_factory,
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "capture_c4_stage1_review_runtime_manifest",
        lambda _root: runtime,
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "capture_c4_stage1_repository_gate",
        lambda _root: _repository_gate(),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "verify_c4_stage1_live_review_boundary",
        lambda **_kwargs: (runtime, readiness),
        raising=False,
    )
    monkeypatch.setattr(
        cli,
        "C4Stage1ReviewCommitments",
        C4Stage1ReviewCommitments,
        raising=False,
    )

    assert (
        cli.main(
            [
                *runtime_arguments,
                "--review-service-port",
                "1",
                "--review-service-auth-secret",
                str(auth),
                "--review-service-timeout-seconds",
                "126",
                "--review-presenter-timeout-ms",
                "120000",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    value = C4Stage1ReviewCommitments.model_validate_json(output.read_bytes())
    assert value.canonical_json_bytes() == output.read_bytes()
    assert value.review_runtime_manifest == runtime
    assert value.review_service_readiness == readiness
    assert client_calls == [
        (
            ("127.0.0.1", 1),
            {
                "auth_secret_path": auth,
                "timeout_seconds": 126.0,
                "presenter_timeout_ms": 120000,
            },
        )
    ]
    assert '"model_calls":0' in capsys.readouterr().out
    assert {
        name
        for name in sys.modules
        if name in {"torch", "diffusers", "transformers", "accelerate", "safetensors"}
    } == model_modules_before
    assert (
        cli.main(
            [
                *runtime_arguments,
                "--review-service-port",
                "1",
                "--review-service-auth-secret",
                str(auth),
                "--output",
                str(output),
            ]
        )
        == 2
    )


def test_commitment_cli_rejects_repository_output(tmp_path: Path, monkeypatch) -> None:
    cli = _load_cli()
    runtime_arguments = _runtime_arguments(tmp_path)
    _bypass_runtime_preflight(cli, monkeypatch)
    auth = (tmp_path / "ipc-auth.key").resolve()
    auth.write_bytes(b"a" * 32)
    output = ROOT / f".forbidden-c4-commitments-{tmp_path.name}.json"
    monkeypatch.setattr(
        cli,
        "C4Stage1ReviewServiceClient",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("service must not be contacted")
        ),
        raising=False,
    )

    assert (
        cli.main(
            [
                *runtime_arguments,
                "--review-service-port",
                "1",
                "--review-service-auth-secret",
                str(auth),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


def test_commitment_cli_rejects_wrong_interpreter_before_application_import(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cli = _load_cli()
    runtime_arguments = _runtime_arguments(tmp_path)
    auth = (tmp_path / "ipc-auth.key").resolve()
    auth.write_bytes(b"a" * 32)
    output = (tmp_path / "commitments.json").resolve()
    application_imported = False

    def application_loader() -> object:
        nonlocal application_imported
        application_imported = True
        raise AssertionError("application imports must remain unreachable")

    monkeypatch.setattr(cli, "_load_application_modules", application_loader)

    assert (
        cli.main(
            [
                *runtime_arguments,
                "--review-service-port",
                "1",
                "--review-service-auth-secret",
                str(auth),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert application_imported is False
    assert not output.exists()
