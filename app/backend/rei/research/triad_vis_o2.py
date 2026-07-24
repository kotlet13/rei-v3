"""TRIAD-VIS-O2 semantic-canvas-conditioned public-credit screen.

This module is research-only. It creates deterministic storyboard canvases,
uses them as explicit reference-image conditioning for the repository-pinned
FLUX.2 renderer, and preserves the outputs for human review. Images never gain
visual valuation, native conclusion, character, governance, or decision
authority.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, Self

from PIL import Image, ImageDraw
from pydantic import Field, model_validator

from ..emocio.artifacts import LocalPngArtifactStore
from ..emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersImageRenderer,
    LazyDiffusersBackend,
)
from ..emocio.renderer import build_render_call_spec
from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.emocio import VisualSceneSpec
from ..models.provider import ProviderCallSpec
from ..models.rendering import (
    ImageRenderBatchOutcome,
    ImageRenderRequest,
    ImageSourceReference,
)
from .triad_vis_o1 import (
    HEIGHT,
    MODEL_ID,
    MODEL_REVISION,
    SNAPSHOT_MANIFEST_SHA256,
    STEPS,
    TIMEOUT_SECONDS,
    WIDTH,
    _file_sha256,
    _git,
    _provider_identity,
    _replace_json,
    _runtime,
    _sha256_bytes,
    _sheet,
    _write_new,
)


EXPECTED_BASE_COMMIT: Final = "8c1f2c9a1369e042efcdbeaf7025ea327a7aa46e"
O1_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o1-2026-07-24"
)
O1_HUMAN_REVIEW_RELATIVE_PATH: Final = O1_RELATIVE_PATH / "human_visual_review.md"
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o2-2026-07-24"
)
O1_PROMPT_MANIFEST_SHA256: Final = (
    "c9a1fa58ec9124cd63d7a036cfcae08a6623b4cc399cda9cacb87ea4bd10c867"
)
CASE_ORDER: Final = (
    "public_credit_audience_visible",
    "public_credit_audience_absent",
)
VARIANT_BY_CASE: Final = {
    "public_credit_audience_visible": "visible",
    "public_credit_audience_absent": "absent",
}
SLOT_ORDER: Final = (
    "current",
    "desired",
    "broken",
    "credit_no_response",
    "credit_private_evidence",
    "credit_public_confront",
)
CALL_ORDER: Final = (
    ("visible", "current"),
    ("absent", "current"),
    ("visible", "desired"),
    ("absent", "desired"),
    ("visible", "broken"),
    ("absent", "broken"),
    ("visible", "credit_private_evidence"),
    ("absent", "credit_private_evidence"),
    ("visible", "credit_public_confront"),
    ("absent", "credit_public_confront"),
)
SEEDS: Final = {
    "current": 314159,
    "desired": 314160,
    "broken": 314161,
    "credit_private_evidence": 314162,
    "credit_public_confront": 314162,
}
STYLE_ID: Final = "clear_cinematic_storyboard_v1"
STYLE_DIRECTIVE: Final = (
    "Clear semi-realistic cinematic storyboard, simple composition, stable "
    "recurring character design, unambiguous body positions and gaze, restrained "
    "background, no readable text, no logos, no extra or duplicate people, no "
    "identity changes, and no symbolic crowns, medals, weapons, flames, or sparks."
)
RENDERER_PROMPT_FORBIDDEN: Final = (
    "evidence_id",
    "credit_ev_",
    "scene_kind",
    "option_id",
    "language_gloss",
    "grounded_evidence_ids",
    "source_status",
    "expected option",
    "expected_option",
    "best",
    "preferred",
    "safest",
    "winner",
    "character",
    "governance",
    "non-acceptance",
)
IDENTITY_COLORS: Final = {
    "visual_self_001": {
        "jacket": (35, 86, 170),
        "shirt": (245, 245, 240),
        "accent": None,
    },
    "visual_colleague_001": {
        "jacket": (55, 58, 64),
        "shirt": (235, 235, 230),
        "accent": (125, 25, 48),
    },
    "visual_leader_001": {
        "jacket": (232, 218, 184),
        "shirt": (38, 42, 50),
        "accent": None,
    },
}


class VisualIdentityAnchorV1(FrozenModel):
    schema_version: Literal["triad-visual-identity-anchor-v1"] = (
        "triad-visual-identity-anchor-v1"
    )
    subject_id: NonEmptyId
    stable_clothing_anchor: NonEmptyText
    stable_role: NonEmptyText
    appearance_description: NonEmptyText
    generated_only: Literal[True] = True
    semantic_authority: Literal["none"] = "none"


TransitionMode = Literal["same_scene_hold", "same_scene_edit", "next_scene_cut"]


class VisualTransitionSpecV1(FrozenModel):
    schema_version: Literal["triad-visual-transition-spec-v1"] = (
        "triad-visual-transition-spec-v1"
    )
    transition_id: NonEmptyId
    slot: NonEmptyId
    mode: TransitionMode
    retained_subject_ids: tuple[NonEmptyId, ...]
    removable_subject_ids: tuple[NonEmptyId, ...] = ()
    audience_policy: NonEmptyText
    camera_policy: NonEmptyText
    layout_policy: NonEmptyText

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        expected = content_id(
            "triad_visual_transition",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"transition_id"},
            ),
        )
        if self.transition_id != expected:
            raise ValueError("Visual transition ID differs from canonical content")
        return self


class SemanticCanvasArtifactV1(FrozenModel):
    schema_version: Literal["triad-semantic-canvas-artifact-v1"] = (
        "triad-semantic-canvas-artifact-v1"
    )
    canvas_id: NonEmptyId
    case_id: NonEmptyId
    variant: Literal["visible", "absent"]
    slot: NonEmptyId
    source_scene_spec_id: NonEmptyId
    source_scene_hash: HashDigest
    identity_anchor_manifest_hash: HashDigest
    transition_spec_hash: HashDigest
    content_sha256: HashDigest
    repository_path: NonEmptyText
    artifact_store_path: NonEmptyText
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    generated_without_image_model: Literal[True] = True
    grounded_external_evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        expected = content_id(
            "semantic_canvas",
            {
                "case_id": self.case_id,
                "variant": self.variant,
                "slot": self.slot,
                "source_scene_spec_id": self.source_scene_spec_id,
                "source_scene_hash": self.source_scene_hash,
                "identity_anchor_manifest_hash": self.identity_anchor_manifest_hash,
                "transition_spec_hash": self.transition_spec_hash,
                "content_sha256": self.content_sha256,
                "width": self.width,
                "height": self.height,
            },
        )
        if self.canvas_id != expected:
            raise ValueError("Semantic canvas ID differs from canonical content")
        return self


def _object_sha256(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def identity_anchors() -> tuple[VisualIdentityAnchorV1, ...]:
    return (
        VisualIdentityAnchorV1(
            subject_id="visual_self_001",
            stable_clothing_anchor="cobalt-blue blazer; white shirt; no tie",
            stable_role="self",
            appearance_description=(
                "Recurring adult with short dark hair and neutral presentation"
            ),
        ),
        VisualIdentityAnchorV1(
            subject_id="visual_colleague_001",
            stable_clothing_anchor="charcoal suit; burgundy tie",
            stable_role="colleague",
            appearance_description=(
                "Recurring adult with short dark hair and neutral presentation"
            ),
        ),
        VisualIdentityAnchorV1(
            subject_id="visual_leader_001",
            stable_clothing_anchor="cream blazer; dark blouse",
            stable_role="leader",
            appearance_description=(
                "Recurring adult with shoulder-length dark hair and neutral presentation"
            ),
        ),
    )


def _transition(
    slot: str,
    mode: TransitionMode,
    *,
    retained: tuple[str, ...],
    removable: tuple[str, ...] = (),
    audience_policy: str,
    camera_policy: str,
    layout_policy: str,
) -> VisualTransitionSpecV1:
    payload = {
        "schema_version": "triad-visual-transition-spec-v1",
        "slot": slot,
        "mode": mode,
        "retained_subject_ids": retained,
        "removable_subject_ids": removable,
        "audience_policy": audience_policy,
        "camera_policy": camera_policy,
        "layout_policy": layout_policy,
    }
    return VisualTransitionSpecV1(
        transition_id=content_id("triad_visual_transition", payload),
        **payload,
    )


def transition_specs() -> tuple[VisualTransitionSpecV1, ...]:
    principals = (
        "visual_colleague_001",
        "visual_leader_001",
        "visual_self_001",
    )
    same_scene_audience = (
        "Preserve exactly six additional neutral adults for the visible variant "
        "and exactly zero for the absent variant."
    )
    return (
        _transition(
            "current",
            "same_scene_hold",
            retained=principals,
            audience_policy=same_scene_audience,
            camera_policy="Keep the canonical meeting-room camera.",
            layout_policy="Keep the canonical current meeting layout.",
        ),
        _transition(
            "desired",
            "same_scene_edit",
            retained=principals,
            audience_policy=same_scene_audience,
            camera_policy="Keep the canonical meeting-room camera.",
            layout_policy="Principal subjects may move; no subject may be added or removed.",
        ),
        _transition(
            "broken",
            "same_scene_edit",
            retained=principals,
            audience_policy=same_scene_audience,
            camera_policy="Keep the canonical meeting-room camera.",
            layout_policy="Principal subjects may move; no subject may be added or removed.",
        ),
        _transition(
            "credit_no_response",
            "same_scene_hold",
            retained=principals,
            audience_policy=same_scene_audience,
            camera_policy="Reuse the exact current image artifact.",
            layout_policy="Reuse the exact current image artifact.",
        ),
        _transition(
            "credit_private_evidence",
            "next_scene_cut",
            retained=("visual_leader_001", "visual_self_001"),
            removable=("visual_colleague_001",),
            audience_policy="No additional audience is present in the later private scene.",
            camera_policy="A new side-office camera and room are allowed.",
            layout_policy="Only the same self and leader remain; no new principal appears.",
        ),
        _transition(
            "credit_public_confront",
            "same_scene_edit",
            retained=principals,
            audience_policy=same_scene_audience,
            camera_policy="Keep the canonical meeting-room camera or a near-identical frame.",
            layout_policy="Principal subjects may move; no subject may be added or removed.",
        ),
    )


def _load_o1_prompt_items(repository_root: Path) -> tuple[Mapping[str, Any], ...]:
    path = repository_root / O1_RELATIVE_PATH / "scene_prompt_manifest.json"
    if _file_sha256(path) != O1_PROMPT_MANIFEST_SHA256:
        raise ValueError("Frozen O1 scene/prompt manifest bytes changed")
    value = json.loads(path.read_text(encoding="utf-8"))
    selected = tuple(
        item for item in value["items"] if item["case_id"] in CASE_ORDER
    )
    if len(selected) != 12:
        raise ValueError("O1 does not contain the exact twelve O2 source slots")
    return selected


def _scene_for_slot(
    repository_root: Path,
    *,
    case_id: str,
    slot: str,
) -> VisualSceneSpec:
    role = {
        "credit_no_response": "option_0",
        "credit_private_evidence": "option_1",
        "credit_public_confront": "option_2",
    }.get(slot, slot)
    matches = tuple(
        item
        for item in _load_o1_prompt_items(repository_root)
        if item["case_id"] == case_id and item["role"] == role
    )
    if len(matches) != 1:
        raise ValueError(f"No exact frozen O1 scene for {case_id}/{slot}")
    return VisualSceneSpec.model_validate_json(
        json.dumps(
            matches[0]["scene_spec"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        strict=True,
    )


def _draw_person(
    draw: ImageDraw.ImageDraw,
    subject_id: str,
    *,
    x: int,
    y: int,
    scale: float = 1.0,
    partially_hidden: bool = False,
) -> tuple[int, int]:
    colors = IDENTITY_COLORS[subject_id]
    head_r = int(16 * scale)
    body_w = int(48 * scale)
    body_h = int(76 * scale)
    head_center = (x, y)
    draw.ellipse(
        (
            x - head_r,
            y - head_r,
            x + head_r,
            y + head_r,
        ),
        fill=(191, 145, 108),
        outline=(55, 45, 40),
        width=max(1, int(2 * scale)),
    )
    draw.pieslice(
        (
            x - head_r - 1,
            y - head_r - 2,
            x + head_r + 1,
            y + head_r,
        ),
        180,
        355,
        fill=(45, 35, 30),
    )
    body_top = y + head_r - 2
    draw.rounded_rectangle(
        (
            x - body_w // 2,
            body_top,
            x + body_w // 2,
            body_top + body_h,
        ),
        radius=max(3, int(7 * scale)),
        fill=colors["jacket"],
        outline=(40, 45, 50),
        width=max(1, int(2 * scale)),
    )
    shirt_w = max(6, int(14 * scale))
    draw.polygon(
        (
            (x - shirt_w, body_top),
            (x + shirt_w, body_top),
            (x, body_top + int(30 * scale)),
        ),
        fill=colors["shirt"],
    )
    if colors["accent"] is not None:
        draw.polygon(
            (
                (x - int(3 * scale), body_top + int(5 * scale)),
                (x + int(3 * scale), body_top + int(5 * scale)),
                (x + int(2 * scale), body_top + int(35 * scale)),
                (x - int(2 * scale), body_top + int(35 * scale)),
            ),
            fill=colors["accent"],
        )
    if partially_hidden:
        draw.rectangle(
            (
                x - body_w // 2,
                body_top + body_h // 3,
                x + body_w // 2,
                body_top + body_h,
            ),
            fill=(196, 201, 207),
            outline=(125, 130, 138),
        )
    return head_center


def _draw_audience(
    draw: ImageDraw.ImageDraw,
    *,
    focus: tuple[int, int],
) -> tuple[tuple[int, int], ...]:
    positions = ((70, 185), (135, 165), (200, 180), (312, 180), (377, 165), (442, 185))
    heads: list[tuple[int, int]] = []
    neutral = ((87, 100, 112), (105, 112, 120), (76, 91, 104))
    for index, (x, y) in enumerate(positions):
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=(186, 142, 108))
        draw.rectangle(
            (x - 18, y + 10, x + 18, y + 52),
            fill=neutral[index % len(neutral)],
        )
        draw.line((x, y, focus[0], focus[1]), fill=(145, 151, 158), width=1)
        heads.append((x, y))
    return tuple(heads)


def _draw_timeline(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = bounds
    mid = (top + bottom) // 2
    draw.rectangle(bounds, fill=(232, 238, 241), outline=(73, 86, 97), width=3)
    draw.line((left + 24, mid, right - 24, mid), fill=(42, 103, 173), width=6)
    for index in range(4):
        x = left + 45 + index * ((right - left - 90) // 3)
        draw.ellipse((x - 8, mid - 8, x + 8, mid + 8), fill=(125, 25, 48))
        draw.rectangle((x - 14, mid - 36, x + 14, mid - 20), fill=(99, 117, 132))


def _draw_project_diagram(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = bounds
    draw.rectangle(bounds, fill=(229, 235, 238), outline=(73, 86, 97), width=3)
    nodes = (
        (left + 50, top + 40),
        ((left + right) // 2, top + 65),
        (right - 50, top + 38),
        ((left + right) // 2, bottom - 35),
    )
    for start, end in ((0, 1), (1, 2), (1, 3)):
        draw.line((*nodes[start], *nodes[end]), fill=(72, 105, 136), width=4)
    for x, y in nodes:
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(55, 116, 174))


def _canvas_png(
    *,
    variant: Literal["visible", "absent"],
    slot: str,
) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), (220, 224, 226))
    draw = ImageDraw.Draw(image)
    if slot == "credit_private_evidence":
        draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(219, 215, 204))
        draw.rectangle((35, 55, 477, 440), fill=(235, 232, 221), outline=(105, 102, 94), width=4)
        draw.rectangle((120, 275, 395, 350), fill=(130, 104, 76), outline=(65, 52, 42), width=3)
        self_head = _draw_person(draw, "visual_self_001", x=175, y=215, scale=1.15)
        leader_head = _draw_person(draw, "visual_leader_001", x=340, y=215, scale=1.15)
        _draw_timeline(draw, (215, 270, 315, 330))
        draw.line((*self_head, 255, 300), fill=(72, 99, 130), width=2)
        draw.line((*leader_head, 265, 300), fill=(72, 99, 130), width=2)
    else:
        draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(211, 218, 223))
        draw.rectangle((20, 25, 492, 460), fill=(231, 234, 235), outline=(99, 110, 119), width=4)
        screen_bounds = (156, 55, 356, 170)
        if slot in {"desired", "credit_public_confront"}:
            _draw_timeline(draw, screen_bounds)
        else:
            _draw_project_diagram(draw, screen_bounds)
        draw.polygon(
            ((92, 325), (420, 325), (468, 455), (44, 455)),
            fill=(142, 112, 82),
            outline=(70, 55, 42),
        )
        if slot in {"desired", "credit_public_confront"}:
            self_pos = (256, 225)
            colleague_pos = (390, 240)
            leader_pos = (115, 240)
            focus = self_pos
            hidden_self = False
        elif slot == "broken":
            self_pos = (65, 260)
            colleague_pos = (256, 220)
            leader_pos = (405, 240)
            focus = colleague_pos
            hidden_self = True
        else:
            self_pos = (75, 250)
            colleague_pos = (256, 220)
            leader_pos = (405, 240)
            focus = colleague_pos
            hidden_self = False
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
            _draw_audience(draw, focus=focus)
        draw.line((*leader_head, *focus), fill=(76, 91, 105), width=2)
        if slot in {"desired", "credit_public_confront"}:
            draw.line((*colleague_head, *self_head), fill=(76, 91, 105), width=2)
    output = io.BytesIO()
    image.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def _natural_prompt(
    *,
    variant: Literal["visible", "absent"],
    slot: str,
) -> str:
    audience = (
        "Exactly six additional neutral adult team members are present behind "
        "the three principal people."
        if variant == "visible"
        else "No additional audience members are present."
    )
    identity = (
        "The recurring self wears a cobalt-blue blazer, white shirt, and no tie. "
        "The recurring colleague wears a charcoal suit and burgundy tie. "
        "The recurring leader wears a cream blazer over a dark blouse."
    )
    style = (
        "Create a clear semi-realistic cinematic storyboard with simple composition, "
        "stable recurring people, unambiguous body positions and gaze, and a "
        "restrained background. Use the supplied semantic canvas as the precise "
        "composition guide. "
    )
    if slot == "current":
        scene = (
            "In the modern meeting room, the colleague stands centered beside a "
            "projection showing a generic project diagram. Self remains clearly "
            "visible at the left edge. The leader watches the centered colleague. "
            f"{audience} Everyone present focuses on the colleague."
        )
    elif slot == "desired":
        scene = (
            "Keep the same meeting room, camera, and principal people. Self now "
            "stands centered beside a projection showing a generic visual timeline. "
            "The colleague remains present in a secondary position. The leader and "
            f"everyone present visibly focus on self. {audience} The composition "
            "shows recognition of self without humiliating or removing the colleague."
        )
    elif slot == "broken":
        scene = (
            "Keep the same meeting room, camera, and principal people. The colleague "
            "is the only centrally recognized presenter beside a generic project "
            "diagram. Self is pushed farther to the edge and partly obscured. The "
            f"leader and everyone present focus on the colleague. {audience} No "
            "authorship timeline or record is visible."
        )
    elif slot == "credit_private_evidence":
        scene = (
            "Show a later scene in a quiet side office with only the same self and "
            "the same leader present. The colleague and all audience members are "
            "absent. Self shows a generic visual timeline on a laptop or document "
            "while the leader studies it. This private scene does not change the "
            "earlier public meeting composition."
        )
    elif slot == "credit_public_confront":
        scene = (
            "Keep the same meeting room, nearly identical camera, and the same "
            "people. Self steps forward beside the projection and presents a generic "
            "visual timeline. The colleague moves from the center to a secondary "
            f"position. The leader and everyone present turn toward self. {audience} "
            "No person is added, removed, replaced, or duplicated."
        )
    else:
        raise ValueError(f"No model prompt exists for slot {slot}")
    constraints = (
        " Preserve all recurring identities and clothing exactly. Do not add or "
        "duplicate people. No readable text, names, labels, logos, aggression, "
        "humiliation, weapons, medals, crowns, flames, sparks, or invented drama."
    )
    return style + identity + " " + scene + constraints


def _audit_trace(
    *,
    scene: VisualSceneSpec,
    transition: VisualTransitionSpecV1,
    anchors: Sequence[VisualIdentityAnchorV1],
    prompt: str,
) -> Mapping[str, Any]:
    return {
        "source_scene_spec": scene,
        "source_scene_hash": scene.content_hash(),
        "source_evidence_ids": scene.grounded_evidence_ids,
        "source_status": "frozen_e3_route_synthesis_plus_implementation_neutral_identity",
        "identity_anchors": anchors,
        "identity_anchor_manifest_hash": _object_sha256(anchors),
        "transition_spec": transition,
        "transition_spec_hash": _object_sha256(transition),
        "style_id": STYLE_ID,
        "style_directive": STYLE_DIRECTIVE,
        "style_status": "implementation_hypothesis",
        "renderer_prompt": prompt,
        "renderer_prompt_contains_audit_metadata": False,
        "private_thinking_persisted": False,
    }


def _o1_inventory(repository_root: Path) -> tuple[Mapping[str, Any], ...]:
    root = repository_root / O1_RELATIVE_PATH
    items = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "human_visual_review.md":
            continue
        items.append(
            {
                "path": path.relative_to(repository_root).as_posix(),
                "sha256": _file_sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    if len(items) < 40:
        raise ValueError("Frozen O1 inventory is unexpectedly incomplete")
    return tuple(items)


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
            raise ValueError(f"Frozen O1 evidence changed: {item['path']}")


def _prompt_gate(items: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    failures: list[Mapping[str, Any]] = []
    for item in items:
        prompt = item["natural_prompt"]
        lowered = prompt.lower()
        hits = tuple(term for term in RENDERER_PROMPT_FORBIDDEN if term in lowered)
        if hits:
            failures.append(
                {
                    "call_index": item["call_index"],
                    "code": "renderer_prompt_metadata_or_leakage",
                    "hits": hits,
                }
            )
        if re.search(r"\b[a-z_]+=", prompt) or re.search(r"\b[0-9a-f]{64}\b", prompt):
            failures.append(
                {
                    "call_index": item["call_index"],
                    "code": "renderer_prompt_serialized_metadata",
                }
            )
    return {
        "passed": not failures,
        "prompt_count": len(items),
        "failures": failures,
    }


def _pair_gate(
    canvases: Sequence[SemanticCanvasArtifactV1],
) -> Mapping[str, Any]:
    by_key = {(item.variant, item.slot): item for item in canvases}
    checks = {
        "twelve_canvas_artifacts": len(canvases) == 12,
        "visible_current_no_response_bytes_equal": (
            by_key[("visible", "current")].content_sha256
            == by_key[("visible", "credit_no_response")].content_sha256
        ),
        "absent_current_no_response_bytes_equal": (
            by_key[("absent", "current")].content_sha256
            == by_key[("absent", "credit_no_response")].content_sha256
        ),
        "private_canvas_pair_identical": (
            by_key[("visible", "credit_private_evidence")].content_sha256
            == by_key[("absent", "credit_private_evidence")].content_sha256
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}


def _canvas_artifact(
    *,
    case_id: str,
    variant: Literal["visible", "absent"],
    slot: str,
    scene: VisualSceneSpec,
    transition: VisualTransitionSpecV1,
    anchor_hash: str,
    content_sha256: str,
) -> SemanticCanvasArtifactV1:
    transition_hash = _object_sha256(transition)
    canvas_id = content_id(
        "semantic_canvas",
        {
            "case_id": case_id,
            "variant": variant,
            "slot": slot,
            "source_scene_spec_id": scene.scene_id,
            "source_scene_hash": scene.content_hash(),
            "identity_anchor_manifest_hash": anchor_hash,
            "transition_spec_hash": transition_hash,
            "content_sha256": content_sha256,
            "width": WIDTH,
            "height": HEIGHT,
        },
    )
    return SemanticCanvasArtifactV1(
        canvas_id=canvas_id,
        case_id=case_id,
        variant=variant,
        slot=slot,
        source_scene_spec_id=scene.scene_id,
        source_scene_hash=scene.content_hash(),
        identity_anchor_manifest_hash=anchor_hash,
        transition_spec_hash=transition_hash,
        content_sha256=content_sha256,
        repository_path=(
            OUTPUT_RELATIVE_PATH / "canvases" / variant / f"{slot}.png"
        ).as_posix(),
        artifact_store_path=f"semantic_canvases/{canvas_id}.png",
        width=WIDTH,
        height=HEIGHT,
    )


def _source_reference(
    canvas: SemanticCanvasArtifactV1,
) -> ImageSourceReference:
    return ImageSourceReference(
        image_id=canvas.canvas_id,
        content_sha256=canvas.content_sha256,
        media_type="image/png",
        path=canvas.artifact_store_path,
        width=canvas.width,
        height=canvas.height,
        grounded=False,
        originating_scene_spec_id=canvas.source_scene_spec_id,
        originating_scene_spec_hash=canvas.source_scene_hash,
    )


def seal(
    repository_root: Path,
    *,
    snapshot_directory: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    snapshot = snapshot_directory.resolve(strict=True)
    if _git(repository_root, "rev-parse", "HEAD") != EXPECTED_BASE_COMMIT:
        raise ValueError("TRIAD-VIS-O2 must seal from the approved O1 result HEAD")
    output = repository_root / OUTPUT_RELATIVE_PATH
    if output.exists():
        raise FileExistsError("TRIAD-VIS-O2 output root already exists")
    human_review = repository_root / O1_HUMAN_REVIEW_RELATIVE_PATH
    if not human_review.is_file():
        raise ValueError("Human-supplied O1 review is missing")
    snapshot_manifest_path = snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    if _file_sha256(snapshot_manifest_path) != SNAPSHOT_MANIFEST_SHA256:
        raise ValueError("Pinned FLUX.2 snapshot manifest SHA-256 changed")
    snapshot_manifest = json.loads(snapshot_manifest_path.read_text(encoding="utf-8"))
    if (
        snapshot_manifest.get("repo_id") != MODEL_ID
        or snapshot_manifest.get("revision") != MODEL_REVISION
    ):
        raise ValueError("Pinned FLUX.2 snapshot identity changed")
    runtime = _runtime(snapshot)
    if runtime.conditioning_method("image_to_image") != "reference_image":
        raise ValueError("Pinned renderer cannot accept semantic canvas references")

    anchors = identity_anchors()
    anchor_hash = _object_sha256(anchors)
    transitions = transition_specs()
    transition_by_slot = {item.slot: item for item in transitions}
    if tuple(transition_by_slot) != SLOT_ORDER:
        raise ValueError("Transition manifest does not cover canonical O2 slot order")
    output.mkdir(parents=True)
    canvas_artifacts: list[SemanticCanvasArtifactV1] = []
    scene_by_key: dict[tuple[str, str], VisualSceneSpec] = {}
    for case_id in CASE_ORDER:
        variant = VARIANT_BY_CASE[case_id]
        current_bytes: bytes | None = None
        for slot in SLOT_ORDER:
            scene = _scene_for_slot(repository_root, case_id=case_id, slot=slot)
            scene_by_key[(variant, slot)] = scene
            if slot == "credit_no_response":
                if current_bytes is None:
                    raise ValueError("Current canvas must precede no-response")
                canvas_bytes = current_bytes
            else:
                canvas_bytes = _canvas_png(variant=variant, slot=slot)
                if slot == "current":
                    current_bytes = canvas_bytes
            digest = _sha256_bytes(canvas_bytes)
            artifact = _canvas_artifact(
                case_id=case_id,
                variant=variant,
                slot=slot,
                scene=scene,
                transition=transition_by_slot[slot],
                anchor_hash=anchor_hash,
                content_sha256=digest,
            )
            _write_new(repository_root / artifact.repository_path, canvas_bytes)
            canvas_artifacts.append(artifact)

    pair_gate = _pair_gate(canvas_artifacts)
    if not pair_gate["passed"]:
        raise ValueError(f"Semantic canvas pair gate failed: {pair_gate}")
    provider = _provider_identity()
    pipeline = runtime.pipeline_spec("image_to_image")
    canvas_by_key = {(item.variant, item.slot): item for item in canvas_artifacts}
    prompt_items: list[Mapping[str, Any]] = []
    expected_calls: list[Mapping[str, Any]] = []
    for call_index, (variant, slot) in enumerate(CALL_ORDER, start=1):
        canvas = canvas_by_key[(variant, slot)]
        scene = scene_by_key[(variant, slot)]
        transition = transition_by_slot[slot]
        prompt = _natural_prompt(variant=variant, slot=slot)
        request = ImageRenderRequest.create(
            mode="image_to_image",
            source_spec=scene,
            provider=provider,
            pipeline=pipeline,
            seed=SEEDS[slot],
            prompt=prompt,
            negative_prompt="",
            width=WIDTH,
            height=HEIGHT,
            num_inference_steps=STEPS,
            guidance_scale=1.0,
            source_image=_source_reference(canvas),
            strength=None,
            conditioning_method="reference_image",
            prompt_language="en",
            style_id=STYLE_ID,
            profile_hash=_object_sha256(
                {
                    "style_id": STYLE_ID,
                    "style_directive": STYLE_DIRECTIVE,
                    "status": "implementation_hypothesis",
                }
            ),
        )
        call = build_render_call_spec(request, timeout_seconds=TIMEOUT_SECONDS)
        prompt_items.append(
            {
                "call_index": call_index,
                "variant": variant,
                "slot": slot,
                "seed": SEEDS[slot],
                "natural_prompt": prompt,
                "negative_prompt": "",
                "negative_prompt_used_by_pipeline": False,
                "audit_trace": _audit_trace(
                    scene=scene,
                    transition=transition,
                    anchors=anchors,
                    prompt=prompt,
                ),
                "canvas": canvas,
                "request": request,
                "call_spec": call,
            }
        )
        expected_calls.append(
            {
                "call_index": call_index,
                "variant": variant,
                "slot": slot,
                "request_id": request.request_id,
                "request_hash": request.content_hash(),
                "call_id": call.call_id,
                "call_spec_hash": call.content_hash(),
                "seed": request.seed,
                "status": "expected_not_started",
            }
        )
    prompt_gate = _prompt_gate(prompt_items)
    if not prompt_gate["passed"]:
        raise ValueError(f"Natural renderer prompt gate failed: {prompt_gate}")
    no_response_calls = tuple(
        item for item in prompt_items if item["slot"] == "credit_no_response"
    )
    if no_response_calls or len(prompt_items) != 10:
        raise ValueError("O2 must freeze exactly ten model calls and zero no-response calls")
    if any(
        item["seed"] != 314162
        for item in prompt_items
        if item["slot"]
        in {"credit_private_evidence", "credit_public_confront"}
    ):
        raise ValueError("Private/public matched seed policy failed")

    o1_inventory = _o1_inventory(repository_root)
    _write_new(
        output / "identity_anchor_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-identity-anchor-manifest-v1",
                "manifest_hash": anchor_hash,
                "anchors": anchors,
                "generated_only": True,
                "semantic_authority": "none",
            }
        ),
    )
    _write_new(
        output / "transition_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-transition-manifest-v1",
                "transitions": transitions,
            }
        ),
    )
    _write_new(
        output / "canvas_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-canvas-manifest-v1",
                "canvas_count": 12,
                "generated_without_image_model": True,
                "items": canvas_artifacts,
            }
        ),
    )
    _write_new(
        output / "prompt_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-natural-prompt-manifest-v1",
                "prompt_count": 10,
                "all_prompts_frozen_before_first_render": True,
                "items": prompt_items,
            }
        ),
    )
    _write_new(
        output / "expected_call_ledger.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-expected-call-ledger-v1",
                "expected_calls": 10,
                "retries": 0,
                "fallbacks": 0,
                "entries": expected_calls,
            }
        ),
    )
    _write_new(
        output / "preflight_report.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-preflight-report-v1",
                "passed": True,
                "identity": {
                    "fixed_anchor_ids": tuple(item.subject_id for item in anchors),
                    "case_or_option_determines_identity": False,
                },
                "pair_isolation": pair_gate,
                "transitions": {
                    "no_response_reuses_current_canvas": True,
                    "private_mode": "next_scene_cut",
                    "public_mode": "same_scene_edit",
                    "private_people": ("visual_self_001", "visual_leader_001"),
                    "public_adds_person": False,
                },
                "prompts": prompt_gate,
                "text_model_calls": 0,
                "image_model_calls_started": 0,
                "character_replay": 0,
                "native_decision_influence": 0,
            }
        ),
    )
    _write_new(
        output / "o1_frozen_inventory.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-o1-frozen-inventory-v1",
                "items": o1_inventory,
            }
        ),
    )
    code_paths = (
        Path("app/backend/rei/research/triad_vis_o2.py"),
        Path("scripts/run_triad_vis_o2.py"),
        Path("tests/rei/test_triad_vis_o2.py"),
    )
    code_hashes = {
        path.as_posix(): _file_sha256(repository_root / path) for path in code_paths
    }
    frozen_files = (
        "identity_anchor_manifest.json",
        "transition_manifest.json",
        "canvas_manifest.json",
        "prompt_manifest.json",
        "expected_call_ledger.json",
        "preflight_report.json",
        "o1_frozen_inventory.json",
    )
    seal_payload = {
        "schema_version": "triad-vis-o2-pre-call-seal-v1",
        "phase": "TRIAD-VIS-O2",
        "base_commit": EXPECTED_BASE_COMMIT,
        "o1_human_review": {
            "path": O1_HUMAN_REVIEW_RELATIVE_PATH.as_posix(),
            "sha256": _file_sha256(human_review),
            "status": "human_supplied_not_codex_assessed",
        },
        "frozen_file_hashes": {
            name: _file_sha256(output / name) for name in frozen_files
        },
        "semantic_canvas_hashes": {
            f"{item.variant}/{item.slot}": item.content_sha256
            for item in canvas_artifacts
        },
        "code_path_hashes": code_hashes,
        "provider": provider,
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "snapshot_manifest_sha256": SNAPSHOT_MANIFEST_SHA256,
        "snapshot_manifest_file_count": len(snapshot_manifest["files"]),
        "pipeline": pipeline,
        "style_id": STYLE_ID,
        "style_directive": STYLE_DIRECTIVE,
        "matched_seed_schedule": SEEDS,
        "call_order": CALL_ORDER,
        "expected_image_model_calls": 10,
        "expected_visible_scene_slots": 12,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "racio_vision": 0,
        "visual_valuation_authority": False,
        "private_thinking_persisted": False,
        "negative_prompt_used_by_pipeline": False,
        "output_root": OUTPUT_RELATIVE_PATH.as_posix(),
        "first_render_started": False,
    }
    _write_new(output / "pre_call_seal.json", canonical_json_bytes(seal_payload))
    return {
        "status": "sealed",
        "pre_call_seal_sha256": _file_sha256(output / "pre_call_seal.json"),
        "human_review_sha256": seal_payload["o1_human_review"]["sha256"],
        "canvas_count": 12,
        "prompt_count": 10,
        "image_model_calls_started": 0,
    }


def verify_seal(
    repository_root: Path,
    *,
    snapshot_directory: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    snapshot = snapshot_directory.resolve(strict=True)
    output = repository_root / OUTPUT_RELATIVE_PATH
    seal_value = json.loads((output / "pre_call_seal.json").read_text(encoding="utf-8"))
    if seal_value["base_commit"] != EXPECTED_BASE_COMMIT:
        raise ValueError("Unexpected O2 seal base")
    if _file_sha256(
        snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    ) != SNAPSHOT_MANIFEST_SHA256:
        raise ValueError("Pinned snapshot manifest changed")
    human_review = repository_root / seal_value["o1_human_review"]["path"]
    if _file_sha256(human_review) != seal_value["o1_human_review"]["sha256"]:
        raise ValueError("Human-supplied O1 review changed")
    for name, digest in seal_value["frozen_file_hashes"].items():
        if _file_sha256(output / name) != digest:
            raise ValueError(f"Sealed O2 file changed: {name}")
    for name, digest in seal_value["code_path_hashes"].items():
        if _file_sha256(repository_root / name) != digest:
            raise ValueError(f"Sealed O2 code path changed: {name}")
    inventory = json.loads(
        (output / "o1_frozen_inventory.json").read_text(encoding="utf-8")
    )["items"]
    _validate_inventory(repository_root, inventory)
    canvas_manifest = json.loads(
        (output / "canvas_manifest.json").read_text(encoding="utf-8")
    )
    for item in canvas_manifest["items"]:
        path = repository_root / item["repository_path"]
        if _file_sha256(path) != item["content_sha256"]:
            raise ValueError(f"Semantic canvas bytes changed: {item['repository_path']}")
    prompts = json.loads(
        (output / "prompt_manifest.json").read_text(encoding="utf-8")
    )["items"]
    prompt_gate = _prompt_gate(prompts)
    if not prompt_gate["passed"] or len(prompts) != 10:
        raise ValueError("Sealed natural prompts failed cold gate")
    return {
        "status": "verified",
        "o1_files_verified": len(inventory),
        "canvas_count": len(canvas_manifest["items"]),
        "prompt_count": len(prompts),
    }


def _strict_request(value: Mapping[str, Any]) -> ImageRenderRequest:
    return ImageRenderRequest.model_validate_json(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        strict=True,
    )


def _strict_call(value: Mapping[str, Any]) -> ProviderCallSpec:
    return ProviderCallSpec.model_validate_json(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        strict=True,
    )


def _manifest_entry(
    *,
    prompt_item: Mapping[str, Any],
    request: ImageRenderRequest,
    call: ProviderCallSpec,
    outcome: Any,
    repository_path: str | None,
    size_bytes: int | None,
) -> Mapping[str, Any]:
    return {
        "call_index": prompt_item["call_index"],
        "variant": prompt_item["variant"],
        "slot": prompt_item["slot"],
        "canvas": prompt_item["canvas"],
        "natural_prompt": prompt_item["natural_prompt"],
        "negative_prompt": "",
        "negative_prompt_used_by_pipeline": False,
        "audit_trace": prompt_item["audit_trace"],
        "request": request.model_dump(mode="json"),
        "call_spec": call.model_dump(mode="json"),
        "call_record": outcome.call_record.model_dump(mode="json"),
        "artifact": (
            outcome.artifact.model_dump(mode="json")
            if outcome.artifact is not None
            else None
        ),
        "failure_code": outcome.failure_code,
        "failure_message": outcome.failure_message,
        "repository_image_path": repository_path,
        "size_bytes": size_bytes,
        "private_thinking_persisted": False,
        "native_decision_influence": 0,
    }


def _report(
    image_items: Sequence[Mapping[str, Any]],
    aliases: Sequence[Mapping[str, Any]],
    sheet_manifest: Mapping[str, Any],
) -> str:
    by_key = {(item["variant"], item["slot"]): item for item in image_items}
    alias_by_key = {(item["variant"], item["slot"]): item for item in aliases}
    lines = [
        "# TRIAD-VIS-O2 — semantic-canvas-conditioned public-credit isolation",
        "",
        "Status: **render evidence awaiting human visual review**.",
        "",
        "This research-only screen uses deterministic semantic canvases as "
        "reference-image conditioning. The images are imagined artifacts and have "
        "zero visual-valuation, native-conclusion, character, governance, decision, "
        "or Racio-vision authority.",
        "",
        "- Image-model calls: `10`",
        "- Visible scene slots: `12`",
        "- Text-model calls: `0`",
        "- Retries / fallbacks: `0 / 0`",
        "- Character replay / native-decision influence / Racio vision: `0 / 0 / 0`",
        "- `private_thinking_persisted = false`",
        "",
        "## Overview sheets",
        "",
        f"![Visible contact sheet]({sheet_manifest['visible_contact']['path']})",
        "",
        f"![Absent contact sheet]({sheet_manifest['absent_contact']['path']})",
        "",
        f"![Pair comparison]({sheet_manifest['pair_comparison']['path']})",
        "",
    ]
    for variant in ("visible", "absent"):
        lines.extend([f"## Audience {variant}", ""])
        for slot in SLOT_ORDER:
            if slot == "credit_no_response":
                alias = alias_by_key[(variant, slot)]
                current = by_key[(variant, "current")]
                image_path = alias["repository_image_path_from_report"]
                image_hash = alias["content_sha256"]
                call_text = "No model call; exact current image artifact alias."
                canvas = alias["canvas"]
            else:
                item = by_key[(variant, slot)]
                artifact = item["artifact"]
                image_path = item["repository_image_path_from_report"]
                image_hash = artifact["content_sha256"]
                call_text = (
                    f"Call `{item['call_index']}`; request `{item['request']['request_id']}`; "
                    f"call `{item['call_spec']['call_id']}`."
                )
                canvas = item["canvas"]
            pair_sheet = sheet_manifest["canvas_render_pairs"][
                f"{variant}/{slot}"
            ]["path"]
            lines.extend(
                [
                    f"### {slot}",
                    "",
                    f"![Canvas and render]({pair_sheet})",
                    "",
                    f"- Canvas: `{canvas['repository_path']}`",
                    f"- Canvas SHA-256: `{canvas['content_sha256']}`",
                    f"- Render: `{image_path}`",
                    f"- Render SHA-256: `{image_hash}`",
                    f"- Execution: {call_text}",
                    "",
                    "Human review (intentionally blank):",
                    "",
                    "- Canvas matches intended semantics:",
                    "- Render follows canvas:",
                    "- Self identity stable:",
                    "- Colleague identity stable:",
                    "- Leader identity stable:",
                    "- Audience count correct:",
                    "- Camera/layout continuity correct:",
                    "- Transition mode respected:",
                    "- Self position correct:",
                    "- Attention/gaze correct:",
                    "- Obstacle state correct:",
                    "- Recognition state visible:",
                    "- Private scene truly private:",
                    "- No extra person:",
                    "- No duplicate person:",
                    "- No readable-text artifact:",
                    "- Unsupported generated detail:",
                    "- Prompt predetermines option:",
                    "- Usable for Racio vision:",
                    "",
                ]
            )
    return "\n".join(lines)


def execute(
    repository_root: Path,
    *,
    snapshot_directory: Path,
    runtime_artifact_root: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    snapshot = snapshot_directory.resolve(strict=True)
    runtime_root = runtime_artifact_root.resolve()
    if runtime_root.exists():
        raise FileExistsError("O2 runtime artifact root must be create-only")
    if _git(repository_root, "status", "--short"):
        raise ValueError("O2 execution requires a clean committed seal")
    verify_seal(repository_root, snapshot_directory=snapshot)
    output = repository_root / OUTPUT_RELATIVE_PATH
    prompt_items = json.loads(
        (output / "prompt_manifest.json").read_text(encoding="utf-8")
    )["items"]
    canvas_items = json.loads(
        (output / "canvas_manifest.json").read_text(encoding="utf-8")
    )["items"]
    store = LocalPngArtifactStore(runtime_root)
    for item in canvas_items:
        data = (repository_root / item["repository_path"]).read_bytes()
        store.persist_png(
            item["artifact_store_path"],
            data,
            expected_width=WIDTH,
            expected_height=HEIGHT,
        )
    runtime = _runtime(snapshot)
    provider = DiffusersImageRenderer(
        identity=_provider_identity(),
        backend=LazyDiffusersBackend(runtime),
        artifact_store=store,
    )
    ledger_path = output / "call_ledger.json"
    _write_new(
        ledger_path,
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-call-ledger-v1",
                "expected_calls": 10,
                "attempted_calls": 0,
                "retries": 0,
                "fallbacks": 0,
                "entries": [],
            }
        ),
    )
    image_items: list[Mapping[str, Any]] = []
    outcomes_by_variant: dict[str, list[Any]] = {"visible": [], "absent": []}
    for prompt_item in prompt_items:
        request = _strict_request(prompt_item["request"])
        call = _strict_call(prompt_item["call_spec"])
        if request != _strict_request(prompt_item["request"]):
            raise ValueError("Sealed request replay is unstable")
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["attempted_calls"] += 1
        ledger["entries"].append(
            {
                "call_index": prompt_item["call_index"],
                "variant": prompt_item["variant"],
                "slot": prompt_item["slot"],
                "request_id": request.request_id,
                "call_id": call.call_id,
                "status": "started",
            }
        )
        _replace_json(ledger_path, ledger)
        outcome = provider.render(request, call=call)
        repository_path: str | None = None
        size_bytes: int | None = None
        if outcome.artifact is not None:
            data = provider.read_artifact_bytes(outcome.artifact)
            relative = Path("images") / prompt_item["variant"] / (
                f"{prompt_item['slot']}.png"
            )
            _write_new(output / relative, data)
            if _sha256_bytes(data) != outcome.artifact.content_sha256:
                raise ValueError("Repository render bytes differ from provider artifact")
            repository_path = (OUTPUT_RELATIVE_PATH / relative).as_posix()
            size_bytes = len(data)
        entry = _manifest_entry(
            prompt_item=prompt_item,
            request=request,
            call=call,
            outcome=outcome,
            repository_path=repository_path,
            size_bytes=size_bytes,
        )
        image_items.append(entry)
        outcomes_by_variant[prompt_item["variant"]].append(outcome)
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        ledger["entries"][-1] = {
            "call_index": prompt_item["call_index"],
            "variant": prompt_item["variant"],
            "slot": prompt_item["slot"],
            "request_id": request.request_id,
            "request_hash": request.content_hash(),
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "status": outcome.call_record.status,
            "outcome_id": outcome.outcome_id,
            "output_artifact_ids": outcome.call_record.output_artifact_ids,
            "failure_code": outcome.failure_code,
        }
        _replace_json(ledger_path, ledger)
    if len(image_items) != 10:
        raise RuntimeError("O2 did not attempt exactly ten image-model calls")
    successful = tuple(item for item in image_items if item["artifact"] is not None)
    if len(successful) != 10:
        raise RuntimeError("O2 did not produce all ten required images")
    _write_new(
        output / "image_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-image-manifest-v1",
                "image_model_call_count": 10,
                "generated_image_count": 10,
                "selection_performed": False,
                "items": image_items,
            }
        ),
    )
    for variant in ("visible", "absent"):
        items = tuple(outcomes_by_variant[variant])
        batch = ImageRenderBatchOutcome.create(
            source_spec_ids=tuple(item.request.source_spec_id for item in items),
            root_seed=314159,
            status="succeeded",
            items=items,
            warnings=(
                "research_only_semantic_canvas_conditioning",
                "zero_native_decision_influence",
            ),
        )
        _write_new(
            output / "cases" / variant / "render_batch.json",
            canonical_json_bytes(batch),
        )
    image_by_key = {
        (item["variant"], item["slot"]): item for item in image_items
    }
    canvas_by_key = {
        (item["variant"], item["slot"]): item for item in canvas_items
    }
    aliases: list[Mapping[str, Any]] = []
    for variant in ("visible", "absent"):
        current = image_by_key[(variant, "current")]
        artifact = current["artifact"]
        aliases.append(
            {
                "schema_version": "triad-vis-o2-image-alias-v1",
                "variant": variant,
                "slot": "credit_no_response",
                "alias_of_slot": "current",
                "image_id": artifact["image_id"],
                "content_sha256": artifact["content_sha256"],
                "repository_image_path": current["repository_image_path"],
                "repository_image_path_from_report": (
                    Path(current["repository_image_path"])
                    .relative_to(OUTPUT_RELATIVE_PATH)
                    .as_posix()
                ),
                "canvas": canvas_by_key[(variant, "credit_no_response")],
                "image_model_calls": 0,
                "exact_current_artifact_reuse": True,
            }
        )
    _write_new(
        output / "aliases.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-o2-alias-manifest-v1",
                "alias_count": 2,
                "items": aliases,
            }
        ),
    )
    for item in image_items:
        item["repository_image_path_from_report"] = (
            Path(item["repository_image_path"])
            .relative_to(OUTPUT_RELATIVE_PATH)
            .as_posix()
        )
    alias_by_key = {(item["variant"], item["slot"]): item for item in aliases}
    sheet_root = output / "sheets"
    contact_records: dict[str, Mapping[str, Any]] = {}
    for variant in ("visible", "absent"):
        cells: list[tuple[str, Path]] = []
        for slot in SLOT_ORDER:
            if slot == "credit_no_response":
                image_path = repository_root / alias_by_key[(variant, slot)][
                    "repository_image_path"
                ]
            else:
                image_path = repository_root / image_by_key[(variant, slot)][
                    "repository_image_path"
                ]
            cells.append((slot, image_path))
        path = sheet_root / f"{variant}_contact.png"
        _sheet(cells, path, columns=3)
        contact_records[variant] = {
            "path": path.relative_to(output).as_posix(),
            "sha256": _file_sha256(path),
        }
    pair_cells: list[tuple[str, Path]] = []
    for variant in ("visible", "absent"):
        for slot in SLOT_ORDER:
            if slot == "credit_no_response":
                image_path = repository_root / alias_by_key[(variant, slot)][
                    "repository_image_path"
                ]
            else:
                image_path = repository_root / image_by_key[(variant, slot)][
                    "repository_image_path"
                ]
            pair_cells.append((f"{variant}: {slot}", image_path))
    pair_path = sheet_root / "public_credit_pair_comparison.png"
    _sheet(pair_cells, pair_path, columns=6)
    pair_record = {
        "path": pair_path.relative_to(output).as_posix(),
        "sha256": _file_sha256(pair_path),
    }
    canvas_render_pairs: dict[str, Mapping[str, Any]] = {}
    for variant in ("visible", "absent"):
        for slot in SLOT_ORDER:
            canvas_path = repository_root / canvas_by_key[(variant, slot)][
                "repository_path"
            ]
            if slot == "credit_no_response":
                image_path = repository_root / alias_by_key[(variant, slot)][
                    "repository_image_path"
                ]
            else:
                image_path = repository_root / image_by_key[(variant, slot)][
                    "repository_image_path"
                ]
            path = sheet_root / "canvas_render" / f"{variant}_{slot}.png"
            _sheet((("semantic canvas", canvas_path), ("model render", image_path)), path, columns=2)
            canvas_render_pairs[f"{variant}/{slot}"] = {
                "path": path.relative_to(output).as_posix(),
                "sha256": _file_sha256(path),
            }
    sheet_manifest = {
        "schema_version": "triad-vis-o2-sheet-manifest-v1",
        "visible_contact": contact_records["visible"],
        "absent_contact": contact_records["absent"],
        "pair_comparison": pair_record,
        "canvas_render_pairs": canvas_render_pairs,
    }
    _write_new(output / "sheet_manifest.json", canonical_json_bytes(sheet_manifest))
    _write_new(
        output / "report.md",
        _report(image_items, aliases, sheet_manifest).encode("utf-8"),
    )
    summary = {
        "schema_version": "triad-vis-o2-summary-v1",
        "phase": "TRIAD-VIS-O2",
        "status": "complete_awaiting_human_visual_review",
        "semantic_canvas_count": 12,
        "visible_scene_slots": 12,
        "image_model_calls": 10,
        "successful_images": 10,
        "no_response_aliases": 2,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "racio_vision": 0,
        "visual_valuation_authority": False,
        "private_thinking_persisted": False,
        "prompt_changed_after_first_render": False,
        "report_path": (OUTPUT_RELATIVE_PATH / "report.md").as_posix(),
    }
    _write_new(output / "summary.json", canonical_json_bytes(summary))
    return summary


def _contains_absolute_path(text: str) -> bool:
    return bool(re.search(r"(?:[A-Za-z]:[\\/]|/home/|/Users/|\\\\Users\\\\)", text))


def _private_key_hits(value: Any, path: str = "$") -> tuple[str, ...]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in {
                "thinking",
                "thoughts",
                "reasoning_content",
                "chain_of_thought",
            }:
                hits.append(f"{path}.{key}")
            hits.extend(_private_key_hits(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_private_key_hits(item, f"{path}[{index}]"))
    return tuple(hits)


def cold_verify(
    repository_root: Path,
    *,
    snapshot_directory: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    output = repository_root / OUTPUT_RELATIVE_PATH
    seal_result = verify_seal(repository_root, snapshot_directory=snapshot_directory)
    ledger = json.loads((output / "call_ledger.json").read_text(encoding="utf-8"))
    images = json.loads((output / "image_manifest.json").read_text(encoding="utf-8"))
    aliases = json.loads((output / "aliases.json").read_text(encoding="utf-8"))
    canvases = json.loads((output / "canvas_manifest.json").read_text(encoding="utf-8"))
    if ledger["attempted_calls"] != 10 or len(ledger["entries"]) != 10:
        raise ValueError("O2 cold verification requires exactly ten attempts")
    if any(item["status"] != "succeeded" for item in ledger["entries"]):
        raise ValueError("O2 call ledger contains a failed render")
    if len(images["items"]) != 10 or images["selection_performed"]:
        raise ValueError("O2 image manifest must preserve all ten unselected images")
    for item in images["items"]:
        path = repository_root / item["repository_image_path"]
        if _file_sha256(path) != item["artifact"]["content_sha256"]:
            raise ValueError(f"O2 image hash mismatch: {item['repository_image_path']}")
    if len(canvases["items"]) != 12:
        raise ValueError("O2 canvas manifest does not contain twelve artifacts")
    for item in canvases["items"]:
        if _file_sha256(repository_root / item["repository_path"]) != item[
            "content_sha256"
        ]:
            raise ValueError("O2 semantic canvas hash mismatch")
    canvas_by_key = {
        (item["variant"], item["slot"]): item for item in canvases["items"]
    }
    image_by_key = {
        (item["variant"], item["slot"]): item for item in images["items"]
    }
    for alias in aliases["items"]:
        current = image_by_key[(alias["variant"], "current")]
        if (
            alias["image_id"] != current["artifact"]["image_id"]
            or alias["content_sha256"] != current["artifact"]["content_sha256"]
            or alias["repository_image_path"] != current["repository_image_path"]
            or canvas_by_key[(alias["variant"], "credit_no_response")][
                "content_sha256"
            ]
            != canvas_by_key[(alias["variant"], "current")]["content_sha256"]
        ):
            raise ValueError("No-response alias does not exactly reuse current")
    for path in output.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".md"}:
            text = path.read_text(encoding="utf-8")
            if _contains_absolute_path(text):
                raise ValueError(f"Local absolute path persisted in {path.name}")
            if path.suffix.lower() == ".json":
                hits = _private_key_hits(json.loads(text))
                if hits:
                    raise ValueError(f"Raw private-thinking keys persisted: {hits}")
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    expected = {
        "semantic_canvas_count": 12,
        "visible_scene_slots": 12,
        "image_model_calls": 10,
        "successful_images": 10,
        "no_response_aliases": 2,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "racio_vision": 0,
        "private_thinking_persisted": False,
        "prompt_changed_after_first_render": False,
    }
    for key, expected_value in expected.items():
        if summary.get(key) != expected_value:
            raise ValueError(f"O2 summary invariant failed: {key}")
    sheet_manifest = json.loads(
        (output / "sheet_manifest.json").read_text(encoding="utf-8")
    )
    if len(sheet_manifest["canvas_render_pairs"]) != 12:
        raise ValueError("O2 lacks twelve canvas/render comparison sheets")
    return {
        "status": "passed",
        "o1_files_verified": seal_result["o1_files_verified"],
        "canvas_artifacts": 12,
        "image_model_attempts": 10,
        "successful_images": 10,
        "no_response_aliases": 2,
        "absolute_paths_found": 0,
        "raw_private_thinking_keys_found": 0,
        "text_model_calls": 0,
        "native_decision_influence": 0,
    }


__all__ = [
    "CALL_ORDER",
    "CASE_ORDER",
    "EXPECTED_BASE_COMMIT",
    "OUTPUT_RELATIVE_PATH",
    "SEEDS",
    "SLOT_ORDER",
    "SemanticCanvasArtifactV1",
    "VisualIdentityAnchorV1",
    "VisualTransitionSpecV1",
    "cold_verify",
    "execute",
    "identity_anchors",
    "seal",
    "transition_specs",
    "verify_seal",
]
