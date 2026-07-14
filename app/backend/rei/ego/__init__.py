"""Append-only Ego composition services; never an Ego decision agent."""

from .composition import derive_composition_snapshot
from .measure import build_ego_measure
from .motifs import (
    CanonicalMotifRule,
    EmbeddingMotifHypothesis,
    MotifCandidate,
    MotifHypothesisValidation,
    MotifObservation,
    ThreeStageMotifEngine,
    normalize_motif_token,
)
from .narrative_composition import (
    NarrativeCompositionDiagnostic,
    diagnose_narrative_composition,
)
from .projections import EgoModalityProjections, derive_modality_projections
from .reflector import (
    DeterministicEgoReflector,
    EgoReflectionHypothesis,
    EgoReflector,
)
from .trace_store import (
    EgoTraceConflictError,
    EgoTraceStoreError,
    EgoTraceTamperError,
    FileEgoTraceStore,
    InMemoryEgoTraceStore,
)
from .world_updates import (
    EmocioLongitudinalVisualSignal,
    EmocioWorldUpdate,
    EmocioWorldUpdater,
    InstinktLongitudinalBodySignal,
    InstinktWorldUpdate,
    InstinktWorldUpdater,
    RacioWorldUpdate,
    RacioWorldUpdater,
)

__all__ = [
    "CanonicalMotifRule",
    "DeterministicEgoReflector",
    "EgoReflectionHypothesis",
    "EgoModalityProjections",
    "EgoReflector",
    "EgoTraceConflictError",
    "EgoTraceStoreError",
    "EgoTraceTamperError",
    "EmbeddingMotifHypothesis",
    "EmocioLongitudinalVisualSignal",
    "EmocioWorldUpdate",
    "EmocioWorldUpdater",
    "FileEgoTraceStore",
    "InMemoryEgoTraceStore",
    "InstinktLongitudinalBodySignal",
    "InstinktWorldUpdate",
    "InstinktWorldUpdater",
    "MotifCandidate",
    "MotifHypothesisValidation",
    "MotifObservation",
    "NarrativeCompositionDiagnostic",
    "RacioWorldUpdate",
    "RacioWorldUpdater",
    "ThreeStageMotifEngine",
    "build_ego_measure",
    "diagnose_narrative_composition",
    "derive_composition_snapshot",
    "derive_modality_projections",
    "normalize_motif_token",
]
