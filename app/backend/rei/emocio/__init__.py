"""Deterministic B6 Emocio structured-core implementation.

The public API deliberately separates grounded packet construction, structured
scene compilation, transparent valuation, native policy, and optional
rendering.  Image artifacts are presentation outputs and are never inputs to
the native policy.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .packets import build_emocio_packet
from .policy import EmocioPolicyDecision, OptionAggregateScore, choose_native_option
from .artifacts import LocalPngArtifactStore, StoredPng, inspect_png
from .diffusers_renderer import (
    DiffusersImageRenderer,
    DiffusersRuntimeConfig,
    DiffusionBackend,
    LazyDiffusersBackend,
)
from .renderer import (
    EmocioRenderer,
    LocalEmocioRenderer,
    NullRenderer,
    RenderSettings,
    ScenePromptCompiler,
    StructuredScenePromptCompiler,
    derive_scene_seed,
)
from .scene_graph import CompiledEmocioScenes, compile_emocio_scenes
from .valuation import (
    aggregate_option_valuation,
    build_emocio_visual_state,
    value_option_rollout,
)

__all__ = [
    "CompiledEmocioScenes",
    "DeterministicEmocioProcessor",
    "DiffusersImageRenderer",
    "DiffusersRuntimeConfig",
    "DiffusionBackend",
    "EmocioPolicyDecision",
    "EmocioProcessingResult",
    "EmocioRenderer",
    "LazyDiffusersBackend",
    "LocalEmocioRenderer",
    "LocalPngArtifactStore",
    "NullRenderer",
    "OptionAggregateScore",
    "RenderSettings",
    "ScenePromptCompiler",
    "StoredPng",
    "StructuredScenePromptCompiler",
    "aggregate_option_valuation",
    "build_emocio_packet",
    "build_emocio_visual_state",
    "choose_native_option",
    "compile_emocio_scenes",
    "derive_scene_seed",
    "inspect_png",
    "process_emocio",
    "value_option_rollout",
]


_LAZY_EXPORTS = {
    "DeterministicEmocioProcessor": ".processor",
    "EmocioProcessingResult": ".processor",
    "process_emocio": ".processor",
}


def __getattr__(name: str) -> Any:
    """Load processor entry points only when a caller explicitly requests one.

    Frozen-bundle consumers intentionally import Emocio projections without
    importing or executing the native processor. Keeping the historical
    package-level API lazy preserves compatibility while enforcing that
    boundary.
    """

    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
