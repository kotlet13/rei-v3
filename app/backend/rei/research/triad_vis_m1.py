"""TRIAD-VIS-M1 research-only Emocio visual mosaic contract.

The module creates deterministic semantic canvases and a temporally bounded
visual-mosaic projection. It performs no model calls and has no runtime,
valuation, native-conclusion, character, governance, or decision authority.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, Self

from PIL import Image, ImageDraw
from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from .triad_vis_o1 import HEIGHT, WIDTH, _file_sha256, _git, _sheet, _write_new
from .triad_vis_o2 import (
    _draw_audience,
    _draw_person,
    _draw_project_diagram,
    _draw_timeline,
    identity_anchors,
)


EXPECTED_BASE_COMMIT: Final = "0d5997316f1671d69dfd78cf5a848298d0577c05"
O2_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o2-2026-07-24"
)
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-m1-2026-07-24"
)
TEMPORAL_HORIZON: Final = (
    "Immediately after the action, before any unknown leader decision or "
    "later organizational response."
)
VARIANTS: Final = ("visible", "absent")
OPTIONS: Final = (
    "credit_no_response",
    "credit_private_evidence",
    "credit_public_confront",
)
DISPLAY_ORDER: Final = (
    "current_state",
    "desired_target_state",
    "broken_failure_state",
    "credit_no_response/action_panel",
    "credit_no_response/immediate_result_panel",
    "credit_private_evidence/action_panel",
    "credit_private_evidence/immediate_result_panel",
    "credit_public_confront/action_panel",
    "credit_public_confront/immediate_result_panel",
)


PanelKind = Literal[
    "current_state",
    "desired_target_state",
    "broken_failure_state",
    "action_panel",
    "immediate_result_panel",
]
Variant = Literal["visible", "absent"]
AttentionTarget = Literal[
    "colleague",
    "self",
    "evidence",
    "leader_considering_evidence",
]
RecognitionState = Literal[
    "unresolved",
    "desired_official_recognition_of_self",
    "broken_exclusive_recognition_of_colleague",
]
LeaderDecisionState = Literal["unknown"]


class MosaicCanvasV1(FrozenModel):
    schema_version: Literal["triad-mosaic-canvas-v1"] = "triad-mosaic-canvas-v1"
    canvas_id: NonEmptyId
    variant: Variant
    semantic_role: NonEmptyId
    repository_path: NonEmptyText
    content_sha256: HashDigest
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    generated_without_image_model: Literal[True] = True
    contains_readable_text: Literal[False] = False
    semantic_authority: Literal["research_projection_only"] = (
        "research_projection_only"
    )

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        expected = content_id(
            "mosaic_canvas",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"canvas_id", "repository_path"},
            ),
        )
        if self.canvas_id != expected:
            raise ValueError("Mosaic canvas ID differs from canonical content")
        return self


class MosaicPanelV1(FrozenModel):
    schema_version: Literal["triad-mosaic-panel-v1"] = "triad-mosaic-panel-v1"
    panel_id: NonEmptyId
    panel_kind: PanelKind
    option_id: NonEmptyId | None = None
    temporal_horizon: NonEmptyText
    semantic_summary: NonEmptyText
    attention_target: AttentionTarget
    official_recognition_state: RecognitionState
    leader_decision_state: LeaderDecisionState
    public_attribution_changed: bool
    canvas: MosaicCanvasV1
    alias_of_panel_id: NonEmptyId | None = None

    @model_validator(mode="after")
    def validate_panel(self) -> Self:
        if self.temporal_horizon != TEMPORAL_HORIZON:
            raise ValueError("Mosaic panel temporal horizon is not canonical")
        state_kinds = {
            "current_state",
            "desired_target_state",
            "broken_failure_state",
        }
        if (self.panel_kind in state_kinds) != (self.option_id is None):
            raise ValueError("State and option panel identity mismatch")
        expected = content_id(
            "mosaic_panel",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"panel_id"},
            ),
        )
        if self.panel_id != expected:
            raise ValueError("Mosaic panel ID differs from canonical content")
        return self


class OptionVisualSequenceV1(FrozenModel):
    schema_version: Literal["triad-option-visual-sequence-v1"] = (
        "triad-option-visual-sequence-v1"
    )
    option_id: NonEmptyId
    action_panel: MosaicPanelV1
    immediate_result_panel: MosaicPanelV1
    unresolved_relations: tuple[NonEmptyText, ...]

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        if self.action_panel.option_id != self.option_id:
            raise ValueError("Action panel option ID mismatch")
        if self.immediate_result_panel.option_id != self.option_id:
            raise ValueError("Immediate-result panel option ID mismatch")
        if self.action_panel.panel_kind != "action_panel":
            raise ValueError("Option action panel has the wrong panel kind")
        if self.immediate_result_panel.panel_kind != "immediate_result_panel":
            raise ValueError("Option result panel has the wrong panel kind")
        if not self.unresolved_relations:
            raise ValueError("Every option must preserve unresolved relations")
        return self


class EmocioVisualMosaicV1(FrozenModel):
    """Canonical research projection of an Emocio thought as a visual mosaic."""

    schema_version: Literal["emocio-visual-mosaic-v1"] = "emocio-visual-mosaic-v1"
    mosaic_id: NonEmptyId
    case_id: NonEmptyId
    variant: Variant
    temporal_horizon: NonEmptyText
    current_state: MosaicPanelV1
    desired_target_state: MosaicPanelV1
    broken_failure_state: MosaicPanelV1
    options: tuple[OptionVisualSequenceV1, ...]
    identity_anchor_ids: tuple[NonEmptyId, ...]
    root_audience_count: Literal[0, 6]
    model_calls: Literal[0] = 0
    native_decision_influence: Literal[0] = 0
    visual_valuation_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_mosaic(self) -> Self:
        if self.temporal_horizon != TEMPORAL_HORIZON:
            raise ValueError("Mosaic temporal horizon is not canonical")
        if self.current_state.panel_kind != "current_state":
            raise ValueError("Current state has the wrong panel kind")
        if self.desired_target_state.panel_kind != "desired_target_state":
            raise ValueError("Desired state has the wrong panel kind")
        if self.broken_failure_state.panel_kind != "broken_failure_state":
            raise ValueError("Broken state has the wrong panel kind")
        if tuple(item.option_id for item in self.options) != OPTIONS:
            raise ValueError("Mosaic options differ from canonical public scope")
        if self.root_audience_count != (6 if self.variant == "visible" else 0):
            raise ValueError("Root audience count differs from variant contract")
        if self.desired_target_state.panel_id in {
            panel.panel_id
            for option in self.options
            for panel in (option.action_panel, option.immediate_result_panel)
        }:
            raise ValueError("Desired state cannot be an option action or result")
        if self.desired_target_state.canvas.content_sha256 in {
            panel.canvas.content_sha256
            for option in self.options
            for panel in (option.action_panel, option.immediate_result_panel)
        }:
            raise ValueError(
                "Desired-state canvas cannot be an option action or result canvas"
            )
        for option in self.options:
            for panel in (option.action_panel, option.immediate_result_panel):
                if (
                    panel.official_recognition_state != "unresolved"
                    or panel.leader_decision_state != "unknown"
                    or panel.public_attribution_changed
                ):
                    raise ValueError(
                        "Option panels cannot resolve leader decision or recognition"
                    )
        current = self.current_state
        no_response = self.options[0]
        for panel in (
            no_response.action_panel,
            no_response.immediate_result_panel,
        ):
            if (
                panel.alias_of_panel_id != current.panel_id
                or panel.canvas.content_sha256 != current.canvas.content_sha256
                or panel.canvas.repository_path != current.canvas.repository_path
            ):
                raise ValueError("No-response panels must exactly alias current")
        for option in self.options[1:]:
            for panel in (option.action_panel, option.immediate_result_panel):
                if panel.alias_of_panel_id is not None:
                    raise ValueError("Only no-response panels may alias current")
        public_result = self.options[2].immediate_result_panel
        if (
            public_result.attention_target != "self"
            or public_result.official_recognition_state != "unresolved"
        ):
            raise ValueError(
                "Public attention shift must remain distinct from recognition"
            )
        private_result = self.options[1].immediate_result_panel
        if (
            private_result.attention_target != "leader_considering_evidence"
            or private_result.public_attribution_changed
        ):
            raise ValueError(
                "Private evidence result must preserve public attribution"
            )
        expected = content_id(
            "emocio_visual_mosaic",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"mosaic_id"},
            ),
        )
        if self.mosaic_id != expected:
            raise ValueError("Mosaic ID differs from canonical content")
        return self


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object_sha256(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _o2_inventory(repository_root: Path) -> tuple[Mapping[str, Any], ...]:
    root = repository_root / O2_RELATIVE_PATH
    items = tuple(
        {
            "path": path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )
    if len(items) != 53:
        raise ValueError("Frozen O2 inventory does not contain exactly 53 files")
    return items


def _validate_o2_inventory(
    repository_root: Path,
    inventory: Sequence[Mapping[str, Any]],
) -> None:
    if len(inventory) != 53:
        raise ValueError("Stored O2 inventory is incomplete")
    for item in inventory:
        path = repository_root / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != item["size_bytes"]
            or _file_sha256(path) != item["sha256"]
        ):
            raise ValueError(f"Frozen O2 evidence changed: {item['path']}")


def _meeting_background(draw: ImageDraw.ImageDraw, *, timeline: bool) -> None:
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


def _meeting_canvas(
    *,
    variant: Variant,
    role: str,
) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), (220, 224, 226))
    draw = ImageDraw.Draw(image)
    timeline = role in {
        "desired_target_state",
        "public_action",
        "public_immediate_result",
    }
    _meeting_background(draw, timeline=timeline)
    if role == "current_state":
        self_pos, colleague_pos, leader_pos = (75, 250), (256, 220), (405, 240)
        focus = colleague_pos
        hidden_self = False
    elif role == "desired_target_state":
        self_pos, colleague_pos, leader_pos = (250, 215), (390, 245), (115, 245)
        focus = self_pos
        hidden_self = False
        draw.ellipse((224, 190, 276, 242), outline=(41, 116, 180), width=4)
    elif role == "broken_failure_state":
        self_pos, colleague_pos, leader_pos = (65, 265), (256, 215), (405, 240)
        focus = colleague_pos
        hidden_self = True
    elif role == "public_action":
        self_pos, colleague_pos, leader_pos = (175, 245), (285, 220), (405, 245)
        focus = self_pos
        hidden_self = False
        draw.line((190, 250, 250, 145), fill=(42, 103, 173), width=5)
    elif role == "public_immediate_result":
        self_pos, colleague_pos, leader_pos = (250, 220), (370, 250), (105, 250)
        focus = self_pos
        hidden_self = False
    else:
        raise ValueError(f"Unknown meeting canvas role: {role}")
    self_head = _draw_person(
        draw,
        "visual_self_001",
        x=self_pos[0],
        y=self_pos[1],
        scale=1.05,
        partially_hidden=hidden_self,
    )
    colleague_head = _draw_person(
        draw,
        "visual_colleague_001",
        x=colleague_pos[0],
        y=colleague_pos[1],
        scale=1.05,
    )
    leader_head = _draw_person(
        draw,
        "visual_leader_001",
        x=leader_pos[0],
        y=leader_pos[1],
        scale=1.05,
    )
    if variant == "visible":
        audience = _draw_audience(draw, focus=focus)
        if len(audience) != 6:
            raise AssertionError("Visible canvas did not draw exactly six people")
    draw.line((*leader_head, *focus), fill=(76, 91, 105), width=2)
    if focus == self_pos:
        draw.line((*colleague_head, *self_head), fill=(76, 91, 105), width=2)
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _private_canvas(*, result: bool) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), (219, 215, 204))
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (35, 55, 477, 440),
        fill=(235, 232, 221),
        outline=(105, 102, 94),
        width=4,
    )
    draw.rectangle(
        (120, 275, 395, 350),
        fill=(130, 104, 76),
        outline=(65, 52, 42),
        width=3,
    )
    self_x = 160 if result else 175
    leader_x = 350 if result else 340
    self_head = _draw_person(
        draw, "visual_self_001", x=self_x, y=215, scale=1.15
    )
    leader_head = _draw_person(
        draw, "visual_leader_001", x=leader_x, y=215, scale=1.15
    )
    _draw_timeline(draw, (215, 270, 315, 330))
    if result:
        draw.line((*leader_head, 265, 300), fill=(72, 99, 130), width=4)
        draw.ellipse((330, 125, 370, 155), outline=(105, 102, 94), width=3)
        for x in (340, 350, 360):
            draw.ellipse((x - 2, 138, x + 2, 142), fill=(105, 102, 94))
    else:
        draw.line((*self_head, 255, 300), fill=(72, 99, 130), width=4)
        draw.line((*leader_head, 265, 300), fill=(72, 99, 130), width=2)
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def deterministic_canvas_bytes(*, variant: Variant, semantic_role: str) -> bytes:
    if semantic_role in {
        "current_state",
        "desired_target_state",
        "broken_failure_state",
        "public_action",
        "public_immediate_result",
    }:
        return _meeting_canvas(variant=variant, role=semantic_role)
    if semantic_role == "private_action":
        return _private_canvas(result=False)
    if semantic_role == "private_immediate_result":
        return _private_canvas(result=True)
    raise ValueError(f"No deterministic canvas for semantic role {semantic_role}")


def _canvas(
    *,
    variant: Variant,
    semantic_role: str,
    repository_path: str,
    content_sha256: str,
) -> MosaicCanvasV1:
    payload = {
        "schema_version": "triad-mosaic-canvas-v1",
        "variant": variant,
        "semantic_role": semantic_role,
        "repository_path": repository_path,
        "content_sha256": content_sha256,
        "width": WIDTH,
        "height": HEIGHT,
        "generated_without_image_model": True,
        "contains_readable_text": False,
        "semantic_authority": "research_projection_only",
    }
    identity_payload = dict(payload)
    identity_payload.pop("repository_path")
    return MosaicCanvasV1(
        canvas_id=content_id("mosaic_canvas", identity_payload),
        **payload,
    )


def _panel(
    *,
    panel_kind: PanelKind,
    option_id: str | None,
    semantic_summary: str,
    attention_target: AttentionTarget,
    recognition: RecognitionState,
    leader_decision: LeaderDecisionState,
    public_attribution_changed: bool,
    canvas: MosaicCanvasV1,
    alias_of_panel_id: str | None = None,
) -> MosaicPanelV1:
    payload = {
        "schema_version": "triad-mosaic-panel-v1",
        "panel_kind": panel_kind,
        "option_id": option_id,
        "temporal_horizon": TEMPORAL_HORIZON,
        "semantic_summary": semantic_summary,
        "attention_target": attention_target,
        "official_recognition_state": recognition,
        "leader_decision_state": leader_decision,
        "public_attribution_changed": public_attribution_changed,
        "canvas": canvas,
        "alias_of_panel_id": alias_of_panel_id,
    }
    return MosaicPanelV1(
        panel_id=content_id("mosaic_panel", payload),
        **payload,
    )


def _mosaic(
    *,
    variant: Variant,
    canvases: Mapping[str, MosaicCanvasV1],
) -> EmocioVisualMosaicV1:
    audience = 6 if variant == "visible" else 0
    current = _panel(
        panel_kind="current_state",
        option_id=None,
        semantic_summary=(
            "The colleague occupies the meeting center and receives attention; "
            "self remains at the edge while official attribution is unresolved."
        ),
        attention_target="colleague",
        recognition="unresolved",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=canvases["current_state"],
    )
    desired = _panel(
        panel_kind="desired_target_state",
        option_id=None,
        semantic_summary=(
            "Target image only: self is officially recognized for the work while "
            "the colleague remains present without humiliation or removal."
        ),
        attention_target="self",
        recognition="desired_official_recognition_of_self",
        leader_decision="unknown",
        public_attribution_changed=True,
        canvas=canvases["desired_target_state"],
    )
    broken = _panel(
        panel_kind="broken_failure_state",
        option_id=None,
        semantic_summary=(
            "Failure image only: the colleague remains exclusively recognized and "
            "self becomes more displaced from the public scene."
        ),
        attention_target="colleague",
        recognition="broken_exclusive_recognition_of_colleague",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=canvases["broken_failure_state"],
    )
    no_action = _panel(
        panel_kind="action_panel",
        option_id="credit_no_response",
        semantic_summary="No response: the current meeting image is held unchanged.",
        attention_target="colleague",
        recognition="unresolved",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=current.canvas,
        alias_of_panel_id=current.panel_id,
    )
    no_result = _panel(
        panel_kind="immediate_result_panel",
        option_id="credit_no_response",
        semantic_summary=(
            "Immediately after no response, the current meeting image remains "
            "unchanged."
        ),
        attention_target="colleague",
        recognition="unresolved",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=current.canvas,
        alias_of_panel_id=current.panel_id,
    )
    private_action = _panel(
        panel_kind="action_panel",
        option_id="credit_private_evidence",
        semantic_summary=(
            "In a private next scene, self and the leader review the authorship "
            "evidence without the colleague or meeting audience."
        ),
        attention_target="evidence",
        recognition="unresolved",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=canvases["private_action"],
    )
    private_result = _panel(
        panel_kind="immediate_result_panel",
        option_id="credit_private_evidence",
        semantic_summary=(
            "The leader is considering the evidence; the earlier public attribution "
            "has not changed within the immediate horizon."
        ),
        attention_target="leader_considering_evidence",
        recognition="unresolved",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=canvases["private_immediate_result"],
    )
    public_action = _panel(
        panel_kind="action_panel",
        option_id="credit_public_confront",
        semantic_summary=(
            "Self steps forward in the same meeting and presents the evidence "
            f"before the leader and {audience} additional audience members."
        ),
        attention_target="self",
        recognition="unresolved",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=canvases["public_action"],
    )
    public_result = _panel(
        panel_kind="immediate_result_panel",
        option_id="credit_public_confront",
        semantic_summary=(
            "Attention has shifted to self and the colleague is secondary; official "
            "attribution and the leader's decision remain unresolved."
        ),
        attention_target="self",
        recognition="unresolved",
        leader_decision="unknown",
        public_attribution_changed=False,
        canvas=canvases["public_immediate_result"],
    )
    unresolved = (
        "official correction remains unknown",
        "public recognition remains unknown",
        "colleague response remains unknown",
    )
    options = (
        OptionVisualSequenceV1(
            option_id="credit_no_response",
            action_panel=no_action,
            immediate_result_panel=no_result,
            unresolved_relations=unresolved,
        ),
        OptionVisualSequenceV1(
            option_id="credit_private_evidence",
            action_panel=private_action,
            immediate_result_panel=private_result,
            unresolved_relations=unresolved,
        ),
        OptionVisualSequenceV1(
            option_id="credit_public_confront",
            action_panel=public_action,
            immediate_result_panel=public_result,
            unresolved_relations=unresolved,
        ),
    )
    payload = {
        "schema_version": "emocio-visual-mosaic-v1",
        "case_id": f"public_credit_audience_{variant}",
        "variant": variant,
        "temporal_horizon": TEMPORAL_HORIZON,
        "current_state": current,
        "desired_target_state": desired,
        "broken_failure_state": broken,
        "options": options,
        "identity_anchor_ids": tuple(item.subject_id for item in identity_anchors()),
        "root_audience_count": audience,
        "model_calls": 0,
        "native_decision_influence": 0,
        "visual_valuation_authority": False,
    }
    return EmocioVisualMosaicV1(
        mosaic_id=content_id("emocio_visual_mosaic", payload),
        **payload,
    )


def _report(
    *,
    mosaics: Sequence[EmocioVisualMosaicV1],
    sheets: Mapping[str, Mapping[str, Any]],
) -> str:
    lines = [
        "# TRIAD-VIS-M1 — canonical Emocio visual mosaic preflight",
        "",
        "Status: **deterministic research projection awaiting human review**.",
        "",
        "This phase defines Emocio thought as a visual mosaic rather than a single "
        "rendered option scene. It made no model calls and has no visual-valuation, "
        "native-conclusion, character, governance, decision, or Racio-vision "
        "authority.",
        "",
        f"Fixed temporal horizon: **{TEMPORAL_HORIZON}**",
        "",
        "Hard semantic boundaries:",
        "",
        "- Desired target state is neither an option action nor an immediate result.",
        "- An attention shift is not official recognition.",
        "- Presenting evidence is not a successful correction.",
        "- The leader decision and later organizational response remain unknown.",
        "- Only no-response action/result panels alias the current state.",
        "",
        "Stable identity anchors:",
        "",
        "- self: cobalt-blue blazer, white shirt, no tie;",
        "- colleague: charcoal suit, burgundy tie;",
        "- leader: cream blazer, dark blouse.",
        "",
    ]
    for mosaic in mosaics:
        lines.extend(
            [
                f"## {mosaic.case_id}",
                "",
                f"- Root meeting audience: `{mosaic.root_audience_count}` additional persons",
                f"- Mosaic ID: `{mosaic.mosaic_id}`",
                "",
                f"![{mosaic.variant} contact sheet]({sheets[mosaic.variant]['path']})",
                "",
                "| Mosaic panel | Immediate semantics | Recognition / leader decision |",
                "|---|---|---|",
                (
                    f"| current_state | {mosaic.current_state.semantic_summary} | "
                    f"`{mosaic.current_state.official_recognition_state}` / "
                    f"`{mosaic.current_state.leader_decision_state}` |"
                ),
                (
                    f"| desired_target_state | {mosaic.desired_target_state.semantic_summary} | "
                    f"`{mosaic.desired_target_state.official_recognition_state}` / "
                    f"`{mosaic.desired_target_state.leader_decision_state}` |"
                ),
                (
                    f"| broken_failure_state | {mosaic.broken_failure_state.semantic_summary} | "
                    f"`{mosaic.broken_failure_state.official_recognition_state}` / "
                    f"`{mosaic.broken_failure_state.leader_decision_state}` |"
                ),
            ]
        )
        for option in mosaic.options:
            lines.extend(
                [
                    (
                        f"| {option.option_id} — action | "
                        f"{option.action_panel.semantic_summary} | "
                        f"`{option.action_panel.official_recognition_state}` / "
                        f"`{option.action_panel.leader_decision_state}` |"
                    ),
                    (
                        f"| {option.option_id} — immediate result | "
                        f"{option.immediate_result_panel.semantic_summary} | "
                        f"`{option.immediate_result_panel.official_recognition_state}` / "
                        f"`{option.immediate_result_panel.leader_decision_state}` |"
                    ),
                ]
            )
        lines.extend(
            [
                "",
                "Human review (intentionally blank):",
                "",
                "- Current state is semantically legible:",
                "- Desired target is distinct from every option panel:",
                "- Broken failure is semantically legible:",
                "- No-response aliases are correct:",
                "- Private action is truly private:",
                "- Private immediate result preserves unresolved public attribution:",
                "- Public action shows evidence presentation without guaranteed success:",
                "- Public immediate result shows attention shift without official recognition:",
                "- Leader decision remains unknown:",
                "- Colleague response remains unknown:",
                "- Stable identities are preserved:",
                "- Audience count is correct where the meeting audience is in scope:",
                "- Unsupported inference:",
                "- Mosaic suitable for later research use:",
                "",
            ]
        )
    return "\n".join(lines)


def build(repository_root: Path) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    if _git(repository_root, "rev-parse", "HEAD") != EXPECTED_BASE_COMMIT:
        raise ValueError("TRIAD-VIS-M1 must start from the approved O2 result HEAD")
    output = repository_root / OUTPUT_RELATIVE_PATH
    if output.exists():
        raise FileExistsError("TRIAD-VIS-M1 output root already exists")
    o2_inventory = _o2_inventory(repository_root)
    anchors = identity_anchors()
    output.mkdir(parents=True)

    mosaics: list[EmocioVisualMosaicV1] = []
    sheet_records: dict[str, Mapping[str, Any]] = {}
    for variant in VARIANTS:
        canvas_by_role: dict[str, MosaicCanvasV1] = {}
        for role in (
            "current_state",
            "desired_target_state",
            "broken_failure_state",
            "private_action",
            "private_immediate_result",
            "public_action",
            "public_immediate_result",
        ):
            data = deterministic_canvas_bytes(variant=variant, semantic_role=role)
            relative = OUTPUT_RELATIVE_PATH / "canvases" / variant / f"{role}.png"
            _write_new(repository_root / relative, data)
            canvas_by_role[role] = _canvas(
                variant=variant,
                semantic_role=role,
                repository_path=relative.as_posix(),
                content_sha256=_sha256_bytes(data),
            )
        mosaic = _mosaic(variant=variant, canvases=canvas_by_role)
        mosaics.append(mosaic)
        display_paths = (
            ("current_state", mosaic.current_state.canvas),
            ("desired_target_state", mosaic.desired_target_state.canvas),
            ("broken_failure_state", mosaic.broken_failure_state.canvas),
            ("no_response/action", mosaic.options[0].action_panel.canvas),
            ("no_response/result", mosaic.options[0].immediate_result_panel.canvas),
            ("private/action", mosaic.options[1].action_panel.canvas),
            ("private/result", mosaic.options[1].immediate_result_panel.canvas),
            ("public/action", mosaic.options[2].action_panel.canvas),
            ("public/result", mosaic.options[2].immediate_result_panel.canvas),
        )
        sheet_path = output / "sheets" / f"{variant}_contact.png"
        _sheet(
            tuple(
                (label, repository_root / canvas.repository_path)
                for label, canvas in display_paths
            ),
            sheet_path,
            columns=3,
        )
        sheet_records[variant] = {
            "path": sheet_path.relative_to(output).as_posix(),
            "sha256": _file_sha256(sheet_path),
            "display_panel_count": 9,
        }

    unresolved = {
        "schema_version": "triad-vis-m1-unresolved-relations-v1",
        "temporal_horizon": TEMPORAL_HORIZON,
        "cases": [
            {
                "case_id": mosaic.case_id,
                "options": [
                    {
                        "option_id": option.option_id,
                        "unresolved_relations": option.unresolved_relations,
                    }
                    for option in mosaic.options
                ],
            }
            for mosaic in mosaics
        ],
        "leader_decision_known_in_option_panels": False,
        "official_correction_known_in_option_panels": False,
    }
    temporal = {
        "schema_version": "triad-vis-m1-temporal-horizon-v1",
        "fixed_horizon": TEMPORAL_HORIZON,
        "included": (
            "option action",
            "immediate visible result",
        ),
        "excluded_as_unknown": (
            "leader decision",
            "official correction",
            "public recognition",
            "colleague response",
            "later organizational response",
        ),
    }
    manifest = {
        "schema_version": "triad-vis-m1-mosaic-manifest-v1",
        "phase": "TRIAD-VIS-M1",
        "base_commit": EXPECTED_BASE_COMMIT,
        "contract": "EmocioVisualMosaicV1",
        "temporal_horizon": TEMPORAL_HORIZON,
        "identity_anchors": anchors,
        "mosaics": mosaics,
        "sheets": sheet_records,
        "frozen_o2_inventory": o2_inventory,
        "frozen_o2_inventory_sha256": _object_sha256(o2_inventory),
        "actual_canvas_files": 14,
        "display_panels": 18,
        "current_alias_panels": 4,
        "model_calls": 0,
        "image_model_calls": 0,
        "text_model_calls": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "private_thinking_persisted": False,
    }
    _write_new(output / "temporal_horizon.json", canonical_json_bytes(temporal))
    _write_new(
        output / "unresolved_relations.json",
        canonical_json_bytes(unresolved),
    )
    _write_new(
        output / "mosaic_manifest.json",
        canonical_json_bytes(manifest),
    )
    _write_new(
        output / "report.md",
        _report(mosaics=mosaics, sheets=sheet_records).encode("utf-8"),
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
        EmocioVisualMosaicV1.model_validate_json(
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
        raise ValueError("M1 must contain exactly two public-credit mosaics")
    _validate_o2_inventory(repository_root, manifest["frozen_o2_inventory"])
    if (
        manifest["model_calls"] != 0
        or manifest["image_model_calls"] != 0
        or manifest["text_model_calls"] != 0
    ):
        raise ValueError("M1 cannot contain model calls")
    canvas_paths: set[str] = set()
    for mosaic in mosaics:
        panels = (
            mosaic.current_state,
            mosaic.desired_target_state,
            mosaic.broken_failure_state,
            *(
                panel
                for option in mosaic.options
                for panel in (option.action_panel, option.immediate_result_panel)
            ),
        )
        for panel in panels:
            path = repository_root / panel.canvas.repository_path
            if (
                not path.is_file()
                or _file_sha256(path) != panel.canvas.content_sha256
            ):
                raise ValueError(f"Mosaic canvas hash mismatch: {path}")
            canvas_paths.add(panel.canvas.repository_path)
    if len(canvas_paths) != 14:
        raise ValueError("M1 must contain fourteen unique deterministic canvases")
    for item in manifest["sheets"].values():
        path = output / item["path"]
        if _file_sha256(path) != item["sha256"]:
            raise ValueError("M1 contact-sheet hash mismatch")
    absolute_hits = []
    for path in output.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".md"}:
            text = path.read_text(encoding="utf-8")
            if _contains_absolute_path(text):
                absolute_hits.append(path.relative_to(repository_root).as_posix())
    if absolute_hits:
        raise ValueError(f"M1 contains local absolute paths: {absolute_hits}")
    report = (output / "report.md").read_text(encoding="utf-8")
    if "Human review (intentionally blank):" not in report:
        raise ValueError("M1 report does not preserve blank human-review fields")
    return {
        "status": "passed",
        "mosaic_count": 2,
        "display_panels": 18,
        "unique_canvas_files": 14,
        "current_alias_panels": 4,
        "visible_root_audience": 6,
        "absent_root_audience": 0,
        "model_calls": 0,
        "image_model_calls": 0,
        "text_model_calls": 0,
        "character_replay": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "native_decision_influence": 0,
        "o2_files_verified": len(manifest["frozen_o2_inventory"]),
        "absolute_paths_found": 0,
        "private_thinking_persisted": False,
    }


__all__ = [
    "DISPLAY_ORDER",
    "EXPECTED_BASE_COMMIT",
    "EmocioVisualMosaicV1",
    "MosaicCanvasV1",
    "MosaicPanelV1",
    "OPTIONS",
    "OUTPUT_RELATIVE_PATH",
    "OptionVisualSequenceV1",
    "TEMPORAL_HORIZON",
    "build",
    "cold_verify",
    "deterministic_canvas_bytes",
]
