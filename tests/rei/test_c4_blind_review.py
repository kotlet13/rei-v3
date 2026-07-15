from __future__ import annotations

import base64
import hashlib
import hmac
import inspect
import json
import struct
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.backend.rei import evaluation as evaluation_api
from app.backend.rei.evaluation import c4_blind_review as c4_blind_review_module
from app.backend.rei.evaluation.c4_blind_review import (
    C4_HMAC_KEY_MAX_BYTES,
    C4_HMAC_KEY_MIN_BYTES,
    C4_OPERATOR_ATTESTATION_CLAIM,
    C4_OPERATOR_ENTRY_ORIGIN,
    C4_OPERATOR_POLICY_SCHEME,
    C4_OUTPUT_POSITIVE_FIELDS,
    C4_PRESENTATION_MAX_PNG_BYTES,
    C4_PRESENTATION_MAX_PNG_CHUNKS,
    C4_PRESENTATION_POLICY,
    C4_PRESENTATION_PNG_CHUNK_POLICY,
    C4_REVIEW_MAX_CANONICAL_BYTES,
    C4BlindHumanReviewSchema,
    C4BlindPresentationManifest,
    C4BlindReviewPacket,
    C4ConsumedOperatorPolicyReceipt,
    C4ExternalUsedPolicyLedgerPort,
    C4HumanReviewOperatorAttestation,
    C4HumanReviewOperatorPolicy,
    C4HumanReviewUnsignedClaim,
    C4OutputHumanJudgment,
    C4PairHumanJudgment,
    C4ReviewMaterialCommitment,
    build_c4_blind_human_review_schema,
    build_c4_blind_presentation_manifest,
    build_c4_human_review_operator_policy,
    build_c4_operator_attestation,
    build_c4_operator_unsigned_claim,
    c4_blind_order_sha256,
    c4_operator_attestation_message,
    commit_c4_review_material,
    evaluate_c4_human_review,
    make_c4_review_option_material,
    prepare_c4_blind_review,
    record_c4_output_human_judgment,
    record_c4_consumed_operator_policy_receipt,
    reveal_c4_review_identities,
    seal_c4_human_review,
    verify_c4_operator_attestation,
)
from app.backend.rei.ids import canonical_json_bytes, content_id


def test_c4_public_api_is_reexported_once_by_evaluation_package() -> None:
    intended_names = tuple(c4_blind_review_module.__all__)

    assert len(intended_names) == len(set(intended_names))
    assert len(evaluation_api.__all__) == len(set(evaluation_api.__all__))
    assert set(intended_names) <= set(evaluation_api.__all__)
    assert all(
        getattr(evaluation_api, name) is getattr(c4_blind_review_module, name)
        for name in intended_names
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_digest(value: object) -> str:
    return _bytes_digest(canonical_json_bytes(value))


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )


def _png_bytes(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    row = b"\x00" + bytes(rgb) * width
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(row * height))
        + _png_chunk(b"IEND", b"")
    )


class InMemoryUsedPolicyLedger(C4ExternalUsedPolicyLedgerPort):
    """Test-only stand-in for one trusted external atomic ledger."""

    def __init__(self) -> None:
        self.available = True
        self._lock = threading.Lock()
        self._transaction_counter = 0
        self._used_by_policy: dict[str, C4ConsumedOperatorPolicyReceipt] = {}
        self._used_by_lease: dict[str, C4ConsumedOperatorPolicyReceipt] = {}

    def consume_once(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4HumanReviewOperatorAttestation,
    ) -> C4ConsumedOperatorPolicyReceipt:
        if not self.available:
            raise RuntimeError("external ledger unavailable")
        lease = attestation.claim.external_one_time_ledger_lease_sha256
        with self._lock:
            if (
                operator_policy.policy_id in self._used_by_policy
                or lease in self._used_by_lease
            ):
                raise ValueError("external ledger policy or lease already consumed")
            self._transaction_counter += 1
            receipt = record_c4_consumed_operator_policy_receipt(
                operator_policy,
                attestation,
                external_transaction_id=(
                    f"ledger-transaction-{self._transaction_counter}"
                ),
                external_transaction_timestamp=datetime(
                    2026,
                    7,
                    15,
                    10,
                    0,
                    self._transaction_counter,
                    tzinfo=timezone.utc,
                ),
            )
            self._used_by_policy[operator_policy.policy_id] = receipt
            self._used_by_lease[lease] = receipt
            return receipt

    def verify_consumed_use(
        self,
        *,
        operator_policy: C4HumanReviewOperatorPolicy,
        attestation: C4HumanReviewOperatorAttestation,
        consumed_receipt: C4ConsumedOperatorPolicyReceipt,
    ) -> bool:
        if not self.available:
            raise RuntimeError("external ledger unavailable")
        lease = attestation.claim.external_one_time_ledger_lease_sha256
        with self._lock:
            return (
                self._used_by_policy.get(operator_policy.policy_id) == consumed_receipt
                and self._used_by_lease.get(lease) == consumed_receipt
            )

    def remove_live_entry(self, policy_id: str, lease: str) -> None:
        with self._lock:
            self._used_by_policy.pop(policy_id, None)
            self._used_by_lease.pop(lease, None)


@dataclass(frozen=True)
class ReviewBundle:
    schema: C4BlindHumanReviewSchema
    policy: C4HumanReviewOperatorPolicy
    commitment: C4ReviewMaterialCommitment
    packet: C4BlindReviewPacket
    presentation: C4BlindPresentationManifest
    secret: bytes
    source_path: Path
    output_paths: tuple[Path, Path]
    ledger_lease_sha256: str
    ledger: InMemoryUsedPolicyLedger


@pytest.fixture
def review_bundle(tmp_path: Path) -> ReviewBundle:
    source_bytes = _png_bytes(4, 3, (20, 30, 40))
    enter_bytes = _png_bytes(4, 3, (80, 20, 10))
    remain_bytes = _png_bytes(4, 3, (10, 80, 20))
    source_path = tmp_path / "source.png"
    enter_path = tmp_path / "enter.png"
    remain_path = tmp_path / "remain.png"
    source_path.write_bytes(source_bytes)
    enter_path.write_bytes(enter_bytes)
    remain_path.write_bytes(remain_bytes)

    secret = bytes(range(1, 33))
    schema = build_c4_blind_human_review_schema()
    policy = build_c4_human_review_operator_policy(
        schema,
        run_id="c4-stage1-preflight",
        candidate_slot_id="blind-candidate-slot-a",
        source_image_sha256=_bytes_digest(source_bytes),
        hmac_key_commitment_sha256=_bytes_digest(secret),
    )
    options = (
        make_c4_review_option_material(
            option_id="remain_edge",
            instruction="Keep the central subject outside the marked threshold.",
            output_sha256=_bytes_digest(remain_bytes),
        ),
        make_c4_review_option_material(
            option_id="enter_circle",
            instruction="Move the central subject across the marked threshold.",
            output_sha256=_bytes_digest(enter_bytes),
        ),
    )
    commitment = commit_c4_review_material(
        schema,
        operator_policy=policy,
        source_image_sha256=_bytes_digest(source_bytes),
        renderer_id="longcat_turbo",
        model_id="meituan-longcat/LongCat-Image-Edit-Turbo",
        model_revision="6a7262de5549f0bf0ec54c08ef7d283ef41f3214",
        options=options,
    )
    packet = prepare_c4_blind_review(
        schema,
        commitment,
        operator_policy=policy,
    )
    path_by_hash = {
        _bytes_digest(enter_bytes): enter_path,
        _bytes_digest(remain_bytes): remain_path,
    }
    output_paths = tuple(path_by_hash[item.output_sha256] for item in packet.outputs)
    presentation = build_c4_blind_presentation_manifest(
        packet,
        operator_policy=policy,
        source_png_path=source_path,
        output_png_paths=output_paths,
    )
    return ReviewBundle(
        schema=schema,
        policy=policy,
        commitment=commitment,
        packet=packet,
        presentation=presentation,
        secret=secret,
        source_path=source_path,
        output_paths=output_paths,
        ledger_lease_sha256=_digest("external-one-time-ledger-lease-0001"),
        ledger=InMemoryUsedPolicyLedger(),
    )


def _presentation_inputs_for_source(
    bundle: ReviewBundle,
    tmp_path: Path,
    *,
    source_bytes: bytes,
    label: str,
) -> tuple[
    Path,
    C4HumanReviewOperatorPolicy,
    C4BlindReviewPacket,
    tuple[Path, Path],
]:
    source_path = tmp_path / f"{label}.png"
    source_path.write_bytes(source_bytes)
    source_hash = _bytes_digest(source_bytes)
    policy = build_c4_human_review_operator_policy(
        bundle.schema,
        run_id=f"{label}-run",
        candidate_slot_id=f"{label}-slot",
        source_image_sha256=source_hash,
        hmac_key_commitment_sha256=_bytes_digest(bundle.secret),
    )
    commitment = commit_c4_review_material(
        bundle.schema,
        operator_policy=policy,
        source_image_sha256=source_hash,
        renderer_id=bundle.commitment.renderer_id,
        model_id=bundle.commitment.model_id,
        model_revision=bundle.commitment.model_revision,
        options=bundle.commitment.options,
    )
    packet = prepare_c4_blind_review(
        bundle.schema,
        commitment,
        operator_policy=policy,
    )
    path_by_hash = {
        item.output_sha256: path
        for item, path in zip(
            bundle.packet.outputs,
            bundle.output_paths,
            strict=True,
        )
    }
    output_paths = tuple(path_by_hash[item.output_sha256] for item in packet.outputs)
    assert len(output_paths) == 2
    return source_path, policy, packet, output_paths  # type: ignore[return-value]


def _judgments(
    packet: C4BlindReviewPacket,
    **overrides: bool,
) -> tuple[C4OutputHumanJudgment, C4OutputHumanJudgment]:
    values = {field: True for field in C4_OUTPUT_POSITIVE_FIELDS}
    values["reviewer_uncertain"] = False
    values.update(overrides)
    result = tuple(
        record_c4_output_human_judgment(
            packet,
            blind_code=reference.blind_code,
            **values,
        )
        for reference in packet.outputs
    )
    assert len(result) == 2
    return result  # type: ignore[return-value]


def _pair(**overrides: bool) -> C4PairHumanJudgment:
    values = {
        "actions_visibly_distinct": True,
        "same_source_bytes_confirmed": True,
    }
    values.update(overrides)
    return C4PairHumanJudgment(**values)


def _external_attestation(
    bundle: ReviewBundle,
    *,
    judgments: tuple[C4OutputHumanJudgment, C4OutputHumanJudgment] | None = None,
    pair: C4PairHumanJudgment | None = None,
    reviewer_pseudonym: str = "reviewer-alpha",
    review_timestamp: datetime = datetime(
        2026,
        7,
        15,
        9,
        30,
        tzinfo=timezone.utc,
    ),
    ledger_lease_sha256: str | None = None,
    signing_secret: bytes | None = None,
):
    claim = build_c4_operator_unsigned_claim(
        bundle.packet,
        operator_policy=bundle.policy,
        presentation_manifest=bundle.presentation,
        reviewer_pseudonym=reviewer_pseudonym,
        review_timestamp=review_timestamp,
        output_judgments=judgments or _judgments(bundle.packet),
        pair_judgment=pair or _pair(),
        external_one_time_ledger_lease_sha256=(
            ledger_lease_sha256 or bundle.ledger_lease_sha256
        ),
    )
    tag = hmac.digest(
        signing_secret or bundle.secret,
        c4_operator_attestation_message(claim),
        "sha256",
    ).hex()
    return claim, build_c4_operator_attestation(
        claim,
        external_hmac_sha256=tag,
    )


def _seal(
    bundle: ReviewBundle,
    *,
    judgment_overrides: dict[str, bool] | None = None,
    pair_overrides: dict[str, bool] | None = None,
    ledger: InMemoryUsedPolicyLedger | None = None,
):
    _, attestation = _external_attestation(
        bundle,
        judgments=_judgments(bundle.packet, **(judgment_overrides or {})),
        pair=_pair(**(pair_overrides or {})),
    )
    return seal_c4_human_review(
        bundle.packet,
        operator_policy=bundle.policy,
        presentation_manifest=bundle.presentation,
        operator_attestation=attestation,
        operator_secret=bundle.secret,
        used_policy_ledger=ledger or bundle.ledger,
    )


def _recontent(model, *, id_field: str, namespace: str):
    base = model.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field},
    )
    return model.model_copy(update={id_field: content_id(namespace, base)})


def _readdress(
    model,
    *,
    id_field: str,
    sha_field: str,
    namespace: str,
):
    base = model.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, sha_field},
    )
    return model.model_copy(
        update={
            id_field: content_id(namespace, base),
            sha_field: _canonical_digest(base),
        }
    )


def test_schema_is_stable_and_operator_policy_is_content_addressed(
    review_bundle: ReviewBundle,
) -> None:
    schema = review_bundle.schema
    policy = review_bundle.policy

    assert schema == build_c4_blind_human_review_schema()
    assert schema.operator_policy_scheme == C4_OPERATOR_POLICY_SCHEME
    assert schema.operator_attestation_claim == C4_OPERATOR_ATTESTATION_CLAIM
    assert schema.human_field_origin == C4_OPERATOR_ENTRY_ORIGIN
    assert schema.external_operator_receipt_required is True
    assert schema.attestation_proves_human_cognition is False
    assert policy.review_schema_id == schema.schema_id
    assert policy.pre_inference_pin_required is True
    assert policy.one_time_issuance_required is True
    assert policy.external_atomic_used_policy_ledger_required is True
    assert policy.minimum_hmac_key_bytes == C4_HMAC_KEY_MIN_BYTES
    assert policy.model_runner_key_access_allowed is False
    assert policy.direct_operator_secret_material_stored_in_artifact is False
    assert policy.attestation_proves_human_cognition is False

    policy_base = policy.model_dump(
        mode="python",
        round_trip=True,
        exclude={"policy_id", "operator_policy_sha256"},
    )
    assert policy.policy_id == content_id("c4_operator_policy", policy_base)
    assert policy.operator_policy_sha256 == _canonical_digest(policy_base)
    assert len(policy.canonical_json_bytes()) < C4_REVIEW_MAX_CANONICAL_BYTES


def test_full_commitment_and_packet_hashes_replay_exactly(
    review_bundle: ReviewBundle,
) -> None:
    commitment = review_bundle.commitment
    packet = review_bundle.packet

    commitment_base = commitment.model_dump(
        mode="python",
        round_trip=True,
        exclude={"commitment_id", "material_commitment_sha256"},
    )
    packet_base = packet.model_dump(
        mode="python",
        round_trip=True,
        exclude={"packet_id", "packet_sha256"},
    )
    assert commitment.commitment_id == content_id(
        "c4_review_material",
        commitment_base,
    )
    assert commitment.material_commitment_sha256 == _canonical_digest(commitment_base)
    assert packet.packet_id == content_id("c4_blind_packet", packet_base)
    assert packet.packet_sha256 == _canonical_digest(packet_base)
    assert packet.material_commitment_sha256 == (commitment.material_commitment_sha256)
    assert packet.operator_policy_sha256 == review_bundle.policy.operator_policy_sha256

    claim, attestation = _external_attestation(review_bundle)
    claim_base = claim.model_dump(
        mode="python",
        round_trip=True,
        exclude={"claim_id", "claim_sha256"},
    )
    attestation_base = attestation.model_dump(
        mode="python",
        round_trip=True,
        exclude={"attestation_id", "attestation_sha256"},
    )
    assert claim.claim_sha256 == _canonical_digest(claim_base)
    assert attestation.attestation_sha256 == _canonical_digest(attestation_base)


def test_blind_codes_use_full_commitment_and_sha256_pair_order(
    review_bundle: ReviewBundle,
) -> None:
    commitment = review_bundle.commitment
    packet = review_bundle.packet

    assert tuple(item.blind_order_sha256 for item in packet.outputs) == tuple(
        sorted(c4_blind_order_sha256(item.blind_code) for item in packet.outputs)
    )
    for reference in packet.outputs:
        assert reference.blind_code == content_id(
            "c4_blind_code",
            {
                "material_commitment_id": commitment.commitment_id,
                "material_commitment_sha256": (commitment.material_commitment_sha256),
                "source_image_sha256": commitment.source_image_sha256,
                "option_id": reference.option_id,
                "instruction_sha256": reference.instruction_sha256,
                "output_sha256": reference.output_sha256,
            },
        )
        assert reference.blind_order_sha256 == _digest(reference.blind_code)


def test_internal_csprng_nonces_are_distinct_and_hidden_from_blind_packet(
    review_bundle: ReviewBundle,
) -> None:
    second_policy = build_c4_human_review_operator_policy(
        review_bundle.schema,
        run_id="c4-stage1-preflight",
        candidate_slot_id="blind-candidate-slot-a",
        source_image_sha256=review_bundle.commitment.source_image_sha256,
        hmac_key_commitment_sha256=_bytes_digest(review_bundle.secret),
    )
    second_commitment = commit_c4_review_material(
        review_bundle.schema,
        operator_policy=review_bundle.policy,
        source_image_sha256=review_bundle.commitment.source_image_sha256,
        renderer_id=review_bundle.commitment.renderer_id,
        model_id=review_bundle.commitment.model_id,
        model_revision=review_bundle.commitment.model_revision,
        options=review_bundle.commitment.options,
    )

    assert second_policy.policy_nonce != review_bundle.policy.policy_nonce
    assert second_policy.policy_id != review_bundle.policy.policy_id
    assert (
        second_commitment.commitment_id != review_bundle.packet.material_commitment_id
    )
    assert second_commitment.material_commitment_sha256 != (
        review_bundle.packet.material_commitment_sha256
    )
    assert len(review_bundle.policy.policy_nonce) == 64
    assert len(review_bundle.commitment.blinding_nonce) == 64
    int(review_bundle.policy.policy_nonce, 16)
    int(review_bundle.commitment.blinding_nonce, 16)
    assert review_bundle.policy.policy_nonce != review_bundle.commitment.blinding_nonce
    assert review_bundle.policy.policy_nonce != review_bundle.secret.hex()
    assert review_bundle.commitment.blinding_nonce != review_bundle.secret.hex()
    assert (
        "policy_nonce"
        not in inspect.signature(build_c4_human_review_operator_policy).parameters
    )
    assert (
        "blinding_nonce" not in inspect.signature(commit_c4_review_material).parameters
    )
    encoded = review_bundle.packet.canonical_json_bytes()
    assert review_bundle.commitment.blinding_nonce.encode() not in encoded
    assert "blinding_nonce" not in json.loads(encoded)
    assert review_bundle.commitment.blinding_nonce not in repr(review_bundle.packet)


def test_first_pass_hides_renderer_model_other_provider_and_secret(
    review_bundle: ReviewBundle,
) -> None:
    encoded = review_bundle.packet.canonical_json_bytes()
    payload = json.loads(encoded)
    commitment = review_bundle.commitment

    assert commitment.renderer_id.encode() not in encoded
    assert commitment.model_id.encode() not in encoded
    assert commitment.model_revision.encode() not in encoded
    assert payload["renderer_identity_structured_field_present"] is False
    assert payload["model_identity_structured_field_present"] is False
    assert payload["other_provider_output_references_present"] is False
    assert payload["pixel_identity_absence_proven"] is False
    assert review_bundle.secret.hex().encode() not in encoded
    assert review_bundle.secret.hex() not in repr(review_bundle.policy)


def test_presentation_manifest_rehashes_pngs_dimensions_and_packet_order(
    review_bundle: ReviewBundle,
) -> None:
    manifest = review_bundle.presentation
    packet = review_bundle.packet

    assert manifest.presentation_policy == C4_PRESENTATION_POLICY
    assert manifest.png_chunk_policy == C4_PRESENTATION_PNG_CHUNK_POLICY
    assert manifest.embedded_metadata_present is False
    assert manifest.cold_validation_reverifies_exact_png_bytes is False
    assert manifest.exact_png_bytes_required_for_reverification is True
    assert manifest.source.decoded_scanlines_verified is True
    assert (manifest.source.width, manifest.source.height) == (4, 3)
    assert manifest.source.image_sha256 == packet.source_image_sha256
    assert tuple(item.blind_code for item in manifest.outputs) == tuple(
        item.blind_code for item in packet.outputs
    )
    assert tuple(item.image_sha256 for item in manifest.outputs) == tuple(
        item.output_sha256 for item in packet.outputs
    )
    assert all((item.width, item.height) == (4, 3) for item in manifest.outputs)
    assert all(item.embedded_metadata_present is False for item in manifest.outputs)
    assert all(item.decoded_scanlines_verified is True for item in manifest.outputs)
    assert manifest.renderer_identity_supplied_label_present is False
    assert manifest.model_identity_supplied_label_present is False
    assert manifest.other_provider_output_supplied_labels_present is False
    assert manifest.presentation_ui_execution_attested is False
    assert manifest.pixel_identity_absence_proven is False

    base = manifest.model_dump(
        mode="python",
        round_trip=True,
        exclude={"presentation_manifest_id", "presentation_manifest_sha256"},
    )
    assert manifest.presentation_manifest_id == content_id("c4_presentation", base)
    assert manifest.presentation_manifest_sha256 == _canonical_digest(base)


def test_presentation_reader_uses_no_path_read_bytes(
    review_bundle: ReviewBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_read_bytes(_path: Path) -> bytes:
        raise AssertionError("Path.read_bytes must not serve presentation PNGs")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read_bytes)

    manifest = build_c4_blind_presentation_manifest(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        source_png_path=review_bundle.source_path,
        output_png_paths=review_bundle.output_paths,
    )

    assert manifest == review_bundle.presentation


def test_presentation_reader_bounds_growth_to_initial_size_plus_one(
    review_bundle: ReviewBundle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_read = c4_blind_review_module.os.read
    source_stat = review_bundle.source_path.stat()
    source_identity = (source_stat.st_dev, source_stat.st_ino)
    requested_sizes: list[int] = []
    returned_sizes: list[int] = []
    appended = False

    def grow_after_first_read(descriptor: int, requested_size: int) -> bytes:
        nonlocal appended
        chunk = real_read(descriptor, requested_size)
        descriptor_stat = c4_blind_review_module.os.fstat(descriptor)
        if (descriptor_stat.st_dev, descriptor_stat.st_ino) == source_identity:
            requested_sizes.append(requested_size)
            returned_sizes.append(len(chunk))
            if not appended:
                with review_bundle.source_path.open("ab") as stream:
                    stream.write(b"x")
                appended = True
        return chunk

    monkeypatch.setattr(c4_blind_review_module.os, "read", grow_after_first_read)

    with pytest.raises(ValueError, match="changed during bounded exact byte read"):
        build_c4_blind_presentation_manifest(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            source_png_path=review_bundle.source_path,
            output_png_paths=review_bundle.output_paths,
        )

    assert appended is True
    assert requested_sizes
    assert max(requested_sizes) <= source_stat.st_size + 1
    assert sum(returned_sizes) == source_stat.st_size + 1
    assert sum(returned_sizes) <= C4_PRESENTATION_MAX_PNG_BYTES + 1


def test_presentation_reader_rejects_post_open_path_identity_swap(
    review_bundle: ReviewBundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replacement_path = tmp_path / "replacement-source.png"
    replacement_path.write_bytes(_png_bytes(4, 3, (200, 201, 202)))
    replacement_stat = replacement_path.stat()
    real_stat = c4_blind_review_module.os.stat
    simulated_swap_observed = False

    def swapped_path_stat(path: object, *args: object, **kwargs: object) -> object:
        nonlocal simulated_swap_observed
        if path == review_bundle.source_path:
            simulated_swap_observed = True
            return replacement_stat
        return real_stat(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(c4_blind_review_module.os, "stat", swapped_path_stat)

    with pytest.raises(ValueError, match="changed during bounded exact byte read"):
        build_c4_blind_presentation_manifest(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            source_png_path=review_bundle.source_path,
            output_png_paths=review_bundle.output_paths,
        )

    assert simulated_swap_observed is True


def test_presentation_reader_rejects_oversize_before_any_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oversized_path = tmp_path / "oversized.png"
    with oversized_path.open("wb") as stream:
        stream.truncate(C4_PRESENTATION_MAX_PNG_BYTES + 1)
    read_called = False

    def forbidden_read(_descriptor: int, _requested_size: int) -> bytes:
        nonlocal read_called
        read_called = True
        raise AssertionError("oversized regular files must not be read")

    monkeypatch.setattr(c4_blind_review_module.os, "read", forbidden_read)

    with pytest.raises(ValueError, match="byte size is outside bounds"):
        c4_blind_review_module._read_bounded_regular_file(oversized_path)

    assert read_called is False


def test_fragmented_idat_stream_is_validated_without_joining_chunks(
    review_bundle: ReviewBundle,
    tmp_path: Path,
) -> None:
    width, height = 4, 3
    rows = (b"\x00" + bytes((5, 6, 7)) * width) * height
    compressed = zlib.compress(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    source_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + b"".join(_png_chunk(b"IDAT", bytes((byte,))) for byte in compressed)
        + _png_chunk(b"IEND", b"")
    )
    source_path, policy, packet, output_paths = _presentation_inputs_for_source(
        review_bundle,
        tmp_path,
        source_bytes=source_bytes,
        label="fragmented-idat",
    )

    manifest = build_c4_blind_presentation_manifest(
        packet,
        operator_policy=policy,
        source_png_path=source_path,
        output_png_paths=output_paths,
    )

    assert manifest.source.image_sha256 == _bytes_digest(source_bytes)
    assert manifest.source.decoded_scanlines_verified is True


def test_valid_png_with_cap_plus_one_chunks_fails_closed(
    review_bundle: ReviewBundle,
    tmp_path: Path,
) -> None:
    width = 256
    row = b"\x00" + bytes((5, 6, 7)) * width
    height = (C4_PRESENTATION_MAX_PNG_CHUNKS + len(row)) // len(row) + 1
    compressed = zlib.compress(row * height, level=0)
    idat_count = C4_PRESENTATION_MAX_PNG_CHUNKS - 1
    assert len(compressed) >= idat_count
    idat_payloads = (
        *(bytes((byte,)) for byte in compressed[: idat_count - 1]),
        compressed[idat_count - 1 :],
    )
    assert len(idat_payloads) == idat_count
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    source_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + b"".join(_png_chunk(b"IDAT", payload) for payload in idat_payloads)
        + _png_chunk(b"IEND", b"")
    )
    source_path, policy, packet, output_paths = _presentation_inputs_for_source(
        review_bundle,
        tmp_path,
        source_bytes=source_bytes,
        label="chunk-cap-plus-one",
    )

    with pytest.raises(ValueError, match="fixed chunk-count bound"):
        build_c4_blind_presentation_manifest(
            packet,
            operator_policy=policy,
            source_png_path=source_path,
            output_png_paths=output_paths,
        )


def test_post_manifest_png_substitution_remains_an_explicit_stage1_blocker(
    review_bundle: ReviewBundle,
) -> None:
    """Foundation sealing preserves history but does not attest displayed bytes."""

    manifest = review_bundle.presentation
    historical_manifest_bytes = manifest.canonical_json_bytes()
    historical_output_hashes = tuple(item.image_sha256 for item in manifest.outputs)
    replacement_pngs = (
        _png_bytes(4, 3, (180, 90, 40)),
        _png_bytes(4, 3, (40, 90, 180)),
    )
    for path, replacement in zip(
        review_bundle.output_paths,
        replacement_pngs,
        strict=True,
    ):
        path.write_bytes(replacement)

    current_output_hashes = tuple(
        _bytes_digest(path.read_bytes()) for path in review_bundle.output_paths
    )
    assert current_output_hashes != historical_output_hashes
    assert manifest.canonical_json_bytes() == historical_manifest_bytes
    assert manifest.presentation_ui_execution_attested is False
    assert manifest.cold_validation_reverifies_exact_png_bytes is False

    submission = _seal(review_bundle)
    gate = evaluate_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
        submission=submission,
    )

    assert submission.presentation_manifest == manifest
    assert submission.human_review_passed is True
    assert submission.semantic_quality_gate_passed is False
    assert submission.production_authority_granted is False
    assert gate.semantic_quality_gate_passed is False
    assert gate.production_authority_granted is False


def test_png_tamper_order_and_hidden_flag_changes_fail_closed(
    review_bundle: ReviewBundle,
) -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        build_c4_blind_presentation_manifest(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            source_png_path=review_bundle.source_path,
            output_png_paths=tuple(reversed(review_bundle.output_paths)),
        )

    first_path = review_bundle.output_paths[0]
    first_path.write_bytes(first_path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA-256"):
        build_c4_blind_presentation_manifest(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            source_png_path=review_bundle.source_path,
            output_png_paths=review_bundle.output_paths,
        )

    payload = review_bundle.presentation.model_dump(mode="python", round_trip=True)
    payload["renderer_identity_supplied_label_present"] = True
    with pytest.raises(ValidationError, match="False"):
        C4BlindPresentationManifest.model_validate(payload)


def test_non_png_with_matching_pinned_hash_fails_structure_validation(
    review_bundle: ReviewBundle,
    tmp_path: Path,
) -> None:
    invalid_source = tmp_path / "invalid.png"
    invalid_source.write_bytes(b"not-a-png-but-byte-pinned")
    source_hash = _bytes_digest(invalid_source.read_bytes())
    policy = build_c4_human_review_operator_policy(
        review_bundle.schema,
        run_id="invalid-png-run",
        candidate_slot_id="blind-invalid-png-slot",
        source_image_sha256=source_hash,
        hmac_key_commitment_sha256=_bytes_digest(review_bundle.secret),
    )
    commitment = commit_c4_review_material(
        review_bundle.schema,
        operator_policy=policy,
        source_image_sha256=source_hash,
        renderer_id=review_bundle.commitment.renderer_id,
        model_id=review_bundle.commitment.model_id,
        model_revision=review_bundle.commitment.model_revision,
        options=review_bundle.commitment.options,
    )
    packet = prepare_c4_blind_review(
        review_bundle.schema,
        commitment,
        operator_policy=policy,
    )
    path_by_hash = {
        item.output_sha256: path
        for item, path in zip(
            review_bundle.packet.outputs,
            review_bundle.output_paths,
            strict=True,
        )
    }
    ordered_paths = tuple(path_by_hash[item.output_sha256] for item in packet.outputs)
    with pytest.raises(ValueError, match="not an exact PNG"):
        build_c4_blind_presentation_manifest(
            packet,
            operator_policy=policy,
            source_png_path=invalid_source,
            output_png_paths=ordered_paths,
        )


def test_crc_tampered_png_with_matching_pinned_hash_fails(
    review_bundle: ReviewBundle,
    tmp_path: Path,
) -> None:
    corrupted = bytearray(_png_bytes(4, 3, (5, 6, 7)))
    idat_index = corrupted.find(b"IDAT")
    assert idat_index > 0
    corrupted[idat_index + 4] ^= 0x01
    source_path = tmp_path / "crc-tampered.png"
    source_path.write_bytes(corrupted)
    source_hash = _bytes_digest(bytes(corrupted))
    policy = build_c4_human_review_operator_policy(
        review_bundle.schema,
        run_id="crc-tamper-run",
        candidate_slot_id="blind-crc-slot",
        source_image_sha256=source_hash,
        hmac_key_commitment_sha256=_bytes_digest(review_bundle.secret),
    )
    commitment = commit_c4_review_material(
        review_bundle.schema,
        operator_policy=policy,
        source_image_sha256=source_hash,
        renderer_id=review_bundle.commitment.renderer_id,
        model_id=review_bundle.commitment.model_id,
        model_revision=review_bundle.commitment.model_revision,
        options=review_bundle.commitment.options,
    )
    packet = prepare_c4_blind_review(
        review_bundle.schema,
        commitment,
        operator_policy=policy,
    )
    path_by_hash = {
        item.output_sha256: path
        for item, path in zip(
            review_bundle.packet.outputs,
            review_bundle.output_paths,
            strict=True,
        )
    }
    ordered_paths = tuple(path_by_hash[item.output_sha256] for item in packet.outputs)
    with pytest.raises(ValueError, match="invalid chunk CRC"):
        build_c4_blind_presentation_manifest(
            packet,
            operator_policy=policy,
            source_png_path=source_path,
            output_png_paths=ordered_paths,
        )


@pytest.mark.parametrize("metadata_chunk", (b"tEXt", b"iTXt", b"zTXt", b"eXIf"))
def test_identity_bearing_png_metadata_with_matching_hash_fails_closed(
    review_bundle: ReviewBundle,
    tmp_path: Path,
    metadata_chunk: bytes,
) -> None:
    width, height = 4, 3
    row = b"\x00" + bytes((5, 6, 7)) * width
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    source_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(metadata_chunk, b"Software\x00provider=renderer-model")
        + _png_chunk(b"IDAT", zlib.compress(row * height))
        + _png_chunk(b"IEND", b"")
    )
    source_path = tmp_path / f"metadata-{metadata_chunk.decode('ascii')}.png"
    source_path.write_bytes(source_bytes)
    source_hash = _bytes_digest(source_bytes)
    suffix = metadata_chunk.decode("ascii")
    policy = build_c4_human_review_operator_policy(
        review_bundle.schema,
        run_id=f"metadata-{suffix}-run",
        candidate_slot_id=f"blind-metadata-{suffix}-slot",
        source_image_sha256=source_hash,
        hmac_key_commitment_sha256=_bytes_digest(review_bundle.secret),
    )
    commitment = commit_c4_review_material(
        review_bundle.schema,
        operator_policy=policy,
        source_image_sha256=source_hash,
        renderer_id=review_bundle.commitment.renderer_id,
        model_id=review_bundle.commitment.model_id,
        model_revision=review_bundle.commitment.model_revision,
        options=review_bundle.commitment.options,
    )
    packet = prepare_c4_blind_review(
        review_bundle.schema,
        commitment,
        operator_policy=policy,
    )
    path_by_hash = {
        item.output_sha256: path
        for item, path in zip(
            review_bundle.packet.outputs,
            review_bundle.output_paths,
            strict=True,
        )
    }
    ordered_paths = tuple(path_by_hash[item.output_sha256] for item in packet.outputs)

    with pytest.raises(ValueError, match="forbidden metadata"):
        build_c4_blind_presentation_manifest(
            packet,
            operator_policy=policy,
            source_png_path=source_path,
            output_png_paths=ordered_paths,
        )


@pytest.mark.parametrize(
    ("case", "ihdr_tail", "idat_kind"),
    (
        ("zero-bit-depth", (0, 2, 0, 0, 0), "valid"),
        ("indexed-color", (8, 3, 0, 0, 0), "valid"),
        ("wrong-compression", (8, 2, 1, 0, 0), "valid"),
        ("wrong-filter-method", (8, 2, 0, 1, 0), "valid"),
        ("interlaced", (8, 2, 0, 0, 1), "valid"),
        ("empty-idat", (8, 2, 0, 0, 0), "empty"),
        ("invalid-zlib", (8, 2, 0, 0, 0), "invalid-zlib"),
        ("short-scanlines", (8, 2, 0, 0, 0), "short"),
        ("invalid-filter-byte", (8, 2, 0, 0, 0), "invalid-filter"),
    ),
)
def test_matching_hash_semantically_invalid_png_fails_closed(
    review_bundle: ReviewBundle,
    tmp_path: Path,
    case: str,
    ihdr_tail: tuple[int, int, int, int, int],
    idat_kind: str,
) -> None:
    width, height = 4, 3
    valid_rows = (b"\x00" + bytes((5, 6, 7)) * width) * height
    idat_payload = {
        "valid": zlib.compress(valid_rows),
        "empty": b"",
        "invalid-zlib": b"not-a-zlib-stream",
        "short": zlib.compress(b"\x00"),
        "invalid-filter": zlib.compress((b"\x05" + bytes((5, 6, 7)) * width) * height),
    }[idat_kind]
    ihdr = struct.pack(">II", width, height) + bytes(ihdr_tail)
    source_bytes = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat_payload)
        + _png_chunk(b"IEND", b"")
    )
    source_path, policy, packet, output_paths = _presentation_inputs_for_source(
        review_bundle,
        tmp_path,
        source_bytes=source_bytes,
        label=case,
    )

    with pytest.raises(
        ValueError,
        match=(
            "non-interlaced 8-bit RGB or RGBA|empty IDAT|IDAT stream|"
            "decoded scanline size|scanline filter"
        ),
    ):
        build_c4_blind_presentation_manifest(
            packet,
            operator_policy=policy,
            source_png_path=source_path,
            output_png_paths=output_paths,
        )


def test_valid_external_receipt_seals_exact_claim_and_passes(
    review_bundle: ReviewBundle,
) -> None:
    claim, attestation = _external_attestation(review_bundle)
    verified = verify_c4_operator_attestation(
        review_bundle.policy,
        attestation,
        operator_secret=review_bundle.secret,
    )
    submission = seal_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        presentation_manifest=review_bundle.presentation,
        operator_attestation=attestation,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )

    assert verified == attestation
    assert claim.operator_attestation_claim == C4_OPERATOR_ATTESTATION_CLAIM
    assert submission.operator_attestation_claim == C4_OPERATOR_ATTESTATION_CLAIM
    assert submission.human_field_origin == C4_OPERATOR_ATTESTATION_CLAIM
    assert claim.attestation_proves_human_cognition is False
    assert attestation.attestation_proves_human_cognition is False
    assert submission.attestation_proves_human_cognition is False
    assert submission.operator_receipt_secret_reverification_required is True
    assert submission.external_ledger_reverification_required is True
    assert submission.cold_validation_authenticates_operator_receipt is False
    assert submission.cold_validation_proves_live_ledger_state is False
    assert submission.human_review_passed is True
    assert submission.semantic_quality_gate_passed is False
    assert submission.production_authority_granted is False
    assert len(submission.canonical_json_bytes()) < C4_REVIEW_MAX_CANONICAL_BYTES


def test_external_atomic_ledger_consumes_policy_and_lease_once(
    review_bundle: ReviewBundle,
) -> None:
    claim, attestation = _external_attestation(review_bundle)
    submission = seal_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        presentation_manifest=review_bundle.presentation,
        operator_attestation=attestation,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    receipt = submission.consumed_policy_receipt
    receipt_base = receipt.model_dump(
        mode="python",
        round_trip=True,
        exclude={"consumed_receipt_id", "consumed_receipt_sha256"},
    )
    assert receipt.operator_policy_id == review_bundle.policy.policy_id
    assert receipt.external_one_time_ledger_lease_sha256 == (
        claim.external_one_time_ledger_lease_sha256
    )
    assert receipt.claim_sha256 == claim.claim_sha256
    assert receipt.attestation_sha256 == attestation.attestation_sha256
    assert receipt.attestation_hmac_sha256 == attestation.hmac_sha256
    assert receipt.consumed_receipt_id == content_id(
        "c4_consumed_policy_receipt",
        receipt_base,
    )
    assert receipt.consumed_receipt_sha256 == _canonical_digest(receipt_base)
    assert receipt.consumed_receipt_id.encode() not in claim.canonical_json_bytes()
    assert b"external_transaction" not in claim.canonical_json_bytes()
    assert receipt.cold_validation_proves_live_ledger_state is False
    assert receipt.live_external_ledger_reverification_required is True

    with pytest.raises(ValueError, match="already consumed"):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=attestation,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )

    _, alternate_lease_attestation = _external_attestation(
        review_bundle,
        ledger_lease_sha256=_digest("alternate-one-time-ledger-lease"),
    )
    with pytest.raises(ValueError, match="already consumed"):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=alternate_lease_attestation,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )

    _, alternate_attestation = _external_attestation(
        review_bundle,
        judgments=_judgments(review_bundle.packet, identity_preserved=False),
    )
    with pytest.raises(ValueError, match="already consumed"):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=alternate_attestation,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )


def test_external_atomic_ledger_rejects_concurrent_double_consume(
    review_bundle: ReviewBundle,
) -> None:
    _, attestation = _external_attestation(review_bundle)
    ledger = InMemoryUsedPolicyLedger()

    def attempt(_: int) -> str:
        try:
            seal_c4_human_review(
                review_bundle.packet,
                operator_policy=review_bundle.policy,
                presentation_manifest=review_bundle.presentation,
                operator_attestation=attestation,
                operator_secret=review_bundle.secret,
                used_policy_ledger=ledger,
            )
        except ValueError as exc:
            assert "already consumed" in str(exc)
            return "rejected"
        return "sealed"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(attempt, range(2)))
    assert sorted(outcomes) == ["rejected", "sealed"]


def test_forged_or_mismatched_ledger_receipt_fails_live_replay(
    review_bundle: ReviewBundle,
) -> None:
    submission = _seal(review_bundle)
    receipt = submission.consumed_policy_receipt
    forged_receipt = _readdress(
        receipt.model_copy(update={"external_transaction_id": "forged-transaction"}),
        id_field="consumed_receipt_id",
        sha_field="consumed_receipt_sha256",
        namespace="c4_consumed_policy_receipt",
    )
    forged_submission = _recontent(
        submission.model_copy(update={"consumed_policy_receipt": forged_receipt}),
        id_field="submission_id",
        namespace="c4_human_review",
    )
    forged_submission = type(submission).model_validate(
        forged_submission.model_dump(mode="python", round_trip=True)
    )
    assert forged_submission.cold_validation_proves_live_ledger_state is False

    with pytest.raises(ValueError, match="external ledger did not verify"):
        evaluate_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
            submission=forged_submission,
        )
    with pytest.raises(ValueError, match="external ledger did not verify"):
        reveal_c4_review_identities(
            forged_submission,
            material_commitment=review_bundle.commitment,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )

    _, alternate_attestation = _external_attestation(
        review_bundle,
        judgments=_judgments(review_bundle.packet, identity_preserved=False),
    )
    mismatched_receipt = record_c4_consumed_operator_policy_receipt(
        review_bundle.policy,
        alternate_attestation,
        external_transaction_id="mismatched-transaction",
        external_transaction_timestamp=datetime(
            2026, 7, 15, 10, 5, tzinfo=timezone.utc
        ),
    )
    mismatched_submission = _recontent(
        submission.model_copy(update={"consumed_policy_receipt": mismatched_receipt}),
        id_field="submission_id",
        namespace="c4_human_review",
    )
    with pytest.raises(ValidationError, match="consumed receipt differs"):
        type(submission).model_validate(
            mismatched_submission.model_dump(mode="python", round_trip=True)
        )


def test_unavailable_or_missing_external_ledger_fails_closed(
    review_bundle: ReviewBundle,
) -> None:
    _, attestation = _external_attestation(review_bundle)
    with pytest.raises(TypeError, match="used_policy_ledger"):
        seal_c4_human_review(  # type: ignore[call-arg]
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=attestation,
            operator_secret=review_bundle.secret,
        )
    submission = _seal(review_bundle)
    with pytest.raises(TypeError, match="used_policy_ledger"):
        evaluate_c4_human_review(  # type: ignore[call-arg]
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            operator_secret=review_bundle.secret,
            submission=submission,
        )
    with pytest.raises(TypeError, match="used_policy_ledger"):
        reveal_c4_review_identities(  # type: ignore[call-arg]
            submission,
            material_commitment=review_bundle.commitment,
            operator_secret=review_bundle.secret,
        )

    review_bundle.ledger.available = False
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        evaluate_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
            submission=submission,
        )
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        reveal_c4_review_identities(
            submission,
            material_commitment=review_bundle.commitment,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )


def test_raw_or_hex_operator_secret_material_cannot_enter_sealed_artifacts(
    review_bundle: ReviewBundle,
) -> None:
    _, leaking_attestation = _external_attestation(
        review_bundle,
        ledger_lease_sha256=review_bundle.secret.hex(),
    )
    with pytest.raises(ValueError, match="forbidden direct operator-secret material"):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=leaking_attestation,
            operator_secret=review_bundle.secret,
            used_policy_ledger=InMemoryUsedPolicyLedger(),
        )


def test_covert_secret_encoding_is_a_trusted_external_text_boundary(
    review_bundle: ReviewBundle,
) -> None:
    encoded_pseudonym = base64.urlsafe_b64encode(review_bundle.secret).decode("ascii")
    _, attestation = _external_attestation(
        review_bundle,
        reviewer_pseudonym=encoded_pseudonym,
    )

    submission = seal_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        presentation_manifest=review_bundle.presentation,
        operator_attestation=attestation,
        operator_secret=review_bundle.secret,
        used_policy_ledger=InMemoryUsedPolicyLedger(),
    )

    assert submission.reviewer_pseudonym == encoded_pseudonym
    assert encoded_pseudonym.encode("ascii") in submission.canonical_json_bytes()
    assert base64.urlsafe_b64decode(encoded_pseudonym) == review_bundle.secret
    assert (
        submission.operator_policy.direct_operator_secret_material_stored_in_artifact
        is False
    )
    assert (
        submission.operator_attestation.direct_operator_secret_material_stored_in_artifact
        is False
    )
    assert submission.attestation_proves_human_cognition is False


def test_gate_and_reveal_reject_removed_live_ledger_state(
    review_bundle: ReviewBundle,
) -> None:
    submission = _seal(review_bundle)
    claim = submission.operator_attestation.claim
    review_bundle.ledger.remove_live_entry(
        review_bundle.policy.policy_id,
        claim.external_one_time_ledger_lease_sha256,
    )

    with pytest.raises(ValueError, match="external ledger did not verify"):
        evaluate_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
            submission=submission,
        )
    with pytest.raises(ValueError, match="external ledger did not verify"):
        reveal_c4_review_identities(
            submission,
            material_commitment=review_bundle.commitment,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )


def test_receipt_never_claims_to_prove_human_cognition(
    review_bundle: ReviewBundle,
) -> None:
    judgments = _judgments(review_bundle.packet)
    pair = _pair()
    claim, attestation = _external_attestation(
        review_bundle,
        judgments=judgments,
        pair=pair,
    )
    submission = seal_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        presentation_manifest=review_bundle.presentation,
        operator_attestation=attestation,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    gate = evaluate_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
        submission=submission,
    )
    reveal = reveal_c4_review_identities(
        submission,
        material_commitment=review_bundle.commitment,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    artifacts = (
        review_bundle.schema,
        review_bundle.policy,
        *judgments,
        pair,
        claim,
        attestation,
        submission.consumed_policy_receipt,
        submission,
        gate,
        reveal,
    )

    assert b'"attestation_proves_human_cognition":false' in (
        claim.canonical_json_bytes()
    )
    assert b"human_reviewer" not in claim.canonical_json_bytes()
    for artifact in artifacts:
        assert artifact.attestation_proves_human_cognition is False
        payload = artifact.model_dump(mode="python", round_trip=True)
        payload["attestation_proves_human_cognition"] = True
        with pytest.raises(ValidationError, match="False"):
            type(artifact).model_validate(payload)


def test_model_literals_or_missing_secret_cannot_seal(
    review_bundle: ReviewBundle,
) -> None:
    _, attestation = _external_attestation(review_bundle)

    with pytest.raises(TypeError, match="operator_secret"):
        seal_c4_human_review(  # type: ignore[call-arg]
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=attestation,
            used_policy_ledger=review_bundle.ledger,
        )
    with pytest.raises(TypeError, match="must be bytes"):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=attestation,
            operator_secret=None,  # type: ignore[arg-type]
            used_policy_ledger=review_bundle.ledger,
        )
    with pytest.raises(TypeError):
        seal_c4_human_review(  # type: ignore[call-arg]
            review_bundle.packet,
            reviewer_pseudonym="model-caller",
            review_timestamp=datetime.now(timezone.utc),
            output_judgments=_judgments(review_bundle.packet),
            pair_judgment=_pair(),
        )


@pytest.mark.parametrize(
    "secret",
    [b"short", b"x" * (C4_HMAC_KEY_MAX_BYTES + 1)],
)
def test_operator_secret_bounds_fail_closed(
    review_bundle: ReviewBundle,
    secret: bytes,
) -> None:
    _, attestation = _external_attestation(review_bundle)
    with pytest.raises(ValueError, match="byte length"):
        verify_c4_operator_attestation(
            review_bundle.policy,
            attestation,
            operator_secret=secret,
        )


def test_wrong_secret_and_receipt_tag_substitution_fail_closed(
    review_bundle: ReviewBundle,
) -> None:
    claim, attestation = _external_attestation(review_bundle)
    wrong_secret = bytes(range(33, 65))
    with pytest.raises(ValueError, match="pinned policy"):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=attestation,
            operator_secret=wrong_secret,
            used_policy_ledger=review_bundle.ledger,
        )

    substituted = build_c4_operator_attestation(
        claim,
        external_hmac_sha256=_digest("substituted-receipt"),
    )
    with pytest.raises(
        ValueError,
        match="HMAC verification failed|consumed receipt differs",
    ):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=substituted,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )


@pytest.mark.parametrize("tamper_kind", ["timestamp", "judgment", "ledger"])
def test_signed_claim_timestamp_judgment_and_ledger_tamper_fail(
    review_bundle: ReviewBundle,
    tamper_kind: str,
) -> None:
    claim, attestation = _external_attestation(review_bundle)
    if tamper_kind == "timestamp":
        tampered_claim = claim.model_copy(
            update={
                "review_timestamp": claim.review_timestamp + timedelta(seconds=1),
            }
        )
    elif tamper_kind == "judgment":
        changed = claim.output_judgments[0].model_copy(
            update={"identity_preserved": False}
        )
        tampered_claim = claim.model_copy(
            update={"output_judgments": (changed, claim.output_judgments[1])}
        )
    else:
        tampered_claim = claim.model_copy(
            update={
                "external_one_time_ledger_lease_sha256": _digest(
                    "different-ledger-entry"
                )
            }
        )
    tampered_claim = _readdress(
        tampered_claim,
        id_field="claim_id",
        sha_field="claim_sha256",
        namespace="c4_review_claim",
    )
    substituted = build_c4_operator_attestation(
        tampered_claim,
        external_hmac_sha256=attestation.hmac_sha256,
    )
    with pytest.raises(
        ValueError,
        match="HMAC verification failed|consumed receipt differs",
    ):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=substituted,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )


def test_policy_substitution_and_cross_packet_receipt_replay_fail(
    review_bundle: ReviewBundle,
) -> None:
    _, attestation = _external_attestation(review_bundle)
    other_secret = bytes(range(65, 97))
    other_policy = build_c4_human_review_operator_policy(
        review_bundle.schema,
        run_id="other-run",
        candidate_slot_id="other-blind-slot",
        source_image_sha256=review_bundle.packet.source_image_sha256,
        hmac_key_commitment_sha256=_bytes_digest(other_secret),
    )
    with pytest.raises(ValueError, match="pinned policy|operator policy"):
        seal_c4_human_review(
            review_bundle.packet,
            operator_policy=other_policy,
            presentation_manifest=review_bundle.presentation,
            operator_attestation=attestation,
            operator_secret=other_secret,
            used_policy_ledger=review_bundle.ledger,
        )

    second_commitment = commit_c4_review_material(
        review_bundle.schema,
        operator_policy=review_bundle.policy,
        source_image_sha256=review_bundle.packet.source_image_sha256,
        renderer_id=review_bundle.commitment.renderer_id,
        model_id=review_bundle.commitment.model_id,
        model_revision=review_bundle.commitment.model_revision,
        options=review_bundle.commitment.options,
    )
    second_packet = prepare_c4_blind_review(
        review_bundle.schema,
        second_commitment,
        operator_policy=review_bundle.policy,
    )
    paths_by_hash = {
        item.output_sha256: path
        for item, path in zip(
            review_bundle.packet.outputs,
            review_bundle.output_paths,
            strict=True,
        )
    }
    second_paths = tuple(
        paths_by_hash[item.output_sha256] for item in second_packet.outputs
    )
    second_presentation = build_c4_blind_presentation_manifest(
        second_packet,
        operator_policy=review_bundle.policy,
        source_png_path=review_bundle.source_path,
        output_png_paths=second_paths,
    )
    with pytest.raises(
        ValueError,
        match="differs from sealed review material|differs from its blind binding",
    ):
        seal_c4_human_review(
            second_packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=second_presentation,
            operator_attestation=attestation,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )


def test_human_pass_replays_every_output_pair_boolean_and_uncertainty(
    review_bundle: ReviewBundle,
) -> None:
    passed = _seal(review_bundle, ledger=InMemoryUsedPolicyLedger())
    failed_output = _seal(
        review_bundle,
        judgment_overrides={"identity_preserved": False},
        ledger=InMemoryUsedPolicyLedger(),
    )
    uncertain = _seal(
        review_bundle,
        judgment_overrides={"reviewer_uncertain": True},
        ledger=InMemoryUsedPolicyLedger(),
    )
    failed_pair = _seal(
        review_bundle,
        pair_overrides={"actions_visibly_distinct": False},
        ledger=InMemoryUsedPolicyLedger(),
    )

    assert passed.human_review_passed is True
    assert failed_output.human_review_passed is False
    assert uncertain.human_review_passed is False
    assert failed_pair.human_review_passed is False


def test_strict_human_fields_and_model_copy_tamper_fail_before_receipt(
    review_bundle: ReviewBundle,
) -> None:
    judgments = _judgments(review_bundle.packet)
    non_boolean = judgments[0].model_copy(update={"source_subject_present": "true"})
    with pytest.warns(UserWarning), pytest.raises(ValidationError, match="boolean"):
        build_c4_operator_unsigned_claim(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            reviewer_pseudonym="reviewer-alpha",
            review_timestamp=datetime.now(timezone.utc),
            output_judgments=(non_boolean, judgments[1]),
            pair_judgment=_pair(),
            external_one_time_ledger_lease_sha256=(review_bundle.ledger_lease_sha256),
        )

    model_sourced = judgments[0].model_copy(
        update={"human_field_origin": "model_judge", "model_judge_calls": 1}
    )
    with pytest.raises(
        ValidationError,
        match="external_operator_manual_entry_unverified|Input should be 0",
    ):
        build_c4_operator_unsigned_claim(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            reviewer_pseudonym="reviewer-alpha",
            review_timestamp=datetime.now(timezone.utc),
            output_judgments=(model_sourced, judgments[1]),
            pair_judgment=_pair(),
            external_one_time_ledger_lease_sha256=(review_bundle.ledger_lease_sha256),
        )


def test_operator_timestamp_normalizes_to_utc_and_all_bindings_are_exact(
    review_bundle: ReviewBundle,
) -> None:
    local_time = datetime(
        2026,
        7,
        15,
        11,
        30,
        tzinfo=timezone(timedelta(hours=2)),
    )
    claim, attestation = _external_attestation(
        review_bundle,
        review_timestamp=local_time,
    )
    submission = seal_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        presentation_manifest=review_bundle.presentation,
        operator_attestation=attestation,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    expected = datetime(2026, 7, 15, 9, 30, tzinfo=timezone.utc)

    assert claim.review_timestamp == expected
    assert submission.review_timestamp == expected
    assert submission.operator_policy == review_bundle.policy
    assert submission.presentation_manifest == review_bundle.presentation
    assert tuple(item.blind_code for item in submission.output_judgments) == tuple(
        item.blind_code for item in review_bundle.packet.outputs
    )


def test_gate_requires_secret_and_reverifies_receipt_for_all_statuses(
    review_bundle: ReviewBundle,
) -> None:
    submission = _seal(review_bundle)
    missing = evaluate_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    skipped = evaluate_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
        skipped=True,
    )
    sealed = evaluate_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
        submission=submission,
    )

    assert (missing.review_status, missing.human_review_passed) == ("missing", False)
    assert missing.operator_receipt_status == "not_applicable_missing"
    assert (skipped.review_status, skipped.human_review_passed) == ("skipped", False)
    assert skipped.operator_receipt_status == "not_applicable_skipped"
    assert (sealed.review_status, sealed.human_review_passed) == (
        "sealed_submission",
        True,
    )
    assert sealed.operator_receipt_status == (
        "requires_runtime_secret_and_ledger_reverification"
    )

    with pytest.raises(TypeError, match="operator_secret"):
        evaluate_c4_human_review(  # type: ignore[call-arg]
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            used_policy_ledger=review_bundle.ledger,
        )
    with pytest.raises(ValueError, match="pinned policy"):
        evaluate_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            operator_secret=bytes(range(33, 65)),
            used_policy_ledger=review_bundle.ledger,
            submission=submission,
        )


def test_cold_artifacts_do_not_claim_hmac_or_live_ledger_authentication(
    review_bundle: ReviewBundle,
) -> None:
    submission = _seal(review_bundle)
    gate = evaluate_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
        submission=submission,
    )
    reveal = reveal_c4_review_identities(
        submission,
        material_commitment=review_bundle.commitment,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    bad_attestation = build_c4_operator_attestation(
        submission.operator_attestation.claim,
        external_hmac_sha256=_digest("bad-post-seal-tag"),
    )
    bad_receipt = record_c4_consumed_operator_policy_receipt(
        review_bundle.policy,
        bad_attestation,
        external_transaction_id="forged-hmac-transaction",
        external_transaction_timestamp=datetime(
            2026, 7, 15, 10, 6, tzinfo=timezone.utc
        ),
    )
    tampered = submission.model_copy(
        update={
            "operator_attestation": bad_attestation,
            "consumed_policy_receipt": bad_receipt,
        }
    )
    tampered = _recontent(
        tampered,
        id_field="submission_id",
        namespace="c4_human_review",
    )
    tampered = type(submission).model_validate(
        tampered.model_dump(mode="python", round_trip=True)
    )
    cold_gate = _recontent(
        gate.model_copy(update={"submission": tampered}),
        id_field="gate_result_id",
        namespace="c4_review_gate",
    )
    cold_gate = type(gate).model_validate(
        cold_gate.model_dump(mode="python", round_trip=True)
    )
    cold_reveal = _recontent(
        reveal.model_copy(update={"submission": tampered}),
        id_field="reveal_id",
        namespace="c4_review_reveal",
    )
    cold_reveal = type(reveal).model_validate(
        cold_reveal.model_dump(mode="python", round_trip=True)
    )
    for artifact in (tampered, cold_gate, cold_reveal):
        assert artifact.cold_validation_authenticates_operator_receipt is False
        assert artifact.cold_validation_proves_live_ledger_state is False
        assert (
            b'"operator_receipt_verified":true' not in artifact.canonical_json_bytes()
        )
    assert cold_gate.operator_receipt_status == (
        "requires_runtime_secret_and_ledger_reverification"
    )

    with pytest.raises(ValueError, match="HMAC verification failed"):
        evaluate_c4_human_review(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
            submission=tampered,
        )
    with pytest.raises(ValueError, match="HMAC verification failed"):
        reveal_c4_review_identities(
            tampered,
            material_commitment=review_bundle.commitment,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )


def test_identity_reveal_requires_exact_secret_submission_and_commitment(
    review_bundle: ReviewBundle,
) -> None:
    submission = _seal(review_bundle)
    with pytest.raises(TypeError, match="sealed operator-attested submission"):
        reveal_c4_review_identities(  # type: ignore[arg-type]
            review_bundle.packet,
            material_commitment=review_bundle.commitment,
            operator_secret=review_bundle.secret,
            used_policy_ledger=review_bundle.ledger,
        )
    with pytest.raises(ValueError, match="pinned policy"):
        reveal_c4_review_identities(
            submission,
            material_commitment=review_bundle.commitment,
            operator_secret=bytes(range(33, 65)),
            used_policy_ledger=review_bundle.ledger,
        )

    reveal = reveal_c4_review_identities(
        submission,
        material_commitment=review_bundle.commitment,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    assert reveal.reveal_state == "revealed_after_sealed_submission"
    assert reveal.operator_receipt_secret_reverification_required is True
    assert reveal.external_ledger_reverification_required is True
    assert tuple(item.blind_code for item in reveal.mappings) == tuple(
        item.blind_code for item in review_bundle.packet.outputs
    )
    assert {item.model_id for item in reveal.mappings} == {
        review_bundle.commitment.model_id
    }
    assert reveal.semantic_quality_gate_passed is False
    assert reveal.production_authority_granted is False


@pytest.mark.parametrize("count", [0, 1, 3])
def test_exact_tuple_preflight_rejects_zero_one_and_three(
    review_bundle: ReviewBundle,
    count: int,
) -> None:
    options = (review_bundle.commitment.options * 2)[:count]
    with pytest.raises(ValueError, match="exact two-option tuple"):
        commit_c4_review_material(
            review_bundle.schema,
            operator_policy=review_bundle.policy,
            source_image_sha256=review_bundle.packet.source_image_sha256,
            renderer_id=review_bundle.commitment.renderer_id,
            model_id=review_bundle.commitment.model_id,
            model_revision=review_bundle.commitment.model_revision,
            options=options,  # type: ignore[arg-type]
        )

    paths = (review_bundle.output_paths * 2)[:count]
    with pytest.raises(ValueError, match="exact two-output path tuple"):
        build_c4_blind_presentation_manifest(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            source_png_path=review_bundle.source_path,
            output_png_paths=paths,  # type: ignore[arg-type]
        )

    judgments = (_judgments(review_bundle.packet) * 2)[:count]
    with pytest.raises(ValueError, match="exact two-judgment tuple"):
        build_c4_operator_unsigned_claim(
            review_bundle.packet,
            operator_policy=review_bundle.policy,
            presentation_manifest=review_bundle.presentation,
            reviewer_pseudonym="reviewer-alpha",
            review_timestamp=datetime.now(timezone.utc),
            output_judgments=judgments,  # type: ignore[arg-type]
            pair_judgment=_pair(),
            external_one_time_ledger_lease_sha256=(review_bundle.ledger_lease_sha256),
        )


def test_cold_validation_rejects_nested_hash_and_oversized_id_tamper(
    review_bundle: ReviewBundle,
) -> None:
    oversized = review_bundle.commitment.model_copy(update={"renderer_id": "r" * 201})
    oversized = _readdress(
        oversized,
        id_field="commitment_id",
        sha_field="material_commitment_sha256",
        namespace="c4_review_material",
    )
    with pytest.raises(ValidationError, match="at most 200"):
        prepare_c4_blind_review(
            review_bundle.schema,
            oversized,
            operator_policy=review_bundle.policy,
        )

    first, second = review_bundle.packet.outputs
    invalid_hash = "not-a-sha256"
    invalid_code = content_id(
        "c4_blind_code",
        {
            "material_commitment_id": review_bundle.packet.material_commitment_id,
            "material_commitment_sha256": (
                review_bundle.packet.material_commitment_sha256
            ),
            "source_image_sha256": review_bundle.packet.source_image_sha256,
            "option_id": first.option_id,
            "instruction_sha256": first.instruction_sha256,
            "output_sha256": invalid_hash,
        },
    )
    invalid_reference = first.model_copy(
        update={
            "blind_code": invalid_code,
            "blind_order_sha256": _digest(invalid_code),
            "output_sha256": invalid_hash,
        }
    )
    outputs = tuple(
        sorted(
            (invalid_reference, second),
            key=lambda item: item.blind_order_sha256,
        )
    )
    invalid_packet = _readdress(
        review_bundle.packet.model_copy(update={"outputs": outputs}),
        id_field="packet_id",
        sha_field="packet_sha256",
        namespace="c4_blind_packet",
    )
    with pytest.raises(ValidationError, match="pattern"):
        record_c4_output_human_judgment(
            invalid_packet,
            blind_code=invalid_code,
            source_subject_present=True,
            identity_preserved=True,
            unchanged_composition_preserved=True,
            option_action_correct=True,
            no_extra_actor=True,
            no_generated_external_evidence_claim=True,
            reviewer_uncertain=False,
        )


def test_model_copy_cannot_bypass_nested_cardinality(
    review_bundle: ReviewBundle,
) -> None:
    submission = _seal(review_bundle)
    reveal = reveal_c4_review_identities(
        submission,
        material_commitment=review_bundle.commitment,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    for count in (0, 1, 3):
        commitment = _readdress(
            review_bundle.commitment.model_copy(
                update={"options": (review_bundle.commitment.options * 2)[:count]}
            ),
            id_field="commitment_id",
            sha_field="material_commitment_sha256",
            namespace="c4_review_material",
        )
        with pytest.raises(ValueError, match="exactly two options"):
            commitment.validate_commitment()

        packet = _readdress(
            review_bundle.packet.model_copy(
                update={"outputs": (review_bundle.packet.outputs * 2)[:count]}
            ),
            id_field="packet_id",
            sha_field="packet_sha256",
            namespace="c4_blind_packet",
        )
        with pytest.raises(ValueError, match="exactly two outputs"):
            packet.validate_packet()

        changed_submission = _recontent(
            submission.model_copy(
                update={"output_judgments": (submission.output_judgments * 2)[:count]}
            ),
            id_field="submission_id",
            namespace="c4_human_review",
        )
        with pytest.raises((ValueError, ValidationError), match="two"):
            changed_submission.validate_submission()

        changed_reveal = _recontent(
            reveal.model_copy(update={"mappings": (reveal.mappings * 2)[:count]}),
            id_field="reveal_id",
            namespace="c4_review_reveal",
        )
        with pytest.raises(ValueError, match="Reveal mapping differs"):
            changed_reveal.validate_reveal()


def test_secret_parameters_have_no_defaults_and_secret_never_enters_artifacts(
    review_bundle: ReviewBundle,
) -> None:
    for function in (
        verify_c4_operator_attestation,
        seal_c4_human_review,
        evaluate_c4_human_review,
        reveal_c4_review_identities,
    ):
        parameter = inspect.signature(function).parameters["operator_secret"]
        assert parameter.default is inspect.Parameter.empty
    for function in (
        seal_c4_human_review,
        evaluate_c4_human_review,
        reveal_c4_review_identities,
    ):
        parameter = inspect.signature(function).parameters["used_policy_ledger"]
        assert parameter.default is inspect.Parameter.empty

    submission = _seal(review_bundle)
    gate = evaluate_c4_human_review(
        review_bundle.packet,
        operator_policy=review_bundle.policy,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
        submission=submission,
    )
    reveal = reveal_c4_review_identities(
        submission,
        material_commitment=review_bundle.commitment,
        operator_secret=review_bundle.secret,
        used_policy_ledger=review_bundle.ledger,
    )
    for artifact in (
        review_bundle.policy,
        review_bundle.commitment,
        review_bundle.packet,
        review_bundle.presentation,
        submission.operator_attestation,
        submission.consumed_policy_receipt,
        submission,
        gate,
        reveal,
    ):
        encoded = artifact.canonical_json_bytes()
        assert review_bundle.secret not in encoded
        assert review_bundle.secret.hex().encode() not in encoded
        assert review_bundle.secret.hex() not in repr(artifact)


def test_instruction_and_all_artifact_serialization_stay_bounded(
    review_bundle: ReviewBundle,
) -> None:
    submission = _seal(review_bundle)
    for artifact in (
        review_bundle.schema,
        review_bundle.policy,
        review_bundle.commitment,
        review_bundle.packet,
        review_bundle.presentation,
        submission.operator_attestation.claim,
        submission.operator_attestation,
        submission.consumed_policy_receipt,
        submission,
    ):
        assert len(artifact.canonical_json_bytes()) < C4_REVIEW_MAX_CANONICAL_BYTES

    with pytest.raises(ValidationError, match="at most 4096"):
        make_c4_review_option_material(
            option_id="too_long",
            instruction="x" * 4097,
            output_sha256=_digest("output"),
        )


def test_policy_and_full_hash_substitution_are_rejected(
    review_bundle: ReviewBundle,
) -> None:
    policy_payload = review_bundle.policy.model_dump(mode="python", round_trip=True)
    policy_payload["operator_policy_sha256"] = _digest("wrong-policy-full-hash")
    with pytest.raises(ValidationError, match="policy SHA-256"):
        C4HumanReviewOperatorPolicy.model_validate(policy_payload)

    packet_payload = review_bundle.packet.model_dump(mode="python", round_trip=True)
    packet_payload["packet_sha256"] = _digest("wrong-packet-full-hash")
    with pytest.raises(ValidationError, match="packet SHA-256"):
        C4BlindReviewPacket.model_validate(packet_payload)

    claim, _ = _external_attestation(review_bundle)
    claim_payload = claim.model_dump(mode="python", round_trip=True)
    claim_payload["claim_sha256"] = _digest("wrong-claim-full-hash")
    with pytest.raises(ValidationError, match="claim SHA-256"):
        C4HumanReviewUnsignedClaim.model_validate(claim_payload)


def test_schema_rejects_rubric_or_operator_scheme_weakening(
    review_bundle: ReviewBundle,
) -> None:
    for field, value in (
        ("output_positive_fields", tuple(reversed(C4_OUTPUT_POSITIVE_FIELDS))),
        ("operator_policy_scheme", "weaker-scheme"),
        ("external_operator_receipt_required", False),
    ):
        payload = review_bundle.schema.model_dump(mode="python", round_trip=True)
        payload[field] = value
        payload["schema_id"] = content_id(
            "c4_review_schema",
            {key: item for key, item in payload.items() if key != "schema_id"},
        )
        with pytest.raises(ValidationError):
            C4BlindHumanReviewSchema.model_validate(payload)
