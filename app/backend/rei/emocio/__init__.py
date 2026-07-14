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
from .dinov2_encoder import (
    DINOV2_BASE_DIMENSIONS,
    DINOV2_BASE_IMAGE_PROCESSOR_BACKEND,
    DINOV2_BASE_IMPLEMENTATION_REVISION,
    DINOV2_BASE_MODEL_ID,
    DINOV2_BASE_MODEL_REVISION,
    DINOV2_BASE_PILLOW_VERSION,
    DINOV2_BASE_TORCH_VERSION,
    DINOV2_BASE_TORCHVISION_VERSION,
    DINOV2_BASE_TRANSFORMERS_VERSION,
    DinoV2BaseImageEncoder,
    DinoV2FeatureBackend,
    DinoV2RuntimeConfig,
    LazyTransformersDinoV2Backend,
    LocalFloat32VectorStore,
    StoredFloat32Vector,
    dinov2_base_provider_identity,
)
from .current_first_renderer import (
    CurrentFirstEmocioRenderer,
    CurrentFirstRolloutConfig,
)
from .prompting import (
    BilingualStructuredScenePromptCompiler,
    VisualPromptProfile,
)
from .vector_encoding import (
    canonical_l2_float32_le_vector,
    normalized_float32_le_bytes,
    verified_float32_le_vector,
)
from .visual_policy_config import (
    VisualValuationPolicyConfig,
    load_visual_valuation_policy,
    load_visual_valuation_policy_config,
)
from .visual_valuation import (
    BoundVisualEmbedding,
    VisualValuationPolicy,
    VisualValuationResult,
    evaluate_visual_valuation,
)
from .visual_world_memory import (
    VisualWorldMemoryRecord,
    build_visual_world_memory_record,
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
    "BilingualStructuredScenePromptCompiler",
    "BoundVisualEmbedding",
    "CurrentFirstEmocioRenderer",
    "CurrentFirstRolloutConfig",
    "DINOV2_BASE_DIMENSIONS",
    "DINOV2_BASE_IMAGE_PROCESSOR_BACKEND",
    "DINOV2_BASE_IMPLEMENTATION_REVISION",
    "DINOV2_BASE_MODEL_ID",
    "DINOV2_BASE_MODEL_REVISION",
    "DINOV2_BASE_PILLOW_VERSION",
    "DINOV2_BASE_TORCH_VERSION",
    "DINOV2_BASE_TORCHVISION_VERSION",
    "DINOV2_BASE_TRANSFORMERS_VERSION",
    "DeterministicEmocioProcessor",
    "DiffusersImageRenderer",
    "DiffusersRuntimeConfig",
    "DiffusionBackend",
    "DinoV2BaseImageEncoder",
    "DinoV2FeatureBackend",
    "DinoV2RuntimeConfig",
    "EmocioPolicyDecision",
    "EmocioProcessingResult",
    "EmocioRenderer",
    "LazyDiffusersBackend",
    "LazyTransformersDinoV2Backend",
    "LocalEmocioRenderer",
    "LocalPngArtifactStore",
    "LocalFloat32VectorStore",
    "NullRenderer",
    "OptionAggregateScore",
    "RenderSettings",
    "ScenePromptCompiler",
    "StoredPng",
    "StoredFloat32Vector",
    "StructuredScenePromptCompiler",
    "VisualPromptProfile",
    "VisualValuationPolicy",
    "VisualValuationPolicyConfig",
    "VisualValuationResult",
    "VisualWorldMemoryRecord",
    "aggregate_option_valuation",
    "build_emocio_packet",
    "build_emocio_visual_state",
    "build_visual_world_memory_record",
    "choose_native_option",
    "compile_emocio_scenes",
    "canonical_l2_float32_le_vector",
    "derive_scene_seed",
    "dinov2_base_provider_identity",
    "evaluate_visual_valuation",
    "inspect_png",
    "load_visual_valuation_policy",
    "load_visual_valuation_policy_config",
    "normalized_float32_le_bytes",
    "process_emocio",
    "value_option_rollout",
    "verified_float32_le_vector",
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
