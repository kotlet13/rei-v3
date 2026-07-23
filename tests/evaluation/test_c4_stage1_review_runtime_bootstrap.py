from __future__ import annotations

import argparse
import ast
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "app" / "backend"
SCRIPT = ROOT / "scripts" / "run_rei_c4_stage1_review_runtime_bootstrap.py"
REVIEW_ENTRYPOINTS = (
    ROOT / "scripts" / "run_rei_c4_stage1_review.py",
    ROOT / "scripts" / "run_rei_c4_stage1_review_service.py",
)
REVIEW_CLI = ROOT / "scripts" / "run_rei_c4_stage1_review.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"_rei_c4_review_runtime_bootstrap_{id(object())}", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_review_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"_rei_c4_review_cli_preflight_{id(object())}", REVIEW_CLI
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_level_nonstdlib_import_roots() -> set[str]:
    pending: list[tuple[str | None, Path]] = [
        (None, path) for path in REVIEW_ENTRYPOINTS
    ]
    seen: set[Path] = set()
    external: set[str] = set()

    def add_local(module_name: str) -> None:
        parts = module_name.split(".")
        for end in range(1, len(parts) + 1):
            partial = parts[:end]
            package = BACKEND_ROOT.joinpath(*partial, "__init__.py")
            module = BACKEND_ROOT.joinpath(*partial).with_suffix(".py")
            candidate = module if module.is_file() else package
            if candidate.is_file():
                pending.append((".".join(partial), candidate.resolve()))

    while pending:
        module_name, path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        package = (
            module_name
            if module_name is not None and path.name == "__init__.py"
            else (module_name or "").rpartition(".")[0]
        )
        for node in tree.body:
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    target = importlib.util.resolve_name(
                        "." * node.level + (node.module or ""), package
                    )
                else:
                    target = node.module or ""
                if target:
                    targets.append(target)
                if node.module is None and target.startswith("rei"):
                    targets.extend(f"{target}.{alias.name}" for alias in node.names)
            for target in targets:
                root = target.partition(".")[0]
                if root == "rei":
                    add_local(target)
                elif root not in sys.stdlib_module_names:
                    external.add(root)
    return external


def _layout(tmp_path: Path) -> tuple[argparse.Namespace, dict[str, Path]]:
    base_root = tmp_path / "base"
    base_root.mkdir()
    base_python = base_root / "python.exe"
    base_python.write_bytes(b"frozen-cpython-3.11-amd64")
    artifact = tmp_path / "artifacts"
    model = tmp_path / "models"
    state = tmp_path / "state"
    artifact.mkdir()
    model.mkdir()
    state.mkdir()
    paths = {
        "base": base_python.resolve(),
        "runtime": (tmp_path / "review-runtime").resolve(),
        "browser": (tmp_path / "review-browsers").resolve(),
        "provenance": (tmp_path / "review-provenance").resolve(),
        "artifact": artifact.resolve(),
        "model": model.resolve(),
        "state": state.resolve(),
    }
    arguments = argparse.Namespace(
        mode="execute",
        execute=True,
        base_python=paths["base"],
        runtime_root=paths["runtime"],
        browser_root=paths["browser"],
        provenance_root=paths["provenance"],
        artifact_root=[paths["artifact"]],
        model_root=[paths["model"]],
        state_root=[paths["state"]],
    )
    return arguments, paths


def _install_fake_processes(
    monkeypatch: pytest.MonkeyPatch,
    bootstrap: ModuleType,
    paths: dict[str, Path],
) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def process_record(
        *,
        step: str,
        command: tuple[str, ...],
        stdout: bytes,
    ) -> dict[str, object]:
        from rei.ids import content_id

        started = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
        empty_sha256 = hashlib.sha256(b"").hexdigest()
        stdout_sha256 = hashlib.sha256(stdout).hexdigest()
        output_limit = bootstrap.PROCESS_TREE_MAX_OUTPUT_LIMIT_BYTES
        body = {
            "schema_version": "rei-process-tree-execution-v1",
            "runner_revision": "rei-process-tree-runner-v1",
            "workload_id": f"c4-review-bootstrap-{step.replace('_', '-')}",
            "command_identity": f"command-fake-{len(calls)}",
            "argument_count": len(command) - 1,
            "working_directory_identity": "cwd-fake",
            "environment_identity": "environment-fake",
            "timeout_seconds": bootstrap._STEP_TIMEOUTS[step],
            "stdout_limit_bytes": output_limit,
            "stderr_limit_bytes": output_limit,
            "platform_system": "Windows",
            "isolation_mode": "windows_job_object_kill_on_close",
            "target_start_token_hash": hashlib.sha256(step.encode()).hexdigest(),
            "target_process_group_id": None,
            "target_session_id": None,
            "started_at": started,
            "finished_at": started + timedelta(seconds=1),
            "elapsed_monotonic_seconds": 1.0,
            "workload_elapsed_monotonic_seconds": 0.9,
            "workload_timing_scope": (
                "release_attempt_to_confirmed_empty_tree_upper_bound"
            ),
            "process_id": 10_000 + len(calls),
            "workload_released": True,
            "workload_release_status": "released",
            "exit_code": 0,
            "status": "succeeded",
            "termination_trigger": "not_required",
            "failure_code": None,
            "failure_message": None,
            "stdout": {
                "byte_count": len(stdout),
                "captured_byte_count": len(stdout),
                "sha256": stdout_sha256,
                "captured_sha256": stdout_sha256,
                "truncated": False,
                "stream_complete": True,
            },
            "stderr": {
                "byte_count": 0,
                "captured_byte_count": 0,
                "sha256": empty_sha256,
                "captured_sha256": empty_sha256,
                "truncated": False,
                "stream_complete": True,
            },
            "tree_termination_requested": False,
            "tree_termination_succeeded": None,
            "tree_termination_method": None,
            "tree_inspection_method": "windows-job-active-processes",
            "final_active_processes": 0,
            "target_identity_confirmed": True,
            "empty_tree_confirmed": True,
            "containment_closed": True,
            "observer_callback_failed": False,
            "fallback_used": False,
        }
        return bootstrap.ProcessTreeExecutionRecord(
            record_id=content_id("process_execution", body),
            **body,
        ).model_dump(mode="json", round_trip=True)

    def fake_run_bounded(
        *,
        step: str,
        command: tuple[str, ...],
        working_directory: Path,
        environment: dict[str, str],
    ) -> object:
        calls.append(
            {
                "step": step,
                "command": command,
                "working_directory": working_directory,
                "environment": dict(environment),
            }
        )
        stdout = b""
        if step in {"base_python_probe", "copied_base_python_probe"}:
            stdout = (
                bootstrap._canonical_json_bytes(
                    {
                        "base_prefix": str(Path(command[0]).parent),
                        "cache_tag": "cpython-311",
                        "executable": command[0],
                        "implementation": "CPython",
                        "is_venv": False,
                        "machine": "AMD64",
                        "platform_tag": "win-amd64",
                        "pointer_bits": 64,
                        "prefix": str(Path(command[0]).parent),
                        "version": "3.11.15",
                        "version_info": [3, 11, 15],
                    }
                )
                + b"\n"
            )
        elif step == "create_copy_venv":
            venv = Path(command[-1])
            (venv / "Scripts").mkdir(parents=True)
            (venv / "Scripts" / "python.exe").write_bytes(Path(command[0]).read_bytes())
            (venv / "Lib" / "site-packages").mkdir(parents=True)
            (venv / "pyvenv.cfg").write_text(
                f"home = {Path(command[0]).parent}\n"
                "include-system-site-packages = false\n"
                "version = 3.11.15\n"
                f"executable = {command[0]}\n"
                f"command = {command[0]} -m venv --copies --without-pip {venv}\n",
                encoding="utf-8",
            )
        elif step == "runtime_python_layout_probe":
            runtime_python = Path(command[0])
            venv = runtime_python.parents[1]
            copied_base = venv.parent / bootstrap.COPIED_BASE_DIRECTORY
            stdout = (
                bootstrap._canonical_json_bytes(
                    {
                        "base_prefix": str(copied_base),
                        "cache_tag": "cpython-311",
                        "executable": command[0],
                        "implementation": "CPython",
                        "is_venv": True,
                        "machine": "AMD64",
                        "platform_tag": "win-amd64",
                        "pointer_bits": 64,
                        "prefix": str(venv),
                        "version": "3.11.15",
                        "version_info": [3, 11, 15],
                    }
                )
                + b"\n"
            )
        elif step == "download_hash_pinned_wheels":
            destination = Path(command[command.index("--dest") + 1])
            for pin in bootstrap.PACKAGE_PINS:
                (destination / pin.filename).write_bytes(
                    f"fake wheel {pin.name} {pin.version}".encode()
                )
        elif step == "install_offline_wheelhouse":
            site = paths["runtime"] / bootstrap.VENV_DIRECTORY / "Lib" / "site-packages"
            browser_data = site / "playwright" / "driver" / "package"
            browser_data.mkdir(parents=True)
            browser_data.joinpath("browsers.json").write_text(
                json.dumps(
                    {
                        "comment": "official fake fixture",
                        "browsers": [
                            {
                                "name": "chromium",
                                "revision": bootstrap.CHROMIUM_REVISION,
                                "installByDefault": True,
                                "browserVersion": bootstrap.CHROMIUM_VERSION,
                                "title": "Chrome for Testing",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            for pin in bootstrap.PACKAGE_PINS:
                metadata = (
                    site / f"{pin.name.replace('-', '_')}-{pin.version}.dist-info"
                )
                metadata.mkdir()
                (metadata / "METADATA").write_text(
                    f"Name: {pin.name}\nVersion: {pin.version}\n",
                    encoding="utf-8",
                )
                (metadata / "RECORD").write_text("", encoding="utf-8")
                (metadata / "WHEEL").write_text(
                    "Wheel-Version: 1.0\n",
                    encoding="utf-8",
                )
        elif step == "installed_package_probe":
            stdout = (
                bootstrap._canonical_json_bytes(
                    {
                        "distributions": (
                            bootstrap._EXPECTED_PACKAGE_DISTRIBUTIONS
                        )
                    }
                )
                + b"\n"
            )
        elif step == "review_import_contract_probe":
            stdout = (
                bootstrap._canonical_json_bytes(
                    {"imported": list(bootstrap.REVIEW_RUNTIME_IMPORT_PROBE_MODULES)}
                )
                + b"\n"
            )
        elif step == "install_matching_chromium":
            chromium_root = paths["browser"] / f"chromium-{bootstrap.CHROMIUM_REVISION}"
            (chromium_root / "chrome-win64").mkdir(parents=True)
            (chromium_root / "chrome-win64" / "chrome.exe").write_bytes(
                b"frozen chromium executable"
            )
            (chromium_root / "INSTALLATION_COMPLETE").write_bytes(b"complete")
        else:  # pragma: no cover - fixed protocol should make this unreachable
            raise AssertionError(step)
        return bootstrap._ProcessOutcome(
            stdout=stdout,
            record=process_record(step=step, command=command, stdout=stdout),
        )

    def fake_verify_wheelhouse(_wheelhouse: Path) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "relative_path": pin.filename,
                "sha256": pin.sha256,
                "size_bytes": pin.size_bytes,
            }
            for pin in bootstrap.PACKAGE_PINS
        )

    monkeypatch.setattr(bootstrap, "_run_bounded", fake_run_bounded)
    monkeypatch.setattr(bootstrap, "_verify_wheelhouse", fake_verify_wheelhouse)
    monkeypatch.setattr(
        bootstrap.review_environment,
        "_verified_wheels",
        lambda _root, *, checkpoint: list(fake_verify_wheelhouse(_root)),
    )
    return calls


def test_official_windows_pins_are_exact_and_complete() -> None:
    bootstrap = _load()
    pins = {pin.name: pin for pin in bootstrap.PACKAGE_PINS}

    assert bootstrap.PLAYWRIGHT_VERSION == "1.61.0"
    assert bootstrap.CHROMIUM_REVISION == "1228"
    assert bootstrap.CHROMIUM_VERSION == "149.0.7827.55"
    assert pins["playwright"].filename == ("playwright-1.61.0-py3-none-win_amd64.whl")
    assert pins["playwright"].sha256 == (
        "35c6cc4589a5d00964a59d7b3e59641e0aac0c02f15479a7af77d20f6bc79597"
    )
    assert pins["playwright"].size_bytes == 37_844_846
    assert {name: pin.version for name, pin in pins.items()} == {
        "annotated-types": "0.7.0",
        "greenlet": "3.1.1",
        "playwright": "1.61.0",
        "pydantic": "2.13.4",
        "pydantic-core": "2.46.4",
        "pyee": "13.0.0",
        "typing-extensions": "4.16.0",
        "typing-inspection": "0.4.2",
    }
    assert (
        pins["pydantic"].filename,
        pins["pydantic"].sha256,
        pins["pydantic"].size_bytes,
    ) == (
        "pydantic-2.13.4-py3-none-any.whl",
        "45a282cde31d808236fd7ea9d919b128653c8b38b393d1c4ab335c62924d9aba",
        472_262,
    )
    assert (
        pins["pydantic-core"].filename,
        pins["pydantic-core"].sha256,
        pins["pydantic-core"].size_bytes,
    ) == (
        "pydantic_core-2.46.4-cp311-cp311-win_amd64.whl",
        "6f2eeda33a839975441c86a4119e1383c50b47faf0cbb5176985565c6bb02c33",
        2_071_114,
    )
    assert (
        pins["annotated-types"].sha256,
        pins["annotated-types"].size_bytes,
    ) == (
        "1f02e8b43a8fbbc3f3e0d4f0f4bfc8131bcb4eebe8849b8e5c773f3a1c582a53",
        13_643,
    )
    assert (
        pins["typing-inspection"].sha256,
        pins["typing-inspection"].size_bytes,
    ) == (
        "4ed1cacbdc298c220f1bd249ed5287caa16f34d44ef4e9c3d0cbad5b521545e7",
        14_611,
    )
    assert all(
        pin.metadata_url.startswith("https://pypi.org/pypi/") for pin in pins.values()
    )
    assert all(
        pin.artifact_url.startswith("https://files.pythonhosted.org/packages/")
        for pin in pins.values()
    )


@pytest.mark.parametrize(
    "member",
    (
        "package/module.py:alternate-stream",
        "CON",
        "package/prn.txt",
        "package/AUX.json",
        "package/nul.data",
        "package/COM1.py",
        "package/lpt9.log",
        "package/trailing.",
        "package/trailing ",
    ),
)
def test_stdlib_wheel_member_policy_rejects_windows_aliases(member: str) -> None:
    bootstrap = _load()
    namespace: dict[str, object] = {}
    exec(bootstrap._STDLIB_WHEEL_MEMBER_POLICY, namespace)  # noqa: S102
    validator = namespace["validated_wheel_member_parts"]

    with pytest.raises(RuntimeError):
        validator(member)

    assert "package/module.py" == "/".join(validator("package/module.py"))


def test_sealed_package_set_covers_review_cli_import_contract() -> None:
    bootstrap = _load()
    pinned = {pin.name for pin in bootstrap.PACKAGE_PINS}
    compile(bootstrap._PACKAGE_PROBE, "<sealed-package-probe>", "exec")
    compile(bootstrap._REVIEW_IMPORT_PROBE, "<review-import-probe>", "exec")

    assert _module_level_nonstdlib_import_roots() == {"pydantic"}
    presenter_path = (
        BACKEND_ROOT / "rei" / "evaluation" / "c4_stage1_review_presenter.py"
    )
    presenter = ast.parse(
        presenter_path.read_text(encoding="utf-8"), filename=str(presenter_path)
    )
    factory = next(
        node
        for node in presenter.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_default_playwright_factory"
    )
    deferred_roots = {
        node.module.partition(".")[0]
        for node in ast.walk(factory)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert deferred_roots == {"playwright"}

    direct_import_root_to_distribution = {
        "playwright": "playwright",
        "pydantic": "pydantic",
    }
    assert set(direct_import_root_to_distribution.values()) <= pinned

    probe_import_root_to_distribution = {
        "annotated_types": "annotated-types",
        "greenlet": "greenlet",
        "playwright": "playwright",
        "pydantic": "pydantic",
        "pydantic_core": "pydantic-core",
        "pyee": "pyee",
        "typing_extensions": "typing-extensions",
        "typing_inspection": "typing-inspection",
    }
    probe_external_roots = {
        name.partition(".")[0]
        for name in bootstrap.REVIEW_RUNTIME_IMPORT_PROBE_MODULES
        if not name.startswith("rei.")
    }
    assert probe_external_roots == set(probe_import_root_to_distribution)
    assert set(probe_import_root_to_distribution.values()) == pinned


def test_plan_is_read_only_and_redacts_local_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load()
    arguments, paths = _layout(tmp_path)
    arguments.mode = "plan"
    arguments.execute = False
    calls = _install_fake_processes(monkeypatch, bootstrap, paths)

    roots = bootstrap._normalize_roots(arguments, fresh=True)
    base_descriptor, _ = bootstrap._probe_base_python(arguments.base_python)
    plan = bootstrap._plan_value(roots, base_descriptor)
    encoded = bootstrap._canonical_json_bytes(plan).decode("utf-8")

    assert [call["step"] for call in calls] == ["base_python_probe"]
    assert plan["network_access_in_plan_mode"] is False
    assert plan["browser_process_launch_performed"] is False
    assert plan["headed_full_ui_smoke_performed"] is False
    assert plan["model_calls"] == 0
    assert not paths["runtime"].exists()
    assert not paths["browser"].exists()
    assert not paths["provenance"].exists()
    for path in paths.values():
        assert str(path) not in encoded


def test_execute_is_explicit_and_rejects_forbidden_root_overlap(tmp_path: Path) -> None:
    bootstrap = _load()
    arguments, paths = _layout(tmp_path)
    arguments.execute = False
    with pytest.raises(bootstrap.C4Stage1ReviewRuntimeBootstrapError):
        bootstrap._execute(arguments)

    arguments.execute = True
    arguments.runtime_root = paths["artifact"] / "nested-runtime"
    with pytest.raises(bootstrap.C4Stage1ReviewRuntimeBootstrapError):
        bootstrap._normalize_roots(arguments, fresh=True)


def test_fake_execution_writes_create_only_verifiable_provenance_without_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load()
    arguments, paths = _layout(tmp_path)
    calls = _install_fake_processes(monkeypatch, bootstrap, paths)

    result = bootstrap._execute(arguments)

    assert result["action"] == "c4_stage1_review_runtime_bootstrap_completed"
    assert result["browser_process_launch_performed"] is False
    assert result["headed_full_ui_smoke_performed"] is False
    assert result["model_calls"] == 0
    assert tuple(sorted(path.name for path in paths["provenance"].iterdir())) == tuple(
        sorted(
            (
                bootstrap.RUNTIME_MANIFEST_NAME,
                bootstrap.BROWSER_MANIFEST_NAME,
                bootstrap.PROVENANCE_NAME,
            )
        )
    )
    provenance_raw = (paths["provenance"] / bootstrap.PROVENANCE_NAME).read_bytes()
    provenance = json.loads(provenance_raw)
    assert bootstrap._canonical_json_bytes(provenance) == provenance_raw
    assert provenance["secrets_stored"] is False
    assert provenance["browser_process_launch_performed"] is False
    assert provenance["headed_full_ui_smoke_authority"] == (
        "authenticated-review-service-only"
    )
    encoded = provenance_raw.decode("utf-8")
    for path in paths.values():
        assert str(path) not in encoded

    install_calls = [
        call for call in calls if call["step"] == "install_matching_chromium"
    ]
    assert len(install_calls) == 1
    assert install_calls[0]["command"][-2:] == ("install", "chromium")
    assert install_calls[0]["command"][1:4] == ("-I", "-S", "-B")
    assert install_calls[0]["environment"]["PLAYWRIGHT_BROWSERS_PATH"] == str(
        paths["browser"]
    )
    assert all("launch" not in call["command"] for call in calls)
    import_probe_calls = [
        call for call in calls if call["step"] == "review_import_contract_probe"
    ]
    assert len(import_probe_calls) == 1
    assert import_probe_calls[0]["command"][0] == str(
        paths["runtime"] / bootstrap.RUNTIME_PYTHON_RELATIVE_PATH
    )
    assert import_probe_calls[0]["command"][1:4] == ("-I", "-S", "-B")
    assert not any(
        argument.casefold() == "pip"
        for call in calls
        for argument in call["command"]
    )

    verified = bootstrap._verify(arguments)
    assert verified["action"] == "c4_stage1_review_runtime_verified"
    assert verified["provenance_id"] == result["provenance_id"]
    assert verified["headed_full_ui_smoke_performed"] is False
    checkpoints = 0

    def checkpoint() -> None:
        nonlocal checkpoints
        checkpoints += 1

    presenter_summary = bootstrap.review_environment.verify_presenter_runtime(
        paths["provenance"],
        paths["runtime"],
        paths["browser"],
        checkpoint=checkpoint,
    )
    assert presenter_summary["provenance"]["provenance_id"] == result["provenance_id"]
    assert presenter_summary["runtime_manifest"]["tree_content_sha256"]
    assert presenter_summary["browser_manifest"]["tree_content_sha256"]
    assert presenter_summary["paths_stored"] is False
    assert checkpoints > 20


def test_verify_rejects_post_install_executable_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load()
    arguments, paths = _layout(tmp_path)
    _install_fake_processes(monkeypatch, bootstrap, paths)
    bootstrap._execute(arguments)
    chromium = paths["browser"].joinpath(
        *bootstrap.CHROMIUM_EXECUTABLE_RELATIVE_PATH.split("/")
    )
    chromium.write_bytes(b"tampered chromium executable")

    with pytest.raises(bootstrap.C4Stage1ReviewRuntimeBootstrapError):
        bootstrap._verify(arguments)


def test_authority_cli_preflight_binds_interpreter_to_sealed_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load()
    arguments, paths = _layout(tmp_path)
    _install_fake_processes(monkeypatch, bootstrap, paths)
    bootstrap._execute(arguments)
    provenance_raw = (paths["provenance"] / bootstrap.PROVENANCE_NAME).read_bytes()
    provenance = json.loads(provenance_raw)
    cli = _load_review_cli()
    cli.sys = SimpleNamespace(
        executable=str(paths["runtime"] / bootstrap.RUNTIME_PYTHON_RELATIVE_PATH),
        flags=SimpleNamespace(
            isolated=1,
            no_site=1,
            ignore_environment=1,
            dont_write_bytecode=1,
        ),
        path=[str(paths["runtime"] / bootstrap.COPIED_BASE_DIRECTORY)],
    )
    preflight_arguments = argparse.Namespace(
        review_runtime_root=paths["runtime"],
        review_browser_root=paths["browser"],
        review_runtime_provenance_root=paths["provenance"],
        confirmed_review_runtime_provenance_id=provenance["provenance_id"],
        confirmed_review_runtime_provenance_sha256=hashlib.sha256(
            provenance_raw
        ).hexdigest(),
        confirmed_review_runtime_manifest_id=provenance["runtime_manifest"][
            "manifest_id"
        ],
        confirmed_review_runtime_manifest_sha256=provenance["runtime_manifest"][
            "sha256"
        ],
        confirmed_review_runtime_python_sha256=provenance["runtime_python"][
            "sha256"
        ],
    )

    preflight = cli._stdlib_runtime_preflight(preflight_arguments)

    assert preflight["provenance_id"] == provenance["provenance_id"]
    assert preflight["runtime_manifest_id"] == provenance["runtime_manifest"][
        "manifest_id"
    ]
    preflight_arguments.confirmed_review_runtime_manifest_id = "forged"
    with pytest.raises(cli._ReviewRuntimePreflightError):
        cli._stdlib_runtime_preflight(preflight_arguments)


@pytest.mark.parametrize(
    "relative_path,payload",
    (
        (
            "venv/Lib/site-packages/duplicate_name-4.16.0.dist-info/METADATA",
            b"Name: typing_extensions\nVersion: 4.16.0\n",
        ),
        ("base-python/Lib/site-packages/execute.pth", b"import os\n"),
        ("venv/Lib/site-packages/sitecustomize.py", b"raise SystemExit\n"),
        ("base-python/Lib/usercustomize.py", b"raise SystemExit\n"),
    ),
)
def test_active_runtime_policy_rejects_extra_distributions_and_customization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    payload: bytes,
) -> None:
    bootstrap = _load()
    arguments, paths = _layout(tmp_path)
    _install_fake_processes(monkeypatch, bootstrap, paths)
    bootstrap._execute(arguments)
    target = paths["runtime"].joinpath(*relative_path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    if target.name == "METADATA":
        (target.parent / "RECORD").write_bytes(b"")
        (target.parent / "WHEEL").write_bytes(b"Wheel-Version: 1.0\n")

    with pytest.raises(bootstrap.review_environment.C4Stage1ReviewEnvironmentError):
        bootstrap.review_environment._installed_distributions(  # noqa: SLF001
            paths["runtime"],
            checkpoint=lambda: None,
        )


def test_failed_execute_rolls_back_all_fresh_external_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load()
    arguments, paths = _layout(tmp_path)
    _install_fake_processes(monkeypatch, bootstrap, paths)
    fake_run_bounded = bootstrap._run_bounded

    def fail_after_wheel_download(**kwargs: object) -> object:
        if kwargs["step"] == "install_offline_wheelhouse":
            raise bootstrap.C4Stage1ReviewRuntimeBootstrapError("synthetic failure")
        return fake_run_bounded(**kwargs)

    monkeypatch.setattr(bootstrap, "_run_bounded", fail_after_wheel_download)

    with pytest.raises(bootstrap.C4Stage1ReviewRuntimeBootstrapError):
        bootstrap._execute(arguments)

    assert not paths["runtime"].exists()
    assert not paths["browser"].exists()
    assert not paths["provenance"].exists()


def test_manifest_rejects_hardlinks(tmp_path: Path) -> None:
    bootstrap = _load()
    root = tmp_path / "runtime"
    root.mkdir()
    payload = root / "python.exe"
    payload.write_bytes(b"runtime")
    alias = root / "alias.exe"
    alias.hardlink_to(payload)

    with pytest.raises(bootstrap.review_environment.C4Stage1ReviewEnvironmentError):
        bootstrap._capture_tree(root.resolve(), tree_role="review-python-runtime")


def test_shared_manifest_rejects_mutable_python_bytecode(tmp_path: Path) -> None:
    bootstrap = _load()
    root = tmp_path / "runtime"
    cache = root / "Lib" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "module.cpython-311.pyc").write_bytes(b"mutable")

    with pytest.raises(bootstrap.review_environment.C4Stage1ReviewEnvironmentError):
        bootstrap.review_environment.capture_c4_stage1_review_tree(
            root.resolve(),
            tree_role="review-complete-python-runtime",
            checkpoint=lambda: None,
        )
