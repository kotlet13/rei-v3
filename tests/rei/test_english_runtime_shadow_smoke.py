from __future__ import annotations

from pathlib import Path

import pytest

from app.backend.rei.providers.language_policy import (
    require_english_local_model_payload,
)
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
    assert first["receipt_id"].startswith("gemma4_english_shadow_receipt_")
    assert len(first["receipt_sha256"]) == 64
