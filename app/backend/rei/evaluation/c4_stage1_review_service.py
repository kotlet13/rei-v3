"""Local, model-free C4 Stage 1 review service.

The service is the concrete owner of the five secrets committed by the
pre-output review manifest: one display-attestation key, two independent
operator keys, one IPC-authentication key, and one submission/authority-state
authentication key.  Secret bytes remain in a private, link-safe state
directory; only SHA-256 commitments cross the service boundary.  Five SQLite
authority tables provide durable consume-once state for display attestations,
completed display receipts, operator policies, presenter submissions, and
operator signing leases.

This module deliberately imports no renderer or model package.  The optional
loopback JSON transport carries canonical review objects and exact PNG bytes,
never keys, filesystem paths, or model/provider labels.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import select
import socket
import socketserver
import sqlite3
import stat
import sys
import threading
import time
from typing import Literal, Protocol, Self, TypeVar

from pydantic import BaseModel, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenArtifactModel, FrozenModel, HashDigest
from .c4_blind_review import C4HumanReviewOperatorPolicy
from .c4_stage1_review import (
    C4Stage1ConsumedDisplayAttestation,
    C4Stage1ConsumedDisplayReceipt,
    C4Stage1ConsumedOperatorPolicyReceipt,
    C4Stage1DisplayAttestation,
    C4Stage1DisplayAttesterPolicy,
    C4Stage1DisplayContext,
    C4Stage1DisplayExecutionReceipt,
    C4Stage1DisplayPortAcknowledgement,
    C4Stage1DisplayPortResult,
    C4Stage1HumanReviewOperatorAttestation,
    C4Stage1HumanReviewUnsignedClaim,
    C4Stage1VisibleOutput,
    build_c4_stage1_display_attestation,
    build_c4_stage1_display_port_acknowledgement,
    build_c4_stage1_operator_attestation,
    c4_stage1_display_attestation_message,
    c4_stage1_operator_attestation_message,
    record_c4_stage1_consumed_display_attestation,
    record_c4_stage1_consumed_display_receipt,
    record_c4_stage1_consumed_operator_policy_receipt,
    verify_c4_stage1_operator_attestation,
)
from .c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY,
    C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256,
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
    C4_STAGE1_REVIEW_PRESENTER_REVISION,
    C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_UI_BUNDLE_SHA256,
)
from .c4_stage1_review_presenter import C4Stage1ReviewBrowserRuntimePin


C4_STAGE1_REVIEW_IPC_SCHEMA = C4_STAGE1_REVIEW_IPC_PROTOCOL
C4_STAGE1_REVIEW_SERVICE_SCHEMA = C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION
C4_STAGE1_REVIEW_LEDGER_SCHEMA = C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION

# Explicit aliases make the frozen manifest vocabulary available without
# coupling this file to the manifest builder's ownership.
C4_STAGE1_OFFLINE_REVIEW_PRESENTER_ID = C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
C4_STAGE1_OFFLINE_REVIEW_PRESENTER_REVISION = C4_STAGE1_REVIEW_PRESENTER_REVISION

C4_STAGE1_REVIEW_SECRET_BYTES = 32
C4_STAGE1_REVIEW_MAX_IPC_BYTES = 128 * 1024 * 1024
C4_STAGE1_REVIEW_MAX_NON_DISPLAY_BODY_BYTES = 4 * 1024 * 1024
C4_STAGE1_REVIEW_MAX_PREAUTH_HEADER_BYTES = 16 * 1024
C4_STAGE1_REVIEW_BODY_READ_CHUNK_BYTES = 64 * 1024
C4_STAGE1_REVIEW_MAX_IPC_TIMEOUT_SECONDS = (4 * 60 * 60) + 60
C4_STAGE1_REVIEW_DEFAULT_PRESENTER_TIMEOUT_MS = 60 * 60 * 1000
C4_STAGE1_REVIEW_CLIENT_TIMEOUT_MARGIN_SECONDS = 5.0
C4_STAGE1_REVIEW_PREAUTH_TIMEOUT_SECONDS = 2.0
C4_STAGE1_REVIEW_AUTHENTICATED_BODY_TIMEOUT_SECONDS = 15.0
C4_STAGE1_REVIEW_RESPONSE_TIMEOUT_SECONDS = 2.0
C4_STAGE1_REVIEW_CANCEL_JOIN_TIMEOUT_SECONDS = 2.0
C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS = 8
C4_STAGE1_REVIEW_LOOPBACK_HOST = "127.0.0.1"
C4_STAGE1_REVIEW_READINESS_ID_NAMESPACE = "c4_s1_review_service_ready"

_WINDOWS_REPARSE_ATTRIBUTE = 0x0400
_DISPLAY_SECRET_FILE = "display-attestation.key"
_OPERATOR_SECRET_FILES = ("operator-1.key", "operator-2.key")
_IPC_AUTH_SECRET_FILE = "ipc-auth.key"
_SUBMISSION_AUTH_SECRET_FILE = "submission-auth.key"
C4_STAGE1_REVIEW_IPC_AUTH_FILENAME = _IPC_AUTH_SECRET_FILE
_DATABASE_FILE = "review-ledgers.sqlite3"
_STATE_MARKER_FILE = "state-instance.json"
_STATE_OWNER_LOCK_FILE = "state-owner.lock"
_LEDGER_TABLES = (
    "display_attestation_uses",
    "display_receipt_uses",
    "operator_policy_uses",
)
_PRESENTATION_CONTEXT_TABLE = "presentation_contexts"
_PRESENTER_SUBMISSION_TABLE = "presenter_submissions"
_OPERATOR_SIGNING_LEASE_TABLE = "operator_signing_leases"
_COMPLETED_SIGNING_COHORT_TABLE = "completed_signing_cohort"
_IPC_NONCE_TABLE = "ipc_request_nonces"
_STATEFUL_OPERATION_RESULT_TABLE = "stateful_operation_results"
_STATEFUL_OPERATIONS = frozenset(
    {
        "display",
        "take_presentation_submission",
        "consume_display_attestation",
        "consume_display_receipt",
        "issue_operator_signing_lease",
        "sign_operator_claim_cohort",
        "consume_operator_policy",
    }
)
_STATEFUL_OPERATION_CARDINALITY = {
    "display": 2,
    "take_presentation_submission": 2,
    "consume_display_attestation": 2,
    "consume_display_receipt": 2,
    "issue_operator_signing_lease": 2,
    "sign_operator_claim_cohort": 1,
    "consume_operator_policy": 2,
}
_STATEFUL_OPERATION_MAX_COMPLETED_ROWS = 13
_STATEFUL_OPERATION_REQUEST_DOMAIN = b"rei-c4-stage1-stateful-operation-request-v1\x00"
_STATEFUL_OPERATION_RESULT_AUTH_DOMAIN = (
    b"rei-c4-stage1-stateful-operation-result-auth-v1\x00"
)
_COMPLETED_SIGNING_COHORT_AUTH_DOMAIN = (
    b"rei-c4-stage1-completed-signing-cohort-authority-snapshot-v1\x00"
)
_IPC_MAX_CLOCK_SKEW_SECONDS = 60
_SUBMISSION_OUTPUT_BOOLEAN_FIELDS = (
    "source_subject_present",
    "identity_preserved",
    "unchanged_composition_preserved",
    "option_action_correct",
    "no_extra_actor",
    "no_generated_external_evidence_claim",
    "reviewer_uncertain",
)
_SUBMISSION_PAIR_BOOLEAN_FIELDS = (
    "actions_visibly_distinct",
    "same_source_bytes_confirmed",
)
_ModelT = TypeVar("_ModelT", bound=BaseModel)
_EXECUTING_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class C4Stage1ReviewServiceError(RuntimeError):
    """Fixed-boundary rejection raised by the local service or its client."""


@dataclass(frozen=True, slots=True)
class _C4Stage1StatefulOperationRequest:
    operation_request_id: str
    service_epoch_id: str
    ipc_schema: str
    operation: str
    body_length: int
    body_sha256: str

    def auth_payload(self) -> dict[str, object]:
        return {
            "operation_request_id": self.operation_request_id,
            "service_epoch_id": self.service_epoch_id,
            "ipc_schema": self.ipc_schema,
            "operation": self.operation,
            "body_length": self.body_length,
            "body_sha256": self.body_sha256,
        }


class C4Stage1ReviewRepositoryGateBinding(FrozenArtifactModel):
    """Immutable canonical copy of the repository gate captured by the service."""

    schema_version: Literal["rei-c4-stage1-review-repository-gate-binding-v1"] = (
        "rei-c4-stage1-review-repository-gate-binding-v1"
    )
    repository_gate_binding_id: str
    repository_gate_binding_sha256: HashDigest
    repository_gate_id: str
    repository_gate_sha256: HashDigest
    repository_gate_canonical_json: str

    @classmethod
    def create(cls, gate: BaseModel) -> C4Stage1ReviewRepositoryGateBinding:
        from .c4_stage1_attempt import C4Stage1RepositoryGate

        gate = C4Stage1RepositoryGate.model_validate(
            gate.model_dump(mode="python", round_trip=True)
        )
        base = {
            "schema_version": "rei-c4-stage1-review-repository-gate-binding-v1",
            "repository_gate_id": gate.repository_gate_id,
            "repository_gate_sha256": gate.repository_gate_sha256,
            "repository_gate_canonical_json": gate.canonical_json_bytes().decode(
                "utf-8"
            ),
        }
        return cls(
            repository_gate_binding_id=content_id(
                "c4_s1_review_repo_gate_binding", base
            ),
            repository_gate_binding_sha256=_sha256(canonical_json_bytes(base)),
            **base,
        )

    @model_validator(mode="after")
    def validate_repository_gate_binding(self) -> Self:
        from .c4_stage1_attempt import C4Stage1RepositoryGate

        try:
            gate = C4Stage1RepositoryGate.model_validate_json(
                self.repository_gate_canonical_json
            )
        except Exception as exc:
            raise ValueError("C4 Stage 1 repository gate binding is invalid") from exc
        if (
            gate.repository_gate_id != self.repository_gate_id
            or gate.repository_gate_sha256 != self.repository_gate_sha256
            or gate.canonical_json_bytes().decode("utf-8")
            != self.repository_gate_canonical_json
        ):
            raise ValueError("C4 Stage 1 repository gate binding changed")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "repository_gate_binding_id",
                "repository_gate_binding_sha256",
            },
        )
        if self.repository_gate_binding_id != content_id(
            "c4_s1_review_repo_gate_binding", base
        ) or self.repository_gate_binding_sha256 != _sha256(canonical_json_bytes(base)):
            raise ValueError("C4 Stage 1 repository gate binding address is invalid")
        return self


class C4Stage1AuthenticatedPresenterSubmission(FrozenArtifactModel):
    """Exact presenter bytes plus a service-held-key authentication tag."""

    schema_version: Literal["rei-c4-stage1-authenticated-presenter-submission-v1"] = (
        "rei-c4-stage1-authenticated-presenter-submission-v1"
    )
    submission_receipt_id: str
    submission_receipt_sha256: HashDigest
    context_id: str
    context_sha256: HashDigest
    packet_id: str
    packet_sha256: HashDigest
    ipc_protocol: Literal["rei-c4-stage1-review-ipc-v1"] = C4_STAGE1_REVIEW_IPC_SCHEMA
    service_schema_revision: Literal["rei-c4-stage1-review-service-v2"] = (
        C4_STAGE1_REVIEW_SERVICE_SCHEMA
    )
    ledger_schema_revision: Literal["rei-c4-stage1-review-ledger-v2"] = (
        C4_STAGE1_REVIEW_LEDGER_SCHEMA
    )
    canonical_submission_base64: str
    canonical_submission_sha256: HashDigest
    canonical_submission_size_bytes: int
    submitted_at: datetime
    service_auth_hmac_sha256: HashDigest
    presenter_submission_is_exact: Literal[True] = True
    service_auth_secret_exposed: Literal[False] = False

    @property
    def canonical_submission_bytes(self) -> bytes:
        try:
            value = base64.b64decode(self.canonical_submission_base64, validate=True)
        except (TypeError, ValueError):
            raise ValueError("Presenter submission encoding is invalid") from None
        return value

    @model_validator(mode="after")
    def validate_submission_receipt(self) -> Self:
        value = self.canonical_submission_bytes
        if (
            type(self.canonical_submission_size_bytes) is not int
            or not 0 < self.canonical_submission_size_bytes <= 64 * 1024
            or len(value) != self.canonical_submission_size_bytes
            or _sha256(value) != self.canonical_submission_sha256
            or canonical_json_bytes(_decode_json(value)) != value
            or self.submitted_at.tzinfo is None
            or self.submitted_at.utcoffset() is None
            or self.submitted_at.astimezone(timezone.utc) != self.submitted_at
        ):
            raise ValueError("Authenticated presenter submission bytes are invalid")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "submission_receipt_id",
                "submission_receipt_sha256",
                "service_auth_hmac_sha256",
            },
        )
        if self.submission_receipt_id != content_id(
            "c4_s1_auth_presenter_submission", base
        ) or self.submission_receipt_sha256 != _sha256(canonical_json_bytes(base)):
            raise ValueError("Presenter submission receipt address is invalid")
        return self


class C4Stage1OperatorSigningLease(FrozenArtifactModel):
    """Create-once, expiring service lease consumed by operator signing."""

    schema_version: Literal["rei-c4-stage1-operator-signing-lease-v1"] = (
        "rei-c4-stage1-operator-signing-lease-v1"
    )
    operator_signing_lease_id: str
    operator_signing_lease_sha256: HashDigest
    operator_policy_id: str
    operator_policy_sha256: HashDigest
    submission_receipt_id: str
    submission_receipt_sha256: HashDigest
    context_id: str
    context_sha256: HashDigest
    display_receipt_id: str
    display_receipt_sha256: HashDigest
    consumed_display_receipt_id: str
    consumed_display_receipt_sha256: HashDigest
    issued_at: datetime
    expires_at: datetime
    review_timestamp: datetime
    service_auth_hmac_sha256: HashDigest
    create_once: Literal[True] = True
    consume_once_before_operator_hmac: Literal[True] = True
    service_auth_secret_exposed: Literal[False] = False

    @model_validator(mode="after")
    def validate_operator_signing_lease(self) -> Self:
        if (
            self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.issued_at.utcoffset() is None
            or self.expires_at.utcoffset() is None
            or self.issued_at.astimezone(timezone.utc) != self.issued_at
            or self.expires_at.astimezone(timezone.utc) != self.expires_at
            or not self.issued_at < self.expires_at
            or self.review_timestamp.tzinfo is None
            or self.review_timestamp.utcoffset() is None
            or self.review_timestamp.astimezone(timezone.utc) != self.review_timestamp
            or self.review_timestamp > self.issued_at
            or (self.issued_at - self.review_timestamp).total_seconds() > 10 * 60
            or (self.expires_at - self.issued_at).total_seconds() > 10 * 60
        ):
            raise ValueError("C4 Stage 1 operator signing lease window is invalid")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "operator_signing_lease_id",
                "operator_signing_lease_sha256",
                "service_auth_hmac_sha256",
            },
        )
        if self.operator_signing_lease_id != content_id(
            "c4_stage1_operator_signing_lease", base
        ) or self.operator_signing_lease_sha256 != _sha256(canonical_json_bytes(base)):
            raise ValueError("C4 Stage 1 operator signing lease address is invalid")
        return self


class C4Stage1OperatorSigningRequest(FrozenModel):
    """One complete, still-unsigned member of the atomic review cohort."""

    schema_version: Literal["rei-c4-stage1-operator-signing-request-v1"] = (
        "rei-c4-stage1-operator-signing-request-v1"
    )
    operator_policy: C4HumanReviewOperatorPolicy
    claim: C4Stage1HumanReviewUnsignedClaim
    submission_receipt: C4Stage1AuthenticatedPresenterSubmission
    operator_signing_lease: C4Stage1OperatorSigningLease
    display_receipt: C4Stage1DisplayExecutionReceipt
    consumed_display_receipt: C4Stage1ConsumedDisplayReceipt


class C4Stage1CompletedSigningCohortMember(FrozenModel):
    """Path-free authority-row snapshot for one durable cohort member."""

    editor_role: Literal["primary", "alternate"]
    provider_slot_id: str
    operator_policy_id: str
    operator_policy_sha256: HashDigest
    operator_key_commitment_sha256: HashDigest
    context_id: str
    context_sha256: HashDigest
    packet_id: str
    packet_sha256: HashDigest
    presentation_manifest_id: str
    presentation_manifest_sha256: HashDigest
    material_commitment_id: str
    material_commitment_sha256: HashDigest
    display_attestation_id: str
    display_attestation_sha256: HashDigest
    consumed_display_attestation_id: str
    consumed_display_attestation_sha256: HashDigest
    display_attestation_ledger_binding_sha256: HashDigest
    display_attestation_ledger_transaction_id: str
    display_receipt_id: str
    display_receipt_sha256: HashDigest
    consumed_display_receipt_id: str
    consumed_display_receipt_sha256: HashDigest
    display_receipt_ledger_binding_sha256: HashDigest
    display_receipt_ledger_transaction_id: str
    submission_receipt_id: str
    submission_receipt_sha256: HashDigest
    operator_signing_lease_id: str
    operator_signing_lease_sha256: HashDigest
    claim_id: str
    claim_sha256: HashDigest
    attestation_id: str
    attestation_sha256: HashDigest
    consumed_operator_receipt_id: str
    consumed_operator_receipt_sha256: HashDigest
    operator_policy_ledger_binding_sha256: HashDigest
    operator_policy_ledger_transaction_id: str


class C4Stage1CompletedSigningCohort(FrozenArtifactModel):
    """The one durable latch proving an exact two-review signing transaction."""

    schema_version: Literal["rei-c4-stage1-completed-signing-cohort-v1"] = (
        "rei-c4-stage1-completed-signing-cohort-v1"
    )
    operator_signing_cohort_id: str
    operator_signing_cohort_sha256: HashDigest
    run_id: str
    prepared_attempt_id: str
    prepared_attempt_sha256: HashDigest
    prepared_anchor_storage_id: str
    prepared_anchor_content_sha256: HashDigest
    screen_contract_id: str
    screen_contract_sha256: HashDigest
    display_policy_id: str
    display_policy_sha256: HashDigest
    display_policy_artifact_sha256: HashDigest
    review_schema_id: str
    review_schema_sha256: HashDigest
    rubric_version: str
    source_storage_id: str
    source_image_sha256: HashDigest
    members: tuple[
        C4Stage1CompletedSigningCohortMember,
        C4Stage1CompletedSigningCohortMember,
    ]
    completed_at: datetime
    authority_snapshot_hmac_sha256: HashDigest
    review_count: Literal[2] = 2
    exact_two_reviews_signed_together: Literal[True] = True
    submission_and_lease_rows_persisted_atomically: Literal[True] = True
    operator_policy_rows_persisted_atomically: Literal[True] = True
    single_use_cohort_latch: Literal[True] = True

    @model_validator(mode="after")
    def validate_completed_signing_cohort(self) -> Self:
        if (
            self.completed_at.tzinfo is None
            or self.completed_at.utcoffset() is None
            or self.completed_at.astimezone(timezone.utc) != self.completed_at
            or tuple(member.editor_role for member in self.members)
            != ("primary", "alternate")
            or self.review_count != 2
            or self.exact_two_reviews_signed_together is not True
            or self.submission_and_lease_rows_persisted_atomically is not True
            or self.operator_policy_rows_persisted_atomically is not True
            or self.single_use_cohort_latch is not True
        ):
            raise ValueError("C4 Stage 1 completed signing cohort is invalid")
        distinct_fields = (
            "provider_slot_id",
            "operator_policy_id",
            "context_id",
            "packet_id",
            "packet_sha256",
            "presentation_manifest_id",
            "presentation_manifest_sha256",
            "material_commitment_id",
            "material_commitment_sha256",
            "display_attestation_id",
            "consumed_display_attestation_id",
            "display_receipt_id",
            "consumed_display_receipt_id",
            "submission_receipt_id",
            "operator_signing_lease_id",
            "claim_id",
            "attestation_id",
            "consumed_operator_receipt_id",
            "display_attestation_ledger_transaction_id",
            "display_receipt_ledger_transaction_id",
            "operator_policy_ledger_transaction_id",
        )
        if (
            any(
                len({getattr(member, field) for member in self.members}) != 2
                for field in distinct_fields
            )
            or len({member.operator_key_commitment_sha256 for member in self.members})
            != 2
        ):
            raise ValueError("C4 Stage 1 signing cohort members are not distinct")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "operator_signing_cohort_id",
                "operator_signing_cohort_sha256",
            },
        )
        if self.operator_signing_cohort_id != content_id(
            "c4_s1_completed_signing_cohort", body
        ) or self.operator_signing_cohort_sha256 != _sha256(canonical_json_bytes(body)):
            raise ValueError("C4 Stage 1 signing cohort address is invalid")
        return self


class C4Stage1AuthenticatedReviewEnvelope(FrozenArtifactModel):
    """Portable post-seal envelope replacing the raw presenter submission."""

    schema_version: Literal["rei-c4-stage1-authenticated-review-envelope-v1"] = (
        "rei-c4-stage1-authenticated-review-envelope-v1"
    )
    authenticated_review_envelope_id: str
    authenticated_review_envelope_sha256: HashDigest
    submission_receipt: C4Stage1AuthenticatedPresenterSubmission
    operator_signing_lease: C4Stage1OperatorSigningLease

    @classmethod
    def create(
        cls,
        *,
        submission_receipt: C4Stage1AuthenticatedPresenterSubmission,
        operator_signing_lease: C4Stage1OperatorSigningLease,
    ) -> C4Stage1AuthenticatedReviewEnvelope:
        submission_receipt = C4Stage1AuthenticatedPresenterSubmission.model_validate(
            submission_receipt.model_dump(mode="python", round_trip=True)
        )
        operator_signing_lease = C4Stage1OperatorSigningLease.model_validate(
            operator_signing_lease.model_dump(mode="python", round_trip=True)
        )
        if (
            operator_signing_lease.submission_receipt_id
            != submission_receipt.submission_receipt_id
            or operator_signing_lease.submission_receipt_sha256
            != submission_receipt.submission_receipt_sha256
        ):
            raise ValueError("Authenticated review envelope crosses submissions")
        base = {
            "schema_version": "rei-c4-stage1-authenticated-review-envelope-v1",
            "submission_receipt": submission_receipt,
            "operator_signing_lease": operator_signing_lease,
        }
        return cls(
            authenticated_review_envelope_id=content_id(
                "c4_s1_auth_review_envelope", base
            ),
            authenticated_review_envelope_sha256=_sha256(canonical_json_bytes(base)),
            **base,
        )

    @model_validator(mode="after")
    def validate_review_envelope(self) -> Self:
        if (
            self.operator_signing_lease.submission_receipt_id
            != self.submission_receipt.submission_receipt_id
            or self.operator_signing_lease.submission_receipt_sha256
            != self.submission_receipt.submission_receipt_sha256
        ):
            raise ValueError("Authenticated review envelope crosses submissions")
        base = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "authenticated_review_envelope_id",
                "authenticated_review_envelope_sha256",
            },
        )
        if self.authenticated_review_envelope_id != content_id(
            "c4_s1_auth_review_envelope", base
        ) or self.authenticated_review_envelope_sha256 != _sha256(
            canonical_json_bytes(base)
        ):
            raise ValueError("Authenticated review envelope address is invalid")
        return self


class C4Stage1ReviewServiceReadiness(FrozenArtifactModel):
    """Public content-addressed receipt; it contains commitments, never keys."""

    schema_version: Literal["rei-c4-stage1-review-service-v2"] = (
        "rei-c4-stage1-review-service-v2"
    )
    readiness_receipt_id: str
    readiness_receipt_sha256: HashDigest
    presenter_implementation_id: Literal["rei-c4-stage1-offline-review-ui"] = (
        C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
    )
    presenter_revision: Literal["c4-stage1-review-ui-v1"] = (
        C4_STAGE1_REVIEW_PRESENTER_REVISION
    )
    ipc_schema: Literal["rei-c4-stage1-review-ipc-v1"] = C4_STAGE1_REVIEW_IPC_SCHEMA
    ledger_schema: Literal["rei-c4-stage1-review-ledger-v2"] = (
        C4_STAGE1_REVIEW_LEDGER_SCHEMA
    )
    ui_bundle_sha256: HashDigest
    content_security_policy_sha256: HashDigest
    repository_gate: C4Stage1ReviewRepositoryGateBinding
    browser_runtime: C4Stage1ReviewBrowserRuntimePin
    presenter_session_timeout_ms: int
    service_epoch_id: str
    state_directory_identity_sha256: HashDigest
    state_database_identity_sha256: HashDigest
    boundary_roots_identity_sha256: HashDigest
    exclusive_state_owner_lock_held: Literal[True] = True
    copied_state_rejected: Literal[True] = True
    display_signing_key_commitment_sha256: HashDigest
    operator_signing_key_commitment_sha256s: tuple[HashDigest, HashDigest]
    ipc_auth_key_commitment_sha256: HashDigest
    submission_auth_key_commitment_sha256: HashDigest
    secret_count: Literal[5] = 5
    secret_size_bytes: Literal[32] = 32
    ipc_auth_required: Literal[True] = True
    ipc_auth_secret_separate_from_review_keys: Literal[True] = True
    ipc_request_nonce_replay_rejected: Literal[True] = True
    ipc_response_auth_required: Literal[True] = True
    ipc_response_request_binding_required: Literal[True] = True
    ipc_response_replay_and_cross_operation_rejected: Literal[True] = True
    stateful_ipc_result_journal_required: Literal[True] = True
    stateful_ipc_request_id_server_derived: Literal[True] = True
    stateful_ipc_result_hmac_required: Literal[True] = True
    stateful_ipc_transport_retry_limit: Literal[1] = 1
    stateful_ipc_operation_count: Literal[7] = 7
    stateful_ipc_max_completed_rows: Literal[13] = 13
    display_in_progress_never_relaunched: Literal[True] = True
    sealed_sign_result_recoverable: Literal[True] = True
    presenter_submission_auth_required: Literal[True] = True
    operator_signing_lease_required: Literal[True] = True
    sqlite_journal_mode: Literal["wal"] = "wal"
    sqlite_synchronous: Literal["FULL"] = "FULL"
    one_time_ledgers: tuple[
        Literal["display_attestation"],
        Literal["display_receipt"],
        Literal["operator_policy"],
        Literal["presenter_submission"],
        Literal["operator_signing_lease"],
    ] = (
        "display_attestation",
        "display_receipt",
        "operator_policy",
        "presenter_submission",
        "operator_signing_lease",
    )
    service_is_model_free: Literal[True] = True
    secrets_exposed: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_readiness(self) -> Self:
        commitments = (
            self.display_signing_key_commitment_sha256,
            *self.operator_signing_key_commitment_sha256s,
            self.ipc_auth_key_commitment_sha256,
            self.submission_auth_key_commitment_sha256,
        )
        if (
            len(set(commitments)) != 5
            or self.secret_count != 5
            or self.secret_size_bytes != C4_STAGE1_REVIEW_SECRET_BYTES
            or self.ipc_auth_required is not True
            or self.ipc_auth_secret_separate_from_review_keys is not True
            or self.ipc_request_nonce_replay_rejected is not True
            or self.ipc_response_auth_required is not True
            or self.ipc_response_request_binding_required is not True
            or self.ipc_response_replay_and_cross_operation_rejected is not True
            or self.stateful_ipc_result_journal_required is not True
            or self.stateful_ipc_request_id_server_derived is not True
            or self.stateful_ipc_result_hmac_required is not True
            or self.stateful_ipc_transport_retry_limit != 1
            or self.stateful_ipc_operation_count != len(_STATEFUL_OPERATIONS)
            or self.stateful_ipc_max_completed_rows
            != _STATEFUL_OPERATION_MAX_COMPLETED_ROWS
            or self.display_in_progress_never_relaunched is not True
            or self.sealed_sign_result_recoverable is not True
            or self.presenter_submission_auth_required is not True
            or self.operator_signing_lease_required is not True
            or type(self.presenter_session_timeout_ms) is not int
            or not 1_000 <= self.presenter_session_timeout_ms <= 4 * 60 * 60 * 1000
            or self.exclusive_state_owner_lock_held is not True
            or self.copied_state_rejected is not True
            or self.ui_bundle_sha256 != C4_STAGE1_REVIEW_UI_BUNDLE_SHA256
            or self.content_security_policy_sha256
            != C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256
            or self.sqlite_journal_mode != "wal"
            or self.sqlite_synchronous != "FULL"
            or self.service_is_model_free is not True
            or self.secrets_exposed is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 review readiness weakens its boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"readiness_receipt_id", "readiness_receipt_sha256"},
        )
        expected_id = content_id(C4_STAGE1_REVIEW_READINESS_ID_NAMESPACE, payload)
        expected_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        if (
            self.readiness_receipt_id != expected_id
            or self.readiness_receipt_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 review readiness address is invalid")
        return self


class _ReviewEndpoint(Protocol):
    def display(
        self,
        *,
        context: C4Stage1DisplayContext,
        display_policy: C4Stage1DisplayAttesterPolicy,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
    ) -> C4Stage1DisplayPortResult: ...

    def take_presentation_submission(
        self,
        *,
        context_id: str,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1AuthenticatedPresenterSubmission: ...

    def issue_operator_signing_lease(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        submission_receipt: C4Stage1AuthenticatedPresenterSubmission,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_display_receipt: C4Stage1ConsumedDisplayReceipt,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1OperatorSigningLease: ...

    def verify_authenticated_submission(
        self, *, submission_receipt: C4Stage1AuthenticatedPresenterSubmission
    ) -> bool: ...

    def verify_operator_signing_lease(
        self, *, operator_signing_lease: C4Stage1OperatorSigningLease
    ) -> bool: ...

    def verify_display_attestation(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> bool: ...

    def consume_display_attestation_once(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> C4Stage1ConsumedDisplayAttestation: ...

    def verify_consumed_display_attestation(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
        consumed_receipt: C4Stage1ConsumedDisplayAttestation,
    ) -> bool: ...

    def consume_display_receipt_once(
        self, *, display_receipt: C4Stage1DisplayExecutionReceipt
    ) -> C4Stage1ConsumedDisplayReceipt: ...

    def verify_consumed_display_receipt(
        self,
        *,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_receipt: C4Stage1ConsumedDisplayReceipt,
    ) -> bool: ...

    def consume_operator_policy_once(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1ConsumedOperatorPolicyReceipt: ...

    def verify_consumed_operator_policy(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
        consumed_receipt: C4Stage1ConsumedOperatorPolicyReceipt,
    ) -> bool: ...

    def sign_operator_claim_cohort(
        self,
        *,
        reviews: tuple[
            C4Stage1OperatorSigningRequest,
            C4Stage1OperatorSigningRequest,
        ],
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> tuple[
        C4Stage1HumanReviewOperatorAttestation,
        C4Stage1HumanReviewOperatorAttestation,
    ]: ...

    def verify_operator_attestation(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> bool: ...


class C4Stage1ReviewPresenter(Protocol):
    """Pinned offline HTML host; a generic image viewer is not sufficient."""

    presenter_implementation_id: str
    presenter_revision: str
    session_timeout_ms: int
    browser_runtime_pin: C4Stage1ReviewBrowserRuntimePin
    runtime_provenance_root: Path
    external_runtime_root: Path
    external_browser_root: Path

    def verify_operational(self) -> bool:
        """Verify the exact headed offline runtime without opening a review."""
        ...

    def verify_runtime_pin(self, expected: C4Stage1ReviewBrowserRuntimePin) -> bool: ...

    def cancel_active(self) -> bool: ...

    def present(
        self,
        context: C4Stage1DisplayContext,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
        *,
        cancellation_event: threading.Event | None = None,
    ) -> bool:
        """Return true only after the exact pinned UI completed presentation."""
        ...

    def peek_submission(self, context_id: str) -> tuple[bytes, datetime]:
        """Return the one canonical submission without forgetting it."""
        ...

    def discard_submission(
        self,
        context_id: str,
        *,
        expected_submission: bytes,
        expected_submitted_at: datetime,
    ) -> bool:
        """Forget only the exact submission durably journaled by the service."""
        ...


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_lower_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_link_or_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_safe_existing_ancestry(path: Path) -> None:
    if not path.is_absolute() or path != _absolute_lexical(path):
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state path must be lexical absolute"
        )
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as exc:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state ancestry is unavailable"
            ) from exc
        if _is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state ancestry contains a link"
            )


def _assert_private_directory(path: Path) -> None:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state directory is unavailable"
        ) from exc
    if _is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state directory is not ordinary"
        )


def _prepare_state_root(path: Path) -> None:
    _assert_safe_existing_ancestry(path.parent)
    _assert_private_directory(path.parent)
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        if any(path.iterdir()):
            required = {
                _DISPLAY_SECRET_FILE,
                *_OPERATOR_SECRET_FILES,
                _IPC_AUTH_SECRET_FILE,
                _SUBMISSION_AUTH_SECRET_FILE,
                _DATABASE_FILE,
                _STATE_MARKER_FILE,
                _STATE_OWNER_LOCK_FILE,
            }
            allowed = {
                *required,
                f"{_DATABASE_FILE}-wal",
                f"{_DATABASE_FILE}-shm",
            }
            names = {item.name for item in path.iterdir()}
            if not required <= names or not names <= allowed:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review state inventory is not an exact restart"
                )
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state directory could not be created"
        ) from exc
    _assert_safe_existing_ancestry(path)
    _assert_private_directory(path)
    try:
        os.chmod(path, 0o700)
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state permissions could not be applied"
        ) from exc


def _assert_no_root_overlap(
    state_root: Path,
    *,
    artifact_roots: Iterable[str | Path],
    model_roots: Iterable[str | Path],
) -> None:
    state = state_root.resolve(strict=False)
    declared = tuple(
        Path(value).expanduser() for value in (*artifact_roots, *model_roots)
    )
    if not declared:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review service requires declared artifact/model roots"
        )
    for root in declared:
        if not root.is_absolute():
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 artifact/model roots must be absolute"
            )
        resolved = root.resolve(strict=False)
        if _path_overlaps(state, resolved):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state overlaps an artifact/model root"
            )


def _path_overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _identity_digest(epoch: str, metadata: os.stat_result, *, role: str) -> str:
    return _sha256(
        epoch.encode("ascii")
        + b"\x00"
        + canonical_json_bytes(
            {
                "role": role,
                "device": int(metadata.st_dev),
                "inode": int(metadata.st_ino),
            }
        )
    )


def _acquire_owner_lock(path: Path) -> int:
    descriptor: int | None = None
    base_flags = (
        os.O_RDWR
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        try:
            descriptor = os.open(path, base_flags | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            before = _ordinary_file_metadata(path)
            descriptor = os.open(path, base_flags)
            opened = os.fstat(descriptor)
            after = _ordinary_file_metadata(path)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or not os.path.samestat(before, opened)
                or not os.path.samestat(opened, after)
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review owner lock changed while opening"
                )
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review owner lock is not one ordinary file"
            )
        if opened.st_size == 0:
            os.write(descriptor, b"0")
        elif opened.st_size != 1:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review owner lock has invalid content"
            )
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:  # pragma: no cover - Windows is the acceptance host
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ImportError, C4Stage1ReviewServiceError) as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if isinstance(exc, C4Stage1ReviewServiceError):
            raise
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state already has a live owner"
        ) from exc
    try:
        current = _ordinary_file_metadata(path, expected_size=1)
        if not os.path.samestat(os.fstat(descriptor), current):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review owner lock changed after acquisition"
            )
    except Exception:
        try:
            _release_owner_lock(descriptor)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise
    return descriptor


def _release_owner_lock(descriptor: int) -> None:
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _ordinary_file_metadata(
    path: Path, *, expected_size: int | None = None
) -> os.stat_result:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state file is unavailable"
        ) from exc
    if (
        _is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (expected_size is not None and metadata.st_size != expected_size)
    ):
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review state file is not one ordinary file"
        )
    return metadata


def _stable_read_secret(path: Path) -> bytes:
    before = _ordinary_file_metadata(path, expected_size=C4_STAGE1_REVIEW_SECRET_BYTES)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review secret could not be opened"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        value = os.read(descriptor, C4_STAGE1_REVIEW_SECRET_BYTES + 1)
        final_handle = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    after = _ordinary_file_metadata(path, expected_size=C4_STAGE1_REVIEW_SECRET_BYTES)
    if (
        not os.path.samestat(before, opened)
        or not os.path.samestat(opened, final_handle)
        or not os.path.samestat(opened, after)
        or len(value) != C4_STAGE1_REVIEW_SECRET_BYTES
    ):
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review secret changed while reading"
        )
    return value


def _load_or_create_secret(path: Path, *, excluding: set[bytes]) -> bytes:
    while True:
        candidate = secrets.token_bytes(C4_STAGE1_REVIEW_SECRET_BYTES)
        if candidate not in excluding:
            break
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        return _stable_read_secret(path)
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review secret could not be created"
        ) from exc
    try:
        view = memoryview(candidate)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError
            view = view[written:]
        os.fsync(descriptor)
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review secret initialization failed"
        ) from exc
    finally:
        os.close(descriptor)
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review secret permissions could not be applied"
        ) from exc
    stored = _stable_read_secret(path)
    if not hmac.compare_digest(candidate, stored):
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review secret differs after create-only initialization"
        )
    return stored


def _create_database_file(path: Path) -> None:
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        _ordinary_file_metadata(path)
        return
    except OSError as exc:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review ledger could not be created"
        ) from exc
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _ordinary_file_metadata(path, expected_size=0)


def _canonical_model(value: _ModelT, model_type: type[_ModelT]) -> _ModelT:
    if not isinstance(value, model_type):
        raise TypeError(f"C4 Stage 1 review value must be {model_type.__name__}")
    return model_type.model_validate(value.model_dump(mode="python", round_trip=True))


def _readiness_from_secrets(
    display_secret: bytes,
    operator_secrets: tuple[bytes, bytes],
    ipc_auth_secret: bytes,
    submission_auth_secret: bytes,
    repository_gate: C4Stage1ReviewRepositoryGateBinding,
    browser_runtime: C4Stage1ReviewBrowserRuntimePin,
    presenter_session_timeout_ms: int,
    service_epoch_id: str,
    state_directory_identity_sha256: str,
    state_database_identity_sha256: str,
    boundary_roots_identity_sha256: str,
) -> C4Stage1ReviewServiceReadiness:
    base = {
        "schema_version": C4_STAGE1_REVIEW_SERVICE_SCHEMA,
        "presenter_implementation_id": C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
        "presenter_revision": C4_STAGE1_REVIEW_PRESENTER_REVISION,
        "ipc_schema": C4_STAGE1_REVIEW_IPC_SCHEMA,
        "ledger_schema": C4_STAGE1_REVIEW_LEDGER_SCHEMA,
        "ui_bundle_sha256": C4_STAGE1_REVIEW_UI_BUNDLE_SHA256,
        "content_security_policy_sha256": (
            C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256
        ),
        "repository_gate": repository_gate,
        "browser_runtime": browser_runtime,
        "presenter_session_timeout_ms": presenter_session_timeout_ms,
        "service_epoch_id": service_epoch_id,
        "state_directory_identity_sha256": state_directory_identity_sha256,
        "state_database_identity_sha256": state_database_identity_sha256,
        "boundary_roots_identity_sha256": boundary_roots_identity_sha256,
        "exclusive_state_owner_lock_held": True,
        "copied_state_rejected": True,
        "display_signing_key_commitment_sha256": _sha256(display_secret),
        "operator_signing_key_commitment_sha256s": tuple(
            _sha256(value) for value in operator_secrets
        ),
        "ipc_auth_key_commitment_sha256": _sha256(ipc_auth_secret),
        "submission_auth_key_commitment_sha256": _sha256(submission_auth_secret),
        "secret_count": 5,
        "secret_size_bytes": C4_STAGE1_REVIEW_SECRET_BYTES,
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
        "stateful_ipc_operation_count": len(_STATEFUL_OPERATIONS),
        "stateful_ipc_max_completed_rows": (_STATEFUL_OPERATION_MAX_COMPLETED_ROWS),
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
    return C4Stage1ReviewServiceReadiness(
        readiness_receipt_id=content_id(C4_STAGE1_REVIEW_READINESS_ID_NAMESPACE, base),
        readiness_receipt_sha256=_sha256(canonical_json_bytes(base)),
        **base,
    )


def _transaction_id(domain: str, ledger_key: str, binding_sha256: str) -> str:
    digest = _sha256(
        canonical_json_bytes(
            {
                "domain": domain,
                "ledger_key": ledger_key,
                "binding_sha256": binding_sha256,
                "nonce": secrets.token_hex(16),
            }
        )
    )
    return f"{domain}-{digest[:40]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_clock(clock: Callable[[], datetime]) -> datetime:
    try:
        value = clock()
    except Exception:
        raise C4Stage1ReviewServiceError("C4 Stage 1 review clock failed") from None
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review clock must be timezone-aware"
        )
    return value.astimezone(timezone.utc)


def _later_of(left: datetime, right: datetime) -> datetime:
    left = left.astimezone(timezone.utc)
    right = right.astimezone(timezone.utc)
    return left if left >= right else right


def _binding_sha256(domain: str, *values: BaseModel) -> str:
    return _sha256(
        canonical_json_bytes(
            {
                "domain": domain,
                "values": tuple(
                    value.model_dump(mode="python", round_trip=True) for value in values
                ),
            }
        )
    )


def _completed_signing_cohort_authority_message(
    body: Mapping[str, object],
) -> bytes:
    return _COMPLETED_SIGNING_COHORT_AUTH_DOMAIN + canonical_json_bytes(body)


def _recv_before_absolute_deadline(
    connection: socket.socket,
    *,
    deadline: float,
    max_bytes: int,
) -> bytes:
    """Receive once without allowing byte-dribble to extend the total budget."""

    remaining_seconds = deadline - time.monotonic()
    if remaining_seconds <= 0:
        raise TimeoutError("C4 Stage 1 IPC receive deadline expired")
    connection.settimeout(max(remaining_seconds, 0.001))
    try:
        value = connection.recv(max_bytes)
    except socket.timeout:
        raise TimeoutError("C4 Stage 1 IPC receive deadline expired") from None
    if time.monotonic() > deadline:
        raise TimeoutError("C4 Stage 1 IPC receive deadline expired")
    return value


def _c4_stage1_review_ipc_body_limit(operation: str) -> int:
    return (
        C4_STAGE1_REVIEW_MAX_IPC_BYTES
        if operation == "display"
        else C4_STAGE1_REVIEW_MAX_NON_DISPLAY_BODY_BYTES
    )


def c4_stage1_review_ipc_auth_message(
    *,
    operation: str,
    body_length: int,
    body_sha256: str,
    nonce: str,
    issued_at: str,
) -> bytes:
    """Canonical HMAC message for the bounded pre-authentication header."""

    return (
        C4_STAGE1_REVIEW_IPC_SCHEMA.encode("ascii")
        + b"\x00"
        + canonical_json_bytes(
            {
                "schema_version": C4_STAGE1_REVIEW_IPC_SCHEMA,
                "operation": operation,
                "body_length": body_length,
                "body_sha256": body_sha256,
                "nonce": nonce,
                "issued_at": issued_at,
            }
        )
    )


def c4_stage1_review_ipc_response_auth_message(
    *,
    operation: str,
    request_nonce: str,
    request_message_sha256: str,
    ok: bool,
    result: object | None = None,
    error: str | None = None,
) -> bytes:
    """Canonical response envelope bound to one exact authenticated request."""

    if (
        type(ok) is not bool
        or (ok and error is not None)
        or (not ok and (not isinstance(error, str) or result is not None))
    ):
        raise ValueError("C4 Stage 1 IPC response envelope is invalid")
    body: dict[str, object] = {
        "schema_version": C4_STAGE1_REVIEW_IPC_SCHEMA,
        "operation": operation,
        "request_nonce": request_nonce,
        "request_message_sha256": request_message_sha256,
        "ok": ok,
    }
    body["result" if ok else "error"] = result if ok else error
    return (
        C4_STAGE1_REVIEW_IPC_SCHEMA.encode("ascii")
        + b"\x00response\x00"
        + canonical_json_bytes(body)
    )


def _capture_service_repository_gate(repository_root: Path) -> BaseModel:
    from .c4_stage1_attempt import capture_c4_stage1_repository_gate

    return capture_c4_stage1_repository_gate(repository_root)


def _submission_receipt_auth_message(
    receipt: C4Stage1AuthenticatedPresenterSubmission,
) -> bytes:
    return b"rei-c4-stage1-presenter-submission-auth-v1\x00" + canonical_json_bytes(
        receipt.model_dump(
            mode="python",
            round_trip=True,
            exclude={"service_auth_hmac_sha256"},
        )
    )


def _operator_signing_lease_auth_message(
    lease: C4Stage1OperatorSigningLease,
) -> bytes:
    return b"rei-c4-stage1-operator-signing-lease-auth-v1\x00" + canonical_json_bytes(
        lease.model_dump(
            mode="python",
            round_trip=True,
            exclude={"service_auth_hmac_sha256"},
        )
    )


class C4Stage1ReviewService:
    """Directly testable secret owner and durable ledger implementation."""

    def __init__(
        self,
        state_root: str | Path,
        *,
        artifact_roots: Iterable[str | Path],
        model_roots: Iterable[str | Path],
        presenter: C4Stage1ReviewPresenter,
        repository_root: str | Path = _EXECUTING_REPOSITORY_ROOT,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if (
            getattr(presenter, "presenter_implementation_id", None)
            != C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
            or getattr(presenter, "presenter_revision", None)
            != C4_STAGE1_REVIEW_PRESENTER_REVISION
            or not callable(getattr(presenter, "present", None))
            or not callable(getattr(presenter, "peek_submission", None))
            or not callable(getattr(presenter, "discard_submission", None))
            or not callable(getattr(presenter, "verify_runtime_pin", None))
            or not callable(getattr(presenter, "cancel_active", None))
        ):
            raise TypeError(
                "C4 Stage 1 review presenter must implement the pinned HTML host"
            )
        if not callable(clock):
            raise TypeError("C4 Stage 1 review clock must be callable")
        repository_root = Path(repository_root)
        if not repository_root.is_absolute():
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review repository root must be absolute"
            )
        try:
            repository_root = repository_root.resolve(strict=True)
            executing_root = _EXECUTING_REPOSITORY_ROOT.resolve(strict=True)
        except OSError as exc:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 executing checkout is unavailable"
            ) from exc
        if repository_root != executing_root:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review service rejects a second checkout"
            )
        try:
            repository_gate = C4Stage1ReviewRepositoryGateBinding.create(
                _capture_service_repository_gate(repository_root)
            )
        except Exception as exc:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review repository gate failed"
            ) from exc
        verify_presenter = getattr(presenter, "verify_operational", None)
        if not callable(verify_presenter):
            raise TypeError(
                "C4 Stage 1 review presenter must expose an operational probe"
            )
        try:
            if verify_presenter() is not True:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review presenter operational probe failed"
                )
            browser_runtime = C4Stage1ReviewBrowserRuntimePin.model_validate(
                presenter.browser_runtime_pin.model_dump(mode="python", round_trip=True)
            )
            presenter_session_timeout_ms = presenter.session_timeout_ms
            if (
                type(presenter_session_timeout_ms) is not int
                or not 1_000 <= presenter_session_timeout_ms <= 4 * 60 * 60 * 1000
            ):
                raise ValueError
            if presenter.verify_runtime_pin(browser_runtime) is not True:
                raise ValueError
        except Exception as exc:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 pinned Playwright runtime is not operational"
            ) from exc
        root = Path(state_root).expanduser()
        if not root.is_absolute():
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state root must be absolute"
            )
        root = _absolute_lexical(root)
        artifact_roots = tuple(artifact_roots)
        model_roots = tuple(model_roots)
        try:
            browser_user_data_parent = Path(presenter.browser_user_data_parent).resolve(
                strict=True
            )
            browser_executable_path = Path(presenter.browser_executable_path).resolve(
                strict=True
            )
            runtime_provenance_root = Path(presenter.runtime_provenance_root).resolve(
                strict=True
            )
            external_runtime_root = Path(presenter.external_runtime_root).resolve(
                strict=True
            )
            external_browser_root = Path(presenter.external_browser_root).resolve(
                strict=True
            )
            python_runtime_root = Path(sys.executable).resolve(strict=True).parent
        except Exception as exc:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter did not expose its verified boundary roots"
            ) from exc
        forbidden_roots = (
            repository_root,
            browser_user_data_parent,
            browser_executable_path.parent,
            runtime_provenance_root,
            external_runtime_root,
            external_browser_root,
            python_runtime_root,
        )
        if any(
            _path_overlaps(root.resolve(strict=False), forbidden)
            for forbidden in forbidden_roots
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state overlaps a repository/runtime/browser root"
            )
        _assert_no_root_overlap(
            root, artifact_roots=artifact_roots, model_roots=model_roots
        )
        _prepare_state_root(root)
        owner_lock_fd = _acquire_owner_lock(root / _STATE_OWNER_LOCK_FILE)
        # Install ownership immediately so every later constructor failure is
        # covered by the best-effort finalizer instead of leaking the OS lock.
        self._owner_lock_fd: int | None = owner_lock_fd
        marker_path = root / _STATE_MARKER_FILE
        if marker_path.exists():
            try:
                marker = _mapping(
                    _decode_json(marker_path.read_bytes()), label="state marker"
                )
            except Exception:
                self._owner_lock_fd = None
                _release_owner_lock(owner_lock_fd)
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review state marker is invalid"
                ) from None
            if (
                set(marker)
                != {
                    "schema_version",
                    "service_epoch",
                    "state_directory_identity_sha256",
                    "state_database_identity_sha256",
                    "boundary_roots_identity_sha256",
                }
                or marker.get("schema_version") != "rei-c4-stage1-review-state-v1"
            ):
                self._owner_lock_fd = None
                _release_owner_lock(owner_lock_fd)
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review state marker is invalid"
                )
            service_epoch = marker["service_epoch"]
            if (
                not isinstance(service_epoch, str)
                or len(service_epoch) != 64
                or any(ch not in "0123456789abcdef" for ch in service_epoch)
            ):
                self._owner_lock_fd = None
                _release_owner_lock(owner_lock_fd)
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review service epoch is invalid"
                )
        else:
            marker = None
            service_epoch = secrets.token_hex(32)
        created: set[bytes] = set()
        display_secret = _load_or_create_secret(
            root / _DISPLAY_SECRET_FILE, excluding=created
        )
        created.add(display_secret)
        operator_values: list[bytes] = []
        for filename in _OPERATOR_SECRET_FILES:
            value = _load_or_create_secret(root / filename, excluding=created)
            if value in created:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review secrets are not independent"
                )
            created.add(value)
            operator_values.append(value)
        if len(created) != 3:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review requires three independent secrets"
            )
        ipc_auth_secret = _load_or_create_secret(
            root / _IPC_AUTH_SECRET_FILE, excluding=created
        )
        if ipc_auth_secret in created:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 IPC auth secret is not independent"
            )
        created.add(ipc_auth_secret)
        submission_auth_secret = _load_or_create_secret(
            root / _SUBMISSION_AUTH_SECRET_FILE, excluding=created
        )
        if submission_auth_secret in created:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 submission auth secret is not independent"
            )
        created.add(submission_auth_secret)
        if len(created) != 5:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review requires five independent secrets"
            )
        database_path = root / _DATABASE_FILE
        _create_database_file(database_path)
        state_root_identity = os.lstat(root)
        database_identity = _ordinary_file_metadata(database_path)
        state_directory_identity_sha256 = _identity_digest(
            service_epoch, state_root_identity, role="state-directory"
        )
        state_database_identity_sha256 = _identity_digest(
            service_epoch, database_identity, role="state-database"
        )
        boundary_records: list[dict[str, object]] = []
        for role, values in (
            ("artifact", artifact_roots),
            ("model", model_roots),
            ("repository", (repository_root,)),
            ("browser-user-data", (browser_user_data_parent,)),
            ("browser-executable", (browser_executable_path.parent,)),
            ("runtime-provenance", (runtime_provenance_root,)),
            ("external-runtime", (external_runtime_root,)),
            ("external-browser", (external_browser_root,)),
            ("python-runtime", (python_runtime_root,)),
        ):
            for value in values:
                resolved = Path(value).expanduser().resolve(strict=False)
                # Bind the declared path to the service epoch while taking the
                # filesystem identity from its stable volume root.  Artifact and
                # model roots may be deliberately absent at service startup and
                # created by the run later; using the nearest existing ancestor
                # would therefore make an otherwise exact restart look rebound.
                volume_root = Path(resolved.anchor)
                metadata_value = os.lstat(volume_root)
                boundary_records.append(
                    {
                        "role": role,
                        "path_commitment_sha256": _sha256(
                            service_epoch.encode("ascii")
                            + b"\x00"
                            + os.fspath(resolved).encode("utf-8")
                        ),
                        "ancestor_identity_sha256": _identity_digest(
                            service_epoch, metadata_value, role=f"{role}-ancestor"
                        ),
                    }
                )
        boundary_roots_identity_sha256 = _sha256(
            canonical_json_bytes(tuple(boundary_records))
        )
        marker_body = {
            "schema_version": "rei-c4-stage1-review-state-v1",
            "service_epoch": service_epoch,
            "state_directory_identity_sha256": state_directory_identity_sha256,
            "state_database_identity_sha256": state_database_identity_sha256,
            "boundary_roots_identity_sha256": boundary_roots_identity_sha256,
        }
        if marker is None:
            descriptor = os.open(
                marker_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o600,
            )
            try:
                os.write(descriptor, canonical_json_bytes(marker_body))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        elif dict(marker) != marker_body:
            self._owner_lock_fd = None
            _release_owner_lock(owner_lock_fd)
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 copied or rebound review state is rejected"
            )
        self._state_root = root
        self._state_root_identity = state_root_identity
        self._owner_lock_fd = owner_lock_fd
        self._owner_lock_path = root / _STATE_OWNER_LOCK_FILE
        self._owner_lock_identity = _ordinary_file_metadata(
            self._owner_lock_path, expected_size=1
        )
        self._service_epoch = service_epoch
        self._secret_paths = (
            root / _DISPLAY_SECRET_FILE,
            *(root / filename for filename in _OPERATOR_SECRET_FILES),
            root / _IPC_AUTH_SECRET_FILE,
            root / _SUBMISSION_AUTH_SECRET_FILE,
        )
        self._secret_identities = tuple(
            _ordinary_file_metadata(path) for path in self._secret_paths
        )
        self._database_path = database_path
        self._database_identity = database_identity
        self._display_secret = display_secret
        self._operator_secrets = (operator_values[0], operator_values[1])
        self._ipc_auth_secret = ipc_auth_secret
        self._submission_auth_secret = submission_auth_secret
        self._cohort_lock = threading.RLock()
        self._stateful_operation_lock = threading.RLock()
        self._active_stateful_display_lock = threading.Lock()
        self._active_stateful_display_request_id: str | None = None
        self._pending_lock = threading.Lock()
        self._retained_contexts: dict[
            str, tuple[C4Stage1DisplayContext, C4Stage1DisplayPortAcknowledgement]
        ] = {}
        self._pending_submission_receipts: dict[
            str, C4Stage1AuthenticatedPresenterSubmission
        ] = {}
        self._pending_operator_leases: dict[str, C4Stage1OperatorSigningLease] = {}
        self._pending_operator_policy_deliveries: dict[
            str, C4Stage1ConsumedOperatorPolicyReceipt
        ] = {}
        self._signing_cohort_latch: C4Stage1CompletedSigningCohort | None = None
        self._repository_root = repository_root
        self._repository_gate = repository_gate
        self._browser_runtime = browser_runtime
        self._presenter_boundary_paths = (
            ("browser_user_data_parent", browser_user_data_parent),
            ("browser_executable_path", browser_executable_path),
            ("runtime_provenance_root", runtime_provenance_root),
            ("external_runtime_root", external_runtime_root),
            ("external_browser_root", external_browser_root),
        )
        self._presenter_session_timeout_ms = presenter_session_timeout_ms
        self._presenter = presenter
        self._presenter_operational = True
        self._clock = clock
        self._readiness = _readiness_from_secrets(
            self._display_secret,
            self._operator_secrets,
            self._ipc_auth_secret,
            self._submission_auth_secret,
            self._repository_gate,
            self._browser_runtime,
            self._presenter_session_timeout_ms,
            content_id("c4_stage1_review_service_epoch", {"epoch": service_epoch}),
            state_directory_identity_sha256,
            state_database_identity_sha256,
            boundary_roots_identity_sha256,
        )
        self._initialize_database()

    @property
    def readiness(self) -> C4Stage1ReviewServiceReadiness:
        self._assert_live_repository_gate()
        self._assert_live_secret_state()
        if not self._presenter_boundary_matches_startup():
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter boundary roots changed after service startup"
            )
        try:
            if self._presenter.verify_runtime_pin(self._browser_runtime) is not True:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 browser runtime changed after service startup"
                )
        except C4Stage1ReviewServiceError:
            raise
        except Exception as exc:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 browser runtime re-verification failed"
            ) from exc
        return C4Stage1ReviewServiceReadiness.model_validate(
            self._readiness.model_dump(mode="python", round_trip=True)
        )

    @property
    def presenter_session_timeout_seconds(self) -> float:
        return self._presenter_session_timeout_ms / 1000.0

    def _presenter_boundary_matches_startup(self) -> bool:
        try:
            return all(
                Path(getattr(self._presenter, name)).resolve(strict=True) == expected
                for name, expected in self._presenter_boundary_paths
            )
        except Exception:
            return False

    def _assert_live_repository_gate(self) -> None:
        try:
            current = C4Stage1ReviewRepositoryGateBinding.create(
                _capture_service_repository_gate(self._repository_root)
            )
        except Exception as exc:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 live repository gate failed"
            ) from exc
        if current != self._repository_gate:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 repository gate changed after service startup"
            )

    def _assert_live_secret_state(self) -> None:
        if self._owner_lock_fd is None:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state owner lock is not held"
            )
        current_owner_lock = _ordinary_file_metadata(
            self._owner_lock_path, expected_size=1
        )
        if not os.path.samestat(
            self._owner_lock_identity, current_owner_lock
        ) or not os.path.samestat(os.fstat(self._owner_lock_fd), current_owner_lock):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state owner lock changed after initialization"
            )
        _assert_safe_existing_ancestry(self._state_root)
        current_root = os.lstat(self._state_root)
        if (
            _is_link_or_reparse(current_root)
            or not stat.S_ISDIR(current_root.st_mode)
            or not os.path.samestat(self._state_root_identity, current_root)
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review state directory changed after initialization"
            )
        current_identities = tuple(
            _ordinary_file_metadata(path) for path in self._secret_paths
        )
        if any(
            not os.path.samestat(expected, current)
            for expected, current in zip(
                self._secret_identities, current_identities, strict=True
            )
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review secret file changed after initialization"
            )
        values = tuple(_stable_read_secret(path) for path in self._secret_paths)
        expected = (
            self._display_secret,
            *self._operator_secrets,
            self._ipc_auth_secret,
            self._submission_auth_secret,
        )
        if any(
            not hmac.compare_digest(left, right)
            for left, right in zip(values, expected, strict=True)
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review secret state changed after initialization"
            )

    def _assert_signing_cohort_open(self) -> None:
        if self._signing_cohort_latch is not None:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 two-review signing cohort is already complete"
            )

    def close(self) -> None:
        descriptor = self._owner_lock_fd
        if descriptor is not None:
            self._owner_lock_fd = None
            _release_owner_lock(descriptor)

    def __del__(self) -> None:  # pragma: no cover - best-effort process teardown
        descriptor = getattr(self, "_owner_lock_fd", None)
        if descriptor is not None:
            try:
                self._owner_lock_fd = None
                _release_owner_lock(descriptor)
            except Exception:
                pass

    def _assert_live_database_file(self) -> None:
        _assert_safe_existing_ancestry(self._database_path.parent)
        current = _ordinary_file_metadata(self._database_path)
        if not os.path.samestat(self._database_identity, current):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review ledger changed after initialization"
            )

    def _connect(self) -> sqlite3.Connection:
        self._assert_live_database_file()
        connection = sqlite3.connect(
            self._database_path,
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        try:
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA foreign_keys=ON")
            journal_mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            connection.execute("PRAGMA synchronous=FULL")
            if str(journal_mode).casefold() != "wal":
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review ledger did not enter WAL mode"
                )
        except Exception:
            connection.close()
            raise
        for suffix in ("-wal", "-shm"):
            candidate = Path(f"{self._database_path}{suffix}")
            if candidate.exists():
                _ordinary_file_metadata(candidate)
        return connection

    def _stateful_operation_request(
        self,
        *,
        operation: str,
        body_length: int,
        body_sha256: str,
    ) -> _C4Stage1StatefulOperationRequest:
        if operation not in _STATEFUL_OPERATIONS:
            raise C4Stage1ReviewServiceError("C4 Stage 1 IPC operation is not stateful")
        body = {
            "service_epoch_id": self._readiness.service_epoch_id,
            "ipc_schema": C4_STAGE1_REVIEW_IPC_SCHEMA,
            "operation": operation,
            "body_length": body_length,
            "body_sha256": body_sha256,
        }
        return _C4Stage1StatefulOperationRequest(
            operation_request_id=_sha256(
                _STATEFUL_OPERATION_REQUEST_DOMAIN + canonical_json_bytes(body)
            ),
            **body,
        )

    def _stateful_request_from_payload(
        self,
        operation: str,
        payload: Mapping[str, object],
    ) -> _C4Stage1StatefulOperationRequest:
        body = canonical_json_bytes(dict(payload))
        return self._stateful_operation_request(
            operation=operation,
            body_length=len(body),
            body_sha256=_sha256(body),
        )

    def _stateful_result_auth_hmac(
        self,
        request: _C4Stage1StatefulOperationRequest,
        *,
        status: Literal["in_progress", "completed"],
        result_json: bytes | None,
        result_sha256: str | None,
        result_size_bytes: int | None,
        effect_kind: str | None,
        effect_id: str | None,
        effect_sha256: str | None,
        completed_at: str | None,
    ) -> str:
        payload = {
            **request.auth_payload(),
            "status": status,
            "result_base64": (
                base64.b64encode(result_json).decode("ascii")
                if result_json is not None
                else None
            ),
            "result_sha256": result_sha256,
            "result_size_bytes": result_size_bytes,
            "effect_kind": effect_kind,
            "effect_id": effect_id,
            "effect_sha256": effect_sha256,
            "completed_at": completed_at,
        }
        return hmac.digest(
            self._submission_auth_secret,
            _STATEFUL_OPERATION_RESULT_AUTH_DOMAIN + canonical_json_bytes(payload),
            "sha256",
        ).hex()

    @staticmethod
    def _stateful_result_columns() -> str:
        return (
            "operation_request_id, service_epoch_id, ipc_schema, operation, "
            "body_length, body_sha256, status, result_json, result_sha256, "
            "result_size_bytes, effect_kind, effect_id, effect_sha256, "
            "completed_at, row_auth_hmac_sha256"
        )

    def _validate_stateful_result_row(
        self,
        row: tuple[object, ...],
    ) -> tuple[_C4Stage1StatefulOperationRequest, object | None]:
        if len(row) != 15:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 stateful operation result row is invalid"
            )
        try:
            request = _C4Stage1StatefulOperationRequest(
                operation_request_id=str(row[0]),
                service_epoch_id=str(row[1]),
                ipc_schema=str(row[2]),
                operation=str(row[3]),
                body_length=int(row[4]),
                body_sha256=str(row[5]),
            )
        except (TypeError, ValueError):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 stateful operation request row is invalid"
            ) from None
        expected = self._stateful_operation_request(
            operation=request.operation,
            body_length=request.body_length,
            body_sha256=request.body_sha256,
        )
        status = row[6]
        result_json = row[7]
        result_sha256 = row[8]
        result_size_bytes = row[9]
        effect_kind = row[10]
        effect_id = row[11]
        effect_sha256 = row[12]
        completed_at = row[13]
        row_auth_hmac_sha256 = row[14]
        if (
            request != expected
            or request.service_epoch_id != self._readiness.service_epoch_id
            or request.ipc_schema != C4_STAGE1_REVIEW_IPC_SCHEMA
            or request.operation not in _STATEFUL_OPERATIONS
            or not 0
            <= request.body_length
            <= _c4_stage1_review_ipc_body_limit(request.operation)
            or not _is_lower_sha256(request.body_sha256)
            or status not in {"in_progress", "completed"}
            or not isinstance(row_auth_hmac_sha256, str)
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 stateful operation request binding is invalid"
            )
        canonical_result: object | None = None
        if status == "in_progress":
            if any(
                value is not None
                for value in (
                    result_json,
                    result_sha256,
                    result_size_bytes,
                    effect_kind,
                    effect_id,
                    effect_sha256,
                    completed_at,
                )
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 in-progress operation contains a result"
                )
        else:
            if (
                type(result_json) is not bytes
                or not isinstance(result_sha256, str)
                or type(result_size_bytes) is not int
                or len(result_json) != result_size_bytes
                or _sha256(result_json) != result_sha256
                or not isinstance(effect_kind, str)
                or not effect_kind
                or not isinstance(effect_id, str)
                or not effect_id
                or not _is_lower_sha256(effect_sha256)
                or not isinstance(completed_at, str)
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 completed operation result is invalid"
                )
            try:
                canonical_result = _decode_json(result_json)
            except Exception:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 operation result is not canonical JSON"
                ) from None
            if canonical_json_bytes(canonical_result) != result_json:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 operation result is not canonical JSON"
                )
            try:
                completed = datetime.fromisoformat(completed_at)
            except ValueError:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 operation completion timestamp is invalid"
                ) from None
            if (
                completed.tzinfo is None
                or completed.utcoffset() is None
                or completed.astimezone(timezone.utc) != completed
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 operation completion timestamp is invalid"
                )
        expected_hmac = self._stateful_result_auth_hmac(
            request,
            status=status,  # type: ignore[arg-type]
            result_json=result_json if type(result_json) is bytes else None,
            result_sha256=(result_sha256 if isinstance(result_sha256, str) else None),
            result_size_bytes=(
                result_size_bytes if type(result_size_bytes) is int else None
            ),
            effect_kind=effect_kind if isinstance(effect_kind, str) else None,
            effect_id=effect_id if isinstance(effect_id, str) else None,
            effect_sha256=(effect_sha256 if isinstance(effect_sha256, str) else None),
            completed_at=completed_at if isinstance(completed_at, str) else None,
        )
        if not hmac.compare_digest(expected_hmac, row_auth_hmac_sha256):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operation result authentication failed"
            )
        return request, canonical_result

    def _reserve_stateful_display(
        self,
        request: _C4Stage1StatefulOperationRequest,
    ) -> None:
        if request.operation != "display":
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 only display may reserve an in-progress result"
            )
        row_hmac = self._stateful_result_auth_hmac(
            request,
            status="in_progress",
            result_json=None,
            result_sha256=None,
            result_size_bytes=None,
            effect_kind=None,
            effect_id=None,
            effect_sha256=None,
            completed_at=None,
        )
        connection = self._connect()
        with self._active_stateful_display_lock:
            try:
                if self._active_stateful_display_request_id is not None:
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 display reservation is already active"
                    )
                connection.execute("BEGIN IMMEDIATE")
                total_count = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {_STATEFUL_OPERATION_RESULT_TABLE}"
                    ).fetchone()[0]
                )
                operation_count = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {_STATEFUL_OPERATION_RESULT_TABLE} "
                        "WHERE operation = ?",
                        (request.operation,),
                    ).fetchone()[0]
                )
                if (
                    total_count >= _STATEFUL_OPERATION_MAX_COMPLETED_ROWS
                    or operation_count
                    >= _STATEFUL_OPERATION_CARDINALITY[request.operation]
                ):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 stateful operation cardinality is exhausted"
                    )
                connection.execute(
                    f"""
                    INSERT INTO {_STATEFUL_OPERATION_RESULT_TABLE}
                        (operation_request_id, service_epoch_id, ipc_schema,
                         operation, body_length, body_sha256, status,
                         row_auth_hmac_sha256)
                    VALUES (?, ?, ?, ?, ?, ?, 'in_progress', ?)
                    """,
                    (
                        request.operation_request_id,
                        request.service_epoch_id,
                        request.ipc_schema,
                        request.operation,
                        request.body_length,
                        request.body_sha256,
                        row_hmac,
                    ),
                )
                connection.execute("COMMIT")
                self._active_stateful_display_request_id = (
                    request.operation_request_id
                )
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            finally:
                connection.close()

    def _clear_active_stateful_display(
        self,
        request: _C4Stage1StatefulOperationRequest,
    ) -> None:
        with self._active_stateful_display_lock:
            if (
                self._active_stateful_display_request_id
                == request.operation_request_id
            ):
                self._active_stateful_display_request_id = None

    def _complete_stateful_result(
        self,
        connection: sqlite3.Connection,
        request: _C4Stage1StatefulOperationRequest | None,
        result: object,
        *,
        effect_kind: str,
        effect_id: str,
        effect_sha256: str,
        completed_at: datetime,
        require_in_progress: bool = False,
    ) -> None:
        if request is None:
            return
        result_json = canonical_json_bytes(result)
        result_sha256 = _sha256(result_json)
        completed_at_text = completed_at.isoformat()
        row_hmac = self._stateful_result_auth_hmac(
            request,
            status="completed",
            result_json=result_json,
            result_sha256=result_sha256,
            result_size_bytes=len(result_json),
            effect_kind=effect_kind,
            effect_id=effect_id,
            effect_sha256=effect_sha256,
            completed_at=completed_at_text,
        )
        if require_in_progress:
            updated = connection.execute(
                f"""
                UPDATE {_STATEFUL_OPERATION_RESULT_TABLE}
                SET status = 'completed', result_json = ?, result_sha256 = ?,
                    result_size_bytes = ?, effect_kind = ?, effect_id = ?,
                    effect_sha256 = ?, completed_at = ?,
                    row_auth_hmac_sha256 = ?
                WHERE operation_request_id = ?
                  AND service_epoch_id = ? AND ipc_schema = ?
                  AND operation = ? AND body_length = ? AND body_sha256 = ?
                  AND status = 'in_progress'
                """,
                (
                    result_json,
                    result_sha256,
                    len(result_json),
                    effect_kind,
                    effect_id,
                    effect_sha256,
                    completed_at_text,
                    row_hmac,
                    request.operation_request_id,
                    request.service_epoch_id,
                    request.ipc_schema,
                    request.operation,
                    request.body_length,
                    request.body_sha256,
                ),
            )
            if updated.rowcount != 1:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 display reservation changed before completion"
                )
            return
        total_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_STATEFUL_OPERATION_RESULT_TABLE}"
            ).fetchone()[0]
        )
        operation_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_STATEFUL_OPERATION_RESULT_TABLE} "
                "WHERE operation = ?",
                (request.operation,),
            ).fetchone()[0]
        )
        if (
            total_count >= _STATEFUL_OPERATION_MAX_COMPLETED_ROWS
            or operation_count >= _STATEFUL_OPERATION_CARDINALITY[request.operation]
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 stateful operation cardinality is exhausted"
            )
        connection.execute(
            f"""
            INSERT INTO {_STATEFUL_OPERATION_RESULT_TABLE}
                (operation_request_id, service_epoch_id, ipc_schema,
                 operation, body_length, body_sha256, status, result_json,
                 result_sha256, result_size_bytes, effect_kind, effect_id,
                 effect_sha256, completed_at, row_auth_hmac_sha256)
            VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.operation_request_id,
                request.service_epoch_id,
                request.ipc_schema,
                request.operation,
                request.body_length,
                request.body_sha256,
                result_json,
                result_sha256,
                len(result_json),
                effect_kind,
                effect_id,
                effect_sha256,
                completed_at_text,
                row_hmac,
            ),
        )

    def _stateful_result_effect_is_valid(
        self,
        operation: str,
        result: object,
        *,
        effect_kind: object,
        effect_id: object,
        effect_sha256: object,
    ) -> bool:
        try:
            if operation == "display":
                result_map = _mapping(result, label="display journal result")
                if set(result_map) != {"acknowledgement", "attestation"}:
                    return False
                acknowledgement = C4Stage1DisplayPortAcknowledgement.model_validate_json(
                    canonical_json_bytes(result_map["acknowledgement"])
                )
                value = C4Stage1DisplayAttestation.model_validate_json(
                    canonical_json_bytes(result_map["attestation"])
                )
                if (
                    acknowledgement.context_id != value.context_id
                    or acknowledgement.context_sha256 != value.context_sha256
                    or acknowledgement.acknowledgement_id
                    != value.acknowledgement_id
                    or acknowledgement.acknowledgement_sha256
                    != value.acknowledgement_sha256
                ):
                    return False
                expected = (
                    "display-attestation",
                    value.display_attestation_id,
                    value.display_attestation_sha256,
                )
            elif operation == "take_presentation_submission":
                value = C4Stage1AuthenticatedPresenterSubmission.model_validate_json(
                    canonical_json_bytes(result)
                )
                if not hmac.compare_digest(
                    value.service_auth_hmac_sha256,
                    hmac.digest(
                        self._submission_auth_secret,
                        _submission_receipt_auth_message(value),
                        "sha256",
                    ).hex(),
                ):
                    return False
                expected = (
                    "presenter-submission",
                    value.submission_receipt_id,
                    value.submission_receipt_sha256,
                )
            elif operation == "issue_operator_signing_lease":
                value = C4Stage1OperatorSigningLease.model_validate_json(
                    canonical_json_bytes(result)
                )
                if not hmac.compare_digest(
                    value.service_auth_hmac_sha256,
                    hmac.digest(
                        self._submission_auth_secret,
                        _operator_signing_lease_auth_message(value),
                        "sha256",
                    ).hex(),
                ):
                    return False
                expected = (
                    "operator-signing-lease",
                    value.operator_signing_lease_id,
                    value.operator_signing_lease_sha256,
                )
            elif operation == "consume_display_attestation":
                value = C4Stage1ConsumedDisplayAttestation.model_validate_json(
                    canonical_json_bytes(result)
                )
                expected = (
                    "consumed-display-attestation",
                    value.consumed_display_attestation_id,
                    value.consumed_display_attestation_sha256,
                )
            elif operation == "consume_display_receipt":
                value = C4Stage1ConsumedDisplayReceipt.model_validate_json(
                    canonical_json_bytes(result)
                )
                expected = (
                    "consumed-display-receipt",
                    value.consumed_display_receipt_id,
                    value.consumed_display_receipt_sha256,
                )
            elif operation == "consume_operator_policy":
                value = C4Stage1ConsumedOperatorPolicyReceipt.model_validate_json(
                    canonical_json_bytes(result)
                )
                expected = (
                    "consumed-operator-policy",
                    value.consumed_operator_receipt_id,
                    value.consumed_operator_receipt_sha256,
                )
            elif operation == "sign_operator_claim_cohort":
                if type(result) is not list or len(result) != 2:
                    return False
                attestations = tuple(
                    C4Stage1HumanReviewOperatorAttestation.model_validate_json(
                        canonical_json_bytes(item)
                    )
                    for item in result
                )
                cohort = self._signing_cohort_latch
                if cohort is None or {
                    (item.attestation_id, item.attestation_sha256)
                    for item in attestations
                } != {
                    (member.attestation_id, member.attestation_sha256)
                    for member in cohort.members
                }:
                    return False
                expected = (
                    "operator-signing-cohort",
                    cohort.operator_signing_cohort_id,
                    cohort.operator_signing_cohort_sha256,
                )
            else:
                return False
        except Exception:
            return False
        return expected == (effect_kind, effect_id, effect_sha256)

    @staticmethod
    def _stateful_expected_effects_for_cohort(
        cohort: C4Stage1CompletedSigningCohort,
    ) -> dict[str, set[tuple[str, str, str]]]:
        return {
            "display": {
                (
                    "display-attestation",
                    member.display_attestation_id,
                    member.display_attestation_sha256,
                )
                for member in cohort.members
            },
            "take_presentation_submission": {
                (
                    "presenter-submission",
                    member.submission_receipt_id,
                    member.submission_receipt_sha256,
                )
                for member in cohort.members
            },
            "consume_display_attestation": {
                (
                    "consumed-display-attestation",
                    member.consumed_display_attestation_id,
                    member.consumed_display_attestation_sha256,
                )
                for member in cohort.members
            },
            "consume_display_receipt": {
                (
                    "consumed-display-receipt",
                    member.consumed_display_receipt_id,
                    member.consumed_display_receipt_sha256,
                )
                for member in cohort.members
            },
            "issue_operator_signing_lease": {
                (
                    "operator-signing-lease",
                    member.operator_signing_lease_id,
                    member.operator_signing_lease_sha256,
                )
                for member in cohort.members
            },
            "sign_operator_claim_cohort": {
                (
                    "operator-signing-cohort",
                    cohort.operator_signing_cohort_id,
                    cohort.operator_signing_cohort_sha256,
                )
            },
            "consume_operator_policy": {
                (
                    "consumed-operator-policy",
                    member.consumed_operator_receipt_id,
                    member.consumed_operator_receipt_sha256,
                )
                for member in cohort.members
            },
        }

    def _completed_signing_cohort_row_is_live(
        self,
        connection: sqlite3.Connection,
        cohort: C4Stage1CompletedSigningCohort,
    ) -> bool:
        rows = connection.execute(
            f"SELECT operator_signing_cohort_id, "
            f"operator_signing_cohort_sha256, cohort_json, completed_at "
            f"FROM {_COMPLETED_SIGNING_COHORT_TABLE}"
        ).fetchall()
        return rows == [
            (
                cohort.operator_signing_cohort_id,
                cohort.operator_signing_cohort_sha256,
                cohort.canonical_json_bytes(),
                cohort.completed_at.isoformat(),
            )
        ] and self._cohort_matches_authority_rows(connection, cohort)

    @staticmethod
    def _stateful_ledger_receipt_is_live(
        connection: sqlite3.Connection,
        *,
        table: str,
        ledger_key: str,
        binding_sha256: str | None,
        receipt: BaseModel,
        receipt_id: str,
        receipt_sha256: str,
        transaction_id: str,
        created_at: object,
    ) -> bool:
        if table not in _LEDGER_TABLES or not isinstance(created_at, str):
            return False
        row = connection.execute(
            f"SELECT binding_sha256, receipt_id, receipt_sha256, "
            f"transaction_id, receipt_json, created_at FROM {table} "
            "WHERE ledger_key = ?",
            (ledger_key,),
        ).fetchone()
        if row is None or not _is_lower_sha256(row[0]):
            return False
        return (
            (binding_sha256 is None or row[0] == binding_sha256)
            and row[1:]
            == (
                receipt_id,
                receipt_sha256,
                transaction_id,
                receipt.canonical_json_bytes(),
                created_at,
            )
        )

    @staticmethod
    def _stateful_receipt_binding_from_payload(
        operation: str,
        payload: Mapping[str, object],
        result: object,
    ) -> str | None:
        try:
            if operation == "consume_display_attestation":
                display_policy = _parse_model(
                    payload, "display_policy", C4Stage1DisplayAttesterPolicy
                )
                context = _parse_model(payload, "context", C4Stage1DisplayContext)
                acknowledgement = _parse_model(
                    payload, "acknowledgement", C4Stage1DisplayPortAcknowledgement
                )
                attestation = _parse_model(
                    payload, "attestation", C4Stage1DisplayAttestation
                )
                receipt = C4Stage1ConsumedDisplayAttestation.model_validate_json(
                    canonical_json_bytes(result)
                )
                expected = record_c4_stage1_consumed_display_attestation(
                    display_policy,
                    context,
                    acknowledgement,
                    attestation,
                    external_transaction_id=receipt.external_transaction_id,
                    external_transaction_timestamp=(
                        receipt.external_transaction_timestamp
                    ),
                )
                if expected != receipt:
                    return None
                return _binding_sha256(
                    "c4-stage1-display-attestation-ledger-binding-v1",
                    display_policy,
                    context,
                    acknowledgement,
                    attestation,
                )
            if operation == "consume_display_receipt":
                display_receipt = _parse_model(
                    payload, "display_receipt", C4Stage1DisplayExecutionReceipt
                )
                receipt = C4Stage1ConsumedDisplayReceipt.model_validate_json(
                    canonical_json_bytes(result)
                )
                expected = record_c4_stage1_consumed_display_receipt(
                    display_receipt,
                    external_transaction_id=receipt.external_transaction_id,
                    external_transaction_timestamp=(
                        receipt.external_transaction_timestamp
                    ),
                )
                if expected != receipt:
                    return None
                return _binding_sha256(
                    "c4-stage1-display-receipt-ledger-binding-v1",
                    display_receipt,
                )
            if operation == "consume_operator_policy":
                operator_policy = _parse_model(
                    payload, "operator_policy", C4HumanReviewOperatorPolicy
                )
                attestation = _parse_model(
                    payload, "attestation", C4Stage1HumanReviewOperatorAttestation
                )
                receipt = C4Stage1ConsumedOperatorPolicyReceipt.model_validate_json(
                    canonical_json_bytes(result)
                )
                expected = record_c4_stage1_consumed_operator_policy_receipt(
                    operator_policy,
                    attestation,
                    external_transaction_id=receipt.external_transaction_id,
                    external_transaction_timestamp=(
                        receipt.external_transaction_timestamp
                    ),
                )
                if expected != receipt:
                    return None
                return _binding_sha256(
                    "c4-stage1-operator-policy-ledger-binding-v1",
                    operator_policy,
                    attestation,
                )
        except Exception:
            return None
        return None

    def _stateful_result_matches_payload(
        self,
        operation: str,
        result: object,
        payload: Mapping[str, object],
    ) -> bool:
        try:
            if operation == "display":
                result_map = _mapping(result, label="display journal result")
                acknowledgement = (
                    C4Stage1DisplayPortAcknowledgement.model_validate_json(
                        canonical_json_bytes(result_map["acknowledgement"])
                    )
                )
                attestation = C4Stage1DisplayAttestation.model_validate_json(
                    canonical_json_bytes(result_map["attestation"])
                )
                context = _parse_model(payload, "context", C4Stage1DisplayContext)
                display_policy = _parse_model(
                    payload, "display_policy", C4Stage1DisplayAttesterPolicy
                )
                source = payload["source_png_base64"]
                if not isinstance(source, str):
                    return False
                expected_acknowledgement = (
                    build_c4_stage1_display_port_acknowledgement(
                        context,
                        source_png_bytes=base64.b64decode(source, validate=True),
                        outputs=_parse_visible_outputs(payload["outputs"]),
                    )
                )
                expected_tag = hmac.digest(
                    self._display_secret,
                    c4_stage1_display_attestation_message(
                        display_policy,
                        context,
                        expected_acknowledgement,
                    ),
                    "sha256",
                ).hex()
                expected_attestation = build_c4_stage1_display_attestation(
                    display_policy,
                    context,
                    expected_acknowledgement,
                    external_hmac_sha256=expected_tag,
                )
                return (
                    acknowledgement == expected_acknowledgement
                    and attestation == expected_attestation
                )
            if operation == "take_presentation_submission":
                receipt = C4Stage1AuthenticatedPresenterSubmission.model_validate_json(
                    canonical_json_bytes(result)
                )
                return set(payload) == {"context_id"} and (
                    payload["context_id"] == receipt.context_id
                )
            if operation == "issue_operator_signing_lease":
                lease = C4Stage1OperatorSigningLease.model_validate_json(
                    canonical_json_bytes(result)
                )
                operator_policy = _parse_model(
                    payload, "operator_policy", C4HumanReviewOperatorPolicy
                )
                submission = _parse_model(
                    payload,
                    "submission_receipt",
                    C4Stage1AuthenticatedPresenterSubmission,
                )
                display_receipt = _parse_model(
                    payload, "display_receipt", C4Stage1DisplayExecutionReceipt
                )
                consumed_display_receipt = _parse_model(
                    payload,
                    "consumed_display_receipt",
                    C4Stage1ConsumedDisplayReceipt,
                )
                return (
                    lease.operator_policy_id == operator_policy.policy_id
                    and lease.operator_policy_sha256
                    == operator_policy.operator_policy_sha256
                    and lease.submission_receipt_id
                    == submission.submission_receipt_id
                    and lease.submission_receipt_sha256
                    == submission.submission_receipt_sha256
                    and lease.context_id == submission.context_id
                    and lease.context_sha256 == submission.context_sha256
                    and lease.display_receipt_id == display_receipt.display_receipt_id
                    and lease.display_receipt_sha256
                    == display_receipt.display_receipt_sha256
                    and lease.consumed_display_receipt_id
                    == consumed_display_receipt.consumed_display_receipt_id
                    and lease.consumed_display_receipt_sha256
                    == consumed_display_receipt.consumed_display_receipt_sha256
                    and lease.review_timestamp
                    == max(
                        submission.submitted_at,
                        display_receipt.display_completed_at.astimezone(timezone.utc),
                    )
                )
            if operation == "sign_operator_claim_cohort":
                raw_reviews = payload.get("reviews")
                if type(raw_reviews) is not list or len(raw_reviews) != 2:
                    return False
                reviews = tuple(
                    C4Stage1OperatorSigningRequest.model_validate_json(
                        canonical_json_bytes(value)
                    )
                    for value in raw_reviews
                )
                if type(result) is not list or len(result) != 2:
                    return False
                attestations = tuple(
                    C4Stage1HumanReviewOperatorAttestation.model_validate_json(
                        canonical_json_bytes(value)
                    )
                    for value in result
                )
                return tuple(item.claim for item in attestations) == tuple(
                    item.claim for item in reviews
                )
            if operation in {
                "consume_display_attestation",
                "consume_display_receipt",
                "consume_operator_policy",
            }:
                return (
                    self._stateful_receipt_binding_from_payload(
                        operation,
                        payload,
                        result,
                    )
                    is not None
                )
        except Exception:
            return False
        return True

    def _stateful_result_effect_is_live(
        self,
        connection: sqlite3.Connection,
        request: _C4Stage1StatefulOperationRequest,
        result: object,
        *,
        effect_kind: object,
        effect_id: object,
        effect_sha256: object,
        completed_at: object,
        payload: Mapping[str, object] | None,
    ) -> bool:
        operation = request.operation
        effect = (effect_kind, effect_id, effect_sha256)
        if not self._stateful_result_effect_is_valid(
            operation,
            result,
            effect_kind=effect_kind,
            effect_id=effect_id,
            effect_sha256=effect_sha256,
        ) or (
            payload is not None
            and not self._stateful_result_matches_payload(operation, result, payload)
        ):
            return False

        cohort = self._signing_cohort_latch
        if cohort is not None:
            expected_effects = self._stateful_expected_effects_for_cohort(cohort)
            if (
                not self._completed_signing_cohort_row_is_live(connection, cohort)
                or effect not in expected_effects[operation]
                or (
                    operation == "sign_operator_claim_cohort"
                    and completed_at != cohort.completed_at.isoformat()
                )
            ):
                return False
            if operation == "consume_display_attestation":
                receipt = C4Stage1ConsumedDisplayAttestation.model_validate_json(
                    canonical_json_bytes(result)
                )
                member = next(
                    member
                    for member in cohort.members
                    if member.consumed_display_attestation_id
                    == receipt.consumed_display_attestation_id
                )
                binding = member.display_attestation_ledger_binding_sha256
                if payload is not None and (
                    self._stateful_receipt_binding_from_payload(
                        operation, payload, result
                    )
                    != binding
                ):
                    return False
                return self._stateful_ledger_receipt_is_live(
                    connection,
                    table="display_attestation_uses",
                    ledger_key=receipt.display_attestation_id,
                    binding_sha256=binding,
                    receipt=receipt,
                    receipt_id=receipt.consumed_display_attestation_id,
                    receipt_sha256=receipt.consumed_display_attestation_sha256,
                    transaction_id=receipt.external_transaction_id,
                    created_at=completed_at,
                )
            if operation == "consume_display_receipt":
                receipt = C4Stage1ConsumedDisplayReceipt.model_validate_json(
                    canonical_json_bytes(result)
                )
                member = next(
                    member
                    for member in cohort.members
                    if member.consumed_display_receipt_id
                    == receipt.consumed_display_receipt_id
                )
                binding = member.display_receipt_ledger_binding_sha256
                if payload is not None and (
                    self._stateful_receipt_binding_from_payload(
                        operation, payload, result
                    )
                    != binding
                ):
                    return False
                return self._stateful_ledger_receipt_is_live(
                    connection,
                    table="display_receipt_uses",
                    ledger_key=receipt.display_receipt_id,
                    binding_sha256=binding,
                    receipt=receipt,
                    receipt_id=receipt.consumed_display_receipt_id,
                    receipt_sha256=receipt.consumed_display_receipt_sha256,
                    transaction_id=receipt.external_transaction_id,
                    created_at=completed_at,
                )
            if operation == "consume_operator_policy":
                receipt = C4Stage1ConsumedOperatorPolicyReceipt.model_validate_json(
                    canonical_json_bytes(result)
                )
                member = next(
                    member
                    for member in cohort.members
                    if member.consumed_operator_receipt_id
                    == receipt.consumed_operator_receipt_id
                )
                binding = member.operator_policy_ledger_binding_sha256
                if payload is not None and (
                    self._stateful_receipt_binding_from_payload(
                        operation, payload, result
                    )
                    != binding
                ):
                    return False
                return self._stateful_ledger_receipt_is_live(
                    connection,
                    table="operator_policy_uses",
                    ledger_key=receipt.operator_policy_id,
                    binding_sha256=binding,
                    receipt=receipt,
                    receipt_id=receipt.consumed_operator_receipt_id,
                    receipt_sha256=receipt.consumed_operator_receipt_sha256,
                    transaction_id=receipt.external_transaction_id,
                    created_at=cohort.completed_at.isoformat(),
                )
            return True

        if connection.execute(
            f"SELECT COUNT(*) FROM {_COMPLETED_SIGNING_COHORT_TABLE}"
        ).fetchone() != (0,):
            return False
        if operation == "display":
            result_map = _mapping(result, label="display journal result")
            attestation = C4Stage1DisplayAttestation.model_validate_json(
                canonical_json_bytes(result_map["attestation"])
            )
            opaque_context_hmac = hmac.digest(
                self._submission_auth_secret,
                b"rei-c4-stage1-opaque-live-context-v1\x00"
                + attestation.context_id.encode("utf-8"),
                "sha256",
            ).hex()
            return connection.execute(
                f"SELECT created_at FROM {_PRESENTATION_CONTEXT_TABLE} "
                "WHERE opaque_context_hmac_sha256 = ?",
                (opaque_context_hmac,),
            ).fetchone() == (completed_at,)
        if operation == "take_presentation_submission":
            receipt = C4Stage1AuthenticatedPresenterSubmission.model_validate_json(
                canonical_json_bytes(result)
            )
            return connection.execute(
                f"SELECT COUNT(*) FROM {_PRESENTER_SUBMISSION_TABLE} "
                "WHERE submission_receipt_id = ?",
                (receipt.submission_receipt_id,),
            ).fetchone() == (0,)
        if operation == "issue_operator_signing_lease":
            lease = C4Stage1OperatorSigningLease.model_validate_json(
                canonical_json_bytes(result)
            )
            return connection.execute(
                f"SELECT COUNT(*) FROM {_OPERATOR_SIGNING_LEASE_TABLE} "
                "WHERE operator_signing_lease_id = ?",
                (lease.operator_signing_lease_id,),
            ).fetchone() == (0,)
        if operation == "consume_display_attestation":
            receipt = C4Stage1ConsumedDisplayAttestation.model_validate_json(
                canonical_json_bytes(result)
            )
            binding = (
                self._stateful_receipt_binding_from_payload(
                    operation, payload, result
                )
                if payload is not None
                else None
            )
            if payload is not None and binding is None:
                return False
            return self._stateful_ledger_receipt_is_live(
                connection,
                table="display_attestation_uses",
                ledger_key=receipt.display_attestation_id,
                binding_sha256=binding,
                receipt=receipt,
                receipt_id=receipt.consumed_display_attestation_id,
                receipt_sha256=receipt.consumed_display_attestation_sha256,
                transaction_id=receipt.external_transaction_id,
                created_at=completed_at,
            )
        if operation == "consume_display_receipt":
            receipt = C4Stage1ConsumedDisplayReceipt.model_validate_json(
                canonical_json_bytes(result)
            )
            binding = (
                self._stateful_receipt_binding_from_payload(
                    operation, payload, result
                )
                if payload is not None
                else None
            )
            if payload is not None and binding is None:
                return False
            return self._stateful_ledger_receipt_is_live(
                connection,
                table="display_receipt_uses",
                ledger_key=receipt.display_receipt_id,
                binding_sha256=binding,
                receipt=receipt,
                receipt_id=receipt.consumed_display_receipt_id,
                receipt_sha256=receipt.consumed_display_receipt_sha256,
                transaction_id=receipt.external_transaction_id,
                created_at=completed_at,
            )
        return False

    def _rehydrate_stateful_result(
        self,
        request: _C4Stage1StatefulOperationRequest,
        payload: Mapping[str, object],
        result: object,
    ) -> None:
        with self._cohort_lock:
            cohort_is_open = self._signing_cohort_latch is None
            if request.operation == "display":
                context = _parse_model(payload, "context", C4Stage1DisplayContext)
                result_map = _mapping(result, label="display journal result")
                acknowledgement = (
                    C4Stage1DisplayPortAcknowledgement.model_validate_json(
                        canonical_json_bytes(result_map["acknowledgement"])
                    )
                )
                if not cohort_is_open:
                    return
                with self._pending_lock:
                    retained = self._retained_contexts.get(context.context_id)
                    if retained is None:
                        self._retained_contexts[context.context_id] = (
                            context,
                            acknowledgement,
                        )
                    elif retained != (context, acknowledgement):
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 cached display differs from retained state"
                        )
            elif request.operation == "take_presentation_submission":
                receipt = C4Stage1AuthenticatedPresenterSubmission.model_validate_json(
                    canonical_json_bytes(result)
                )
                if not cohort_is_open:
                    return
                with self._pending_lock:
                    pending = self._pending_submission_receipts.get(receipt.context_id)
                    if pending is None:
                        self._pending_submission_receipts[receipt.context_id] = receipt
                    elif pending != receipt:
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 cached submission differs from pending state"
                        )
                discard = getattr(self._presenter, "discard_submission", None)
                if not callable(discard):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 presenter cannot discard a cached submission"
                    )
                try:
                    discard(
                        receipt.context_id,
                        expected_submission=receipt.canonical_submission_bytes,
                        expected_submitted_at=receipt.submitted_at,
                    )
                except Exception:
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 cached presenter submission changed"
                    ) from None
            elif request.operation == "issue_operator_signing_lease":
                lease = C4Stage1OperatorSigningLease.model_validate_json(
                    canonical_json_bytes(result)
                )
                if not cohort_is_open:
                    return
                with self._pending_lock:
                    pending = self._pending_operator_leases.get(
                        lease.submission_receipt_id
                    )
                    if pending is None:
                        self._pending_operator_leases[lease.submission_receipt_id] = (
                            lease
                        )
                    elif pending != lease:
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 cached lease differs from pending state"
                        )
            elif request.operation == "consume_operator_policy":
                receipt = C4Stage1ConsumedOperatorPolicyReceipt.model_validate_json(
                    canonical_json_bytes(result)
                )
                with self._pending_lock:
                    pending = self._pending_operator_policy_deliveries.get(
                        receipt.operator_policy_id
                    )
                    if pending is not None and pending != receipt:
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 cached operator delivery changed"
                        )
                    self._pending_operator_policy_deliveries.pop(
                        receipt.operator_policy_id, None
                    )

    def _lookup_stateful_result(
        self,
        request: _C4Stage1StatefulOperationRequest,
        payload: Mapping[str, object],
    ) -> object | None:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            row = connection.execute(
                f"SELECT {self._stateful_result_columns()} "
                f"FROM {_STATEFUL_OPERATION_RESULT_TABLE} "
                "WHERE operation_request_id = ?",
                (request.operation_request_id,),
            ).fetchone()
            if row is None:
                return None
            stored_request, result = self._validate_stateful_result_row(row)
            if stored_request != request:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 stateful operation input binding changed"
                )
            if row[6] == "in_progress":
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 stateful operation is terminally in progress"
                )
            if result is None or not self._stateful_result_effect_is_live(
                connection,
                request,
                result,
                effect_kind=row[10],
                effect_id=row[11],
                effect_sha256=row[12],
                completed_at=row[13],
                payload=payload,
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 stateful operation authority effect is not live"
                )
        finally:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            connection.close()
        self._rehydrate_stateful_result(request, payload, result)
        return result

    def _audit_stateful_operation_results(
        self,
        *,
        restart: bool,
    ) -> dict[str, object]:
        with self._active_stateful_display_lock:
            active_display_request_id = self._active_stateful_display_request_id
            connection = self._connect()
            try:
                connection.execute("BEGIN")
                rows = connection.execute(
                    f"SELECT {self._stateful_result_columns()} "
                    f"FROM {_STATEFUL_OPERATION_RESULT_TABLE} "
                    "ORDER BY operation_request_id"
                ).fetchall()
                if len(rows) > _STATEFUL_OPERATION_MAX_COMPLETED_ROWS:
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 stateful result journal exceeds its bound"
                    )
                counts = {operation: 0 for operation in _STATEFUL_OPERATIONS}
                effects: dict[str, set[tuple[object, object, object]]] = {
                    operation: set() for operation in _STATEFUL_OPERATIONS
                }
                in_progress_ids: set[str] = set()
                completed = 0
                for row in rows:
                    request, result = self._validate_stateful_result_row(row)
                    counts[request.operation] += 1
                    if (
                        counts[request.operation]
                        > _STATEFUL_OPERATION_CARDINALITY[request.operation]
                    ):
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 stateful result cardinality is invalid"
                        )
                    if row[6] == "in_progress":
                        in_progress_ids.add(request.operation_request_id)
                        if restart:
                            raise C4Stage1ReviewServiceError(
                                "C4 Stage 1 review state contains an incomplete "
                                "stateful cohort"
                            )
                        if request.operation != "display" or (
                            request.operation_request_id
                            != active_display_request_id
                        ):
                            raise C4Stage1ReviewServiceError(
                                "C4 Stage 1 stateful display reservation is orphaned"
                            )
                    else:
                        completed += 1
                        effects[request.operation].add((row[10], row[11], row[12]))
                        if result is None or not self._stateful_result_effect_is_live(
                            connection,
                            request,
                            result,
                            effect_kind=row[10],
                            effect_id=row[11],
                            effect_sha256=row[12],
                            completed_at=row[13],
                            payload=None,
                        ):
                            raise C4Stage1ReviewServiceError(
                                "C4 Stage 1 stateful result authority effect is not live"
                            )
                if (
                    active_display_request_id is None
                    and in_progress_ids
                    or active_display_request_id is not None
                    and in_progress_ids != {active_display_request_id}
                ):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 active display reservation is inconsistent"
                    )

                cohort = self._signing_cohort_latch
                if restart and cohort is None and rows:
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 review state contains an incomplete stateful cohort"
                    )
                if cohort is None:
                    authority_counts = self._authority_ledger_counts(connection)
                    expected_authority_counts = {
                        "display_attestation_uses": counts[
                            "consume_display_attestation"
                        ],
                        "display_receipt_uses": counts["consume_display_receipt"],
                        "operator_policy_uses": 0,
                        _PRESENTER_SUBMISSION_TABLE: 0,
                        _OPERATOR_SIGNING_LEASE_TABLE: 0,
                    }
                    context_count = int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {_PRESENTATION_CONTEXT_TABLE}"
                        ).fetchone()[0]
                    )
                    if (
                        authority_counts != expected_authority_counts
                        or context_count != len(effects["display"])
                    ):
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 open result journal differs from authority rows"
                        )
                else:
                    expected_base = {
                        "display": 2,
                        "take_presentation_submission": 2,
                        "consume_display_attestation": 2,
                        "consume_display_receipt": 2,
                        "issue_operator_signing_lease": 2,
                        "sign_operator_claim_cohort": 1,
                    }
                    if any(
                        counts[name] != value
                        for name, value in expected_base.items()
                    ) or (
                        counts["consume_operator_policy"] not in {0, 1, 2}
                        or in_progress_ids
                    ):
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 sealed result journal is incomplete"
                        )
                    expected_effects = self._stateful_expected_effects_for_cohort(
                        cohort
                    )
                    if any(
                        effects[operation] != expected_effects[operation]
                        for operation in expected_base
                    ):
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 sealed result effects differ from authority rows"
                        )
                    if not effects["consume_operator_policy"].issubset(
                        expected_effects["consume_operator_policy"]
                    ):
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 operator delivery result is orphaned"
                        )
                return {
                    "row_count": len(rows),
                    "completed_count": completed,
                    "in_progress_count": len(in_progress_ids),
                    "operation_counts": counts,
                    "sealed_sign_result_recoverable": bool(
                        cohort is not None
                        and counts["sign_operator_claim_cohort"] == 1
                    ),
                }
            finally:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                connection.close()

    def _initialize_database(self) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS service_metadata (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    ledger_schema TEXT NOT NULL,
                    readiness_json BLOB NOT NULL UNIQUE
                ) STRICT
                """
            )
            for table in _LEDGER_TABLES:
                connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        ledger_key TEXT NOT NULL PRIMARY KEY,
                        binding_sha256 TEXT NOT NULL UNIQUE
                            CHECK (length(binding_sha256) = 64),
                        receipt_id TEXT NOT NULL UNIQUE,
                        receipt_sha256 TEXT NOT NULL UNIQUE
                            CHECK (length(receipt_sha256) = 64),
                        transaction_id TEXT NOT NULL UNIQUE,
                        receipt_json BLOB NOT NULL UNIQUE,
                        created_at TEXT NOT NULL
                    ) STRICT
                    """
                )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_IPC_NONCE_TABLE} (
                    nonce TEXT NOT NULL PRIMARY KEY CHECK (length(nonce) = 64),
                    request_sha256 TEXT NOT NULL UNIQUE
                        CHECK (length(request_sha256) = 64),
                    issued_at TEXT NOT NULL,
                    consumed_at TEXT NOT NULL
                ) STRICT
                """
            )
            stateful_operations_sql = ", ".join(
                f"'{operation}'" for operation in sorted(_STATEFUL_OPERATIONS)
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_STATEFUL_OPERATION_RESULT_TABLE} (
                    operation_request_id TEXT NOT NULL PRIMARY KEY
                        CHECK (length(operation_request_id) = 64),
                    service_epoch_id TEXT NOT NULL,
                    ipc_schema TEXT NOT NULL,
                    operation TEXT NOT NULL
                        CHECK (operation IN ({stateful_operations_sql})),
                    body_length INTEGER NOT NULL CHECK (body_length >= 0),
                    body_sha256 TEXT NOT NULL CHECK (length(body_sha256) = 64),
                    status TEXT NOT NULL
                        CHECK (status IN ('in_progress', 'completed')),
                    result_json BLOB,
                    result_sha256 TEXT CHECK (
                        result_sha256 IS NULL OR length(result_sha256) = 64
                    ),
                    result_size_bytes INTEGER CHECK (
                        result_size_bytes IS NULL OR result_size_bytes >= 0
                    ),
                    effect_kind TEXT,
                    effect_id TEXT,
                    effect_sha256 TEXT CHECK (
                        effect_sha256 IS NULL OR length(effect_sha256) = 64
                    ),
                    completed_at TEXT,
                    row_auth_hmac_sha256 TEXT NOT NULL
                        CHECK (length(row_auth_hmac_sha256) = 64),
                    UNIQUE (effect_kind, effect_id),
                    CHECK (
                        (status = 'in_progress'
                         AND result_json IS NULL
                         AND result_sha256 IS NULL
                         AND result_size_bytes IS NULL
                         AND effect_kind IS NULL
                         AND effect_id IS NULL
                         AND effect_sha256 IS NULL
                         AND completed_at IS NULL)
                        OR
                        (status = 'completed'
                         AND result_json IS NOT NULL
                         AND result_sha256 IS NOT NULL
                         AND result_size_bytes IS NOT NULL
                         AND effect_kind IS NOT NULL
                         AND effect_id IS NOT NULL
                         AND effect_sha256 IS NOT NULL
                         AND completed_at IS NOT NULL)
                    )
                ) STRICT
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_PRESENTATION_CONTEXT_TABLE} (
                    opaque_context_hmac_sha256 TEXT NOT NULL PRIMARY KEY
                        CHECK (length(opaque_context_hmac_sha256) = 64),
                    created_at TEXT NOT NULL
                ) STRICT
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_PRESENTER_SUBMISSION_TABLE} (
                    submission_receipt_id TEXT NOT NULL PRIMARY KEY,
                    submission_receipt_sha256 TEXT NOT NULL UNIQUE
                        CHECK (length(submission_receipt_sha256) = 64),
                    context_id TEXT NOT NULL UNIQUE,
                    receipt_json BLOB NOT NULL UNIQUE,
                    consumed_at TEXT,
                    claim_id TEXT UNIQUE,
                    attestation_json BLOB UNIQUE
                ) STRICT
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_OPERATOR_SIGNING_LEASE_TABLE} (
                    operator_signing_lease_id TEXT NOT NULL PRIMARY KEY,
                    operator_signing_lease_sha256 TEXT NOT NULL UNIQUE
                        CHECK (length(operator_signing_lease_sha256) = 64),
                    submission_receipt_id TEXT NOT NULL UNIQUE,
                    operator_policy_id TEXT NOT NULL,
                    context_id TEXT NOT NULL,
                    lease_json BLOB NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT,
                    claim_id TEXT UNIQUE
                ) STRICT
                """
            )
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_COMPLETED_SIGNING_COHORT_TABLE} (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    operator_signing_cohort_id TEXT NOT NULL UNIQUE,
                    operator_signing_cohort_sha256 TEXT NOT NULL UNIQUE
                        CHECK (length(operator_signing_cohort_sha256) = 64),
                    cohort_json BLOB NOT NULL UNIQUE,
                    completed_at TEXT NOT NULL
                ) STRICT
                """
            )
            readiness_json = self._readiness.canonical_json_bytes()
            connection.execute(
                """
                INSERT OR IGNORE INTO service_metadata
                    (singleton, ledger_schema, readiness_json)
                VALUES (1, ?, ?)
                """,
                (C4_STAGE1_REVIEW_LEDGER_SCHEMA, readiness_json),
            )
            stored = connection.execute(
                "SELECT ledger_schema, readiness_json FROM service_metadata WHERE singleton = 1"
            ).fetchone()
            if stored != (C4_STAGE1_REVIEW_LEDGER_SCHEMA, readiness_json):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review ledger belongs to another key set"
                )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        self._assert_live_database_file()
        self._signing_cohort_latch = self._load_signing_cohort_state()
        self._audit_stateful_operation_results(restart=True)

    @staticmethod
    def _authority_ledger_counts(
        connection: sqlite3.Connection,
    ) -> dict[str, int]:
        counts = {
            table: int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            for table in _LEDGER_TABLES
        }
        counts[_PRESENTER_SUBMISSION_TABLE] = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_PRESENTER_SUBMISSION_TABLE}"
            ).fetchone()[0]
        )
        counts[_OPERATOR_SIGNING_LEASE_TABLE] = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_OPERATOR_SIGNING_LEASE_TABLE}"
            ).fetchone()[0]
        )
        return counts

    def _cohort_matches_authority_rows(
        self,
        connection: sqlite3.Connection,
        cohort: C4Stage1CompletedSigningCohort,
    ) -> bool:
        if any(
            value != 2
            for value in C4Stage1ReviewService._authority_ledger_counts(
                connection
            ).values()
        ) or connection.execute(
            f"SELECT COUNT(*) FROM {_PRESENTATION_CONTEXT_TABLE}"
        ).fetchone() != (0,):
            return False
        authority_body = cohort.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "operator_signing_cohort_id",
                "operator_signing_cohort_sha256",
                "authority_snapshot_hmac_sha256",
            },
        )
        if not hmac.compare_digest(
            cohort.authority_snapshot_hmac_sha256,
            hmac.digest(
                self._submission_auth_secret,
                _completed_signing_cohort_authority_message(authority_body),
                "sha256",
            ).hex(),
        ):
            return False

        def ledger_receipt_matches(
            *,
            table: str,
            ledger_key: str,
            model_type: type[BaseModel],
            receipt_id_field: str,
            receipt_sha256_field: str,
            expected_receipt_id: str,
            expected_receipt_sha256: str,
            expected_binding_sha256: str,
            expected_transaction_id: str,
            expected_fields: Mapping[str, object],
        ) -> BaseModel | None:
            row = connection.execute(
                f"SELECT binding_sha256, receipt_id, receipt_sha256, "
                f"transaction_id, receipt_json FROM {table} "
                "WHERE ledger_key = ?",
                (ledger_key,),
            ).fetchone()
            if row is None:
                return False
            try:
                receipt = model_type.model_validate_json(row[4])
            except Exception:
                return None
            if (
                row[:4]
                != (
                    expected_binding_sha256,
                    expected_receipt_id,
                    expected_receipt_sha256,
                    expected_transaction_id,
                )
                or getattr(receipt, receipt_id_field) != expected_receipt_id
                or getattr(receipt, receipt_sha256_field) != expected_receipt_sha256
                or getattr(receipt, "external_transaction_id")
                != expected_transaction_id
                or any(
                    getattr(receipt, field, None) != expected
                    for field, expected in expected_fields.items()
                )
                or receipt.canonical_json_bytes() != row[4]
            ):
                return None
            return receipt

        matched_operator_secret_indexes: set[int] = set()
        for member in cohort.members:
            if not ledger_receipt_matches(
                table="display_attestation_uses",
                ledger_key=member.display_attestation_id,
                model_type=C4Stage1ConsumedDisplayAttestation,
                receipt_id_field="consumed_display_attestation_id",
                receipt_sha256_field="consumed_display_attestation_sha256",
                expected_receipt_id=member.consumed_display_attestation_id,
                expected_receipt_sha256=(member.consumed_display_attestation_sha256),
                expected_binding_sha256=(
                    member.display_attestation_ledger_binding_sha256
                ),
                expected_transaction_id=(
                    member.display_attestation_ledger_transaction_id
                ),
                expected_fields={
                    "display_policy_id": cohort.display_policy_id,
                    "display_policy_sha256": cohort.display_policy_sha256,
                    "context_id": member.context_id,
                    "context_sha256": member.context_sha256,
                    "display_attestation_id": member.display_attestation_id,
                    "display_attestation_sha256": member.display_attestation_sha256,
                },
            ):
                return False
            if not ledger_receipt_matches(
                table="display_receipt_uses",
                ledger_key=member.display_receipt_id,
                model_type=C4Stage1ConsumedDisplayReceipt,
                receipt_id_field="consumed_display_receipt_id",
                receipt_sha256_field="consumed_display_receipt_sha256",
                expected_receipt_id=member.consumed_display_receipt_id,
                expected_receipt_sha256=member.consumed_display_receipt_sha256,
                expected_binding_sha256=member.display_receipt_ledger_binding_sha256,
                expected_transaction_id=(member.display_receipt_ledger_transaction_id),
                expected_fields={
                    "display_receipt_id": member.display_receipt_id,
                    "display_receipt_sha256": member.display_receipt_sha256,
                },
            ):
                return False
            operator_receipt = ledger_receipt_matches(
                table="operator_policy_uses",
                ledger_key=member.operator_policy_id,
                model_type=C4Stage1ConsumedOperatorPolicyReceipt,
                receipt_id_field="consumed_operator_receipt_id",
                receipt_sha256_field="consumed_operator_receipt_sha256",
                expected_receipt_id=member.consumed_operator_receipt_id,
                expected_receipt_sha256=member.consumed_operator_receipt_sha256,
                expected_binding_sha256=member.operator_policy_ledger_binding_sha256,
                expected_transaction_id=(member.operator_policy_ledger_transaction_id),
                expected_fields={
                    "operator_policy_id": member.operator_policy_id,
                    "operator_policy_sha256": member.operator_policy_sha256,
                    "one_time_ledger_key_policy_id": member.operator_policy_id,
                    "operator_signing_lease_id": member.operator_signing_lease_id,
                    "operator_signing_lease_sha256": (
                        member.operator_signing_lease_sha256
                    ),
                    "claim_id": member.claim_id,
                    "claim_sha256": member.claim_sha256,
                    "attestation_id": member.attestation_id,
                    "attestation_sha256": member.attestation_sha256,
                    "display_receipt_id": member.display_receipt_id,
                    "display_receipt_sha256": member.display_receipt_sha256,
                },
            )
            if operator_receipt is None:
                return False
            submission = connection.execute(
                f"SELECT submission_receipt_sha256, context_id, receipt_json, "
                f"claim_id, attestation_json, consumed_at "
                f"FROM {_PRESENTER_SUBMISSION_TABLE} "
                "WHERE submission_receipt_id = ?",
                (member.submission_receipt_id,),
            ).fetchone()
            if submission is None:
                return False
            try:
                submission_receipt = (
                    C4Stage1AuthenticatedPresenterSubmission.model_validate_json(
                        submission[2]
                    )
                )
                attestation = (
                    C4Stage1HumanReviewOperatorAttestation.model_validate_json(
                        submission[4]
                    )
                )
            except Exception:
                return False
            claim = attestation.claim
            operator_secret_matches = tuple(
                index
                for index, secret in enumerate(self._operator_secrets)
                if hmac.compare_digest(
                    attestation.hmac_sha256,
                    hmac.digest(
                        secret,
                        c4_stage1_operator_attestation_message(claim),
                        "sha256",
                    ).hex(),
                )
            )
            if (
                submission[:2]
                != (
                    member.submission_receipt_sha256,
                    member.context_id,
                )
                or submission[3] != member.claim_id
                or submission[5] != cohort.completed_at.isoformat()
                or submission_receipt.submission_receipt_id
                != member.submission_receipt_id
                or submission_receipt.submission_receipt_sha256
                != member.submission_receipt_sha256
                or submission_receipt.context_id != member.context_id
                or submission_receipt.context_sha256 != member.context_sha256
                or submission_receipt.packet_id != claim.packet_id
                or submission_receipt.packet_sha256 != claim.packet_sha256
                or submission_receipt.canonical_json_bytes() != submission[2]
                or not hmac.compare_digest(
                    submission_receipt.service_auth_hmac_sha256,
                    hmac.digest(
                        self._submission_auth_secret,
                        _submission_receipt_auth_message(submission_receipt),
                        "sha256",
                    ).hex(),
                )
                or attestation.canonical_json_bytes() != submission[4]
                or attestation.attestation_id != member.attestation_id
                or attestation.attestation_sha256 != member.attestation_sha256
                or getattr(operator_receipt, "attestation_hmac_sha256", None)
                != attestation.hmac_sha256
                or claim.claim_id != member.claim_id
                or claim.claim_sha256 != member.claim_sha256
                or claim.operator_policy_id != member.operator_policy_id
                or claim.operator_policy_sha256 != member.operator_policy_sha256
                or claim.packet_id != member.packet_id
                or claim.packet_sha256 != member.packet_sha256
                or claim.presentation_manifest_id != member.presentation_manifest_id
                or claim.presentation_manifest_sha256
                != member.presentation_manifest_sha256
                or claim.review_schema_id != cohort.review_schema_id
                or any(
                    judgment.source_image_sha256 != cohort.source_image_sha256
                    for judgment in claim.output_judgments
                )
                or claim.screen_contract_id != cohort.screen_contract_id
                or claim.screen_contract_sha256 != cohort.screen_contract_sha256
                or claim.display_policy_id != cohort.display_policy_id
                or claim.display_policy_sha256 != cohort.display_policy_sha256
                or claim.display_policy_artifact_sha256
                != cohort.display_policy_artifact_sha256
                or claim.display_attestation_id != member.display_attestation_id
                or claim.display_attestation_sha256 != member.display_attestation_sha256
                or claim.consumed_display_attestation_id
                != member.consumed_display_attestation_id
                or claim.consumed_display_attestation_sha256
                != member.consumed_display_attestation_sha256
                or claim.display_receipt_id != member.display_receipt_id
                or claim.display_receipt_sha256 != member.display_receipt_sha256
                or claim.consumed_display_receipt_id
                != member.consumed_display_receipt_id
                or claim.consumed_display_receipt_sha256
                != member.consumed_display_receipt_sha256
                or claim.submission_receipt_id != member.submission_receipt_id
                or claim.submission_receipt_sha256 != member.submission_receipt_sha256
                or claim.operator_signing_lease_id != member.operator_signing_lease_id
                or claim.operator_signing_lease_sha256
                != member.operator_signing_lease_sha256
                or len(operator_secret_matches) != 1
                or self._readiness.operator_signing_key_commitment_sha256s[
                    operator_secret_matches[0]
                ]
                != member.operator_key_commitment_sha256
            ):
                return False
            matched_operator_secret_indexes.add(operator_secret_matches[0])
            lease = connection.execute(
                f"SELECT operator_signing_lease_sha256, submission_receipt_id, "
                f"operator_policy_id, context_id, lease_json, expires_at, "
                f"claim_id, consumed_at FROM {_OPERATOR_SIGNING_LEASE_TABLE} "
                "WHERE operator_signing_lease_id = ?",
                (member.operator_signing_lease_id,),
            ).fetchone()
            if lease is None:
                return False
            try:
                lease_model = C4Stage1OperatorSigningLease.model_validate_json(lease[4])
            except Exception:
                return False
            if (
                lease[:4]
                != (
                    member.operator_signing_lease_sha256,
                    member.submission_receipt_id,
                    member.operator_policy_id,
                    member.context_id,
                )
                or lease[5:]
                != (
                    lease_model.expires_at.isoformat(),
                    member.claim_id,
                    cohort.completed_at.isoformat(),
                )
                or (
                    lease_model.operator_signing_lease_id
                    != member.operator_signing_lease_id
                    or lease_model.operator_signing_lease_sha256
                    != member.operator_signing_lease_sha256
                    or lease_model.operator_policy_id != member.operator_policy_id
                    or lease_model.operator_policy_sha256
                    != member.operator_policy_sha256
                    or lease_model.submission_receipt_id != member.submission_receipt_id
                    or lease_model.submission_receipt_sha256
                    != member.submission_receipt_sha256
                    or lease_model.context_id != member.context_id
                    or lease_model.context_sha256 != member.context_sha256
                    or lease_model.display_receipt_id != member.display_receipt_id
                    or lease_model.display_receipt_sha256
                    != member.display_receipt_sha256
                    or lease_model.consumed_display_receipt_id
                    != member.consumed_display_receipt_id
                    or lease_model.consumed_display_receipt_sha256
                    != member.consumed_display_receipt_sha256
                    or lease_model.review_timestamp != claim.review_timestamp
                    or lease_model.canonical_json_bytes() != lease[4]
                    or not hmac.compare_digest(
                        lease_model.service_auth_hmac_sha256,
                        hmac.digest(
                            self._submission_auth_secret,
                            _operator_signing_lease_auth_message(lease_model),
                            "sha256",
                        ).hex(),
                    )
                )
            ):
                return False
        return matched_operator_secret_indexes == {0, 1} and {
            member.operator_key_commitment_sha256 for member in cohort.members
        } == set(self._readiness.operator_signing_key_commitment_sha256s)

    def _load_signing_cohort_state(
        self,
    ) -> C4Stage1CompletedSigningCohort | None:
        connection = self._connect()
        try:
            counts = self._authority_ledger_counts(connection)
            context_count = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_PRESENTATION_CONTEXT_TABLE}"
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"SELECT operator_signing_cohort_id, "
                f"operator_signing_cohort_sha256, cohort_json, completed_at "
                f"FROM {_COMPLETED_SIGNING_COHORT_TABLE}"
            ).fetchall()
            if (
                not rows
                and context_count == 0
                and all(value == 0 for value in counts.values())
            ):
                return None
            if len(rows) != 1:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review state contains a partial signing cohort"
                )
            try:
                cohort = C4Stage1CompletedSigningCohort.model_validate_json(rows[0][2])
            except Exception as exc:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 completed signing cohort is invalid"
                ) from exc
            if (
                rows[0][0] != cohort.operator_signing_cohort_id
                or rows[0][1] != cohort.operator_signing_cohort_sha256
                or rows[0][2] != cohort.canonical_json_bytes()
                or rows[0][3] != cohort.completed_at.isoformat()
                or not self._cohort_matches_authority_rows(connection, cohort)
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 completed signing cohort differs from authority ledgers"
                )
            return cohort
        finally:
            connection.close()

    def health(self) -> dict[str, object]:
        self._assert_live_repository_gate()
        self._assert_live_secret_state()
        presenter_boundary_matches = self._presenter_boundary_matches_startup()
        try:
            browser_runtime_matches = (
                presenter_boundary_matches
                and self._presenter.verify_runtime_pin(self._browser_runtime) is True
            )
        except Exception:
            browser_runtime_matches = False
        connection = self._connect()
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            journal = str(
                connection.execute("PRAGMA journal_mode").fetchone()[0]
            ).casefold()
            synchronous = int(connection.execute("PRAGMA synchronous").fetchone()[0])
            counts = self._authority_ledger_counts(connection)
            cohort = self._signing_cohort_latch
            cohort_row = connection.execute(
                f"SELECT operator_signing_cohort_id, "
                f"operator_signing_cohort_sha256, cohort_json, completed_at "
                f"FROM {_COMPLETED_SIGNING_COHORT_TABLE}"
            ).fetchone()
            cohort_rows_match = bool(
                cohort is not None
                and cohort_row
                == (
                    cohort.operator_signing_cohort_id,
                    cohort.operator_signing_cohort_sha256,
                    cohort.canonical_json_bytes(),
                    cohort.completed_at.isoformat(),
                )
                and self._cohort_matches_authority_rows(connection, cohort)
            )
        finally:
            connection.close()
        try:
            stateful_results = self._audit_stateful_operation_results(restart=False)
            stateful_results_valid = True
        except C4Stage1ReviewServiceError:
            stateful_results = {
                "row_count": -1,
                "completed_count": -1,
                "in_progress_count": -1,
                "operation_counts": {},
                "sealed_sign_result_recoverable": False,
            }
            stateful_results_valid = False
        cohort_complete = cohort_rows_match
        cohort_state_consistent = (
            cohort is None and cohort_row is None
        ) or cohort_rows_match
        return {
            "schema_version": C4_STAGE1_REVIEW_SERVICE_SCHEMA,
            "ready": (
                integrity == "ok"
                and journal == "wal"
                and synchronous == 2
                and browser_runtime_matches
                and cohort_state_consistent
                and stateful_results_valid
            ),
            "sqlite_integrity": integrity,
            "sqlite_journal_mode": journal,
            "sqlite_synchronous": "FULL" if synchronous == 2 else "not-full",
            "ledger_counts": counts,
            "secret_commitments_match_state": True,
            "display_presenter_attached": self._presenter_operational,
            "repository_gate_matches_startup": True,
            "presenter_boundary_roots_match_startup": presenter_boundary_matches,
            "browser_runtime_matches_readiness": browser_runtime_matches,
            "ipc_response_auth_required": True,
            "presenter_submission_auth_required": True,
            "operator_signing_lease_required": True,
            "stateful_ipc_result_journal_valid": stateful_results_valid,
            "stateful_ipc_result_journal_rows": stateful_results["row_count"],
            "stateful_ipc_completed_result_rows": stateful_results["completed_count"],
            "stateful_ipc_in_progress_rows": stateful_results["in_progress_count"],
            "stateful_ipc_operation_counts": stateful_results["operation_counts"],
            "sealed_sign_result_recoverable": (
                cohort is None
                or stateful_results["sealed_sign_result_recoverable"] is True
            ),
            "operator_signing_cohort_complete": cohort_complete,
            "operator_signing_cohort_id": (
                cohort.operator_signing_cohort_id if cohort is not None else None
            ),
            "operator_signing_cohort_sha256": (
                cohort.operator_signing_cohort_sha256 if cohort is not None else None
            ),
            "service_is_model_free": True,
            "semantic_quality_gate_passed": False,
            "production_authority_granted": False,
            "model_judge_calls": 0,
        }

    def authenticate_ipc_request(
        self,
        *,
        operation: str,
        body_length: int,
        body_sha256: str,
        nonce: str,
        issued_at: str,
        request_hmac_sha256: str,
    ) -> str:
        """Authenticate and durably consume one loopback request nonce."""

        self._assert_live_secret_state()
        if (
            not isinstance(operation, str)
            or not 1 <= len(operation) <= 80
            or type(body_length) is not int
            or not 0 <= body_length <= _c4_stage1_review_ipc_body_limit(operation)
            or not isinstance(body_sha256, str)
            or len(body_sha256) != 64
            or body_sha256.casefold() != body_sha256
            or any(character not in "0123456789abcdef" for character in body_sha256)
            or not isinstance(nonce, str)
            or len(nonce) != 64
            or nonce.casefold() != nonce
            or any(character not in "0123456789abcdef" for character in nonce)
            or not isinstance(issued_at, str)
            or not isinstance(request_hmac_sha256, str)
            or len(request_hmac_sha256) != 64
            or request_hmac_sha256.casefold() != request_hmac_sha256
            or any(
                character not in "0123456789abcdef" for character in request_hmac_sha256
            )
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC authentication fields are invalid"
            )
        try:
            timestamp = datetime.fromisoformat(issued_at)
        except ValueError:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC timestamp is invalid"
            ) from None
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC timestamp is invalid"
            )
        timestamp = timestamp.astimezone(timezone.utc)
        now = _normalized_clock(self._clock)
        if abs((now - timestamp).total_seconds()) > _IPC_MAX_CLOCK_SKEW_SECONDS:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC request is outside its time window"
            )
        message = c4_stage1_review_ipc_auth_message(
            operation=operation,
            body_length=body_length,
            body_sha256=body_sha256,
            nonce=nonce,
            issued_at=issued_at,
        )
        expected_hmac = hmac.digest(self._ipc_auth_secret, message, "sha256").hex()
        if not hmac.compare_digest(expected_hmac, request_hmac_sha256):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC authentication failed"
            )
        request_sha256 = _sha256(message)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"""
                INSERT INTO {_IPC_NONCE_TABLE}
                    (nonce, request_sha256, issued_at, consumed_at)
                VALUES (?, ?, ?, ?)
                """,
                (nonce, request_sha256, issued_at, now.isoformat()),
            )
            connection.execute("COMMIT")
        except sqlite3.IntegrityError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC request replay"
            ) from None
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        return request_sha256

    def build_authenticated_ipc_response(
        self,
        *,
        operation: str,
        request_nonce: str,
        request_message_sha256: str,
        ok: bool,
        result: object | None = None,
        error: str | None = None,
    ) -> dict[str, object]:
        message = c4_stage1_review_ipc_response_auth_message(
            operation=operation,
            request_nonce=request_nonce,
            request_message_sha256=request_message_sha256,
            ok=ok,
            result=result,
            error=error,
        )
        response: dict[str, object] = {
            "schema_version": C4_STAGE1_REVIEW_IPC_SCHEMA,
            "operation": operation,
            "request_nonce": request_nonce,
            "request_message_sha256": request_message_sha256,
            "ok": ok,
            "response_hmac_sha256": hmac.digest(
                self._ipc_auth_secret, message, "sha256"
            ).hex(),
        }
        response["result" if ok else "error"] = result if ok else error
        return response

    def _select_operator_secret(
        self, operator_policy: C4HumanReviewOperatorPolicy
    ) -> bytes:
        operator_policy = _canonical_model(operator_policy, C4HumanReviewOperatorPolicy)
        commitments = self._readiness.operator_signing_key_commitment_sha256s
        try:
            index = commitments.index(operator_policy.hmac_key_commitment_sha256)
        except ValueError:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operator policy is not committed by this service"
            ) from None
        return self._operator_secrets[index]

    def _validate_display_policy(
        self, display_policy: C4Stage1DisplayAttesterPolicy
    ) -> C4Stage1DisplayAttesterPolicy:
        display_policy = _canonical_model(display_policy, C4Stage1DisplayAttesterPolicy)
        if (
            display_policy.presenter_implementation_id
            != C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
            or display_policy.presenter_revision != C4_STAGE1_REVIEW_PRESENTER_REVISION
            or display_policy.ui_bundle_sha256 != C4_STAGE1_REVIEW_UI_BUNDLE_SHA256
            or display_policy.content_security_policy
            != C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY
            or display_policy.content_security_policy_sha256
            != C4_STAGE1_REVIEW_CONTENT_SECURITY_POLICY_SHA256
            or not hmac.compare_digest(
                display_policy.display_signing_key_commitment_sha256,
                self._readiness.display_signing_key_commitment_sha256,
            )
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 display policy is not committed by this service"
            )
        return display_policy

    def display(
        self,
        *,
        context: C4Stage1DisplayContext,
        display_policy: C4Stage1DisplayAttesterPolicy,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
        cancellation_event: threading.Event | None = None,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1DisplayPortResult:
        if _stateful_request is None:
            _stateful_request = self._stateful_request_from_payload(
                "display",
                {
                    "context": _model_payload(context),
                    "display_policy": _model_payload(display_policy),
                    "source_png_base64": base64.b64encode(source_png_bytes).decode(
                        "ascii"
                    ),
                    "outputs": [_visible_output_payload(item) for item in outputs],
                },
            )
        if cancellation_event is None:
            cancellation_event = threading.Event()
        self._assert_display_request_active(cancellation_event, "cohort admission")
        with self._cohort_lock:
            self._assert_display_request_active(cancellation_event, "cohort lock")
            self._assert_signing_cohort_open()
            context = _canonical_model(context, C4Stage1DisplayContext)
            self._assert_display_request_active(
                cancellation_event, "display context validation"
            )
            with self._pending_lock:
                if len(self._retained_contexts) >= 2 or any(
                    retained.operator_policy_id == context.operator_policy_id
                    for retained, _ in self._retained_contexts.values()
                ):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 review cohort already contains this policy"
                    )
            return self._display_before_signing_cohort(
                context=context,
                display_policy=display_policy,
                source_png_bytes=source_png_bytes,
                outputs=outputs,
                cancellation_event=cancellation_event,
                stateful_request=_stateful_request,
            )

    @staticmethod
    def _assert_display_request_active(
        cancellation_event: threading.Event,
        checkpoint: str,
    ) -> None:
        if cancellation_event.is_set():
            raise C4Stage1ReviewServiceError(
                f"C4 Stage 1 display request was cancelled during {checkpoint}"
            )

    def _display_before_signing_cohort(
        self,
        *,
        context: C4Stage1DisplayContext,
        display_policy: C4Stage1DisplayAttesterPolicy,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
        cancellation_event: threading.Event,
        stateful_request: _C4Stage1StatefulOperationRequest | None,
    ) -> C4Stage1DisplayPortResult:
        self._assert_display_request_active(cancellation_event, "repository gate")
        self._assert_live_repository_gate()
        self._assert_display_request_active(cancellation_event, "secret-state gate")
        self._assert_live_secret_state()
        self._assert_display_request_active(cancellation_event, "presenter boundary")
        if (
            self._presenter_operational is not True
            or not self._presenter_boundary_matches_startup()
            or getattr(self._presenter, "presenter_implementation_id", None)
            != C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
            or getattr(self._presenter, "presenter_revision", None)
            != C4_STAGE1_REVIEW_PRESENTER_REVISION
            or getattr(self._presenter, "browser_runtime_pin", None)
            != self._browser_runtime
            or not callable(getattr(self._presenter, "present", None))
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 pinned presenter changed after initialization"
            )
        display_policy = self._validate_display_policy(display_policy)
        self._assert_display_request_active(
            cancellation_event, "display policy validation"
        )
        context = _canonical_model(context, C4Stage1DisplayContext)
        if (
            context.ui_implementation_id != C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID
            or context.ui_revision != C4_STAGE1_REVIEW_PRESENTER_REVISION
            or context.display_policy_id != display_policy.display_policy_id
            or context.display_policy_sha256 != display_policy.display_policy_sha256
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 display context differs from the offline presenter"
            )
        self._assert_display_request_active(
            cancellation_event, "display acknowledgement"
        )
        acknowledgement = build_c4_stage1_display_port_acknowledgement(
            context,
            source_png_bytes=source_png_bytes,
            outputs=outputs,
        )
        self._assert_display_request_active(cancellation_event, "presentation start")
        if stateful_request is not None:
            self._reserve_stateful_display(stateful_request)
        try:
            return self._present_and_complete_display(
                context=context,
                display_policy=display_policy,
                source_png_bytes=source_png_bytes,
                outputs=outputs,
                acknowledgement=acknowledgement,
                cancellation_event=cancellation_event,
                stateful_request=stateful_request,
            )
        finally:
            if stateful_request is not None:
                self._clear_active_stateful_display(stateful_request)

    def _present_and_complete_display(
        self,
        *,
        context: C4Stage1DisplayContext,
        display_policy: C4Stage1DisplayAttesterPolicy,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        cancellation_event: threading.Event,
        stateful_request: _C4Stage1StatefulOperationRequest | None,
    ) -> C4Stage1DisplayPortResult:
        try:
            displayed = self._presenter.present(
                context,
                source_png_bytes,
                outputs,
                cancellation_event=cancellation_event,
            )
        except Exception:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 offline presentation failed"
            ) from None
        self._assert_display_request_active(
            cancellation_event, "presentation completion"
        )
        if displayed is not True:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 offline presentation was not completed"
            )
        self._assert_display_request_active(
            cancellation_event, "presentation retention"
        )
        tag = hmac.digest(
            self._display_secret,
            c4_stage1_display_attestation_message(
                display_policy, context, acknowledgement
            ),
            "sha256",
        ).hex()
        attestation = build_c4_stage1_display_attestation(
            display_policy,
            context,
            acknowledgement,
            external_hmac_sha256=tag,
        )
        result_payload = {
            "acknowledgement": _model_payload(acknowledgement),
            "attestation": _model_payload(attestation),
        }
        completed_at = _normalized_clock(self._clock)
        connection = self._connect()
        opaque_context_hmac = hmac.digest(
            self._submission_auth_secret,
            b"rei-c4-stage1-opaque-live-context-v1\x00"
            + context.context_id.encode("utf-8"),
            "sha256",
        ).hex()
        active_lock_acquired = False
        if stateful_request is not None:
            self._active_stateful_display_lock.acquire()
            active_lock_acquired = True
        try:
            if stateful_request is not None and (
                self._active_stateful_display_request_id
                != stateful_request.operation_request_id
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 active display reservation changed"
                )
            connection.execute("BEGIN IMMEDIATE")
            self._assert_display_request_active(
                cancellation_event, "presentation retention transaction"
            )
            connection.execute(
                f"""
                INSERT INTO {_PRESENTATION_CONTEXT_TABLE}
                    (opaque_context_hmac_sha256, created_at)
                VALUES (?, ?)
                """,
                (
                    opaque_context_hmac,
                    completed_at.isoformat(),
                ),
            )
            self._complete_stateful_result(
                connection,
                stateful_request,
                result_payload,
                effect_kind="display-attestation",
                effect_id=attestation.display_attestation_id,
                effect_sha256=attestation.display_attestation_sha256,
                completed_at=completed_at,
                require_in_progress=stateful_request is not None,
            )
            self._assert_display_request_active(
                cancellation_event, "presentation retention commit"
            )
            connection.execute("COMMIT")
            if stateful_request is not None:
                self._active_stateful_display_request_id = None
        except sqlite3.IntegrityError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presentation context was already retained"
            ) from None
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
            if active_lock_acquired:
                self._active_stateful_display_lock.release()
        with self._pending_lock:
            if context.context_id in self._retained_contexts:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 live presentation context replay"
                )
            self._retained_contexts[context.context_id] = (context, acknowledgement)
        return C4Stage1DisplayPortResult(
            acknowledgement=acknowledgement,
            attestation=attestation,
        )

    def cancel_active_presentation(self) -> bool:
        cancel = getattr(self._presenter, "cancel_active", None)
        if not callable(cancel):
            return False
        try:
            return cancel() is True
        except Exception:
            return False

    @staticmethod
    def _validate_submission_against_context(
        value: bytes, context: C4Stage1DisplayContext
    ) -> Mapping[str, object]:
        decoded = _mapping(_decode_json(value), label="presenter submission")
        expected = {
            "ipcProtocol",
            "serviceSchemaRevision",
            "ledgerSchemaRevision",
            "packetId",
            "packetSha256",
            "sourceImageSha256",
            "reviewerPseudonym",
            "outputs",
            "pairJudgments",
        }
        outputs = decoded.get("outputs")
        if (
            set(decoded) != expected
            or canonical_json_bytes(decoded) != value
            or decoded.get("ipcProtocol") != C4_STAGE1_REVIEW_IPC_SCHEMA
            or decoded.get("serviceSchemaRevision") != C4_STAGE1_REVIEW_SERVICE_SCHEMA
            or decoded.get("ledgerSchemaRevision") != C4_STAGE1_REVIEW_LEDGER_SCHEMA
            or decoded.get("packetId") != context.packet_id
            or decoded.get("packetSha256") != context.packet_sha256
            or decoded.get("sourceImageSha256") != context.source_image_sha256
            or type(outputs) is not list
            or len(outputs) != 2
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission differs from its exact context"
            )
        for raw, reference in zip(outputs, context.outputs, strict=True):
            if (
                type(raw) is not dict
                or set(raw)
                != {"blindCode", "instructionSha256", "outputSha256", "judgments"}
                or raw.get("blindCode") != reference.blind_code
                or raw.get("instructionSha256") != reference.instruction_sha256
                or raw.get("outputSha256") != reference.output_sha256
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 presenter output differs from its exact context"
                )
        return decoded

    def take_presentation_submission(
        self,
        *,
        context_id: str,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1AuthenticatedPresenterSubmission:
        """Authenticate, retain and return one exact presenter submission."""

        if _stateful_request is None:
            _stateful_request = self._stateful_request_from_payload(
                "take_presentation_submission", {"context_id": context_id}
            )
        with self._cohort_lock:
            self._assert_signing_cohort_open()
            return self._take_presentation_submission_before_cohort(
                context_id=context_id,
                stateful_request=_stateful_request,
            )

    def _take_presentation_submission_before_cohort(
        self,
        *,
        context_id: str,
        stateful_request: _C4Stage1StatefulOperationRequest | None,
    ) -> C4Stage1AuthenticatedPresenterSubmission:
        """Retain a submission while the only signing cohort is still open."""

        self._assert_live_repository_gate()
        self._assert_live_secret_state()
        if (
            self._presenter_operational is not True
            or not self._presenter_boundary_matches_startup()
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 offline presenter is not operational"
            )
        peek = getattr(self._presenter, "peek_submission", None)
        discard = getattr(self._presenter, "discard_submission", None)
        if not callable(peek) or not callable(discard):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter cannot return a sealed submission"
            )
        try:
            taken = peek(context_id)
        except Exception:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission is unavailable"
            ) from None
        if (
            type(taken) is not tuple
            or len(taken) != 2
            or type(taken[0]) is not bytes
            or not isinstance(taken[1], datetime)
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission result is invalid"
            )
        value, submitted_at = taken
        if not 0 < len(value) <= 64 * 1024:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission is not bounded canonical JSON"
            )
        if submitted_at.tzinfo is None or submitted_at.utcoffset() is None:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission timestamp is invalid"
            )
        submitted_at = submitted_at.astimezone(timezone.utc)
        now = _normalized_clock(self._clock)
        if (
            submitted_at > now
            or (now - submitted_at).total_seconds()
            > self.presenter_session_timeout_seconds + 60
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission timestamp is outside its session"
            )
        with self._pending_lock:
            retained = self._retained_contexts.get(context_id)
        if retained is None:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission has no live retained display context"
            )
        context, _acknowledgement = retained
        self._validate_submission_against_context(value, context)
        base = {
            "schema_version": "rei-c4-stage1-authenticated-presenter-submission-v1",
            "context_id": context.context_id,
            "context_sha256": context.context_sha256,
            "packet_id": context.packet_id,
            "packet_sha256": context.packet_sha256,
            "ipc_protocol": C4_STAGE1_REVIEW_IPC_SCHEMA,
            "service_schema_revision": C4_STAGE1_REVIEW_SERVICE_SCHEMA,
            "ledger_schema_revision": C4_STAGE1_REVIEW_LEDGER_SCHEMA,
            "canonical_submission_base64": base64.b64encode(value).decode("ascii"),
            "canonical_submission_sha256": _sha256(value),
            "canonical_submission_size_bytes": len(value),
            "submitted_at": submitted_at,
            "presenter_submission_is_exact": True,
            "service_auth_secret_exposed": False,
        }
        receipt_id = content_id("c4_s1_auth_presenter_submission", base)
        receipt_sha256 = _sha256(canonical_json_bytes(base))
        unsigned = C4Stage1AuthenticatedPresenterSubmission(
            submission_receipt_id=receipt_id,
            submission_receipt_sha256=receipt_sha256,
            service_auth_hmac_sha256="0" * 64,
            **base,
        )
        receipt = C4Stage1AuthenticatedPresenterSubmission(
            **{
                **unsigned.model_dump(mode="python", round_trip=True),
                "service_auth_hmac_sha256": hmac.digest(
                    self._submission_auth_secret,
                    _submission_receipt_auth_message(unsigned),
                    "sha256",
                ).hex(),
            }
        )
        with self._pending_lock:
            if context_id in self._pending_submission_receipts:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 presenter submission was already retained"
                )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._complete_stateful_result(
                connection,
                stateful_request,
                _model_payload(receipt),
                effect_kind="presenter-submission",
                effect_id=receipt.submission_receipt_id,
                effect_sha256=receipt.submission_receipt_sha256,
                completed_at=now,
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        with self._pending_lock:
            if context_id in self._pending_submission_receipts:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 presenter submission was already retained"
                )
            self._pending_submission_receipts[context_id] = receipt
        try:
            discard(
                context_id,
                expected_submission=value,
                expected_submitted_at=submitted_at,
            )
        except Exception:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter submission discard failed"
            ) from None
        return receipt

    def verify_authenticated_submission(
        self, *, submission_receipt: C4Stage1AuthenticatedPresenterSubmission
    ) -> bool:
        self._assert_live_secret_state()
        try:
            receipt = _canonical_model(
                submission_receipt, C4Stage1AuthenticatedPresenterSubmission
            )
            expected = hmac.digest(
                self._submission_auth_secret,
                _submission_receipt_auth_message(receipt),
                "sha256",
            ).hex()
            if not hmac.compare_digest(expected, receipt.service_auth_hmac_sha256):
                return False
            with self._pending_lock:
                pending = self._pending_submission_receipts.get(receipt.context_id)
            if pending == receipt:
                return True
            connection = self._connect()
            try:
                stored = connection.execute(
                    f"SELECT receipt_json FROM {_PRESENTER_SUBMISSION_TABLE} "
                    "WHERE submission_receipt_id = ?",
                    (receipt.submission_receipt_id,),
                ).fetchone()
            finally:
                connection.close()
            return stored == (receipt.canonical_json_bytes(),)
        except (TypeError, ValueError, C4Stage1ReviewServiceError):
            return False

    def issue_operator_signing_lease(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        submission_receipt: C4Stage1AuthenticatedPresenterSubmission,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_display_receipt: C4Stage1ConsumedDisplayReceipt,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1OperatorSigningLease:
        """Issue one short-lived lease for an exact retained manual submission."""

        if _stateful_request is None:
            _stateful_request = self._stateful_request_from_payload(
                "issue_operator_signing_lease",
                {
                    "operator_policy": _model_payload(operator_policy),
                    "submission_receipt": _model_payload(submission_receipt),
                    "display_receipt": _model_payload(display_receipt),
                    "consumed_display_receipt": _model_payload(
                        consumed_display_receipt
                    ),
                },
            )
        with self._cohort_lock:
            self._assert_signing_cohort_open()
            return self._issue_operator_signing_lease_before_cohort(
                operator_policy=operator_policy,
                submission_receipt=submission_receipt,
                display_receipt=display_receipt,
                consumed_display_receipt=consumed_display_receipt,
                stateful_request=_stateful_request,
            )

    def _issue_operator_signing_lease_before_cohort(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        submission_receipt: C4Stage1AuthenticatedPresenterSubmission,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_display_receipt: C4Stage1ConsumedDisplayReceipt,
        stateful_request: _C4Stage1StatefulOperationRequest | None,
    ) -> C4Stage1OperatorSigningLease:
        """Create one lease while the only signing cohort remains open."""

        operator_policy = _canonical_model(operator_policy, C4HumanReviewOperatorPolicy)
        submission_receipt = _canonical_model(
            submission_receipt, C4Stage1AuthenticatedPresenterSubmission
        )
        display_receipt = _canonical_model(
            display_receipt, C4Stage1DisplayExecutionReceipt
        )
        consumed_display_receipt = _canonical_model(
            consumed_display_receipt, C4Stage1ConsumedDisplayReceipt
        )
        if (
            not self.verify_authenticated_submission(
                submission_receipt=submission_receipt
            )
            or not self.verify_consumed_display_receipt(
                display_receipt=display_receipt,
                consumed_receipt=consumed_display_receipt,
            )
            or display_receipt.context.context_id != submission_receipt.context_id
            or display_receipt.context.context_sha256
            != submission_receipt.context_sha256
            or display_receipt.context.packet_id != submission_receipt.packet_id
            or display_receipt.context.packet_sha256 != submission_receipt.packet_sha256
            or display_receipt.context.operator_policy_id != operator_policy.policy_id
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operator lease inputs cross a retained review boundary"
            )
        issued_at = _normalized_clock(self._clock)
        review_timestamp = max(
            submission_receipt.submitted_at,
            display_receipt.display_completed_at.astimezone(timezone.utc),
        )
        if (
            review_timestamp > issued_at
            or (issued_at - review_timestamp).total_seconds() > 10 * 60
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 server-derived review timestamp is outside its window"
            )
        base = {
            "schema_version": "rei-c4-stage1-operator-signing-lease-v1",
            "operator_policy_id": operator_policy.policy_id,
            "operator_policy_sha256": operator_policy.operator_policy_sha256,
            "submission_receipt_id": submission_receipt.submission_receipt_id,
            "submission_receipt_sha256": submission_receipt.submission_receipt_sha256,
            "context_id": submission_receipt.context_id,
            "context_sha256": submission_receipt.context_sha256,
            "display_receipt_id": display_receipt.display_receipt_id,
            "display_receipt_sha256": display_receipt.display_receipt_sha256,
            "consumed_display_receipt_id": (
                consumed_display_receipt.consumed_display_receipt_id
            ),
            "consumed_display_receipt_sha256": (
                consumed_display_receipt.consumed_display_receipt_sha256
            ),
            "issued_at": issued_at,
            "expires_at": issued_at + timedelta(minutes=5),
            "review_timestamp": review_timestamp,
            "create_once": True,
            "consume_once_before_operator_hmac": True,
            "service_auth_secret_exposed": False,
        }
        lease_id = content_id("c4_stage1_operator_signing_lease", base)
        lease_sha256 = _sha256(canonical_json_bytes(base))
        unsigned = C4Stage1OperatorSigningLease(
            operator_signing_lease_id=lease_id,
            operator_signing_lease_sha256=lease_sha256,
            service_auth_hmac_sha256="0" * 64,
            **base,
        )
        lease = C4Stage1OperatorSigningLease(
            **{
                **unsigned.model_dump(mode="python", round_trip=True),
                "service_auth_hmac_sha256": hmac.digest(
                    self._submission_auth_secret,
                    _operator_signing_lease_auth_message(unsigned),
                    "sha256",
                ).hex(),
            }
        )
        with self._pending_lock:
            if lease.submission_receipt_id in self._pending_operator_leases:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 operator signing lease was already issued"
                )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._complete_stateful_result(
                connection,
                stateful_request,
                _model_payload(lease),
                effect_kind="operator-signing-lease",
                effect_id=lease.operator_signing_lease_id,
                effect_sha256=lease.operator_signing_lease_sha256,
                completed_at=issued_at,
            )
            connection.execute("COMMIT")
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()
        with self._pending_lock:
            if lease.submission_receipt_id in self._pending_operator_leases:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 operator signing lease was already issued"
                )
            self._pending_operator_leases[lease.submission_receipt_id] = lease
        return lease

    def verify_operator_signing_lease(
        self, *, operator_signing_lease: C4Stage1OperatorSigningLease
    ) -> bool:
        self._assert_live_secret_state()
        try:
            lease = _canonical_model(
                operator_signing_lease, C4Stage1OperatorSigningLease
            )
            expected = hmac.digest(
                self._submission_auth_secret,
                _operator_signing_lease_auth_message(lease),
                "sha256",
            ).hex()
            if not hmac.compare_digest(expected, lease.service_auth_hmac_sha256):
                return False
            with self._pending_lock:
                pending = self._pending_operator_leases.get(lease.submission_receipt_id)
            if pending == lease:
                return True
            connection = self._connect()
            try:
                stored = connection.execute(
                    f"SELECT lease_json FROM {_OPERATOR_SIGNING_LEASE_TABLE} "
                    "WHERE operator_signing_lease_id = ?",
                    (lease.operator_signing_lease_id,),
                ).fetchone()
            finally:
                connection.close()
            return stored == (lease.canonical_json_bytes(),)
        except (TypeError, ValueError, C4Stage1ReviewServiceError):
            return False

    def verify_display_attestation(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> bool:
        self._assert_live_secret_state()
        try:
            display_policy = self._validate_display_policy(display_policy)
            context = _canonical_model(context, C4Stage1DisplayContext)
            acknowledgement = _canonical_model(
                acknowledgement, C4Stage1DisplayPortAcknowledgement
            )
            attestation = _canonical_model(attestation, C4Stage1DisplayAttestation)
            tag = hmac.digest(
                self._display_secret,
                c4_stage1_display_attestation_message(
                    display_policy, context, acknowledgement
                ),
                "sha256",
            ).hex()
            expected = build_c4_stage1_display_attestation(
                display_policy,
                context,
                acknowledgement,
                external_hmac_sha256=tag,
            )
        except (TypeError, ValueError, C4Stage1ReviewServiceError):
            return False
        return expected == attestation

    def _validate_operator_signing_request(
        self,
        request: C4Stage1OperatorSigningRequest,
        *,
        now: datetime,
    ) -> C4Stage1OperatorSigningRequest:
        request = C4Stage1OperatorSigningRequest.model_validate(
            request.model_dump(mode="python", round_trip=True)
        )
        operator_policy = request.operator_policy
        claim = request.claim
        submission_receipt = request.submission_receipt
        operator_signing_lease = request.operator_signing_lease
        display_receipt = request.display_receipt
        consumed_display_receipt = request.consumed_display_receipt
        if (
            claim.operator_policy_id != operator_policy.policy_id
            or claim.operator_policy_sha256 != operator_policy.operator_policy_sha256
            or claim.review_schema_id != operator_policy.review_schema_id
            or claim.packet_id != display_receipt.context.packet_id
            or claim.packet_sha256 != display_receipt.context.packet_sha256
            or claim.presentation_manifest_id
            != display_receipt.context.presentation_manifest_id
            or claim.presentation_manifest_sha256
            != display_receipt.context.presentation_manifest_sha256
            or claim.screen_contract_id != display_receipt.context.screen_contract_id
            or claim.screen_contract_sha256
            != display_receipt.context.screen_contract_sha256
            or claim.display_policy_id != display_receipt.context.display_policy_id
            or claim.display_policy_sha256
            != display_receipt.context.display_policy_sha256
            or claim.display_policy_artifact_sha256
            != display_receipt.context.display_policy_artifact_sha256
            or claim.display_attestation_id
            != display_receipt.display_attestation.display_attestation_id
            or claim.display_attestation_sha256
            != display_receipt.display_attestation.display_attestation_sha256
            or claim.consumed_display_attestation_id
            != display_receipt.consumed_display_attestation.consumed_display_attestation_id
            or claim.consumed_display_attestation_sha256
            != display_receipt.consumed_display_attestation.consumed_display_attestation_sha256
            or not self.verify_authenticated_submission(
                submission_receipt=submission_receipt
            )
            or not self.verify_operator_signing_lease(
                operator_signing_lease=operator_signing_lease
            )
            or not self.verify_consumed_display_receipt(
                display_receipt=display_receipt,
                consumed_receipt=consumed_display_receipt,
            )
            or operator_signing_lease.operator_policy_id != operator_policy.policy_id
            or operator_signing_lease.operator_policy_sha256
            != operator_policy.operator_policy_sha256
            or operator_signing_lease.submission_receipt_id
            != submission_receipt.submission_receipt_id
            or operator_signing_lease.submission_receipt_sha256
            != submission_receipt.submission_receipt_sha256
            or operator_signing_lease.context_id != display_receipt.context.context_id
            or operator_signing_lease.context_sha256
            != display_receipt.context.context_sha256
            or operator_signing_lease.display_receipt_id
            != display_receipt.display_receipt_id
            or operator_signing_lease.display_receipt_sha256
            != display_receipt.display_receipt_sha256
            or operator_signing_lease.consumed_display_receipt_id
            != consumed_display_receipt.consumed_display_receipt_id
            or operator_signing_lease.consumed_display_receipt_sha256
            != consumed_display_receipt.consumed_display_receipt_sha256
            or claim.submission_receipt_id != submission_receipt.submission_receipt_id
            or claim.submission_receipt_sha256
            != submission_receipt.submission_receipt_sha256
            or claim.operator_signing_lease_id
            != operator_signing_lease.operator_signing_lease_id
            or claim.operator_signing_lease_sha256
            != operator_signing_lease.operator_signing_lease_sha256
            or claim.review_timestamp != operator_signing_lease.review_timestamp
            or claim.display_receipt_id != display_receipt.display_receipt_id
            or claim.display_receipt_sha256 != display_receipt.display_receipt_sha256
            or claim.consumed_display_receipt_id
            != consumed_display_receipt.consumed_display_receipt_id
            or claim.consumed_display_receipt_sha256
            != consumed_display_receipt.consumed_display_receipt_sha256
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operator claim differs from its retained submission lease"
            )
        if (
            now > operator_signing_lease.expires_at
            or now < operator_signing_lease.issued_at
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operator signing lease expired"
            )
        decoded = self._validate_submission_against_context(
            submission_receipt.canonical_submission_bytes,
            display_receipt.context,
        )
        raw_outputs = decoded["outputs"]
        if (
            not isinstance(raw_outputs, list)
            or decoded["reviewerPseudonym"] != claim.reviewer_pseudonym
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operator claim mutates its retained reviewer or outputs"
            )
        for raw, judgment in zip(raw_outputs, claim.output_judgments, strict=True):
            if not isinstance(raw, dict):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 retained submission output is invalid"
                )
            raw_judgments = raw.get("judgments")
            if (
                not isinstance(raw_judgments, dict)
                or set(raw_judgments) != set(_SUBMISSION_OUTPUT_BOOLEAN_FIELDS)
                or any(
                    type(raw_judgments[field]) is not bool
                    or raw_judgments[field] != getattr(judgment, field)
                    for field in _SUBMISSION_OUTPUT_BOOLEAN_FIELDS
                )
                or raw.get("blindCode") != judgment.blind_code
                or raw.get("instructionSha256") != judgment.instruction_sha256
                or raw.get("outputSha256") != judgment.output_sha256
                or judgment.source_image_sha256
                != display_receipt.context.source_image_sha256
            ):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 operator claim mutates retained judgments"
                )
        raw_pair = decoded["pairJudgments"]
        if (
            not isinstance(raw_pair, dict)
            or set(raw_pair) != set(_SUBMISSION_PAIR_BOOLEAN_FIELDS)
            or any(
                type(raw_pair[field]) is not bool
                or raw_pair[field] != getattr(claim.pair_judgment, field)
                for field in _SUBMISSION_PAIR_BOOLEAN_FIELDS
            )
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operator claim mutates the retained pair judgment"
            )
        return request

    def _validate_two_review_cohort_bindings(
        self,
        reviews: tuple[
            C4Stage1OperatorSigningRequest,
            C4Stage1OperatorSigningRequest,
        ],
    ) -> None:
        first, second = reviews
        publications = tuple(
            review.display_receipt.publication_binding for review in reviews
        )
        contexts = tuple(review.display_receipt.context for review in reviews)
        policies = tuple(review.operator_policy for review in reviews)
        if (
            {policy.hmac_key_commitment_sha256 for policy in policies}
            != set(self._readiness.operator_signing_key_commitment_sha256s)
            or {publication.editor_role for publication in publications}
            != {"primary", "alternate"}
            or publications[0].run_id != publications[1].run_id
            or publications[0].prepared_attempt_id
            != publications[1].prepared_attempt_id
            or publications[0].prepared_attempt_sha256
            != publications[1].prepared_attempt_sha256
            or publications[0].prepared_anchor_storage
            != publications[1].prepared_anchor_storage
            or publications[0].source_storage != publications[1].source_storage
            or contexts[0].screen_contract_id != contexts[1].screen_contract_id
            or contexts[0].screen_contract_sha256 != contexts[1].screen_contract_sha256
            or contexts[0].display_policy_id != contexts[1].display_policy_id
            or contexts[0].display_policy_sha256 != contexts[1].display_policy_sha256
            or contexts[0].display_policy_artifact_sha256
            != contexts[1].display_policy_artifact_sha256
            or contexts[0].review_schema_id != contexts[1].review_schema_id
            or contexts[0].review_schema_sha256 != contexts[1].review_schema_sha256
            or contexts[0].rubric_version != contexts[1].rubric_version
            or contexts[0].source_image_sha256 != contexts[1].source_image_sha256
            or policies[0].run_id != policies[1].run_id
            or policies[0].run_id != publications[0].run_id
            or policies[0].review_schema_id != contexts[0].review_schema_id
            or policies[1].review_schema_id != contexts[1].review_schema_id
            or policies[0].source_image_sha256 != contexts[0].source_image_sha256
            or policies[1].source_image_sha256 != contexts[1].source_image_sha256
            or publications[0].source_storage.content_sha256
            != contexts[0].source_image_sha256
            or any(
                review.operator_policy.candidate_slot_id
                != review.display_receipt.publication_binding.provider_slot_id
                or review.display_receipt.context.operator_policy_id
                != review.operator_policy.policy_id
                or review.display_receipt.context.operator_policy_sha256
                != review.operator_policy.operator_policy_sha256
                for review in reviews
            )
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing requests cross review cohorts"
            )
        distinct_pairs = (
            (first.operator_policy.policy_id, second.operator_policy.policy_id),
            (
                first.operator_policy.candidate_slot_id,
                second.operator_policy.candidate_slot_id,
            ),
            (
                first.display_receipt.context.context_id,
                second.display_receipt.context.context_id,
            ),
            (
                first.display_receipt.context.packet_id,
                second.display_receipt.context.packet_id,
            ),
            (
                first.display_receipt.context.packet_sha256,
                second.display_receipt.context.packet_sha256,
            ),
            (
                first.display_receipt.context.presentation_manifest_id,
                second.display_receipt.context.presentation_manifest_id,
            ),
            (
                first.display_receipt.context.presentation_manifest_sha256,
                second.display_receipt.context.presentation_manifest_sha256,
            ),
            (
                first.display_receipt.context.material_commitment_id,
                second.display_receipt.context.material_commitment_id,
            ),
            (
                first.display_receipt.context.material_commitment_sha256,
                second.display_receipt.context.material_commitment_sha256,
            ),
            (
                first.display_receipt.display_receipt_id,
                second.display_receipt.display_receipt_id,
            ),
            (
                first.consumed_display_receipt.consumed_display_receipt_id,
                second.consumed_display_receipt.consumed_display_receipt_id,
            ),
            (
                first.submission_receipt.submission_receipt_id,
                second.submission_receipt.submission_receipt_id,
            ),
            (
                first.operator_signing_lease.operator_signing_lease_id,
                second.operator_signing_lease.operator_signing_lease_id,
            ),
            (first.claim.claim_id, second.claim.claim_id),
        )
        if any(left == right for left, right in distinct_pairs):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing cohort members must be distinct"
            )

    def _completed_signing_cohort(
        self,
        reviews: tuple[
            C4Stage1OperatorSigningRequest,
            C4Stage1OperatorSigningRequest,
        ],
        attestations: tuple[
            C4Stage1HumanReviewOperatorAttestation,
            C4Stage1HumanReviewOperatorAttestation,
        ],
        consumed_operator_receipts: tuple[
            C4Stage1ConsumedOperatorPolicyReceipt,
            C4Stage1ConsumedOperatorPolicyReceipt,
        ],
        *,
        completed_at: datetime,
    ) -> C4Stage1CompletedSigningCohort:
        records = []
        for request, attestation, consumed in zip(
            reviews, attestations, consumed_operator_receipts, strict=True
        ):
            context = request.display_receipt.context
            publication = request.display_receipt.publication_binding
            display_attestation_binding = _binding_sha256(
                "c4-stage1-display-attestation-ledger-binding-v1",
                request.display_receipt.display_attester_policy,
                context,
                request.display_receipt.acknowledgement,
                request.display_receipt.display_attestation,
            )
            display_receipt_binding = _binding_sha256(
                "c4-stage1-display-receipt-ledger-binding-v1",
                request.display_receipt,
            )
            operator_policy_binding = _binding_sha256(
                "c4-stage1-operator-policy-ledger-binding-v1",
                request.operator_policy,
                attestation,
            )
            records.append(
                C4Stage1CompletedSigningCohortMember(
                    editor_role=publication.editor_role,
                    provider_slot_id=publication.provider_slot_id,
                    operator_policy_id=request.operator_policy.policy_id,
                    operator_policy_sha256=(
                        request.operator_policy.operator_policy_sha256
                    ),
                    operator_key_commitment_sha256=(
                        request.operator_policy.hmac_key_commitment_sha256
                    ),
                    context_id=context.context_id,
                    context_sha256=context.context_sha256,
                    packet_id=context.packet_id,
                    packet_sha256=context.packet_sha256,
                    presentation_manifest_id=context.presentation_manifest_id,
                    presentation_manifest_sha256=(context.presentation_manifest_sha256),
                    material_commitment_id=context.material_commitment_id,
                    material_commitment_sha256=context.material_commitment_sha256,
                    display_attestation_id=(
                        request.display_receipt.display_attestation.display_attestation_id
                    ),
                    display_attestation_sha256=(
                        request.display_receipt.display_attestation.display_attestation_sha256
                    ),
                    consumed_display_attestation_id=(
                        request.display_receipt.consumed_display_attestation.consumed_display_attestation_id
                    ),
                    consumed_display_attestation_sha256=(
                        request.display_receipt.consumed_display_attestation.consumed_display_attestation_sha256
                    ),
                    display_attestation_ledger_binding_sha256=(
                        display_attestation_binding
                    ),
                    display_attestation_ledger_transaction_id=(
                        request.display_receipt.consumed_display_attestation.external_transaction_id
                    ),
                    display_receipt_id=request.display_receipt.display_receipt_id,
                    display_receipt_sha256=(
                        request.display_receipt.display_receipt_sha256
                    ),
                    consumed_display_receipt_id=(
                        request.consumed_display_receipt.consumed_display_receipt_id
                    ),
                    consumed_display_receipt_sha256=(
                        request.consumed_display_receipt.consumed_display_receipt_sha256
                    ),
                    display_receipt_ledger_binding_sha256=display_receipt_binding,
                    display_receipt_ledger_transaction_id=(
                        request.consumed_display_receipt.external_transaction_id
                    ),
                    submission_receipt_id=(
                        request.submission_receipt.submission_receipt_id
                    ),
                    submission_receipt_sha256=(
                        request.submission_receipt.submission_receipt_sha256
                    ),
                    operator_signing_lease_id=(
                        request.operator_signing_lease.operator_signing_lease_id
                    ),
                    operator_signing_lease_sha256=(
                        request.operator_signing_lease.operator_signing_lease_sha256
                    ),
                    claim_id=request.claim.claim_id,
                    claim_sha256=request.claim.claim_sha256,
                    attestation_id=attestation.attestation_id,
                    attestation_sha256=attestation.attestation_sha256,
                    consumed_operator_receipt_id=(
                        consumed.consumed_operator_receipt_id
                    ),
                    consumed_operator_receipt_sha256=(
                        consumed.consumed_operator_receipt_sha256
                    ),
                    operator_policy_ledger_binding_sha256=(operator_policy_binding),
                    operator_policy_ledger_transaction_id=(
                        consumed.external_transaction_id
                    ),
                )
            )
        records.sort(key=lambda item: 0 if item.editor_role == "primary" else 1)
        publication = reviews[0].display_receipt.publication_binding
        context = reviews[0].display_receipt.context
        body = {
            "schema_version": "rei-c4-stage1-completed-signing-cohort-v1",
            "run_id": publication.run_id,
            "prepared_attempt_id": publication.prepared_attempt_id,
            "prepared_attempt_sha256": publication.prepared_attempt_sha256,
            "prepared_anchor_storage_id": publication.prepared_anchor_storage.storage_id,
            "prepared_anchor_content_sha256": (
                publication.prepared_anchor_storage.content_sha256
            ),
            "screen_contract_id": context.screen_contract_id,
            "screen_contract_sha256": context.screen_contract_sha256,
            "display_policy_id": context.display_policy_id,
            "display_policy_sha256": context.display_policy_sha256,
            "display_policy_artifact_sha256": context.display_policy_artifact_sha256,
            "review_schema_id": context.review_schema_id,
            "review_schema_sha256": context.review_schema_sha256,
            "rubric_version": context.rubric_version,
            "source_storage_id": publication.source_storage.storage_id,
            "source_image_sha256": context.source_image_sha256,
            "members": tuple(records),
            "completed_at": completed_at,
            "review_count": 2,
            "exact_two_reviews_signed_together": True,
            "submission_and_lease_rows_persisted_atomically": True,
            "operator_policy_rows_persisted_atomically": True,
            "single_use_cohort_latch": True,
        }
        authority_snapshot_hmac_sha256 = hmac.digest(
            self._submission_auth_secret,
            _completed_signing_cohort_authority_message(body),
            "sha256",
        ).hex()
        body = {
            **body,
            "authority_snapshot_hmac_sha256": authority_snapshot_hmac_sha256,
        }
        return C4Stage1CompletedSigningCohort(
            operator_signing_cohort_id=content_id(
                "c4_s1_completed_signing_cohort", body
            ),
            operator_signing_cohort_sha256=_sha256(canonical_json_bytes(body)),
            **body,
        )

    def sign_operator_claim_cohort(
        self,
        *,
        reviews: tuple[
            C4Stage1OperatorSigningRequest,
            C4Stage1OperatorSigningRequest,
        ],
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> tuple[
        C4Stage1HumanReviewOperatorAttestation,
        C4Stage1HumanReviewOperatorAttestation,
    ]:
        if type(reviews) is not tuple or len(reviews) != 2:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing requires exactly two complete review requests"
            )
        if _stateful_request is None:
            _stateful_request = self._stateful_request_from_payload(
                "sign_operator_claim_cohort",
                {"reviews": [_model_payload(review) for review in reviews]},
            )
        with self._cohort_lock:
            self._assert_live_repository_gate()
            self._assert_live_secret_state()
            self._assert_signing_cohort_open()
            now = _normalized_clock(self._clock)
            validated = tuple(
                self._validate_operator_signing_request(request, now=now)
                for request in reviews
            )
            self._validate_two_review_cohort_bindings(validated)  # type: ignore[arg-type]
            validated = validated  # type: ignore[assignment]
            context_ids = {
                request.display_receipt.context.context_id for request in validated
            }
            receipt_ids = {
                request.submission_receipt.submission_receipt_id
                for request in validated
            }
            with self._pending_lock:
                if (
                    set(self._retained_contexts) != context_ids
                    or set(self._pending_submission_receipts) != context_ids
                    or set(self._pending_operator_leases) != receipt_ids
                    or self._pending_operator_policy_deliveries
                    or any(
                        self._pending_submission_receipts.get(
                            request.submission_receipt.context_id
                        )
                        != request.submission_receipt
                        or self._pending_operator_leases.get(
                            request.submission_receipt.submission_receipt_id
                        )
                        != request.operator_signing_lease
                        for request in validated
                    )
                ):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 signing requests do not exhaust retained cohort state"
                    )
            attestations = tuple(
                build_c4_stage1_operator_attestation(
                    request.claim,
                    external_hmac_sha256=hmac.digest(
                        self._select_operator_secret(request.operator_policy),
                        c4_stage1_operator_attestation_message(request.claim),
                        "sha256",
                    ).hex(),
                )
                for request in validated
            )
            consumed_operator_receipts = []
            operator_rows = []
            for request, attestation in zip(validated, attestations, strict=True):
                binding = _binding_sha256(
                    "c4-stage1-operator-policy-ledger-binding-v1",
                    request.operator_policy,
                    attestation,
                )
                transaction_id = _transaction_id(
                    "operator-policy", request.operator_policy.policy_id, binding
                )
                receipt = record_c4_stage1_consumed_operator_policy_receipt(
                    request.operator_policy,
                    attestation,
                    external_transaction_id=transaction_id,
                    external_transaction_timestamp=_later_of(
                        now, attestation.claim.review_timestamp
                    ),
                )
                consumed_operator_receipts.append(receipt)
                operator_rows.append((binding, transaction_id, receipt))
            consumed_tuple = tuple(consumed_operator_receipts)
            cohort = self._completed_signing_cohort(
                validated,  # type: ignore[arg-type]
                attestations,  # type: ignore[arg-type]
                consumed_tuple,  # type: ignore[arg-type]
                completed_at=now,
            )
            result_payload = [_model_payload(item) for item in attestations]
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                expected_counts = {
                    "display_attestation_uses": 2,
                    "display_receipt_uses": 2,
                    "operator_policy_uses": 0,
                    _PRESENTER_SUBMISSION_TABLE: 0,
                    _OPERATOR_SIGNING_LEASE_TABLE: 0,
                }
                if (
                    self._authority_ledger_counts(connection) != expected_counts
                    or connection.execute(
                        f"SELECT COUNT(*) FROM {_PRESENTATION_CONTEXT_TABLE}"
                    ).fetchone()
                    != (2,)
                    or connection.execute(
                        f"SELECT COUNT(*) FROM {_COMPLETED_SIGNING_COHORT_TABLE}"
                    ).fetchone()
                    != (0,)
                ):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 authority ledgers are not an exact open cohort"
                    )
                for request, attestation, operator_row in zip(
                    validated, attestations, operator_rows, strict=True
                ):
                    binding, transaction_id, consumed = operator_row
                    connection.execute(
                        f"""
                        INSERT INTO {_PRESENTER_SUBMISSION_TABLE}
                            (submission_receipt_id, submission_receipt_sha256,
                             context_id, receipt_json, consumed_at, claim_id,
                             attestation_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            request.submission_receipt.submission_receipt_id,
                            request.submission_receipt.submission_receipt_sha256,
                            request.submission_receipt.context_id,
                            request.submission_receipt.canonical_json_bytes(),
                            now.isoformat(),
                            request.claim.claim_id,
                            attestation.canonical_json_bytes(),
                        ),
                    )
                    connection.execute(
                        f"""
                        INSERT INTO {_OPERATOR_SIGNING_LEASE_TABLE}
                            (operator_signing_lease_id,
                             operator_signing_lease_sha256,
                             submission_receipt_id, operator_policy_id,
                             context_id, lease_json, expires_at, consumed_at,
                             claim_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            request.operator_signing_lease.operator_signing_lease_id,
                            request.operator_signing_lease.operator_signing_lease_sha256,
                            request.operator_signing_lease.submission_receipt_id,
                            request.operator_signing_lease.operator_policy_id,
                            request.operator_signing_lease.context_id,
                            request.operator_signing_lease.canonical_json_bytes(),
                            request.operator_signing_lease.expires_at.isoformat(),
                            now.isoformat(),
                            request.claim.claim_id,
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO operator_policy_uses
                            (ledger_key, binding_sha256, receipt_id,
                             receipt_sha256, transaction_id, receipt_json,
                             created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            request.operator_policy.policy_id,
                            binding,
                            consumed.consumed_operator_receipt_id,
                            consumed.consumed_operator_receipt_sha256,
                            transaction_id,
                            consumed.canonical_json_bytes(),
                            now.isoformat(),
                        ),
                    )
                    opaque_context_hmac = hmac.digest(
                        self._submission_auth_secret,
                        b"rei-c4-stage1-opaque-live-context-v1\x00"
                        + request.submission_receipt.context_id.encode("utf-8"),
                        "sha256",
                    ).hex()
                    deleted = connection.execute(
                        f"DELETE FROM {_PRESENTATION_CONTEXT_TABLE} "
                        "WHERE opaque_context_hmac_sha256 = ?",
                        (opaque_context_hmac,),
                    )
                    if deleted.rowcount != 1:
                        raise C4Stage1ReviewServiceError(
                            "C4 Stage 1 retained context changed before cohort commit"
                        )
                if not self._cohort_matches_authority_rows(connection, cohort):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 atomic authority rows do not match their cohort"
                    )
                connection.execute(
                    f"""
                    INSERT INTO {_COMPLETED_SIGNING_COHORT_TABLE}
                        (singleton, operator_signing_cohort_id,
                         operator_signing_cohort_sha256, cohort_json,
                         completed_at)
                    VALUES (1, ?, ?, ?, ?)
                    """,
                    (
                        cohort.operator_signing_cohort_id,
                        cohort.operator_signing_cohort_sha256,
                        cohort.canonical_json_bytes(),
                        cohort.completed_at.isoformat(),
                    ),
                )
                self._complete_stateful_result(
                    connection,
                    _stateful_request,
                    result_payload,
                    effect_kind="operator-signing-cohort",
                    effect_id=cohort.operator_signing_cohort_id,
                    effect_sha256=cohort.operator_signing_cohort_sha256,
                    completed_at=now,
                )
                connection.execute("COMMIT")
            except Exception as exc:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                if isinstance(exc, C4Stage1ReviewServiceError):
                    raise
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 two-review signing cohort failed atomically"
                ) from None
            finally:
                connection.close()
            with self._pending_lock:
                for request, consumed in zip(validated, consumed_tuple, strict=True):
                    self._pending_submission_receipts.pop(
                        request.submission_receipt.context_id, None
                    )
                    self._pending_operator_leases.pop(
                        request.submission_receipt.submission_receipt_id, None
                    )
                    self._retained_contexts.pop(
                        request.submission_receipt.context_id, None
                    )
                    self._pending_operator_policy_deliveries[
                        request.operator_policy.policy_id
                    ] = consumed
                self._signing_cohort_latch = cohort
            return attestations  # type: ignore[return-value]

    def verify_operator_attestation(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> bool:
        self._assert_live_secret_state()
        try:
            operator_policy = _canonical_model(
                operator_policy, C4HumanReviewOperatorPolicy
            )
            attestation = _canonical_model(
                attestation, C4Stage1HumanReviewOperatorAttestation
            )
            secret = self._select_operator_secret(operator_policy)
            verify_c4_stage1_operator_attestation(
                operator_policy, attestation, operator_secret=secret
            )
        except (TypeError, ValueError, C4Stage1ReviewServiceError):
            return False
        return True

    def _insert_receipt(
        self,
        *,
        table: str,
        ledger_key: str,
        binding_sha256: str,
        receipt: BaseModel,
        receipt_id: str,
        receipt_sha256: str,
        transaction_id: str,
        replay_message: str,
        stateful_request: _C4Stage1StatefulOperationRequest | None = None,
        result_payload: object | None = None,
        effect_kind: str | None = None,
    ) -> None:
        if table not in _LEDGER_TABLES:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review ledger table is invalid"
            )
        receipt_json = canonical_json_bytes(receipt)
        created_at = _normalized_clock(self._clock)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"""
                INSERT INTO {table}
                    (ledger_key, binding_sha256, receipt_id, receipt_sha256,
                     transaction_id, receipt_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ledger_key,
                    binding_sha256,
                    receipt_id,
                    receipt_sha256,
                    transaction_id,
                    receipt_json,
                    created_at.isoformat(),
                ),
            )
            if stateful_request is not None:
                if result_payload is None or effect_kind is None:
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 receipt result journal binding is incomplete"
                    )
                self._complete_stateful_result(
                    connection,
                    stateful_request,
                    result_payload,
                    effect_kind=effect_kind,
                    effect_id=receipt_id,
                    effect_sha256=receipt_sha256,
                    completed_at=created_at,
                )
            connection.execute("COMMIT")
        except sqlite3.IntegrityError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise ValueError(replay_message) from None
        except Exception:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _receipt_is_live(
        self,
        *,
        table: str,
        ledger_key: str,
        binding_sha256: str,
        receipt: BaseModel,
        receipt_id: str,
        receipt_sha256: str,
        transaction_id: str,
    ) -> bool:
        if table not in _LEDGER_TABLES:
            return False
        connection = self._connect()
        try:
            row = connection.execute(
                f"""
                SELECT binding_sha256, receipt_id, receipt_sha256,
                       transaction_id, receipt_json
                FROM {table}
                WHERE ledger_key = ?
                """,
                (ledger_key,),
            ).fetchone()
        finally:
            connection.close()
        expected = (
            binding_sha256,
            receipt_id,
            receipt_sha256,
            transaction_id,
            canonical_json_bytes(receipt),
        )
        return row == expected

    def consume_display_attestation_once(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1ConsumedDisplayAttestation:
        if _stateful_request is None:
            _stateful_request = self._stateful_request_from_payload(
                "consume_display_attestation",
                {
                    "display_policy": _model_payload(display_policy),
                    "context": _model_payload(context),
                    "acknowledgement": _model_payload(acknowledgement),
                    "attestation": _model_payload(attestation),
                },
            )
        with self._cohort_lock:
            self._assert_signing_cohort_open()
            return self._consume_display_attestation_before_cohort(
                display_policy=display_policy,
                context=context,
                acknowledgement=acknowledgement,
                attestation=attestation,
                stateful_request=_stateful_request,
            )

    def _consume_display_attestation_before_cohort(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
        stateful_request: _C4Stage1StatefulOperationRequest | None,
    ) -> C4Stage1ConsumedDisplayAttestation:
        if not self.verify_display_attestation(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
        ):
            raise ValueError("C4 Stage 1 display attestation HMAC is invalid")
        display_policy = self._validate_display_policy(display_policy)
        context = _canonical_model(context, C4Stage1DisplayContext)
        acknowledgement = _canonical_model(
            acknowledgement, C4Stage1DisplayPortAcknowledgement
        )
        attestation = _canonical_model(attestation, C4Stage1DisplayAttestation)
        binding = _binding_sha256(
            "c4-stage1-display-attestation-ledger-binding-v1",
            display_policy,
            context,
            acknowledgement,
            attestation,
        )
        transaction_id = _transaction_id(
            "display-attestation", attestation.display_attestation_id, binding
        )
        receipt = record_c4_stage1_consumed_display_attestation(
            display_policy,
            context,
            acknowledgement,
            attestation,
            external_transaction_id=transaction_id,
            external_transaction_timestamp=_normalized_clock(self._clock),
        )
        self._insert_receipt(
            table="display_attestation_uses",
            ledger_key=attestation.display_attestation_id,
            binding_sha256=binding,
            receipt=receipt,
            receipt_id=receipt.consumed_display_attestation_id,
            receipt_sha256=receipt.consumed_display_attestation_sha256,
            transaction_id=transaction_id,
            replay_message="C4 Stage 1 display attestation replay",
            stateful_request=stateful_request,
            result_payload=_model_payload(receipt),
            effect_kind="consumed-display-attestation",
        )
        return receipt

    def verify_consumed_display_attestation(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
        consumed_receipt: C4Stage1ConsumedDisplayAttestation,
    ) -> bool:
        if not self.verify_display_attestation(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
        ):
            return False
        try:
            display_policy = self._validate_display_policy(display_policy)
            context = _canonical_model(context, C4Stage1DisplayContext)
            acknowledgement = _canonical_model(
                acknowledgement, C4Stage1DisplayPortAcknowledgement
            )
            attestation = _canonical_model(attestation, C4Stage1DisplayAttestation)
            consumed_receipt = _canonical_model(
                consumed_receipt, C4Stage1ConsumedDisplayAttestation
            )
            binding = _binding_sha256(
                "c4-stage1-display-attestation-ledger-binding-v1",
                display_policy,
                context,
                acknowledgement,
                attestation,
            )
            expected = record_c4_stage1_consumed_display_attestation(
                display_policy,
                context,
                acknowledgement,
                attestation,
                external_transaction_id=consumed_receipt.external_transaction_id,
                external_transaction_timestamp=(
                    consumed_receipt.external_transaction_timestamp
                ),
            )
        except (TypeError, ValueError, C4Stage1ReviewServiceError):
            return False
        return expected == consumed_receipt and self._receipt_is_live(
            table="display_attestation_uses",
            ledger_key=attestation.display_attestation_id,
            binding_sha256=binding,
            receipt=consumed_receipt,
            receipt_id=consumed_receipt.consumed_display_attestation_id,
            receipt_sha256=(consumed_receipt.consumed_display_attestation_sha256),
            transaction_id=consumed_receipt.external_transaction_id,
        )

    def consume_display_receipt_once(
        self,
        *,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1ConsumedDisplayReceipt:
        if _stateful_request is None:
            _stateful_request = self._stateful_request_from_payload(
                "consume_display_receipt",
                {"display_receipt": _model_payload(display_receipt)},
            )
        with self._cohort_lock:
            self._assert_signing_cohort_open()
            return self._consume_display_receipt_before_cohort(
                display_receipt=display_receipt,
                stateful_request=_stateful_request,
            )

    def _consume_display_receipt_before_cohort(
        self,
        *,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        stateful_request: _C4Stage1StatefulOperationRequest | None,
    ) -> C4Stage1ConsumedDisplayReceipt:
        self._assert_live_secret_state()
        display_receipt = _canonical_model(
            display_receipt, C4Stage1DisplayExecutionReceipt
        )
        if not self.verify_consumed_display_attestation(
            display_policy=display_receipt.display_attester_policy,
            context=display_receipt.context,
            acknowledgement=display_receipt.acknowledgement,
            attestation=display_receipt.display_attestation,
            consumed_receipt=display_receipt.consumed_display_attestation,
        ):
            raise ValueError(
                "C4 Stage 1 display receipt lacks a live attestation consumption"
            )
        binding = _binding_sha256(
            "c4-stage1-display-receipt-ledger-binding-v1", display_receipt
        )
        transaction_id = _transaction_id(
            "display-receipt", display_receipt.display_receipt_id, binding
        )
        timestamp = _later_of(
            _normalized_clock(self._clock), display_receipt.display_completed_at
        )
        receipt = record_c4_stage1_consumed_display_receipt(
            display_receipt,
            external_transaction_id=transaction_id,
            external_transaction_timestamp=timestamp,
        )
        self._insert_receipt(
            table="display_receipt_uses",
            ledger_key=display_receipt.display_receipt_id,
            binding_sha256=binding,
            receipt=receipt,
            receipt_id=receipt.consumed_display_receipt_id,
            receipt_sha256=receipt.consumed_display_receipt_sha256,
            transaction_id=transaction_id,
            replay_message="C4 Stage 1 display receipt replay",
            stateful_request=stateful_request,
            result_payload=_model_payload(receipt),
            effect_kind="consumed-display-receipt",
        )
        return receipt

    def verify_consumed_display_receipt(
        self,
        *,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_receipt: C4Stage1ConsumedDisplayReceipt,
    ) -> bool:
        try:
            display_receipt = _canonical_model(
                display_receipt, C4Stage1DisplayExecutionReceipt
            )
            consumed_receipt = _canonical_model(
                consumed_receipt, C4Stage1ConsumedDisplayReceipt
            )
            if not self.verify_consumed_display_attestation(
                display_policy=display_receipt.display_attester_policy,
                context=display_receipt.context,
                acknowledgement=display_receipt.acknowledgement,
                attestation=display_receipt.display_attestation,
                consumed_receipt=display_receipt.consumed_display_attestation,
            ):
                return False
            binding = _binding_sha256(
                "c4-stage1-display-receipt-ledger-binding-v1", display_receipt
            )
            expected = record_c4_stage1_consumed_display_receipt(
                display_receipt,
                external_transaction_id=consumed_receipt.external_transaction_id,
                external_transaction_timestamp=(
                    consumed_receipt.external_transaction_timestamp
                ),
            )
        except (TypeError, ValueError, C4Stage1ReviewServiceError):
            return False
        return expected == consumed_receipt and self._receipt_is_live(
            table="display_receipt_uses",
            ledger_key=display_receipt.display_receipt_id,
            binding_sha256=binding,
            receipt=consumed_receipt,
            receipt_id=consumed_receipt.consumed_display_receipt_id,
            receipt_sha256=consumed_receipt.consumed_display_receipt_sha256,
            transaction_id=consumed_receipt.external_transaction_id,
        )

    def consume_operator_policy_once(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
        _stateful_request: _C4Stage1StatefulOperationRequest | None = None,
    ) -> C4Stage1ConsumedOperatorPolicyReceipt:
        allow_durable_delivery_recovery = _stateful_request is not None
        if _stateful_request is None:
            _stateful_request = self._stateful_request_from_payload(
                "consume_operator_policy",
                {
                    "operator_policy": _model_payload(operator_policy),
                    "attestation": _model_payload(attestation),
                },
            )
        with self._cohort_lock:
            if (
                self._signing_cohort_latch is None
                or not self.verify_operator_attestation(
                    operator_policy=operator_policy, attestation=attestation
                )
            ):
                raise ValueError(
                    "C4 Stage 1 operator policy is not in a completed signing cohort"
                )
            operator_policy = _canonical_model(
                operator_policy, C4HumanReviewOperatorPolicy
            )
            attestation = _canonical_model(
                attestation, C4Stage1HumanReviewOperatorAttestation
            )
            binding = _binding_sha256(
                "c4-stage1-operator-policy-ledger-binding-v1",
                operator_policy,
                attestation,
            )
            with self._pending_lock:
                pending_receipt = self._pending_operator_policy_deliveries.get(
                    operator_policy.policy_id
                )
            if pending_receipt is None and not allow_durable_delivery_recovery:
                raise ValueError("C4 Stage 1 operator policy replay")
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT binding_sha256, receipt_id, receipt_sha256,
                           transaction_id, receipt_json
                    FROM operator_policy_uses
                    WHERE ledger_key = ?
                    """,
                    (operator_policy.policy_id,),
                ).fetchone()
                if row is None:
                    raise ValueError(
                        "C4 Stage 1 completed operator policy receipt is missing"
                    )
                try:
                    receipt = C4Stage1ConsumedOperatorPolicyReceipt.model_validate_json(
                        row[4]
                    )
                except Exception:
                    raise ValueError(
                        "C4 Stage 1 completed operator policy receipt is invalid"
                    ) from None
                if (
                    row[:4]
                    != (
                        binding,
                        receipt.consumed_operator_receipt_id,
                        receipt.consumed_operator_receipt_sha256,
                        receipt.external_transaction_id,
                    )
                    or receipt.canonical_json_bytes() != row[4]
                ):
                    raise ValueError(
                        "C4 Stage 1 completed operator policy receipt changed"
                    )
                expected = record_c4_stage1_consumed_operator_policy_receipt(
                    operator_policy,
                    attestation,
                    external_transaction_id=receipt.external_transaction_id,
                    external_transaction_timestamp=(
                        receipt.external_transaction_timestamp
                    ),
                )
                if expected != receipt or (
                    pending_receipt is not None and pending_receipt != receipt
                ):
                    raise ValueError(
                        "C4 Stage 1 completed operator policy receipt changed"
                    )
                self._complete_stateful_result(
                    connection,
                    _stateful_request,
                    _model_payload(receipt),
                    effect_kind="consumed-operator-policy",
                    effect_id=receipt.consumed_operator_receipt_id,
                    effect_sha256=receipt.consumed_operator_receipt_sha256,
                    completed_at=_normalized_clock(self._clock),
                )
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            finally:
                connection.close()
            with self._pending_lock:
                delivered = self._pending_operator_policy_deliveries.pop(
                    operator_policy.policy_id, None
                )
                if delivered is not None and delivered != receipt:
                    raise ValueError(
                        "C4 Stage 1 completed operator policy receipt changed"
                    )
            return receipt

    def verify_consumed_operator_policy(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
        consumed_receipt: C4Stage1ConsumedOperatorPolicyReceipt,
    ) -> bool:
        if not self.verify_operator_attestation(
            operator_policy=operator_policy, attestation=attestation
        ):
            return False
        try:
            operator_policy = _canonical_model(
                operator_policy, C4HumanReviewOperatorPolicy
            )
            attestation = _canonical_model(
                attestation, C4Stage1HumanReviewOperatorAttestation
            )
            consumed_receipt = _canonical_model(
                consumed_receipt, C4Stage1ConsumedOperatorPolicyReceipt
            )
            binding = _binding_sha256(
                "c4-stage1-operator-policy-ledger-binding-v1",
                operator_policy,
                attestation,
            )
            expected = record_c4_stage1_consumed_operator_policy_receipt(
                operator_policy,
                attestation,
                external_transaction_id=consumed_receipt.external_transaction_id,
                external_transaction_timestamp=(
                    consumed_receipt.external_transaction_timestamp
                ),
            )
        except (TypeError, ValueError, C4Stage1ReviewServiceError):
            return False
        return expected == consumed_receipt and self._receipt_is_live(
            table="operator_policy_uses",
            ledger_key=operator_policy.policy_id,
            binding_sha256=binding,
            receipt=consumed_receipt,
            receipt_id=consumed_receipt.consumed_operator_receipt_id,
            receipt_sha256=consumed_receipt.consumed_operator_receipt_sha256,
            transaction_id=consumed_receipt.external_transaction_id,
        )


class C4Stage1ReviewDisplayPort:
    """Concrete ``C4Stage1TrustedDisplayPort`` adapter."""

    def __init__(self, endpoint: _ReviewEndpoint) -> None:
        self._endpoint = endpoint

    def display(
        self,
        *,
        context: C4Stage1DisplayContext,
        display_policy: C4Stage1DisplayAttesterPolicy,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
    ) -> C4Stage1DisplayPortResult:
        return self._endpoint.display(
            context=context,
            display_policy=display_policy,
            source_png_bytes=source_png_bytes,
            outputs=outputs,
        )


class C4Stage1ReviewDisplayAttestationVerifier:
    """Concrete external keyed verifier plus attestation-ledger adapter."""

    def __init__(self, endpoint: _ReviewEndpoint) -> None:
        self._endpoint = endpoint

    def verify_attestation(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> bool:
        return self._endpoint.verify_display_attestation(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
        )

    def consume_once(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> C4Stage1ConsumedDisplayAttestation:
        return self._endpoint.consume_display_attestation_once(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
        )

    def verify_consumed_use(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
        consumed_receipt: C4Stage1ConsumedDisplayAttestation,
    ) -> bool:
        return self._endpoint.verify_consumed_display_attestation(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
            consumed_receipt=consumed_receipt,
        )


class C4Stage1ReviewDisplayReceiptLedger:
    """Concrete external display-receipt consume-once adapter."""

    def __init__(self, endpoint: _ReviewEndpoint) -> None:
        self._endpoint = endpoint

    def consume_once(
        self, *, display_receipt: C4Stage1DisplayExecutionReceipt
    ) -> C4Stage1ConsumedDisplayReceipt:
        return self._endpoint.consume_display_receipt_once(
            display_receipt=display_receipt
        )

    def verify_consumed_use(
        self,
        *,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_receipt: C4Stage1ConsumedDisplayReceipt,
    ) -> bool:
        return self._endpoint.verify_consumed_display_receipt(
            display_receipt=display_receipt,
            consumed_receipt=consumed_receipt,
        )


class C4Stage1ReviewOperatorPolicyLedger:
    """Concrete external used-policy consume-once adapter."""

    def __init__(self, endpoint: _ReviewEndpoint) -> None:
        self._endpoint = endpoint

    def consume_once(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> C4Stage1ConsumedOperatorPolicyReceipt:
        return self._endpoint.consume_operator_policy_once(
            operator_policy=operator_policy, attestation=attestation
        )

    def verify_consumed_use(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
        consumed_receipt: C4Stage1ConsumedOperatorPolicyReceipt,
    ) -> bool:
        return self._endpoint.verify_consumed_operator_policy(
            operator_policy=operator_policy,
            attestation=attestation,
            consumed_receipt=consumed_receipt,
        )


class C4Stage1ReviewOperatorAttestationVerifier:
    """External operator-HMAC signer/verifier that never releases either key."""

    def __init__(self, endpoint: _ReviewEndpoint) -> None:
        self._endpoint = endpoint

    def sign_claim_cohort(
        self,
        *,
        reviews: tuple[
            C4Stage1OperatorSigningRequest,
            C4Stage1OperatorSigningRequest,
        ],
    ) -> tuple[
        C4Stage1HumanReviewOperatorAttestation,
        C4Stage1HumanReviewOperatorAttestation,
    ]:
        return self._endpoint.sign_operator_claim_cohort(
            reviews=reviews,
        )

    def verify_attestation(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> bool:
        return self._endpoint.verify_operator_attestation(
            operator_policy=operator_policy, attestation=attestation
        )


def _model_payload(value: BaseModel) -> dict[str, object]:
    return value.model_dump(mode="json", round_trip=True)


def _visible_output_payload(value: C4Stage1VisibleOutput) -> dict[str, object]:
    if not isinstance(value, C4Stage1VisibleOutput):
        raise TypeError("C4 Stage 1 visible output has the wrong type")
    return {
        "blind_code": value.blind_code,
        "blind_order_sha256": value.blind_order_sha256,
        "instruction": value.instruction,
        "instruction_sha256": value.instruction_sha256,
        "output_sha256": value.output_sha256,
        "png_base64": base64.b64encode(value.png_bytes).decode("ascii"),
    }


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON member")
        value[key] = item
    return value


def _decode_json(value: bytes) -> object:
    try:
        return json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-finite JSON value")
            ),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review IPC payload is invalid"
        ) from None


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise C4Stage1ReviewServiceError(f"C4 Stage 1 {label} must be an object")
    return value


def _parse_model(
    payload: Mapping[str, object], key: str, model_type: type[_ModelT]
) -> _ModelT:
    try:
        return model_type.model_validate_json(canonical_json_bytes(payload[key]))
    except (KeyError, TypeError, ValueError):
        raise C4Stage1ReviewServiceError(
            f"C4 Stage 1 review IPC {key} is invalid"
        ) from None


def _parse_visible_outputs(
    value: object,
) -> tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput]:
    if not isinstance(value, list) or len(value) != 2:
        raise C4Stage1ReviewServiceError(
            "C4 Stage 1 review IPC requires two visible outputs"
        )
    parsed: list[C4Stage1VisibleOutput] = []
    expected_keys = {
        "blind_code",
        "blind_order_sha256",
        "instruction",
        "instruction_sha256",
        "output_sha256",
        "png_base64",
    }
    for item in value:
        candidate = _mapping(item, label="visible output")
        if set(candidate) != expected_keys or not all(
            isinstance(candidate[key], str) for key in expected_keys
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC visible output is invalid"
            )
        try:
            png_bytes = base64.b64decode(
                candidate["png_base64"],
                validate=True,  # type: ignore[arg-type]
            )
        except (ValueError, TypeError):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC PNG encoding is invalid"
            ) from None
        parsed.append(
            C4Stage1VisibleOutput(
                blind_code=str(candidate["blind_code"]),
                blind_order_sha256=str(candidate["blind_order_sha256"]),
                instruction=str(candidate["instruction"]),
                instruction_sha256=str(candidate["instruction_sha256"]),
                output_sha256=str(candidate["output_sha256"]),
                png_bytes=png_bytes,
            )
        )
    return parsed[0], parsed[1]


def _dispatch_ipc(
    service: C4Stage1ReviewService,
    operation: str,
    payload: Mapping[str, object],
    *,
    display_cancellation_event: threading.Event | None = None,
    stateful_request: _C4Stage1StatefulOperationRequest | None = None,
) -> object:
    if operation == "readiness":
        if payload:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 readiness request must be empty"
            )
        return _model_payload(service.readiness)
    if operation == "health":
        if payload:
            raise C4Stage1ReviewServiceError("C4 Stage 1 health request must be empty")
        return service.health()
    if operation == "display":
        if set(payload) != {
            "context",
            "display_policy",
            "source_png_base64",
            "outputs",
        }:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 display request has unexpected fields"
            )
        source = payload["source_png_base64"]
        if not isinstance(source, str):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 source PNG encoding is invalid"
            )
        try:
            source_bytes = base64.b64decode(source, validate=True)
        except (ValueError, TypeError):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 source PNG encoding is invalid"
            ) from None
        result = service.display(
            context=_parse_model(payload, "context", C4Stage1DisplayContext),
            display_policy=_parse_model(
                payload, "display_policy", C4Stage1DisplayAttesterPolicy
            ),
            source_png_bytes=source_bytes,
            outputs=_parse_visible_outputs(payload["outputs"]),
            cancellation_event=display_cancellation_event,
            _stateful_request=stateful_request,
        )
        return {
            "acknowledgement": _model_payload(result.acknowledgement),
            "attestation": _model_payload(result.attestation),
        }
    if operation == "take_presentation_submission":
        if set(payload) != {"context_id"} or not isinstance(payload["context_id"], str):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 presenter-submission request is invalid"
            )
        value = service.take_presentation_submission(
            context_id=payload["context_id"],
            _stateful_request=stateful_request,
        )
        return _model_payload(value)
    if operation == "verify_authenticated_submission":
        if set(payload) != {"submission_receipt"}:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 submission verification request is invalid"
            )
        return service.verify_authenticated_submission(
            submission_receipt=_parse_model(
                payload,
                "submission_receipt",
                C4Stage1AuthenticatedPresenterSubmission,
            )
        )
    if operation == "verify_operator_signing_lease":
        if set(payload) != {"operator_signing_lease"}:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing-lease verification request is invalid"
            )
        return service.verify_operator_signing_lease(
            operator_signing_lease=_parse_model(
                payload, "operator_signing_lease", C4Stage1OperatorSigningLease
            )
        )
    if operation == "issue_operator_signing_lease":
        if set(payload) != {
            "operator_policy",
            "submission_receipt",
            "display_receipt",
            "consumed_display_receipt",
        }:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing-lease request has unexpected fields"
            )
        return _model_payload(
            service.issue_operator_signing_lease(
                operator_policy=_parse_model(
                    payload, "operator_policy", C4HumanReviewOperatorPolicy
                ),
                submission_receipt=_parse_model(
                    payload,
                    "submission_receipt",
                    C4Stage1AuthenticatedPresenterSubmission,
                ),
                display_receipt=_parse_model(
                    payload, "display_receipt", C4Stage1DisplayExecutionReceipt
                ),
                consumed_display_receipt=_parse_model(
                    payload,
                    "consumed_display_receipt",
                    C4Stage1ConsumedDisplayReceipt,
                ),
                _stateful_request=stateful_request,
            )
        )
    if operation in {
        "verify_display_attestation",
        "consume_display_attestation",
        "verify_consumed_display_attestation",
    }:
        required = {
            "display_policy",
            "context",
            "acknowledgement",
            "attestation",
        }
        if operation == "verify_consumed_display_attestation":
            required.add("consumed_receipt")
        if set(payload) != required:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 display-attestation request has unexpected fields"
            )
        arguments = {
            "display_policy": _parse_model(
                payload, "display_policy", C4Stage1DisplayAttesterPolicy
            ),
            "context": _parse_model(payload, "context", C4Stage1DisplayContext),
            "acknowledgement": _parse_model(
                payload, "acknowledgement", C4Stage1DisplayPortAcknowledgement
            ),
            "attestation": _parse_model(
                payload, "attestation", C4Stage1DisplayAttestation
            ),
        }
        if operation == "verify_display_attestation":
            return service.verify_display_attestation(**arguments)
        if operation == "consume_display_attestation":
            return _model_payload(
                service.consume_display_attestation_once(
                    **arguments,
                    _stateful_request=stateful_request,
                )
            )
        return service.verify_consumed_display_attestation(
            **arguments,
            consumed_receipt=_parse_model(
                payload,
                "consumed_receipt",
                C4Stage1ConsumedDisplayAttestation,
            ),
        )
    if operation in {"consume_display_receipt", "verify_consumed_display_receipt"}:
        required = {"display_receipt"}
        if operation == "verify_consumed_display_receipt":
            required.add("consumed_receipt")
        if set(payload) != required:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 display-receipt request has unexpected fields"
            )
        display_receipt = _parse_model(
            payload, "display_receipt", C4Stage1DisplayExecutionReceipt
        )
        if operation == "consume_display_receipt":
            return _model_payload(
                service.consume_display_receipt_once(
                    display_receipt=display_receipt,
                    _stateful_request=stateful_request,
                )
            )
        return service.verify_consumed_display_receipt(
            display_receipt=display_receipt,
            consumed_receipt=_parse_model(
                payload, "consumed_receipt", C4Stage1ConsumedDisplayReceipt
            ),
        )
    if operation == "sign_operator_claim_cohort":
        if set(payload) != {"reviews"}:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing cohort request has unexpected fields"
            )
        raw_reviews = payload.get("reviews")
        if type(raw_reviews) is not list or len(raw_reviews) != 2:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing cohort requires exactly two reviews"
            )
        try:
            reviews = tuple(
                C4Stage1OperatorSigningRequest.model_validate_json(
                    canonical_json_bytes(value)
                )
                for value in raw_reviews
            )
        except (TypeError, ValueError):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing cohort request is invalid"
            ) from None
        return [
            _model_payload(attestation)
            for attestation in service.sign_operator_claim_cohort(
                reviews=reviews,  # type: ignore[arg-type]
                _stateful_request=stateful_request,
            )
        ]
    if operation in {
        "verify_operator_attestation",
        "consume_operator_policy",
        "verify_consumed_operator_policy",
    }:
        required = {"operator_policy", "attestation"}
        if operation == "verify_consumed_operator_policy":
            required.add("consumed_receipt")
        if set(payload) != required:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 operator request has unexpected fields"
            )
        operator_policy = _parse_model(
            payload, "operator_policy", C4HumanReviewOperatorPolicy
        )
        attestation = _parse_model(
            payload, "attestation", C4Stage1HumanReviewOperatorAttestation
        )
        if operation == "verify_operator_attestation":
            return service.verify_operator_attestation(
                operator_policy=operator_policy, attestation=attestation
            )
        if operation == "consume_operator_policy":
            return _model_payload(
                service.consume_operator_policy_once(
                    operator_policy=operator_policy,
                    attestation=attestation,
                    _stateful_request=stateful_request,
                )
            )
        return service.verify_consumed_operator_policy(
            operator_policy=operator_policy,
            attestation=attestation,
            consumed_receipt=_parse_model(
                payload,
                "consumed_receipt",
                C4Stage1ConsumedOperatorPolicyReceipt,
            ),
        )
    raise C4Stage1ReviewServiceError("C4 Stage 1 review IPC operation is not supported")


def _dispatch_stateful_ipc(
    service: C4Stage1ReviewService,
    operation: str,
    payload: Mapping[str, object],
    request: _C4Stage1StatefulOperationRequest,
    *,
    display_cancellation_event: threading.Event | None = None,
) -> object:
    if operation == "display":
        with service._stateful_operation_lock:
            cached = service._lookup_stateful_result(request, payload)
        if cached is not None:
            return cached
        return _dispatch_ipc(
            service,
            operation,
            payload,
            display_cancellation_event=display_cancellation_event,
            stateful_request=request,
        )
    with service._stateful_operation_lock:
        cached = service._lookup_stateful_result(request, payload)
        if cached is not None:
            return cached
        return _dispatch_ipc(
            service,
            operation,
            payload,
            display_cancellation_event=display_cancellation_event,
            stateful_request=request,
        )


class _C4Stage1ReviewRequestHandler(socketserver.StreamRequestHandler):
    def _peer_disconnected(self) -> bool:
        try:
            readable, _, _ = select.select([self.connection], [], [], 0)
            if not readable:
                return False
            return self.connection.recv(1, socket.MSG_PEEK) == b""
        except OSError:
            return True

    def _dispatch_authenticated(
        self,
        service: C4Stage1ReviewService,
        operation: str,
        payload: Mapping[str, object],
        stateful_request: _C4Stage1StatefulOperationRequest | None,
    ) -> tuple[object | None, Exception | None, bool]:
        if operation != "display":
            try:
                if stateful_request is not None:
                    result = _dispatch_stateful_ipc(
                        service,
                        operation,
                        payload,
                        stateful_request,
                    )
                else:
                    result = _dispatch_ipc(service, operation, payload)
                return result, None, False
            except Exception as exc:
                return None, exc, False
        if stateful_request is None:
            return (
                None,
                C4Stage1ReviewServiceError(
                    "C4 Stage 1 display request lacks a stateful binding"
                ),
                False,
            )
        try:
            with service._stateful_operation_lock:
                cached = service._lookup_stateful_result(stateful_request, payload)
            if cached is not None:
                return cached, None, False
        except Exception as exc:
            return None, exc, False
        server = self.server  # type: ignore[assignment]
        if not server.try_acquire_display_admission():  # type: ignore[attr-defined]
            return (
                None,
                C4Stage1ReviewServiceError(
                    "C4 Stage 1 display admission is already occupied"
                ),
                False,
            )
        completed = threading.Event()
        request_cancelled = threading.Event()
        outcome: dict[str, object] = {}

        def run() -> None:
            try:
                outcome["result"] = _dispatch_stateful_ipc(
                    service,
                    operation,
                    payload,
                    stateful_request,
                    display_cancellation_event=request_cancelled,
                )
            except Exception as exc:  # noqa: BLE001 - serialized below
                outcome["error"] = exc
            finally:
                completed.set()
                server.release_display_admission()  # type: ignore[attr-defined]

        worker = threading.Thread(target=run, daemon=True)
        try:
            worker.start()
        except BaseException:
            server.release_display_admission()  # type: ignore[attr-defined]
            raise
        deadline = time.monotonic() + service.presenter_session_timeout_seconds
        disconnected = False
        while not completed.wait(0.05):
            disconnected = self._peer_disconnected()
            if disconnected or time.monotonic() >= deadline:
                request_cancelled.set()
                completed.wait(C4_STAGE1_REVIEW_CANCEL_JOIN_TIMEOUT_SECONDS)
                if disconnected:
                    return None, None, True
                return (
                    None,
                    C4Stage1ReviewServiceError(
                        "C4 Stage 1 presentation exceeded its server deadline"
                    ),
                    False,
                )
        error = outcome.get("error")
        return (
            outcome.get("result"),
            error if isinstance(error, Exception) else None,
            False,
        )

    def _read_preauth_header(self) -> bytes | None:
        deadline = time.monotonic() + C4_STAGE1_REVIEW_PREAUTH_TIMEOUT_SECONDS
        raw = bytearray()
        try:
            while len(raw) <= C4_STAGE1_REVIEW_MAX_PREAUTH_HEADER_BYTES:
                value = _recv_before_absolute_deadline(
                    self.connection,
                    deadline=deadline,
                    max_bytes=1,
                )
                if not value:
                    return None
                raw.extend(value)
                if value == b"\n":
                    return (
                        bytes(raw)
                        if len(raw) <= C4_STAGE1_REVIEW_MAX_PREAUTH_HEADER_BYTES
                        else None
                    )
        except (OSError, TimeoutError):
            return None
        return None

    def _read_authenticated_body(self, body_length: int) -> tuple[bytes, str]:
        deadline = (
            time.monotonic() + C4_STAGE1_REVIEW_AUTHENTICATED_BODY_TIMEOUT_SECONDS
        )
        body = bytearray()
        body_hasher = hashlib.sha256()
        remaining = body_length
        while remaining:
            try:
                chunk = _recv_before_absolute_deadline(
                    self.connection,
                    deadline=deadline,
                    max_bytes=min(
                        remaining,
                        C4_STAGE1_REVIEW_BODY_READ_CHUNK_BYTES,
                    ),
                )
            except (OSError, TimeoutError):
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 IPC body exceeded its authenticated deadline"
                ) from None
            if not chunk:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 IPC body ended before its authenticated length"
                )
            body.extend(chunk)
            body_hasher.update(chunk)
            remaining -= len(chunk)
        return bytes(body), body_hasher.hexdigest()

    def handle(self) -> None:
        peer = ipaddress.ip_address(self.client_address[0])
        if not peer.is_loopback:
            return
        raw = self._read_preauth_header()
        if (
            not raw
            or len(raw) > C4_STAGE1_REVIEW_MAX_PREAUTH_HEADER_BYTES
            or not raw.endswith(b"\n")
        ):
            return
        try:
            request = _mapping(_decode_json(raw[:-1]), label="IPC request")
            if canonical_json_bytes(request) != raw[:-1]:
                return
            if set(request) != {
                "schema_version",
                "operation",
                "body_length",
                "body_sha256",
                "nonce",
                "issued_at",
                "request_hmac_sha256",
            }:
                return
            operation = request["operation"]
            body_length = request["body_length"]
            body_sha256 = request["body_sha256"]
            nonce = request["nonce"]
            issued_at = request["issued_at"]
            request_hmac = request["request_hmac_sha256"]
            if (
                request["schema_version"] != C4_STAGE1_REVIEW_IPC_SCHEMA
                or not isinstance(operation, str)
                or type(body_length) is not int
                or not 0 <= body_length <= _c4_stage1_review_ipc_body_limit(operation)
                or not isinstance(body_sha256, str)
                or not isinstance(nonce, str)
                or not isinstance(issued_at, str)
                or not isinstance(request_hmac, str)
            ):
                return
            request_message_sha256 = _sha256(
                c4_stage1_review_ipc_auth_message(
                    operation=operation,
                    body_length=body_length,
                    body_sha256=body_sha256,
                    nonce=nonce,
                    issued_at=issued_at,
                )
            )
            service = self.server.review_service  # type: ignore[attr-defined]
            try:
                authenticated_sha256 = service.authenticate_ipc_request(
                    operation=operation,
                    body_length=body_length,
                    body_sha256=body_sha256,
                    nonce=nonce,
                    issued_at=issued_at,
                    request_hmac_sha256=request_hmac,
                )
                if not hmac.compare_digest(
                    authenticated_sha256, request_message_sha256
                ):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 request binding changed"
                    )
                body_bytes, received_body_sha256 = self._read_authenticated_body(
                    body_length
                )
                if not hmac.compare_digest(received_body_sha256, body_sha256):
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 IPC body differs from its authenticated digest"
                    )
                payload = _mapping(_decode_json(body_bytes), label="IPC payload")
                if canonical_json_bytes(payload) != body_bytes:
                    raise C4Stage1ReviewServiceError(
                        "C4 Stage 1 IPC body is not canonical"
                    )
                stateful_request = (
                    service._stateful_operation_request(
                        operation=operation,
                        body_length=body_length,
                        body_sha256=body_sha256,
                    )
                    if operation in _STATEFUL_OPERATIONS
                    else None
                )
                self.connection.settimeout(None)
                result, dispatch_error, disconnected = self._dispatch_authenticated(
                    service,
                    operation,
                    payload,
                    stateful_request,
                )
                if disconnected:
                    return
                if dispatch_error is not None:
                    raise dispatch_error
                response = service.build_authenticated_ipc_response(
                    operation=operation,
                    request_nonce=nonce,
                    request_message_sha256=request_message_sha256,
                    ok=True,
                    result=result,
                )
            except Exception as exc:
                message = (
                    str(exc)
                    if isinstance(
                        exc, (C4Stage1ReviewServiceError, ValueError, TypeError)
                    )
                    else "C4 Stage 1 review service request failed"
                )
                response = service.build_authenticated_ipc_response(
                    operation=operation,
                    request_nonce=nonce,
                    request_message_sha256=request_message_sha256,
                    ok=False,
                    error=message,
                )
        except Exception:
            return
        encoded = canonical_json_bytes(response) + b"\n"
        if len(encoded) <= C4_STAGE1_REVIEW_MAX_IPC_BYTES:
            try:
                self.connection.settimeout(C4_STAGE1_REVIEW_RESPONSE_TIMEOUT_SECONDS)
                self.wfile.write(encoded)
            except OSError:
                return


class _C4Stage1LoopbackTcpServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = False
    daemon_threads = True
    block_on_close = False
    request_queue_size = C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._request_slots = threading.BoundedSemaphore(
            C4_STAGE1_REVIEW_MAX_CONCURRENT_CONNECTIONS
        )
        self._display_admission = threading.BoundedSemaphore(1)
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def try_acquire_display_admission(self) -> bool:
        return self._display_admission.acquire(blocking=False)

    def release_display_admission(self) -> None:
        self._display_admission.release()

    def process_request(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        if not self._request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._request_slots.release()
            self.shutdown_request(request)
            raise

    def process_request_thread(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


class C4Stage1ReviewServiceServer:
    """Single-process loopback JSON server for one review service core."""

    def __init__(
        self,
        service: C4Stage1ReviewService,
        *,
        host: str = C4_STAGE1_REVIEW_LOOPBACK_HOST,
        port: int = 0,
    ) -> None:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review server host must be a loopback IP"
            ) from None
        if not address.is_loopback or address.version != 4:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review server is IPv4-loopback only"
            )
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("C4 Stage 1 review server port is invalid")
        server = _C4Stage1LoopbackTcpServer(
            (str(address), port), _C4Stage1ReviewRequestHandler
        )
        server.review_service = service  # type: ignore[attr-defined]
        self._server = server
        self._service = service

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address
        return str(host), int(port)

    def serve_forever(self) -> None:
        self._server.serve_forever(poll_interval=0.1)

    def shutdown(self) -> None:
        self._server.shutdown()

    def close(self) -> None:
        self._server.server_close()
        self._service.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()


class C4Stage1ReviewServiceClient:
    """Loopback client implementing the endpoint consumed by all four adapters."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        auth_secret_path: str | Path,
        timeout_seconds: float = 3_606.0,
        presenter_timeout_ms: int = C4_STAGE1_REVIEW_DEFAULT_PRESENTER_TIMEOUT_MS,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review client host must be a loopback IP"
            ) from None
        if not address.is_loopback or address.version != 4:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review client is IPv4-loopback only"
            )
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("C4 Stage 1 review client port is invalid")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not 0
            < float(timeout_seconds)
            <= C4_STAGE1_REVIEW_MAX_IPC_TIMEOUT_SECONDS
        ):
            raise ValueError("C4 Stage 1 review client timeout is invalid")
        if (
            type(presenter_timeout_ms) is not int
            or not 1_000 <= presenter_timeout_ms <= 4 * 60 * 60 * 1000
        ):
            raise ValueError("C4 Stage 1 presenter timeout is invalid")
        timeout_margin = float(timeout_seconds) - (presenter_timeout_ms / 1000.0)
        if not (
            C4_STAGE1_REVIEW_CLIENT_TIMEOUT_MARGIN_SECONDS <= timeout_margin <= 60.0
        ):
            raise ValueError(
                "C4 Stage 1 client timeout must exceed the presenter deadline "
                "by a bounded margin"
            )
        auth_path = Path(auth_secret_path).expanduser()
        if not auth_path.is_absolute() or auth_path != _absolute_lexical(auth_path):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 IPC auth path must be lexical absolute"
            )
        _assert_safe_existing_ancestry(auth_path.parent)
        auth_secret = _stable_read_secret(auth_path)
        if not callable(clock):
            raise TypeError("C4 Stage 1 review client clock must be callable")
        self._address = str(address), port
        self._timeout_seconds = float(timeout_seconds)
        self._presenter_timeout_ms = presenter_timeout_ms
        self._auth_secret_path = auth_path
        self._auth_secret = auth_secret
        self._clock = clock

    def _call(self, operation: str, payload: Mapping[str, object]) -> object:
        current_auth_secret = _stable_read_secret(self._auth_secret_path)
        if not hmac.compare_digest(current_auth_secret, self._auth_secret):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 IPC auth secret changed after client initialization"
            )
        body = canonical_json_bytes(dict(payload))
        body_limit = _c4_stage1_review_ipc_body_limit(operation)
        if len(body) > body_limit:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC request body exceeds its operation bound"
            )
        body_sha256 = _sha256(body)
        attempts = 2 if operation in _STATEFUL_OPERATIONS else 1
        response_bytes = b""
        nonce = ""
        request_message_sha256 = ""
        for attempt in range(attempts):
            nonce = secrets.token_hex(32)
            issued_at = _normalized_clock(self._clock).isoformat()
            request_message = c4_stage1_review_ipc_auth_message(
                operation=operation,
                body_length=len(body),
                body_sha256=body_sha256,
                nonce=nonce,
                issued_at=issued_at,
            )
            request_message_sha256 = _sha256(request_message)
            request_hmac_sha256 = hmac.digest(
                self._auth_secret,
                request_message,
                "sha256",
            ).hex()
            header = (
                canonical_json_bytes(
                    {
                        "schema_version": C4_STAGE1_REVIEW_IPC_SCHEMA,
                        "operation": operation,
                        "body_length": len(body),
                        "body_sha256": body_sha256,
                        "nonce": nonce,
                        "issued_at": issued_at,
                        "request_hmac_sha256": request_hmac_sha256,
                    }
                )
                + b"\n"
            )
            if len(header) > C4_STAGE1_REVIEW_MAX_PREAUTH_HEADER_BYTES:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review IPC authentication header exceeds its bound"
                )
            try:
                with socket.create_connection(
                    self._address, timeout=self._timeout_seconds
                ) as connection:
                    connection.settimeout(self._timeout_seconds)
                    connection.sendall(header)
                    connection.sendall(body)
                    reader = connection.makefile("rb")
                    response_bytes = reader.readline(C4_STAGE1_REVIEW_MAX_IPC_BYTES + 1)
            except OSError:
                if attempt + 1 < attempts:
                    continue
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review service is unavailable"
                ) from None
            if (
                response_bytes
                and len(response_bytes) <= C4_STAGE1_REVIEW_MAX_IPC_BYTES
                and response_bytes.endswith(b"\n")
            ):
                break
            if attempt + 1 >= attempts:
                raise C4Stage1ReviewServiceError(
                    "C4 Stage 1 review IPC response is invalid"
                )
        response = _mapping(_decode_json(response_bytes[:-1]), label="IPC response")
        if canonical_json_bytes(response) != response_bytes[:-1]:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC response is not canonical"
            )
        ok = response.get("ok")
        expected_keys = {
            "schema_version",
            "operation",
            "request_nonce",
            "request_message_sha256",
            "ok",
            "response_hmac_sha256",
            "result" if ok is True else "error",
        }
        if (
            type(ok) is not bool
            or set(response) != expected_keys
            or response.get("schema_version") != C4_STAGE1_REVIEW_IPC_SCHEMA
            or response.get("operation") != operation
            or response.get("request_nonce") != nonce
            or response.get("request_message_sha256") != request_message_sha256
            or not isinstance(response.get("response_hmac_sha256"), str)
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC response binding is invalid"
            )
        response_message = c4_stage1_review_ipc_response_auth_message(
            operation=operation,
            request_nonce=nonce,
            request_message_sha256=request_message_sha256,
            ok=ok,
            result=response.get("result") if ok else None,
            error=response.get("error") if not ok else None,  # type: ignore[arg-type]
        )
        expected_response_hmac = hmac.digest(
            self._auth_secret, response_message, "sha256"
        ).hex()
        if not hmac.compare_digest(
            expected_response_hmac, str(response["response_hmac_sha256"])
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review IPC response authentication failed"
            )
        if ok is not True:
            error = response.get("error")
            raise C4Stage1ReviewServiceError(
                error
                if isinstance(error, str)
                else "C4 Stage 1 review service rejected the request"
            )
        return response["result"]

    @property
    def readiness(self) -> C4Stage1ReviewServiceReadiness:
        receipt = C4Stage1ReviewServiceReadiness.model_validate_json(
            canonical_json_bytes(self._call("readiness", {}))
        )
        if not hmac.compare_digest(
            receipt.ipc_auth_key_commitment_sha256, _sha256(self._auth_secret)
        ) or (
            receipt.presenter_session_timeout_ms != self._presenter_timeout_ms
            or receipt.ipc_response_auth_required is not True
        ):
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 client contract differs from service readiness"
            )
        return receipt

    def health(self) -> dict[str, object]:
        return dict(_mapping(self._call("health", {}), label="health response"))

    def display(
        self,
        *,
        context: C4Stage1DisplayContext,
        display_policy: C4Stage1DisplayAttesterPolicy,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
    ) -> C4Stage1DisplayPortResult:
        result = _mapping(
            self._call(
                "display",
                {
                    "context": _model_payload(context),
                    "display_policy": _model_payload(display_policy),
                    "source_png_base64": base64.b64encode(source_png_bytes).decode(
                        "ascii"
                    ),
                    "outputs": [_visible_output_payload(item) for item in outputs],
                },
            ),
            label="display response",
        )
        if set(result) != {"acknowledgement", "attestation"}:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 review display response has unexpected fields"
            )
        return C4Stage1DisplayPortResult(
            acknowledgement=C4Stage1DisplayPortAcknowledgement.model_validate_json(
                canonical_json_bytes(result["acknowledgement"])
            ),
            attestation=C4Stage1DisplayAttestation.model_validate_json(
                canonical_json_bytes(result["attestation"])
            ),
        )

    def take_presentation_submission(
        self, *, context_id: str
    ) -> C4Stage1AuthenticatedPresenterSubmission:
        return C4Stage1AuthenticatedPresenterSubmission.model_validate_json(
            canonical_json_bytes(
                self._call(
                    "take_presentation_submission",
                    {"context_id": context_id},
                )
            )
        )

    def verify_authenticated_submission(
        self, *, submission_receipt: C4Stage1AuthenticatedPresenterSubmission
    ) -> bool:
        return (
            self._call(
                "verify_authenticated_submission",
                {"submission_receipt": _model_payload(submission_receipt)},
            )
            is True
        )

    def issue_operator_signing_lease(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        submission_receipt: C4Stage1AuthenticatedPresenterSubmission,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_display_receipt: C4Stage1ConsumedDisplayReceipt,
    ) -> C4Stage1OperatorSigningLease:
        return C4Stage1OperatorSigningLease.model_validate_json(
            canonical_json_bytes(
                self._call(
                    "issue_operator_signing_lease",
                    {
                        "operator_policy": _model_payload(operator_policy),
                        "submission_receipt": _model_payload(submission_receipt),
                        "display_receipt": _model_payload(display_receipt),
                        "consumed_display_receipt": _model_payload(
                            consumed_display_receipt
                        ),
                    },
                )
            )
        )

    def verify_operator_signing_lease(
        self, *, operator_signing_lease: C4Stage1OperatorSigningLease
    ) -> bool:
        return (
            self._call(
                "verify_operator_signing_lease",
                {"operator_signing_lease": _model_payload(operator_signing_lease)},
            )
            is True
        )

    @staticmethod
    def _display_attestation_payload(
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> dict[str, object]:
        return {
            "display_policy": _model_payload(display_policy),
            "context": _model_payload(context),
            "acknowledgement": _model_payload(acknowledgement),
            "attestation": _model_payload(attestation),
        }

    def verify_display_attestation(self, **kwargs: object) -> bool:
        return (
            self._call(
                "verify_display_attestation",
                self._display_attestation_payload(**kwargs),  # type: ignore[arg-type]
            )
            is True
        )

    def consume_display_attestation_once(
        self, **kwargs: object
    ) -> C4Stage1ConsumedDisplayAttestation:
        return C4Stage1ConsumedDisplayAttestation.model_validate_json(
            canonical_json_bytes(
                self._call(
                    "consume_display_attestation",
                    self._display_attestation_payload(  # type: ignore[arg-type]
                        **kwargs
                    ),
                )
            )
        )

    def verify_consumed_display_attestation(
        self,
        *,
        consumed_receipt: C4Stage1ConsumedDisplayAttestation,
        **kwargs: object,
    ) -> bool:
        payload = self._display_attestation_payload(**kwargs)  # type: ignore[arg-type]
        payload["consumed_receipt"] = _model_payload(consumed_receipt)
        return self._call("verify_consumed_display_attestation", payload) is True

    def consume_display_receipt_once(
        self, *, display_receipt: C4Stage1DisplayExecutionReceipt
    ) -> C4Stage1ConsumedDisplayReceipt:
        return C4Stage1ConsumedDisplayReceipt.model_validate_json(
            canonical_json_bytes(
                self._call(
                    "consume_display_receipt",
                    {"display_receipt": _model_payload(display_receipt)},
                )
            )
        )

    def verify_consumed_display_receipt(
        self,
        *,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_receipt: C4Stage1ConsumedDisplayReceipt,
    ) -> bool:
        return (
            self._call(
                "verify_consumed_display_receipt",
                {
                    "display_receipt": _model_payload(display_receipt),
                    "consumed_receipt": _model_payload(consumed_receipt),
                },
            )
            is True
        )

    def sign_operator_claim_cohort(
        self,
        *,
        reviews: tuple[
            C4Stage1OperatorSigningRequest,
            C4Stage1OperatorSigningRequest,
        ],
    ) -> tuple[
        C4Stage1HumanReviewOperatorAttestation,
        C4Stage1HumanReviewOperatorAttestation,
    ]:
        result = self._call(
            "sign_operator_claim_cohort",
            {"reviews": [_model_payload(review) for review in reviews]},
        )
        if type(result) is not list or len(result) != 2:
            raise C4Stage1ReviewServiceError(
                "C4 Stage 1 signing cohort response is invalid"
            )
        return tuple(
            C4Stage1HumanReviewOperatorAttestation.model_validate_json(
                canonical_json_bytes(value)
            )
            for value in result
        )  # type: ignore[return-value]

    def verify_operator_attestation(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> bool:
        return (
            self._call(
                "verify_operator_attestation",
                {
                    "operator_policy": _model_payload(operator_policy),
                    "attestation": _model_payload(attestation),
                },
            )
            is True
        )

    def consume_operator_policy_once(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> C4Stage1ConsumedOperatorPolicyReceipt:
        return C4Stage1ConsumedOperatorPolicyReceipt.model_validate_json(
            canonical_json_bytes(
                self._call(
                    "consume_operator_policy",
                    {
                        "operator_policy": _model_payload(operator_policy),
                        "attestation": _model_payload(attestation),
                    },
                )
            )
        )

    def verify_consumed_operator_policy(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
        consumed_receipt: C4Stage1ConsumedOperatorPolicyReceipt,
    ) -> bool:
        return (
            self._call(
                "verify_consumed_operator_policy",
                {
                    "operator_policy": _model_payload(operator_policy),
                    "attestation": _model_payload(attestation),
                    "consumed_receipt": _model_payload(consumed_receipt),
                },
            )
            is True
        )


__all__ = [
    "C4_STAGE1_REVIEW_DEFAULT_PRESENTER_TIMEOUT_MS",
    "C4_STAGE1_OFFLINE_REVIEW_PRESENTER_ID",
    "C4_STAGE1_OFFLINE_REVIEW_PRESENTER_REVISION",
    "C4_STAGE1_REVIEW_IPC_SCHEMA",
    "C4_STAGE1_REVIEW_IPC_AUTH_FILENAME",
    "C4_STAGE1_REVIEW_LEDGER_SCHEMA",
    "C4_STAGE1_REVIEW_LOOPBACK_HOST",
    "C4_STAGE1_REVIEW_MAX_IPC_TIMEOUT_SECONDS",
    "C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID",
    "C4_STAGE1_REVIEW_PRESENTER_REVISION",
    "C4_STAGE1_REVIEW_READINESS_ID_NAMESPACE",
    "C4_STAGE1_REVIEW_SECRET_BYTES",
    "C4_STAGE1_REVIEW_SERVICE_SCHEMA",
    "C4Stage1AuthenticatedPresenterSubmission",
    "C4Stage1AuthenticatedReviewEnvelope",
    "C4Stage1CompletedSigningCohort",
    "C4Stage1CompletedSigningCohortMember",
    "C4Stage1OperatorSigningRequest",
    "C4Stage1OperatorSigningLease",
    "C4Stage1ReviewRepositoryGateBinding",
    "C4Stage1ReviewDisplayAttestationVerifier",
    "C4Stage1ReviewDisplayPort",
    "C4Stage1ReviewDisplayReceiptLedger",
    "C4Stage1ReviewOperatorAttestationVerifier",
    "C4Stage1ReviewOperatorPolicyLedger",
    "C4Stage1ReviewPresenter",
    "C4Stage1ReviewService",
    "C4Stage1ReviewServiceClient",
    "C4Stage1ReviewServiceError",
    "C4Stage1ReviewServiceReadiness",
    "C4Stage1ReviewServiceServer",
    "c4_stage1_review_ipc_auth_message",
    "c4_stage1_review_ipc_response_auth_message",
]
