from __future__ import annotations

import ast
import asyncio
from dataclasses import dataclass
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
from app.backend.rei.models.emocio import ImageArtifact
from app.backend.rei.persistence import ArtifactIntegrityError, FileArtifactStore
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
NATIVE_GAP_KEYS = {
    "native_option_id",
    "native_action_tendency",
    "native_motive_summary",
    "fidelity_components",
}


def _request(*, run_id: str, ego_id: str) -> ReiNativeCycleRequest:
    base = ReiNativeCycleRequest.model_validate_json(FIXTURE.read_bytes())
    return base.model_copy(update={"run_id": run_id, "ego_id": ego_id})


def _http_request(
    body: bytes,
    *,
    host: str = "127.0.0.1",
    content_length: int | None = None,
) -> Request:
    delivered = False

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    headers = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/cycles",
            "headers": headers,
            "client": (host, 43100),
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

    assert payload["schema_version"] == "rei-native-workbench-bootstrap-v1"
    assert payload["execution"] == {
        "providers": "deterministic_only",
        "models_enabled": False,
        "image_generation_enabled": False,
        "dataset_actions_enabled": False,
    }
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


def test_workbench_envelope_redacts_evaluator_truth_by_default(
    completed_views: dict[str, Any],
) -> None:
    normal = completed_views["normal"]
    debug = completed_views["debug"]

    assert normal["schema_version"] == "rei-native-workbench-v1"
    assert set(normal) == {"schema_version", "run", "panels", "diagnostics"}
    assert set(normal["panels"]) == {"native", "communication", "character", "ego"}
    assert normal["run"]["all_invariants_passed"] is True

    communication = normal["panels"]["communication"]
    assert communication["ground_truth_visible"] is False
    assert "evaluator_ground_truth" not in communication
    for gap in communication["translation_gaps"].values():
        assert NATIVE_GAP_KEYS.isdisjoint(gap)
    serialized = json.dumps(communication, sort_keys=True)
    assert "native_motive_summary" not in serialized
    assert "native_action_tendency" not in serialized
    assert "native_option_id" not in serialized

    debug_communication = debug["panels"]["communication"]
    assert debug_communication["ground_truth_visible"] is True
    ground_truth = debug_communication["evaluator_ground_truth"]
    assert ground_truth["label"] == "DEBUG / EVALUATOR GROUND TRUTH"
    assert "Racio did not see" in ground_truth["warning"]
    assert ground_truth["emocio"]["native_option_id"] is not None
    assert ground_truth["instinkt"]["native_action_tendency"] is not None


def test_native_panel_preserves_image_slots_and_complete_body_trajectories(
    completed_views: dict[str, Any],
) -> None:
    result = completed_views["result"]
    native = completed_views["normal"]["panels"]["native"]
    emocio = native["emocio"]
    instinkt = native["instinkt"]

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

    assert len(instinkt["rollouts"]) == len(result.request.scene.options)
    for rollout in instinkt["rollouts"]:
        assert len(rollout["trajectory"]) == result.request.instinkt_config.rollout_steps + 1
        for state in rollout["trajectory"]:
            assert BODY_DIMENSIONS <= set(state)
    decisive = next(
        item
        for item in instinkt["rollouts"]
        if item["rollout_id"] == native["instinkt"]["conclusion"]["decisive_rollout_id"]
    )
    assert instinkt["body_after"] == decisive["trajectory"][-1]


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
    assert ego["composition_snapshot"]["snapshot_id"] == result.composition_snapshot.snapshot_id
    assert ego["self_narrative"]["narrative_id"] == result.narrative.narrative_id
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
    assert (runs_root / request.run_id / "run_manifest.json").is_file()
    assert tuple(traces_root.glob("*.trace.json"))
    assert all(not provider.uses_model for provider in FileArtifactStore(runs_root).verify_run(request.run_id).providers)
    with pytest.raises(HTTPException) as raised:
        server.execute_native_cycle(request, debug=False)
    assert raised.value.status_code == 409


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

    monkeypatch.setenv(server.ALLOW_REMOTE_DEBUG_ENV, "true")
    remote_debug_result = asyncio.run(
        server.run_native_cycle(
            _http_request(b"{}", host="203.0.113.9"),
            debug=True,
        )
    )
    assert remote_debug_result == {"request": parsed, "debug": True}


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
    index_record: StoredArtifact
    pixel_record: StoredArtifact
    index_bytes: bytes
    pixel_bytes: bytes

    def verify_run(self, run_id: str):
        assert run_id == self.run_id
        return SimpleNamespace(
            artifact_inventory=(self.index_record, self.pixel_record)
        )

    def read_verified(self, artifact: StoredArtifact) -> bytes:
        if artifact.relative_path == self.index_record.relative_path:
            return self.index_bytes
        if artifact.relative_path == self.pixel_record.relative_path:
            return self.pixel_bytes
        raise AssertionError(f"unexpected artifact: {artifact.relative_path}")


def _verified_image_store() -> tuple[_FakeVerifiedImageStore, ImageArtifact]:
    run_id = "verified-image-run"
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
    return (
        _FakeVerifiedImageStore(
            run_id=run_id,
            index_record=_stored(run_id, server.IMAGE_INDEX_PATH, index_bytes),
            pixel_record=_stored(run_id, artifact.path, png),
            index_bytes=index_bytes,
            pixel_bytes=png,
        ),
        artifact,
    )


def test_image_route_requires_manifest_inventory_and_rechecks_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_store, artifact = _verified_image_store()
    monkeypatch.setattr(server, "_artifact_store", lambda: fake_store)

    response = server.verified_run_image(fake_store.run_id, artifact.image_id)

    assert response.body == fake_store.pixel_bytes
    assert response.media_type == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    fake_store.pixel_bytes += b"tampered"
    with pytest.raises(HTTPException) as raised:
        server.verified_run_image(fake_store.run_id, artifact.image_id)
    assert raised.value.status_code == 409


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
        request=SimpleNamespace(run_id="available-slot-run"),
        emocio_execution=SimpleNamespace(
            visual_state=result.emocio_execution.visual_state,
            rendered_images=(artifact,),
        ),
        manifest=SimpleNamespace(artifact_inventory=(inventory,)),
    )

    slots = view_model._image_slots(proxy)
    available = next(item for item in slots if item["status"] == "available")

    assert available["artifact"]["image_id"] == artifact.image_id
    assert available["url"] == (
        f"/api/runs/available-slot-run/images/{artifact.image_id}"
    )
    assert available["url"].startswith("/")
    assert "://" not in available["url"]


def test_gui_routes_and_imports_exclude_legacy_dataset_actions() -> None:
    route_paths = {
        route.path for route in server.app.routes if hasattr(route, "path")
    }
    assert "/api/bootstrap" in route_paths
    assert "/api/cycles" in route_paths
    assert "/api/runs/{run_id}/images/{image_id}" in route_paths
    assert not any(
        forbidden in path.casefold()
        for path in route_paths
        for forbidden in ("dataset", "prompt", "model", "ollama")
    )

    backend_files = (
        ROOT / "app" / "gui" / "__init__.py",
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
