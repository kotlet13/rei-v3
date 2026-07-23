from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
from pydantic import ValidationError

from rei.emocio.c4_stage1_editor import (
    C4Stage1DependencyVersions,
    VerifiedC4Stage1Snapshot,
)
from rei.emocio.dinov2_encoder import dinov2_base_provider_identity
from rei.emocio.longcat_turbo_editor import (
    build_longcat_turbo_worker_request,
    longcat_turbo_stage1_spec,
)
from rei.emocio.omnigen_editor import (
    build_omnigen_worker_request,
    omnigen_stage1_spec,
)
from rei.ids import canonical_json_bytes, content_id
from rei.evaluation.c4_blind_review import (
    build_c4_blind_human_review_schema,
    build_c4_human_review_operator_policy,
)
from rei.evaluation import c4_stage1_attempt as attempt_module
from rei.evaluation.c4_stage1_attempt import (
    C4_STAGE1_BOOTSTRAP_SCRIPT_PATH,
    C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH,
    C4_STAGE1_DINO_WORKER_SCRIPT_PATH,
    C4_STAGE1_GIT_SCOPE_PATHS,
    C4_STAGE1_ORIGIN_URL,
    C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS,
    C4Stage1GitRuntimePin,
    C4Stage1DinoEntrypointPin,
    C4Stage1LaunchPolicy,
    C4Stage1PreparationError,
    C4Stage1PreparedAttempt,
    C4Stage1PreparedWorker,
    C4Stage1ReviewCommitments,
    C4Stage1RepositoryGate,
    C4Stage1RuntimePaths,
    C4Stage1RuntimeTreeInventoryPin,
    C4Stage1WorkerRuntimePin,
    _content_pin,
    _telemetry_content_pin,
    build_c4_stage1_worker_environment,
    capture_c4_stage1_worker_runtime,
    capture_c4_stage1_repository_gate,
    verify_c4_stage1_live_review_boundary,
    verify_c4_stage1_pre_spawn_runtime_bindings,
    verify_c4_stage1_staging_parent,
)
from rei.evaluation.c4_stage1_fixture import build_c4_stage1_fixture
from rei.evaluation.c4_stage1_review import (
    build_c4_stage1_display_attester_policy,
    c4_stage1_display_policy_content_pin,
)
from rei.evaluation.c4_stage1_review_runtime import (
    capture_c4_stage1_review_runtime_manifest,
)
from rei.evaluation.c4_stage1_review_service import (
    C4_STAGE1_REVIEW_READINESS_ID_NAMESPACE,
    C4Stage1ReviewRepositoryGateBinding,
    C4Stage1ReviewServiceReadiness,
)
from rei.evaluation.c4_stage1_review_presenter import (
    C4Stage1ReviewBrowserRuntimePin,
    C4Stage1ReviewExternalRuntimePin,
    C4Stage1ReviewSealedTreeIdentity,
)
from rei.evaluation.c4_stage1_screen import (
    C4_STAGE1_ADDENDUM_PATH,
    C4_STAGE1_PROTOCOL_PATH,
    C4Stage1DinoPolicy,
    C4Stage1DocumentPin,
    C4Stage1ScreenContract,
    C4Stage1SourcePin,
)
from rei.evaluation.c4_stage1_telemetry import c4_stage1_telemetry_policy
from rei.evaluation.resource_telemetry import ResourceTelemetryCudaDeviceIdentity


ROOT = Path(__file__).resolve().parents[2]
CUDA_DEVICE = ResourceTelemetryCudaDeviceIdentity.resolved(
    logical_device_index=0,
    physical_gpu_uuid="GPU-11111111-2222-3333-4444-555555555555",
    pci_bus_id="00000000:01:00.0",
)
RUNTIME_METADATA = {
    "python": "3.11",
    "python_full_version": "3.11.9",
    "python_implementation": "CPython",
    "torch": "2.13.0+cu130",
    "diffusers": "0.39.0",
    "transformers": "5.13.0",
    "accelerate": "1.14.0",
    "safetensors": "0.8.0",
    "pillow": "12.3.0",
}


def _tree_pin(
    role: str,
    *,
    payload: bytes,
) -> C4Stage1RuntimeTreeInventoryPin:
    return C4Stage1RuntimeTreeInventoryPin(
        tree_role=role,
        tree_content_sha256=hashlib.sha256(payload).hexdigest(),
        file_count=1,
        directory_count=1,
        total_size_bytes=len(payload),
        pth_file_count=0,
    )


def _runtime_pin() -> C4Stage1WorkerRuntimePin:
    return C4Stage1WorkerRuntimePin.create(
        worker_python_sha256=hashlib.sha256(b"stage1-worker-python").hexdigest(),
        worker_python_size_bytes=len(b"stage1-worker-python"),
        python_full_version=RUNTIME_METADATA["python_full_version"],
        dependencies=C4Stage1DependencyVersions(),
        worker_venv_inventory=_tree_pin(
            "worker-venv",
            payload=b"stage1-worker-venv",
        ),
        base_runtime_inventory=_tree_pin(
            "base-runtime",
            payload=b"stage1-base-runtime",
        ),
    )


def _runtime_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    worker_venv = (tmp_path / "worker-venv").resolve()
    base_runtime = (tmp_path / "base-runtime").resolve()
    executable_directory = worker_venv / ("Scripts" if os.name == "nt" else "bin")
    site_packages = (
        worker_venv / "Lib" / "site-packages"
        if os.name == "nt"
        else worker_venv / "lib" / "python3.11" / "site-packages"
    )
    executable_directory.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    base_runtime.mkdir()
    worker_python = executable_directory / (
        "python.exe" if os.name == "nt" else "python"
    )
    worker_python.write_bytes(b"exact-stage1-worker-python")
    (worker_venv / "pyvenv.cfg").write_bytes(b"home = path-is-runtime-only\n")
    package_payload = site_packages / "frozen-package.py"
    package_payload.write_bytes(b"frozen-package-runtime-bytes")
    (site_packages / "never-executed.pth").write_bytes(
        b"import pathlib; pathlib.Path('pth-executed').write_text('bad')\n"
    )
    (base_runtime / "python-runtime.dll").write_bytes(b"base-runtime-bytes")
    metadata = {
        **RUNTIME_METADATA,
        "_runtime_worker_venv_root": os.fspath(worker_venv),
        "_runtime_base_root": os.fspath(base_runtime),
        "_runtime_site_packages": os.fspath(site_packages),
    }
    return worker_python, worker_venv, base_runtime, package_payload, metadata


def _git_runtime_pin() -> C4Stage1GitRuntimePin:
    return C4Stage1GitRuntimePin.create(
        git_executable_sha256=hashlib.sha256(b"trusted-git-fixture").hexdigest(),
        git_executable_size_bytes=len(b"trusted-git-fixture"),
        git_version="git version 2.54.0.windows.1",
        trusted_location_class="windows-program-files-git-bin",
    )


def _repository_gate() -> C4Stage1RepositoryGate:
    return C4Stage1RepositoryGate.create(
        git_runtime=_git_runtime_pin(),
        head_commit="1" * 40,
        local_origin_main_commit="1" * 40,
        remote_origin_main_commit="1" * 40,
    )


def _external_runtime_pin(
    *, chromium_sha256: str = "4" * 64
) -> C4Stage1ReviewExternalRuntimePin:
    runtime_tree = C4Stage1ReviewSealedTreeIdentity(
        schema_version="rei-c4-stage1-review-sealed-tree-identity-v1",
        manifest_id="runtime-manifest-fixture",
        canonical_sha256="1" * 64,
        canonical_size_bytes=1,
        tree_content_id="runtime-tree-fixture",
        tree_content_sha256="2" * 64,
        file_count=1,
        directory_count=1,
        executable_count=1,
        total_size_bytes=1,
    )
    browser_tree = C4Stage1ReviewSealedTreeIdentity(
        schema_version="rei-c4-stage1-review-sealed-tree-identity-v1",
        manifest_id="browser-manifest-fixture",
        canonical_sha256="3" * 64,
        canonical_size_bytes=1,
        tree_content_id="browser-tree-fixture",
        tree_content_sha256="4" * 64,
        file_count=1,
        directory_count=1,
        executable_count=1,
        total_size_bytes=1,
    )
    base = {
        "schema_version": "rei-c4-stage1-review-external-runtime-pin-v1",
        "verification_schema_version": ("rei-c4-stage1-review-runtime-verification-v1"),
        "verification_id": "external-runtime-verification-fixture",
        "verification_sha256": "5" * 64,
        "provenance_id": "external-runtime-provenance-fixture",
        "provenance_canonical_sha256": "6" * 64,
        "provenance_canonical_size_bytes": 1,
        "create_only_inventory_verified": True,
        "runtime_manifest": runtime_tree,
        "browser_manifest": browser_tree,
        "runtime_python_relative_path": "venv/Scripts/python.exe",
        "runtime_python_sha256": "7" * 64,
        "runtime_python_size_bytes": 1,
        "installed_browsers_json_sha256": "8" * 64,
        "installed_browsers_json_size_bytes": 1,
        "chromium_executable_relative_path": ("chromium-1228/chrome-win64/chrome.exe"),
        "chromium_executable_sha256": chromium_sha256,
        "chromium_executable_size_bytes": 1,
        "checkpoint_applied_during_all_file_and_tree_hashing": True,
        "paths_stored": False,
        "browser_process_launch_performed": False,
        "headed_full_ui_smoke_performed": False,
        "model_calls": 0,
    }
    return C4Stage1ReviewExternalRuntimePin(
        external_runtime_pin_id=content_id("c4_review_external_runtime", base),
        external_runtime_pin_sha256=hashlib.sha256(
            canonical_json_bytes(base)
        ).hexdigest(),
        **base,
    )


def _git_runner(
    *,
    branch: str = "main",
    dirty: str = "",
    origin_url: str = C4_STAGE1_ORIGIN_URL,
    tracked: str = "H app/backend/requirements.txt\n",
):
    commit = "1" * 40

    def run(arguments: tuple[str, ...], root: Path) -> str:
        assert root.is_absolute()
        assert arguments[0] == "stage1-injected-git-runner"
        if arguments[1:5] == ("symbolic-ref", "--quiet", "--short", "HEAD"):
            return branch + "\n"
        if arguments[1:4] == ("rev-parse", "--verify", "HEAD^{commit}"):
            return commit + "\n"
        if arguments[1:4] == (
            "rev-parse",
            "--verify",
            "refs/remotes/origin/main^{commit}",
        ):
            return commit + "\n"
        if arguments[1:4] == ("remote", "get-url", "origin"):
            return origin_url + "\n"
        if arguments[1:5] == ("remote", "get-url", "--push", "origin"):
            return origin_url + "\n"
        if arguments[1:4] == (
            "ls-remote",
            "--exit-code",
            C4_STAGE1_ORIGIN_URL,
        ):
            return f"{commit}\trefs/heads/main\n"
        if arguments[1:3] == ("status", "--porcelain=v1"):
            assert arguments[-len(C4_STAGE1_GIT_SCOPE_PATHS) :] == (
                C4_STAGE1_GIT_SCOPE_PATHS
            )
            return dirty
        if arguments[1:3] == ("ls-files", "-v"):
            assert arguments[-len(C4_STAGE1_GIT_SCOPE_PATHS) :] == (
                C4_STAGE1_GIT_SCOPE_PATHS
            )
            return tracked
        raise AssertionError(arguments)

    return run


def _documents():
    return (
        C4Stage1DocumentPin.create(
            role="protocol",
            relative_path=C4_STAGE1_PROTOCOL_PATH,
            payload=(ROOT / C4_STAGE1_PROTOCOL_PATH).read_bytes(),
        ),
        C4Stage1DocumentPin.create(
            role="model_free_addendum",
            relative_path=C4_STAGE1_ADDENDUM_PATH,
            payload=(ROOT / C4_STAGE1_ADDENDUM_PATH).read_bytes(),
        ),
    )


def _review_boundary():
    runtime = capture_c4_stage1_review_runtime_manifest(ROOT)
    operator_commitments = tuple(
        hashlib.sha256(f"operator-secret-{index}".encode()).hexdigest()
        for index in range(2)
    )
    base = {
        "schema_version": "rei-c4-stage1-review-service-v2",
        "presenter_implementation_id": runtime.presenter_implementation_id,
        "presenter_revision": runtime.presenter_revision,
        "ipc_schema": runtime.ipc_protocol,
        "ledger_schema": runtime.ledger_schema_revision,
        "ui_bundle_sha256": runtime.ui_bundle_sha256,
        "content_security_policy_sha256": runtime.content_security_policy_sha256,
        "repository_gate": C4Stage1ReviewRepositoryGateBinding.create(
            _repository_gate()
        ),
        "browser_runtime": C4Stage1ReviewBrowserRuntimePin.create(
            browser_executable_sha256="4" * 64,
            browser_executable_size_bytes=1,
            external_runtime=_external_runtime_pin(),
        ),
        "presenter_session_timeout_ms": 3_600_000,
        "service_epoch_id": content_id(
            "c4_stage1_review_service_epoch", {"epoch": "e" * 64}
        ),
        "state_directory_identity_sha256": "a" * 64,
        "state_database_identity_sha256": "b" * 64,
        "boundary_roots_identity_sha256": "c" * 64,
        "exclusive_state_owner_lock_held": True,
        "copied_state_rejected": True,
        "display_signing_key_commitment_sha256": "5" * 64,
        "operator_signing_key_commitment_sha256s": operator_commitments,
        "ipc_auth_key_commitment_sha256": "6" * 64,
        "submission_auth_key_commitment_sha256": "7" * 64,
        "secret_count": 5,
        "secret_size_bytes": 32,
        "ipc_auth_required": True,
        "ipc_auth_secret_separate_from_review_keys": True,
        "ipc_request_nonce_replay_rejected": True,
        "ipc_response_auth_required": True,
        "ipc_response_request_binding_required": True,
        "ipc_response_replay_and_cross_operation_rejected": True,
        "stateful_ipc_result_journal_required": True,
        "stateful_ipc_request_id_server_derived": True,
        "stateful_ipc_result_hmac_required": True,
        "stateful_ipc_transport_retry_limit": 1,
        "stateful_ipc_operation_count": 7,
        "stateful_ipc_max_completed_rows": 13,
        "display_in_progress_never_relaunched": True,
        "sealed_sign_result_recoverable": True,
        "presenter_submission_auth_required": True,
        "operator_signing_lease_required": True,
        "sqlite_journal_mode": "wal",
        "sqlite_synchronous": "FULL",
        "one_time_ledgers": (
            "display_attestation",
            "display_receipt",
            "operator_policy",
            "presenter_submission",
            "operator_signing_lease",
        ),
        "service_is_model_free": True,
        "secrets_exposed": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    readiness = C4Stage1ReviewServiceReadiness(
        readiness_receipt_id=content_id(C4_STAGE1_REVIEW_READINESS_ID_NAMESPACE, base),
        readiness_receipt_sha256=hashlib.sha256(canonical_json_bytes(base)).hexdigest(),
        **base,
    )
    return runtime, readiness


class _ReviewService:
    def __init__(
        self,
        readiness,
        *,
        ledger_count: int = 0,
        cohort_complete: bool | None = None,
    ):
        self.readiness = readiness
        self.ledger_count = ledger_count
        self.cohort_complete = (
            ledger_count == 2 if cohort_complete is None else cohort_complete
        )

    def health(self):
        return {
            "schema_version": "rei-c4-stage1-review-service-v2",
            "ready": True,
            "sqlite_integrity": "ok",
            "sqlite_journal_mode": "wal",
            "sqlite_synchronous": "FULL",
            "ledger_counts": {
                "display_attestation_uses": self.ledger_count,
                "display_receipt_uses": self.ledger_count,
                "operator_policy_uses": self.ledger_count,
                "presenter_submissions": self.ledger_count,
                "operator_signing_leases": self.ledger_count,
            },
            "operator_signing_cohort_complete": self.cohort_complete,
            "operator_signing_cohort_id": (
                "c4_stage1_operator_signing_cohort_test"
                if self.cohort_complete
                else None
            ),
            "operator_signing_cohort_sha256": (
                "d" * 64 if self.cohort_complete else None
            ),
            "secret_commitments_match_state": True,
            "display_presenter_attached": True,
            "repository_gate_matches_startup": True,
            "presenter_boundary_roots_match_startup": True,
            "browser_runtime_matches_readiness": True,
            "ipc_response_auth_required": True,
            "presenter_submission_auth_required": True,
            "operator_signing_lease_required": True,
            "service_is_model_free": True,
            "semantic_quality_gate_passed": False,
            "production_authority_granted": False,
            "model_judge_calls": 0,
        }


def _readdress_readiness(readiness, **updates):
    base = readiness.model_dump(
        mode="python",
        round_trip=True,
        exclude={"readiness_receipt_id", "readiness_receipt_sha256"},
    )
    base.update(updates)
    return C4Stage1ReviewServiceReadiness(
        readiness_receipt_id=content_id(C4_STAGE1_REVIEW_READINESS_ID_NAMESPACE, base),
        readiness_receipt_sha256=hashlib.sha256(canonical_json_bytes(base)).hexdigest(),
        **base,
    )


def _prepared_attempt(
    *,
    worker_runtime: C4Stage1WorkerRuntimePin | None = None,
) -> C4Stage1PreparedAttempt:
    fixture = build_c4_stage1_fixture()
    review_runtime, review_readiness = _review_boundary()
    schema = build_c4_blind_human_review_schema()
    policies = tuple(
        build_c4_human_review_operator_policy(
            schema,
            run_id="stage1-test-run",
            candidate_slot_id=f"candidate-{index}",
            source_image_sha256=fixture.source_image.content_sha256,
            hmac_key_commitment_sha256=hashlib.sha256(
                f"operator-secret-{index}".encode()
            ).hexdigest(),
        )
        for index in range(2)
    )
    display = build_c4_stage1_display_attester_policy(
        policy_nonce="3" * 64,
        ui_bundle_sha256=review_runtime.ui_bundle_sha256,
        content_security_policy=review_runtime.content_security_policy,
        presenter_implementation_id=review_runtime.presenter_implementation_id,
        presenter_revision=review_runtime.presenter_revision,
        display_attester_id=review_readiness.readiness_receipt_id,
        display_signing_key_commitment_sha256="5" * 64,
    )
    telemetry = c4_stage1_telemetry_policy()
    specs = (longcat_turbo_stage1_spec(), omnigen_stage1_spec())
    verified = tuple(VerifiedC4Stage1Snapshot.create(spec) for spec in specs)
    protocol, addendum = _documents()
    screen = C4Stage1ScreenContract.create(
        protocol=protocol,
        model_free_addendum=addendum,
        fixture=fixture,
        source=C4Stage1SourcePin.create(
            source_png_size_bytes=987_133,
            source_provenance_sha256=(
                "0c4f56b487213c1592ebdde0c69a0b850620bc94add1a910f321fea36107107f"
            ),
        ),
        editor_specs=specs,
        review_schema=_content_pin("review_schema", schema),
        review_operator_policies=tuple(
            _content_pin("review_operator_policy", policy) for policy in policies
        ),
        display_policy=c4_stage1_display_policy_content_pin(display),
        review_runtime=attempt_module._review_runtime_content_pin(review_runtime),
        review_service_readiness=(
            attempt_module._review_service_readiness_content_pin(review_readiness)
        ),
        telemetry_policy=_telemetry_content_pin(telemetry),
        dino_policy=C4Stage1DinoPolicy.create(dinov2_base_provider_identity()),
    )
    workers = []
    for provider_index, (spec, snapshot, policy, builder, role) in enumerate(
        zip(
            specs,
            verified,
            policies,
            (build_longcat_turbo_worker_request, build_omnigen_worker_request),
            ("primary", "alternate"),
            strict=True,
        )
    ):
        for option_index, prompt in enumerate(fixture.prompts):
            request = builder(
                editor_spec=spec,
                verified_snapshot=snapshot,
                scene=prompt.scene,
                source_image=fixture.source_image,
                seed=prompt.derived_seed,
                prompt=prompt.prompt,
                profile_hash=fixture.prompt_profile_hash,
            )
            workers.append(
                C4Stage1PreparedWorker.create(
                    provider_order_index=provider_index,
                    option_order_index=option_index,
                    editor_role=role,
                    option_id=prompt.option_id,
                    operator_policy_id=policy.policy_id,
                    worker_request=request,
                )
            )
    launch = C4Stage1LaunchPolicy.create(
        (ROOT / "scripts" / "run_rei_c4_stage1_worker.py").read_bytes(),
        bootstrap_script=b"# frozen stage1 bootstrap fixture\n",
        cuda_device=CUDA_DEVICE,
        worker_runtime=_runtime_pin() if worker_runtime is None else worker_runtime,
    )
    return C4Stage1PreparedAttempt.create(
        run_id="stage1-test-run",
        repository_gate=_repository_gate(),
        launch_policy=launch,
        worker_runtime=launch.worker_runtime,
        cuda_device=CUDA_DEVICE,
        source_provenance_sha256=screen.source.source_provenance_sha256,
        telemetry_policy=telemetry,
        review_schema=schema,
        review_operator_policies=policies,
        display_policy=display,
        review_runtime_manifest=review_runtime,
        review_service_readiness=review_readiness,
        screen_contract=screen,
        workers=tuple(workers),
        artifact_inventory_before_anchor=(),
    )


def test_review_commitments_are_derived_from_exact_runtime_and_service() -> None:
    runtime, readiness = _review_boundary()
    commitments = C4Stage1ReviewCommitments.create(
        review_runtime_manifest=runtime,
        review_service_readiness=readiness,
        display_policy_nonce="3" * 64,
    )

    assert commitments.ui_bundle_sha256 == runtime.ui_bundle_sha256
    assert commitments.operator_hmac_key_commitments_sha256 == (
        readiness.operator_signing_key_commitment_sha256s
    )
    assert commitments.display_attester_id == readiness.readiness_receipt_id
    forged = commitments.model_dump(mode="python", round_trip=True)
    forged["ui_bundle_sha256"] = "f" * 64
    with pytest.raises(ValidationError, match="pinned runtime service"):
        C4Stage1ReviewCommitments.model_validate(forged)


def test_live_review_boundary_rejects_other_or_used_service() -> None:
    runtime, readiness = _review_boundary()
    verified_runtime, verified_readiness = verify_c4_stage1_live_review_boundary(
        repository_root=ROOT.resolve(),
        repository_gate=_repository_gate(),
        review_runtime_manifest=runtime,
        review_service_readiness=readiness,
        review_service=_ReviewService(readiness),
        expected_completed_review_count=0,
    )
    assert verified_runtime == runtime
    assert verified_readiness == readiness

    other = _readdress_readiness(
        readiness,
        ipc_auth_key_commitment_sha256="8" * 64,
    )
    with pytest.raises(C4Stage1PreparationError, match="public commitment"):
        verify_c4_stage1_live_review_boundary(
            repository_root=ROOT.resolve(),
            repository_gate=_repository_gate(),
            review_runtime_manifest=runtime,
            review_service_readiness=readiness,
            review_service=_ReviewService(other),
            expected_completed_review_count=0,
        )
    with pytest.raises(C4Stage1PreparationError, match="fresh and exact"):
        verify_c4_stage1_live_review_boundary(
            repository_root=ROOT.resolve(),
            repository_gate=_repository_gate(),
            review_runtime_manifest=runtime,
            review_service_readiness=readiness,
            review_service=_ReviewService(readiness, ledger_count=1),
            expected_completed_review_count=0,
        )

    verified_runtime, verified_readiness = verify_c4_stage1_live_review_boundary(
        repository_root=ROOT.resolve(),
        repository_gate=_repository_gate(),
        review_runtime_manifest=runtime,
        review_service_readiness=readiness,
        review_service=_ReviewService(readiness, ledger_count=2),
        expected_completed_review_count=2,
    )
    assert verified_runtime == runtime
    assert verified_readiness == readiness

    with pytest.raises(C4Stage1PreparationError, match="fresh and exact"):
        verify_c4_stage1_live_review_boundary(
            repository_root=ROOT.resolve(),
            repository_gate=_repository_gate(),
            review_runtime_manifest=runtime,
            review_service_readiness=readiness,
            review_service=_ReviewService(
                readiness, ledger_count=2, cohort_complete=False
            ),
            expected_completed_review_count=2,
        )


def test_live_review_boundary_rehashes_ui_before_use(tmp_path: Path) -> None:
    repository = (tmp_path / "repository").resolve()
    source = ROOT / "app/backend/rei/evaluation/c4_stage1_review_ui"
    target = repository / "app/backend/rei/evaluation/c4_stage1_review_ui"
    target.mkdir(parents=True)
    for name in ("index.html", "review.css", "review.js"):
        shutil.copy2(source / name, target / name)
    runtime = capture_c4_stage1_review_runtime_manifest(repository)
    _, readiness = _review_boundary()
    script = target / "review.js"
    script.write_bytes(script.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="differs from the pinned revision"):
        verify_c4_stage1_live_review_boundary(
            repository_root=repository,
            repository_gate=_repository_gate(),
            review_runtime_manifest=runtime,
            review_service_readiness=readiness,
            review_service=_ReviewService(readiness),
            expected_completed_review_count=0,
        )


def test_repository_gate_requires_live_equal_main_and_ignores_unrelated_dirt(
    tmp_path: Path,
) -> None:
    gate = capture_c4_stage1_repository_gate(
        tmp_path.resolve(),
        command_runner=_git_runner(),
        injected_git_runtime=_git_runtime_pin(),
    )

    assert gate.branch == "main"
    assert gate.origin_url == C4_STAGE1_ORIGIN_URL
    assert gate.git_runtime == _git_runtime_pin()
    assert gate.head_commit == gate.remote_origin_main_commit
    assert gate.scoped_paths == C4_STAGE1_GIT_SCOPE_PATHS
    assert gate.unrelated_worktree_changes_allowed is True
    assert "app/backend/requirements.txt" not in gate.scoped_paths
    assert ":(glob)scripts/run_rei_c4_stage1*.py" in gate.scoped_paths
    assert ":(glob)tests/evaluation/test_c4_stage1*.py" in gate.scoped_paths
    assert ":(glob)tests/rei/test_c4_stage1*.py" in gate.scoped_paths

    with pytest.raises(C4Stage1PreparationError, match="only on main"):
        capture_c4_stage1_repository_gate(
            tmp_path.resolve(),
            command_runner=_git_runner(branch="codex/unsafe"),
            injected_git_runtime=_git_runtime_pin(),
        )
    with pytest.raises(C4Stage1PreparationError, match="not committed"):
        capture_c4_stage1_repository_gate(
            tmp_path.resolve(),
            command_runner=_git_runner(dirty=" M app/backend/rei/unsafe.py\n"),
            injected_git_runtime=_git_runtime_pin(),
        )
    with pytest.raises(C4Stage1PreparationError, match="origin URL"):
        capture_c4_stage1_repository_gate(
            tmp_path.resolve(),
            command_runner=_git_runner(origin_url="https://example.invalid/repo.git"),
            injected_git_runtime=_git_runtime_pin(),
        )
    for tracked in (
        "S app/backend/rei/evaluation/c4_stage1_attempt.py\n",
        "h app/backend/rei/evaluation/c4_stage1_attempt.py\n",
    ):
        with pytest.raises(C4Stage1PreparationError, match="hides worktree changes"):
            capture_c4_stage1_repository_gate(
                tmp_path.resolve(),
                command_runner=_git_runner(tracked=tracked),
                injected_git_runtime=_git_runtime_pin(),
            )


def test_dino_entrypoint_pin_binds_exact_git_scope_bytes_and_gate() -> None:
    gate = _repository_gate()
    bootstrap = (ROOT / C4_STAGE1_DINO_BOOTSTRAP_SCRIPT_PATH).read_bytes()
    worker = (ROOT / C4_STAGE1_DINO_WORKER_SCRIPT_PATH).read_bytes()

    pin = C4Stage1DinoEntrypointPin.create(
        repository_gate=gate,
        bootstrap_script=bootstrap,
        worker_script=worker,
    )

    assert pin.repository_gate_id == gate.repository_gate_id
    assert pin.repository_gate_sha256 == gate.repository_gate_sha256
    assert pin.repository_head_commit == gate.head_commit
    assert tuple(item.role for item in pin.scripts) == (
        "dino-bootstrap",
        "dino-worker",
    )
    assert tuple(item.content_sha256 for item in pin.scripts) == (
        hashlib.sha256(bootstrap).hexdigest(),
        hashlib.sha256(worker).hexdigest(),
    )
    assert tuple(item.size_bytes for item in pin.scripts) == (
        len(bootstrap),
        len(worker),
    )
    assert str(ROOT).encode() not in pin.canonical_json_bytes()


@pytest.mark.parametrize("role", ("dino-bootstrap", "dino-worker"))
def test_cold_dino_entrypoint_copy_verification_rejects_replacement(
    tmp_path: Path,
    role: str,
) -> None:
    prepared = _prepared_attempt()
    store = attempt_module.FileArtifactStore(tmp_path / "runs")
    descriptors = {}
    for script_pin in prepared.dino_entrypoint_pin.scripts:
        payload = (ROOT / script_pin.repository_relative_path).read_bytes()
        relative_path = attempt_module._dino_script_copy_path(
            prepared.dino_entrypoint_pin,
            script_pin.role,
        )
        descriptors[relative_path] = store.write_bytes(
            prepared.run_id,
            relative_path,
            payload,
            overwrite=False,
        )

    attempt_module._cold_verify_dino_entrypoint_copies(
        store,
        prepared,
        descriptors,
    )
    target_pin = next(
        item for item in prepared.dino_entrypoint_pin.scripts if item.role == role
    )
    target_path = store.run_path(prepared.run_id) / attempt_module._dino_script_copy_path(
        prepared.dino_entrypoint_pin,
        target_pin.role,
    )
    target_path.write_bytes(b"replaced DINO entrypoint bytes")

    with pytest.raises(
        attempt_module.C4Stage1ColdVerificationError,
        match="not cold-readable|differs from its exact pin",
    ):
        attempt_module._cold_verify_dino_entrypoint_copies(
            store,
            prepared,
            descriptors,
        )


def test_worker_runtime_pin_uses_stable_executable_and_exact_runtime_inventory(
    tmp_path: Path,
) -> None:
    worker_python, worker_venv, base_runtime, _, runtime_metadata = _runtime_fixture(
        tmp_path
    )
    worker_bytes = worker_python.read_bytes()
    observed_paths: list[Path] = []

    def metadata_runner(path: Path):
        observed_paths.append(path)
        return runtime_metadata

    runtime = capture_c4_stage1_worker_runtime(
        worker_python,
        metadata_runner=metadata_runner,
    )

    assert observed_paths == [worker_python]
    assert runtime.worker_python_sha256 == hashlib.sha256(worker_bytes).hexdigest()
    assert runtime.dependencies == C4Stage1DependencyVersions()
    assert runtime.schema_version == "rei-c4-stage1-worker-runtime-pin-v2"
    assert runtime.worker_venv_inventory.tree_role == "worker-venv"
    assert runtime.base_runtime_inventory.tree_role == "base-runtime"
    assert runtime.worker_venv_inventory.pth_file_count == 1
    assert runtime.worker_venv_inventory.pth_files_executed is False
    assert runtime.runtime_inventory_file_count == (
        runtime.worker_venv_inventory.file_count
        + runtime.base_runtime_inventory.file_count
    )
    assert runtime.runtime_paths_stored is False
    assert runtime.site_activation_disabled is True
    assert runtime.complete_runtime_trees_inventory_verified is True
    assert runtime.inventory_recapture_required_before_every_spawn is True
    assert runtime.model_packages_imported_in_parent is False
    assert runtime.worker_python_path_stored is False
    assert str(worker_python).encode() not in runtime.canonical_json_bytes()
    assert str(worker_venv).encode() not in runtime.canonical_json_bytes()
    assert str(base_runtime).encode() not in runtime.canonical_json_bytes()
    assert b"frozen-package.py" not in runtime.canonical_json_bytes()
    assert not (tmp_path / "pth-executed").exists()

    mismatched = dict(runtime_metadata, torch="0.0.0")
    with pytest.raises(C4Stage1PreparationError, match="dependency versions"):
        capture_c4_stage1_worker_runtime(
            worker_python,
            metadata_runner=lambda _path: mismatched,
        )

    hardlink = (tmp_path / "python-hardlink.exe").resolve()
    hardlink.hardlink_to(worker_python)
    with pytest.raises(C4Stage1PreparationError, match="ordinary non-linked file"):
        capture_c4_stage1_worker_runtime(
            hardlink,
            metadata_runner=metadata_runner,
        )


def test_default_runtime_probe_is_isolated_no_site_and_explicit_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker_python, _, _, _, runtime_metadata = _runtime_fixture(tmp_path)
    observed: dict[str, object] = {}

    def fake_run(arguments, **kwargs):
        observed["arguments"] = arguments
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            arguments,
            0,
            stdout=json.dumps(runtime_metadata).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(attempt_module.subprocess, "run", fake_run)
    payload = attempt_module._default_worker_runtime_metadata_runner(worker_python)

    arguments = observed["arguments"]
    assert arguments[:4] == (os.fspath(worker_python), "-I", "-S", "-c")
    probe = arguments[4]
    assert probe.index("sys.dont_write_bytecode = True") < probe.index(
        "import importlib.metadata"
    )
    assert "metadata.distributions(path=[site_packages])" in probe
    assert "import site\n" not in probe
    assert payload == runtime_metadata
    kwargs = observed["kwargs"]
    assert kwargs["shell"] is False
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_runtime_inventory_changes_on_any_runtime_byte_mutation(
    tmp_path: Path,
) -> None:
    worker_python, _, _, package_payload, runtime_metadata = _runtime_fixture(tmp_path)
    before = capture_c4_stage1_worker_runtime(
        worker_python,
        metadata_runner=lambda _path: runtime_metadata,
    )

    package_payload.write_bytes(b"mutated-package-runtime-bytes")
    after = capture_c4_stage1_worker_runtime(
        worker_python,
        metadata_runner=lambda _path: runtime_metadata,
    )

    assert before.worker_python_sha256 == after.worker_python_sha256
    assert (
        before.worker_venv_inventory.tree_content_sha256
        != after.worker_venv_inventory.tree_content_sha256
    )
    assert before.runtime_inventory_sha256 != after.runtime_inventory_sha256
    assert before.worker_runtime_id != after.worker_runtime_id


def test_pre_spawn_reverification_rejects_runtime_inventory_mutation(
    tmp_path: Path,
) -> None:
    worker_python, worker_venv, base_runtime, package_payload, runtime_metadata = (
        _runtime_fixture(tmp_path / "runtime")
    )
    prepared_runtime = capture_c4_stage1_worker_runtime(
        worker_python,
        metadata_runner=lambda _path: runtime_metadata,
    )
    prepared = _prepared_attempt(worker_runtime=prepared_runtime)
    staging_parent = (tmp_path / "staging").resolve()
    staging_parent.mkdir()
    package_payload.write_bytes(b"changed-before-first-spawn")
    paths = C4Stage1RuntimePaths(
        repository_root=ROOT,
        worker_python=worker_python,
        source_png=worker_python,
        source_provenance=worker_venv / "pyvenv.cfg",
        primary_snapshot=worker_venv,
        alternate_snapshot=base_runtime,
        staging_parent=staging_parent,
    )

    with pytest.raises(C4Stage1PreparationError, match="runtime changed"):
        verify_c4_stage1_pre_spawn_runtime_bindings(
            paths,
            prepared,
            cuda_device=CUDA_DEVICE,
            metadata_runner=lambda _path: runtime_metadata,
        )


def test_runtime_inventory_rejects_hardlinks_reparse_and_customization(
    tmp_path: Path,
) -> None:
    hardlink_case = tmp_path / "hardlink-case"
    worker_python, _, _, package_payload, runtime_metadata = _runtime_fixture(
        hardlink_case
    )
    hardlink = package_payload.with_name("frozen-package-hardlink.py")
    hardlink.hardlink_to(package_payload)
    with pytest.raises(C4Stage1PreparationError, match="non-linked"):
        attempt_module._stable_read_regular(
            package_payload,
            maximum_bytes=1024,
        )
    with pytest.raises(C4Stage1PreparationError, match="non-linked"):
        capture_c4_stage1_worker_runtime(
            worker_python,
            metadata_runner=lambda _path: runtime_metadata,
        )

    customization_case = tmp_path / "customization-case"
    worker_python, _, _, package_payload, runtime_metadata = _runtime_fixture(
        customization_case
    )
    package_payload.with_name("sitecustomize.py").write_bytes(b"raise SystemExit\n")
    with pytest.raises(C4Stage1PreparationError, match="customization modules"):
        capture_c4_stage1_worker_runtime(
            worker_python,
            metadata_runner=lambda _path: runtime_metadata,
        )

    reparse_case = tmp_path / "reparse-case"
    worker_python, _, base_runtime, package_payload, runtime_metadata = (
        _runtime_fixture(reparse_case)
    )
    linked_payload = package_payload.with_name("linked-runtime.py")
    try:
        linked_payload.symlink_to(base_runtime / "python-runtime.dll")
    except OSError:
        return
    with pytest.raises(C4Stage1PreparationError, match="link or reparse"):
        capture_c4_stage1_worker_runtime(
            worker_python,
            metadata_runner=lambda _path: runtime_metadata,
        )


def test_runtime_paths_reject_nonregular_worker_and_linked_staging_ancestry(
    tmp_path: Path,
) -> None:
    staging_parent = (tmp_path / "staging").resolve()
    staging_parent.mkdir()
    assert verify_c4_stage1_staging_parent(staging_parent) == staging_parent

    worker_directory = (tmp_path / "worker-directory").resolve()
    worker_directory.mkdir()
    with pytest.raises(C4Stage1PreparationError, match="ordinary non-linked file"):
        capture_c4_stage1_worker_runtime(
            worker_directory,
            metadata_runner=lambda _path: RUNTIME_METADATA,
        )

    non_directory = (tmp_path / "not-a-staging-directory").resolve()
    non_directory.write_bytes(b"not a directory")
    with pytest.raises(
        C4Stage1PreparationError, match="ordinary non-reparse directory"
    ):
        verify_c4_stage1_staging_parent(non_directory)

    linked_parent = (tmp_path / "linked-staging").resolve()
    try:
        linked_parent.symlink_to(staging_parent, target_is_directory=True)
    except OSError:
        pytest.skip("This Windows account cannot create directory symlinks")
    with pytest.raises(C4Stage1PreparationError, match="link or reparse"):
        verify_c4_stage1_staging_parent(linked_parent)


def test_launch_policy_inherits_only_allowlisted_values_and_forces_offline() -> None:
    policy = C4Stage1LaunchPolicy.create(
        b"print('worker')\n",
        bootstrap_script=b"print('bootstrap')\n",
        cuda_device=CUDA_DEVICE,
        worker_runtime=_runtime_pin(),
    )
    environment = build_c4_stage1_worker_environment(
        policy,
        parent_environment={
            "SYSTEMROOT": r"C:\Windows",
            "PATH": r"C:\safe",
            "OPENAI_API_KEY": "must-not-reach-worker",
        },
    )

    assert environment["HF_HUB_OFFLINE"] == "1"
    assert environment["TRANSFORMERS_OFFLINE"] == "1"
    assert environment["SYSTEMROOT"] == r"C:\Windows"
    assert environment["CUDA_VISIBLE_DEVICES"] == CUDA_DEVICE.physical_gpu_uuid
    assert "OPENAI_API_KEY" not in environment
    assert r"C:\safe" not in policy.canonical_json_bytes().decode()
    assert policy.worker_runtime == _runtime_pin()
    assert policy.bootstrap_script_relative_path == C4_STAGE1_BOOTSTRAP_SCRIPT_PATH
    assert (
        policy.bootstrap_script_sha256
        == hashlib.sha256(b"print('bootstrap')\n").hexdigest()
    )
    assert policy.interpreter_isolation_flags == ("-I", "-S")
    assert policy.command_identity_scope == "worker-entrypoint-and-runtime-only-v1"
    assert policy.per_worker_process_request_identity_required is True
    assert policy.runtime_request_details_stored is False
    assert C4_STAGE1_TELEMETRY_JOIN_TIMEOUT_SECONDS == 2.0

    forged_policy = policy.model_dump(mode="python", round_trip=True)
    forged_policy["bootstrap_script_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="environment|canonical content"):
        C4Stage1LaunchPolicy.model_validate(forged_policy)

    remapped_wrong = ResourceTelemetryCudaDeviceIdentity.resolved(
        logical_device_index=1,
        physical_gpu_uuid=CUDA_DEVICE.physical_gpu_uuid,
        pci_bus_id=CUDA_DEVICE.pci_bus_id,
    )
    with pytest.raises(ValueError, match="exact CUDA identity"):
        C4Stage1LaunchPolicy.create(
            b"print('worker')\n",
            bootstrap_script=b"print('bootstrap')\n",
            cuda_device=remapped_wrong,
            worker_runtime=_runtime_pin(),
        )


def test_prepared_attempt_binds_two_one_time_policies_and_no_outputs() -> None:
    prepared = _prepared_attempt()

    assert len(prepared.review_operator_policies) == 2
    assert len({item.policy_id for item in prepared.review_operator_policies}) == 2
    assert tuple(item.editor_role for item in prepared.workers) == (
        "primary",
        "primary",
        "alternate",
        "alternate",
    )
    assert prepared.output_count == 0
    assert prepared.model_calls_before_prepared_anchor == 0
    assert prepared.worker_runtime == prepared.launch_policy.worker_runtime
    assert (
        prepared.source_provenance_sha256
        == prepared.screen_contract.source.source_provenance_sha256
    )
    assert prepared.source_provenance_storage_policy == "hash-only-runtime-binding-v1"
    assert prepared.source_provenance_bytes_stored is False
    assert prepared.staging_parent_ancestry_verified is True
    assert prepared.staging_parent_path_stored is False
    assert prepared.runtime_bindings_reverification_required_before_spawn is True

    forged = prepared.model_dump(mode="python", round_trip=True)
    forged["workers"][2]["operator_policy_id"] = prepared.review_operator_policies[
        0
    ].policy_id
    with pytest.raises(ValidationError, match="canonical content|operator policies"):
        C4Stage1PreparedAttempt.model_validate(forged)

    forged_provenance = prepared.model_dump(mode="python", round_trip=True)
    forged_provenance["source_provenance_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="screen contract|canonical content"):
        C4Stage1PreparedAttempt.model_validate(forged_provenance)


def test_prepared_worker_rejects_provider_option_order_forgery() -> None:
    worker = _prepared_attempt().workers[0]
    forged = worker.model_dump(mode="python", round_trip=True)
    forged["option_order_index"] = 1
    with pytest.raises(ValidationError, match="order differs"):
        C4Stage1PreparedWorker.model_validate(forged)
