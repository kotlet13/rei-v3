"""TRIAD-VIS-M2 source-context-complete rendering of frozen M1R2 mosaics.

Research-only image rendering. This module never runs text models, Racio vision,
visual valuation, character replay, governance, or native processors.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, Self

from PIL import Image, ImageDraw
from pydantic import model_validator

from ..emocio.diffusers_renderer import (
    DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME,
    DiffusersImageRenderer,
    LazyDiffusersBackend,
    LocalPngArtifactStore,
)
from ..emocio.renderer import build_render_call_spec
from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from ..models.emocio import AttentionWeight, VisualSceneSpec
from ..models.provider import ProviderCallSpec, ProviderIdentity
from ..models.rendering import ImageRenderRequest, ImageSourceReference
from .triad_vis_m1r2 import (
    M1R_RELATIVE_PATH,
    OUTPUT_RELATIVE_PATH as M1R2_RELATIVE_PATH,
)
from .triad_vis_o1 import (
    MODEL_ID,
    MODEL_REVISION,
    SNAPSHOT_MANIFEST_SHA256,
    STYLE_DIRECTIVE,
    STYLE_ID,
    _file_sha256,
    _git,
    _provider_identity,
    _replace_json,
    _runtime,
    _sha256_bytes,
    _sheet,
    _write_new,
)


EXPECTED_BASE_COMMIT: Final = "ed92dbf8083f7c73a4805c305679f7186909c60a"
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-m2-2026-07-24"
)
HUMAN_REVIEW_RELATIVE_PATH: Final = (
    M1R2_RELATIVE_PATH / "human_visual_review.md"
)
M1_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-m1-2026-07-24"
)
O2_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o2-2026-07-24"
)
O1_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-o1-2026-07-24"
)
WIDTH: Final = 512
HEIGHT: Final = 512
STEPS: Final = 4
GUIDANCE: Final = 1.0
TIMEOUT_SECONDS: Final = 600.0
PIPELINE_REVISION: Final = "0.39.0"
MEETING_SEED: Final = 314159
PRIVATE_SEED: Final = 314160
VARIANTS: Final = ("visible", "absent")
CANVAS_ROLES: Final = (
    "present",
    "desired",
    "broken",
    "no_response_completion",
    "private_action",
    "private_result",
    "private_completion",
    "public_action",
    "public_result",
    "public_completion",
)
PROJECTION_BASES: Final = {
    "no_response_completion": (
        "self_centered_desired_image_denied",
        "competition_loss",
        "obstacle_persistence",
    ),
    "private_completion": (
        "delayed_attention",
        "possible_future_obstacle_removal",
        "gullibility",
        "delayed_desired_image_fulfilment",
    ),
    "public_completion": (
        "attention_gain",
        "imagined_competitive_victory",
        "imagined_obstacle_removal",
        "immediate_desired_image_fulfilment",
    ),
}

EvidenceModality = Literal[
    "observed_fact",
    "absent_constraint",
    "conditional_relation",
    "unresolved_realization",
]


class RenderContextItemV1(FrozenModel):
    """Source-complete context for one frozen source-addressed canvas."""

    schema_version: Literal["triad-render-context-item-v1"] = (
        "triad-render-context-item-v1"
    )
    canvas_id: NonEmptyId
    canvas_content_sha256: HashDigest
    source_case_id: NonEmptyId
    variant: Literal["visible", "absent"]
    semantic_role: NonEmptyId
    repository_canvas_path: NonEmptyText
    primary_support_record_ids: tuple[NonEmptyId, ...] = ()
    primary_trigger_record_ids: tuple[NonEmptyId, ...] = ()
    inherited_context_record_ids: tuple[NonEmptyId, ...] = ()
    negative_constraint_record_ids: tuple[NonEmptyId, ...] = ()
    evidence_modalities: Mapping[NonEmptyId, EvidenceModality]
    unresolved_realization_record_ids: tuple[NonEmptyId, ...] = ()
    render_projection_basis: tuple[NonEmptyId, ...] = ()
    clean_natural_prompt: NonEmptyText
    clean_natural_prompt_sha256: HashDigest
    seed: int
    panel_scopes: tuple[NonEmptyId, ...]
    derivation_statuses: tuple[NonEmptyId, ...]
    reality_claim_authorities: tuple[bool, ...]
    recognition_scope: NonEmptyId
    epistemic_classification: Literal["grounded", "imagined"]
    canvas_artifact_store_path: NonEmptyText
    render_key: HashDigest

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if bool(self.primary_support_record_ids) == bool(
            self.primary_trigger_record_ids
        ):
            raise ValueError("Canvas must use exactly one primary lineage class")
        if self.epistemic_classification == "imagined":
            if self.primary_support_record_ids:
                raise ValueError("Imagined canvas cannot use primary support")
            if any(self.reality_claim_authorities):
                raise ValueError("Imagined canvas cannot gain reality authority")
        elif self.primary_trigger_record_ids:
            raise ValueError("Grounded canvas cannot use primary triggers")
        if self.semantic_role == "private_action" or self.semantic_role == "private_result":
            if self.seed != PRIVATE_SEED:
                raise ValueError("Private-office canvas seed changed")
        elif self.seed != MEETING_SEED:
            raise ValueError("Meeting canvas seed changed")
        return self


class RenderContextManifestV1(FrozenModel):
    """Frozen context contract for all twenty M1R2 canvases."""

    schema_version: Literal["triad-render-context-manifest-v1"] = (
        "triad-render-context-manifest-v1"
    )
    phase: Literal["TRIAD-VIS-M2"] = "TRIAD-VIS-M2"
    source_manifest_path: NonEmptyText
    source_manifest_sha256: HashDigest
    evidence_manifest_path: NonEmptyText
    evidence_manifest_sha256: HashDigest
    conditional_evidence_policy: Mapping[str, Any]
    canvas_count: Literal[20] = 20
    unique_render_key_count: Literal[18] = 18
    items: tuple[RenderContextItemV1, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        if len(self.items) != 20:
            raise ValueError("M2 requires exactly twenty source-addressed canvases")
        if len({item.canvas_id for item in self.items}) != 20:
            raise ValueError("M2 canvas IDs must remain source-addressed")
        if len({item.render_key for item in self.items}) != 18:
            raise ValueError("M2 pre-call render-key dedup count must equal eighteen")
        return self


def _object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _json(path: Path) -> Mapping[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _human_review() -> bytes:
    return (
        "# TRIAD-VIS-M1R2 human visual review\n\n"
        "review_source: human_supplied\n\n"
        "flux_render_approval: true_with_pre_call_context_gate\n\n"
        "racio_vision_approval: false\n\n"
        "visual_valuation_authority: false\n\n"
        "native_decision_influence: 0\n\n"
        "Human adjudication:\n\n"
        "- evidence-record lineage: pass with inherited-context caveat;\n"
        "- grounded support / imagined trigger separation: pass;\n"
        "- depicted imagined world / grounded reality separation: pass;\n"
        "- visible recognition scope: pass;\n"
        "- absent recognition scope: pass;\n"
        "- absent audience support = not_applicable: pass;\n"
        "- manual-reference boundary: pass;\n"
        "- autonomous Emocio cognition: not claimed;\n"
        "- ready for controlled FLUX rendering: yes;\n"
        "- ready for Racio vision: no.\n"
    ).encode("utf-8")


def _repository_blob_inventory(
    repository_root: Path,
    relative_roots: Sequence[Path],
) -> tuple[Mapping[str, Any], ...]:
    paths: list[Path] = []
    for relative_root in relative_roots:
        root = repository_root / relative_root
        paths.extend(sorted(item for item in root.rglob("*") if item.is_file()))
    return tuple(
        {
            "path": path.relative_to(repository_root).as_posix(),
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(paths)
    )


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
            raise ValueError(f"Frozen prior evidence changed: {item['path']}")


def _flatten_panels(mosaic: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    panels: list[Mapping[str, Any]] = [
        mosaic["present_state"],
        mosaic["desired_counterfactual"],
        mosaic["broken_counterfactual"],
    ]
    for option in mosaic["options"]:
        panels.extend(
            (
                option["action_panel"],
                option["grounded_immediate_result_panel"],
                option["emocio_imagined_completion_panel"],
            )
        )
    return tuple(panels)


def _role_for_panel(panel: Mapping[str, Any]) -> str:
    path = Path(panel["canvas"]["repository_path"])
    return path.stem


def _load_source(
    repository_root: Path,
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    Mapping[tuple[str, str], Mapping[str, Any]],
    Mapping[tuple[str, str], Mapping[str, Any]],
]:
    mosaic_manifest = _json(repository_root / M1R2_RELATIVE_PATH / "mosaic_manifest.json")
    evidence_manifest = _json(
        repository_root / M1R2_RELATIVE_PATH / "evidence_record_manifest.json"
    )
    records = {
        (item["original_source_case_id"], item["evidence_id"]): item
        for item in evidence_manifest["records"]
    }
    panels: dict[tuple[str, str], Mapping[str, Any]] = {}
    for mosaic in mosaic_manifest["mosaics"]:
        variant = mosaic["variant"]
        for panel in _flatten_panels(mosaic):
            role = _role_for_panel(panel)
            key = (variant, role)
            existing = panels.get(key)
            if existing is None:
                panels[key] = panel
            elif existing["canvas"] != panel["canvas"]:
                raise ValueError(f"Canvas alias differs for {variant}/{role}")
    if len(panels) != 20:
        raise ValueError("Frozen M1R2 does not expose twenty source canvases")
    return mosaic_manifest, evidence_manifest, records, panels


def _record_ids(
    records: Mapping[tuple[str, str], Mapping[str, Any]],
    case_id: str,
    evidence_ids: Sequence[str],
) -> tuple[str, ...]:
    return tuple(records[(case_id, evidence_id)]["record_id"] for evidence_id in evidence_ids)


def _lineage_evidence_ids(role: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    primary = {
        "present": ("credit_ev_claim", "credit_ev_positions"),
        "desired": ("credit_ev_record", "credit_ev_recognition", "credit_ev_positions"),
        "broken": ("credit_ev_claim", "credit_ev_positions"),
        "no_response_completion": ("credit_ev_claim", "credit_ev_positions"),
        "private_action": ("credit_ev_record", "credit_ev_correction"),
        "private_result": ("credit_ev_record", "credit_ev_correction"),
        "private_completion": (
            "credit_ev_correction",
            "credit_ev_record",
            "credit_ev_recognition",
        ),
        "public_action": (
            "credit_ev_record",
            "credit_ev_correction",
            "credit_ev_positions",
        ),
        "public_result": (
            "credit_ev_record",
            "credit_ev_correction",
            "credit_ev_positions",
        ),
        "public_completion": (
            "credit_ev_record",
            "credit_ev_correction",
            "credit_ev_recognition",
            "credit_ev_positions",
        ),
    }[role]
    inherited = {
        "present": ("credit_ev_audience", "credit_ev_record"),
        "desired": ("credit_ev_audience", "credit_ev_claim"),
        "broken": ("credit_ev_audience",),
        "no_response_completion": ("credit_ev_audience", "credit_ev_recognition"),
        "private_action": ("credit_ev_claim", "credit_ev_positions"),
        "private_result": ("credit_ev_claim", "credit_ev_positions"),
        "private_completion": ("credit_ev_audience", "credit_ev_claim"),
        "public_action": ("credit_ev_audience", "credit_ev_claim"),
        "public_result": (
            "credit_ev_audience",
            "credit_ev_claim",
            "credit_ev_recognition",
        ),
        "public_completion": ("credit_ev_audience", "credit_ev_claim"),
    }[role]
    negative = (
        ("credit_ev_retaliation",)
        if role in {"public_action", "public_result", "public_completion"}
        else ()
    )
    return primary, inherited, negative


def _base_prompt() -> str:
    return (
        "Create a clear semi-realistic cinematic storyboard with a restrained "
        "natural appearance and simple composition. Use the supplied semantic "
        "canvas as the precise composition guide. Self wears a cobalt-blue blazer, "
        "white shirt, and no tie. The colleague wears a charcoal suit and burgundy "
        "tie. The leader wears a cream blazer over a dark blouse. "
    )


def _audience_prompt(variant: str) -> str:
    if variant == "visible":
        return (
            "Exactly six additional neutral adults are visible behind the three "
            "principal people. "
        )
    return (
        "Exactly zero additional adults are present; only the three principal "
        "people appear. "
    )


def _negative_prompt_text() -> str:
    return (
        "Preserve the recurring identities and clothing. Do not add or duplicate "
        "people. Show no physical violence, humiliation, retaliation, punishment, "
        "weapons, flames, medals, crowns, status symbols, logos, or readable text."
    )


def _natural_prompt(variant: str, role: str) -> str:
    base = _base_prompt()
    audience = _audience_prompt(variant)
    descriptions = {
        "present": (
            "In a modern meeting room, the colleague occupies the center beside a "
            "generic project diagram. Self remains at the edge while the leader "
            "watches the colleague. Everyone present attends to the colleague. "
        ),
        "desired": (
            "In the meeting room, self occupies the recognized central authorship "
            "position. A leader-confirmed official-record marker visibly connects "
            "the project to self, while the colleague stands secondary. "
        ),
        "broken": (
            "In the meeting room, the colleague remains the visibly recognized "
            "author. Self is smaller, distant, and partly outside the main frame, "
            "while the leader attends to the colleague. "
        ),
        "no_response_completion": (
            "In the imagined later meeting image, the colleague remains the sole "
            "visible author and self is more excluded at the edge. No correction "
            "is depicted. "
        ),
        "private_completion": (
            (
                "In an imagined later meeting, self pictures delayed recognition "
                "before the six neutral adults, while the leader appears to confirm "
                "the corrected official record and the colleague becomes secondary. "
            )
            if variant == "visible"
            else (
                "In an imagined later three-person meeting, self pictures a "
                "leader-level correction of the official record. The leader appears "
                "to confirm self while the colleague becomes secondary. "
            )
        ),
        "public_action": (
            "In the meeting room, self steps forward and presents a generic visual "
            "evidence card. Attention begins moving toward self while the official "
            "record marker stays neutral and pending. "
        ),
        "public_result": (
            "Immediately afterward in the meeting room, attention is on self and "
            "the colleague is secondary. The leader is still considering the "
            "evidence, and the official-record marker remains neutral and pending. "
        ),
        "public_completion": (
            (
                "In an imagined completion, self pictures recognition before the "
                "six neutral adults. Attention remains on self, the leader appears "
                "to confirm the official record, and the colleague is secondary. "
            )
            if variant == "visible"
            else (
                "In an imagined completion within the three-person meeting, self "
                "pictures recognition by the leader. Attention remains on self, the "
                "leader appears to confirm the official record, and the colleague "
                "is secondary. "
            )
        ),
    }
    if role == "private_action":
        scene = (
            "In a private office, only self and the leader sit together reviewing "
            "a generic visual evidence card. The colleague is not in this private "
            "scene, and exactly zero additional adults are present. "
        )
        return base + scene + _negative_prompt_text()
    if role == "private_result":
        scene = (
            "Immediately afterward in a private office, only self and the leader "
            "remain. The leader considers the generic evidence card while a neutral "
            "pending marker remains unresolved. The colleague is not in this private "
            "scene, and exactly zero additional adults are present. "
        )
        return base + scene + _negative_prompt_text()
    return base + descriptions[role] + audience + _negative_prompt_text()


def _prompt_gate(prompt: str, *, variant: str, role: str) -> tuple[str, ...]:
    lowered = prompt.lower()
    forbidden = (
        "credit_ev_",
        "record_",
        "sha256",
        "schema",
        "option_",
        "expected option",
        "winner",
        "best",
        "preferred",
        "safest",
        "{",
        "}",
        "=",
    )
    hits = tuple(token for token in forbidden if token in lowered)
    if re.search(r"\b0\.\d+\b", lowered):
        hits += ("numeric_attention_score",)
    if variant == "absent" and ("wider audience" in lowered or "wider group" in lowered):
        hits += ("absent_wider_audience",)
    required = (
        "cobalt-blue blazer",
        "white shirt",
        "no tie",
        "charcoal suit",
        "burgundy tie",
        "cream blazer",
        "dark blouse",
    )
    hits += tuple(f"missing:{token}" for token in required if token not in lowered)
    if role not in {"private_action", "private_result"}:
        audience_text = (
            "exactly six additional neutral adults"
            if variant == "visible"
            else "exactly zero additional adults"
        )
        if audience_text not in lowered:
            hits += ("missing:audience_count",)
    return hits


def _scene(
    *,
    context_id: str,
    role: str,
    option_id: str | None,
    record_ids: Sequence[str],
    prompt: str,
) -> VisualSceneSpec:
    kind = {
        "present": "current",
        "desired": "desired",
        "broken": "broken",
    }.get(role, "option_rollout")
    resolved_option = option_id if kind == "option_rollout" else None
    payload = {
        "scene_kind": kind,
        "option_id": resolved_option,
        "entities": ("colleague", "leader", "self"),
        "self_position": prompt,
        "attention_structure": (
            AttentionWeight(target="colleague", score=0.5),
            AttentionWeight(target="self", score=0.5),
        ),
        "group_belonging": "M1R2 source-addressed public-credit scene.",
        "status_relations": ("Epistemic status remains defined by the source panel.",),
        "movement": (prompt,),
        "composition": (prompt,),
        "attraction_markers": (),
        "obstacle_markers": (),
        "grounded_evidence_ids": tuple(sorted(set(record_ids))),
        "inferred_elements": (),
    }
    scene_id = content_id("triad_m2_scene", {"context_id": context_id, **payload})
    return VisualSceneSpec(scene_id=scene_id, **payload)


def _source_reference(item: Mapping[str, Any]) -> ImageSourceReference:
    return ImageSourceReference(
        image_id=item["canvas_id"],
        content_sha256=item["canvas_content_sha256"],
        media_type="image/png",
        path=item["canvas_artifact_store_path"],
        width=WIDTH,
        height=HEIGHT,
        grounded=False,
        originating_scene_spec_id=item["source_scene"]["scene_id"],
        originating_scene_spec_hash=_object_sha256(item["source_scene"]),
    )


def _option_for_role(role: str) -> str | None:
    if role.startswith("no_response"):
        return "credit_no_response"
    if role.startswith("private"):
        return "credit_private_evidence"
    if role.startswith("public"):
        return "credit_public_confront"
    return None


def _profile_hash() -> str:
    return _object_sha256(
        {
            "style_id": STYLE_ID,
            "style_directive": STYLE_DIRECTIVE,
            "status": "implementation_hypothesis",
        }
    )


def _render_key_payload(
    *,
    canvas_sha: str,
    prompt_sha: str,
    pipeline: Mapping[str, Any],
    seed: int,
) -> Mapping[str, Any]:
    return {
        "canvas_content_sha256": canvas_sha,
        "natural_prompt_sha256": prompt_sha,
        "style_profile_sha256": _profile_hash(),
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "pipeline": pipeline,
        "pipeline_revision": PIPELINE_REVISION,
        "seed": seed,
        "width": WIDTH,
        "height": HEIGHT,
        "num_inference_steps": STEPS,
        "guidance_scale": GUIDANCE,
        "conditioning_parameters": {
            "mode": "image_to_image",
            "conditioning_method": "reference_image",
            "strength": None,
            "negative_prompt": "",
        },
    }


def _context_and_requests(
    repository_root: Path,
    *,
    snapshot: Path,
) -> tuple[RenderContextManifestV1, tuple[Mapping[str, Any], ...]]:
    mosaic_manifest, evidence_manifest, records, panels = _load_source(repository_root)
    pipeline = _runtime(snapshot).pipeline_spec("image_to_image")
    pipeline_json = pipeline.model_dump(mode="json")
    provider = _provider_identity()
    contexts: list[RenderContextItemV1] = []
    request_sources: dict[str, Mapping[str, Any]] = {}
    for mosaic in mosaic_manifest["mosaics"]:
        variant = mosaic["variant"]
        case_id = mosaic["case_id"]
        recognition_scope = (
            "wider_group" if variant == "visible" else "three_person_meeting"
        )
        for role in CANVAS_ROLES:
            panel = panels[(variant, role)]
            canvas = panel["canvas"]
            primary_ids, inherited_ids, negative_ids = _lineage_evidence_ids(role)
            primary_record_ids = _record_ids(records, case_id, primary_ids)
            inherited_record_ids = _record_ids(records, case_id, inherited_ids)
            negative_record_ids = _record_ids(records, case_id, negative_ids)
            imagined = role.endswith("_completion")
            prompt = _natural_prompt(variant, role)
            hits = _prompt_gate(prompt, variant=variant, role=role)
            if hits:
                raise ValueError(f"Natural prompt gate failed for {variant}/{role}: {hits}")
            prompt_sha = _sha256_bytes(prompt.encode("utf-8"))
            seed = PRIVATE_SEED if role in {"private_action", "private_result"} else MEETING_SEED
            render_key = _object_sha256(
                _render_key_payload(
                    canvas_sha=canvas["content_sha256"],
                    prompt_sha=prompt_sha,
                    pipeline=pipeline_json,
                    seed=seed,
                )
            )
            panel_matches = tuple(
                candidate
                for candidate in _flatten_panels(mosaic)
                if candidate["canvas"]["canvas_id"] == canvas["canvas_id"]
            )
            modalities = {}
            all_record_ids = (
                *primary_record_ids,
                *inherited_record_ids,
                *negative_record_ids,
            )
            for record_id in dict.fromkeys(all_record_ids):
                record = next(
                    value
                    for value in evidence_manifest["records"]
                    if value["record_id"] == record_id
                )
                if record["evidence_id"] == "credit_ev_recognition":
                    modalities[record_id] = "conditional_relation"
                elif record["polarity"] == "absent":
                    modalities[record_id] = "absent_constraint"
                else:
                    modalities[record_id] = "observed_fact"
            recognition_records = tuple(
                record_id
                for record_id in all_record_ids
                if next(
                    value["evidence_id"]
                    for value in evidence_manifest["records"]
                    if value["record_id"] == record_id
                )
                == "credit_ev_recognition"
            )
            context = RenderContextItemV1(
                canvas_id=canvas["canvas_id"],
                canvas_content_sha256=canvas["content_sha256"],
                source_case_id=case_id,
                variant=variant,
                semantic_role=role,
                repository_canvas_path=canvas["repository_path"],
                primary_support_record_ids=() if imagined else primary_record_ids,
                primary_trigger_record_ids=primary_record_ids if imagined else (),
                inherited_context_record_ids=inherited_record_ids,
                negative_constraint_record_ids=negative_record_ids,
                evidence_modalities=modalities,
                unresolved_realization_record_ids=recognition_records,
                render_projection_basis=PROJECTION_BASES.get(role, ()),
                clean_natural_prompt=prompt,
                clean_natural_prompt_sha256=prompt_sha,
                seed=seed,
                panel_scopes=tuple(
                    sorted({item["panel_scope"] for item in panel_matches})
                ),
                derivation_statuses=tuple(
                    sorted({item["derivation_status"] for item in panel_matches})
                ),
                reality_claim_authorities=tuple(
                    sorted({item["reality_claim_authority"] for item in panel_matches})
                ),
                recognition_scope=recognition_scope,
                epistemic_classification="imagined" if imagined else "grounded",
                canvas_artifact_store_path=f"semantic_canvases/{canvas['canvas_id']}.png",
                render_key=render_key,
            )
            contexts.append(context)
            request_sources.setdefault(
                render_key,
                {
                    "context": context,
                    "canvas": canvas,
                    "option_id": _option_for_role(role),
                    "record_ids": tuple(dict.fromkeys(all_record_ids)),
                },
            )
    manifest = RenderContextManifestV1(
        source_manifest_path=(M1R2_RELATIVE_PATH / "mosaic_manifest.json").as_posix(),
        source_manifest_sha256=_file_sha256(
            repository_root / M1R2_RELATIVE_PATH / "mosaic_manifest.json"
        ),
        evidence_manifest_path=(
            M1R2_RELATIVE_PATH / "evidence_record_manifest.json"
        ).as_posix(),
        evidence_manifest_sha256=_file_sha256(
            repository_root / M1R2_RELATIVE_PATH / "evidence_record_manifest.json"
        ),
        conditional_evidence_policy={
            "credit_ev_recognition": {
                "conditional_relation": "present",
                "realization": "unresolved",
                "may_not_be_interpreted_as_completed_recognition": True,
            }
        },
        items=tuple(contexts),
    )
    request_items: list[Mapping[str, Any]] = []
    for call_index, render_key in enumerate(sorted(request_sources), start=1):
        source = request_sources[render_key]
        context: RenderContextItemV1 = source["context"]
        scene = _scene(
            context_id=context.canvas_id,
            role=context.semantic_role,
            option_id=source["option_id"],
            record_ids=source["record_ids"],
            prompt=context.clean_natural_prompt,
        )
        request = ImageRenderRequest.create(
            mode="image_to_image",
            source_spec=scene,
            provider=provider,
            pipeline=pipeline,
            seed=context.seed,
            prompt=context.clean_natural_prompt,
            negative_prompt="",
            width=WIDTH,
            height=HEIGHT,
            num_inference_steps=STEPS,
            guidance_scale=GUIDANCE,
            source_image=ImageSourceReference(
                image_id=context.canvas_id,
                content_sha256=context.canvas_content_sha256,
                media_type="image/png",
                path=context.canvas_artifact_store_path,
                width=WIDTH,
                height=HEIGHT,
                grounded=False,
                originating_scene_spec_id=scene.scene_id,
                originating_scene_spec_hash=scene.content_hash(),
            ),
            strength=None,
            conditioning_method="reference_image",
            prompt_language="en",
            style_id=STYLE_ID,
            profile_hash=_profile_hash(),
        )
        call = build_render_call_spec(request, timeout_seconds=TIMEOUT_SECONDS)
        request_items.append(
            {
                "call_index": call_index,
                "render_key": render_key,
                "representative_canvas_id": context.canvas_id,
                "representative_variant": context.variant,
                "representative_role": context.semantic_role,
                "source_scene": scene,
                "request": request,
                "call_spec": call,
            }
        )
    if len(request_items) != 18:
        raise ValueError(
            f"Pre-call render-key dedup count is {len(request_items)}, expected 18"
        )
    return manifest, tuple(request_items)


def _preflight(
    manifest: RenderContextManifestV1,
    requests: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    by_role = {(item.variant, item.semantic_role): item for item in manifest.items}
    private_action = {
        by_role[(variant, "private_action")].render_key for variant in VARIANTS
    }
    private_result = {
        by_role[(variant, "private_result")].render_key for variant in VARIANTS
    }
    checks = {
        "canvas_count_20": len(manifest.items) == 20,
        "render_keys_18": len({item.render_key for item in manifest.items}) == 18,
        "request_count_18": len(requests) == 18,
        "private_action_reused": len(private_action) == 1,
        "private_result_reused": len(private_result) == 1,
        "visible_audience_six": all(
            "exactly six additional neutral adults" in item.clean_natural_prompt.lower()
            for item in manifest.items
            if item.variant == "visible"
            and item.semantic_role not in {"private_action", "private_result"}
        ),
        "absent_audience_zero": all(
            "exactly zero additional adults" in item.clean_natural_prompt.lower()
            for item in manifest.items
            if item.variant == "absent"
            and item.semantic_role not in {"private_action", "private_result"}
        ),
        "absent_has_no_wider_audience": all(
            "wider audience" not in item.clean_natural_prompt.lower()
            and "wider group" not in item.clean_natural_prompt.lower()
            for item in manifest.items
            if item.variant == "absent"
        ),
        "imagined_has_no_authority": all(
            not any(item.reality_claim_authorities)
            for item in manifest.items
            if item.epistemic_classification == "imagined"
        ),
        "desired_confirmed_marker": all(
            "leader-confirmed official-record marker"
            in item.clean_natural_prompt.lower()
            for item in manifest.items
            if item.semantic_role == "desired"
        ),
        "public_result_pending_marker": all(
            "neutral and pending" in item.clean_natural_prompt.lower()
            for item in manifest.items
            if item.semantic_role == "public_result"
        ),
        "complete_lineage": all(
            (
                bool(item.primary_support_record_ids)
                or bool(item.primary_trigger_record_ids)
            )
            and bool(item.inherited_context_record_ids)
            for item in manifest.items
        ),
    }
    return {
        "schema_version": "triad-vis-m2-preflight-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "display_panels": 24,
        "source_addressed_canvases": 20,
        "unique_render_keys": 18,
        "expected_image_model_calls": 18,
        "text_model_calls": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
    }


def seal(
    repository_root: Path,
    *,
    snapshot_directory: Path,
) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    snapshot = snapshot_directory.resolve(strict=True)
    if _git(repository_root, "rev-parse", "HEAD") != EXPECTED_BASE_COMMIT:
        raise ValueError("TRIAD-VIS-M2 must seal from the approved M1R2 HEAD")
    output = repository_root / OUTPUT_RELATIVE_PATH
    if output.exists():
        raise FileExistsError("TRIAD-VIS-M2 output root already exists")
    review = repository_root / HUMAN_REVIEW_RELATIVE_PATH
    if review.exists():
        raise FileExistsError("M1R2 human review must be create-only")
    snapshot_manifest_path = snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    if _file_sha256(snapshot_manifest_path) != SNAPSHOT_MANIFEST_SHA256:
        raise ValueError("Pinned FLUX.2 snapshot manifest SHA-256 changed")
    snapshot_manifest = _json(snapshot_manifest_path)
    if (
        snapshot_manifest.get("repo_id") != MODEL_ID
        or snapshot_manifest.get("revision") != MODEL_REVISION
    ):
        raise ValueError("Pinned FLUX.2 snapshot identity changed")
    runtime = _runtime(snapshot)
    if runtime.conditioning_method("image_to_image") != "reference_image":
        raise ValueError("Pinned canvas-conditioning pipeline is unavailable")
    prior_inventory = _repository_blob_inventory(
        repository_root,
        (
            M1R2_RELATIVE_PATH,
            M1R_RELATIVE_PATH,
            M1_RELATIVE_PATH,
            O2_RELATIVE_PATH,
            O1_RELATIVE_PATH,
        ),
    )
    if len(
        tuple(
            item
            for item in prior_inventory
            if item["path"].startswith(M1R2_RELATIVE_PATH.as_posix())
        )
    ) != 27:
        raise ValueError("Frozen M1R2 inventory count changed before review")
    manifest, requests = _context_and_requests(repository_root, snapshot=snapshot)
    preflight = _preflight(manifest, requests)
    if not preflight["passed"]:
        raise ValueError(f"TRIAD-VIS-M2 pre-call gates failed: {preflight}")
    _write_new(review, _human_review())
    output.mkdir(parents=True)
    _write_new(output / "render_context_manifest.json", canonical_json_bytes(manifest))
    _write_new(
        output / "render_requests.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-m2-render-requests-v1",
                "request_count": 18,
                "items": requests,
            }
        ),
    )
    expected_entries = tuple(
        {
            "call_index": item["call_index"],
            "render_key": item["render_key"],
            "request_id": item["request"].request_id,
            "request_hash": item["request"].content_hash(),
            "call_id": item["call_spec"].call_id,
            "call_spec_hash": item["call_spec"].content_hash(),
            "status": "expected_not_started",
        }
        for item in requests
    )
    _write_new(
        output / "expected_call_ledger.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-m2-expected-call-ledger-v1",
                "expected_calls": 18,
                "retries": 0,
                "fallbacks": 0,
                "entries": expected_entries,
            }
        ),
    )
    _write_new(output / "preflight_report.json", canonical_json_bytes(preflight))
    _write_new(
        output / "prior_frozen_inventory.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-m2-prior-frozen-inventory-v1",
                "items": prior_inventory,
            }
        ),
    )
    code_paths = (
        Path("app/backend/rei/research/triad_vis_m2.py"),
        Path("scripts/run_triad_vis_m2.py"),
        Path("tests/rei/test_triad_vis_m2.py"),
    )
    frozen_files = (
        "render_context_manifest.json",
        "render_requests.json",
        "expected_call_ledger.json",
        "preflight_report.json",
        "prior_frozen_inventory.json",
    )
    seal_value = {
        "schema_version": "triad-vis-m2-pre-call-seal-v1",
        "phase": "TRIAD-VIS-M2",
        "base_commit": EXPECTED_BASE_COMMIT,
        "m1r2_manifest_sha256": _file_sha256(
            repository_root / M1R2_RELATIVE_PATH / "mosaic_manifest.json"
        ),
        "m1r2_human_review": {
            "path": HUMAN_REVIEW_RELATIVE_PATH.as_posix(),
            "sha256": _file_sha256(review),
            "review_source": "human_supplied",
        },
        "render_context_manifest_sha256": _file_sha256(
            output / "render_context_manifest.json"
        ),
        "canvas_hashes": {
            item.canvas_id: item.canvas_content_sha256 for item in manifest.items
        },
        "render_keys": tuple(item["render_key"] for item in requests),
        "natural_prompts": tuple(
            item["request"].prompt for item in requests
        ),
        "frozen_file_hashes": {
            name: _file_sha256(output / name) for name in frozen_files
        },
        "code_path_hashes": {
            path.as_posix(): _file_sha256(repository_root / path) for path in code_paths
        },
        "provider": _provider_identity(),
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "snapshot_manifest_sha256": SNAPSHOT_MANIFEST_SHA256,
        "snapshot_manifest_file_count": len(snapshot_manifest["files"]),
        "pipeline": runtime.pipeline_spec("image_to_image"),
        "pipeline_revision": PIPELINE_REVISION,
        "seed_schedule": {
            "meeting_scenes": MEETING_SEED,
            "private_office_scenes": PRIVATE_SEED,
        },
        "dimensions": {"width": WIDTH, "height": HEIGHT},
        "num_inference_steps": STEPS,
        "guidance_scale": GUIDANCE,
        "provider_call_specs": tuple(item["call_spec"] for item in requests),
        "expected_calls": 18,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "private_thinking_persisted": False,
        "output_root": OUTPUT_RELATIVE_PATH.as_posix(),
        "first_render_started": False,
    }
    _write_new(output / "pre_call_seal.json", canonical_json_bytes(seal_value))
    return {
        "status": "sealed",
        "seal_sha256": _file_sha256(output / "pre_call_seal.json"),
        "human_review_sha256": _file_sha256(review),
        "canvas_count": 20,
        "render_key_count": 18,
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
    seal_value = _json(output / "pre_call_seal.json")
    if seal_value["base_commit"] != EXPECTED_BASE_COMMIT:
        raise ValueError("Unexpected M2 seal base")
    if _file_sha256(
        snapshot / DIFFUSERS_SNAPSHOT_MANIFEST_FILENAME
    ) != SNAPSHOT_MANIFEST_SHA256:
        raise ValueError("Pinned snapshot manifest changed")
    review = repository_root / seal_value["m1r2_human_review"]["path"]
    if _file_sha256(review) != seal_value["m1r2_human_review"]["sha256"]:
        raise ValueError("Human-supplied M1R2 review changed")
    for name, digest in seal_value["frozen_file_hashes"].items():
        if _file_sha256(output / name) != digest:
            raise ValueError(f"Sealed M2 file changed: {name}")
    for name, digest in seal_value["code_path_hashes"].items():
        if _file_sha256(repository_root / name) != digest:
            raise ValueError(f"Sealed M2 code path changed: {name}")
    inventory = _json(output / "prior_frozen_inventory.json")["items"]
    _validate_inventory(repository_root, inventory)
    manifest = RenderContextManifestV1.model_validate_json(
        (output / "render_context_manifest.json").read_text(encoding="utf-8"),
        strict=True,
    )
    for item in manifest.items:
        path = repository_root / item.repository_canvas_path
        if _file_sha256(path) != item.canvas_content_sha256:
            raise ValueError(f"Frozen canvas changed: {item.repository_canvas_path}")
    requests = _json(output / "render_requests.json")["items"]
    if len(requests) != 18 or len({item["render_key"] for item in requests}) != 18:
        raise ValueError("Sealed render request count changed")
    return {
        "status": "verified",
        "prior_files_verified": len(inventory),
        "canvas_count": 20,
        "render_key_count": 18,
        "request_count": 18,
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


def _image_entry(
    *,
    request_item: Mapping[str, Any],
    outcome: Any,
    repository_path: str | None,
    size_bytes: int | None,
    contexts: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    return {
        "call_index": request_item["call_index"],
        "render_key": request_item["render_key"],
        "request": request_item["request"],
        "call_spec": request_item["call_spec"],
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
        "source_contexts": contexts,
        "epistemic_image_boundary": {
            "image_has_independent_reality_authority": False,
            "inherits_panel_epistemic_status": True,
            "imagined_style_signal_added": False,
        },
        "private_thinking_persisted": False,
        "native_decision_influence": 0,
    }


def _mapping(
    mosaic_manifest: Mapping[str, Any],
    contexts: Sequence[Mapping[str, Any]],
    images: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    context_by_canvas = {item["canvas_id"]: item for item in contexts}
    image_by_key = {item["render_key"]: item for item in images}
    rows = []
    for mosaic in mosaic_manifest["mosaics"]:
        for panel in _flatten_panels(mosaic):
            canvas = panel["canvas"]
            context = context_by_canvas[canvas["canvas_id"]]
            image = image_by_key[context["render_key"]]
            role = _role_for_panel(panel)
            alias_current = (
                panel["panel_scope"] in {"option_action", "grounded_immediate_result"}
                and role == "present"
            )
            rows.append(
                {
                    "case_id": mosaic["case_id"],
                    "variant": mosaic["variant"],
                    "panel_id": panel["panel_id"],
                    "panel_scope": panel["panel_scope"],
                    "derivation_status": panel["derivation_status"],
                    "reality_claim_authority": panel["reality_claim_authority"],
                    "canvas_id": canvas["canvas_id"],
                    "canvas_sha256": canvas["content_sha256"],
                    "render_key": context["render_key"],
                    "image_id": image["artifact"]["image_id"],
                    "image_sha256": image["artifact"]["content_sha256"],
                    "repository_image_path": image["repository_image_path"],
                    "exact_current_image_alias": alias_current,
                    "cross_variant_shared_render": context["semantic_role"]
                    in {"private_action", "private_result"},
                }
            )
    if len(rows) != 24:
        raise ValueError("M2 panel mapping must contain 24 display rows")
    return {
        "schema_version": "triad-vis-m2-panel-canvas-image-mapping-v1",
        "display_panel_count": 24,
        "source_addressed_canvas_count": 20,
        "generated_image_artifact_count": 18,
        "rows": rows,
    }


def _storyboard(
    cells: Sequence[tuple[str, Path]],
    destination: Path,
) -> None:
    columns = 4
    cell_width = 270
    image_size = 240
    label_height = 44
    rows = (len(cells) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * cell_width, rows * (image_size + label_height)), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (label, path) in enumerate(cells):
        image = Image.open(path).convert("RGB").resize((image_size, image_size))
        x = (index % columns) * cell_width + 15
        y = (index // columns) * (image_size + label_height)
        canvas.paste(image, (x, y))
        draw.rectangle((x, y, x + image_size, y + image_size), outline="#334155", width=2)
        draw.text((x, y + image_size + 8), label, fill="#111827")
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, format="PNG", optimize=True)


def _report(
    mapping: Mapping[str, Any],
    contexts: Sequence[Mapping[str, Any]],
    sheet_manifest: Mapping[str, Any],
) -> str:
    lines = [
        "# TRIAD-VIS-M2 - source-context-complete frozen Emocio mosaic renders",
        "",
        "Status: **render evidence awaiting human render-gap review**.",
        "",
        "These are controlled FLUX render artifacts conditioned by frozen M1R2 "
        "semantic canvases. They are not autonomous Emocio cognition, native "
        "processor output, visual valuation, option gold, training labels, runtime "
        "authority, or Racio-vision evidence.",
        "",
        "- Text-model calls: `0`",
        "- Image-model calls: `18`",
        "- Retries / fallbacks: `0 / 0`",
        "- Racio vision / visual valuation / character replay: `0 / 0 / 0`",
        "- Native-decision influence: `0`",
        "- Display panels / source canvases / generated images: `24 / 20 / 18`",
        "",
        f"![Visible contact sheet]({sheet_manifest['visible_contact']['path']})",
        "",
        f"![Absent contact sheet]({sheet_manifest['absent_contact']['path']})",
        "",
        f"![Visible storyboard graph]({sheet_manifest['visible_storyboard']['path']})",
        "",
        f"![Absent storyboard graph]({sheet_manifest['absent_storyboard']['path']})",
        "",
    ]
    for context in contexts:
        pair = sheet_manifest["canvas_render_pairs"][context["canvas_id"]]
        lines.extend(
            [
                f"## {context['variant']} / {context['semantic_role']}",
                "",
                f"![Canvas and render]({pair['path']})",
                "",
                f"- Canvas ID: `{context['canvas_id']}`",
                f"- Canvas SHA-256: `{context['canvas_content_sha256']}`",
                f"- Render key: `{context['render_key']}`",
                f"- Epistemic class: `{context['epistemic_classification']}`",
                f"- Reality authority: `{any(context['reality_claim_authorities'])}`",
                "",
                "Human render-gap review (intentionally blank):",
                "",
                "- canvas semantics preserved:",
                "- principal identities preserved:",
                "- audience count preserved:",
                "- role positions preserved:",
                "- attention direction preserved:",
                "- official marker preserved:",
                "- pending marker preserved:",
                "- grounded/imagined panel meaning preserved:",
                "- no extra person:",
                "- no duplicate person:",
                "- no unsupported aggression:",
                "- no unsupported status symbol:",
                "- no readable text artifact:",
                "- render introduces a new fact:",
                "- usable for later Racio vision:",
                "",
            ]
        )
    for variant in VARIANTS:
        lines.extend(
            [
                f"## {variant} option-lane review",
                "",
                "- action/result/completion remain distinct:",
                "- public grounded result remains distinct from desired:",
                "- imagined completion remains distinct from grounded result:",
                "- no-response completion does not overwrite grounded current state:",
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
        raise FileExistsError("M2 runtime artifact root must be create-only")
    if _git(repository_root, "status", "--short"):
        raise ValueError("M2 execution requires a clean committed seal")
    verify_seal(repository_root, snapshot_directory=snapshot)
    output = repository_root / OUTPUT_RELATIVE_PATH
    manifest = _json(output / "render_context_manifest.json")
    request_items = _json(output / "render_requests.json")["items"]
    contexts_by_key: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in manifest["items"]:
        contexts_by_key[item["render_key"]].append(item)
    store = LocalPngArtifactStore(runtime_root)
    for item in manifest["items"]:
        data = (repository_root / item["repository_canvas_path"]).read_bytes()
        store.persist_png(
            item["canvas_artifact_store_path"],
            data,
            expected_width=WIDTH,
            expected_height=HEIGHT,
        )
    provider = DiffusersImageRenderer(
        identity=_provider_identity(),
        backend=LazyDiffusersBackend(_runtime(snapshot)),
        artifact_store=store,
    )
    record_path = output / "provider_call_records.json"
    _write_new(
        record_path,
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-m2-provider-call-records-v1",
                "expected_calls": 18,
                "attempted_calls": 0,
                "retries": 0,
                "fallbacks": 0,
                "records": [],
            }
        ),
    )
    image_items: list[Mapping[str, Any]] = []
    for item in request_items:
        request = _strict_request(item["request"])
        call = _strict_call(item["call_spec"])
        records_value = _json(record_path)
        records_value["attempted_calls"] += 1
        records_value["records"].append(
            {
                "call_index": item["call_index"],
                "render_key": item["render_key"],
                "request_id": request.request_id,
                "call_id": call.call_id,
                "status": "started",
            }
        )
        _replace_json(record_path, records_value)
        outcome = provider.render(request, call=call)
        repository_image_path = None
        size_bytes = None
        if outcome.artifact is not None:
            data = provider.read_artifact_bytes(outcome.artifact)
            relative = Path("images") / f"render_{item['call_index']:02d}.png"
            _write_new(output / relative, data)
            if _sha256_bytes(data) != outcome.artifact.content_sha256:
                raise ValueError("Repository render bytes differ from provider artifact")
            repository_image_path = (OUTPUT_RELATIVE_PATH / relative).as_posix()
            size_bytes = len(data)
        entry = _image_entry(
            request_item=item,
            outcome=outcome,
            repository_path=repository_image_path,
            size_bytes=size_bytes,
            contexts=contexts_by_key[item["render_key"]],
        )
        image_items.append(entry)
        records_value = _json(record_path)
        records_value["records"][-1] = {
            "call_index": item["call_index"],
            "render_key": item["render_key"],
            "request_id": request.request_id,
            "request_hash": request.content_hash(),
            "call_id": call.call_id,
            "call_spec_hash": call.content_hash(),
            "status": outcome.call_record.status,
            "failure_code": outcome.failure_code,
            "output_artifact_ids": outcome.call_record.output_artifact_ids,
            "call_record": outcome.call_record.model_dump(mode="json"),
        }
        _replace_json(record_path, records_value)
    if len(image_items) != 18:
        raise RuntimeError("M2 did not attempt exactly eighteen image calls")
    _write_new(
        output / "image_manifest.json",
        canonical_json_bytes(
            {
                "schema_version": "triad-vis-m2-image-manifest-v1",
                "image_model_call_count": 18,
                "generated_image_count": sum(
                    item["artifact"] is not None for item in image_items
                ),
                "selection_performed": False,
                "items": image_items,
            }
        ),
    )
    failed = tuple(item for item in image_items if item["artifact"] is None)
    if failed:
        raise RuntimeError(
            "M2 image failures: "
            + ", ".join(
                f"{item['call_index']}:{item['failure_code']}" for item in failed
            )
        )
    mosaic_manifest = _json(
        repository_root / M1R2_RELATIVE_PATH / "mosaic_manifest.json"
    )
    mapping = _mapping(mosaic_manifest, manifest["items"], image_items)
    _write_new(
        output / "panel_to_canvas_to_image_mapping.json",
        canonical_json_bytes(mapping),
    )
    image_by_key = {
        item["render_key"]: repository_root / item["repository_image_path"]
        for item in image_items
    }
    panel_rows_by_variant: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in mapping["rows"]:
        panel_rows_by_variant[row["variant"]].append(row)
    sheet_manifest: dict[str, Any] = {
        "schema_version": "triad-vis-m2-sheet-manifest-v1",
        "canvas_render_pairs": {},
    }
    for variant in VARIANTS:
        rows = panel_rows_by_variant[variant]
        cells = tuple(
            (f"{row['panel_scope']}", repository_root / row["repository_image_path"])
            for row in rows
        )
        contact = output / "sheets" / f"{variant}_contact.png"
        _sheet(cells, contact, columns=4)
        sheet_manifest[f"{variant}_contact"] = {
            "path": contact.relative_to(output).as_posix(),
            "sha256": _file_sha256(contact),
        }
        graph = output / "sheets" / f"{variant}_storyboard_graph.png"
        _storyboard(cells, graph)
        sheet_manifest[f"{variant}_storyboard"] = {
            "path": graph.relative_to(output).as_posix(),
            "sha256": _file_sha256(graph),
        }
    for context in manifest["items"]:
        canvas_path = repository_root / context["repository_canvas_path"]
        image_path = image_by_key[context["render_key"]]
        pair_path = (
            output
            / "sheets"
            / "canvas_render"
            / f"{context['variant']}_{context['semantic_role']}.png"
        )
        _sheet(
            (("frozen semantic canvas", canvas_path), ("FLUX render", image_path)),
            pair_path,
            columns=2,
        )
        sheet_manifest["canvas_render_pairs"][context["canvas_id"]] = {
            "path": pair_path.relative_to(output).as_posix(),
            "sha256": _file_sha256(pair_path),
        }
    _write_new(output / "sheet_manifest.json", canonical_json_bytes(sheet_manifest))
    _write_new(
        output / "report.md",
        _report(mapping, manifest["items"], sheet_manifest).encode("utf-8"),
    )
    summary = {
        "schema_version": "triad-vis-m2-summary-v1",
        "phase": "TRIAD-VIS-M2",
        "status": "complete_awaiting_human_render_gap_review",
        "display_panels": 24,
        "source_addressed_canvases": 20,
        "generated_images": 18,
        "image_model_calls": 18,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
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
    records = _json(output / "provider_call_records.json")
    images = _json(output / "image_manifest.json")
    mapping = _json(output / "panel_to_canvas_to_image_mapping.json")
    sheets = _json(output / "sheet_manifest.json")
    summary = _json(output / "summary.json")
    if records["attempted_calls"] != 18 or len(records["records"]) != 18:
        raise ValueError("M2 requires exactly eighteen recorded attempts")
    if any(item["status"] != "succeeded" for item in records["records"]):
        raise ValueError("M2 contains a failed image attempt")
    if images["generated_image_count"] != 18 or len(images["items"]) != 18:
        raise ValueError("M2 image count differs")
    for item in images["items"]:
        path = repository_root / item["repository_image_path"]
        if _file_sha256(path) != item["artifact"]["content_sha256"]:
            raise ValueError(f"M2 image hash differs: {item['repository_image_path']}")
    if (
        mapping["display_panel_count"],
        mapping["source_addressed_canvas_count"],
        mapping["generated_image_artifact_count"],
    ) != (24, 20, 18):
        raise ValueError("M2 panel/canvas/image mapping differs")
    if len(sheets["canvas_render_pairs"]) != 20:
        raise ValueError("M2 requires twenty canvas/render comparison sheets")
    for value in (
        sheets["visible_contact"],
        sheets["absent_contact"],
        sheets["visible_storyboard"],
        sheets["absent_storyboard"],
        *sheets["canvas_render_pairs"].values(),
    ):
        if _file_sha256(output / value["path"]) != value["sha256"]:
            raise ValueError(f"M2 sheet hash differs: {value['path']}")
    json_files = tuple(output.rglob("*.json"))
    json_values = tuple(_json(path) for path in json_files)
    if any(_private_key_hits(value) for value in json_values):
        raise ValueError("M2 persisted private thinking")
    text = "\n".join(path.read_text(encoding="utf-8") for path in json_files)
    if _contains_absolute_path(text):
        raise ValueError("M2 contains an absolute local path")
    if summary["image_model_calls"] != 18 or any(
        summary[key] != 0
        for key in (
            "retries",
            "fallbacks",
            "text_model_calls",
            "racio_vision",
            "visual_valuation",
            "character_replay",
            "native_decision_influence",
        )
    ):
        raise ValueError("M2 call or authority accounting differs")
    return {
        **seal_result,
        "status": "passed",
        "image_model_calls": 18,
        "successful_images": 18,
        "retries": 0,
        "fallbacks": 0,
        "text_model_calls": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "display_panels": 24,
        "source_addressed_canvases": 20,
        "unique_render_artifacts": 18,
        "private_thinking_persisted": False,
        "absolute_paths_found": 0,
    }


__all__ = [
    "EXPECTED_BASE_COMMIT",
    "OUTPUT_RELATIVE_PATH",
    "RenderContextItemV1",
    "RenderContextManifestV1",
    "_context_and_requests",
    "_preflight",
    "cold_verify",
    "execute",
    "seal",
    "verify_seal",
]
