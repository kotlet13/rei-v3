"""Thin English-only projection of the frozen native Ollama Racio provider."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.provider import ProviderIdentity, ProviderParameter
from ..models.racio import RacioInputPacket
from ..racio.text_reasoner_adapter import RACIO_STRUCTURED_INSTRUCTION_EN
from .language_policy import (
    ENGLISH_PRESENTATION_MODE,
    LOCAL_MODEL_LANGUAGE_POLICY_ID,
    require_english_local_model_payload,
)
from .ollama import (
    OLLAMA_PROVIDER_REVISION,
    OllamaRacioNativeProvider,
    OllamaRacioNativeProviders,
    _parameter,
    build_ollama_racio_native_providers,
)


OLLAMA_EN_TRIAD_PROVIDER_REVISION = (
    "rei-native-ollama-racio-en-triad-screen-v1"
)


@dataclass(frozen=True, slots=True)
class OllamaRacioNativeEnTriadProvider(OllamaRacioNativeProvider):
    """English gate and screen profile layered over the reviewed provider."""

    top_p: float = 0.95
    top_k: int = 64

    def __post_init__(self) -> None:
        OllamaRacioNativeProvider.__post_init__(self)
        if not math.isfinite(self.top_p) or not 0.0 < self.top_p <= 1.0:
            raise ValueError("Ollama top_p must be in (0, 1]")
        if isinstance(self.top_k, bool) or self.top_k < 1:
            raise ValueError("Ollama top_k must be a positive integer")

    @property
    def identity(self) -> ProviderIdentity:
        payload = {
            "kind": "text_reasoner",
            "implementation": (
                "rei.providers.ollama_en.OllamaRacioNativeEnTriadProvider"
            ),
            "implementation_revision": (
                f"{OLLAMA_EN_TRIAD_PROVIDER_REVISION};"
                f"ollama={self.runtime.server_version}"
            ),
            "uses_model": True,
            "model": self.runtime.model,
            "model_revision": self.runtime.digest,
        }
        return ProviderIdentity(provider_id=content_id("provider", payload), **payload)

    @property
    def parameters(self) -> tuple[ProviderParameter, ...]:
        inherited = OllamaRacioNativeProvider.parameters.fget(self)
        values = {item.name: item for item in inherited}
        additions = {
            "instruction_sha256": sha256_hex(RACIO_STRUCTURED_INSTRUCTION_EN),
            "local_model_language_policy_id": LOCAL_MODEL_LANGUAGE_POLICY_ID,
            "presentation_mode": ENGLISH_PRESENTATION_MODE,
            "source_provider_revision": OLLAMA_PROVIDER_REVISION,
            "top_k": self.top_k,
            "top_p": self.top_p,
        }
        values.update(
            {name: _parameter(name, value) for name, value in additions.items()}
        )
        return tuple(values[name] for name in sorted(values))

    def request_payload(self, packet: RacioInputPacket) -> Mapping[str, Any]:
        packet_payload = packet.model_dump(mode="json", round_trip=True)
        gate_payload = {
            "language": packet.language,
            "presentation_mode": ENGLISH_PRESENTATION_MODE,
            "packet": packet_payload,
        }
        require_english_local_model_payload(
            declared_language=packet.language,
            provider_payload=gate_payload,
        )
        payload = dict(OllamaRacioNativeProvider.request_payload(self, packet))
        payload["system"] = RACIO_STRUCTURED_INSTRUCTION_EN
        payload["prompt"] = canonical_json_bytes(packet_payload).decode("utf-8")
        options = dict(payload["options"])
        options["top_p"] = self.top_p
        options["top_k"] = self.top_k
        payload["options"] = options
        return payload


def build_ollama_racio_native_en_triad_providers(
    provider: OllamaRacioNativeEnTriadProvider,
) -> OllamaRacioNativeProviders:
    """Bind only the screen wrapper to deterministic Emocio and Instinkt."""

    if not isinstance(provider, OllamaRacioNativeEnTriadProvider):
        raise TypeError("TRIAD-S1 requires the English triad-screen wrapper")
    return build_ollama_racio_native_providers(provider)


__all__ = [
    "OLLAMA_EN_TRIAD_PROVIDER_REVISION",
    "OllamaRacioNativeEnTriadProvider",
    "build_ollama_racio_native_en_triad_providers",
]
