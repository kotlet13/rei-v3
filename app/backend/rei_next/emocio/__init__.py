"""Deterministic B6 Emocio structured-core implementation.

The public API deliberately separates grounded packet construction, structured
scene compilation, transparent valuation, native policy, and optional
rendering.  Image artifacts are presentation outputs and are never inputs to
the native policy.
"""

from .packets import build_emocio_packet
from .policy import EmocioPolicyDecision, OptionAggregateScore, choose_native_option
from .processor import (
    DeterministicEmocioProcessor,
    EmocioProcessingResult,
    process_emocio,
)
from .renderer import EmocioRenderer, NullRenderer
from .scene_graph import CompiledEmocioScenes, compile_emocio_scenes
from .valuation import (
    aggregate_option_valuation,
    build_emocio_visual_state,
    value_option_rollout,
)

__all__ = [
    "CompiledEmocioScenes",
    "DeterministicEmocioProcessor",
    "EmocioPolicyDecision",
    "EmocioProcessingResult",
    "EmocioRenderer",
    "NullRenderer",
    "OptionAggregateScore",
    "aggregate_option_valuation",
    "build_emocio_packet",
    "build_emocio_visual_state",
    "choose_native_option",
    "compile_emocio_scenes",
    "process_emocio",
    "value_option_rollout",
]
