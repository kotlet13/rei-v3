"""Bounded embodied/protective simulator; not a textual decision agent."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .association_memory import (
    AssociationMatch,
    AssociationMemoryConfig,
    BoundedAssociativeMemory,
)
from .dynamics import predicted_loss, recoverability, simulate_option_rollout
from .manifestation import build_instinkt_fixture_projection, build_instinkt_manifestation
from .packets import (
    INSTINKT_PACKET_CAVEAT,
    InstinktEffectSpec,
    bind_instinkt_effects,
    build_instinkt_packet,
)
from .policy import (
    ProtectiveOptionScore,
    ProtectivePolicyDecision,
    build_native_conclusion,
    protective_cost,
    resolve_protective_policy,
)
__all__ = [
    "AssociationMatch",
    "AssociationMemoryConfig",
    "BoundedAssociativeMemory",
    "InstinktProcessResult",
    "OptionAssociationMatches",
    "ProtectiveOptionScore",
    "ProtectivePolicyDecision",
    "build_instinkt_manifestation",
    "build_instinkt_fixture_projection",
    "INSTINKT_PACKET_CAVEAT",
    "InstinktEffectSpec",
    "bind_instinkt_effects",
    "build_instinkt_packet",
    "build_native_conclusion",
    "predicted_loss",
    "process_instinkt",
    "protective_cost",
    "recoverability",
    "resolve_protective_policy",
    "simulate_option_rollout",
]


_LAZY_EXPORTS = {
    "InstinktProcessResult": ".processor",
    "OptionAssociationMatches": ".processor",
    "process_instinkt": ".processor",
}


def __getattr__(name: str) -> Any:
    """Load processor entry points only when explicitly requested.

    B11 frozen-bundle evaluation needs the public manifestation projection but
    must not import or execute native processing code. Lazy exports retain the
    established package API without crossing that boundary.
    """

    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
