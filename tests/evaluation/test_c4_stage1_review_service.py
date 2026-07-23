from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import threading
import time

import pytest

from rei.evaluation import c4_stage1_review as review_module
import rei.evaluation.c4_stage1_review_service as review_service_module

from rei.evaluation.c4_blind_review import (
    build_c4_human_review_operator_policy,
    build_c4_blind_presentation_manifest,
    commit_c4_review_material,
    prepare_c4_blind_review,
)
from rei.evaluation.c4_stage1_review import (
    C4Stage1DisplayContext,
    C4Stage1VisibleOutput,
    build_c4_stage1_display_attester_policy,
    build_c4_stage1_operator_unsigned_claim,
    _execute_c4_stage1_display_from_paths as execute_c4_stage1_display,
)
from rei.evaluation.c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY,
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
    C4_STAGE1_REVIEW_PRESENTER_REVISION,
    C4_STAGE1_REVIEW_UI_BUNDLE_SHA256,
)
from rei.evaluation.c4_stage1_review_service import (
    C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
    C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS,
    C4Stage1ReviewDisplayAttestationVerifier,
    C4Stage1ReviewDisplayPort,
    C4Stage1ReviewDisplayReceiptLedger,
    C4Stage1ReviewOperatorPolicyLedger,
    C4Stage1ReviewService,
    C4Stage1ReviewServiceClient,
    C4Stage1ReviewServiceError,
    C4Stage1ReviewServiceServer,
    c4_stage1_review_ipc_auth_message,
    c4_stage1_review_ipc_response_auth_message,
    C4Stage1AuthenticatedPresenterSubmission,
    C4Stage1OperatorSigningRequest,
    C4Stage1OperatorSigningLease,
)
from rei.evaluation.c4_stage1_review_presenter import (
    C4Stage1ReviewBrowserRuntimePin,
)
from rei.evaluation.c4_stage1_attempt import (
    C4Stage1GitRuntimePin,
    C4Stage1RepositoryGate,
)
from rei.ids import canonical_json_bytes, content_id

from . import test_c4_stage1_review as review_fixtures
from .test_c4_stage1_attempt import _external_runtime_pin


ROOT = Path(__file__).resolve().parents[2]


class RecordingPinnedPresenter:
    presenter_implementation_id = C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
    presenter_revision = C4_STAGE1_REVIEW_PRESENTER_REVISION

    def __init__(
        self, *, completed: bool = True, submission: bytes | None = None
    ) -> None:
        self.completed = completed
        self.submission = submission
        self.calls: list[tuple[object, bytes, tuple[object, object]]] = []
        self.session_timeout_ms = 1_000
        self.browser_runtime_pin = C4Stage1ReviewBrowserRuntimePin.create(
            browser_executable_sha256="b" * 64,
            browser_executable_size_bytes=1,
            external_runtime=_external_runtime_pin(chromium_sha256="b" * 64),
        )
        self.browser_executable_path = Path(sys.executable).resolve()
        self.browser_user_data_parent = self.browser_executable_path.parent
        self.runtime_provenance_root = self.browser_executable_path.parent
        self.external_runtime_root = self.browser_executable_path.parent
        self.external_browser_root = self.browser_executable_path.parent

    def present(
        self,
        context,
        source_png_bytes,
        outputs,
        *,
        cancellation_event: threading.Event | None = None,
    ) -> bool:
        if cancellation_event is not None and cancellation_event.is_set():
            return False
        self.calls.append((context, source_png_bytes, outputs))
        return self.completed

    def verify_operational(self) -> bool:
        return True

    def verify_runtime_pin(self, expected) -> bool:
        return expected == self.browser_runtime_pin

    def cancel_active(self) -> bool:
        return True

    def peek_submission(self, _context_id: str):
        if self.submission is None:
            raise RuntimeError("test presenter has no retained submission")
        return self.submission, datetime.now(timezone.utc)

    def discard_submission(
        self,
        _context_id: str,
        *,
        expected_submission: bytes,
        expected_submitted_at: datetime,
    ) -> bool:
        del expected_submitted_at
        if self.submission is None:
            return False
        if self.submission != expected_submission:
            raise RuntimeError("test presenter submission changed")
        self.submission = None
        return True


@pytest.fixture(autouse=True)
def _stable_repository_gate(monkeypatch: pytest.MonkeyPatch):
    git_runtime = C4Stage1GitRuntimePin.create(
        git_executable_sha256="a" * 64,
        git_executable_size_bytes=1,
        git_version="git version 2.0.0",
        trusted_location_class=(
            "windows-program-files-git-bin" if os.name == "nt" else "posix-usr-bin-git"
        ),
    )
    gate = C4Stage1RepositoryGate.create(
        git_runtime=git_runtime,
        head_commit="1" * 40,
        local_origin_main_commit="1" * 40,
        remote_origin_main_commit="1" * 40,
    )
    monkeypatch.setattr(
        review_service_module,
        "_capture_service_repository_gate",
        lambda _root: gate,
    )
    return gate


def test_review_client_allows_the_full_bounded_human_review_timeout(
    tmp_path: Path,
) -> None:
    auth = tmp_path / "ipc-auth.key"
    auth.write_bytes(b"a" * 32)
    client = C4Stage1ReviewServiceClient(
        "127.0.0.1",
        1,
        auth_secret_path=auth.resolve(),
        timeout_seconds=3_606,
    )
    assert (
        client._timeout_seconds  # noqa: SLF001 - exact timeout is the contract
        == 3_606
    )
    with pytest.raises(ValueError, match="timeout"):
        C4Stage1ReviewServiceClient(
            "127.0.0.1",
            1,
            auth_secret_path=auth.resolve(),
            timeout_seconds=3_604,
        )


def _service(
    tmp_path: Path,
    *,
    presenter: RecordingPinnedPresenter | None = None,
) -> tuple[C4Stage1ReviewService, RecordingPinnedPresenter, Path, Path, Path]:
    state_root = tmp_path / "service-state"
    artifact_root = tmp_path / "review-material"
    model_root = tmp_path / "model-snapshots"
    presenter = presenter or RecordingPinnedPresenter()
    service = C4Stage1ReviewService(
        state_root,
        artifact_roots=(artifact_root,),
        model_roots=(model_root,),
        presenter=presenter,
    )
    return service, presenter, state_root, artifact_root, model_root


def _review_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    service: C4Stage1ReviewService,
    *,
    suffix: str = "review-material",
):
    readiness = service.readiness
    original_policy_builder = build_c4_human_review_operator_policy
    original_display_builder = build_c4_stage1_display_attester_policy

    def policy_builder(schema, **kwargs):
        commitment_index = 1 if "alternate" in kwargs["candidate_slot_id"] else 0
        return original_policy_builder(
            schema,
            **{
                **kwargs,
                "hmac_key_commitment_sha256": (
                    readiness.operator_signing_key_commitment_sha256s[commitment_index]
                ),
            },
        )

    def display_builder(**kwargs):
        return original_display_builder(
            **{
                **kwargs,
                "ui_bundle_sha256": C4_STAGE1_REVIEW_UI_BUNDLE_SHA256,
                "content_security_policy": (C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY),
                "presenter_implementation_id": (
                    C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
                ),
                "presenter_revision": C4_STAGE1_REVIEW_PRESENTER_REVISION,
                "display_signing_key_commitment_sha256": (
                    readiness.display_signing_key_commitment_sha256
                ),
            }
        )

    monkeypatch.setattr(
        review_fixtures, "build_c4_human_review_operator_policy", policy_builder
    )
    monkeypatch.setattr(
        review_fixtures, "build_c4_stage1_display_attester_policy", display_builder
    )
    review_fixtures._model_free_publication_verifier.__wrapped__(monkeypatch)
    return review_fixtures._fixture(tmp_path, suffix=suffix)


def _execute_display(fixture, endpoint):
    return execute_c4_stage1_display(
        fixture.schema,
        fixture.packet,
        publication_binding=fixture.publication_binding,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        presentation_manifest=fixture.presentation,
        source_png_path=fixture.source_path,
        output_png_paths=fixture.output_paths,
        display_port=C4Stage1ReviewDisplayPort(endpoint),
        display_attestation_verifier=(
            C4Stage1ReviewDisplayAttestationVerifier(endpoint)
        ),
        ui_implementation_id=C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
        ui_revision=C4_STAGE1_REVIEW_PRESENTER_REVISION,
        ui_session_id="offline-review-session-1",
    )


def _submission_for(fixture, context) -> bytes:
    outputs, pair = review_fixtures._judgments(fixture)
    return canonical_json_bytes(
        {
            "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "serviceSchemaRevision": "rei-c4-stage1-review-service-v2",
            "ledgerSchemaRevision": "rei-c4-stage1-review-ledger-v2",
            "packetId": context.packet_id,
            "packetSha256": context.packet_sha256,
            "sourceImageSha256": context.source_image_sha256,
            "reviewerPseudonym": "offline-reviewer-1",
            "outputs": [
                {
                    "blindCode": judgment.blind_code,
                    "instructionSha256": judgment.instruction_sha256,
                    "outputSha256": judgment.output_sha256,
                    "judgments": {
                        field: getattr(judgment, field)
                        for field in (
                            "source_subject_present",
                            "identity_preserved",
                            "unchanged_composition_preserved",
                            "option_action_correct",
                            "no_extra_actor",
                            "no_generated_external_evidence_claim",
                            "reviewer_uncertain",
                        )
                    },
                }
                for judgment in outputs
            ],
            "pairJudgments": {
                "actions_visibly_distinct": pair.actions_visibly_distinct,
                "same_source_bytes_confirmed": pair.same_source_bytes_confirmed,
            },
        }
    )


def _claim(
    fixture,
    display_receipt,
    consumed_display_receipt,
    submission_receipt,
    signing_lease,
):
    outputs, pair = review_fixtures._judgments(fixture)
    return build_c4_stage1_operator_unsigned_claim(
        fixture.schema,
        fixture.packet,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        presentation_manifest=fixture.presentation,
        display_receipt=display_receipt,
        consumed_display_receipt=consumed_display_receipt,
        reviewer_pseudonym="offline-reviewer-1",
        review_timestamp=signing_lease.review_timestamp,
        output_judgments=outputs,
        pair_judgment=pair,
        submission_receipt_id=submission_receipt.submission_receipt_id,
        submission_receipt_sha256=submission_receipt.submission_receipt_sha256,
        operator_signing_lease_id=signing_lease.operator_signing_lease_id,
        operator_signing_lease_sha256=signing_lease.operator_signing_lease_sha256,
    )


def _clone_context_with_updates(context, **updates) -> C4Stage1DisplayContext:
    body = context.model_dump(
        mode="python", round_trip=True, exclude={"context_id", "context_sha256"}
    )
    body.update(updates)
    return C4Stage1DisplayContext(
        context_id=content_id("c4_stage1_display_context", body),
        context_sha256=hashlib.sha256(canonical_json_bytes(body)).hexdigest(),
        **body,
    )


def _clone_context_with_session(context, session: str) -> C4Stage1DisplayContext:
    return _clone_context_with_updates(context, ui_session_id=session)


def _visible_outputs(context, fixture):
    return tuple(
        C4Stage1VisibleOutput(
            blind_code=reference.blind_code,
            blind_order_sha256=reference.blind_order_sha256,
            instruction=reference.instruction,
            instruction_sha256=reference.instruction_sha256,
            output_sha256=reference.output_sha256,
            png_bytes=value,
        )
        for reference, value in zip(context.outputs, fixture.output_bytes, strict=True)
    )


def _concurrent_once(callable_):
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(callable_) for _ in range(8)]
    successes = []
    failures = []
    for future in futures:
        try:
            successes.append(future.result())
        except (ValueError, C4Stage1ReviewServiceError) as exc:
            failures.append(exc)
    assert len(successes) == 1
    assert len(failures) == 7
    return successes[0]


def _prepare_signing_flow(service, presenter, fixture):
    display_receipt = _execute_display(fixture, service)
    presenter.submission = _submission_for(fixture, display_receipt.context)
    submission_receipt = service.take_presentation_submission(
        context_id=display_receipt.context.context_id
    )
    consumed_display = C4Stage1ReviewDisplayReceiptLedger(service).consume_once(
        display_receipt=display_receipt
    )
    signing_lease = service.issue_operator_signing_lease(
        operator_policy=fixture.policy,
        submission_receipt=submission_receipt,
        display_receipt=display_receipt,
        consumed_display_receipt=consumed_display,
    )
    claim = _claim(
        fixture,
        display_receipt,
        consumed_display,
        submission_receipt,
        signing_lease,
    )
    return (
        display_receipt,
        submission_receipt,
        consumed_display,
        signing_lease,
        claim,
    )


def _paired_review_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    service: C4Stage1ReviewService,
    *,
    suffix: str = "review-material",
    alternate_operator_commitment_index: int = 1,
):
    """Build one real primary/alternate pair from one prepared-attempt identity."""

    original = _review_fixture(tmp_path, monkeypatch, service, suffix=suffix)
    alternate_policy = build_c4_human_review_operator_policy(
        original.schema,
        run_id=original.policy.run_id,
        candidate_slot_id=f"{original.policy.candidate_slot_id}-alternate-cohort",
        source_image_sha256=original.policy.source_image_sha256,
        hmac_key_commitment_sha256=(
            service.readiness.operator_signing_key_commitment_sha256s[
                alternate_operator_commitment_index
            ]
        ),
    )
    screen_contract = review_fixtures._screen_contract(
        original.schema,
        original.policy,
        alternate_policy,
        original.display_policy,
    )
    primary = replace(
        original,
        alternate_policy=alternate_policy,
        screen_contract=screen_contract,
    )
    alternate_commitment = commit_c4_review_material(
        primary.schema,
        operator_policy=alternate_policy,
        source_image_sha256=primary.commitment.source_image_sha256,
        renderer_id=primary.commitment.renderer_id,
        model_id=primary.commitment.model_id,
        model_revision=primary.commitment.model_revision,
        options=primary.commitment.options,
    )
    alternate_packet = prepare_c4_blind_review(
        primary.schema,
        alternate_commitment,
        operator_policy=alternate_policy,
    )
    path_by_sha256 = {
        hashlib.sha256(path.read_bytes()).hexdigest(): path
        for path in primary.output_paths
    }
    alternate_output_paths = tuple(
        path_by_sha256[item.output_sha256] for item in alternate_packet.outputs
    )
    alternate_presentation = build_c4_blind_presentation_manifest(
        alternate_packet,
        operator_policy=alternate_policy,
        source_png_path=primary.source_path,
        output_png_paths=alternate_output_paths,
    )

    binding = primary.publication_binding
    member_id = f"{binding.member_publication_receipt_id}-alternate"
    member_sha256 = hashlib.sha256(member_id.encode("utf-8")).hexdigest()
    member_storage_sha256 = hashlib.sha256(
        f"{member_id}-storage".encode("utf-8")
    ).hexdigest()
    member_relative_path = f"diagnostics/{member_id}.member-publication.json"
    member_storage_type = type(binding.member_publication_receipt_storage)
    member_storage = member_storage_type(
        storage_id=review_fixtures.stored_artifact_id(
            run_id=binding.run_id,
            relative_path=member_relative_path,
            content_sha256=member_storage_sha256,
            size_bytes=1,
        ),
        run_id=binding.run_id,
        relative_path=member_relative_path,
        content_sha256=member_storage_sha256,
        size_bytes=1,
    )
    candidate_type = type(binding.candidates[0])
    alternate_candidates = tuple(
        candidate_type(
            option_id=item.option_id,
            candidate_receipt_id=f"{item.candidate_receipt_id}-alternate",
            candidate_receipt_sha256=hashlib.sha256(
                f"{item.candidate_receipt_id}-alternate".encode("utf-8")
            ).hexdigest(),
            prepared_worker_id=f"{item.prepared_worker_id}-alternate",
            prepared_worker_sha256=hashlib.sha256(
                f"{item.prepared_worker_id}-alternate".encode("utf-8")
            ).hexdigest(),
            worker_request_id=f"{item.worker_request_id}-alternate",
            worker_request_sha256=hashlib.sha256(
                f"{item.worker_request_id}-alternate".encode("utf-8")
            ).hexdigest(),
            staged_output_storage=item.staged_output_storage,
        )
        for item in binding.candidates
    )
    publication_type = type(binding)
    alternate_binding = publication_type.create(
        run_id=binding.run_id,
        prepared_attempt_id=binding.prepared_attempt_id,
        prepared_attempt_sha256=binding.prepared_attempt_sha256,
        prepared_anchor_storage=binding.prepared_anchor_storage,
        member_publication_receipt_id=member_id,
        member_publication_receipt_sha256=member_sha256,
        member_publication_receipt_storage=member_storage,
        editor_role="alternate",
        provider_slot_id=alternate_policy.candidate_slot_id,
        source_storage=binding.source_storage,
        candidates=alternate_candidates,
    )
    alternate = replace(
        primary,
        policy=alternate_policy,
        alternate_policy=primary.policy,
        commitment=alternate_commitment,
        packet=alternate_packet,
        presentation=alternate_presentation,
        publication_binding=alternate_binding,
        output_paths=alternate_output_paths,
        output_bytes=tuple(path.read_bytes() for path in alternate_output_paths),
    )
    return primary, alternate


def _signing_request(fixture, flow) -> C4Stage1OperatorSigningRequest:
    return C4Stage1OperatorSigningRequest(
        operator_policy=fixture.policy,
        claim=flow[4],
        submission_receipt=flow[1],
        operator_signing_lease=flow[3],
        display_receipt=flow[0],
        consumed_display_receipt=flow[2],
    )


def _readdress_stage1_claim(claim, **updates):
    body = claim.model_dump(
        mode="python",
        round_trip=True,
        exclude={"claim_id", "claim_sha256"},
    )
    body.update(updates)
    return type(claim)(
        claim_id=content_id("c4_stage1_review_claim", body),
        claim_sha256=hashlib.sha256(canonical_json_bytes(body)).hexdigest(),
        **body,
    )


def _prepare_signing_cohort(
    service: C4Stage1ReviewService,
    presenter: RecordingPinnedPresenter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    suffix: str = "review-material",
    alternate_operator_commitment_index: int = 1,
    endpoint=None,
):
    fixtures = _paired_review_fixtures(
        tmp_path,
        monkeypatch,
        service,
        suffix=suffix,
        alternate_operator_commitment_index=alternate_operator_commitment_index,
    )
    review_endpoint = service if endpoint is None else endpoint
    flows = tuple(
        _prepare_signing_flow(review_endpoint, presenter, fixture)
        for fixture in fixtures
    )
    requests = tuple(
        _signing_request(fixture, flow)
        for fixture, flow in zip(fixtures, flows, strict=True)
    )
    return fixtures, flows, requests


def test_state_is_create_only_link_safe_and_exposes_only_commitments(
    tmp_path: Path,
) -> None:
    service, _, state_root, artifact_root, model_root = _service(tmp_path)
    readiness = service.readiness
    health = service.health()

    assert readiness.secret_count == 5
    assert readiness.secret_size_bytes == 32
    assert readiness.ipc_auth_required is True
    assert readiness.ipc_auth_secret_separate_from_review_keys is True
    assert health["ready"] is True
    assert health["sqlite_journal_mode"] == "wal"
    assert health["sqlite_synchronous"] == "FULL"

    secret_paths = sorted(state_root.glob("*.key"))
    assert len(secret_paths) == 5
    secret_values = [path.read_bytes() for path in secret_paths]
    assert {len(value) for value in secret_values} == {32}
    assert len(set(secret_values)) == 5
    public = readiness.canonical_json_bytes() + canonical_json_bytes(health)
    assert all(value not in public for value in secret_values)
    database = state_root / "review-ledgers.sqlite3"
    assert all(value not in database.read_bytes() for value in secret_values)

    service.close()
    restarted = C4Stage1ReviewService(
        state_root,
        artifact_roots=(artifact_root,),
        model_roots=(model_root,),
        presenter=RecordingPinnedPresenter(),
    )
    assert restarted.readiness == readiness
    restarted.close()

    hardlink = tmp_path / "secret-hardlink"
    os.link(secret_paths[0], hardlink)
    with pytest.raises(C4Stage1ReviewServiceError, match="ordinary file"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_state_rejects_concurrent_owner_clone_and_incomplete_restart(
    tmp_path: Path,
) -> None:
    service, _, state_root, artifact_root, model_root = _service(tmp_path)
    with pytest.raises(C4Stage1ReviewServiceError, match="live owner"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )
    service.close()

    clone_root = tmp_path / "copied-service-state"
    shutil.copytree(state_root, clone_root)
    with pytest.raises(C4Stage1ReviewServiceError, match="copied or rebound"):
        C4Stage1ReviewService(
            clone_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )

    secret = next(state_root.glob("*.key"))
    secret.unlink()
    with pytest.raises(C4Stage1ReviewServiceError, match="exact restart"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_owner_lock_file_is_live_and_link_safe(tmp_path: Path) -> None:
    service, _, state_root, _, _ = _service(tmp_path)
    owner_lock = state_root / review_service_module._STATE_OWNER_LOCK_FILE
    external_link = tmp_path / "owner-lock-hardlink"
    os.link(owner_lock, external_link)
    with pytest.raises(C4Stage1ReviewServiceError, match="ordinary file"):
        service.health()
    service.close()


def test_repository_gate_and_browser_runtime_are_live_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _stable_repository_gate: C4Stage1RepositoryGate,
) -> None:
    current = [_stable_repository_gate]
    monkeypatch.setattr(
        review_service_module,
        "_capture_service_repository_gate",
        lambda _root: current[0],
    )
    service, presenter, _, _, _ = _service(tmp_path)
    current[0] = C4Stage1RepositoryGate.create(
        git_runtime=_stable_repository_gate.git_runtime,
        head_commit="2" * 40,
        local_origin_main_commit="2" * 40,
        remote_origin_main_commit="2" * 40,
    )
    with pytest.raises(
        C4Stage1ReviewServiceError, match="changed after service startup"
    ):
        service.health()
    service.close()

    current[0] = _stable_repository_gate
    browser_root = tmp_path / "browser-drift"
    browser_root.mkdir()
    service, presenter, _, _, _ = _service(browser_root)
    fixture = _review_fixture(browser_root, monkeypatch, service)
    presenter.browser_runtime_pin = C4Stage1ReviewBrowserRuntimePin.create(
        browser_executable_sha256="c" * 64,
        browser_executable_size_bytes=1,
        external_runtime=_external_runtime_pin(chromium_sha256="c" * 64),
    )
    health = service.health()
    assert health["ready"] is False
    assert health["browser_runtime_matches_readiness"] is False
    with pytest.raises(ValueError, match="trusted display execution failed"):
        _execute_display(fixture, service)
    service.close()

    other_checkout = tmp_path / "other-checkout"
    other_checkout.mkdir()
    with pytest.raises(C4Stage1ReviewServiceError, match="second checkout"):
        C4Stage1ReviewService(
            tmp_path / "other-state",
            artifact_roots=(tmp_path / "other-artifacts",),
            model_roots=(tmp_path / "other-models",),
            presenter=RecordingPinnedPresenter(),
            repository_root=other_checkout,
        )


@pytest.mark.parametrize(
    "root_attribute",
    (
        "runtime_provenance_root",
        "external_runtime_root",
        "external_browser_root",
    ),
)
def test_presenter_sealed_runtime_roots_are_live_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    root_attribute: str,
) -> None:
    service, presenter, _, _, _ = _service(tmp_path)
    fixture = _review_fixture(tmp_path, monkeypatch, service)
    replacement = tmp_path / f"{root_attribute}-replacement"
    replacement.mkdir()
    setattr(presenter, root_attribute, replacement.resolve())

    health = service.health()
    assert health["ready"] is False
    assert health["presenter_boundary_roots_match_startup"] is False
    assert health["browser_runtime_matches_readiness"] is False
    with pytest.raises(
        C4Stage1ReviewServiceError,
        match="boundary roots changed after service startup",
    ):
        _ = service.readiness

    with pytest.raises(ValueError, match="trusted display execution failed"):
        _execute_display(fixture, service)
    service.close()


def test_state_overlap_and_unpinned_presenter_fail_closed(tmp_path: Path) -> None:
    class WrongPresenter:
        presenter_implementation_id = "generic-viewer"
        presenter_revision = "generic-viewer-v1"

        def present(self, _context, _source, _outputs):
            return True

    with pytest.raises(TypeError, match="pinned HTML host"):
        C4Stage1ReviewService(
            tmp_path / "wrong-presenter-state",
            artifact_roots=(tmp_path / "artifacts",),
            model_roots=(tmp_path / "models",),
            presenter=WrongPresenter(),
        )

    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    with pytest.raises(C4Stage1ReviewServiceError, match="overlaps"):
        C4Stage1ReviewService(
            artifact_root / "state",
            artifact_roots=(artifact_root,),
            model_roots=(tmp_path / "models",),
            presenter=RecordingPinnedPresenter(),
        )

    sealed_runtime = tmp_path / "sealed-runtime"
    sealed_runtime.mkdir()
    presenter = RecordingPinnedPresenter()
    presenter.external_runtime_root = sealed_runtime
    with pytest.raises(C4Stage1ReviewServiceError, match="overlaps"):
        C4Stage1ReviewService(
            sealed_runtime / "state",
            artifact_roots=(tmp_path / "other-artifacts",),
            model_roots=(tmp_path / "other-models",),
            presenter=presenter,
        )


def test_presenter_submission_is_canonical_and_consumed_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submission = canonical_json_bytes({"complete": True})
    service, _, _, _, _ = _service(
        tmp_path,
        presenter=RecordingPinnedPresenter(submission=submission),
    )
    fixture = _review_fixture(tmp_path, monkeypatch, service)
    display_receipt = _execute_display(fixture, service)

    with pytest.raises(C4Stage1ReviewServiceError, match="exact context"):
        service.take_presentation_submission(
            context_id=display_receipt.context.context_id
        )
    with pytest.raises(C4Stage1ReviewServiceError, match="exact context"):
        service.take_presentation_submission(
            context_id=display_receipt.context.context_id
        )
    service.close()


def test_preseal_authority_uses_opaque_context_and_journals_authenticated_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, state_root, _, _ = _service(tmp_path)
    fixture = _review_fixture(tmp_path, monkeypatch, service)
    context = review_module._build_display_context(
        fixture.schema,
        fixture.packet,
        fixture.policy,
        fixture.presentation,
        fixture.screen_contract,
        fixture.display_policy,
        ui_implementation_id=C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
        ui_revision=C4_STAGE1_REVIEW_PRESENTER_REVISION,
        ui_session_id="opaque-preseal-context",
    )
    service.display(
        context=context,
        display_policy=fixture.display_policy,
        source_png_bytes=fixture.source_bytes,
        outputs=_visible_outputs(context, fixture),  # type: ignore[arg-type]
    )
    database = state_root / "review-ledgers.sqlite3"
    connection = sqlite3.connect(database)
    try:
        table = review_service_module._PRESENTATION_CONTEXT_TABLE
        columns = tuple(
            item[1] for item in connection.execute(f"PRAGMA table_info({table})")
        )
        assert columns == ("opaque_context_hmac_sha256", "created_at")
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
        assert len(rows) == 1
        assert len(rows[0][0]) == 64
        assert connection.execute(
            f"SELECT COUNT(*) FROM {review_service_module._PRESENTER_SUBMISSION_TABLE}"
        ).fetchone() == (0,)
        assert connection.execute(
            f"SELECT COUNT(*) FROM {review_service_module._OPERATOR_SIGNING_LEASE_TABLE}"
        ).fetchone() == (0,)
        journal_row = connection.execute(
            f"SELECT operation, status, result_json, result_sha256, "
            f"result_size_bytes, effect_kind, row_auth_hmac_sha256 "
            f"FROM {review_service_module._STATEFUL_OPERATION_RESULT_TABLE}"
        ).fetchone()
        assert journal_row is not None
        assert journal_row[:2] == ("display", "completed")
        assert hashlib.sha256(journal_row[2]).hexdigest() == journal_row[3]
        assert len(journal_row[2]) == journal_row[4]
        assert journal_row[5] == "display-attestation"
        assert len(journal_row[6]) == 64
        assert context.context_id.encode() in journal_row[2]
    finally:
        connection.close()
    service.close()


def test_atomic_cohort_operator_receipt_is_restart_safe_and_delivered_once_under_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    fixtures, _, requests = _prepare_signing_cohort(
        service, presenter, tmp_path, monkeypatch
    )
    attestations = service.sign_operator_claim_cohort(reviews=requests)
    operator_ledger = C4Stage1ReviewOperatorPolicyLedger(service)
    consumed_operator = _concurrent_once(
        lambda: operator_ledger.consume_once(
            operator_policy=fixtures[0].policy,
            attestation=attestations[0],
        )
    )
    second_consumed = operator_ledger.consume_once(
        operator_policy=fixtures[1].policy,
        attestation=attestations[1],
    )

    service.close()
    restarted = C4Stage1ReviewService(
        state_root,
        artifact_roots=(artifact_root,),
        model_roots=(model_root,),
        presenter=RecordingPinnedPresenter(),
    )
    assert C4Stage1ReviewOperatorPolicyLedger(restarted).verify_consumed_use(
        operator_policy=fixtures[0].policy,
        attestation=attestations[0],
        consumed_receipt=consumed_operator,
    )
    assert C4Stage1ReviewOperatorPolicyLedger(restarted).verify_consumed_use(
        operator_policy=fixtures[1].policy,
        attestation=attestations[1],
        consumed_receipt=second_consumed,
    )
    with pytest.raises(ValueError, match="operator policy replay"):
        C4Stage1ReviewOperatorPolicyLedger(restarted).consume_once(
            operator_policy=fixtures[0].policy,
            attestation=attestations[0],
        )
    restarted.close()


def test_stateful_ipc_reset_after_commit_retries_all_operations_and_recovers_exact_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    remaining = set(review_service_module._STATEFUL_OPERATIONS)
    dropped: dict[str, tuple[str, bytes]] = {}
    delivered: dict[str, tuple[str, bytes]] = {}
    fault_lock = threading.Lock()
    original_handle = review_service_module._C4Stage1ReviewRequestHandler.handle

    class ResetAfterCommitWriter:
        def __init__(self, inner, connection: socket.socket) -> None:
            self._inner = inner
            self._connection = connection

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

        def write(self, value: bytes) -> int:
            response = json.loads(bytes(value).removesuffix(b"\n"))
            operation = response.get("operation")
            should_reset = False
            if response.get("ok") is True and operation in remaining | dropped.keys():
                canonical_result = canonical_json_bytes(response["result"])
                with fault_lock:
                    if operation in remaining:
                        remaining.remove(operation)
                        dropped[operation] = (
                            response["request_nonce"],
                            canonical_result,
                        )
                        should_reset = True
                    elif operation in dropped and operation not in delivered:
                        delivered[operation] = (
                            response["request_nonce"],
                            canonical_result,
                        )
            if should_reset:
                linger = (
                    struct.pack("hh", 1, 0)
                    if os.name == "nt"
                    else struct.pack("ii", 1, 0)
                )
                self._connection.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    linger,
                )
                self._connection.close()
                raise OSError("injected reset after durable completion")
            return self._inner.write(value)

    def faulting_handle(handler) -> None:
        handler.wfile = ResetAfterCommitWriter(handler.wfile, handler.connection)
        original_handle(handler)

    with monkeypatch.context() as fault_injection:
        fault_injection.setattr(
            review_service_module._C4Stage1ReviewRequestHandler,
            "handle",
            faulting_handle,
        )
        with C4Stage1ReviewServiceServer(service) as server:
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            client = C4Stage1ReviewServiceClient(
                *server.address,
                auth_secret_path=(state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME),
                timeout_seconds=6,
                presenter_timeout_ms=1_000,
            )
            try:
                fixtures, _, requests = _prepare_signing_cohort(
                    service,
                    presenter,
                    tmp_path,
                    monkeypatch,
                    endpoint=client,
                )
                attestations = client.sign_operator_claim_cohort(reviews=requests)
                consumed = tuple(
                    C4Stage1ReviewOperatorPolicyLedger(client).consume_once(
                        operator_policy=fixture.policy,
                        attestation=attestation,
                    )
                    for fixture, attestation in zip(fixtures, attestations, strict=True)
                )
            finally:
                server.shutdown()
                server_thread.join(timeout=5)
                assert not server_thread.is_alive()

    expected_counts = {
        "display": 2,
        "take_presentation_submission": 2,
        "consume_display_attestation": 2,
        "consume_display_receipt": 2,
        "issue_operator_signing_lease": 2,
        "sign_operator_claim_cohort": 1,
        "consume_operator_policy": 2,
    }
    assert remaining == set()
    assert set(dropped) == set(expected_counts)
    assert set(delivered) == set(expected_counts)
    for operation in expected_counts:
        dropped_nonce, dropped_result = dropped[operation]
        delivered_nonce, delivered_result = delivered[operation]
        assert delivered_nonce != dropped_nonce
        assert delivered_result == dropped_result
    assert len(presenter.calls) == 2

    with sqlite3.connect(state_root / "review-ledgers.sqlite3") as connection:
        rows = connection.execute(
            f"SELECT operation, status, COUNT(*) "
            f"FROM {review_service_module._STATEFUL_OPERATION_RESULT_TABLE} "
            "GROUP BY operation, status"
        ).fetchall()
    assert {(operation, status): count for operation, status, count in rows} == {
        (operation, "completed"): count for operation, count in expected_counts.items()
    }

    restarted = C4Stage1ReviewService(
        state_root,
        artifact_roots=(artifact_root,),
        model_roots=(model_root,),
        presenter=RecordingPinnedPresenter(),
    )
    with C4Stage1ReviewServiceServer(restarted) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = C4Stage1ReviewServiceClient(
            *server.address,
            auth_secret_path=state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
            timeout_seconds=6,
            presenter_timeout_ms=1_000,
        )
        try:
            assert client.sign_operator_claim_cohort(reviews=requests) == attestations
            for fixture, attestation, receipt in zip(
                fixtures, attestations, consumed, strict=True
            ):
                assert (
                    C4Stage1ReviewOperatorPolicyLedger(client).consume_once(
                        operator_policy=fixture.policy,
                        attestation=attestation,
                    )
                    == receipt
                )
            with pytest.raises(C4Stage1ReviewServiceError, match="cohort|replay"):
                client.sign_operator_claim_cohort(reviews=(requests[1], requests[0]))
        finally:
            server.shutdown()
            server_thread.join(timeout=5)
            assert not server_thread.is_alive()


def test_authenticated_submission_and_signing_lease_reject_forgery_reuse_and_cross_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, _, _, _ = _service(tmp_path)
    fixtures, flows, requests = _prepare_signing_cohort(
        service, presenter, tmp_path, monkeypatch
    )
    fixture = fixtures[0]
    display_receipt, submission_receipt, consumed_display, signing_lease, _ = flows[0]
    assert isinstance(submission_receipt, C4Stage1AuthenticatedPresenterSubmission)
    assert isinstance(signing_lease, C4Stage1OperatorSigningLease)
    assert service.verify_authenticated_submission(
        submission_receipt=submission_receipt
    )
    assert service.verify_operator_signing_lease(operator_signing_lease=signing_lease)

    forged_submission = submission_receipt.model_copy(
        update={"service_auth_hmac_sha256": "0" * 64}
    )
    forged_lease = signing_lease.model_copy(
        update={"service_auth_hmac_sha256": "0" * 64}
    )
    assert not service.verify_authenticated_submission(
        submission_receipt=forged_submission
    )
    assert not service.verify_operator_signing_lease(
        operator_signing_lease=forged_lease
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="cross a retained"):
        service.issue_operator_signing_lease(
            operator_policy=fixture.alternate_policy,
            submission_receipt=submission_receipt,
            display_receipt=display_receipt,
            consumed_display_receipt=consumed_display,
        )
    forged_request = C4Stage1OperatorSigningRequest(
        operator_policy=requests[0].operator_policy,
        claim=requests[0].claim,
        submission_receipt=forged_submission,
        operator_signing_lease=forged_lease,
        display_receipt=requests[0].display_receipt,
        consumed_display_receipt=requests[0].consumed_display_receipt,
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="retained|authenticated"):
        service.sign_operator_claim_cohort(reviews=(forged_request, requests[1]))
    attestations = service.sign_operator_claim_cohort(reviews=requests)
    assert all(
        service.verify_operator_attestation(
            operator_policy=fixture.policy,
            attestation=attestation,
        )
        for fixture, attestation in zip(fixtures, attestations, strict=True)
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="cohort|replay"):
        service.sign_operator_claim_cohort(reviews=requests)
    service.close()


@pytest.mark.parametrize("mutation", ("presentation-manifest", "source-image"))
def test_readdressed_claim_exact_bindings_fail_before_any_operator_hmac(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    service, presenter, _, _, _ = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    original = requests[0]
    if mutation == "presentation-manifest":
        forged_claim = _readdress_stage1_claim(
            original.claim,
            presentation_manifest_id="forged-presentation-manifest",
            presentation_manifest_sha256="f" * 64,
        )
    else:
        forged_judgments = tuple(
            type(judgment)(
                **{
                    **judgment.model_dump(mode="python", round_trip=True),
                    "source_image_sha256": "f" * 64,
                }
            )
            for judgment in original.claim.output_judgments
        )
        forged_claim = _readdress_stage1_claim(
            original.claim,
            output_judgments=forged_judgments,
        )
    forged_request = C4Stage1OperatorSigningRequest(
        operator_policy=original.operator_policy,
        claim=forged_claim,
        submission_receipt=original.submission_receipt,
        operator_signing_lease=original.operator_signing_lease,
        display_receipt=original.display_receipt,
        consumed_display_receipt=original.consumed_display_receipt,
    )
    original_builder = review_service_module.build_c4_stage1_operator_attestation
    signer_calls = 0

    def counted_builder(*args, **kwargs):
        nonlocal signer_calls
        signer_calls += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        review_service_module,
        "build_c4_stage1_operator_attestation",
        counted_builder,
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="claim|judgment|retained"):
        service.sign_operator_claim_cohort(reviews=(forged_request, requests[1]))
    assert signer_calls == 0
    assert service.health()["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    assert service.health()["operator_signing_cohort_complete"] is False
    service.close()


def test_operator_signing_lease_uses_the_service_clock_and_expires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, _, _, _ = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    service._clock = lambda: (  # noqa: SLF001 - expiry is the test input
        requests[0].operator_signing_lease.expires_at + timedelta(seconds=1)
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="expired"):
        service.sign_operator_claim_cohort(reviews=requests)
    assert service.health()["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    service.close()


def test_single_review_has_no_signing_surface_and_restart_rejects_partial_precohort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    fixture = _paired_review_fixtures(tmp_path, monkeypatch, service)[0]
    flow = _prepare_signing_flow(service, presenter, fixture)
    request = _signing_request(fixture, flow)
    original_builder = review_service_module.build_c4_stage1_operator_attestation
    signer_calls = 0

    def counted_builder(*args, **kwargs):
        nonlocal signer_calls
        signer_calls += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        review_service_module,
        "build_c4_stage1_operator_attestation",
        counted_builder,
    )
    assert not hasattr(service, "sign_operator_claim")
    with pytest.raises(C4Stage1ReviewServiceError, match="exactly two|cohort"):
        service.sign_operator_claim_cohort(reviews=(request,))  # type: ignore[arg-type]
    assert signer_calls == 0
    health = service.health()
    assert health["operator_signing_cohort_complete"] is False
    assert health["ledger_counts"] == {
        "display_attestation_uses": 1,
        "display_receipt_uses": 1,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    with sqlite3.connect(state_root / "review-ledgers.sqlite3") as connection:
        assert connection.execute(
            f"SELECT COUNT(*) FROM {review_service_module._PRESENTATION_CONTEXT_TABLE}"
        ).fetchone() == (1,)
    service.close()

    with pytest.raises(C4Stage1ReviewServiceError, match="partial|incomplete|cohort"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_cross_prepared_attempt_cohort_mixing_rejects_without_consuming_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = tmp_path / "service-state"
    artifact_roots = (tmp_path / "cohort-a", tmp_path / "cohort-b")
    model_root = tmp_path / "model-snapshots"
    presenter = RecordingPinnedPresenter()
    service = C4Stage1ReviewService(
        state_root,
        artifact_roots=artifact_roots,
        model_roots=(model_root,),
        presenter=presenter,
    )
    cohort_a = _paired_review_fixtures(
        tmp_path, monkeypatch, service, suffix="cohort-a"
    )
    cohort_b = _paired_review_fixtures(
        tmp_path, monkeypatch, service, suffix="cohort-b"
    )
    first_flow = _prepare_signing_flow(service, presenter, cohort_a[0])
    second_flow = _prepare_signing_flow(service, presenter, cohort_b[1])
    mixed = (
        _signing_request(cohort_a[0], first_flow),
        _signing_request(cohort_b[1], second_flow),
    )

    with pytest.raises(C4Stage1ReviewServiceError, match="cohort"):
        service.sign_operator_claim_cohort(reviews=mixed)
    assert all(
        service.verify_authenticated_submission(
            submission_receipt=request.submission_receipt
        )
        and service.verify_operator_signing_lease(
            operator_signing_lease=request.operator_signing_lease
        )
        for request in mixed
    )
    health = service.health()
    assert health["operator_signing_cohort_complete"] is False
    assert health["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    with sqlite3.connect(state_root / "review-ledgers.sqlite3") as connection:
        assert connection.execute(
            f"SELECT COUNT(*) FROM {review_service_module._PRESENTATION_CONTEXT_TABLE}"
        ).fetchone() == (2,)
    service.close()


def test_two_review_cohort_requires_both_distinct_service_operator_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, _, _, _ = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(
        service,
        presenter,
        tmp_path,
        monkeypatch,
        alternate_operator_commitment_index=0,
    )
    assert (
        requests[0].operator_policy.hmac_key_commitment_sha256
        == requests[1].operator_policy.hmac_key_commitment_sha256
    )
    original_builder = review_service_module.build_c4_stage1_operator_attestation
    signer_calls = 0

    def counted_builder(*args, **kwargs):
        nonlocal signer_calls
        signer_calls += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        review_service_module,
        "build_c4_stage1_operator_attestation",
        counted_builder,
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="cohort"):
        service.sign_operator_claim_cohort(reviews=requests)
    assert signer_calls == 0
    assert service.health()["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    assert service.health()["operator_signing_cohort_complete"] is False
    service.close()


def test_two_review_cohort_rejects_mixed_context_rubric_before_operator_hmac(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, _, _, _ = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    forged_context = _clone_context_with_updates(
        requests[1].display_receipt.context,
        rubric_version="forged-rubric-version",
    )
    forged_display_receipt = requests[1].display_receipt.model_copy(
        update={"context": forged_context}
    )
    forged_request = requests[1].model_copy(
        update={"display_receipt": forged_display_receipt}
    )
    monkeypatch.setattr(
        service,
        "_validate_operator_signing_request",
        lambda request, *, now: request,
    )
    original_builder = review_service_module.build_c4_stage1_operator_attestation
    signer_calls = 0

    def counted_builder(*args, **kwargs):
        nonlocal signer_calls
        signer_calls += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        review_service_module,
        "build_c4_stage1_operator_attestation",
        counted_builder,
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="cohort"):
        service.sign_operator_claim_cohort(reviews=(requests[0], forged_request))
    assert signer_calls == 0
    assert service.health()["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    service.close()


def test_mid_cohort_transaction_failure_rolls_back_every_authority_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    real_connect = service._connect  # noqa: SLF001 - injected transaction fault
    submission_inserts = 0

    class FaultingConnection:
        def __init__(self, connection) -> None:
            self._connection = connection

        def execute(self, statement, parameters=()):
            nonlocal submission_inserts
            if (
                "INSERT INTO" in statement
                and review_service_module._PRESENTER_SUBMISSION_TABLE in statement
            ):
                submission_inserts += 1
                if submission_inserts == 2:
                    raise RuntimeError("injected second cohort member failure")
            return self._connection.execute(statement, parameters)

        def __getattr__(self, name):
            return getattr(self._connection, name)

    monkeypatch.setattr(
        service,
        "_connect",
        lambda: FaultingConnection(real_connect()),
    )
    with pytest.raises(
        C4Stage1ReviewServiceError, match="two-review signing cohort failed atomically"
    ):
        service.sign_operator_claim_cohort(reviews=requests)
    assert submission_inserts == 2
    monkeypatch.setattr(service, "_connect", real_connect)
    health = service.health()
    assert health["operator_signing_cohort_complete"] is False
    assert health["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    with sqlite3.connect(state_root / "review-ledgers.sqlite3") as connection:
        assert connection.execute(
            f"SELECT COUNT(*) FROM {review_service_module._PRESENTATION_CONTEXT_TABLE}"
        ).fetchone() == (2,)
    service.close()

    with pytest.raises(C4Stage1ReviewServiceError, match="partial|incomplete|cohort"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_two_review_signing_cohort_persists_all_authority_receipts_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = tmp_path / "service-state"
    artifact_roots = (tmp_path / "review-material",)
    model_root = tmp_path / "model-snapshots"
    presenter = RecordingPinnedPresenter()
    service = C4Stage1ReviewService(
        state_root,
        artifact_roots=artifact_roots,
        model_roots=(model_root,),
        presenter=presenter,
    )
    fixtures, flows, requests = _prepare_signing_cohort(
        service,
        presenter,
        tmp_path,
        monkeypatch,
    )
    health = service.health()
    assert health["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 0,
        "presenter_submissions": 0,
        "operator_signing_leases": 0,
    }
    assert health["operator_signing_cohort_complete"] is False

    reversed_requests = (requests[1], requests[0])
    reversed_attestations = service.sign_operator_claim_cohort(
        reviews=reversed_requests
    )
    assert tuple(item.claim for item in reversed_attestations) == tuple(
        item.claim for item in reversed_requests
    )
    health = service.health()
    assert health["operator_signing_cohort_complete"] is True
    assert all(
        health["ledger_counts"][name] == 2
        for name in (
            "display_attestation_uses",
            "display_receipt_uses",
            "operator_policy_uses",
            "presenter_submissions",
            "operator_signing_leases",
        )
    )
    attestations_by_policy = {
        request.operator_policy.policy_id: attestation
        for request, attestation in zip(
            reversed_requests, reversed_attestations, strict=True
        )
    }
    consumed_operator_receipts = tuple(
        C4Stage1ReviewOperatorPolicyLedger(service).consume_once(
            operator_policy=fixture.policy,
            attestation=attestations_by_policy[fixture.policy.policy_id],
        )
        for fixture in fixtures
    )
    for fixture, receipt in zip(fixtures, consumed_operator_receipts, strict=True):
        attestation = attestations_by_policy[fixture.policy.policy_id]
        assert service.verify_operator_attestation(
            operator_policy=fixture.policy,
            attestation=attestation,
        )
        assert C4Stage1ReviewOperatorPolicyLedger(service).verify_consumed_use(
            operator_policy=fixture.policy,
            attestation=attestation,
            consumed_receipt=receipt,
        )
    service.close()

    restarted = C4Stage1ReviewService(
        state_root,
        artifact_roots=artifact_roots,
        model_roots=(model_root,),
        presenter=RecordingPinnedPresenter(),
    )
    assert restarted.health()["operator_signing_cohort_complete"] is True
    for fixture, flow, receipt in zip(
        fixtures, flows, consumed_operator_receipts, strict=True
    ):
        assert restarted.verify_authenticated_submission(submission_receipt=flow[1])
        assert restarted.verify_operator_signing_lease(operator_signing_lease=flow[3])
        attestation = attestations_by_policy[fixture.policy.policy_id]
        assert restarted.verify_operator_attestation(
            operator_policy=fixture.policy,
            attestation=attestation,
        )
        assert C4Stage1ReviewOperatorPolicyLedger(restarted).verify_consumed_use(
            operator_policy=fixture.policy,
            attestation=attestation,
            consumed_receipt=receipt,
        )
    restarted.close()


def test_noncanonical_authority_ledger_json_marks_health_unready_and_restart_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    service.sign_operator_claim_cohort(reviews=requests)
    healthy = service.health()
    assert healthy["ready"] is True
    assert healthy["operator_signing_cohort_complete"] is True

    database = state_root / "review-ledgers.sqlite3"
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT ledger_key, receipt_json FROM operator_policy_uses "
            "ORDER BY ledger_key LIMIT 1"
        ).fetchone()
        assert row is not None
        canonical_receipt = bytes(row[1])
        noncanonical_receipt = b"\n" + canonical_receipt
        assert json.loads(noncanonical_receipt) == json.loads(canonical_receipt)
        connection.execute(
            "UPDATE operator_policy_uses SET receipt_json = ? WHERE ledger_key = ?",
            (noncanonical_receipt, row[0]),
        )

    unhealthy = service.health()
    assert unhealthy["ready"] is False
    assert unhealthy["operator_signing_cohort_complete"] is False
    assert unhealthy["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 2,
        "presenter_submissions": 2,
        "operator_signing_leases": 2,
    }
    service.close()

    with pytest.raises(C4Stage1ReviewServiceError, match="authority ledgers|cohort"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


@pytest.mark.parametrize(
    "mutation",
    ("row-hmac", "missing-base-effect", "authenticated-orphan-effect"),
)
def test_stateful_result_journal_tamper_delete_and_orphan_fail_health_and_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    fixtures, _, requests = _prepare_signing_cohort(
        service, presenter, tmp_path, monkeypatch
    )
    attestations = service.sign_operator_claim_cohort(reviews=requests)
    database = state_root / "review-ledgers.sqlite3"

    with sqlite3.connect(database) as connection:
        table = review_service_module._STATEFUL_OPERATION_RESULT_TABLE
        if mutation == "row-hmac":
            connection.execute(
                f"UPDATE {table} SET row_auth_hmac_sha256 = ? "
                "WHERE operation = 'sign_operator_claim_cohort'",
                ("0" * 64,),
            )
        elif mutation == "missing-base-effect":
            connection.execute(
                f"DELETE FROM {table} WHERE operation_request_id = ("
                f"SELECT operation_request_id FROM {table} "
                "WHERE operation = 'display' ORDER BY operation_request_id LIMIT 1)"
            )
        else:
            orphan = review_module.record_c4_stage1_consumed_operator_policy_receipt(
                fixtures[0].policy,
                attestations[0],
                external_transaction_id="f" * 64,
                external_transaction_timestamp=attestations[0].claim.review_timestamp,
            )
            payload = {
                "operator_policy": review_service_module._model_payload(
                    fixtures[0].policy
                ),
                "attestation": review_service_module._model_payload(attestations[0]),
            }
            request = service._stateful_request_from_payload(  # noqa: SLF001
                "consume_operator_policy", payload
            )
            result_json = canonical_json_bytes(
                review_service_module._model_payload(orphan)
            )
            completed_at = datetime.now(timezone.utc).isoformat()
            row_hmac = service._stateful_result_auth_hmac(  # noqa: SLF001
                request,
                status="completed",
                result_json=result_json,
                result_sha256=hashlib.sha256(result_json).hexdigest(),
                result_size_bytes=len(result_json),
                effect_kind="consumed-operator-policy",
                effect_id=orphan.consumed_operator_receipt_id,
                effect_sha256=orphan.consumed_operator_receipt_sha256,
                completed_at=completed_at,
            )
            connection.execute(
                f"INSERT INTO {table} "
                "(operation_request_id, service_epoch_id, ipc_schema, operation, "
                "body_length, body_sha256, status, result_json, result_sha256, "
                "result_size_bytes, effect_kind, effect_id, effect_sha256, "
                "completed_at, row_auth_hmac_sha256) "
                "VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    request.operation_request_id,
                    request.service_epoch_id,
                    request.ipc_schema,
                    request.operation,
                    request.body_length,
                    request.body_sha256,
                    result_json,
                    hashlib.sha256(result_json).hexdigest(),
                    len(result_json),
                    "consumed-operator-policy",
                    orphan.consumed_operator_receipt_id,
                    orphan.consumed_operator_receipt_sha256,
                    completed_at,
                    row_hmac,
                ),
            )

    unhealthy = service.health()
    assert unhealthy["ready"] is False
    assert unhealthy["stateful_ipc_result_journal_valid"] is False
    assert unhealthy["sealed_sign_result_recoverable"] is False
    service.close()

    with pytest.raises(
        C4Stage1ReviewServiceError,
        match="stateful|journal|effect|incomplete|orphan|authentication",
    ):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_presenter_receipt_auth_tag_tamper_marks_health_unready_and_restart_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    service.sign_operator_claim_cohort(reviews=requests)
    healthy = service.health()
    assert healthy["ready"] is True
    assert healthy["operator_signing_cohort_complete"] is True

    database = state_root / "review-ledgers.sqlite3"
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            f"SELECT submission_receipt_id, receipt_json "
            f"FROM {review_service_module._PRESENTER_SUBMISSION_TABLE} "
            "ORDER BY submission_receipt_id LIMIT 1"
        ).fetchone()
        assert row is not None
        receipt = json.loads(bytes(row[1]))
        original_auth_tag = receipt["service_auth_hmac_sha256"]
        receipt["service_auth_hmac_sha256"] = (
            "0" * 64 if original_auth_tag != "0" * 64 else "1" * 64
        )
        tampered_receipt = canonical_json_bytes(receipt)
        assert tampered_receipt != bytes(row[1])
        connection.execute(
            f"UPDATE {review_service_module._PRESENTER_SUBMISSION_TABLE} "
            "SET receipt_json = ? WHERE submission_receipt_id = ?",
            (tampered_receipt, row[0]),
        )

    unhealthy = service.health()
    assert unhealthy["ready"] is False
    assert unhealthy["operator_signing_cohort_complete"] is False
    assert unhealthy["ledger_counts"] == {
        "display_attestation_uses": 2,
        "display_receipt_uses": 2,
        "operator_policy_uses": 2,
        "presenter_submissions": 2,
        "operator_signing_leases": 2,
    }
    service.close()

    with pytest.raises(C4Stage1ReviewServiceError, match="authority ledgers|cohort"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


@pytest.mark.parametrize(
    "tamper",
    ("ledger-binding", "submission-consumed-at", "lease-consumed-at"),
)
def test_exact_authority_snapshot_rejects_database_row_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    service.sign_operator_claim_cohort(reviews=requests)
    assert service.health()["operator_signing_cohort_complete"] is True

    database = state_root / "review-ledgers.sqlite3"
    with sqlite3.connect(database) as connection:
        if tamper == "ledger-binding":
            connection.execute(
                "UPDATE display_receipt_uses SET binding_sha256 = ? "
                "WHERE ledger_key = ?",
                ("0" * 64, requests[0].display_receipt.display_receipt_id),
            )
        elif tamper == "submission-consumed-at":
            connection.execute(
                f"UPDATE {review_service_module._PRESENTER_SUBMISSION_TABLE} "
                "SET consumed_at = ? WHERE submission_receipt_id = ?",
                (
                    "2000-01-01T00:00:00+00:00",
                    requests[0].submission_receipt.submission_receipt_id,
                ),
            )
        else:
            connection.execute(
                f"UPDATE {review_service_module._OPERATOR_SIGNING_LEASE_TABLE} "
                "SET consumed_at = ? WHERE operator_signing_lease_id = ?",
                (
                    "2000-01-01T00:00:00+00:00",
                    requests[0].operator_signing_lease.operator_signing_lease_id,
                ),
            )

    unhealthy = service.health()
    assert unhealthy["ready"] is False
    assert unhealthy["operator_signing_cohort_complete"] is False
    service.close()

    with pytest.raises(C4Stage1ReviewServiceError, match="authority ledgers|cohort"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_readdressed_operator_rows_still_require_the_original_operator_hmac(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, state_root, artifact_root, model_root = _service(tmp_path)
    _, _, requests = _prepare_signing_cohort(service, presenter, tmp_path, monkeypatch)
    service.sign_operator_claim_cohort(reviews=requests)
    request = requests[0]
    database = state_root / "review-ledgers.sqlite3"

    with sqlite3.connect(database) as connection:
        attestation_row = connection.execute(
            f"SELECT attestation_json FROM "
            f"{review_service_module._PRESENTER_SUBMISSION_TABLE} "
            "WHERE submission_receipt_id = ?",
            (request.submission_receipt.submission_receipt_id,),
        ).fetchone()
        operator_row = connection.execute(
            "SELECT receipt_json, transaction_id FROM operator_policy_uses "
            "WHERE ledger_key = ?",
            (request.operator_policy.policy_id,),
        ).fetchone()
        cohort_row = connection.execute(
            f"SELECT cohort_json FROM "
            f"{review_service_module._COMPLETED_SIGNING_COHORT_TABLE}"
        ).fetchone()
        assert attestation_row and operator_row and cohort_row

        forged_attestation = json.loads(bytes(attestation_row[0]))
        original_hmac = forged_attestation["hmac_sha256"]
        forged_attestation["hmac_sha256"] = (
            "0" * 64 if original_hmac != "0" * 64 else "1" * 64
        )
        attestation_body = {
            key: value
            for key, value in forged_attestation.items()
            if key not in {"attestation_id", "attestation_sha256"}
        }
        forged_attestation["attestation_id"] = content_id(
            "c4_stage1_operator_attestation", attestation_body
        )
        forged_attestation["attestation_sha256"] = hashlib.sha256(
            canonical_json_bytes(attestation_body)
        ).hexdigest()
        forged_attestation_model = (
            review_module.C4Stage1HumanReviewOperatorAttestation.model_validate_json(
                canonical_json_bytes(forged_attestation)
            )
        )

        forged_receipt = json.loads(bytes(operator_row[0]))
        forged_receipt.update(
            {
                "attestation_id": forged_attestation_model.attestation_id,
                "attestation_sha256": forged_attestation_model.attestation_sha256,
                "attestation_hmac_sha256": forged_attestation_model.hmac_sha256,
            }
        )
        receipt_body = {
            key: value
            for key, value in forged_receipt.items()
            if key
            not in {
                "consumed_operator_receipt_id",
                "consumed_operator_receipt_sha256",
            }
        }
        forged_receipt["consumed_operator_receipt_id"] = content_id(
            "c4_s1_operator_use", receipt_body
        )
        forged_receipt["consumed_operator_receipt_sha256"] = hashlib.sha256(
            canonical_json_bytes(receipt_body)
        ).hexdigest()
        forged_receipt_model = (
            review_module.C4Stage1ConsumedOperatorPolicyReceipt.model_validate_json(
                canonical_json_bytes(forged_receipt)
            )
        )
        forged_binding = review_service_module._binding_sha256(
            "c4-stage1-operator-policy-ledger-binding-v1",
            request.operator_policy,
            forged_attestation_model,
        )

        forged_cohort = json.loads(bytes(cohort_row[0]))
        member = next(
            item
            for item in forged_cohort["members"]
            if item["operator_policy_id"] == request.operator_policy.policy_id
        )
        member.update(
            {
                "attestation_id": forged_attestation_model.attestation_id,
                "attestation_sha256": forged_attestation_model.attestation_sha256,
                "consumed_operator_receipt_id": (
                    forged_receipt_model.consumed_operator_receipt_id
                ),
                "consumed_operator_receipt_sha256": (
                    forged_receipt_model.consumed_operator_receipt_sha256
                ),
                "operator_policy_ledger_binding_sha256": forged_binding,
            }
        )
        authority_body = {
            key: value
            for key, value in forged_cohort.items()
            if key
            not in {
                "operator_signing_cohort_id",
                "operator_signing_cohort_sha256",
                "authority_snapshot_hmac_sha256",
            }
        }
        forged_cohort["authority_snapshot_hmac_sha256"] = hmac.digest(
            service._submission_auth_secret,  # noqa: SLF001 - adversarial fixture
            review_service_module._completed_signing_cohort_authority_message(
                authority_body
            ),
            "sha256",
        ).hex()
        cohort_address_body = {
            key: value
            for key, value in forged_cohort.items()
            if key
            not in {
                "operator_signing_cohort_id",
                "operator_signing_cohort_sha256",
            }
        }
        forged_cohort["operator_signing_cohort_id"] = content_id(
            "c4_s1_completed_signing_cohort", cohort_address_body
        )
        forged_cohort["operator_signing_cohort_sha256"] = hashlib.sha256(
            canonical_json_bytes(cohort_address_body)
        ).hexdigest()
        forged_cohort_model = (
            review_service_module.C4Stage1CompletedSigningCohort.model_validate_json(
                canonical_json_bytes(forged_cohort)
            )
        )

        connection.execute(
            f"UPDATE {review_service_module._PRESENTER_SUBMISSION_TABLE} "
            "SET attestation_json = ? WHERE submission_receipt_id = ?",
            (
                forged_attestation_model.canonical_json_bytes(),
                request.submission_receipt.submission_receipt_id,
            ),
        )
        connection.execute(
            "UPDATE operator_policy_uses SET binding_sha256 = ?, receipt_id = ?, "
            "receipt_sha256 = ?, receipt_json = ? WHERE ledger_key = ?",
            (
                forged_binding,
                forged_receipt_model.consumed_operator_receipt_id,
                forged_receipt_model.consumed_operator_receipt_sha256,
                forged_receipt_model.canonical_json_bytes(),
                request.operator_policy.policy_id,
            ),
        )
        connection.execute(
            f"UPDATE {review_service_module._COMPLETED_SIGNING_COHORT_TABLE} "
            "SET operator_signing_cohort_id = ?, "
            "operator_signing_cohort_sha256 = ?, cohort_json = ?",
            (
                forged_cohort_model.operator_signing_cohort_id,
                forged_cohort_model.operator_signing_cohort_sha256,
                forged_cohort_model.canonical_json_bytes(),
            ),
        )

    service._signing_cohort_latch = forged_cohort_model  # noqa: SLF001
    unhealthy = service.health()
    assert unhealthy["ready"] is False
    assert unhealthy["operator_signing_cohort_complete"] is False
    service.close()

    with pytest.raises(C4Stage1ReviewServiceError, match="authority ledgers|cohort"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_post_seal_display_sign_and_cohort_reuse_all_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, presenter, _, _, _ = _service(tmp_path)
    fixtures, _, requests = _prepare_signing_cohort(
        service, presenter, tmp_path, monkeypatch
    )
    attestations = service.sign_operator_claim_cohort(reviews=requests)
    sealed_counts = dict(service.health()["ledger_counts"])

    with pytest.raises((ValueError, C4Stage1ReviewServiceError)):
        _execute_display(fixtures[0], service)
    assert not hasattr(service, "sign_operator_claim")
    for replay in (requests, (requests[1], requests[0])):
        with pytest.raises(C4Stage1ReviewServiceError, match="cohort|replay"):
            service.sign_operator_claim_cohort(reviews=replay)

    operator_ledger = C4Stage1ReviewOperatorPolicyLedger(service)
    consumed = tuple(
        operator_ledger.consume_once(
            operator_policy=fixture.policy,
            attestation=attestation,
        )
        for fixture, attestation in zip(fixtures, attestations, strict=True)
    )
    for fixture, attestation, receipt in zip(
        fixtures, attestations, consumed, strict=True
    ):
        assert operator_ledger.verify_consumed_use(
            operator_policy=fixture.policy,
            attestation=attestation,
            consumed_receipt=receipt,
        )
        with pytest.raises(ValueError, match="operator policy replay"):
            operator_ledger.consume_once(
                operator_policy=fixture.policy,
                attestation=attestation,
            )
    assert service.health()["ledger_counts"] == sealed_counts
    assert service.health()["operator_signing_cohort_complete"] is True
    service.close()


def _raw_exchange(
    address: tuple[str, int], header: dict[str, object], body: bytes
) -> dict:
    with socket.create_connection(address, timeout=10) as connection:
        connection.sendall(canonical_json_bytes(header) + b"\n")
        connection.sendall(body)
        response = connection.makefile("rb").readline()
    return json.loads(response)


def _serve_one_response(response_builder):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    address = listener.getsockname()

    def run() -> None:
        with listener:
            connection, _ = listener.accept()
            with connection:
                reader = connection.makefile("rb")
                request = json.loads(reader.readline())
                body = reader.read(request["body_length"])
                request["payload"] = json.loads(body)
                response = response_builder(request)
                connection.sendall(canonical_json_bytes(response) + b"\n")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return (str(address[0]), int(address[1])), thread


@pytest.mark.parametrize(
    ("operation", "result"),
    (
        ("readiness", {"ready": True}),
        ("display", {"displayed": True}),
        ("verify_authenticated_submission", True),
    ),
)
def test_client_rejects_forged_true_responses_for_every_authority_class(
    tmp_path: Path, operation: str, result: object
) -> None:
    auth = tmp_path / f"{operation}.key"
    auth.write_bytes(b"r" * 32)

    def forged(request):
        request_message = c4_stage1_review_ipc_auth_message(
            operation=request["operation"],
            body_length=request["body_length"],
            body_sha256=request["body_sha256"],
            nonce=request["nonce"],
            issued_at=request["issued_at"],
        )
        return {
            "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "operation": request["operation"],
            "request_nonce": request["nonce"],
            "request_message_sha256": hashlib.sha256(request_message).hexdigest(),
            "ok": True,
            "result": result,
            "response_hmac_sha256": "0" * 64,
        }

    address, thread = _serve_one_response(forged)
    client = C4Stage1ReviewServiceClient(
        *address,
        auth_secret_path=auth,
        timeout_seconds=6,
        presenter_timeout_ms=1_000,
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="authentication failed"):
        client._call(operation, {})
    thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.mark.parametrize("mutation", ("missing-mac", "cross-operation", "replay"))
def test_client_rejects_missing_mac_cross_operation_and_replayed_response(
    tmp_path: Path, mutation: str
) -> None:
    secret = b"s" * 32
    auth = tmp_path / f"{mutation}.key"
    auth.write_bytes(secret)

    def mutated(request):
        request_message = c4_stage1_review_ipc_auth_message(
            operation=request["operation"],
            body_length=request["body_length"],
            body_sha256=request["body_sha256"],
            nonce=request["nonce"],
            issued_at=request["issued_at"],
        )
        operation = "readiness" if mutation == "cross-operation" else "health"
        nonce = "f" * 64 if mutation == "replay" else request["nonce"]
        request_sha256 = hashlib.sha256(request_message).hexdigest()
        response = {
            "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "operation": operation,
            "request_nonce": nonce,
            "request_message_sha256": request_sha256,
            "ok": True,
            "result": {"ready": True},
        }
        response["response_hmac_sha256"] = hmac.digest(
            secret,
            c4_stage1_review_ipc_response_auth_message(
                operation=operation,
                request_nonce=nonce,
                request_message_sha256=request_sha256,
                ok=True,
                result=response["result"],
            ),
            "sha256",
        ).hex()
        if mutation == "missing-mac":
            del response["response_hmac_sha256"]
        return response

    address, thread = _serve_one_response(mutated)
    client = C4Stage1ReviewServiceClient(
        *address,
        auth_secret_path=auth,
        timeout_seconds=6,
        presenter_timeout_ms=1_000,
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="binding is invalid"):
        client._call("health", {})
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_loopback_ipc_requires_hmac_and_rejects_durable_nonce_replay(
    tmp_path: Path,
) -> None:
    presentation_submission = canonical_json_bytes({"review": "complete"})
    service, _, state_root, _, _ = _service(
        tmp_path,
        presenter=RecordingPinnedPresenter(submission=presentation_submission),
    )
    with C4Stage1ReviewServiceServer(service) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = C4Stage1ReviewServiceClient(
                *server.address,
                auth_secret_path=state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
                timeout_seconds=6,
                presenter_timeout_ms=1_000,
            )
            assert client.readiness == service.readiness
            assert client.health()["ready"] is True

            auth_secret = (state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME).read_bytes()
            nonce = "1" * 64
            issued_at = datetime.now(timezone.utc).isoformat()
            body = canonical_json_bytes({})
            body_sha256 = hashlib.sha256(body).hexdigest()
            message = c4_stage1_review_ipc_auth_message(
                operation="readiness",
                body_length=len(body),
                body_sha256=body_sha256,
                nonce=nonce,
                issued_at=issued_at,
            )
            signed_request = {
                "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                "operation": "readiness",
                "body_length": len(body),
                "body_sha256": body_sha256,
                "nonce": nonce,
                "issued_at": issued_at,
                "request_hmac_sha256": hmac.digest(
                    auth_secret, message, "sha256"
                ).hex(),
            }
            assert _raw_exchange(server.address, signed_request, body)["ok"] is True
            replay = _raw_exchange(server.address, signed_request, body)
            assert replay["ok"] is False
            assert "replay" in replay["error"]
        finally:
            server.shutdown()
            thread.join(timeout=10)

    restarted = C4Stage1ReviewService(
        state_root,
        artifact_roots=(tmp_path / "review-material",),
        model_roots=(tmp_path / "model-snapshots",),
        presenter=RecordingPinnedPresenter(),
    )
    with pytest.raises(C4Stage1ReviewServiceError, match="replay"):
        restarted.authenticate_ipc_request(
            operation="readiness",
            body_length=len(body),
            body_sha256=body_sha256,
            nonce=nonce,
            issued_at=issued_at,
            request_hmac_sha256=signed_request["request_hmac_sha256"],
        )


def test_unauthenticated_mismatched_body_and_wrong_operation_create_no_stateful_result(
    tmp_path: Path,
) -> None:
    service, presenter, state_root, _, _ = _service(tmp_path)
    secret = (state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME).read_bytes()

    def request(
        operation: str,
        *,
        nonce: str,
        authenticated_body: bytes,
        authenticate: bool = True,
    ) -> dict[str, object]:
        issued_at = datetime.now(timezone.utc).isoformat()
        body_sha256 = hashlib.sha256(authenticated_body).hexdigest()
        message = c4_stage1_review_ipc_auth_message(
            operation=operation,
            body_length=len(authenticated_body),
            body_sha256=body_sha256,
            nonce=nonce,
            issued_at=issued_at,
        )
        return {
            "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "operation": operation,
            "body_length": len(authenticated_body),
            "body_sha256": body_sha256,
            "nonce": nonce,
            "issued_at": issued_at,
            "request_hmac_sha256": (
                hmac.digest(secret, message, "sha256").hex()
                if authenticate
                else "0" * 64
            ),
        }

    canonical_empty = canonical_json_bytes({})
    attempts = (
        (
            request(
                "display",
                nonce="2" * 64,
                authenticated_body=canonical_empty,
                authenticate=False,
            ),
            canonical_empty,
        ),
        (
            request(
                "display",
                nonce="3" * 64,
                authenticated_body=canonical_empty,
            ),
            canonical_json_bytes([]),
        ),
        (
            request(
                "not-a-stateful-operation",
                nonce="4" * 64,
                authenticated_body=canonical_empty,
            ),
            canonical_empty,
        ),
    )
    with C4Stage1ReviewServiceServer(service) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            for header, body in attempts:
                response = _raw_exchange(server.address, header, body)
                assert response["ok"] is False
                with sqlite3.connect(
                    state_root / "review-ledgers.sqlite3"
                ) as connection:
                    assert connection.execute(
                        f"SELECT COUNT(*) FROM "
                        f"{review_service_module._STATEFUL_OPERATION_RESULT_TABLE}"
                    ).fetchone() == (0,)
            assert presenter.calls == []
        finally:
            server.shutdown()
            server_thread.join(timeout=5)
            assert not server_thread.is_alive()


def test_silent_and_partial_preauth_clients_cannot_wedge_valid_requests(
    tmp_path: Path,
) -> None:
    service, _, state_root, _, _ = _service(tmp_path)
    with C4Stage1ReviewServiceServer(service) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        silent = socket.create_connection(server.address, timeout=2)
        partial = socket.create_connection(server.address, timeout=2)
        partial.sendall(b"{")
        try:
            client = C4Stage1ReviewServiceClient(
                *server.address,
                auth_secret_path=state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
                timeout_seconds=6,
                presenter_timeout_ms=1_000,
            )
            assert client.health()["ready"] is True
        finally:
            silent.close()
            partial.close()
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_preauth_byte_dribble_cannot_hold_all_connection_slots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        review_service_module,
        "C4_STAGE1_REVIEW_PREAUTH_TIMEOUT_SECONDS",
        0.25,
    )
    service, _, state_root, _, _ = _service(tmp_path)
    stop = threading.Event()
    connections: list[socket.socket] = []
    dribblers: list[threading.Thread] = []

    def dribble(connection: socket.socket) -> None:
        while not stop.wait(0.03):
            try:
                connection.sendall(b" ")
            except OSError:
                return

    with C4Stage1ReviewServiceServer(service) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            for _ in range(C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS):
                connection = socket.create_connection(server.address, timeout=2)
                connection.sendall(b"{")
                connections.append(connection)
                dribbler = threading.Thread(
                    target=dribble,
                    args=(connection,),
                    daemon=True,
                )
                dribbler.start()
                dribblers.append(dribbler)

            capacity_deadline = time.monotonic() + 2
            while (
                server._server._request_slots._value  # noqa: SLF001
                != 0
                and time.monotonic() < capacity_deadline
            ):
                stop.wait(0.01)
            assert server._server._request_slots._value == 0  # noqa: SLF001

            release_deadline = time.monotonic() + 2
            while (
                server._server._request_slots._value  # noqa: SLF001
                != C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS
                and time.monotonic() < release_deadline
            ):
                stop.wait(0.01)
            assert (  # noqa: SLF001
                server._server._request_slots._value
                == C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS
            )

            client = C4Stage1ReviewServiceClient(
                *server.address,
                auth_secret_path=state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
                timeout_seconds=6,
                presenter_timeout_ms=1_000,
            )
            assert client.health()["ready"] is True
        finally:
            stop.set()
            for connection in connections:
                connection.close()
            for dribbler in dribblers:
                dribbler.join(timeout=2)
            server.shutdown()
            server_thread.join(timeout=5)
            assert not server_thread.is_alive()


def test_authenticated_body_byte_dribble_has_one_total_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        review_service_module,
        "C4_STAGE1_REVIEW_AUTHENTICATED_BODY_TIMEOUT_SECONDS",
        0.25,
    )
    service, _, state_root, _, _ = _service(tmp_path)
    body = b"{" + (b" " * 128) + b"}"
    body_sha256 = hashlib.sha256(body).hexdigest()
    nonce = "b" * 64
    issued_at = datetime.now(timezone.utc).isoformat()
    message = c4_stage1_review_ipc_auth_message(
        operation="health",
        body_length=len(body),
        body_sha256=body_sha256,
        nonce=nonce,
        issued_at=issued_at,
    )
    secret = (state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME).read_bytes()
    header = {
        "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "operation": "health",
        "body_length": len(body),
        "body_sha256": body_sha256,
        "nonce": nonce,
        "issued_at": issued_at,
        "request_hmac_sha256": hmac.digest(secret, message, "sha256").hex(),
    }
    stop = threading.Event()

    with C4Stage1ReviewServiceServer(service) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        with socket.create_connection(server.address, timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall(canonical_json_bytes(header) + b"\n" + body[:1])

            def dribble() -> None:
                for value in body[1:]:
                    if stop.wait(0.03):
                        return
                    try:
                        connection.sendall(bytes((value,)))
                    except OSError:
                        return

            dribbler = threading.Thread(target=dribble, daemon=True)
            dribbler.start()
            response = json.loads(connection.makefile("rb").readline())
            stop.set()
            dribbler.join(timeout=2)
        try:
            assert response["ok"] is False
            assert "authenticated deadline" in response["error"]
            assert len(response["response_hmac_sha256"]) == 64
        finally:
            server.shutdown()
            server_thread.join(timeout=5)
            assert not server_thread.is_alive()


def test_forged_large_body_claim_is_rejected_before_body_read(tmp_path: Path) -> None:
    service, _, _, _, _ = _service(tmp_path)
    header = {
        "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "operation": "display",
        "body_length": review_service_module.C4_STAGE1_REVIEW_MAX_IPC_BYTES,
        "body_sha256": "0" * 64,
        "nonce": "a" * 64,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "request_hmac_sha256": "0" * 64,
    }
    with C4Stage1ReviewServiceServer(service) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with socket.create_connection(server.address, timeout=2) as connection:
                connection.settimeout(2)
                connection.sendall(canonical_json_bytes(header) + b"\n")
                response = json.loads(connection.makefile("rb").readline())
            assert response["ok"] is False
            assert "authentication failed" in response["error"]
        finally:
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_loopback_server_caps_concurrent_preauth_handlers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _, _, _, _ = _service(tmp_path)
    release = threading.Event()
    capacity_reached = threading.Event()
    lock = threading.Lock()
    active = 0
    peak = 0

    def blocking_handle(_handler) -> None:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS:
                capacity_reached.set()
        try:
            release.wait(timeout=5)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(
        review_service_module._C4Stage1ReviewRequestHandler,
        "handle",
        blocking_handle,
    )
    connections: list[socket.socket] = []
    with C4Stage1ReviewServiceServer(service) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for _ in range(C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS * 3):
                try:
                    connections.append(
                        socket.create_connection(server.address, timeout=0.25)
                    )
                except OSError:
                    pass
            assert capacity_reached.wait(timeout=2)
            assert peak == C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS
        finally:
            release.set()
            for connection in connections:
                connection.close()
            server.shutdown()
            thread.join(timeout=5)
            assert not thread.is_alive()


def test_second_display_is_rejected_without_cancelling_or_orphaning_the_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BlockingPresenter(RecordingPinnedPresenter):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()
            self.cancelled = threading.Event()

        def present(
            self,
            context,
            source_png_bytes,
            outputs,
            *,
            cancellation_event: threading.Event | None = None,
        ) -> bool:
            self.calls.append((context, source_png_bytes, outputs))
            self.started.set()
            self.release.wait(5)
            if cancellation_event is not None and cancellation_event.is_set():
                return False
            return True

        def cancel_active(self) -> bool:
            self.cancelled.set()
            self.release.set()
            return True

    presenter = BlockingPresenter()
    service, _, state_root, _, _ = _service(tmp_path, presenter=presenter)
    fixture = _review_fixture(tmp_path, monkeypatch, service)
    with C4Stage1ReviewServiceServer(service) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = C4Stage1ReviewServiceClient(
            *server.address,
            auth_secret_path=state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
            timeout_seconds=6,
            presenter_timeout_ms=1_000,
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                first = executor.submit(_execute_display, fixture, client)
                assert presenter.started.wait(timeout=2)
                with pytest.raises(
                    (ValueError, C4Stage1ReviewServiceError), match="display"
                ):
                    _execute_display(fixture, client)
                assert len(presenter.calls) == 1
                assert presenter.cancelled.is_set() is False
                assert first.done() is False
                presenter.release.set()
                assert (
                    first.result(timeout=3).context.packet_id
                    == fixture.packet.packet_id
                )
        finally:
            presenter.release.set()
            server.shutdown()
            server_thread.join(timeout=5)
            assert not server_thread.is_alive()


@pytest.mark.filterwarnings("error")
def test_non_display_response_reset_does_not_cancel_an_active_display(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BlockingPresenter(RecordingPinnedPresenter):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()
            self.cancelled = threading.Event()

        def present(
            self,
            context,
            source_png_bytes,
            outputs,
            *,
            cancellation_event: threading.Event | None = None,
        ) -> bool:
            self.calls.append((context, source_png_bytes, outputs))
            self.started.set()
            self.release.wait(5)
            if cancellation_event is not None and cancellation_event.is_set():
                return False
            return True

        def cancel_active(self) -> bool:
            self.cancelled.set()
            self.release.set()
            return True

    presenter = BlockingPresenter()
    service, _, state_root, _, _ = _service(tmp_path, presenter=presenter)
    fixture = _review_fixture(tmp_path, monkeypatch, service)
    health_started = threading.Event()
    release_health = threading.Event()
    original_health = service.health

    def blocked_health():
        health_started.set()
        release_health.wait(2)
        return original_health()

    monkeypatch.setattr(service, "health", blocked_health)
    secret = (state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME).read_bytes()
    body = canonical_json_bytes({})
    body_sha256 = hashlib.sha256(body).hexdigest()
    nonce = "c" * 64
    issued_at = datetime.now(timezone.utc).isoformat()
    message = c4_stage1_review_ipc_auth_message(
        operation="health",
        body_length=len(body),
        body_sha256=body_sha256,
        nonce=nonce,
        issued_at=issued_at,
    )
    header = {
        "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "operation": "health",
        "body_length": len(body),
        "body_sha256": body_sha256,
        "nonce": nonce,
        "issued_at": issued_at,
        "request_hmac_sha256": hmac.digest(secret, message, "sha256").hex(),
    }

    with C4Stage1ReviewServiceServer(service) as server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = C4Stage1ReviewServiceClient(
            *server.address,
            auth_secret_path=state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
            timeout_seconds=6,
            presenter_timeout_ms=1_000,
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                display = executor.submit(_execute_display, fixture, client)
                assert presenter.started.wait(timeout=2)
                health_connection = socket.create_connection(server.address, timeout=2)
                health_connection.sendall(canonical_json_bytes(header) + b"\n" + body)
                assert health_started.wait(timeout=2)
                linger = (
                    struct.pack("hh", 1, 0)
                    if os.name == "nt"
                    else struct.pack("ii", 1, 0)
                )
                health_connection.setsockopt(
                    socket.SOL_SOCKET,
                    socket.SO_LINGER,
                    linger,
                )
                health_connection.close()
                release_health.set()
                assert presenter.cancelled.wait(0.3) is False
                assert display.done() is False
                presenter.release.set()
                assert (
                    display.result(timeout=3).context.packet_id
                    == fixture.packet.packet_id
                )
        finally:
            release_health.set()
            presenter.release.set()
            server.shutdown()
            server_thread.join(timeout=5)
            assert not server_thread.is_alive()


def test_display_peer_disconnect_cancels_the_active_presenter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BlockingPresenter(RecordingPinnedPresenter):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.cancelled = threading.Event()
            self.release = threading.Event()
            self.finished = threading.Event()
            self.generic_cancel_calls = 0

        def present(
            self,
            context,
            source_png_bytes,
            outputs,
            *,
            cancellation_event: threading.Event | None = None,
        ) -> bool:
            self.calls.append((context, source_png_bytes, outputs))
            assert cancellation_event is not None
            self.started.set()
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if cancellation_event.wait(0.01):
                    self.cancelled.set()
                    break
                if self.release.is_set():
                    break
            self.finished.set()
            return False

        def cancel_active(self) -> bool:
            self.generic_cancel_calls += 1
            return False

    presenter = BlockingPresenter()
    service, _, state_root, _, _ = _service(tmp_path, presenter=presenter)
    fixture = _review_fixture(tmp_path, monkeypatch, service)
    context = review_module._build_display_context(
        fixture.schema,
        fixture.packet,
        fixture.policy,
        fixture.presentation,
        fixture.screen_contract,
        fixture.display_policy,
        ui_implementation_id=C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
        ui_revision=C4_STAGE1_REVIEW_PRESENTER_REVISION,
        ui_session_id="disconnect-cancel-session",
    )
    outputs = _visible_outputs(context, fixture)
    payload = {
        "context": review_service_module._model_payload(context),
        "display_policy": review_service_module._model_payload(fixture.display_policy),
        "source_png_base64": base64.b64encode(fixture.source_bytes).decode("ascii"),
        "outputs": [
            review_service_module._visible_output_payload(item) for item in outputs
        ],
    }
    nonce = "d" * 64
    issued_at = datetime.now(timezone.utc).isoformat()
    body = canonical_json_bytes(payload)
    body_sha256 = hashlib.sha256(body).hexdigest()
    message = c4_stage1_review_ipc_auth_message(
        operation="display",
        body_length=len(body),
        body_sha256=body_sha256,
        nonce=nonce,
        issued_at=issued_at,
    )
    secret = (state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME).read_bytes()
    request = {
        "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "operation": "display",
        "body_length": len(body),
        "body_sha256": body_sha256,
        "nonce": nonce,
        "issued_at": issued_at,
        "request_hmac_sha256": hmac.digest(secret, message, "sha256").hex(),
    }
    with C4Stage1ReviewServiceServer(service) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = socket.create_connection(server.address, timeout=2)
        connection.sendall(canonical_json_bytes(request) + b"\n")
        connection.sendall(body)
        assert presenter.started.wait(3)
        connection.shutdown(socket.SHUT_RDWR)
        connection.close()
        assert presenter.cancelled.wait(3)
        assert presenter.finished.wait(3)
        assert presenter.generic_cancel_calls == 0
        server.shutdown()
        thread.join(timeout=5)
        assert not thread.is_alive()

    database = sqlite3.connect(state_root / "review-ledgers.sqlite3")
    try:
        assert database.execute(
            f"SELECT COUNT(*) FROM {review_service_module._PRESENTATION_CONTEXT_TABLE}"
        ).fetchone() == (0,)
    finally:
        database.close()


def test_display_disconnect_cancels_during_pre_registration_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class PreRegistrationPresenter(RecordingPinnedPresenter):
        def __init__(self) -> None:
            super().__init__()
            self.validation_started = threading.Event()
            self.request_cancelled = threading.Event()
            self.browser_launched = threading.Event()
            self.finished = threading.Event()
            self.generic_cancel_calls = 0

        def present(
            self,
            context,
            source_png_bytes,
            outputs,
            *,
            cancellation_event: threading.Event | None = None,
        ) -> bool:
            self.calls.append((context, source_png_bytes, outputs))
            assert cancellation_event is not None
            self.validation_started.set()
            if cancellation_event.wait(5):
                self.request_cancelled.set()
                self.finished.set()
                return False
            self.browser_launched.set()
            self.finished.set()
            return True

        def cancel_active(self) -> bool:
            self.generic_cancel_calls += 1
            return False

    presenter = PreRegistrationPresenter()
    service, _, state_root, artifact_root, model_root = _service(
        tmp_path, presenter=presenter
    )
    fixture = _review_fixture(tmp_path, monkeypatch, service)
    context = review_module._build_display_context(
        fixture.schema,
        fixture.packet,
        fixture.policy,
        fixture.presentation,
        fixture.screen_contract,
        fixture.display_policy,
        ui_implementation_id=C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
        ui_revision=C4_STAGE1_REVIEW_PRESENTER_REVISION,
        ui_session_id="disconnect-pre-registration-session",
    )
    outputs = _visible_outputs(context, fixture)
    payload = {
        "context": review_service_module._model_payload(context),
        "display_policy": review_service_module._model_payload(fixture.display_policy),
        "source_png_base64": base64.b64encode(fixture.source_bytes).decode("ascii"),
        "outputs": [
            review_service_module._visible_output_payload(item) for item in outputs
        ],
    }
    nonce = "e" * 64
    issued_at = datetime.now(timezone.utc).isoformat()
    body = canonical_json_bytes(payload)
    body_sha256 = hashlib.sha256(body).hexdigest()
    message = c4_stage1_review_ipc_auth_message(
        operation="display",
        body_length=len(body),
        body_sha256=body_sha256,
        nonce=nonce,
        issued_at=issued_at,
    )
    secret = (state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME).read_bytes()
    request = {
        "schema_version": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "operation": "display",
        "body_length": len(body),
        "body_sha256": body_sha256,
        "nonce": nonce,
        "issued_at": issued_at,
        "request_hmac_sha256": hmac.digest(secret, message, "sha256").hex(),
    }
    with C4Stage1ReviewServiceServer(service) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = socket.create_connection(server.address, timeout=2)
        connection.sendall(canonical_json_bytes(request) + b"\n" + body)
        assert presenter.validation_started.wait(3)
        connection.shutdown(socket.SHUT_RDWR)
        connection.close()
        assert presenter.request_cancelled.wait(3)
        assert presenter.finished.wait(3)
        assert presenter.browser_launched.is_set() is False
        assert presenter.generic_cancel_calls == 0

        admission_released = False
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if server._server.try_acquire_display_admission():
                server._server.release_display_admission()
                admission_released = True
                break
            time.sleep(0.01)
        assert admission_released is True
        retry_client = C4Stage1ReviewServiceClient(
            *server.address,
            auth_secret_path=state_root / C4_STAGE1_REVIEW_IPC_AUTH_FILENAME,
            timeout_seconds=6,
            presenter_timeout_ms=1_000,
        )
        with pytest.raises(C4Stage1ReviewServiceError, match="terminally in progress"):
            retry_client.display(
                context=context,
                display_policy=fixture.display_policy,
                source_png_bytes=fixture.source_bytes,
                outputs=outputs,  # type: ignore[arg-type]
            )
        assert len(presenter.calls) == 1
        assert presenter.browser_launched.is_set() is False
        server.shutdown()
        thread.join(timeout=5)
        assert not thread.is_alive()

    database = sqlite3.connect(state_root / "review-ledgers.sqlite3")
    try:
        assert database.execute(
            f"SELECT COUNT(*) FROM {review_service_module._PRESENTATION_CONTEXT_TABLE}"
        ).fetchone() == (0,)
        assert database.execute(
            f"SELECT operation, status, COUNT(*) "
            f"FROM {review_service_module._STATEFUL_OPERATION_RESULT_TABLE} "
            "GROUP BY operation, status"
        ).fetchall() == [("display", "in_progress", 1)]
    finally:
        database.close()

    with pytest.raises(C4Stage1ReviewServiceError, match="incomplete stateful cohort"):
        C4Stage1ReviewService(
            state_root,
            artifact_roots=(artifact_root,),
            model_roots=(model_root,),
            presenter=RecordingPinnedPresenter(),
        )


def test_cli_readiness_fails_closed_without_external_browser_runtime(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "cli-state"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_rei_c4_stage1_review_service.py"),
            "--state-root",
            str(state_root),
            "--artifact-root",
            str(tmp_path / "cli-artifacts"),
            "--model-root",
            str(tmp_path / "cli-models"),
            "--runtime-provenance-root",
            str(tmp_path / "cli-provenance"),
            "--external-runtime-root",
            str(tmp_path / "cli-runtime"),
            "--external-browser-root",
            str(tmp_path / "cli-browser"),
            "--readiness-only",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode != 0
    assert "fresh external browser user-data path" in completed.stderr
    assert not state_root.exists()
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys;"
                f"sys.path.insert(0,{str(ROOT / 'app' / 'backend')!r});"
                "import rei.evaluation.c4_stage1_review_service;"
                "blocked={'torch','diffusers','transformers','accelerate','safetensors'};"
                "print(','.join(sorted(blocked & {name.split('.',1)[0] for name in sys.modules})))"
            ),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == ""


def test_sqlite_schema_has_full_durability_and_unique_review_ledgers(
    tmp_path: Path,
) -> None:
    _, _, state_root, _, _ = _service(tmp_path)
    database = state_root / "review-ledgers.sqlite3"
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        connection.execute("PRAGMA synchronous=FULL")
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        for table in (
            "display_attestation_uses",
            "display_receipt_uses",
            "operator_policy_uses",
            "presenter_submissions",
            "operator_signing_leases",
        ):
            indexes = connection.execute(f"PRAGMA index_list({table})").fetchall()
            assert sum(bool(item[2]) for item in indexes) >= 5
    finally:
        connection.close()
