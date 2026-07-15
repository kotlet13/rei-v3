from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_PATH = ROOT / "scripts" / "run_rei_c4_stage1_bootstrap.py"
MODEL_ROOTS = {"accelerate", "diffusers", "safetensors", "torch", "transformers"}


def _load_bootstrap() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"_rei_c4_stage1_bootstrap_test_{id(object())}", BOOTSTRAP_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _model_modules() -> set[str]:
    return {name for name in sys.modules if name.split(".", 1)[0] in MODEL_ROOTS}


def _envelope(
    bootstrap: ModuleType,
    *,
    argv: list[str],
    environment: dict[str, str],
    cwd: str,
) -> dict[str, object]:
    command = ("python", "-I", "-S", "bootstrap.py", *argv)
    process = {
        "workload_id": "workload_exact",
        "command_identity": "command_exact",
        "working_directory_identity": "cwd_exact",
        "environment_identity": "environment_exact",
        "argument_count": len(command) - 1,
    }
    body = {
        "schema_version": "rei-c4-stage1-launch-envelope-v1",
        "prepared_attempt_id": "prepared_exact",
        "confirmed_prepared_attempt_id": "prepared_exact",
        "exact_prepared_attempt_confirmation": True,
        "interpreter_isolation_flags": ["-I", "-S"],
        "argument_count": len(command) - 1,
        "raw_argv_commitment_sha256": bootstrap._runtime_commitment(
            "raw-argv", command
        ),
        "raw_environment_commitment_sha256": bootstrap._runtime_commitment(
            "raw-environment", sorted(environment.items())
        ),
        "raw_working_directory_commitment_sha256": bootstrap._runtime_commitment(
            "raw-working-directory", cwd
        ),
        "process_request": process,
        "workload_id": process["workload_id"],
        "command_identity": process["command_identity"],
        "working_directory_identity": process["working_directory_identity"],
        "environment_identity": process["environment_identity"],
        "cuda_device": {
            "status": "resolved",
            "logical_device_index": 0,
            "physical_gpu_uuid": "GPU-exact",
        },
        "bootstrap_cold_verification_required": True,
        "worker_cold_verification_required": True,
        "model_calls_before_envelope": 0,
        "semantic_authority_granted": False,
        "production_authority_granted": False,
        "local_paths_stored": False,
        "raw_argv_stored": False,
        "raw_environment_stored": False,
        "raw_working_directory_stored": False,
    }
    return {
        "launch_envelope_id": bootstrap._content_id("c4_stage1_launch_envelope", body),
        "launch_envelope_sha256": hashlib.sha256(
            bootstrap._canonical_json_bytes(body)
        ).hexdigest(),
        **body,
    }


def _descriptor(
    bootstrap: ModuleType,
    *,
    run_id: str,
    relative_path: str,
    payload: bytes,
) -> dict[str, object]:
    body = {
        "run_id": run_id,
        "relative_path": relative_path,
        "content_sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }
    return {
        "schema_version": "rei-native-stored-artifact-v1",
        "storage_id": bootstrap._content_id("stored", body),
        **body,
    }


def test_bootstrap_import_is_stdlib_only_and_direct_failure_is_fixed() -> None:
    rei_before = {
        name for name in sys.modules if name == "rei" or name.startswith("rei.")
    }
    model_before = _model_modules()
    bootstrap = _load_bootstrap()

    assert bootstrap.main([]) == 64
    assert {
        name for name in sys.modules if name == "rei" or name.startswith("rei.")
    } == rei_before
    assert _model_modules() == model_before


def test_envelope_binds_exact_argv_environment_and_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load_bootstrap()
    argv = ["--launch-envelope", r"C:\exact\envelope.json"]
    environment = {"CUDA_VISIBLE_DEVICES": "GPU-exact", "PYTHONUTF8": "1"}
    cwd = r"C:\exact\repo"
    monkeypatch.setattr(
        bootstrap,
        "_raw_command",
        lambda value: ("python", "-I", "-S", "bootstrap.py", *value),
    )
    envelope = _envelope(bootstrap, argv=argv, environment=environment, cwd=cwd)
    bootstrap._validate_envelope_shape(
        envelope, argv=argv, environment=environment, cwd=cwd
    )

    for changed_argv, changed_environment, changed_cwd in (
        (argv + ["--extra", "value"], environment, cwd),
        (argv, {**environment, "EXTRA": "value"}, cwd),
        (argv, environment, cwd + "-changed"),
    ):
        with pytest.raises(bootstrap.C4Stage1BootstrapError):
            bootstrap._validate_envelope_shape(
                envelope,
                argv=changed_argv,
                environment=changed_environment,
                cwd=changed_cwd,
            )

    envelope["source_sha256"] = "0" * 64
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._validate_envelope_shape(
            envelope, argv=argv, environment=environment, cwd=cwd
        )


def test_stable_reads_and_runtime_inventory_reject_links_and_customization(
    tmp_path: Path,
) -> None:
    bootstrap = _load_bootstrap()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "package.py").write_bytes(b"exact-runtime")
    pth = runtime / "never-execute.pth"
    marker = tmp_path / "executed.txt"
    pth.write_text(
        f"import pathlib; pathlib.Path({str(marker)!r}).write_text('bad')\n",
        encoding="utf-8",
    )
    first = bootstrap._capture_runtime_tree(runtime.resolve(), tree_role="worker-venv")
    assert first["pth_file_count"] == 1
    assert not marker.exists()

    (runtime / "package.py").write_bytes(b"tampered-runtime")
    second = bootstrap._capture_runtime_tree(runtime.resolve(), tree_role="worker-venv")
    assert second["tree_content_sha256"] != first["tree_content_sha256"]

    (runtime / "sitecustomize.py").write_bytes(b"raise SystemExit")
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._capture_runtime_tree(runtime.resolve(), tree_role="worker-venv")
    (runtime / "sitecustomize.py").unlink()

    hardlink = runtime / "hardlink.py"
    hardlink.hardlink_to(runtime / "package.py")
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._capture_runtime_tree(runtime.resolve(), tree_role="worker-venv")

    symlink = runtime / "symlink.py"
    try:
        symlink.symlink_to(pth)
    except OSError:
        return
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._capture_runtime_tree(runtime.resolve(), tree_role="worker-venv")


def test_script_pins_reject_tampered_bootstrap_or_worker(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    repository = tmp_path / "repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    bootstrap_bytes = b"# exact bootstrap\n"
    worker_bytes = b"# exact worker\n"
    (scripts / "run_rei_c4_stage1_bootstrap.py").write_bytes(bootstrap_bytes)
    (scripts / "run_rei_c4_stage1_worker.py").write_bytes(worker_bytes)
    policy = {
        "bootstrap_script_sha256": hashlib.sha256(bootstrap_bytes).hexdigest(),
        "bootstrap_script_size_bytes": len(bootstrap_bytes),
        "worker_script_sha256": hashlib.sha256(worker_bytes).hexdigest(),
        "worker_script_size_bytes": len(worker_bytes),
    }
    envelope = dict(policy)
    assert bootstrap._verify_script_pins(
        repository.resolve(), policy=policy, envelope=envelope
    ) == (bootstrap_bytes, worker_bytes)

    (scripts / "run_rei_c4_stage1_worker.py").write_bytes(b"# tampered\n")
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._verify_script_pins(
            repository.resolve(), policy=policy, envelope=envelope
        )


def test_source_and_snapshot_are_exact_byte_pinned(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    source = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + (1024).to_bytes(4, "big")
        + (768).to_bytes(4, "big")
    )
    request_source = {
        "render_request": {
            "source_image": {
                "content_sha256": hashlib.sha256(source).hexdigest(),
                "width": 1024,
                "height": 768,
            }
        }
    }
    bootstrap._verify_source_png(source, request_source)
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._verify_source_png(source + b"substitution", request_source)

    run_id = "run_exact"
    run_root = tmp_path / run_id
    diagnostics = run_root / "diagnostics"
    diagnostics.mkdir(parents=True)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    model_bytes = b"exact-model-snapshot-bytes"
    (snapshot / "model.bin").write_bytes(model_bytes)
    manifest = {
        "schema_version": "rei-diffusers-snapshot-manifest-v1",
        "repo_id": "repo/exact",
        "revision": "f" * 40,
        "files": [
            {
                "relative_path": "model.bin",
                "sha256": hashlib.sha256(model_bytes).hexdigest(),
                "size_bytes": len(model_bytes),
            }
        ],
    }
    manifest_bytes = bootstrap._canonical_json_bytes(manifest)
    (snapshot / ".rei_snapshot_manifest.json").write_bytes(manifest_bytes)
    committed_relative = "diagnostics/primary.snapshot-manifest.json"
    (run_root / committed_relative).write_bytes(manifest_bytes)
    descriptor = _descriptor(
        bootstrap,
        run_id=run_id,
        relative_path=committed_relative,
        payload=manifest_bytes,
    )
    prepared = {"artifact_inventory_before_anchor": [descriptor]}
    request = {
        "editor_spec": {
            "editor_role": "primary",
            "repo_id": "repo/exact",
            "revision": "f" * 40,
            "snapshot_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "snapshot_file_count": 1,
            "snapshot_total_bytes": len(model_bytes),
        }
    }
    bootstrap._verify_snapshot(
        snapshot.resolve(),
        request=request,
        prepared=prepared,
        run_id=run_id,
        run_root=run_root.resolve(),
    )
    (snapshot / "model.bin").write_bytes(b"tampered-model-snapshot")
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._verify_snapshot(
            snapshot.resolve(),
            request=request,
            prepared=prepared,
            run_id=run_id,
            run_root=run_root.resolve(),
        )


def test_descriptor_rejects_forged_id_and_hardlinked_payload(tmp_path: Path) -> None:
    bootstrap = _load_bootstrap()
    run_id = "run_exact"
    run_root = tmp_path / run_id
    diagnostics = run_root / "diagnostics"
    diagnostics.mkdir(parents=True)
    relative = "diagnostics/exact.json"
    payload = b"{}"
    path = run_root / relative
    path.write_bytes(payload)
    descriptor = _descriptor(
        bootstrap,
        run_id=run_id,
        relative_path=relative,
        payload=payload,
    )
    bootstrap._validate_descriptor(
        descriptor, run_id=run_id, run_root=run_root.resolve()
    )
    forged = dict(descriptor)
    forged["storage_id"] = "stored_" + "0" * 32
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._validate_descriptor(
            forged, run_id=run_id, run_root=run_root.resolve()
        )

    hardlink = diagnostics / "alias.json"
    hardlink.hardlink_to(path)
    with pytest.raises(bootstrap.C4Stage1BootstrapError):
        bootstrap._validate_descriptor(
            descriptor, run_id=run_id, run_root=run_root.resolve()
        )
