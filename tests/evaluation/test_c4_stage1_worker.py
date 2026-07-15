from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
WORKER_PATH = ROOT / "scripts" / "run_rei_c4_stage1_worker.py"
MODEL_ROOTS = {"accelerate", "diffusers", "safetensors", "torch", "transformers"}


def _model_modules() -> set[str]:
    return {name for name in sys.modules if name.split(".", 1)[0] in MODEL_ROOTS}


def _load_worker(*, capability: object | None = None) -> ModuleType:
    name = f"_rei_c4_stage1_worker_test_{id(capability)}"
    spec = importlib.util.spec_from_file_location(name, WORKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    if capability is not None:
        module.__dict__["_REI_C4_STAGE1_BOOTSTRAP_CAPABILITY"] = capability
    spec.loader.exec_module(module)
    return module


def test_direct_worker_is_inert_and_imports_no_rei_or_model_packages() -> None:
    rei_before = {
        name for name in sys.modules if name == "rei" or name.startswith("rei.")
    }
    model_before = _model_modules()
    worker = _load_worker()

    assert worker.main(["--request", r"C:\sensitive\request.json"]) == 64
    assert {
        name for name in sys.modules if name == "rei" or name.startswith("rei.")
    } == rei_before
    assert _model_modules() == model_before
    with pytest.raises(worker.C4Stage1WorkerAuthorizationError):
        worker.run_authorized(object())
    assert _model_modules() == model_before


def test_authorized_worker_consumes_exact_capability_once_and_stages_create_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = object()
    worker = _load_worker(capability=capability)
    staging = tmp_path.resolve()
    request = object()
    direct = b"direct-exact-bytes"
    staged = b"staged-exact-bytes"
    result = SimpleNamespace(canonical_json_bytes=lambda: b'{"status":"succeeded"}')
    execution = SimpleNamespace(
        worker_result=result,
        output=SimpleNamespace(direct_png=direct, staged_png=staged),
    )
    authorization = SimpleNamespace(_capability=capability)
    monkeypatch.setattr(
        worker,
        "_validate_authorized_lineage",
        lambda value: (request, b"source", tmp_path, staging),
    )
    monkeypatch.setattr(worker, "_execute", lambda *args: execution)

    assert worker.run_authorized(authorization) == 0
    assert (staging / "direct.png").read_bytes() == direct
    assert (staging / "staged.png").read_bytes() == staged
    assert (staging / "worker_result.json").read_bytes() == b'{"status":"succeeded"}'
    with pytest.raises(worker.C4Stage1WorkerAuthorizationError):
        worker.run_authorized(authorization)


def test_worker_rejects_forged_capability_and_nonfresh_staging(
    tmp_path: Path,
) -> None:
    capability = object()
    worker = _load_worker(capability=capability)
    with pytest.raises(worker.C4Stage1WorkerAuthorizationError):
        worker.run_authorized(SimpleNamespace(_capability=object()))

    marker = tmp_path / "user-owned.txt"
    marker.write_text("user-owned", encoding="utf-8")
    with pytest.raises(worker.C4Stage1WorkerAuthorizationError):
        worker._fresh_staging_root(tmp_path.resolve())
    assert marker.read_text(encoding="utf-8") == "user-owned"


def test_worker_failure_is_path_free_and_base_exception_is_reraised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = object()
    worker = _load_worker(capability=capability)
    staging = tmp_path.resolve()
    authorization = SimpleNamespace(_capability=capability)
    monkeypatch.setattr(
        worker,
        "_validate_authorized_lineage",
        lambda value: (object(), b"source", tmp_path, staging),
    )

    def fail(*args: object) -> object:
        raise RuntimeError("secret-token at C:/sensitive/snapshot")

    monkeypatch.setattr(worker, "_execute", fail)
    assert worker.run_authorized(authorization) == 20
    assert tuple(staging.iterdir()) == ()

    second_capability = object()
    second = _load_worker(capability=second_capability)
    second_authorization = SimpleNamespace(_capability=second_capability)
    monkeypatch.setattr(
        second,
        "_validate_authorized_lineage",
        lambda value: (object(), b"source", tmp_path, staging),
    )

    def interrupt(*args: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(second, "_execute", interrupt)
    with pytest.raises(KeyboardInterrupt):
        second.run_authorized(second_authorization)
    assert tuple(staging.iterdir()) == ()


def test_worker_stable_reader_rejects_hardlinks_and_symlinks(tmp_path: Path) -> None:
    worker = _load_worker()
    original = tmp_path / "original.bin"
    original.write_bytes(b"exact")
    hardlink = tmp_path / "hardlink.bin"
    hardlink.hardlink_to(original)
    with pytest.raises(worker.C4Stage1WorkerAuthorizationError):
        worker._stable_read(original.resolve(), maximum_bytes=32)

    symlink = tmp_path / "symlink.bin"
    try:
        symlink.symlink_to(hardlink)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(worker.C4Stage1WorkerAuthorizationError):
        worker._stable_read(symlink.absolute(), maximum_bytes=32)
