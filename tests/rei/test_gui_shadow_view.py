from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from fastapi import HTTPException
import pytest
from starlette.requests import Request

from app.gui import server
from app.gui import shadow_view


ROOT = Path(__file__).resolve().parents[2]
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])")
POSIX_LOCAL_PATH = re.compile(r"(?<![A-Za-z0-9])/(?:home|Users|tmp|private|var/tmp)/")


def _http_request(
    *,
    path: str,
    host: str = "127.0.0.1",
    host_header: str | None = None,
) -> Request:
    authority = host_header
    if authority is None:
        authority = f"[{host}]:8765" if ":" in host else f"{host}:8765"
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": [(b"host", authority.encode("ascii"))],
            "client": (host, 43100),
            "server": ("127.0.0.1", 8765),
        }
    )


@pytest.fixture(scope="module")
def frozen_views() -> dict[str, dict[str, Any]]:
    return {
        evidence_id: shadow_view.build_shadow_evidence_view(ROOT, evidence_id)
        for evidence_id in shadow_view.SHADOW_EVIDENCE_IDS
    }


def test_registered_roots_and_external_receipt_cold_verify(
    frozen_views: dict[str, dict[str, Any]],
) -> None:
    current = frozen_views["en2-explained"]
    previous_english = frozen_views["en1-runtime"]
    partial = frozen_views["s1-partial"]
    reconciled = frozen_views["s1r-reconciled"]

    assert current["integrity"]["status"] == "cold_verified"
    assert current["integrity"]["receipt_required"] is True
    assert current["integrity"]["receipt_verified"] is True
    assert current["integrity"]["receipt_id"] == (
        "gemma4_en2_shadow_receipt_a2bc1cea5b615e2c9da81d1c83cfe2b3"
    )
    assert current["integrity"]["receipt_sha256"] == (
        "702d149703a21fa3e4160522f0f26025248e97638e17d219df74847b704c8f20"
    )
    assert previous_english["integrity"]["status"] == "cold_verified"
    assert previous_english["integrity"]["receipt_verified"] is True
    assert partial["integrity"]["status"] == "cold_verified"
    assert partial["integrity"]["receipt_required"] is False
    assert partial["integrity"]["receipt_verified"] is False
    assert reconciled["integrity"]["status"] == "cold_verified"
    assert reconciled["integrity"]["receipt_required"] is True
    assert reconciled["integrity"]["receipt_verified"] is True
    assert reconciled["integrity"]["receipt_id"] == (
        "s1r_verify_receipt_f589ffd26f095f610ff27688f727b1d0"
    )
    assert reconciled["integrity"]["receipt_sha256"] == (
        "f8338d63a1cc12a1e133ff289630acde13c3fbebdb1dd97069e827519366f843"
    )
    assert all(
        view["integrity"]["file_count"] <= 128
        and view["integrity"]["total_bytes"] <= 1024 * 1024
        and view["model_calls"] == 0
        for view in frozen_views.values()
    )


def test_en2_current_runtime_projection_is_english_exact_and_honest(
    frozen_views: dict[str, dict[str, Any]],
) -> None:
    current = frozen_views["en2-explained"]
    emocio = current["lanes"]["emocio"]
    instinkt = current["lanes"]["instinkt"]

    assert current["kind"] == "current_runtime"
    assert current["language"] == "en"
    assert current["historical"] is False
    assert current["language_boundary"] == "current_english_model_boundary"
    assert emocio["presentation_shape"] == "failed"
    assert emocio["authoritative"]["status"] == "succeeded"
    assert emocio["shadow"]["failure"] == {
        "stage": "draft_v3_validation",
        "code": "draft_v3_validation",
        "summary": "The text-shadow final JSON failed explained-draft validation.",
    }
    assert emocio["exact_model_input"]["source"] == (
        "hash_verified_reconstruction"
    )
    assert emocio["exact_model_input"]["request_payload_sha256"] == (
        "241f08323136a88ab79e1c33687c5e2967dac17a8da429e40ef6a856f51e93aa"
    )
    assert emocio["shadow"]["action_hypotheses"] == []
    assert emocio["shadow"]["option_inference"] is None
    assert emocio["shadow"]["motive_hypotheses"] == []
    assert instinkt["presentation_shape"] == "bounded_claims"
    assert instinkt["exact_model_input"]["source"] == "persisted_exact"
    assert len(instinkt["shadow"]["action_hypotheses"]) == 1
    assert instinkt["shadow"]["option_inference"]["option_id"] == "option_001"
    assert len(instinkt["shadow"]["motive_hypotheses"]) == 1
    assert all(
        observation["model_text"] is None
        or isinstance(observation["model_text"], str)
        for lane in (emocio, instinkt)
        for observation in lane["visible_input"]["observations"]
    )
    assert all(
        option["model_text"]
        for lane in (emocio, instinkt)
        for option in lane["visible_input"]["public_options"]
    )
    assert instinkt["shadow"]["unknown_reasons"] == {
        "action": None,
        "option": None,
        "motive": None,
    }
    for lane in (emocio, instinkt):
        exact = lane["exact_model_input"]
        assert exact["availability"] == "complete"
        assert "Use the names Emocio, Instinkt, and Racio exactly." in (
            exact["system_instruction"]
        )
        assert json.loads(exact["user_packet_json"])["language"] == "en"
    serialized = json.dumps(current, ensure_ascii=False, sort_keys=True)
    for forbidden in ('"canonical_sl"', '"notes_sl"', '"prompt_sl"'):
        assert forbidden not in serialized


def test_en2_api_detail_uses_the_current_english_boundary() -> None:
    payload = server.shadow_evidence_detail(
        "en2-explained",
        _http_request(path="/api/shadow-evidence/en2-explained"),
    )

    assert payload["evidence_id"] == "en2-explained"
    assert payload["kind"] == "current_runtime"
    assert payload["language"] == "en"
    assert payload["model_calls"] == 0


def test_s1_and_s1r_remain_historical_slovene_evidence(
    frozen_views: dict[str, dict[str, Any]],
) -> None:
    for evidence_id in ("s1-partial", "s1r-reconciled"):
        view = frozen_views[evidence_id]
        assert view["kind"] == "historical"
        assert view["language"] == "sl"
        assert view["historical"] is True
        assert view["language_boundary"] == "historical_slovene_model_boundary"
        assert "historical Slovene" in view["label"]


def test_en1_remains_historical_english_evidence(
    frozen_views: dict[str, dict[str, Any]],
) -> None:
    view = frozen_views["en1-runtime"]
    assert view["kind"] == "historical"
    assert view["language"] == "en"
    assert view["historical"] is True
    assert view["language_boundary"] == "historical_english_model_boundary"
    assert "historical English" in view["label"]


def test_explained_projection_separates_gemma_text_from_canonicalizer_text() -> None:
    result = {"status": "succeeded", "no_authority": True}
    structured = {
        "action_hypotheses": [],
        "action_unknown_reason": "canonical action placeholder",
        "option_inference": None,
        "option_unknown_reason": "canonical option placeholder",
        "motive_hypotheses": [],
        "motive_unknown_reason": "canonical motive placeholder",
        "racio_reported_uncertainty": {
            "option_mapping": "not_reported",
            "motive_interpretation": "not_reported",
        },
    }
    interpretation = {"structured_output": structured}
    draft = {
        "source_mind": "E",
        "action_hypotheses": [],
        "action_abstention_explanation": {
            "explanation": "One signal is unavailable and the others do not display an action.",
            "cited_observation_ids": ["observation_004"],
        },
        "option_inference": None,
        "option_abstention_explanation": {
            "explanation": "No visible observation distinguishes the two public options.",
            "cited_observation_ids": ["observation_004"],
        },
        "motive_hypotheses": [],
        "motive_abstention_explanation": {
            "explanation": "No visible observation independently supports a motive.",
            "cited_observation_ids": ["observation_004"],
        },
        "racio_reported_uncertainty": structured["racio_reported_uncertainty"],
    }
    response = {
        "model_draft": draft,
        "exact_model_request": {
            "model": "gemma4:31b",
            "messages": [
                {"role": "system", "content": "Use Emocio, Instinkt, and Racio."},
                {"role": "user", "content": '{"language":"en"}'},
            ],
            "format": {"type": "object"},
            "options": {"seed": 314159},
            "stream": False,
            "think": True,
        },
    }

    shape, projected = shadow_view._shadow_view(  # noqa: SLF001
        result, interpretation, response
    )

    assert shape == "full_abstention"
    assert projected["model_explanation_status"] == "provided"
    assert projected["model_authored_abstention_explanations"]["action"] == (
        draft["action_abstention_explanation"]
    )
    assert all(
        item["source"] == "deterministic_canonicalizer"
        and item["model_authored"] is False
        for item in projected["canonicalizer_additions"]
    )
    assert {
        item["value"] for item in projected["canonicalizer_additions"]
    } == {
        "canonical action placeholder",
        "canonical option placeholder",
        "canonical motive placeholder",
    }


def test_exact_model_input_projection_exposes_request_without_safety_notice() -> None:
    exact_request = {
        "model": "gemma4:31b",
        "messages": [
            {"role": "system", "content": "Use Emocio, Instinkt, and Racio."},
            {"role": "user", "content": '{"language":"en"}'},
        ],
        "format": {"type": "object"},
        "options": {"seed": 314159},
        "stream": False,
        "think": True,
    }
    projected = shadow_view._exact_model_input_view(  # noqa: SLF001
        {"language": "en"},
        {
            "call_id": "call_001",
            "parameters": [
                {
                    "name": "request_payload_sha256",
                    "canonical_json_value": json.dumps(
                        shadow_view.sha256_hex(exact_request)
                    ),
                }
            ],
            "safety_notice": {"canonical_sl": "hidden"},
        },
        {"exact_model_request": exact_request},
        None,
    )

    assert projected["availability"] == "complete"
    assert projected["system_instruction"] == "Use Emocio, Instinkt, and Racio."
    assert projected["user_packet_json"] == '{"language":"en"}'
    assert projected["source"] == "persisted_exact"
    assert projected["request_payload_sha256"] == shadow_view.sha256_hex(
        exact_request
    )
    assert projected["call_spec"] == {
        "call_id": "call_001",
        "parameters": [
            {
                "name": "request_payload_sha256",
                "canonical_json_value": json.dumps(
                    shadow_view.sha256_hex(exact_request)
                ),
            }
        ],
    }
    assert "canonical_sl" not in json.dumps(projected, sort_keys=True)


def test_s1r_receipt_is_bounded_and_not_mutated_by_replay() -> None:
    receipt_path = (
        ROOT
        / "Docs/evals/research_reset_2026-07/"
        "gemma4_text_shadow_s1r_post_verification_receipt.json"
    )
    before = receipt_path.read_bytes()
    assert len(before) <= shadow_view.MAX_EXTERNAL_RECEIPT_BYTES
    payload = shadow_view.build_shadow_evidence_view(ROOT, "s1r-reconciled")
    after = receipt_path.read_bytes()
    assert after == before
    bounded = json.loads(before)
    assert payload["integrity"]["receipt_id"] == bounded["receipt_id"]
    assert payload["integrity"]["receipt_sha256"] == bounded["receipt_sha256"]


def test_frozen_lane_shapes_preserve_authoritative_success(
    frozen_views: dict[str, dict[str, Any]],
) -> None:
    s1_e = frozen_views["s1-partial"]["lanes"]["emocio"]
    s1_i = frozen_views["s1-partial"]["lanes"]["instinkt"]
    s1r_e = frozen_views["s1r-reconciled"]["lanes"]["emocio"]
    s1r_i = frozen_views["s1r-reconciled"]["lanes"]["instinkt"]

    assert s1_e["presentation_shape"] == "failed"
    assert s1_e["authoritative"]["status"] == "succeeded"
    assert s1_e["shadow"]["status"] == "failed"
    assert s1_e["shadow"]["failure"] == {
        "stage": "canonicalizer_v3_validation",
        "code": "canonicalizer_failure",
        "summary": "DraftV3 failed the non-semantic V3 canonicalizer.",
    }
    assert s1_e["shadow"]["accepted_interpretation_published"] is False
    assert s1_i["presentation_shape"] == "action_only"

    assert s1r_e["presentation_shape"] == "full_abstention"
    assert s1r_e["shadow"]["status"] == "succeeded"
    assert s1r_e["shadow"]["action_hypotheses"] == []
    assert s1r_e["shadow"]["option_inference"] is None
    assert s1r_e["shadow"]["motive_hypotheses"] == []
    assert all(s1r_e["shadow"]["unknown_reasons"].values())
    assert s1r_e["diagnostic_comparison"]["citation_differences"][
        "shadow_action_citations"
    ] == []
    assert s1r_e["shadow"]["accepted_interpretation_published"] is True

    assert s1r_i["presentation_shape"] == "action_only"
    assert len(s1r_i["shadow"]["action_hypotheses"]) == 1
    assert s1r_i["shadow"]["option_inference"] is None
    assert s1r_i["shadow"]["motive_hypotheses"] == []
    assert s1r_i["shadow"]["unknown_reasons"]["action"] is None
    assert s1r_i["shadow"]["unknown_reasons"]["option"]
    assert s1r_i["shadow"]["unknown_reasons"]["motive"]
    assert all(
        lane["shadow"]["no_authority"] is True
        for view in frozen_views.values()
        for lane in view["lanes"].values()
    )


def test_view_keeps_noncomparable_semantics_explicit(
    frozen_views: dict[str, dict[str, Any]],
) -> None:
    comparison = frozen_views["s1r-reconciled"]["lanes"]["instinkt"][
        "diagnostic_comparison"
    ]
    assert comparison["motive_family_overlap"]["comparable"] is False
    assert comparison["motive_family_overlap"]["value"] is None
    assert comparison["motive_subtype_overlap"]["comparable"] is False
    assert comparison["motive_subtype_overlap"]["value"] is None
    assert comparison["citation_differences"]["comparable"] is False
    assert comparison["citation_differences"][
        "authoritative_supporting_observation_ids"
    ]
    assert comparison["citation_differences"]["shadow_action_citations"] == [
        ["observation_006"]
    ]
    assert comparison["uncertainty_differences"]["comparable"] is False
    assert comparison["uncertainty_differences"]["authoritative"] is None
    assert "aggregate" not in json.dumps(comparison, sort_keys=True).casefold()


def test_visible_projection_is_allowlisted_and_private_by_default(
    frozen_views: dict[str, dict[str, Any]],
) -> None:
    payload = frozen_views["s1r-reconciled"]
    visible = payload["lanes"]["instinkt"]["visible_input"]
    assert visible["observations"]
    assert visible["public_options"]
    assert visible["observations"][0]["canonical_sl"]
    assert visible["presentation_mode"] == "canonical_sl_only"
    assert visible["public_options"][0]["operational_en"] is None
    assert visible["observations"][0]["visibility"] in {"clear", "degraded"}
    assert visible["channel_quality"] == pytest.approx(0.6408628125)

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for private_key in (
        '"thinking"',
        '"raw_response"',
        '"raw_response_envelope"',
        '"native_option_id"',
        '"native_action_tendency"',
        '"native_motive_summary"',
        '"evaluator_gold"',
    ):
        assert private_key not in serialized
    assert WINDOWS_ABSOLUTE_PATH.search(serialized) is None
    assert POSIX_LOCAL_PATH.search(serialized) is None
    assert "debug_evaluator_ground_truth" not in serialized


def test_debug_projection_uses_control_gap_and_warns_racio_never_saw_truth() -> None:
    payload = shadow_view.build_shadow_evidence_view(
        ROOT, "s1r-reconciled", debug=True
    )
    truth = payload["lanes"]["instinkt"]["debug_evaluator_ground_truth"]
    assert truth["label"] == "DEBUG / EVALUATOR GROUND TRUTH"
    assert truth["warning"] == "Racio did not receive evaluator ground truth."
    assert truth["native_option_id"] == "option_restore"
    assert truth["native_action_tendency"] == "maintain"
    assert truth["native_motive_summary"] == "The shared exit stays clear."


def test_manifest_tamper_fails_before_lazy_cold_verifier(tmp_path: Path) -> None:
    relative = Path(
        "Docs/evals/semantic_lab_v1/s1-gemma4-text-shadow-2026-07-19"
    )
    copied = tmp_path / relative
    shutil.copytree(ROOT / relative, copied)
    summary = copied / "summary.json"
    summary.write_bytes(summary.read_bytes() + b"\n")
    calls = 0

    def must_not_run(_root: Path, _registration: Any):
        nonlocal calls
        calls += 1
        raise AssertionError("tampered preflight cannot reach cold verifier")

    with pytest.raises(shadow_view.ShadowEvidenceIntegrityError):
        shadow_view.build_shadow_evidence_view(
            tmp_path,
            "s1-partial",
            cold_verifier=must_not_run,
        )
    assert calls == 0


def test_tampered_en1_route_returns_409(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = Path(
        "Docs/evals/semantic_lab_v1/en1-gemma4-text-shadow-2026-07-20"
    )
    copied = tmp_path / relative
    shutil.copytree(ROOT / relative, copied)
    summary = copied / "summary.json"
    summary.write_bytes(summary.read_bytes() + b"\n")
    monkeypatch.setattr(server, "ROOT", tmp_path)

    with pytest.raises(HTTPException) as raised:
        server.shadow_evidence_detail(
            "en1-runtime",
            _http_request(path="/api/shadow-evidence/en1-runtime"),
        )
    assert raised.value.status_code == 409
    assert raised.value.detail == (
        "Frozen shadow evidence failed integrity verification."
    )


def test_tampered_en2_route_returns_409(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relative = Path(
        "Docs/evals/semantic_lab_v1/en2-gemma4-explained-shadow-2026-07-21"
    )
    copied = tmp_path / relative
    shutil.copytree(ROOT / relative, copied)
    summary = copied / "summary.json"
    summary.write_bytes(summary.read_bytes() + b"\n")
    monkeypatch.setattr(server, "ROOT", tmp_path)

    with pytest.raises(HTTPException) as raised:
        server.shadow_evidence_detail(
            "en2-explained",
            _http_request(path="/api/shadow-evidence/en2-explained"),
        )
    assert raised.value.status_code == 409
    assert raised.value.detail == (
        "Frozen shadow evidence failed integrity verification."
    )


def test_scan_enforces_file_count_limit(tmp_path: Path) -> None:
    root = tmp_path / "bounded-root"
    root.mkdir()
    for index in range(shadow_view.MAX_EVIDENCE_FILES + 1):
        (root / f"{index:03d}.json").write_text("{}", encoding="utf-8")
    with pytest.raises(
        shadow_view.ShadowEvidenceIntegrityError, match="file-count limit"
    ):
        shadow_view._scan_evidence_root(root)


@pytest.mark.parametrize(
    "evidence_id",
    ("unknown", "../s1-partial", r"C:\\private\\root", "/tmp/s1-partial"),
)
def test_route_rejects_unknown_or_raw_filesystem_locator(evidence_id: str) -> None:
    with pytest.raises(HTTPException) as raised:
        server.shadow_evidence_detail(
            evidence_id,
            _http_request(path=f"/api/shadow-evidence/{evidence_id}"),
        )
    assert raised.value.status_code == 404
    assert "path" not in raised.value.detail.casefold()


def test_route_masks_integrity_details_and_rejects_concurrent_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        server,
        "build_shadow_evidence_view",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            shadow_view.ShadowEvidenceIntegrityError("private local path and hash")
        ),
    )
    with pytest.raises(HTTPException) as raised:
        server.shadow_evidence_detail(
            "s1-partial",
            _http_request(path="/api/shadow-evidence/s1-partial"),
        )
    assert raised.value.status_code == 409
    assert raised.value.detail == (
        "Frozen shadow evidence failed integrity verification."
    )
    assert "private" not in raised.value.detail

    class BusyGate:
        def acquire(self, *, blocking: bool) -> bool:
            assert blocking is False
            return False

        def release(self) -> None:
            pytest.fail("a gate that was not acquired cannot be released")

    monkeypatch.setattr(server, "_SHADOW_EVIDENCE_BUILD_GATE", BusyGate())
    with pytest.raises(HTTPException) as raised:
        server.shadow_evidence_detail(
            "s1-partial",
            _http_request(path="/api/shadow-evidence/s1-partial"),
        )
    assert raised.value.status_code == 503
    assert raised.value.headers == {"Retry-After": "1"}


@pytest.mark.parametrize("debug", (False, True))
def test_shadow_detail_is_strictly_loopback_only(
    monkeypatch: pytest.MonkeyPatch,
    debug: bool,
) -> None:
    monkeypatch.setenv(server.ALLOW_REMOTE_ENV, "true")
    monkeypatch.setenv(server.ALLOW_REMOTE_DEBUG_ENV, "true")
    monkeypatch.setattr(
        server,
        "build_shadow_evidence_view",
        lambda _root, evidence_id, *, debug: {
            "evidence_id": evidence_id,
            "debug": debug,
        },
    )
    with pytest.raises(HTTPException) as raised:
        server.shadow_evidence_detail(
            "s1r-reconciled",
            _http_request(
                path="/api/shadow-evidence/s1r-reconciled",
                host="203.0.113.9",
                host_header="public.example:8765",
            ),
            debug=debug,
        )
    assert raised.value.status_code == 403
    assert "loopback" in raised.value.detail

    assert server.shadow_evidence_detail(
        "s1r-reconciled",
        _http_request(
            path="/api/shadow-evidence/s1r-reconciled",
            host="::1",
        ),
        debug=debug,
    ) == {"evidence_id": "s1r-reconciled", "debug": debug}


def test_shadow_index_is_strictly_loopback_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(server.ALLOW_REMOTE_ENV, "true")
    monkeypatch.setenv(server.ALLOW_REMOTE_DEBUG_ENV, "true")
    monkeypatch.setattr(
        server,
        "build_shadow_evidence_index",
        lambda _root: {"evidence": []},
    )
    with pytest.raises(HTTPException) as raised:
        server.shadow_evidence_index(
            _http_request(
                path="/api/shadow-evidence",
                host="203.0.113.9",
                host_header="public.example:8765",
            )
        )
    assert raised.value.status_code == 403
    assert "loopback" in raised.value.detail

    assert server.shadow_evidence_index(
        _http_request(path="/api/shadow-evidence", host="::1")
    ) == {"evidence": []}


def test_bootstrap_and_replay_imports_do_not_load_concrete_model_providers() -> None:
    code = """
from pathlib import Path
import sys
from app.gui import server
from app.gui.shadow_view import build_shadow_evidence_view
server.bootstrap()
for evidence_id in ('en2-explained', 'en1-runtime', 's1-partial', 's1r-reconciled'):
    build_shadow_evidence_view(Path.cwd(), evidence_id)
for name in sorted(sys.modules):
    lowered = name.lower()
    if '.providers.ollama' in lowered or '.providers.gemma4_text_shadow' in lowered:
        print(name)
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.stdout == ""
    assert completed.stderr == ""


def test_verified_index_is_read_only_and_model_free() -> None:
    payload = shadow_view.build_shadow_evidence_index(ROOT)
    assert payload["default_evidence_id"] == "en2-explained"
    assert [item["evidence_id"] for item in payload["evidence"]] == [
        "en2-explained",
        "en1-runtime",
        "s1-partial",
        "s1r-reconciled",
    ]
    assert [item["label"] for item in payload["evidence"]] == [
        "EN2 · current explained English shadow",
        "EN1 · historical English runtime shadow",
        "S1 · historical Slovene partial failure",
        "S1R · historical Slovene reconciled success",
    ]
    assert [item["kind"] for item in payload["evidence"]] == [
        "current_runtime",
        "historical",
        "historical",
        "historical",
    ]
    assert [item["language"] for item in payload["evidence"]] == [
        "en",
        "en",
        "sl",
        "sl",
    ]
    assert all(
        "Current explained English boundary" in item["summary"]
        or "Previous English boundary" in item["summary"]
        or "authoritative deterministic cycle" in item["summary"]
        or "action-only hypothesis" in item["summary"]
        for item in payload["evidence"]
    )
    assert payload["read_only"] is True
    assert payload["live_model_execution"] is False
    assert payload["authority"] == "none"
    assert payload["model_calls"] == 0


def test_all_registered_roots_and_receipts_are_read_only_during_replay() -> None:
    paths = (
        ROOT / "Docs/evals/semantic_lab_v1/s1-gemma4-text-shadow-2026-07-19",
        ROOT / "Docs/evals/semantic_lab_v1/s1r-gemma4-text-shadow-2026-07-19",
        ROOT / "Docs/evals/semantic_lab_v1/en1-gemma4-text-shadow-2026-07-20",
        ROOT
        / "Docs/evals/semantic_lab_v1/"
        "en2-gemma4-explained-shadow-2026-07-21",
    )
    receipts = (
        ROOT
        / "Docs/evals/research_reset_2026-07/"
        "gemma4_text_shadow_s1r_post_verification_receipt.json",
        ROOT
        / "Docs/evals/research_reset_2026-07/"
        "gemma4_english_runtime_shadow_smoke_receipt.json",
        ROOT
        / "Docs/evals/research_reset_2026-07/"
        "gemma4_english_explained_shadow_smoke_receipt.json",
    )

    def snapshot() -> dict[str, bytes]:
        return {
            path.relative_to(ROOT).as_posix(): path.read_bytes()
            for root in paths
            for path in sorted(root.rglob("*"))
            if path.is_file()
        } | {
            path.relative_to(ROOT).as_posix(): path.read_bytes()
            for path in receipts
        }

    before = snapshot()
    shadow_view.build_shadow_evidence_index(ROOT)
    assert snapshot() == before


def test_api_middleware_applies_existing_loopback_boundary_to_replay() -> None:
    async def accepted(_request: Request):
        return server.Response(status_code=204)

    rejected = asyncio.run(
        server.enforce_loopback_default(
            _http_request(
                path="/api/shadow-evidence",
                host="203.0.113.10",
            ),
            accepted,
        )
    )
    assert rejected.status_code == 403
    allowed = asyncio.run(
        server.enforce_loopback_default(
            _http_request(path="/api/shadow-evidence"),
            accepted,
        )
    )
    assert allowed.status_code == 204
    assert allowed.headers["cache-control"] == "no-store"
