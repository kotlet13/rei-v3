"""English-only active projection of the frozen C3 Ollama interpreter.

The C3 v6 provider and instruction remain untouched for historical benchmark
replay. This subclass adds a new identity, an English instruction, and a
provider-local language gate while reusing the frozen transport and validation
behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..communication.conscious_access import ConsciousAccessPacket
from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.provider import ProviderIdentity, ProviderParameter
from .language_policy import (
    LOCAL_MODEL_LANGUAGE_POLICY_ID,
    require_english_local_model_payload,
)
from .ollama import _parameter
from .ollama_interpreter import (
    OLLAMA_INTERPRETER_PROVIDER_REVISION,
    OllamaStructuredRacioInterpreterProvider,
    RACIO_INTERPRETER_STRUCTURED_INSTRUCTION,
)


OLLAMA_INTERPRETER_EN_PROVIDER_REVISION = (
    "rei-ollama-racio-interpreter-en-v1"
)
RACIO_INTERPRETER_STRUCTURED_INSTRUCTION_EN = (
    RACIO_INTERPRETER_STRUCTURED_INSTRUCTION.replace(
        "These labels remain hypotheses, not facts about a person. Use the same enum\n"
        "identifier for semantically equivalent Slovenian and English packets.",
        "These labels remain hypotheses, not facts about a person. The packet prose "
        "is\nEnglish; preserve its enum identifiers exactly and respond only in "
        "English.",
    )
)
if (
    RACIO_INTERPRETER_STRUCTURED_INSTRUCTION_EN
    == RACIO_INTERPRETER_STRUCTURED_INSTRUCTION
):
    raise RuntimeError("Frozen C3 instruction no longer matches the English projection")


@dataclass(frozen=True, slots=True)
class OllamaStructuredRacioInterpreterEnProvider(
    OllamaStructuredRacioInterpreterProvider
):
    """Conscious-access interpreter with a provider-local English-only gate."""

    @property
    def identity(self) -> ProviderIdentity:
        payload = {
            "kind": "text_reasoner",
            "implementation": (
                "rei.providers.ollama_interpreter_en."
                "OllamaStructuredRacioInterpreterEnProvider"
            ),
            "implementation_revision": (
                f"{OLLAMA_INTERPRETER_EN_PROVIDER_REVISION};"
                f"ollama={self.runtime.server_version}"
            ),
            "uses_model": True,
            "model": self.runtime.model,
            "model_revision": self.runtime.digest,
        }
        return ProviderIdentity(provider_id=content_id("provider", payload), **payload)

    @property
    def parameters(self) -> tuple[ProviderParameter, ...]:
        inherited = OllamaStructuredRacioInterpreterProvider.parameters.fget(self)
        values = {item.name: item for item in inherited}
        additions = {
            "instruction_sha256": sha256_hex(
                RACIO_INTERPRETER_STRUCTURED_INSTRUCTION_EN
            ),
            "local_model_language_policy_id": LOCAL_MODEL_LANGUAGE_POLICY_ID,
            "source_provider_revision": OLLAMA_INTERPRETER_PROVIDER_REVISION,
        }
        values.update(
            {name: _parameter(name, value) for name, value in additions.items()}
        )
        return tuple(values[name] for name in sorted(values))

    def request_payload(
        self,
        packet: ConsciousAccessPacket,
    ) -> Mapping[str, Any]:
        provider_view = packet.provider_payload()
        require_english_local_model_payload(
            declared_language=packet.language,
            provider_payload=provider_view,
        )
        payload = dict(
            OllamaStructuredRacioInterpreterProvider.request_payload(self, packet)
        )
        payload["system"] = RACIO_INTERPRETER_STRUCTURED_INSTRUCTION_EN
        payload["prompt"] = canonical_json_bytes(provider_view).decode("utf-8")
        return payload


__all__ = [
    "OLLAMA_INTERPRETER_EN_PROVIDER_REVISION",
    "OllamaStructuredRacioInterpreterEnProvider",
    "RACIO_INTERPRETER_STRUCTURED_INSTRUCTION_EN",
]
