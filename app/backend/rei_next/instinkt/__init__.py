"""Bounded embodied/protective simulator; not a textual decision agent."""

from .association_memory import (
    AssociationMatch,
    AssociationMemoryConfig,
    BoundedAssociativeMemory,
)
from .dynamics import predicted_loss, recoverability, simulate_option_rollout
from .manifestation import build_instinkt_manifestation
from .policy import (
    ProtectiveOptionScore,
    ProtectivePolicyDecision,
    build_native_conclusion,
    protective_cost,
    resolve_protective_policy,
)
from .processor import (
    InstinktProcessResult,
    OptionAssociationMatches,
    process_instinkt,
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
    "build_native_conclusion",
    "predicted_loss",
    "process_instinkt",
    "protective_cost",
    "recoverability",
    "resolve_protective_policy",
    "simulate_option_rollout",
]
