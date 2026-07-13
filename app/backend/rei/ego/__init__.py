"""Append-only Ego composition services; never an Ego decision agent."""

from .composition import derive_composition_snapshot
from .measure import build_ego_measure
from .projections import EgoModalityProjections, derive_modality_projections
from .trace_store import (
    EgoTraceConflictError,
    EgoTraceStoreError,
    EgoTraceTamperError,
    FileEgoTraceStore,
    InMemoryEgoTraceStore,
)

__all__ = [
    "EgoModalityProjections",
    "EgoTraceConflictError",
    "EgoTraceStoreError",
    "EgoTraceTamperError",
    "FileEgoTraceStore",
    "InMemoryEgoTraceStore",
    "build_ego_measure",
    "derive_composition_snapshot",
    "derive_modality_projections",
]
