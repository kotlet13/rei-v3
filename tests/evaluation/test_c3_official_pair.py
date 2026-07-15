from __future__ import annotations

import ast
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import py_compile
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.backend.rei.communication.model_registry import (
    load_racio_interpreter_model_registry,
)
from app.backend.rei.evaluation.c3_official_suite import (
    PROTOCOL_FREEZE_COMMIT,
    load_official_c3_suite_pair,
)
from app.backend.rei.ids import content_id
from app.backend.rei.models.provider import ProviderIdentity
from app.backend.rei.providers.ollama import (
    OllamaApiClient,
    OllamaRacioSettings,
    OllamaRuntimeModel,
)
from app.backend.rei.providers.ollama_interpreter import (
    OllamaInterpreterExecutionError,
    OllamaStructuredRacioInterpreterProvider,
)
import scripts.c3_racio_official_pair as pair_runner
import scripts.run_c3_racio_official_pair as bootstrap_runner


SOURCE_COMMIT = "a" * 40
REGISTRY_SHA256 = "b" * 64
LEDGER_SHA256 = "c" * 64


class _NoNetworkTransport:
    def request_json(self, **kwargs):
        del kwargs
        raise AssertionError("model/network access is forbidden in this test")


class _RejectingOfficialProvider:
    def __init__(self, provider: OllamaStructuredRacioInterpreterProvider) -> None:
        self._provider = provider

    @property
    def identity(self):
        return self._provider.identity

    def build_call_spec(self, packet):
        return self._provider.build_call_spec(packet)

    def execute(self, *args, **kwargs):
        del args, kwargs
        raise OllamaInterpreterExecutionError(
            "structured_output_invalid",
            "synthetic sanitized rejection",
            rejected_response_sha256="f" * 64,
            rejected_response_byte_count=17,
        )


def _profile(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REI_OLLAMA_NUM_CTX", "65536")
    monkeypatch.setenv("REI_OLLAMA_NUM_GPU", "999")
    return pair_runner.frozen_profile_from_environment()


def _candidate():
    return load_racio_interpreter_model_registry().require_candidate(
        model_id=pair_runner.OFFICIAL_MODEL_ID,
        digest=pair_runner.OFFICIAL_MODEL_DIGEST,
    )


def _provider_identity() -> ProviderIdentity:
    payload: dict[str, Any] = {
        "kind": "text_reasoner",
        "implementation": (
            "rei.providers.ollama_interpreter.OllamaStructuredRacioInterpreterProvider"
        ),
        "implementation_revision": "rei-ollama-racio-interpreter-c3-v6;ollama=test",
        "uses_model": True,
        "model": pair_runner.OFFICIAL_MODEL_ID,
        "model_revision": pair_runner.OFFICIAL_MODEL_DIGEST,
    }
    return ProviderIdentity(provider_id=content_id("provider", payload), **payload)


def _outcome(
    role: str,
    *,
    quality_gate_pass: bool,
    dispatches: int,
) -> pair_runner.C3OfficialSuiteOutcome:
    if role == "untouched_holdout":
        benchmark_id = "rei-c3-racio-interpreter-holdout-v1"
        child = "holdout"
    else:
        benchmark_id = "rei-c3-racio-interpreter-benchmark-v1"
        child = "regression"
    return pair_runner.C3OfficialSuiteOutcome(
        suite_role=role,
        benchmark_id=benchmark_id,
        run_id=f"test-{child}",
        child_directory=f"Docs/evals/semantic_lab_v1/test/{child}",
        child_provenance_sha256=("d" if child == "holdout" else "e") * 64,
        provider_case_attempt_count=32,
        api_generate_dispatch_count=dispatches,
        passed_case_count=32 if quality_gate_pass else 31,
        failure_count=0,
        quality_gate_pass=quality_gate_pass,
    )


def test_bootstrap_uses_only_stdlib_before_preflight() -> None:
    source = Path("scripts/run_c3_racio_official_pair.py").read_text(encoding="utf-8")
    preflight_call = source.index("source_commit = bootstrap_preflight()")
    project_import = source.index(
        'implementation = importlib.import_module("scripts.c3_racio_official_pair")'
    )
    assert preflight_call < project_import
    final_preflight_call = source.rindex("bootstrap_preflight()")
    assert source.index("site.main()") < final_preflight_call < project_import
    imported_roots: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.partition(".")[0])
    assert imported_roots <= {
        "__future__",
        "hashlib",
        "importlib",
        "os",
        "pathlib",
        "secrets",
        "stat",
        "subprocess",
        "sys",
        "tempfile",
        "types",
    }


def test_bootstrap_sanitizes_git_redirection_and_replacement_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_DIR", "elsewhere")
    monkeypatch.setenv("GIT_WORK_TREE", "elsewhere")
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", "elsewhere")
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", "elsewhere")
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/evil")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "evil")

    environment = bootstrap_runner._sanitized_git_environment()

    assert not (
        {
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_REPLACE_REF_BASE",
            "GIT_CONFIG_COUNT",
            "GIT_CONFIG_KEY_0",
            "GIT_CONFIG_VALUE_0",
        }
        & set(environment)
    )
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"


def test_git_execution_rejects_repository_shadow_before_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "git.exe").write_bytes(b"not executable")
    monkeypatch.setattr(bootstrap_runner, "ROOT", tmp_path)
    subprocess_calls = 0

    def forbidden_subprocess(*args, **kwargs):
        nonlocal subprocess_calls
        del args, kwargs
        subprocess_calls += 1
        raise AssertionError("shadowed Git must never execute")

    monkeypatch.setattr(bootstrap_runner.subprocess, "run", forbidden_subprocess)
    with pytest.raises(ValueError, match="Git shadow candidate"):
        bootstrap_runner._git_text({}, "status")
    assert subprocess_calls == 0


def test_trusted_windows_git_hash_pin_matches_local_executable() -> None:
    if os.name != "nt":
        pytest.skip("Windows Git pin")
    executable = bootstrap_runner._trusted_git_executable()
    assert executable == bootstrap_runner.TRUSTED_WINDOWS_GIT_EXECUTABLE
    assert executable == Path(r"C:\Program Files\Git\mingw64\bin\git.exe")
    assert (
        bootstrap_runner._bounded_regular_file_sha256(
            executable,
            maximum_bytes=64 * 1024 * 1024,
            label="test Git executable",
        )
        == bootstrap_runner.TRUSTED_WINDOWS_GIT_SHA256
    )


def _scoped_tree_record(path: str, payload: bytes) -> bytes:
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {len(payload)}\0".encode("ascii"))
    digest.update(payload)
    return f"100644 blob {digest.hexdigest()}\t{path}\0".encode("utf-8")


def _scoped_index_record(path: str, payload: bytes, *, stage: int = 0) -> bytes:
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {len(payload)}\0".encode("ascii"))
    digest.update(payload)
    return f"100644 {digest.hexdigest()} {stage}\t{path}\0".encode("utf-8")


def test_scoped_tree_z_parser_preserves_tabs_and_newlines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap_runner, "SCOPED_EXECUTION_PATHS", ("runtime",))
    monkeypatch.setattr(bootstrap_runner, "SCOPED_DIRECTORY_ROOTS", ("runtime",))
    path = "runtime/control\tcharacter\nmodule.py"

    assert bootstrap_runner._parse_scoped_ls_tree(
        _scoped_tree_record(path, b"source\n")
    ) == {
        path: (
            "100644",
            _scoped_index_record(path, b"source\n").split(b" ", 2)[1].decode("ascii"),
        )
    }


@pytest.mark.parametrize(
    "payload",
    (
        b"100644 blob " + b"a" * 40 + b"\truntime/module.py",
        b"120000 blob " + b"a" * 40 + b"\truntime/module.py\0",
        b"100644 blob bad\truntime/module.py\0",
        b"100644 blob "
        + b"a" * 40
        + b"\truntime/module.py\0"
        + b"100644 blob "
        + b"a" * 40
        + b"\truntime/module.py\0",
    ),
)
def test_scoped_tree_z_parser_rejects_malformed_records(
    payload: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap_runner, "SCOPED_EXECUTION_PATHS", ("runtime",))
    monkeypatch.setattr(bootstrap_runner, "SCOPED_DIRECTORY_ROOTS", ("runtime",))

    with pytest.raises(ValueError, match="Git tree inventory is malformed"):
        bootstrap_runner._parse_scoped_ls_tree(payload)


def test_scoped_index_z_parser_rejects_conflict_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap_runner, "SCOPED_EXECUTION_PATHS", ("runtime",))
    monkeypatch.setattr(bootstrap_runner, "SCOPED_DIRECTORY_ROOTS", ("runtime",))

    with pytest.raises(ValueError, match="Git index inventory is malformed"):
        bootstrap_runner._parse_scoped_ls_files(
            _scoped_index_record("runtime/module.py", b"source\n", stage=2)
        )


def _patch_scoped_tree(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root: Path,
    tracked_payload: bytes,
    index_tracked_payload: bytes | None = None,
) -> None:
    monkeypatch.setattr(bootstrap_runner, "ROOT", root)
    monkeypatch.setattr(bootstrap_runner, "SCOPED_EXECUTION_PATHS", ("runtime",))
    monkeypatch.setattr(bootstrap_runner, "SCOPED_DIRECTORY_ROOTS", ("runtime",))

    def fake_git_bytes(environment: dict[str, str], *args: str) -> bytes:
        assert environment == {"TEST": "isolated"}
        if args == (
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            "--abbrev=40",
            SOURCE_COMMIT,
            "--",
            "runtime",
        ):
            return _scoped_tree_record("runtime/module.py", tracked_payload)
        if args == (
            "ls-files",
            "--stage",
            "-z",
            "--full-name",
            "--",
            "runtime",
        ):
            return _scoped_index_record(
                "runtime/module.py",
                tracked_payload
                if index_tracked_payload is None
                else index_tracked_payload,
            )
        raise AssertionError(f"unexpected scoped Git args: {args}")

    monkeypatch.setattr(bootstrap_runner, "_git_bytes", fake_git_bytes)


def test_scoped_tree_rejects_worktree_bytes_hidden_from_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "module.py").write_bytes(b"locally replaced\n")
    _patch_scoped_tree(
        monkeypatch,
        root=tmp_path,
        tracked_payload=b"committed source\n",
    )

    with pytest.raises(ValueError, match="scoped source differs from HEAD"):
        bootstrap_runner._validate_worktree_against_head(
            SOURCE_COMMIT,
            environment={"TEST": "isolated"},
        )


def test_scoped_tree_rejects_index_that_differs_from_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    tracked_payload = b"committed source\n"
    (runtime / "module.py").write_bytes(tracked_payload)
    _patch_scoped_tree(
        monkeypatch,
        root=tmp_path,
        tracked_payload=tracked_payload,
        index_tracked_payload=b"staged replacement\n",
    )

    with pytest.raises(ValueError, match="Git index differs from HEAD"):
        bootstrap_runner._validate_worktree_against_head(
            SOURCE_COMMIT,
            environment={"TEST": "isolated"},
        )


def test_scoped_tree_rejects_ignored_import_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    tracked_payload = b"committed source\n"
    (runtime / "module.py").write_bytes(tracked_payload)
    collision = runtime / "module"
    collision.mkdir()
    (collision / "__init__.py").write_bytes(b"malicious package\n")
    _patch_scoped_tree(
        monkeypatch,
        root=tmp_path,
        tracked_payload=tracked_payload,
    )

    with pytest.raises(ValueError, match="filesystem inventory differs from HEAD"):
        bootstrap_runner._validate_worktree_against_head(
            SOURCE_COMMIT,
            environment={"TEST": "isolated"},
        )


def test_scoped_tree_rejects_ignored_extension_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    tracked_payload = b"committed source\n"
    (runtime / "module.py").write_bytes(tracked_payload)
    extension_suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    (runtime / f"module{extension_suffix}").write_bytes(b"extension collision")
    _patch_scoped_tree(
        monkeypatch,
        root=tmp_path,
        tracked_payload=tracked_payload,
    )

    with pytest.raises(ValueError, match="filesystem inventory differs from HEAD"):
        bootstrap_runner._validate_worktree_against_head(
            SOURCE_COMMIT,
            environment={"TEST": "isolated"},
        )


def test_scoped_tree_allows_only_isolated_pycache_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    tracked_payload = b"committed source\n"
    (runtime / "module.py").write_bytes(tracked_payload)
    pycache = runtime / "__pycache__"
    pycache.mkdir()
    (pycache / "module.cpython-311.pyc").write_bytes(b"ignored bytecode")
    _patch_scoped_tree(
        monkeypatch,
        root=tmp_path,
        tracked_payload=tracked_payload,
    )

    bootstrap_runner._validate_worktree_against_head(
        SOURCE_COMMIT,
        environment={"TEST": "isolated"},
    )


def test_isolated_project_import_ignores_matching_local_pyc(tmp_path: Path) -> None:
    source_path = tmp_path / "probe.py"
    malicious_source = "VALUE = 'pwned!'\n"
    trusted_source = "VALUE = 'source'\n"
    assert len(malicious_source) == len(trusted_source)
    source_path.write_text(malicious_source, encoding="utf-8")
    source_metadata = source_path.stat()
    cache_path = Path(importlib.util.cache_from_source(str(source_path)))
    py_compile.compile(str(source_path), cfile=str(cache_path), doraise=True)
    source_path.write_text(trusted_source, encoding="utf-8")
    os.utime(
        source_path,
        ns=(source_metadata.st_atime_ns, source_metadata.st_mtime_ns),
    )

    unisolated = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            f"import sys;sys.path.insert(0,{str(tmp_path)!r});import probe;print(probe.VALUE)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert unisolated.stdout.strip() == "pwned!"

    bootstrap_path = Path("scripts/run_c3_racio_official_pair.py").resolve()
    isolated_code = (
        "import importlib.util,sys;"
        f"p={str(bootstrap_path)!r};"
        "s=importlib.util.spec_from_file_location('_c3_bootstrap_test',p);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "prefix=m._isolate_project_bytecode();"
        f"sys.path.insert(0,{str(tmp_path)!r});"
        "import probe;"
        "print(probe.VALUE);"
        "print(int(sys.dont_write_bytecode));"
        "print(int(__import__('os').path.lexists(prefix)))"
    )
    isolated = subprocess.run(
        [sys.executable, "-I", "-S", "-c", isolated_code],
        check=True,
        capture_output=True,
        text=True,
    )
    assert isolated.stdout.splitlines() == ["source", "1", "0"]


def test_isolated_project_import_does_not_readd_repository_root() -> None:
    bootstrap_path = Path("scripts/run_c3_racio_official_pair.py").resolve()
    isolated_code = f"""
import importlib.util
import sys
from pathlib import Path

path = {str(bootstrap_path)!r}
spec = importlib.util.spec_from_file_location("_c3_bootstrap_probe", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.bootstrap_preflight = lambda: {SOURCE_COMMIT!r}
original_import = module.importlib.import_module

def intercepted_import(name, package=None):
    imported = original_import(name, package)
    if name == "scripts.c3_racio_official_pair":
        imported.main = lambda argv, bootstrap_source_commit: 0
    return imported

module.importlib.import_module = intercepted_import
print(module.main([]))
root = module.ROOT.resolve(strict=True)
print(int(any(module._path_entry_is_repository_root(item, root) for item in sys.path)))
"""
    isolated = subprocess.run(
        [sys.executable, "-I", "-S", "-c", isolated_code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert isolated.stdout.splitlines() == ["0", "0"]


@pytest.mark.parametrize("runner", (bootstrap_runner, pair_runner))
def test_git_reparse_gate_runs_before_any_git_subprocess(
    runner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(runner, "ROOT", repository)
    original_lstat = runner.os.lstat

    def fake_lstat(path):
        if Path(path) == repository / ".git":
            return SimpleNamespace(
                st_mode=stat.S_IFDIR,
                st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024),
            )
        return original_lstat(path)

    git_calls: list[tuple[str, ...]] = []

    def forbidden_git(*args, **kwargs):
        del kwargs
        git_calls.append(tuple(args))
        raise AssertionError("Git must not run before the local .git reparse gate")

    monkeypatch.setattr(runner.os, "lstat", fake_lstat)
    monkeypatch.setattr(runner, "_git_text", forbidden_git)
    operation = (
        runner.bootstrap_preflight
        if runner is bootstrap_runner
        else runner.scoped_source_commit
    )
    with pytest.raises(ValueError, match="Git directory"):
        operation()
    assert git_calls == []


def test_namespace_install_rejects_same_stem_package_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts_dir = tmp_path / "scripts"
    backend_dir = tmp_path / "app" / "backend"
    scripts_dir.mkdir()
    backend_dir.mkdir(parents=True)
    for module_name in (
        "run_c3_racio_official_pair",
        "c3_racio_official_pair",
        "run_racio_interpreter_benchmark",
    ):
        (scripts_dir / f"{module_name}.py").write_text("# trusted\n", encoding="utf-8")
    (scripts_dir / "c3_racio_official_pair").mkdir()
    monkeypatch.setattr(bootstrap_runner, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="import anchor is ambiguous"):
        bootstrap_runner._install_execution_namespaces()


def test_namespace_install_rejects_same_stem_extension_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts_dir = tmp_path / "scripts"
    backend_dir = tmp_path / "app" / "backend"
    scripts_dir.mkdir()
    backend_dir.mkdir(parents=True)
    for module_name in (
        "run_c3_racio_official_pair",
        "c3_racio_official_pair",
        "run_racio_interpreter_benchmark",
    ):
        (scripts_dir / f"{module_name}.py").write_text("# trusted\n", encoding="utf-8")
    extension_suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    (scripts_dir / f"c3_racio_official_pair{extension_suffix}").write_bytes(b"evil")
    monkeypatch.setattr(bootstrap_runner, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="import anchor is ambiguous"):
        bootstrap_runner._install_execution_namespaces()


def test_namespace_install_rejects_top_level_rei_module_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scripts_dir = tmp_path / "scripts"
    backend_dir = tmp_path / "app" / "backend"
    scripts_dir.mkdir()
    (backend_dir / "rei").mkdir(parents=True)
    for module_name in (
        "run_c3_racio_official_pair",
        "c3_racio_official_pair",
        "run_racio_interpreter_benchmark",
    ):
        (scripts_dir / f"{module_name}.py").write_text("# trusted\n", encoding="utf-8")
    (backend_dir / "rei.py").write_text("# collision\n", encoding="utf-8")
    monkeypatch.setattr(bootstrap_runner, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="app.backend.rei import anchor is ambiguous"):
        bootstrap_runner._install_execution_namespaces()


def test_bootstrap_failure_prevents_implementation_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imported: list[str] = []
    original_import = __import__

    def tracking_import(name, *args, **kwargs):
        if name == "scripts.c3_racio_official_pair":
            imported.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(
        bootstrap_runner,
        "bootstrap_preflight",
        lambda: (_ for _ in ()).throw(ValueError("blocked before import")),
    )
    monkeypatch.setattr(bootstrap_runner, "_require_isolated_startup", lambda: None)
    monkeypatch.setattr("builtins.__import__", tracking_import)
    with pytest.raises(ValueError, match="blocked before import"):
        bootstrap_runner.main([])
    assert imported == []


def test_bootstrap_requires_isolated_no_site_python() -> None:
    with pytest.raises(ValueError, match="requires Python flags -I -S"):
        bootstrap_runner._require_isolated_startup()


def test_bootstrap_accepts_only_exact_pushed_seal_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REI_OLLAMA_NUM_CTX", "65536")
    monkeypatch.setenv("REI_OLLAMA_NUM_GPU", "999")
    observed_environments: list[dict[str, str]] = []

    def fake_git_text(environment: dict[str, str], *args: str) -> str:
        observed_environments.append(environment)
        if args == ("rev-parse", "--show-toplevel"):
            return str(bootstrap_runner.ROOT)
        if args == ("rev-parse", "--absolute-git-dir"):
            return str(bootstrap_runner.ROOT / ".git")
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("rev-parse", "HEAD"):
            return SOURCE_COMMIT
        if args == ("rev-parse", "--verify", "origin/main"):
            return SOURCE_COMMIT
        if args == (
            "cat-file",
            "-e",
            f"{PROTOCOL_FREEZE_COMMIT}^{{commit}}",
        ):
            return ""
        if args == ("show", "-s", "--format=%P", SOURCE_COMMIT):
            return PROTOCOL_FREEZE_COMMIT
        if args == (
            "diff",
            "--name-only",
            "--no-renames",
            PROTOCOL_FREEZE_COMMIT,
            SOURCE_COMMIT,
            "--",
        ):
            return "\n".join(bootstrap_runner.EXPECTED_SEAL_DELTA)
        if args[:4] == (
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
        ):
            return ""
        raise AssertionError(f"unexpected bootstrap git args: {args}")

    monkeypatch.setattr(bootstrap_runner, "_git_text", fake_git_text)
    monkeypatch.setattr(
        bootstrap_runner,
        "_validate_worktree_against_head",
        lambda *args, **kwargs: None,
    )
    assert bootstrap_runner.bootstrap_preflight() == SOURCE_COMMIT
    assert observed_environments
    assert all(item["GIT_NO_REPLACE_OBJECTS"] == "1" for item in observed_environments)


def test_official_profile_is_exact_typed_and_has_no_cli_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile(monkeypatch)

    assert profile.model_id == "qwen3.6:35b"
    assert profile.model_digest == (
        "07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522"
    )
    assert profile.provider_revision == "rei-ollama-racio-interpreter-c3-v6"
    assert profile.seed == 314159
    assert profile.temperature == 0.0
    assert profile.num_ctx == 65536
    assert profile.num_gpu == 999
    assert profile.num_predict == 1536
    assert profile.timeout_seconds == 600.0
    assert profile.keep_alive == "10m"
    assert profile.base_url == "http://127.0.0.1:11434"
    assert profile.allow_remote is False
    assert profile.require_full_gpu is True
    assert profile.maximum_response_bytes == 4 * 1024 * 1024
    assert profile.retry_count == 0
    assert profile.fallback_mode == "none"
    assert pair_runner.parse_args([]).__dict__ == {}
    with pytest.raises(SystemExit):
        pair_runner.parse_args(["--model-id", "other"])


def test_official_profile_requires_explicit_gpu_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REI_OLLAMA_NUM_CTX", raising=False)
    monkeypatch.delenv("REI_OLLAMA_NUM_GPU", raising=False)
    with pytest.raises(ValueError, match="REI_OLLAMA_NUM_CTX"):
        pair_runner.frozen_profile_from_environment()

    monkeypatch.setenv("REI_OLLAMA_NUM_CTX", "65536")
    with pytest.raises(ValueError, match="REI_OLLAMA_NUM_GPU"):
        pair_runner.frozen_profile_from_environment()


@pytest.mark.parametrize(
    ("name", "value"),
    (
        ("REI_OLLAMA_NUM_CTX", "32768"),
        ("REI_OLLAMA_NUM_GPU", "0"),
        ("REI_OLLAMA_MODEL", "qwen3.5:27b"),
        ("REI_OLLAMA_BASE_URL", "http://example.invalid:11434"),
        ("REI_OLLAMA_SEED", "1"),
        ("REI_OLLAMA_NUM_PREDICT", "2048"),
        ("REI_OLLAMA_KEEP_ALIVE", "5m"),
        ("REI_OLLAMA_TEMPERATURE", "0.1"),
        ("REI_OLLAMA_TIMEOUT_SECONDS", "30"),
        ("REI_OLLAMA_REQUIRE_FULL_GPU", "false"),
    ),
)
def test_official_profile_rejects_environment_deviation(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv("REI_OLLAMA_NUM_CTX", "65536")
    monkeypatch.setenv("REI_OLLAMA_NUM_GPU", "999")
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        pair_runner.frozen_profile_from_environment()


def _patch_source_git(
    monkeypatch: pytest.MonkeyPatch,
    *,
    branch: str = "main",
    head: str = SOURCE_COMMIT,
    origin: str = SOURCE_COMMIT,
    parents: str = PROTOCOL_FREEZE_COMMIT,
    status: str = "",
    changed: tuple[str, ...] = pair_runner.EXPECTED_SEAL_DELTA,
) -> None:
    def fake_git_text(*args: str) -> str:
        if args == ("rev-parse", "--show-toplevel"):
            return str(pair_runner.ROOT)
        if args == ("rev-parse", "--absolute-git-dir"):
            return str(pair_runner.ROOT / ".git")
        if args == ("branch", "--show-current"):
            return branch
        if args == ("rev-parse", "HEAD"):
            return head
        if args == ("rev-parse", "--verify", "origin/main"):
            return origin
        if args == ("cat-file", "-e", f"{PROTOCOL_FREEZE_COMMIT}^{{commit}}"):
            return ""
        if args == ("show", "-s", "--format=%P", head):
            return parents
        if args == (
            "diff",
            "--name-only",
            "--no-renames",
            PROTOCOL_FREEZE_COMMIT,
            head,
            "--",
        ):
            return "\n".join(changed)
        if args[:4] == (
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
        ):
            return status
        raise AssertionError(f"unexpected git args: {args}")

    monkeypatch.setattr(pair_runner, "_git_text", fake_git_text)
    monkeypatch.setattr(
        pair_runner,
        "_validate_worktree_against_head",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        pair_runner,
        "_require_no_execution_import_collisions",
        lambda: None,
    )


def test_source_gate_accepts_only_clean_pushed_direct_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_source_git(monkeypatch)
    assert pair_runner.scoped_source_commit() == SOURCE_COMMIT


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"branch": "codex/feature"}, "directly on main"),
        ({"origin": "f" * 40}, "HEAD to equal origin/main"),
        ({"parents": "f" * 40}, "single direct child"),
        (
            {"parents": f"{PROTOCOL_FREEZE_COMMIT} {'f' * 40}"},
            "single direct child",
        ),
        ({"status": " M app/backend/rei/__init__.py\n"}, "must be clean"),
    ),
)
def test_source_gate_rejects_branch_origin_descendant_merge_and_dirt(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, str],
    message: str,
) -> None:
    _patch_source_git(monkeypatch, **overrides)
    with pytest.raises(ValueError, match=message):
        pair_runner.scoped_source_commit()


def test_source_gate_rejects_missing_protocol_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git_text(*args: str) -> str:
        if args == ("rev-parse", "--show-toplevel"):
            return str(pair_runner.ROOT)
        if args == ("rev-parse", "--absolute-git-dir"):
            return str(pair_runner.ROOT / ".git")
        if args == ("branch", "--show-current"):
            return "main"
        if args == ("rev-parse", "HEAD"):
            return SOURCE_COMMIT
        if args == ("rev-parse", "--verify", "origin/main"):
            return SOURCE_COMMIT
        raise subprocess.CalledProcessError(128, ["git", *args])

    monkeypatch.setattr(pair_runner, "_git_text", fake_git_text)
    with pytest.raises(ValueError, match="protocol-freeze commit is unavailable"):
        pair_runner.scoped_source_commit()


def test_source_gate_rejects_any_non_allowlisted_seal_delta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = tuple(
        sorted((*pair_runner.EXPECTED_SEAL_DELTA, "app/backend/rei/ids.py"))
    )
    _patch_source_git(monkeypatch, changed=changed)
    with pytest.raises(ValueError, match="delta differs from its allowlist"):
        pair_runner.scoped_source_commit()


def test_frozen_source_validation_rejects_protocol_fixture_tamper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holdout, _regression = load_official_c3_suite_pair()
    monkeypatch.setattr(pair_runner, "_git_bytes", lambda *args: b"tampered")
    with pytest.raises(ValueError, match="source fixture differs from pin"):
        pair_runner._validate_protocol_frozen_sources(
            source_commit=SOURCE_COMMIT,
            holdout=holdout,
        )


def test_counting_transport_counts_only_exact_generate_dispatch() -> None:
    class Delegate:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def request_json(
            self, *, method, url, payload, timeout_seconds, max_response_bytes
        ):
            del payload, timeout_seconds, max_response_bytes
            self.calls.append((method, url))
            return {"ok": True}

    delegate = Delegate()
    transport = pair_runner.CountingOllamaJsonTransport(delegate)
    common = {
        "payload": None,
        "timeout_seconds": 1.0,
        "max_response_bytes": 10,
    }
    transport.request_json(
        method="GET",
        url=f"{pair_runner.OFFICIAL_BASE_URL}/api/generate",
        **common,
    )
    transport.request_json(
        method="POST",
        url=f"{pair_runner.OFFICIAL_BASE_URL}/api/show",
        **common,
    )
    transport.request_json(
        method="POST",
        url=f"{pair_runner.OFFICIAL_BASE_URL}/api/generate",
        **common,
    )
    assert transport.api_generate_dispatch_count == 1
    assert len(delegate.calls) == 3


def test_output_reservation_is_create_only_and_precedes_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile(monkeypatch)
    holdout, regression = load_official_c3_suite_pair()
    candidate = _candidate()
    output_root = tmp_path / "official-pair"
    output_root.mkdir()
    monkeypatch.setattr(pair_runner, "ROOT", tmp_path)
    monkeypatch.setattr(pair_runner, "OFFICIAL_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(
        pair_runner, "scoped_source_commit", lambda **kwargs: SOURCE_COMMIT
    )
    monkeypatch.setattr(pair_runner, "frozen_profile_from_environment", lambda: profile)
    monkeypatch.setattr(
        pair_runner,
        "validate_frozen_contract",
        lambda **kwargs: (holdout, regression, candidate, REGISTRY_SHA256),
    )
    monkeypatch.setattr(pair_runner, "deterministic_results", lambda suite: ())
    construction_count = 0

    def forbidden_provider(**kwargs):
        nonlocal construction_count
        construction_count += 1
        raise AssertionError("provider construction must not occur")

    monkeypatch.setattr(pair_runner, "build_official_provider", forbidden_provider)
    with pytest.raises(FileExistsError, match="reruns are forbidden"):
        pair_runner.run_official_pair(bootstrap_source_commit=SOURCE_COMMIT)
    assert construction_count == 0


def test_output_target_cannot_escape_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(pair_runner, "ROOT", repository)
    monkeypatch.setattr(pair_runner, "OFFICIAL_OUTPUT_ROOT", outside / "pair")

    with pytest.raises(ValueError, match="inside the repository"):
        pair_runner._resolved_official_output_target()


def test_output_reservation_detects_directory_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "pair"
    target.mkdir()
    monkeypatch.setattr(pair_runner, "ROOT", tmp_path)
    monkeypatch.setattr(pair_runner, "OFFICIAL_OUTPUT_ROOT", target)
    metadata = target.stat()
    reservation = pair_runner.ReservedOutputRoot(
        path=target,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )
    displaced = tmp_path / "displaced"
    target.rename(displaced)
    target.mkdir()

    with pytest.raises(ValueError, match="reservation identity changed"):
        reservation.validate()


@pytest.mark.skipif(os.name != "nt", reason="Windows mandatory-share lock regression")
def test_windows_directory_anchor_blocks_concurrent_staging_swap_and_external_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "reserved"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    root_anchor = pair_runner.DirectoryAnchor.open(root)
    staging_anchor = root_anchor.create_child(".holdout.staging-test")
    try:
        with pytest.raises(OSError):
            os.rename(staging_anchor.path, outside / "redirected")
        assert staging_anchor.path.is_dir()
        assert list(outside.iterdir()) == []

        pair_runner._write_anchored_atomic(
            parent=staging_anchor,
            destination_name="evidence.json",
            payload=b"{}\n",
            label="test evidence",
        )
        pair_runner._publish_anchored_directory(
            parent=root_anchor,
            source=staging_anchor,
            destination_name="holdout",
        )
        assert (root / "holdout" / "evidence.json").read_bytes() == b"{}\n"
        assert list(outside.iterdir()) == []
    finally:
        staging_anchor.close()
        root_anchor.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows no-replace handle regression")
def test_windows_atomic_file_publication_preserves_racing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "reserved"
    root.mkdir()
    root_anchor = pair_runner.DirectoryAnchor.open(root)
    original_rename = pair_runner._rename_windows_handle_no_replace

    def collide(handle: int, destination: Path) -> None:
        destination.write_bytes(b"sentinel")
        original_rename(handle, destination)

    monkeypatch.setattr(pair_runner, "_rename_windows_handle_no_replace", collide)
    try:
        with pytest.raises(FileExistsError):
            pair_runner._write_anchored_atomic(
                parent=root_anchor,
                destination_name="evidence.json",
                payload=b"replacement",
                label="test evidence",
            )
        assert (root / "evidence.json").read_bytes() == b"sentinel"
    finally:
        root_anchor.close()


def test_runner_orders_baselines_reservation_one_provider_and_both_suites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile(monkeypatch)
    holdout, regression = load_official_c3_suite_pair()
    candidate = _candidate()
    identity = _provider_identity()
    provider = SimpleNamespace(identity=identity)
    transport = SimpleNamespace(api_generate_dispatch_count=0)
    events: list[str] = []

    monkeypatch.setattr(
        pair_runner, "scoped_source_commit", lambda **kwargs: SOURCE_COMMIT
    )
    monkeypatch.setattr(pair_runner, "frozen_profile_from_environment", lambda: profile)
    monkeypatch.setattr(
        pair_runner,
        "validate_frozen_contract",
        lambda **kwargs: (holdout, regression, candidate, REGISTRY_SHA256),
    )

    def fake_baseline(suite):
        events.append(f"baseline:{suite.manifest.benchmark_id}")
        return ()

    monkeypatch.setattr(pair_runner, "deterministic_results", fake_baseline)

    def fake_reserve(**kwargs):
        events.append("reserve")
        return SimpleNamespace(close=lambda: None), None, LEDGER_SHA256

    monkeypatch.setattr(pair_runner, "reserve_output_root", fake_reserve)
    provider_count = 0

    def fake_provider(**kwargs):
        nonlocal provider_count
        provider_count += 1
        events.append("provider")
        return provider, transport

    monkeypatch.setattr(pair_runner, "build_official_provider", fake_provider)
    monkeypatch.setattr(pair_runner, "verify_execution_state", lambda **kwargs: None)

    def fake_execute(**kwargs):
        role = kwargs["suite_role"]
        events.append(f"suite:{role}")
        return _outcome(
            role,
            quality_gate_pass=(role == "frozen_regression"),
            dispatches=32,
        )

    monkeypatch.setattr(pair_runner, "execute_and_publish_suite", fake_execute)
    sentinel = object()

    def fake_final(**kwargs):
        events.append("final")
        assert tuple(item.suite_role for item in kwargs["outcomes"]) == (
            "untouched_holdout",
            "frozen_regression",
        )
        return sentinel

    monkeypatch.setattr(pair_runner, "write_final_pair_provenance", fake_final)

    assert (
        pair_runner.run_official_pair(bootstrap_source_commit=SOURCE_COMMIT) is sentinel
    )
    assert provider_count == 1
    assert events == [
        "baseline:rei-c3-racio-interpreter-holdout-v1",
        "baseline:rei-c3-racio-interpreter-benchmark-v1",
        "reserve",
        "provider",
        "suite:untouched_holdout",
        "suite:frozen_regression",
        "final",
    ]


def test_suite_publication_uses_hidden_staging_then_atomic_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "pair"
    output_root.mkdir()
    monkeypatch.setattr(pair_runner, "ROOT", tmp_path)
    monkeypatch.setattr(pair_runner, "OFFICIAL_OUTPUT_ROOT", output_root)
    holdout, _regression = load_official_c3_suite_pair()
    candidate = _candidate()
    transport = SimpleNamespace(api_generate_dispatch_count=0)
    output_metadata = output_root.stat()
    reservation = pair_runner.ReservedOutputRoot(
        path=output_root,
        device=output_metadata.st_dev,
        inode=output_metadata.st_ino,
    )

    def fake_execute(**kwargs):
        transport.api_generate_dispatch_count = 7
        return ()

    monkeypatch.setattr(pair_runner, "execute_provider_suite", fake_execute)
    monkeypatch.setattr(
        pair_runner,
        "evaluate_c3_benchmark_run",
        lambda **kwargs: SimpleNamespace(
            passed_case_count=12,
            quality_gate_pass=False,
        ),
    )
    monkeypatch.setattr(pair_runner, "verify_execution_state", lambda **kwargs: None)

    monkeypatch.setattr(
        pair_runner,
        "_official_suite_artifact_payloads",
        lambda **kwargs: ((), candidate),
    )
    outcome = pair_runner.execute_and_publish_suite(
        output_root=reservation,
        suite_role="untouched_holdout",
        child_name="holdout",
        run_id="test-holdout",
        manifest_path=pair_runner.HOLDOUT_MANIFEST_PATH,
        suite=holdout,
        baseline_results=(),
        provider=SimpleNamespace(),
        transport=transport,
        candidate=candidate,
        source_commit=SOURCE_COMMIT,
        registry_sha256=REGISTRY_SHA256,
    )

    assert outcome.api_generate_dispatch_count == 7
    assert outcome.quality_gate_pass is False
    assert (output_root / "holdout" / "suite_outcome.json").is_file()
    assert not any(
        item.name.startswith(".holdout.staging-") for item in output_root.iterdir()
    )
    reservation.close()


def test_final_pair_provenance_rejects_unclosed_disk_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile(monkeypatch)
    output_root = tmp_path / "pair"
    output_root.mkdir()
    monkeypatch.setattr(pair_runner, "ROOT", tmp_path)
    monkeypatch.setattr(pair_runner, "OFFICIAL_OUTPUT_ROOT", output_root)
    (output_root / "attempt_ledger.json").write_text("{}\n", encoding="utf-8")
    (output_root / "holdout").mkdir()
    (output_root / "regression").mkdir()
    metadata = output_root.stat()
    reservation = pair_runner.ReservedOutputRoot(
        path=output_root,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )
    outcomes = (
        _outcome("untouched_holdout", quality_gate_pass=False, dispatches=30),
        _outcome("frozen_regression", quality_gate_pass=True, dispatches=31),
    )

    with pytest.raises(ValueError, match="attempt ledger hash differs"):
        pair_runner.write_final_pair_provenance(
            output_root=reservation,
            source_commit=SOURCE_COMMIT,
            attempt_ledger_sha256=LEDGER_SHA256,
            profile=profile,
            registry_sha256=REGISTRY_SHA256,
            candidate=_candidate(),
            provider_identity=_provider_identity(),
            outcomes=outcomes,
        )
    assert not (output_root / "pair_provenance.json").exists()


def test_disk_backed_pair_closure_recomputes_both_suites_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile(monkeypatch)
    holdout, regression = load_official_c3_suite_pair()
    candidate = _candidate()
    transport = pair_runner.CountingOllamaJsonTransport(_NoNetworkTransport())
    client = OllamaApiClient(
        base_url=profile.base_url,
        allow_remote=False,
        transport=transport,
    )
    settings = OllamaRacioSettings(
        model=profile.model_id,
        seed=profile.seed,
        temperature=profile.temperature,
        num_ctx=profile.num_ctx,
        num_gpu=profile.num_gpu,
        num_predict=profile.num_predict,
        timeout_seconds=profile.timeout_seconds,
        keep_alive=profile.keep_alive,
        require_full_gpu=True,
    )
    runtime = OllamaRuntimeModel(
        server_version="test-server",
        model=profile.model_id,
        digest=profile.model_digest,
        size_bytes=1,
        quantization_level="test",
        context_length=262144,
        capabilities=("completion", "vision"),
    )
    canonical_provider = OllamaStructuredRacioInterpreterProvider(
        client=client,
        runtime=runtime,
        settings=settings,
        expected_digest=profile.model_digest,
    )
    provider = _RejectingOfficialProvider(canonical_provider)
    output_target = tmp_path / "official-pair"
    monkeypatch.setattr(pair_runner, "OFFICIAL_OUTPUT_ROOT", output_target)
    monkeypatch.setattr(pair_runner, "verify_execution_state", lambda **kwargs: None)
    descriptors = pair_runner._suite_descriptors(holdout, regression)
    reservation, _ledger, ledger_sha256 = pair_runner.reserve_output_root(
        source_commit=SOURCE_COMMIT,
        profile=profile,
        descriptors=descriptors,
    )
    registry_sha256 = pair_runner._regular_file_sha256(
        pair_runner.RACIO_INTERPRETER_MODEL_REGISTRY_PATH,
        maximum_bytes=2 * 1024 * 1024,
        label="test registry",
    )
    holdout_outcome = pair_runner.execute_and_publish_suite(
        output_root=reservation,
        suite_role="untouched_holdout",
        child_name="holdout",
        run_id="test-official-holdout",
        manifest_path=pair_runner.HOLDOUT_MANIFEST_PATH,
        suite=holdout,
        baseline_results=pair_runner.deterministic_results(holdout),
        provider=provider,
        transport=transport,
        candidate=candidate,
        source_commit=SOURCE_COMMIT,
        registry_sha256=registry_sha256,
    )
    regression_outcome = pair_runner.execute_and_publish_suite(
        output_root=reservation,
        suite_role="frozen_regression",
        child_name="regression",
        run_id="test-official-regression",
        manifest_path=pair_runner.MANIFEST_PATH,
        suite=regression,
        baseline_results=pair_runner.deterministic_results(regression),
        provider=provider,
        transport=transport,
        candidate=candidate,
        source_commit=SOURCE_COMMIT,
        registry_sha256=registry_sha256,
    )

    provenance = pair_runner.write_final_pair_provenance(
        output_root=reservation,
        source_commit=SOURCE_COMMIT,
        attempt_ledger_sha256=ledger_sha256,
        profile=profile,
        registry_sha256=registry_sha256,
        candidate=candidate,
        provider_identity=provider.identity,
        outcomes=(holdout_outcome, regression_outcome),
    )

    assert provenance.api_generate_dispatch_count == 0
    assert provenance.provider_case_attempt_count == 64
    assert provenance.quality_gate_pass is False
    assert (output_target / "pair_provenance.json").is_file()
    assert transport.api_generate_dispatch_count == 0


def test_final_pair_provenance_closes_order_dispatches_and_is_last_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile(monkeypatch)
    output_root = tmp_path / "pair"
    output_root.mkdir()
    monkeypatch.setattr(pair_runner, "ROOT", tmp_path)
    monkeypatch.setattr(pair_runner, "OFFICIAL_OUTPUT_ROOT", output_root)
    metadata = output_root.stat()
    reservation = pair_runner.ReservedOutputRoot(
        path=output_root,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )
    (output_root / "attempt_ledger.json").write_text("{}\n", encoding="utf-8")
    (output_root / "holdout").mkdir()
    (output_root / "regression").mkdir()
    outcomes = (
        _outcome("untouched_holdout", quality_gate_pass=False, dispatches=30),
        _outcome("frozen_regression", quality_gate_pass=True, dispatches=31),
    )
    closure_calls = 0

    def count_closure(**kwargs):
        nonlocal closure_calls
        del kwargs
        closure_calls += 1

    monkeypatch.setattr(
        pair_runner,
        "_validate_pair_evidence_closure",
        count_closure,
    )
    monkeypatch.setattr(pair_runner, "verify_execution_state", lambda **kwargs: None)

    provenance = pair_runner.write_final_pair_provenance(
        output_root=reservation,
        source_commit=SOURCE_COMMIT,
        attempt_ledger_sha256=LEDGER_SHA256,
        profile=profile,
        registry_sha256=REGISTRY_SHA256,
        candidate=_candidate(),
        provider_identity=_provider_identity(),
        outcomes=outcomes,
    )

    assert provenance.provider_case_attempt_count == 64
    assert provenance.api_generate_dispatch_count == 61
    assert provenance.quality_gate_pass is False
    assert closure_calls == 2
    final_path = output_root / "pair_provenance.json"
    assert final_path.is_file()
    assert not any(item.name.startswith(".") for item in output_root.iterdir())
    recorded = json.loads(final_path.read_text(encoding="utf-8"))
    assert [item["suite_role"] for item in recorded["suite_outcomes"]] == [
        "untouched_holdout",
        "frozen_regression",
    ]
    assert recorded["api_generate_dispatch_count"] == 61

    reversed_payload = provenance.model_dump(mode="python")
    reversed_payload["suite_outcomes"] = tuple(reversed(outcomes))
    with pytest.raises(ValidationError, match="suite order differs"):
        pair_runner.C3OfficialPairProvenance.model_validate(reversed_payload)
