from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from app.backend.rei.providers.language_policy import (
    require_english_local_model_payload,
)
from app.backend.rei.ids import content_id
from scripts import run_gemma4_racio_english_shadow_smoke as smoke


def test_smoke_request_and_packets_are_explicitly_english(tmp_path: Path) -> None:
    request = smoke._build_request()
    assert request.scene.language == "en"
    assert request.scene.raw_input == (
        "Decide whether to restore the shared workshop or leave it closed."
    )
    assert tuple(option.description for option in request.scene.options) == (
        "Open and restore the shared workshop.",
        "Keep the shared workshop closed.",
    )

    control = smoke._run_cycle(tmp_path / "control", request)
    packets = smoke._packet_pair(control)

    assert tuple(packet.source_mind for packet in packets) == ("E", "I")
    assert all(packet.language == "en" for packet in packets)
    for packet in packets:
        require_english_local_model_payload(
            declared_language=packet.language,
            provider_payload=packet.provider_payload(),
        )


def test_counting_client_caps_chat_dispatches_at_two() -> None:
    class Base:
        def post(self, path, payload, *, timeout_seconds):
            return path, payload, timeout_seconds

    client = smoke._CountingOllamaClient(Base())
    for index in range(2):
        client.post(
            "/api/chat",
            {"index": index},
            timeout_seconds=1.0,
        )
    with pytest.raises(RuntimeError, match="more than two"):
        client.post("/api/chat", {}, timeout_seconds=1.0)
    assert client.chat_dispatch_count == 2


def test_receipt_is_content_addressed_and_reproducible(tmp_path: Path) -> None:
    output_root = tmp_path / "evidence"
    output_root.mkdir()
    smoke._create_json(
        output_root / "summary.json",
        {
            "shadow_statuses": ["succeeded", "succeeded"],
            "api_chat_dispatches": 2,
            "retries": 0,
            "fallbacks": 0,
            "authoritative_cycle_unchanged": True,
        },
    )
    manifest = {
        "execution_head": "a" * 40,
        "manifest_id": "manifest_test",
        "manifest_sha256": "b" * 64,
    }

    first = smoke._receipt_value(output_root, manifest=manifest)
    second = smoke._receipt_value(output_root, manifest=manifest)

    assert first == second
    assert first["receipt_id"].startswith(f"{smoke.RECEIPT_ID_PREFIX}_")
    assert len(first["receipt_sha256"]) == 64


def test_manifest_prefix_is_valid_stable_and_content_addressed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "evidence"
    output_root.mkdir()
    (output_root / "artifact.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(smoke, "_canonical_json_file_sha256", lambda _path: "a" * 64)

    first = smoke._manifest_value(output_root, execution_head="b" * 40)
    second = smoke._manifest_value(output_root, execution_head="b" * 40)
    (output_root / "artifact.json").write_text('{"changed":true}', encoding="utf-8")
    changed = smoke._manifest_value(output_root, execution_head="b" * 40)

    assert len(smoke.MANIFEST_ID_PREFIX) <= 32
    assert first == second
    assert first["manifest_id"].startswith(f"{smoke.MANIFEST_ID_PREFIX}_")
    assert changed["manifest_id"] != first["manifest_id"]


@pytest.mark.parametrize(
    "prefix",
    ("Bad", "has space", "has/slash", "has:colon", "a" * 33),
)
def test_global_content_id_prefix_protection_remains(prefix: str) -> None:
    with pytest.raises(ValueError, match="ID prefix"):
        content_id(prefix, {"value": 1})


def test_only_manifest_may_be_added_to_preserved_evidence() -> None:
    before = (("summary.json", "a" * 64, 12),)
    after = (*before, (smoke.MANIFEST_NAME, "b" * 64, 42))

    smoke._assert_only_manifest_added(before, after)

    with pytest.raises(ValueError, match="changed existing model evidence"):
        smoke._assert_only_manifest_added(
            before,
            (("summary.json", "c" * 64, 12), after[-1]),
        )


def test_offline_completion_does_not_discover_or_call_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "evidence"
    output_root.mkdir()
    smoke._create_json(
        output_root / "summary.json",
        {
            "execution_head": "a" * 40,
            "shadow_statuses": ["succeeded", "succeeded"],
            "api_chat_dispatches": 2,
            "retries": 0,
            "fallbacks": 0,
            "authoritative_cycle_unchanged": True,
        },
    )
    receipt_path = tmp_path / "receipt.json"
    monkeypatch.setattr(smoke, "RECEIPT_PATH", receipt_path)
    monkeypatch.setattr(smoke, "_git_text", lambda *_args: smoke.BRANCH)
    monkeypatch.setattr(
        smoke,
        "_discover_shadow_interpreter",
        lambda: pytest.fail("offline completion attempted provider discovery"),
    )
    monkeypatch.setattr(
        smoke,
        "_manifest_value",
        lambda _root, *, execution_head: {
            "execution_head": execution_head,
            "manifest_id": "manifest_test",
            "manifest_sha256": "b" * 64,
        },
    )
    monkeypatch.setattr(
        smoke,
        "_verify_root",
        lambda _root: {
            "execution_head": "a" * 40,
            "manifest_id": "manifest_test",
            "manifest_sha256": "b" * 64,
        },
    )

    assert smoke.complete_offline(output_root) == 0
    assert receipt_path.is_file()
    assert (output_root / smoke.MANIFEST_NAME).is_file()
    with pytest.raises(FileExistsError):
        smoke.complete_offline(output_root)


def test_english_smoke_evidence_checkout_is_byte_stable() -> None:
    report_path = (
        "Docs/evals/semantic_lab_v1/en1-gemma4-text-shadow-2026-07-20/report.md"
    )
    attributes = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", report_path],
        cwd=smoke.ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert f"{report_path}: text: set" in attributes
    assert f"{report_path}: eol: lf" in attributes
