from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.backend.rei_next.models.emocio import ImageArtifact, VisualSceneSpec
from app.backend.rei_next.models.provider import (
    ProviderCallRecord,
    ProviderCallSpec,
    ProviderFallbackPlan,
    ProviderFallbackPolicy,
    ProviderFallbackRecord,
    ProviderIdentity,
    ProviderParameter,
)
from app.backend.rei_next.models.run import (
    ArtifactHashRecord,
    NativeBundleAssemblyRecord,
    RunManifest,
    SeedRecord,
)
from app.backend.rei_next.providers.protocols import (
    StoredArtifact,
    TextReasoningRequest,
    TextReasoningResult,
    ensure_call_contract,
    ensure_call_record_contract,
    validate_rendered_image,
)


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
HASH = "a" * 64


def _no_fallback(reason: str = "No compatible fallback is configured.") -> ProviderFallbackPolicy:
    return ProviderFallbackPolicy(mode="none", no_fallback_reason=reason)


def test_model_provider_requires_model_revision_and_seed() -> None:
    with pytest.raises(ValidationError):
        ProviderIdentity(
            provider_id="text_provider_invalid",
            kind="text_reasoner",
            implementation="example.TextProvider",
            implementation_revision="1",
            uses_model=True,
        )

    provider = ProviderIdentity(
        provider_id="text_provider_1",
        kind="text_reasoner",
        implementation="example.TextProvider",
        implementation_revision="1",
        uses_model=True,
        model="example-model",
        model_revision="revision-1",
    )
    with pytest.raises(ValidationError):
        ProviderCallSpec(
            call_id="call_without_seed",
            request_id="request_1",
            provider=provider,
            timeout_seconds=5.0,
            fallback_policy=_no_fallback(),
        )


def test_provider_parameters_must_be_canonical_json() -> None:
    with pytest.raises(ValidationError):
        ProviderParameter(
            name="config",
            canonical_json_value='{"b":2, "a":1}',
        )

    parameter = ProviderParameter(
        name="config",
        canonical_json_value='{"a":1,"b":2}',
    )

    assert parameter.canonical_json_value == '{"a":1,"b":2}'


def test_provider_call_contract_binds_identity_request_and_seed() -> None:
    provider = ProviderIdentity(
        provider_id="deterministic_provider_1",
        kind="text_reasoner",
        implementation="example.DeterministicProvider",
        implementation_revision="1",
    )
    call = ProviderCallSpec(
        call_id="call_1",
        request_id="request_1",
        provider=provider,
        seed=17,
        timeout_seconds=5.0,
        fallback_policy=_no_fallback(
            "Deterministic provider does not require fallback."
        ),
    )

    ensure_call_contract(provider, call, request_id="request_1", seed=17)
    with pytest.raises(ValueError):
        ensure_call_contract(provider, call, request_id="request_other", seed=17)
    with pytest.raises(ValueError):
        ensure_call_contract(provider, call, request_id="request_1", seed=18)

    with pytest.raises(ValidationError):
        ProviderCallRecord(
            call_id=call.call_id,
            spec_hash=call.content_hash(),
            request_id=call.request_id,
            input_artifact_ids=("artifact_same",),
            provider=provider,
            seed=17,
            timeout_seconds=5.0,
            started_at=NOW,
            primary_finished_at=NOW,
            finished_at=NOW,
            status="succeeded",
            primary_status="succeeded",
            output_artifact_ids=("artifact_same",),
        )


def test_text_result_round_trip_closes_call_spec_and_evidence_lineage() -> None:
    request = TextReasoningRequest(
        request_id="text_request_1",
        instruction="Return a structured fixture result.",
        input_text="Grounded fixture input.",
        language="en",
        evidence_ids=("evidence_1",),
    )
    provider = ProviderIdentity(
        provider_id="text_fixture_provider",
        kind="text_reasoner",
        implementation="example.TextFixtureProvider",
        implementation_revision="1",
    )
    call_spec = ProviderCallSpec(
        call_id="text_call_1",
        request_id=request.request_id,
        input_artifact_ids=request.evidence_ids,
        provider=provider,
        timeout_seconds=5.0,
        fallback_policy=_no_fallback("This fixture provider is deterministic."),
    )
    call_record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=request.request_id,
        input_artifact_ids=call_spec.input_artifact_ids,
        provider=provider,
        timeout_seconds=call_spec.timeout_seconds,
        started_at=NOW,
        primary_finished_at=NOW,
        finished_at=NOW,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=("text_result_1",),
    )
    result = TextReasoningResult(
        result_id="text_result_1",
        request_id=request.request_id,
        text="Structured fixture result.",
        supporting_evidence_ids=("evidence_1",),
        call_spec=call_spec,
        call=call_record,
    )

    ensure_call_contract(
        provider,
        call_spec,
        request_id=request.request_id,
        expected_kind="text_reasoner",
        required_input_artifact_ids=request.evidence_ids,
    )
    assert TextReasoningResult.model_validate_json(result.model_dump_json()) == result

    with pytest.raises(ValidationError):
        TextReasoningResult(
            result_id="text_result_1",
            request_id=request.request_id,
            text="Invalid evidence claim.",
            supporting_evidence_ids=("evidence_missing",),
            call_spec=call_spec,
            call=call_record,
        )


def test_provider_result_requires_the_correct_capability_kind() -> None:
    wrong_provider = ProviderIdentity(
        provider_id="artifact_store_provider",
        kind="artifact_store",
        implementation="example.ArtifactStore",
        implementation_revision="1",
    )
    call_spec = ProviderCallSpec(
        call_id="wrong_kind_call",
        request_id="text_request_wrong_kind",
        provider=wrong_provider,
        timeout_seconds=5.0,
        fallback_policy=_no_fallback("Wrong-kind regression fixture."),
    )
    call_record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        provider=wrong_provider,
        timeout_seconds=5.0,
        started_at=NOW,
        primary_finished_at=NOW,
        finished_at=NOW,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=("text_result_wrong_kind",),
    )

    with pytest.raises(ValidationError):
        TextReasoningResult(
            result_id="text_result_wrong_kind",
            request_id=call_spec.request_id,
            text="Must not be accepted.",
            call_spec=call_spec,
            call=call_record,
        )


def test_provider_call_requires_an_explicit_fallback_policy() -> None:
    provider = ProviderIdentity(
        provider_id="deterministic_provider_1",
        kind="text_reasoner",
        implementation="example.DeterministicProvider",
        implementation_revision="1",
    )
    with pytest.raises(ValidationError):
        ProviderCallSpec(
            call_id="call_without_fallback_policy",
            request_id="request_1",
            provider=provider,
            timeout_seconds=5.0,
        )
    with pytest.raises(ValidationError):
        ProviderFallbackPolicy(mode="none")

    incompatible_fallback = ProviderIdentity(
        provider_id="body_provider_1",
        kind="body_dynamics",
        implementation="example.BodyProvider",
        implementation_revision="1",
    )
    with pytest.raises(ValidationError):
        ProviderCallSpec(
            call_id="call_with_wrong_fallback_capability",
            request_id="request_1",
            provider=provider,
            timeout_seconds=5.0,
            fallback_policy=ProviderFallbackPolicy(
                mode="provider",
                plan=ProviderFallbackPlan(
                    provider=incompatible_fallback,
                    timeout_seconds=5.0,
                ),
            ),
        )


def test_rendered_image_is_bound_to_source_call_and_model_provenance() -> None:
    source_spec = VisualSceneSpec(
        scene_id="visual_spec_1",
        scene_kind="current",
        option_id=None,
        entities=("actor",),
        self_position="observer",
        attention_structure=(),
        group_belonging="unspecified",
        status_relations=(),
        movement=(),
        composition=(),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=("evidence_1",),
        inferred_elements=(),
    )
    provider = ProviderIdentity(
        provider_id="renderer_1",
        kind="image_renderer",
        implementation="example.ImageRenderer",
        implementation_revision="1",
        uses_model=True,
        model="example-image-model",
        model_revision="revision-1",
    )
    call_spec = ProviderCallSpec(
        call_id="render_call_1",
        request_id="render_request_1",
        input_artifact_ids=(source_spec.scene_id,),
        provider=provider,
        seed=17,
        timeout_seconds=30.0,
        fallback_policy=_no_fallback("Rendering is optional presentation output."),
    )
    call_record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        input_artifact_ids=call_spec.input_artifact_ids,
        provider=provider,
        seed=17,
        parameters=call_spec.parameters,
        timeout_seconds=call_spec.timeout_seconds,
        started_at=NOW,
        primary_finished_at=NOW,
        finished_at=NOW,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=("image_1",),
    )
    artifact = ImageArtifact(
        image_id="image_1",
        request_id=call_spec.request_id,
        render_call_id=call_spec.call_id,
        source_spec_id=source_spec.scene_id,
        provider_id=provider.provider_id,
        model=provider.model,
        model_revision=provider.model_revision,
        seed=17,
        input_spec_hash=source_spec.content_hash(),
        content_sha256=HASH,
        media_type="image/png",
        prompt="presentation-only prompt",
        negative_prompt="",
        path="emocio/images/image_1.png",
        width=64,
        height=64,
        generated_only_elements=(),
    )

    validate_rendered_image(
        artifact,
        source_spec=source_spec,
        identity=provider,
        call_spec=call_spec,
        call_record=call_record,
        seed=17,
    )

    with pytest.raises(ValueError):
        validate_rendered_image(
            artifact.model_copy(update={"input_spec_hash": "0" * 64}),
            source_spec=source_spec,
            identity=provider,
            call_spec=call_spec,
            call_record=call_record,
            seed=17,
        )


def test_rendered_image_records_the_successful_fallback_provider() -> None:
    source_spec = VisualSceneSpec(
        scene_id="visual_spec_fallback",
        scene_kind="current",
        option_id=None,
        entities=("actor",),
        self_position="observer",
        attention_structure=(),
        group_belonging="unspecified",
        status_relations=(),
        movement=(),
        composition=(),
        attraction_markers=(),
        obstacle_markers=(),
        grounded_evidence_ids=("evidence_1",),
        inferred_elements=(),
    )
    primary = ProviderIdentity(
        provider_id="renderer_primary",
        kind="image_renderer",
        implementation="example.PrimaryRenderer",
        implementation_revision="1",
        uses_model=True,
        model="primary-image-model",
        model_revision="revision-1",
    )
    fallback = ProviderIdentity(
        provider_id="renderer_fallback",
        kind="image_renderer",
        implementation="example.FallbackRenderer",
        implementation_revision="1",
        uses_model=True,
        model="fallback-image-model",
        model_revision="revision-2",
    )
    fallback_plan = ProviderFallbackPlan(
        provider=fallback,
        seed=22,
        timeout_seconds=20.0,
    )
    call_spec = ProviderCallSpec(
        call_id="render_call_fallback",
        request_id="render_request_fallback",
        input_artifact_ids=(source_spec.scene_id,),
        provider=primary,
        seed=17,
        timeout_seconds=10.0,
        fallback_policy=ProviderFallbackPolicy(
            mode="provider",
            plan=fallback_plan,
        ),
    )
    fallback_record = ProviderFallbackRecord(
        provider=fallback,
        seed=22,
        timeout_seconds=20.0,
        started_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=2),
        status="succeeded",
        output_artifact_ids=("image_fallback",),
    )
    call_record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        input_artifact_ids=call_spec.input_artifact_ids,
        provider=primary,
        seed=17,
        timeout_seconds=10.0,
        started_at=NOW,
        primary_finished_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=2),
        status="fell_back",
        primary_status="failed",
        fallback=fallback_record,
        output_artifact_ids=("image_fallback",),
    )
    artifact = ImageArtifact(
        image_id="image_fallback",
        request_id=call_spec.request_id,
        render_call_id=call_spec.call_id,
        source_spec_id=source_spec.scene_id,
        provider_id=fallback.provider_id,
        model=fallback.model,
        model_revision=fallback.model_revision,
        seed=22,
        input_spec_hash=source_spec.content_hash(),
        content_sha256=HASH,
        media_type="image/png",
        prompt="presentation-only prompt",
        negative_prompt="",
        path="emocio/images/image_fallback.png",
        width=64,
        height=64,
        generated_only_elements=(),
    )

    validate_rendered_image(
        artifact,
        source_spec=source_spec,
        identity=primary,
        call_spec=call_spec,
        call_record=call_record,
        seed=22,
    )


def test_unsuccessful_fallback_is_recorded_without_publishing_outputs() -> None:
    primary = ProviderIdentity(
        provider_id="text_primary",
        kind="text_reasoner",
        implementation="example.PrimaryTextProvider",
        implementation_revision="1",
    )
    fallback = ProviderIdentity(
        provider_id="text_fallback",
        kind="text_reasoner",
        implementation="example.FallbackTextProvider",
        implementation_revision="1",
    )
    call_spec = ProviderCallSpec(
        call_id="text_call_failed_fallback",
        request_id="text_request_failed_fallback",
        provider=primary,
        timeout_seconds=5.0,
        fallback_policy=ProviderFallbackPolicy(
            mode="provider",
            plan=ProviderFallbackPlan(
                provider=fallback,
                timeout_seconds=5.0,
            ),
        ),
    )
    fallback_record = ProviderFallbackRecord(
        provider=fallback,
        timeout_seconds=5.0,
        started_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=2),
        status="failed",
    )
    record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        provider=primary,
        timeout_seconds=5.0,
        started_at=NOW,
        primary_finished_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=2),
        status="failed",
        primary_status="timed_out",
        fallback=fallback_record,
    )

    assert record.fallback is not None
    assert record.fallback.status == "failed"
    assert record.output_artifact_ids == ()
    ensure_call_record_contract(call_spec, record)

    missing_fallback_outcome = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        provider=primary,
        timeout_seconds=5.0,
        started_at=NOW,
        primary_finished_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=1),
        status="timed_out",
        primary_status="timed_out",
    )
    with pytest.raises(ValueError):
        ensure_call_record_contract(call_spec, missing_fallback_outcome)

    skipped_fallback = ProviderFallbackRecord(
        provider=fallback,
        timeout_seconds=5.0,
        status="skipped",
        skip_reason="Fallback dependency was unavailable before invocation.",
    )
    skipped_record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        provider=primary,
        timeout_seconds=5.0,
        started_at=NOW,
        primary_finished_at=NOW + timedelta(seconds=1),
        finished_at=NOW + timedelta(seconds=1),
        status="timed_out",
        primary_status="timed_out",
        fallback=skipped_fallback,
    )
    ensure_call_record_contract(call_spec, skipped_record)

    with pytest.raises(ValidationError):
        ProviderCallRecord(
            call_id=call_spec.call_id,
            spec_hash=call_spec.content_hash(),
            request_id=call_spec.request_id,
            provider=primary,
            timeout_seconds=5.0,
            started_at=NOW,
            primary_finished_at=NOW + timedelta(seconds=2),
            finished_at=NOW + timedelta(seconds=2),
            status="failed",
            primary_status="timed_out",
            fallback=fallback_record,
        )


def test_failed_call_cannot_back_a_provider_result() -> None:
    provider = ProviderIdentity(
        provider_id="text_failed_provider",
        kind="text_reasoner",
        implementation="example.FailedTextProvider",
        implementation_revision="1",
    )
    call_spec = ProviderCallSpec(
        call_id="text_call_failed",
        request_id="text_request_failed",
        provider=provider,
        timeout_seconds=5.0,
        fallback_policy=_no_fallback("Failure is final for this fixture."),
    )
    record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        provider=provider,
        timeout_seconds=5.0,
        started_at=NOW,
        primary_finished_at=NOW,
        finished_at=NOW,
        status="failed",
        primary_status="failed",
    )

    with pytest.raises(ValidationError):
        TextReasoningResult(
            result_id="text_result_from_failure",
            request_id=call_spec.request_id,
            text="Must not be accepted.",
            call_spec=call_spec,
            call=record,
        )


def test_stored_artifact_requires_a_portable_relative_path() -> None:
    artifact = StoredArtifact(
        storage_id="stored_1",
        run_id="run_1",
        relative_path="native/bundle.json",
        content_sha256=HASH,
        size_bytes=1,
    )
    assert artifact.relative_path == "native/bundle.json"

    for invalid_path in (
        "",
        "/absolute/path.json",
        "../escape.json",
        "native/../../escape.json",
        "C:/absolute/path.json",
        "native\\windows.json",
        "native/CON.json",
        "native/AUX.txt",
        "native/trailing.",
        "native/trailing ",
        "native/control\x1f.json",
    ):
        with pytest.raises(ValidationError):
            StoredArtifact(
                storage_id="stored_invalid",
                run_id="run_1",
                relative_path=invalid_path,
                content_sha256=HASH,
                size_bytes=1,
            )


def test_generated_image_artifact_can_never_be_grounded() -> None:
    payload = {
        "image_id": "image_1",
        "request_id": "render_request_1",
        "render_call_id": "render_call_1",
        "source_spec_id": "visual_spec_1",
        "provider_id": "renderer_1",
        "model": "example-image-model",
        "model_revision": "revision-1",
        "seed": 17,
        "input_spec_hash": HASH,
        "content_sha256": HASH,
        "media_type": "image/png",
        "prompt": "presentation-only prompt",
        "negative_prompt": "",
        "path": "emocio/images/image_1.png",
        "width": 64,
        "height": 64,
        "generated_only_elements": (),
    }

    artifact = ImageArtifact(**payload)
    assert artifact.grounded is False

    with pytest.raises(ValidationError):
        ImageArtifact(**payload, grounded=True)
    with pytest.raises(ValidationError):
        ImageArtifact(**{**payload, "path": "../../outside.png"})
    with pytest.raises(ValidationError):
        ImageArtifact(**{**payload, "grounded_mask_path": "C:/outside.png"})


def test_run_manifest_serializes_complete_provenance() -> None:
    provider = ProviderIdentity(
        provider_id="deterministic_provider_1",
        kind="text_reasoner",
        implementation="example.DeterministicProvider",
        implementation_revision="1",
    )
    call_spec = ProviderCallSpec(
        call_id="native_call_1",
        request_id="native_request_1",
        provider=provider,
        seed=17,
        timeout_seconds=5.0,
        fallback_policy=_no_fallback(
            "The deterministic native fixture has no secondary implementation."
        ),
    )
    call_record = ProviderCallRecord(
        call_id=call_spec.call_id,
        spec_hash=call_spec.content_hash(),
        request_id=call_spec.request_id,
        provider=provider,
        seed=17,
        parameters=call_spec.parameters,
        timeout_seconds=call_spec.timeout_seconds,
        started_at=NOW,
        primary_finished_at=NOW,
        finished_at=NOW,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=(
            "racio_conclusion_1",
            "emocio_conclusion_1",
            "instinkt_conclusion_1",
        ),
    )
    manifest = RunManifest(
        run_id="run_1",
        source_commit="d1a19b9f1d4b9c1cf709342aa883c2b2d45491c5",
        canon_version="rei-native-canon-v2",
        mode="controlled_profile_matrix",
        profile_id="R=E=I",
        acceptance_state_id="acceptance_1",
        acceptance_config_hash=HASH,
        providers=(provider,),
        provider_call_specs=(call_spec,),
        provider_calls=(call_record,),
        seeds=(
            SeedRecord(
                call_id=call_spec.call_id,
                provider_id=provider.provider_id,
                seed=17,
            ),
        ),
        native_artifact_hashes=(
            ArtifactHashRecord(
                artifact_id="bundle_1",
                role="native_bundle",
                sha256=HASH,
            ),
            ArtifactHashRecord(
                artifact_id="racio_conclusion_1",
                role="racio_native",
                sha256=HASH,
            ),
            ArtifactHashRecord(
                artifact_id="emocio_conclusion_1",
                role="emocio_native",
                sha256=HASH,
            ),
            ArtifactHashRecord(
                artifact_id="instinkt_conclusion_1",
                role="instinkt_native",
                sha256=HASH,
            ),
        ),
        native_artifact_source="produced",
        native_assembly=NativeBundleAssemblyRecord(
            assembly_id="native_assembly_1",
            implementation="app.backend.rei_next.models.run.NativeMindBundle.create",
            implementation_revision="1",
            racio_conclusion_id="racio_conclusion_1",
            emocio_conclusion_id="emocio_conclusion_1",
            instinkt_conclusion_id="instinkt_conclusion_1",
            bundle_id="bundle_1",
            started_at=NOW,
            finished_at=NOW,
        ),
        started_at=NOW,
        finished_at=NOW,
        status="completed",
    )

    restored = RunManifest.model_validate_json(manifest.model_dump_json())

    assert restored == manifest
    assert restored.safety_notice.conceptual_simulator is True
    assert restored.safety_notice.diagnostic_use_allowed is False

    bundle_producer_record = call_record.model_copy(
        update={
            "output_artifact_ids": (
                *call_record.output_artifact_ids,
                "bundle_1",
            )
        }
    )
    bundle_producer_payload = {
        name: getattr(manifest, name)
        for name in RunManifest.model_fields
    }
    bundle_producer_payload["provider_calls"] = (bundle_producer_record,)
    with pytest.raises(ValidationError):
        RunManifest(**bundle_producer_payload)

    inherited = RunManifest(
        run_id="run_2",
        parent_run_id=manifest.run_id,
        parent_run_hash=manifest.content_hash(),
        source_commit=manifest.source_commit,
        canon_version=manifest.canon_version,
        mode="person_longitudinal",
        profile_id=manifest.profile_id,
        acceptance_state_id=manifest.acceptance_state_id,
        acceptance_config_hash=manifest.acceptance_config_hash,
        native_artifact_hashes=manifest.native_artifact_hashes,
        native_artifact_source="inherited",
        started_at=NOW,
        finished_at=NOW,
        status="completed",
    )
    inherited.validate_inherited_native_artifacts(manifest)

    future_parent_lineage = inherited.model_copy(
        update={
            "started_at": NOW - timedelta(seconds=1),
            "finished_at": NOW,
        }
    )
    with pytest.raises(ValueError):
        future_parent_lineage.validate_inherited_native_artifacts(manifest)

    tampered_inherited = inherited.model_copy(
        update={
            "native_artifact_hashes": (
                ArtifactHashRecord(
                    artifact_id="bundle_1",
                    role="native_bundle",
                    sha256="b" * 64,
                ),
                *inherited.native_artifact_hashes[1:],
            )
        }
    )
    with pytest.raises(ValueError):
        tampered_inherited.validate_inherited_native_artifacts(manifest)

    duplicate_spec = ProviderCallSpec(
        call_id="native_call_duplicate_producer",
        request_id="native_request_duplicate_producer",
        provider=provider,
        timeout_seconds=5.0,
        fallback_policy=_no_fallback("Duplicate-producer regression fixture."),
    )
    duplicate_record = ProviderCallRecord(
        call_id=duplicate_spec.call_id,
        spec_hash=duplicate_spec.content_hash(),
        request_id=duplicate_spec.request_id,
        provider=provider,
        timeout_seconds=5.0,
        started_at=NOW,
        primary_finished_at=NOW,
        finished_at=NOW,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=("racio_conclusion_1",),
    )
    duplicate_payload = {
        name: getattr(manifest, name)
        for name in RunManifest.model_fields
    }
    duplicate_payload["provider_call_specs"] = (
        *manifest.provider_call_specs,
        duplicate_spec,
    )
    duplicate_payload["provider_calls"] = (
        *manifest.provider_calls,
        duplicate_record,
    )
    with pytest.raises(ValidationError):
        RunManifest(**duplicate_payload)

    manifest_payload = {
        name: getattr(manifest, name)
        for name in RunManifest.model_fields
    }
    manifest_payload["native_assembly"] = None
    with pytest.raises(ValidationError):
        RunManifest(**manifest_payload)
