from __future__ import annotations

import ast
import asyncio
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from typing import Any
import zlib

from fastapi import HTTPException
import pytest
from starlette.requests import Request

from app.backend.rei.engine import ReiNativeCycleRequest, ReiNativeEngine
from app.backend.rei.ids import canonical_json_bytes
from app.backend.rei.models.character import (
    CHARACTER_PROFILE_CONTRACTS,
    CHARACTER_PROFILE_ORDER,
)
from app.backend.rei.models.common import PUBLIC_SAFETY_CAVEAT_EN
from app.backend.rei.models.emocio import ImageArtifact
from app.backend.rei.persistence import (
    ArtifactIntegrityError,
    ArtifactStoreError,
    FileArtifactStore,
)
from app.backend.rei.providers.native import DeterministicExecutionClock
from app.backend.rei.providers.protocols import StoredArtifact
from app.gui import server
from app.gui import view_model


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
BODY_DIMENSIONS = {
    "energy",
    "fatigue",
    "pain",
    "arousal",
    "tension",
    "physical_integrity",
    "uncertainty",
    "trust",
    "attachment_security",
    "resource_security",
    "boundary_integrity",
    "escape_availability",
    "predictability",
}


def _request(*, run_id: str, ego_id: str) -> ReiNativeCycleRequest:
    base = ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())
    return base.model_copy(update={"run_id": run_id, "ego_id": ego_id})


def _http_request(
    body: bytes,
    *,
    method: str = "POST",
    path: str = "/api/cycles",
    host: str = "127.0.0.1",
    host_header: str | None = None,
    content_type: str | None = "application/json",
    content_length: int | None = None,
    origin: str | None = None,
    sec_fetch_site: str | None = None,
) -> Request:
    delivered = False

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    authority = host_header
    if authority is None:
        authority = f"[{host}]:8765" if ":" in host else f"{host}:8765"
    headers = [(b"host", authority.encode("ascii"))]
    if content_type is not None:
        headers.append((b"content-type", content_type.encode("ascii")))
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode("ascii")))
    if origin is not None:
        headers.append((b"origin", origin.encode("ascii")))
    if sec_fetch_site is not None:
        headers.append((b"sec-fetch-site", sec_fetch_site.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "http",
            "path": path,
            "headers": headers,
            "client": (host, 43100),
            "server": ("127.0.0.1", 8765),
        },
        receive,
    )


@pytest.fixture(scope="module")
def completed_views(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("gui-view")
    request = _request(run_id="gui-view-run", ego_id="gui-view-ego")
    engine = ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego-traces",
        clock=DeterministicExecutionClock(request.started_at),
    )
    result = engine.run_cycle(request)
    return {
        "root": root,
        "request": request,
        "result": result,
        "normal": view_model.build_workbench_view(result),
        "debug": view_model.build_workbench_view(result, debug=True),
    }


def test_bootstrap_is_fixture_only_and_exposes_all_profile_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server,
        "_engine",
        lambda _request: pytest.fail("bootstrap must not construct an engine"),
    )

    payload = server.bootstrap()

    assert (
        payload["schema_version"]
        == "rei-semantic-native-workbench-bootstrap-v2"
    )
    assert payload["execution"] == {
        "providers": "deterministic_only",
        "models_enabled": False,
        "image_generation_enabled": False,
        "dataset_actions_enabled": False,
        "semantic_lab_read_only": True,
        "network_scope": "loopback_default",
        "remote_access_policy": "trusted_single_user_unauthenticated_opt_in",
        "longitudinal_bundle_limit": 30,
        "history_lookup_window": 64,
        "run_storage_partition": "sha256_ego_id",
    }
    assert payload["shadow_evidence_replay"] == {
        "available": True,
        "live_model_execution": False,
        "authority": "none",
        "evidence_ids": ["s1-partial", "s1r-reconciled"],
    }
    assert payload["safety_caveat"] == PUBLIC_SAFETY_CAVEAT_EN
    assert len(payload["profile_contracts"]) == 13
    assert [item["profile_id"] for item in payload["profile_contracts"]] == list(
        CHARACTER_PROFILE_ORDER
    )
    for item in payload["profile_contracts"]:
        tiers, rule = CHARACTER_PROFILE_CONTRACTS[item["profile_id"]]
        assert item["authority_tiers"] == [list(tier) for tier in tiers]
        assert item["rule"] == rule
    parsed = server._parse_cycle_request(
        json.dumps(payload["default_request"]).encode("utf-8")
    )
    assert parsed == ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())


def test_semantic_lab_route_is_read_only_and_masks_integrity_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projected = {
        "schema_version": "rei-semantic-lab-workbench-v1",
        "execution_policy": {"read_only": True, "model_calls": 0},
    }

    def build(root: Path) -> dict[str, Any]:
        assert root == server.ROOT
        return projected

    monkeypatch.setattr(server, "build_semantic_lab_view", build)
    assert server.semantic_lab() is projected

    def reject(_root: Path) -> dict[str, Any]:
        raise server.SemanticLabIntegrityError("secret local path and hash")

    monkeypatch.setattr(server, "build_semantic_lab_view", reject)
    with pytest.raises(HTTPException) as raised:
        server.semantic_lab()
    assert raised.value.status_code == 409
    assert raised.value.detail == (
        "Semantic Lab evidence failed integrity verification."
    )
    assert "secret" not in raised.value.detail


def test_semantic_lab_route_rejects_concurrent_cold_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BusyGate:
        def acquire(self, *, blocking: bool) -> bool:
            assert blocking is False
            return False

        def release(self) -> None:
            pytest.fail("a gate that was not acquired cannot be released")

    monkeypatch.setattr(server, "_SEMANTIC_LAB_BUILD_GATE", BusyGate())
    monkeypatch.setattr(
        server,
        "build_semantic_lab_view",
        lambda _root: pytest.fail("busy requests cannot start another replay"),
    )

    with pytest.raises(HTTPException) as raised:
        server.semantic_lab()
    assert raised.value.status_code == 503
    assert raised.value.headers == {"Retry-After": "1"}


def test_workbench_envelope_redacts_evaluator_truth_by_default(
    completed_views: dict[str, Any],
) -> None:
    normal = completed_views["normal"]
    debug = completed_views["debug"]

    assert normal["schema_version"] == "rei-semantic-native-workbench-v2"
    assert set(normal) == {"schema_version", "run", "panels", "diagnostics"}
    assert set(normal["panels"]) == {
        "racio",
        "emocio",
        "instinkt",
        "character",
        "ego",
    }
    assert normal["run"]["all_invariants_passed"] is True

    racio = normal["panels"]["racio"]
    assert racio["ground_truth_visible"] is False
    assert "evaluator_ground_truth" not in racio
    assert racio["warning"].startswith(
        "Racio did not receive evaluator ground truth."
    )
    assert racio["visible_inputs"]["emocio"] == (
        completed_views["result"]
        .emocio_communication.request.model_dump(mode="json")
    )
    assert racio["visible_inputs"]["instinkt"] == (
        completed_views["result"]
        .instinkt_communication.request.model_dump(mode="json")
    )
    assert "translation_gaps" not in racio
    assert "evaluator_labels" not in racio
    serialized = json.dumps(racio, sort_keys=True)
    assert "native_motive_summary" not in serialized
    assert "native_action_tendency" not in serialized
    assert "native_option_id" not in serialized
    normal_ego = json.dumps(normal["panels"]["ego"], sort_keys=True)
    for evaluator_key in (
        "native_option_id",
        "native_action_tendency",
        "native_motive_summary",
        "source_conclusion_hash",
        "fidelity_components",
        "motive_fidelity",
    ):
        assert evaluator_key not in normal_ego

    debug_racio = debug["panels"]["racio"]
    assert debug_racio["ground_truth_visible"] is True
    assert debug_racio["translation_gaps"] == {
        "emocio": completed_views[
            "result"
        ].emocio_communication.translation_gap.model_dump(mode="json"),
        "instinkt": completed_views[
            "result"
        ].instinkt_communication.translation_gap.model_dump(mode="json"),
    }
    assert debug_racio["evaluator_labels"] == {
        "emocio": completed_views[
            "result"
        ].emocio_communication.translation_gap.gap_status,
        "instinkt": completed_views[
            "result"
        ].instinkt_communication.translation_gap.gap_status,
    }
    ground_truth = debug_racio["evaluator_ground_truth"]
    assert ground_truth["label"] == "DEBUG / EVALUATOR GROUND TRUTH"
    assert ground_truth["warning"].startswith(
        "Racio did not receive evaluator ground truth."
    )
    assert "Racio did not see" in ground_truth["warning"]
    assert ground_truth["emocio"]["native_option_id"] is not None
    assert ground_truth["instinkt"]["native_action_tendency"] is not None
    debug_ego = json.dumps(debug["panels"]["ego"], sort_keys=True)
    assert "native_motive_summary" in debug_ego
    assert "fidelity_components" in debug_ego
    for gap in (
        completed_views["result"].emocio_communication.translation_gap,
        completed_views["result"].instinkt_communication.translation_gap,
    ):
        evaluator_text = (
            f"translation_gap:{gap.source_mind}:{gap.distortion_type}:"
            f"{gap.native_option_id}->{gap.interpreted_option_id}"
        )
        assert evaluator_text not in normal_ego


def test_native_panel_preserves_image_slots_and_complete_body_trajectories(
    completed_views: dict[str, Any],
) -> None:
    result = completed_views["result"]
    panels = completed_views["normal"]["panels"]
    emocio = panels["emocio"]
    instinkt = panels["instinkt"]

    slots = emocio["image_slots"]
    assert len(slots) == 3 + len(result.request.scene.options)
    assert {slot["scene_kind"] for slot in slots} == {
        "current",
        "desired",
        "broken",
        "option_rollout",
    }
    assert all(slot["status"] == "not_rendered" for slot in slots)
    assert all("url" not in slot and "artifact" not in slot for slot in slots)
    assert all("structured scene remains authoritative" in slot["message"] for slot in slots)
    assert len(emocio["scene_specs"]) == len(slots)
    assert emocio["visual_status"]["embedding_status"] == "not_executed_in_this_cycle"
    assert emocio["visual_status"]["similarity_status"] == "not_executed_in_this_cycle"
    assert emocio["visual_observations"] == []
    assert emocio["visual_valuation"] is None
    assert emocio["native_option_id"] == result.native_bundle.emocio.option_id

    assert len(instinkt["rollouts"]) == len(result.request.scene.options)
    assert instinkt["cue_evidence"] == [
        item.model_dump(mode="json")
        for item in result.instinkt_packet.cue_evidence_bindings
    ]
    assert instinkt["predicted_body_effects"] == []
    assert len(instinkt["manual_option_effects"]) == len(
        result.request.scene.options
    )
    assert instinkt["effect_status"] == {
        "source": "manual_fixture",
        "prediction_status": "not_executed_manual_fixture",
    }
    assert len(instinkt["association_matches"]) == len(result.request.scene.options)
    assert instinkt["abstention"]["abstained"] is False
    for rollout in instinkt["rollouts"]:
        assert len(rollout["trajectory"]) == result.request.instinkt_config.rollout_steps + 1
        for state in rollout["trajectory"]:
            assert BODY_DIMENSIONS <= set(state)
    decisive = next(
        item
        for item in instinkt["rollouts"]
        if item["rollout_id"] == instinkt["conclusion"]["decisive_rollout_id"]
    )
    assert instinkt["body_after"] == decisive["trajectory"][-1]
    assert instinkt["dominant_alarm"] == decisive["dominant_alarm"]


def test_character_and_ego_panels_keep_distinct_records_and_lineage(
    completed_views: dict[str, Any],
) -> None:
    result = completed_views["result"]
    panels = completed_views["normal"]["panels"]
    character = panels["character"]
    ego = panels["ego"]

    assert character["structural_profile"]["profile_id"] == result.request.character.profile_id
    assert character["authority_tiers"] == [
        list(tier) for tier in result.request.character.authority_tiers
    ]
    assert character["processor_availability"]["explicit"] is False
    assert character["thirteenth_majority"]["applicable"] is False
    ids = {
        character["governance_mandate"]["mandate_id"],
        character["conscious_decision"]["decision_id"],
        character["behavior_resultant"]["resultant_id"],
    }
    assert len(ids) == 3

    assert ego["measure"]["measure_id"] == result.ego_measure.measure_id
    assert [item["event_id"] for item in ego["timeline"]] == [
        item.event_id for item in result.ego_trace.event_order
    ]
    measure_events = [
        item["event"]
        for item in ego["timeline"]
        if item["event_kind"] == "measure"
    ]
    assert measure_events
    for measure in measure_events:
        assert measure["conscious_decision"]["decision_id"]
        assert measure["behavior_resultant"]["resultant_id"]
        assert "outcome" in measure
        assert len(measure["translation_gaps"]) == 2
        assert "unresolved_tensions" in measure
        assert "spoznanje_status" in measure
    assert ego["composition_snapshot"]["snapshot_id"] == result.composition_snapshot.snapshot_id
    assert {
        "identity_motifs",
        "recurring_translation_errors",
        "unresolved_tensions",
        "spoznanja",
    } <= set(ego["composition_snapshot"])
    assert ego["self_narrative"]["narrative_id"] == result.narrative.narrative_id
    assert {
        "explanation",
        "claimed_motive",
        "acknowledged_minds",
        "omitted_minds",
        "uncertainty",
    } <= set(ego["self_narrative"])
    for mind, projection in zip(
        ("racio", "emocio", "instinkt"),
        result.projections,
        strict=True,
    ):
        assert ego["projections"][mind]["projection_id"] == projection.projection_id
        assert ego["projections"][mind]["projection_hash"] == projection.projection_hash


def test_cycle_route_uses_env_roots_and_duplicate_run_is_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs_root = tmp_path / "configured-runs"
    traces_root = tmp_path / "configured-traces"
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(runs_root))
    monkeypatch.setenv(server.EGO_TRACES_ROOT_ENV, str(traces_root))
    request = _request(run_id="gui-route-run", ego_id="gui-route-ego")

    first = server.execute_native_cycle(request, debug=False)

    assert first["run"]["run_id"] == request.run_id
    partition_root = server._ego_runs_root(request.ego_id)
    assert partition_root.parent == runs_root
    assert (partition_root / request.run_id / "run_manifest.json").is_file()
    assert tuple(traces_root.glob("*.trace.json"))
    assert all(
        not provider.uses_model
        for provider in FileArtifactStore(partition_root)
        .verify_run(request.run_id)
        .providers
    )
    with pytest.raises(HTTPException) as raised:
        server.execute_native_cycle(request, debug=False)
    assert raised.value.status_code == 409


def test_cycle_route_resolves_verified_longitudinal_history_server_side(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs_root = tmp_path / "longitudinal-runs"
    traces_root = tmp_path / "longitudinal-traces"
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(runs_root))
    monkeypatch.setenv(server.EGO_TRACES_ROOT_ENV, str(traces_root))
    first_request = _request(run_id="gui-history-run-1", ego_id="gui-history-ego")
    second_request = _request(
        run_id="gui-history-run-2",
        ego_id=first_request.ego_id,
    ).model_copy(update={"started_at": first_request.started_at + timedelta(seconds=1)})

    first = server.execute_native_cycle(first_request, debug=False)
    second = server.execute_native_cycle(second_request, debug=False)

    assert len(first["panels"]["ego"]["timeline"]) == 1
    assert len(second["panels"]["ego"]["timeline"]) == 2
    assert second["run"]["run_id"] == second_request.run_id
    assert "evaluator_ground_truth" not in second["panels"]["racio"]
    serialized_second_ego = json.dumps(second["panels"]["ego"], sort_keys=True)
    for evaluator_key in (
        "native_option_id",
        "native_action_tendency",
        "native_motive_summary",
        "source_conclusion_hash",
        "fidelity_components",
        "motive_fidelity",
    ):
        assert evaluator_key not in serialized_second_ego
    safe_errors = second["panels"]["ego"]["composition_snapshot"][
        "recurring_translation_errors"
    ]
    assert safe_errors
    assert all(len(item.split(":")) == 3 for item in safe_errors)
    for item in second["panels"]["ego"]["timeline"]:
        if item["event_kind"] != "measure":
            continue
        for gap in item["event"]["translation_gaps"]:
            assert "native_option_id" not in gap
            assert "fidelity_components" not in gap

    third_request = _request(
        run_id="gui-history-run-3",
        ego_id=first_request.ego_id,
    ).model_copy(update={"started_at": first_request.started_at + timedelta(seconds=2)})
    third = server.execute_native_cycle(third_request, debug=True)
    assert len(third["panels"]["ego"]["timeline"]) == 3
    assert "evaluator_ground_truth" in third["panels"]["racio"]
    debug_errors = third["panels"]["ego"]["composition_snapshot"][
        "recurring_translation_errors"
    ]
    assert debug_errors
    assert all(len(item.split(":")) == 4 for item in debug_errors)
    assert any("->" in item for item in debug_errors)
    for item in third["panels"]["ego"]["timeline"]:
        if item["event_kind"] != "measure":
            continue
        for gap in item["event"]["translation_gaps"]:
            assert "native_option_id" in gap
            assert "fidelity_components" in gap


def test_same_run_id_is_isolated_between_ego_partitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(server.EGO_TRACES_ROOT_ENV, str(tmp_path / "traces"))
    first = _request(run_id="shared-run-id", ego_id="partition-ego-a")
    second = _request(run_id="shared-run-id", ego_id="partition-ego-b")

    first_view = server.execute_native_cycle(first)
    second_view = server.execute_native_cycle(second)

    first_root = server._ego_runs_root(first.ego_id)
    second_root = server._ego_runs_root(second.ego_id)
    assert first_root != second_root
    assert (first_root / first.run_id / "run_manifest.json").is_file()
    assert (second_root / second.run_id / "run_manifest.json").is_file()
    assert len(first_view["panels"]["ego"]["timeline"]) == 1
    assert len(second_view["panels"]["ego"]["timeline"]) == 1


def test_cycle_route_rejects_client_supplied_private_history(
    completed_views: dict[str, Any],
) -> None:
    request = _request(run_id="gui-client-history", ego_id="gui-client-history-ego")
    request = request.model_copy(
        update={"historical_bundles": (completed_views["result"].native_bundle,)}
    )

    with pytest.raises(HTTPException) as raised:
        server.execute_native_cycle(request, debug=False)
    assert raised.value.status_code == 422
    assert "server-resolved" in raised.value.detail


def test_cycle_route_recovers_trace_committed_prepared_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs_root = tmp_path / "recovery-runs"
    traces_root = tmp_path / "recovery-traces"
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(runs_root))
    monkeypatch.setenv(server.EGO_TRACES_ROOT_ENV, str(traces_root))
    first_request = _request(run_id="gui-recovery-run-1", ego_id="gui-recovery-ego")
    second_request = _request(
        run_id="gui-recovery-run-2",
        ego_id=first_request.ego_id,
    ).model_copy(update={"started_at": first_request.started_at + timedelta(seconds=1)})
    original_write_json = FileArtifactStore.write_json
    fail_final_once = True

    def interrupt_final_manifest(
        store: FileArtifactStore,
        run_id: str,
        relative_path: str,
        value: object,
    ):
        nonlocal fail_final_once
        if relative_path == "run_manifest.json" and fail_final_once:
            fail_final_once = False
            raise ArtifactStoreError("simulated post-trace crash")
        return original_write_json(store, run_id, relative_path, value)

    monkeypatch.setattr(FileArtifactStore, "write_json", interrupt_final_manifest)
    with pytest.raises(HTTPException) as interrupted:
        server.execute_native_cycle(first_request, debug=False)
    assert interrupted.value.status_code == 409
    first_run = server._ego_runs_root(first_request.ego_id) / first_request.run_id
    assert (first_run / "diagnostics" / "prepared_manifest.json").is_file()
    assert not (first_run / "run_manifest.json").exists()

    monkeypatch.setattr(FileArtifactStore, "write_json", original_write_json)
    with pytest.raises(HTTPException) as recovered_duplicate:
        server.execute_native_cycle(first_request, debug=False)
    assert recovered_duplicate.value.status_code == 409
    assert (first_run / "run_manifest.json").is_file()

    continued = server.execute_native_cycle(second_request, debug=False)
    assert len(continued["panels"]["ego"]["timeline"]) == 2


def test_gui_longitudinal_history_has_an_explicit_30_bundle_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    measures = tuple(
        SimpleNamespace(
            native_bundle_id=f"bundle-{index}",
            native_bundle_hash=f"{index:064x}",
            event_id=f"event-{index}",
        )
        for index in range(server.MAX_GUI_LONGITUDINAL_BUNDLES)
    )
    trace = SimpleNamespace(measures=measures)
    trace_store = SimpleNamespace(load_trace=lambda _ego_id: trace)
    monkeypatch.setattr(server, "FileEgoTraceStore", lambda _root: trace_store)
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(tmp_path / "runs"))
    request = _request(run_id="gui-history-bound", ego_id="gui-history-bound-ego")

    with pytest.raises(ValueError, match="30 measures"):
        server._verified_historical_bundles(request)


def test_gui_run_partitions_are_safe_isolated_and_absolutely_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs_root = tmp_path / "partitioned-runs"
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(runs_root))
    unusual_ego_id = " ../CON/oseba Å¾\u0000 "
    partition = server._ego_runs_root(unusual_ego_id)

    assert partition.parent == runs_root
    assert partition.name.startswith("ego-")
    assert len(partition.name) == 68
    assert set(partition.name.removeprefix("ego-")) <= set("0123456789abcdef")
    assert unusual_ego_id not in str(partition)

    request = _request(run_id="new-run", ego_id=unusual_ego_id)
    partition.mkdir(parents=True)
    for index in range(server.MAX_HISTORY_RUN_DIRECTORIES):
        (partition / f"junk-{index:03d}").write_bytes(b"")

    with pytest.raises(ArtifactIntegrityError, match="no capacity"):
        server._verified_historical_bundles(request)

    other = _request(run_id="other-run", ego_id="other-ego")
    assert server._verified_historical_bundles(other) == ()
    assert server._ego_runs_root(other.ego_id) != partition


def test_gui_run_partition_stops_at_cap_plus_one_for_empty_trace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(tmp_path / "runs"))
    request = _request(run_id="bounded-run", ego_id="bounded-empty-ego")
    partition = server._ego_runs_root(request.ego_id)
    partition.mkdir(parents=True)
    for index in range(server.MAX_HISTORY_RUN_DIRECTORIES + 1):
        (partition / f"entry-{index:03d}").mkdir()

    with pytest.raises(ArtifactIntegrityError, match="bounded directory limit"):
        server._verified_historical_bundles(request)


def test_gui_bundle_larger_than_legacy_64k_recovers_on_second_cycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(tmp_path / "runs"))
    monkeypatch.setenv(server.EGO_TRACES_ROOT_ENV, str(tmp_path / "traces"))
    first_request = _request(run_id="large-bundle-1", ego_id="large-bundle-ego")
    first_request = first_request.model_copy(
        update={
            "emocio_world": first_request.emocio_world.model_copy(
                update={"desired_scenes": ("x" * 70_000,)}
            )
        }
    )
    second_request = first_request.model_copy(
        update={
            "run_id": "large-bundle-2",
            "started_at": first_request.started_at + timedelta(seconds=1),
        }
    )

    server.execute_native_cycle(first_request)
    bundle_path = (
        server._ego_runs_root(first_request.ego_id)
        / first_request.run_id
        / server.NATIVE_BUNDLE_PATH
    )
    assert 64 * 1024 < bundle_path.stat().st_size <= server.MAX_NATIVE_BUNDLE_BYTES

    second = server.execute_native_cycle(second_request)
    assert len(second["panels"]["ego"]["timeline"]) == 2


def test_gui_rejects_oversize_native_bundle_before_writing_it(
    tmp_path: Path,
) -> None:
    store = server._BoundedGuiArtifactStore(tmp_path / "runs")

    with pytest.raises(ArtifactIntegrityError, match="recovery contract"):
        store.write_json(
            "oversize-run",
            server.NATIVE_BUNDLE_PATH,
            {"payload": "x" * server.MAX_NATIVE_BUNDLE_BYTES},
        )

    assert not store.run_path("oversize-run").exists()


def test_cycle_route_maps_server_history_race_to_retryable_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(run_id="gui-history-race", ego_id="gui-history-race-ego")
    monkeypatch.setattr(server, "_verified_historical_bundles", lambda _request: ())

    class RacedEngine:
        def run_cycle(self, _request: ReiNativeCycleRequest):
            raise ValueError(
                "Historical bundles must exactly cover the loaded EgoTrace "
                "(missing=['bundle-new'], unexpected=[])"
            )

    monkeypatch.setattr(server, "_engine", lambda _request: RacedEngine())

    with pytest.raises(HTTPException) as raised:
        server.execute_native_cycle(request, debug=False)
    assert raised.value.status_code == 409
    assert "retry" in raised.value.detail


def test_cycle_route_rejects_declared_and_streamed_oversize_bodies() -> None:
    declared = _http_request(
        b"{}",
        content_length=server.MAX_CYCLE_REQUEST_BYTES + 1,
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(server._bounded_request_body(declared))
    assert raised.value.status_code == 413
    assert str(server.MAX_CYCLE_REQUEST_BYTES) in raised.value.detail

    streamed = _http_request(b"x" * (server.MAX_CYCLE_REQUEST_BYTES + 1))
    with pytest.raises(HTTPException) as raised:
        asyncio.run(server._bounded_request_body(streamed))
    assert raised.value.status_code == 413
    assert "byte limit" in raised.value.detail


def test_debug_route_is_loopback_only_without_explicit_remote_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(server.ALLOW_REMOTE_DEBUG_ENV, raising=False)
    monkeypatch.delenv(server.ALLOW_REMOTE_ENV, raising=False)
    parsed = object()
    monkeypatch.setattr(server, "_parse_cycle_request", lambda _content: parsed)
    monkeypatch.setattr(
        server,
        "execute_native_cycle",
        lambda request, *, debug: {"request": request, "debug": debug},
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            server.run_native_cycle(
                _http_request(b"{}", host="203.0.113.9"),
                debug=True,
            )
        )
    assert raised.value.status_code == 403
    assert server.ALLOW_REMOTE_DEBUG_ENV in raised.value.detail

    local_result = asyncio.run(
        server.run_native_cycle(
            _http_request(b"{}", host="::1"),
            debug=True,
        )
    )
    assert local_result == {"request": parsed, "debug": True}

    remote_normal_result = asyncio.run(
        server.run_native_cycle(
            _http_request(b"{}", host="203.0.113.9"),
            debug=False,
        )
    )
    assert remote_normal_result == {"request": parsed, "debug": False}

    monkeypatch.setenv(server.ALLOW_REMOTE_ENV, "true")
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            server.run_native_cycle(
                _http_request(
                    b"{}",
                    host="127.0.0.1",
                    host_header="public.example:8765",
                ),
                debug=True,
            )
        )
    assert raised.value.status_code == 403

    monkeypatch.setenv(server.ALLOW_REMOTE_ENV, "true")
    monkeypatch.setenv(server.ALLOW_REMOTE_DEBUG_ENV, "true")
    remote_debug_result = asyncio.run(
        server.run_native_cycle(
            _http_request(b"{}", host="203.0.113.9"),
            debug=True,
        )
    )
    assert remote_debug_result == {"request": parsed, "debug": True}


def test_http_surface_is_loopback_only_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(server.ALLOW_REMOTE_ENV, raising=False)

    async def accepted(_request: Request):
        return server.Response(status_code=204)

    rejected = asyncio.run(
        server.enforce_loopback_default(
            _http_request(b"", host="203.0.113.10"),
            accepted,
        )
    )
    assert rejected.status_code == 403
    assert server.ALLOW_REMOTE_ENV.encode("utf-8") in rejected.body

    allowed = asyncio.run(
        server.enforce_loopback_default(
            _http_request(b"", host="127.0.0.1"),
            accepted,
        )
    )
    assert allowed.status_code == 204
    assert "frame-ancestors 'none'" in allowed.headers["content-security-policy"]
    assert allowed.headers["x-frame-options"] == "DENY"
    assert allowed.headers["x-content-type-options"] == "nosniff"
    assert allowed.headers["referrer-policy"] == "no-referrer"
    assert allowed.headers["cache-control"] == "no-store"


def test_loopback_surface_rejects_dns_rebinding_or_untrusted_proxy_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(server.ALLOW_REMOTE_ENV, raising=False)

    async def accepted(_request: Request):
        return server.Response(status_code=204)

    response = asyncio.run(
        server.enforce_loopback_default(
            _http_request(
                b"",
                host="127.0.0.1",
                host_header="attacker.example:8765",
            ),
            accepted,
        )
    )
    assert response.status_code == 403
    assert server.ALLOW_REMOTE_ENV.encode("utf-8") in response.body


@pytest.mark.parametrize("fetch_site", ["cross-site", "same-site", "invalid"])
def test_api_surface_rejects_non_same_origin_browser_gets(fetch_site: str) -> None:
    async def accepted(_request: Request):
        return server.Response(status_code=204)

    response = asyncio.run(
        server.enforce_loopback_default(
            _http_request(
                b"",
                method="GET",
                path="/api/semantic-lab",
                sec_fetch_site=fetch_site,
            ),
            accepted,
        )
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("fetch_site", [None, "none", "same-origin"])
def test_api_surface_allows_non_browser_and_same_origin_fetches(
    fetch_site: str | None,
) -> None:
    async def accepted(_request: Request):
        return server.Response(status_code=204)

    response = asyncio.run(
        server.enforce_loopback_default(
            _http_request(
                b"",
                method="GET",
                path="/api/semantic-lab",
                sec_fetch_site=fetch_site,
            ),
            accepted,
        )
    )
    assert response.status_code == 204


def test_cycle_route_requires_json_and_same_origin_browser_requests() -> None:
    with pytest.raises(HTTPException) as raised:
        server._require_same_origin_json(
            _http_request(b"{}", content_type="text/plain")
        )
    assert raised.value.status_code == 415

    with pytest.raises(HTTPException) as raised:
        server._require_same_origin_json(
            _http_request(
                b"{}",
                origin="http://attacker.example:8765",
            )
        )
    assert raised.value.status_code == 403

    with pytest.raises(HTTPException) as raised:
        server._require_same_origin_json(
            _http_request(b"{}", sec_fetch_site="cross-site")
        )
    assert raised.value.status_code == 403

    server._require_same_origin_json(
        _http_request(
            b"{}",
            origin="http://127.0.0.1:8765",
            sec_fetch_site="same-origin",
        )
    )


def test_cycle_route_rejects_concurrent_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BusyGate:
        def acquire(self, *, blocking: bool) -> bool:
            assert blocking is False
            return False

        def release(self) -> None:
            pytest.fail("a gate that was not acquired cannot be released")

    parsed = object()
    monkeypatch.setattr(server, "_CYCLE_EXECUTION_GATE", BusyGate())
    monkeypatch.setattr(server, "_parse_cycle_request", lambda _content: parsed)
    monkeypatch.setattr(
        server,
        "execute_native_cycle",
        lambda *_args, **_kwargs: pytest.fail("busy cycles cannot execute"),
    )

    with pytest.raises(HTTPException) as raised:
        asyncio.run(server.run_native_cycle(_http_request(b"{}")))
    assert raised.value.status_code == 503
    assert raised.value.headers == {"Retry-After": "1"}


def _stored(run_id: str, path: str, content: bytes) -> StoredArtifact:
    return StoredArtifact(
        storage_id=f"stored-{hashlib.sha256(path.encode()).hexdigest()[:24]}",
        run_id=run_id,
        relative_path=path,
        content_sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )


def _png(width: int, height: int) -> bytes:
    """Return a tiny deterministic PNG protocol fixture using only stdlib."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", checksum)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    scanline = bytes((0,)) + bytes((25, 80, 140, 255)) * width
    pixels = scanline * height
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"IDAT", zlib.compress(pixels, level=9)),
            chunk(b"IEND", b""),
        )
    )


@dataclass
class _FakeVerifiedImageStore:
    run_id: str
    ego_id: str
    reservation_record: StoredArtifact
    index_record: StoredArtifact
    pixel_record: StoredArtifact
    reservation_bytes: bytes
    index_bytes: bytes
    pixel_bytes: bytes

    def verify_run(self, run_id: str):
        assert run_id == self.run_id
        return SimpleNamespace(
            artifact_inventory=(
                self.reservation_record,
                self.index_record,
                self.pixel_record,
            )
        )

    def read_verified(self, artifact: StoredArtifact) -> bytes:
        if artifact.relative_path == self.reservation_record.relative_path:
            return self.reservation_bytes
        if artifact.relative_path == self.index_record.relative_path:
            return self.index_bytes
        if artifact.relative_path == self.pixel_record.relative_path:
            return self.pixel_bytes
        raise AssertionError(f"unexpected artifact: {artifact.relative_path}")


def _verified_image_store() -> tuple[_FakeVerifiedImageStore, ImageArtifact]:
    run_id = "verified-image-run"
    ego_id = "verified-image-ego"
    png = _png(1, 1)
    digest = hashlib.sha256(png).hexdigest()
    artifact = ImageArtifact(
        image_id="verified-image",
        request_id="verified-image-request",
        render_call_id="verified-image-call",
        source_spec_id="verified-scene",
        provider_id="verified-provider",
        model=None,
        model_revision=None,
        seed=7,
        input_spec_hash="1" * 64,
        content_sha256=digest,
        media_type="image/png",
        grounded=False,
        prompt="fixture prompt",
        negative_prompt="",
        path="emocio/images/verified-image.png",
        width=1,
        height=1,
        generated_only_elements=("fixture-only",),
        grounded_mask_path=None,
    )
    index_bytes = canonical_json_bytes((artifact,))
    reservation_bytes = canonical_json_bytes(
        {
            "schema_version": "rei-native-run-reservation-v1",
            "run_id": run_id,
            "ego_id": ego_id,
            "request_hash": "1" * 64,
            "expected_trace_hash": "2" * 64,
            "created_at": "2026-07-15T00:00:00.000000Z",
        }
    )
    return (
        _FakeVerifiedImageStore(
            run_id=run_id,
            ego_id=ego_id,
            reservation_record=_stored(
                run_id,
                server.RUN_RESERVATION_PATH,
                reservation_bytes,
            ),
            index_record=_stored(run_id, server.IMAGE_INDEX_PATH, index_bytes),
            pixel_record=_stored(run_id, artifact.path, png),
            reservation_bytes=reservation_bytes,
            index_bytes=index_bytes,
            pixel_bytes=png,
        ),
        artifact,
    )


def test_image_route_requires_manifest_inventory_and_rechecks_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_store, artifact = _verified_image_store()
    partition_id = server.ego_partition_id(fake_store.ego_id)
    monkeypatch.setattr(
        server, "_partition_artifact_store", lambda _partition_id: fake_store
    )

    response = server.verified_run_image(
        partition_id,
        fake_store.run_id,
        artifact.image_id,
    )

    assert response.body == fake_store.pixel_bytes
    assert response.media_type == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    fake_store.pixel_bytes += b"tampered"
    with pytest.raises(HTTPException) as raised:
        server.verified_run_image(
            partition_id,
            fake_store.run_id,
            artifact.image_id,
        )
    assert raised.value.status_code == 409

    with pytest.raises(HTTPException) as wrong_partition:
        server.verified_run_image(
            "0" * 64,
            fake_store.run_id,
            artifact.image_id,
        )
    assert wrong_partition.value.status_code == 409


def test_missing_image_partition_get_does_not_create_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(server.RUNS_ROOT_ENV, str(tmp_path / "runs"))
    partition_id = "3" * 64
    partition = server._partition_runs_root(partition_id)
    assert not partition.exists()

    with pytest.raises(HTTPException) as raised:
        server.verified_run_image(partition_id, "missing-run", "missing-image")

    assert raised.value.status_code == 404
    assert not partition.exists()


def test_available_image_slot_uses_same_origin_verified_route(
    completed_views: dict[str, Any],
) -> None:
    result = completed_views["result"]
    fake_store, artifact = _verified_image_store()
    artifact = artifact.model_copy(
        update={
            "source_spec_id": result.emocio_execution.visual_state.current_scene.scene_id,
        }
    )
    inventory = SimpleNamespace(
        relative_path=artifact.path,
        content_sha256=artifact.content_sha256,
    )
    proxy = SimpleNamespace(
        request=SimpleNamespace(
            run_id="available-slot-run",
            ego_id="available-slot-ego",
        ),
        emocio_execution=SimpleNamespace(
            visual_state=result.emocio_execution.visual_state,
            rendered_images=(artifact,),
        ),
        manifest=SimpleNamespace(artifact_inventory=(inventory,)),
    )

    slots = view_model._image_slots(proxy)
    available = next(item for item in slots if item["status"] == "available")

    assert available["artifact"]["image_id"] == artifact.image_id
    partition_id = server.ego_partition_id(proxy.request.ego_id)
    assert available["url"] == (
        f"/api/ego-runs/{partition_id}/available-slot-run/images/{artifact.image_id}"
    )
    assert available["url"].startswith("/")
    assert "://" not in available["url"]
    other_proxy = SimpleNamespace(
        request=SimpleNamespace(
            run_id=proxy.request.run_id,
            ego_id="another-available-slot-ego",
        ),
        emocio_execution=proxy.emocio_execution,
        manifest=proxy.manifest,
    )
    other_available = next(
        item
        for item in view_model._image_slots(other_proxy)
        if item["status"] == "available"
    )
    assert other_available["url"] != available["url"]


def test_gui_routes_and_imports_exclude_legacy_dataset_actions() -> None:
    route_paths = {
        route.path for route in server.app.routes if hasattr(route, "path")
    }
    assert "/api/bootstrap" in route_paths
    assert "/api/semantic-lab" in route_paths
    assert "/api/shadow-evidence" in route_paths
    assert "/api/shadow-evidence/{evidence_id}" in route_paths
    assert "/api/cycles" in route_paths
    assert "/api/ego-runs/{partition_id}/{run_id}/images/{image_id}" in route_paths
    assert not any(
        forbidden in path.casefold()
        for path in route_paths
        for forbidden in ("dataset", "prompt", "model", "ollama")
    )

    backend_files = (
        ROOT / "app" / "gui" / "__init__.py",
        ROOT / "app" / "gui" / "semantic_lab.py",
        ROOT / "app" / "gui" / "shadow_view.py",
        ROOT / "app" / "gui" / "storage.py",
        ROOT / "app" / "gui" / "view_model.py",
        ROOT / "app" / "gui" / "server.py",
    )
    imported: set[str] = set()
    for path in backend_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    assert any(module.startswith("app.backend.rei.") for module in imported)
    assert not any(
        token in module.casefold()
        for module in imported
        for token in ("archive", "dataset", "ollama")
    )

    frontend = (ROOT / "app" / "gui" / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "majority.agreeing_minds" in frontend
    assert "majority.support_count" not in frontend


def test_shadow_debug_reload_discards_stale_responses() -> None:
    frontend = (ROOT / "app" / "gui" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert "shadowRequestGeneration" in frontend
    assert "state.shadowAbortController?.abort()" in frontend
    assert "requestGeneration !== state.shadowRequestGeneration" in frontend
    assert "requestedDebug !== els.debugToggle.checked" in frontend
    assert "if (state.selectedShadowEvidenceId)" in frontend
    assert "if (state.shadowEvidence && state.selectedShadowEvidenceId)" not in frontend


def test_gui_chrome_is_english_and_source_language_evidence_is_explicit() -> None:
    frontend = (ROOT / "app" / "gui" / "static" / "app.js").read_text(
        encoding="utf-8"
    )

    assert '"Semantic Lab · Research Corpus"' in frontend
    assert 'element("span", "", "Test variant")' in frontend
    assert "fieldGroup(selectedVariantInputLabel(variant), variant.input_text)" in frontend
    assert "Selected research input — ${language}" in frontend
    assert '"Source family title — Slovenian"' in frontend
    assert '"Historical exact model input — Slovenian"' in frontend
    assert '"Historical action unknown reason — Slovenian exact accepted output"' in frontend
    assert 'card("What Racio actually saw"' in frontend

    for forbidden_chrome in (
        "Racio ground trutha ni prejel.",
        "Slovenščina · canonical",
        "ni na voljo",
        "Brez citatov",
        "Kanonizirani slovenski signal",
        "Kar je Racio dejansko videl",
        'fieldGroup("Spoznanje"',
        'fieldGroup("Spoznanja"',
    ):
        assert forbidden_chrome not in frontend
