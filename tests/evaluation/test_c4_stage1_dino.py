from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

import pytest

from rei.emocio.dinov2_encoder import (
    dinov2_base_encoding_spec,
    dinov2_base_provider_identity,
)
from rei.emocio.vector_encoding import canonical_l2_float32_le_vector
from rei.evaluation import c4_stage1_dino as dino_module
from rei.evaluation import c4_stage1_run as run_module
from rei.evaluation.c4_stage1_dino import (
    build_c4_stage1_dino_pair_result,
    verify_c4_stage1_dino_pair_result,
)
from rei.evaluation.c4_stage1_screen import (
    C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256,
    C4Stage1DinoPairResult,
)
from rei.models.provider import ProviderCallRecord
from rei.providers.protocols import (
    ImageEncodingRequest,
    VerifiedImageEncoding,
    build_image_encoding_call_spec,
)
from tests.evaluation.test_c4_stage1_run import (
    _Harness,
    _minimal_cold_envelope,
    _prepared_store,
    _run,
)


def _vector(first: float, second: float = 0.0, *, dimensions: int = 768) -> bytes:
    values = (first, second, *(0.0 for _ in range(dimensions - 2)))
    data, _, _ = canonical_l2_float32_le_vector(
        tuple(values),
        expected_dimensions=dimensions,
    )
    return data


def _encodings(images, vectors: tuple[bytes, bytes]):
    provider = dinov2_base_provider_identity()
    results: list[VerifiedImageEncoding] = []
    for index, (image, vector) in enumerate(zip(images, vectors, strict=True)):
        request = ImageEncodingRequest.create(
            image=image,
            provider=provider,
            spec=dinov2_base_encoding_spec(
                snapshot_manifest_sha256=(C4_STAGE1_DINOV2_SNAPSHOT_MANIFEST_SHA256),
                device="cuda",
            ),
        )
        call_spec = build_image_encoding_call_spec(request, timeout_seconds=30.0)
        vector_sha256 = hashlib.sha256(vector).hexdigest()
        vector_ref = f"emocio/embeddings/{vector_sha256}.f32"
        encoding_id = VerifiedImageEncoding.derive_id(
            request=request,
            vector_ref=vector_ref,
            vector_hash=vector_sha256,
            dimensions=768,
        )
        started_at = datetime(2026, 7, 15, 12, 0, index, tzinfo=UTC)
        call = ProviderCallRecord(
            call_id=call_spec.call_id,
            spec_hash=call_spec.content_hash(),
            request_id=call_spec.request_id,
            input_artifact_ids=call_spec.input_artifact_ids,
            provider=call_spec.provider,
            seed=call_spec.seed,
            parameters=call_spec.parameters,
            timeout_seconds=call_spec.timeout_seconds,
            started_at=started_at,
            primary_finished_at=started_at + timedelta(milliseconds=1),
            finished_at=started_at + timedelta(milliseconds=1),
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=(encoding_id,),
        )
        results.append(
            VerifiedImageEncoding.create(
                request=request,
                vector_ref=vector_ref,
                vector_hash=vector_sha256,
                dimensions=768,
                call_spec=call_spec,
                call=call,
            )
        )
    return results[0], results[1]


def _published_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    role: str = "primary",
):
    store, prepared_outcome, paths = _prepared_store(tmp_path)
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
    monkeypatch.setattr(
        dino_module,
        "cold_verify_c4_stage1_prepared_attempt",
        lambda *_args, **_kwargs: prepared_outcome,
    )
    member = next(
        item for item in outcome.manifest.member_runs if item.editor_role == role
    )
    publication_storage = member.worker_terminals[0].member_publication_receipt_storage
    assert publication_storage is not None
    cold = dino_module._cold_publication(
        store,
        prepared_outcome.prepared_anchor_storage,
        publication_storage,
    )
    cold_store, prepared, _, publication, _ = cold
    images = tuple(
        dino_module._published_image(
            cold_store,
            dino_module._prepared_worker(prepared, candidate),
            candidate,
        )[0]
        for candidate in publication.candidate_receipts
    )
    return store, prepared_outcome, outcome, publication_storage, images


def test_public_builder_cold_binds_committed_family_and_exact_math(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared, _, publication_storage, images = _published_family(
        tmp_path, monkeypatch
    )
    vectors = (_vector(1.0), _vector(0.0, 1.0))
    encodings = _encodings(images, vectors)
    before = {name for name in sys.modules if name in {"torch", "diffusers"}}

    result = build_c4_stage1_dino_pair_result(
        store,
        prepared.prepared_anchor_storage,
        publication_storage,
        encodings=encodings,
        vector_bytes=vectors,
    )

    assert result.direct_rollout_separation == 0.5
    assert result.dino_gate_passed is True
    assert result.prepared_anchor_storage == prepared.prepared_anchor_storage
    assert result.member_publication_receipt_storage == publication_storage
    assert tuple(item.image for item in result.outputs) == images
    assert all(item.candidate_receipt_id for item in result.outputs)
    assert all(item.candidate_staged_output_storage for item in result.outputs)
    assert result.semantic_authority_granted is False
    assert result.production_authority_granted is False
    assert {name for name in sys.modules if name in {"torch", "diffusers"}} == before


def test_public_verifier_replays_store_and_rejects_result_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared, _, publication_storage, images = _published_family(
        tmp_path, monkeypatch
    )
    vectors = (_vector(1.0), _vector(0.0, 1.0))
    encodings = _encodings(images, vectors)
    result = build_c4_stage1_dino_pair_result(
        store,
        prepared.prepared_anchor_storage,
        publication_storage,
        encodings=encodings,
        vector_bytes=vectors,
    )
    assert (
        verify_c4_stage1_dino_pair_result(
            result,
            artifact_store=store,
            prepared_anchor_storage=prepared.prepared_anchor_storage,
            member_publication_receipt_storage=publication_storage,
            encodings=encodings,
            vector_bytes=vectors,
        )
        == result
    )

    forged = result.model_copy(update={"direct_rollout_separation": 0.0})
    with pytest.raises(ValueError):
        verify_c4_stage1_dino_pair_result(
            forged,
            artifact_store=store,
            prepared_anchor_storage=prepared.prepared_anchor_storage,
            member_publication_receipt_storage=publication_storage,
            encodings=encodings,
            vector_bytes=vectors,
        )


def test_cross_family_encodings_and_arbitrary_vectors_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared, outcome, primary_storage, primary_images = _published_family(
        tmp_path, monkeypatch
    )
    alternate = next(
        item for item in outcome.manifest.member_runs if item.editor_role == "alternate"
    )
    alternate_storage = alternate.worker_terminals[0].member_publication_receipt_storage
    assert alternate_storage is not None
    vectors = (_vector(1.0), _vector(0.0, 1.0))
    primary_encodings = _encodings(primary_images, vectors)

    with pytest.raises(ValueError, match="uncommitted image bytes"):
        build_c4_stage1_dino_pair_result(
            store,
            prepared.prepared_anchor_storage,
            alternate_storage,
            encodings=primary_encodings,
            vector_bytes=vectors,
        )
    with pytest.raises(ValueError, match="vector hash"):
        build_c4_stage1_dino_pair_result(
            store,
            prepared.prepared_anchor_storage,
            primary_storage,
            encodings=primary_encodings,
            vector_bytes=(vectors[1], vectors[1]),
        )


def test_uncommitted_partial_or_mutated_publication_cannot_be_consumed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared, _, publication_storage, images = _published_family(
        tmp_path, monkeypatch
    )
    vectors = (_vector(1.0), _vector(0.0, 1.0))
    encodings = _encodings(images, vectors)
    with pytest.raises(TypeError):
        build_c4_stage1_dino_pair_result(
            store,
            prepared.prepared_anchor_storage,
            None,  # type: ignore[arg-type]
            encodings=encodings,
            vector_bytes=vectors,
        )

    _, _, _, publication, _ = dino_module._cold_publication(
        store,
        prepared.prepared_anchor_storage,
        publication_storage,
    )
    staged = publication.candidate_receipts[0].staged_output_storage
    store.artifact_path(staged.run_id, staged.relative_path).write_bytes(b"mutated")
    with pytest.raises(Exception):
        build_c4_stage1_dino_pair_result(
            store,
            prepared.prepared_anchor_storage,
            publication_storage,
            encodings=encodings,
            vector_bytes=vectors,
        )


def test_strict_threshold_and_serialized_publication_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prepared, _, publication_storage, images = _published_family(
        tmp_path, monkeypatch
    )
    left = _vector(1.0)
    boundary = _vector(0.98, math.sqrt(1.0 - 0.98**2))
    vectors = (left, boundary)
    result = build_c4_stage1_dino_pair_result(
        store,
        prepared.prepared_anchor_storage,
        publication_storage,
        encodings=_encodings(images, vectors),
        vector_bytes=vectors,
    )
    assert result.direct_rollout_separation <= 0.01
    assert result.action_collapse_detected is True
    assert result.dino_gate_passed is False

    forged_output = result.outputs[0].model_copy(
        update={"candidate_receipt_id": "candidate_forged"}
    )
    forged_result = result.model_copy(
        update={"outputs": (forged_output, result.outputs[1])}
    )
    with pytest.raises(ValueError):
        C4Stage1DinoPairResult.model_validate(
            forged_result.model_dump(mode="python", round_trip=True)
        )
