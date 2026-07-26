"""TRIAD-VIS-M1R2 variant-correct, epistemically explicit Emocio mosaic.

Research-only deterministic projection. No model, image, vision, valuation,
character, governance, or native-decision execution occurs here.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, Self

from PIL import Image, ImageDraw
from pydantic import model_validator

from ..ids import canonical_json_bytes, content_id
from ..models.common import FrozenModel, HashDigest, NonEmptyId, NonEmptyText
from .triad_vis_m1r import (
    IMAGINED_HORIZON,
    IMMEDIATE_HORIZON,
    deterministic_canvas_bytes,
)
from .triad_vis_o1 import _file_sha256, _git, _sheet, _write_new
from .triad_vis_o2 import identity_anchors


EXPECTED_BASE_COMMIT: Final = "8bc67f1472ccc6dd48a7b78f8fba98512b3f4b32"
M1R_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-m1r-2026-07-24"
)
SOURCE_CORPUS_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-route-isolation-p1-2026-07-23/"
    "route_isolation_corpus_candidate.json"
)
OUTPUT_RELATIVE_PATH: Final = Path(
    "Docs/evals/semantic_lab_v1/triad-vis-m1r2-2026-07-24"
)
VARIANTS: Final = ("visible", "absent")
OPTION_IDS: Final = (
    "credit_no_response",
    "credit_private_evidence",
    "credit_public_confront",
)
CANVAS_ROLES: Final = (
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


Polarity = Literal["present", "absent", "unknown"]
DerivationStatus = Literal[
    "direct_source",
    "source_synthesis",
    "implementation_neutral",
    "imagined_by_emocio",
]
PanelScope = Literal[
    "present_state",
    "desired_counterfactual",
    "broken_counterfactual",
    "option_action",
    "grounded_immediate_result",
    "emocio_imagined_completion",
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
    "not_applicable",
]
ProjectionBasisClaim = Literal[
    "self_centered_desired_image",
    "attention",
    "competition",
    "obstacle_removal",
    "gullibility",
    "immediate_desired_image_fulfilment",
]
RecognitionScope = Literal["wider_group", "three_person_meeting"]
Variant = Literal["visible", "absent"]


class EvidenceRecordV1(FrozenModel):
    schema_version: Literal["triad-original-evidence-record-v1"] = (
        "triad-original-evidence-record-v1"
    )
    record_id: NonEmptyId
    evidence_id: NonEmptyId
    canonical_fact_text: NonEmptyText
    operational_english: NonEmptyText
    original_source_case_id: NonEmptyId
    original_source_case_sha256: HashDigest
    evidence_sha256: HashDigest
    polarity: Polarity
    derivation_status: Literal["direct_source"] = "direct_source"

    @model_validator(mode="after")
    def validate_hashes(self) -> Self:
        evidence_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"record_id", "evidence_sha256"},
        )
        expected_sha = _object_sha256(evidence_payload)
        if self.evidence_sha256 != expected_sha:
            raise ValueError("Evidence SHA does not match canonical record")
        expected_id = content_id(
            "original_evidence_record",
            {**evidence_payload, "evidence_sha256": expected_sha},
        )
        if self.record_id != expected_id:
            raise ValueError("Evidence record ID is not canonical")
        return self


class DepictedImaginedStateV1(FrozenModel):
    schema_version: Literal["triad-depicted-imagined-state-v1"] = (
        "triad-depicted-imagined-state-v1"
    )
    official_attribution: Literal[
        "colleague_remains_sole_visible_author",
        "possible_later_self_correction",
        "self_recognized",
    ]
    attention_target: Literal["colleague", "leader_and_record", "self"]
    recognition_scope: RecognitionScope
    colleague_position: Literal["central", "present_secondary"]
    imagined_leader_outcome: Literal[
        "no_correction",
        "possible_later_correction",
        "confirming_self",
    ]


class GroundedRealityStatusV1(FrozenModel):
    schema_version: Literal["triad-grounded-reality-status-v1"] = (
        "triad-grounded-reality-status-v1"
    )
    actual_leader_decision: Literal["not_triggered", "pending", "unknown"]
    actual_official_correction: Literal["not_triggered", "pending", "unknown"]
    actual_audience_support: Literal["unknown", "not_applicable"]
    actual_colleague_response: Literal[
        "not_triggered",
        "not_observed",
        "unknown",
        "unknown_active",
    ]


class EpistemicCanvasV1(FrozenModel):
    schema_version: Literal["triad-epistemic-canvas-v1"] = (
        "triad-epistemic-canvas-v1"
    )
    canvas_id: NonEmptyId
    variant: Variant
    semantic_role: NonEmptyId
    source_case_id: NonEmptyId
    source_case_sha256: HashDigest
    evidence_record_ids: tuple[NonEmptyId, ...]
    evidence_role: Literal["support", "projection_trigger"]
    additional_person_count: Literal[0, 6]
    repository_path: NonEmptyText
    content_sha256: HashDigest
    generated_without_image_model: Literal[True] = True
    contains_readable_text: Literal[False] = False
    reality_claim_authority: bool

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        expected = content_id(
            "epistemic_canvas",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"canvas_id", "repository_path"},
            ),
        )
        if self.canvas_id != expected:
            raise ValueError("Epistemic canvas ID is not canonical")
        return self


class EpistemicPanelV1(FrozenModel):
    schema_version: Literal["triad-epistemic-panel-v1"] = (
        "triad-epistemic-panel-v1"
    )
    panel_id: NonEmptyId
    panel_scope: PanelScope
    option_id: NonEmptyId | None = None
    temporal_horizon: NonEmptyText | None = None
    semantic_summary: NonEmptyText
    source_case_id: NonEmptyId
    source_case_sha256: HashDigest
    derivation_status: DerivationStatus
    reality_claim_authority: bool
    supporting_evidence_ids: tuple[NonEmptyId, ...] | None = None
    supporting_evidence_record_ids: tuple[NonEmptyId, ...] | None = None
    triggering_evidence_ids: tuple[NonEmptyId, ...] | None = None
    triggering_evidence_record_ids: tuple[NonEmptyId, ...] | None = None
    projection_basis_claims: tuple[ProjectionBasisClaim, ...] = ()
    official_attribution_state: OfficialAttributionState | None = None
    leader_decision_state: LeaderDecisionState | None = None
    depicted_imagined_state: DepictedImaginedStateV1 | None = None
    grounded_reality_status: GroundedRealityStatusV1 | None = None
    canvas: EpistemicCanvasV1
    alias_of_panel_id: NonEmptyId | None = None

    @model_validator(mode="after")
    def validate_epistemic_layers(self) -> Self:
        option_scope = self.panel_scope in {
            "option_action",
            "grounded_immediate_result",
            "emocio_imagined_completion",
        }
        if option_scope != (self.option_id is not None):
            raise ValueError("Panel option scope and ID mismatch")
        if option_scope != (self.temporal_horizon is not None):
            raise ValueError("Temporal horizon is exclusive to option panels")
        imagined = self.panel_scope == "emocio_imagined_completion"
        if imagined:
            if (
                self.supporting_evidence_ids is not None
                or self.supporting_evidence_record_ids is not None
                or not self.triggering_evidence_ids
                or not self.triggering_evidence_record_ids
                or not self.projection_basis_claims
                or self.derivation_status != "imagined_by_emocio"
                or self.reality_claim_authority
                or self.depicted_imagined_state is None
                or self.grounded_reality_status is None
                or self.official_attribution_state is not None
                or self.leader_decision_state is not None
                or self.canvas.evidence_role != "projection_trigger"
            ):
                raise ValueError("Imagined completion mixes support and projection")
            if (
                self.canvas.evidence_record_ids
                != self.triggering_evidence_record_ids
            ):
                raise ValueError("Imagined canvas trigger lineage mismatch")
        else:
            if (
                not self.supporting_evidence_ids
                or not self.supporting_evidence_record_ids
                or self.triggering_evidence_ids is not None
                or self.triggering_evidence_record_ids is not None
                or self.projection_basis_claims
                or self.depicted_imagined_state is not None
                or self.grounded_reality_status is not None
                or self.official_attribution_state is None
                or self.leader_decision_state is None
                or self.canvas.evidence_role != "support"
            ):
                raise ValueError("Grounded panel lacks support lineage or status")
            if (
                self.canvas.evidence_record_ids
                != self.supporting_evidence_record_ids
            ):
                raise ValueError("Grounded canvas support lineage mismatch")
        if self.panel_scope in {
            "desired_counterfactual",
            "broken_counterfactual",
        } and self.leader_decision_state != "not_applicable":
            raise ValueError("Counterfactual leader decision must be not_applicable")
        expected = content_id(
            "epistemic_panel",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"panel_id"},
            ),
        )
        if self.panel_id != expected:
            raise ValueError("Epistemic panel ID is not canonical")
        return self


class EvidenceAddressedRelationV1(FrozenModel):
    schema_version: Literal["triad-evidence-addressed-relation-v1"] = (
        "triad-evidence-addressed-relation-v1"
    )
    relation_id: NonEmptyId
    option_id: NonEmptyId
    relation_type: RelationType
    state: RelationState
    source_case_id: NonEmptyId
    source_case_sha256: HashDigest
    supporting_evidence_ids: tuple[NonEmptyId, ...]
    supporting_evidence_record_ids: tuple[NonEmptyId, ...]
    derivation_status: Literal["source_synthesis"] = "source_synthesis"
    reality_claim_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_id(self) -> Self:
        expected = content_id(
            "evidence_addressed_relation",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"relation_id"},
            ),
        )
        if self.relation_id != expected:
            raise ValueError("Evidence-addressed relation ID is not canonical")
        return self


class EpistemicOptionSequenceV1(FrozenModel):
    schema_version: Literal["triad-epistemic-option-sequence-v1"] = (
        "triad-epistemic-option-sequence-v1"
    )
    option_id: NonEmptyId
    action_panel: EpistemicPanelV1
    grounded_immediate_result_panel: EpistemicPanelV1
    emocio_imagined_completion_panel: EpistemicPanelV1
    unresolved_relations: tuple[EvidenceAddressedRelationV1, ...]

    @model_validator(mode="after")
    def validate_sequence(self) -> Self:
        if any(
            panel.option_id != self.option_id
            for panel in (
                self.action_panel,
                self.grounded_immediate_result_panel,
                self.emocio_imagined_completion_panel,
            )
        ):
            raise ValueError("Sequence changed opaque option ID")
        if self.action_panel.panel_scope != "option_action":
            raise ValueError("Action panel scope mismatch")
        if (
            self.grounded_immediate_result_panel.panel_scope
            != "grounded_immediate_result"
        ):
            raise ValueError("Grounded result scope mismatch")
        if (
            self.emocio_imagined_completion_panel.panel_scope
            != "emocio_imagined_completion"
        ):
            raise ValueError("Imagined completion scope mismatch")
        return self


class EmocioVisualMosaicR2(FrozenModel):
    schema_version: Literal["emocio-visual-mosaic-m1r2"] = (
        "emocio-visual-mosaic-m1r2"
    )
    mosaic_id: NonEmptyId
    case_id: NonEmptyId
    source_case_sha256: HashDigest
    variant: Variant
    root_audience_count: Literal[0, 6]
    recognition_scope: RecognitionScope
    present_state: EpistemicPanelV1
    desired_counterfactual: EpistemicPanelV1
    broken_counterfactual: EpistemicPanelV1
    options: tuple[EpistemicOptionSequenceV1, ...]
    identity_anchor_ids: tuple[NonEmptyId, ...]
    model_calls: Literal[0] = 0
    image_calls: Literal[0] = 0
    character_replay: Literal[0] = 0
    native_decision_influence: Literal[0] = 0
    runtime_authority: Literal[False] = False

    @model_validator(mode="after")
    def validate_mosaic(self) -> Self:
        if tuple(option.option_id for option in self.options) != OPTION_IDS:
            raise ValueError("Mosaic changed opaque option scope")
        expected_audience = 6 if self.variant == "visible" else 0
        expected_scope = (
            "wider_group" if self.variant == "visible" else "three_person_meeting"
        )
        if (
            self.root_audience_count != expected_audience
            or self.recognition_scope != expected_scope
        ):
            raise ValueError("Mosaic audience variant is inconsistent")
        panels = (
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
            ),
        )
        if any(
            panel.source_case_id != self.case_id
            or panel.source_case_sha256 != self.source_case_sha256
            for panel in panels
        ):
            raise ValueError("Panel source-case address mismatch")
        desired_hash = self.desired_counterfactual.canvas.content_sha256
        if any(
            desired_hash
            in {
                option.action_panel.canvas.content_sha256,
                option.grounded_immediate_result_panel.canvas.content_sha256,
                option.emocio_imagined_completion_panel.canvas.content_sha256,
            }
            for option in self.options
        ):
            raise ValueError("Desired aliases an option layer")
        for option in self.options:
            result = option.grounded_immediate_result_panel
            if result.leader_decision_state not in {
                "not_triggered",
                "pending",
                "unknown",
            }:
                raise ValueError("Grounded result resolves leader decision")
            completion = option.emocio_imagined_completion_panel
            if completion.reality_claim_authority:
                raise ValueError("Imagined completion has reality authority")
            if completion.canvas.content_sha256 in {
                option.action_panel.canvas.content_sha256,
                result.canvas.content_sha256,
            }:
                raise ValueError("Completion aliases action or grounded result")
        public = self.options[2]
        audience_relation = next(
            relation
            for relation in public.unresolved_relations
            if relation.relation_type == "audience_support"
        )
        completion = public.emocio_imagined_completion_panel
        if self.root_audience_count == 0:
            if audience_relation.state != "not_applicable":
                raise ValueError("Absent audience support must be not_applicable")
            if (
                completion.depicted_imagined_state.recognition_scope
                != "three_person_meeting"
                or completion.grounded_reality_status.actual_audience_support
                != "not_applicable"
            ):
                raise ValueError("Absent completion escaped three-person scope")
            absent_text = " ".join(
                panel.semantic_summary
                for panel in panels
            ).lower()
            if any(
                term in absent_text
                for term in (
                    "wider audience",
                    "wider group",
                    "public admiration",
                    "six team",
                )
            ):
                raise ValueError("Absent summary introduces a wider audience")
            if any(panel.canvas.additional_person_count != 0 for panel in panels):
                raise ValueError("Absent canvas contains an additional person")
        else:
            if audience_relation.state != "unknown":
                raise ValueError("Visible audience support must remain unknown")
            if (
                completion.depicted_imagined_state.recognition_scope
                != "wider_group"
                or completion.grounded_reality_status.actual_audience_support
                != "unknown"
            ):
                raise ValueError("Visible completion lost wider-group scope")
        expected = content_id(
            "emocio_visual_mosaic_m1r2",
            self.model_dump(
                mode="python",
                round_trip=True,
                exclude={"mosaic_id"},
            ),
        )
        if self.mosaic_id != expected:
            raise ValueError("M1R2 mosaic ID is not canonical")
        return self


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _object_sha256(value: Any) -> str:
    return _sha256_bytes(canonical_json_bytes(value))


def _inventory(
    repository_root: Path,
    relative_root: Path,
    *,
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
        relative_path = item["path"]
        path = repository_root / relative_path
        if not path.is_file():
            raise ValueError(f"Frozen M1R evidence changed: {item['path']}")
        baseline_blob = subprocess.run(
            ("git", "show", f"{EXPECTED_BASE_COMMIT}:{relative_path}"),
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
        current_blob = subprocess.run(
            ("git", "show", f"HEAD:{relative_path}"),
            cwd=repository_root,
            check=True,
            capture_output=True,
        ).stdout
        unstaged = subprocess.run(
            ("git", "diff", "--quiet", "--", relative_path),
            cwd=repository_root,
            check=False,
        ).returncode
        staged = subprocess.run(
            ("git", "diff", "--cached", "--quiet", "--", relative_path),
            cwd=repository_root,
            check=False,
        ).returncode
        if (
            baseline_blob != current_blob
            or unstaged != 0
            or staged != 0
        ):
            raise ValueError(f"Frozen M1R evidence changed: {relative_path}")


def _polarity(evidence_id: str, variant: Variant) -> Polarity:
    if evidence_id == "credit_ev_audience":
        return "present" if variant == "visible" else "absent"
    if evidence_id == "credit_ev_retaliation":
        return "absent"
    if evidence_id == "credit_ev_recognition":
        return "unknown"
    return "present"


def evidence_records(
    repository_root: Path,
) -> tuple[tuple[EvidenceRecordV1, ...], Mapping[str, Mapping[str, Any]]]:
    corpus = json.loads(
        (repository_root / SOURCE_CORPUS_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    pair = next(
        item for item in corpus["pairs"] if item["pair_id"] == "public_credit_audience"
    )
    records = []
    sources: dict[str, Mapping[str, Any]] = {}
    for case in pair["variants"]:
        variant = case["variant_id"].removeprefix("audience_")
        source_sha = _object_sha256(case)
        source_id = case["case_id"]
        sources[source_id] = {
            "source_case_id": source_id,
            "source_case_sha256": source_sha,
            "variant": variant,
        }
        sl = {item["evidence_id"]: item["text"] for item in case["canonical_sl"]["facts"]}
        en = {item["evidence_id"]: item["text"] for item in case["operational_en"]["facts"]}
        if set(sl) != set(en) or any(not key.startswith("credit_ev_") for key in sl):
            raise ValueError("Original credit evidence IDs are not aligned")
        for evidence_id in sorted(sl):
            evidence_payload = {
                "schema_version": "triad-original-evidence-record-v1",
                "evidence_id": evidence_id,
                "canonical_fact_text": sl[evidence_id],
                "operational_english": en[evidence_id],
                "original_source_case_id": source_id,
                "original_source_case_sha256": source_sha,
                "polarity": _polarity(evidence_id, variant),
                "derivation_status": "direct_source",
            }
            evidence_sha = _object_sha256(evidence_payload)
            records.append(
                EvidenceRecordV1(
                    record_id=content_id(
                        "original_evidence_record",
                        {**evidence_payload, "evidence_sha256": evidence_sha},
                    ),
                    evidence_sha256=evidence_sha,
                    **evidence_payload,
                )
            )
    if len(records) != 16:
        raise ValueError("Expected eight credit evidence records per variant")
    return tuple(records), sources


def _records_for(
    records: Sequence[EvidenceRecordV1],
    *,
    case_id: str,
    evidence_ids: tuple[str, ...],
) -> tuple[EvidenceRecordV1, ...]:
    by_key = {
        (record.original_source_case_id, record.evidence_id): record
        for record in records
    }
    return tuple(by_key[(case_id, evidence_id)] for evidence_id in evidence_ids)


def _panel_evidence_ids(
    *,
    semantic_role: str,
    variant: Variant,
) -> tuple[str, ...]:
    if semantic_role == "present":
        return ("credit_ev_audience", "credit_ev_claim", "credit_ev_positions")
    if semantic_role == "desired":
        return (
            "credit_ev_audience",
            "credit_ev_positions",
            "credit_ev_recognition",
            "credit_ev_record",
        )
    if semantic_role == "broken":
        return ("credit_ev_claim", "credit_ev_positions")
    if semantic_role.startswith("private"):
        return ("credit_ev_correction", "credit_ev_record")
    if semantic_role.startswith("public"):
        return (
            "credit_ev_audience",
            "credit_ev_positions",
            "credit_ev_recognition",
            "credit_ev_record",
        )
    if semantic_role == "no_response_completion":
        return ("credit_ev_claim", "credit_ev_positions")
    raise ValueError(f"No evidence mapping for {semantic_role}/{variant}")


def _additional_person_count(*, variant: Variant, semantic_role: str) -> int:
    if semantic_role in {"private_action", "private_result"}:
        return 0
    return 6 if variant == "visible" else 0


def _canvas(
    *,
    variant: Variant,
    role: str,
    source: Mapping[str, Any],
    record_ids: tuple[str, ...],
    evidence_role: Literal["support", "projection_trigger"],
    path: str,
    data: bytes,
    authority: bool,
) -> EpistemicCanvasV1:
    payload = {
        "schema_version": "triad-epistemic-canvas-v1",
        "variant": variant,
        "semantic_role": role,
        "source_case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "evidence_record_ids": record_ids,
        "evidence_role": evidence_role,
        "additional_person_count": _additional_person_count(
            variant=variant,
            semantic_role=role,
        ),
        "repository_path": path,
        "content_sha256": _sha256_bytes(data),
        "generated_without_image_model": True,
        "contains_readable_text": False,
        "reality_claim_authority": authority,
    }
    id_payload = dict(payload)
    id_payload.pop("repository_path")
    return EpistemicCanvasV1(
        canvas_id=content_id("epistemic_canvas", id_payload),
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
    record_ids: tuple[str, ...],
    derivation: DerivationStatus,
    authority: bool,
    canvas: EpistemicCanvasV1,
    attribution: OfficialAttributionState | None = None,
    leader: LeaderDecisionState | None = None,
    alias_of: str | None = None,
    basis: tuple[ProjectionBasisClaim, ...] = (),
    depicted: DepictedImaginedStateV1 | None = None,
    grounded: GroundedRealityStatusV1 | None = None,
) -> EpistemicPanelV1:
    imagined = scope == "emocio_imagined_completion"
    payload = {
        "schema_version": "triad-epistemic-panel-v1",
        "panel_scope": scope,
        "option_id": option_id,
        "temporal_horizon": horizon,
        "semantic_summary": summary,
        "source_case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "derivation_status": derivation,
        "reality_claim_authority": authority,
        "supporting_evidence_ids": None if imagined else evidence_ids,
        "supporting_evidence_record_ids": None if imagined else record_ids,
        "triggering_evidence_ids": evidence_ids if imagined else None,
        "triggering_evidence_record_ids": record_ids if imagined else None,
        "projection_basis_claims": basis,
        "official_attribution_state": attribution,
        "leader_decision_state": leader,
        "depicted_imagined_state": depicted,
        "grounded_reality_status": grounded,
        "canvas": canvas,
        "alias_of_panel_id": alias_of,
    }
    return EpistemicPanelV1(
        panel_id=content_id("epistemic_panel", payload),
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
}


def _public_relations(variant: Variant) -> tuple[tuple[str, str], ...]:
    return (
        ("leader_decision", "pending"),
        ("official_correction", "pending"),
        ("public_attention", "shifted_to_self"),
        ("audience_support", "unknown" if variant == "visible" else "not_applicable"),
        ("colleague_response", "unknown_active"),
    )


def _relation(
    *,
    option_id: str,
    relation_type: RelationType,
    state: RelationState,
    source: Mapping[str, Any],
    evidence_ids: tuple[str, ...],
    record_ids: tuple[str, ...],
) -> EvidenceAddressedRelationV1:
    payload = {
        "schema_version": "triad-evidence-addressed-relation-v1",
        "option_id": option_id,
        "relation_type": relation_type,
        "state": state,
        "source_case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "supporting_evidence_ids": evidence_ids,
        "supporting_evidence_record_ids": record_ids,
        "derivation_status": "source_synthesis",
        "reality_claim_authority": False,
    }
    return EvidenceAddressedRelationV1(
        relation_id=content_id("evidence_addressed_relation", payload),
        **payload,
    )


def _imagined_states(
    *,
    option_id: str,
    variant: Variant,
) -> tuple[
    str,
    tuple[ProjectionBasisClaim, ...],
    DepictedImaginedStateV1,
    GroundedRealityStatusV1,
]:
    scope: RecognitionScope = (
        "wider_group" if variant == "visible" else "three_person_meeting"
    )
    audience_status = "unknown" if variant == "visible" else "not_applicable"
    if option_id == "credit_no_response":
        summary = (
            "Candidate projection: the colleague remains the sole visible author "
            "and self becomes more excluded "
            + (
                "before the wider group."
                if variant == "visible"
                else "within the three-person meeting."
            )
        )
        basis = (
            "self_centered_desired_image",
            "competition",
            "obstacle_removal",
        )
        depicted = DepictedImaginedStateV1(
            official_attribution="colleague_remains_sole_visible_author",
            attention_target="colleague",
            recognition_scope=scope,
            colleague_position="central",
            imagined_leader_outcome="no_correction",
        )
        grounded = GroundedRealityStatusV1(
            actual_leader_decision="not_triggered",
            actual_official_correction="not_triggered",
            actual_audience_support=audience_status,
            actual_colleague_response="not_triggered",
        )
    elif option_id == "credit_private_evidence":
        summary = (
            "Candidate projection: later public recognition before the six team "
            "members is imagined but delayed."
            if variant == "visible"
            else (
                "Candidate projection: a later leader-level correction is imagined "
                "within the three-person source scope."
            )
        )
        basis = (
            "self_centered_desired_image",
            "attention",
            "obstacle_removal",
            "gullibility",
        )
        depicted = DepictedImaginedStateV1(
            official_attribution="possible_later_self_correction",
            attention_target="leader_and_record",
            recognition_scope=scope,
            colleague_position="central",
            imagined_leader_outcome="possible_later_correction",
        )
        grounded = GroundedRealityStatusV1(
            actual_leader_decision="pending",
            actual_official_correction="pending",
            actual_audience_support=audience_status,
            actual_colleague_response="not_observed",
        )
    else:
        summary = (
            "Candidate projection: self imagines recognition before the wider group, "
            "with attention staying on self and the colleague secondary."
            if variant == "visible"
            else (
                "Candidate projection: self imagines recognition within the "
                "three-person meeting, with attention on self and the colleague "
                "secondary."
            )
        )
        basis = (
            "self_centered_desired_image",
            "attention",
            "competition",
            "obstacle_removal",
            "immediate_desired_image_fulfilment",
        )
        depicted = DepictedImaginedStateV1(
            official_attribution="self_recognized",
            attention_target="self",
            recognition_scope=scope,
            colleague_position="present_secondary",
            imagined_leader_outcome="confirming_self",
        )
        grounded = GroundedRealityStatusV1(
            actual_leader_decision="unknown",
            actual_official_correction="pending",
            actual_audience_support=audience_status,
            actual_colleague_response="unknown",
        )
    return summary, basis, depicted, grounded


def _build_mosaic(
    *,
    variant: Variant,
    source: Mapping[str, Any],
    records: Sequence[EvidenceRecordV1],
    canvases: Mapping[str, EpistemicCanvasV1],
) -> EmocioVisualMosaicR2:
    def lineage(role: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        ids = _panel_evidence_ids(semantic_role=role, variant=variant)
        found = _records_for(
            records,
            case_id=source["source_case_id"],
            evidence_ids=ids,
        )
        return ids, tuple(item.record_id for item in found)

    def grounded_panel(
        *,
        role: str,
        scope: PanelScope,
        option_id: str | None,
        horizon: str | None,
        summary: str,
        attribution: OfficialAttributionState,
        leader: LeaderDecisionState,
        authority: bool = False,
        alias_of: str | None = None,
    ) -> EpistemicPanelV1:
        ids, record_ids = lineage(role)
        return _panel(
            scope=scope,
            option_id=option_id,
            horizon=horizon,
            summary=summary,
            source=source,
            evidence_ids=ids,
            record_ids=record_ids,
            derivation="source_synthesis",
            authority=authority,
            canvas=canvases[role],
            attribution=attribution,
            leader=leader,
            alias_of=alias_of,
        )

    present = grounded_panel(
        role="present",
        scope="present_state",
        option_id=None,
        horizon=None,
        summary=(
            "Present meeting state: the colleague holds attention while official "
            "attribution remains unresolved."
        ),
        attribution="current_unresolved",
        leader="unknown",
        authority=True,
    )
    desired = grounded_panel(
        role="desired",
        scope="desired_counterfactual",
        option_id=None,
        horizon=None,
        summary=(
            "Desired counterfactual: an official-record marker assigns authorship "
            "to self; this is a target image, not an observed result."
        ),
        attribution="desired_self_recognized",
        leader="not_applicable",
    )
    broken = grounded_panel(
        role="broken",
        scope="broken_counterfactual",
        option_id=None,
        horizon=None,
        summary=(
            "Broken counterfactual: the colleague remains recognized while self is "
            "smaller and partly outside the frame."
        ),
        attribution="broken_colleague_recognized",
        leader="not_applicable",
    )
    sequences = []
    for option_id in OPTION_IDS:
        if option_id == "credit_no_response":
            ids = present.supporting_evidence_ids
            record_ids = present.supporting_evidence_record_ids
            action = _panel(
                scope="option_action",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary="No response holds the present scene unchanged.",
                source=source,
                evidence_ids=ids,
                record_ids=record_ids,
                derivation="source_synthesis",
                authority=False,
                canvas=present.canvas,
                attribution="unchanged",
                leader="not_triggered",
                alias_of=present.panel_id,
            )
            result = _panel(
                scope="grounded_immediate_result",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary="The grounded immediate result remains the present scene.",
                source=source,
                evidence_ids=ids,
                record_ids=record_ids,
                derivation="source_synthesis",
                authority=False,
                canvas=present.canvas,
                attribution="unchanged",
                leader="not_triggered",
                alias_of=present.panel_id,
            )
            completion_role = "no_response_completion"
        elif option_id == "credit_private_evidence":
            action = grounded_panel(
                role="private_action",
                scope="option_action",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary="Self and the leader privately review the evidence.",
                attribution="unchanged",
                leader="pending",
            )
            result = grounded_panel(
                role="private_result",
                scope="grounded_immediate_result",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary=(
                    "The leader considers the evidence; attribution remains unchanged "
                    "at the immediate horizon."
                ),
                attribution="unchanged",
                leader="pending",
            )
            completion_role = "private_completion"
        else:
            action = grounded_panel(
                role="public_action",
                scope="option_action",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary=(
                    "Self presents evidence during the meeting before six team members."
                    if variant == "visible"
                    else "Self presents evidence within the three-person meeting."
                ),
                attribution="pending",
                leader="pending",
            )
            result = grounded_panel(
                role="public_result",
                scope="grounded_immediate_result",
                option_id=option_id,
                horizon=IMMEDIATE_HORIZON,
                summary=(
                    "Attention shifts to self; official correction and leader decision "
                    "remain pending."
                ),
                attribution="pending",
                leader="pending",
            )
            completion_role = "public_completion"
        trigger_ids, trigger_record_ids = lineage(completion_role)
        completion_summary, basis, depicted, grounded = _imagined_states(
            option_id=option_id,
            variant=variant,
        )
        completion = _panel(
            scope="emocio_imagined_completion",
            option_id=option_id,
            horizon=IMAGINED_HORIZON,
            summary=completion_summary,
            source=source,
            evidence_ids=trigger_ids,
            record_ids=trigger_record_ids,
            derivation="imagined_by_emocio",
            authority=False,
            canvas=canvases[completion_role],
            basis=basis,
            depicted=depicted,
            grounded=grounded,
        )
        relation_pairs = (
            _public_relations(variant)
            if option_id == "credit_public_confront"
            else RELATION_STATES[option_id]
        )
        relation_evidence_ids = (
            action.supporting_evidence_ids
            if option_id == "credit_no_response"
            else result.supporting_evidence_ids
        )
        relation_record_ids = (
            action.supporting_evidence_record_ids
            if option_id == "credit_no_response"
            else result.supporting_evidence_record_ids
        )
        relations = tuple(
            _relation(
                option_id=option_id,
                relation_type=relation_type,
                state=state,
                source=source,
                evidence_ids=relation_evidence_ids,
                record_ids=relation_record_ids,
            )
            for relation_type, state in relation_pairs
        )
        sequences.append(
            EpistemicOptionSequenceV1(
                option_id=option_id,
                action_panel=action,
                grounded_immediate_result_panel=result,
                emocio_imagined_completion_panel=completion,
                unresolved_relations=relations,
            )
        )
    payload = {
        "schema_version": "emocio-visual-mosaic-m1r2",
        "case_id": source["source_case_id"],
        "source_case_sha256": source["source_case_sha256"],
        "variant": variant,
        "root_audience_count": 6 if variant == "visible" else 0,
        "recognition_scope": (
            "wider_group" if variant == "visible" else "three_person_meeting"
        ),
        "present_state": present,
        "desired_counterfactual": desired,
        "broken_counterfactual": broken,
        "options": tuple(sequences),
        "identity_anchor_ids": tuple(item.subject_id for item in identity_anchors()),
        "model_calls": 0,
        "image_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "runtime_authority": False,
    }
    return EmocioVisualMosaicR2(
        mosaic_id=content_id("emocio_visual_mosaic_m1r2", payload),
        **payload,
    )


def _display_panels(
    mosaic: EmocioVisualMosaicR2,
) -> tuple[tuple[str, EpistemicPanelV1], ...]:
    items = [
        ("current", mosaic.present_state),
        ("desired", mosaic.desired_counterfactual),
        ("broken", mosaic.broken_counterfactual),
    ]
    labels = {
        "credit_no_response": "no-response",
        "credit_private_evidence": "private",
        "credit_public_confront": "public",
    }
    for option in mosaic.options:
        label = labels[option.option_id]
        items.extend(
            (
                (f"{label}/action", option.action_panel),
                (f"{label}/grounded", option.grounded_immediate_result_panel),
                (f"{label}/imagined", option.emocio_imagined_completion_panel),
            )
        )
    return tuple(items)


def _storyboard_graph(
    *,
    mosaic: EmocioVisualMosaicR2,
    repository_root: Path,
    destination: Path,
) -> None:
    canvas = Image.new("RGB", (1480, 1530), "white")
    draw = ImageDraw.Draw(canvas)

    def paste(panel: EpistemicPanelV1, x: int, y: int, label: str) -> None:
        with Image.open(repository_root / panel.canvas.repository_path) as source:
            rendered = source.convert("RGB").resize((230, 230))
        canvas.paste(rendered, (x, y))
        draw.rectangle((x, y, x + 230, y + 230), outline=(45, 50, 55), width=2)
        draw.text((x, y - 20), label, fill="black")

    draw.text(
        (20, 12),
        f"{mosaic.case_id} | variant={mosaic.variant}, "
        f"recognition_scope={mosaic.recognition_scope}",
        fill="black",
    )
    paste(mosaic.present_state, 30, 65, "PRESENT")
    paste(mosaic.desired_counterfactual, 330, 65, "DESIRED REFERENCE")
    paste(mosaic.broken_counterfactual, 630, 65, "BROKEN REFERENCE")
    draw.multiline_text(
        (930, 75),
        "Reference states\nNo option horizon\nDesired/broken leader decision:\n"
        "not_applicable",
        fill="black",
        spacing=5,
    )
    for option, y in zip(mosaic.options, (395, 755, 1115)):
        paste(option.action_panel, 30, y, f"{option.option_id}: ACTION")
        paste(
            option.grounded_immediate_result_panel,
            330,
            y,
            "GROUNDED RESULT",
        )
        paste(
            option.emocio_imagined_completion_panel,
            630,
            y,
            "IMAGINED COMPLETION",
        )
        for start, end, color in (
            (260, 325, (42, 103, 173)),
            (560, 625, (125, 25, 48)),
        ):
            draw.line((start, y + 115, end, y + 115), fill=color, width=4)
            draw.polygon(
                ((end, y + 115), (end - 12, y + 108), (end - 12, y + 122)),
                fill=color,
            )
        relations = "\n".join(
            f"{item.relation_type}: {item.state}"
            for item in option.unresolved_relations
        )
        completion = option.emocio_imagined_completion_panel
        grounded = completion.grounded_reality_status
        status = (
            "UNRESOLVED RELATIONS\n"
            f"{relations}\n\n"
            "IMAGINED PANEL VERSUS GROUNDED STATUS\n"
            f"leader: {grounded.actual_leader_decision}\n"
            f"correction: {grounded.actual_official_correction}\n"
            f"audience support: {grounded.actual_audience_support}\n"
            f"colleague: {grounded.actual_colleague_response}"
        )
        draw.rounded_rectangle(
            (920, y, 1450, y + 280),
            radius=8,
            fill=(244, 246, 247),
            outline=(100, 108, 115),
            width=2,
        )
        draw.multiline_text((940, y + 14), status, fill="black", spacing=5)
    draw.text(
        (30, 1500),
        "Blue: grounded sequence. Burgundy: human-authored Emocio hypothesis; "
        "reality_claim_authority=false.",
        fill="black",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"Storyboard graph exists: {destination}")
    canvas.save(destination, format="PNG", optimize=True)


def _report(
    *,
    mosaics: Sequence[EmocioVisualMosaicR2],
    sheets: Mapping[str, Mapping[str, Any]],
    evidence_manifest_sha256: str,
) -> str:
    lines = [
        "# TRIAD-VIS-M1R2 — variant-correct epistemic Emocio mosaic",
        "",
        "Status: **model-free candidate awaiting human visual review**.",
        "",
        "Manual-reference boundary:",
        "",
        "- Completions are human-authored source-grounded REI hypotheses.",
        "- They are not autonomous Emocio cognition.",
        "- They are not native processor output.",
        "- They are not visual valuation.",
        "- They are not option gold.",
        "- They are not training labels.",
        "- They have no runtime authority.",
        "",
        f"- Evidence-record manifest SHA-256: `{evidence_manifest_sha256}`",
        "- Model calls / image calls: `0 / 0`",
        "- Character replay / native-decision influence: `0 / 0`",
        "",
        "Grounded panels use `supporting_evidence_ids`. Imagined completions use "
        "`triggering_evidence_ids` and bounded `projection_basis_claims`; their "
        "depicted world is serialized separately from grounded reality status.",
        "",
    ]
    for mosaic in mosaics:
        record = sheets[mosaic.variant]
        lines.extend(
            [
                f"## {mosaic.case_id}",
                "",
                f"- Audience count: `{mosaic.root_audience_count}`",
                f"- Recognition scope: `{mosaic.recognition_scope}`",
                f"- Source case SHA-256: `{mosaic.source_case_sha256}`",
                "",
                f"![{mosaic.variant} contact sheet]({record['contact_path']})",
                "",
                f"![{mosaic.variant} storyboard graph]({record['graph_path']})",
                "",
                "| Option | Grounded result | Imagined depiction | Grounded status retained beside depiction |",
                "|---|---|---|---|",
            ]
        )
        for option in mosaic.options:
            result = option.grounded_immediate_result_panel
            completion = option.emocio_imagined_completion_panel
            depicted = completion.depicted_imagined_state
            grounded = completion.grounded_reality_status
            lines.append(
                f"| `{option.option_id}` | attribution=`{result.official_attribution_state}`; "
                f"leader=`{result.leader_decision_state}` | "
                f"attribution=`{depicted.official_attribution}`; "
                f"scope=`{depicted.recognition_scope}` | "
                f"leader=`{grounded.actual_leader_decision}`; "
                f"correction=`{grounded.actual_official_correction}`; "
                f"audience_support=`{grounded.actual_audience_support}` |"
            )
        lines.extend(
            [
                "",
                "Human review (intentionally blank):",
                "",
                "- Evidence-record lineage:",
                "- Evidence polarity:",
                "- Grounded support wording:",
                "- Projection-trigger wording:",
                "- Depicted imagined state:",
                "- Grounded reality status:",
                "- Variant-correct recognition scope:",
                "- Audience-support relation:",
                "- Absent canvas contains only three principal people:",
                "- Visible and absent completion texts are meaningfully distinct:",
                "- Desired/action/grounded/completion distinction:",
                "- Manual-reference boundary is clear:",
                "- Unsupported inference:",
                "- Ready for FLUX rendering:",
                "- Ready for Racio vision:",
                "",
            ]
        )
    return "\n".join(lines)


def build(repository_root: Path) -> Mapping[str, Any]:
    repository_root = repository_root.resolve()
    if _git(repository_root, "rev-parse", "HEAD") != EXPECTED_BASE_COMMIT:
        raise ValueError("TRIAD-VIS-M1R2 must start from approved M1R HEAD")
    output = repository_root / OUTPUT_RELATIVE_PATH
    if output.exists():
        raise FileExistsError("TRIAD-VIS-M1R2 output root already exists")
    m1r_inventory = _inventory(
        repository_root,
        M1R_RELATIVE_PATH,
        expected_count=28,
    )
    records, source_by_case = evidence_records(repository_root)
    evidence_manifest = {
        "schema_version": "triad-vis-m1r2-evidence-record-manifest-v1",
        "source_corpus": {
            "path": SOURCE_CORPUS_RELATIVE_PATH.as_posix(),
            "sha256": _file_sha256(repository_root / SOURCE_CORPUS_RELATIVE_PATH),
        },
        "record_count": len(records),
        "records": records,
    }
    evidence_manifest_sha = _object_sha256(evidence_manifest)
    output.mkdir(parents=True)
    mosaics = []
    sheets: dict[str, Mapping[str, Any]] = {}
    for variant in VARIANTS:
        case_id = f"public_credit_audience_{variant}"
        source = source_by_case[case_id]
        canvases = {}
        for role in CANVAS_ROLES:
            data = deterministic_canvas_bytes(variant=variant, semantic_role=role)
            evidence_ids = _panel_evidence_ids(
                semantic_role=role,
                variant=variant,
            )
            role_records = _records_for(
                records,
                case_id=case_id,
                evidence_ids=evidence_ids,
            )
            relative = OUTPUT_RELATIVE_PATH / "canvases" / variant / f"{role}.png"
            _write_new(repository_root / relative, data)
            imagined = role.endswith("_completion")
            canvases[role] = _canvas(
                variant=variant,
                role=role,
                source=source,
                record_ids=tuple(record.record_id for record in role_records),
                evidence_role="projection_trigger" if imagined else "support",
                path=relative.as_posix(),
                data=data,
                authority=(role == "present"),
            )
        mosaic = _build_mosaic(
            variant=variant,
            source=source,
            records=records,
            canvases=canvases,
        )
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
        sheets[variant] = {
            "contact_path": contact_path.relative_to(output).as_posix(),
            "contact_sha256": _file_sha256(contact_path),
            "graph_path": graph_path.relative_to(output).as_posix(),
            "graph_sha256": _file_sha256(graph_path),
        }
    manifest = {
        "schema_version": "triad-vis-m1r2-manifest-v1",
        "phase": "TRIAD-VIS-M1R2",
        "base_commit": EXPECTED_BASE_COMMIT,
        "contract": "EmocioVisualMosaicR2",
        "evidence_record_manifest_sha256": evidence_manifest_sha,
        "m1r_frozen_inventory": m1r_inventory,
        "m1r_frozen_inventory_sha256": _object_sha256(m1r_inventory),
        "mosaics": tuple(
            mosaic.model_dump(mode="json", exclude_none=True)
            for mosaic in mosaics
        ),
        "sheets": sheets,
        "unique_canvas_files": 20,
        "display_panels": 24,
        "model_calls": 0,
        "image_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "runtime_authority": False,
        "private_thinking_persisted": False,
    }
    _write_new(
        output / "evidence_record_manifest.json",
        canonical_json_bytes(evidence_manifest),
    )
    _write_new(output / "mosaic_manifest.json", canonical_json_bytes(manifest))
    _write_new(
        output / "report.md",
        _report(
            mosaics=mosaics,
            sheets=sheets,
            evidence_manifest_sha256=evidence_manifest_sha,
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
    evidence_manifest = json.loads(
        (output / "evidence_record_manifest.json").read_text(encoding="utf-8")
    )
    if _object_sha256(evidence_manifest) != manifest["evidence_record_manifest_sha256"]:
        raise ValueError("Evidence-record manifest hash closure failed")
    records = tuple(
        EvidenceRecordV1.model_validate_json(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            strict=True,
        )
        for item in evidence_manifest["records"]
    )
    if len(records) != 16:
        raise ValueError("Evidence-record manifest count mismatch")
    record_by_id = {record.record_id: record for record in records}
    mosaics = tuple(
        EmocioVisualMosaicR2.model_validate_json(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            strict=True,
        )
        for item in manifest["mosaics"]
    )
    _validate_inventory(repository_root, manifest["m1r_frozen_inventory"])
    if len(mosaics) != 2:
        raise ValueError("M1R2 must contain two mosaics")
    canvas_paths = set()
    for mosaic in mosaics:
        for _, panel in _display_panels(mosaic):
            ids = (
                panel.triggering_evidence_record_ids
                if panel.panel_scope == "emocio_imagined_completion"
                else panel.supporting_evidence_record_ids
            )
            if any(record_id not in record_by_id for record_id in ids):
                raise ValueError("Panel points outside evidence-record manifest")
            path = repository_root / panel.canvas.repository_path
            if _file_sha256(path) != panel.canvas.content_sha256:
                raise ValueError("M1R2 canvas hash mismatch")
            canvas_paths.add(panel.canvas.repository_path)
            if panel.panel_scope == "emocio_imagined_completion":
                dumped = panel.model_dump(mode="json", exclude_none=True)
                if "supporting_evidence_ids" in dumped:
                    raise ValueError("Imagined completion serialized support evidence")
                if not dumped.get("triggering_evidence_ids"):
                    raise ValueError("Imagined completion lost triggering evidence")
        for option in mosaic.options:
            for relation in option.unresolved_relations:
                if any(
                    record_id not in record_by_id
                    for record_id in relation.supporting_evidence_record_ids
                ):
                    raise ValueError("Relation points outside evidence records")
    if len(canvas_paths) != 20:
        raise ValueError("M1R2 must contain twenty unique canvases")
    for record in manifest["sheets"].values():
        if (
            _file_sha256(output / record["contact_path"])
            != record["contact_sha256"]
            or _file_sha256(output / record["graph_path"]) != record["graph_sha256"]
        ):
            raise ValueError("M1R2 sheet hash mismatch")
    serialized = canonical_json_bytes(manifest).decode("utf-8")
    forbidden = (
        "character_profile",
        "governance_tier",
        "expected_option",
        "gold_route",
        "training_label",
    )
    if any(term in serialized for term in forbidden):
        raise ValueError("M1R2 contains authority/answer leakage")
    absolute_hits = []
    for path in output.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".json", ".md"}:
            if _contains_absolute_path(path.read_text(encoding="utf-8")):
                absolute_hits.append(path.relative_to(repository_root).as_posix())
    if absolute_hits:
        raise ValueError(f"M1R2 contains absolute paths: {absolute_hits}")
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
    ) or manifest["runtime_authority"]:
        raise ValueError("M1R2 has non-zero call or authority state")
    return {
        "status": "passed",
        "evidence_records": 16,
        "evidence_hash_closure": "passed",
        "mosaic_count": 2,
        "display_panels": 24,
        "unique_canvas_files": 20,
        "m1r_files_verified": len(manifest["m1r_frozen_inventory"]),
        "absent_audience_support": "not_applicable",
        "model_calls": 0,
        "image_calls": 0,
        "character_replay": 0,
        "native_decision_influence": 0,
        "racio_vision": 0,
        "visual_valuation": 0,
        "runtime_authority": False,
        "absolute_paths_found": 0,
        "private_thinking_persisted": False,
    }


__all__ = [
    "CANVAS_ROLES",
    "EXPECTED_BASE_COMMIT",
    "EmocioVisualMosaicR2",
    "EvidenceRecordV1",
    "OPTION_IDS",
    "OUTPUT_RELATIVE_PATH",
    "build",
    "cold_verify",
    "evidence_records",
]
