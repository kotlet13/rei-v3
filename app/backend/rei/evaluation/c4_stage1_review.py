"""Stage 1 immutable-display and operator-review boundary for C4.

The foundation presentation manifest proves that controlled PNG inputs existed.
This module adds the stronger, versioned boundary needed before Stage 1 model
execution: the exact bytes read from pinned file handles are passed by value to
a trusted display port, re-read from those same handles after the display call,
and bound into a content-addressed execution receipt.  A later cold verifier
must re-open and re-hash caller-supplied paths; paths never enter an artifact.

Before any output exists, the top-level screen contract must pin a display
attester policy covering the exact UI bundle, CSP bytes, presenter revision and
a separate display-signing-key commitment.  The trusted port's exact-byte
acknowledgement is externally HMAC-attested and atomically consumed through a
live verifier whose key is never supplied to the model runner.

The display receipt is part of the canonical operator claim and therefore part
of its external HMAC.  Sealing additionally requires live one-time external
state for both the display receipt and the operator policy.  These receipts
attest execution and external claims only.  They do not prove human attention,
human cognition, semantic quality, or production authority.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Callable, Literal, Protocol, Self, TypeVar

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    UtcTimestamp,
)
from ..persistence.artifacts import FileArtifactStore
from ..providers.protocols import StoredArtifact
from .c4_blind_review import (
    C4_HMAC_KEY_MAX_BYTES,
    C4_HMAC_KEY_MIN_BYTES,
    C4_OPERATOR_ATTESTATION_CLAIM,
    C4_PRESENTATION_MAX_PNG_BYTES,
    C4BlindHumanReviewSchema,
    C4BlindOutputReference,
    C4BlindPresentationManifest,
    C4BlindReviewPacket,
    C4HumanReviewOperatorPolicy,
    C4OutputHumanJudgment,
    C4PairHumanJudgment,
)
from .c4_stage1_screen import C4Stage1ContentPin, C4Stage1ScreenContract


C4_STAGE1_DISPLAY_POLICY = "c4-stage1-exact-byte-display-execution-v1"
C4_STAGE1_DISPLAY_PORT_POLICY = "trusted-display-port-exact-bytes-v1"
C4_STAGE1_DISPLAY_ATTESTATION_DOMAIN = "rei-c4-stage1-external-display-attestation-v1"
C4_STAGE1_DISPLAY_ATTESTATION_SCHEME = "c4-stage1-external-display-hmac-sha256-v1"
C4_STAGE1_OPERATOR_RECEIPT_DOMAIN = "rei-c4-stage1-operator-manual-entry-receipt-v1"
C4_STAGE1_MAX_CANONICAL_BYTES = 256 * 1024

_C4_STAGE1_READ_CHUNK_BYTES = 1024 * 1024
_C4_STAGE1_FORBIDDEN_VISIBLE_IDENTITY_TOKENS = (
    "longcat",
    "omnigen",
    "meituan",
    "shitao",
)

Stage1OpaqueId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
Stage1ContentSecurityPolicy = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
]
Stage1ReviewStatus = Literal["sealed_submission", "missing", "skipped"]
Stage1ReviewReason = Literal[
    "human_review_passed",
    "human_review_failed",
    "human_review_missing",
    "human_review_skipped",
]

_OPAQUE_ID_ADAPTER = TypeAdapter(Stage1OpaqueId)
_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: object) -> str:
    return _bytes_sha256(canonical_json_bytes(value))


def _content_addresses(namespace: str, payload: object) -> tuple[str, str]:
    return content_id(namespace, payload), _canonical_sha256(payload)


def _cold_validate(
    value: object,
    model_type: type[_ModelT],
    *,
    label: str,
) -> _ModelT:
    if not isinstance(value, model_type):
        raise TypeError(f"{label} must be a {model_type.__name__}")
    return model_type.model_validate(value.model_dump(mode="python", round_trip=True))


def _require_bounded_canonical(value: object, *, label: str) -> None:
    if len(canonical_json_bytes(value)) > C4_STAGE1_MAX_CANONICAL_BYTES:
        raise ValueError(f"{label} exceeds the canonical serialization bound")


def _normalized_utc(value: datetime, *, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_clock(clock: Callable[[], datetime], *, label: str) -> datetime:
    if not callable(clock):
        raise TypeError("C4 Stage 1 display clock must be callable")
    try:
        value = clock()
    except Exception:
        raise ValueError("C4 Stage 1 display clock failed") from None
    return _normalized_utc(value, label=label)


def _validate_opaque_id(value: str, *, label: str) -> str:
    try:
        return _OPAQUE_ID_ADAPTER.validate_python(value, strict=True)
    except Exception:
        raise ValueError(f"{label} must be a bounded opaque identifier") from None


def _reject_visible_identity_labels(*values: str) -> None:
    for value in values:
        lowered = value.casefold()
        if any(
            token in lowered for token in _C4_STAGE1_FORBIDDEN_VISIBLE_IDENTITY_TOKENS
        ):
            raise ValueError(
                "C4 Stage 1 display material exposes a provider/model label"
            )


def _validate_operator_secret(
    operator_policy: C4HumanReviewOperatorPolicy,
    operator_secret: bytes,
) -> None:
    if type(operator_secret) is not bytes:
        raise TypeError("C4 Stage 1 operator secret must be bytes")
    if not C4_HMAC_KEY_MIN_BYTES <= len(operator_secret) <= C4_HMAC_KEY_MAX_BYTES:
        raise ValueError("C4 Stage 1 operator secret length is outside policy bounds")
    if not hmac.compare_digest(
        _bytes_sha256(operator_secret),
        operator_policy.hmac_key_commitment_sha256,
    ):
        raise ValueError("C4 Stage 1 operator secret differs from the pinned policy")
    _reject_operator_secret_material(operator_policy, operator_secret)


def _reject_operator_secret_material(value: object, operator_secret: bytes) -> None:
    """Reject direct key, exact UTF-8, and hexadecimal material.

    External opaque identifiers remain a trusted-caller boundary.  This check
    intentionally does not claim detection of arbitrary reversible encodings.
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
        raise ValueError("C4 Stage 1 artifact contains direct operator-secret material")


def _text_matches_secret_commitment(value: str, commitment_sha256: str) -> bool:
    candidates = [value.encode("utf-8")]
    try:
        candidates.append(bytes.fromhex(value))
    except ValueError:
        pass
    return any(
        hmac.compare_digest(_bytes_sha256(candidate), commitment_sha256)
        for candidate in candidates
    )


def _is_reparse_point(value: os.stat_result) -> bool:
    attributes = getattr(value, "st_file_attributes", 0)
    return bool(attributes & 0x400)


def _path_and_handle_identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


@dataclass(frozen=True, slots=True)
class _PinnedRead:
    value: bytes
    sha256: str


class _PinnedPngHandle:
    """One regular-file handle retained for pre/post display re-hashing."""

    def __init__(self, path: str | Path, *, expected_sha256: str, expected_size: int):
        self._path = Path(path)
        self._expected_sha256 = expected_sha256
        self._expected_size = expected_size
        self._descriptor: int | None = None
        self._initial_stat: os.stat_result | None = None

    def __enter__(self) -> _PinnedPngHandle:
        flags = os.O_RDONLY
        flags |= getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            path_lstat = os.lstat(self._path)
            if stat.S_ISLNK(path_lstat.st_mode) or _is_reparse_point(path_lstat):
                raise OSError
            descriptor = os.open(self._path, flags)
            handle_stat = os.fstat(descriptor)
            path_stat = os.stat(self._path)
            if (
                not stat.S_ISREG(handle_stat.st_mode)
                or not stat.S_ISREG(path_stat.st_mode)
                or _path_and_handle_identity(handle_stat)
                != _path_and_handle_identity(path_stat)
                or handle_stat.st_size != self._expected_size
                or path_stat.st_size != self._expected_size
                or self._expected_size <= 0
                or self._expected_size > C4_PRESENTATION_MAX_PNG_BYTES
            ):
                raise OSError
        except (OSError, ValueError):
            if "descriptor" in locals():
                os.close(descriptor)
            raise ValueError(
                "C4 Stage 1 display PNG path must be a stable regular file"
            ) from None
        self._descriptor = descriptor
        self._initial_stat = handle_stat
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is not None:
            os.close(descriptor)

    def read_and_rehash(self) -> _PinnedRead:
        descriptor = self._descriptor
        initial_stat = self._initial_stat
        if descriptor is None or initial_stat is None:
            raise RuntimeError("C4 Stage 1 display PNG handle is not open")
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            value = bytearray()
            limit = min(self._expected_size + 1, C4_PRESENTATION_MAX_PNG_BYTES + 1)
            while len(value) < limit:
                requested = min(_C4_STAGE1_READ_CHUNK_BYTES, limit - len(value))
                chunk = os.read(descriptor, requested)
                if not isinstance(chunk, bytes) or len(chunk) > requested:
                    raise OSError
                if not chunk:
                    break
                value.extend(chunk)
            handle_stat = os.fstat(descriptor)
            path_lstat = os.lstat(self._path)
            path_stat = os.stat(self._path)
        except (OSError, ValueError):
            raise ValueError(
                "C4 Stage 1 display PNG changed during exact-byte rehash"
            ) from None
        if (
            stat.S_ISLNK(path_lstat.st_mode)
            or _is_reparse_point(path_lstat)
            or not stat.S_ISREG(handle_stat.st_mode)
            or not stat.S_ISREG(path_stat.st_mode)
            or _path_and_handle_identity(handle_stat)
            != _path_and_handle_identity(initial_stat)
            or _path_and_handle_identity(path_stat)
            != _path_and_handle_identity(initial_stat)
            or handle_stat.st_size != self._expected_size
            or path_stat.st_size != self._expected_size
            or len(value) != self._expected_size
        ):
            raise ValueError("C4 Stage 1 display PNG changed during exact-byte rehash")
        exact = bytes(value)
        digest = _bytes_sha256(exact)
        if not hmac.compare_digest(digest, self._expected_sha256):
            raise ValueError("C4 Stage 1 display PNG differs from the blind packet")
        return _PinnedRead(value=exact, sha256=digest)


class C4Stage1DisplayAttesterPolicy(FrozenArtifactModel):
    """Pre-output commitment to the UI and separately keyed display attester."""

    schema_version: Literal["rei-c4-stage1-display-attester-policy-v1"] = (
        "rei-c4-stage1-display-attester-policy-v1"
    )
    display_policy_id: NonEmptyId
    display_policy_sha256: HashDigest
    policy_nonce: HashDigest
    ui_bundle_sha256: HashDigest
    content_security_policy: Stage1ContentSecurityPolicy
    content_security_policy_sha256: HashDigest
    presenter_implementation_id: Stage1OpaqueId
    presenter_revision: Stage1OpaqueId
    display_attester_id: Stage1OpaqueId
    display_signing_key_commitment_sha256: HashDigest
    attestation_scheme: Literal["c4-stage1-external-display-hmac-sha256-v1"]
    minimum_signing_key_bytes: Literal[32] = 32
    maximum_signing_key_bytes: Literal[128] = 128
    pre_output_screen_contract_pin_required: Literal[True] = True
    output_hashes_present: Literal[False] = False
    one_time_attestation_consumption_required: Literal[True] = True
    external_atomic_attestation_ledger_required: Literal[True] = True
    live_external_keyed_verification_required: Literal[True] = True
    cold_validation_authenticates_display_hmac: Literal[False] = False
    display_signing_key_external_to_model_runner: Literal[True] = True
    model_runner_signing_key_access_allowed: Literal[False] = False
    direct_display_signing_secret_material_stored: Literal[False] = False
    external_text_identifiers_trusted_caller_boundary: Literal[True] = True
    absence_of_covert_secret_encoding_proven: Literal[False] = False
    policy_proves_human_attention: Literal[False] = False
    policy_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_display_policy(self) -> Self:
        if self.content_security_policy_sha256 != _bytes_sha256(
            self.content_security_policy.encode("utf-8")
        ):
            raise ValueError("C4 Stage 1 CSP bytes differ from their policy hash")
        if (
            len(
                {
                    self.policy_nonce,
                    self.ui_bundle_sha256,
                    self.content_security_policy_sha256,
                    self.display_signing_key_commitment_sha256,
                }
            )
            != 4
        ):
            raise ValueError(
                "C4 Stage 1 display policy commitments are not independent"
            )
        if any(
            _text_matches_secret_commitment(
                value, self.display_signing_key_commitment_sha256
            )
            for value in (
                self.policy_nonce,
                self.ui_bundle_sha256,
                self.content_security_policy,
                self.presenter_implementation_id,
                self.presenter_revision,
                self.display_attester_id,
            )
        ):
            raise ValueError(
                "C4 Stage 1 display policy contains direct signing-secret material"
            )
        _reject_visible_identity_labels(
            self.presenter_implementation_id,
            self.presenter_revision,
            self.display_attester_id,
        )
        if (
            self.attestation_scheme != C4_STAGE1_DISPLAY_ATTESTATION_SCHEME
            or self.minimum_signing_key_bytes != C4_HMAC_KEY_MIN_BYTES
            or self.maximum_signing_key_bytes != C4_HMAC_KEY_MAX_BYTES
            or self.pre_output_screen_contract_pin_required is not True
            or self.output_hashes_present is not False
            or self.one_time_attestation_consumption_required is not True
            or self.external_atomic_attestation_ledger_required is not True
            or self.live_external_keyed_verification_required is not True
            or self.cold_validation_authenticates_display_hmac is not False
            or self.display_signing_key_external_to_model_runner is not True
            or self.model_runner_signing_key_access_allowed is not False
            or self.direct_display_signing_secret_material_stored is not False
            or self.external_text_identifiers_trusted_caller_boundary is not True
            or self.absence_of_covert_secret_encoding_proven is not False
            or self.policy_proves_human_attention is not False
            or self.policy_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 display policy weakens the attester boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"display_policy_id", "display_policy_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_s1_display_policy", payload
        )
        if (
            self.display_policy_id != expected_id
            or self.display_policy_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 display policy address differs from content")
        _require_bounded_canonical(self, label="C4 Stage 1 display policy")
        return self


def build_c4_stage1_display_attester_policy(
    *,
    policy_nonce: str,
    ui_bundle_sha256: str,
    content_security_policy: str,
    presenter_implementation_id: str,
    presenter_revision: str,
    display_attester_id: str,
    display_signing_key_commitment_sha256: str,
) -> C4Stage1DisplayAttesterPolicy:
    content_security_policy = TypeAdapter(Stage1ContentSecurityPolicy).validate_python(
        content_security_policy, strict=True
    )
    presenter_implementation_id = _validate_opaque_id(
        presenter_implementation_id, label="C4 Stage 1 presenter implementation"
    )
    presenter_revision = _validate_opaque_id(
        presenter_revision, label="C4 Stage 1 presenter revision"
    )
    display_attester_id = _validate_opaque_id(
        display_attester_id, label="C4 Stage 1 display attester"
    )
    base = {
        "schema_version": "rei-c4-stage1-display-attester-policy-v1",
        "policy_nonce": policy_nonce,
        "ui_bundle_sha256": ui_bundle_sha256,
        "content_security_policy": content_security_policy,
        "content_security_policy_sha256": _bytes_sha256(
            content_security_policy.encode("utf-8")
        ),
        "presenter_implementation_id": presenter_implementation_id,
        "presenter_revision": presenter_revision,
        "display_attester_id": display_attester_id,
        "display_signing_key_commitment_sha256": (
            display_signing_key_commitment_sha256
        ),
        "attestation_scheme": C4_STAGE1_DISPLAY_ATTESTATION_SCHEME,
        "minimum_signing_key_bytes": C4_HMAC_KEY_MIN_BYTES,
        "maximum_signing_key_bytes": C4_HMAC_KEY_MAX_BYTES,
        "pre_output_screen_contract_pin_required": True,
        "output_hashes_present": False,
        "one_time_attestation_consumption_required": True,
        "external_atomic_attestation_ledger_required": True,
        "live_external_keyed_verification_required": True,
        "cold_validation_authenticates_display_hmac": False,
        "display_signing_key_external_to_model_runner": True,
        "model_runner_signing_key_access_allowed": False,
        "direct_display_signing_secret_material_stored": False,
        "external_text_identifiers_trusted_caller_boundary": True,
        "absence_of_covert_secret_encoding_proven": False,
        "policy_proves_human_attention": False,
        "policy_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    policy_id, policy_sha256 = _content_addresses("c4_s1_display_policy", base)
    return C4Stage1DisplayAttesterPolicy(
        display_policy_id=policy_id,
        display_policy_sha256=policy_sha256,
        **base,
    )


def c4_stage1_display_policy_content_pin(
    policy: C4Stage1DisplayAttesterPolicy,
) -> C4Stage1ContentPin:
    """Return the exact generic pin consumed by the pre-output screen contract."""

    policy = _cold_validate(
        policy, C4Stage1DisplayAttesterPolicy, label="C4 Stage 1 display policy"
    )
    return C4Stage1ContentPin(
        kind="display_policy",
        artifact_id=policy.display_policy_id,
        artifact_hash=policy.content_hash(),
        schema_version=policy.schema_version,
    )


def _validate_pre_output_display_binding(
    screen_contract: C4Stage1ScreenContract,
    schema: C4BlindHumanReviewSchema,
    operator_policy: C4HumanReviewOperatorPolicy,
    display_policy: C4Stage1DisplayAttesterPolicy,
) -> C4Stage1ScreenContract:
    screen_contract = _cold_validate(
        screen_contract,
        C4Stage1ScreenContract,
        label="C4 Stage 1 pre-output screen contract",
    )
    display_policy = _cold_validate(
        display_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    expected_review_schema = C4Stage1ContentPin(
        kind="review_schema",
        artifact_id=schema.schema_id,
        artifact_hash=schema.content_hash(),
        schema_version=schema.schema_version,
    )
    expected_operator_policy = C4Stage1ContentPin(
        kind="review_operator_policy",
        artifact_id=operator_policy.policy_id,
        artifact_hash=operator_policy.content_hash(),
        schema_version=operator_policy.schema_version,
    )
    expected_display_policy = c4_stage1_display_policy_content_pin(display_policy)
    operator_policy_pins = getattr(screen_contract, "review_operator_policies", None)
    if operator_policy_pins is None:
        legacy_pin = getattr(screen_contract, "review_operator_policy", None)
        operator_policy_pins = (legacy_pin,) if legacy_pin is not None else ()
    if (
        screen_contract.review_schema != expected_review_schema
        or type(operator_policy_pins) is not tuple
        or operator_policy_pins.count(expected_operator_policy) != 1
        or screen_contract.display_policy != expected_display_policy
        or screen_contract.output_count != 0
        or screen_contract.output_artifact_ids != ()
    ):
        raise ValueError(
            "C4 Stage 1 display policy was not pinned by the pre-output contract"
        )
    return screen_contract


class C4Stage1DisplayContext(FrozenArtifactModel):
    """Label-free content-addressed context supplied to the display port."""

    schema_version: Literal["rei-c4-stage1-display-context-v1"] = (
        "rei-c4-stage1-display-context-v1"
    )
    context_id: NonEmptyId
    context_sha256: HashDigest
    screen_contract_id: NonEmptyId
    screen_contract_sha256: HashDigest
    display_policy_id: NonEmptyId
    display_policy_sha256: HashDigest
    display_policy_artifact_sha256: HashDigest
    ui_bundle_sha256: HashDigest
    content_security_policy_sha256: HashDigest
    display_attester_id: Stage1OpaqueId
    review_schema_id: NonEmptyId
    review_schema_sha256: HashDigest
    rubric_version: NonEmptyId
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    packet_id: NonEmptyId
    packet_sha256: HashDigest
    presentation_manifest_id: NonEmptyId
    presentation_manifest_sha256: HashDigest
    material_commitment_id: NonEmptyId
    material_commitment_sha256: HashDigest
    source_image_sha256: HashDigest
    outputs: tuple[C4BlindOutputReference, ...] = Field(min_length=2, max_length=2)
    pair_order_policy: Literal["ascending_sha256_of_blind_code"] = (
        "ascending_sha256_of_blind_code"
    )
    ui_implementation_id: Stage1OpaqueId
    ui_revision: Stage1OpaqueId
    ui_session_id: Stage1OpaqueId
    renderer_identity_structured_field_present: Literal[False] = False
    model_identity_structured_field_present: Literal[False] = False
    provider_or_model_labels_passed_to_display_port: Literal[False] = False
    other_provider_output_references_present: Literal[False] = False
    external_text_identifiers_trusted_caller_boundary: Literal[True] = True
    absence_of_covert_secret_encoding_proven: Literal[False] = False

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if len(self.outputs) != 2:
            raise ValueError("C4 Stage 1 display context requires two outputs")
        for output in self.outputs:
            C4BlindOutputReference.model_validate(
                output.model_dump(mode="python", round_trip=True)
            )
        order = tuple(item.blind_order_sha256 for item in self.outputs)
        if order != tuple(sorted(order)):
            raise ValueError("C4 Stage 1 display context has the wrong blind order")
        if (
            self.pair_order_policy != "ascending_sha256_of_blind_code"
            or self.renderer_identity_structured_field_present is not False
            or self.model_identity_structured_field_present is not False
            or self.provider_or_model_labels_passed_to_display_port is not False
            or self.other_provider_output_references_present is not False
            or self.external_text_identifiers_trusted_caller_boundary is not True
            or self.absence_of_covert_secret_encoding_proven is not False
        ):
            raise ValueError("C4 Stage 1 display context weakens the blind boundary")
        _reject_visible_identity_labels(
            self.display_attester_id,
            self.ui_implementation_id,
            self.ui_revision,
            self.ui_session_id,
            *(item.instruction for item in self.outputs),
        )
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"context_id", "context_sha256"}
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_display_context", payload
        )
        if self.context_id != expected_id or self.context_sha256 != expected_sha256:
            raise ValueError("C4 Stage 1 display context address differs from content")
        _require_bounded_canonical(self, label="C4 Stage 1 display context")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1VisibleOutput:
    """One output passed by value to the trusted UI; no hidden identity fields."""

    blind_code: str
    blind_order_sha256: str
    instruction: str
    instruction_sha256: str
    output_sha256: str
    png_bytes: bytes


class C4Stage1DisplayAckOutput(FrozenModel):
    blind_code: NonEmptyId
    blind_order_sha256: HashDigest
    instruction_sha256: HashDigest
    output_sha256: HashDigest
    received_png_sha256: HashDigest

    @model_validator(mode="after")
    def validate_ack_output(self) -> Self:
        if self.output_sha256 != self.received_png_sha256:
            raise ValueError("C4 Stage 1 display port received the wrong output bytes")
        return self


class C4Stage1DisplayPortAcknowledgement(FrozenArtifactModel):
    """Trusted-port completion claim; it does not prove attention or cognition."""

    schema_version: Literal["rei-c4-stage1-display-port-ack-v1"] = (
        "rei-c4-stage1-display-port-ack-v1"
    )
    acknowledgement_id: NonEmptyId
    acknowledgement_sha256: HashDigest
    display_port_policy: Literal["trusted-display-port-exact-bytes-v1"]
    context_id: NonEmptyId
    context_sha256: HashDigest
    source_image_sha256: HashDigest
    received_source_png_sha256: HashDigest
    outputs: tuple[C4Stage1DisplayAckOutput, ...] = Field(min_length=2, max_length=2)
    received_exact_bytes_bundle_sha256: HashDigest
    display_execution_completed: Literal[True] = True
    partial_display: Literal[False] = False
    provider_or_model_labels_present: Literal[False] = False
    acknowledgement_proves_human_attention: Literal[False] = False
    acknowledgement_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_acknowledgement(self) -> Self:
        if len(self.outputs) != 2:
            raise ValueError("C4 Stage 1 display acknowledgement requires two outputs")
        for output in self.outputs:
            C4Stage1DisplayAckOutput.model_validate(
                output.model_dump(mode="python", round_trip=True)
            )
        if (
            self.display_port_policy != C4_STAGE1_DISPLAY_PORT_POLICY
            or self.source_image_sha256 != self.received_source_png_sha256
            or self.display_execution_completed is not True
            or self.partial_display is not False
            or self.provider_or_model_labels_present is not False
            or self.acknowledgement_proves_human_attention is not False
            or self.acknowledgement_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 display acknowledgement weakens its boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"acknowledgement_id", "acknowledgement_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_display_ack", payload
        )
        if (
            self.acknowledgement_id != expected_id
            or self.acknowledgement_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 display acknowledgement address is invalid")
        _require_bounded_canonical(self, label="C4 Stage 1 display acknowledgement")
        return self


class C4Stage1TrustedDisplayPort(Protocol):
    """Trusted execution port that receives only label-free exact PNG bytes."""

    def display(
        self,
        *,
        context: C4Stage1DisplayContext,
        display_policy: C4Stage1DisplayAttesterPolicy,
        source_png_bytes: bytes,
        outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
    ) -> C4Stage1DisplayPortResult:
        """Display all buffers and return exact-byte plus external-HMAC evidence."""
        ...


def _exact_bytes_bundle_sha256(
    *,
    context: C4Stage1DisplayContext,
    source_sha256: str,
    output_records: tuple[tuple[str, str, str, str], tuple[str, str, str, str]],
) -> str:
    return _canonical_sha256(
        {
            "domain": "rei-c4-stage1-display-exact-bytes-bundle-v1",
            "context_id": context.context_id,
            "context_sha256": context.context_sha256,
            "source_sha256": source_sha256,
            "outputs": output_records,
        }
    )


def build_c4_stage1_display_port_acknowledgement(
    context: C4Stage1DisplayContext,
    *,
    source_png_bytes: bytes,
    outputs: tuple[C4Stage1VisibleOutput, C4Stage1VisibleOutput],
) -> C4Stage1DisplayPortAcknowledgement:
    """Build an acknowledgement after a trusted port completed presentation."""

    context = _cold_validate(
        context, C4Stage1DisplayContext, label="C4 Stage 1 display context"
    )
    if type(source_png_bytes) is not bytes:
        raise TypeError("C4 Stage 1 source display bytes must be bytes")
    if type(outputs) is not tuple or len(outputs) != 2:
        raise ValueError("C4 Stage 1 display acknowledgement requires two outputs")
    source_sha256 = _bytes_sha256(source_png_bytes)
    if not hmac.compare_digest(source_sha256, context.source_image_sha256):
        raise ValueError("C4 Stage 1 display port received the wrong source bytes")
    ack_outputs: list[C4Stage1DisplayAckOutput] = []
    bundle_records: list[tuple[str, str, str, str]] = []
    for visible, reference in zip(outputs, context.outputs, strict=True):
        if not isinstance(visible, C4Stage1VisibleOutput):
            raise TypeError("C4 Stage 1 visible output has the wrong type")
        received_sha256 = _bytes_sha256(visible.png_bytes)
        if (
            visible.blind_code != reference.blind_code
            or visible.blind_order_sha256 != reference.blind_order_sha256
            or visible.instruction != reference.instruction
            or visible.instruction_sha256 != reference.instruction_sha256
            or visible.output_sha256 != reference.output_sha256
            or received_sha256 != reference.output_sha256
        ):
            raise ValueError(
                "C4 Stage 1 display port received a mismatched blind output"
            )
        ack_outputs.append(
            C4Stage1DisplayAckOutput(
                blind_code=visible.blind_code,
                blind_order_sha256=visible.blind_order_sha256,
                instruction_sha256=visible.instruction_sha256,
                output_sha256=visible.output_sha256,
                received_png_sha256=received_sha256,
            )
        )
        bundle_records.append(
            (
                visible.blind_code,
                visible.blind_order_sha256,
                visible.instruction_sha256,
                received_sha256,
            )
        )
    bundle_sha256 = _exact_bytes_bundle_sha256(
        context=context,
        source_sha256=source_sha256,
        output_records=tuple(bundle_records),  # type: ignore[arg-type]
    )
    base = {
        "schema_version": "rei-c4-stage1-display-port-ack-v1",
        "display_port_policy": C4_STAGE1_DISPLAY_PORT_POLICY,
        "context_id": context.context_id,
        "context_sha256": context.context_sha256,
        "source_image_sha256": context.source_image_sha256,
        "received_source_png_sha256": source_sha256,
        "outputs": tuple(ack_outputs),
        "received_exact_bytes_bundle_sha256": bundle_sha256,
        "display_execution_completed": True,
        "partial_display": False,
        "provider_or_model_labels_present": False,
        "acknowledgement_proves_human_attention": False,
        "acknowledgement_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    acknowledgement_id, acknowledgement_sha256 = _content_addresses(
        "c4_stage1_display_ack", base
    )
    return C4Stage1DisplayPortAcknowledgement(
        acknowledgement_id=acknowledgement_id,
        acknowledgement_sha256=acknowledgement_sha256,
        **base,
    )


class C4Stage1DisplayAttestation(FrozenArtifactModel):
    """External keyed attestation over one exact display acknowledgement."""

    schema_version: Literal["rei-c4-stage1-display-attestation-v1"] = (
        "rei-c4-stage1-display-attestation-v1"
    )
    display_attestation_id: NonEmptyId
    display_attestation_sha256: HashDigest
    attestation_domain: Literal["rei-c4-stage1-external-display-attestation-v1"]
    attestation_scheme: Literal["c4-stage1-external-display-hmac-sha256-v1"]
    screen_contract_id: NonEmptyId
    screen_contract_sha256: HashDigest
    display_policy_id: NonEmptyId
    display_policy_sha256: HashDigest
    display_policy_artifact_sha256: HashDigest
    context_id: NonEmptyId
    context_sha256: HashDigest
    acknowledgement_id: NonEmptyId
    acknowledgement_sha256: HashDigest
    display_attester_id: Stage1OpaqueId
    hmac_algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    hmac_sha256: HashDigest
    external_keyed_verification_required: Literal[True] = True
    cold_validation_authenticates_display_hmac: Literal[False] = False
    direct_display_signing_secret_material_stored: Literal[False] = False
    attestation_proves_human_attention: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_display_attestation(self) -> Self:
        if (
            self.attestation_domain != C4_STAGE1_DISPLAY_ATTESTATION_DOMAIN
            or self.attestation_scheme != C4_STAGE1_DISPLAY_ATTESTATION_SCHEME
            or self.hmac_algorithm != "HMAC-SHA256"
            or self.external_keyed_verification_required is not True
            or self.cold_validation_authenticates_display_hmac is not False
            or self.direct_display_signing_secret_material_stored is not False
            or self.attestation_proves_human_attention is not False
            or self.attestation_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 display attestation weakens its boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"display_attestation_id", "display_attestation_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_s1_display_attestation", payload
        )
        if (
            self.display_attestation_id != expected_id
            or self.display_attestation_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 display attestation address is invalid")
        _require_bounded_canonical(self, label="C4 Stage 1 display attestation")
        return self


@dataclass(frozen=True, slots=True)
class C4Stage1DisplayPortResult:
    acknowledgement: C4Stage1DisplayPortAcknowledgement
    attestation: C4Stage1DisplayAttestation


def c4_stage1_display_attestation_message(
    display_policy: C4Stage1DisplayAttesterPolicy,
    context: C4Stage1DisplayContext,
    acknowledgement: C4Stage1DisplayPortAcknowledgement,
) -> bytes:
    display_policy = _cold_validate(
        display_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    context = _cold_validate(
        context, C4Stage1DisplayContext, label="C4 Stage 1 display context"
    )
    acknowledgement = _cold_validate(
        acknowledgement,
        C4Stage1DisplayPortAcknowledgement,
        label="C4 Stage 1 display acknowledgement",
    )
    return (
        C4_STAGE1_DISPLAY_ATTESTATION_DOMAIN.encode("ascii")
        + b"\x00"
        + canonical_json_bytes(
            {
                "screen_contract_id": context.screen_contract_id,
                "screen_contract_sha256": context.screen_contract_sha256,
                "display_policy_id": display_policy.display_policy_id,
                "display_policy_sha256": display_policy.display_policy_sha256,
                "display_policy_artifact_sha256": display_policy.content_hash(),
                "context_id": context.context_id,
                "context_sha256": context.context_sha256,
                "acknowledgement_id": acknowledgement.acknowledgement_id,
                "acknowledgement_sha256": acknowledgement.acknowledgement_sha256,
                "received_exact_bytes_bundle_sha256": (
                    acknowledgement.received_exact_bytes_bundle_sha256
                ),
            }
        )
    )


def build_c4_stage1_display_attestation(
    display_policy: C4Stage1DisplayAttesterPolicy,
    context: C4Stage1DisplayContext,
    acknowledgement: C4Stage1DisplayPortAcknowledgement,
    *,
    external_hmac_sha256: str,
) -> C4Stage1DisplayAttestation:
    display_policy = _cold_validate(
        display_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    context = _cold_validate(
        context, C4Stage1DisplayContext, label="C4 Stage 1 display context"
    )
    acknowledgement = _cold_validate(
        acknowledgement,
        C4Stage1DisplayPortAcknowledgement,
        label="C4 Stage 1 display acknowledgement",
    )
    if (
        context.display_policy_id != display_policy.display_policy_id
        or context.display_policy_sha256 != display_policy.display_policy_sha256
        or context.display_policy_artifact_sha256 != display_policy.content_hash()
        or context.display_attester_id != display_policy.display_attester_id
        or acknowledgement.context_id != context.context_id
        or acknowledgement.context_sha256 != context.context_sha256
    ):
        raise ValueError(
            "C4 Stage 1 display attestation differs from pinned invocation"
        )
    base = {
        "schema_version": "rei-c4-stage1-display-attestation-v1",
        "attestation_domain": C4_STAGE1_DISPLAY_ATTESTATION_DOMAIN,
        "attestation_scheme": C4_STAGE1_DISPLAY_ATTESTATION_SCHEME,
        "screen_contract_id": context.screen_contract_id,
        "screen_contract_sha256": context.screen_contract_sha256,
        "display_policy_id": display_policy.display_policy_id,
        "display_policy_sha256": display_policy.display_policy_sha256,
        "display_policy_artifact_sha256": display_policy.content_hash(),
        "context_id": context.context_id,
        "context_sha256": context.context_sha256,
        "acknowledgement_id": acknowledgement.acknowledgement_id,
        "acknowledgement_sha256": acknowledgement.acknowledgement_sha256,
        "display_attester_id": display_policy.display_attester_id,
        "hmac_algorithm": "HMAC-SHA256",
        "hmac_sha256": external_hmac_sha256,
        "external_keyed_verification_required": True,
        "cold_validation_authenticates_display_hmac": False,
        "direct_display_signing_secret_material_stored": False,
        "attestation_proves_human_attention": False,
        "attestation_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "model_judge_calls": 0,
    }
    attestation_id, attestation_sha256 = _content_addresses(
        "c4_s1_display_attestation", base
    )
    return C4Stage1DisplayAttestation(
        display_attestation_id=attestation_id,
        display_attestation_sha256=attestation_sha256,
        **base,
    )


def _validate_display_attestation_binding(
    display_policy: C4Stage1DisplayAttesterPolicy,
    context: C4Stage1DisplayContext,
    acknowledgement: C4Stage1DisplayPortAcknowledgement,
    attestation: C4Stage1DisplayAttestation,
) -> C4Stage1DisplayAttestation:
    attestation = _cold_validate(
        attestation,
        C4Stage1DisplayAttestation,
        label="C4 Stage 1 display attestation",
    )
    if (
        attestation.screen_contract_id != context.screen_contract_id
        or attestation.screen_contract_sha256 != context.screen_contract_sha256
        or attestation.display_policy_id != display_policy.display_policy_id
        or attestation.display_policy_sha256 != display_policy.display_policy_sha256
        or attestation.display_policy_artifact_sha256 != display_policy.content_hash()
        or attestation.context_id != context.context_id
        or attestation.context_sha256 != context.context_sha256
        or attestation.acknowledgement_id != acknowledgement.acknowledgement_id
        or attestation.acknowledgement_sha256 != acknowledgement.acknowledgement_sha256
        or attestation.display_attester_id != display_policy.display_attester_id
    ):
        raise ValueError("C4 Stage 1 display attestation differs from execution")
    return attestation


class C4Stage1ConsumedDisplayAttestation(FrozenArtifactModel):
    schema_version: Literal["rei-c4-stage1-consumed-display-attestation-v1"] = (
        "rei-c4-stage1-consumed-display-attestation-v1"
    )
    consumed_display_attestation_id: NonEmptyId
    consumed_display_attestation_sha256: HashDigest
    display_policy_id: NonEmptyId
    display_policy_sha256: HashDigest
    context_id: NonEmptyId
    context_sha256: HashDigest
    acknowledgement_id: NonEmptyId
    acknowledgement_sha256: HashDigest
    display_attestation_id: NonEmptyId
    display_attestation_sha256: HashDigest
    display_attestation_hmac_sha256: HashDigest
    external_transaction_id: Stage1OpaqueId
    external_transaction_timestamp: UtcTimestamp
    external_keyed_hmac_verified: Literal[True] = True
    external_ledger_claimed_atomic_consume_once: Literal[True] = True
    cold_validation_proves_live_verifier_state: Literal[False] = False
    live_external_reverification_required: Literal[True] = True
    receipt_proves_human_attention: Literal[False] = False
    receipt_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_consumed_display_attestation(self) -> Self:
        _normalized_utc(
            self.external_transaction_timestamp,
            label="display attestation transaction timestamp",
        )
        if (
            self.external_keyed_hmac_verified is not True
            or self.external_ledger_claimed_atomic_consume_once is not True
            or self.cold_validation_proves_live_verifier_state is not False
            or self.live_external_reverification_required is not True
            or self.receipt_proves_human_attention is not False
            or self.receipt_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
        ):
            raise ValueError(
                "C4 Stage 1 consumed display attestation weakens its boundary"
            )
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "consumed_display_attestation_id",
                "consumed_display_attestation_sha256",
            },
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_s1_attestation_use", payload
        )
        if (
            self.consumed_display_attestation_id != expected_id
            or self.consumed_display_attestation_sha256 != expected_sha256
        ):
            raise ValueError(
                "C4 Stage 1 consumed display attestation address is invalid"
            )
        _require_bounded_canonical(
            self, label="C4 Stage 1 consumed display attestation"
        )
        return self


def record_c4_stage1_consumed_display_attestation(
    display_policy: C4Stage1DisplayAttesterPolicy,
    context: C4Stage1DisplayContext,
    acknowledgement: C4Stage1DisplayPortAcknowledgement,
    attestation: C4Stage1DisplayAttestation,
    *,
    external_transaction_id: str,
    external_transaction_timestamp: datetime,
) -> C4Stage1ConsumedDisplayAttestation:
    display_policy = _cold_validate(
        display_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    context = _cold_validate(
        context, C4Stage1DisplayContext, label="C4 Stage 1 display context"
    )
    acknowledgement = _cold_validate(
        acknowledgement,
        C4Stage1DisplayPortAcknowledgement,
        label="C4 Stage 1 display acknowledgement",
    )
    attestation = _validate_display_attestation_binding(
        display_policy, context, acknowledgement, attestation
    )
    transaction_id = _validate_opaque_id(
        external_transaction_id, label="C4 Stage 1 display attestation transaction"
    )
    transaction_timestamp = _normalized_utc(
        external_transaction_timestamp,
        label="display attestation transaction timestamp",
    )
    base = {
        "schema_version": "rei-c4-stage1-consumed-display-attestation-v1",
        "display_policy_id": display_policy.display_policy_id,
        "display_policy_sha256": display_policy.display_policy_sha256,
        "context_id": context.context_id,
        "context_sha256": context.context_sha256,
        "acknowledgement_id": acknowledgement.acknowledgement_id,
        "acknowledgement_sha256": acknowledgement.acknowledgement_sha256,
        "display_attestation_id": attestation.display_attestation_id,
        "display_attestation_sha256": attestation.display_attestation_sha256,
        "display_attestation_hmac_sha256": attestation.hmac_sha256,
        "external_transaction_id": transaction_id,
        "external_transaction_timestamp": transaction_timestamp,
        "external_keyed_hmac_verified": True,
        "external_ledger_claimed_atomic_consume_once": True,
        "cold_validation_proves_live_verifier_state": False,
        "live_external_reverification_required": True,
        "receipt_proves_human_attention": False,
        "receipt_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
    }
    receipt_id, receipt_sha256 = _content_addresses("c4_s1_attestation_use", base)
    return C4Stage1ConsumedDisplayAttestation(
        consumed_display_attestation_id=receipt_id,
        consumed_display_attestation_sha256=receipt_sha256,
        **base,
    )


class C4Stage1ExternalDisplayAttestationVerifierPort(Protocol):
    """Separate keyed verifier and one-time store; the runner never gets its key."""

    def verify_attestation(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> bool: ...

    def consume_once(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
    ) -> C4Stage1ConsumedDisplayAttestation: ...

    def verify_consumed_use(
        self,
        *,
        display_policy: C4Stage1DisplayAttesterPolicy,
        context: C4Stage1DisplayContext,
        acknowledgement: C4Stage1DisplayPortAcknowledgement,
        attestation: C4Stage1DisplayAttestation,
        consumed_receipt: C4Stage1ConsumedDisplayAttestation,
    ) -> bool: ...


def _validate_consumed_display_attestation_binding(
    display_policy: C4Stage1DisplayAttesterPolicy,
    context: C4Stage1DisplayContext,
    acknowledgement: C4Stage1DisplayPortAcknowledgement,
    attestation: C4Stage1DisplayAttestation,
    consumed_receipt: C4Stage1ConsumedDisplayAttestation,
) -> C4Stage1ConsumedDisplayAttestation:
    consumed_receipt = _cold_validate(
        consumed_receipt,
        C4Stage1ConsumedDisplayAttestation,
        label="C4 Stage 1 consumed display attestation",
    )
    if (
        consumed_receipt.display_policy_id != display_policy.display_policy_id
        or consumed_receipt.display_policy_sha256
        != display_policy.display_policy_sha256
        or consumed_receipt.context_id != context.context_id
        or consumed_receipt.context_sha256 != context.context_sha256
        or consumed_receipt.acknowledgement_id != acknowledgement.acknowledgement_id
        or consumed_receipt.acknowledgement_sha256
        != acknowledgement.acknowledgement_sha256
        or consumed_receipt.display_attestation_id != attestation.display_attestation_id
        or consumed_receipt.display_attestation_sha256
        != attestation.display_attestation_sha256
        or consumed_receipt.display_attestation_hmac_sha256 != attestation.hmac_sha256
    ):
        raise ValueError("C4 Stage 1 attestation ledger receipt differs from display")
    return consumed_receipt


def _verify_and_consume_display_attestation_once(
    verifier: C4Stage1ExternalDisplayAttestationVerifierPort,
    display_policy: C4Stage1DisplayAttesterPolicy,
    context: C4Stage1DisplayContext,
    acknowledgement: C4Stage1DisplayPortAcknowledgement,
    attestation: C4Stage1DisplayAttestation,
) -> C4Stage1ConsumedDisplayAttestation:
    attestation = _validate_display_attestation_binding(
        display_policy, context, acknowledgement, attestation
    )
    verify = getattr(verifier, "verify_attestation", None)
    consume = getattr(verifier, "consume_once", None)
    if not callable(verify) or not callable(consume):
        raise TypeError("C4 Stage 1 display requires a live external keyed verifier")
    if (
        verify(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
        )
        is not True
    ):
        raise ValueError("C4 Stage 1 external display HMAC verification failed")
    consumed = consume(
        display_policy=display_policy,
        context=context,
        acknowledgement=acknowledgement,
        attestation=attestation,
    )
    return _validate_consumed_display_attestation_binding(
        display_policy, context, acknowledgement, attestation, consumed
    )


def _reverify_consumed_display_attestation(
    verifier: C4Stage1ExternalDisplayAttestationVerifierPort,
    display_policy: C4Stage1DisplayAttesterPolicy,
    context: C4Stage1DisplayContext,
    acknowledgement: C4Stage1DisplayPortAcknowledgement,
    attestation: C4Stage1DisplayAttestation,
    consumed_receipt: C4Stage1ConsumedDisplayAttestation,
) -> C4Stage1ConsumedDisplayAttestation:
    attestation = _validate_display_attestation_binding(
        display_policy, context, acknowledgement, attestation
    )
    consumed_receipt = _validate_consumed_display_attestation_binding(
        display_policy,
        context,
        acknowledgement,
        attestation,
        consumed_receipt,
    )
    verify_attestation = getattr(verifier, "verify_attestation", None)
    verify_consumed = getattr(verifier, "verify_consumed_use", None)
    if not callable(verify_attestation) or not callable(verify_consumed):
        raise TypeError("C4 Stage 1 replay requires a live keyed display verifier")
    if (
        verify_attestation(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
        )
        is not True
        or verify_consumed(
            display_policy=display_policy,
            context=context,
            acknowledgement=acknowledgement,
            attestation=attestation,
            consumed_receipt=consumed_receipt,
        )
        is not True
    ):
        raise ValueError("C4 Stage 1 display attestation is not live externally")
    return consumed_receipt


class C4Stage1DisplayedPng(FrozenModel):
    image_role: Literal["source", "output"]
    blind_code: NonEmptyId | None = None
    blind_order_sha256: HashDigest | None = None
    image_sha256: HashDigest
    byte_size: int = Field(gt=0, le=C4_PRESENTATION_MAX_PNG_BYTES)
    pre_display_sha256: HashDigest
    post_display_sha256: HashDigest
    same_open_file_handle_rehashed_before_and_after_display: Literal[True] = True
    exact_bytes_passed_by_value_to_display_port: Literal[True] = True
    local_path_stored_in_artifact: Literal[False] = False

    @model_validator(mode="after")
    def validate_displayed_png(self) -> Self:
        if self.image_role == "source":
            if self.blind_code is not None or self.blind_order_sha256 is not None:
                raise ValueError("C4 Stage 1 source display cannot carry a blind code")
        elif self.blind_code is None or self.blind_order_sha256 is None:
            raise ValueError("C4 Stage 1 output display requires a blind code")
        if (
            self.image_sha256 != self.pre_display_sha256
            or self.image_sha256 != self.post_display_sha256
            or self.same_open_file_handle_rehashed_before_and_after_display is not True
            or self.exact_bytes_passed_by_value_to_display_port is not True
            or self.local_path_stored_in_artifact is not False
        ):
            raise ValueError("C4 Stage 1 displayed PNG lacks exact-byte closure")
        return self


class C4Stage1DisplayCandidatePublicationBinding(FrozenModel):
    """Path-safe projection of one candidate embedded in a family marker."""

    option_id: Literal["enter_circle", "remain_edge"]
    candidate_receipt_id: NonEmptyId
    candidate_receipt_sha256: HashDigest
    prepared_worker_id: NonEmptyId
    prepared_worker_sha256: HashDigest
    worker_request_id: NonEmptyId
    worker_request_sha256: HashDigest
    staged_output_storage: StoredArtifact


class C4Stage1DisplayPublicationBinding(FrozenArtifactModel):
    """Durable projection of the atomic publication consumed by a display."""

    schema_version: Literal["rei-c4-stage1-display-publication-binding-v1"] = (
        "rei-c4-stage1-display-publication-binding-v1"
    )
    publication_binding_id: NonEmptyId
    publication_binding_sha256: HashDigest
    run_id: NonEmptyId
    prepared_attempt_id: NonEmptyId
    prepared_attempt_sha256: HashDigest
    prepared_anchor_storage: StoredArtifact
    member_publication_receipt_id: NonEmptyId
    member_publication_receipt_sha256: HashDigest
    member_publication_receipt_storage: StoredArtifact
    editor_role: Literal["primary", "alternate"]
    provider_slot_id: NonEmptyId
    source_storage: StoredArtifact
    candidates: tuple[
        C4Stage1DisplayCandidatePublicationBinding,
        C4Stage1DisplayCandidatePublicationBinding,
    ]
    publication_committed: Literal[True] = True
    both_options_technical_passed: Literal[True] = True
    generated_images_are_external_evidence: Literal[False] = False
    semantic_authority_granted: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        prepared_attempt_id: str,
        prepared_attempt_sha256: str,
        prepared_anchor_storage: StoredArtifact,
        member_publication_receipt_id: str,
        member_publication_receipt_sha256: str,
        member_publication_receipt_storage: StoredArtifact,
        editor_role: Literal["primary", "alternate"],
        provider_slot_id: str,
        source_storage: StoredArtifact,
        candidates: tuple[
            C4Stage1DisplayCandidatePublicationBinding,
            C4Stage1DisplayCandidatePublicationBinding,
        ],
    ) -> C4Stage1DisplayPublicationBinding:
        body = {
            "schema_version": "rei-c4-stage1-display-publication-binding-v1",
            "run_id": run_id,
            "prepared_attempt_id": prepared_attempt_id,
            "prepared_attempt_sha256": prepared_attempt_sha256,
            "prepared_anchor_storage": prepared_anchor_storage,
            "member_publication_receipt_id": member_publication_receipt_id,
            "member_publication_receipt_sha256": member_publication_receipt_sha256,
            "member_publication_receipt_storage": member_publication_receipt_storage,
            "editor_role": editor_role,
            "provider_slot_id": provider_slot_id,
            "source_storage": source_storage,
            "candidates": candidates,
            "publication_committed": True,
            "both_options_technical_passed": True,
            "generated_images_are_external_evidence": False,
            "semantic_authority_granted": False,
            "production_authority_granted": False,
        }
        binding_id, binding_sha256 = _content_addresses(
            "c4_stage1_display_publication", body
        )
        return cls(
            publication_binding_id=binding_id,
            publication_binding_sha256=binding_sha256,
            **body,
        )

    @model_validator(mode="after")
    def validate_publication_binding(self) -> Self:
        prepared = StoredArtifact.model_validate(
            self.prepared_anchor_storage.model_dump(mode="python", round_trip=True)
        )
        member = StoredArtifact.model_validate(
            self.member_publication_receipt_storage.model_dump(
                mode="python", round_trip=True
            )
        )
        source = StoredArtifact.model_validate(
            self.source_storage.model_dump(mode="python", round_trip=True)
        )
        candidates = tuple(
            C4Stage1DisplayCandidatePublicationBinding.model_validate(
                item.model_dump(mode="python", round_trip=True)
            )
            for item in self.candidates
        )
        if (
            prepared.run_id != self.run_id
            or prepared.relative_path != "diagnostics/c4_stage1_prepared_attempt.json"
            or member.run_id != self.run_id
            or member.relative_path
            != (
                "diagnostics/"
                f"{self.member_publication_receipt_id}.member-publication.json"
            )
            or source.run_id != self.run_id
            or tuple(item.option_id for item in candidates)
            != ("enter_circle", "remain_edge")
            or any(
                item.staged_output_storage.run_id != self.run_id for item in candidates
            )
            or len({item.candidate_receipt_id for item in candidates}) != 2
            or len({item.prepared_worker_id for item in candidates}) != 2
            or len({item.worker_request_id for item in candidates}) != 2
        ):
            raise ValueError("C4 Stage 1 display publication binding is inconsistent")
        body = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"publication_binding_id", "publication_binding_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_display_publication", body
        )
        if (
            self.publication_binding_id != expected_id
            or self.publication_binding_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 display publication binding changed")
        return self


class C4Stage1DisplayExecutionReceipt(FrozenArtifactModel):
    """Immutable exact-byte display execution receipt, not cognition evidence."""

    schema_version: Literal["rei-c4-stage1-display-execution-receipt-v1"] = (
        "rei-c4-stage1-display-execution-receipt-v1"
    )
    display_receipt_id: NonEmptyId
    display_receipt_sha256: HashDigest
    display_policy: Literal["c4-stage1-exact-byte-display-execution-v1"]
    publication_binding: C4Stage1DisplayPublicationBinding
    context: C4Stage1DisplayContext
    display_attester_policy: C4Stage1DisplayAttesterPolicy
    acknowledgement: C4Stage1DisplayPortAcknowledgement
    display_attestation: C4Stage1DisplayAttestation
    consumed_display_attestation: C4Stage1ConsumedDisplayAttestation
    source: C4Stage1DisplayedPng
    outputs: tuple[C4Stage1DisplayedPng, ...] = Field(min_length=2, max_length=2)
    display_started_at: UtcTimestamp
    display_completed_at: UtcTimestamp
    pre_display_exact_bytes_bundle_sha256: HashDigest
    port_received_exact_bytes_bundle_sha256: HashDigest
    post_display_exact_bytes_bundle_sha256: HashDigest
    trusted_display_port_invoked: Literal[True] = True
    display_execution_completed: Literal[True] = True
    partial_display: Literal[False] = False
    exact_bytes_passed_by_value: Literal[True] = True
    pre_and_post_display_same_handle_rehash: Literal[True] = True
    cold_path_reverification_required_before_claim_trust: Literal[True] = True
    cold_artifact_alone_proves_current_path_bytes: Literal[False] = False
    external_one_time_display_receipt_consumption_required: Literal[True] = True
    live_external_display_receipt_reverification_required: Literal[True] = True
    separately_keyed_display_attestation_required: Literal[True] = True
    live_external_display_attestation_reverification_required: Literal[True] = True
    source_or_output_local_paths_stored: Literal[False] = False
    provider_or_model_labels_present: Literal[False] = False
    external_text_identifiers_trusted_caller_boundary: Literal[True] = True
    absence_of_covert_secret_encoding_proven: Literal[False] = False
    display_receipt_proves_human_attention: Literal[False] = False
    display_receipt_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_display_receipt(self) -> Self:
        publication = C4Stage1DisplayPublicationBinding.model_validate(
            self.publication_binding.model_dump(mode="python", round_trip=True)
        )
        context = C4Stage1DisplayContext.model_validate(
            self.context.model_dump(mode="python", round_trip=True)
        )
        display_attester_policy = C4Stage1DisplayAttesterPolicy.model_validate(
            self.display_attester_policy.model_dump(mode="python", round_trip=True)
        )
        acknowledgement = C4Stage1DisplayPortAcknowledgement.model_validate(
            self.acknowledgement.model_dump(mode="python", round_trip=True)
        )
        display_attestation = _validate_display_attestation_binding(
            display_attester_policy,
            context,
            acknowledgement,
            self.display_attestation,
        )
        consumed_display_attestation = _validate_consumed_display_attestation_binding(
            display_attester_policy,
            context,
            acknowledgement,
            display_attestation,
            self.consumed_display_attestation,
        )
        source = C4Stage1DisplayedPng.model_validate(
            self.source.model_dump(mode="python", round_trip=True)
        )
        if source.image_role != "source" or len(self.outputs) != 2:
            raise ValueError(
                "C4 Stage 1 display receipt requires source and two outputs"
            )
        for output in self.outputs:
            C4Stage1DisplayedPng.model_validate(
                output.model_dump(mode="python", round_trip=True)
            )
            if output.image_role != "output":
                raise ValueError("C4 Stage 1 display receipt output has wrong role")
        output_records = tuple(
            (item.blind_code, item.blind_order_sha256, item.image_sha256)
            for item in self.outputs
        )
        expected_records = tuple(
            (item.blind_code, item.blind_order_sha256, item.output_sha256)
            for item in context.outputs
        )
        published_by_option = {
            item.option_id: item.staged_output_storage
            for item in publication.candidates
        }
        if (
            output_records != expected_records
            or source.image_sha256 != context.source_image_sha256
            or publication.source_storage.content_sha256 != source.image_sha256
            or publication.source_storage.size_bytes != source.byte_size
            or any(
                reference.option_id not in published_by_option
                or published_by_option[reference.option_id].content_sha256
                != displayed.image_sha256
                or published_by_option[reference.option_id].size_bytes
                != displayed.byte_size
                for reference, displayed in zip(
                    context.outputs, self.outputs, strict=True
                )
            )
            or context.display_policy_id != display_attester_policy.display_policy_id
            or context.display_policy_sha256
            != display_attester_policy.display_policy_sha256
            or context.display_policy_artifact_sha256
            != display_attester_policy.content_hash()
            or context.ui_bundle_sha256 != display_attester_policy.ui_bundle_sha256
            or context.content_security_policy_sha256
            != display_attester_policy.content_security_policy_sha256
            or context.display_attester_id
            != display_attester_policy.display_attester_id
        ):
            raise ValueError("C4 Stage 1 display receipt differs from its context")
        acknowledgement_records = tuple(
            (
                item.blind_code,
                item.blind_order_sha256,
                item.instruction_sha256,
                item.output_sha256,
                item.received_png_sha256,
            )
            for item in acknowledgement.outputs
        )
        expected_acknowledgement_records = tuple(
            (
                item.blind_code,
                item.blind_order_sha256,
                item.instruction_sha256,
                item.output_sha256,
                item.output_sha256,
            )
            for item in context.outputs
        )
        if (
            acknowledgement.context_id != context.context_id
            or acknowledgement.context_sha256 != context.context_sha256
            or acknowledgement.source_image_sha256 != context.source_image_sha256
            or acknowledgement.received_source_png_sha256 != source.image_sha256
            or acknowledgement_records != expected_acknowledgement_records
        ):
            raise ValueError(
                "C4 Stage 1 display receipt differs from port acknowledgement"
            )
        started = _normalized_utc(self.display_started_at, label="display_started_at")
        completed = _normalized_utc(
            self.display_completed_at, label="display_completed_at"
        )
        if completed < started:
            raise ValueError("C4 Stage 1 display timestamps moved backwards")
        if consumed_display_attestation.external_transaction_timestamp < completed:
            raise ValueError(
                "C4 Stage 1 display attestation was consumed before completion"
            )
        expected_bundle_sha256 = _exact_bytes_bundle_sha256(
            context=context,
            source_sha256=source.image_sha256,
            output_records=tuple(
                (
                    item.blind_code,
                    item.blind_order_sha256,
                    reference.instruction_sha256,
                    item.image_sha256,
                )
                for item, reference in zip(self.outputs, context.outputs, strict=True)
            ),
        )
        if (
            self.pre_display_exact_bytes_bundle_sha256 != expected_bundle_sha256
            or self.pre_display_exact_bytes_bundle_sha256
            != self.port_received_exact_bytes_bundle_sha256
            or self.pre_display_exact_bytes_bundle_sha256
            != self.post_display_exact_bytes_bundle_sha256
            or self.port_received_exact_bytes_bundle_sha256
            != acknowledgement.received_exact_bytes_bundle_sha256
        ):
            raise ValueError("C4 Stage 1 display byte bundle changed across execution")
        if (
            self.display_policy != C4_STAGE1_DISPLAY_POLICY
            or self.trusted_display_port_invoked is not True
            or self.display_execution_completed is not True
            or self.partial_display is not False
            or self.exact_bytes_passed_by_value is not True
            or self.pre_and_post_display_same_handle_rehash is not True
            or self.cold_path_reverification_required_before_claim_trust is not True
            or self.cold_artifact_alone_proves_current_path_bytes is not False
            or self.external_one_time_display_receipt_consumption_required is not True
            or self.live_external_display_receipt_reverification_required is not True
            or self.separately_keyed_display_attestation_required is not True
            or self.live_external_display_attestation_reverification_required
            is not True
            or self.source_or_output_local_paths_stored is not False
            or self.provider_or_model_labels_present is not False
            or self.external_text_identifiers_trusted_caller_boundary is not True
            or self.absence_of_covert_secret_encoding_proven is not False
            or self.display_receipt_proves_human_attention is not False
            or self.display_receipt_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 display receipt weakens authority boundaries")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"display_receipt_id", "display_receipt_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_display_receipt", payload
        )
        if (
            self.display_receipt_id != expected_id
            or self.display_receipt_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 display receipt address differs from content")
        _require_bounded_canonical(self, label="C4 Stage 1 display receipt")
        return self


def _validate_display_inputs(
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    operator_policy: C4HumanReviewOperatorPolicy,
    presentation_manifest: C4BlindPresentationManifest,
) -> tuple[
    C4BlindHumanReviewSchema,
    C4BlindReviewPacket,
    C4HumanReviewOperatorPolicy,
    C4BlindPresentationManifest,
]:
    schema = _cold_validate(schema, C4BlindHumanReviewSchema, label="C4 review schema")
    packet = _cold_validate(packet, C4BlindReviewPacket, label="C4 blind packet")
    operator_policy = _cold_validate(
        operator_policy, C4HumanReviewOperatorPolicy, label="C4 operator policy"
    )
    presentation_manifest = _cold_validate(
        presentation_manifest,
        C4BlindPresentationManifest,
        label="C4 presentation manifest",
    )
    if (
        packet.review_schema_id != schema.schema_id
        or packet.rubric_version != schema.rubric_version
        or packet.operator_policy_id != operator_policy.policy_id
        or packet.operator_policy_sha256 != operator_policy.operator_policy_sha256
        or operator_policy.review_schema_id != schema.schema_id
        or packet.source_image_sha256 != operator_policy.source_image_sha256
    ):
        raise ValueError("C4 Stage 1 schema/policy differs from blind packet")
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
        raise ValueError("C4 Stage 1 presentation differs from blind packet")
    actual_outputs = tuple(
        (item.blind_code, item.blind_order_sha256, item.image_sha256)
        for item in presentation_manifest.outputs
    )
    expected_outputs = tuple(
        (item.blind_code, item.blind_order_sha256, item.output_sha256)
        for item in packet.outputs
    )
    if actual_outputs != expected_outputs:
        raise ValueError("C4 Stage 1 presentation output order differs from packet")
    return schema, packet, operator_policy, presentation_manifest


def _build_display_context(
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    operator_policy: C4HumanReviewOperatorPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    screen_contract: C4Stage1ScreenContract,
    display_policy: C4Stage1DisplayAttesterPolicy,
    *,
    ui_implementation_id: str,
    ui_revision: str,
    ui_session_id: str,
) -> C4Stage1DisplayContext:
    ui_implementation_id = _validate_opaque_id(
        ui_implementation_id, label="C4 Stage 1 UI implementation"
    )
    ui_revision = _validate_opaque_id(ui_revision, label="C4 Stage 1 UI revision")
    ui_session_id = _validate_opaque_id(ui_session_id, label="C4 Stage 1 UI session")
    _reject_visible_identity_labels(ui_implementation_id, ui_revision, ui_session_id)
    screen_contract = _validate_pre_output_display_binding(
        screen_contract, schema, operator_policy, display_policy
    )
    display_policy = _cold_validate(
        display_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    if (
        ui_implementation_id != display_policy.presenter_implementation_id
        or ui_revision != display_policy.presenter_revision
    ):
        raise ValueError("C4 Stage 1 runtime presenter differs from display policy")
    base = {
        "schema_version": "rei-c4-stage1-display-context-v1",
        "screen_contract_id": screen_contract.screen_contract_id,
        "screen_contract_sha256": screen_contract.content_hash(),
        "display_policy_id": display_policy.display_policy_id,
        "display_policy_sha256": display_policy.display_policy_sha256,
        "display_policy_artifact_sha256": display_policy.content_hash(),
        "ui_bundle_sha256": display_policy.ui_bundle_sha256,
        "content_security_policy_sha256": (
            display_policy.content_security_policy_sha256
        ),
        "display_attester_id": display_policy.display_attester_id,
        "review_schema_id": schema.schema_id,
        "review_schema_sha256": _canonical_sha256(schema),
        "rubric_version": schema.rubric_version,
        "operator_policy_id": operator_policy.policy_id,
        "operator_policy_sha256": operator_policy.operator_policy_sha256,
        "packet_id": packet.packet_id,
        "packet_sha256": packet.packet_sha256,
        "presentation_manifest_id": presentation_manifest.presentation_manifest_id,
        "presentation_manifest_sha256": presentation_manifest.presentation_manifest_sha256,
        "material_commitment_id": packet.material_commitment_id,
        "material_commitment_sha256": packet.material_commitment_sha256,
        "source_image_sha256": packet.source_image_sha256,
        "outputs": packet.outputs,
        "pair_order_policy": "ascending_sha256_of_blind_code",
        "ui_implementation_id": ui_implementation_id,
        "ui_revision": ui_revision,
        "ui_session_id": ui_session_id,
        "renderer_identity_structured_field_present": False,
        "model_identity_structured_field_present": False,
        "provider_or_model_labels_passed_to_display_port": False,
        "other_provider_output_references_present": False,
        "external_text_identifiers_trusted_caller_boundary": True,
        "absence_of_covert_secret_encoding_proven": False,
    }
    context_id, context_sha256 = _content_addresses("c4_stage1_display_context", base)
    return C4Stage1DisplayContext(
        context_id=context_id, context_sha256=context_sha256, **base
    )


def _display_bundle_records(
    context: C4Stage1DisplayContext,
    reads: tuple[_PinnedRead, _PinnedRead],
) -> tuple[tuple[str, str, str, str], tuple[str, str, str, str]]:
    return tuple(
        (
            reference.blind_code,
            reference.blind_order_sha256,
            reference.instruction_sha256,
            read.sha256,
        )
        for reference, read in zip(context.outputs, reads, strict=True)
    )  # type: ignore[return-value]


def _execute_c4_stage1_display_from_paths(
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    *,
    publication_binding: C4Stage1DisplayPublicationBinding,
    operator_policy: C4HumanReviewOperatorPolicy,
    screen_contract: C4Stage1ScreenContract,
    display_attester_policy: C4Stage1DisplayAttesterPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    source_png_path: str | Path,
    output_png_paths: tuple[str | Path, str | Path],
    display_port: C4Stage1TrustedDisplayPort,
    display_attestation_verifier: C4Stage1ExternalDisplayAttestationVerifierPort,
    ui_implementation_id: str,
    ui_revision: str,
    ui_session_id: str,
    clock: Callable[[], datetime] = _utc_now,
) -> C4Stage1DisplayExecutionReceipt:
    """Display exact pinned bytes and issue a path-free immutable receipt."""

    schema, packet, operator_policy, presentation_manifest = _validate_display_inputs(
        schema, packet, operator_policy, presentation_manifest
    )
    publication_binding = _cold_validate(
        publication_binding,
        C4Stage1DisplayPublicationBinding,
        label="C4 Stage 1 display publication binding",
    )
    if type(output_png_paths) is not tuple or len(output_png_paths) != 2:
        raise ValueError("C4 Stage 1 display requires exactly two output paths")
    display = getattr(display_port, "display", None)
    if not callable(display):
        raise TypeError("C4 Stage 1 requires a trusted display port")
    context = _build_display_context(
        schema,
        packet,
        operator_policy,
        presentation_manifest,
        screen_contract,
        display_attester_policy,
        ui_implementation_id=ui_implementation_id,
        ui_revision=ui_revision,
        ui_session_id=ui_session_id,
    )
    with ExitStack() as stack:
        source_handle = stack.enter_context(
            _PinnedPngHandle(
                source_png_path,
                expected_sha256=presentation_manifest.source.image_sha256,
                expected_size=presentation_manifest.source.byte_size,
            )
        )
        output_handles = tuple(
            stack.enter_context(
                _PinnedPngHandle(
                    path,
                    expected_sha256=presented.image_sha256,
                    expected_size=presented.byte_size,
                )
            )
            for path, presented in zip(
                output_png_paths, presentation_manifest.outputs, strict=True
            )
        )
        source_pre = source_handle.read_and_rehash()
        outputs_pre = tuple(handle.read_and_rehash() for handle in output_handles)
        visible_outputs = tuple(
            C4Stage1VisibleOutput(
                blind_code=reference.blind_code,
                blind_order_sha256=reference.blind_order_sha256,
                instruction=reference.instruction,
                instruction_sha256=reference.instruction_sha256,
                output_sha256=reference.output_sha256,
                png_bytes=read.value,
            )
            for reference, read in zip(packet.outputs, outputs_pre, strict=True)
        )
        display_started_at = _safe_clock(clock, label="display_started_at")
        display_error: BaseException | None = None
        display_result_value: object | None = None
        try:
            display_result_value = display(
                context=context,
                display_policy=display_attester_policy,
                source_png_bytes=source_pre.value,
                outputs=visible_outputs,
            )
        except BaseException as exc:  # cleanup and post-read also cover interrupts
            display_error = exc
        post_error: Exception | None = None
        try:
            source_post = source_handle.read_and_rehash()
            outputs_post = tuple(handle.read_and_rehash() for handle in output_handles)
        except Exception as exc:
            post_error = exc
            source_post = source_pre
            outputs_post = outputs_pre
        if display_error is not None:
            if isinstance(display_error, Exception):
                raise ValueError(
                    "C4 Stage 1 trusted display execution failed"
                ) from None
            raise display_error
        if post_error is not None:
            raise ValueError(
                "C4 Stage 1 display bytes changed during execution"
            ) from None
        if not isinstance(display_result_value, C4Stage1DisplayPortResult):
            raise ValueError("C4 Stage 1 trusted display returned an incomplete result")
        acknowledgement = _cold_validate(
            display_result_value.acknowledgement,
            C4Stage1DisplayPortAcknowledgement,
            label="C4 Stage 1 display acknowledgement",
        )
        display_attestation = _validate_display_attestation_binding(
            display_attester_policy,
            context,
            acknowledgement,
            display_result_value.attestation,
        )
        display_completed_at = _safe_clock(clock, label="display_completed_at")
        consumed_display_attestation = _verify_and_consume_display_attestation_once(
            display_attestation_verifier,
            display_attester_policy,
            context,
            acknowledgement,
            display_attestation,
        )
    pre_bundle = _exact_bytes_bundle_sha256(
        context=context,
        source_sha256=source_pre.sha256,
        output_records=_display_bundle_records(context, outputs_pre),
    )
    post_bundle = _exact_bytes_bundle_sha256(
        context=context,
        source_sha256=source_post.sha256,
        output_records=_display_bundle_records(context, outputs_post),
    )
    if (
        acknowledgement.context_id != context.context_id
        or acknowledgement.context_sha256 != context.context_sha256
        or acknowledgement.received_exact_bytes_bundle_sha256 != pre_bundle
    ):
        raise ValueError("C4 Stage 1 display acknowledgement differs from invocation")
    source = C4Stage1DisplayedPng(
        image_role="source",
        image_sha256=source_pre.sha256,
        byte_size=len(source_pre.value),
        pre_display_sha256=source_pre.sha256,
        post_display_sha256=source_post.sha256,
        same_open_file_handle_rehashed_before_and_after_display=True,
        exact_bytes_passed_by_value_to_display_port=True,
        local_path_stored_in_artifact=False,
    )
    outputs = tuple(
        C4Stage1DisplayedPng(
            image_role="output",
            blind_code=reference.blind_code,
            blind_order_sha256=reference.blind_order_sha256,
            image_sha256=pre.sha256,
            byte_size=len(pre.value),
            pre_display_sha256=pre.sha256,
            post_display_sha256=post.sha256,
            same_open_file_handle_rehashed_before_and_after_display=True,
            exact_bytes_passed_by_value_to_display_port=True,
            local_path_stored_in_artifact=False,
        )
        for reference, pre, post in zip(
            context.outputs, outputs_pre, outputs_post, strict=True
        )
    )
    base = {
        "schema_version": "rei-c4-stage1-display-execution-receipt-v1",
        "display_policy": C4_STAGE1_DISPLAY_POLICY,
        "publication_binding": publication_binding,
        "context": context,
        "display_attester_policy": display_attester_policy,
        "acknowledgement": acknowledgement,
        "display_attestation": display_attestation,
        "consumed_display_attestation": consumed_display_attestation,
        "source": source,
        "outputs": outputs,
        "display_started_at": display_started_at,
        "display_completed_at": display_completed_at,
        "pre_display_exact_bytes_bundle_sha256": pre_bundle,
        "port_received_exact_bytes_bundle_sha256": (
            acknowledgement.received_exact_bytes_bundle_sha256
        ),
        "post_display_exact_bytes_bundle_sha256": post_bundle,
        "trusted_display_port_invoked": True,
        "display_execution_completed": True,
        "partial_display": False,
        "exact_bytes_passed_by_value": True,
        "pre_and_post_display_same_handle_rehash": True,
        "cold_path_reverification_required_before_claim_trust": True,
        "cold_artifact_alone_proves_current_path_bytes": False,
        "external_one_time_display_receipt_consumption_required": True,
        "live_external_display_receipt_reverification_required": True,
        "separately_keyed_display_attestation_required": True,
        "live_external_display_attestation_reverification_required": True,
        "source_or_output_local_paths_stored": False,
        "provider_or_model_labels_present": False,
        "external_text_identifiers_trusted_caller_boundary": True,
        "absence_of_covert_secret_encoding_proven": False,
        "display_receipt_proves_human_attention": False,
        "display_receipt_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    display_receipt_id, display_receipt_sha256 = _content_addresses(
        "c4_stage1_display_receipt", base
    )
    return C4Stage1DisplayExecutionReceipt(
        display_receipt_id=display_receipt_id,
        display_receipt_sha256=display_receipt_sha256,
        **base,
    )


def execute_c4_stage1_display(
    artifact_store: FileArtifactStore,
    prepared_anchor_storage: StoredArtifact,
    member_publication_receipt_storage: StoredArtifact,
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
    display_attester_policy: C4Stage1DisplayAttesterPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    display_port: C4Stage1TrustedDisplayPort,
    display_attestation_verifier: C4Stage1ExternalDisplayAttestationVerifierPort,
    ui_implementation_id: str,
    ui_revision: str,
    ui_session_id: str,
    clock: Callable[[], datetime] = _utc_now,
) -> C4Stage1DisplayExecutionReceipt:
    """Display only a cold-verified, atomically committed Stage 1 family."""

    # Local imports avoid a module cycle: preparation freezes this module's
    # display policy before any output exists.
    from .c4_stage1_attempt import cold_verify_c4_stage1_prepared_attempt
    from .c4_stage1_run import cold_verify_c4_stage1_member_publication

    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("C4 Stage 1 committed display requires FileArtifactStore")
    if not isinstance(prepared_anchor_storage, StoredArtifact) or not isinstance(
        member_publication_receipt_storage, StoredArtifact
    ):
        raise TypeError("C4 Stage 1 committed display requires stored descriptors")
    prepared_storage = StoredArtifact.model_validate(
        prepared_anchor_storage.model_dump(mode="python", round_trip=True)
    )
    publication_storage = StoredArtifact.model_validate(
        member_publication_receipt_storage.model_dump(mode="python", round_trip=True)
    )
    schema, packet, operator_policy, presentation_manifest = _validate_display_inputs(
        schema, packet, operator_policy, presentation_manifest
    )
    display_attester_policy = _cold_validate(
        display_attester_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    cold_store = FileArtifactStore(artifact_store.root, create=False)
    prepared_outcome = cold_verify_c4_stage1_prepared_attempt(
        cold_store,
        prepared_storage,
        require_exact_pre_spawn_inventory=False,
    )
    if prepared_outcome.prepared_anchor_storage != prepared_storage:
        raise ValueError("C4 Stage 1 committed display prepared anchor changed")
    prepared = prepared_outcome.prepared_attempt
    publication = cold_verify_c4_stage1_member_publication(
        cold_store,
        publication_storage,
        prepared,
    )
    policies = tuple(
        policy
        for policy in prepared.review_operator_policies
        if policy.candidate_slot_id == publication.provider_slot_id
    )
    if (
        len(policies) != 1
        or schema != prepared.review_schema
        or operator_policy != policies[0]
        or display_attester_policy != prepared.display_policy
        or packet.source_image_sha256
        != prepared.screen_contract.source.source_png_sha256
        or presentation_manifest.source.image_sha256
        != prepared.screen_contract.source.source_png_sha256
        or publication.run_id != prepared.run_id
        or not publication.publication_committed
        or not publication.both_options_technical_passed
    ):
        raise ValueError(
            "C4 Stage 1 review material differs from the committed family policy"
        )
    candidates = {item.option_id: item for item in publication.candidate_receipts}
    if set(candidates) != {"enter_circle", "remain_edge"} or any(
        reference.option_id not in candidates
        or reference.output_sha256 != candidates[reference.option_id].staged_png_sha256
        for reference in packet.outputs
    ):
        raise ValueError(
            "C4 Stage 1 blind packet differs from committed family outputs"
        )
    source_path = prepared.screen_contract.fixture.source_image.path
    source_descriptors = tuple(
        item
        for item in prepared.artifact_inventory_before_anchor
        if item.relative_path == source_path
    )
    if len(source_descriptors) != 1:
        raise ValueError("C4 Stage 1 prepared source descriptor is not unique")
    source_descriptor = source_descriptors[0]
    if (
        source_descriptor.content_sha256 != packet.source_image_sha256
        or source_descriptor.size_bytes != presentation_manifest.source.byte_size
    ):
        raise ValueError("C4 Stage 1 prepared source differs from blind presentation")
    output_descriptors = tuple(
        candidates[reference.option_id].staged_output_storage
        for reference in packet.outputs
    )
    if any(
        descriptor.content_sha256 != presented.image_sha256
        or descriptor.size_bytes != presented.byte_size
        for descriptor, presented in zip(
            output_descriptors,
            presentation_manifest.outputs,
            strict=True,
        )
    ):
        raise ValueError(
            "C4 Stage 1 presentation differs from committed output descriptors"
        )
    publication_binding = C4Stage1DisplayPublicationBinding.create(
        run_id=prepared.run_id,
        prepared_attempt_id=prepared.prepared_attempt_id,
        prepared_attempt_sha256=prepared.prepared_attempt_sha256,
        prepared_anchor_storage=prepared_storage,
        member_publication_receipt_id=(publication.member_publication_receipt_id),
        member_publication_receipt_sha256=(
            publication.member_publication_receipt_sha256
        ),
        member_publication_receipt_storage=publication_storage,
        editor_role=publication.editor_role,
        provider_slot_id=publication.provider_slot_id,
        source_storage=source_descriptor,
        candidates=tuple(
            C4Stage1DisplayCandidatePublicationBinding(
                option_id=item.option_id,
                candidate_receipt_id=item.candidate_receipt_id,
                candidate_receipt_sha256=item.candidate_receipt_sha256,
                prepared_worker_id=item.prepared_worker_id,
                prepared_worker_sha256=item.prepared_worker_sha256,
                worker_request_id=item.worker_request_id,
                worker_request_sha256=item.worker_request_sha256,
                staged_output_storage=item.staged_output_storage,
            )
            for item in publication.candidate_receipts
        ),  # type: ignore[arg-type]
    )
    return _execute_c4_stage1_display_from_paths(
        schema,
        packet,
        publication_binding=publication_binding,
        operator_policy=operator_policy,
        screen_contract=prepared.screen_contract,
        display_attester_policy=display_attester_policy,
        presentation_manifest=presentation_manifest,
        source_png_path=cold_store.artifact_path(
            prepared.run_id,
            source_descriptor.relative_path,
        ),
        output_png_paths=tuple(
            cold_store.artifact_path(prepared.run_id, item.relative_path)
            for item in output_descriptors
        ),  # type: ignore[arg-type]
        display_port=display_port,
        display_attestation_verifier=display_attestation_verifier,
        ui_implementation_id=ui_implementation_id,
        ui_revision=ui_revision,
        ui_session_id=ui_session_id,
        clock=clock,
    )


def _cold_verify_display_publication_binding(
    artifact_store: FileArtifactStore,
    binding: C4Stage1DisplayPublicationBinding,
    *,
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    operator_policy: C4HumanReviewOperatorPolicy,
    screen_contract: C4Stage1ScreenContract,
    display_attester_policy: C4Stage1DisplayAttesterPolicy,
    presentation_manifest: C4BlindPresentationManifest,
) -> tuple[Path, tuple[Path, Path]]:
    """Cold-replay the exact prepared anchor and atomic member marker."""

    from .c4_stage1_attempt import cold_verify_c4_stage1_prepared_attempt
    from .c4_stage1_run import cold_verify_c4_stage1_member_publication

    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("C4 Stage 1 display replay requires FileArtifactStore")
    binding = _cold_validate(
        binding,
        C4Stage1DisplayPublicationBinding,
        label="C4 Stage 1 display publication binding",
    )
    cold_store = FileArtifactStore(artifact_store.root, create=False)
    prepared_outcome = cold_verify_c4_stage1_prepared_attempt(
        cold_store,
        binding.prepared_anchor_storage,
        require_exact_pre_spawn_inventory=False,
    )
    prepared = prepared_outcome.prepared_attempt
    publication = cold_verify_c4_stage1_member_publication(
        cold_store,
        binding.member_publication_receipt_storage,
        prepared,
    )
    policies = tuple(
        item
        for item in prepared.review_operator_policies
        if item.candidate_slot_id == publication.provider_slot_id
    )
    source_matches = tuple(
        item
        for item in prepared.artifact_inventory_before_anchor
        if item.relative_path == prepared.screen_contract.fixture.source_image.path
    )
    if len(source_matches) != 1 or len(policies) != 1:
        raise ValueError("C4 Stage 1 display publication lineage is incomplete")
    source_storage = source_matches[0]
    expected = C4Stage1DisplayPublicationBinding.create(
        run_id=prepared.run_id,
        prepared_attempt_id=prepared.prepared_attempt_id,
        prepared_attempt_sha256=prepared.prepared_attempt_sha256,
        prepared_anchor_storage=prepared_outcome.prepared_anchor_storage,
        member_publication_receipt_id=(publication.member_publication_receipt_id),
        member_publication_receipt_sha256=(
            publication.member_publication_receipt_sha256
        ),
        member_publication_receipt_storage=(binding.member_publication_receipt_storage),
        editor_role=publication.editor_role,
        provider_slot_id=publication.provider_slot_id,
        source_storage=source_storage,
        candidates=tuple(
            C4Stage1DisplayCandidatePublicationBinding(
                option_id=item.option_id,
                candidate_receipt_id=item.candidate_receipt_id,
                candidate_receipt_sha256=item.candidate_receipt_sha256,
                prepared_worker_id=item.prepared_worker_id,
                prepared_worker_sha256=item.prepared_worker_sha256,
                worker_request_id=item.worker_request_id,
                worker_request_sha256=item.worker_request_sha256,
                staged_output_storage=item.staged_output_storage,
            )
            for item in publication.candidate_receipts
        ),  # type: ignore[arg-type]
    )
    by_option = {item.option_id: item for item in publication.candidate_receipts}
    if (
        binding != expected
        or prepared_outcome.prepared_anchor_storage != binding.prepared_anchor_storage
        or prepared.screen_contract != screen_contract
        or prepared.review_schema != schema
        or policies[0] != operator_policy
        or prepared.display_policy != display_attester_policy
        or packet.source_image_sha256 != source_storage.content_sha256
        or presentation_manifest.source.image_sha256 != source_storage.content_sha256
        or any(
            reference.option_id not in by_option
            or reference.output_sha256
            != by_option[reference.option_id].staged_png_sha256
            for reference in packet.outputs
        )
    ):
        raise ValueError("C4 Stage 1 display receipt cites another publication")
    output_storage = tuple(
        by_option[reference.option_id].staged_output_storage
        for reference in packet.outputs
    )
    return (
        cold_store.artifact_path(prepared.run_id, source_storage.relative_path),
        tuple(
            cold_store.artifact_path(prepared.run_id, item.relative_path)
            for item in output_storage
        ),  # type: ignore[return-value]
    )


def cold_verify_c4_stage1_display_execution_receipt(
    receipt: C4Stage1DisplayExecutionReceipt,
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    *,
    artifact_store: FileArtifactStore,
    operator_policy: C4HumanReviewOperatorPolicy,
    screen_contract: C4Stage1ScreenContract,
    display_attester_policy: C4Stage1DisplayAttesterPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    source_png_path: str | Path | None = None,
    output_png_paths: tuple[str | Path, str | Path] | None = None,
) -> C4Stage1DisplayExecutionReceipt:
    """Cold-validate the receipt, marker and store-derived exact PNG paths."""

    receipt = _cold_validate(
        receipt, C4Stage1DisplayExecutionReceipt, label="C4 Stage 1 display receipt"
    )
    schema, packet, operator_policy, presentation_manifest = _validate_display_inputs(
        schema, packet, operator_policy, presentation_manifest
    )
    # Legacy caller paths are accepted only for API compatibility and never
    # used as authority; the marker-bound store descriptors choose the paths.
    del source_png_path, output_png_paths
    source_png_path, output_png_paths = _cold_verify_display_publication_binding(
        artifact_store,
        receipt.publication_binding,
        schema=schema,
        packet=packet,
        operator_policy=operator_policy,
        screen_contract=screen_contract,
        display_attester_policy=display_attester_policy,
        presentation_manifest=presentation_manifest,
    )
    expected_context = _build_display_context(
        schema,
        packet,
        operator_policy,
        presentation_manifest,
        screen_contract,
        display_attester_policy,
        ui_implementation_id=receipt.context.ui_implementation_id,
        ui_revision=receipt.context.ui_revision,
        ui_session_id=receipt.context.ui_session_id,
    )
    if (
        receipt.context != expected_context
        or receipt.display_attester_policy != display_attester_policy
    ):
        raise ValueError("C4 Stage 1 display receipt differs from cold review inputs")
    with ExitStack() as stack:
        source_handle = stack.enter_context(
            _PinnedPngHandle(
                source_png_path,
                expected_sha256=receipt.source.image_sha256,
                expected_size=receipt.source.byte_size,
            )
        )
        output_handles = tuple(
            stack.enter_context(
                _PinnedPngHandle(
                    path,
                    expected_sha256=item.image_sha256,
                    expected_size=item.byte_size,
                )
            )
            for path, item in zip(output_png_paths, receipt.outputs, strict=True)
        )
        source_first = source_handle.read_and_rehash()
        outputs_first = tuple(handle.read_and_rehash() for handle in output_handles)
        source_second = source_handle.read_and_rehash()
        outputs_second = tuple(handle.read_and_rehash() for handle in output_handles)
    if source_first != source_second or outputs_first != outputs_second:
        raise ValueError("C4 Stage 1 cold display bytes changed during verification")
    bundle = _exact_bytes_bundle_sha256(
        context=receipt.context,
        source_sha256=source_first.sha256,
        output_records=_display_bundle_records(receipt.context, outputs_first),
    )
    if bundle != receipt.pre_display_exact_bytes_bundle_sha256:
        raise ValueError("C4 Stage 1 cold display bundle differs from receipt")
    return receipt


def _reverify_display_receipt_attestation(
    verifier: C4Stage1ExternalDisplayAttestationVerifierPort,
    receipt: C4Stage1DisplayExecutionReceipt,
) -> C4Stage1ConsumedDisplayAttestation:
    return _reverify_consumed_display_attestation(
        verifier,
        receipt.display_attester_policy,
        receipt.context,
        receipt.acknowledgement,
        receipt.display_attestation,
        receipt.consumed_display_attestation,
    )


class C4Stage1ConsumedDisplayReceipt(FrozenArtifactModel):
    schema_version: Literal["rei-c4-stage1-consumed-display-receipt-v1"] = (
        "rei-c4-stage1-consumed-display-receipt-v1"
    )
    consumed_display_receipt_id: NonEmptyId
    consumed_display_receipt_sha256: HashDigest
    display_receipt_id: NonEmptyId
    display_receipt_sha256: HashDigest
    ui_session_id: Stage1OpaqueId
    external_transaction_id: Stage1OpaqueId
    external_transaction_timestamp: UtcTimestamp
    external_ledger_claimed_atomic_consume_once: Literal[True] = True
    ledger_state_external_to_model_runner: Literal[True] = True
    cold_validation_proves_live_ledger_state: Literal[False] = False
    live_external_ledger_reverification_required: Literal[True] = True
    receipt_proves_human_attention: Literal[False] = False
    receipt_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_consumed_display_receipt(self) -> Self:
        _normalized_utc(
            self.external_transaction_timestamp,
            label="display receipt transaction timestamp",
        )
        if (
            self.external_ledger_claimed_atomic_consume_once is not True
            or self.ledger_state_external_to_model_runner is not True
            or self.cold_validation_proves_live_ledger_state is not False
            or self.live_external_ledger_reverification_required is not True
            or self.receipt_proves_human_attention is not False
            or self.receipt_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
        ):
            raise ValueError("C4 Stage 1 display ledger receipt weakens its boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "consumed_display_receipt_id",
                "consumed_display_receipt_sha256",
            },
        )
        expected_id, expected_sha256 = _content_addresses("c4_s1_display_use", payload)
        if (
            self.consumed_display_receipt_id != expected_id
            or self.consumed_display_receipt_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 consumed display receipt address is invalid")
        _require_bounded_canonical(self, label="C4 Stage 1 consumed display receipt")
        return self


def record_c4_stage1_consumed_display_receipt(
    display_receipt: C4Stage1DisplayExecutionReceipt,
    *,
    external_transaction_id: str,
    external_transaction_timestamp: datetime,
) -> C4Stage1ConsumedDisplayReceipt:
    display_receipt = _cold_validate(
        display_receipt,
        C4Stage1DisplayExecutionReceipt,
        label="C4 Stage 1 display receipt",
    )
    external_transaction_id = _validate_opaque_id(
        external_transaction_id, label="C4 Stage 1 display transaction"
    )
    transaction_timestamp = _normalized_utc(
        external_transaction_timestamp, label="display receipt transaction timestamp"
    )
    if transaction_timestamp < display_receipt.display_completed_at:
        raise ValueError(
            "C4 Stage 1 display receipt was consumed before display completion"
        )
    base = {
        "schema_version": "rei-c4-stage1-consumed-display-receipt-v1",
        "display_receipt_id": display_receipt.display_receipt_id,
        "display_receipt_sha256": display_receipt.display_receipt_sha256,
        "ui_session_id": display_receipt.context.ui_session_id,
        "external_transaction_id": external_transaction_id,
        "external_transaction_timestamp": transaction_timestamp,
        "external_ledger_claimed_atomic_consume_once": True,
        "ledger_state_external_to_model_runner": True,
        "cold_validation_proves_live_ledger_state": False,
        "live_external_ledger_reverification_required": True,
        "receipt_proves_human_attention": False,
        "receipt_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
    }
    receipt_id, receipt_sha256 = _content_addresses("c4_s1_display_use", base)
    return C4Stage1ConsumedDisplayReceipt(
        consumed_display_receipt_id=receipt_id,
        consumed_display_receipt_sha256=receipt_sha256,
        **base,
    )


class C4Stage1ExternalDisplayReceiptLedgerPort(Protocol):
    def consume_once(
        self, *, display_receipt: C4Stage1DisplayExecutionReceipt
    ) -> C4Stage1ConsumedDisplayReceipt:
        """Atomically reject a reused display receipt, then return evidence."""
        ...

    def verify_consumed_use(
        self,
        *,
        display_receipt: C4Stage1DisplayExecutionReceipt,
        consumed_receipt: C4Stage1ConsumedDisplayReceipt,
    ) -> bool:
        """Verify the exact receipt against live external one-time state."""
        ...


def _validate_consumed_display_binding(
    display_receipt: C4Stage1DisplayExecutionReceipt,
    consumed_receipt: C4Stage1ConsumedDisplayReceipt,
) -> C4Stage1ConsumedDisplayReceipt:
    consumed_receipt = _cold_validate(
        consumed_receipt,
        C4Stage1ConsumedDisplayReceipt,
        label="C4 Stage 1 consumed display receipt",
    )
    if (
        consumed_receipt.display_receipt_id != display_receipt.display_receipt_id
        or consumed_receipt.display_receipt_sha256
        != display_receipt.display_receipt_sha256
        or consumed_receipt.ui_session_id != display_receipt.context.ui_session_id
    ):
        raise ValueError("C4 Stage 1 display ledger receipt differs from display")
    return consumed_receipt


def consume_c4_stage1_display_receipt_once(
    ledger: C4Stage1ExternalDisplayReceiptLedgerPort,
    display_receipt: C4Stage1DisplayExecutionReceipt,
) -> C4Stage1ConsumedDisplayReceipt:
    display_receipt = _cold_validate(
        display_receipt,
        C4Stage1DisplayExecutionReceipt,
        label="C4 Stage 1 display receipt",
    )
    consume_once = getattr(ledger, "consume_once", None)
    if not callable(consume_once):
        raise TypeError("C4 Stage 1 display receipt requires an external atomic ledger")
    consumed = consume_once(display_receipt=display_receipt)
    return _validate_consumed_display_binding(display_receipt, consumed)


def _reverify_consumed_display_receipt(
    ledger: C4Stage1ExternalDisplayReceiptLedgerPort,
    display_receipt: C4Stage1DisplayExecutionReceipt,
    consumed_receipt: C4Stage1ConsumedDisplayReceipt,
) -> C4Stage1ConsumedDisplayReceipt:
    consumed_receipt = _validate_consumed_display_binding(
        display_receipt, consumed_receipt
    )
    verify = getattr(ledger, "verify_consumed_use", None)
    if not callable(verify):
        raise TypeError("C4 Stage 1 replay requires a live display-receipt verifier")
    verified = verify(
        display_receipt=display_receipt,
        consumed_receipt=consumed_receipt,
    )
    if verified is not True:
        raise ValueError("C4 Stage 1 display receipt is not live in external state")
    return consumed_receipt


def _validate_judgments(
    packet: C4BlindReviewPacket,
    output_judgments: tuple[C4OutputHumanJudgment, C4OutputHumanJudgment],
    pair_judgment: C4PairHumanJudgment,
) -> tuple[tuple[C4OutputHumanJudgment, C4OutputHumanJudgment], C4PairHumanJudgment]:
    if type(output_judgments) is not tuple or len(output_judgments) != 2:
        raise ValueError("C4 Stage 1 claim requires exactly two judgments")
    validated = tuple(
        _cold_validate(
            judgment,
            C4OutputHumanJudgment,
            label="C4 Stage 1 output judgment",
        )
        for judgment in output_judgments
    )
    pair_judgment = _cold_validate(
        pair_judgment, C4PairHumanJudgment, label="C4 Stage 1 pair judgment"
    )
    for judgment, reference in zip(validated, packet.outputs, strict=True):
        if (
            judgment.blind_code != reference.blind_code
            or judgment.source_image_sha256 != packet.source_image_sha256
            or judgment.instruction_sha256 != reference.instruction_sha256
            or judgment.output_sha256 != reference.output_sha256
        ):
            raise ValueError("C4 Stage 1 judgment differs from blind binding")
    return validated, pair_judgment  # type: ignore[return-value]


class C4Stage1HumanReviewUnsignedClaim(FrozenArtifactModel):
    """Canonical Stage 1 claim whose HMAC includes the display receipt."""

    schema_version: Literal["rei-c4-stage1-human-review-unsigned-claim-v2"] = (
        "rei-c4-stage1-human-review-unsigned-claim-v2"
    )
    claim_id: NonEmptyId
    claim_sha256: HashDigest
    receipt_domain: Literal["rei-c4-stage1-operator-manual-entry-receipt-v1"]
    operator_attestation_claim: Literal[
        "trusted_external_operator_attested_manual_entry"
    ]
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    review_schema_id: NonEmptyId
    packet_id: NonEmptyId
    packet_sha256: HashDigest
    presentation_manifest_id: NonEmptyId
    presentation_manifest_sha256: HashDigest
    screen_contract_id: NonEmptyId
    screen_contract_sha256: HashDigest
    display_policy_id: NonEmptyId
    display_policy_sha256: HashDigest
    display_policy_artifact_sha256: HashDigest
    display_attestation_id: NonEmptyId
    display_attestation_sha256: HashDigest
    consumed_display_attestation_id: NonEmptyId
    consumed_display_attestation_sha256: HashDigest
    display_receipt_id: NonEmptyId
    display_receipt_sha256: HashDigest
    consumed_display_receipt_id: NonEmptyId
    consumed_display_receipt_sha256: HashDigest
    reviewer_pseudonym: NonEmptyId
    review_timestamp: UtcTimestamp
    output_judgments: tuple[C4OutputHumanJudgment, ...] = Field(
        min_length=2, max_length=2
    )
    pair_judgment: C4PairHumanJudgment
    submission_receipt_id: NonEmptyId
    submission_receipt_sha256: HashDigest
    operator_signing_lease_id: NonEmptyId
    operator_signing_lease_sha256: HashDigest
    authenticated_presenter_submission_required: Literal[True] = True
    operator_signing_lease_preissued: Literal[True] = True
    separately_keyed_display_attestation_in_operator_hmac: Literal[True] = True
    display_receipt_cold_reverification_required_before_seal: Literal[True] = True
    live_external_display_receipt_reverification_required: Literal[True] = True
    live_external_operator_signing_lease_reverification_required: Literal[True] = True
    direct_operator_secret_material_stored_in_artifact: Literal[False] = False
    external_text_identifiers_trusted_caller_boundary: Literal[True] = True
    absence_of_covert_secret_encoding_proven: Literal[False] = False
    attestation_proves_human_attention: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        _normalized_utc(self.review_timestamp, label="C4 Stage 1 review timestamp")
        if len(self.output_judgments) != 2:
            raise ValueError("C4 Stage 1 claim requires two judgments")
        for judgment in self.output_judgments:
            C4OutputHumanJudgment.model_validate(
                judgment.model_dump(mode="python", round_trip=True)
            )
        C4PairHumanJudgment.model_validate(
            self.pair_judgment.model_dump(mode="python", round_trip=True)
        )
        if (
            self.receipt_domain != C4_STAGE1_OPERATOR_RECEIPT_DOMAIN
            or self.operator_attestation_claim != C4_OPERATOR_ATTESTATION_CLAIM
            or self.authenticated_presenter_submission_required is not True
            or self.operator_signing_lease_preissued is not True
            or self.separately_keyed_display_attestation_in_operator_hmac is not True
            or self.display_receipt_cold_reverification_required_before_seal is not True
            or self.live_external_display_receipt_reverification_required is not True
            or self.live_external_operator_signing_lease_reverification_required
            is not True
            or self.direct_operator_secret_material_stored_in_artifact is not False
            or self.external_text_identifiers_trusted_caller_boundary is not True
            or self.absence_of_covert_secret_encoding_proven is not False
            or self.attestation_proves_human_attention is not False
            or self.attestation_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 operator claim weakens authority boundaries")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"claim_id", "claim_sha256"}
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_review_claim", payload
        )
        if self.claim_id != expected_id or self.claim_sha256 != expected_sha256:
            raise ValueError("C4 Stage 1 operator claim address differs from content")
        _require_bounded_canonical(self, label="C4 Stage 1 operator claim")
        return self


def build_c4_stage1_operator_unsigned_claim(
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    *,
    operator_policy: C4HumanReviewOperatorPolicy,
    screen_contract: C4Stage1ScreenContract,
    display_attester_policy: C4Stage1DisplayAttesterPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    display_receipt: C4Stage1DisplayExecutionReceipt,
    consumed_display_receipt: C4Stage1ConsumedDisplayReceipt,
    reviewer_pseudonym: str,
    review_timestamp: datetime,
    output_judgments: tuple[C4OutputHumanJudgment, C4OutputHumanJudgment],
    pair_judgment: C4PairHumanJudgment,
    submission_receipt_id: str,
    submission_receipt_sha256: str,
    operator_signing_lease_id: str,
    operator_signing_lease_sha256: str,
) -> C4Stage1HumanReviewUnsignedClaim:
    schema, packet, operator_policy, presentation_manifest = _validate_display_inputs(
        schema, packet, operator_policy, presentation_manifest
    )
    screen_contract = _validate_pre_output_display_binding(
        screen_contract, schema, operator_policy, display_attester_policy
    )
    display_attester_policy = _cold_validate(
        display_attester_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    display_receipt = _cold_validate(
        display_receipt,
        C4Stage1DisplayExecutionReceipt,
        label="C4 Stage 1 display receipt",
    )
    consumed_display_receipt = _validate_consumed_display_binding(
        display_receipt, consumed_display_receipt
    )
    if (
        display_receipt.context.packet_id != packet.packet_id
        or display_receipt.context.packet_sha256 != packet.packet_sha256
        or display_receipt.context.presentation_manifest_id
        != presentation_manifest.presentation_manifest_id
        or display_receipt.context.presentation_manifest_sha256
        != presentation_manifest.presentation_manifest_sha256
        or display_receipt.context.review_schema_id != schema.schema_id
        or display_receipt.context.operator_policy_id != operator_policy.policy_id
        or display_receipt.context.screen_contract_id
        != screen_contract.screen_contract_id
        or display_receipt.context.screen_contract_sha256
        != screen_contract.content_hash()
        or display_receipt.display_attester_policy != display_attester_policy
    ):
        raise ValueError("C4 Stage 1 display receipt differs from review material")
    output_judgments, pair_judgment = _validate_judgments(
        packet, output_judgments, pair_judgment
    )
    reviewer_pseudonym = _validate_opaque_id(
        reviewer_pseudonym, label="C4 Stage 1 reviewer pseudonym"
    )
    review_timestamp = _normalized_utc(review_timestamp, label="review timestamp")
    if review_timestamp < display_receipt.display_completed_at:
        raise ValueError("C4 Stage 1 review predates completed display execution")
    base = {
        "schema_version": "rei-c4-stage1-human-review-unsigned-claim-v2",
        "receipt_domain": C4_STAGE1_OPERATOR_RECEIPT_DOMAIN,
        "operator_attestation_claim": C4_OPERATOR_ATTESTATION_CLAIM,
        "operator_policy_id": operator_policy.policy_id,
        "operator_policy_sha256": operator_policy.operator_policy_sha256,
        "review_schema_id": schema.schema_id,
        "packet_id": packet.packet_id,
        "packet_sha256": packet.packet_sha256,
        "presentation_manifest_id": presentation_manifest.presentation_manifest_id,
        "presentation_manifest_sha256": presentation_manifest.presentation_manifest_sha256,
        "screen_contract_id": screen_contract.screen_contract_id,
        "screen_contract_sha256": screen_contract.content_hash(),
        "display_policy_id": display_attester_policy.display_policy_id,
        "display_policy_sha256": display_attester_policy.display_policy_sha256,
        "display_policy_artifact_sha256": display_attester_policy.content_hash(),
        "display_attestation_id": (
            display_receipt.display_attestation.display_attestation_id
        ),
        "display_attestation_sha256": (
            display_receipt.display_attestation.display_attestation_sha256
        ),
        "consumed_display_attestation_id": (
            display_receipt.consumed_display_attestation.consumed_display_attestation_id
        ),
        "consumed_display_attestation_sha256": (
            display_receipt.consumed_display_attestation.consumed_display_attestation_sha256
        ),
        "display_receipt_id": display_receipt.display_receipt_id,
        "display_receipt_sha256": display_receipt.display_receipt_sha256,
        "consumed_display_receipt_id": (
            consumed_display_receipt.consumed_display_receipt_id
        ),
        "consumed_display_receipt_sha256": (
            consumed_display_receipt.consumed_display_receipt_sha256
        ),
        "reviewer_pseudonym": reviewer_pseudonym,
        "review_timestamp": review_timestamp,
        "output_judgments": output_judgments,
        "pair_judgment": pair_judgment,
        "submission_receipt_id": submission_receipt_id,
        "submission_receipt_sha256": submission_receipt_sha256,
        "operator_signing_lease_id": operator_signing_lease_id,
        "operator_signing_lease_sha256": operator_signing_lease_sha256,
        "authenticated_presenter_submission_required": True,
        "operator_signing_lease_preissued": True,
        "separately_keyed_display_attestation_in_operator_hmac": True,
        "display_receipt_cold_reverification_required_before_seal": True,
        "live_external_display_receipt_reverification_required": True,
        "live_external_operator_signing_lease_reverification_required": True,
        "direct_operator_secret_material_stored_in_artifact": False,
        "external_text_identifiers_trusted_caller_boundary": True,
        "absence_of_covert_secret_encoding_proven": False,
        "attestation_proves_human_attention": False,
        "attestation_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    claim_id, claim_sha256 = _content_addresses("c4_stage1_review_claim", base)
    return C4Stage1HumanReviewUnsignedClaim(
        claim_id=claim_id, claim_sha256=claim_sha256, **base
    )


def c4_stage1_operator_attestation_message(
    claim: C4Stage1HumanReviewUnsignedClaim,
) -> bytes:
    claim = _cold_validate(
        claim,
        C4Stage1HumanReviewUnsignedClaim,
        label="C4 Stage 1 operator claim",
    )
    return (
        C4_STAGE1_OPERATOR_RECEIPT_DOMAIN.encode("ascii")
        + b"\x00"
        + claim.canonical_json_bytes()
    )


class C4Stage1HumanReviewOperatorAttestation(FrozenArtifactModel):
    schema_version: Literal["rei-c4-stage1-human-review-attestation-v2"] = (
        "rei-c4-stage1-human-review-attestation-v2"
    )
    attestation_id: NonEmptyId
    attestation_sha256: HashDigest
    claim: C4Stage1HumanReviewUnsignedClaim
    hmac_algorithm: Literal["HMAC-SHA256"] = "HMAC-SHA256"
    hmac_sha256: HashDigest
    operator_attestation_claim: Literal[
        "trusted_external_operator_attested_manual_entry"
    ]
    direct_operator_secret_material_stored_in_artifact: Literal[False] = False
    external_text_identifiers_trusted_caller_boundary: Literal[True] = True
    absence_of_covert_secret_encoding_proven: Literal[False] = False
    secret_reverification_required_before_trust: Literal[True] = True
    attestation_proves_human_attention: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_attestation(self) -> Self:
        C4Stage1HumanReviewUnsignedClaim.model_validate(
            self.claim.model_dump(mode="python", round_trip=True)
        )
        if (
            self.hmac_algorithm != "HMAC-SHA256"
            or self.operator_attestation_claim != C4_OPERATOR_ATTESTATION_CLAIM
            or self.direct_operator_secret_material_stored_in_artifact is not False
            or self.external_text_identifiers_trusted_caller_boundary is not True
            or self.absence_of_covert_secret_encoding_proven is not False
            or self.secret_reverification_required_before_trust is not True
            or self.attestation_proves_human_attention is not False
            or self.attestation_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
        ):
            raise ValueError("C4 Stage 1 attestation weakens authority boundaries")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"attestation_id", "attestation_sha256"},
        )
        expected_id, expected_sha256 = _content_addresses(
            "c4_stage1_operator_attestation", payload
        )
        if (
            self.attestation_id != expected_id
            or self.attestation_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 attestation address differs from content")
        _require_bounded_canonical(self, label="C4 Stage 1 operator attestation")
        return self


def build_c4_stage1_operator_attestation(
    claim: C4Stage1HumanReviewUnsignedClaim,
    *,
    external_hmac_sha256: str,
) -> C4Stage1HumanReviewOperatorAttestation:
    claim = _cold_validate(
        claim,
        C4Stage1HumanReviewUnsignedClaim,
        label="C4 Stage 1 operator claim",
    )
    base = {
        "schema_version": "rei-c4-stage1-human-review-attestation-v2",
        "claim": claim,
        "hmac_algorithm": "HMAC-SHA256",
        "hmac_sha256": external_hmac_sha256,
        "operator_attestation_claim": C4_OPERATOR_ATTESTATION_CLAIM,
        "direct_operator_secret_material_stored_in_artifact": False,
        "external_text_identifiers_trusted_caller_boundary": True,
        "absence_of_covert_secret_encoding_proven": False,
        "secret_reverification_required_before_trust": True,
        "attestation_proves_human_attention": False,
        "attestation_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
    }
    attestation_id, attestation_sha256 = _content_addresses(
        "c4_stage1_operator_attestation", base
    )
    return C4Stage1HumanReviewOperatorAttestation(
        attestation_id=attestation_id,
        attestation_sha256=attestation_sha256,
        **base,
    )


class C4Stage1ExternalOperatorAttestationVerifierPort(Protocol):
    """Separate keyed operator verifier; callers never receive its key."""

    def verify_attestation(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> bool: ...


def verify_c4_stage1_operator_attestation(
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4Stage1HumanReviewOperatorAttestation,
    *,
    operator_secret: bytes | None = None,
    operator_attestation_verifier: (
        C4Stage1ExternalOperatorAttestationVerifierPort | None
    ) = None,
) -> C4Stage1HumanReviewOperatorAttestation:
    operator_policy = _cold_validate(
        operator_policy, C4HumanReviewOperatorPolicy, label="C4 operator policy"
    )
    attestation = _cold_validate(
        attestation,
        C4Stage1HumanReviewOperatorAttestation,
        label="C4 Stage 1 operator attestation",
    )
    if (
        attestation.claim.operator_policy_id != operator_policy.policy_id
        or attestation.claim.operator_policy_sha256
        != operator_policy.operator_policy_sha256
        or attestation.claim.review_schema_id != operator_policy.review_schema_id
    ):
        raise ValueError("C4 Stage 1 attestation differs from operator policy")
    if (operator_secret is None) == (operator_attestation_verifier is None):
        raise TypeError(
            "C4 Stage 1 operator verification requires exactly one keyed boundary"
        )
    if operator_secret is not None:
        _validate_operator_secret(operator_policy, operator_secret)
        _reject_operator_secret_material(attestation, operator_secret)
        expected_hmac = hmac.digest(
            operator_secret,
            c4_stage1_operator_attestation_message(attestation.claim),
            "sha256",
        ).hex()
        verified = hmac.compare_digest(expected_hmac, attestation.hmac_sha256)
    else:
        verify = getattr(operator_attestation_verifier, "verify_attestation", None)
        if not callable(verify):
            raise TypeError(
                "C4 Stage 1 operator verification requires a live external verifier"
            )
        verified = (
            verify(operator_policy=operator_policy, attestation=attestation) is True
        )
    if not verified:
        raise ValueError("C4 Stage 1 operator HMAC verification failed")
    return attestation


class C4Stage1ConsumedOperatorPolicyReceipt(FrozenArtifactModel):
    schema_version: Literal["rei-c4-stage1-consumed-operator-policy-v2"] = (
        "rei-c4-stage1-consumed-operator-policy-v2"
    )
    consumed_operator_receipt_id: NonEmptyId
    consumed_operator_receipt_sha256: HashDigest
    operator_policy_id: NonEmptyId
    operator_policy_sha256: HashDigest
    one_time_ledger_key_policy_id: NonEmptyId
    operator_signing_lease_id: NonEmptyId
    operator_signing_lease_sha256: HashDigest
    claim_id: NonEmptyId
    claim_sha256: HashDigest
    attestation_id: NonEmptyId
    attestation_sha256: HashDigest
    attestation_hmac_sha256: HashDigest
    display_receipt_id: NonEmptyId
    display_receipt_sha256: HashDigest
    external_transaction_id: Stage1OpaqueId
    external_transaction_timestamp: UtcTimestamp
    external_ledger_claimed_atomic_consume_once: Literal[True] = True
    external_ledger_claimed_policy_id_consume_once: Literal[True] = True
    cold_validation_proves_live_ledger_state: Literal[False] = False
    live_external_ledger_reverification_required: Literal[True] = True
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False

    @model_validator(mode="after")
    def validate_consumed_operator_receipt(self) -> Self:
        _normalized_utc(
            self.external_transaction_timestamp,
            label="operator receipt transaction timestamp",
        )
        if (
            self.external_ledger_claimed_atomic_consume_once is not True
            or self.external_ledger_claimed_policy_id_consume_once is not True
            or self.one_time_ledger_key_policy_id != self.operator_policy_id
            or self.cold_validation_proves_live_ledger_state is not False
            or self.live_external_ledger_reverification_required is not True
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
        ):
            raise ValueError("C4 Stage 1 operator ledger receipt weakens its boundary")
        payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={
                "consumed_operator_receipt_id",
                "consumed_operator_receipt_sha256",
            },
        )
        expected_id, expected_sha256 = _content_addresses("c4_s1_operator_use", payload)
        if (
            self.consumed_operator_receipt_id != expected_id
            or self.consumed_operator_receipt_sha256 != expected_sha256
        ):
            raise ValueError("C4 Stage 1 consumed operator receipt address is invalid")
        _require_bounded_canonical(self, label="C4 Stage 1 operator ledger receipt")
        return self


def record_c4_stage1_consumed_operator_policy_receipt(
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4Stage1HumanReviewOperatorAttestation,
    *,
    external_transaction_id: str,
    external_transaction_timestamp: datetime,
) -> C4Stage1ConsumedOperatorPolicyReceipt:
    operator_policy = _cold_validate(
        operator_policy, C4HumanReviewOperatorPolicy, label="C4 operator policy"
    )
    attestation = _cold_validate(
        attestation,
        C4Stage1HumanReviewOperatorAttestation,
        label="C4 Stage 1 operator attestation",
    )
    claim = attestation.claim
    if (
        claim.operator_policy_id != operator_policy.policy_id
        or claim.operator_policy_sha256 != operator_policy.operator_policy_sha256
    ):
        raise ValueError("C4 Stage 1 operator receipt differs from policy")
    transaction_id = _validate_opaque_id(
        external_transaction_id, label="C4 Stage 1 operator transaction"
    )
    transaction_timestamp = _normalized_utc(
        external_transaction_timestamp, label="operator transaction timestamp"
    )
    if transaction_timestamp < claim.review_timestamp:
        raise ValueError("C4 Stage 1 operator receipt predates signed review")
    base = {
        "schema_version": "rei-c4-stage1-consumed-operator-policy-v2",
        "operator_policy_id": operator_policy.policy_id,
        "operator_policy_sha256": operator_policy.operator_policy_sha256,
        "one_time_ledger_key_policy_id": operator_policy.policy_id,
        "operator_signing_lease_id": claim.operator_signing_lease_id,
        "operator_signing_lease_sha256": claim.operator_signing_lease_sha256,
        "claim_id": claim.claim_id,
        "claim_sha256": claim.claim_sha256,
        "attestation_id": attestation.attestation_id,
        "attestation_sha256": attestation.attestation_sha256,
        "attestation_hmac_sha256": attestation.hmac_sha256,
        "display_receipt_id": claim.display_receipt_id,
        "display_receipt_sha256": claim.display_receipt_sha256,
        "external_transaction_id": transaction_id,
        "external_transaction_timestamp": transaction_timestamp,
        "external_ledger_claimed_atomic_consume_once": True,
        "external_ledger_claimed_policy_id_consume_once": True,
        "cold_validation_proves_live_ledger_state": False,
        "live_external_ledger_reverification_required": True,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
    }
    receipt_id, receipt_sha256 = _content_addresses("c4_s1_operator_use", base)
    return C4Stage1ConsumedOperatorPolicyReceipt(
        consumed_operator_receipt_id=receipt_id,
        consumed_operator_receipt_sha256=receipt_sha256,
        **base,
    )


class C4Stage1ExternalUsedPolicyLedgerPort(Protocol):
    """External ledger keyed only by policy_id, never by caller lease data."""

    def consume_once(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
    ) -> C4Stage1ConsumedOperatorPolicyReceipt:
        """Atomically reject every second issuance for operator_policy.policy_id."""
        ...

    def verify_consumed_use(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4Stage1HumanReviewOperatorAttestation,
        consumed_receipt: C4Stage1ConsumedOperatorPolicyReceipt,
    ) -> bool:
        """Reverify the exact policy-id consumption against live state."""
        ...


def _validate_consumed_operator_binding(
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4Stage1HumanReviewOperatorAttestation,
    consumed_receipt: C4Stage1ConsumedOperatorPolicyReceipt,
) -> C4Stage1ConsumedOperatorPolicyReceipt:
    consumed_receipt = _cold_validate(
        consumed_receipt,
        C4Stage1ConsumedOperatorPolicyReceipt,
        label="C4 Stage 1 consumed operator receipt",
    )
    claim = attestation.claim
    if (
        consumed_receipt.operator_policy_id != operator_policy.policy_id
        or consumed_receipt.one_time_ledger_key_policy_id != operator_policy.policy_id
        or consumed_receipt.operator_policy_sha256
        != operator_policy.operator_policy_sha256
        or consumed_receipt.operator_signing_lease_id != claim.operator_signing_lease_id
        or consumed_receipt.operator_signing_lease_sha256
        != claim.operator_signing_lease_sha256
        or consumed_receipt.claim_id != claim.claim_id
        or consumed_receipt.claim_sha256 != claim.claim_sha256
        or consumed_receipt.attestation_id != attestation.attestation_id
        or consumed_receipt.attestation_sha256 != attestation.attestation_sha256
        or consumed_receipt.attestation_hmac_sha256 != attestation.hmac_sha256
        or consumed_receipt.display_receipt_id != claim.display_receipt_id
        or consumed_receipt.display_receipt_sha256 != claim.display_receipt_sha256
    ):
        raise ValueError("C4 Stage 1 operator ledger receipt differs from claim")
    return consumed_receipt


def _consume_operator_policy_once(
    ledger: C4Stage1ExternalUsedPolicyLedgerPort,
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4Stage1HumanReviewOperatorAttestation,
) -> C4Stage1ConsumedOperatorPolicyReceipt:
    consume_once = getattr(ledger, "consume_once", None)
    if not callable(consume_once):
        raise TypeError("C4 Stage 1 sealing requires an external operator ledger")
    consumed = consume_once(operator_policy=operator_policy, attestation=attestation)
    return _validate_consumed_operator_binding(operator_policy, attestation, consumed)


def _reverify_consumed_operator_policy(
    ledger: C4Stage1ExternalUsedPolicyLedgerPort,
    operator_policy: C4HumanReviewOperatorPolicy,
    attestation: C4Stage1HumanReviewOperatorAttestation,
    consumed_receipt: C4Stage1ConsumedOperatorPolicyReceipt,
) -> C4Stage1ConsumedOperatorPolicyReceipt:
    consumed_receipt = _validate_consumed_operator_binding(
        operator_policy, attestation, consumed_receipt
    )
    verify = getattr(ledger, "verify_consumed_use", None)
    if not callable(verify):
        raise TypeError("C4 Stage 1 replay requires a live operator-ledger verifier")
    verified = verify(
        operator_policy=operator_policy,
        attestation=attestation,
        consumed_receipt=consumed_receipt,
    )
    if verified is not True:
        raise ValueError("C4 Stage 1 operator receipt is not live in external state")
    return consumed_receipt


class C4Stage1SealedHumanReviewSubmission(FrozenArtifactModel):
    schema_version: Literal["rei-c4-stage1-sealed-human-review-v2"] = (
        "rei-c4-stage1-sealed-human-review-v2"
    )
    submission_id: NonEmptyId
    packet: C4BlindReviewPacket
    operator_policy: C4HumanReviewOperatorPolicy
    screen_contract_id: NonEmptyId
    screen_contract_sha256: HashDigest
    display_attester_policy: C4Stage1DisplayAttesterPolicy
    presentation_manifest: C4BlindPresentationManifest
    display_receipt: C4Stage1DisplayExecutionReceipt
    consumed_display_receipt: C4Stage1ConsumedDisplayReceipt
    operator_attestation: C4Stage1HumanReviewOperatorAttestation
    consumed_operator_receipt: C4Stage1ConsumedOperatorPolicyReceipt
    reviewer_pseudonym: NonEmptyId
    review_timestamp: UtcTimestamp
    output_judgments: tuple[C4OutputHumanJudgment, ...] = Field(
        min_length=2, max_length=2
    )
    pair_judgment: C4PairHumanJudgment
    review_state: Literal["sealed_submission"] = "sealed_submission"
    human_review_passed: bool
    exact_display_receipt_in_operator_hmac: Literal[True] = True
    separately_keyed_display_attestation_in_operator_hmac: Literal[True] = True
    display_receipt_cold_reverification_required: Literal[True] = True
    display_receipt_live_external_reverification_required: Literal[True] = True
    operator_secret_and_live_ledger_reverification_required: Literal[True] = True
    cold_artifact_proves_human_attention: Literal[False] = False
    attestation_proves_human_cognition: Literal[False] = False
    reveal_mapping_present: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_submission(self) -> Self:
        packet = C4BlindReviewPacket.model_validate(
            self.packet.model_dump(mode="python", round_trip=True)
        )
        operator_policy = C4HumanReviewOperatorPolicy.model_validate(
            self.operator_policy.model_dump(mode="python", round_trip=True)
        )
        display_attester_policy = C4Stage1DisplayAttesterPolicy.model_validate(
            self.display_attester_policy.model_dump(mode="python", round_trip=True)
        )
        presentation = C4BlindPresentationManifest.model_validate(
            self.presentation_manifest.model_dump(mode="python", round_trip=True)
        )
        display_receipt = C4Stage1DisplayExecutionReceipt.model_validate(
            self.display_receipt.model_dump(mode="python", round_trip=True)
        )
        consumed_display = _validate_consumed_display_binding(
            display_receipt, self.consumed_display_receipt
        )
        attestation = C4Stage1HumanReviewOperatorAttestation.model_validate(
            self.operator_attestation.model_dump(mode="python", round_trip=True)
        )
        consumed_operator = _validate_consumed_operator_binding(
            operator_policy, attestation, self.consumed_operator_receipt
        )
        judgments, pair = _validate_judgments(
            packet, self.output_judgments, self.pair_judgment
        )
        claim = attestation.claim
        packet_output_records = tuple(
            (item.blind_code, item.blind_order_sha256, item.output_sha256)
            for item in packet.outputs
        )
        presentation_output_records = tuple(
            (item.blind_code, item.blind_order_sha256, item.image_sha256)
            for item in presentation.outputs
        )
        if (
            packet.operator_policy_id != operator_policy.policy_id
            or packet.operator_policy_sha256 != operator_policy.operator_policy_sha256
            or packet.review_schema_id != operator_policy.review_schema_id
            or packet.source_image_sha256 != operator_policy.source_image_sha256
            or presentation.review_schema_id != packet.review_schema_id
            or presentation.operator_policy_id != packet.operator_policy_id
            or presentation.operator_policy_sha256 != packet.operator_policy_sha256
            or presentation.packet_id != packet.packet_id
            or presentation.packet_sha256 != packet.packet_sha256
            or presentation.material_commitment_id != packet.material_commitment_id
            or presentation.material_commitment_sha256
            != packet.material_commitment_sha256
            or presentation.source.image_sha256 != packet.source_image_sha256
            or presentation_output_records != packet_output_records
            or display_receipt.context.packet_id != packet.packet_id
            or display_receipt.context.packet_sha256 != packet.packet_sha256
            or display_receipt.context.presentation_manifest_id
            != presentation.presentation_manifest_id
            or display_receipt.context.presentation_manifest_sha256
            != presentation.presentation_manifest_sha256
            or display_receipt.context.material_commitment_id
            != packet.material_commitment_id
            or display_receipt.context.material_commitment_sha256
            != packet.material_commitment_sha256
            or display_receipt.context.review_schema_id != packet.review_schema_id
            or display_receipt.context.rubric_version != packet.rubric_version
            or display_receipt.context.operator_policy_id != packet.operator_policy_id
            or display_receipt.context.operator_policy_sha256
            != packet.operator_policy_sha256
            or display_receipt.context.source_image_sha256 != packet.source_image_sha256
            or display_receipt.context.outputs != packet.outputs
            or display_receipt.context.screen_contract_id != self.screen_contract_id
            or display_receipt.context.screen_contract_sha256
            != self.screen_contract_sha256
            or display_receipt.display_attester_policy != display_attester_policy
            or claim.operator_policy_id != operator_policy.policy_id
            or claim.operator_policy_sha256 != operator_policy.operator_policy_sha256
            or claim.review_schema_id != packet.review_schema_id
            or claim.packet_id != packet.packet_id
            or claim.packet_sha256 != packet.packet_sha256
            or claim.presentation_manifest_id != presentation.presentation_manifest_id
            or claim.presentation_manifest_sha256
            != presentation.presentation_manifest_sha256
            or claim.screen_contract_id != self.screen_contract_id
            or claim.screen_contract_sha256 != self.screen_contract_sha256
            or claim.display_policy_id != display_attester_policy.display_policy_id
            or claim.display_policy_sha256
            != display_attester_policy.display_policy_sha256
            or claim.display_policy_artifact_sha256
            != display_attester_policy.content_hash()
            or claim.display_attestation_id
            != display_receipt.display_attestation.display_attestation_id
            or claim.display_attestation_sha256
            != display_receipt.display_attestation.display_attestation_sha256
            or claim.consumed_display_attestation_id
            != display_receipt.consumed_display_attestation.consumed_display_attestation_id
            or claim.consumed_display_attestation_sha256
            != display_receipt.consumed_display_attestation.consumed_display_attestation_sha256
            or claim.display_receipt_id != display_receipt.display_receipt_id
            or claim.display_receipt_sha256 != display_receipt.display_receipt_sha256
            or claim.consumed_display_receipt_id
            != consumed_display.consumed_display_receipt_id
            or claim.consumed_display_receipt_sha256
            != consumed_display.consumed_display_receipt_sha256
            or claim.reviewer_pseudonym != self.reviewer_pseudonym
            or claim.review_timestamp != self.review_timestamp
            or claim.output_judgments != judgments
            or claim.pair_judgment != pair
            or consumed_operator != self.consumed_operator_receipt
        ):
            raise ValueError("C4 Stage 1 sealed review differs from signed claim")
        expected_pass = all(item.passed for item in judgments) and pair.passed
        if (
            type(self.human_review_passed) is not bool
            or self.human_review_passed != expected_pass
        ):
            raise ValueError("C4 Stage 1 review pass differs from strict rubric")
        if (
            self.review_state != "sealed_submission"
            or self.exact_display_receipt_in_operator_hmac is not True
            or self.separately_keyed_display_attestation_in_operator_hmac is not True
            or self.display_receipt_cold_reverification_required is not True
            or self.display_receipt_live_external_reverification_required is not True
            or self.operator_secret_and_live_ledger_reverification_required is not True
            or self.cold_artifact_proves_human_attention is not False
            or self.attestation_proves_human_cognition is not False
            or self.reveal_mapping_present is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 sealed review weakens authority boundaries")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"submission_id"}
        )
        if self.submission_id != content_id("c4_stage1_human_review", payload):
            raise ValueError("C4 Stage 1 sealed review ID differs from content")
        _require_bounded_canonical(self, label="C4 Stage 1 sealed review")
        return self


def seal_c4_stage1_human_review(
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    *,
    artifact_store: FileArtifactStore,
    operator_policy: C4HumanReviewOperatorPolicy,
    screen_contract: C4Stage1ScreenContract,
    display_attester_policy: C4Stage1DisplayAttesterPolicy,
    presentation_manifest: C4BlindPresentationManifest,
    display_receipt: C4Stage1DisplayExecutionReceipt,
    consumed_display_receipt: C4Stage1ConsumedDisplayReceipt,
    operator_attestation: C4Stage1HumanReviewOperatorAttestation,
    operator_secret: bytes | None,
    display_attestation_verifier: C4Stage1ExternalDisplayAttestationVerifierPort,
    display_receipt_ledger: C4Stage1ExternalDisplayReceiptLedgerPort,
    used_policy_ledger: C4Stage1ExternalUsedPolicyLedgerPort,
    operator_attestation_verifier: (
        C4Stage1ExternalOperatorAttestationVerifierPort | None
    ) = None,
    source_png_path: str | Path | None = None,
    output_png_paths: tuple[str | Path, str | Path] | None = None,
) -> C4Stage1SealedHumanReviewSubmission:
    del source_png_path, output_png_paths
    schema, packet, operator_policy, presentation_manifest = _validate_display_inputs(
        schema, packet, operator_policy, presentation_manifest
    )
    screen_contract = _validate_pre_output_display_binding(
        screen_contract, schema, operator_policy, display_attester_policy
    )
    display_attester_policy = _cold_validate(
        display_attester_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    display_receipt = cold_verify_c4_stage1_display_execution_receipt(
        display_receipt,
        schema,
        packet,
        artifact_store=artifact_store,
        operator_policy=operator_policy,
        screen_contract=screen_contract,
        display_attester_policy=display_attester_policy,
        presentation_manifest=presentation_manifest,
    )
    _reverify_display_receipt_attestation(display_attestation_verifier, display_receipt)
    consumed_display_receipt = _reverify_consumed_display_receipt(
        display_receipt_ledger, display_receipt, consumed_display_receipt
    )
    operator_attestation = verify_c4_stage1_operator_attestation(
        operator_policy,
        operator_attestation,
        operator_secret=operator_secret,
        operator_attestation_verifier=operator_attestation_verifier,
    )
    for artifact in (
        packet,
        display_attester_policy,
        presentation_manifest,
        display_receipt,
        consumed_display_receipt,
        operator_attestation,
    ):
        if operator_secret is not None:
            _reject_operator_secret_material(artifact, operator_secret)
    claim = operator_attestation.claim
    judgments, pair_judgment = _validate_judgments(
        packet, claim.output_judgments, claim.pair_judgment
    )
    if (
        claim.operator_policy_id != operator_policy.policy_id
        or claim.operator_policy_sha256 != operator_policy.operator_policy_sha256
        or claim.review_schema_id != schema.schema_id
        or claim.packet_id != packet.packet_id
        or claim.packet_sha256 != packet.packet_sha256
        or claim.presentation_manifest_id
        != presentation_manifest.presentation_manifest_id
        or claim.presentation_manifest_sha256
        != presentation_manifest.presentation_manifest_sha256
        or claim.screen_contract_id != screen_contract.screen_contract_id
        or claim.screen_contract_sha256 != screen_contract.content_hash()
        or claim.display_policy_id != display_attester_policy.display_policy_id
        or claim.display_policy_sha256 != display_attester_policy.display_policy_sha256
        or claim.display_policy_artifact_sha256
        != display_attester_policy.content_hash()
        or claim.display_attestation_id
        != display_receipt.display_attestation.display_attestation_id
        or claim.display_attestation_sha256
        != display_receipt.display_attestation.display_attestation_sha256
        or claim.consumed_display_attestation_id
        != display_receipt.consumed_display_attestation.consumed_display_attestation_id
        or claim.consumed_display_attestation_sha256
        != display_receipt.consumed_display_attestation.consumed_display_attestation_sha256
        or claim.display_receipt_id != display_receipt.display_receipt_id
        or claim.display_receipt_sha256 != display_receipt.display_receipt_sha256
        or claim.consumed_display_receipt_id
        != consumed_display_receipt.consumed_display_receipt_id
        or claim.consumed_display_receipt_sha256
        != consumed_display_receipt.consumed_display_receipt_sha256
    ):
        raise ValueError("C4 Stage 1 signed claim differs from review material")
    consumed_operator_receipt = _consume_operator_policy_once(
        used_policy_ledger, operator_policy, operator_attestation
    )
    if operator_secret is not None:
        _reject_operator_secret_material(consumed_operator_receipt, operator_secret)
    passed = all(item.passed for item in judgments) and pair_judgment.passed
    base = {
        "schema_version": "rei-c4-stage1-sealed-human-review-v2",
        "packet": packet,
        "operator_policy": operator_policy,
        "screen_contract_id": screen_contract.screen_contract_id,
        "screen_contract_sha256": screen_contract.content_hash(),
        "display_attester_policy": display_attester_policy,
        "presentation_manifest": presentation_manifest,
        "display_receipt": display_receipt,
        "consumed_display_receipt": consumed_display_receipt,
        "operator_attestation": operator_attestation,
        "consumed_operator_receipt": consumed_operator_receipt,
        "reviewer_pseudonym": claim.reviewer_pseudonym,
        "review_timestamp": claim.review_timestamp,
        "output_judgments": judgments,
        "pair_judgment": pair_judgment,
        "review_state": "sealed_submission",
        "human_review_passed": passed,
        "exact_display_receipt_in_operator_hmac": True,
        "separately_keyed_display_attestation_in_operator_hmac": True,
        "display_receipt_cold_reverification_required": True,
        "display_receipt_live_external_reverification_required": True,
        "operator_secret_and_live_ledger_reverification_required": True,
        "cold_artifact_proves_human_attention": False,
        "attestation_proves_human_cognition": False,
        "reveal_mapping_present": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    return C4Stage1SealedHumanReviewSubmission(
        submission_id=content_id("c4_stage1_human_review", base), **base
    )


class C4Stage1HumanReviewGateResult(FrozenArtifactModel):
    schema_version: Literal["rei-c4-stage1-human-review-gate-v2"] = (
        "rei-c4-stage1-human-review-gate-v2"
    )
    gate_result_id: NonEmptyId
    packet: C4BlindReviewPacket
    operator_policy: C4HumanReviewOperatorPolicy
    screen_contract_id: NonEmptyId
    screen_contract_sha256: HashDigest
    display_attester_policy: C4Stage1DisplayAttesterPolicy
    review_status: Stage1ReviewStatus
    reason: Stage1ReviewReason
    submission: C4Stage1SealedHumanReviewSubmission | None = None
    human_review_passed: bool
    display_receipt_status: Literal[
        "requires_runtime_cold_and_live_reverification",
        "not_applicable_missing",
        "not_applicable_skipped",
    ]
    operator_receipt_status: Literal[
        "requires_runtime_secret_and_live_reverification",
        "not_applicable_missing",
        "not_applicable_skipped",
    ]
    gate_artifact_proves_human_attention: Literal[False] = False
    gate_artifact_proves_human_cognition: Literal[False] = False
    semantic_quality_gate_passed: Literal[False] = False
    production_authority_granted: Literal[False] = False
    generated_images_are_external_evidence: Literal[False] = False
    model_judge_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_gate(self) -> Self:
        packet = C4BlindReviewPacket.model_validate(
            self.packet.model_dump(mode="python", round_trip=True)
        )
        operator_policy = C4HumanReviewOperatorPolicy.model_validate(
            self.operator_policy.model_dump(mode="python", round_trip=True)
        )
        display_attester_policy = C4Stage1DisplayAttesterPolicy.model_validate(
            self.display_attester_policy.model_dump(mode="python", round_trip=True)
        )
        if (
            packet.operator_policy_id != operator_policy.policy_id
            or packet.operator_policy_sha256 != operator_policy.operator_policy_sha256
        ):
            raise ValueError("C4 Stage 1 gate policy differs from packet")
        if self.review_status == "sealed_submission":
            if (
                self.submission is None
                or self.submission.packet != packet
                or self.submission.screen_contract_id != self.screen_contract_id
                or self.submission.screen_contract_sha256 != self.screen_contract_sha256
                or self.submission.display_attester_policy != display_attester_policy
            ):
                raise ValueError("C4 Stage 1 sealed gate requires exact submission")
            submission = C4Stage1SealedHumanReviewSubmission.model_validate(
                self.submission.model_dump(mode="python", round_trip=True)
            )
            expected_pass = submission.human_review_passed
            expected_reason = (
                "human_review_passed" if expected_pass else "human_review_failed"
            )
            expected_display_status = "requires_runtime_cold_and_live_reverification"
            expected_operator_status = "requires_runtime_secret_and_live_reverification"
        else:
            if self.submission is not None:
                raise ValueError(
                    "C4 Stage 1 missing/skipped gate cannot contain submission"
                )
            expected_pass = False
            if self.review_status == "missing":
                expected_reason = "human_review_missing"
                expected_display_status = "not_applicable_missing"
                expected_operator_status = "not_applicable_missing"
            else:
                expected_reason = "human_review_skipped"
                expected_display_status = "not_applicable_skipped"
                expected_operator_status = "not_applicable_skipped"
        if (
            type(self.human_review_passed) is not bool
            or self.human_review_passed != expected_pass
            or self.reason != expected_reason
            or self.display_receipt_status != expected_display_status
            or self.operator_receipt_status != expected_operator_status
            or self.gate_artifact_proves_human_attention is not False
            or self.gate_artifact_proves_human_cognition is not False
            or self.semantic_quality_gate_passed is not False
            or self.production_authority_granted is not False
            or self.generated_images_are_external_evidence is not False
            or self.model_judge_calls != 0
        ):
            raise ValueError("C4 Stage 1 gate does not replay fail closed")
        payload = self.model_dump(
            mode="python", round_trip=True, exclude={"gate_result_id"}
        )
        if self.gate_result_id != content_id("c4_stage1_review_gate", payload):
            raise ValueError("C4 Stage 1 gate ID differs from content")
        _require_bounded_canonical(self, label="C4 Stage 1 review gate")
        return self


def evaluate_c4_stage1_human_review(
    schema: C4BlindHumanReviewSchema,
    packet: C4BlindReviewPacket,
    *,
    artifact_store: FileArtifactStore,
    operator_policy: C4HumanReviewOperatorPolicy,
    screen_contract: C4Stage1ScreenContract,
    display_attester_policy: C4Stage1DisplayAttesterPolicy,
    operator_secret: bytes | None,
    display_attestation_verifier: C4Stage1ExternalDisplayAttestationVerifierPort,
    display_receipt_ledger: C4Stage1ExternalDisplayReceiptLedgerPort,
    used_policy_ledger: C4Stage1ExternalUsedPolicyLedgerPort,
    operator_attestation_verifier: (
        C4Stage1ExternalOperatorAttestationVerifierPort | None
    ) = None,
    submission: C4Stage1SealedHumanReviewSubmission | None = None,
    source_png_path: str | Path | None = None,
    output_png_paths: tuple[str | Path, str | Path] | None = None,
    skipped: bool = False,
) -> C4Stage1HumanReviewGateResult:
    del source_png_path, output_png_paths
    schema = _cold_validate(schema, C4BlindHumanReviewSchema, label="C4 review schema")
    packet = _cold_validate(packet, C4BlindReviewPacket, label="C4 blind packet")
    operator_policy = _cold_validate(
        operator_policy, C4HumanReviewOperatorPolicy, label="C4 operator policy"
    )
    if (
        packet.review_schema_id != schema.schema_id
        or packet.rubric_version != schema.rubric_version
        or packet.operator_policy_id != operator_policy.policy_id
        or packet.operator_policy_sha256 != operator_policy.operator_policy_sha256
        or operator_policy.review_schema_id != schema.schema_id
    ):
        raise ValueError("C4 Stage 1 gate schema/policy differs from packet")
    screen_contract = _validate_pre_output_display_binding(
        screen_contract, schema, operator_policy, display_attester_policy
    )
    display_attester_policy = _cold_validate(
        display_attester_policy,
        C4Stage1DisplayAttesterPolicy,
        label="C4 Stage 1 display policy",
    )
    if (operator_secret is None) == (operator_attestation_verifier is None):
        raise TypeError(
            "C4 Stage 1 review gate requires exactly one operator keyed boundary"
        )
    if operator_secret is not None:
        _validate_operator_secret(operator_policy, operator_secret)
        _reject_operator_secret_material(packet, operator_secret)
    if type(skipped) is not bool:
        raise TypeError("C4 Stage 1 skipped flag must be boolean")
    if skipped and submission is not None:
        raise ValueError("C4 Stage 1 skipped review cannot contain submission")
    if submission is not None:
        submission = _cold_validate(
            submission,
            C4Stage1SealedHumanReviewSubmission,
            label="C4 Stage 1 sealed submission",
        )
        if (
            submission.packet != packet
            or submission.operator_policy != operator_policy
            or submission.screen_contract_id != screen_contract.screen_contract_id
            or submission.screen_contract_sha256 != screen_contract.content_hash()
            or submission.display_attester_policy != display_attester_policy
        ):
            raise ValueError("C4 Stage 1 submission belongs to different review")
        _validate_display_inputs(
            schema,
            packet,
            operator_policy,
            submission.presentation_manifest,
        )
        verify_c4_stage1_operator_attestation(
            operator_policy,
            submission.operator_attestation,
            operator_secret=operator_secret,
            operator_attestation_verifier=operator_attestation_verifier,
        )
        if operator_secret is not None:
            _reject_operator_secret_material(submission, operator_secret)
        cold_verify_c4_stage1_display_execution_receipt(
            submission.display_receipt,
            schema,
            packet,
            artifact_store=artifact_store,
            operator_policy=operator_policy,
            screen_contract=screen_contract,
            display_attester_policy=display_attester_policy,
            presentation_manifest=submission.presentation_manifest,
        )
        _reverify_display_receipt_attestation(
            display_attestation_verifier, submission.display_receipt
        )
        _reverify_consumed_display_receipt(
            display_receipt_ledger,
            submission.display_receipt,
            submission.consumed_display_receipt,
        )
        _reverify_consumed_operator_policy(
            used_policy_ledger,
            operator_policy,
            submission.operator_attestation,
            submission.consumed_operator_receipt,
        )
        review_status: Stage1ReviewStatus = "sealed_submission"
        passed = submission.human_review_passed
        reason: Stage1ReviewReason = (
            "human_review_passed" if passed else "human_review_failed"
        )
        display_status = "requires_runtime_cold_and_live_reverification"
        operator_status = "requires_runtime_secret_and_live_reverification"
    elif skipped:
        review_status = "skipped"
        passed = False
        reason = "human_review_skipped"
        display_status = "not_applicable_skipped"
        operator_status = "not_applicable_skipped"
    else:
        review_status = "missing"
        passed = False
        reason = "human_review_missing"
        display_status = "not_applicable_missing"
        operator_status = "not_applicable_missing"
    base = {
        "schema_version": "rei-c4-stage1-human-review-gate-v2",
        "packet": packet,
        "operator_policy": operator_policy,
        "screen_contract_id": screen_contract.screen_contract_id,
        "screen_contract_sha256": screen_contract.content_hash(),
        "display_attester_policy": display_attester_policy,
        "review_status": review_status,
        "reason": reason,
        "submission": submission,
        "human_review_passed": passed,
        "display_receipt_status": display_status,
        "operator_receipt_status": operator_status,
        "gate_artifact_proves_human_attention": False,
        "gate_artifact_proves_human_cognition": False,
        "semantic_quality_gate_passed": False,
        "production_authority_granted": False,
        "generated_images_are_external_evidence": False,
        "model_judge_calls": 0,
    }
    return C4Stage1HumanReviewGateResult(
        gate_result_id=content_id("c4_stage1_review_gate", base), **base
    )


__all__ = [
    "C4_STAGE1_DISPLAY_ATTESTATION_DOMAIN",
    "C4_STAGE1_DISPLAY_ATTESTATION_SCHEME",
    "C4_STAGE1_DISPLAY_POLICY",
    "C4_STAGE1_DISPLAY_PORT_POLICY",
    "C4_STAGE1_MAX_CANONICAL_BYTES",
    "C4_STAGE1_OPERATOR_RECEIPT_DOMAIN",
    "C4Stage1ConsumedDisplayAttestation",
    "C4Stage1ConsumedDisplayReceipt",
    "C4Stage1ConsumedOperatorPolicyReceipt",
    "C4Stage1DisplayAckOutput",
    "C4Stage1DisplayAttestation",
    "C4Stage1DisplayAttesterPolicy",
    "C4Stage1DisplayContext",
    "C4Stage1DisplayCandidatePublicationBinding",
    "C4Stage1DisplayedPng",
    "C4Stage1DisplayExecutionReceipt",
    "C4Stage1DisplayPortAcknowledgement",
    "C4Stage1DisplayPortResult",
    "C4Stage1DisplayPublicationBinding",
    "C4Stage1ExternalDisplayAttestationVerifierPort",
    "C4Stage1ExternalDisplayReceiptLedgerPort",
    "C4Stage1ExternalOperatorAttestationVerifierPort",
    "C4Stage1ExternalUsedPolicyLedgerPort",
    "C4Stage1HumanReviewGateResult",
    "C4Stage1HumanReviewOperatorAttestation",
    "C4Stage1HumanReviewUnsignedClaim",
    "C4Stage1SealedHumanReviewSubmission",
    "C4Stage1TrustedDisplayPort",
    "C4Stage1VisibleOutput",
    "build_c4_stage1_display_attestation",
    "build_c4_stage1_display_attester_policy",
    "build_c4_stage1_display_port_acknowledgement",
    "build_c4_stage1_operator_attestation",
    "build_c4_stage1_operator_unsigned_claim",
    "c4_stage1_display_attestation_message",
    "c4_stage1_display_policy_content_pin",
    "c4_stage1_operator_attestation_message",
    "cold_verify_c4_stage1_display_execution_receipt",
    "consume_c4_stage1_display_receipt_once",
    "evaluate_c4_stage1_human_review",
    "execute_c4_stage1_display",
    "record_c4_stage1_consumed_display_attestation",
    "record_c4_stage1_consumed_display_receipt",
    "record_c4_stage1_consumed_operator_policy_receipt",
    "seal_c4_stage1_human_review",
    "verify_c4_stage1_operator_attestation",
]
