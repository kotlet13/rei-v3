from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from rei.emocio.dinov2_encoder import dinov2_base_provider_identity
from rei.emocio.longcat_turbo_editor import longcat_turbo_stage1_spec
from rei.emocio.omnigen_editor import omnigen_stage1_spec
from rei.evaluation.c4_blind_review import (
    C4BlindPresentationManifest,
    C4PresentedPng,
    C4PairHumanJudgment,
    build_c4_blind_human_review_schema,
    build_c4_blind_presentation_manifest,
    build_c4_human_review_operator_policy,
    commit_c4_review_material,
    make_c4_review_option_material,
    prepare_c4_blind_review,
    record_c4_output_human_judgment,
)
from rei.evaluation import c4_stage1_attempt as attempt_module
from rei.evaluation import c4_stage1_review as review_module
from rei.evaluation import c4_stage1_run as run_module
from rei.evaluation.c4_stage1_review import (
    C4Stage1ConsumedDisplayReceipt,
    C4Stage1DisplayAttesterPolicy,
    C4Stage1DisplayCandidatePublicationBinding,
    C4Stage1DisplayExecutionReceipt,
    C4Stage1DisplayPortResult,
    C4Stage1DisplayPublicationBinding,
    C4Stage1ExternalDisplayAttestationVerifierPort,
    C4Stage1ExternalDisplayReceiptLedgerPort,
    C4Stage1ExternalUsedPolicyLedgerPort,
    C4Stage1TrustedDisplayPort,
    C4Stage1VisibleOutput,
    build_c4_stage1_display_attestation,
    build_c4_stage1_display_attester_policy,
    build_c4_stage1_display_port_acknowledgement,
    build_c4_stage1_operator_attestation,
    build_c4_stage1_operator_unsigned_claim,
    c4_stage1_display_attestation_message,
    c4_stage1_display_policy_content_pin,
    c4_stage1_operator_attestation_message,
    cold_verify_c4_stage1_display_execution_receipt,
    consume_c4_stage1_display_receipt_once,
    evaluate_c4_stage1_human_review,
    execute_c4_stage1_display as execute_committed_c4_stage1_display,
    _execute_c4_stage1_display_from_paths as execute_c4_stage1_display,
    record_c4_stage1_consumed_display_attestation,
    record_c4_stage1_consumed_display_receipt,
    record_c4_stage1_consumed_operator_policy_receipt,
    seal_c4_stage1_human_review,
    verify_c4_stage1_operator_attestation,
)
from rei.evaluation.c4_stage1_screen import (
    C4_STAGE1_ADDENDUM_PATH,
    C4_STAGE1_PROTOCOL_PATH,
    C4Stage1ContentPin,
    C4Stage1DinoPolicy,
    C4Stage1DocumentPin,
    C4Stage1ScreenContract,
    C4Stage1SourcePin,
)
from rei.evaluation.c4_stage1_fixture import build_c4_stage1_fixture
from rei.ids import canonical_json_bytes
from rei.ids import content_id
from rei.persistence.artifacts import FileArtifactStore, stored_artifact_id
from rei.providers.protocols import StoredArtifact
from tests.evaluation.test_c4_stage1_run import (
    _Harness,
    _minimal_cold_envelope,
    _prepared_store,
    _run,
)


SECRET = b"stage1-operator-secret-material-001"
ALT_OPERATOR_SECRET = b"stage1-alternate-operator-secret-001"
DISPLAY_SECRET = b"stage1-display-signing-secret-001"
DISPLAY_CSP = "default-src 'self'; object-src 'none'; frame-ancestors 'none'"
_REAL_COLD_PUBLICATION_VERIFIER = review_module._cold_verify_display_publication_binding


@pytest.fixture(autouse=True)
def _model_free_publication_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep legacy display-unit fixtures below the production marker boundary."""

    def verify(store, binding, **kwargs):
        by_option = {
            item.option_id: item.staged_output_storage for item in binding.candidates
        }
        packet = kwargs["packet"]
        return (
            store.artifact_path(binding.run_id, binding.source_storage.relative_path),
            tuple(
                store.artifact_path(
                    binding.run_id,
                    by_option[item.option_id].relative_path,
                )
                for item in packet.outputs
            ),
        )

    monkeypatch.setattr(
        review_module,
        "_cold_verify_display_publication_binding",
        verify,
    )


ROOT = Path(__file__).resolve().parents[2]
STARTED_AT = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)
COMPLETED_AT = STARTED_AT + timedelta(seconds=1)
DISPLAY_TRANSACTION_AT = COMPLETED_AT + timedelta(seconds=1)
REVIEWED_AT = DISPLAY_TRANSACTION_AT + timedelta(seconds=1)
OPERATOR_TRANSACTION_AT = REVIEWED_AT + timedelta(seconds=1)


def _png_bytes(red: int, green: int, blue: int) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    scanline = bytes((0, red, green, blue))

    def chunk(name: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(name)
        checksum = zlib.crc32(payload, checksum) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(payload))
            + name
            + payload
            + struct.pack(">I", checksum)
        )

    return (
        signature
        + chunk(b"IHDR", ihdr_data)
        + chunk(b"IDAT", zlib.compress(scanline))
        + chunk(b"IEND", b"")
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _document_pin(role: str) -> C4Stage1DocumentPin:
    relative_path = (
        C4_STAGE1_PROTOCOL_PATH if role == "protocol" else C4_STAGE1_ADDENDUM_PATH
    )
    return C4Stage1DocumentPin.create(
        role=role,
        relative_path=relative_path,
        payload=(ROOT / relative_path).read_bytes(),
    )


def _content_pin(kind: str, artifact) -> C4Stage1ContentPin:
    domain_id = artifact.schema_id if kind == "review_schema" else artifact.policy_id
    return C4Stage1ContentPin(
        kind=kind,
        artifact_id=domain_id,
        artifact_hash=artifact.content_hash(),
        schema_version=artifact.schema_version,
    )


def _screen_contract(
    schema,
    operator_policy,
    alternate_operator_policy,
    display_policy: C4Stage1DisplayAttesterPolicy,
) -> C4Stage1ScreenContract:
    fixture = build_c4_stage1_fixture()
    return C4Stage1ScreenContract.create(
        protocol=_document_pin("protocol"),
        model_free_addendum=_document_pin("model_free_addendum"),
        fixture=fixture,
        source=C4Stage1SourcePin.create(
            source_png_size_bytes=987_133,
            source_provenance_sha256=(
                "0c4f56b487213c1592ebdde0c69a0b850620bc94add1a910f321fea36107107f"
            ),
        ),
        editor_specs=(
            longcat_turbo_stage1_spec(
                "4a447342e10a7b214f43818e666af6a25b8c757650f7f8b6ff4317fca0f24783"
            ),
            omnigen_stage1_spec(
                "3522d2bb368a4a304045432d6641abb69a4b73d876d8f904d36efe9458998bce"
            ),
        ),
        review_schema=_content_pin("review_schema", schema),
        review_operator_policies=(
            _content_pin("review_operator_policy", operator_policy),
            _content_pin("review_operator_policy", alternate_operator_policy),
        ),
        display_policy=c4_stage1_display_policy_content_pin(display_policy),
        review_runtime=C4Stage1ContentPin(
            kind="review_runtime",
            artifact_id="review-runtime-fixture",
            artifact_hash="c" * 64,
            schema_version="rei-c4-stage1-review-runtime-fixture-v1",
        ),
        review_service_readiness=C4Stage1ContentPin(
            kind="review_service_readiness",
            artifact_id="review-service-readiness-fixture",
            artifact_hash="d" * 64,
            schema_version="rei-c4-stage1-review-service-fixture-v1",
        ),
        telemetry_policy=C4Stage1ContentPin(
            kind="telemetry_policy",
            artifact_id="telemetry-policy-fixture",
            artifact_hash="e" * 64,
            schema_version="rei-c4-stage1-telemetry-policy-fixture-v1",
        ),
        dino_policy=C4Stage1DinoPolicy.create(dinov2_base_provider_identity()),
    )


class FixedClock:
    def __init__(self, *values: datetime):
        self._values = list(values)

    def __call__(self) -> datetime:
        return self._values.pop(0)


class RecordingDisplayPort(C4Stage1TrustedDisplayPort):
    def __init__(
        self,
        *,
        hook=None,
        failure: bool = False,
        partial: bool = False,
        display_secret: bytes = DISPLAY_SECRET,
    ):
        self.hook = hook
        self.failure = failure
        self.partial = partial
        self.display_secret = display_secret
        self.calls = []

    def display(self, *, context, display_policy, source_png_bytes, outputs):
        self.calls.append(
            {
                "context": context,
                "display_policy": display_policy,
                "source_png_bytes": source_png_bytes,
                "outputs": outputs,
            }
        )
        if self.hook is not None:
            self.hook()
        if self.failure:
            raise RuntimeError("local path and provider secret must not escape")
        if self.partial:
            return {"display_execution_completed": False}
        acknowledgement = build_c4_stage1_display_port_acknowledgement(
            context,
            source_png_bytes=source_png_bytes,
            outputs=outputs,
        )
        tag = hmac.digest(
            self.display_secret,
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
        return C4Stage1DisplayPortResult(
            acknowledgement=acknowledgement,
            attestation=attestation,
        )


class DisplayAttestationVerifier(C4Stage1ExternalDisplayAttestationVerifierPort):
    def __init__(self, secret: bytes = DISPLAY_SECRET):
        self._secret = secret
        self._receipts = {}
        self.live = True
        self.verify_calls = 0

    def verify_attestation(
        self, *, display_policy, context, acknowledgement, attestation
    ):
        self.verify_calls += 1
        expected = hmac.digest(
            self._secret,
            c4_stage1_display_attestation_message(
                display_policy, context, acknowledgement
            ),
            "sha256",
        ).hex()
        return (
            self.live
            and _sha256(self._secret)
            == display_policy.display_signing_key_commitment_sha256
            and hmac.compare_digest(expected, attestation.hmac_sha256)
        )

    def consume_once(self, *, display_policy, context, acknowledgement, attestation):
        key = attestation.display_attestation_id
        if key in self._receipts:
            raise ValueError("display attestation replay")
        receipt = record_c4_stage1_consumed_display_attestation(
            display_policy,
            context,
            acknowledgement,
            attestation,
            external_transaction_id=f"display-attestation-tx-{len(self._receipts) + 1}",
            external_transaction_timestamp=DISPLAY_TRANSACTION_AT,
        )
        self._receipts[key] = receipt
        return receipt

    def verify_consumed_use(
        self,
        *,
        display_policy,
        context,
        acknowledgement,
        attestation,
        consumed_receipt,
    ):
        return (
            self.live
            and self._receipts.get(attestation.display_attestation_id)
            == consumed_receipt
        )


class DisplayLedger(C4Stage1ExternalDisplayReceiptLedgerPort):
    def __init__(self):
        self._receipts = {}
        self.live = True
        self.verify_calls = 0

    def consume_once(self, *, display_receipt):
        key = display_receipt.display_receipt_id
        if key in self._receipts:
            raise ValueError("display receipt replay")
        receipt = record_c4_stage1_consumed_display_receipt(
            display_receipt,
            external_transaction_id=f"display-tx-{len(self._receipts) + 1}",
            external_transaction_timestamp=DISPLAY_TRANSACTION_AT,
        )
        self._receipts[key] = receipt
        return receipt

    def verify_consumed_use(self, *, display_receipt, consumed_receipt):
        self.verify_calls += 1
        return (
            self.live
            and self._receipts.get(display_receipt.display_receipt_id)
            == consumed_receipt
        )


class OperatorLedger(C4Stage1ExternalUsedPolicyLedgerPort):
    def __init__(self):
        self._receipts = {}
        self.live = True
        self.verify_calls = 0

    def consume_once(self, *, operator_policy, attestation):
        key = operator_policy.policy_id
        if key in self._receipts:
            raise ValueError("operator policy replay")
        receipt = record_c4_stage1_consumed_operator_policy_receipt(
            operator_policy,
            attestation,
            external_transaction_id=f"operator-tx-{len(self._receipts) + 1}",
            external_transaction_timestamp=OPERATOR_TRANSACTION_AT,
        )
        self._receipts[key] = receipt
        return receipt

    def verify_consumed_use(self, *, operator_policy, attestation, consumed_receipt):
        self.verify_calls += 1
        key = operator_policy.policy_id
        return self.live and self._receipts.get(key) == consumed_receipt


class OperatorAttestationVerifier:
    def __init__(self, secret: bytes = SECRET):
        self._secret = secret
        self.verify_calls = 0

    def sign_claim(self, *, operator_policy, claim):
        assert _sha256(self._secret) == operator_policy.hmac_key_commitment_sha256
        return build_c4_stage1_operator_attestation(
            claim,
            external_hmac_sha256=hmac.digest(
                self._secret,
                c4_stage1_operator_attestation_message(claim),
                "sha256",
            ).hex(),
        )

    def verify_attestation(self, *, operator_policy, attestation):
        self.verify_calls += 1
        expected = hmac.digest(
            self._secret,
            c4_stage1_operator_attestation_message(attestation.claim),
            "sha256",
        ).hex()
        return _sha256(
            self._secret
        ) == operator_policy.hmac_key_commitment_sha256 and hmac.compare_digest(
            expected, attestation.hmac_sha256
        )


@dataclass
class ReviewFixture:
    schema: object
    policy: object
    alternate_policy: object
    display_policy: C4Stage1DisplayAttesterPolicy
    screen_contract: C4Stage1ScreenContract
    display_verifier: DisplayAttestationVerifier
    artifact_store: FileArtifactStore
    publication_binding: C4Stage1DisplayPublicationBinding
    commitment: object
    packet: object
    presentation: object
    source_path: Path
    output_paths: tuple[Path, Path]
    source_bytes: bytes
    output_bytes: tuple[bytes, bytes]


def _fixture(tmp_path: Path, *, suffix: str = "one") -> ReviewFixture:
    root = tmp_path / suffix
    root.mkdir()
    source_bytes = _png_bytes(12, 34, 56)
    by_option = {
        "enter_circle": _png_bytes(200, 30, 40),
        "remain_edge": _png_bytes(20, 180, 60),
    }
    source_path = root / "source.png"
    source_path.write_bytes(source_bytes)
    option_paths = {}
    for option_id, value in by_option.items():
        path = root / f"{option_id}.png"
        path.write_bytes(value)
        option_paths[_sha256(value)] = path

    schema = build_c4_blind_human_review_schema()
    policy = build_c4_human_review_operator_policy(
        schema,
        run_id=f"run-{suffix}",
        candidate_slot_id=f"candidate-{suffix}",
        source_image_sha256=_sha256(source_bytes),
        hmac_key_commitment_sha256=_sha256(SECRET),
    )
    alternate_policy = build_c4_human_review_operator_policy(
        schema,
        run_id=f"run-{suffix}-alternate",
        candidate_slot_id=f"candidate-{suffix}-alternate",
        source_image_sha256=_sha256(source_bytes),
        hmac_key_commitment_sha256=_sha256(ALT_OPERATOR_SECRET),
    )
    display_policy = build_c4_stage1_display_attester_policy(
        policy_nonce=_sha256(f"display-policy-nonce-{suffix}".encode()),
        ui_bundle_sha256=_sha256(f"ui-bundle-{suffix}".encode()),
        content_security_policy=DISPLAY_CSP,
        presenter_implementation_id="rei-c4-stage1-review-ui",
        presenter_revision="ui-revision-1",
        display_attester_id=f"display-attester-{suffix}",
        display_signing_key_commitment_sha256=_sha256(DISPLAY_SECRET),
    )
    screen_contract = _screen_contract(schema, policy, alternate_policy, display_policy)
    options = tuple(
        make_c4_review_option_material(
            option_id=option_id,
            instruction=f"Perform the {option_id} action.",
            output_sha256=_sha256(value),
        )
        for option_id, value in sorted(by_option.items())
    )
    commitment = commit_c4_review_material(
        schema,
        operator_policy=policy,
        source_image_sha256=_sha256(source_bytes),
        renderer_id="hidden-renderer-family",
        model_id="hidden-org/Hidden-Image-Editor",
        model_revision="1" * 40,
        options=options,
    )
    packet = prepare_c4_blind_review(schema, commitment, operator_policy=policy)
    output_paths = tuple(option_paths[item.output_sha256] for item in packet.outputs)
    presentation = build_c4_blind_presentation_manifest(
        packet,
        operator_policy=policy,
        source_png_path=source_path,
        output_png_paths=output_paths,
    )
    output_bytes = tuple(path.read_bytes() for path in output_paths)
    run_id = f"run-{suffix}"
    artifact_store = FileArtifactStore(root / "runs")
    source_storage = artifact_store.write_bytes(
        run_id,
        screen_contract.fixture.source_image.path,
        source_bytes,
        overwrite=False,
    )
    output_storage_by_option = {
        option_id: artifact_store.write_bytes(
            run_id,
            f"emocio/images/worker-{option_id}.png",
            value,
            overwrite=False,
        )
        for option_id, value in by_option.items()
    }
    prepared_sha256 = _sha256(f"prepared-{suffix}".encode())
    prepared_anchor = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=run_id,
            relative_path="diagnostics/c4_stage1_prepared_attempt.json",
            content_sha256=prepared_sha256,
            size_bytes=1,
        ),
        run_id=run_id,
        relative_path="diagnostics/c4_stage1_prepared_attempt.json",
        content_sha256=prepared_sha256,
        size_bytes=1,
    )
    member_id = f"member-publication-{suffix}"
    member_sha256 = _sha256(f"member-body-{suffix}".encode())
    member_storage_sha256 = _sha256(f"member-storage-{suffix}".encode())
    member_storage = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=run_id,
            relative_path=f"diagnostics/{member_id}.member-publication.json",
            content_sha256=member_storage_sha256,
            size_bytes=1,
        ),
        run_id=run_id,
        relative_path=f"diagnostics/{member_id}.member-publication.json",
        content_sha256=member_storage_sha256,
        size_bytes=1,
    )
    publication_binding = C4Stage1DisplayPublicationBinding.create(
        run_id=run_id,
        prepared_attempt_id=f"prepared-attempt-{suffix}",
        prepared_attempt_sha256=prepared_sha256,
        prepared_anchor_storage=prepared_anchor,
        member_publication_receipt_id=member_id,
        member_publication_receipt_sha256=member_sha256,
        member_publication_receipt_storage=member_storage,
        editor_role="primary",
        provider_slot_id=policy.candidate_slot_id,
        source_storage=source_storage,
        candidates=tuple(
            C4Stage1DisplayCandidatePublicationBinding(
                option_id=option_id,
                candidate_receipt_id=f"candidate-{suffix}-{option_id}",
                candidate_receipt_sha256=_sha256(
                    f"candidate-{suffix}-{option_id}".encode()
                ),
                prepared_worker_id=f"prepared-worker-{suffix}-{option_id}",
                prepared_worker_sha256=_sha256(
                    f"prepared-worker-{suffix}-{option_id}".encode()
                ),
                worker_request_id=f"worker-{suffix}-{option_id}",
                worker_request_sha256=_sha256(f"worker-{suffix}-{option_id}".encode()),
                staged_output_storage=output_storage_by_option[option_id],
            )
            for option_id in ("enter_circle", "remain_edge")
        ),  # type: ignore[arg-type]
    )
    return ReviewFixture(
        schema=schema,
        policy=policy,
        alternate_policy=alternate_policy,
        display_policy=display_policy,
        screen_contract=screen_contract,
        display_verifier=DisplayAttestationVerifier(),
        artifact_store=artifact_store,
        publication_binding=publication_binding,
        commitment=commitment,
        packet=packet,
        presentation=presentation,
        source_path=source_path,
        output_paths=output_paths,
        source_bytes=source_bytes,
        output_bytes=output_bytes,
    )


def _display(fixture: ReviewFixture, *, port=None, session="ui-session-1"):
    port = port or RecordingDisplayPort()
    receipt = execute_c4_stage1_display(
        fixture.schema,
        fixture.packet,
        publication_binding=fixture.publication_binding,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        presentation_manifest=fixture.presentation,
        source_png_path=fixture.source_path,
        output_png_paths=fixture.output_paths,
        display_port=port,
        display_attestation_verifier=fixture.display_verifier,
        ui_implementation_id="rei-c4-stage1-review-ui",
        ui_revision="ui-revision-1",
        ui_session_id=session,
        clock=FixedClock(STARTED_AT, COMPLETED_AT),
    )
    return receipt, port


def _judgments(fixture: ReviewFixture, *, uncertain: bool = False):
    outputs = tuple(
        record_c4_output_human_judgment(
            fixture.packet,
            blind_code=reference.blind_code,
            source_subject_present=True,
            identity_preserved=True,
            unchanged_composition_preserved=True,
            option_action_correct=True,
            no_extra_actor=True,
            no_generated_external_evidence_claim=True,
            reviewer_uncertain=uncertain,
        )
        for reference in fixture.packet.outputs
    )
    pair = C4PairHumanJudgment(
        actions_visibly_distinct=True,
        same_source_bytes_confirmed=True,
    )
    return outputs, pair


def _claim_and_attestation(
    fixture: ReviewFixture,
    receipt: C4Stage1DisplayExecutionReceipt,
    consumed_display: C4Stage1ConsumedDisplayReceipt,
    *,
    reviewer="reviewer-1",
    uncertain=False,
    hmac_override=None,
    operator_lease_sha256="a" * 64,
):
    outputs, pair = _judgments(fixture, uncertain=uncertain)
    claim = build_c4_stage1_operator_unsigned_claim(
        fixture.schema,
        fixture.packet,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        presentation_manifest=fixture.presentation,
        display_receipt=receipt,
        consumed_display_receipt=consumed_display,
        reviewer_pseudonym=reviewer,
        review_timestamp=REVIEWED_AT,
        output_judgments=outputs,
        pair_judgment=pair,
        submission_receipt_id="authenticated-submission-receipt-test",
        submission_receipt_sha256="9" * 64,
        operator_signing_lease_id="operator-signing-lease-test",
        operator_signing_lease_sha256=operator_lease_sha256,
    )
    tag = hmac.digest(
        SECRET,
        c4_stage1_operator_attestation_message(claim),
        "sha256",
    ).hex()
    attestation = build_c4_stage1_operator_attestation(
        claim,
        external_hmac_sha256=hmac_override or tag,
    )
    return claim, attestation


def _sealed_flow(
    fixture: ReviewFixture,
    *,
    uncertain=False,
    reviewer="reviewer-1",
):
    receipt, port = _display(fixture)
    display_ledger = DisplayLedger()
    consumed_display = consume_c4_stage1_display_receipt_once(display_ledger, receipt)
    claim, attestation = _claim_and_attestation(
        fixture,
        receipt,
        consumed_display,
        reviewer=reviewer,
        uncertain=uncertain,
    )
    operator_ledger = OperatorLedger()
    submission = seal_c4_stage1_human_review(
        fixture.schema,
        fixture.packet,
        artifact_store=fixture.artifact_store,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        presentation_manifest=fixture.presentation,
        display_receipt=receipt,
        consumed_display_receipt=consumed_display,
        operator_attestation=attestation,
        operator_secret=SECRET,
        display_attestation_verifier=fixture.display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
        source_png_path=fixture.source_path,
        output_png_paths=fixture.output_paths,
    )
    return (
        receipt,
        port,
        display_ledger,
        consumed_display,
        claim,
        attestation,
        operator_ledger,
        submission,
    )


def _readdress_artifact(
    artifact,
    *,
    namespace: str,
    id_field: str,
    sha256_field: str,
    **updates,
):
    body = artifact.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, sha256_field},
    )
    body.update(updates)
    return type(artifact)(
        **{
            id_field: content_id(namespace, body),
            sha256_field: _sha256(canonical_json_bytes(body)),
            **body,
        }
    )


def _directly_construct_readdressed_sealed_submission(submission, mutation: str):
    presentation = submission.presentation_manifest
    context = submission.display_receipt.context
    claim_specific_updates = {}
    context_updates = {}

    def readdress_presentation(**updates):
        nonlocal presentation
        presentation = _readdress_artifact(
            presentation,
            namespace="c4_presentation",
            id_field="presentation_manifest_id",
            sha256_field="presentation_manifest_sha256",
            **updates,
        )
        context_updates.update(
            presentation_manifest_id=presentation.presentation_manifest_id,
            presentation_manifest_sha256=(presentation.presentation_manifest_sha256),
        )

    if mutation == "presentation-packet-sha256":
        readdress_presentation(packet_sha256="f" * 64)
    elif mutation == "presentation-review-schema-id":
        readdress_presentation(review_schema_id="forged-review-schema")
    elif mutation == "presentation-operator-policy-id":
        readdress_presentation(operator_policy_id="forged-operator-policy")
    elif mutation == "presentation-source-sha256":
        source = C4PresentedPng.model_validate(
            {
                **presentation.source.model_dump(mode="python", round_trip=True),
                "image_sha256": "f" * 64,
            }
        )
        readdress_presentation(source=source)
    elif mutation == "presentation-output-sha256":
        outputs = list(presentation.outputs)
        outputs[0] = C4PresentedPng.model_validate(
            {
                **outputs[0].model_dump(mode="python", round_trip=True),
                "image_sha256": "f" * 64,
            }
        )
        readdress_presentation(outputs=tuple(outputs))
    elif mutation == "context-packet-sha256":
        context_updates["packet_sha256"] = "f" * 64
    elif mutation == "context-review-schema-id":
        context_updates["review_schema_id"] = "forged-review-schema"
    elif mutation == "context-operator-policy-id":
        context_updates["operator_policy_id"] = "forged-operator-policy"
    elif mutation == "context-presentation-id":
        context_updates["presentation_manifest_id"] = "forged-presentation"
    elif mutation == "context-presentation-sha256":
        context_updates["presentation_manifest_sha256"] = "f" * 64
    elif mutation == "context-material-id":
        context_updates["material_commitment_id"] = "forged-material"
    elif mutation == "context-material-sha256":
        context_updates["material_commitment_sha256"] = "f" * 64
    elif mutation == "claim-packet-sha256":
        claim_specific_updates["packet_sha256"] = "f" * 64
    elif mutation == "claim-presentation-sha256":
        claim_specific_updates["presentation_manifest_sha256"] = "f" * 64
    elif mutation == "claim-review-schema-id":
        claim_specific_updates["review_schema_id"] = "forged-review-schema"
    else:
        raise AssertionError(f"unknown sealed mutation: {mutation}")

    context = _readdress_artifact(
        context,
        namespace="c4_stage1_display_context",
        id_field="context_id",
        sha256_field="context_sha256",
        **context_updates,
    )
    bundle_sha256 = review_module._exact_bytes_bundle_sha256(
        context=context,
        source_sha256=submission.display_receipt.source.image_sha256,
        output_records=tuple(
            (
                reference.blind_code,
                reference.blind_order_sha256,
                reference.instruction_sha256,
                reference.output_sha256,
            )
            for reference in context.outputs
        ),
    )
    acknowledgement = _readdress_artifact(
        submission.display_receipt.acknowledgement,
        namespace="c4_stage1_display_ack",
        id_field="acknowledgement_id",
        sha256_field="acknowledgement_sha256",
        context_id=context.context_id,
        context_sha256=context.context_sha256,
        received_exact_bytes_bundle_sha256=bundle_sha256,
    )
    display_attestation = build_c4_stage1_display_attestation(
        submission.display_attester_policy,
        context,
        acknowledgement,
        external_hmac_sha256=(
            submission.display_receipt.display_attestation.hmac_sha256
        ),
    )
    consumed_display_attestation = record_c4_stage1_consumed_display_attestation(
        submission.display_attester_policy,
        context,
        acknowledgement,
        display_attestation,
        external_transaction_id=(
            submission.display_receipt.consumed_display_attestation.external_transaction_id
        ),
        external_transaction_timestamp=(
            submission.display_receipt.consumed_display_attestation.external_transaction_timestamp
        ),
    )
    receipt_body = submission.display_receipt.model_dump(
        mode="python",
        round_trip=True,
        exclude={"display_receipt_id", "display_receipt_sha256"},
    )
    receipt_body.update(
        context=context,
        acknowledgement=acknowledgement,
        display_attestation=display_attestation,
        consumed_display_attestation=consumed_display_attestation,
        pre_display_exact_bytes_bundle_sha256=bundle_sha256,
        port_received_exact_bytes_bundle_sha256=bundle_sha256,
        post_display_exact_bytes_bundle_sha256=bundle_sha256,
    )
    display_receipt = C4Stage1DisplayExecutionReceipt(
        display_receipt_id=content_id("c4_stage1_display_receipt", receipt_body),
        display_receipt_sha256=_sha256(canonical_json_bytes(receipt_body)),
        **receipt_body,
    )
    consumed_display = record_c4_stage1_consumed_display_receipt(
        display_receipt,
        external_transaction_id=(
            submission.consumed_display_receipt.external_transaction_id
        ),
        external_transaction_timestamp=(
            submission.consumed_display_receipt.external_transaction_timestamp
        ),
    )
    claim_updates = {
        "packet_id": context.packet_id,
        "packet_sha256": context.packet_sha256,
        "presentation_manifest_id": context.presentation_manifest_id,
        "presentation_manifest_sha256": context.presentation_manifest_sha256,
        "display_attestation_id": display_attestation.display_attestation_id,
        "display_attestation_sha256": display_attestation.display_attestation_sha256,
        "consumed_display_attestation_id": (
            consumed_display_attestation.consumed_display_attestation_id
        ),
        "consumed_display_attestation_sha256": (
            consumed_display_attestation.consumed_display_attestation_sha256
        ),
        "display_receipt_id": display_receipt.display_receipt_id,
        "display_receipt_sha256": display_receipt.display_receipt_sha256,
        "consumed_display_receipt_id": consumed_display.consumed_display_receipt_id,
        "consumed_display_receipt_sha256": (
            consumed_display.consumed_display_receipt_sha256
        ),
        **claim_specific_updates,
    }
    claim = _readdress_artifact(
        submission.operator_attestation.claim,
        namespace="c4_stage1_review_claim",
        id_field="claim_id",
        sha256_field="claim_sha256",
        **claim_updates,
    )
    operator_attestation = build_c4_stage1_operator_attestation(
        claim,
        external_hmac_sha256=submission.operator_attestation.hmac_sha256,
    )
    consumed_operator = record_c4_stage1_consumed_operator_policy_receipt(
        submission.operator_policy,
        operator_attestation,
        external_transaction_id=(
            submission.consumed_operator_receipt.external_transaction_id
        ),
        external_transaction_timestamp=(
            submission.consumed_operator_receipt.external_transaction_timestamp
        ),
    )
    body = submission.model_dump(
        mode="python",
        round_trip=True,
        exclude={"submission_id"},
    )
    body.update(
        presentation_manifest=presentation,
        display_receipt=display_receipt,
        consumed_display_receipt=consumed_display,
        operator_attestation=operator_attestation,
        consumed_operator_receipt=consumed_operator,
    )
    return review_module.C4Stage1SealedHumanReviewSubmission(
        submission_id=content_id("c4_stage1_human_review", body),
        **body,
    )


def test_display_receipt_binds_exact_bytes_without_labels_paths_or_authority(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt, port = _display(fixture)

    assert len(port.calls) == 1
    call = port.calls[0]
    assert call["source_png_bytes"] == fixture.source_bytes
    assert tuple(item.png_bytes for item in call["outputs"]) == fixture.output_bytes
    assert all(isinstance(item, C4Stage1VisibleOutput) for item in call["outputs"])
    assert receipt.display_started_at == STARTED_AT
    assert receipt.display_completed_at == COMPLETED_AT
    assert receipt.pre_display_exact_bytes_bundle_sha256 == (
        receipt.port_received_exact_bytes_bundle_sha256
    )
    assert receipt.post_display_exact_bytes_bundle_sha256 == (
        receipt.pre_display_exact_bytes_bundle_sha256
    )
    assert receipt.display_receipt_proves_human_attention is False
    assert receipt.display_receipt_proves_human_cognition is False
    assert receipt.semantic_quality_gate_passed is False
    assert receipt.production_authority_granted is False
    encoded = receipt.canonical_json_bytes()
    assert str(tmp_path).encode() not in encoded
    assert fixture.commitment.renderer_id.encode() not in encoded
    assert fixture.commitment.model_id.encode() not in encoded
    assert DISPLAY_SECRET not in encoded
    assert DISPLAY_SECRET.hex().encode() not in encoded.lower()
    assert (
        receipt.context.screen_contract_id == fixture.screen_contract.screen_contract_id
    )
    assert receipt.display_attester_policy == fixture.display_policy
    assert receipt.context.ui_bundle_sha256 == fixture.display_policy.ui_bundle_sha256
    assert receipt.context.content_security_policy_sha256 == (
        fixture.display_policy.content_security_policy_sha256
    )
    assert receipt.display_attestation.hmac_sha256
    assert receipt.consumed_display_attestation.external_keyed_hmac_verified is True

    assert (
        cold_verify_c4_stage1_display_execution_receipt(
            receipt,
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )
        == receipt
    )


def test_pre_output_contract_requires_exact_display_policy_pin(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    other_policy = build_c4_stage1_display_attester_policy(
        policy_nonce=_sha256(b"other-display-policy-nonce"),
        ui_bundle_sha256=_sha256(b"other-ui-bundle"),
        content_security_policy=DISPLAY_CSP,
        presenter_implementation_id="rei-c4-stage1-review-ui",
        presenter_revision="ui-revision-1",
        display_attester_id="other-display-attester",
        display_signing_key_commitment_sha256=_sha256(DISPLAY_SECRET),
    )
    port = RecordingDisplayPort()

    with pytest.raises(ValueError, match="pinned by the pre-output contract"):
        execute_c4_stage1_display(
            fixture.schema,
            fixture.packet,
            publication_binding=fixture.publication_binding,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=other_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
            display_port=port,
            display_attestation_verifier=fixture.display_verifier,
            ui_implementation_id="rei-c4-stage1-review-ui",
            ui_revision="ui-revision-1",
            ui_session_id="ui-session-1",
            clock=FixedClock(STARTED_AT, COMPLETED_AT),
        )

    assert port.calls == []


def test_both_distinct_operator_policy_pins_are_usable_without_provider_labels(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    options = tuple(
        make_c4_review_option_material(
            option_id=reference.option_id,
            instruction=reference.instruction,
            output_sha256=reference.output_sha256,
        )
        for reference in sorted(fixture.packet.outputs, key=lambda item: item.option_id)
    )
    commitment = commit_c4_review_material(
        fixture.schema,
        operator_policy=fixture.alternate_policy,
        source_image_sha256=_sha256(fixture.source_bytes),
        renderer_id="second-hidden-renderer",
        model_id="hidden-org/Second-Hidden-Editor",
        model_revision="2" * 40,
        options=options,
    )
    packet = prepare_c4_blind_review(
        fixture.schema,
        commitment,
        operator_policy=fixture.alternate_policy,
    )
    paths_by_hash = {
        _sha256(value): path
        for value, path in zip(fixture.output_bytes, fixture.output_paths, strict=True)
    }
    output_paths = tuple(paths_by_hash[item.output_sha256] for item in packet.outputs)
    presentation = build_c4_blind_presentation_manifest(
        packet,
        operator_policy=fixture.alternate_policy,
        source_png_path=fixture.source_path,
        output_png_paths=output_paths,
    )
    receipt = execute_c4_stage1_display(
        fixture.schema,
        packet,
        publication_binding=fixture.publication_binding,
        operator_policy=fixture.alternate_policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        presentation_manifest=presentation,
        source_png_path=fixture.source_path,
        output_png_paths=output_paths,
        display_port=RecordingDisplayPort(),
        display_attestation_verifier=fixture.display_verifier,
        ui_implementation_id="rei-c4-stage1-review-ui",
        ui_revision="ui-revision-1",
        ui_session_id="ui-session-alternate-policy",
        clock=FixedClock(STARTED_AT, COMPLETED_AT),
    )

    assert len(fixture.screen_contract.review_operator_policies) == 2
    assert receipt.context.operator_policy_id == fixture.alternate_policy.policy_id
    encoded = receipt.canonical_json_bytes()
    assert commitment.renderer_id.encode() not in encoded
    assert commitment.model_id.encode() not in encoded


@pytest.mark.parametrize("attester_id", [DISPLAY_SECRET.decode(), DISPLAY_SECRET.hex()])
def test_display_policy_rejects_direct_signing_secret_material(
    attester_id: str,
) -> None:
    with pytest.raises(ValueError, match="direct signing-secret material"):
        build_c4_stage1_display_attester_policy(
            policy_nonce=_sha256(b"direct-secret-policy-nonce"),
            ui_bundle_sha256=_sha256(b"direct-secret-ui-bundle"),
            content_security_policy=DISPLAY_CSP,
            presenter_implementation_id="rei-c4-stage1-review-ui",
            presenter_revision="ui-revision-1",
            display_attester_id=attester_id,
            display_signing_key_commitment_sha256=_sha256(DISPLAY_SECRET),
        )


def test_display_hmac_and_live_keyed_verifier_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(ValueError, match="external display HMAC verification failed"):
        _display(
            fixture,
            port=RecordingDisplayPort(
                display_secret=b"wrong-display-signing-secret-0001"
            ),
        )
    with pytest.raises(TypeError, match="live external keyed verifier"):
        execute_c4_stage1_display(
            fixture.schema,
            fixture.packet,
            publication_binding=fixture.publication_binding,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
            display_port=RecordingDisplayPort(),
            display_attestation_verifier=object(),
            ui_implementation_id="rei-c4-stage1-review-ui",
            ui_revision="ui-revision-1",
            ui_session_id="ui-session-missing-verifier",
            clock=FixedClock(STARTED_AT, COMPLETED_AT),
        )


def _manifest_from_committed_descriptors(packet, candidates):
    source = C4PresentedPng(
        image_role="source",
        image_sha256=packet.source_image_sha256,
        byte_size=987_133,
        width=1024,
        height=768,
    )
    by_option = {item.option_id: item for item in candidates}
    outputs = tuple(
        C4PresentedPng(
            image_role="output",
            blind_code=reference.blind_code,
            blind_order_sha256=reference.blind_order_sha256,
            image_sha256=reference.output_sha256,
            byte_size=by_option[reference.option_id].staged_png_size_bytes,
            width=1024,
            height=768,
        )
        for reference in packet.outputs
    )
    base = {
        "schema_version": "rei-c4-blind-presentation-manifest-v1",
        "presentation_policy": "c4-byte-verified-png-input-manifest-v1",
        "review_schema_id": packet.review_schema_id,
        "operator_policy_id": packet.operator_policy_id,
        "operator_policy_sha256": packet.operator_policy_sha256,
        "packet_id": packet.packet_id,
        "packet_sha256": packet.packet_sha256,
        "material_commitment_id": packet.material_commitment_id,
        "material_commitment_sha256": packet.material_commitment_sha256,
        "source": source,
        "outputs": outputs,
        "pair_order_policy": "ascending_sha256_of_blind_code",
        "png_chunk_policy": "png-rgb8-rgba8-noninterlaced-no-metadata-v1",
        "embedded_metadata_present": False,
        "renderer_identity_supplied_label_present": False,
        "model_identity_supplied_label_present": False,
        "other_provider_output_supplied_labels_present": False,
        "presentation_ui_policy": "reviewer-ui-omit-provider-labels-v1",
        "presentation_ui_execution_attested": False,
        "pixel_identity_absence_proven": False,
        "cold_validation_reverifies_exact_png_bytes": False,
        "exact_png_bytes_required_for_reverification": True,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    return C4BlindPresentationManifest(
        presentation_manifest_id=content_id("c4_presentation", base),
        presentation_manifest_sha256=hashlib.sha256(
            canonical_json_bytes(base)
        ).hexdigest(),
        **base,
    )


def test_committed_display_wrapper_derives_store_paths_and_rejects_other_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared_outcome, paths = _prepared_store(tmp_path / "publication")
    harness = _Harness(store, prepared_outcome)
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_prepared_attempt",
        lambda *_args, **_kwargs: prepared_outcome,
    )
    outcome = _run(harness, paths)
    prepared = prepared_outcome.prepared_attempt
    primary = next(
        item for item in outcome.manifest.member_runs if item.editor_role == "primary"
    )
    publication_storage = primary.worker_terminals[0].member_publication_receipt_storage
    assert publication_storage is not None
    publication = run_module.cold_verify_c4_stage1_member_publication(
        FileArtifactStore(store.root, create=False),
        publication_storage,
        prepared,
    )
    policy = next(
        item
        for item in prepared.review_operator_policies
        if item.candidate_slot_id == publication.provider_slot_id
    )
    by_option = {item.option_id: item for item in publication.candidate_receipts}
    options = tuple(
        make_c4_review_option_material(
            option_id=option_id,
            instruction=f"Perform the {option_id} action.",
            output_sha256=by_option[option_id].staged_png_sha256,
        )
        for option_id in ("enter_circle", "remain_edge")
    )
    commitment = commit_c4_review_material(
        prepared.review_schema,
        operator_policy=policy,
        source_image_sha256=prepared.screen_contract.source.source_png_sha256,
        renderer_id="hidden-stage1-renderer",
        model_id="hidden-stage1-model",
        model_revision="1" * 40,
        options=options,
    )
    packet = prepare_c4_blind_review(
        prepared.review_schema,
        commitment,
        operator_policy=policy,
    )
    presentation = _manifest_from_committed_descriptors(
        packet, publication.candidate_receipts
    )
    source_relative_path = prepared.screen_contract.fixture.source_image.path
    source_descriptor = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=prepared.run_id,
            relative_path=source_relative_path,
            content_sha256=packet.source_image_sha256,
            size_bytes=987_133,
        ),
        run_id=prepared.run_id,
        relative_path=source_relative_path,
        content_sha256=packet.source_image_sha256,
        size_bytes=987_133,
    )
    consumer_prepared = prepared.model_copy(
        update={
            "artifact_inventory_before_anchor": tuple(
                sorted(
                    (*prepared.artifact_inventory_before_anchor, source_descriptor),
                    key=lambda item: item.relative_path,
                )
            )
        }
    )
    monkeypatch.setattr(
        attempt_module,
        "cold_verify_c4_stage1_prepared_attempt",
        lambda *_args, **_kwargs: SimpleNamespace(
            prepared_attempt=consumer_prepared,
            prepared_anchor_storage=prepared_outcome.prepared_anchor_storage,
        ),
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_member_publication",
        lambda *_args, **_kwargs: publication,
    )
    captured = {}

    def fake_display(*args, **kwargs):
        captured.update(kwargs)
        return "immutable-display-receipt"

    monkeypatch.setattr(
        review_module,
        "_execute_c4_stage1_display_from_paths",
        fake_display,
    )
    result = execute_committed_c4_stage1_display(
        store,
        prepared_outcome.prepared_anchor_storage,
        publication_storage,
        prepared.review_schema,
        packet,
        operator_policy=policy,
        display_attester_policy=prepared.display_policy,
        presentation_manifest=presentation,
        display_port=object(),
        display_attestation_verifier=object(),
        ui_implementation_id=prepared.display_policy.presenter_implementation_id,
        ui_revision=prepared.display_policy.presenter_revision,
        ui_session_id="committed-display-session",
    )
    assert result == "immutable-display-receipt"
    assert captured["publication_binding"].prepared_attempt_id == (
        prepared.prepared_attempt_id
    )
    assert captured["publication_binding"].member_publication_receipt_id == (
        publication.member_publication_receipt_id
    )
    assert tuple(
        item.candidate_receipt_id for item in captured["publication_binding"].candidates
    ) == tuple(item.candidate_receipt_id for item in publication.candidate_receipts)
    assert captured["source_png_path"] == store.artifact_path(
        prepared.run_id, source_relative_path
    )
    assert captured["output_png_paths"] == tuple(
        store.artifact_path(
            prepared.run_id,
            by_option[reference.option_id].staged_output_storage.relative_path,
        )
        for reference in packet.outputs
    )

    alternate_policy = next(
        item for item in prepared.review_operator_policies if item != policy
    )
    with pytest.raises(ValueError):
        execute_committed_c4_stage1_display(
            store,
            prepared_outcome.prepared_anchor_storage,
            publication_storage,
            prepared.review_schema,
            packet,
            operator_policy=alternate_policy,
            display_attester_policy=prepared.display_policy,
            presentation_manifest=presentation,
            display_port=object(),
            display_attestation_verifier=object(),
            ui_implementation_id=prepared.display_policy.presenter_implementation_id,
            ui_revision=prepared.display_policy.presenter_revision,
            ui_session_id="committed-display-session",
        )


def test_display_attestation_replay_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _display(fixture, session="same-ui-session")

    with pytest.raises(ValueError, match="display attestation replay"):
        _display(fixture, session="same-ui-session")


def test_swap_after_manifest_fails_before_display(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture.output_paths[0].write_bytes(_png_bytes(1, 2, 3))
    port = RecordingDisplayPort()

    with pytest.raises(ValueError, match="differs from the blind packet"):
        _display(fixture, port=port)

    assert port.calls == []


def test_bytes_mutated_during_display_fail_post_handle_rehash(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)

    def mutate() -> None:
        fixture.output_paths[0].write_bytes(_png_bytes(2, 3, 4))

    port = RecordingDisplayPort(hook=mutate)
    with pytest.raises(ValueError, match="display bytes changed"):
        _display(fixture, port=port)
    assert len(port.calls) == 1


def test_bytes_mutated_after_display_fail_cold_reverification(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    fixture.output_paths[1].write_bytes(_png_bytes(4, 5, 6))
    by_option = {
        item.option_id: item.staged_output_storage
        for item in fixture.publication_binding.candidates
    }
    storage = by_option[fixture.packet.outputs[1].option_id]
    fixture.artifact_store.artifact_path(
        storage.run_id, storage.relative_path
    ).write_bytes(_png_bytes(4, 5, 6))

    with pytest.raises(ValueError, match="display PNG"):
        cold_verify_c4_stage1_display_execution_receipt(
            receipt,
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )


def test_wrong_blind_path_order_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(ValueError, match="differs from the blind packet"):
        execute_c4_stage1_display(
            fixture.schema,
            fixture.packet,
            publication_binding=fixture.publication_binding,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=tuple(reversed(fixture.output_paths)),
            display_port=RecordingDisplayPort(),
            display_attestation_verifier=fixture.display_verifier,
            ui_implementation_id="rei-c4-stage1-review-ui",
            ui_revision="ui-revision-1",
            ui_session_id="ui-session-1",
            clock=FixedClock(STARTED_AT, COMPLETED_AT),
        )


@pytest.mark.parametrize("failure,partial", [(True, False), (False, True)])
def test_failed_or_partial_display_publishes_no_receipt(
    tmp_path: Path, failure: bool, partial: bool
) -> None:
    fixture = _fixture(tmp_path)
    port = RecordingDisplayPort(failure=failure, partial=partial)
    with pytest.raises((TypeError, ValueError)):
        _display(fixture, port=port)


def test_provider_family_label_in_ui_identifier_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(ValueError, match="provider/model label"):
        execute_c4_stage1_display(
            fixture.schema,
            fixture.packet,
            publication_binding=fixture.publication_binding,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
            display_port=RecordingDisplayPort(),
            display_attestation_verifier=fixture.display_verifier,
            ui_implementation_id="longcat-review-ui",
            ui_revision="ui-revision-1",
            ui_session_id="ui-session-1",
            clock=FixedClock(STARTED_AT, COMPLETED_AT),
        )


def test_cold_model_copy_and_packet_tampering_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    tampered_receipt = receipt.model_copy(update={"partial_display": True})
    with pytest.raises(Exception):
        cold_verify_c4_stage1_display_execution_receipt(
            tampered_receipt,
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )

    tampered_packet = fixture.packet.model_copy(update={"packet_sha256": "0" * 64})
    with pytest.raises(Exception):
        cold_verify_c4_stage1_display_execution_receipt(
            receipt,
            fixture.schema,
            tampered_packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )


def test_display_receipt_external_state_is_one_time_and_live(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    ledger = DisplayLedger()
    consumed = consume_c4_stage1_display_receipt_once(ledger, receipt)
    assert consumed.display_receipt_id == receipt.display_receipt_id

    with pytest.raises(ValueError, match="replay"):
        consume_c4_stage1_display_receipt_once(ledger, receipt)
    with pytest.raises(TypeError, match="external atomic ledger"):
        consume_c4_stage1_display_receipt_once(object(), receipt)


def test_operator_hmac_and_sealed_submission_include_exact_display_receipt(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    (
        receipt,
        _,
        display_ledger,
        consumed_display,
        claim,
        attestation,
        operator_ledger,
        submission,
    ) = _sealed_flow(fixture)

    assert claim.display_receipt_id == receipt.display_receipt_id
    assert claim.display_receipt_sha256 == receipt.display_receipt_sha256
    assert claim.display_policy_id == fixture.display_policy.display_policy_id
    assert claim.display_attestation_id == (
        receipt.display_attestation.display_attestation_id
    )
    assert claim.consumed_display_attestation_id == (
        receipt.consumed_display_attestation.consumed_display_attestation_id
    )
    assert claim.consumed_display_receipt_id == (
        consumed_display.consumed_display_receipt_id
    )
    assert submission.exact_display_receipt_in_operator_hmac is True
    assert submission.separately_keyed_display_attestation_in_operator_hmac is True
    assert submission.display_receipt == receipt
    assert submission.human_review_passed is True
    assert submission.semantic_quality_gate_passed is False
    assert submission.production_authority_granted is False
    assert display_ledger.verify_calls == 1
    assert (
        verify_c4_stage1_operator_attestation(
            fixture.policy, attestation, operator_secret=SECRET
        )
        == attestation
    )

    gate = evaluate_c4_stage1_human_review(
        fixture.schema,
        fixture.packet,
        artifact_store=fixture.artifact_store,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        operator_secret=SECRET,
        display_attestation_verifier=fixture.display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
        submission=submission,
        source_png_path=fixture.source_path,
        output_png_paths=fixture.output_paths,
    )
    assert gate.human_review_passed is True
    assert gate.semantic_quality_gate_passed is False
    assert display_ledger.verify_calls == 2
    assert operator_ledger.verify_calls == 1
    encoded = submission.canonical_json_bytes()
    assert SECRET not in encoded
    assert SECRET.hex().encode() not in encoded.lower()
    assert str(tmp_path).encode() not in encoded


@pytest.mark.parametrize(
    "mutation",
    (
        "presentation-packet-sha256",
        "presentation-review-schema-id",
        "presentation-operator-policy-id",
        "presentation-source-sha256",
        "presentation-output-sha256",
        "context-packet-sha256",
        "context-review-schema-id",
        "context-operator-policy-id",
        "context-presentation-id",
        "context-presentation-sha256",
        "context-material-id",
        "context-material-sha256",
        "claim-packet-sha256",
        "claim-presentation-sha256",
        "claim-review-schema-id",
    ),
)
def test_direct_sealed_model_rejects_readdressed_cross_artifact_bindings(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _fixture(tmp_path)
    *_, submission = _sealed_flow(fixture)

    with pytest.raises(ValueError, match="sealed review differs"):
        _directly_construct_readdressed_sealed_submission(submission, mutation)


def test_external_operator_verifier_keeps_secret_out_of_seal_and_gate(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    display_ledger = DisplayLedger()
    consumed_display = consume_c4_stage1_display_receipt_once(display_ledger, receipt)
    claim, _ = _claim_and_attestation(fixture, receipt, consumed_display)
    verifier = OperatorAttestationVerifier()
    attestation = verifier.sign_claim(
        operator_policy=fixture.policy,
        claim=claim,
    )
    operator_ledger = OperatorLedger()
    submission = seal_c4_stage1_human_review(
        fixture.schema,
        fixture.packet,
        artifact_store=fixture.artifact_store,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        presentation_manifest=fixture.presentation,
        display_receipt=receipt,
        consumed_display_receipt=consumed_display,
        operator_attestation=attestation,
        operator_secret=None,
        operator_attestation_verifier=verifier,
        display_attestation_verifier=fixture.display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
    )
    gate = evaluate_c4_stage1_human_review(
        fixture.schema,
        fixture.packet,
        artifact_store=fixture.artifact_store,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        operator_secret=None,
        operator_attestation_verifier=verifier,
        display_attestation_verifier=fixture.display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
        submission=submission,
    )

    assert gate.human_review_passed is True
    assert verifier.verify_calls == 2
    assert SECRET not in submission.canonical_json_bytes()


def test_breaking_stage1_review_artifact_family_uses_v2_schemas(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    (
        _,
        _,
        display_ledger,
        _,
        claim,
        attestation,
        operator_ledger,
        submission,
    ) = _sealed_flow(fixture)
    gate = evaluate_c4_stage1_human_review(
        fixture.schema,
        fixture.packet,
        artifact_store=fixture.artifact_store,
        operator_policy=fixture.policy,
        screen_contract=fixture.screen_contract,
        display_attester_policy=fixture.display_policy,
        operator_secret=SECRET,
        display_attestation_verifier=fixture.display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
        submission=submission,
    )
    artifacts = (
        (
            claim,
            "rei-c4-stage1-human-review-unsigned-claim-v2",
            "rei-c4-stage1-human-review-unsigned-claim-v1",
        ),
        (
            attestation,
            "rei-c4-stage1-human-review-attestation-v2",
            "rei-c4-stage1-human-review-attestation-v1",
        ),
        (
            submission.consumed_operator_receipt,
            "rei-c4-stage1-consumed-operator-policy-v2",
            "rei-c4-stage1-consumed-operator-policy-v1",
        ),
        (
            submission,
            "rei-c4-stage1-sealed-human-review-v2",
            "rei-c4-stage1-sealed-human-review-v1",
        ),
        (
            gate,
            "rei-c4-stage1-human-review-gate-v2",
            "rei-c4-stage1-human-review-gate-v1",
        ),
    )

    for artifact, expected_schema, legacy_schema in artifacts:
        assert artifact.schema_version == expected_schema
        legacy = artifact.model_dump(mode="python", round_trip=True)
        legacy["schema_version"] = legacy_schema
        with pytest.raises(ValueError):
            type(artifact).model_validate(legacy)


def test_raw_path_receipt_without_live_member_marker_cannot_be_sealed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    display_ledger = DisplayLedger()
    consumed = consume_c4_stage1_display_receipt_once(display_ledger, receipt)
    _, attestation = _claim_and_attestation(fixture, receipt, consumed)
    monkeypatch.setattr(
        review_module,
        "_cold_verify_display_publication_binding",
        _REAL_COLD_PUBLICATION_VERIFIER,
    )

    with pytest.raises(Exception):
        seal_c4_stage1_human_review(
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            display_receipt=receipt,
            consumed_display_receipt=consumed,
            operator_attestation=attestation,
            operator_secret=SECRET,
            display_attestation_verifier=fixture.display_verifier,
            display_receipt_ledger=display_ledger,
            used_policy_ledger=OperatorLedger(),
        )


def test_recomputed_receipt_rejects_swapped_publication_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    binding = fixture.publication_binding
    candidates = tuple(
        SimpleNamespace(
            option_id=item.option_id,
            candidate_receipt_id=item.candidate_receipt_id,
            candidate_receipt_sha256=item.candidate_receipt_sha256,
            prepared_worker_id=item.prepared_worker_id,
            prepared_worker_sha256=item.prepared_worker_sha256,
            worker_request_id=item.worker_request_id,
            worker_request_sha256=item.worker_request_sha256,
            staged_output_storage=item.staged_output_storage,
            staged_png_sha256=item.staged_output_storage.content_sha256,
        )
        for item in binding.candidates
    )
    publication = SimpleNamespace(
        member_publication_receipt_id=binding.member_publication_receipt_id,
        member_publication_receipt_sha256=binding.member_publication_receipt_sha256,
        editor_role=binding.editor_role,
        provider_slot_id=binding.provider_slot_id,
        candidate_receipts=candidates,
    )
    prepared = SimpleNamespace(
        run_id=binding.run_id,
        prepared_attempt_id=binding.prepared_attempt_id,
        prepared_attempt_sha256=binding.prepared_attempt_sha256,
        screen_contract=fixture.screen_contract,
        review_schema=fixture.schema,
        review_operator_policies=(fixture.policy, fixture.alternate_policy),
        display_policy=fixture.display_policy,
        artifact_inventory_before_anchor=(binding.source_storage,),
    )

    def cold_prepared(_store, storage, **_kwargs):
        if storage != binding.prepared_anchor_storage:
            raise ValueError("prepared anchor mismatch")
        return SimpleNamespace(
            prepared_attempt=prepared,
            prepared_anchor_storage=binding.prepared_anchor_storage,
        )

    def cold_member(_store, storage, _prepared):
        if storage != binding.member_publication_receipt_storage:
            raise ValueError("member marker mismatch")
        return publication

    monkeypatch.setattr(
        attempt_module,
        "cold_verify_c4_stage1_prepared_attempt",
        cold_prepared,
    )
    monkeypatch.setattr(
        run_module,
        "cold_verify_c4_stage1_member_publication",
        cold_member,
    )
    monkeypatch.setattr(
        review_module,
        "_cold_verify_display_publication_binding",
        _REAL_COLD_PUBLICATION_VERIFIER,
    )

    def replace_binding(**updates):
        values = {
            "run_id": binding.run_id,
            "prepared_attempt_id": binding.prepared_attempt_id,
            "prepared_attempt_sha256": binding.prepared_attempt_sha256,
            "prepared_anchor_storage": binding.prepared_anchor_storage,
            "member_publication_receipt_id": (binding.member_publication_receipt_id),
            "member_publication_receipt_sha256": (
                binding.member_publication_receipt_sha256
            ),
            "member_publication_receipt_storage": (
                binding.member_publication_receipt_storage
            ),
            "editor_role": binding.editor_role,
            "provider_slot_id": binding.provider_slot_id,
            "source_storage": binding.source_storage,
            "candidates": binding.candidates,
        }
        values.update(updates)
        return C4Stage1DisplayPublicationBinding.create(**values)

    def replace_receipt(publication_binding):
        body = receipt.model_dump(
            mode="python",
            round_trip=True,
            exclude={"display_receipt_id", "display_receipt_sha256"},
        )
        body["publication_binding"] = publication_binding
        return C4Stage1DisplayExecutionReceipt(
            display_receipt_id=content_id("c4_stage1_display_receipt", body),
            display_receipt_sha256=hashlib.sha256(
                canonical_json_bytes(body)
            ).hexdigest(),
            **body,
        )

    def verify(value):
        return cold_verify_c4_stage1_display_execution_receipt(
            value,
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
        )

    assert verify(receipt) == receipt

    swapped_member_id = "swapped-member-publication"
    swapped_member = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=binding.run_id,
            relative_path=(f"diagnostics/{swapped_member_id}.member-publication.json"),
            content_sha256=_sha256(b"swapped-member-storage"),
            size_bytes=1,
        ),
        run_id=binding.run_id,
        relative_path=f"diagnostics/{swapped_member_id}.member-publication.json",
        content_sha256=_sha256(b"swapped-member-storage"),
        size_bytes=1,
    )
    with pytest.raises(ValueError, match="member marker mismatch"):
        verify(
            replace_receipt(
                replace_binding(
                    member_publication_receipt_id=swapped_member_id,
                    member_publication_receipt_sha256=_sha256(b"swapped-member"),
                    member_publication_receipt_storage=swapped_member,
                )
            )
        )

    swapped_anchor = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=binding.run_id,
            relative_path="diagnostics/c4_stage1_prepared_attempt.json",
            content_sha256=_sha256(b"swapped-anchor"),
            size_bytes=1,
        ),
        run_id=binding.run_id,
        relative_path="diagnostics/c4_stage1_prepared_attempt.json",
        content_sha256=_sha256(b"swapped-anchor"),
        size_bytes=1,
    )
    with pytest.raises(ValueError, match="prepared anchor mismatch"):
        verify(replace_receipt(replace_binding(prepared_anchor_storage=swapped_anchor)))

    original_candidate = binding.candidates[0]
    swapped_output = StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=binding.run_id,
            relative_path="emocio/images/swapped-candidate.png",
            content_sha256=original_candidate.staged_output_storage.content_sha256,
            size_bytes=original_candidate.staged_output_storage.size_bytes,
        ),
        run_id=binding.run_id,
        relative_path="emocio/images/swapped-candidate.png",
        content_sha256=original_candidate.staged_output_storage.content_sha256,
        size_bytes=original_candidate.staged_output_storage.size_bytes,
    )
    swapped_candidate = original_candidate.model_copy(
        update={"staged_output_storage": swapped_output}
    )
    with pytest.raises(ValueError, match="cites another publication"):
        verify(
            replace_receipt(
                replace_binding(candidates=(swapped_candidate, binding.candidates[1]))
            )
        )


def test_hmac_from_other_display_receipt_cannot_authenticate_claim(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    first, _ = _display(fixture, session="ui-session-1")
    second, _ = _display(fixture, session="ui-session-2")
    first_ledger = DisplayLedger()
    second_ledger = DisplayLedger()
    first_consumed = consume_c4_stage1_display_receipt_once(first_ledger, first)
    second_consumed = consume_c4_stage1_display_receipt_once(second_ledger, second)
    first_claim, _ = _claim_and_attestation(fixture, first, first_consumed)
    wrong_tag = hmac.digest(
        SECRET,
        c4_stage1_operator_attestation_message(first_claim),
        "sha256",
    ).hex()
    _, second_attestation = _claim_and_attestation(
        fixture,
        second,
        second_consumed,
        hmac_override=wrong_tag,
    )

    with pytest.raises(ValueError, match="HMAC verification failed"):
        verify_c4_stage1_operator_attestation(
            fixture.policy,
            second_attestation,
            operator_secret=SECRET,
        )


def test_operator_policy_replay_with_different_lease_is_rejected(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    *_, operator_ledger, _ = _sealed_flow(fixture)
    second_receipt, _ = _display(fixture, session="ui-session-second-claim")
    second_display_ledger = DisplayLedger()
    second_consumed = consume_c4_stage1_display_receipt_once(
        second_display_ledger, second_receipt
    )
    _, second_attestation = _claim_and_attestation(
        fixture,
        second_receipt,
        second_consumed,
        operator_lease_sha256="b" * 64,
    )

    with pytest.raises(ValueError, match="operator policy replay"):
        seal_c4_stage1_human_review(
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            display_receipt=second_receipt,
            consumed_display_receipt=second_consumed,
            operator_attestation=second_attestation,
            operator_secret=SECRET,
            display_attestation_verifier=fixture.display_verifier,
            display_receipt_ledger=second_display_ledger,
            used_policy_ledger=operator_ledger,
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )


def test_missing_live_display_verifier_and_false_live_state_fail_seal(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    display_ledger = DisplayLedger()
    consumed = consume_c4_stage1_display_receipt_once(display_ledger, receipt)
    _, attestation = _claim_and_attestation(fixture, receipt, consumed)

    common = {
        "artifact_store": fixture.artifact_store,
        "operator_policy": fixture.policy,
        "screen_contract": fixture.screen_contract,
        "display_attester_policy": fixture.display_policy,
        "presentation_manifest": fixture.presentation,
        "display_receipt": receipt,
        "consumed_display_receipt": consumed,
        "operator_attestation": attestation,
        "operator_secret": SECRET,
        "display_receipt_ledger": display_ledger,
        "used_policy_ledger": OperatorLedger(),
        "source_png_path": fixture.source_path,
        "output_png_paths": fixture.output_paths,
    }
    with pytest.raises(TypeError, match="live keyed display verifier"):
        seal_c4_stage1_human_review(
            fixture.schema,
            fixture.packet,
            display_attestation_verifier=object(),
            **common,
        )

    fixture.display_verifier.live = False
    with pytest.raises(ValueError, match="not live externally"):
        seal_c4_stage1_human_review(
            fixture.schema,
            fixture.packet,
            display_attestation_verifier=fixture.display_verifier,
            **common,
        )
    fixture.display_verifier.live = True

    with pytest.raises(TypeError, match="live display-receipt verifier"):
        seal_c4_stage1_human_review(
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            display_receipt=receipt,
            consumed_display_receipt=consumed,
            operator_attestation=attestation,
            operator_secret=SECRET,
            display_attestation_verifier=fixture.display_verifier,
            display_receipt_ledger=object(),
            used_policy_ledger=OperatorLedger(),
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )

    display_ledger.live = False
    with pytest.raises(ValueError, match="not live"):
        seal_c4_stage1_human_review(
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            display_receipt=receipt,
            consumed_display_receipt=consumed,
            operator_attestation=attestation,
            operator_secret=SECRET,
            display_attestation_verifier=fixture.display_verifier,
            display_receipt_ledger=display_ledger,
            used_policy_ledger=OperatorLedger(),
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )


@pytest.mark.parametrize("reviewer", [SECRET.decode(), SECRET.hex()])
def test_direct_operator_secret_in_external_identifier_fails_sealing(
    tmp_path: Path, reviewer: str
) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    display_ledger = DisplayLedger()
    consumed = consume_c4_stage1_display_receipt_once(display_ledger, receipt)
    _, attestation = _claim_and_attestation(
        fixture, receipt, consumed, reviewer=reviewer
    )

    with pytest.raises(ValueError, match="direct operator-secret material"):
        seal_c4_stage1_human_review(
            fixture.schema,
            fixture.packet,
            artifact_store=fixture.artifact_store,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            display_receipt=receipt,
            consumed_display_receipt=consumed,
            operator_attestation=attestation,
            operator_secret=SECRET,
            display_attestation_verifier=fixture.display_verifier,
            display_receipt_ledger=display_ledger,
            used_policy_ledger=OperatorLedger(),
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
        )


def test_covert_identifier_boundary_is_explicit_and_not_overclaimed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    covert = base64.urlsafe_b64encode(SECRET).decode().rstrip("=")
    covert_display = base64.urlsafe_b64encode(DISPLAY_SECRET).decode().rstrip("=")
    display_policy = build_c4_stage1_display_attester_policy(
        policy_nonce=_sha256(b"covert-display-policy-nonce"),
        ui_bundle_sha256=_sha256(b"covert-display-ui-bundle"),
        content_security_policy=DISPLAY_CSP,
        presenter_implementation_id="rei-c4-stage1-review-ui",
        presenter_revision="ui-revision-1",
        display_attester_id=covert_display,
        display_signing_key_commitment_sha256=_sha256(DISPLAY_SECRET),
    )
    *_, claim, attestation, _, submission = _sealed_flow(fixture, reviewer=covert)
    assert display_policy.absence_of_covert_secret_encoding_proven is False
    assert claim.absence_of_covert_secret_encoding_proven is False
    assert attestation.absence_of_covert_secret_encoding_proven is False
    assert submission.attestation_proves_human_cognition is False


def test_missing_skipped_and_uncertain_review_fail_closed(tmp_path: Path) -> None:
    missing_fixture = _fixture(tmp_path, suffix="missing")
    missing = evaluate_c4_stage1_human_review(
        missing_fixture.schema,
        missing_fixture.packet,
        artifact_store=missing_fixture.artifact_store,
        operator_policy=missing_fixture.policy,
        screen_contract=missing_fixture.screen_contract,
        display_attester_policy=missing_fixture.display_policy,
        operator_secret=SECRET,
        display_attestation_verifier=missing_fixture.display_verifier,
        display_receipt_ledger=DisplayLedger(),
        used_policy_ledger=OperatorLedger(),
    )
    assert missing.review_status == "missing"
    assert missing.human_review_passed is False

    skipped_fixture = _fixture(tmp_path, suffix="skipped")
    skipped = evaluate_c4_stage1_human_review(
        skipped_fixture.schema,
        skipped_fixture.packet,
        artifact_store=skipped_fixture.artifact_store,
        operator_policy=skipped_fixture.policy,
        screen_contract=skipped_fixture.screen_contract,
        display_attester_policy=skipped_fixture.display_policy,
        operator_secret=SECRET,
        display_attestation_verifier=skipped_fixture.display_verifier,
        display_receipt_ledger=DisplayLedger(),
        used_policy_ledger=OperatorLedger(),
        skipped=True,
    )
    assert skipped.review_status == "skipped"
    assert skipped.human_review_passed is False

    uncertain_fixture = _fixture(tmp_path, suffix="uncertain")
    (
        _,
        _,
        display_ledger,
        _,
        _,
        _,
        operator_ledger,
        submission,
    ) = _sealed_flow(uncertain_fixture, uncertain=True)
    assert submission.human_review_passed is False
    uncertain = evaluate_c4_stage1_human_review(
        uncertain_fixture.schema,
        uncertain_fixture.packet,
        artifact_store=uncertain_fixture.artifact_store,
        operator_policy=uncertain_fixture.policy,
        screen_contract=uncertain_fixture.screen_contract,
        display_attester_policy=uncertain_fixture.display_policy,
        operator_secret=SECRET,
        display_attestation_verifier=uncertain_fixture.display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
        submission=submission,
        source_png_path=uncertain_fixture.source_path,
        output_png_paths=uncertain_fixture.output_paths,
    )
    assert uncertain.reason == "human_review_failed"
    assert uncertain.human_review_passed is False


def test_missing_judgment_and_wrong_display_hash_fail_claim(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    display_ledger = DisplayLedger()
    consumed = consume_c4_stage1_display_receipt_once(display_ledger, receipt)
    outputs, pair = _judgments(fixture)
    with pytest.raises(ValueError, match="exactly two judgments"):
        build_c4_stage1_operator_unsigned_claim(
            fixture.schema,
            fixture.packet,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            display_receipt=receipt,
            consumed_display_receipt=consumed,
            reviewer_pseudonym="reviewer-1",
            review_timestamp=REVIEWED_AT,
            output_judgments=(outputs[0],),
            pair_judgment=pair,
            submission_receipt_id="authenticated-submission-receipt-test",
            submission_receipt_sha256="9" * 64,
            operator_signing_lease_id="operator-signing-lease-test",
            operator_signing_lease_sha256="a" * 64,
        )

    tampered = receipt.model_copy(update={"display_receipt_sha256": "0" * 64})
    with pytest.raises(Exception):
        build_c4_stage1_operator_unsigned_claim(
            fixture.schema,
            fixture.packet,
            operator_policy=fixture.policy,
            screen_contract=fixture.screen_contract,
            display_attester_policy=fixture.display_policy,
            presentation_manifest=fixture.presentation,
            display_receipt=tampered,
            consumed_display_receipt=consumed,
            reviewer_pseudonym="reviewer-1",
            review_timestamp=REVIEWED_AT,
            output_judgments=outputs,
            pair_judgment=pair,
            submission_receipt_id="authenticated-submission-receipt-test",
            submission_receipt_sha256="9" * 64,
            operator_signing_lease_id="operator-signing-lease-test",
            operator_signing_lease_sha256="a" * 64,
        )


def test_public_artifacts_are_canonical_and_do_not_contain_raw_png_bytes(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt, _ = _display(fixture)
    payload = receipt.canonical_json_bytes()
    assert canonical_json_bytes(receipt) == payload
    assert fixture.source_bytes not in payload
    assert all(value not in payload for value in fixture.output_bytes)
