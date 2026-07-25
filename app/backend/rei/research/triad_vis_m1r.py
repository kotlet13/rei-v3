"""TRIAD-VIS-M1R source-addressed dual-layer Emocio mosaic.

This research-only module creates deterministic semantic diagrams. It does not
change active Emocio runtime behavior and performs no model, vision, valuation,
character, governance, or native-decision work.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, Self

from PIL import Image, ImageDraw
from pydantic import model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from .triad_vis_m1 import deterministic_canvas_bytes as m1_canvas_bytes
from .triad_vis_o1 import HEIGHT, WIDTH, _file_sha256, _git, _sheet, _write_new
from .triad_vis_o2 import (
    _draw_audience,
    _draw_person,
    _draw_project_diagram,
    _draw_timeline,
    identity_anchors,
)


EXPECTED_BASE_COMMIT: Final = "7d08936de204bc76e76d0196d2ded7639db317d2"
M1_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-m1-2026-07-24"
)
M1_REVIEW_RELATIVE_PATH: Final = M1_RELATIVE_PATH / "human_visual_review.md"
O2_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o2-2026-07-24"
)
O1_SCENE_MANIFEST_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o1-2026-07-24/"
    "scene_prompt_manifest.json"
)
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-m1r-2026-07-24"
)
IMMEDIATE_HORIZON: Final = (
    "Immediately after the action, before any unknown leader decision or "
    "later organizational response."
)
IMAGINED_HORIZON: Final = (
    "Emocio-imagined completion beyond the grounded immediate result; timing "
    "and realization remain unspecified."
)
VARIANTS: Final = ("visible", "absent")
OPTION_IDS: Final = (
    "credit_no_response",
    "credit_private_evidence",
    "credit_public_confront",
)
STATE_ROLES: Final = ("current", "desired", "broken")
OPTION_ROLE_BY_ID: Final = {
    "credit_no_response": "option_0",
    "credit_private_evidence": "option_1",
    "credit_public_confront": "option_2",
}


PanelScope = Literal[
    "present_state",
    "desired_counterfactual",
    "broken_counterfactual",
    "option_action",
    "grounded_immediate_result",
    "emocio_imagined_completion",
]
DerivationStatus = Literal[
    "direct_source",
    "source_synthesis",
    "implementation_neutral",
    "imagined_by_emocio",
]
OfficialAttributionState = Literal[
    "current_unresolved",
    "desired_self_recognized",
    "broken_colleague_recognized",
    "pending",
    "unchanged",
]
LeaderDecisionState = Literal[
    "not_applicable",
    "not_triggered",
    "pending",
    "unknown",
]
RelationType = Literal[
    "leader_decision",
    "official_correction",
    "public_recognition",
    "colleague_response",
    "public_attention",
    "audience_support",
]
RelationState = Literal[
    "not_triggered",
    "unchanged",
    "pending",
    "unchanged_at_immediate_horizon",
    "not_observed",
    "shifted_to_self",
    "unknown",
    "unknown_active",
]
Variant = Literal["visible", "absent"]


class SourceAddressedCanvasV2(FrozenModel):
    schema_version: Literal["triad-source-addressed-canvas-v2"] = (
        "triad-source-addressed-canvas-v2"
    )
    canvas_id: NonEmptyId
    variant: Variant
    semantic_role: NonEmptyId
    source_case_id: NonEmptyId
    source_case_sha256: HashDigest
    supporting_evidence_ids: tuple[NonEmptyId, ...]
    derivation_status: DerivationStatus
    reality_claim_authority: bool
    repository_path: NonEmptyText
    content_sha256: HashDigest
    generated_without_image_model: Literal[True] = True
    contains_readable_text: Literal[False] = False

    @model_validator(mode="after")
    def validate_canvas_id(self) -> Self:
        expected = content_id(
            "source_addressed_canvas",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"canvas_id", "repository_path"},
            ),
        )
        if self.canvas_id != expected:
            raise ValueError("Source-addressed canvas ID is not canonical")
        return self


class SourceAddressedPanelV2(FrozenModel):
    schema_version: Literal["triad-source-addressed-panel-v2"] = (
        "triad-source-addressed-panel-v2"
    )
    panel_id: NonEmptyId
    panel_scope: PanelScope
    option_id: NonEmptyId | None = None
    temporal_horizon: NonEmptyText | None = None
    semantic_summary: NonEmptyText
    source_case_id: NonEmptyId
    source_case_sha256: HashDigest
    supporting_evidence_ids: tuple[NonEmptyId, ...]
    derivation_status: DerivationStatus
    reality_claim_authority: bool
    official_attribution_state: OfficialAttributionState
    leader_decision_state: LeaderDecisionState
    canvas: SourceAddressedCanvasV2
    alias_of_panel_id: NonEmptyId | None = None
    imagined_route_rationale: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def validate_panel(self) -> Self:
        option_scope = self.panel_scope in {
            "option_action",
            "grounded_immediate_result",
            "emocio_imagined_completion",
        }
        if option_scope != (self.option_id is not None):
            raise ValueError("Option panel scope and option ID disagree")
        if option_scope != (self.temporal_horizon is not None):
            raise ValueError("Temporal horizon is allowed only on option panels")
        if self.panel_scope in {
            "desired_counterfactual",
            "broken_counterfactual",
        } and self.leader_decision_state != "not_applicable":
            raise ValueError("Desired/broken counterfactual leader state must be N/A")
        if self.panel_scope == "emocio_imagined_completion":
            if (
                self.derivation_status != "imagined_by_emocio"
                or self.reality_claim_authority
                or not self.imagined_route_rationale
            ):
                raise ValueError("Imagined completion lacks its epistemic boundary")
        elif self.derivation_status == "imagined_by_emocio":
            raise ValueError("Only completion panels may be imagined_by_emocio")
        if self.canvas.source_case_id != self.source_case_id:
            raise ValueError("Panel/canvas source case mismatch")
        if self.canvas.source_case_sha256 != self.source_case_sha256:
            raise ValueError("Panel/canvas source hash mismatch")
        if self.canvas.supporting_evidence_ids != self.supporting_evidence_ids:
            raise ValueError("Canvas cannot expand panel evidence")
        expected = content_id(
            "source_addressed_panel",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"panel_id"},
            ),
        )
        if self.panel_id != expected:
            raise ValueError("Source-addressed panel ID is not canonical")
        return self


class TypedUnresolvedRelationV2(FrozenModel):
    schema_version: Literal["triad-typed-unresolved-relation-v2"] = (
        "triad-typed-unresolved-relation-v2"
    )
    relation_id: NonEmptyId
    option_id: NonEmptyId
    relation_type: RelationType
    state: RelationState
    source_case_id: NonEmptyId
    source_case_sha256: HashDigest
    supporting_evidence_ids: tuple[NonEmptyId, ...]
    derivation_status: DerivationStatus
    reality_claim_authority: bool

    @model_validator(mode="after")
    def validate_relation_id(self) -> Self:
        expected = content_id(
            "typed_unresolved_relation",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"relation_id"},
            ),
        )
        if self.relation_id != expected:
            raise ValueError("Typed relation ID is not canonical")
        return self


class DualLayerOptionSequenceV2(FrozenModel):
    schema_version: Literal["triad-dual-layer-option-sequence-v2"] = (
        "triad-dual-layer-option-sequence-v2"
    )
    option_id: NonEmptyId
    action_panel: SourceAddressedPanelV2
    grounded_immediate_result_panel: SourceAddressedPanelV2
    emocio_imagined_completion_panel: SourceAddressedPanelV2 | None = None
    unresolved_relations: tuple[TypedUnresolvedRelationV2, ...]

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        panels = (
            self.action_panel,
            self.grounded_immediate_result_panel,
            self.emocio_imagined_completion_panel,
        )
        if any(panel is not None and panel.option_id != self.option_id for panel in panels):
            raise ValueError("Dual-layer sequence option ID mismatch")
        if self.action_panel.panel_scope != "option_action":
            raise ValueError("Sequence action has the wrong scope")
        if (
            self.grounded_immediate_result_panel.panel_scope
            != "grounded_immediate_result"
        ):
            raise ValueError("Sequence grounded result has the wrong scope")
        if (
            self.emocio_imagined_completion_panel is not None
            and self.emocio_imagined_completion_panel.panel_scope
            != "emocio_imagined_completion"
        ):
            raise ValueError("Sequence completion has the wrong scope")
        if any(item.option_id != self.option_id for item in self.unresolved_relations):
            raise ValueError("Sequence relation option ID mismatch")
        return self


class EmocioVisualMosaicV2(FrozenModel):
    schema_version: Literal["emocio-visual-mosaic-v2"] = "emocio-visual-mosaic-v2"
    mosaic_id: NonEmptyId
    case_id: NonEmptyId
    source_case_id: NonEmptyId
    source_case_sha256: HashDigest
    source_evidence_ids: tuple[NonEmptyId, ...]
    variant: Variant
    present_state: SourceAddressedPanelV2
    desired_counterfactual: SourceAddressedPanelV2
    broken_counterfactual: SourceAddressedPanelV2
    options: tuple[DualLayerOptionSequenceV2, ...]
    identity_anchor_ids: tuple[NonEmptyId, ...]
    root_audience_count: Literal[0, 6]
    model_calls: Literal[0] = 0
    character_replay: Literal[0] = 0
    native_decision_influence: Literal[0] = 0
    visual_valuation_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_mosaic(self) -> Self:
        if self.case_id != self.source_case_id:
            raise ValueError("Mosaic must preserve the opaque source case ID")
        if tuple(item.option_id for item in self.options) != OPTION_IDS:
            raise ValueError("Mosaic changed opaque option IDs or ordering")
        if self.root_audience_count != (6 if self.variant == "visible" else 0):
            raise ValueError("Mosaic root audience count mismatch")
        if self.present_state.panel_scope != "present_state":
            raise ValueError("Present-state panel scope mismatch")
        if self.desired_counterfactual.panel_scope != "desired_counterfactual":
            raise ValueError("Desired panel scope mismatch")
        if self.broken_counterfactual.panel_scope != "broken_counterfactual":
            raise ValueError("Broken panel scope mismatch")
        if any(
            panel.temporal_horizon is not None
            for panel in (
                self.present_state,
                self.desired_counterfactual,
                self.broken_counterfactual,
            )
        ):
            raise ValueError("State/counterfactual panels cannot use option horizon")
        if (
            self.desired_counterfactual.leader_decision_state != "not_applicable"
            or self.broken_counterfactual.leader_decision_state != "not_applicable"
        ):
            raise ValueError("Desired/broken leader decision must be not_applicable")
        allowed_evidence = set(self.source_evidence_ids)
        all_panels = (
            self.present_state,
            self.desired_counterfactual,
            self.broken_counterfactual,
            *(
                panel
                for option in self.options
                for panel in (
                    option.action_panel,
                    option.grounded_immediate_result_panel,
                    option.emocio_imagined_completion_panel,
                )
                if panel is not None
            ),
        )
        for panel in all_panels:
            if (
                panel.source_case_id != self.source_case_id
                or panel.source_case_sha256 != self.source_case_sha256
                or not set(panel.supporting_evidence_ids) <= allowed_evidence
            ):
                raise ValueError("Panel violates source-evidence closure")
        for option in self.options:
            result = option.grounded_immediate_result_panel
            if result.leader_decision_state not in {"not_triggered", "pending", "unknown"}:
                raise ValueError("Grounded result resolved an unknown leader decision")
            completion = option.emocio_imagined_completion_panel
            if completion is None:
                continue
            if completion.reality_claim_authority:
                raise ValueError("Imagined completion gained reality authority")
            if completion.panel_id in {
                option.action_panel.panel_id,
                result.panel_id,
                self.desired_counterfactual.panel_id,
            }:
                raise ValueError("Imagined completion aliases another semantic panel")
            if completion.canvas.content_sha256 in {
                option.action_panel.canvas.content_sha256,
                result.canvas.content_sha256,
                self.desired_counterfactual.canvas.content_sha256,
            }:
                raise ValueError("Imagined completion aliases another canvas")
        desired_hash = self.desired_counterfactual.canvas.content_sha256
        if any(
            desired_hash
            in {
                option.action_panel.canvas.content_sha256,
                option.grounded_immediate_result_panel.canvas.content_sha256,
            }
            for option in self.options
        ):
            raise ValueError("Desired canvas aliases action or grounded result")
        no_relations = {
            item.relation_type: item.state
            for item in self.options[0].unresolved_relations
        }
        public_relations = {
            item.relation_type: item.state
            for item in self.options[2].unresolved_relations
        }
        if no_relations == public_relations:
            raise ValueError("No-response relations copied public confrontation")
        expected = content_id(
            "emocio_visual_mosaic_v2",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"mosaic_id"},
            ),
        )
        if self.mosaic_id != expected:
            raise ValueError("V2 mosaic ID is not canonical")
        return self


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object_sha256(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _inventory(
    repository_root: Path,
    relative_root: Path,
    *,
    excluded_names: tuple[str, ...] = (),
    expected_count: int,
) -> tuple[Mapping[str, Any], ...]:
    root = repository_root / relative_root
    items = tuple(
        {
            "path": path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name not in excluded_names
    )
    if len(items) != expected_count:
        raise ValueError(
            f"Frozen inventory {relative_root} has {len(items)}, expected {expected_count}"
        )
    return items


def _validate_inventory(
    repository_root: Path,
    inventory: Sequence[Mapping[str, Any]],
) -> None:
    for item in inventory:
        path = repository_root / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != item["size_bytes"]
            or _file_sha256(path) != item["sha256"]
        ):
            raise ValueError(f"Frozen evidence changed: {item['path']}")


def source_case_projections(repository_root: Path) -> tuple[Mapping[str, Any], ...]:
    manifest = json.loads(
        (repository_root / O1_SCENE_MANIFEST_RELATIVE_PATH).read_text(
            encoding="utf-8"
        )
    )
    projections = []
    for variant in VARIANTS:
        case_id = f"public_credit_audience_{variant}"
        source_items = tuple(
            {
                "role": item["role"],
                "option_id": item["option_id"],
                "scene_spec": item["scene_spec"],
            }
            for item in manifest["items"]
            if item["case_id"] == case_id
        )
        if len(source_items) != 6:
            raise ValueError(f"Source case {case_id} does not have six scenes")
        projection = {
            "source_case_id": case_id,
            "source_items": source_items,
        }
        evidence_ids = tuple(
            sorted(
                {
                    evidence_id
                    for item in source_items
                    for evidence_id in item["scene_spec"]["grounded_evidence_ids"]
                }
            )
        )
        projections.append(
            {
                **projection,
                "source_case_sha256": _object_sha256(projection),
                "source_evidence_ids": evidence_ids,
            }
        )
    return tuple(projections)


def _source_support(
    source: Mapping[str, Any],
    *,
    role: str,
) -> tuple[str, ...]:
    item = next(item for item in source["source_items"] if item["role"] == role)
    return tuple(sorted(item["scene_spec"]["grounded_evidence_ids"]))


def _meeting_base(draw: ImageDraw.ImageDraw, *, timeline: bool) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(211, 218, 223))
    draw.rectangle(
        (20, 25, 492, 460),
        fill=(231, 234, 235),
        outline=(99, 110, 119),
        width=4,
    )
    if timeline:
        _draw_timeline(draw, (156, 55, 356, 170))
    else:
        _draw_project_diagram(draw, (156, 55, 356, 170))
    draw.polygon(
        ((92, 325), (420, 325), (468, 455), (44, 455)),
        fill=(142, 112, 82),
        outline=(70, 55, 42),
    )


def _record_marker(
    draw: ImageDraw.ImageDraw,
    *,
    state: Literal["confirmed_self", "confirmed_colleague", "pending"],
) -> None:
    draw.rounded_rectangle(
        (382, 55, 474, 132),
        radius=7,
        fill=(244, 245, 242),
        outline=(78, 89, 98),
        width=3,
    )
    token = {
        "confirmed_self": (35, 86, 170),
        "confirmed_colleague": (125, 25, 48),
        "pending": (145, 151, 158),
    }[state]
    draw.ellipse((397, 79, 421, 103), fill=token, outline=(55, 60, 65), width=2)
    draw.polygon(
        ((446, 77), (458, 91), (446, 105), (434, 91)),
        fill=(232, 218, 184) if state != "pending" else (220, 222, 220),
        outline=(55, 60, 65),
    )
    if state == "pending":
        draw.line((424, 91, 433, 91), fill=(135, 140, 145), width=2)
        draw.ellipse((427, 87, 431, 91), fill=(135, 140, 145))
    else:
        draw.line((423, 92, 438, 100), fill=(52, 132, 83), width=4)
        draw.line((438, 100, 461, 73), fill=(52, 132, 83), width=4)


def _meeting_canvas(*, variant: Variant, role: str) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), (220, 224, 226))
    draw = ImageDraw.Draw(image)
    timeline = role in {
        "desired",
        "public_action",
        "public_result",
        "public_completion",
        "private_completion",
    }
    _meeting_base(draw, timeline=timeline)
    scale_self = 1.05
    if role == "desired":
        positions = ((245, 215), (345, 250), (105, 245))
        focus = positions[0]
        _record_marker(draw, state="confirmed_self")
    elif role == "broken":
        positions = ((18, 270), (250, 212), (385, 245))
        focus = positions[1]
        scale_self = 0.72
        _record_marker(draw, state="confirmed_colleague")
    elif role == "public_action":
        positions = ((175, 245), (285, 220), (405, 245))
        focus = positions[0]
        _record_marker(draw, state="pending")
        draw.line((190, 250, 250, 145), fill=(42, 103, 173), width=5)
    elif role == "public_result":
        positions = ((250, 220), (370, 250), (105, 250))
        focus = positions[0]
        _record_marker(draw, state="pending")
    elif role == "public_completion":
        positions = ((245, 205), (385, 260), (95, 250))
        focus = positions[0]
        _record_marker(draw, state="confirmed_self")
        draw.ellipse((214, 174, 276, 236), outline=(35, 86, 170), width=3)
    elif role == "no_response_completion":
        positions = ((22, 280), (250, 205), (390, 245))
        focus = positions[1]
        scale_self = 0.78
    elif role == "private_completion":
        positions = ((105, 255), (310, 220), (420, 245))
        focus = positions[1]
        _record_marker(draw, state="pending")
    else:
        raise ValueError(f"Unknown M1R meeting role: {role}")
    self_head = _draw_person(
        draw,
        "visual_self_001",
        x=positions[0][0],
        y=positions[0][1],
        scale=scale_self,
    )
    colleague_head = _draw_person(
        draw,
        "visual_colleague_001",
        x=positions[1][0],
        y=positions[1][1],
        scale=1.05,
    )
    leader_head = _draw_person(
        draw,
        "visual_leader_001",
        x=positions[2][0],
        y=positions[2][1],
        scale=1.05,
    )
    if variant == "visible":
        if len(_draw_audience(draw, focus=focus)) != 6:
            raise AssertionError("Visible meeting must contain six audience members")
    draw.line((*leader_head, *focus), fill=(76, 91, 105), width=2)
    if focus == positions[0]:
        draw.line((*colleague_head, *self_head), fill=(76, 91, 105), width=2)
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def deterministic_canvas_bytes(*, variant: Variant, semantic_role: str) -> bytes:
    if semantic_role == "present":
        return m1_canvas_bytes(variant=variant, semantic_role="current_state")
    if semantic_role == "private_action":
        return m1_canvas_bytes(variant=variant, semantic_role="private_action")
    if semantic_role == "private_result":
        return m1_canvas_bytes(
            variant=variant,
            semantic_role="private_immediate_result",
        )
    return _meeting_canvas(variant=variant, role=semantic_role)


def _canvas(
    *,
    variant: Variant,
    semantic_role: str,
    source: Mapping[str, Any],
    evidence_ids: tuple[str, ...],
    derivation_status: DerivationStatus,
    reality_claim_authority: bool,
    repository_path: str,
    data: bytes,
) -> SourceAddressedCanvasV2:
    payload = {
        "schema_version": "triad-source-addressed-canvas-v2",
        "variant": variant,
        "semantic_role": semantic_role,
        "source_case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "supporting_evidence_ids": evidence_ids,
        "derivation_status": derivation_status,
        "reality_claim_authority": reality_claim_authority,
        "repository_path": repository_path,
        "content_sha256": _sha256_bytes(data),
        "generated_without_image_model": True,
        "contains_readable_text": False,
    }
    identity_payload = dict(payload)
    identity_payload.pop("repository_path")
    return SourceAddressedCanvasV2(
        canvas_id=content_id("source_addressed_canvas", identity_payload),
        **payload,
    )


def _panel(
    *,
    scope: PanelScope,
    option_id: str | None,
    horizon: str | None,
    summary: str,
    source: Mapping[str, Any],
    evidence_ids: tuple[str, ...],
    derivation_status: DerivationStatus,
    reality_claim_authority: bool,
    attribution: OfficialAttributionState,
    leader: LeaderDecisionState,
    canvas: SourceAddressedCanvasV2,
    alias_of: str | None = None,
    rationale: tuple[str, ...] = (),
) -> SourceAddressedPanelV2:
    payload = {
        "schema_version": "triad-source-addressed-panel-v2",
        "panel_scope": scope,
        "option_id": option_id,
        "temporal_horizon": horizon,
        "semantic_summary": summary,
        "source_case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "supporting_evidence_ids": evidence_ids,
        "derivation_status": derivation_status,
        "reality_claim_authority": reality_claim_authority,
        "official_attribution_state": attribution,
        "leader_decision_state": leader,
        "canvas": canvas,
        "alias_of_panel_id": alias_of,
        "imagined_route_rationale": rationale,
    }
    return SourceAddressedPanelV2(
        panel_id=content_id("source_addressed_panel", payload),
        **payload,
    )


def _relation(
    *,
    option_id: str,
    relation_type: RelationType,
    state: RelationState,
    source: Mapping[str, Any],
    evidence_ids: tuple[str, ...],
) -> TypedUnresolvedRelationV2:
    payload = {
        "schema_version": "triad-typed-unresolved-relation-v2",
        "option_id": option_id,
        "relation_type": relation_type,
        "state": state,
        "source_case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "supporting_evidence_ids": evidence_ids,
        "derivation_status": "source_synthesis",
        "reality_claim_authority": False,
    }
    return TypedUnresolvedRelationV2(
        relation_id=content_id("typed_unresolved_relation", payload),
        **payload,
    )


RELATION_STATES: Final = {
    "credit_no_response": (
        ("leader_decision", "not_triggered"),
        ("official_correction", "not_triggered"),
        ("public_recognition", "unchanged"),
        ("colleague_response", "not_triggered"),
    ),
    "credit_private_evidence": (
        ("leader_decision", "pending"),
        ("official_correction", "pending"),
        ("public_recognition", "unchanged_at_immediate_horizon"),
        ("colleague_response", "not_observed"),
    ),
    "credit_public_confront": (
        ("leader_decision", "pending"),
        ("official_correction", "pending"),
        ("public_attention", "shifted_to_self"),
        ("audience_support", "unknown"),
        ("colleague_response", "unknown_active"),
    ),
}


def _build_mosaic(
    *,
    variant: Variant,
    source: Mapping[str, Any],
    canvases: Mapping[str, SourceAddressedCanvasV2],
) -> EmocioVisualMosaicV2:
    evidence = {
        "current": _source_support(source, role="current"),
        "desired": _source_support(source, role="desired"),
        "broken": _source_support(source, role="broken"),
        **{
            option_id: _source_support(
                source,
                role=OPTION_ROLE_BY_ID[option_id],
            )
            for option_id in OPTION_IDS
        },
    }
    present = _panel(
        scope="present_state",
        option_id=None,
        horizon=None,
        summary=(
            "Present meeting state: the colleague holds attention while official "
            "attribution remains unresolved."
        ),
        source=source,
        evidence_ids=evidence["current"],
        derivation_status="source_synthesis",
        reality_claim_authority=True,
        attribution="current_unresolved",
        leader="unknown",
        canvas=canvases["present"],
    )
    desired = _panel(
        scope="desired_counterfactual",
        option_id=None,
        horizon=None,
        summary=(
            "Desired counterfactual: an explicit official-record marker assigns "
            "authorship to self with leader confirmation."
        ),
        source=source,
        evidence_ids=evidence["desired"],
        derivation_status="source_synthesis",
        reality_claim_authority=False,
        attribution="desired_self_recognized",
        leader="not_applicable",
        canvas=canvases["desired"],
    )
    broken = _panel(
        scope="broken_counterfactual",
        option_id=None,
        horizon=None,
        summary=(
            "Broken counterfactual: the colleague remains recognized while self is "
            "smaller, farther away, and partly outside the frame."
        ),
        source=source,
        evidence_ids=evidence["broken"],
        derivation_status="source_synthesis",
        reality_claim_authority=False,
        attribution="broken_colleague_recognized",
        leader="not_applicable",
        canvas=canvases["broken"],
    )
    sequences = []
    for option_id in OPTION_IDS:
        option_evidence = evidence[option_id]
        if option_id == "credit_no_response":
            alias_evidence = present.supporting_evidence_ids
            action = _panel(
                scope="option_action",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary="No response holds the present scene unchanged.",
                source=source,
                evidence_ids=alias_evidence,
                derivation_status="source_synthesis",
                reality_claim_authority=False,
                attribution="unchanged",
                leader="not_triggered",
                canvas=present.canvas,
                alias_of=present.panel_id,
            )
            result = _panel(
                scope="grounded_immediate_result",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary="The immediate grounded result remains the present scene.",
                source=source,
                evidence_ids=alias_evidence,
                derivation_status="source_synthesis",
                reality_claim_authority=False,
                attribution="unchanged",
                leader="not_triggered",
                canvas=present.canvas,
                alias_of=present.panel_id,
            )
            completion_summary = (
                "Candidate Emocio projection: the colleague remains the sole visible "
                "author and self becomes more excluded."
            )
            completion_canvas = canvases["no_response_completion"]
            rationale = (
                "self-centered desired image is denied",
                "competition remains visually lost to the colleague",
                "the obstacle remains in the center",
            )
            completion_attribution = "unchanged"
            completion_leader = "not_triggered"
        elif option_id == "credit_private_evidence":
            action = _panel(
                scope="option_action",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary="Self and the leader privately review the evidence.",
                source=source,
                evidence_ids=option_evidence,
                derivation_status="source_synthesis",
                reality_claim_authority=False,
                attribution="unchanged",
                leader="pending",
                canvas=canvases["private_action"],
            )
            result = _panel(
                scope="grounded_immediate_result",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary=(
                    "The leader considers the evidence; public attribution remains "
                    "unchanged at the immediate horizon."
                ),
                source=source,
                evidence_ids=option_evidence,
                derivation_status="source_synthesis",
                reality_claim_authority=False,
                attribution="unchanged",
                leader="pending",
                canvas=canvases["private_result"],
            )
            completion_summary = (
                "Candidate Emocio projection: the leader may correct the record "
                "later, while public recognition remains weak or delayed."
            )
            completion_canvas = canvases["private_completion"]
            rationale = (
                "attention is delayed rather than immediately public",
                "obstacle removal is imagined but remains incomplete",
                "gullibility permits an optimistic later correction image",
            )
            completion_attribution = "pending"
            completion_leader = "unknown"
        else:
            action = _panel(
                scope="option_action",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary="Self steps forward and presents evidence publicly.",
                source=source,
                evidence_ids=option_evidence,
                derivation_status="source_synthesis",
                reality_claim_authority=False,
                attribution="pending",
                leader="pending",
                canvas=canvases["public_action"],
            )
            result = _panel(
                scope="grounded_immediate_result",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary=(
                    "Attention shifts to self, but the neutral official-record marker "
                    "and leader decision remain pending."
                ),
                source=source,
                evidence_ids=option_evidence,
                derivation_status="source_synthesis",
                reality_claim_authority=False,
                attribution="pending",
                leader="pending",
                canvas=canvases["public_result"],
            )
            completion_summary = (
                "Candidate Emocio projection: self imagines public recognition, "
                "audience attention staying on self, and the colleague secondary."
            )
            completion_canvas = canvases["public_completion"]
            rationale = (
                "self-centered desired image places self at the center",
                "attention and competition favor visible victory",
                "immediate desired-image fulfilment imagines obstacle removal",
            )
            completion_attribution = "desired_self_recognized"
            completion_leader = "unknown"
        completion = _panel(
            scope="emocio_imagined_completion",
            option_id=option_id,
            horizon=IMAGINED_HORIZON,
            summary=completion_summary,
            source=source,
            evidence_ids=option_evidence,
            derivation_status="imagined_by_emocio",
            reality_claim_authority=False,
            attribution=completion_attribution,
            leader=completion_leader,
            canvas=completion_canvas,
            rationale=rationale,
        )
        relations = tuple(
            _relation(
                option_id=option_id,
                relation_type=relation_type,
                state=state,
                source=source,
                evidence_ids=option_evidence,
            )
            for relation_type, state in RELATION_STATES[option_id]
        )
        sequences.append(
            DualLayerOptionSequenceV2(
                option_id=option_id,
                action_panel=action,
                grounded_immediate_result_panel=result,
                emocio_imagined_completion_panel=completion,
                unresolved_relations=relations,
            )
        )
    payload = {
        "schema_version": "emocio-visual-mosaic-v2",
        "case_id": source["source_case_id"],
        "source_case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "source_evidence_ids": source["source_evidence_ids"],
        "variant": variant,
        "present_state": present,
        "desired_counterfactual": desired,
        "broken_counterfactual": broken,
        "options": tuple(sequences),
        "identity_anchor_ids": tuple(item.subject_id for item in identity_anchors()),
        "root_audience_count": 6 if variant == "visible" else 0,
        "model_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "visual_valuation_authority": False,
    }
    return EmocioVisualMosaicV2(
        mosaic_id=content_id("emocio_visual_mosaic_v2", payload),
        **payload,
    )


def _display_panels(
    mosaic: EmocioVisualMosaicV2,
) -> tuple[tuple[str, SourceAddressedPanelV2], ...]:
    values = [
        ("current", mosaic.present_state),
        ("desired", mosaic.desired_counterfactual),
        ("broken", mosaic.broken_counterfactual),
    ]
    short = {
        "credit_no_response": "no-response",
        "credit_private_evidence": "private",
        "credit_public_confront": "public",
    }
    for option in mosaic.options:
        name = short[option.option_id]
        values.extend(
            (
                (f"{name}/action", option.action_panel),
                (f"{name}/grounded", option.grounded_immediate_result_panel),
                (f"{name}/imagined", option.emocio_imagined_completion_panel),
            )
        )
    return tuple(values)


def _storyboard_graph(
    *,
    mosaic: EmocioVisualMosaicV2,
    repository_root: Path,
    destination: Path,
) -> None:
    canvas = Image.new("RGB", (1450, 1530), "white")
    draw = ImageDraw.Draw(canvas)

    def paste_panel(
        panel: SourceAddressedPanelV2,
        *,
        x: int,
        y: int,
        label: str,
    ) -> None:
        with Image.open(repository_root / panel.canvas.repository_path) as source:
            rendered = source.convert("RGB").resize((230, 230))
        canvas.paste(rendered, (x, y))
        draw.rectangle((x, y, x + 230, y + 230), outline=(45, 50, 55), width=2)
        draw.text((x, y - 20), label, fill="black")

    draw.text((20, 12), f"{mosaic.case_id} — EmocioVisualMosaicV2", fill="black")
    paste_panel(mosaic.present_state, x=30, y=65, label="PRESENT STATE")
    paste_panel(
        mosaic.desired_counterfactual,
        x=330,
        y=65,
        label="DESIRED COUNTERFACTUAL",
    )
    paste_panel(
        mosaic.broken_counterfactual,
        x=630,
        y=65,
        label="BROKEN COUNTERFACTUAL",
    )
    draw.line((260, 180, 325, 180), fill=(70, 80, 90), width=3)
    draw.line((560, 180, 625, 180), fill=(70, 80, 90), width=3)
    draw.text(
        (930, 75),
        "Reference states only.\nNo option horizon.\nDesired/broken leader decision:\nnot_applicable.",
        fill="black",
        spacing=5,
    )
    y_positions = (395, 755, 1115)
    option_labels = ("NO RESPONSE", "PRIVATE EVIDENCE", "PUBLIC CONFRONTATION")
    for option, label, y in zip(mosaic.options, option_labels, y_positions):
        action = option.action_panel
        result = option.grounded_immediate_result_panel
        completion = option.emocio_imagined_completion_panel
        paste_panel(action, x=30, y=y, label=f"{label}: ACTION")
        paste_panel(result, x=330, y=y, label="GROUNDED IMMEDIATE RESULT")
        paste_panel(completion, x=630, y=y, label="EMOCIO-IMAGINED COMPLETION")
        draw.line((260, y + 115, 325, y + 115), fill=(42, 103, 173), width=4)
        draw.polygon(
            ((325, y + 115), (313, y + 108), (313, y + 122)),
            fill=(42, 103, 173),
        )
        draw.line((560, y + 115, 625, y + 115), fill=(125, 25, 48), width=4)
        draw.polygon(
            ((625, y + 115), (613, y + 108), (613, y + 122)),
            fill=(125, 25, 48),
        )
        relation_lines = [
            f"{item.relation_type}: {item.state}"
            for item in option.unresolved_relations
        ]
        relation_text = "UNRESOLVED RELATIONS\n" + "\n".join(relation_lines)
        draw.rounded_rectangle(
            (920, y, 1425, y + 230),
            radius=8,
            fill=(244, 246, 247),
            outline=(100, 108, 115),
            width=2,
        )
        draw.multiline_text((940, y + 16), relation_text, fill="black", spacing=6)
    draw.text(
        (30, 1495),
        "Blue arrows: grounded sequence. Burgundy arrows: explicitly imagined "
        "completion with reality_claim_authority=false.",
        fill="black",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Storyboard graph exists: {destination}")
    canvas.save(destination, format="PNG", optimize=True)


def _report(
    *,
    mosaics: Sequence[EmocioVisualMosaicV2],
    sheets: Mapping[str, Mapping[str, Any]],
    human_review_sha256: str,
) -> str:
    lines = [
        "# TRIAD-VIS-M1R — source-addressed dual-layer Emocio mosaic",
        "",
        "Status: **model-free candidate awaiting human visual review**.",
        "",
        "M1 remains frozen. M1R separates grounded immediate option results from "
        "Emocio-imagined completions and gives every panel and typed unresolved "
        "relation an explicit source address and epistemic status.",
        "",
        f"- Human-supplied M1 review SHA-256: `{human_review_sha256}`",
        "- Model calls / image calls: `0 / 0`",
        "- Character replay / native-decision influence: `0 / 0`",
        "- Visual valuation / Racio vision: `0 / 0`",
        "",
        "Epistemic boundaries:",
        "",
        "- Desired and broken are counterfactual reference states without an option horizon.",
        "- Grounded immediate results never resolve the pending leader decision.",
        "- Imagined completions have `derivation_status = imagined_by_emocio` and "
        "`reality_claim_authority = false`.",
        "- The desired official-record marker is confirmed; the public grounded "
        "result uses a visibly neutral/pending record marker.",
        "",
    ]
    for mosaic in mosaics:
        record = sheets[mosaic.variant]
        lines.extend(
            [
                f"## {mosaic.case_id}",
                "",
                f"- Source case SHA-256: `{mosaic.source_case_sha256}`",
                f"- Root audience: `{mosaic.root_audience_count}` additional persons",
                f"- Mosaic ID: `{mosaic.mosaic_id}`",
                "",
                f"![{mosaic.variant} contact sheet]({record['contact_path']})",
                "",
                f"![{mosaic.variant} storyboard graph]({record['graph_path']})",
                "",
                "| Option | Grounded immediate state | Typed unresolved relations | Imagined completion authority |",
                "|---|---|---|---|",
            ]
        )
        for option in mosaic.options:
            relations = "; ".join(
                f"{item.relation_type}={item.state}"
                for item in option.unresolved_relations
            )
            result = option.grounded_immediate_result_panel
            completion = option.emocio_imagined_completion_panel
            lines.append(
                f"| `{option.option_id}` | attribution=`{result.official_attribution_state}`; "
                f"leader=`{result.leader_decision_state}` | {relations} | "
                f"`{completion.derivation_status}`; "
                f"`reality_claim_authority={str(completion.reality_claim_authority).lower()}` |"
            )
        lines.extend(
            [
                "",
                "Human review (intentionally blank):",
                "",
                "- Source addressing is understandable:",
                "- Present state:",
                "- Desired official-record marker:",
                "- Broken state without gray occlusion:",
                "- No-response sequence:",
                "- Private grounded sequence:",
                "- Public grounded sequence:",
                "- Public attention-only marker remains distinct from recognition:",
                "- No-response imagined completion:",
                "- Private imagined completion:",
                "- Public imagined completion:",
                "- Imagined completions remain visibly epistemically separate:",
                "- Typed unresolved relations are correct:",
                "- Stable identities:",
                "- Audience counts:",
                "- Unsupported visual inference:",
                "- Ready for FLUX rendering:",
                "- Ready for Racio vision:",
                "",
            ]
        )
    return "\n".join(lines)


def build(repository_root: Path) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    if _git(repository_root, "rev-parse", "HEAD") != EXPECTED_BASE_COMMIT:
        raise ValueError("TRIAD-VIS-M1R must start from approved M1 HEAD")
    output = repository_root / OUTPUT_RELATIVE_PATH
    if output.exists():
        raise FileExistsError("TRIAD-VIS-M1R output root already exists")
    review_path = repository_root / M1_REVIEW_RELATIVE_PATH
    if not review_path.is_file():
        raise ValueError("Human-supplied M1 review is missing")
    review_text = review_path.read_text(encoding="utf-8")
    if (
        "`review_source`: `human_supplied`" not in review_text
        or "`racio_vision_approval`: `false`" not in review_text
    ):
        raise ValueError("M1 review lacks human-source metadata")
    human_review_sha256 = _file_sha256(review_path)
    m1_inventory = _inventory(
        repository_root,
        M1_RELATIVE_PATH,
        excluded_names=("human_visual_review.md",),
        expected_count=20,
    )
    o2_inventory = _inventory(
        repository_root,
        O2_RELATIVE_PATH,
        expected_count=53,
    )
    sources = source_case_projections(repository_root)
    output.mkdir(parents=True)
    mosaics = []
    sheet_records: dict[str, Mapping[str, Any]] = {}
    canvas_roles = (
        "present",
        "desired",
        "broken",
        "private_action",
        "private_result",
        "public_action",
        "public_result",
        "no_response_completion",
        "private_completion",
        "public_completion",
    )
    source_role = {
        "present": "current",
        "desired": "desired",
        "broken": "broken",
        "private_action": "option_1",
        "private_result": "option_1",
        "public_action": "option_2",
        "public_result": "option_2",
        "no_response_completion": "option_0",
        "private_completion": "option_1",
        "public_completion": "option_2",
    }
    for source in sources:
        variant = source["source_case_id"].rsplit("_", 1)[-1]
        canvases: dict[str, SourceAddressedCanvasV2] = {}
        for role in canvas_roles:
            data = deterministic_canvas_bytes(variant=variant, semantic_role=role)
            relative = OUTPUT_RELATIVE_PATH / "canvases" / variant / f"{role}.png"
            _write_new(repository_root / relative, data)
            imagined = role.endswith("_completion")
            canvases[role] = _canvas(
                variant=variant,
                semantic_role=role,
                source=source,
                evidence_ids=_source_support(source, role=source_role[role]),
                derivation_status=(
                    "imagined_by_emocio" if imagined else "implementation_neutral"
                ),
                reality_claim_authority=(role == "present"),
                repository_path=relative.as_posix(),
                data=data,
            )
        mosaic = _build_mosaic(variant=variant, source=source, canvases=canvases)
        mosaics.append(mosaic)
        display = _display_panels(mosaic)
        contact_path = output / "sheets" / f"{variant}_contact.png"
        _sheet(
            tuple(
                (label, repository_root / panel.canvas.repository_path)
                for label, panel in display
            ),
            contact_path,
            columns=4,
        )
        graph_path = output / "sheets" / f"{variant}_storyboard_graph.png"
        _storyboard_graph(
            mosaic=mosaic,
            repository_root=repository_root,
            destination=graph_path,
        )
        sheet_records[variant] = {
            "contact_path": contact_path.relative_to(output).as_posix(),
            "contact_sha256": _file_sha256(contact_path),
            "graph_path": graph_path.relative_to(output).as_posix(),
            "graph_sha256": _file_sha256(graph_path),
        }
    unresolved = {
        "schema_version": "triad-vis-m1r-unresolved-relations-v2",
        "items": tuple(
            relation
            for mosaic in mosaics
            for option in mosaic.options
            for relation in option.unresolved_relations
        ),
    }
    source_manifest = {
        "schema_version": "triad-vis-m1r-source-case-manifest-v1",
        "source_cases": sources,
    }
    manifest = {
        "schema_version": "triad-vis-m1r-manifest-v1",
        "phase": "TRIAD-VIS-M1R",
        "base_commit": EXPECTED_BASE_COMMIT,
        "contract": "EmocioVisualMosaicV2",
        "human_review": {
            "path": M1_REVIEW_RELATIVE_PATH.as_posix(),
            "sha256": human_review_sha256,
            "review_source": "human_supplied",
            "visual_valuation_authority": False,
            "racio_vision_approval": False,
        },
        "m1_frozen_inventory": m1_inventory,
        "m1_frozen_inventory_sha256": _object_sha256(m1_inventory),
        "o2_frozen_inventory": o2_inventory,
        "o2_frozen_inventory_sha256": _object_sha256(o2_inventory),
        "source_case_manifest_sha256": _object_sha256(source_manifest),
        "mosaics": mosaics,
        "sheets": sheet_records,
        "unique_canvas_files": 20,
        "display_panels": 24,
        "model_calls": 0,
        "image_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "private_thinking_persisted": False,
    }
    _write_new(
        output / "source_case_manifest.json",
        canonical_json_bytes(source_manifest),
    )
    _write_new(
        output / "unresolved_relations.json",
        canonical_json_bytes(unresolved),
    )
    _write_new(output / "mosaic_manifest.json", canonical_json_bytes(manifest))
    _write_new(
        output / "report.md",
        _report(
            mosaics=mosaics,
            sheets=sheet_records,
            human_review_sha256=human_review_sha256,
        ).encode("utf-8"),
    )
    return cold_verify(repository_root)


def _contains_absolute_path(text: str) -> bool:
    return bool(re.search(r"(?:[A-Za-z]:[\\/]|/home/|/Users/|\\\\Users\\\\)", text))


def cold_verify(repository_root: Path) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    output = repository_root / OUTPUT_RELATIVE_PATH
    manifest = json.loads(
        (output / "mosaic_manifest.json").read_text(encoding="utf-8")
    )
    mosaics = tuple(
        EmocioVisualMosaicV2.model_validate_json(
            json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            strict=True,
        )
        for item in manifest["mosaics"]
    )
    if len(mosaics) != 2:
        raise ValueError("M1R must contain two mosaics")
    _validate_inventory(repository_root, manifest["m1_frozen_inventory"])
    _validate_inventory(repository_root, manifest["o2_frozen_inventory"])
    review_path = repository_root / manifest["human_review"]["path"]
    if _file_sha256(review_path) != manifest["human_review"]["sha256"]:
        raise ValueError("M1 human review hash changed")
    source_manifest = json.loads(
        (output / "source_case_manifest.json").read_text(encoding="utf-8")
    )
    if _object_sha256(source_manifest) != manifest["source_case_manifest_sha256"]:
        raise ValueError("M1R source-case manifest hash changed")
    canvas_paths = {
        panel.canvas.repository_path
        for mosaic in mosaics
        for _, panel in _display_panels(mosaic)
    }
    if len(canvas_paths) != 20:
        raise ValueError("M1R must contain twenty unique canvases")
    for mosaic in mosaics:
        allowed = set(mosaic.source_evidence_ids)
        for _, panel in _display_panels(mosaic):
            if not set(panel.supporting_evidence_ids) <= allowed:
                raise ValueError("Panel evidence escaped source closure")
            path = repository_root / panel.canvas.repository_path
            if _file_sha256(path) != panel.canvas.content_sha256:
                raise ValueError("M1R canvas hash mismatch")
        desired_hash = mosaic.desired_counterfactual.canvas.content_sha256
        public_result_hash = mosaic.options[2].grounded_immediate_result_panel.canvas.content_sha256
        if desired_hash == public_result_hash:
            raise ValueError("Official recognition marker equals attention-only marker")
    for record in manifest["sheets"].values():
        contact = output / record["contact_path"]
        graph = output / record["graph_path"]
        if (
            _file_sha256(contact) != record["contact_sha256"]
            or _file_sha256(graph) != record["graph_sha256"]
        ):
            raise ValueError("M1R sheet hash mismatch")
    serialized = canonical_json_bytes(manifest).decode("utf-8")
    forbidden = (
        "character_profile",
        "governance_tier",
        "expected_option",
        "leading_mind",
        "gold_route",
    )
    if any(term in serialized for term in forbidden):
        raise ValueError("M1R contains character/governance/answer leakage")
    absolute_hits = []
    for path in output.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".md"}:
            if _contains_absolute_path(path.read_text(encoding="utf-8")):
                absolute_hits.append(path.relative_to(repository_root).as_posix())
    if absolute_hits:
        raise ValueError(f"M1R contains absolute paths: {absolute_hits}")
    if any(
        manifest[key] != 0
        for key in (
            "model_calls",
            "image_calls",
            "character_replay",
            "native_decision_influence",
            "racio_vision",
            "visual_valuation",
        )
    ):
        raise ValueError("M1R authority/call accounting is non-zero")
    report = (output / "report.md").read_text(encoding="utf-8")
    if report.count("Human review (intentionally blank):") != 2:
        raise ValueError("M1R human-review fields are not preserved")
    return {
        "status": "passed",
        "mosaic_count": 2,
        "display_panels": 24,
        "unique_canvas_files": 20,
        "storyboard_graphs": 2,
        "contact_sheets": 2,
        "m1_files_verified": len(manifest["m1_frozen_inventory"]),
        "o2_files_verified": len(manifest["o2_frozen_inventory"]),
        "source_evidence_closure": "passed",
        "model_calls": 0,
        "image_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "absolute_paths_found": 0,
        "private_thinking_persisted": False,
    }


__all__ = [
    "EXPECTED_BASE_COMMIT",
    "EmocioVisualMosaicV2",
    "IMAGINED_HORIZON",
    "IMMEDIATE_HORIZON",
    "OPTION_IDS",
    "OUTPUT_RELATIVE_PATH",
    "RELATION_STATES",
    "SourceAddressedPanelV2",
    "TypedUnresolvedRelationV2",
    "build",
    "cold_verify",
    "deterministic_canvas_bytes",
    "source_case_projections",
]
