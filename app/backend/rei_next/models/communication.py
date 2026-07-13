"""Immutable communication, acceptance, and translation contracts.

These records keep consciously observable manifestations separate from native
conclusions.  In particular, :class:`TranslationGap` is a diagnostic artifact;
it is not input ground truth for Racio's interpreter.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from .common import (
    FrozenArtifactModel,
    FrozenModel,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .emocio import EmocioNativeConclusion, ImageArtifact
from .instinkt import InstinktNativeConclusion


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
    body_locations: tuple[str, ...] = ()
    felt_tension: Score01
    fear_intensity: Score01
    attachment_pull: Score01
    withdrawal_urge: Score01
    freeze_intensity: Score01
    boundary_alarm: Score01
    raw_urge: str

    def validate_against(self, conclusion: InstinktNativeConclusion) -> Self:
        if self.source_conclusion_id != conclusion.conclusion_id:
            raise ValueError("Instinkt manifestation belongs to another conclusion")
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
