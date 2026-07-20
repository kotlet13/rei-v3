"""English-only active projection of the frozen native Ollama provider.

The historical B14 provider remains unchanged for exact evidence replay. This
subclass changes only the active provider identity, instruction, and language
gate; it reuses the reviewed transport, GPU, retry, fallback, and evidence
contracts.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.provider import ProviderIdentity, ProviderParameter
from ..models.racio import RacioInputPacket
from ..racio.text_reasoner_adapter import RACIO_STRUCTURED_INSTRUCTION_EN
from .language_policy import (
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


OLLAMA_EN_PROVIDER_REVISION = "rei-native-ollama-racio-en-v1"


@dataclass(frozen=True, slots=True)
class OllamaRacioNativeEnProvider(OllamaRacioNativeProvider):
    """Native Racio provider that fails before transport unless input is English."""

    @property
    def identity(self) -> ProviderIdentity:
        payload = {
            "kind": "text_reasoner",
            "implementation": "rei.providers.ollama_en.OllamaRacioNativeEnProvider",
            "implementation_revision": (
                f"{OLLAMA_EN_PROVIDER_REVISION};"
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
            "source_provider_revision": OLLAMA_PROVIDER_REVISION,
        }
        values.update(
            {name: _parameter(name, value) for name, value in additions.items()}
        )
        return tuple(values[name] for name in sorted(values))

    def request_payload(self, packet: RacioInputPacket) -> Mapping[str, Any]:
        packet_payload = packet.model_dump(mode="json", round_trip=True)
        require_english_local_model_payload(
            declared_language=packet.language,
            provider_payload=packet_payload,
        )
        payload = dict(OllamaRacioNativeProvider.request_payload(self, packet))
        payload["system"] = RACIO_STRUCTURED_INSTRUCTION_EN
        payload["prompt"] = canonical_json_bytes(packet_payload).decode("utf-8")
        return payload


def build_ollama_racio_native_en_providers(
    provider: OllamaRacioNativeEnProvider,
) -> OllamaRacioNativeProviders:
    """Bind only the active English wrapper into a native provider set."""

    if not isinstance(provider, OllamaRacioNativeEnProvider):
        raise TypeError("Active Ollama provider sets require the English wrapper")
    return build_ollama_racio_native_providers(provider)


__all__ = [
    "OLLAMA_EN_PROVIDER_REVISION",
    "OllamaRacioNativeEnProvider",
    "build_ollama_racio_native_en_providers",
]
