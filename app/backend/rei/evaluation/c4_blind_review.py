"""Fail-closed blind operator review for the C4 visual remediation screen.

The first-pass packet exposes committed source and option/output bindings but
never the renderer or model identity.  Identity mapping can be revealed only by
binding an immutable, externally attested submission to the original hidden
commitment.  The receipt authenticates a manual-entry claim; it does not prove
human cognition.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import stat
import struct
import zlib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self, TypeVar

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    CommitDigest,
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    UtcTimestamp,
)


C4_REVIEW_RUBRIC_VERSION = "c4-visual-remediation-human-review-v1"
C4_BLINDING_POLICY = "c4-content-derived-blind-pair-v1"
C4_OPERATOR_POLICY_SCHEME = "c4-external-one-time-hmac-sha256-v1"
C4_OPERATOR_ATTESTATION_CLAIM = "trusted_external_operator_attested_manual_entry"
C4_OPERATOR_ENTRY_ORIGIN = "external_operator_manual_entry_unverified"
C4_OPERATOR_RECEIPT_DOMAIN = "rei-c4-operator-manual-entry-receipt-v1"
C4_PRESENTATION_POLICY = "c4-byte-verified-png-input-manifest-v1"
C4_PRESENTATION_PNG_CHUNK_POLICY = "png-rgb8-rgba8-noninterlaced-no-metadata-v1"
C4_HMAC_KEY_MIN_BYTES = 32
C4_HMAC_KEY_MAX_BYTES = 128
C4_PRESENTATION_MAX_PNG_BYTES = 64 * 1024 * 1024
C4_PRESENTATION_MAX_PNG_CHUNKS = 65_536
C4_PRESENTATION_MAX_DECODED_BYTES = 256 * 1024 * 1024
C4_PRESENTATION_MAX_DIMENSION = 32_768
C4_REVIEW_MAX_CANONICAL_BYTES = 65_536

_C4_PRESENTATION_ALLOWED_PNG_CHUNKS = frozenset({b"IHDR", b"IDAT", b"IEND"})
_C4_PRESENTATION_READ_CHUNK_BYTES = 1024 * 1024

C4_OUTPUT_POSITIVE_FIELDS: tuple[str, ...] = (
    "source_subject_present",
    "identity_preserved",
    "unchanged_composition_preserved",
    "option_action_correct",
    "no_extra_actor",
    "no_generated_external_evidence_claim",
)
C4_OUTPUT_UNCERTAINTY_FIELD = "reviewer_uncertain"
C4_PAIR_POSITIVE_FIELDS: tuple[str, ...] = (
    "actions_visibly_distinct",
    "same_source_bytes_confirmed",
)

BoundedReviewInstruction = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
]
ReviewStatus = Literal["sealed_submission", "missing", "skipped"]
ReviewReason = Literal[
    "human_review_passed",
    "human_review_failed",
    "human_review_missing",
    "human_review_skipped",
]

_INSTRUCTION_ADAPTER = TypeAdapter(BoundedReviewInstruction)
_ID_ADAPTER = TypeAdapter(NonEmptyId)
_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _utf8_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _bytes_sha256(canonical_json_bytes(value))


def _content_addresses(namespace: str, payload: object) -> tuple[str, str]:
    return content_id(namespace, payload), _canonical_sha256(payload)


def _fresh_nonce_hex(*, excluding: frozenset[str]) -> str:
    """Generate an internal 256-bit nonce distinct from public hash fields."""

    while True:
        candidate = secrets.token_bytes(32).hex()
        if candidate not in excluding:
            return candidate


def c4_blind_order_sha256(blind_code: str) -> str:
    """Return the raw UTF-8 SHA-256 used for deterministic pair presentation."""

    return _utf8_sha256(blind_code)


def _require_bounded_canonical(value: object, *, label: str) -> None:
    if len(canonical_json_bytes(value)) > C4_REVIEW_MAX_CANONICAL_BYTES:
        raise ValueError(f"{label} exceeds the canonical serialization bound")


def _cold_validate(
    value: object,
    model_type: type[_ModelT],
    *,
    label: str,
) -> _ModelT:
    """Rebuild one public-boundary model so ``model_copy`` cannot bypass checks."""

    if not isinstance(value, model_type):
        raise TypeError(f"{label} must be a {model_type.__name__}")
    return model_type.model_validate(value.model_dump(mode="python", round_trip=True))


class C4BlindHumanReviewSchema(FrozenArtifactModel):
    """Content-addressed definition of the exact C4 operator-review rubric."""

    schema_version: Literal["rei-c4-blind-human-review-schema-v1"] = (
        "rei-c4-blind-human-review-schema-v1"
    )
    schema_id: NonEmptyId
    rubric_version: Literal["c4-visual-remediation-human-review-v1"]
    blinding_policy: Literal["c4-content-derived-blind-pair-v1"]
    output_positive_fields: tuple[NonEmptyId, ...]
    output_uncertainty_field: NonEmptyId
    pair_positive_fields: tuple[NonEmptyId, ...]
    pair_size: Literal[2] = 2
    human_field_origin: Literal["external_operator_manual_entry_unverified"] = (
        "external_operator_manual_entry_unverified"
    )
    operator_policy_scheme: Literal["c4-external-one-time-hmac-sha256-v1"]
    operator_attestation_claim: Literal[
        "trusted_external_operator_attested_manual_entry"
    ]
    external_operator_receipt_required: Literal[True] = True
    attestation_proves_human_cognition: Literal[False] = False
    reveal_requires_sealed_submission: Literal[True] = True
    missing_or_skipped_fails_closed: Literal[True] = True
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_schema(self) -> Self:
        if self.output_positive_fields != C4_OUTPUT_POSITIVE_FIELDS:
            raise ValueError("Output positive fields differ from the frozen rubric")
        if self.output_uncertainty_field != C4_OUTPUT_UNCERTAINTY_FIELD:
            raise ValueError("Output uncertainty field differs from the frozen rubric")
        if self.pair_positive_fields != C4_PAIR_POSITIVE_FIELDS:
            raise ValueError("Pair positive fields differ from the frozen rubric")
        if (
            self.pair_size != 2
            or self.human_field_origin != C4_OPERATOR_ENTRY_ORIGIN
            or self.operator_policy_scheme != C4_OPERATOR_POLICY_SCHEME
            or self.operator_attestation_claim != C4_OPERATOR_ATTESTATION_CLAIM
            or self.external_operator_receipt_required is not True
            or self.attestation_proves_human_cognition is not False
            or self.reveal_requires_sealed_submission is not True
            or self.missing_or_skipped_fails_closed is not True
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 review schema weakens a frozen fail-closed boundary")
        payload = self.model_dump(mode="python", round_trip=True, exclude={"schema_id"})
        if self.schema_id != content_id("c4_review_schema", payload):
            raise ValueError("C4 review schema ID differs from canonical content")
        _require_bounded_canonical(self, label="C4 review schema")
        return self


def build_c4_blind_human_review_schema() -> C4BlindHumanReviewSchema:
    base = {
        "schema_version": "rei-c4-blind-human-review-schema-v1",
        "rubric_version": C4_REVIEW_RUBRIC_VERSION,
        "blinding_policy": C4_BLINDING_POLICY,
        "output_positive_fields": C4_OUTPUT_POSITIVE_FIELDS,
        "output_uncertainty_field": C4_OUTPUT_UNCERTAINTY_FIELD,
        "pair_positive_fields": C4_PAIR_POSITIVE_FIELDS,
        "pair_size": 2,
        "human_field_origin": C4_OPERATOR_ENTRY_ORIGIN,
        "operator_policy_scheme": C4_OPERATOR_POLICY_SCHEME,
        "operator_attestation_claim": C4_OPERATOR_ATTESTATION_CLAIM,
        "external_operator_receipt_required": True,
        "attestation_proves_human_cognition": False,
        "reveal_requires_sealed_submission": True,
        "missing_or_skipped_fails_closed": True,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    return C4BlindHumanReviewSchema(
        schema_id=content_id("c4_review_schema", base), **base
    )


class C4HumanReviewOperatorPolicy(FrozenArtifactModel):
    """Public pre-inference commitment to one external manual-entry issuer.

    The artifact rejects direct raw, UTF-8 and hexadecimal key material.  Its
    caller-supplied IDs remain a trusted external boundary and can carry covert
    encodings, so the schema deliberately makes no information-flow claim
    about every reversible representation of the operator secret.
    """

    schema_version: Literal["rei-c4-human-review-operator-policy-v1"] = (
        "rei-c4-human-review-operator-policy-v1"
    )
    policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    review_schema_id: NonEmptyId
    run_id: NonEmptyId
    candidate_slot_id: NonEmptyId
    source_image_sha256: HashDigest
    policy_nonce: HashDigest
    hmac_key_commitment_sha256: HashDigest
    receipt_scheme: Literal["c4-external-one-time-hmac-sha256-v1"]
    operator_attestation_claim: Literal[
        "trusted_external_operator_attested_manual_entry"
    ]
    minimum_hmac_key_bytes: Literal[32] = 32
    maximum_hmac_key_bytes: Literal[128] = 128
    pre_inference_pin_required: Literal[True] = True
    one_time_issuance_required: Literal[True] = True
    external_atomic_used_policy_ledger_required: Literal[True] = True
    live_external_ledger_verification_required: Literal[True] = True
    cold_validation_proves_one_time_issuance: Literal[False] = False
    manual_entry_issuer_external_to_model_runner: Literal[True] = True
    model_runner_key_access_allowed: Literal[False] = False
    direct_operator_secret_material_stored_in_artifact: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    cold_validation_authenticates_operator_hmac: Literal[False] = False
    secret_reverification_required_before_trust: Literal[True] = True
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if (
            self.receipt_scheme != C4_OPERATOR_POLICY_SCHEME
            or self.operator_attestation_claim != C4_OPERATOR_ATTESTATION_CLAIM
            or self.minimum_hmac_key_bytes != C4_HMAC_KEY_MIN_BYTES
            or self.maximum_hmac_key_bytes != C4_HMAC_KEY_MAX_BYTES
            or self.pre_inference_pin_required is not True
            or self.one_time_issuance_required is not True
            or self.external_atomic_used_policy_ledger_required is not True
            or self.live_external_ledger_verification_required is not True
            or self.cold_validation_proves_one_time_issuance is not False
            or self.manual_entry_issuer_external_to_model_runner is not True
            or self.model_runner_key_access_allowed is not False
            or self.direct_operator_secret_material_stored_in_artifact is not False
            or self.attestation_proves_human_cognition is not False
            or self.cold_validation_authenticates_operator_hmac is not False
            or self.secret_reverification_required_before_trust is not True
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 operator policy weakens the external issuer boundary")
        if (
            len(
                {
                    self.policy_nonce,
                    self.source_image_sha256,
                    self.hmac_key_commitment_sha256,
                }
            )
            != 3
        ):
            raise ValueError("C4 operator policy nonce and key must be independent")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"policy_id", "operator_policy_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_operator_policy",
            payload,
        )
        if self.policy_id != expected_id:
            raise ValueError("C4 operator policy ID differs from canonical content")
        if self.operator_policy_sha256 != expected_sha256:
            raise ValueError(
                "C4 operator policy SHA-256 differs from canonical content"
            )
        _require_bounded_canonical(self, label="C4 operator policy")
        return self


def build_c4_human_review_operator_policy(
    schema: C4BlindHumanReviewSchema,
    *,
    run_id: str,
    candidate_slot_id: str,
    source_image_sha256: str,
    hmac_key_commitment_sha256: str,
) -> C4HumanReviewOperatorPolicy:
    """Build a public policy with a fresh nonce and external key commitment."""

    schema = _cold_validate(
        schema,
        C4BlindHumanReviewSchema,
        label="C4 review schema",
    )
    base = {
        "schema_version": "rei-c4-human-review-operator-policy-v1",
        "review_schema_id": schema.schema_id,
        "run_id": run_id,
        "candidate_slot_id": candidate_slot_id,
        "source_image_sha256": source_image_sha256,
        "policy_nonce": _fresh_nonce_hex(
            excluding=frozenset({source_image_sha256, hmac_key_commitment_sha256})
        ),
        "hmac_key_commitment_sha256": hmac_key_commitment_sha256,
        "receipt_scheme": schema.operator_policy_scheme,
        "operator_attestation_claim": schema.operator_attestation_claim,
        "minimum_hmac_key_bytes": C4_HMAC_KEY_MIN_BYTES,
        "maximum_hmac_key_bytes": C4_HMAC_KEY_MAX_BYTES,
        "pre_inference_pin_required": True,
        "one_time_issuance_required": True,
        "external_atomic_used_policy_ledger_required": True,
        "live_external_ledger_verification_required": True,
        "cold_validation_proves_one_time_issuance": False,
        "manual_entry_issuer_external_to_model_runner": True,
        "model_runner_key_access_allowed": False,
        "direct_operator_secret_material_stored_in_artifact": False,
        "attestation_proves_human_cognition": False,
        "cold_validation_authenticates_operator_hmac": False,
        "secret_reverification_required_before_trust": True,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    policy_id, operator_policy_sha256 = _content_addresses(
        "c4_operator_policy",
        base,
    )
    return C4HumanReviewOperatorPolicy(
        policy_id=policy_id,
        operator_policy_sha256=operator_policy_sha256,
        **base,
    )


class C4ReviewOptionMaterial(FrozenModel):
    """One hidden option/output binding committed before first-pass review."""

    option_id: NonEmptyId
    instruction: BoundedReviewInstruction
    instruction_sha256: HashDigest
    output_sha256: HashDigest

    @model_validator(mode="after")
    def validate_instruction_hash(self) -> Self:
        if self.instruction_sha256 != _utf8_sha256(self.instruction):
            raise ValueError("Instruction hash differs from normalized UTF-8 text")
        return self


def make_c4_review_option_material(
    *,
    option_id: str,
    instruction: str,
    output_sha256: str,
) -> C4ReviewOptionMaterial:
    normalized = _INSTRUCTION_ADAPTER.validate_python(instruction, strict=True)
    return C4ReviewOptionMaterial(
        option_id=option_id,
        instruction=normalized,
        instruction_sha256=_utf8_sha256(normalized),
        output_sha256=output_sha256,
    )


class C4ReviewMaterialCommitment(FrozenArtifactModel):
    """Trusted identity mapping retained outside the first-pass packet."""

    schema_version: Literal["rei-c4-review-material-commitment-v1"] = (
        "rei-c4-review-material-commitment-v1"
    )
    commitment_id: NonEmptyId
    material_commitment_sha256: HashDigest
    review_schema_id: NonEmptyId
    rubric_version: Literal["c4-visual-remediation-human-review-v1"]
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    blinding_nonce: HashDigest
    source_image_sha256: HashDigest
    renderer_id: NonEmptyId
    model_id: NonEmptyId
    model_revision: CommitDigest
    options: tuple[C4ReviewOptionMaterial, ...] = Field(min_length=2, max_length=2)
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_commitment(self) -> Self:
        if len(self.options) != 2:
            raise ValueError("C4 review commitment requires exactly two options")
        for option in self.options:
            C4ReviewOptionMaterial.model_validate(
                option.model_dump(mode="python", round_trip=True)
            )
        option_ids = tuple(item.option_id for item in self.options)
        if option_ids != tuple(sorted(set(option_ids))):
            raise ValueError("Committed options must use sorted unique option IDs")
        if (
            self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 review commitment cannot grant semantic authority")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"commitment_id", "material_commitment_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_review_material",
            payload,
        )
        if self.commitment_id != expected_id:
            raise ValueError("C4 review commitment ID differs from canonical content")
        if self.material_commitment_sha256 != expected_sha256:
            raise ValueError(
                "C4 review commitment SHA-256 differs from canonical content"
            )
        _require_bounded_canonical(self, label="C4 review commitment")
        return self


def commit_c4_review_material(
    schema: C4BlindHumanReviewSchema,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
    source_image_sha256: str,
    renderer_id: str,
    model_id: str,
    model_revision: str,
    options: tuple[C4ReviewOptionMaterial, C4ReviewOptionMaterial],
) -> C4ReviewMaterialCommitment:
    schema = _cold_validate(
        schema,
        C4BlindHumanReviewSchema,
        label="C4 review schema",
    )
    operator_policy = _cold_validate(
        operator_policy,
        C4HumanReviewOperatorPolicy,
        label="C4 operator policy",
    )
    if operator_policy.review_schema_id != schema.schema_id:
        raise ValueError("C4 operator policy differs from the review schema")
    if operator_policy.source_image_sha256 != source_image_sha256:
        raise ValueError("C4 operator policy source differs from review material")
    blinding_nonce = _fresh_nonce_hex(
        excluding=frozenset(
            {
                operator_policy.policy_nonce,
                operator_policy.hmac_key_commitment_sha256,
                source_image_sha256,
            }
        )
    )
    if type(options) is not tuple or len(options) != 2:
        raise ValueError("C4 review material requires an exact two-option tuple")
    validated_options = tuple(
        _cold_validate(
            option,
            C4ReviewOptionMaterial,
            label="C4 review option material",
        )
        for option in options
    )
    canonical_options = tuple(
        sorted(validated_options, key=lambda item: item.option_id)
    )
    base = {
        "schema_version": "rei-c4-review-material-commitment-v1",
        "review_schema_id": schema.schema_id,
        "rubric_version": schema.rubric_version,
        "operator_policy_id": operator_policy.policy_id,
        "operator_policy_sha256": operator_policy.operator_policy_sha256,
        "blinding_nonce": blinding_nonce,
        "source_image_sha256": source_image_sha256,
        "renderer_id": renderer_id,
        "model_id": model_id,
        "model_revision": model_revision,
        "options": canonical_options,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    commitment_id, material_commitment_sha256 = _content_addresses(
        "c4_review_material",
        base,
    )
    return C4ReviewMaterialCommitment(
        commitment_id=commitment_id,
        material_commitment_sha256=material_commitment_sha256,
        **base,
    )


def _blind_code(
    commitment: C4ReviewMaterialCommitment,
    option: C4ReviewOptionMaterial,
) -> str:
    return content_id(
        "c4_blind_code",
        {
            "material_commitment_id": commitment.commitment_id,
            "material_commitment_sha256": commitment.material_commitment_sha256,
            "source_image_sha256": commitment.source_image_sha256,
            "option_id": option.option_id,
            "instruction_sha256": option.instruction_sha256,
            "output_sha256": option.output_sha256,
        },
    )


class C4BlindOutputReference(FrozenModel):
    blind_code: NonEmptyId
    blind_order_sha256: HashDigest
    option_id: NonEmptyId
    instruction: BoundedReviewInstruction
    instruction_sha256: HashDigest
    output_sha256: HashDigest

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.instruction_sha256 != _utf8_sha256(self.instruction):
            raise ValueError("Blind instruction hash differs from its UTF-8 text")
        if self.blind_order_sha256 != c4_blind_order_sha256(self.blind_code):
            raise ValueError("Blind presentation digest differs from blind code")
        return self


class C4BlindReviewPacket(FrozenArtifactModel):
    """Only material allowed to reach the reviewer before sealed submission."""

    schema_version: Literal["rei-c4-blind-review-packet-v1"] = (
        "rei-c4-blind-review-packet-v1"
    )
    packet_id: NonEmptyId
    packet_sha256: HashDigest
    review_schema_id: NonEmptyId
    rubric_version: Literal["c4-visual-remediation-human-review-v1"]
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    material_commitment_id: NonEmptyId
    material_commitment_sha256: HashDigest
    source_image_sha256: HashDigest
    outputs: tuple[C4BlindOutputReference, ...] = Field(min_length=2, max_length=2)
    blinding_policy: Literal["c4-content-derived-blind-pair-v1"]
    renderer_identity_structured_field_present: Literal[False] = False
    model_identity_structured_field_present: Literal[False] = False
    other_provider_output_references_present: Literal[False] = False
    pixel_identity_absence_proven: Literal[False] = False
    reveal_mapping_present: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_packet(self) -> Self:
        if (
            self.blinding_policy != C4_BLINDING_POLICY
            or self.renderer_identity_structured_field_present is not False
            or self.model_identity_structured_field_present is not False
            or self.other_provider_output_references_present is not False
            or self.pixel_identity_absence_proven is not False
            or self.reveal_mapping_present is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 blind packet weakens a frozen first-pass boundary")
        if len(self.outputs) != 2:
            raise ValueError("C4 blind packet requires exactly two outputs")
        for item in self.outputs:
            C4BlindOutputReference.model_validate(
                item.model_dump(mode="python", round_trip=True)
            )
        codes = tuple(item.blind_code for item in self.outputs)
        if len(set(codes)) != len(codes):
            raise ValueError("Blind output codes must be unique")
        order = tuple(item.blind_order_sha256 for item in self.outputs)
        if order != tuple(sorted(order)):
            raise ValueError(
                "Blind outputs must use ascending SHA-256 presentation order"
            )
        for item in self.outputs:
            expected = content_id(
                "c4_blind_code",
                {
                    "material_commitment_id": self.material_commitment_id,
                    "material_commitment_sha256": self.material_commitment_sha256,
                    "source_image_sha256": self.source_image_sha256,
                    "option_id": item.option_id,
                    "instruction_sha256": item.instruction_sha256,
                    "output_sha256": item.output_sha256,
                },
            )
            if item.blind_code != expected:
                raise ValueError("Blind code differs from committed visible content")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"packet_id", "packet_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_blind_packet",
            payload,
        )
        if self.packet_id != expected_id:
            raise ValueError("C4 blind packet ID differs from canonical content")
        if self.packet_sha256 != expected_sha256:
            raise ValueError("C4 blind packet SHA-256 differs from canonical content")
        _require_bounded_canonical(self, label="C4 blind packet")
        return self


def _blind_outputs(
    commitment: C4ReviewMaterialCommitment,
) -> tuple[C4BlindOutputReference, ...]:
    outputs = tuple(
        C4BlindOutputReference(
            blind_code=_blind_code(commitment, option),
            blind_order_sha256=c4_blind_order_sha256(_blind_code(commitment, option)),
            option_id=option.option_id,
            instruction=option.instruction,
            instruction_sha256=option.instruction_sha256,
            output_sha256=option.output_sha256,
        )
        for option in commitment.options
    )
    return tuple(sorted(outputs, key=lambda item: item.blind_order_sha256))


def prepare_c4_blind_review(
    schema: C4BlindHumanReviewSchema,
    commitment: C4ReviewMaterialCommitment,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
) -> C4BlindReviewPacket:
    schema = _cold_validate(
        schema,
        C4BlindHumanReviewSchema,
        label="C4 review schema",
    )
    commitment = _cold_validate(
        commitment,
        C4ReviewMaterialCommitment,
        label="C4 review commitment",
    )
    operator_policy = _cold_validate(
        operator_policy,
        C4HumanReviewOperatorPolicy,
        label="C4 operator policy",
    )
    if commitment.review_schema_id != schema.schema_id:
        raise ValueError("C4 commitment does not use the requested review schema")
    if commitment.rubric_version != schema.rubric_version:
        raise ValueError("C4 commitment rubric differs from the review schema")
    if (
        commitment.operator_policy_id != operator_policy.policy_id
        or commitment.operator_policy_sha256 != operator_policy.operator_policy_sha256
    ):
        raise ValueError("C4 commitment differs from the operator policy")
    if operator_policy.review_schema_id != schema.schema_id:
        raise ValueError("C4 operator policy differs from the review schema")
    if operator_policy.source_image_sha256 != commitment.source_image_sha256:
        raise ValueError("C4 operator policy source differs from review material")
    base = {
        "schema_version": "rei-c4-blind-review-packet-v1",
        "review_schema_id": schema.schema_id,
        "rubric_version": schema.rubric_version,
        "operator_policy_id": operator_policy.policy_id,
        "operator_policy_sha256": operator_policy.operator_policy_sha256,
        "material_commitment_id": commitment.commitment_id,
        "material_commitment_sha256": commitment.material_commitment_sha256,
        "source_image_sha256": commitment.source_image_sha256,
        "outputs": _blind_outputs(commitment),
        "blinding_policy": schema.blinding_policy,
        "renderer_identity_structured_field_present": False,
        "model_identity_structured_field_present": False,
        "other_provider_output_references_present": False,
        "pixel_identity_absence_proven": False,
        "reveal_mapping_present": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    packet_id, packet_sha256 = _content_addresses("c4_blind_packet", base)
    return C4BlindReviewPacket(
        packet_id=packet_id,
        packet_sha256=packet_sha256,
        **base,
    )


class C4PresentedPng(FrozenModel):
    """Build-time byte receipt for one controlled, metadata-free PNG input."""

    image_role: Literal["source", "output"]
    blind_code: NonEmptyId | None = None
    blind_order_sha256: HashDigest | None = None
    image_sha256: HashDigest
    byte_size: int = Field(gt=0, le=C4_PRESENTATION_MAX_PNG_BYTES)
    width: int = Field(gt=0, le=C4_PRESENTATION_MAX_DIMENSION)
    height: int = Field(gt=0, le=C4_PRESENTATION_MAX_DIMENSION)
    png_signature_verified: Literal[True] = True
    png_structure_verified: Literal[True] = True
    png_crc_verified: Literal[True] = True
    exact_bytes_rehashed: Literal[True] = True
    png_chunk_policy: Literal["png-rgb8-rgba8-noninterlaced-no-metadata-v1"] = (
        "png-rgb8-rgba8-noninterlaced-no-metadata-v1"
    )
    embedded_metadata_present: Literal[False] = False
    decoded_scanlines_verified: Literal[True] = True
    cold_validation_reverifies_exact_png_bytes: Literal[False] = False
    exact_png_bytes_required_for_reverification: Literal[True] = True

    @model_validator(mode="after")
    def validate_presented_png(self) -> Self:
        if self.image_role == "source":
            if self.blind_code is not None or self.blind_order_sha256 is not None:
                raise ValueError("C4 source presentation cannot carry a blind code")
        elif self.blind_code is None or self.blind_order_sha256 is None:
            raise ValueError("C4 output presentation requires its blind code and order")
        elif self.blind_order_sha256 != c4_blind_order_sha256(self.blind_code):
            raise ValueError("C4 output presentation order differs from its blind code")
        if (
            self.png_signature_verified is not True
            or self.png_structure_verified is not True
            or self.png_crc_verified is not True
            or self.exact_bytes_rehashed is not True
            or self.png_chunk_policy != C4_PRESENTATION_PNG_CHUNK_POLICY
            or self.embedded_metadata_present is not False
            or self.decoded_scanlines_verified is not True
            or self.cold_validation_reverifies_exact_png_bytes is not False
            or self.exact_png_bytes_required_for_reverification is not True
        ):
            raise ValueError(
                "C4 presented PNG lacks exact byte and metadata-free verification"
            )
        return self


class C4BlindPresentationManifest(FrozenArtifactModel):
    """PNG input receipt; it is deliberately not an actual-display receipt."""

    schema_version: Literal["rei-c4-blind-presentation-manifest-v1"] = (
        "rei-c4-blind-presentation-manifest-v1"
    )
    presentation_manifest_id: NonEmptyId
    presentation_manifest_sha256: HashDigest
    presentation_policy: Literal["c4-byte-verified-png-input-manifest-v1"]
    review_schema_id: NonEmptyId
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    packet_id: NonEmptyId
    packet_sha256: HashDigest
    material_commitment_id: NonEmptyId
    material_commitment_sha256: HashDigest
    source: C4PresentedPng
    outputs: tuple[C4PresentedPng, ...] = Field(min_length=2, max_length=2)
    pair_order_policy: Literal["ascending_sha256_of_blind_code"] = (
        "ascending_sha256_of_blind_code"
    )
    png_chunk_policy: Literal["png-rgb8-rgba8-noninterlaced-no-metadata-v1"] = (
        "png-rgb8-rgba8-noninterlaced-no-metadata-v1"
    )
    embedded_metadata_present: Literal[False] = False
    renderer_identity_supplied_label_present: Literal[False] = False
    model_identity_supplied_label_present: Literal[False] = False
    other_provider_output_supplied_labels_present: Literal[False] = False
    presentation_ui_policy: Literal["reviewer-ui-omit-provider-labels-v1"] = (
        "reviewer-ui-omit-provider-labels-v1"
    )
    presentation_ui_execution_attested: Literal[False] = False
    pixel_identity_absence_proven: Literal[False] = False
    cold_validation_reverifies_exact_png_bytes: Literal[False] = False
    exact_png_bytes_required_for_reverification: Literal[True] = True
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        C4PresentedPng.model_validate(
            self.source.model_dump(mode="python", round_trip=True)
        )
        if self.source.image_role != "source":
            raise ValueError("C4 presentation manifest requires one source PNG")
        if len(self.outputs) != 2:
            raise ValueError("C4 presentation manifest requires exactly two outputs")
        for output in self.outputs:
            C4PresentedPng.model_validate(
                output.model_dump(mode="python", round_trip=True)
            )
            if output.image_role != "output":
                raise ValueError("C4 presentation output has the wrong role")
        order = tuple(item.blind_order_sha256 for item in self.outputs)
        if order != tuple(sorted(order)):
            raise ValueError("C4 presentation outputs differ from blind packet order")
        codes = tuple(item.blind_code for item in self.outputs)
        if len(set(codes)) != 2:
            raise ValueError("C4 presentation outputs require unique blind codes")
        if (
            self.presentation_policy != C4_PRESENTATION_POLICY
            or self.pair_order_policy != "ascending_sha256_of_blind_code"
            or self.png_chunk_policy != C4_PRESENTATION_PNG_CHUNK_POLICY
            or self.embedded_metadata_present is not False
            or self.renderer_identity_supplied_label_present is not False
            or self.model_identity_supplied_label_present is not False
            or self.other_provider_output_supplied_labels_present is not False
            or self.presentation_ui_policy != "reviewer-ui-omit-provider-labels-v1"
            or self.presentation_ui_execution_attested is not False
            or self.pixel_identity_absence_proven is not False
            or self.cold_validation_reverifies_exact_png_bytes is not False
            or self.exact_png_bytes_required_for_reverification is not True
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 presentation manifest weakens the blind boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "presentation_manifest_id",
                "presentation_manifest_sha256",
            },
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_presentation",
            payload,
        )
        if self.presentation_manifest_id != expected_id:
            raise ValueError(
                "C4 presentation manifest ID differs from canonical content"
            )
        if self.presentation_manifest_sha256 != expected_sha256:
            raise ValueError(
                "C4 presentation manifest SHA-256 differs from canonical content"
            )
        _require_bounded_canonical(self, label="C4 presentation manifest")
        return self


def _parse_png_dimensions(value: bytes) -> tuple[int, int]:
    if len(value) < 33 or value[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("C4 presentation input is not an exact PNG")
    offset = 8
    width: int | None = None
    height: int | None = None
    channels: int | None = None
    row_size: int | None = None
    decoded_size: int | None = None
    decoded_byte_count = 0
    decompressor = None
    saw_idat = False
    saw_iend = False
    chunk_count = 0
    while offset < len(value):
        if offset + 12 > len(value):
            raise ValueError("C4 presentation PNG has a truncated chunk")
        chunk_length = struct.unpack(">I", value[offset : offset + 4])[0]
        chunk_type = value[offset + 4 : offset + 8]
        chunk_end = offset + 12 + chunk_length
        if chunk_end > len(value):
            raise ValueError("C4 presentation PNG chunk exceeds exact bytes")
        chunk_count += 1
        if chunk_count > C4_PRESENTATION_MAX_PNG_CHUNKS:
            raise ValueError("C4 presentation PNG exceeds the fixed chunk-count bound")
        chunk_data = value[offset + 8 : offset + 8 + chunk_length]
        expected_crc = struct.unpack(
            ">I", value[offset + 8 + chunk_length : chunk_end]
        )[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError("C4 presentation PNG has an invalid chunk CRC")
        if chunk_type not in _C4_PRESENTATION_ALLOWED_PNG_CHUNKS:
            raise ValueError(
                "C4 presentation PNG contains forbidden metadata or non-pixel chunk"
            )
        if chunk_count == 1:
            if chunk_type != b"IHDR" or chunk_length != 13:
                raise ValueError("C4 presentation PNG must start with exact IHDR")
            width, height = struct.unpack(">II", chunk_data[:8])
            if (
                width <= 0
                or height <= 0
                or width > C4_PRESENTATION_MAX_DIMENSION
                or height > C4_PRESENTATION_MAX_DIMENSION
            ):
                raise ValueError("C4 presentation PNG dimensions are outside bounds")
            bit_depth, color_type, compression, filter_method, interlace = chunk_data[
                8:
            ]
            if (
                bit_depth != 8
                or color_type not in {2, 6}
                or compression != 0
                or filter_method != 0
                or interlace != 0
            ):
                raise ValueError(
                    "C4 presentation PNG must be non-interlaced 8-bit RGB or RGBA"
                )
            channels = 3 if color_type == 2 else 4
            row_size = 1 + width * channels
            decoded_size = height * row_size
            if decoded_size > C4_PRESENTATION_MAX_DECODED_BYTES:
                raise ValueError(
                    "C4 presentation PNG decoded byte size is outside bounds"
                )
            decompressor = zlib.decompressobj()
        elif chunk_type == b"IHDR":
            raise ValueError("C4 presentation PNG contains a duplicate IHDR")
        if chunk_type == b"IDAT":
            if chunk_length == 0:
                raise ValueError("C4 presentation PNG contains an empty IDAT chunk")
            if decompressor is None or decoded_size is None or row_size is None:
                raise ValueError("C4 presentation PNG must start with exact IHDR")
            saw_idat = True
            pending = chunk_data
            while pending:
                remaining_output = decoded_size + 1 - decoded_byte_count
                if remaining_output <= 0:
                    raise ValueError(
                        "C4 presentation PNG decoded scanline size is invalid"
                    )
                pending_size = len(pending)
                try:
                    decoded = decompressor.decompress(pending, remaining_output)
                except zlib.error as exc:
                    raise ValueError(
                        "C4 presentation PNG IDAT stream is invalid"
                    ) from exc
                if decompressor.unused_data:
                    raise ValueError("C4 presentation PNG IDAT stream is invalid")
                next_pending = decompressor.unconsumed_tail
                next_decoded_byte_count = decoded_byte_count + len(decoded)
                if next_decoded_byte_count > decoded_size:
                    raise ValueError(
                        "C4 presentation PNG decoded scanline size is invalid"
                    )
                first_filter_offset = (-decoded_byte_count) % row_size
                if any(
                    decoded[filter_offset] > 4
                    for filter_offset in range(
                        first_filter_offset,
                        len(decoded),
                        row_size,
                    )
                ):
                    raise ValueError(
                        "C4 presentation PNG contains an invalid scanline filter"
                    )
                decoded_byte_count = next_decoded_byte_count
                if next_pending and len(next_pending) >= pending_size and not decoded:
                    raise ValueError(
                        "C4 presentation PNG IDAT stream made no bounded progress"
                    )
                pending = next_pending
        if chunk_type == b"IEND":
            if chunk_length != 0 or chunk_end != len(value):
                raise ValueError("C4 presentation PNG has an invalid final IEND")
            saw_iend = True
            offset = chunk_end
            break
        offset = chunk_end
    if (
        width is None
        or height is None
        or channels is None
        or row_size is None
        or decoded_size is None
        or decompressor is None
        or not saw_idat
        or not saw_iend
    ):
        raise ValueError("C4 presentation PNG structure is incomplete")
    if offset != len(value):
        raise ValueError("C4 presentation PNG contains trailing bytes")
    if (
        decoded_byte_count != decoded_size
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
    ):
        raise ValueError("C4 presentation PNG decoded scanline size is invalid")
    try:
        flushed = decompressor.flush()
    except zlib.error as exc:
        raise ValueError("C4 presentation PNG IDAT stream is invalid") from exc
    if flushed:
        raise ValueError("C4 presentation PNG decoded scanline size is invalid")
    return width, height


def _read_bounded_regular_file(candidate: Path) -> bytes:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(candidate, flags)
    except (OSError, ValueError):
        raise ValueError(
            "C4 presentation PNG path must be a readable regular file"
        ) from None

    try:
        try:
            initial_stat = os.fstat(descriptor)
        except OSError:
            raise ValueError(
                "C4 presentation PNG path must be a readable regular file"
            ) from None
        if not stat.S_ISREG(initial_stat.st_mode):
            raise ValueError("C4 presentation PNG path must be a readable regular file")
        initial_size = initial_stat.st_size
        if initial_size <= 0 or initial_size > C4_PRESENTATION_MAX_PNG_BYTES:
            raise ValueError("C4 presentation PNG byte size is outside bounds")

        read_limit = min(
            initial_size + 1,
            C4_PRESENTATION_MAX_PNG_BYTES + 1,
        )
        value = bytearray()
        while len(value) < read_limit:
            requested_size = min(
                _C4_PRESENTATION_READ_CHUNK_BYTES,
                read_limit - len(value),
            )
            try:
                chunk = os.read(descriptor, requested_size)
            except OSError:
                raise ValueError(
                    "C4 presentation PNG path must be a readable regular file"
                ) from None
            if not isinstance(chunk, bytes) or len(chunk) > requested_size:
                raise ValueError(
                    "C4 presentation PNG bounded read returned invalid bytes"
                )
            if not chunk:
                break
            value.extend(chunk)

        try:
            final_handle_stat = os.fstat(descriptor)
        except OSError:
            raise ValueError(
                "C4 presentation PNG changed during bounded exact byte read"
            ) from None
        try:
            final_path_stat = os.stat(candidate)
        except OSError:
            raise ValueError(
                "C4 presentation PNG changed during bounded exact byte read"
            ) from None
        initial_identity = (initial_stat.st_dev, initial_stat.st_ino)
        if (
            not stat.S_ISREG(final_handle_stat.st_mode)
            or not stat.S_ISREG(final_path_stat.st_mode)
            or (final_handle_stat.st_dev, final_handle_stat.st_ino) != initial_identity
            or (final_path_stat.st_dev, final_path_stat.st_ino) != initial_identity
            or final_handle_stat.st_size != initial_size
            or final_path_stat.st_size != initial_size
            or len(value) != initial_size
        ):
            raise ValueError(
                "C4 presentation PNG changed during bounded exact byte read"
            )
        return bytes(value)
    finally:
        os.close(descriptor)


def _read_presented_png(
    path: str | Path,
    *,
    image_role: Literal["source", "output"],
    expected_sha256: str,
    blind_code: str | None = None,
    blind_order_sha256: str | None = None,
) -> C4PresentedPng:
    candidate = Path(path)
    value = _read_bounded_regular_file(candidate)
    image_sha256 = _bytes_sha256(value)
    if not hmac.compare_digest(image_sha256, expected_sha256):
        raise ValueError("C4 presentation PNG SHA-256 differs from the blind packet")
    width, height = _parse_png_dimensions(value)
    return C4PresentedPng(
        image_role=image_role,
        blind_code=blind_code,
        blind_order_sha256=blind_order_sha256,
        image_sha256=image_sha256,
        byte_size=len(value),
        width=width,
        height=height,
        png_signature_verified=True,
        png_structure_verified=True,
        png_crc_verified=True,
        exact_bytes_rehashed=True,
        png_chunk_policy=C4_PRESENTATION_PNG_CHUNK_POLICY,
        embedded_metadata_present=False,
        decoded_scanlines_verified=True,
        cold_validation_reverifies_exact_png_bytes=False,
        exact_png_bytes_required_for_reverification=True,
    )


def build_c4_blind_presentation_manifest(
    packet: C4BlindReviewPacket,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
    source_png_path: str | Path,
    output_png_paths: tuple[str | Path, str | Path],
) -> C4BlindPresentationManifest:
    packet = _cold_validate(
        packet,
        C4BlindReviewPacket,
        label="C4 blind review packet",
    )
    operator_policy = _cold_validate(
        operator_policy,
        C4HumanReviewOperatorPolicy,
        label="C4 operator policy",
    )
    if type(output_png_paths) is not tuple or len(output_png_paths) != 2:
        raise ValueError("C4 presentation requires an exact two-output path tuple")
    if (
        packet.operator_policy_id != operator_policy.policy_id
        or packet.operator_policy_sha256 != operator_policy.operator_policy_sha256
        or packet.review_schema_id != operator_policy.review_schema_id
        or packet.source_image_sha256 != operator_policy.source_image_sha256
    ):
        raise ValueError("C4 presentation policy differs from the blind packet")
    source = _read_presented_png(
        source_png_path,
        image_role="source",
        expected_sha256=packet.source_image_sha256,
    )
    outputs = tuple(
        _read_presented_png(
            path,
            image_role="output",
            expected_sha256=reference.output_sha256,
            blind_code=reference.blind_code,
            blind_order_sha256=reference.blind_order_sha256,
        )
        for path, reference in zip(output_png_paths, packet.outputs, strict=True)
    )
    base = {
        "schema_version": "rei-c4-blind-presentation-manifest-v1",
        "presentation_policy": C4_PRESENTATION_POLICY,
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
        "png_chunk_policy": C4_PRESENTATION_PNG_CHUNK_POLICY,
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
    manifest_id, manifest_sha256 = _content_addresses("c4_presentation", base)
    return C4BlindPresentationManifest(
        presentation_manifest_id=manifest_id,
        presentation_manifest_sha256=manifest_sha256,
        **base,
    )


class C4OutputHumanJudgment(FrozenModel):
    """Unverified manual-entry booleans for one blind output."""

    blind_code: NonEmptyId
    source_image_sha256: HashDigest
    instruction_sha256: HashDigest
    output_sha256: HashDigest
    source_subject_present: bool
    identity_preserved: bool
    unchanged_composition_preserved: bool
    option_action_correct: bool
    no_extra_actor: bool
    no_generated_external_evidence_claim: bool
    reviewer_uncertain: bool
    human_field_origin: Literal["external_operator_manual_entry_unverified"] = (
        "external_operator_manual_entry_unverified"
    )
    attestation_proves_human_cognition: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_human_fields(self) -> Self:
        fields = (*C4_OUTPUT_POSITIVE_FIELDS, C4_OUTPUT_UNCERTAINTY_FIELD)
        if any(type(getattr(self, field)) is not bool for field in fields):
            raise ValueError("Every C4 output judgment must be a strict boolean")
        if (
            self.human_field_origin != C4_OPERATOR_ENTRY_ORIGIN
            or self.attestation_proves_human_cognition is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 output judgment weakens the manual-entry boundary")
        return self

    @property
    def passed(self) -> bool:
        return all(
            getattr(self, field) for field in C4_OUTPUT_POSITIVE_FIELDS
        ) and not (self.reviewer_uncertain)


def record_c4_output_human_judgment(
    packet: C4BlindReviewPacket,
    *,
    blind_code: str,
    source_subject_present: bool,
    identity_preserved: bool,
    unchanged_composition_preserved: bool,
    option_action_correct: bool,
    no_extra_actor: bool,
    no_generated_external_evidence_claim: bool,
    reviewer_uncertain: bool,
) -> C4OutputHumanJudgment:
    packet = _cold_validate(
        packet,
        C4BlindReviewPacket,
        label="C4 blind review packet",
    )
    references = tuple(item for item in packet.outputs if item.blind_code == blind_code)
    if len(references) != 1:
        raise ValueError("Manual-entry blind code is outside the review packet")
    reference = references[0]
    return C4OutputHumanJudgment(
        blind_code=reference.blind_code,
        source_image_sha256=packet.source_image_sha256,
        instruction_sha256=reference.instruction_sha256,
        output_sha256=reference.output_sha256,
        source_subject_present=source_subject_present,
        identity_preserved=identity_preserved,
        unchanged_composition_preserved=unchanged_composition_preserved,
        option_action_correct=option_action_correct,
        no_extra_actor=no_extra_actor,
        no_generated_external_evidence_claim=no_generated_external_evidence_claim,
        reviewer_uncertain=reviewer_uncertain,
        human_field_origin=C4_OPERATOR_ENTRY_ORIGIN,
        attestation_proves_human_cognition=False,
        model_judge_calls=0,
    )


class C4PairHumanJudgment(FrozenModel):
    actions_visibly_distinct: bool
    same_source_bytes_confirmed: bool
    human_field_origin: Literal["external_operator_manual_entry_unverified"] = (
        "external_operator_manual_entry_unverified"
    )
    attestation_proves_human_cognition: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_human_fields(self) -> Self:
        if any(
            type(getattr(self, field)) is not bool for field in C4_PAIR_POSITIVE_FIELDS
        ):
            raise ValueError("Every C4 pair judgment must be a strict boolean")
        if (
            self.human_field_origin != C4_OPERATOR_ENTRY_ORIGIN
            or self.attestation_proves_human_cognition is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 pair judgment weakens the manual-entry boundary")
        return self

    @property
    def passed(self) -> bool:
        return all(getattr(self, field) for field in C4_PAIR_POSITIVE_FIELDS)


class C4HumanReviewUnsignedClaim(FrozenArtifactModel):
    """Canonical operator claim; authentication does not prove human cognition."""

    schema_version: Literal["rei-c4-human-review-unsigned-claim-v1"] = (
        "rei-c4-human-review-unsigned-claim-v1"
    )
    claim_id: NonEmptyId
    claim_sha256: HashDigest
    receipt_domain: Literal["rei-c4-operator-manual-entry-receipt-v1"]
    operator_attestation_claim: Literal[
        "trusted_external_operator_attested_manual_entry"
    ]
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    review_schema_id: NonEmptyId
    packet_id: NonEmptyId
    packet_sha256: HashDigest
    material_commitment_id: NonEmptyId
    material_commitment_sha256: HashDigest
    reviewer_pseudonym: NonEmptyId
    review_timestamp: UtcTimestamp
    output_judgments: tuple[C4OutputHumanJudgment, ...] = Field(
        min_length=2,
        max_length=2,
    )
    pair_judgment: C4PairHumanJudgment
    presentation_manifest_id: NonEmptyId
    presentation_manifest_sha256: HashDigest
    external_one_time_ledger_lease_sha256: HashDigest
    operator_claims_ledger_lease_preissued: Literal[True] = True
    cold_validation_proves_ledger_lease_issuance: Literal[False] = False
    live_external_ledger_verification_required: Literal[True] = True
    manual_entry_issuer_external_to_model_runner: Literal[True] = True
    model_runner_key_access_allowed: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        if (
            self.receipt_domain != C4_OPERATOR_RECEIPT_DOMAIN
            or self.operator_attestation_claim != C4_OPERATOR_ATTESTATION_CLAIM
            or self.manual_entry_issuer_external_to_model_runner is not True
            or self.model_runner_key_access_allowed is not False
            or self.operator_claims_ledger_lease_preissued is not True
            or self.cold_validation_proves_ledger_lease_issuance is not False
            or self.live_external_ledger_verification_required is not True
            or self.attestation_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 operator claim weakens the manual-entry boundary")
        if (
            not isinstance(self.review_timestamp, datetime)
            or self.review_timestamp.tzinfo is None
            or self.review_timestamp.utcoffset() is None
            or self.review_timestamp.utcoffset().total_seconds() != 0
        ):
            raise ValueError("C4 operator claim timestamp must be normalized UTC")
        if len(self.output_judgments) != 2:
            raise ValueError("C4 operator claim requires exactly two judgments")
        for judgment in self.output_judgments:
            C4OutputHumanJudgment.model_validate(
                judgment.model_dump(mode="python", round_trip=True)
            )
        C4PairHumanJudgment.model_validate(
            self.pair_judgment.model_dump(mode="python", round_trip=True)
        )
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"claim_id", "claim_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses("c4_review_claim", payload)
        if self.claim_id != expected_id:
            raise ValueError("C4 operator claim ID differs from canonical content")
        if self.claim_sha256 != expected_sha256:
            raise ValueError("C4 operator claim SHA-256 differs from canonical content")
        _require_bounded_canonical(self, label="C4 operator unsigned claim")
        return self


def _validate_review_inputs(
    packet: C4BlindReviewPacket,
    operator_policy: C4HumanReviewOperatorPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    output_judgments: tuple[C4OutputHumanJudgment, C4OutputHumanJudgment],
    pair_judgment: C4PairHumanJudgment,
) -> tuple[
    C4BlindReviewPacket,
    C4HumanReviewOperatorPolicy,
    C4BlindPresentationManifest,
    tuple[C4OutputHumanJudgment, C4OutputHumanJudgment],
    C4PairHumanJudgment,
]:
    packet = _cold_validate(
        packet,
        C4BlindReviewPacket,
        label="C4 blind review packet",
    )
    operator_policy = _cold_validate(
        operator_policy,
        C4HumanReviewOperatorPolicy,
        label="C4 operator policy",
    )
    presentation_manifest = _cold_validate(
        presentation_manifest,
        C4BlindPresentationManifest,
        label="C4 presentation manifest",
    )
    if type(output_judgments) is not tuple or len(output_judgments) != 2:
        raise ValueError("C4 operator claim requires an exact two-judgment tuple")
    validated_judgments = tuple(
        _cold_validate(
            judgment,
            C4OutputHumanJudgment,
            label="C4 output manual-entry judgment",
        )
        for judgment in output_judgments
    )
    pair_judgment = _cold_validate(
        pair_judgment,
        C4PairHumanJudgment,
        label="C4 pair manual-entry judgment",
    )
    if (
        packet.operator_policy_id != operator_policy.policy_id
        or packet.operator_policy_sha256 != operator_policy.operator_policy_sha256
        or packet.review_schema_id != operator_policy.review_schema_id
        or packet.source_image_sha256 != operator_policy.source_image_sha256
    ):
        raise ValueError("C4 operator policy differs from the blind packet")
    if (
        presentation_manifest.review_schema_id != packet.review_schema_id
        or presentation_manifest.operator_policy_id != packet.operator_policy_id
        or presentation_manifest.operator_policy_sha256 != packet.operator_policy_sha256
        or presentation_manifest.packet_id != packet.packet_id
        or presentation_manifest.packet_sha256 != packet.packet_sha256
        or presentation_manifest.material_commitment_id != packet.material_commitment_id
        or presentation_manifest.material_commitment_sha256
        != packet.material_commitment_sha256
        or presentation_manifest.source.image_sha256 != packet.source_image_sha256
    ):
        raise ValueError("C4 presentation manifest differs from the blind packet")
    expected_output_records = tuple(
        (
            reference.blind_code,
            reference.blind_order_sha256,
            reference.output_sha256,
        )
        for reference in packet.outputs
    )
    actual_output_records = tuple(
        (item.blind_code, item.blind_order_sha256, item.image_sha256)
        for item in presentation_manifest.outputs
    )
    if actual_output_records != expected_output_records:
        raise ValueError("C4 presentation PNG order differs from the blind packet")
    for judgment, reference in zip(
        validated_judgments,
        packet.outputs,
        strict=True,
    ):
        if (
            judgment.blind_code != reference.blind_code
            or judgment.source_image_sha256 != packet.source_image_sha256
            or judgment.instruction_sha256 != reference.instruction_sha256
            or judgment.output_sha256 != reference.output_sha256
        ):
            raise ValueError("Manual-entry judgment differs from its blind binding")
    return (
        packet,
        operator_policy,
        presentation_manifest,
        validated_judgments,
        pair_judgment,
    )


def build_c4_operator_unsigned_claim(
    packet: C4BlindReviewPacket,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    reviewer_pseudonym: str,
    review_timestamp: datetime,
    output_judgments: tuple[C4OutputHumanJudgment, C4OutputHumanJudgment],
    pair_judgment: C4PairHumanJudgment,
    external_one_time_ledger_lease_sha256: str,
) -> C4HumanReviewUnsignedClaim:
    (
        packet,
        operator_policy,
        presentation_manifest,
        output_judgments,
        pair_judgment,
    ) = _validate_review_inputs(
        packet,
        operator_policy,
        presentation_manifest,
        output_judgments,
        pair_judgment,
    )
    base = {
        "schema_version": "rei-c4-human-review-unsigned-claim-v1",
        "receipt_domain": C4_OPERATOR_RECEIPT_DOMAIN,
        "operator_attestation_claim": C4_OPERATOR_ATTESTATION_CLAIM,
        "operator_policy_id": operator_policy.policy_id,
        "operator_policy_sha256": operator_policy.operator_policy_sha256,
        "review_schema_id": packet.review_schema_id,
        "packet_id": packet.packet_id,
        "packet_sha256": packet.packet_sha256,
        "material_commitment_id": packet.material_commitment_id,
        "material_commitment_sha256": packet.material_commitment_sha256,
        "reviewer_pseudonym": reviewer_pseudonym,
        "review_timestamp": review_timestamp,
        "output_judgments": output_judgments,
        "pair_judgment": pair_judgment,
        "presentation_manifest_id": presentation_manifest.presentation_manifest_id,
        "presentation_manifest_sha256": (
            presentation_manifest.presentation_manifest_sha256
        ),
        "external_one_time_ledger_lease_sha256": (
            external_one_time_ledger_lease_sha256
        ),
        "operator_claims_ledger_lease_preissued": True,
        "cold_validation_proves_ledger_lease_issuance": False,
        "live_external_ledger_verification_required": True,
        "manual_entry_issuer_external_to_model_runner": True,
        "model_runner_key_access_allowed": False,
        "attestation_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    claim_id, claim_sha256 = _content_addresses("c4_review_claim", base)
    return C4HumanReviewUnsignedClaim(
        claim_id=claim_id,
        claim_sha256=claim_sha256,
        **base,
    )


def c4_operator_attestation_message(
    claim: C4HumanReviewUnsignedClaim,
) -> bytes:
    claim = _cold_validate(
        claim,
        C4HumanReviewUnsignedClaim,
        label="C4 operator unsigned claim",
    )
    return (
        C4_OPERATOR_RECEIPT_DOMAIN.encode("ascii")
        + b"\x00"
        + claim.canonical_json_bytes()
    )


class C4HumanReviewOperatorAttestation(FrozenArtifactModel):
    """External HMAC receipt for a claim, not proof of human cognition.

    ``False`` below excludes direct key material, not covert encodings in
    trusted external claim fields.
    """

    schema_version: Literal["rei-c4-human-review-operator-attestation-v1"] = (
        "rei-c4-human-review-operator-attestation-v1"
    )
    attestation_id: NonEmptyId
    attestation_sha256: HashDigest
    claim: C4HumanReviewUnsignedClaim
    hmac_algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    hmac_sha256: HashDigest
    operator_attestation_claim: Literal[
        "trusted_external_operator_attested_manual_entry"
    ]
    manual_entry_issuer_external_to_model_runner: Literal[True] = True
    direct_operator_secret_material_stored_in_artifact: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    cold_validation_authenticates_operator_hmac: Literal[False] = False
    secret_reverification_required_before_trust: Literal[True] = True
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_attestation(self) -> Self:
        C4HumanReviewUnsignedClaim.model_validate(
            self.claim.model_dump(mode="python", round_trip=True)
        )
        if (
            self.hmac_algorithm != "HMAC-SHA256"
            or self.operator_attestation_claim != C4_OPERATOR_ATTESTATION_CLAIM
            or self.manual_entry_issuer_external_to_model_runner is not True
            or self.direct_operator_secret_material_stored_in_artifact is not False
            or self.attestation_proves_human_cognition is not False
            or self.cold_validation_authenticates_operator_hmac is not False
            or self.secret_reverification_required_before_trust is not True
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 operator attestation weakens the receipt boundary")
        if self.claim.operator_attestation_claim != self.operator_attestation_claim:
            raise ValueError("C4 operator attestation claim differs from its payload")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"attestation_id", "attestation_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_operator_attestation",
            payload,
        )
        if self.attestation_id != expected_id:
            raise ValueError(
                "C4 operator attestation ID differs from canonical content"
            )
        if self.attestation_sha256 != expected_sha256:
            raise ValueError(
                "C4 operator attestation SHA-256 differs from canonical content"
            )
        _require_bounded_canonical(self, label="C4 operator attestation")
        return self


def build_c4_operator_attestation(
    claim: C4HumanReviewUnsignedClaim,
    *,
    external_hmac_sha256: str,
) -> C4HumanReviewOperatorAttestation:
    """Record an external receipt tag without generating or signing it."""

    claim = _cold_validate(
        claim,
        C4HumanReviewUnsignedClaim,
        label="C4 operator unsigned claim",
    )
    base = {
        "schema_version": "rei-c4-human-review-operator-attestation-v1",
        "claim": claim,
        "hmac_algorithm": "HMAC-SHA256",
        "hmac_sha256": external_hmac_sha256,
        "operator_attestation_claim": C4_OPERATOR_ATTESTATION_CLAIM,
        "manual_entry_issuer_external_to_model_runner": True,
        "direct_operator_secret_material_stored_in_artifact": False,
        "attestation_proves_human_cognition": False,
        "cold_validation_authenticates_operator_hmac": False,
        "secret_reverification_required_before_trust": True,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    attestation_id, attestation_sha256 = _content_addresses(
        "c4_operator_attestation",
        base,
    )
    return C4HumanReviewOperatorAttestation(
        attestation_id=attestation_id,
        attestation_sha256=attestation_sha256,
        **base,
    )


def _validate_operator_secret(
    policy: C4HumanReviewOperatorPolicy,
    operator_secret: bytes,
) -> None:
    if type(operator_secret) is not bytes:
        raise TypeError("C4 operator secret must be bytes")
    if not C4_HMAC_KEY_MIN_BYTES <= len(operator_secret) <= C4_HMAC_KEY_MAX_BYTES:
        raise ValueError("C4 operator secret byte length is outside policy bounds")
    actual_commitment = _bytes_sha256(operator_secret)
    if not hmac.compare_digest(
        actual_commitment,
        policy.hmac_key_commitment_sha256,
    ):
        raise ValueError("C4 operator secret differs from the pinned policy")
    _reject_operator_secret_material(policy, operator_secret)


def _reject_operator_secret_material(value: object, operator_secret: bytes) -> None:
    """Reject direct key bytes, exact UTF-8 text and hexadecimal material.

    This is a defense-in-depth check under a trusted-caller contract, not a
    proof that arbitrary external text contains no covert reversible encoding.
    """

    encoded = canonical_json_bytes(value)
    try:
        utf8_literal = canonical_json_bytes(operator_secret.decode("utf-8"))
    except UnicodeDecodeError:
        utf8_literal = None
    if (
        operator_secret in encoded
        or (utf8_literal is not None and utf8_literal in encoded)
        or operator_secret.hex().encode("ascii") in encoded.lower()
    ):
        raise ValueError(
            "C4 artifact contains forbidden direct operator-secret material"
        )


def verify_c4_operator_attestation(
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4HumanReviewOperatorAttestation,
    *,
    operator_secret: bytes,
) -> C4HumanReviewOperatorAttestation:
    operator_policy = _cold_validate(
        operator_policy,
        C4HumanReviewOperatorPolicy,
        label="C4 operator policy",
    )
    attestation = _cold_validate(
        attestation,
        C4HumanReviewOperatorAttestation,
        label="C4 operator attestation",
    )
    if (
        attestation.claim.operator_policy_id != operator_policy.policy_id
        or attestation.claim.operator_policy_sha256
        != operator_policy.operator_policy_sha256
        or attestation.claim.review_schema_id != operator_policy.review_schema_id
    ):
        raise ValueError("C4 operator attestation differs from the pinned policy")
    _validate_operator_secret(operator_policy, operator_secret)
    _reject_operator_secret_material(attestation, operator_secret)
    expected_hmac = hmac.digest(
        operator_secret,
        c4_operator_attestation_message(attestation.claim),
        "sha256",
    ).hex()
    if not hmac.compare_digest(expected_hmac, attestation.hmac_sha256):
        raise ValueError("C4 operator attestation HMAC verification failed")
    return attestation


class C4ConsumedOperatorPolicyReceipt(FrozenArtifactModel):
    """External-ledger claim of one atomic policy/lease consumption."""

    schema_version: Literal["rei-c4-consumed-operator-policy-receipt-v1"] = (
        "rei-c4-consumed-operator-policy-receipt-v1"
    )
    consumed_receipt_id: NonEmptyId
    consumed_receipt_sha256: HashDigest
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    external_one_time_ledger_lease_sha256: HashDigest
    claim_id: NonEmptyId
    claim_sha256: HashDigest
    attestation_id: NonEmptyId
    attestation_sha256: HashDigest
    attestation_hmac_sha256: HashDigest
    external_transaction_id: NonEmptyId
    external_transaction_timestamp: UtcTimestamp
    external_ledger_claimed_atomic_consume_once: Literal[True] = True
    ledger_state_external_to_model_runner: Literal[True] = True
    cold_validation_proves_live_ledger_state: Literal[False] = False
    live_external_ledger_reverification_required: Literal[True] = True
    attestation_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_consumed_receipt(self) -> Self:
        if (
            not isinstance(self.external_transaction_timestamp, datetime)
            or self.external_transaction_timestamp.tzinfo is None
            or self.external_transaction_timestamp.utcoffset() is None
            or self.external_transaction_timestamp.utcoffset().total_seconds() != 0
        ):
            raise ValueError("C4 ledger transaction timestamp must be normalized UTC")
        if (
            self.external_ledger_claimed_atomic_consume_once is not True
            or self.ledger_state_external_to_model_runner is not True
            or self.cold_validation_proves_live_ledger_state is not False
            or self.live_external_ledger_reverification_required is not True
            or self.attestation_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 consumed receipt weakens the external-ledger boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"consumed_receipt_id", "consumed_receipt_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_consumed_policy_receipt",
            payload,
        )
        if self.consumed_receipt_id != expected_id:
            raise ValueError("C4 consumed receipt ID differs from canonical content")
        if self.consumed_receipt_sha256 != expected_sha256:
            raise ValueError(
                "C4 consumed receipt SHA-256 differs from canonical content"
            )
        _require_bounded_canonical(self, label="C4 consumed operator-policy receipt")
        return self


def record_c4_consumed_operator_policy_receipt(
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4HumanReviewOperatorAttestation,
    *,
    external_transaction_id: str,
    external_transaction_timestamp: datetime,
) -> C4ConsumedOperatorPolicyReceipt:
    """Record values returned by a trusted external atomic ledger."""

    operator_policy = _cold_validate(
        operator_policy,
        C4HumanReviewOperatorPolicy,
        label="C4 operator policy",
    )
    attestation = _cold_validate(
        attestation,
        C4HumanReviewOperatorAttestation,
        label="C4 operator attestation",
    )
    claim = attestation.claim
    if (
        claim.operator_policy_id != operator_policy.policy_id
        or claim.operator_policy_sha256 != operator_policy.operator_policy_sha256
    ):
        raise ValueError("C4 ledger receipt inputs differ from the operator policy")
    base = {
        "schema_version": "rei-c4-consumed-operator-policy-receipt-v1",
        "operator_policy_id": operator_policy.policy_id,
        "operator_policy_sha256": operator_policy.operator_policy_sha256,
        "external_one_time_ledger_lease_sha256": (
            claim.external_one_time_ledger_lease_sha256
        ),
        "claim_id": claim.claim_id,
        "claim_sha256": claim.claim_sha256,
        "attestation_id": attestation.attestation_id,
        "attestation_sha256": attestation.attestation_sha256,
        "attestation_hmac_sha256": attestation.hmac_sha256,
        "external_transaction_id": external_transaction_id,
        "external_transaction_timestamp": external_transaction_timestamp,
        "external_ledger_claimed_atomic_consume_once": True,
        "ledger_state_external_to_model_runner": True,
        "cold_validation_proves_live_ledger_state": False,
        "live_external_ledger_reverification_required": True,
        "attestation_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    receipt_id, receipt_sha256 = _content_addresses(
        "c4_consumed_policy_receipt",
        base,
    )
    return C4ConsumedOperatorPolicyReceipt(
        consumed_receipt_id=receipt_id,
        consumed_receipt_sha256=receipt_sha256,
        **base,
    )


class C4ExternalUsedPolicyLedgerPort(Protocol):
    """Trusted external atomic state required for policy use and replay."""

    def consume_once(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4HumanReviewOperatorAttestation,
    ) -> C4ConsumedOperatorPolicyReceipt:
        """Atomically reject a reused policy or lease, then return its receipt."""
        ...

    def verify_consumed_use(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4HumanReviewOperatorAttestation,
        consumed_receipt: C4ConsumedOperatorPolicyReceipt,
    ) -> bool:
        """Check the exact receipt against current authoritative ledger state."""
        ...


def _validate_consumed_receipt_binding(
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4HumanReviewOperatorAttestation,
    consumed_receipt: C4ConsumedOperatorPolicyReceipt,
) -> C4ConsumedOperatorPolicyReceipt:
    consumed_receipt = _cold_validate(
        consumed_receipt,
        C4ConsumedOperatorPolicyReceipt,
        label="C4 consumed operator-policy receipt",
    )
    claim = attestation.claim
    if (
        consumed_receipt.operator_policy_id != operator_policy.policy_id
        or consumed_receipt.operator_policy_sha256
        != operator_policy.operator_policy_sha256
        or consumed_receipt.external_one_time_ledger_lease_sha256
        != claim.external_one_time_ledger_lease_sha256
        or consumed_receipt.claim_id != claim.claim_id
        or consumed_receipt.claim_sha256 != claim.claim_sha256
        or consumed_receipt.attestation_id != attestation.attestation_id
        or consumed_receipt.attestation_sha256 != attestation.attestation_sha256
        or consumed_receipt.attestation_hmac_sha256 != attestation.hmac_sha256
    ):
        raise ValueError("C4 consumed receipt differs from policy and attestation")
    return consumed_receipt


def _consume_operator_policy_once(
    ledger: C4ExternalUsedPolicyLedgerPort,
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4HumanReviewOperatorAttestation,
) -> C4ConsumedOperatorPolicyReceipt:
    consume_once = getattr(ledger, "consume_once", None)
    if not callable(consume_once):
        raise TypeError("C4 sealing requires an external atomic ledger consume port")
    consumed_receipt = consume_once(
        operator_policy=operator_policy,
        attestation=attestation,
    )
    return _validate_consumed_receipt_binding(
        operator_policy,
        attestation,
        consumed_receipt,
    )


def _reverify_consumed_operator_policy(
    ledger: C4ExternalUsedPolicyLedgerPort,
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4HumanReviewOperatorAttestation,
    consumed_receipt: C4ConsumedOperatorPolicyReceipt,
) -> C4ConsumedOperatorPolicyReceipt:
    consumed_receipt = _validate_consumed_receipt_binding(
        operator_policy,
        attestation,
        consumed_receipt,
    )
    verify_consumed_use = getattr(ledger, "verify_consumed_use", None)
    if not callable(verify_consumed_use):
        raise TypeError(
            "C4 replay requires an external atomic ledger verification port"
        )
    verified = verify_consumed_use(
        operator_policy=operator_policy,
        attestation=attestation,
        consumed_receipt=consumed_receipt,
    )
    if verified is not True:
        raise ValueError("C4 external ledger did not verify the consumed policy use")
    return consumed_receipt


class C4SealedHumanReviewSubmission(FrozenArtifactModel):
    """Immutable operator-attested submission with no identity reveal mapping."""

    schema_version: Literal["rei-c4-sealed-human-review-v1"] = (
        "rei-c4-sealed-human-review-v1"
    )
    submission_id: NonEmptyId
    packet: C4BlindReviewPacket
    operator_policy: C4HumanReviewOperatorPolicy
    presentation_manifest: C4BlindPresentationManifest
    operator_attestation: C4HumanReviewOperatorAttestation
    consumed_policy_receipt: C4ConsumedOperatorPolicyReceipt
    reviewer_pseudonym: NonEmptyId
    review_timestamp: UtcTimestamp
    rubric_version: Literal["c4-visual-remediation-human-review-v1"]
    review_state: Literal["sealed_submission"] = "sealed_submission"
    output_judgments: tuple[C4OutputHumanJudgment, ...] = Field(
        min_length=2, max_length=2
    )
    pair_judgment: C4PairHumanJudgment
    human_review_passed: bool
    operator_attestation_claim: Literal[
        "trusted_external_operator_attested_manual_entry"
    ]
    operator_receipt_secret_reverification_required: Literal[True] = True
    external_ledger_reverification_required: Literal[True] = True
    cold_validation_authenticates_operator_receipt: Literal[False] = False
    cold_validation_proves_live_ledger_state: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    human_field_origin: Literal["trusted_external_operator_attested_manual_entry"]
    reveal_mapping_present: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_submission(self) -> Self:
        (
            packet,
            operator_policy,
            presentation_manifest,
            output_judgments,
            pair_judgment,
        ) = _validate_review_inputs(
            self.packet,
            self.operator_policy,
            self.presentation_manifest,
            self.output_judgments,
            self.pair_judgment,
        )
        attestation = _cold_validate(
            self.operator_attestation,
            C4HumanReviewOperatorAttestation,
            label="C4 operator attestation",
        )
        consumed_receipt = _validate_consumed_receipt_binding(
            operator_policy,
            attestation,
            self.consumed_policy_receipt,
        )
        _ID_ADAPTER.validate_python(self.reviewer_pseudonym, strict=True)
        if (
            not isinstance(self.review_timestamp, datetime)
            or self.review_timestamp.tzinfo is None
            or self.review_timestamp.utcoffset() is None
            or self.review_timestamp.utcoffset().total_seconds() != 0
        ):
            raise ValueError("C4 review timestamp must be normalized UTC")
        if (
            self.review_state != "sealed_submission"
            or self.operator_attestation_claim != C4_OPERATOR_ATTESTATION_CLAIM
            or self.operator_receipt_secret_reverification_required is not True
            or self.external_ledger_reverification_required is not True
            or self.cold_validation_authenticates_operator_receipt is not False
            or self.cold_validation_proves_live_ledger_state is not False
            or self.attestation_proves_human_cognition is not False
            or self.human_field_origin != C4_OPERATOR_ATTESTATION_CLAIM
            or self.reveal_mapping_present is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
            or type(self.human_review_passed) is not bool
        ):
            raise ValueError("C4 submission weakens a frozen operator-review boundary")
        if self.rubric_version != packet.rubric_version:
            raise ValueError("Submission rubric differs from the blind packet")
        claim = attestation.claim
        if (
            claim.operator_policy_id != operator_policy.policy_id
            or claim.operator_policy_sha256 != operator_policy.operator_policy_sha256
            or claim.review_schema_id != packet.review_schema_id
            or claim.packet_id != packet.packet_id
            or claim.packet_sha256 != packet.packet_sha256
            or claim.material_commitment_id != packet.material_commitment_id
            or claim.material_commitment_sha256 != packet.material_commitment_sha256
            or claim.presentation_manifest_id
            != presentation_manifest.presentation_manifest_id
            or claim.presentation_manifest_sha256
            != presentation_manifest.presentation_manifest_sha256
            or claim.reviewer_pseudonym != self.reviewer_pseudonym
            or claim.review_timestamp != self.review_timestamp
            or claim.output_judgments != output_judgments
            or claim.pair_judgment != pair_judgment
            or claim.operator_attestation_claim != self.operator_attestation_claim
            or consumed_receipt != self.consumed_policy_receipt
        ):
            raise ValueError("C4 sealed submission differs from its operator claim")
        expected_refs = packet.outputs
        if len(self.output_judgments) != 2 or len(expected_refs) != 2:
            raise ValueError("C4 submission must bind exactly two output judgments")
        for judgment, reference in zip(
            self.output_judgments,
            expected_refs,
            strict=True,
        ):
            C4OutputHumanJudgment.model_validate(
                judgment.model_dump(mode="python", round_trip=True)
            )
            if (
                judgment.blind_code != reference.blind_code
                or judgment.source_image_sha256 != packet.source_image_sha256
                or judgment.instruction_sha256 != reference.instruction_sha256
                or judgment.output_sha256 != reference.output_sha256
            ):
                raise ValueError("Manual-entry judgment differs from its blind binding")
        C4PairHumanJudgment.model_validate(
            self.pair_judgment.model_dump(mode="python", round_trip=True)
        )
        expected_pass = all(item.passed for item in self.output_judgments) and (
            self.pair_judgment.passed
        )
        if self.human_review_passed != expected_pass:
            raise ValueError("C4 rubric pass differs from the strict boolean replay")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"submission_id"}
        )
        if self.submission_id != content_id("c4_human_review", payload):
            raise ValueError("C4 human review ID differs from canonical content")
        _require_bounded_canonical(self, label="C4 human review submission")
        return self


def seal_c4_human_review(
    packet: C4BlindReviewPacket,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    operator_attestation: C4HumanReviewOperatorAttestation,
    operator_secret: bytes,
    used_policy_ledger: C4ExternalUsedPolicyLedgerPort,
) -> C4SealedHumanReviewSubmission:
    operator_attestation = verify_c4_operator_attestation(
        operator_policy,
        operator_attestation,
        operator_secret=operator_secret,
    )
    _reject_operator_secret_material(packet, operator_secret)
    _reject_operator_secret_material(presentation_manifest, operator_secret)
    claim = operator_attestation.claim
    (
        packet,
        operator_policy,
        presentation_manifest,
        canonical_judgments,
        pair_judgment,
    ) = _validate_review_inputs(
        packet,
        operator_policy,
        presentation_manifest,
        claim.output_judgments,
        claim.pair_judgment,
    )
    if (
        claim.operator_policy_id != operator_policy.policy_id
        or claim.operator_policy_sha256 != operator_policy.operator_policy_sha256
        or claim.review_schema_id != packet.review_schema_id
        or claim.packet_id != packet.packet_id
        or claim.packet_sha256 != packet.packet_sha256
        or claim.material_commitment_id != packet.material_commitment_id
        or claim.material_commitment_sha256 != packet.material_commitment_sha256
        or claim.presentation_manifest_id
        != presentation_manifest.presentation_manifest_id
        or claim.presentation_manifest_sha256
        != presentation_manifest.presentation_manifest_sha256
    ):
        raise ValueError("C4 operator claim differs from sealed review material")
    consumed_policy_receipt = _consume_operator_policy_once(
        used_policy_ledger,
        operator_policy,
        operator_attestation,
    )
    passed = all(item.passed for item in canonical_judgments) and pair_judgment.passed
    base = {
        "schema_version": "rei-c4-sealed-human-review-v1",
        "packet": packet,
        "operator_policy": operator_policy,
        "presentation_manifest": presentation_manifest,
        "operator_attestation": operator_attestation,
        "consumed_policy_receipt": consumed_policy_receipt,
        "reviewer_pseudonym": claim.reviewer_pseudonym,
        "review_timestamp": claim.review_timestamp,
        "rubric_version": packet.rubric_version,
        "review_state": "sealed_submission",
        "output_judgments": canonical_judgments,
        "pair_judgment": pair_judgment,
        "human_review_passed": passed,
        "operator_attestation_claim": C4_OPERATOR_ATTESTATION_CLAIM,
        "operator_receipt_secret_reverification_required": True,
        "external_ledger_reverification_required": True,
        "cold_validation_authenticates_operator_receipt": False,
        "cold_validation_proves_live_ledger_state": False,
        "attestation_proves_human_cognition": False,
        "human_field_origin": C4_OPERATOR_ATTESTATION_CLAIM,
        "reveal_mapping_present": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    return C4SealedHumanReviewSubmission(
        submission_id=content_id("c4_human_review", base), **base
    )


class C4HumanReviewGateResult(FrozenArtifactModel):
    """Fail-closed rubric result; no state proves human cognition."""

    schema_version: Literal["rei-c4-human-review-gate-v1"] = (
        "rei-c4-human-review-gate-v1"
    )
    gate_result_id: NonEmptyId
    packet: C4BlindReviewPacket
    operator_policy: C4HumanReviewOperatorPolicy
    review_status: ReviewStatus
    reason: ReviewReason
    submission: C4SealedHumanReviewSubmission | None = None
    human_review_passed: bool
    operator_receipt_status: Literal[
        "requires_runtime_secret_and_ledger_reverification",
        "not_applicable_missing",
        "not_applicable_skipped",
    ]
    operator_receipt_secret_reverification_required: Literal[True] = True
    external_ledger_reverification_required: Literal[True] = True
    cold_validation_authenticates_operator_receipt: Literal[False] = False
    cold_validation_proves_live_ledger_state: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_gate_result(self) -> Self:
        C4BlindReviewPacket.model_validate(
            self.packet.model_dump(mode="python", round_trip=True)
        )
        C4HumanReviewOperatorPolicy.model_validate(
            self.operator_policy.model_dump(mode="python", round_trip=True)
        )
        if (
            self.packet.operator_policy_id != self.operator_policy.policy_id
            or self.packet.operator_policy_sha256
            != self.operator_policy.operator_policy_sha256
        ):
            raise ValueError("C4 gate operator policy differs from the blind packet")
        if (
            self.semantic_quality_gate_passed is not False
            or self.operator_receipt_secret_reverification_required is not True
            or self.external_ledger_reverification_required is not True
            or self.cold_validation_authenticates_operator_receipt is not False
            or self.cold_validation_proves_live_ledger_state is not False
            or self.attestation_proves_human_cognition is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
            or type(self.human_review_passed) is not bool
        ):
            raise ValueError("C4 operator-review gate cannot grant semantic authority")
        if self.review_status == "sealed_submission":
            if self.submission is None or self.submission.packet != self.packet:
                raise ValueError(
                    "Sealed gate result requires its exact packet submission"
                )
            C4SealedHumanReviewSubmission.model_validate(
                self.submission.model_dump(mode="python", round_trip=True)
            )
            expected_pass = self.submission.human_review_passed
            expected_reason = (
                "human_review_passed" if expected_pass else "human_review_failed"
            )
            expected_receipt_status = (
                "requires_runtime_secret_and_ledger_reverification"
            )
        else:
            if self.submission is not None:
                raise ValueError(
                    "Missing or skipped review cannot contain a submission"
                )
            expected_pass = False
            expected_reason = (
                "human_review_missing"
                if self.review_status == "missing"
                else "human_review_skipped"
            )
            expected_receipt_status = (
                "not_applicable_missing"
                if self.review_status == "missing"
                else "not_applicable_skipped"
            )
        if (
            self.human_review_passed != expected_pass
            or self.reason != expected_reason
            or self.operator_receipt_status != expected_receipt_status
        ):
            raise ValueError("C4 review gate result does not replay fail closed")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"gate_result_id"}
        )
        if self.gate_result_id != content_id("c4_review_gate", payload):
            raise ValueError("C4 review gate ID differs from canonical content")
        _require_bounded_canonical(self, label="C4 human review gate")
        return self


def evaluate_c4_human_review(
    packet: C4BlindReviewPacket,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
    operator_secret: bytes,
    used_policy_ledger: C4ExternalUsedPolicyLedgerPort,
    submission: C4SealedHumanReviewSubmission | None = None,
    skipped: bool = False,
) -> C4HumanReviewGateResult:
    packet = _cold_validate(
        packet,
        C4BlindReviewPacket,
        label="C4 blind review packet",
    )
    operator_policy = _cold_validate(
        operator_policy,
        C4HumanReviewOperatorPolicy,
        label="C4 operator policy",
    )
    if (
        packet.operator_policy_id != operator_policy.policy_id
        or packet.operator_policy_sha256 != operator_policy.operator_policy_sha256
    ):
        raise ValueError("C4 gate operator policy differs from the blind packet")
    _validate_operator_secret(operator_policy, operator_secret)
    _reject_operator_secret_material(packet, operator_secret)
    if type(skipped) is not bool:
        raise TypeError("skipped must be a strict boolean")
    if skipped and submission is not None:
        raise ValueError("A skipped review cannot contain a sealed submission")
    if submission is not None and submission.packet != packet:
        raise ValueError("Operator submission belongs to a different blind packet")
    if submission is not None:
        submission = _cold_validate(
            submission,
            C4SealedHumanReviewSubmission,
            label="C4 sealed operator-review submission",
        )
        _reject_operator_secret_material(submission, operator_secret)
        if submission.operator_policy != operator_policy:
            raise ValueError("C4 submission belongs to a different operator policy")
        verify_c4_operator_attestation(
            operator_policy,
            submission.operator_attestation,
            operator_secret=operator_secret,
        )
        _reverify_consumed_operator_policy(
            used_policy_ledger,
            operator_policy,
            submission.operator_attestation,
            submission.consumed_policy_receipt,
        )
        review_status: ReviewStatus = "sealed_submission"
        passed = submission.human_review_passed
        reason: ReviewReason = (
            "human_review_passed" if passed else "human_review_failed"
        )
        operator_receipt_status = "requires_runtime_secret_and_ledger_reverification"
    elif skipped:
        review_status = "skipped"
        passed = False
        reason = "human_review_skipped"
        operator_receipt_status = "not_applicable_skipped"
    else:
        review_status = "missing"
        passed = False
        reason = "human_review_missing"
        operator_receipt_status = "not_applicable_missing"
    base = {
        "schema_version": "rei-c4-human-review-gate-v1",
        "packet": packet,
        "operator_policy": operator_policy,
        "review_status": review_status,
        "reason": reason,
        "submission": submission,
        "human_review_passed": passed,
        "operator_receipt_status": operator_receipt_status,
        "operator_receipt_secret_reverification_required": True,
        "external_ledger_reverification_required": True,
        "cold_validation_authenticates_operator_receipt": False,
        "cold_validation_proves_live_ledger_state": False,
        "attestation_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    return C4HumanReviewGateResult(
        gate_result_id=content_id("c4_review_gate", base), **base
    )


class C4ReviewIdentityMapping(FrozenModel):
    blind_code: NonEmptyId
    option_id: NonEmptyId
    instruction_sha256: HashDigest
    output_sha256: HashDigest
    renderer_id: NonEmptyId
    model_id: NonEmptyId
    model_revision: CommitDigest


class C4HumanReviewReveal(FrozenArtifactModel):
    """Identity mapping after a sealed claim; not proof of human cognition."""

    schema_version: Literal["rei-c4-human-review-reveal-v1"] = (
        "rei-c4-human-review-reveal-v1"
    )
    reveal_id: NonEmptyId
    submission: C4SealedHumanReviewSubmission
    material_commitment: C4ReviewMaterialCommitment
    mappings: tuple[C4ReviewIdentityMapping, ...] = Field(min_length=2, max_length=2)
    reveal_state: Literal["revealed_after_sealed_submission"] = (
        "revealed_after_sealed_submission"
    )
    reveal_mapping_present: Literal[True] = True
    operator_receipt_secret_reverification_required: Literal[True] = True
    external_ledger_reverification_required: Literal[True] = True
    cold_validation_authenticates_operator_receipt: Literal[False] = False
    cold_validation_proves_live_ledger_state: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_reveal(self) -> Self:
        C4SealedHumanReviewSubmission.model_validate(
            self.submission.model_dump(mode="python", round_trip=True)
        )
        C4ReviewMaterialCommitment.model_validate(
            self.material_commitment.model_dump(mode="python", round_trip=True)
        )
        if (
            self.reveal_state != "revealed_after_sealed_submission"
            or self.reveal_mapping_present is not True
            or self.operator_receipt_secret_reverification_required is not True
            or self.external_ledger_reverification_required is not True
            or self.cold_validation_authenticates_operator_receipt is not False
            or self.cold_validation_proves_live_ledger_state is not False
            or self.attestation_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 identity reveal weakens a frozen authority boundary")
        packet = self.submission.packet
        commitment = self.material_commitment
        if packet.material_commitment_id != commitment.commitment_id:
            raise ValueError("Reveal commitment differs from sealed blind submission")
        if packet.material_commitment_sha256 != commitment.material_commitment_sha256:
            raise ValueError("Reveal commitment SHA-256 differs from sealed submission")
        if packet.review_schema_id != commitment.review_schema_id:
            raise ValueError("Reveal schema differs from sealed blind submission")
        if (
            commitment.operator_policy_id != self.submission.operator_policy.policy_id
            or commitment.operator_policy_sha256
            != self.submission.operator_policy.operator_policy_sha256
            or packet.operator_policy_id != commitment.operator_policy_id
            or packet.operator_policy_sha256 != commitment.operator_policy_sha256
        ):
            raise ValueError("Reveal operator policy differs from sealed submission")
        expected_outputs = _blind_outputs(commitment)
        if packet.outputs != expected_outputs:
            raise ValueError("Reveal material does not reproduce the blind packet")
        expected_mappings = tuple(
            C4ReviewIdentityMapping(
                blind_code=reference.blind_code,
                option_id=reference.option_id,
                instruction_sha256=reference.instruction_sha256,
                output_sha256=reference.output_sha256,
                renderer_id=commitment.renderer_id,
                model_id=commitment.model_id,
                model_revision=commitment.model_revision,
            )
            for reference in packet.outputs
        )
        if len(self.mappings) != 2 or self.mappings != expected_mappings:
            raise ValueError("Reveal mapping differs from committed blind identities")
        for mapping in self.mappings:
            C4ReviewIdentityMapping.model_validate(
                mapping.model_dump(mode="python", round_trip=True)
            )
        payload = self.model_dump(mode="python", round_trip=True, exclude={"reveal_id"})
        if self.reveal_id != content_id("c4_review_reveal", payload):
            raise ValueError("C4 review reveal ID differs from canonical content")
        _require_bounded_canonical(self, label="C4 human review reveal")
        return self


def reveal_c4_review_identities(
    submission: C4SealedHumanReviewSubmission,
    *,
    material_commitment: C4ReviewMaterialCommitment,
    operator_secret: bytes,
    used_policy_ledger: C4ExternalUsedPolicyLedgerPort,
) -> C4HumanReviewReveal:
    if not isinstance(submission, C4SealedHumanReviewSubmission):
        raise TypeError(
            "Identity reveal requires a sealed operator-attested submission"
        )
    submission = _cold_validate(
        submission,
        C4SealedHumanReviewSubmission,
        label="Identity reveal submission",
    )
    material_commitment = _cold_validate(
        material_commitment,
        C4ReviewMaterialCommitment,
        label="C4 review commitment",
    )
    verify_c4_operator_attestation(
        submission.operator_policy,
        submission.operator_attestation,
        operator_secret=operator_secret,
    )
    _reject_operator_secret_material(material_commitment, operator_secret)
    _reverify_consumed_operator_policy(
        used_policy_ledger,
        submission.operator_policy,
        submission.operator_attestation,
        submission.consumed_policy_receipt,
    )
    if submission.packet.material_commitment_id != material_commitment.commitment_id:
        raise ValueError("Reveal commitment differs from sealed blind submission")
    if (
        submission.packet.material_commitment_sha256
        != material_commitment.material_commitment_sha256
    ):
        raise ValueError("Reveal commitment SHA-256 differs from sealed submission")
    if (
        material_commitment.operator_policy_id != submission.operator_policy.policy_id
        or material_commitment.operator_policy_sha256
        != submission.operator_policy.operator_policy_sha256
    ):
        raise ValueError("Reveal commitment differs from the operator policy")
    mappings = tuple(
        C4ReviewIdentityMapping(
            blind_code=reference.blind_code,
            option_id=reference.option_id,
            instruction_sha256=reference.instruction_sha256,
            output_sha256=reference.output_sha256,
            renderer_id=material_commitment.renderer_id,
            model_id=material_commitment.model_id,
            model_revision=material_commitment.model_revision,
        )
        for reference in submission.packet.outputs
    )
    base = {
        "schema_version": "rei-c4-human-review-reveal-v1",
        "submission": submission,
        "material_commitment": material_commitment,
        "mappings": mappings,
        "reveal_state": "revealed_after_sealed_submission",
        "reveal_mapping_present": True,
        "operator_receipt_secret_reverification_required": True,
        "external_ledger_reverification_required": True,
        "cold_validation_authenticates_operator_receipt": False,
        "cold_validation_proves_live_ledger_state": False,
        "attestation_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    return C4HumanReviewReveal(reveal_id=content_id("c4_review_reveal", base), **base)


__all__ = [
    "C4_BLINDING_POLICY",
    "C4_HMAC_KEY_MAX_BYTES",
    "C4_HMAC_KEY_MIN_BYTES",
    "C4_OPERATOR_ATTESTATION_CLAIM",
    "C4_OPERATOR_ENTRY_ORIGIN",
    "C4_OPERATOR_POLICY_SCHEME",
    "C4_OPERATOR_RECEIPT_DOMAIN",
    "C4_OUTPUT_POSITIVE_FIELDS",
    "C4_OUTPUT_UNCERTAINTY_FIELD",
    "C4_PAIR_POSITIVE_FIELDS",
    "C4_PRESENTATION_MAX_DECODED_BYTES",
    "C4_PRESENTATION_MAX_DIMENSION",
    "C4_PRESENTATION_MAX_PNG_BYTES",
    "C4_PRESENTATION_MAX_PNG_CHUNKS",
    "C4_PRESENTATION_POLICY",
    "C4_PRESENTATION_PNG_CHUNK_POLICY",
    "C4_REVIEW_MAX_CANONICAL_BYTES",
    "C4_REVIEW_RUBRIC_VERSION",
    "C4BlindPresentationManifest",
    "C4BlindHumanReviewSchema",
    "C4BlindOutputReference",
    "C4BlindReviewPacket",
    "C4ConsumedOperatorPolicyReceipt",
    "C4ExternalUsedPolicyLedgerPort",
    "C4HumanReviewOperatorAttestation",
    "C4HumanReviewOperatorPolicy",
    "C4HumanReviewGateResult",
    "C4HumanReviewReveal",
    "C4HumanReviewUnsignedClaim",
    "C4OutputHumanJudgment",
    "C4PairHumanJudgment",
    "C4PresentedPng",
    "C4ReviewIdentityMapping",
    "C4ReviewMaterialCommitment",
    "C4ReviewOptionMaterial",
    "C4SealedHumanReviewSubmission",
    "build_c4_blind_presentation_manifest",
    "build_c4_blind_human_review_schema",
    "build_c4_human_review_operator_policy",
    "build_c4_operator_attestation",
    "build_c4_operator_unsigned_claim",
    "c4_operator_attestation_message",
    "c4_blind_order_sha256",
    "commit_c4_review_material",
    "evaluate_c4_human_review",
    "make_c4_review_option_material",
    "prepare_c4_blind_review",
    "record_c4_output_human_judgment",
    "record_c4_consumed_operator_policy_receipt",
    "reveal_c4_review_identities",
    "seal_c4_human_review",
    "verify_c4_operator_attestation",
]
