"""Cold publication-bound construction and replay of C4 Stage 1 DINO pairs.

This module performs no model work.  The encoder outputs are supplied as
portable evidence, while the compared PNGs can only come from a cold-verified,
create-only Stage 1 family publication in ``FileArtifactStore``.
"""

from __future__ import annotations

import hashlib

from ..emocio.c4_stage1_editor import inspect_c4_stage1_png_bytes
from ..emocio.dinov2_encoder import DINOV2_BASE_DIMENSIONS
from ..emocio.vector_encoding import verified_float32_le_vector
from ..ids import content_id
from ..models.emocio import ImageArtifact
from ..persistence.artifacts import FileArtifactStore
from ..providers.protocols import StoredArtifact, VerifiedImageEncoding
from .c4_stage1_attempt import (
    C4Stage1PreparedAttempt,
    C4Stage1PreparedWorker,
    cold_verify_c4_stage1_prepared_attempt,
)
from .c4_stage1_run import (
    C4Stage1MemberPublicationReceipt,
    C4Stage1PublishedCandidateReceipt,
    cold_verify_c4_stage1_member_publication,
)
from .c4_stage1_screen import (
    C4Stage1DinoOptionEvidence,
    C4Stage1DinoPairResult,
)


def _stored(value: StoredArtifact, *, label: str) -> StoredArtifact:
    if not isinstance(value, StoredArtifact):
        raise TypeError(f"{label} must be a StoredArtifact")
    return StoredArtifact.model_validate(
        value.model_dump(mode="python", round_trip=True)
    )


def _cold_publication(
    artifact_store: FileArtifactStore,
    prepared_anchor_storage: StoredArtifact,
    member_publication_receipt_storage: StoredArtifact,
) -> tuple[
    FileArtifactStore,
    C4Stage1PreparedAttempt,
    StoredArtifact,
    C4Stage1MemberPublicationReceipt,
    StoredArtifact,
]:
    if not isinstance(artifact_store, FileArtifactStore):
        raise TypeError("C4 Stage 1 DINO requires FileArtifactStore")
    prepared_storage = _stored(
        prepared_anchor_storage,
        label="prepared_anchor_storage",
    )
    publication_storage = _stored(
        member_publication_receipt_storage,
        label="member_publication_receipt_storage",
    )
    cold_store = FileArtifactStore(artifact_store.root, create=False)
    prepared_outcome = cold_verify_c4_stage1_prepared_attempt(
        cold_store,
        prepared_storage,
        require_exact_pre_spawn_inventory=False,
    )
    prepared = prepared_outcome.prepared_attempt
    if prepared_outcome.prepared_anchor_storage != prepared_storage:
        raise ValueError("C4 Stage 1 DINO prepared anchor descriptor changed")
    publication = cold_verify_c4_stage1_member_publication(
        cold_store,
        publication_storage,
        prepared,
    )
    if (
        publication_storage.run_id != prepared.run_id
        or publication.run_id != prepared.run_id
        or publication.prepared_attempt_id != prepared.prepared_attempt_id
        or publication.prepared_attempt_sha256 != prepared.prepared_attempt_sha256
        or not publication.publication_committed
        or not publication.both_options_technical_passed
    ):
        raise ValueError("C4 Stage 1 DINO publication is not a committed family")
    return (
        cold_store,
        prepared,
        prepared_storage,
        publication,
        publication_storage,
    )


def _prepared_worker(
    prepared: C4Stage1PreparedAttempt,
    candidate: C4Stage1PublishedCandidateReceipt,
) -> C4Stage1PreparedWorker:
    matches = tuple(
        worker
        for worker in prepared.workers
        if worker.prepared_worker_id == candidate.prepared_worker_id
    )
    if len(matches) != 1:
        raise ValueError("C4 Stage 1 DINO candidate has no exact prepared worker")
    worker = matches[0]
    if (
        worker.content_hash() != candidate.prepared_worker_sha256
        or worker.worker_request.worker_request_id != candidate.worker_request_id
        or worker.worker_request.content_hash() != candidate.worker_request_sha256
        or worker.editor_role != candidate.editor_role
        or worker.option_id != candidate.option_id
    ):
        raise ValueError("C4 Stage 1 DINO candidate differs from prepared worker")
    return worker


def _published_image(
    cold_store: FileArtifactStore,
    worker: C4Stage1PreparedWorker,
    candidate: C4Stage1PublishedCandidateReceipt,
) -> tuple[ImageArtifact, bytes]:
    payload = cold_store.read_verified(candidate.staged_output_storage)
    digest = hashlib.sha256(payload).hexdigest()
    request = worker.worker_request
    render = request.render_request
    if (
        digest != candidate.staged_png_sha256
        or len(payload) != candidate.staged_png_size_bytes
        or inspect_c4_stage1_png_bytes(payload)
        != (candidate.staged_width, candidate.staged_height)
    ):
        raise ValueError("C4 Stage 1 DINO staged publication bytes changed")
    image_id = content_id(
        "image",
        {
            "request_id": render.request_id,
            "content_sha256": digest,
        },
    )
    image = ImageArtifact(
        image_id=image_id,
        request_id=render.request_id,
        render_call_id=request.call_spec.call_id,
        source_spec_id=render.source_spec_id,
        provider_id=render.provider.provider_id,
        model=render.provider.model,
        model_revision=render.provider.model_revision,
        seed=render.seed,
        input_spec_hash=render.source_spec_hash,
        content_sha256=digest,
        media_type="image/png",
        grounded=False,
        prompt=render.prompt,
        negative_prompt=render.negative_prompt,
        path=candidate.staged_output_storage.relative_path,
        width=candidate.staged_width,
        height=candidate.staged_height,
        generated_only_elements=("c4_stage1_unverified_generated_candidate",),
        grounded_mask_path=None,
    )
    return image, payload


def _build_outputs(
    cold_store: FileArtifactStore,
    prepared: C4Stage1PreparedAttempt,
    publication: C4Stage1MemberPublicationReceipt,
    encodings: tuple[VerifiedImageEncoding, VerifiedImageEncoding],
) -> tuple[C4Stage1DinoOptionEvidence, C4Stage1DinoOptionEvidence]:
    if type(encodings) is not tuple or len(encodings) != 2:
        raise ValueError("C4 Stage 1 DINO comparison requires exactly two encodings")
    outputs: list[C4Stage1DinoOptionEvidence] = []
    for candidate, encoding_value in zip(
        publication.candidate_receipts,
        encodings,
        strict=True,
    ):
        if not isinstance(encoding_value, VerifiedImageEncoding):
            raise TypeError("C4 Stage 1 DINO requires VerifiedImageEncoding lineage")
        encoding = VerifiedImageEncoding.model_validate(
            encoding_value.model_dump(mode="python", round_trip=True)
        )
        worker = _prepared_worker(prepared, candidate)
        image, payload = _published_image(cold_store, worker, candidate)
        image_sha256 = hashlib.sha256(payload).hexdigest()
        if (
            encoding.request.image_content_sha256 != image_sha256
            or encoding.image_id != image.image_id
        ):
            raise ValueError("C4 Stage 1 DINO encoding cites uncommitted image bytes")
        outputs.append(
            C4Stage1DinoOptionEvidence(
                option_id=candidate.option_id,
                prepared_worker_id=candidate.prepared_worker_id,
                prepared_worker_sha256=candidate.prepared_worker_sha256,
                worker_request_id=candidate.worker_request_id,
                worker_request_sha256=candidate.worker_request_sha256,
                candidate_receipt_id=candidate.candidate_receipt_id,
                candidate_receipt_sha256=candidate.candidate_receipt_sha256,
                candidate_staged_output_storage=candidate.staged_output_storage,
                image=image,
                image_artifact_id=encoding.image_id,
                image_sha256=image_sha256,
                embedding_artifact_id=encoding.encoding_id,
                embedding_artifact_hash=encoding.content_hash(),
                vector_sha256=encoding.vector_hash,
                encoding=encoding,
            )
        )
    return outputs[0], outputs[1]


def _verify_vectors(
    outputs: tuple[C4Stage1DinoOptionEvidence, C4Stage1DinoOptionEvidence],
    vector_bytes: tuple[bytes, bytes],
) -> None:
    if type(vector_bytes) is not tuple or len(vector_bytes) != 2:
        raise ValueError("C4 Stage 1 DINO comparison requires exactly two vectors")
    for evidence, payload in zip(outputs, vector_bytes, strict=True):
        if type(payload) is not bytes:
            raise TypeError("C4 Stage 1 DINO vectors must be immutable bytes")
        _, digest = verified_float32_le_vector(
            payload,
            expected_dimensions=DINOV2_BASE_DIMENSIONS,
        )
        if digest != evidence.vector_sha256:
            raise ValueError("C4 Stage 1 DINO vector hash differs from evidence")


def build_c4_stage1_dino_pair_result(
    artifact_store: FileArtifactStore,
    prepared_anchor_storage: StoredArtifact,
    member_publication_receipt_storage: StoredArtifact,
    *,
    encodings: tuple[VerifiedImageEncoding, VerifiedImageEncoding],
    vector_bytes: tuple[bytes, bytes],
) -> C4Stage1DinoPairResult:
    """Build a DINO result only from one cold-verified committed family."""

    (
        cold_store,
        prepared,
        prepared_storage,
        publication,
        publication_storage,
    ) = _cold_publication(
        artifact_store,
        prepared_anchor_storage,
        member_publication_receipt_storage,
    )
    outputs = _build_outputs(cold_store, prepared, publication, encodings)
    _verify_vectors(outputs, vector_bytes)
    editor = next(
        item
        for item in prepared.screen_contract.editors
        if item.role == publication.editor_role
    )
    return C4Stage1DinoPairResult.create(
        screen_contract=prepared.screen_contract,
        run_id=prepared.run_id,
        prepared_attempt_id=prepared.prepared_attempt_id,
        prepared_attempt_sha256=prepared.prepared_attempt_sha256,
        prepared_anchor_storage=prepared_storage,
        member_publication_receipt_id=(publication.member_publication_receipt_id),
        member_publication_receipt_sha256=(
            publication.member_publication_receipt_sha256
        ),
        member_publication_receipt_storage=publication_storage,
        provider_slot_id=publication.provider_slot_id,
        editor_role=publication.editor_role,
        editor_spec_id=editor.spec_id,
        dino_policy=prepared.screen_contract.dino_policy,
        outputs=outputs,
        vector_bytes=vector_bytes,
    )


def verify_c4_stage1_dino_pair_result(
    result: C4Stage1DinoPairResult,
    *,
    artifact_store: FileArtifactStore,
    prepared_anchor_storage: StoredArtifact,
    member_publication_receipt_storage: StoredArtifact,
    encodings: tuple[VerifiedImageEncoding, VerifiedImageEncoding],
    vector_bytes: tuple[bytes, bytes],
) -> C4Stage1DinoPairResult:
    """Cold-replay a result against the same committed family and exact bytes."""

    if not isinstance(result, C4Stage1DinoPairResult):
        raise TypeError("result must be a C4Stage1DinoPairResult")
    validated = C4Stage1DinoPairResult.model_validate(
        result.model_dump(mode="python", round_trip=True)
    )
    expected = build_c4_stage1_dino_pair_result(
        artifact_store,
        prepared_anchor_storage,
        member_publication_receipt_storage,
        encodings=encodings,
        vector_bytes=vector_bytes,
    )
    if validated != expected:
        raise ValueError("C4 Stage 1 DINO result differs from cold publication replay")
    return validated


__all__ = [
    "build_c4_stage1_dino_pair_result",
    "verify_c4_stage1_dino_pair_result",
]
