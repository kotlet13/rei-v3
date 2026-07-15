"""Semantic Lab and native REI composition workbench.

The package is intentionally isolated from the archived textual workbench.
"""

from .semantic_lab import build_semantic_lab_view
from .view_model import build_workbench_view

__all__ = ["build_semantic_lab_view", "build_workbench_view"]
