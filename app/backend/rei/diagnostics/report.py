"""Stable Markdown rendering for B11 run diagnostics."""

from __future__ import annotations

from ..models.run import RunManifest
from .invariants import InvariantReport


def render_diagnostic_report(
    invariants: InvariantReport,
    manifest: RunManifest,
) -> str:
    lines = [
        f"# REI native run {manifest.run_id}",
        "",
        f"- status: `{manifest.status}`",
        f"- mode: `{manifest.mode}`",
        f"- profile: `{manifest.profile_id}`",
        f"- invariant gate: `{'passed' if invariants.all_passed else 'failed'}`",
        "",
        "## Invariants",
        "",
    ]
    lines.extend(
        f"- [{'x' if item.status == 'passed' else ' '}] `{item.check_id}` — {item.detail}"
        for item in invariants.checks
    )
    lines.extend(("", "## Warnings", ""))
    if manifest.warnings:
        lines.extend(f"- {warning}" for warning in manifest.warnings)
    else:
        lines.append("- none")
    lines.extend(("", "## Safety flags", ""))
    if manifest.safety_flags:
        lines.extend(f"- `{flag}`" for flag in manifest.safety_flags)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


__all__ = ["render_diagnostic_report"]
