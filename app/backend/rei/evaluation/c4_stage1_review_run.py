"""Create-only orchestration for the two C4 Stage 1 human reviews.

The renderer run is an immutable input.  This module cold-verifies its final
inventory anchor before contacting the review service, presents the primary
and alternate family in that frozen order, seals both manual submissions via
the separately keyed service, and writes only to a fresh review run.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import secrets
from typing import Callable, Literal, Mapping, Self, TypeVar

from pydantic import BaseModel, model_validator

from ..emocio.c4_stage1_editor import C4Stage1EditorSpec
from ..ids import canonical_json_bytes, content_id, utc_now
from ..models.common import FrozenArtifactModel, HashDigest, NonEmptyId
from ..persistence.artifacts import FileArtifactStore
from ..providers.protocols import StoredArtifact
from .c4_blind_review import (
    C4BlindPresentationManifest,
    C4BlindReviewPacket,
    C4HumanReviewOperatorPolicy,
    C4PairHumanJudgment,
    C4ReviewMaterialCommitment,
    C4ReviewOptionMaterial,
    build_c4_blind_presentation_manifest,
    commit_c4_review_material,
    make_c4_review_option_material,
    prepare_c4_blind_review,
    record_c4_output_human_judgment,
)
from .c4_stage1_attempt import (
    C4Stage1PreparedAttempt,
    capture_c4_stage1_repository_gate,
    cold_verify_c4_stage1_prepared_attempt,
    verify_c4_stage1_live_review_boundary,
)
from .c4_stage1_review import (
    C4Stage1ConsumedDisplayReceipt,
    C4Stage1DisplayExecutionReceipt,
    C4Stage1HumanReviewGateResult,
    C4Stage1HumanReviewOperatorAttestation,
    C4Stage1HumanReviewUnsignedClaim,
    C4Stage1SealedHumanReviewSubmission,
    build_c4_stage1_operator_unsigned_claim,
    cold_verify_c4_stage1_display_execution_receipt,
    consume_c4_stage1_display_receipt_once,
    evaluate_c4_stage1_human_review,
    execute_c4_stage1_display,
    seal_c4_stage1_human_review,
)
from .c4_stage1_review_service import (
    C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
    C4_STAGE1_REVIEW_PRESENTER_REVISION,
    C4Stage1AuthenticatedPresenterSubmission,
    C4Stage1AuthenticatedReviewEnvelope,
    C4Stage1OperatorSigningRequest,
    C4Stage1OperatorSigningLease,
    C4Stage1ReviewDisplayAttestationVerifier,
    C4Stage1ReviewDisplayPort,
    C4Stage1ReviewDisplayReceiptLedger,
    C4Stage1ReviewOperatorAttestationVerifier,
    C4Stage1ReviewOperatorPolicyLedger,
    C4Stage1ReviewServiceClient,
)
from .c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
)
from .c4_stage1_run import (
    C4Stage1MemberPublicationReceipt,
    C4Stage1RunOutcome,
    cold_verify_c4_stage1_member_publication,
    cold_verify_c4_stage1_run,
)


C4_STAGE1_REVIEW_RUN_ANCHOR_PATH = "diagnostics/c4_stage1_human_review_inventory.json"

_FAMILY_ROLES = ("primary", "alternate")
_OUTPUT_BOOLEAN_FIELDS = (
    "source_subject_present",
    "identity_preserved",
    "unchanged_composition_preserved",
    "option_action_correct",
    "no_extra_actor",
    "no_generated_external_evidence_claim",
    "reviewer_uncertain",
)
_PAIR_BOOLEAN_FIELDS = (
    "actions_visibly_distinct",
    "same_source_bytes_confirmed",
)
_MAX_SUBMISSION_BYTES = 64 * 1024
_GENERIC_IDENTITY_ALIAS_TOKENS = frozenset(
    {
        "app",
        "backend",
        "diffusers",
        "edit",
        "editor",
        "emocio",
        "image",
        "lazy",
        "model",
        "pipeline",
        "provider",
        "rei",
        "run",
        "stage1",
        "turbo",
    }
)
_HEX_DIGITS = frozenset("0123456789abcdef")


class C4Stage1ReviewRunError(RuntimeError):
    """The review run could not preserve its sealed boundary."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256(canonical_json_bytes(value))


def _identity_aliases(value: str) -> tuple[str, ...]:
    """Return bounded, identity-bearing aliases without generic prompt words."""

    if type(value) is not str or not value:
        return ()
    aliases = {value}
    for segment in re.split(r"[/\\.;:=]+", value):
        segment = segment.strip()
        if len(segment) >= 6 and segment.casefold() not in _GENERIC_IDENTITY_ALIAS_TOKENS:
            aliases.add(segment)
        for token in re.split(r"[-_]+", segment):
            token = token.strip()
            if (
                len(token) >= 6
                and token.casefold() not in _GENERIC_IDENTITY_ALIAS_TOKENS
                and not token.isdecimal()
            ):
                aliases.add(token)
    compact = "".join(character for character in value if character.isalnum())
    if len(compact) >= 8:
        aliases.add(compact)
    folded = value.casefold()
    if len(folded) >= 12 and all(character in _HEX_DIGITS for character in folded):
        aliases.update((value[:7], value[:8], value[:12]))
    return tuple(sorted(aliases, key=lambda item: (item.casefold(), item)))


def _hidden_identity_tokens(spec: C4Stage1EditorSpec) -> tuple[str, ...]:
    """One central complete renderer/model identity deny-set for visible text."""

    spec = C4Stage1EditorSpec.model_validate(
        spec.model_dump(mode="python", round_trip=True)
    )
    provider = spec.provider
    values = (
        spec.spec_id,
        spec.snapshot_manifest_sha256,
        provider.provider_id,
        spec.repo_id,
        provider.model or "",
        provider.implementation,
        provider.implementation_revision,
        provider.model_revision or "",
        spec.revision,
        spec.pipeline.implementation,
        spec.pipeline.implementation_revision,
    )
    aliases = {
        alias
        for value in values
        if value
        for alias in _identity_aliases(value)
        if alias
    }
    return tuple(sorted(aliases, key=lambda item: (item.casefold(), item)))


def _assert_visible_text_stays_blind(
    value: str,
    forbidden_tokens: tuple[str, ...],
    *,
    label: str,
) -> None:
    if type(value) is not str:
        raise TypeError("C4 Stage 1 visible text must be a string")
    folded = value.casefold()
    compact = "".join(character for character in folded if character.isalnum())
    for token in forbidden_tokens:
        token_folded = token.casefold()
        token_compact = "".join(
            character for character in token_folded if character.isalnum()
        )
        if token_folded in folded or (
            len(token_compact) >= 8 and token_compact in compact
        ):
            raise C4Stage1ReviewRunError(
                f"{label} contains a hidden provider or model identity"
            )


def _artifact_path(role: str, label: str) -> str:
    return f"diagnostics/{role}.{label}.json"


_ARTIFACT_LABELS = (
    "material-commitment",
    "blind-packet",
    "presentation-manifest",
    "presenter-submission",
    "display-receipt",
    "consumed-display-receipt",
    "unsigned-claim",
    "operator-attestation",
    "sealed-submission",
    "gate-result",
)


def _expected_review_paths() -> tuple[str, ...]:
    return tuple(
        sorted(
            _artifact_path(role, label)
            for role in _FAMILY_ROLES
            for label in _ARTIFACT_LABELS
        )
    )


class C4Stage1ReviewFamilyEvidence(FrozenArtifactModel):
    """Portable storage lineage for one sealed, still-blind family review."""

    schema_version: Literal["rei-c4-stage1-review-family-evidence-v1"] = (
        "rei-c4-stage1-review-family-evidence-v1"
    )
    editor_role: Literal["primary", "alternate"]
    member_publication_receipt_storage: StoredArtifact
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    material_commitment_id: NonEmptyId
    material_commitment_sha256: HashDigest
    material_commitment_storage: StoredArtifact
    packet_id: NonEmptyId
    packet_sha256: HashDigest
    packet_storage: StoredArtifact
    presentation_manifest_id: NonEmptyId
    presentation_manifest_sha256: HashDigest
    presentation_manifest_storage: StoredArtifact
    presenter_submission_storage: StoredArtifact
    display_receipt_id: NonEmptyId
    display_receipt_sha256: HashDigest
    display_receipt_storage: StoredArtifact
    consumed_display_receipt_id: NonEmptyId
    consumed_display_receipt_sha256: HashDigest
    consumed_display_receipt_storage: StoredArtifact
    claim_id: NonEmptyId
    claim_sha256: HashDigest
    unsigned_claim_storage: StoredArtifact
    operator_attestation_id: NonEmptyId
    operator_attestation_sha256: HashDigest
    operator_attestation_storage: StoredArtifact
    sealed_submission_id: NonEmptyId
    sealed_submission_storage: StoredArtifact
    gate_result_id: NonEmptyId
    gate_result_storage: StoredArtifact
    human_review_passed: bool
    post_submission_identity_mapping_commitment_id: NonEmptyId
    post_submission_identity_mapping_commitment_sha256: HashDigest
    presenter_submission_contains_provider_or_model_identity: Literal[False] = False
    presenter_submission_contains_blind_to_option_mapping: Literal[False] = False
    identity_mapping_persisted_only_after_sealed_submission: Literal[True] = True
    reveal_mapping_present: Literal[False] = False
    human_review_substituted_by_model: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    def review_artifact_storages(self) -> tuple[StoredArtifact, ...]:
        return (
            self.material_commitment_storage,
            self.packet_storage,
            self.presentation_manifest_storage,
            self.presenter_submission_storage,
            self.display_receipt_storage,
            self.consumed_display_receipt_storage,
            self.unsigned_claim_storage,
            self.operator_attestation_storage,
            self.sealed_submission_storage,
            self.gate_result_storage,
        )

    @model_validator(mode="after")
    def validate_family_evidence(self) -> Self:
        review_storages = self.review_artifact_storages()
        expected = tuple(
            _artifact_path(self.editor_role, label) for label in _ARTIFACT_LABELS
        )
        if (
            tuple(item.relative_path for item in review_storages) != expected
            or len({item.storage_id for item in review_storages})
            != len(review_storages)
            or len({item.run_id for item in review_storages}) != 1
            or self.member_publication_receipt_storage.run_id
            == review_storages[0].run_id
            or self.post_submission_identity_mapping_commitment_id
            != self.material_commitment_id
            or self.post_submission_identity_mapping_commitment_sha256
            != self.material_commitment_sha256
            or self.presenter_submission_contains_provider_or_model_identity
            is not False
            or self.presenter_submission_contains_blind_to_option_mapping is not False
            or self.identity_mapping_persisted_only_after_sealed_submission is not True
            or self.reveal_mapping_present is not False
            or self.human_review_substituted_by_model is not False
            or self.semantic_authority_granted is not False
            or self.production_authority_granted is not False
            or type(self.human_review_passed) is not bool
        ):
            raise ValueError("C4 Stage 1 review family evidence is inconsistent")
        return self


class C4Stage1HumanReviewRunAnchor(FrozenArtifactModel):
    """Final create-only anchor for both sealed Stage 1 family reviews."""

    schema_version: Literal["rei-c4-stage1-human-review-run-v1"] = (
        "rei-c4-stage1-human-review-run-v1"
    )
    review_run_anchor_id: NonEmptyId
    review_run_anchor_sha256: HashDigest
    review_run_id: NonEmptyId
    render_run_id: NonEmptyId
    render_inventory_anchor_id: NonEmptyId
    render_inventory_anchor_sha256: HashDigest
    render_inventory_anchor_storage: StoredArtifact
    render_artifact_inventory: tuple[StoredArtifact, ...]
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    prepared_anchor_storage: StoredArtifact
    operator_signing_cohort_id: NonEmptyId
    operator_signing_cohort_sha256: HashDigest
    families: tuple[
        C4Stage1ReviewFamilyEvidence,
        C4Stage1ReviewFamilyEvidence,
    ]
    artifact_inventory_before_anchor: tuple[StoredArtifact, ...]
    render_evidence_cold_verified_before_first_display: Literal[True] = True
    render_evidence_ready_required: Literal[True] = True
    both_family_submissions_sealed: Literal[True] = True
    family_review_count: Literal[2] = 2
    all_human_reviews_passed: bool
    identity_reveal_status: Literal[
        "post_seal_mapping_bound_no_compatible_reveal_artifact"
    ] = "post_seal_mapping_bound_no_compatible_reveal_artifact"
    post_submission_mapping_bound_by_both_sealed_records: Literal[True] = True
    pre_seal_review_artifacts_persisted_by_orchestrator: Literal[False] = False
    cold_anchor_alone_proves_historical_write_order: Literal[False] = False
    reveal_mapping_present: Literal[False] = False
    dino_gate_independent_and_not_evaluated_here: Literal[True] = True
    semantic_stage1_passed: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @classmethod
    def create(
        cls,
        *,
        review_run_id: str,
        render_outcome: C4Stage1RunOutcome,
        render_artifact_inventory: tuple[StoredArtifact, ...],
        prepared: C4Stage1PreparedAttempt,
        operator_signing_cohort_id: str,
        operator_signing_cohort_sha256: str,
        families: tuple[
            C4Stage1ReviewFamilyEvidence,
            C4Stage1ReviewFamilyEvidence,
        ],
        artifact_inventory_before_anchor: tuple[StoredArtifact, ...],
    ) -> "C4Stage1HumanReviewRunAnchor":
        body = {
            "schema_version": "rei-c4-stage1-human-review-run-v1",
            "review_run_id": review_run_id,
            "render_run_id": render_outcome.manifest.run_id,
            "render_inventory_anchor_id": (
                render_outcome.inventory_anchor.render_inventory_anchor_id
            ),
            "render_inventory_anchor_sha256": (
                render_outcome.inventory_anchor.render_inventory_anchor_sha256
            ),
            "render_inventory_anchor_storage": (
                render_outcome.inventory_anchor_storage
            ),
            "render_artifact_inventory": render_artifact_inventory,
            "prepared_attempt_id": prepared.prepared_attempt_id,
            "prepared_attempt_sha256": prepared.prepared_attempt_sha256,
            "prepared_anchor_storage": render_outcome.manifest.prepared_anchor_storage,
            "operator_signing_cohort_id": operator_signing_cohort_id,
            "operator_signing_cohort_sha256": operator_signing_cohort_sha256,
            "families": families,
            "artifact_inventory_before_anchor": artifact_inventory_before_anchor,
            "render_evidence_cold_verified_before_first_display": True,
            "render_evidence_ready_required": True,
            "both_family_submissions_sealed": True,
            "family_review_count": 2,
            "all_human_reviews_passed": all(
                family.human_review_passed for family in families
            ),
            "identity_reveal_status": (
                "post_seal_mapping_bound_no_compatible_reveal_artifact"
            ),
            "post_submission_mapping_bound_by_both_sealed_records": True,
            "pre_seal_review_artifacts_persisted_by_orchestrator": False,
            "cold_anchor_alone_proves_historical_write_order": False,
            "reveal_mapping_present": False,
            "dino_gate_independent_and_not_evaluated_here": True,
            "semantic_stage1_passed": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
            "generated_images_are_external_evidence": False,
            "model_judge_calls": 0,
        }
        return cls(
            review_run_anchor_id=content_id("c4_stage1_review_run", body),
            review_run_anchor_sha256=_canonical_sha256(body),
            **body,
        )

    @model_validator(mode="after")
    def validate_anchor(self) -> Self:
        paths = tuple(
            item.relative_path for item in self.artifact_inventory_before_anchor
        )
        family_storages = tuple(
            sorted(
                (
                    storage
                    for family in self.families
                    for storage in family.review_artifact_storages()
                ),
                key=lambda item: item.relative_path,
            )
        )
        if (
            tuple(item.editor_role for item in self.families)
            != ("primary", "alternate")
            or paths != _expected_review_paths()
            or len(paths) != len(set(paths))
            or len(family_storages) != 20
            or len({item.storage_id for item in family_storages}) != 20
            or family_storages != self.artifact_inventory_before_anchor
            or any(
                item.run_id != self.review_run_id
                for item in self.artifact_inventory_before_anchor
            )
            or self.render_inventory_anchor_storage.run_id != self.render_run_id
            or self.prepared_anchor_storage.run_id != self.render_run_id
            or any(
                item.run_id != self.render_run_id
                for item in self.render_artifact_inventory
            )
            or self.render_inventory_anchor_storage
            not in self.render_artifact_inventory
            or self.prepared_anchor_storage not in self.render_artifact_inventory
            or any(
                family.member_publication_receipt_storage
                not in self.render_artifact_inventory
                for family in self.families
            )
            or self.all_human_reviews_passed
            != all(family.human_review_passed for family in self.families)
            or self.identity_reveal_status
            != "post_seal_mapping_bound_no_compatible_reveal_artifact"
            or self.post_submission_mapping_bound_by_both_sealed_records is not True
            or self.pre_seal_review_artifacts_persisted_by_orchestrator is not False
            or self.cold_anchor_alone_proves_historical_write_order is not False
            or self.reveal_mapping_present is not False
            or self.semantic_stage1_passed is not False
            or self.semantic_authority_granted is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 review run anchor is inconsistent")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"review_run_anchor_id", "review_run_anchor_sha256"},
        )
        if self.review_run_anchor_id != content_id(
            "c4_stage1_review_run", body
        ) or self.review_run_anchor_sha256 != _canonical_sha256(body):
            raise ValueError("C4 Stage 1 review run anchor differs from content")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1HumanReviewRunOutcome:
    anchor: C4Stage1HumanReviewRunAnchor
    anchor_storage: StoredArtifact


@dataclass(frozen=True, slots=True)
class _FamilyRuntime:
    editor_role: Literal["primary", "alternate"]
    publication: C4Stage1MemberPublicationReceipt
    publication_storage: StoredArtifact
    operator_policy: C4HumanReviewOperatorPolicy
    commitment: C4ReviewMaterialCommitment
    packet: C4BlindReviewPacket
    presentation: C4BlindPresentationManifest
    presenter_submission: C4Stage1AuthenticatedReviewEnvelope
    display_receipt: C4Stage1DisplayExecutionReceipt
    consumed_display_receipt: C4Stage1ConsumedDisplayReceipt
    claim: C4Stage1HumanReviewUnsignedClaim
    operator_attestation: C4Stage1HumanReviewOperatorAttestation
    sealed_submission: C4Stage1SealedHumanReviewSubmission
    gate: C4Stage1HumanReviewGateResult


@dataclass(frozen=True, slots=True)
class _PendingFamily:
    editor_role: Literal["primary", "alternate"]
    publication: C4Stage1MemberPublicationReceipt
    publication_storage: StoredArtifact
    operator_policy: C4HumanReviewOperatorPolicy
    commitment: C4ReviewMaterialCommitment
    packet: C4BlindReviewPacket
    presentation: C4BlindPresentationManifest
    submission_receipt: C4Stage1AuthenticatedPresenterSubmission
    operator_signing_lease: C4Stage1OperatorSigningLease
    display_receipt: C4Stage1DisplayExecutionReceipt
    consumed_display_receipt: C4Stage1ConsumedDisplayReceipt
    claim: C4Stage1HumanReviewUnsignedClaim


def _strict_json_object(value: bytes) -> dict[str, object]:
    if type(value) is not bytes or not 0 < len(value) <= _MAX_SUBMISSION_BYTES:
        raise C4Stage1ReviewRunError("Presenter submission is not bounded bytes")

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in items:
            if key in result:
                raise C4Stage1ReviewRunError(
                    "Presenter submission contains a duplicate field"
                )
            result[key] = item
        return result

    try:
        decoded = json.loads(value.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, C4Stage1ReviewRunError):
            raise
        raise C4Stage1ReviewRunError("Presenter submission is invalid JSON") from exc
    if type(decoded) is not dict or canonical_json_bytes(decoded) != value:
        raise C4Stage1ReviewRunError(
            "Presenter submission is not one canonical JSON object"
        )
    return decoded


def _strict_bool_mapping(
    value: object, expected: tuple[str, ...], *, label: str
) -> dict[str, bool]:
    if type(value) is not dict or set(value) != set(expected):
        raise C4Stage1ReviewRunError(f"{label} has incomplete judgment fields")
    if any(type(value[field]) is not bool for field in expected):
        raise C4Stage1ReviewRunError(f"{label} contains a non-boolean judgment")
    return {field: value[field] for field in expected}  # type: ignore[misc]


def _submission_judgments(
    packet: C4BlindReviewPacket,
    value: bytes,
) -> tuple[
    str,
    tuple[object, object],
    C4PairHumanJudgment,
]:
    decoded = _strict_json_object(value)
    expected_keys = {
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
    if set(decoded) != expected_keys:
        raise C4Stage1ReviewRunError("Presenter submission has unexpected fields")
    if (
        decoded["ipcProtocol"] != C4_STAGE1_REVIEW_IPC_PROTOCOL
        or decoded["serviceSchemaRevision"] != C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION
        or decoded["ledgerSchemaRevision"] != C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION
        or decoded["packetId"] != packet.packet_id
        or decoded["packetSha256"] != packet.packet_sha256
        or decoded["sourceImageSha256"] != packet.source_image_sha256
    ):
        raise C4Stage1ReviewRunError(
            "Presenter submission differs from the displayed packet"
        )
    reviewer = decoded["reviewerPseudonym"]
    if (
        type(reviewer) is not str
        or not reviewer
        or reviewer.strip() != reviewer
        or len(reviewer) > 200
    ):
        raise C4Stage1ReviewRunError("Reviewer pseudonym is invalid")
    raw_outputs = decoded["outputs"]
    if type(raw_outputs) is not list or len(raw_outputs) != 2:
        raise C4Stage1ReviewRunError("Presenter submission requires two outputs")
    judgments: list[object] = []
    for index, (raw, reference) in enumerate(
        zip(raw_outputs, packet.outputs, strict=True)
    ):
        if type(raw) is not dict or set(raw) != {
            "blindCode",
            "instructionSha256",
            "outputSha256",
            "judgments",
        }:
            raise C4Stage1ReviewRunError(
                f"Presenter output {index + 1} has unexpected fields"
            )
        if (
            raw["blindCode"] != reference.blind_code
            or raw["instructionSha256"] != reference.instruction_sha256
            or raw["outputSha256"] != reference.output_sha256
        ):
            raise C4Stage1ReviewRunError(
                "Presenter output differs from its displayed blind binding"
            )
        fields = _strict_bool_mapping(
            raw["judgments"],
            _OUTPUT_BOOLEAN_FIELDS,
            label=f"Presenter output {index + 1}",
        )
        judgments.append(
            record_c4_output_human_judgment(
                packet,
                blind_code=reference.blind_code,
                **fields,
            )
        )
    pair_fields = _strict_bool_mapping(
        decoded["pairJudgments"],
        _PAIR_BOOLEAN_FIELDS,
        label="Presenter pair judgment",
    )
    pair = C4PairHumanJudgment(**pair_fields)
    return reviewer, tuple(judgments), pair  # type: ignore[return-value]


def _assert_submission_stays_blind(
    submission: bytes,
    commitment: C4ReviewMaterialCommitment,
    *,
    hidden_identity_tokens: tuple[str, ...],
) -> None:
    """Reject provider identity or the hidden blind-to-option mapping."""

    decoded = _strict_json_object(submission)
    visible_text = json.dumps(
        decoded,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).casefold()
    forbidden = tuple(
        sorted(
            {
                *hidden_identity_tokens,
                *_identity_aliases(commitment.renderer_id),
                *_identity_aliases(commitment.model_id),
                *_identity_aliases(commitment.model_revision),
                *(item.option_id for item in commitment.options),
            },
            key=lambda item: (item.casefold(), item),
        )
    )
    _assert_visible_text_stays_blind(
        visible_text,
        forbidden,
        label="Presenter canonical submission",
    )


def _publication_storage(
    outcome: C4Stage1RunOutcome,
    role: Literal["primary", "alternate"],
) -> StoredArtifact:
    members = tuple(
        member for member in outcome.manifest.member_runs if member.editor_role == role
    )
    if len(members) != 1 or not members[0].publication_completed:
        raise C4Stage1ReviewRunError(
            f"C4 Stage 1 {role} family was not atomically published"
        )
    storages = tuple(
        terminal.member_publication_receipt_storage
        for terminal in members[0].worker_terminals
    )
    if len(storages) != 2 or storages[0] is None or storages[0] != storages[1]:
        raise C4Stage1ReviewRunError(
            f"C4 Stage 1 {role} publication marker is incomplete"
        )
    return storages[0]


def _prepared_family_inputs(
    prepared: C4Stage1PreparedAttempt,
    publication: C4Stage1MemberPublicationReceipt,
) -> tuple[
    C4HumanReviewOperatorPolicy,
    tuple[C4ReviewOptionMaterial, C4ReviewOptionMaterial],
    str,
    str,
    str,
    tuple[str, ...],
]:
    policies = tuple(
        item
        for item in prepared.review_operator_policies
        if item.candidate_slot_id == publication.provider_slot_id
    )
    all_hidden_identity_tokens = {
        alias
        for worker in prepared.workers
        for alias in _hidden_identity_tokens(worker.worker_request.editor_spec)
    }
    workers = {
        item.prepared_worker_id: item
        for item in prepared.workers
        if item.editor_role == publication.editor_role
    }
    if len(policies) != 1 or len(workers) != 2:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 publication lacks one distinct prepared review policy"
        )
    policy = policies[0]
    options = []
    identities = []
    for candidate in publication.candidate_receipts:
        worker = workers.get(candidate.prepared_worker_id)
        if (
            worker is None
            or worker.option_id != candidate.option_id
            or worker.worker_request.worker_request_id != candidate.worker_request_id
        ):
            raise C4Stage1ReviewRunError(
                "C4 Stage 1 publication differs from its prepared worker"
            )
        spec = worker.worker_request.editor_spec
        identities.append((spec.provider.provider_id, spec.repo_id, spec.revision))
        instruction = worker.worker_request.render_request.prompt
        _assert_visible_text_stays_blind(
            instruction,
            tuple(all_hidden_identity_tokens),
            label="C4 Stage 1 visible instruction",
        )
        options.append(
            make_c4_review_option_material(
                option_id=candidate.option_id,
                instruction=instruction,
                output_sha256=candidate.staged_png_sha256,
            )
        )
    if len(set(identities)) != 1:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 family publication mixes renderer identities"
        )
    renderer_id, model_id, model_revision = identities[0]
    return (
        policy,
        tuple(options),  # type: ignore[return-value]
        renderer_id,
        model_id,
        model_revision,
        tuple(
            sorted(
                all_hidden_identity_tokens,
                key=lambda item: (item.casefold(), item),
            )
        ),
    )


def _family_material(
    render_store: FileArtifactStore,
    prepared: C4Stage1PreparedAttempt,
    publication: C4Stage1MemberPublicationReceipt,
    publication_storage: StoredArtifact,
) -> tuple[
    C4HumanReviewOperatorPolicy,
    C4ReviewMaterialCommitment,
    C4BlindReviewPacket,
    C4BlindPresentationManifest,
    tuple[str, ...],
]:
    (
        policy,
        options,
        renderer_id,
        model_id,
        model_revision,
        hidden_identity_tokens,
    ) = _prepared_family_inputs(prepared, publication)
    commitment = commit_c4_review_material(
        prepared.review_schema,
        operator_policy=policy,
        source_image_sha256=prepared.screen_contract.source.source_png_sha256,
        renderer_id=renderer_id,
        model_id=model_id,
        model_revision=model_revision,
        options=options,
    )
    packet = prepare_c4_blind_review(
        prepared.review_schema,
        commitment,
        operator_policy=policy,
    )
    by_option = {
        candidate.option_id: candidate.staged_output_storage
        for candidate in publication.candidate_receipts
    }
    source_path = render_store.artifact_path(
        prepared.run_id,
        prepared.screen_contract.fixture.source_image.path,
    )
    output_paths = tuple(
        render_store.artifact_path(
            prepared.run_id,
            by_option[reference.option_id].relative_path,
        )
        for reference in packet.outputs
    )
    presentation = build_c4_blind_presentation_manifest(
        packet,
        operator_policy=policy,
        source_png_path=source_path,
        output_png_paths=output_paths,  # type: ignore[arg-type]
    )
    if publication_storage.run_id != prepared.run_id:
        raise C4Stage1ReviewRunError("C4 Stage 1 publication cites another run")
    return policy, commitment, packet, presentation, hidden_identity_tokens


def _review_ui_session_id() -> str:
    return content_id(
        "c4_stage1_review_ui_session",
        {"cryptographic_nonce": secrets.token_hex(32)},
    )


def _verify_review_ui_session(
    *,
    review_run_id: str,
    editor_role: Literal["primary", "alternate"],
    packet: C4BlindReviewPacket,
    publication: C4Stage1MemberPublicationReceipt,
    display_receipt: C4Stage1DisplayExecutionReceipt,
) -> None:
    session = display_receipt.context.ui_session_id
    if (
        not session.startswith("c4_stage1_review_ui_session_")
        or editor_role in session
        or review_run_id in session
        or packet.packet_id in session
        or publication.member_publication_receipt_id in session
    ):
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 display receipt cites another review UI session"
        )


def _review_one_family(
    render_store: FileArtifactStore,
    prepared: C4Stage1PreparedAttempt,
    publication: C4Stage1MemberPublicationReceipt,
    publication_storage: StoredArtifact,
    *,
    prepared_anchor_storage_value: StoredArtifact,
    review_run_id: str,
    review_service: C4Stage1ReviewServiceClient,
    display_port: C4Stage1ReviewDisplayPort,
    display_verifier: C4Stage1ReviewDisplayAttestationVerifier,
    display_ledger: C4Stage1ReviewDisplayReceiptLedger,
    clock: Callable[[], datetime],
) -> _PendingFamily:
    policy, commitment, packet, presentation, hidden_identity_tokens = _family_material(
        render_store,
        prepared,
        publication,
        publication_storage,
    )
    session_id = _review_ui_session_id()
    display_receipt = execute_c4_stage1_display(
        render_store,
        prepared_anchor_storage=prepared_anchor_storage_value,
        member_publication_receipt_storage=publication_storage,
        schema=prepared.review_schema,
        packet=packet,
        operator_policy=policy,
        display_attester_policy=prepared.display_policy,
        presentation_manifest=presentation,
        display_port=display_port,
        display_attestation_verifier=display_verifier,
        ui_implementation_id=C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
        ui_revision=C4_STAGE1_REVIEW_PRESENTER_REVISION,
        ui_session_id=session_id,
        clock=clock,
    )
    submission_receipt = review_service.take_presentation_submission(
        context_id=display_receipt.context.context_id
    )
    presenter_submission = submission_receipt.canonical_submission_bytes
    _assert_submission_stays_blind(
        presenter_submission,
        commitment,
        hidden_identity_tokens=hidden_identity_tokens,
    )
    reviewer, output_judgments, pair_judgment = _submission_judgments(
        packet, presenter_submission
    )
    consumed_display = consume_c4_stage1_display_receipt_once(
        display_ledger, display_receipt
    )
    operator_signing_lease = review_service.issue_operator_signing_lease(
        operator_policy=policy,
        submission_receipt=submission_receipt,
        display_receipt=display_receipt,
        consumed_display_receipt=consumed_display,
    )
    claim = build_c4_stage1_operator_unsigned_claim(
        prepared.review_schema,
        packet,
        operator_policy=policy,
        screen_contract=prepared.screen_contract,
        display_attester_policy=prepared.display_policy,
        presentation_manifest=presentation,
        display_receipt=display_receipt,
        consumed_display_receipt=consumed_display,
        reviewer_pseudonym=reviewer,
        review_timestamp=operator_signing_lease.review_timestamp,
        output_judgments=output_judgments,  # type: ignore[arg-type]
        pair_judgment=pair_judgment,
        submission_receipt_id=submission_receipt.submission_receipt_id,
        submission_receipt_sha256=submission_receipt.submission_receipt_sha256,
        operator_signing_lease_id=(operator_signing_lease.operator_signing_lease_id),
        operator_signing_lease_sha256=(
            operator_signing_lease.operator_signing_lease_sha256
        ),
    )
    return _PendingFamily(
        editor_role=publication.editor_role,
        publication=publication,
        publication_storage=publication_storage,
        operator_policy=policy,
        commitment=commitment,
        packet=packet,
        presentation=presentation,
        submission_receipt=submission_receipt,
        operator_signing_lease=operator_signing_lease,
        display_receipt=display_receipt,
        consumed_display_receipt=consumed_display,
        claim=claim,
    )


def _seal_pending_family(
    pending: _PendingFamily,
    *,
    operator_attestation: C4Stage1HumanReviewOperatorAttestation,
    prepared: C4Stage1PreparedAttempt,
    render_store: FileArtifactStore,
    operator_verifier: C4Stage1ReviewOperatorAttestationVerifier,
    operator_ledger: C4Stage1ReviewOperatorPolicyLedger,
    display_verifier: C4Stage1ReviewDisplayAttestationVerifier,
    display_ledger: C4Stage1ReviewDisplayReceiptLedger,
) -> _FamilyRuntime:
    sealed = seal_c4_stage1_human_review(
        prepared.review_schema,
        pending.packet,
        artifact_store=render_store,
        operator_policy=pending.operator_policy,
        screen_contract=prepared.screen_contract,
        display_attester_policy=prepared.display_policy,
        presentation_manifest=pending.presentation,
        display_receipt=pending.display_receipt,
        consumed_display_receipt=pending.consumed_display_receipt,
        operator_attestation=operator_attestation,
        operator_secret=None,
        display_attestation_verifier=display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
        operator_attestation_verifier=operator_verifier,
    )
    gate = evaluate_c4_stage1_human_review(
        prepared.review_schema,
        pending.packet,
        artifact_store=render_store,
        operator_policy=pending.operator_policy,
        screen_contract=prepared.screen_contract,
        display_attester_policy=prepared.display_policy,
        operator_secret=None,
        display_attestation_verifier=display_verifier,
        display_receipt_ledger=display_ledger,
        used_policy_ledger=operator_ledger,
        operator_attestation_verifier=operator_verifier,
        submission=sealed,
    )
    envelope = C4Stage1AuthenticatedReviewEnvelope.create(
        submission_receipt=pending.submission_receipt,
        operator_signing_lease=pending.operator_signing_lease,
    )
    return _FamilyRuntime(
        editor_role=pending.editor_role,
        publication=pending.publication,
        publication_storage=pending.publication_storage,
        operator_policy=pending.operator_policy,
        commitment=pending.commitment,
        packet=pending.packet,
        presentation=pending.presentation,
        presenter_submission=envelope,
        display_receipt=pending.display_receipt,
        consumed_display_receipt=pending.consumed_display_receipt,
        claim=pending.claim,
        operator_attestation=operator_attestation,
        sealed_submission=sealed,
        gate=gate,
    )


def _sign_pending_family_cohort(
    pending_families: tuple[_PendingFamily, _PendingFamily],
    *,
    operator_verifier: C4Stage1ReviewOperatorAttestationVerifier,
) -> tuple[
    C4Stage1HumanReviewOperatorAttestation,
    C4Stage1HumanReviewOperatorAttestation,
]:
    """Create both operator HMACs in one complete service transaction."""

    if type(pending_families) is not tuple or len(pending_families) != 2:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 operator signing cohort must contain two reviews"
        )
    requests = tuple(
        C4Stage1OperatorSigningRequest(
            operator_policy=pending.operator_policy,
            claim=pending.claim,
            submission_receipt=pending.submission_receipt,
            operator_signing_lease=pending.operator_signing_lease,
            display_receipt=pending.display_receipt,
            consumed_display_receipt=pending.consumed_display_receipt,
        )
        for pending in pending_families
    )
    attestations = operator_verifier.sign_claim_cohort(
        reviews=requests  # type: ignore[arg-type]
    )
    if type(attestations) is not tuple or len(attestations) != 2:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 operator signing service returned an incomplete cohort"
        )
    validated: list[C4Stage1HumanReviewOperatorAttestation] = []
    for request, attestation in zip(requests, attestations, strict=True):
        if (
            type(attestation) is not C4Stage1HumanReviewOperatorAttestation
            or attestation.claim != request.claim
            or operator_verifier.verify_attestation(
                operator_policy=request.operator_policy,
                attestation=attestation,
            )
            is not True
        ):
            raise C4Stage1ReviewRunError(
                "C4 Stage 1 operator signing service returned another review"
            )
        validated.append(attestation)
    if len({item.attestation_id for item in validated}) != 2:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 operator signing service duplicated a cohort member"
        )
    return validated[0], validated[1]


def _persist_family(
    store: FileArtifactStore,
    review_run_id: str,
    family: _FamilyRuntime,
) -> C4Stage1ReviewFamilyEvidence:
    role = family.editor_role
    values: tuple[tuple[str, object | bytes], ...] = (
        ("material-commitment", family.commitment),
        ("blind-packet", family.packet),
        ("presentation-manifest", family.presentation),
        ("presenter-submission", family.presenter_submission),
        ("display-receipt", family.display_receipt),
        ("consumed-display-receipt", family.consumed_display_receipt),
        ("unsigned-claim", family.claim),
        ("operator-attestation", family.operator_attestation),
        ("sealed-submission", family.sealed_submission),
        ("gate-result", family.gate),
    )
    storages = []
    for label, value in values:
        path = _artifact_path(role, label)
        if type(value) is bytes:
            storage = store.write_bytes(review_run_id, path, value, overwrite=False)
        else:
            storage = store.write_json(review_run_id, path, value, overwrite=False)
        storages.append(storage)
    return C4Stage1ReviewFamilyEvidence(
        editor_role=role,
        member_publication_receipt_storage=family.publication_storage,
        operator_policy_id=family.operator_policy.policy_id,
        operator_policy_sha256=family.operator_policy.operator_policy_sha256,
        material_commitment_id=family.commitment.commitment_id,
        material_commitment_sha256=family.commitment.material_commitment_sha256,
        material_commitment_storage=storages[0],
        packet_id=family.packet.packet_id,
        packet_sha256=family.packet.packet_sha256,
        packet_storage=storages[1],
        presentation_manifest_id=family.presentation.presentation_manifest_id,
        presentation_manifest_sha256=(family.presentation.presentation_manifest_sha256),
        presentation_manifest_storage=storages[2],
        presenter_submission_storage=storages[3],
        display_receipt_id=family.display_receipt.display_receipt_id,
        display_receipt_sha256=family.display_receipt.display_receipt_sha256,
        display_receipt_storage=storages[4],
        consumed_display_receipt_id=(
            family.consumed_display_receipt.consumed_display_receipt_id
        ),
        consumed_display_receipt_sha256=(
            family.consumed_display_receipt.consumed_display_receipt_sha256
        ),
        consumed_display_receipt_storage=storages[5],
        claim_id=family.claim.claim_id,
        claim_sha256=family.claim.claim_sha256,
        unsigned_claim_storage=storages[6],
        operator_attestation_id=family.operator_attestation.attestation_id,
        operator_attestation_sha256=family.operator_attestation.attestation_sha256,
        operator_attestation_storage=storages[7],
        sealed_submission_id=family.sealed_submission.submission_id,
        sealed_submission_storage=storages[8],
        gate_result_id=family.gate.gate_result_id,
        gate_result_storage=storages[9],
        human_review_passed=family.gate.human_review_passed,
        post_submission_identity_mapping_commitment_id=(
            family.commitment.commitment_id
        ),
        post_submission_identity_mapping_commitment_sha256=(
            family.commitment.material_commitment_sha256
        ),
    )


def _assert_distinct_stores(
    render_store: FileArtifactStore, review_store: FileArtifactStore
) -> None:
    if not isinstance(render_store, FileArtifactStore) or not isinstance(
        review_store, FileArtifactStore
    ):
        raise TypeError("C4 Stage 1 review requires two FileArtifactStore instances")
    render_root = render_store.root
    review_root = review_store.root
    if (
        render_store is review_store
        or render_root == review_root
        or render_root.is_relative_to(review_root)
        or review_root.is_relative_to(render_root)
    ):
        raise C4Stage1ReviewRunError(
            "Render and review artifact stores must be non-overlapping"
        )


def _completed_operator_signing_cohort_identity(
    review_service: C4Stage1ReviewServiceClient,
) -> tuple[str, str]:
    """Read the exact already-verified singleton cohort identity."""

    health = review_service.health()
    counts = health.get("ledger_counts") if isinstance(health, Mapping) else None
    cohort_id = (
        health.get("operator_signing_cohort_id")
        if isinstance(health, Mapping)
        else None
    )
    cohort_sha256 = (
        health.get("operator_signing_cohort_sha256")
        if isinstance(health, Mapping)
        else None
    )
    if (
        not isinstance(counts, Mapping)
        or set(counts)
        != {
            "display_attestation_uses",
            "display_receipt_uses",
            "operator_policy_uses",
            "presenter_submissions",
            "operator_signing_leases",
        }
        or any(type(value) is not int or value != 2 for value in counts.values())
        or health.get("operator_signing_cohort_complete") is not True
        or type(cohort_id) is not str
        or not cohort_id
        or type(cohort_sha256) is not str
        or len(cohort_sha256) != 64
        or any(character not in "0123456789abcdef" for character in cohort_sha256)
    ):
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 completed signing cohort identity is unavailable"
        )
    return cohort_id, cohort_sha256


def _verify_repository_gate(
    prepared: C4Stage1PreparedAttempt,
    repository_root: str | Path,
) -> None:
    try:
        current = capture_c4_stage1_repository_gate(Path(repository_root))
    except Exception as exc:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 repository gate is not currently clean and exact"
        ) from exc
    if current != prepared.repository_gate:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 repository gate changed after render preparation"
        )


def run_c4_stage1_human_review(
    render_artifact_store: FileArtifactStore,
    render_inventory_anchor_storage: StoredArtifact,
    prepared_anchor_storage_value: StoredArtifact,
    member_publication_receipt_storages: tuple[StoredArtifact, StoredArtifact],
    review_artifact_store: FileArtifactStore,
    *,
    review_run_id: str,
    confirmed_render_inventory_anchor_id: str,
    confirmed_render_inventory_anchor_sha256: str,
    confirmed_prepared_attempt_id: str,
    confirmed_prepared_attempt_sha256: str,
    repository_root: str | Path,
    review_service: C4Stage1ReviewServiceClient,
    clock: Callable[[], datetime] = utc_now,
) -> C4Stage1HumanReviewRunOutcome:
    """Seal both family reviews without ever extending the render run tree."""

    _assert_distinct_stores(render_artifact_store, review_artifact_store)
    if (
        type(member_publication_receipt_storages) is not tuple
        or len(member_publication_receipt_storages) != 2
    ):
        raise ValueError("C4 Stage 1 review requires two publication descriptors")

    # This is intentionally the first operation that can inspect evidence.  No
    # service/display method and no review-store write precedes it.
    render_outcome = cold_verify_c4_stage1_run(
        render_artifact_store, render_inventory_anchor_storage
    )
    if (
        render_outcome.inventory_anchor_storage != render_inventory_anchor_storage
        or render_outcome.manifest.status != "evidence_ready"
        or not render_outcome.manifest.render_technical_completed
        or render_outcome.inventory_anchor.render_inventory_anchor_id
        != confirmed_render_inventory_anchor_id
        or render_outcome.inventory_anchor.render_inventory_anchor_sha256
        != confirmed_render_inventory_anchor_sha256
    ):
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 render run is not the confirmed evidence-ready anchor"
        )
    prepared_outcome = cold_verify_c4_stage1_prepared_attempt(
        render_artifact_store,
        prepared_anchor_storage_value,
        require_exact_pre_spawn_inventory=False,
    )
    prepared = prepared_outcome.prepared_attempt
    if (
        prepared_outcome.prepared_anchor_storage != prepared_anchor_storage_value
        or render_outcome.manifest.prepared_anchor_storage
        != prepared_anchor_storage_value
        or prepared.prepared_attempt_id != confirmed_prepared_attempt_id
        or prepared.prepared_attempt_sha256 != confirmed_prepared_attempt_sha256
        or render_outcome.manifest.prepared_attempt_id != confirmed_prepared_attempt_id
        or render_outcome.manifest.prepared_attempt_sha256
        != confirmed_prepared_attempt_sha256
    ):
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 review confirmation differs from the prepared attempt"
        )
    _verify_repository_gate(prepared, repository_root)
    render_inventory = render_artifact_store.inspect_run_inventory_exact(
        prepared.run_id
    )
    expected_publication_storages = tuple(
        _publication_storage(render_outcome, role) for role in _FAMILY_ROLES
    )
    if member_publication_receipt_storages != expected_publication_storages:
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 publication descriptors are not in primary/alternate order"
        )
    publications = tuple(
        cold_verify_c4_stage1_member_publication(
            render_artifact_store,
            storage,
            prepared,
        )
        for storage in member_publication_receipt_storages
    )
    if tuple(item.editor_role for item in publications) != _FAMILY_ROLES:
        raise C4Stage1ReviewRunError("C4 Stage 1 publications changed family order")
    if (
        len({item.provider_slot_id for item in publications}) != 2
        or len({item.policy_id for item in prepared.review_operator_policies}) != 2
    ):
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 review requires two distinct prepared operator policies"
        )
    review_path = review_artifact_store.run_path(review_run_id)
    if review_path.exists():
        raise C4Stage1ReviewRunError("C4 Stage 1 review run must be fresh")

    verify_c4_stage1_live_review_boundary(
        repository_root=Path(repository_root),
        repository_gate=prepared.repository_gate,
        review_runtime_manifest=prepared.review_runtime_manifest,
        review_service_readiness=prepared.review_service_readiness,
        review_service=review_service,
        expected_completed_review_count=0,
    )
    display_port = C4Stage1ReviewDisplayPort(review_service)
    display_verifier = C4Stage1ReviewDisplayAttestationVerifier(review_service)
    display_ledger = C4Stage1ReviewDisplayReceiptLedger(review_service)
    operator_verifier = C4Stage1ReviewOperatorAttestationVerifier(review_service)
    operator_ledger = C4Stage1ReviewOperatorPolicyLedger(review_service)

    presentation_pairs = list(
        zip(publications, member_publication_receipt_storages, strict=True)
    )
    if secrets.randbelow(2) == 1:
        presentation_pairs.reverse()
    pending_families = tuple(
        _review_one_family(
            render_artifact_store,
            prepared,
            publication,
            storage,
            prepared_anchor_storage_value=prepared_anchor_storage_value,
            review_run_id=review_run_id,
            review_service=review_service,
            display_port=display_port,
            display_verifier=display_verifier,
            display_ledger=display_ledger,
            clock=clock,
        )
        for publication, storage in presentation_pairs
    )
    if {item.editor_role for item in pending_families} != set(_FAMILY_ROLES):
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 randomized review cohort is incomplete"
        )
    operator_attestations = _sign_pending_family_cohort(
        pending_families,  # type: ignore[arg-type]
        operator_verifier=operator_verifier,
    )
    sealed_in_random_order = tuple(
        _seal_pending_family(
            pending,
            operator_attestation=operator_attestation,
            prepared=prepared,
            render_store=render_artifact_store,
            operator_verifier=operator_verifier,
            operator_ledger=operator_ledger,
            display_verifier=display_verifier,
            display_ledger=display_ledger,
        )
        for pending, operator_attestation in zip(
            pending_families, operator_attestations, strict=True
        )
    )
    runtime_families = tuple(
        next(item for item in sealed_in_random_order if item.editor_role == role)
        for role in _FAMILY_ROLES
    )
    if tuple(item.editor_role for item in runtime_families) != _FAMILY_ROLES:
        raise C4Stage1ReviewRunError("C4 Stage 1 post-seal canonical order changed")
    verify_c4_stage1_live_review_boundary(
        repository_root=Path(repository_root),
        repository_gate=prepared.repository_gate,
        review_runtime_manifest=prepared.review_runtime_manifest,
        review_service_readiness=prepared.review_service_readiness,
        review_service=review_service,
        expected_completed_review_count=2,
    )
    operator_signing_cohort_id, operator_signing_cohort_sha256 = (
        _completed_operator_signing_cohort_identity(review_service)
    )

    # Only now, after both submissions are sealed, may portable commitments
    # containing the hidden identity mapping enter the separate review run.
    families = tuple(
        _persist_family(review_artifact_store, review_run_id, item)
        for item in runtime_families
    )
    inventory_before_anchor = review_artifact_store.inspect_run_inventory_exact(
        review_run_id
    )
    anchor = C4Stage1HumanReviewRunAnchor.create(
        review_run_id=review_run_id,
        render_outcome=render_outcome,
        render_artifact_inventory=render_inventory,
        prepared=prepared,
        operator_signing_cohort_id=operator_signing_cohort_id,
        operator_signing_cohort_sha256=operator_signing_cohort_sha256,
        families=families,  # type: ignore[arg-type]
        artifact_inventory_before_anchor=inventory_before_anchor,
    )
    anchor_storage = review_artifact_store.write_json(
        review_run_id,
        C4_STAGE1_REVIEW_RUN_ANCHOR_PATH,
        anchor,
        overwrite=False,
    )
    outcome = cold_verify_c4_stage1_human_review_run(
        render_artifact_store,
        review_artifact_store,
        anchor_storage,
        repository_root=repository_root,
        review_service=review_service,
    )
    final_render = cold_verify_c4_stage1_run(
        render_artifact_store, render_inventory_anchor_storage
    )
    if (
        final_render != render_outcome
        or render_artifact_store.inspect_run_inventory_exact(prepared.run_id)
        != render_inventory
    ):
        raise C4Stage1ReviewRunError("C4 Stage 1 render tree changed during review")
    return outcome


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _load_model(
    store: FileArtifactStore,
    storage: StoredArtifact,
    model_type: type[_ModelT],
) -> _ModelT:
    value = store.read_verified(storage)
    model = model_type.model_validate_json(value)
    if canonical_json_bytes(model) != value:
        raise C4Stage1ReviewRunError("Review artifact is not canonical JSON")
    return model


def cold_verify_c4_stage1_human_review_run(
    render_artifact_store: FileArtifactStore,
    review_artifact_store: FileArtifactStore,
    review_anchor_storage: StoredArtifact,
    *,
    repository_root: str | Path,
    review_service: C4Stage1ReviewServiceClient,
) -> C4Stage1HumanReviewRunOutcome:
    """Cold-replay both portable submissions plus all live one-time ledgers."""

    _assert_distinct_stores(render_artifact_store, review_artifact_store)
    anchor_bytes = review_artifact_store.read_verified(review_anchor_storage)
    anchor = C4Stage1HumanReviewRunAnchor.model_validate_json(anchor_bytes)
    if (
        canonical_json_bytes(anchor) != anchor_bytes
        or review_anchor_storage.run_id != anchor.review_run_id
        or review_anchor_storage.relative_path != C4_STAGE1_REVIEW_RUN_ANCHOR_PATH
        or review_anchor_storage.content_sha256 != _sha256(anchor_bytes)
        or review_anchor_storage.size_bytes != len(anchor_bytes)
    ):
        raise C4Stage1ReviewRunError("C4 Stage 1 review anchor is inconsistent")
    actual_review_inventory = review_artifact_store.inspect_run_inventory_exact(
        anchor.review_run_id
    )
    expected_review_inventory = tuple(
        sorted(
            (*anchor.artifact_inventory_before_anchor, review_anchor_storage),
            key=lambda item: item.relative_path,
        )
    )
    flattened_family_inventory = tuple(
        sorted(
            (
                storage
                for family in anchor.families
                for storage in family.review_artifact_storages()
            ),
            key=lambda item: item.relative_path,
        )
    )
    if (
        actual_review_inventory != expected_review_inventory
        or flattened_family_inventory != anchor.artifact_inventory_before_anchor
        or len(flattened_family_inventory) != 20
        or len({item.storage_id for item in flattened_family_inventory}) != 20
        or any(
            item.run_id != anchor.review_run_id for item in flattened_family_inventory
        )
    ):
        raise C4Stage1ReviewRunError("C4 Stage 1 review inventory changed")
    render_outcome = cold_verify_c4_stage1_run(
        render_artifact_store, anchor.render_inventory_anchor_storage
    )
    render_inventory = render_artifact_store.inspect_run_inventory_exact(
        anchor.render_run_id
    )
    if (
        render_outcome.manifest.status != "evidence_ready"
        or render_outcome.inventory_anchor_storage
        != anchor.render_inventory_anchor_storage
        or render_outcome.inventory_anchor.render_inventory_anchor_id
        != anchor.render_inventory_anchor_id
        or render_outcome.inventory_anchor.render_inventory_anchor_sha256
        != anchor.render_inventory_anchor_sha256
        or render_inventory != anchor.render_artifact_inventory
    ):
        raise C4Stage1ReviewRunError("C4 Stage 1 render evidence changed")
    prepared_outcome = cold_verify_c4_stage1_prepared_attempt(
        render_artifact_store,
        anchor.prepared_anchor_storage,
        require_exact_pre_spawn_inventory=False,
    )
    prepared = prepared_outcome.prepared_attempt
    if (
        prepared.prepared_attempt_id != anchor.prepared_attempt_id
        or prepared.prepared_attempt_sha256 != anchor.prepared_attempt_sha256
        or prepared_outcome.prepared_anchor_storage != anchor.prepared_anchor_storage
    ):
        raise C4Stage1ReviewRunError("C4 Stage 1 prepared evidence changed")
    _verify_repository_gate(prepared, repository_root)
    verify_c4_stage1_live_review_boundary(
        repository_root=Path(repository_root),
        repository_gate=prepared.repository_gate,
        review_runtime_manifest=prepared.review_runtime_manifest,
        review_service_readiness=prepared.review_service_readiness,
        review_service=review_service,
        expected_completed_review_count=2,
    )
    live_operator_signing_cohort = _completed_operator_signing_cohort_identity(
        review_service
    )
    if live_operator_signing_cohort != (
        anchor.operator_signing_cohort_id,
        anchor.operator_signing_cohort_sha256,
    ):
        raise C4Stage1ReviewRunError(
            "C4 Stage 1 completed signing cohort differs from the review anchor"
        )
    display_verifier = C4Stage1ReviewDisplayAttestationVerifier(review_service)
    display_ledger = C4Stage1ReviewDisplayReceiptLedger(review_service)
    operator_verifier = C4Stage1ReviewOperatorAttestationVerifier(review_service)
    operator_ledger = C4Stage1ReviewOperatorPolicyLedger(review_service)

    for family in anchor.families:
        publication = cold_verify_c4_stage1_member_publication(
            render_artifact_store,
            family.member_publication_receipt_storage,
            prepared,
        )
        if publication.editor_role != family.editor_role:
            raise C4Stage1ReviewRunError("Review family cites another publication")
        policy = next(
            (
                item
                for item in prepared.review_operator_policies
                if item.policy_id == family.operator_policy_id
                and item.operator_policy_sha256 == family.operator_policy_sha256
                and item.candidate_slot_id == publication.provider_slot_id
            ),
            None,
        )
        if policy is None:
            raise C4Stage1ReviewRunError("Review family cites another operator policy")
        commitment = _load_model(
            review_artifact_store,
            family.material_commitment_storage,
            C4ReviewMaterialCommitment,
        )
        packet = _load_model(
            review_artifact_store, family.packet_storage, C4BlindReviewPacket
        )
        presentation = _load_model(
            review_artifact_store,
            family.presentation_manifest_storage,
            C4BlindPresentationManifest,
        )
        presenter_submission = _load_model(
            review_artifact_store,
            family.presenter_submission_storage,
            C4Stage1AuthenticatedReviewEnvelope,
        )
        display_receipt = _load_model(
            review_artifact_store,
            family.display_receipt_storage,
            C4Stage1DisplayExecutionReceipt,
        )
        consumed_display = _load_model(
            review_artifact_store,
            family.consumed_display_receipt_storage,
            C4Stage1ConsumedDisplayReceipt,
        )
        claim = _load_model(
            review_artifact_store,
            family.unsigned_claim_storage,
            C4Stage1HumanReviewUnsignedClaim,
        )
        attestation = _load_model(
            review_artifact_store,
            family.operator_attestation_storage,
            C4Stage1HumanReviewOperatorAttestation,
        )
        sealed = _load_model(
            review_artifact_store,
            family.sealed_submission_storage,
            C4Stage1SealedHumanReviewSubmission,
        )
        gate = _load_model(
            review_artifact_store,
            family.gate_result_storage,
            C4Stage1HumanReviewGateResult,
        )
        (
            expected_policy,
            expected_options,
            expected_renderer_id,
            expected_model_id,
            expected_model_revision,
            hidden_identity_tokens,
        ) = _prepared_family_inputs(prepared, publication)
        if (
            expected_policy != policy
            or commitment.operator_policy_id != policy.policy_id
            or commitment.operator_policy_sha256 != policy.operator_policy_sha256
            or commitment.source_image_sha256
            != prepared.screen_contract.source.source_png_sha256
            or commitment.renderer_id != expected_renderer_id
            or commitment.model_id != expected_model_id
            or commitment.model_revision != expected_model_revision
            or commitment.options != expected_options
            or packet
            != prepare_c4_blind_review(
                prepared.review_schema, commitment, operator_policy=policy
            )
        ):
            raise C4Stage1ReviewRunError("Stored review material changed")
        if (
            review_service.verify_authenticated_submission(
                submission_receipt=presenter_submission.submission_receipt
            )
            is not True
            or review_service.verify_operator_signing_lease(
                operator_signing_lease=presenter_submission.operator_signing_lease
            )
            is not True
        ):
            raise C4Stage1ReviewRunError(
                "Stored presenter submission authentication is unavailable"
            )
        presenter_submission_bytes = (
            presenter_submission.submission_receipt.canonical_submission_bytes
        )
        _assert_submission_stays_blind(
            presenter_submission_bytes,
            commitment,
            hidden_identity_tokens=hidden_identity_tokens,
        )
        by_option = {
            item.option_id: item.staged_output_storage
            for item in publication.candidate_receipts
        }
        expected_presentation = build_c4_blind_presentation_manifest(
            packet,
            operator_policy=policy,
            source_png_path=render_artifact_store.artifact_path(
                prepared.run_id,
                prepared.screen_contract.fixture.source_image.path,
            ),
            output_png_paths=tuple(
                render_artifact_store.artifact_path(
                    prepared.run_id,
                    by_option[item.option_id].relative_path,
                )
                for item in packet.outputs
            ),  # type: ignore[arg-type]
        )
        reviewer, judgments, pair = _submission_judgments(
            packet, presenter_submission_bytes
        )
        _verify_review_ui_session(
            review_run_id=anchor.review_run_id,
            editor_role=family.editor_role,
            packet=packet,
            publication=publication,
            display_receipt=display_receipt,
        )
        cold_verify_c4_stage1_display_execution_receipt(
            display_receipt,
            prepared.review_schema,
            packet,
            artifact_store=render_artifact_store,
            operator_policy=policy,
            screen_contract=prepared.screen_contract,
            display_attester_policy=prepared.display_policy,
            presentation_manifest=presentation,
        )
        if (
            presentation != expected_presentation
            or claim.output_judgments != judgments
            or claim.pair_judgment != pair
            or claim.reviewer_pseudonym != reviewer
            or claim.submission_receipt_id
            != presenter_submission.submission_receipt.submission_receipt_id
            or claim.submission_receipt_sha256
            != presenter_submission.submission_receipt.submission_receipt_sha256
            or claim.operator_signing_lease_id
            != presenter_submission.operator_signing_lease.operator_signing_lease_id
            or claim.operator_signing_lease_sha256
            != presenter_submission.operator_signing_lease.operator_signing_lease_sha256
            or claim.review_timestamp
            != presenter_submission.operator_signing_lease.review_timestamp
            or attestation.claim != claim
            or sealed.operator_attestation != attestation
            or sealed.consumed_display_receipt != consumed_display
            or gate.submission != sealed
            or sealed.packet != packet
            or family.post_submission_identity_mapping_commitment_id
            != commitment.commitment_id
            or family.post_submission_identity_mapping_commitment_sha256
            != commitment.material_commitment_sha256
        ):
            raise C4Stage1ReviewRunError("Sealed review differs from portable inputs")
        replayed_gate = evaluate_c4_stage1_human_review(
            prepared.review_schema,
            packet,
            artifact_store=render_artifact_store,
            operator_policy=policy,
            screen_contract=prepared.screen_contract,
            display_attester_policy=prepared.display_policy,
            operator_secret=None,
            display_attestation_verifier=display_verifier,
            display_receipt_ledger=display_ledger,
            used_policy_ledger=operator_ledger,
            operator_attestation_verifier=operator_verifier,
            submission=sealed,
        )
        if (
            replayed_gate != gate
            or gate.gate_result_id != family.gate_result_id
            or sealed.submission_id != family.sealed_submission_id
            or attestation.attestation_id != family.operator_attestation_id
            or attestation.attestation_sha256 != family.operator_attestation_sha256
            or claim.claim_id != family.claim_id
            or claim.claim_sha256 != family.claim_sha256
            or display_receipt.display_receipt_id != family.display_receipt_id
            or display_receipt.display_receipt_sha256 != family.display_receipt_sha256
            or consumed_display.consumed_display_receipt_id
            != family.consumed_display_receipt_id
            or consumed_display.consumed_display_receipt_sha256
            != family.consumed_display_receipt_sha256
            or packet.packet_id != family.packet_id
            or packet.packet_sha256 != family.packet_sha256
            or commitment.commitment_id != family.material_commitment_id
            or commitment.material_commitment_sha256
            != family.material_commitment_sha256
            or presentation.presentation_manifest_id != family.presentation_manifest_id
            or presentation.presentation_manifest_sha256
            != family.presentation_manifest_sha256
            or gate.human_review_passed != family.human_review_passed
        ):
            raise C4Stage1ReviewRunError("Review family anchor binding changed")
    return C4Stage1HumanReviewRunOutcome(
        anchor=anchor,
        anchor_storage=review_anchor_storage,
    )


__all__ = [
    "C4_STAGE1_REVIEW_RUN_ANCHOR_PATH",
    "C4Stage1HumanReviewRunAnchor",
    "C4Stage1HumanReviewRunOutcome",
    "C4Stage1ReviewFamilyEvidence",
    "C4Stage1ReviewRunError",
    "cold_verify_c4_stage1_human_review_run",
    "run_c4_stage1_human_review",
]
