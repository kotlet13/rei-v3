from __future__ import annotations

import ast
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from typing import Any, Iterator

import pytest

from app.backend.rei_next.diagnostics import InvariantReport
from app.backend.rei_next.ego.trace_store import FileEgoTraceStore
from app.backend.rei_next.engine import (
    ReiNativeCycleRequest,
    ReiNativeCycleResult,
    ReiNativeEngine,
)
from app.backend.rei_next.governance.profiles import parse_character_profile
from app.backend.rei_next.ids import canonical_json_bytes, content_id
from app.backend.rei_next.models.character import CHARACTER_PROFILE_ORDER
from app.backend.rei_next.models.ego import EgoMeasure
from app.backend.rei_next.models.instinkt import InstinktProjectionObservation
from app.backend.rei_next.models.provider import (
    ProviderCallRecord,
    ProviderIdentity,
    ProviderParameter,
    ensure_call_record_contract,
)
from app.backend.rei_next.models.run import NativeMindBundle, RunManifest
from app.backend.rei_next.persistence import (
    RUN_TREE_DIRECTORIES,
    ArtifactExistsError,
    ArtifactIntegrityError,
    FileArtifactStore,
)
from app.backend.rei_next.providers.deterministic import (
    build_deterministic_native_providers,
    emocio_world_input_id,
    instinkt_association_input_id,
)
from app.backend.rei_next.providers.native import (
    DeterministicExecutionClock,
    build_provider_call_spec,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
RUNNER = ROOT / "scripts" / "run_rei_native_cycle.py"
MATRIX_RUNNER = ROOT / "scripts" / "run_rei_native_profile_matrix.py"
RESERVATION_PATH = "diagnostics/run_reservation.json"


def _request() -> ReiNativeCycleRequest:
    return ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())


def _run(root: Path) -> tuple[ReiNativeEngine, ReiNativeCycleResult]:
    engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(_request().started_at),
    )
    return engine, engine.run_cycle(_request())


class _BarrierRacioProvider:
    def __init__(self, provider: Any, barrier: Barrier) -> None:
        self.provider = provider
        self.barrier = barrier

    @property
    def identity(self):
        return self.provider.identity

    def required_input_artifact_ids(self, packet):
        return self.provider.required_input_artifact_ids(packet)

    def build_call_spec(self, packet):
        return self.provider.build_call_spec(packet)

    def execute(self, packet, *, call, clock):
        self.barrier.wait(timeout=5)
        return self.provider.execute(packet, call=call, clock=clock)


class _BarrierEmocioProvider:
    def __init__(self, provider: Any, barrier: Barrier) -> None:
        self.provider = provider
        self.barrier = barrier

    @property
    def identity(self):
        return self.provider.identity

    def required_input_artifact_ids(self, scene, world, packet):
        return self.provider.required_input_artifact_ids(scene, world, packet)

    def build_call_spec(self, scene, world, packet):
        return self.provider.build_call_spec(scene, world, packet)

    def execute(self, scene, world, *, packet, call, clock):
        self.barrier.wait(timeout=5)
        return self.provider.execute(
            scene,
            world,
            packet=packet,
            call=call,
            clock=clock,
        )


class _BarrierInstinktProvider:
    def __init__(self, provider: Any, barrier: Barrier) -> None:
        self.provider = provider
        self.barrier = barrier

    @property
    def identity(self):
        return self.provider.identity

    def required_input_artifact_ids(self, **kwargs):
        return self.provider.required_input_artifact_ids(**kwargs)

    def build_call_spec(self, **kwargs):
        return self.provider.build_call_spec(**kwargs)

    def execute(
        self,
        *,
        scene,
        packet,
        source_body_state,
        option_effects,
        config,
        associations,
        call,
        clock,
    ):
        self.barrier.wait(timeout=5)
        return self.provider.execute(
            scene=scene,
            packet=packet,
            source_body_state=source_body_state,
            option_effects=option_effects,
            config=config,
            associations=associations,
            call=call,
            clock=clock,
        )


class _BarrierProviderSet:
    def __init__(self, barrier: Barrier) -> None:
        providers = build_deterministic_native_providers()
        self.racio = _BarrierRacioProvider(providers.racio, barrier)
        self.emocio = _BarrierEmocioProvider(providers.emocio, barrier)
        self.instinkt = _BarrierInstinktProvider(providers.instinkt, barrier)

    @property
    def identities(self):
        return (self.racio.identity, self.emocio.identity, self.instinkt.identity)


class _FailingArtifactStore:
    def __init__(self, store: FileArtifactStore, fail_path: str) -> None:
        self.store = store
        self.fail_path = fail_path

    @property
    def identity(self):
        return self.store.identity

    def ensure_run_tree(self, run_id):
        return self.store.ensure_run_tree(run_id)

    def write_json(self, run_id, relative_path, artifact, *, overwrite=False):
        if relative_path == self.fail_path:
            raise RuntimeError(f"injected failure at {relative_path}")
        return self.store.write_json(
            run_id,
            relative_path,
            artifact,
            overwrite=overwrite,
        )

    def write_bytes(self, run_id, relative_path, content, *, overwrite=False):
        if relative_path == self.fail_path:
            raise RuntimeError(f"injected failure at {relative_path}")
        return self.store.write_bytes(
            run_id,
            relative_path,
            content,
            overwrite=overwrite,
        )

    def read_bytes(self, storage_id):
        return self.store.read_bytes(storage_id)


_MODEL_PARAMETERS = (
    ProviderParameter(name="temperature", canonical_json_value="0"),
)


def _strict_model_identity(kind: str) -> ProviderIdentity:
    payload = {
        "kind": kind,
        "implementation": f"tests.StrictModel{kind}",
        "implementation_revision": "b11-test-v1",
        "uses_model": True,
        "model": "strict-fake-native-model",
        "model_revision": "immutable-test-revision",
    }
    return ProviderIdentity(
        provider_id=content_id("provider", payload),
        **payload,
    )


def _model_execution(execution: Any, call: Any):
    timing = execution.call_record
    record = ProviderCallRecord(
        call_id=call.call_id,
        spec_hash=call.content_hash(),
        request_id=call.request_id,
        input_artifact_ids=call.input_artifact_ids,
        provider=call.provider,
        seed=call.seed,
        parameters=call.parameters,
        timeout_seconds=call.timeout_seconds,
        started_at=timing.started_at,
        primary_finished_at=timing.primary_finished_at,
        finished_at=timing.finished_at,
        status="succeeded",
        primary_status="succeeded",
        output_artifact_ids=(execution.conclusion.conclusion_id,),
        safety_notice=call.safety_notice,
    )
    return replace(execution, call_spec=call, call_record=record)


class _StrictModelRacioProvider:
    def __init__(self) -> None:
        self.base = build_deterministic_native_providers().racio
        self._identity = _strict_model_identity("text_reasoner")

    @property
    def identity(self):
        return self._identity

    def required_input_artifact_ids(self, packet):
        return self.base.required_input_artifact_ids(packet)

    def build_call_spec(self, packet):
        return build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=self.required_input_artifact_ids(packet),
            seed=101,
            parameters=_MODEL_PARAMETERS,
        )

    def execute(self, packet, *, call, clock):
        base_call = self.base.build_call_spec(packet)
        return _model_execution(
            self.base.execute(packet, call=base_call, clock=clock),
            call,
        )


class _StrictModelEmocioProvider:
    def __init__(self) -> None:
        self.base = build_deterministic_native_providers().emocio
        self._identity = _strict_model_identity("visual_world_model")

    @property
    def identity(self):
        return self._identity

    def required_input_artifact_ids(self, scene, world, packet):
        return self.base.required_input_artifact_ids(scene, world, packet)

    def build_call_spec(self, scene, world, packet):
        return build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=self.required_input_artifact_ids(
                scene, world, packet
            ),
            seed=102,
            parameters=_MODEL_PARAMETERS,
        )

    def execute(self, scene, world, *, packet, call, clock):
        base_call = self.base.build_call_spec(scene, world, packet)
        return _model_execution(
            self.base.execute(
                scene,
                world,
                packet=packet,
                call=base_call,
                clock=clock,
            ),
            call,
        )


class _StrictModelInstinktProvider:
    def __init__(self) -> None:
        self.base = build_deterministic_native_providers().instinkt
        self._identity = _strict_model_identity("body_dynamics")

    @property
    def identity(self):
        return self._identity

    def required_input_artifact_ids(self, **kwargs):
        return self.base.required_input_artifact_ids(**kwargs)

    def build_call_spec(self, **kwargs):
        return build_provider_call_spec(
            identity=self.identity,
            request_id=kwargs["packet"].packet_id,
            input_artifact_ids=self.required_input_artifact_ids(**kwargs),
            seed=103,
            parameters=_MODEL_PARAMETERS,
        )

    def execute(
        self,
        *,
        scene,
        packet,
        source_body_state,
        option_effects,
        config,
        associations,
        call,
        clock,
    ):
        inputs = {
            "scene": scene,
            "packet": packet,
            "source_body_state": source_body_state,
            "option_effects": option_effects,
            "config": config,
            "associations": associations,
        }
        base_call = self.base.build_call_spec(**inputs)
        return _model_execution(
            self.base.execute(**inputs, call=base_call, clock=clock),
            call,
        )


class _StrictModelProviderSet:
    def __init__(self) -> None:
        self.racio = _StrictModelRacioProvider()
        self.emocio = _StrictModelEmocioProvider()
        self.instinkt = _StrictModelInstinktProvider()

    @property
    def identities(self):
        return (self.racio.identity, self.emocio.identity, self.instinkt.identity)


class _SpecSwappingRacioProvider:
    def __init__(self, provider: Any) -> None:
        self.provider = provider

    @property
    def identity(self):
        return self.provider.identity

    def required_input_artifact_ids(self, packet):
        return self.provider.required_input_artifact_ids(packet)

    def build_call_spec(self, packet):
        return self.provider.build_call_spec(packet)

    def execute(self, packet, *, call, clock):
        execution = self.provider.execute(packet, call=call, clock=clock)
        swapped = build_provider_call_spec(
            identity=self.identity,
            request_id=packet.packet_id,
            input_artifact_ids=self.required_input_artifact_ids(packet),
            timeout_seconds=31.0,
        )
        return _model_execution(execution, swapped)


class _SpecSwappingProviderSet:
    def __init__(self) -> None:
        providers = build_deterministic_native_providers()
        self.racio = _SpecSwappingRacioProvider(providers.racio)
        self.emocio = providers.emocio
        self.instinkt = providers.instinkt

    @property
    def identities(self):
        return (self.racio.identity, self.emocio.identity, self.instinkt.identity)


def _run_directory(root: Path, result: ReiNativeCycleResult) -> Path:
    return root / "runs" / result.request.run_id


def _files_below(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _expected_artifact_paths(result: ReiNativeCycleResult) -> set[str]:
    visual_state = result.emocio_execution.visual_state
    visual_scene_ids = {
        scene.scene_id
        for scene in (
            visual_state.current_scene,
            visual_state.desired_scene,
            visual_state.broken_scene,
            *visual_state.option_rollouts,
        )
    }
    return {
        "scene/event.json",
        "scene/racio_packet.json",
        "scene/emocio_packet.json",
        "scene/instinkt_packet.json",
        "scene/racio_world.json",
        "scene/emocio_world.json",
        "native/bundle.json",
        "native/racio.json",
        "native/emocio.json",
        "native/instinkt.json",
        "emocio/visual_state.json",
        "emocio/images/index.json",
        *(f"emocio/scenes/{scene_id}.json" for scene_id in visual_scene_ids),
        "instinkt/body_before.json",
        "instinkt/simulation_config.json",
        "instinkt/option_effects.json",
        "instinkt/ego_memory.json",
        "instinkt/option_rollouts.json",
        "instinkt/body_after.json",
        "communication/manifestations.json",
        "communication/interpretations.json",
        "communication/translation_gaps.json",
        "governance/character.json",
        "governance/effective_authority.json",
        "governance/mandate.json",
        "governance/delegation.json",
        "conscious/mandate_view.json",
        "conscious/decision.json",
        "conscious/narrative.json",
        "behavior/resultant.json",
        "ego/measure.json",
        "ego/trace.json",
        "ego/composition_snapshot.json",
        "ego/racio_projection.json",
        "ego/emocio_projection.json",
        "ego/instinkt_projection.json",
        RESERVATION_PATH,
        "diagnostics/invariants.json",
        "diagnostics/report.md",
        "diagnostics/prepared_manifest.json",
        "run_manifest.json",
    }


def _all_mapping_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield str(key)
            yield from _all_mapping_keys(nested)
    elif isinstance(value, (tuple, list)):
        for nested in value:
            yield from _all_mapping_keys(nested)


def test_checked_in_request_runs_complete_exact_tree_and_closes_manifest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "complete"
    engine, result = _run(root)
    run_directory = _run_directory(root, result)
    files = _files_below(run_directory)

    assert set(files) == _expected_artifact_paths(result)
    assert {
        path.relative_to(run_directory).as_posix()
        for path in run_directory.rglob("*")
        if path.is_dir()
    } == set(RUN_TREE_DIRECTORIES)

    receipt_paths = tuple(item.relative_path for item in result.stored_artifacts)
    assert len(receipt_paths) == len(set(receipt_paths)) == len(files)
    assert receipt_paths[0] == RESERVATION_PATH
    assert receipt_paths[-1] == "run_manifest.json"
    assert set(receipt_paths) == set(files)
    assert (run_directory / "run_manifest.json").stat().st_mtime_ns >= max(
        path.stat().st_mtime_ns
        for path in run_directory.rglob("*")
        if path.is_file() and path.name != "run_manifest.json"
    )

    persisted_manifest = RunManifest.model_validate_json(files["run_manifest.json"])
    persisted_invariants = InvariantReport.model_validate_json(
        files["diagnostics/invariants.json"]
    )
    persisted_bundle = NativeMindBundle.model_validate_json(files["native/bundle.json"])
    persisted_measure = EgoMeasure.model_validate_json(files["ego/measure.json"])
    assert persisted_manifest == result.manifest
    assert persisted_invariants == result.invariants
    assert persisted_bundle == result.native_bundle
    assert persisted_measure == result.ego_measure
    assert files["run_manifest.json"] == canonical_json_bytes(result.manifest)
    assert result.invariants.all_passed
    assert all(check.status == "passed" for check in result.invariants.checks)

    manifest = result.manifest
    assert manifest.status == "completed"
    assert manifest.native_artifact_source == "produced"
    assert manifest.native_assembly == result.native_assembly
    assert manifest.schema_version == "rei-native-run-manifest-v2"
    assert manifest.manifest_id is not None
    assert manifest.manifest_hash is not None
    assert manifest.artifact_inventory_hash is not None
    assert len(manifest.providers) == 5
    assert len(manifest.provider_call_specs) == len(manifest.provider_calls) == 3
    assert {identity.kind for identity in manifest.providers} == {
        "text_reasoner",
        "visual_world_model",
        "body_dynamics",
        "artifact_store",
        "ego_trace_store",
    }
    assert all(identity.uses_model is False for identity in manifest.providers)
    inventory_paths = tuple(
        item.relative_path for item in manifest.artifact_inventory
    )
    assert inventory_paths == tuple(sorted(inventory_paths))
    assert set(inventory_paths) == set(files) - {
        "diagnostics/prepared_manifest.json",
        "run_manifest.json",
    }
    assert files["diagnostics/prepared_manifest.json"] == files["run_manifest.json"]
    receipts_by_path = {
        item.relative_path: item for item in result.stored_artifacts
    }
    assert tuple(
        item.model_dump(mode="python") for item in manifest.artifact_inventory
    ) == tuple(
        receipts_by_path[path].model_dump(mode="python")
        for path in inventory_paths
    )
    for spec, record in zip(
        manifest.provider_call_specs,
        manifest.provider_calls,
        strict=True,
    ):
        ensure_call_record_contract(spec, record)
        assert record.status == "succeeded"
        assert len(record.output_artifact_ids) == 1
    assert {
        (item.role, item.artifact_id, item.sha256)
        for item in manifest.native_artifact_hashes
    } == {
        (
            "native_bundle",
            result.native_bundle.bundle_id,
            result.native_bundle.immutable_hash,
        ),
        (
            "racio_native",
            result.native_bundle.racio.conclusion_id,
            result.native_bundle.racio.content_hash(),
        ),
        (
            "emocio_native",
            result.native_bundle.emocio.conclusion_id,
            result.native_bundle.emocio.content_hash(),
        ),
        (
            "instinkt_native",
            result.native_bundle.instinkt.conclusion_id,
            result.native_bundle.instinkt.content_hash(),
        ),
    }
    result.native_bundle.validate_native_lineage(
        scene=result.request.scene,
        racio_packet=result.racio_packet,
        emocio_packet=result.emocio_packet,
        instinkt_packet=result.instinkt_packet,
        emocio_visual_state=result.emocio_execution.visual_state,
        instinkt_body_state=result.request.body_state,
        instinkt_rollouts=result.instinkt_execution.rollouts,
    )

    assert result.request.outcome is None
    assert result.ego_measure.outcome is None
    assert result.ego_trace.measures[-1].outcome is None
    assert json.loads(files["ego/measure.json"])["outcome"] is None

    restarted_store = FileArtifactStore(root / "runs")
    assert restarted_store.verify_run(result.request.run_id) == result.manifest
    for artifact in result.stored_artifacts:
        assert restarted_store.read_verified(artifact) == files[artifact.relative_path]
    manifest_receipt = result.stored_artifacts[-1]
    assert restarted_store.read_bytes(manifest_receipt.storage_id) == files[
        "run_manifest.json"
    ]
    restarted_trace = FileEgoTraceStore(root / "ego_traces").load_trace(
        result.request.ego_id
    )
    assert restarted_trace == result.ego_trace
    assert engine.ego_trace_store.load_trace(result.request.ego_id) == result.ego_trace


def test_three_native_calls_are_concurrent_and_profile_blind(tmp_path: Path) -> None:
    root = tmp_path / "concurrency"
    request = _request()
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(root / "runs"),
        ego_trace_store=FileEgoTraceStore(root / "ego_traces"),
        providers=_BarrierProviderSet(Barrier(3)),
        clock=DeterministicExecutionClock(request.started_at),
    )
    result = engine.run_cycle(request)
    calls = result.manifest.provider_calls
    assembly = result.manifest.native_assembly
    assert assembly is not None

    intervals = {
        (call.started_at, call.primary_finished_at, call.finished_at)
        for call in calls
    }
    assert len(calls) == 3
    assert len(intervals) == 1
    assert all(call.started_at < call.finished_at <= assembly.started_at for call in calls)
    # The shared barrier would time out if the engine entered any provider
    # sequentially. Timestamps remain a separate provenance assertion.

    packets = (
        result.racio_packet,
        result.emocio_packet,
        result.instinkt_packet,
    )
    forbidden_key_fragments = ("profile", "character", "authority", "acceptance")
    sensitive_values = (
        result.request.character.character_id,
        result.request.character.profile_id,
        result.request.acceptance_state.acceptance_state_id,
        result.request.acceptance_state.content_hash(),
    )
    for artifact in packets:
        payload = artifact.model_dump(mode="python", round_trip=True)
        assert not any(
            fragment in key.casefold()
            for key in _all_mapping_keys(payload)
            for fragment in forbidden_key_fragments
        )
        serialized = canonical_json_bytes(artifact).decode("utf-8")
        assert all(value not in serialized for value in sensitive_values)

    for spec in result.manifest.provider_call_specs:
        call_input_scope = {
            "request_id": spec.request_id,
            "input_artifact_ids": spec.input_artifact_ids,
            "parameters": spec.parameters,
        }
        assert not any(
            fragment in key.casefold()
            for key in _all_mapping_keys(call_input_scope)
            for fragment in forbidden_key_fragments
        )
        serialized = canonical_json_bytes(call_input_scope).decode("utf-8")
        assert all(value not in serialized for value in sensitive_values)

    racio_spec, emocio_spec, instinkt_spec = result.manifest.provider_call_specs
    assert racio_spec.request_id == result.racio_packet.packet_id
    assert racio_spec.input_artifact_ids == (result.racio_packet.packet_id,)
    assert emocio_spec.request_id == result.emocio_packet.packet_id
    assert set(emocio_spec.input_artifact_ids) == {
        result.request.scene.event_id,
        result.emocio_packet.packet_id,
        emocio_world_input_id(result.request.emocio_world),
    }
    changed_world = result.request.emocio_world.model_copy(
        update={
            "desired_scenes": (
                *result.request.emocio_world.desired_scenes,
                "same world ID but different admitted content",
            )
        }
    )
    assert changed_world.world_id == result.request.emocio_world.world_id
    assert changed_world.content_hash() != result.request.emocio_world.content_hash()
    assert emocio_world_input_id(changed_world) != emocio_world_input_id(
        result.request.emocio_world
    )
    assert engine.providers.emocio.required_input_artifact_ids(
        result.request.scene,
        changed_world,
        result.emocio_packet,
    ) != engine.providers.emocio.required_input_artifact_ids(
        result.request.scene,
        result.request.emocio_world,
        result.emocio_packet,
    )
    assert instinkt_spec.request_id == result.instinkt_packet.packet_id
    assert set(instinkt_spec.input_artifact_ids) == {
        result.request.scene.event_id,
        result.instinkt_packet.packet_id,
        result.request.body_state.body_state_id,
        result.request.instinkt_config.config_id,
        *(effect.effect_id for effect in result.instinkt_execution.option_effects),
    }


def test_engine_accepts_model_backed_native_providers_and_records_seeds(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "b11-model-provider-test"})
    root = tmp_path / "model_providers"
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(root / "runs"),
        ego_trace_store=FileEgoTraceStore(root / "ego_traces"),
        providers=_StrictModelProviderSet(),
        clock=DeterministicExecutionClock(request.started_at),
    )

    result = engine.run_cycle(request)

    native_identities = result.manifest.providers[:3]
    assert all(identity.uses_model for identity in native_identities)
    assert {item.seed for item in result.manifest.seeds} == {101, 102, 103}
    assert len(result.manifest.seeds) == 3
    assert all(
        spec.parameters == _MODEL_PARAMETERS and spec.seed is not None
        for spec in result.manifest.provider_call_specs
    )
    for spec, record in zip(
        result.manifest.provider_call_specs,
        result.manifest.provider_calls,
        strict=True,
    ):
        ensure_call_record_contract(spec, record)
    assert FileArtifactStore(root / "runs").verify_run(request.run_id) == result.manifest


def test_engine_rejects_provider_that_swaps_preapproved_call_spec(
    tmp_path: Path,
) -> None:
    request = _request().model_copy(update={"run_id": "b11-swapped-spec-test"})
    root = tmp_path / "swapped_spec"
    trace_store = FileEgoTraceStore(root / "ego_traces")
    engine = ReiNativeEngine(
        artifact_store=FileArtifactStore(root / "runs"),
        ego_trace_store=trace_store,
        providers=_SpecSwappingProviderSet(),
        clock=DeterministicExecutionClock(request.started_at),
    )

    with pytest.raises(ValueError, match="pre-approved contract"):
        engine.run_cycle(request)

    assert trace_store.load_trace(request.ego_id).measures == ()


@pytest.mark.parametrize(
    "relative_path",
    (
        "scene/event.json",
        "governance/mandate.json",
        "ego/trace.json",
        "run_manifest.json",
    ),
)
def test_cold_verifier_rejects_tampered_critical_artifacts(
    tmp_path: Path,
    relative_path: str,
) -> None:
    root = tmp_path / relative_path.replace("/", "_")
    _, result = _run(root)
    run_root = _run_directory(root, result)
    (run_root / relative_path).write_bytes(b"{}")

    with pytest.raises(ArtifactIntegrityError):
        FileArtifactStore(root / "runs").verify_run(result.request.run_id)


def test_cold_verifier_rejects_missing_and_extra_run_entries(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"
    _, missing_result = _run(missing_root)
    missing_run = _run_directory(missing_root, missing_result)
    (missing_run / "native" / "racio.json").unlink()
    with pytest.raises(ArtifactIntegrityError):
        FileArtifactStore(missing_root / "runs").verify_run(
            missing_result.request.run_id
        )

    extra_root = tmp_path / "extra"
    _, extra_result = _run(extra_root)
    extra_run = _run_directory(extra_root, extra_result)
    (extra_run / "evil.bin").write_bytes(b"not inventoried")
    with pytest.raises(ArtifactIntegrityError, match="non-canonical|inventory"):
        FileArtifactStore(extra_root / "runs").verify_run(extra_result.request.run_id)


def test_cold_verifier_rejects_extra_reparse_entry(tmp_path: Path) -> None:
    root = tmp_path / "extra_reparse"
    _, result = _run(root)
    run_root = _run_directory(root, result)
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"{}")
    link = run_root / "diagnostics" / "extra_link.json"
    try:
        link.symlink_to(outside)
    except (NotImplementedError, OSError):
        pytest.skip("This platform does not permit file symlinks for the test user")

    with pytest.raises(ArtifactIntegrityError, match="symlink or reparse"):
        FileArtifactStore(root / "runs").verify_run(result.request.run_id)


def test_cycle_replays_byte_for_byte_across_clean_roots(tmp_path: Path) -> None:
    first_root = tmp_path / "replay_a"
    second_root = tmp_path / "replay_b"
    _, first = _run(first_root)
    _, second = _run(second_root)

    assert first.native_bundle == second.native_bundle
    assert first.governance == second.governance
    assert first.conscious_decision == second.conscious_decision
    assert first.behavior_resultant == second.behavior_resultant
    assert first.ego_measure == second.ego_measure
    assert first.ego_trace == second.ego_trace
    assert first.composition_snapshot == second.composition_snapshot
    assert first.projections == second.projections
    assert first.manifest == second.manifest
    assert first.invariants == second.invariants
    assert first.stored_artifacts == second.stored_artifacts
    assert _files_below(_run_directory(first_root, first)) == _files_below(
        _run_directory(second_root, second)
    )


def test_second_cycle_consumes_exact_modality_projections_without_fake_loss(
    tmp_path: Path,
) -> None:
    root = tmp_path / "longitudinal"
    first_request = _request()
    first_engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(first_request.started_at),
    )
    first = first_engine.run_cycle(first_request)
    second_request = first_request.model_copy(
        update={
            "run_id": "b11-e2e-cycle-2",
            "started_at": first_request.started_at + timedelta(seconds=1),
            "historical_bundles": (first.native_bundle,),
        }
    )
    second_engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(second_request.started_at),
    )
    second = second_engine.run_cycle(second_request)

    projections = first.projections
    assert second.prior_snapshot == first.composition_snapshot
    assert second.prior_projections == projections
    assert second.racio_packet.previous_racio_projection_ids == (
        projections.racio.projection_id,
    )
    assert second.racio_packet.previous_racio_projection_hashes == (
        projections.racio.projection_hash,
    )
    assert second.emocio_packet.previous_emocio_projection_ids == (
        projections.emocio.projection_id,
    )
    assert second.emocio_packet.previous_emocio_projection_hashes == (
        projections.emocio.projection_hash,
    )
    assert second.instinkt_packet.previous_instinkt_projection_ids == (
        projections.instinkt.projection_id,
    )
    assert second.instinkt_packet.previous_instinkt_projection_hashes == (
        projections.instinkt.projection_hash,
    )

    assert set(projections.racio.statements).issubset(
        second.racio_world_input.explicit_beliefs
    )
    assert set(projections.racio.causal_links).issubset(
        second.racio_world_input.rules
    )
    assert set(projections.emocio.recurring_scenes).issubset(
        second.emocio_world_input.visual_memories
    )
    assert set(projections.emocio.desire_motifs).issubset(
        second.emocio_world_input.desired_scenes
    )

    projection_ids = {
        "R": projections.racio.projection_id,
        "E": projections.emocio.projection_id,
        "I": projections.instinkt.projection_id,
    }
    serialized_packets = {
        "R": canonical_json_bytes(second.racio_packet).decode("utf-8"),
        "E": canonical_json_bytes(second.emocio_packet).decode("utf-8"),
        "I": canonical_json_bytes(second.instinkt_packet).decode("utf-8"),
    }
    for mind, serialized in serialized_packets.items():
        assert projection_ids[mind] in serialized
        assert all(
            projection_id not in serialized
            for other, projection_id in projection_ids.items()
            if other != mind
        )

    associations = second.instinkt_execution.associations
    assert associations
    assert first_request.outcome is None
    assert projections.instinkt.losses == ()
    assert all(
        isinstance(item, InstinktProjectionObservation) for item in associations
    )
    assert all(
        rollout.association_matches
        for rollout in second.instinkt_execution.rollouts
    )
    assert instinkt_association_input_id(associations) in (
        second.instinkt_execution.call_spec.input_artifact_ids
    )

    provider = build_deterministic_native_providers().instinkt
    baseline_spec = provider.build_call_spec(
        scene=second_request.scene,
        packet=second.instinkt_packet,
        source_body_state=second_request.body_state,
        option_effects=second.instinkt_execution.option_effects,
        config=second_request.instinkt_config,
        associations=(),
    )
    baseline = provider.execute(
        scene=second_request.scene,
        packet=second.instinkt_packet,
        source_body_state=second_request.body_state,
        option_effects=second.instinkt_execution.option_effects,
        config=second_request.instinkt_config,
        associations=(),
        call=baseline_spec,
        clock=DeterministicExecutionClock(second_request.started_at),
    )
    assert all(not rollout.association_matches for rollout in baseline.rollouts)
    assert baseline.conclusion.conclusion_id != second.instinkt_execution.conclusion.conclusion_id
    assert {
        item.option_id: (item.predicted_loss, item.recoverability)
        for item in baseline.rollouts
    } == {
        item.option_id: (item.predicted_loss, item.recoverability)
        for item in second.instinkt_execution.rollouts
    }
    assert len(second.ego_trace.measures) == 2


@pytest.mark.parametrize(
    "bundle_update",
    (
        {"immutable_hash": "0" * 64},
        {"scene_id": "wrong_historical_event"},
    ),
)
def test_historical_bundle_hash_and_event_must_match_trace(
    tmp_path: Path,
    bundle_update: dict[str, str],
) -> None:
    field_name = next(iter(bundle_update))
    root = tmp_path / field_name
    first_engine, first = _run(root)
    del first_engine
    bad_bundle = first.native_bundle.model_copy(update=bundle_update)
    request = first.request.model_copy(
        update={
            "run_id": f"bad-history-{field_name}",
            "started_at": first.request.started_at + timedelta(seconds=1),
            "historical_bundles": (bad_bundle,),
        }
    )
    engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(request.started_at),
    )
    with pytest.raises(ValueError, match="identity, hash and event"):
        engine.run_cycle(request)


def test_longitudinal_trace_rejects_structural_character_switch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "character_switch"
    first_engine, first = _run(root)
    trace_before = first_engine.ego_trace_store.load_trace(first.request.ego_id)
    alternate_profile = next(
        profile_id
        for profile_id in CHARACTER_PROFILE_ORDER
        if profile_id != first.request.character.profile_id
    )
    request = first.request.model_copy(
        update={
            "run_id": "b11-character-switch-rejected",
            "started_at": first.request.started_at + timedelta(seconds=1),
            "historical_bundles": (first.native_bundle,),
            "character": parse_character_profile(alternate_profile),
        }
    )
    engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(request.started_at),
    )

    with pytest.raises(ValueError, match="cannot switch structural"):
        engine.run_cycle(request)

    assert engine.ego_trace_store.load_trace(request.ego_id) == trace_before
    assert not (
        root
        / "runs"
        / request.run_id
        / "diagnostics"
        / "run_reservation.json"
    ).exists()


def test_failure_before_trace_cas_never_advances_authoritative_trace(
    tmp_path: Path,
) -> None:
    root = tmp_path / "pre_cas_failure"
    request = _request()
    trace_store = FileEgoTraceStore(root / "ego_traces")
    engine = ReiNativeEngine(
        artifact_store=_FailingArtifactStore(
            FileArtifactStore(root / "runs"),
            "ego/measure.json",
        ),
        ego_trace_store=trace_store,
        clock=DeterministicExecutionClock(request.started_at),
    )
    trace_before = trace_store.load_trace(request.ego_id)

    with pytest.raises(RuntimeError, match="injected failure"):
        engine.run_cycle(request)

    assert trace_store.load_trace(request.ego_id) == trace_before
    run_root = root / "runs" / request.run_id
    assert not (run_root / "diagnostics" / "prepared_manifest.json").exists()
    assert not (run_root / "run_manifest.json").exists()


def test_cold_retry_recovers_crash_after_trace_cas_before_final_manifest(
    tmp_path: Path,
) -> None:
    root = tmp_path / "post_cas_recovery"
    request = _request()
    trace_store = FileEgoTraceStore(root / "ego_traces")
    engine = ReiNativeEngine(
        artifact_store=_FailingArtifactStore(
            FileArtifactStore(root / "runs"),
            "run_manifest.json",
        ),
        ego_trace_store=trace_store,
        clock=DeterministicExecutionClock(request.started_at),
    )

    with pytest.raises(RuntimeError, match="run_manifest"):
        engine.run_cycle(request)

    trace_after_failure = trace_store.load_trace(request.ego_id)
    assert len(trace_after_failure.measures) == 1
    run_root = root / "runs" / request.run_id
    assert (run_root / "diagnostics" / "prepared_manifest.json").is_file()
    assert not (run_root / "run_manifest.json").exists()

    fresh_engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(request.started_at),
    )
    with pytest.raises(ArtifactExistsError, match="recovered"):
        fresh_engine.run_cycle(request)

    assert fresh_engine.ego_trace_store.load_trace(request.ego_id) == trace_after_failure
    recovered = FileArtifactStore(root / "runs").verify_run(request.run_id)
    assert recovered.status == "completed"
    assert (run_root / "run_manifest.json").read_bytes() == (
        run_root / "diagnostics" / "prepared_manifest.json"
    ).read_bytes()


def test_run_id_reservation_rejects_reuse_before_trace_mutation(tmp_path: Path) -> None:
    engine, result = _run(tmp_path / "reservation")
    trace_before = engine.ego_trace_store.load_trace(result.request.ego_id)

    with pytest.raises(ArtifactExistsError, match="already completed|recovered"):
        engine.run_cycle(result.request)

    assert engine.ego_trace_store.load_trace(result.request.ego_id) == trace_before


def test_cycle_cli_parses_request_and_prints_only_canonical_summary(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--input",
            str(FIXTURE),
            "--runs-root",
            str(tmp_path / "cli" / "runs"),
            "--ego-traces-root",
            str(tmp_path / "cli" / "ego_traces"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )

    assert completed.stderr == b""
    summary = json.loads(completed.stdout)
    assert completed.stdout == canonical_json_bytes(summary)
    assert summary["schema_version"] == "rei-native-cycle-summary-v1"
    assert summary["run_id"] == _request().run_id
    assert summary["ego_id"] == _request().ego_id
    assert summary["profile_id"] == _request().character.profile_id
    assert summary["all_invariants_passed"] is True
    assert summary["stored_artifact_count"] == len(
        _files_below(tmp_path / "cli" / "runs" / _request().run_id)
    )


def _literal_dynamic_import(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        name = node.func.attr
    else:
        return None
    if name not in {"__import__", "import_module"}:
        return None
    argument = node.args[0] if node.args else next(
        (item.value for item in node.keywords if item.arg == "name"),
        None,
    )
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    return None


def test_native_runtime_ast_boundary_rejects_active_legacy_imports() -> None:
    sources = sorted((ROOT / "app" / "backend" / "rei_next").rglob("*.py"))
    sources.extend((RUNNER, MATRIX_RUNNER))
    findings: list[str] = []

    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                modules = tuple(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules = (node.module,)
            elif isinstance(node, ast.Call):
                dynamic = _literal_dynamic_import(node)
                if dynamic is not None:
                    modules = (dynamic,)
            for module in modules:
                if module.partition(".")[0] == "rei":
                    findings.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}: {module}"
                    )

    assert not findings, "Native runtime imports the legacy rei package:\n" + "\n".join(
        findings
    )
