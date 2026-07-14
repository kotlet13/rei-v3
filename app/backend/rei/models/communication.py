"""Immutable communication, acceptance, and translation contracts.

These records keep consciously observable manifestations separate from native
conclusions.  In particular, :class:`TranslationGap` is a diagnostic artifact;
it is not input ground truth for Racio's interpreter.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Literal, Self

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from .common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
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
CommunicationArtifactStatus = Literal["unverified_contract", "derived_b9"]
InterpretationStatus = Literal[
    "unverified_contract",
    "interpreted_b9",
    "omitted_b9",
    "unavailable_b9",
]
ObservableSignalName = Literal[
    "attraction_intensity",
    "aversion_intensity",
    "anger_intensity",
    "motor_urge",
    "social_pull",
    "visible_image_artifact_id",
    "renderer_interpretation",
    "felt_tension",
    "fear_intensity",
    "attachment_pull",
    "withdrawal_urge",
    "freeze_intensity",
    "boundary_alarm",
    "raw_urge",
]
RelationDirection = Literal["R_to_E", "R_to_I"]

_EMOCIO_OBSERVABLE_SIGNALS: tuple[ObservableSignalName, ...] = (
    "attraction_intensity",
    "aversion_intensity",
    "anger_intensity",
    "motor_urge",
    "social_pull",
)
_INSTINKT_OBSERVABLE_SIGNALS: tuple[ObservableSignalName, ...] = (
    "felt_tension",
    "fear_intensity",
    "attachment_pull",
    "withdrawal_urge",
    "freeze_intensity",
    "boundary_alarm",
    "raw_urge",
)
B9_FIXTURE_EMOCIO_PROJECTION_POLICY = "b9_fixture_emocio_projection_v1"
B9_EXACT_ACTION_FIDELITY_POLICY = "b9-exact-action-tendency-fidelity-v1"
B9_EXACT_DISTORTION_POLICY = "b9-exact-distortion-classifier-v1"
B9_ACCEPTANCE_FIDELITY_AUDIT_POLICY = "b9-acceptance-fidelity-record-only-v1"


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


class CommunicationArtifactRef(FrozenModel):
    """Compact immutable ID/hash reference without importing the run model layer."""

    artifact_id: NonEmptyId
    artifact_hash: HashDigest


def _b9_emocio_projection_values(
    conclusion: EmocioNativeConclusion,
) -> dict[str, float | str]:
    """Transparent B9 fixture projection; an implementation hypothesis, not theory."""

    approach_actions = {"approach", "perform", "compete", "connect", "improvise"}
    aversion_actions = {"attack", "withdraw_contact"}
    action = conclusion.action_tendency
    if action == "connect":
        social_pull = "structured_social_pull:toward_connection"
    elif action == "withdraw_contact":
        social_pull = "structured_social_pull:away_from_contact"
    else:
        social_pull = "structured_social_pull:unspecified"
    return {
        "attraction_intensity": (
            conclusion.intensity if action in approach_actions else 0.0
        ),
        "aversion_intensity": (
            conclusion.intensity if action in aversion_actions else 0.0
        ),
        "anger_intensity": conclusion.intensity if action == "attack" else 0.0,
        "motor_urge": f"structured_tendency:{action}",
        "social_pull": social_pull,
    }


class EmocioManifestation(FrozenArtifactModel):
    """The consciously observable projection of an Emocio conclusion."""

    schema_version: Literal["rei-native-emocio-manifestation-v1"] = (
        "rei-native-emocio-manifestation-v1"
    )
    manifestation_id: NonEmptyId
    source_conclusion_id: NonEmptyId
    source_conclusion_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    manifestation_status: CommunicationArtifactStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    projection_policy: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    visible_image_artifact_ids: tuple[NonEmptyId, ...] = ()
    visible_image_artifact_hashes: tuple[CommunicationArtifactRef, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    attraction_intensity: Score01
    aversion_intensity: Score01
    anger_intensity: Score01
    motor_urge: str
    social_pull: str
    manifestation_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @classmethod
    def create_b9_fixture_projection(
        cls,
        *,
        conclusion: EmocioNativeConclusion,
        images: tuple[ImageArtifact, ...] = (),
    ) -> EmocioManifestation:
        """Build the conservative, provider-free B9 fixture manifestation."""

        image_by_id = {image.image_id: image for image in images}
        if len(image_by_id) != len(images):
            raise ValueError("Supplied ImageArtifact IDs must be unique")
        allowed_scene_ids = {
            conclusion.current_scene_id,
            conclusion.desired_scene_id,
            conclusion.decisive_rollout_scene_id,
        } - {None}
        visible_images = tuple(
            sorted(
                (
                    image
                    for image in images
                    if image.source_spec_id in allowed_scene_ids
                ),
                key=lambda image: image.image_id,
            )
        )
        base: dict[str, object] = {
            "schema_version": "rei-native-emocio-manifestation-v1",
            "source_conclusion_id": conclusion.conclusion_id,
            "source_conclusion_hash": conclusion.content_hash(),
            "manifestation_status": "derived_b9",
            "projection_policy": B9_FIXTURE_EMOCIO_PROJECTION_POLICY,
            "visible_image_artifact_ids": tuple(
                image.image_id for image in visible_images
            ),
            **_b9_emocio_projection_values(conclusion),
        }
        if visible_images:
            base["visible_image_artifact_hashes"] = tuple(
                CommunicationArtifactRef(
                    artifact_id=image.image_id,
                    artifact_hash=image.content_hash(),
                )
                for image in visible_images
            )
        manifestation_id = content_id("emocio_manifestation", base)
        payload = {"manifestation_id": manifestation_id, **base}
        manifestation = cls(
            **payload,
            manifestation_hash=sha256_hex(payload),
        )
        manifestation.validate_against(conclusion, images)
        return manifestation

    @model_validator(mode="after")
    def validate_image_ids(self) -> Self:
        if len(set(self.visible_image_artifact_ids)) != len(
            self.visible_image_artifact_ids
        ):
            raise ValueError("visible image artifact IDs must be unique")
        lineage = (
            self.source_conclusion_hash,
            self.projection_policy,
            self.manifestation_hash,
        )
        if self.manifestation_status == "unverified_contract":
            if any(value is not None for value in lineage):
                raise ValueError("Unverified Emocio manifestation cannot claim B9 lineage")
            if self.visible_image_artifact_hashes:
                raise ValueError(
                    "Unverified Emocio manifestation cannot publish B9 image hashes"
                )
            return self
        if any(value is None for value in lineage):
            raise ValueError("Derived Emocio manifestation requires complete B9 lineage")
        if self.projection_policy != B9_FIXTURE_EMOCIO_PROJECTION_POLICY:
            raise ValueError("Unknown Emocio manifestation projection policy")
        if self.visible_image_artifact_ids != tuple(
            sorted(self.visible_image_artifact_ids)
        ):
            raise ValueError("Derived Emocio image IDs must use canonical order")
        hash_ids = tuple(item.artifact_id for item in self.visible_image_artifact_hashes)
        if hash_ids != self.visible_image_artifact_ids:
            raise ValueError("Emocio image hash references must exactly match visible IDs")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"manifestation_id", "manifestation_hash"},
        )
        if self.manifestation_id != content_id("emocio_manifestation", id_payload):
            raise ValueError("manifestation_id does not match Emocio manifestation content")
        expected_hash = self.content_hash(
            exclude_fields=frozenset({"manifestation_hash"})
        )
        if self.manifestation_hash != expected_hash:
            raise ValueError("manifestation_hash does not match Emocio manifestation content")
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
        if self.manifestation_status == "unverified_contract":
            return self
        if self.source_conclusion_hash != conclusion.content_hash():
            raise ValueError("Emocio manifestation conclusion hash differs")
        eligible_images = tuple(
            sorted(
                (
                    image
                    for image in images
                    if image.source_spec_id in allowed_scene_ids
                ),
                key=lambda image: image.image_id,
            )
        )
        expected_refs = tuple(
            CommunicationArtifactRef(
                artifact_id=image.image_id,
                artifact_hash=image.content_hash(),
            )
            for image in eligible_images
        )
        if self.visible_image_artifact_hashes != expected_refs:
            raise ValueError("Emocio manifestation image lineage differs")
        expected_values = _b9_emocio_projection_values(conclusion)
        for field_name, expected in expected_values.items():
            actual = getattr(self, field_name)
            if isinstance(expected, float):
                if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
                    raise ValueError(
                        f"Emocio manifestation {field_name} does not replay"
                    )
            elif actual != expected:
                raise ValueError(f"Emocio manifestation {field_name} does not replay")
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
    manifestation_status: Literal[
        "unverified_contract",
        "simulated_v1",
        "fixture_projection_b11",
    ] = Field(
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
        if self.manifestation_status == "fixture_projection_b11":
            if decisive_rollout is not None or self.source_decisive_rollout_id is not None:
                raise ValueError("Fixture projection cannot claim a B8 decisive rollout")
        elif conclusion.decisive_rollout_id is None:
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
    observation_status: CommunicationArtifactStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    observation_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_manifestation_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    signal_name: ObservableSignalName | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    canonical_json_value: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_image_artifact_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_provider_result_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_provider_result_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    observation_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @classmethod
    def create_structured(
        cls,
        *,
        manifestation_id: NonEmptyId,
        manifestation_hash: HashDigest,
        signal_name: ObservableSignalName,
        value: object,
        image_ref: CommunicationArtifactRef | None = None,
    ) -> ManifestationObservation:
        canonical_value = canonical_json_bytes(value).decode("utf-8")
        provenance: ObservationProvenance = (
            "renderer_added_ungrounded" if image_ref is not None else "manifested"
        )
        base: dict[str, object] = {
            "manifestation_id": manifestation_id,
            "content": f"{signal_name}={canonical_value}",
            "provenance": provenance,
            "source_image_artifact_id": (
                image_ref.artifact_id if image_ref is not None else None
            ),
            "observation_status": "derived_b9",
            "source_manifestation_hash": manifestation_hash,
            "signal_name": signal_name,
            "canonical_json_value": canonical_value,
        }
        if image_ref is not None:
            base["source_image_artifact_id"] = image_ref.artifact_id
            base["source_image_artifact_hash"] = image_ref.artifact_hash
        observation_id = content_id("manifestation_observation", base)
        payload = {**base, "observation_id": observation_id}
        return cls(**payload, observation_hash=sha256_hex(payload))

    @classmethod
    def create_renderer_interpretation(
        cls,
        *,
        manifestation_id: NonEmptyId,
        manifestation_hash: HashDigest,
        image_ref: CommunicationArtifactRef,
        provider_result_id: NonEmptyId,
        provider_result_hash: HashDigest,
        interpretation: str,
        inferred_claims: tuple[str, ...] = (),
    ) -> ManifestationObservation:
        """Record VLM text only as explicitly ungrounded renderer provenance."""

        value = {
            "interpretation": interpretation,
            "inferred_claims": inferred_claims,
        }
        canonical_value = canonical_json_bytes(value).decode("utf-8")
        base: dict[str, object] = {
            "manifestation_id": manifestation_id,
            "content": f"renderer_interpretation={canonical_value}",
            "provenance": "renderer_added_ungrounded",
            "source_image_artifact_id": image_ref.artifact_id,
            "observation_status": "derived_b9",
            "source_manifestation_hash": manifestation_hash,
            "signal_name": "renderer_interpretation",
            "canonical_json_value": canonical_value,
            "source_image_artifact_hash": image_ref.artifact_hash,
            "source_provider_result_id": provider_result_id,
            "source_provider_result_hash": provider_result_hash,
        }
        observation_id = content_id("manifestation_observation", base)
        payload = {**base, "observation_id": observation_id}
        return cls(**payload, observation_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        renderer_added = self.provenance == "renderer_added_ungrounded"
        if renderer_added != (self.source_image_artifact_id is not None):
            raise ValueError(
                "Only renderer-added ungrounded observations may cite generated images"
            )
        structured_lineage = (
            self.observation_id,
            self.source_manifestation_hash,
            self.signal_name,
            self.canonical_json_value,
            self.observation_hash,
        )
        if self.observation_status == "unverified_contract":
            if any(value is not None for value in structured_lineage):
                raise ValueError("Legacy observation cannot claim structured B9 lineage")
            if self.source_image_artifact_hash is not None:
                raise ValueError("Legacy observation cannot claim a B9 image hash")
            if (
                self.source_provider_result_id is not None
                or self.source_provider_result_hash is not None
            ):
                raise ValueError("Legacy observation cannot claim B9 provider lineage")
            return self
        if any(value is None for value in structured_lineage):
            raise ValueError("Structured observation requires complete B9 lineage")
        assert self.canonical_json_value is not None
        try:
            decoded_value = json.loads(self.canonical_json_value)
        except json.JSONDecodeError as exc:
            raise ValueError("Observation value must be canonical JSON") from exc
        if canonical_json_bytes(decoded_value).decode("utf-8") != self.canonical_json_value:
            raise ValueError("Observation value must use canonical JSON")
        if self.content != f"{self.signal_name}={self.canonical_json_value}":
            raise ValueError("Structured observation content must replay from its signal")
        numeric_signals = {
            "attraction_intensity",
            "aversion_intensity",
            "anger_intensity",
            "felt_tension",
            "fear_intensity",
            "attachment_pull",
            "withdrawal_urge",
            "freeze_intensity",
            "boundary_alarm",
        }
        if self.signal_name in numeric_signals:
            if (
                isinstance(decoded_value, bool)
                or not isinstance(decoded_value, (int, float))
                or not 0.0 <= float(decoded_value) <= 1.0
            ):
                raise ValueError("Observable intensity signals must stay within [0, 1]")
        elif self.signal_name in {"motor_urge", "raw_urge"}:
            allowed_actions = {
                "approach",
                "perform",
                "compete",
                "connect",
                "attack",
                "improvise",
                "withdraw_contact",
                "protect",
                "withdraw",
                "maintain",
                "set_boundary",
                "seek_safety",
                "seek_attachment",
                "conserve",
                "freeze",
                "unknown",
            }
            if not isinstance(decoded_value, str) or decoded_value not in {
                f"structured_tendency:{action}" for action in allowed_actions
            }:
                raise ValueError("Observable action signals must use a typed tendency code")
        elif self.signal_name == "social_pull":
            if decoded_value not in {
                "structured_social_pull:toward_connection",
                "structured_social_pull:away_from_contact",
                "structured_social_pull:unspecified",
            }:
                raise ValueError("Observable social pull must use a structured code")
        provider_lineage_complete = (
            self.source_provider_result_id is not None
            and self.source_provider_result_hash is not None
        )
        if (self.source_provider_result_id is None) != (
            self.source_provider_result_hash is None
        ):
            raise ValueError("Renderer provider result ID/hash must appear together")
        if renderer_added:
            if self.source_image_artifact_hash is None:
                raise ValueError("Renderer observation requires exact image hash lineage")
            if self.signal_name == "visible_image_artifact_id":
                if decoded_value != self.source_image_artifact_id:
                    raise ValueError("Visible-image observation must replay its image ID")
                if provider_lineage_complete:
                    raise ValueError("Visible-image identity is not a VLM interpretation")
            elif self.signal_name == "renderer_interpretation":
                if not provider_lineage_complete or not isinstance(decoded_value, dict):
                    raise ValueError("Renderer interpretation requires provider result lineage")
                if set(decoded_value) != {"interpretation", "inferred_claims"}:
                    raise ValueError("Renderer interpretation has an invalid typed value")
                if not isinstance(decoded_value["interpretation"], str) or not isinstance(
                    decoded_value["inferred_claims"], list
                ) or any(
                    not isinstance(claim, str)
                    for claim in decoded_value["inferred_claims"]
                ):
                    raise ValueError("Renderer interpretation value has invalid field types")
            else:
                raise ValueError("Renderer provenance is restricted to visible image signals")
        elif self.signal_name == "visible_image_artifact_id":
            raise ValueError(
                "Visible-image observations require renderer-added provenance and hashes"
            )
        elif self.source_image_artifact_hash is not None:
            raise ValueError("Manifested structured fields cannot claim image lineage")
        elif provider_lineage_complete:
            raise ValueError("Manifested fields cannot claim renderer provider lineage")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"observation_id", "observation_hash"},
        )
        if self.observation_id != content_id("manifestation_observation", id_payload):
            raise ValueError("observation_id does not match structured observation content")
        expected_hash = self.content_hash(
            exclude_fields=frozenset({"observation_hash"})
        )
        if self.observation_hash != expected_hash:
            raise ValueError("observation_hash does not match structured observation content")
        return self


def _observable_manifestation_values(
    manifestation: EmocioManifestation | InstinktManifestation,
) -> tuple[tuple[ObservableSignalName, object, CommunicationArtifactRef | None], ...]:
    if isinstance(manifestation, EmocioManifestation):
        values: list[
            tuple[ObservableSignalName, object, CommunicationArtifactRef | None]
        ] = [
            (name, getattr(manifestation, name), None)
            for name in _EMOCIO_OBSERVABLE_SIGNALS
        ]
        refs = {
            item.artifact_id: item
            for item in manifestation.visible_image_artifact_hashes
        }
        values.extend(
            (
                "visible_image_artifact_id",
                image_id,
                refs.get(image_id),
            )
            for image_id in manifestation.visible_image_artifact_ids
        )
        return tuple(values)
    return tuple(
        (name, getattr(manifestation, name), None)
        for name in _INSTINKT_OBSERVABLE_SIGNALS
    )


class ObservableManifestationView(FrozenArtifactModel):
    """Sanitized, replayable surface passed to Racio instead of native truth."""

    schema_version: Literal["rei-native-observable-manifestation-view-v1"] = (
        "rei-native-observable-manifestation-view-v1"
    )
    view_id: NonEmptyId
    source_mind: InterpretedMindId
    manifestation_id: NonEmptyId
    manifestation_hash: HashDigest
    observations: tuple[ManifestationObservation, ...] = Field(min_length=1)
    view_hash: HashDigest

    @classmethod
    def create(
        cls,
        manifestation: EmocioManifestation | InstinktManifestation,
    ) -> ObservableManifestationView:
        if isinstance(manifestation, EmocioManifestation):
            if manifestation.manifestation_status != "derived_b9":
                raise ValueError("B9 Emocio view requires a verified manifestation")
            source_mind: InterpretedMindId = "E"
        else:
            if manifestation.manifestation_status == "unverified_contract":
                raise ValueError("B9 Instinkt view requires a verified manifestation")
            source_mind = "I"
        manifestation_hash = manifestation.content_hash()
        observations = tuple(
            ManifestationObservation.create_structured(
                manifestation_id=manifestation.manifestation_id,
                manifestation_hash=manifestation_hash,
                signal_name=signal_name,
                value=value,
                image_ref=image_ref,
            )
            for signal_name, value, image_ref in _observable_manifestation_values(
                manifestation
            )
        )
        base = {
            "schema_version": "rei-native-observable-manifestation-view-v1",
            "source_mind": source_mind,
            "manifestation_id": manifestation.manifestation_id,
            "manifestation_hash": manifestation_hash,
            "observations": observations,
        }
        view_id = content_id("manifestation_view", base)
        payload = {"view_id": view_id, **base}
        return cls(**payload, view_hash=sha256_hex(payload))

    @classmethod
    def create_with_renderer_observations(
        cls,
        *,
        manifestation: EmocioManifestation,
        renderer_observations: tuple[ManifestationObservation, ...],
    ) -> ObservableManifestationView:
        """Attach explicitly supplied, ungrounded VLM observations to a trusted E view."""

        base_view = cls.create(manifestation)
        canonical_renderer = tuple(
            sorted(
                renderer_observations,
                key=lambda item: (
                    item.source_image_artifact_id or "",
                    item.observation_id or "",
                ),
            )
        )
        image_refs = {
            ref.artifact_id: ref.artifact_hash
            for ref in manifestation.visible_image_artifact_hashes
        }
        for observation in canonical_renderer:
            if (
                observation.provenance != "renderer_added_ungrounded"
                or observation.signal_name != "renderer_interpretation"
                or observation.manifestation_id != manifestation.manifestation_id
                or observation.source_manifestation_hash != manifestation.content_hash()
                or observation.source_image_artifact_id not in image_refs
                or image_refs[observation.source_image_artifact_id]
                != observation.source_image_artifact_hash
                or observation.source_provider_result_id is None
                or observation.source_provider_result_hash is None
            ):
                raise ValueError("Renderer enrichment does not close visible Emocio lineage")
        base = {
            "schema_version": "rei-native-observable-manifestation-view-v1",
            "source_mind": "E",
            "manifestation_id": manifestation.manifestation_id,
            "manifestation_hash": manifestation.content_hash(),
            "observations": (*base_view.observations, *canonical_renderer),
        }
        view_id = content_id("manifestation_view", base)
        payload = {"view_id": view_id, **base}
        return cls(**payload, view_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_view(self) -> Self:
        expected_prefix = (
            _EMOCIO_OBSERVABLE_SIGNALS
            if self.source_mind == "E"
            else _INSTINKT_OBSERVABLE_SIGNALS
        )
        signal_names = tuple(item.signal_name for item in self.observations)
        if signal_names[: len(expected_prefix)] != expected_prefix:
            raise ValueError("Observable view must use its canonical signal order")
        remainder = signal_names[len(expected_prefix) :]
        if self.source_mind == "I" and remainder:
            raise ValueError("Instinkt view cannot expose renderer observations")
        allowed_remainder = {"visible_image_artifact_id", "renderer_interpretation"}
        if any(name not in allowed_remainder for name in remainder):
            raise ValueError("Only visible-image signals may follow Emocio fields")
        first_renderer = next(
            (index for index, name in enumerate(remainder) if name == "renderer_interpretation"),
            len(remainder),
        )
        if any(name == "visible_image_artifact_id" for name in remainder[first_renderer:]):
            raise ValueError("Renderer interpretations must follow visible-image identities")
        if any(
            item.observation_status != "derived_b9"
            or item.manifestation_id != self.manifestation_id
            or item.source_manifestation_hash != self.manifestation_hash
            for item in self.observations
        ):
            raise ValueError("Observable view contains unverified or foreign observations")
        observation_ids = tuple(item.observation_id for item in self.observations)
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("Observable view observation IDs must be unique")
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"view_id", "view_hash"}
        )
        if self.view_id != content_id("manifestation_view", id_payload):
            raise ValueError("view_id does not match observable view content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"view_hash"}))
        if self.view_hash != expected_hash:
            raise ValueError("view_hash does not match observable view content")
        return self

    def validate_against(
        self,
        manifestation: EmocioManifestation | InstinktManifestation,
        *,
        renderer_observations: tuple[ManifestationObservation, ...] = (),
    ) -> Self:
        if isinstance(manifestation, InstinktManifestation) and renderer_observations:
            raise ValueError("Instinkt views cannot receive renderer observations")
        expected = (
            type(self).create_with_renderer_observations(
                manifestation=manifestation,
                renderer_observations=renderer_observations,
            )
            if isinstance(manifestation, EmocioManifestation)
            and renderer_observations
            else type(self).create(manifestation)
        )
        if self != expected:
            raise ValueError("Observable view differs from its manifestation replay")
        return self


class RacioInterpreterRequest(FrozenArtifactModel):
    """Interpreter input containing only observable views and explicit acceptance."""

    schema_version: Literal["rei-native-racio-interpreter-request-v1"] = (
        "rei-native-racio-interpreter-request-v1"
    )
    request_id: NonEmptyId
    source_mind: InterpretedMindId
    observable_views: tuple[ObservableManifestationView, ...] = Field(min_length=1)
    source_manifestation_hashes: tuple[CommunicationArtifactRef, ...] = Field(
        min_length=1
    )
    allowed_option_ids: tuple[NonEmptyId, ...]
    acceptance_state_id: NonEmptyId
    acceptance_state_hash: HashDigest
    relation_direction: RelationDirection
    relation: DirectedMindRelation
    request_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        views: tuple[ObservableManifestationView, ...],
        allowed_option_ids: tuple[NonEmptyId, ...],
        acceptance_state: AcceptanceState,
    ) -> RacioInterpreterRequest:
        if not views:
            raise ValueError("Racio interpreter requires at least one observable view")
        source_minds = {view.source_mind for view in views}
        if len(source_minds) != 1:
            raise ValueError("One interpreter request cannot mix E and I manifestations")
        source_mind = next(iter(source_minds))
        direction: RelationDirection = "R_to_E" if source_mind == "E" else "R_to_I"
        relation = acceptance_state.R_to_E if source_mind == "E" else acceptance_state.R_to_I
        canonical_views = tuple(sorted(views, key=lambda item: item.manifestation_id))
        refs = tuple(
            CommunicationArtifactRef(
                artifact_id=view.manifestation_id,
                artifact_hash=view.manifestation_hash,
            )
            for view in canonical_views
        )
        base = {
            "schema_version": "rei-native-racio-interpreter-request-v1",
            "source_mind": source_mind,
            "observable_views": canonical_views,
            "source_manifestation_hashes": refs,
            "allowed_option_ids": tuple(sorted(set(allowed_option_ids))),
            "acceptance_state_id": acceptance_state.acceptance_state_id,
            "acceptance_state_hash": acceptance_state.content_hash(),
            "relation_direction": direction,
            "relation": relation,
        }
        request_id = content_id("racio_interpreter_request", base)
        payload = {"request_id": request_id, **base}
        return cls(**payload, request_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.allowed_option_ids != tuple(sorted(set(self.allowed_option_ids))):
            raise ValueError("Interpreter allowed options must be sorted and unique")
        manifestation_ids = tuple(
            view.manifestation_id for view in self.observable_views
        )
        if len(set(manifestation_ids)) != len(manifestation_ids):
            raise ValueError("Interpreter request manifestation IDs must be unique")
        if tuple(view.source_mind for view in self.observable_views) != (
            self.source_mind,
        ) * len(self.observable_views):
            raise ValueError("Interpreter request views must share source_mind")
        if tuple(view.manifestation_id for view in self.observable_views) != tuple(
            sorted(view.manifestation_id for view in self.observable_views)
        ):
            raise ValueError("Interpreter views must use canonical manifestation order")
        expected_refs = tuple(
            CommunicationArtifactRef(
                artifact_id=view.manifestation_id,
                artifact_hash=view.manifestation_hash,
            )
            for view in self.observable_views
        )
        if self.source_manifestation_hashes != expected_refs:
            raise ValueError("Interpreter manifestation hashes differ from its views")
        expected_direction = "R_to_E" if self.source_mind == "E" else "R_to_I"
        if self.relation_direction != expected_direction:
            raise ValueError("Interpreter request carries the wrong directed relation")
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"request_id", "request_hash"}
        )
        if self.request_id != content_id("racio_interpreter_request", id_payload):
            raise ValueError("request_id does not match Racio interpreter request content")
        expected_hash = self.content_hash(exclude_fields=frozenset({"request_hash"}))
        if self.request_hash != expected_hash:
            raise ValueError("request_hash does not match Racio interpreter request content")
        return self

    def validate_against(
        self,
        *,
        manifestations: tuple[EmocioManifestation | InstinktManifestation, ...],
        acceptance_state: AcceptanceState,
        renderer_observations_by_manifestation: Mapping[
            str, tuple[ManifestationObservation, ...]
        ] | None = None,
    ) -> Self:
        manifestation_by_id = {
            manifestation.manifestation_id: manifestation
            for manifestation in manifestations
        }
        if len(manifestation_by_id) != len(manifestations):
            raise ValueError("Trusted manifestation IDs must be unique")
        if set(manifestation_by_id) != {
            view.manifestation_id for view in self.observable_views
        }:
            raise ValueError("Trusted manifestations must exactly match request views")
        trusted_renderer = renderer_observations_by_manifestation or {}
        if not set(trusted_renderer).issubset(manifestation_by_id):
            raise ValueError("Renderer observations cite an unknown manifestation")
        for view in self.observable_views:
            view.validate_against(
                manifestation_by_id[view.manifestation_id],
                renderer_observations=trusted_renderer.get(view.manifestation_id, ()),
            )
        if (
            self.acceptance_state_id != acceptance_state.acceptance_state_id
            or self.acceptance_state_hash != acceptance_state.content_hash()
        ):
            raise ValueError("Interpreter request belongs to another AcceptanceState")
        expected_relation = (
            acceptance_state.R_to_E
            if self.source_mind == "E"
            else acceptance_state.R_to_I
        )
        if self.relation != expected_relation:
            raise ValueError("Interpreter request relation differs from AcceptanceState")
        return self


class RacioInterpretation(FrozenArtifactModel):
    """Racio's inference from an E/I manifestation, without native ground truth."""

    schema_version: Literal["rei-native-racio-interpretation-v1"] = (
        "rei-native-racio-interpretation-v1"
    )
    interpretation_id: NonEmptyId
    interpretation_status: InterpretationStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_request_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_request_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_manifestation_hashes: tuple[CommunicationArtifactRef, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    interpreter_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpreter_revision: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpreter_policy: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    policy_basis: Literal["implementation_hypothesis"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    language: LanguageCode | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    conscious_access_packet_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    conscious_access_packet_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpreter_result_id: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpreter_result_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_mind: InterpretedMindId
    observed_manifestation_ids: tuple[NonEmptyId, ...] = Field(min_length=1)
    observed_manifestations: tuple[ManifestationObservation, ...] = ()
    supporting_observation_ids: tuple[NonEmptyId, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    inferred_option_id: NonEmptyId | None = None
    inferred_action_tendency: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    inferred_motive: str
    inferred_motive_class: NonEmptyId | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    confidence: Score01
    alternative_hypotheses: tuple[str, ...] = ()
    unresolved_ambiguity: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpretation_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @classmethod
    def create_b9(
        cls,
        *,
        request: RacioInterpreterRequest,
        status: Literal["interpreted_b9", "omitted_b9", "unavailable_b9"],
        observations: tuple[ManifestationObservation, ...],
        inferred_option_id: NonEmptyId | None,
        inferred_action_tendency: str | None,
        inferred_motive: str,
        confidence: Score01,
        alternative_hypotheses: tuple[str, ...],
        interpreter_id: NonEmptyId,
        interpreter_revision: NonEmptyText,
        interpreter_policy: NonEmptyText,
    ) -> RacioInterpretation:
        supporting_ids = tuple(
            observation.observation_id
            for observation in observations
            if observation.observation_id is not None
        )
        base: dict[str, object] = {
            "schema_version": "rei-native-racio-interpretation-v1",
            "interpretation_status": status,
            "source_request_id": request.request_id,
            "source_request_hash": request.content_hash(),
            "source_manifestation_hashes": request.source_manifestation_hashes,
            "interpreter_id": interpreter_id,
            "interpreter_revision": interpreter_revision,
            "interpreter_policy": interpreter_policy,
            "policy_basis": "implementation_hypothesis",
            "source_mind": request.source_mind,
            "observed_manifestation_ids": tuple(
                item.artifact_id for item in request.source_manifestation_hashes
            ),
            "observed_manifestations": observations,
            "inferred_option_id": inferred_option_id,
            "inferred_motive": inferred_motive,
            "confidence": confidence,
            "alternative_hypotheses": alternative_hypotheses,
        }
        if supporting_ids:
            base["supporting_observation_ids"] = supporting_ids
        if inferred_action_tendency is not None:
            base["inferred_action_tendency"] = inferred_action_tendency
        interpretation_id = content_id("racio_interpretation", base)
        payload = {"interpretation_id": interpretation_id, **base}
        interpretation = cls(
            **payload,
            interpretation_hash=sha256_hex(payload),
        )
        interpretation.validate_against_request(request)
        return interpretation

    @classmethod
    def create_c3(
        cls,
        *,
        request: RacioInterpreterRequest,
        observations: tuple[ManifestationObservation, ...],
        inferred_option_id: NonEmptyId | None,
        inferred_action_tendency: str | None,
        inferred_motive_class: NonEmptyId | None,
        confidence: Score01,
        alternative_hypotheses: tuple[str, ...],
        unresolved_ambiguity: NonEmptyText | None,
        interpreter_id: NonEmptyId,
        interpreter_revision: NonEmptyText,
        interpreter_policy: NonEmptyText,
        language: LanguageCode,
        conscious_access_packet_id: NonEmptyId,
        conscious_access_packet_hash: HashDigest,
        interpreter_result_id: NonEmptyId,
        interpreter_result_hash: HashDigest,
    ) -> RacioInterpretation:
        """Create the trusted runtime projection of one alias-only C3 result."""

        status: Literal["interpreted_b9", "omitted_b9"] = (
            "interpreted_b9" if observations else "omitted_b9"
        )
        supporting_ids = tuple(
            observation.observation_id
            for observation in observations
            if observation.observation_id is not None
        )
        base: dict[str, object] = {
            "schema_version": "rei-native-racio-interpretation-v1",
            "interpretation_status": status,
            "source_request_id": request.request_id,
            "source_request_hash": request.content_hash(),
            "source_manifestation_hashes": request.source_manifestation_hashes,
            "interpreter_id": interpreter_id,
            "interpreter_revision": interpreter_revision,
            "interpreter_policy": interpreter_policy,
            "policy_basis": "implementation_hypothesis",
            "language": language,
            "conscious_access_packet_id": conscious_access_packet_id,
            "conscious_access_packet_hash": conscious_access_packet_hash,
            "interpreter_result_id": interpreter_result_id,
            "interpreter_result_hash": interpreter_result_hash,
            "source_mind": request.source_mind,
            "observed_manifestation_ids": tuple(
                item.artifact_id for item in request.source_manifestation_hashes
            ),
            "observed_manifestations": observations,
            "inferred_option_id": inferred_option_id,
            "inferred_motive": (
                f"structured_motive_class:{inferred_motive_class}"
                if inferred_motive_class is not None
                else "no_grounded_motive_class"
            ),
            "confidence": confidence,
            "alternative_hypotheses": alternative_hypotheses,
        }
        if supporting_ids:
            base["supporting_observation_ids"] = supporting_ids
        if inferred_action_tendency is not None:
            base["inferred_action_tendency"] = inferred_action_tendency
        if inferred_motive_class is not None:
            base["inferred_motive_class"] = inferred_motive_class
        if unresolved_ambiguity is not None:
            base["unresolved_ambiguity"] = unresolved_ambiguity
        interpretation_id = content_id("racio_interpretation", base)
        payload = {"interpretation_id": interpretation_id, **base}
        interpretation = cls(
            **payload,
            interpretation_hash=sha256_hex(payload),
        )
        interpretation.validate_against_request(request)
        return interpretation

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
        lineage = (
            self.source_request_id,
            self.source_request_hash,
            self.interpreter_id,
            self.interpreter_revision,
            self.interpreter_policy,
            self.policy_basis,
            self.interpretation_hash,
        )
        if self.interpretation_status == "unverified_contract":
            if any(value is not None for value in lineage):
                raise ValueError("Legacy interpretation cannot claim B9 lineage")
            if (
                self.source_manifestation_hashes
                or self.supporting_observation_ids
                or self.inferred_action_tendency is not None
                or self.language is not None
                or self.conscious_access_packet_id is not None
                or self.conscious_access_packet_hash is not None
                or self.interpreter_result_id is not None
                or self.interpreter_result_hash is not None
                or self.inferred_motive_class is not None
                or self.unresolved_ambiguity is not None
            ):
                raise ValueError("Legacy interpretation cannot publish B9 audit fields")
            return self
        if any(value is None for value in lineage):
            raise ValueError("B9 interpretation requires complete request and policy lineage")
        if not self.source_manifestation_hashes:
            raise ValueError("B9 interpretation requires manifestation hash lineage")
        c3_lineage = (
            self.language,
            self.conscious_access_packet_id,
            self.conscious_access_packet_hash,
            self.interpreter_result_id,
            self.interpreter_result_hash,
        )
        if any(value is not None for value in c3_lineage) and any(
            value is None for value in c3_lineage
        ):
            raise ValueError("C3 interpretation requires complete packet/result lineage")
        has_c3_lineage = all(value is not None for value in c3_lineage)
        if (
            self.inferred_motive_class is not None
            or self.unresolved_ambiguity is not None
        ) and not has_c3_lineage:
            raise ValueError("C3 structured fields require packet/result lineage")
        if (
            has_c3_lineage
            and self.inferred_option_id is None
            and self.unresolved_ambiguity is None
        ):
            raise ValueError("C3 option abstention requires unresolved ambiguity")
        if any(
            item.observation_status != "derived_b9"
            for item in self.observed_manifestations
        ):
            raise ValueError("B9 interpretation accepts only structured observations")
        observation_id_set = {
            item.observation_id for item in self.observed_manifestations
        }
        if self.supporting_observation_ids != tuple(
            item.observation_id for item in self.observed_manifestations
        ):
            raise ValueError("Supporting observation IDs must match observations in order")
        if None in observation_id_set:
            raise ValueError("B9 observations require stable IDs")
        if self.interpretation_status == "interpreted_b9":
            if not self.observed_manifestations:
                raise ValueError("An interpreted B9 result requires observations")
        else:
            if (
                self.observed_manifestations
                or self.supporting_observation_ids
                or self.inferred_option_id is not None
                or self.inferred_action_tendency is not None
                or self.confidence != 0.0
                or self.alternative_hypotheses
                or self.inferred_motive_class is not None
            ):
                raise ValueError("Omitted/unavailable interpretation cannot claim an inference")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"interpretation_id", "interpretation_hash"},
        )
        if self.interpretation_id != content_id("racio_interpretation", id_payload):
            raise ValueError("interpretation_id does not match B9 interpretation content")
        expected_hash = self.content_hash(
            exclude_fields=frozenset({"interpretation_hash"})
        )
        if self.interpretation_hash != expected_hash:
            raise ValueError("interpretation_hash does not match B9 interpretation content")
        return self

    def validate_against_request(self, request: RacioInterpreterRequest) -> Self:
        if self.interpretation_status == "unverified_contract":
            raise ValueError("Legacy interpretation has no verified B9 request lineage")
        if (
            self.source_request_id != request.request_id
            or self.source_request_hash != request.content_hash()
        ):
            raise ValueError("Racio interpretation belongs to another request")
        if self.source_mind != request.source_mind:
            raise ValueError("Racio interpretation source mind differs from its request")
        if self.source_manifestation_hashes != request.source_manifestation_hashes:
            raise ValueError("Racio interpretation manifestation lineage differs")
        expected_ids = tuple(
            item.artifact_id for item in request.source_manifestation_hashes
        )
        if self.observed_manifestation_ids != expected_ids:
            raise ValueError("Racio interpretation scope differs from its request")
        if (
            self.inferred_option_id is not None
            and self.inferred_option_id not in request.allowed_option_ids
        ):
            raise ValueError("Racio interpretation selected an option outside its request")
        request_observations = {
            observation.observation_id: observation
            for view in request.observable_views
            for observation in view.observations
        }
        if any(
            request_observations.get(observation.observation_id) != observation
            for observation in self.observed_manifestations
        ):
            raise ValueError("Racio interpretation contains a non-request observation")
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


class FidelityComponent(FrozenModel):
    """One exact typed component in the B9 fixture fidelity metric."""

    facet: Literal["action_tendency"]
    native_value: str
    interpreted_value: str | None = None
    score: Score01
    weight: Score01


class TranslationGap(FrozenArtifactModel):
    """Diagnostic comparison of a native E/I conclusion and Racio's inference."""

    schema_version: Literal["rei-native-translation-gap-v1"] = (
        "rei-native-translation-gap-v1"
    )
    translation_gap_id: NonEmptyId
    gap_status: CommunicationArtifactStatus = Field(
        default="unverified_contract",
        exclude_if=lambda value: value == "unverified_contract",
    )
    source_mind: InterpretedMindId
    source_conclusion_id: NonEmptyId
    source_conclusion_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpretation_id: NonEmptyId
    source_interpretation_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpretation_status: InterpretationStatus | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    native_option_id: NonEmptyId | None = None
    interpreted_option_id: NonEmptyId | None = None
    native_action_tendency: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    interpreted_action_tendency: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    native_motive_summary: str
    interpreted_motive: str
    option_match: bool
    option_comparison_applicable: bool | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    motive_fidelity: Score01
    distortion_type: DistortionType
    fidelity_components: tuple[FidelityComponent, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    metric_policy: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    metric_basis: Literal["implementation_hypothesis"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    distortion_policy: NonEmptyText | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    translation_gap_hash: HashDigest | None = Field(
        default=None, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def validate_option_match(self) -> "TranslationGap":
        actual_match = self.native_option_id == self.interpreted_option_id
        if self.option_match != actual_match:
            raise ValueError("option_match must agree with the recorded option IDs")
        lineage = (
            self.source_conclusion_hash,
            self.source_interpretation_hash,
            self.interpretation_status,
            self.native_action_tendency,
            self.metric_policy,
            self.metric_basis,
            self.distortion_policy,
            self.translation_gap_hash,
        )
        if self.gap_status == "unverified_contract":
            if any(value is not None for value in lineage):
                raise ValueError("Legacy TranslationGap cannot claim B9 lineage")
            if self.fidelity_components or self.interpreted_action_tendency is not None:
                raise ValueError("Legacy TranslationGap cannot publish B9 metric fields")
            return self
        if any(value is None for value in lineage):
            raise ValueError("Evaluated TranslationGap requires complete B9 lineage")
        expected_applicability = (
            self.native_option_id is not None
            and self.interpreted_option_id is not None
        )
        if self.option_comparison_applicable != expected_applicability:
            raise ValueError(
                "option_comparison_applicable must record whether both option IDs exist"
            )
        if self.metric_policy != B9_EXACT_ACTION_FIDELITY_POLICY:
            raise ValueError("Unknown B9 translation fidelity policy")
        if self.distortion_policy != B9_EXACT_DISTORTION_POLICY:
            raise ValueError("Unknown B9 translation distortion policy")
        if len(self.fidelity_components) != 1:
            raise ValueError("B9 fixture fidelity requires exactly one typed component")
        component = self.fidelity_components[0]
        if component.facet != "action_tendency" or component.weight != 1.0:
            raise ValueError("B9 fixture fidelity is exact action tendency with weight one")
        if component.native_value != self.native_action_tendency:
            raise ValueError("TranslationGap native action component differs")
        if component.interpreted_value != self.interpreted_action_tendency:
            raise ValueError("TranslationGap interpreted action component differs")
        if not math.isclose(
            self.motive_fidelity,
            component.score,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("motive_fidelity must replay from typed components")
        omitted = self.interpretation_status in {"omitted_b9", "unavailable_b9"}
        if omitted:
            expected_distortion: DistortionType = "omission"
        elif self.native_option_id is None and self.interpreted_option_id is None:
            # Equality of two unavailable option IDs is not a successful translation.
            expected_distortion = "unknown"
        elif self.option_match and component.score == 1.0:
            expected_distortion = "none"
        elif not self.option_match or component.score == 0.0:
            expected_distortion = "misclassification"
        else:
            expected_distortion = "unknown"
        if self.distortion_type != expected_distortion:
            raise ValueError("distortion_type does not replay from objective B9 fields")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"translation_gap_id", "translation_gap_hash"},
        )
        if self.translation_gap_id != content_id("translation_gap", id_payload):
            raise ValueError("translation_gap_id does not match evaluated gap content")
        expected_hash = self.content_hash(
            exclude_fields=frozenset({"translation_gap_hash"})
        )
        if self.translation_gap_hash != expected_hash:
            raise ValueError("translation_gap_hash does not match evaluated gap content")
        return self


class AcceptanceFidelityAssessment(FrozenArtifactModel):
    """Record-only comparison; it neither infers acceptance nor changes authority."""

    schema_version: Literal["rei-native-acceptance-fidelity-assessment-v1"] = (
        "rei-native-acceptance-fidelity-assessment-v1"
    )
    assessment_id: NonEmptyId
    source_mind: InterpretedMindId
    acceptance_state_id: NonEmptyId
    acceptance_state_hash: HashDigest
    relation_direction: RelationDirection
    declared_interpretation_fidelity: Score01
    translation_gap_id: NonEmptyId
    translation_gap_hash: HashDigest
    measured_motive_fidelity: Score01
    absolute_difference: Score01
    comparison: Literal["measured_lower", "equal", "measured_higher"]
    audit_policy: Literal[
        "b9-acceptance-fidelity-record-only-v1"
    ] = B9_ACCEPTANCE_FIDELITY_AUDIT_POLICY
    assessment_hash: HashDigest

    @model_validator(mode="after")
    def validate_assessment(self) -> Self:
        expected_direction = "R_to_E" if self.source_mind == "E" else "R_to_I"
        if self.relation_direction != expected_direction:
            raise ValueError("Acceptance fidelity uses the wrong directed relation")
        expected_difference = abs(
            self.measured_motive_fidelity - self.declared_interpretation_fidelity
        )
        if not math.isclose(
            self.absolute_difference,
            expected_difference,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("Acceptance fidelity difference does not replay")
        delta = self.measured_motive_fidelity - self.declared_interpretation_fidelity
        expected_comparison = (
            "equal"
            if math.isclose(delta, 0.0, rel_tol=0.0, abs_tol=1e-12)
            else "measured_higher"
            if delta > 0.0
            else "measured_lower"
        )
        if self.comparison != expected_comparison:
            raise ValueError("Acceptance fidelity comparison does not replay")
        id_payload = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"assessment_id", "assessment_hash"},
        )
        if self.assessment_id != content_id("acceptance_fidelity", id_payload):
            raise ValueError("assessment_id does not match fidelity audit content")
        expected_hash = self.content_hash(
            exclude_fields=frozenset({"assessment_hash"})
        )
        if self.assessment_hash != expected_hash:
            raise ValueError("assessment_hash does not match fidelity audit content")
        return self


__all__ = [
    "AcceptanceFidelityAssessment",
    "AcceptanceMode",
    "AcceptanceState",
    "B9_ACCEPTANCE_FIDELITY_AUDIT_POLICY",
    "B9_EXACT_ACTION_FIDELITY_POLICY",
    "B9_EXACT_DISTORTION_POLICY",
    "B9_FIXTURE_EMOCIO_PROJECTION_POLICY",
    "CommunicationArtifactRef",
    "CommunicationArtifactStatus",
    "DirectedMindRelation",
    "DistortionType",
    "EmocioManifestation",
    "FidelityComponent",
    "InstinktManifestation",
    "InterpretedMindId",
    "InterpretationStatus",
    "ManifestationObservation",
    "ObservableManifestationView",
    "ObservableSignalName",
    "ObservationProvenance",
    "RacioInterpreterRequest",
    "RacioInterpretation",
    "RelationDirection",
    "TranslationGap",
]
