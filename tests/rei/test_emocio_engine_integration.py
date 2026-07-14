from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backend.rei.emocio import (
    CurrentFirstEmocioRenderer,
    DeterministicEmocioProcessor,
    DiffusersImageRenderer,
    EmocioBinarySnapshot,
    DinoV2BaseImageEncoder,
    DinoV2RuntimeConfig,
    LocalFloat32VectorStore,
    LocalPngArtifactStore,
    RenderSettings,
    VisualValuationPolicy,
    VisualValuationPolicyConfig,
)
from app.backend.rei.engine import ReiNativeEngine
from app.backend.rei.ego.trace_store import FileEgoTraceStore
from app.backend.rei.ids import canonical_json_bytes, content_id
from app.backend.rei.models.provider import ProviderFallbackPolicy
from app.backend.rei.persistence import ArtifactIntegrityError, FileArtifactStore
from app.backend.rei.providers.native import (
    DeterministicExecutionClock,
    SystemExecutionClock,
)
from app.backend.rei.providers.deterministic import (
    build_deterministic_native_providers,
)
from tests.rei.test_emocio_current_first_renderer import (
    RecordingBackend,
    _identity as renderer_identity,
    _png,
)
from tests.rei.test_emocio_dinov2_encoder import (
    RecordingFeatureBackend,
    _snapshot,
)
from tests.rei.test_engine import _request


class _OldShapeEmocioProvider:
    def __init__(self, provider) -> None:
        self.provider = provider

    @property
    def identity(self):
        return self.provider.identity

    def required_input_artifact_ids(self, scene, world, packet):
        return self.provider.required_input_artifact_ids(scene, world, packet)

    def build_call_spec(self, scene, world, packet):
        return self.provider.build_call_spec(scene, world, packet)

    def execute(self, scene, world, *, packet, call, clock):
        execution = self.provider.execute(
            scene,
            world,
            packet=packet,
            call=call,
            clock=clock,
        )
        return SimpleNamespace(
            conclusion=execution.conclusion,
            call_spec=execution.call_spec,
            call_record=execution.call_record,
            source_world_id=execution.source_world_id,
            source_world_hash=execution.source_world_hash,
            packet=execution.packet,
            visual_state=execution.visual_state,
            rendered_images=execution.rendered_images,
            renderer_warning=execution.renderer_warning,
        )


class _OldShapeProviderSet:
    def __init__(
        self,
        processor: DeterministicEmocioProcessor | None = None,
    ) -> None:
        providers = build_deterministic_native_providers(
            emocio_processor=processor,
        )
        self.racio = providers.racio
        self.emocio = _OldShapeEmocioProvider(providers.emocio)
        self.instinkt = providers.instinkt

    @property
    def identities(self):
        return (self.racio.identity, self.emocio.identity, self.instinkt.identity)


class _RejectingPreparedStore(FileArtifactStore):
    def verify_prepared_run(self, run_id: str):
        del run_id
        raise ArtifactIntegrityError("synthetic configured replay rejection")


class _TamperingConfiguredEmocioProvider:
    def __init__(self, provider, *, warning: str | None = None, snapshot=False):
        self.provider = provider
        self.warning = warning
        self.snapshot = snapshot

    @property
    def identity(self):
        return self.provider.identity

    def required_input_artifact_ids(self, scene, world, packet):
        return self.provider.required_input_artifact_ids(scene, world, packet)

    def build_call_spec(self, scene, world, packet):
        return self.provider.build_call_spec(scene, world, packet)

    def execute(self, scene, world, *, packet, call, clock):
        execution = self.provider.execute(
            scene,
            world,
            packet=packet,
            call=call,
            clock=clock,
        )
        snapshots = execution.binary_snapshots
        if self.snapshot:
            original = next(item for item in snapshots if item.role == "image")
            altered_png = _png(
                original.width,
                original.height,
                (230, 20, 60, 255),
            )
            altered = EmocioBinarySnapshot(
                artifact_id=original.artifact_id,
                role="image",
                relative_path="emocio/images/altered-wrapper.png",
                content_sha256=hashlib.sha256(altered_png).hexdigest(),
                content=altered_png,
                width=original.width,
                height=original.height,
            )
            snapshots = tuple(
                sorted(
                    (
                        altered if item is original else item
                        for item in snapshots
                    ),
                    key=lambda item: (item.relative_path, item.artifact_id),
                )
            )
        return SimpleNamespace(
            conclusion=execution.conclusion,
            call_spec=execution.call_spec,
            call_record=execution.call_record,
            processing=execution.processing,
            runtime_config=execution.runtime_config,
            processing_artifact=execution.processing_artifact,
            binary_snapshots=snapshots,
            source_world_id=execution.source_world_id,
            source_world_hash=execution.source_world_hash,
            packet=execution.packet,
            visual_state=execution.visual_state,
            rendered_images=execution.rendered_images,
            renderer_warning=(
                execution.renderer_warning
                if self.warning is None
                else self.warning
            ),
        )


class _TamperingConfiguredProviderSet:
    def __init__(
        self,
        processor: DeterministicEmocioProcessor,
        *,
        warning: str | None = None,
        snapshot: bool = False,
    ) -> None:
        providers = build_deterministic_native_providers(
            emocio_processor=processor,
        )
        self.racio = providers.racio
        self.emocio = _TamperingConfiguredEmocioProvider(
            providers.emocio,
            warning=warning,
            snapshot=snapshot,
        )
        self.instinkt = providers.instinkt

    @property
    def identities(self):
        return (self.racio.identity, self.emocio.identity, self.instinkt.identity)


class _FailIfCalledInterpreter:
    interpreter_id = "c4_fail_if_called"
    interpreter_revision = "1"
    interpreter_policy = "c4_pre_downstream_gate_test"

    def __init__(self) -> None:
        self.calls = 0

    def interpret(self, request):
        del request
        self.calls += 1
        raise AssertionError("downstream interpreter must not run")


def _visual_processor(
    tmp_path: Path,
) -> tuple[DeterministicEmocioProcessor, RecordingBackend]:
    provider_artifacts = tmp_path / "provider-artifacts"
    image_store = LocalPngArtifactStore(provider_artifacts)
    render_backend = RecordingBackend()
    renderer = CurrentFirstEmocioRenderer(
        provider=DiffusersImageRenderer(
            identity=renderer_identity(),
            backend=render_backend,
            artifact_store=image_store,
        ),
        settings=RenderSettings(
            width=4,
            height=3,
            num_inference_steps=2,
            guidance_scale=1.0,
            negative_prompt="",
            timeout_seconds=2.0,
        ),
    )
    snapshot, manifest_digest = _snapshot(tmp_path)
    encoder = DinoV2BaseImageEncoder(
        runtime=DinoV2RuntimeConfig(
            local_snapshot_path=str(snapshot),
            expected_snapshot_manifest_sha256=manifest_digest,
            device="cpu",
        ),
        image_store=image_store,
        vector_store=LocalFloat32VectorStore(provider_artifacts),
        backend=RecordingFeatureBackend(),
    )
    policy = VisualValuationPolicyConfig.create(
        policy=VisualValuationPolicy.create(
            structured_weight=1.0,
            desired_similarity_weight=1.0,
            broken_avoidance_weight=1.0,
            seed_consistency_penalty=0.0,
            uncertainty_penalty=0.0,
        )
    )
    return (
        DeterministicEmocioProcessor(
            renderer=renderer,
            cognition_mode="visual_cognition",
            render_seed=43,
            image_encoder=encoder,
            visual_policy_config=policy,
            encoding_timeout_seconds=2.0,
        ),
        render_backend,
    )


def test_configured_structured_engine_persists_exact_replay_without_binaries(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(
        update={"run_id": "c4-configured-structured-engine"}
    )
    root = tmp_path / "structured"
    engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego-traces",
        clock=DeterministicExecutionClock(request.started_at),
        emocio_processor=DeterministicEmocioProcessor(
            cognition_mode="structured_only"
        ),
    )

    result = engine.run_cycle(request)
    execution = result.manifest.emocio_execution
    run_root = root / "runs" / request.run_id

    assert execution is not None
    assert execution.renderer_call_ids == ()
    assert execution.encoder_call_ids == ()
    assert execution.materialized_artifacts == ()
    assert result.emocio_execution.processing_artifact is not None
    assert (run_root / execution.processor_config_path).read_bytes() == (
        result.emocio_execution.runtime_config.canonical_json_bytes()
    )
    assert (run_root / execution.processing_artifact_path).read_bytes() == (
        result.emocio_execution.processing_artifact.canonical_json_bytes()
    )
    assert not (run_root / "emocio" / "embeddings").exists()
    assert FileArtifactStore(root / "runs").verify_run(request.run_id) == (
        result.manifest
    )
    (run_root / "emocio" / "embeddings").mkdir()
    with pytest.raises(ArtifactIntegrityError, match="directory inventory"):
        FileArtifactStore(root / "runs").verify_run(request.run_id)


def test_cold_replay_rejects_semantically_rewritten_duplicate_packet_view(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "c4-duplicate-view-rewrite"})
    root = tmp_path / "duplicate-view"
    result = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego-traces",
        clock=DeterministicExecutionClock(request.started_at),
        emocio_processor=DeterministicEmocioProcessor(),
    ).run_cycle(request)
    relative_path = "scene/emocio_packet.json"
    target = root / "runs" / request.run_id / relative_path
    original_bytes = target.read_bytes()
    mutated_packet = result.emocio_execution.packet.model_copy(
        update={"caveat": "Canonical but contradictory duplicate packet view."}
    )
    mutated_bytes = mutated_packet.canonical_json_bytes()
    target.write_bytes(mutated_bytes)

    original_record = next(
        item
        for item in result.manifest.artifact_inventory
        if item.relative_path == relative_path
    )
    metadata = {
        "schema_version": "rei-native-stored-artifact-v1",
        "run_id": request.run_id,
        "relative_path": relative_path,
        "content_sha256": hashlib.sha256(mutated_bytes).hexdigest(),
        "size_bytes": len(mutated_bytes),
    }
    mutated_record = type(original_record)(
        storage_id=content_id("stored", metadata),
        **metadata,
    )
    mutated_manifest = result.manifest.model_copy(
        update={
            "artifact_inventory": tuple(
                mutated_record if item.relative_path == relative_path else item
                for item in result.manifest.artifact_inventory
            )
        }
    )

    with pytest.raises(ArtifactIntegrityError, match="cold replay"):
        FileArtifactStore(root / "runs")._verify_emocio_execution(
            mutated_manifest
        )

    target.write_bytes(original_bytes)
    assert FileArtifactStore(root / "runs").verify_run(request.run_id) == (
        result.manifest
    )


def test_cold_replay_requires_exact_outer_identity_and_no_fallback(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "c4-outer-contract-rewrite"})
    root = tmp_path / "outer-contract"
    result = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego-traces",
        clock=DeterministicExecutionClock(request.started_at),
        emocio_processor=DeterministicEmocioProcessor(),
    ).run_cycle(request)
    execution = result.manifest.emocio_execution
    assert execution is not None
    outer_index = next(
        index
        for index, item in enumerate(result.manifest.provider_call_specs)
        if item.call_id == execution.outer_call_id
    )
    outer = result.manifest.provider_call_specs[outer_index]
    altered_specs = (
        outer.model_copy(
            update={
                "provider": outer.provider.model_copy(
                    update={"provider_id": "provider_c4_unapproved_identity"}
                )
            }
        ),
        outer.model_copy(
            update={
                "fallback_policy": ProviderFallbackPolicy(
                    mode="none",
                    no_fallback_reason="secret=C4-UNAPPROVED-FALLBACK-REASON",
                )
            }
        ),
    )
    store = FileArtifactStore(root / "runs")
    for altered in altered_specs:
        specs = list(result.manifest.provider_call_specs)
        specs[outer_index] = altered
        mutated_manifest = result.manifest.model_copy(
            update={"provider_call_specs": tuple(specs)}
        )
        with pytest.raises(ArtifactIntegrityError, match="cold replay"):
            store._verify_emocio_execution(mutated_manifest)
    warning_manifest = result.manifest.model_copy(
        update={"warnings": ("secret=C4-MANIFEST-WARNING",)}
    )
    with pytest.raises(ArtifactIntegrityError, match="cold replay"):
        store._verify_emocio_execution(warning_manifest)


def test_visual_engine_closes_nested_calls_and_cold_replays_png_and_vectors(
    tmp_path: Path,
) -> None:
    processor, render_backend = _visual_processor(tmp_path)
    request = _request().model_copy(update={"run_id": "c4-visual-engine"})
    root = tmp_path / "visual"
    engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego-traces",
        clock=SystemExecutionClock(),
        emocio_processor=processor,
    )

    result = engine.run_cycle(request)
    manifest = result.manifest
    execution = manifest.emocio_execution
    run_root = root / "runs" / request.run_id

    assert execution is not None
    assert len(execution.renderer_call_ids) == len(
        result.emocio_execution.rendered_images
    )
    assert len(execution.encoder_call_ids) == len(
        result.emocio_execution.processing.visual_observations
    )
    assert len(render_backend.calls) == len(execution.renderer_call_ids)
    assert {
        item.role for item in execution.materialized_artifacts
    } == {"image", "vector"}
    assert all(
        (run_root / item.relative_path).is_file()
        for item in execution.materialized_artifacts
    )
    vector_records = tuple(
        item
        for item in execution.materialized_artifacts
        if item.role == "vector"
    )
    assert len(vector_records) == len(execution.encoder_call_ids)
    assert len({item.relative_path for item in vector_records}) < len(
        vector_records
    )
    assert (run_root / "emocio" / "embeddings").is_dir()
    assert manifest.provider_call_specs[:3] == (
        result.racio_execution.call_spec,
        result.emocio_execution.call_spec,
        result.instinkt_execution.call_spec,
    )
    expected_call_ids = (
        result.racio_execution.call_spec.call_id,
        result.emocio_execution.call_spec.call_id,
        result.instinkt_execution.call_spec.call_id,
        *execution.renderer_call_ids,
        *execution.encoder_call_ids,
    )
    assert tuple(
        item.call_id for item in manifest.provider_call_specs
    ) == expected_call_ids
    assert tuple(item.call_id for item in manifest.provider_calls) == expected_call_ids
    assert canonical_json_bytes(manifest) == (
        run_root / "run_manifest.json"
    ).read_bytes()
    cold_store = FileArtifactStore(root / "runs")
    assert cold_store.verify_run(request.run_id) == manifest

    for orphan_path, orphan_bytes in (
        ("emocio/images/orphan.png", _png(1, 1, (1, 2, 3, 255))),
        ("emocio/embeddings/orphan.f32", b"\x00\x00\x00\x00"),
    ):
        orphan_target = run_root / orphan_path
        orphan_target.write_bytes(orphan_bytes)
        orphan_metadata = {
            "schema_version": "rei-native-stored-artifact-v1",
            "run_id": request.run_id,
            "relative_path": orphan_path,
            "content_sha256": hashlib.sha256(orphan_bytes).hexdigest(),
            "size_bytes": len(orphan_bytes),
        }
        orphan_record = type(manifest.artifact_inventory[0])(
            storage_id=content_id("stored", orphan_metadata),
            **orphan_metadata,
        )
        orphan_manifest = manifest.model_copy(
            update={
                "artifact_inventory": tuple(
                    sorted(
                        (*manifest.artifact_inventory, orphan_record),
                        key=lambda item: item.relative_path,
                    )
                )
            }
        )
        with pytest.raises(ArtifactIntegrityError, match="cold replay"):
            cold_store._verify_emocio_execution(orphan_manifest)
        orphan_target.unlink()

    tamper_targets = (
        execution.processor_config_path,
        execution.processing_artifact_path,
        next(
            item.relative_path
            for item in execution.materialized_artifacts
            if item.role == "image"
        ),
        next(
            item.relative_path
            for item in execution.materialized_artifacts
            if item.role == "vector"
        ),
    )
    for relative_path in tamper_targets:
        target = run_root / relative_path
        original = target.read_bytes()
        target.write_bytes(bytes((original[0] ^ 1,)) + original[1:])
        with pytest.raises(ArtifactIntegrityError):
            FileArtifactStore(root / "runs").verify_run(request.run_id)
        target.write_bytes(original)
    image_path = next(
        item.relative_path
        for item in execution.materialized_artifacts
        if item.role == "image"
    )
    image_target = run_root / image_path
    original_image = image_target.read_bytes()
    altered_image = _png(4, 3, (10, 220, 35, 255))
    image_target.write_bytes(altered_image)
    original_inventory_record = next(
        item
        for item in manifest.artifact_inventory
        if item.relative_path == image_path
    )
    altered_metadata = {
        "schema_version": "rei-native-stored-artifact-v1",
        "run_id": request.run_id,
        "relative_path": image_path,
        "content_sha256": hashlib.sha256(altered_image).hexdigest(),
        "size_bytes": len(altered_image),
    }
    altered_inventory_record = type(original_inventory_record)(
        storage_id=content_id("stored", altered_metadata),
        **altered_metadata,
    )
    altered_manifest = manifest.model_copy(
        update={
            "artifact_inventory": tuple(
                altered_inventory_record
                if item.relative_path == image_path
                else item
                for item in manifest.artifact_inventory
            )
        }
    )
    with pytest.raises(ArtifactIntegrityError, match="cold replay"):
        FileArtifactStore(root / "runs")._verify_emocio_execution(
            altered_manifest
        )
    image_target.write_bytes(original_image)
    assert FileArtifactStore(root / "runs").verify_run(request.run_id) == manifest


def test_synthetic_clock_rejects_rendering_before_backend_invocation(
    tmp_path: Path,
) -> None:
    processor, render_backend = _visual_processor(tmp_path)
    request = _request().model_copy(update={"run_id": "c4-synthetic-clock-reject"})
    root = tmp_path / "synthetic"
    engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego-traces",
        clock=DeterministicExecutionClock(request.started_at),
        emocio_processor=processor,
    )

    with pytest.raises(ValueError, match="system execution clock"):
        engine.run_cycle(request)

    assert render_backend.calls == []


def test_engine_accepts_pre_c4_emocio_execution_shape_as_legacy(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "c4-old-execution-shape"})
    root = tmp_path / "old-shape"
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(root / "runs"),
        ego_trace_store=FileEgoTraceStore(root / "ego-traces"),
        providers=_OldShapeProviderSet(),
        clock=DeterministicExecutionClock(request.started_at),
    )

    result = engine.run_cycle(request)

    assert result.manifest.emocio_execution is None
    assert FileArtifactStore(root / "runs").verify_run(request.run_id) == (
        result.manifest
    )


def test_engine_rejects_pre_c4_execution_shape_for_configured_call(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "c4-old-configured-shape"})
    root = tmp_path / "old-configured-shape"
    trace_store = FileEgoTraceStore(root / "ego-traces")
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(root / "runs"),
        ego_trace_store=trace_store,
        providers=_OldShapeProviderSet(DeterministicEmocioProcessor()),
        clock=DeterministicExecutionClock(request.started_at),
    )

    with pytest.raises(ValueError, match="shape differs"):
        engine.run_cycle(request)

    assert trace_store.load_trace(request.ego_id).measures == ()


def test_configured_warning_injection_fails_before_downstream_calls(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "c4-warning-injection"})
    root = tmp_path / "warning-injection"
    interpreter = _FailIfCalledInterpreter()
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(root / "runs"),
        ego_trace_store=FileEgoTraceStore(root / "ego-traces"),
        providers=_TamperingConfiguredProviderSet(
            DeterministicEmocioProcessor(),
            warning="secret=C4-WARNING-INJECTION",
        ),
        clock=DeterministicExecutionClock(request.started_at),
        interpreter=interpreter,
    )

    with pytest.raises(ValueError, match="processing artifact differs"):
        engine.run_cycle(request)

    assert interpreter.calls == 0


def test_configured_snapshot_substitution_fails_before_downstream_calls(
    tmp_path: Path,
) -> None:
    processor, _ = _visual_processor(tmp_path)
    request = _request().model_copy(update={"run_id": "c4-snapshot-substitution"})
    root = tmp_path / "snapshot-substitution"
    interpreter = _FailIfCalledInterpreter()
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(root / "runs"),
        ego_trace_store=FileEgoTraceStore(root / "ego-traces"),
        providers=_TamperingConfiguredProviderSet(
            processor,
            snapshot=True,
        ),
        clock=SystemExecutionClock(),
        interpreter=interpreter,
    )

    with pytest.raises(ValueError, match="processing provenance"):
        engine.run_cycle(request)

    assert interpreter.calls == 0


def test_configured_prepared_replay_failure_prevents_ego_trace_commit(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "c4-prepared-replay-reject"})
    root = tmp_path / "prepared-reject"
    trace_store = FileEgoTraceStore(root / "ego-traces")
    engine = ReiNativeEngine(
        artifact_store=_RejectingPreparedStore(root / "runs"),
        ego_trace_store=trace_store,
        providers=build_deterministic_native_providers(
            emocio_processor=DeterministicEmocioProcessor(),
        ),
        clock=DeterministicExecutionClock(request.started_at),
    )

    with pytest.raises(ArtifactIntegrityError, match="configured replay rejection"):
        engine.run_cycle(request)

    assert trace_store.load_trace(request.ego_id).measures == ()
    run_root = root / "runs" / request.run_id
    assert (run_root / "diagnostics" / "prepared_manifest.json").is_file()
    assert not (run_root / "run_manifest.json").exists()
