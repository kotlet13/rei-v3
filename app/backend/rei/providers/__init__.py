"""Provider-neutral protocols and lazily exported deterministic adapters.

The lazy boundary avoids an import cycle because Emocio's renderer imports the
provider protocols while the deterministic Emocio adapter wraps its processor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .native import build_provider_call_spec

if TYPE_CHECKING:
    from .deterministic import (
        DeterministicEmocioNativeProvider,
        DeterministicInstinktNativeProvider,
        DeterministicNativeProviders,
        DeterministicRacioNativeProvider,
        EmocioNativeExecution,
        InstinktNativeExecution,
        NativeProviderExecution,
        RacioNativeExecution,
        build_deterministic_native_providers,
        build_native_call_spec,
        emocio_world_input_id,
        instinkt_association_input_id,
    )
    from .ollama import (
        OllamaApiClient,
        OllamaActiveModel,
        OllamaRacioNativeExecution,
        OllamaRacioNativeProvider,
        OllamaRacioNativeProviders,
        OllamaRacioResponseEvidence,
        OllamaRacioSettings,
        OllamaRuntimeModel,
        build_ollama_racio_native_providers,
        inspect_ollama_runtime,
        inspect_ollama_active_model,
    )
    from .ollama_en import (
        OllamaRacioNativeEnProvider,
        build_ollama_racio_native_en_providers,
    )
    from .ollama_interpreter import (
        OllamaStructuredRacioInterpreterExecution,
        OllamaStructuredRacioInterpreterProvider,
        OllamaStructuredRacioInterpreterResponseEvidence,
    )
    from .ollama_interpreter_en import (
        OllamaStructuredRacioInterpreterEnProvider,
    )

__all__ = [
    "DeterministicEmocioNativeProvider",
    "DeterministicInstinktNativeProvider",
    "DeterministicNativeProviders",
    "DeterministicRacioNativeProvider",
    "EmocioNativeExecution",
    "InstinktNativeExecution",
    "NativeProviderExecution",
    "RacioNativeExecution",
    "OllamaApiClient",
    "OllamaActiveModel",
    "OllamaRacioNativeExecution",
    "OllamaRacioNativeEnProvider",
    "OllamaRacioNativeProviders",
    "OllamaRacioResponseEvidence",
    "OllamaRacioSettings",
    "OllamaRuntimeModel",
    "OllamaStructuredRacioInterpreterExecution",
    "OllamaStructuredRacioInterpreterEnProvider",
    "OllamaStructuredRacioInterpreterResponseEvidence",
    "build_deterministic_native_providers",
    "build_native_call_spec",
    "build_ollama_racio_native_en_providers",
    "build_provider_call_spec",
    "emocio_world_input_id",
    "instinkt_association_input_id",
    "inspect_ollama_runtime",
    "inspect_ollama_active_model",
]


def __getattr__(name: str) -> Any:
    if name == "build_provider_call_spec":
        return build_provider_call_spec
    if name not in __all__:
        raise AttributeError(name)
    if name in {
        "OllamaRacioNativeEnProvider",
        "build_ollama_racio_native_en_providers",
    }:
        from . import ollama_en

        return getattr(ollama_en, name)
    if name == "OllamaStructuredRacioInterpreterEnProvider":
        from . import ollama_interpreter_en

        return getattr(ollama_interpreter_en, name)
    if name.startswith("OllamaStructuredRacioInterpreter"):
        from . import ollama_interpreter

        return getattr(ollama_interpreter, name)
    if name.startswith("Ollama") or name in {
        "build_ollama_racio_native_providers",
        "inspect_ollama_active_model",
        "inspect_ollama_runtime",
    }:
        from . import ollama

        return getattr(ollama, name)
    from . import deterministic

    return getattr(deterministic, name)
