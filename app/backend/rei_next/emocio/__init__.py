"""Deterministic B6 Emocio structured-core implementation.

The public API deliberately separates grounded packet construction, structured
scene compilation, transparent valuation, native policy, and optional
rendering.  Image artifacts are presentation outputs and are never inputs to
the native policy.
"""

from .packets import build_emocio_packet
from .policy import EmocioPolicyDecision, OptionAggregateScore, choose_native_option
from .artifacts import LocalPngArtifactStore, StoredPng, inspect_png
from .diffusers_renderer import (
    DiffusersImageRenderer,
    DiffusersRuntimeConfig,
    DiffusionBackend,
    LazyDiffusersBackend,
)
from .processor import (
    DeterministicEmocioProcessor,
    EmocioProcessingResult,
    process_emocio,
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
