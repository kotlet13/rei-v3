from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
import struct
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from rei.emocio.dinov2_encoder import (
    DINOV2_BASE_DIMENSIONS,
    dinov2_base_encoding_spec,
    dinov2_base_provider_identity,
)
from rei.emocio.vector_encoding import canonical_l2_float32_le_vector
from rei.evaluation import c4_stage1_dino as dino_bridge
from rei.evaluation import c4_stage1_dino_run as dino_run
from rei.evaluation import c4_stage1_run as render_run
from rei.evaluation.c4_stage1_attempt import build_c4_stage1_worker_environment
from rei.evaluation.c4_stage1_dino_run import (
    C4_STAGE1_DINO_ANCHOR_PATH,
    C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH,
    C4Stage1DinoSemanticChildRequest,
    C4Stage1DinoRunError,
    _ChildExecution,
    _child_process_request,
    _preflight,
    _run_with_child_executor,
    _verify_actual_repository_root,
    _verify_external_staging_parent,
    _worker_base_runtime_root,
    cold_verify_c4_stage1_dino_collapse_check,
    verify_c4_stage1_dino_snapshot,
)
from rei.evaluation.c4_stage1_screen import (
    C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
)
from rei.evaluation.process_tree_runner import (
    PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
    BoundedProcessRequest,
    BoundedProcessTreeRunner,
)
from rei.ids import canonical_json_bytes, content_id
from rei.models.provider import ProviderCallRecord, ProviderCallSpec
from rei.persistence.artifacts import FileArtifactStore
from rei.providers.protocols import StoredArtifact, VerifiedImageEncoding
from tests.evaluation.test_c4_stage1_run import (
    _Harness,
    _minimal_cold_envelope,
    _prepared_store,
    _process_record,
    _run,
)


_MODEL_ROOTS = {"accelerate", "diffusers", "safetensors", "torch", "transformers"}
_ROOT = Path(__file__).resolve().parents[2]


def _load_dino_bootstrap() -> ModuleType:
    path = _ROOT / C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH
    spec = importlib.util.spec_from_file_location(
        f"_c4_dino_bootstrap_test_{id(object())}",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _basis(index: int) -> bytes:
    values = tuple(1.0 if position == index else 0.0 for position in range(768))
    payload, _, _ = canonical_l2_float32_le_vector(
        values,
        expected_dimensions=DINOV2_BASE_DIMENSIONS,
    )
    return payload


def _rendered_families(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store, prepared, paths = _prepared_store(tmp_path / "render")
    harness = _Harness(store, prepared)
    monkeypatch.setattr(
        render_run,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    monkeypatch.setattr(
        render_run,
        "cold_verify_c4_stage1_prepared_attempt",
        lambda *_args, **_kwargs: prepared,
    )
    outcome = _run(harness, paths)
    monkeypatch.setattr(
        dino_bridge,
        "cold_verify_c4_stage1_prepared_attempt",
        lambda *_args, **_kwargs: prepared,
    )
    storages = []
    for role in ("primary", "alternate"):
        member = next(
            item for item in outcome.manifest.member_runs if item.editor_role == role
        )
        storage = member.worker_terminals[0].member_publication_receipt_storage
        assert storage is not None
        storages.append(storage)
    return store, prepared, outcome, (storages[0], storages[1])


def _preflight_rendered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    render_store, prepared, render_outcome, storages = _rendered_families(
        tmp_path,
        monkeypatch,
    )
    dino_store = FileArtifactStore(tmp_path / "dino-runs", create=True)
    preflight = _preflight(
        render_store,
        dino_store,
        render_outcome.inventory_anchor_storage,
        storages,
        dino_run_id="c4-stage1-dino-test",
        confirmed_prepared_attempt_id=prepared.prepared_attempt.prepared_attempt_id,
        confirmed_dino_policy_id=(
            prepared.prepared_attempt.screen_contract.dino_policy.dino_policy_id
        ),
    )
    return render_store, dino_store, prepared, render_outcome, storages, preflight


class _FakeChildExecutor:
    def __init__(self, preflight, vectors: tuple[bytes, bytes, bytes, bytes]) -> None:
        self.preflight = preflight
        self.vectors = vectors
        self.calls: list[str] = []

    def execute(self, *, image, call, editor_role, option_id) -> _ChildExecution:
        del editor_role, option_id
        assert not {
            name for name in sys.modules if name.split(".", 1)[0] in _MODEL_ROOTS
        }
        index = len(self.calls)
        self.calls.append(image.image_id)
        vector = self.vectors[index]
        digest = hashlib.sha256(vector).hexdigest()
        encoding_id = VerifiedImageEncoding.derive_id(
            request=call_request(call, image),
            vector_ref=f"emocio/embeddings/{digest}.f32",
            vector_hash=digest,
            dimensions=DINOV2_BASE_DIMENSIONS,
        )
        started = datetime(2026, 7, 15, 14, 0, index, tzinfo=UTC)
        provider_record = ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=call.input_artifact_ids,
            provider=call.provider,
            seed=call.seed,
            parameters=call.parameters,
            timeout_seconds=call.timeout_seconds,
            started_at=started,
            primary_finished_at=started + timedelta(milliseconds=1),
            finished_at=started + timedelta(milliseconds=1),
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(encoding_id,),
        )
        encoding = VerifiedImageEncoding.create(
            request=call_request(call, image),
            vector_ref=f"emocio/embeddings/{digest}.f32",
            vector_hash=digest,
            dimensions=DINOV2_BASE_DIMENSIONS,
            call_spec=call,
            call=provider_record,
        )
        semantic_request = C4Stage1DinoSemanticChildRequest.create(
            self.preflight.prepared,
            image=image,
            call=call,
        )
        bootstrap_pin, worker_pin = self.preflight.prepared.dino_entrypoint_pin.scripts
        bootstrap_bytes = (
            _ROOT / bootstrap_pin.repository_relative_path
        ).read_bytes()
        worker_bytes = (_ROOT / worker_pin.repository_relative_path).read_bytes()
        transport_bytes = dino_run._child_request_payload(
            repository_root=_ROOT,
            worker_python=Path(sys.executable).resolve(),
            render_run_root=self.preflight.render_store.run_path(
                self.preflight.prepared.run_id
            ),
            staging_root=self.preflight.dino_store.root,
            snapshot=_ROOT,
            prepared=self.preflight.prepared,
            image=image,
            call=call,
            bootstrap_bytes=bootstrap_bytes,
            worker_bytes=worker_bytes,
        )
        transport_sha = hashlib.sha256(transport_bytes).hexdigest()
        bounded_request = _child_process_request(
            repository_root=_ROOT,
            worker_python=Path(sys.executable).resolve(),
            bootstrap_path=_ROOT / C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH,
            request_path=(
                self.preflight.dino_store.root / f"fake-request-{index}.json"
            ),
            transport_request_sha256=transport_sha,
            semantic_request=semantic_request,
            environment=build_c4_stage1_worker_environment(
                self.preflight.prepared.launch_policy
            ),
        )
        return _ChildExecution(
            record=_process_record(bounded_request, index=index, succeeded=True),
            semantic_request=semantic_request,
            transport_request_sha256=transport_sha,
            child_result_sha256=hashlib.sha256(
                canonical_json_bytes(
                    {
                        "schema_version": "rei-c4-stage1-dino-child-result-v1",
                        "encoding": encoding,
                    }
                )
            ).hexdigest(),
            bootstrap_script_sha256=bootstrap_pin.content_sha256,
            bootstrap_script_size_bytes=bootstrap_pin.size_bytes,
            worker_script_sha256=worker_pin.content_sha256,
            worker_script_size_bytes=worker_pin.size_bytes,
            encoding=encoding,
            vector_bytes=vector,
        )


def call_request(call: ProviderCallSpec, image):
    from rei.providers.protocols import ImageEncodingRequest

    request = ImageEncodingRequest.create(
        image=image,
        provider=dinov2_base_provider_identity(),
        spec=dinov2_base_encoding_spec(
            snapshot_manifest_sha256=C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
            device="cuda",
        ),
    )
    assert request.request_id == call.request_id
    return request


def test_separate_dino_run_preserves_exact_render_cold_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    render_store, dino_store, _, render_outcome, _, preflight = _preflight_rendered(
        tmp_path,
        monkeypatch,
    )
    render_inventory_before = render_store.inspect_run_inventory_exact(
        preflight.prepared.run_id
    )
    executor = _FakeChildExecutor(
        preflight,
        (_basis(0), _basis(1), _basis(2), _basis(3)),
    )

    outcome = _run_with_child_executor(preflight, executor)

    assert outcome.anchor.render_run_id == preflight.prepared.run_id
    assert outcome.anchor.dino_run_id == "c4-stage1-dino-test"
    assert outcome.anchor.render_run_id != outcome.anchor.dino_run_id
    assert outcome.anchor.isolated_child_process_count == 4
    assert outcome.anchor.all_dino_gates_passed is True
    assert outcome.anchor.semantic_authority_granted is False
    assert outcome.anchor_storage.relative_path == C4_STAGE1_DINO_ANCHOR_PATH
    assert render_store.inspect_run_inventory_exact(preflight.prepared.run_id) == (
        render_inventory_before
    )
    assert (
        render_run.cold_verify_c4_stage1_run(
            FileArtifactStore(render_store.root, create=False),
            render_outcome.inventory_anchor_storage,
        )
        == render_outcome
    )
    assert (
        cold_verify_c4_stage1_dino_collapse_check(
            render_store,
            dino_store,
            outcome.anchor_storage,
        )
        == outcome.anchor
    )
    assert tuple(executor.calls) == tuple(
        image.image_id for family in preflight.images for image in family
    )


@pytest.mark.parametrize(
    "mutation",
    ("semantic-request", "environment", "isolated-flags", "script-pin"),
)
def test_cold_replay_rejects_mutated_child_execution_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    render_store, dino_store, _, _, _, preflight = _preflight_rendered(
        tmp_path,
        monkeypatch,
    )
    outcome = _run_with_child_executor(
        preflight,
        _FakeChildExecutor(
            preflight,
            (_basis(0), _basis(1), _basis(2), _basis(3)),
        ),
    )
    anchor_path = dino_store.run_path(outcome.anchor.dino_run_id).joinpath(
        *outcome.anchor_storage.relative_path.split("/")
    )
    value = json.loads(anchor_path.read_text(encoding="utf-8"))
    process = value["families"][0]["processes"][0]
    if mutation == "semantic-request":
        process["semantic_request"]["semantic_request_sha256"] = "0" * 64
    elif mutation == "environment":
        process["process_execution_record"]["environment_identity"] = (
            "c4-stage1-mutated-environment"
        )
    elif mutation == "isolated-flags":
        process["isolated_interpreter_flags"] = ["-I", "-I"]
    else:
        process["bootstrap_script_sha256"] = "0" * 64
    mutated = canonical_json_bytes(value)
    anchor_path.write_bytes(mutated)
    storage_body = {
        "schema_version": "rei-native-stored-artifact-v1",
        "run_id": outcome.anchor_storage.run_id,
        "relative_path": outcome.anchor_storage.relative_path,
        "content_sha256": hashlib.sha256(mutated).hexdigest(),
        "size_bytes": len(mutated),
    }
    mutated_storage = StoredArtifact(
        storage_id=content_id("stored", storage_body),
        **storage_body,
    )

    with pytest.raises(C4Stage1DinoRunError, match="failed cold parsing"):
        cold_verify_c4_stage1_dino_collapse_check(
            render_store,
            FileArtifactStore(dino_store.root, create=False),
            mutated_storage,
        )


def test_exact_final_render_anchor_and_inventory_are_required_before_dino(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    render_store, prepared, outcome, storages = _rendered_families(
        tmp_path, monkeypatch
    )
    dino_store = FileArtifactStore(tmp_path / "dino-runs", create=True)
    with pytest.raises(C4Stage1DinoRunError, match="final render anchor"):
        _preflight(
            render_store,
            dino_store,
            prepared.prepared_anchor_storage,
            storages,
            dino_run_id="c4-stage1-dino-test",
            confirmed_prepared_attempt_id=prepared.prepared_attempt.prepared_attempt_id,
            confirmed_dino_policy_id=(
                prepared.prepared_attempt.screen_contract.dino_policy.dino_policy_id
            ),
        )

    render_store.write_bytes(
        prepared.prepared_attempt.run_id,
        "diagnostics/unknown-after-render.bin",
        b"forbidden",
    )
    with pytest.raises(C4Stage1DinoRunError, match="final render anchor"):
        _preflight(
            render_store,
            dino_store,
            outcome.inventory_anchor_storage,
            storages,
            dino_run_id="c4-stage1-dino-test",
            confirmed_prepared_attempt_id=prepared.prepared_attempt.prepared_attempt_id,
            confirmed_dino_policy_id=(
                prepared.prepared_attempt.screen_contract.dino_policy.dino_policy_id
            ),
        )


def test_other_repository_checkout_is_rejected_before_repository_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, _, preflight = _preflight_rendered(tmp_path, monkeypatch)
    called = False

    def forbidden(_path):
        nonlocal called
        called = True
        raise AssertionError("repository capture must not run")

    monkeypatch.setattr(dino_run, "capture_c4_stage1_repository_gate", forbidden)
    with pytest.raises(C4Stage1DinoRunError, match="checkout that loaded"):
        _verify_actual_repository_root(tmp_path, preflight.prepared)
    assert called is False


def test_model_modules_are_absent_before_every_child_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, _, preflight = _preflight_rendered(tmp_path, monkeypatch)
    before = {name for name in sys.modules if name.split(".", 1)[0] in _MODEL_ROOTS}
    assert before == set()
    executor = _FakeChildExecutor(
        preflight,
        (_basis(0), _basis(1), _basis(2), _basis(3)),
    )
    _run_with_child_executor(preflight, executor)
    after = {name for name in sys.modules if name.split(".", 1)[0] in _MODEL_ROOTS}
    assert after == before
    assert len(executor.calls) == 4


def test_production_child_command_is_no_site_and_hard_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, _, preflight = _preflight_rendered(tmp_path, monkeypatch)
    request_path = tmp_path / "request.json"
    request_path.write_bytes(b"{}")
    environment = {"HF_HUB_OFFLINE": "1"}
    image = preflight.images[0][0]
    call = dino_run._build_encoding_call(image)
    semantic_request = C4Stage1DinoSemanticChildRequest.create(
        preflight.prepared,
        image=image,
        call=call,
    )
    request = _child_process_request(
        repository_root=Path(__file__).resolve().parents[2],
        worker_python=Path(sys.executable),
        bootstrap_path=(
            Path(__file__).resolve().parents[2] / C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH
        ),
        request_path=request_path,
        transport_request_sha256=hashlib.sha256(b"{}").hexdigest(),
        semantic_request=semantic_request,
        environment=environment,
    )
    assert request.command[1:3] == ("-I", "-S")
    assert Path(request.command[3]).name == "run_rei_c4_stage1_dino_bootstrap.py"
    assert request.timeout_seconds == 120.0


def test_base_runtime_probe_uses_bounded_tree_and_rejects_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, _, preflight = _preflight_rendered(tmp_path, monkeypatch)
    requests: list[BoundedProcessRequest] = []

    class _TimedOutRunner:
        def run(self, request: BoundedProcessRequest):
            requests.append(request)
            record = SimpleNamespace(
                status="timed_out",
                termination_trigger="hard_timeout",
                tree_termination_requested=True,
                tree_termination_succeeded=True,
                empty_tree_confirmed=True,
                containment_closed=True,
            )
            return SimpleNamespace(
                succeeded=False,
                record=record,
                stdout=b"",
                stderr=b"",
            )

    monkeypatch.setattr(dino_run, "BoundedProcessTreeRunner", _TimedOutRunner)
    with pytest.raises(C4Stage1DinoRunError, match="base runtime probe failed"):
        _worker_base_runtime_root(Path(sys.executable).resolve(), preflight.prepared)

    assert len(requests) == 1
    request = requests[0]
    assert request.command[1:3] == ("-I", "-S")
    assert request.command[3] == "-c"
    assert request.timeout_seconds == 30.0
    assert request.stdout_limit_bytes == 32_767
    assert request.stderr_limit_bytes == 32_767


def test_base_runtime_probe_requires_confirmed_empty_contained_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, _, _, _, preflight = _preflight_rendered(tmp_path, monkeypatch)
    expected = Path(sys.base_prefix).resolve(strict=True)

    class _ProbeRunner:
        mutated_field: str | None = None

        def run(self, request: BoundedProcessRequest):
            record = _process_record(request, index=76, succeeded=True)
            if self.mutated_field is not None:
                fields = record.model_dump(mode="python", round_trip=True)
                fields[self.mutated_field] = False
                record = SimpleNamespace(**fields)
            return SimpleNamespace(
                succeeded=True,
                record=record,
                stdout=os.fspath(expected).encode("utf-8"),
                stderr=b"",
            )

    monkeypatch.setattr(dino_run, "BoundedProcessTreeRunner", _ProbeRunner)
    assert (
        _worker_base_runtime_root(Path(sys.executable).resolve(), preflight.prepared)
        == expected
    )
    for field in (
        "target_identity_confirmed",
        "empty_tree_confirmed",
        "containment_closed",
    ):
        _ProbeRunner.mutated_field = field
        with pytest.raises(C4Stage1DinoRunError, match="base runtime probe failed"):
            _worker_base_runtime_root(
                Path(sys.executable).resolve(),
                preflight.prepared,
            )


@pytest.mark.parametrize("stream", ("stdout", "stderr"))
def test_base_runtime_probe_rejects_bounded_output_flood(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stream: str,
) -> None:
    _, _, _, _, _, preflight = _preflight_rendered(tmp_path, monkeypatch)

    class _FloodRunner:
        def run(self, request: BoundedProcessRequest):
            record = _process_record(request, index=77, succeeded=True)
            flood = b"x" * (request.stdout_limit_bytes + 1)
            return SimpleNamespace(
                succeeded=True,
                record=record,
                stdout=flood if stream == "stdout" else b"base",
                stderr=flood if stream == "stderr" else b"",
            )

    monkeypatch.setattr(dino_run, "BoundedProcessTreeRunner", _FloodRunner)
    with pytest.raises(C4Stage1DinoRunError, match="base runtime probe failed"):
        _worker_base_runtime_root(Path(sys.executable).resolve(), preflight.prepared)


def test_injected_hanging_child_is_killed_with_a_bounded_tree(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-survive.txt"
    code = (
        "import time,pathlib;"
        "time.sleep(30);"
        f"pathlib.Path({str(marker)!r}).write_text('survived')"
    )
    request = BoundedProcessRequest(
        workload_id="c4-stage1-dino-hang-test",
        command_identity="c4-stage1-dino-hang-command",
        working_directory_identity="c4-stage1-dino-hang-cwd",
        environment_identity="c4-stage1-dino-hang-env",
        command=(sys.executable, "-I", "-S", "-c", code),
        working_directory=tmp_path,
        environment=dict(os.environ),
        timeout_seconds=0.2,
        stdout_limit_bytes=PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
        stderr_limit_bytes=PROCESS_TREE_DEFAULT_OUTPUT_LIMIT_BYTES,
    )
    result = BoundedProcessTreeRunner().run(request)
    assert result.record.status == "timed_out"
    assert result.record.termination_trigger == "hard_timeout"
    assert result.record.tree_termination_requested is True
    assert result.record.tree_termination_succeeded is True
    assert result.record.empty_tree_confirmed is True
    assert not marker.exists()


def test_no_site_bootstrap_recaptures_full_runtime_and_rejects_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load_dino_bootstrap()
    venv = tmp_path / "worker-venv"
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    site_packages = (
        venv / "Lib" / "site-packages"
        if os.name == "nt"
        else venv
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    base = tmp_path / "base-runtime"
    scripts.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    base.mkdir()
    executable = scripts / ("python.exe" if os.name == "nt" else "python")
    executable.write_bytes(b"fake ordinary python")
    (venv / "pyvenv.cfg").write_text("home = external\n", encoding="utf-8")
    package = site_packages / "package.py"
    package.write_bytes(b"VERSION = 1\n")
    (base / "stdlib.py").write_bytes(b"BASE = 1\n")
    worker_inventory = bootstrap._capture_runtime_tree(
        venv,
        tree_role="worker-venv",
    )
    base_inventory = bootstrap._capture_runtime_tree(
        base,
        tree_role="base-runtime",
    )
    inventory_body = {
        "policy": bootstrap._RUNTIME_INVENTORY_POLICY,
        "worker_venv_inventory": worker_inventory,
        "base_runtime_inventory": base_inventory,
    }
    pin = {
        "schema_version": "rei-c4-stage1-worker-runtime-pin-v2",
        "worker_python_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "worker_python_size_bytes": executable.stat().st_size,
        "worker_venv_inventory": worker_inventory,
        "base_runtime_inventory": base_inventory,
        "runtime_inventory_policy": bootstrap._RUNTIME_INVENTORY_POLICY,
        "runtime_inventory_sha256": hashlib.sha256(
            bootstrap._canonical_json_bytes(inventory_body)
        ).hexdigest(),
        "runtime_inventory_file_count": (
            worker_inventory["file_count"] + base_inventory["file_count"]
        ),
        "runtime_inventory_directory_count": (
            worker_inventory["directory_count"] + base_inventory["directory_count"]
        ),
        "runtime_inventory_size_bytes": (
            worker_inventory["total_size_bytes"] + base_inventory["total_size_bytes"]
        ),
        "runtime_tree_count": 2,
        "runtime_paths_stored": False,
        "site_activation_disabled": True,
        "runtime_customization_modules_rejected": True,
        "pth_files_never_executed": True,
        "complete_runtime_trees_inventory_verified": True,
        "inventory_recapture_required_before_every_spawn": True,
        "runtime_reverification_required_before_spawn": True,
        "model_packages_imported_in_parent": False,
        "network_access_required": False,
    }
    runtime_id, runtime_sha = bootstrap._runtime_pin_content(pin)
    pin["worker_runtime_id"] = runtime_id
    pin["worker_runtime_sha256"] = runtime_sha
    # Adding the identities changes neither body digest because the helper
    # deliberately excludes both identity fields.
    assert bootstrap._runtime_pin_content(pin) == (runtime_id, runtime_sha)
    staging = tmp_path / "staging"
    render = tmp_path / "render"
    snapshot = tmp_path / "snapshot"
    staging.mkdir()
    render.mkdir()
    snapshot.mkdir()
    bootstrap_bytes = bootstrap.BOOTSTRAP_PATH.read_bytes()
    worker_bytes = bootstrap.WORKER_PATH.read_bytes()
    request = {
        "repository_root": os.fspath(bootstrap.ROOT),
        "staging_root": os.fspath(staging),
        "render_run_root": os.fspath(render),
        "snapshot_path": os.fspath(snapshot),
        "bootstrap_script_sha256": hashlib.sha256(bootstrap_bytes).hexdigest(),
        "bootstrap_script_size_bytes": len(bootstrap_bytes),
        "worker_script_sha256": hashlib.sha256(worker_bytes).hexdigest(),
        "worker_script_size_bytes": len(worker_bytes),
        "worker_python_sha256": pin["worker_python_sha256"],
        "worker_python_size_bytes": pin["worker_python_size_bytes"],
        "worker_runtime_id": runtime_id,
        "worker_runtime_sha256": runtime_sha,
        "worker_runtime": pin,
    }
    monkeypatch.setattr(bootstrap.sys, "executable", os.fspath(executable))
    monkeypatch.setattr(bootstrap.sys, "base_prefix", os.fspath(base))
    monkeypatch.setattr(
        bootstrap.sysconfig,
        "get_path",
        lambda _name, **_kwargs: os.fspath(site_packages),
    )
    assert bootstrap._verify_runtime(request) == (site_packages,)

    package.write_bytes(b"VERSION = 2\n")
    with pytest.raises(bootstrap.C4Stage1DinoBootstrapError):
        bootstrap._verify_runtime(request)


def test_bootstrap_passes_sealed_request_bytes_and_ignores_path_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load_dino_bootstrap()
    request_path = tmp_path / "request.json"
    request_path.write_bytes(b"sealed-original")
    received: list[bytes] = []
    monkeypatch.setattr(bootstrap, "_require_isolated_startup", lambda: None)
    monkeypatch.setattr(bootstrap, "_arguments", lambda _argv: request_path)
    monkeypatch.setattr(
        bootstrap,
        "_load_request",
        lambda _path: (b"sealed-original", {"validated": True}),
    )

    def verify_then_replace(_request):
        request_path.write_bytes(b"canonical-replacement")
        return ()

    monkeypatch.setattr(bootstrap, "_verify_runtime", verify_then_replace)
    monkeypatch.setattr(
        bootstrap,
        "_load_worker",
        lambda _roots: SimpleNamespace(
            run_authorized_request=lambda raw: received.append(raw) or 0
        ),
    )
    assert bootstrap.main(["--request", os.fspath(request_path)]) == 0
    assert request_path.read_bytes() == b"canonical-replacement"
    assert received == [b"sealed-original"]


@pytest.mark.parametrize("boundary", ("repository", "snapshot"))
def test_staging_parent_cannot_overlap_repository_or_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    _, _, _, _, _, preflight = _preflight_rendered(tmp_path, monkeypatch)
    repository = _ROOT
    snapshot = tmp_path / "external-snapshot"
    base = tmp_path / "external-base"
    snapshot.mkdir()
    base.mkdir()
    staging = repository if boundary == "repository" else snapshot
    with pytest.raises(C4Stage1DinoRunError, match="overlaps"):
        _verify_external_staging_parent(
            staging,
            repository_root=repository,
            worker_python=Path(sys.executable).resolve(),
            base_runtime_root=base,
            snapshot=snapshot,
            preflight=preflight,
        )


def test_snapshot_preflight_rejects_hardlinks_before_manifest_acceptance(
    tmp_path: Path,
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    model = snapshot / "model.safetensors"
    model.write_bytes(b"not-a-model")
    os.link(model, snapshot / "alias.safetensors")
    with pytest.raises(C4Stage1DinoRunError, match="ordinary unlinked"):
        verify_c4_stage1_dino_snapshot(snapshot)


def test_cli_is_inert_without_explicit_execute() -> None:
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        (sys.executable, os.fspath(root / "scripts" / "run_rei_c4_stage1_dino.py")),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30.0,
        shell=False,
    )
    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr == b""


def test_vectors_are_exact_float32_and_not_scalar_placeholders() -> None:
    payload = _basis(5)
    assert len(payload) == 4 * DINOV2_BASE_DIMENSIONS
    assert hashlib.sha256(payload).hexdigest()
    assert struct.unpack_from("<f", payload, 5 * 4)[0] == 1.0
