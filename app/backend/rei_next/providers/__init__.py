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

__all__ = [
    "DeterministicEmocioNativeProvider",
    "DeterministicInstinktNativeProvider",
    "DeterministicNativeProviders",
    "DeterministicRacioNativeProvider",
    "EmocioNativeExecution",
    "InstinktNativeExecution",
    "NativeProviderExecution",
    "RacioNativeExecution",
    "build_deterministic_native_providers",
    "build_native_call_spec",
    "build_provider_call_spec",
    "emocio_world_input_id",
    "instinkt_association_input_id",
]


def __getattr__(name: str) -> Any:
    if name == "build_provider_call_spec":
        return build_provider_call_spec
    if name not in __all__:
        raise AttributeError(name)
    from . import deterministic

    return getattr(deterministic, name)
