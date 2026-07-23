from __future__ import annotations

import base64
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from rei.emocio.longcat_turbo_editor import longcat_turbo_stage1_spec
from rei.evaluation import c4_stage1_review as review_module
from rei.evaluation import c4_stage1_review_run as review_run_module
from rei.evaluation import c4_stage1_run as render_run_module
from rei.evaluation.c4_stage1_review import (
    C4Stage1DisplayPortResult,
    build_c4_stage1_display_attestation,
    build_c4_stage1_display_port_acknowledgement,
    build_c4_stage1_operator_attestation,
    record_c4_stage1_consumed_display_attestation,
    record_c4_stage1_consumed_display_receipt,
    record_c4_stage1_consumed_operator_policy_receipt,
)
from rei.evaluation.c4_stage1_review_run import (
    C4Stage1HumanReviewRunAnchor,
    C4Stage1HumanReviewRunOutcome,
    C4Stage1ReviewRunError,
    _review_one_family,
    _submission_judgments,
    _verify_review_ui_session,
    _verify_repository_gate,
    run_c4_stage1_human_review,
)
from rei.evaluation.c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
)
from rei.evaluation.c4_stage1_review_service import (
    C4Stage1AuthenticatedPresenterSubmission,
    C4Stage1OperatorSigningLease,
)
from rei.ids import canonical_json_bytes, content_id
from rei.persistence.artifacts import FileArtifactStore, stored_artifact_id
from rei.providers.protocols import StoredArtifact
from tests.evaluation import test_c4_stage1_review as review_fixtures
from tests.evaluation.test_c4_stage1_run import (
    _Harness,
    _minimal_cold_envelope,
    _prepared_store,
    _run,
)
from tests.evaluation.test_c4_stage1_attempt import _prepared_attempt


ROOT = Path(__file__).resolve().parents[2]

_FAMILY_STORAGE_FIELDS = (
    "material_commitment_storage",
    "packet_storage",
    "presentation_manifest_storage",
    "presenter_submission_storage",
    "display_receipt_storage",
    "consumed_display_receipt_storage",
    "unsigned_claim_storage",
    "operator_attestation_storage",
    "sealed_submission_storage",
    "gate_result_storage",
)


def _descriptor_with(
    storage: StoredArtifact,
    *,
    run_id: str | None = None,
    content_sha256: str | None = None,
) -> StoredArtifact:
    selected_run = storage.run_id if run_id is None else run_id
    selected_sha256 = (
        storage.content_sha256 if content_sha256 is None else content_sha256
    )
    return StoredArtifact(
        storage_id=stored_artifact_id(
            run_id=selected_run,
            relative_path=storage.relative_path,
            content_sha256=selected_sha256,
            size_bytes=storage.size_bytes,
        ),
        run_id=selected_run,
        relative_path=storage.relative_path,
        content_sha256=selected_sha256,
        size_bytes=storage.size_bytes,
    )


def _readdress_anchor(anchor, **updates):
    body = anchor.model_dump(
        mode="python",
        round_trip=True,
        exclude={"review_run_anchor_id", "review_run_anchor_sha256"},
    )
    body.update(updates)
    return C4Stage1HumanReviewRunAnchor(
        review_run_anchor_id=review_run_module.content_id("c4_stage1_review_run", body),
        review_run_anchor_sha256=review_run_module._canonical_sha256(body),
        **body,
    )


def _submission(context, *, incomplete: bool = False) -> bytes:
    body = {
        "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "serviceSchemaRevision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
        "ledgerSchemaRevision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
        "packetId": context.packet_id,
        "packetSha256": context.packet_sha256,
        "sourceImageSha256": context.source_image_sha256,
        "reviewerPseudonym": "reviewer-one",
        "outputs": [
            {
                "blindCode": output.blind_code,
                "instructionSha256": output.instruction_sha256,
                "outputSha256": output.output_sha256,
                "judgments": {
                    "source_subject_present": True,
                    "identity_preserved": True,
                    "unchanged_composition_preserved": True,
                    "option_action_correct": True,
                    "no_extra_actor": True,
                    "no_generated_external_evidence_claim": True,
                    "reviewer_uncertain": False,
                },
            }
            for output in context.outputs
        ],
        "pairJudgments": {
            "actions_visibly_distinct": True,
            "same_source_bytes_confirmed": True,
        },
    }
    if incomplete:
        del body["outputs"][0]["judgments"]["identity_preserved"]
    return canonical_json_bytes(body)


class _FakeReviewClient:
    """Model-free endpoint with a fake presenter and exact one-time ledgers."""

    def __init__(self, *, mode: str = "success") -> None:
        self.mode = mode
        self.submissions = {}
        self.contexts = {}
        self.authenticated_submissions = {}
        self.operator_signing_leases = {}
        self.display_attestations = {}
        self.display_attestation_receipts = {}
        self.display_receipts = {}
        self.operator_attestations = {}
        self.operator_receipts = {}
        self.operator_receipt_deliveries = set()
        self.operator_signing_cohort_calls = []
        self.operator_signing_cohort_complete = False
        self.operator_signing_cohort_id = None
        self.operator_signing_cohort_sha256 = None

    def display(self, *, context, display_policy, source_png_bytes, outputs):
        if self.mode == "cancel":
            raise C4Stage1ReviewRunError("review cancelled")
        acknowledgement = build_c4_stage1_display_port_acknowledgement(
            context,
            source_png_bytes=source_png_bytes,
            outputs=outputs,
        )
        attestation = build_c4_stage1_display_attestation(
            display_policy,
            context,
            acknowledgement,
            external_hmac_sha256="a" * 64,
        )
        self.display_attestations[attestation.display_attestation_id] = attestation
        if self.mode != "missing":
            self.submissions[context.context_id] = _submission(
                context, incomplete=self.mode == "incomplete"
            )
            self.contexts[context.context_id] = context
        return C4Stage1DisplayPortResult(
            acknowledgement=acknowledgement,
            attestation=attestation,
        )

    def take_presentation_submission(self, *, context_id):
        try:
            submission = self.submissions.pop(context_id)
            context = self.contexts.pop(context_id)
        except KeyError:
            raise C4Stage1ReviewRunError("submission missing") from None
        submitted_at = datetime.now(timezone.utc)
        base = {
            "schema_version": "rei-c4-stage1-authenticated-presenter-submission-v1",
            "context_id": context.context_id,
            "context_sha256": context.context_sha256,
            "packet_id": context.packet_id,
            "packet_sha256": context.packet_sha256,
            "ipc_protocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
            "service_schema_revision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
            "ledger_schema_revision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
            "canonical_submission_base64": base64.b64encode(submission).decode("ascii"),
            "canonical_submission_sha256": hashlib.sha256(submission).hexdigest(),
            "canonical_submission_size_bytes": len(submission),
            "submitted_at": submitted_at,
            "presenter_submission_is_exact": True,
            "service_auth_secret_exposed": False,
        }
        receipt = C4Stage1AuthenticatedPresenterSubmission(
            submission_receipt_id=content_id("c4_s1_auth_presenter_submission", base),
            submission_receipt_sha256=hashlib.sha256(
                canonical_json_bytes(base)
            ).hexdigest(),
            service_auth_hmac_sha256="c" * 64,
            **base,
        )
        self.authenticated_submissions[receipt.submission_receipt_id] = receipt
        return receipt

    def verify_authenticated_submission(self, *, submission_receipt):
        return (
            self.authenticated_submissions.get(submission_receipt.submission_receipt_id)
            == submission_receipt
        )

    def issue_operator_signing_lease(
        self,
        *,
        operator_policy,
        submission_receipt,
        display_receipt,
        consumed_display_receipt,
    ):
        review_timestamp = max(
            submission_receipt.submitted_at,
            display_receipt.display_completed_at,
        )
        issued_at = max(datetime.now(timezone.utc), review_timestamp)
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
        lease = C4Stage1OperatorSigningLease(
            operator_signing_lease_id=content_id(
                "c4_stage1_operator_signing_lease", base
            ),
            operator_signing_lease_sha256=hashlib.sha256(
                canonical_json_bytes(base)
            ).hexdigest(),
            service_auth_hmac_sha256="d" * 64,
            **base,
        )
        self.operator_signing_leases[lease.operator_signing_lease_id] = lease
        return lease

    def verify_operator_signing_lease(self, *, operator_signing_lease):
        return (
            self.operator_signing_leases.get(
                operator_signing_lease.operator_signing_lease_id
            )
            == operator_signing_lease
        )

    def verify_display_attestation(self, **kwargs):
        attestation = kwargs["attestation"]
        return self.display_attestations.get(attestation.display_attestation_id) == (
            attestation
        )

    def consume_display_attestation_once(self, **kwargs):
        attestation = kwargs["attestation"]
        if attestation.display_attestation_id in self.display_attestation_receipts:
            raise ValueError("display attestation replay")
        receipt = record_c4_stage1_consumed_display_attestation(
            kwargs["display_policy"],
            kwargs["context"],
            kwargs["acknowledgement"],
            attestation,
            external_transaction_id=(
                f"display-attestation-{len(self.display_attestation_receipts) + 1}"
            ),
            external_transaction_timestamp=datetime.now(timezone.utc),
        )
        self.display_attestation_receipts[attestation.display_attestation_id] = receipt
        return receipt

    def verify_consumed_display_attestation(self, *, consumed_receipt, **kwargs):
        return (
            self.verify_display_attestation(**kwargs)
            and self.display_attestation_receipts.get(
                kwargs["attestation"].display_attestation_id
            )
            == consumed_receipt
        )

    def consume_display_receipt_once(self, *, display_receipt):
        if display_receipt.display_receipt_id in self.display_receipts:
            raise ValueError("display receipt replay")
        receipt = record_c4_stage1_consumed_display_receipt(
            display_receipt,
            external_transaction_id=(
                f"display-receipt-{len(self.display_receipts) + 1}"
            ),
            external_transaction_timestamp=datetime.now(timezone.utc),
        )
        self.display_receipts[display_receipt.display_receipt_id] = receipt
        return receipt

    def verify_consumed_display_receipt(self, *, display_receipt, consumed_receipt):
        return self.display_receipts.get(display_receipt.display_receipt_id) == (
            consumed_receipt
        )

    def sign_operator_claim_cohort(self, *, reviews):
        assert type(reviews) is tuple and len(reviews) == 2
        assert len({review.operator_policy.policy_id for review in reviews}) == 2
        attestations = []
        for review in reviews:
            assert (
                review.claim.submission_receipt_id
                == review.submission_receipt.submission_receipt_id
            )
            assert (
                review.claim.operator_signing_lease_id
                == review.operator_signing_lease.operator_signing_lease_id
            )
            assert (
                review.claim.display_receipt_id
                == review.display_receipt.display_receipt_id
            )
            assert (
                review.claim.consumed_display_receipt_id
                == review.consumed_display_receipt.consumed_display_receipt_id
            )
            attestations.append(
                build_c4_stage1_operator_attestation(
                    review.claim,
                    external_hmac_sha256=("b" * 63 + str(len(attestations) + 1)),
                )
            )
        self.operator_signing_cohort_calls.append(reviews)
        self.operator_attestations.update(
            {
                review.operator_policy.policy_id: attestation
                for review, attestation in zip(reviews, attestations, strict=True)
            }
        )
        self.operator_receipts.update(
            {
                review.operator_policy.policy_id: (
                    record_c4_stage1_consumed_operator_policy_receipt(
                        review.operator_policy,
                        attestation,
                        external_transaction_id=(f"operator-policy-cohort-{index + 1}"),
                        external_transaction_timestamp=datetime.now(timezone.utc),
                    )
                )
                for index, (review, attestation) in enumerate(
                    zip(reviews, attestations, strict=True)
                )
            }
        )
        cohort_body = {
            "request_claim_ids": tuple(review.claim.claim_id for review in reviews),
            "attestation_ids": tuple(
                attestation.attestation_id for attestation in attestations
            ),
        }
        self.operator_signing_cohort_id = content_id(
            "c4_s1_signing_cohort", cohort_body
        )
        self.operator_signing_cohort_sha256 = hashlib.sha256(
            canonical_json_bytes(cohort_body)
        ).hexdigest()
        self.operator_signing_cohort_complete = True
        return attestations[0], attestations[1]

    def verify_operator_attestation(self, *, operator_policy, attestation):
        return self.operator_attestations.get(operator_policy.policy_id) == attestation

    def consume_operator_policy_once(self, *, operator_policy, attestation):
        if operator_policy.policy_id in self.operator_receipt_deliveries:
            raise ValueError("operator policy replay")
        receipt = self.operator_receipts.get(operator_policy.policy_id)
        if (
            receipt is None
            or self.operator_attestations.get(operator_policy.policy_id) != attestation
        ):
            raise ValueError("operator policy has no completed cohort receipt")
        self.operator_receipt_deliveries.add(operator_policy.policy_id)
        return receipt

    def verify_consumed_operator_policy(
        self, *, operator_policy, attestation, consumed_receipt
    ):
        return (
            self.verify_operator_attestation(
                operator_policy=operator_policy,
                attestation=attestation,
            )
            and self.operator_receipts.get(operator_policy.policy_id)
            == consumed_receipt
        )

    def health(self):
        return {
            "ledger_counts": {
                "display_attestation_uses": len(self.display_attestation_receipts),
                "display_receipt_uses": len(self.display_receipts),
                "operator_policy_uses": len(self.operator_receipts),
                "presenter_submissions": len(self.authenticated_submissions),
                "operator_signing_leases": len(self.operator_signing_leases),
            },
            "operator_signing_cohort_complete": (self.operator_signing_cohort_complete),
            "operator_signing_cohort_id": self.operator_signing_cohort_id,
            "operator_signing_cohort_sha256": (self.operator_signing_cohort_sha256),
        }


def _family_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "success",
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    fixture = review_fixtures._fixture(tmp_path, suffix=f"family-{mode}")
    endpoint = _FakeReviewClient(mode=mode)
    publication = SimpleNamespace(
        editor_role="primary",
        member_publication_receipt_id=(
            fixture.publication_binding.member_publication_receipt_id
        ),
    )
    monkeypatch.setattr(
        review_run_module,
        "_family_material",
        lambda *_args, **_kwargs: (
            fixture.policy,
            fixture.commitment,
            fixture.packet,
            fixture.presentation,
            (),
        ),
    )

    def execute(_store, **kwargs):
        return review_module._execute_c4_stage1_display_from_paths(
            kwargs["schema"],
            kwargs["packet"],
            publication_binding=fixture.publication_binding,
            operator_policy=kwargs["operator_policy"],
            screen_contract=fixture.screen_contract,
            display_attester_policy=kwargs["display_attester_policy"],
            presentation_manifest=kwargs["presentation_manifest"],
            source_png_path=fixture.source_path,
            output_png_paths=fixture.output_paths,
            display_port=kwargs["display_port"],
            display_attestation_verifier=kwargs["display_attestation_verifier"],
            ui_implementation_id=fixture.display_policy.presenter_implementation_id,
            ui_revision=fixture.display_policy.presenter_revision,
            ui_session_id=kwargs["ui_session_id"],
            clock=kwargs["clock"],
        )

    monkeypatch.setattr(review_run_module, "execute_c4_stage1_display", execute)
    monkeypatch.setattr(
        review_module,
        "_cold_verify_display_publication_binding",
        lambda *_args, **_kwargs: (fixture.source_path, fixture.output_paths),
    )
    prepared = SimpleNamespace(
        review_schema=fixture.schema,
        screen_contract=fixture.screen_contract,
        display_policy=fixture.display_policy,
    )
    pending = _review_one_family(
        fixture.artifact_store,
        prepared,
        publication,
        fixture.publication_binding.member_publication_receipt_storage,
        prepared_anchor_storage_value=(
            fixture.publication_binding.prepared_anchor_storage
        ),
        review_run_id="review-run-one",
        review_service=endpoint,
        display_port=review_run_module.C4Stage1ReviewDisplayPort(endpoint),
        display_verifier=(
            review_run_module.C4Stage1ReviewDisplayAttestationVerifier(endpoint)
        ),
        display_ledger=review_run_module.C4Stage1ReviewDisplayReceiptLedger(endpoint),
        clock=lambda: datetime.now(timezone.utc),
    )
    operator_attestation = build_c4_stage1_operator_attestation(
        pending.claim,
        external_hmac_sha256="b" * 64,
    )
    endpoint.operator_attestations[pending.operator_policy.policy_id] = (
        operator_attestation
    )
    endpoint.operator_receipts[pending.operator_policy.policy_id] = (
        record_c4_stage1_consumed_operator_policy_receipt(
            pending.operator_policy,
            operator_attestation,
            external_transaction_id="operator-policy-isolated-family",
            external_transaction_timestamp=datetime.now(timezone.utc),
        )
    )
    runtime = review_run_module._seal_pending_family(
        pending,
        operator_attestation=operator_attestation,
        prepared=prepared,
        render_store=fixture.artifact_store,
        operator_verifier=(
            review_run_module.C4Stage1ReviewOperatorAttestationVerifier(endpoint)
        ),
        operator_ledger=(
            review_run_module.C4Stage1ReviewOperatorPolicyLedger(endpoint)
        ),
        display_verifier=(
            review_run_module.C4Stage1ReviewDisplayAttestationVerifier(endpoint)
        ),
        display_ledger=review_run_module.C4Stage1ReviewDisplayReceiptLedger(endpoint),
    )
    return fixture, endpoint, runtime, prepared, publication


def _pending_from_runtime(runtime):
    return review_run_module._PendingFamily(
        editor_role=runtime.editor_role,
        publication=runtime.publication,
        publication_storage=runtime.publication_storage,
        operator_policy=runtime.operator_policy,
        commitment=runtime.commitment,
        packet=runtime.packet,
        presentation=runtime.presentation,
        submission_receipt=runtime.presenter_submission.submission_receipt,
        operator_signing_lease=runtime.presenter_submission.operator_signing_lease,
        display_receipt=runtime.display_receipt,
        consumed_display_receipt=runtime.consumed_display_receipt,
        claim=runtime.claim,
    )


def test_orchestrator_requests_one_complete_operator_signing_cohort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, primary, _, _ = _family_runtime(tmp_path / "primary", monkeypatch)
    _, _, alternate, _, _ = _family_runtime(tmp_path / "alternate", monkeypatch)
    alternate = replace(alternate, editor_role="alternate")
    assert primary.operator_policy.policy_id != alternate.operator_policy.policy_id
    endpoint = _FakeReviewClient()
    assert endpoint.operator_attestations == {}

    pending = (_pending_from_runtime(primary), _pending_from_runtime(alternate))
    attestations = review_run_module._sign_pending_family_cohort(
        pending,
        operator_verifier=(
            review_run_module.C4Stage1ReviewOperatorAttestationVerifier(endpoint)
        ),
    )

    assert len(endpoint.operator_signing_cohort_calls) == 1
    assert endpoint.operator_signing_cohort_calls[0] == tuple(
        review_run_module.C4Stage1OperatorSigningRequest(
            operator_policy=item.operator_policy,
            claim=item.claim,
            submission_receipt=item.submission_receipt,
            operator_signing_lease=item.operator_signing_lease,
            display_receipt=item.display_receipt,
            consumed_display_receipt=item.consumed_display_receipt,
        )
        for item in pending
    )
    assert tuple(item.claim for item in attestations) == tuple(
        item.claim for item in pending
    )
    assert endpoint.operator_signing_cohort_complete is True
    assert endpoint.operator_signing_cohort_id is not None
    assert endpoint.operator_signing_cohort_sha256 is not None
    assert not hasattr(endpoint, "sign_operator_claim")


def test_fake_presenter_maps_all_fields_and_seals_without_identity_reveal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, endpoint, runtime, _, _ = _family_runtime(tmp_path, monkeypatch)

    assert runtime.gate.review_status == "sealed_submission"
    assert runtime.gate.human_review_passed is True
    assert runtime.sealed_submission.reveal_mapping_present is False
    assert len(runtime.claim.output_judgments) == 2
    assert all(item.passed for item in runtime.claim.output_judgments)
    assert runtime.claim.pair_judgment.passed is True
    assert endpoint.submissions == {}
    payload = (
        runtime.presenter_submission.submission_receipt.canonical_submission_bytes
    ).decode("utf-8")
    assert fixture.commitment.renderer_id not in payload
    assert fixture.commitment.model_id not in payload
    assert "enter_circle" not in payload
    assert "remain_edge" not in payload

    mutated_receipt = runtime.display_receipt.model_copy(
        update={
            "context": runtime.display_receipt.context.model_copy(
                update={"ui_session_id": "forged-review-session"}
            )
        }
    )
    with pytest.raises(C4Stage1ReviewRunError, match="another review UI session"):
        _verify_review_ui_session(
            review_run_id="review-run-one",
            editor_role="primary",
            packet=runtime.packet,
            publication=runtime.publication,
            display_receipt=mutated_receipt,
        )


def test_complete_hidden_identity_set_blocks_instructions_and_reviewer_pseudonym(
    tmp_path: Path,
) -> None:
    fixture = review_fixtures._fixture(tmp_path, suffix="identity-deny-set")
    spec = longcat_turbo_stage1_spec()
    hidden = review_run_module._hidden_identity_tokens(spec)
    adversarial_tokens = (
        spec.provider.provider_id,
        spec.repo_id,
        spec.repo_id.rsplit("/", 1)[-1],
        spec.provider.model,
        spec.provider.implementation,
        spec.provider.implementation_revision,
        spec.revision,
        spec.revision[:8],
        spec.pipeline.implementation,
        spec.pipeline.implementation_revision,
        "LongCat",
        "meituan",
    )
    assert all(token is not None for token in adversarial_tokens)
    hidden_folded = {token.casefold() for token in hidden}
    assert all(str(token).casefold() in hidden_folded for token in adversarial_tokens)

    context = SimpleNamespace(
        packet_id=fixture.packet.packet_id,
        packet_sha256=fixture.packet.packet_sha256,
        source_image_sha256=fixture.packet.source_image_sha256,
        outputs=fixture.packet.outputs,
    )
    for token_value in adversarial_tokens:
        token = str(token_value)
        with pytest.raises(C4Stage1ReviewRunError, match="hidden provider"):
            review_run_module._assert_visible_text_stays_blind(
                f"Apply the requested action with {token}.",
                hidden,
                label="C4 Stage 1 visible instruction",
            )

        submission = review_run_module._strict_json_object(_submission(context))
        submission["reviewerPseudonym"] = token
        with pytest.raises(C4Stage1ReviewRunError, match="hidden provider"):
            review_run_module._assert_submission_stays_blind(
                canonical_json_bytes(submission),
                fixture.commitment,
                hidden_identity_tokens=hidden,
            )


def test_prepared_family_rejects_identity_alias_in_visible_instruction(
    tmp_path: Path,
) -> None:
    fixture = review_fixtures._fixture(tmp_path, suffix="identity-instruction")
    spec = longcat_turbo_stage1_spec()
    candidates = tuple(
        SimpleNamespace(
            prepared_worker_id=f"worker-{index}",
            option_id=option_id,
            worker_request_id=f"request-{index}",
            staged_png_sha256=hashlib.sha256(option_id.encode()).hexdigest(),
        )
        for index, option_id in enumerate(("enter_circle", "remain_edge"))
    )
    workers = tuple(
        SimpleNamespace(
            prepared_worker_id=candidate.prepared_worker_id,
            editor_role="primary",
            option_id=candidate.option_id,
            worker_request=SimpleNamespace(
                worker_request_id=candidate.worker_request_id,
                editor_spec=spec,
                render_request=SimpleNamespace(
                    prompt=(
                        "Move the subject toward LongCat."
                        if index == 0
                        else "Keep the subject at the edge."
                    )
                ),
            ),
        )
        for index, candidate in enumerate(candidates)
    )
    prepared = SimpleNamespace(
        review_operator_policies=(fixture.policy,),
        workers=workers,
    )
    publication = SimpleNamespace(
        provider_slot_id=fixture.policy.candidate_slot_id,
        editor_role="primary",
        candidate_receipts=candidates,
    )

    with pytest.raises(C4Stage1ReviewRunError, match="hidden provider"):
        review_run_module._prepared_family_inputs(prepared, publication)


@pytest.mark.parametrize("mode", ["cancel", "missing", "incomplete"])
def test_cancel_missing_and_incomplete_presenter_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    with pytest.raises((C4Stage1ReviewRunError, ValueError)):
        _family_runtime(tmp_path, monkeypatch, mode=mode)


def test_presenter_submission_never_defaults_a_missing_human_boolean(
    tmp_path: Path,
) -> None:
    fixture = review_fixtures._fixture(tmp_path, suffix="strict-submission")
    context = SimpleNamespace(
        packet_id=fixture.packet.packet_id,
        packet_sha256=fixture.packet.packet_sha256,
        source_image_sha256=fixture.packet.source_image_sha256,
        outputs=fixture.packet.outputs,
    )
    with pytest.raises(C4Stage1ReviewRunError, match="incomplete"):
        _submission_judgments(
            fixture.packet,
            _submission(context, incomplete=True),
        )


def test_replayed_review_context_or_policy_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, endpoint, _, prepared, publication = _family_runtime(tmp_path, monkeypatch)
    display_verifier = review_run_module.C4Stage1ReviewDisplayAttestationVerifier(
        endpoint
    )
    display_ledger = review_run_module.C4Stage1ReviewDisplayReceiptLedger(endpoint)
    pending = _review_one_family(
        fixture.artifact_store,
        prepared,
        publication,
        fixture.publication_binding.member_publication_receipt_storage,
        prepared_anchor_storage_value=(
            fixture.publication_binding.prepared_anchor_storage
        ),
        review_run_id="review-run-one",
        review_service=endpoint,
        display_port=review_run_module.C4Stage1ReviewDisplayPort(endpoint),
        display_verifier=display_verifier,
        display_ledger=display_ledger,
        clock=lambda: datetime.now(timezone.utc),
    )
    replay_attestation = build_c4_stage1_operator_attestation(
        pending.claim,
        external_hmac_sha256="e" * 64,
    )
    endpoint.operator_attestations[pending.operator_policy.policy_id] = (
        replay_attestation
    )
    with pytest.raises(ValueError, match="replay"):
        review_run_module._seal_pending_family(
            pending,
            operator_attestation=replay_attestation,
            prepared=prepared,
            render_store=fixture.artifact_store,
            operator_verifier=(
                review_run_module.C4Stage1ReviewOperatorAttestationVerifier(endpoint)
            ),
            operator_ledger=(
                review_run_module.C4Stage1ReviewOperatorPolicyLedger(endpoint)
            ),
            display_verifier=display_verifier,
            display_ledger=display_ledger,
        )


def test_separate_review_run_does_not_mutate_cold_verified_render_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cold_replay = review_run_module.cold_verify_c4_stage1_human_review_run
    render_store, prepared_outcome, paths = _prepared_store(tmp_path / "render")
    harness = _Harness(render_store, prepared_outcome)
    monkeypatch.setattr(
        render_run_module,
        "cold_verify_c4_stage1_launch_envelope",
        _minimal_cold_envelope,
    )
    monkeypatch.setattr(
        render_run_module,
        "cold_verify_c4_stage1_prepared_attempt",
        lambda *_args, **_kwargs: prepared_outcome,
    )
    render_outcome = _run(harness, paths)
    verified_before = render_run_module.cold_verify_c4_stage1_run(
        FileArtifactStore(render_store.root, create=False),
        render_outcome.inventory_anchor_storage,
    )
    inventory_before = render_store.inspect_run_inventory_exact(
        prepared_outcome.prepared_attempt.run_id
    )
    primary_storage = (
        render_outcome.manifest.member_runs[0]
        .worker_terminals[0]
        .member_publication_receipt_storage
    )
    alternate_storage = (
        render_outcome.manifest.member_runs[1]
        .worker_terminals[0]
        .member_publication_receipt_storage
    )
    assert primary_storage is not None and alternate_storage is not None

    _, _, primary_runtime, _, _ = _family_runtime(tmp_path / "portable", monkeypatch)
    runtime_fixtures = {
        "primary": replace(primary_runtime, publication_storage=primary_storage),
        "alternate": replace(
            primary_runtime,
            editor_role="alternate",
            publication_storage=alternate_storage,
        ),
    }
    pending_values = iter(
        (
            SimpleNamespace(editor_role="primary"),
            SimpleNamespace(editor_role="alternate"),
        )
    )
    monkeypatch.setattr(
        review_run_module,
        "cold_verify_c4_stage1_prepared_attempt",
        lambda *_args, **_kwargs: prepared_outcome,
    )
    boundary_counts = []

    def verify_boundary(**kwargs):
        boundary_counts.append(kwargs["expected_completed_review_count"])

    monkeypatch.setattr(
        review_run_module,
        "verify_c4_stage1_live_review_boundary",
        verify_boundary,
    )
    monkeypatch.setattr(
        review_run_module,
        "capture_c4_stage1_repository_gate",
        lambda _root: prepared_outcome.prepared_attempt.repository_gate,
    )
    monkeypatch.setattr(
        review_run_module,
        "_review_one_family",
        lambda *_args, **_kwargs: next(pending_values),
    )
    monkeypatch.setattr(
        review_run_module,
        "_seal_pending_family",
        lambda pending, **_kwargs: runtime_fixtures[pending.editor_role],
    )
    monkeypatch.setattr(
        review_run_module,
        "_sign_pending_family_cohort",
        lambda pending, **_kwargs: tuple(
            runtime_fixtures[item.editor_role].operator_attestation for item in pending
        ),
    )

    def cold_review(_render, review, storage, **_kwargs):
        value = review.read_verified(storage)
        anchor = C4Stage1HumanReviewRunAnchor.model_validate_json(value)
        return C4Stage1HumanReviewRunOutcome(anchor=anchor, anchor_storage=storage)

    monkeypatch.setattr(
        review_run_module,
        "cold_verify_c4_stage1_human_review_run",
        cold_review,
    )
    endpoint = _FakeReviewClient()
    endpoint.display_attestation_receipts = {"one": object(), "two": object()}
    endpoint.display_receipts = {"one": object(), "two": object()}
    endpoint.operator_receipts = {"one": object(), "two": object()}
    endpoint.authenticated_submissions = {"one": object(), "two": object()}
    endpoint.operator_signing_leases = {"one": object(), "two": object()}
    endpoint.operator_signing_cohort_complete = True
    endpoint.operator_signing_cohort_id = "c4_stage1_completed_signing_cohort_test"
    endpoint.operator_signing_cohort_sha256 = "f" * 64
    review_store = FileArtifactStore(tmp_path / "review-artifacts")
    outcome = run_c4_stage1_human_review(
        render_store,
        render_outcome.inventory_anchor_storage,
        prepared_outcome.prepared_anchor_storage,
        (primary_storage, alternate_storage),
        review_store,
        review_run_id="stage1-review-run",
        confirmed_render_inventory_anchor_id=(
            render_outcome.inventory_anchor.render_inventory_anchor_id
        ),
        confirmed_render_inventory_anchor_sha256=(
            render_outcome.inventory_anchor.render_inventory_anchor_sha256
        ),
        confirmed_prepared_attempt_id=(
            prepared_outcome.prepared_attempt.prepared_attempt_id
        ),
        confirmed_prepared_attempt_sha256=(
            prepared_outcome.prepared_attempt.prepared_attempt_sha256
        ),
        repository_root=ROOT,
        review_service=endpoint,
    )
    verified_after = render_run_module.cold_verify_c4_stage1_run(
        FileArtifactStore(render_store.root, create=False),
        render_outcome.inventory_anchor_storage,
    )

    assert verified_after == verified_before
    assert (
        render_store.inspect_run_inventory_exact(
            prepared_outcome.prepared_attempt.run_id
        )
        == inventory_before
    )
    assert outcome.anchor.render_artifact_inventory == inventory_before
    assert outcome.anchor.pre_seal_review_artifacts_persisted_by_orchestrator is False
    assert outcome.anchor.cold_anchor_alone_proves_historical_write_order is False
    assert outcome.anchor.post_submission_mapping_bound_by_both_sealed_records is True
    assert outcome.anchor.operator_signing_cohort_id == (
        endpoint.operator_signing_cohort_id
    )
    assert outcome.anchor.operator_signing_cohort_sha256 == (
        endpoint.operator_signing_cohort_sha256
    )
    assert outcome.anchor.identity_reveal_status == (
        "post_seal_mapping_bound_no_compatible_reveal_artifact"
    )
    assert all(
        family.post_submission_identity_mapping_commitment_id
        == family.material_commitment_id
        for family in outcome.anchor.families
    )
    assert boundary_counts == [0, 2]

    primary_family = outcome.anchor.families[0]
    cross_run_updates = {
        field: _descriptor_with(
            getattr(primary_family, field), run_id="grafted-review-run"
        )
        for field in _FAMILY_STORAGE_FIELDS
    }
    cross_run_family = type(primary_family).model_validate(
        {
            **primary_family.model_dump(mode="python", round_trip=True),
            **cross_run_updates,
        }
    )
    with pytest.raises(ValidationError, match="review run anchor is inconsistent"):
        _readdress_anchor(
            outcome.anchor,
            families=(cross_run_family, outcome.anchor.families[1]),
        )
    forged_body = outcome.anchor.model_dump(
        mode="python",
        round_trip=True,
        exclude={"review_run_anchor_id", "review_run_anchor_sha256"},
    )
    forged_body["families"] = (
        cross_run_family,
        outcome.anchor.families[1],
    )
    forged_payload = {
        "review_run_anchor_id": review_run_module.content_id(
            "c4_stage1_review_run", forged_body
        ),
        "review_run_anchor_sha256": review_run_module._canonical_sha256(forged_body),
        **forged_body,
    }
    forged_store = FileArtifactStore(tmp_path / "forged-review-artifacts")
    forged_storage = forged_store.write_json(
        outcome.anchor.review_run_id,
        review_run_module.C4_STAGE1_REVIEW_RUN_ANCHOR_PATH,
        forged_payload,
        overwrite=False,
    )
    with pytest.raises(ValidationError, match="review run anchor is inconsistent"):
        review_run_module.cold_verify_c4_stage1_human_review_run(
            render_store,
            forged_store,
            forged_storage,
            repository_root=ROOT,
            review_service=object(),  # type: ignore[arg-type]
        )

    replaced = outcome.anchor.artifact_inventory_before_anchor[0]
    placeholder = _descriptor_with(replaced, content_sha256="f" * 64)
    placeholder_inventory = tuple(
        placeholder if item == replaced else item
        for item in outcome.anchor.artifact_inventory_before_anchor
    )
    with pytest.raises(ValidationError, match="review run anchor is inconsistent"):
        _readdress_anchor(
            outcome.anchor,
            artifact_inventory_before_anchor=placeholder_inventory,
        )

    mismatched_anchor = _readdress_anchor(
        outcome.anchor,
        operator_signing_cohort_id="c4_stage1_completed_signing_cohort_other",
    )
    mismatch_store = FileArtifactStore(tmp_path / "mismatched-cohort-review")
    for storage in outcome.anchor.artifact_inventory_before_anchor:
        copied = mismatch_store.write_bytes(
            storage.run_id,
            storage.relative_path,
            review_store.read_verified(storage),
            overwrite=False,
        )
        assert copied == storage
    mismatch_anchor_storage = mismatch_store.write_json(
        mismatched_anchor.review_run_id,
        review_run_module.C4_STAGE1_REVIEW_RUN_ANCHOR_PATH,
        mismatched_anchor,
        overwrite=False,
    )
    with pytest.raises(C4Stage1ReviewRunError, match="differs from the review anchor"):
        cold_replay(
            render_store,
            mismatch_store,
            mismatch_anchor_storage,
            repository_root=ROOT,
            review_service=endpoint,
        )
    assert boundary_counts == [0, 2, 2]


def test_render_and_review_store_overlap_is_rejected_before_review(
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifacts"
    render = FileArtifactStore(root)
    review = FileArtifactStore(root)
    with pytest.raises(C4Stage1ReviewRunError, match="non-overlapping"):
        run_c4_stage1_human_review(
            render,
            object(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            (object(), object()),  # type: ignore[arg-type]
            review,
            review_run_id="review-run",
            confirmed_render_inventory_anchor_id="anchor",
            confirmed_render_inventory_anchor_sha256="a" * 64,
            confirmed_prepared_attempt_id="prepared",
            confirmed_prepared_attempt_sha256="b" * 64,
            repository_root=ROOT,
            review_service=object(),  # type: ignore[arg-type]
        )


def test_dirty_or_wrong_head_repository_gate_fails_before_service_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_attempt()
    wrong_head = prepared.repository_gate.model_copy(update={"head_commit": "2" * 40})
    monkeypatch.setattr(
        review_run_module,
        "capture_c4_stage1_repository_gate",
        lambda _root: wrong_head,
    )
    with pytest.raises(C4Stage1ReviewRunError, match="changed"):
        _verify_repository_gate(prepared, ROOT)

    def dirty(_root):
        raise RuntimeError("scoped worktree is dirty")

    monkeypatch.setattr(
        review_run_module,
        "capture_c4_stage1_repository_gate",
        dirty,
    )
    with pytest.raises(C4Stage1ReviewRunError, match="clean and exact"):
        _verify_repository_gate(prepared, ROOT)


def test_review_cli_is_inert_without_explicit_execute() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_rei_c4_stage1_review.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 64
    assert completed.stdout == ""
    assert completed.stderr == ""

    cli_path = ROOT / "scripts/run_rei_c4_stage1_review.py"
    spec = importlib.util.spec_from_file_location("_rei_c4_review_cli_test", cli_path)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    defaults = cli._parser().parse_args([])
    assert defaults.service_timeout_seconds == 3606.0
    assert defaults.presenter_timeout_ms == 3_600_000


def test_review_cli_rejects_wrong_interpreter_before_application_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli_path = ROOT / "scripts/run_rei_c4_stage1_review.py"
    spec = importlib.util.spec_from_file_location("_rei_c4_review_cli_wrong", cli_path)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    application_imported = False

    def application_loader() -> object:
        nonlocal application_imported
        application_imported = True
        raise AssertionError("application imports must remain unreachable")

    monkeypatch.setattr(cli, "_load_application_modules", application_loader)
    result = cli.main(
        [
            "--execute",
            "--review-runtime-root",
            str(ROOT),
            "--review-browser-root",
            str(ROOT),
            "--review-runtime-provenance-root",
            str(ROOT),
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
    )

    assert result == 2
    assert application_imported is False
