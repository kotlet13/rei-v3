"""E1R protocol-correction contracts for the isolated Emocio VWM study."""

from .boundary import BoundaryViolation, validate_clean_media_call
from .preflight import inspect_lpwm_execution_gate

__all__ = [
    "BoundaryViolation",
    "inspect_lpwm_execution_gate",
    "validate_clean_media_call",
]
