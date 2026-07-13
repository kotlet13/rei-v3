"""Immutable communication, acceptance, and translation contracts.

These records keep consciously observable manifestations separate from native
conclusions.  In particular, :class:`TranslationGap` is a diagnostic artifact;
it is not input ground truth for Racio's interpreter.
"""

from __future__ import annotations

import math
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import content_id
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .emocio import EmocioNativeConclusion, ImageArtifact
from .instinkt import (
    BodyState,
    InstinktNativeConclusion,
    InstinktOptionRollout,
)


AcceptanceMode = Literal["accepting", "mixed", "conflicted", "unknown"]
DistortionType = Literal[
    "none",
    "omission",
    "rationalization",
    "minimization",
    "projection",
    "misclassification",
    "unknown",
]
InterpretedMindId = Literal["E", "I"]


class DirectedMindRelation(FrozenModel):
    """Acceptance dimensions for one directed relationship between two minds."""

    visibility: Score01
    interpretation_fidelity: Score01
    tolerance: Score01
    delegation_willingness: Score01
    sabotage_risk: Score01


class AcceptanceState(FrozenArtifactModel):
    """Explicit acceptance input, orthogonal to structural character authority."""

    schema_version: Literal["rei-native-acceptance-state-v1"] = (
        "rei-native-acceptance-state-v1"
    )
    acceptance_state_id: NonEmptyId
    R_to_E: DirectedMindRelation
    R_to_I: DirectedMindRelation
    E_to_R: DirectedMindRelation
    E_to_I: DirectedMindRelation
    I_to_R: DirectedMindRelation
    I_to_E: DirectedMindRelation
    overall_mode: AcceptanceMode


class EmocioManifestation(FrozenArtifactModel):
    """The consciously observable projection of an Emocio conclusion."""

    schema_version: Literal["rei-native-emocio-manifestation-v1"] = (
        "rei-native-emocio-manifestation-v1"
    )
    manifestation_id: NonEmptyId
    source_conclusion_id: NonEmptyId
    visible_image_artifact_ids: tuple[NonEmptyId, ...] = ()
    attraction_intensity: Score01
    aversion_intensity: Score01
    anger_intensity: Score01
    motor_urge: str
    social_pull: str

    @model_validator(mode="after")
    def validate_image_ids(self) -> Self:
        if len(set(self.visible_image_artifact_ids)) != len(
            self.visible_image_artifact_ids
        ):
            raise ValueError("visible image artifact IDs must be unique")
        return self

    def validate_against(
        self,
        conclusion: EmocioNativeConclusion,
        images: tuple[ImageArtifact, ...] = (),
    ) -> Self:
        """Bind visible generated images to scenes named by the native conclusion."""

        if self.source_conclusion_id != conclusion.conclusion_id:
            raise ValueError("Emocio manifestation belongs to another conclusion")
        image_by_id = {image.image_id: image for image in images}
        if len(image_by_id) != len(images):
            raise ValueError("Supplied ImageArtifact IDs must be unique")
        allowed_scene_ids = {
            conclusion.current_scene_id,
            conclusion.desired_scene_id,
            conclusion.decisive_rollout_scene_id,
        } - {None}
        for image_id in self.visible_image_artifact_ids:
            image = image_by_id.get(image_id)
            if image is None or image.source_spec_id not in allowed_scene_ids:
                raise ValueError(
                    "Visible Emocio image must originate from a conclusion scene"
                )
        return self


class InstinktManifestation(FrozenArtifactModel):
    """The consciously observable embodied projection of an Instinkt conclusion."""

    schema_version: Literal["rei-native-instinkt-manifestation-v1"] = (
        "rei-native-instinkt-manifestation-v1"
    )
    manifestation_id: NonEmptyId
    source_conclusion_id: NonEmptyId
    source_conclusion_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    manifestation_status: Literal["unverified_contract", "simulated_v1"] = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_body_state_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_body_state_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_decisive_rollout_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_decisive_rollout_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    body_locations: tuple[str, ...] = ()
    felt_tension: Score01
    fear_intensity: Score01
    attachment_pull: Score01
    withdrawal_urge: Score01
    freeze_intensity: Score01
    boundary_alarm: Score01
    raw_urge: str
    manifestation_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def validate_manifestation_record(self) -> Self:
        if len(set(self.body_locations)) != len(self.body_locations):
            raise ValueError("Instinkt manifestation body locations must be unique")
        lineage = (
            self.source_conclusion_hash,
            self.source_body_state_id,
            self.source_body_state_hash,
            self.source_decisive_rollout_id,
            self.source_decisive_rollout_hash,
            self.manifestation_hash,
        )
        if self.manifestation_status == "unverified_contract":
            if any(value is not None for value in lineage):
                raise ValueError("Unverified manifestation cannot claim B8 lineage")
            return self
        if (
            self.source_conclusion_hash is None
            or self.source_body_state_id is None
            or self.source_body_state_hash is None
            or self.manifestation_hash is None
        ):
            raise ValueError("Simulated manifestation requires BodyState lineage")
        if (self.source_decisive_rollout_id is None) != (
            self.source_decisive_rollout_hash is None
        ):
            raise ValueError("Manifestation rollout ID and hash must appear together")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"manifestation_id", "manifestation_hash"},
        )
        if self.manifestation_id != content_id("instinkt_manifestation", id_payload):
            raise ValueError("manifestation_id does not match manifestation content")
        expected_hash = self.content_hash(
            exclude_fields=frozenset({"manifestation_hash"})
        )
        if self.manifestation_hash != expected_hash:
            raise ValueError("manifestation_hash does not match manifestation content")
        return self

    def validate_against(
        self,
        conclusion: InstinktNativeConclusion,
        body_state: BodyState | None = None,
        decisive_rollout: InstinktOptionRollout | None = None,
    ) -> Self:
        if self.source_conclusion_id != conclusion.conclusion_id:
            raise ValueError("Instinkt manifestation belongs to another conclusion")
        if self.manifestation_status == "unverified_contract":
            return self
        if body_state is None:
            raise ValueError("Simulated manifestation requires its source BodyState")
        if self.source_conclusion_hash != conclusion.content_hash():
            raise ValueError("Instinkt manifestation conclusion hash differs")
        if (
            self.source_body_state_id != body_state.body_state_id
            or self.source_body_state_hash != body_state.content_hash()
        ):
            raise ValueError("Instinkt manifestation BodyState lineage differs")
        if conclusion.decisive_rollout_id is None:
            if decisive_rollout is not None or self.source_decisive_rollout_id is not None:
                raise ValueError("Abstaining manifestation cannot cite a rollout")
            if conclusion.source_body_state_id != body_state.body_state_id:
                raise ValueError("Abstaining manifestation must use the source BodyState")
        else:
            if decisive_rollout is None or decisive_rollout.rollout_hash is None:
                raise ValueError("Selected manifestation requires its decisive rollout")
            if (
                decisive_rollout.rollout_id != conclusion.decisive_rollout_id
                or decisive_rollout.option_id != conclusion.option_id
                or decisive_rollout.trajectory[-1] != body_state
                or self.source_decisive_rollout_id != decisive_rollout.rollout_id
                or self.source_decisive_rollout_hash != decisive_rollout.rollout_hash
            ):
                raise ValueError("Instinkt manifestation decisive rollout lineage differs")
        expected_values = {
            "felt_tension": body_state.tension,
            "fear_intensity": (
                0.50 * conclusion.intensity
                + 0.30 * body_state.tension
                + 0.20 * body_state.arousal
            ),
            "attachment_pull": (
                (1.0 - body_state.attachment_security) * conclusion.intensity
            ),
            "withdrawal_urge": (
                conclusion.intensity
                if conclusion.action_tendency in {"withdraw", "seek_safety"}
                else 0.0
            ),
            "freeze_intensity": (
                conclusion.intensity
                if conclusion.action_tendency == "freeze"
                else 0.0
            ),
            "boundary_alarm": 1.0 - body_state.boundary_integrity,
        }
        for field_name, expected in expected_values.items():
            if not math.isclose(
                getattr(self, field_name),
                expected,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    f"Instinkt manifestation {field_name} does not replay"
                )
        expected_urge = f"structured_tendency:{conclusion.action_tendency}"
        if self.raw_urge != expected_urge:
            raise ValueError("Instinkt manifestation raw urge does not replay")
        return self


ObservationProvenance = Literal["manifested", "renderer_added_ungrounded"]


class ManifestationObservation(FrozenModel):
    """One conscious observation with explicit renderer-added provenance."""

    manifestation_id: NonEmptyId
    content: NonEmptyText
    provenance: ObservationProvenance
    source_image_artifact_id: NonEmptyId | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        renderer_added = self.provenance == "renderer_added_ungrounded"
        if renderer_added != (self.source_image_artifact_id is not None):
            raise ValueError(
                "Only renderer-added ungrounded observations may cite generated images"
            )
        return self


class RacioInterpretation(FrozenArtifactModel):
    """Racio's inference from an E/I manifestation, without native ground truth."""

    schema_version: Literal["rei-native-racio-interpretation-v1"] = (
        "rei-native-racio-interpretation-v1"
    )
    interpretation_id: NonEmptyId
    source_mind: InterpretedMindId
    observed_manifestation_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    observed_manifestations: tuple[ManifestationObservation, ...] = ()
    inferred_option_id: NonEmptyId | None = None
    inferred_motive: str
    confidence: Score01
    alternative_hypotheses: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_observation_scope(self) -> Self:
        if len(set(self.observed_manifestation_ids)) != len(
            self.observed_manifestation_ids
        ):
            raise ValueError("observed_manifestation_ids must be unique")
        observation_ids = tuple(
            observation.manifestation_id for observation in self.observed_manifestations
        )
        if not set(observation_ids).issubset(self.observed_manifestation_ids):
            raise ValueError("Every observation must reference an observed manifestation")
        return self

    def validate_against(
        self,
        manifestations: tuple[EmocioManifestation | InstinktManifestation, ...],
    ) -> Self:
        """Close manifestation type and renderer-image provenance externally."""

        manifestation_by_id = {
            manifestation.manifestation_id: manifestation
            for manifestation in manifestations
        }
        if len(manifestation_by_id) != len(manifestations):
            raise ValueError("Supplied manifestation IDs must be unique")
        if set(manifestation_by_id) != set(self.observed_manifestation_ids):
            raise ValueError(
                "Supplied manifestations must exactly match the interpretation scope"
            )
        expected_type = (
            EmocioManifestation if self.source_mind == "E" else InstinktManifestation
        )
        if any(
            not isinstance(manifestation, expected_type)
            for manifestation in manifestations
        ):
            raise ValueError("Interpretation source_mind differs from manifestation type")
        for observation in self.observed_manifestations:
            manifestation = manifestation_by_id[observation.manifestation_id]
            image_id = observation.source_image_artifact_id
            if image_id is None:
                continue
            if not isinstance(manifestation, EmocioManifestation):
                raise ValueError(
                    "Only Emocio manifestations can expose renderer image artifacts"
                )
            if image_id not in manifestation.visible_image_artifact_ids:
                raise ValueError(
                    "Renderer-added observation must cite an image visible in its manifestation"
                )
        return self


class TranslationGap(FrozenArtifactModel):
    """Diagnostic comparison of a native E/I conclusion and Racio's inference."""

    schema_version: Literal["rei-native-translation-gap-v1"] = (
        "rei-native-translation-gap-v1"
    )
    translation_gap_id: NonEmptyId
    source_mind: InterpretedMindId
    source_conclusion_id: NonEmptyId
    interpretation_id: NonEmptyId
    native_option_id: NonEmptyId | None = None
    interpreted_option_id: NonEmptyId | None = None
    native_motive_summary: str
    interpreted_motive: str
    option_match: bool
    motive_fidelity: Score01
    distortion_type: DistortionType

    @model_validator(mode="after")
    def validate_option_match(self) -> "TranslationGap":
        actual_match = self.native_option_id == self.interpreted_option_id
        if self.option_match != actual_match:
            raise ValueError("option_match must agree with the recorded option IDs")
        return self


__all__ = [
    "AcceptanceMode",
    "AcceptanceState",
    "DirectedMindRelation",
    "DistortionType",
    "EmocioManifestation",
    "InstinktManifestation",
    "InterpretedMindId",
    "ManifestationObservation",
    "ObservationProvenance",
    "RacioInterpretation",
    "TranslationGap",
]
