"""C3 conscious-access filtering with a provider-visible non-interference boundary.

The trusted request and acceptance relation stay in the audit record.  A model
receives only :class:`ConsciousAccessPacket`, whose observation, option and
artifact identifiers are packet-local aliases that reveal no native IDs or
hashes.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Literal, Mapping, Self

from pydantic import Field, model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    LanguageCode,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.communication import (
    InterpretedMindId,
    ManifestationObservation,
    RacioInterpreterRequest,
)


CONSCIOUS_ACCESS_POLICY_ID = "c3-conscious-access-filter-v1"

InterpreterAblationMode = Literal[
    "structured_only",
    "image_only",
    "structured_plus_image",
    "body_structured_only",
    "body_graph_plus_structured",
]
ConsciousObservationStatus = Literal["clear", "degraded"]
VisibleArtifactKind = Literal["emocio_image", "body_trajectory_graph"]

_IMAGE_SIGNAL_NAMES = frozenset(
    {"visible_image_artifact_id", "renderer_interpretation"}
)


def _round_score(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 12)


def _canonical_json_text(value: object) -> str:
    return canonical_json_bytes(value).decode("utf-8")


class TrustedVisibleArtifact(FrozenModel):
    """Trusted artifact input retained outside the provider-visible packet."""

    source_artifact_id: NonEmptyId
    source_artifact_hash: HashDigest
    kind: VisibleArtifactKind
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/svg+xml"]


class ConsciousAccessObservation(FrozenModel):
    """One packet-local perceived signal with no native lineage fields."""

    observation_id: NonEmptyId
    signal_name: NonEmptyId
    perception_status: ConsciousObservationStatus
    perceived_value_json: str | None = None
    provenance: Literal["manifested", "renderer_added_ungrounded"]
    public_artifact_ids: tuple[NonEmptyId, ...] = ()

    @model_validator(mode="after")
    def validate_perception(self) -> Self:
        if self.public_artifact_ids != tuple(sorted(set(self.public_artifact_ids))):
            raise ValueError("Public artifact IDs must be sorted and unique")
        if self.perception_status == "degraded":
            if self.perceived_value_json is not None:
                raise ValueError("A degraded observation cannot expose its exact value")
            return self
        if self.perceived_value_json is None:
            raise ValueError("A clear observation requires a perceived value")
        try:
            value = json.loads(self.perceived_value_json)
        except json.JSONDecodeError as exc:
            raise ValueError("Perceived values must be valid JSON") from exc
        if _canonical_json_text(value) != self.perceived_value_json:
            raise ValueError("Perceived values must use canonical JSON")
        return self


class ConsciousAccessOption(FrozenModel):
    """A packet-local option alias plus a consciously public description."""

    option_id: NonEmptyId
    description: NonEmptyText


class ConsciousAccessArtifact(FrozenModel):
    """Provider-visible artifact metadata without storage or native identifiers."""

    artifact_id: NonEmptyId
    kind: VisibleArtifactKind
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/svg+xml"]


class ConsciousAccessPacket(FrozenArtifactModel):
    """The complete and only semantic payload admitted to an interpreter model."""

    schema_version: Literal["rei-conscious-access-packet-v1"] = (
        "rei-conscious-access-packet-v1"
    )
    packet_id: NonEmptyId
    source_mind: InterpretedMindId
    language: LanguageCode
    ablation_mode: InterpreterAblationMode
    visible_observations: tuple[ConsciousAccessObservation, ...] = ()
    omitted_observation_ids: tuple[NonEmptyId, ...] = ()
    degraded_observation_ids: tuple[NonEmptyId, ...] = ()
    visible_artifacts: tuple[ConsciousAccessArtifact, ...] = ()
    visible_artifact_ids: tuple[NonEmptyId, ...] = ()
    public_option_scope: tuple[ConsciousAccessOption, ...] = ()
    channel_quality: Score01
    uncertainty: NonEmptyText
    filter_policy: Literal["c3-conscious-access-filter-v1"] = (
        CONSCIOUS_ACCESS_POLICY_ID
    )
    packet_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        source_mind: InterpretedMindId,
        language: LanguageCode,
        ablation_mode: InterpreterAblationMode,
        visible_observations: tuple[ConsciousAccessObservation, ...],
        omitted_observation_ids: tuple[NonEmptyId, ...],
        visible_artifacts: tuple[ConsciousAccessArtifact, ...],
        public_option_scope: tuple[ConsciousAccessOption, ...],
        channel_quality: Score01,
        uncertainty: NonEmptyText,
    ) -> "ConsciousAccessPacket":
        canonical_observations = tuple(
            sorted(visible_observations, key=lambda item: item.observation_id)
        )
        canonical_omitted = tuple(sorted(set(omitted_observation_ids)))
        canonical_artifacts = tuple(
            sorted(visible_artifacts, key=lambda item: item.artifact_id)
        )
        canonical_options = tuple(
            sorted(public_option_scope, key=lambda item: item.option_id)
        )
        degraded = tuple(
            item.observation_id
            for item in canonical_observations
            if item.perception_status == "degraded"
        )
        base = {
            "schema_version": "rei-conscious-access-packet-v1",
            "source_mind": source_mind,
            "language": language,
            "ablation_mode": ablation_mode,
            "visible_observations": canonical_observations,
            "omitted_observation_ids": canonical_omitted,
            "degraded_observation_ids": degraded,
            "visible_artifacts": canonical_artifacts,
            "visible_artifact_ids": tuple(
                item.artifact_id for item in canonical_artifacts
            ),
            "public_option_scope": canonical_options,
            "channel_quality": channel_quality,
            "uncertainty": uncertainty,
            "filter_policy": CONSCIOUS_ACCESS_POLICY_ID,
        }
        packet_id = content_id("conscious_access", base)
        payload = {"packet_id": packet_id, **base}
        return cls(**payload, packet_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_packet(self) -> Self:
        visible_ids = tuple(item.observation_id for item in self.visible_observations)
        if visible_ids != tuple(sorted(set(visible_ids))):
            raise ValueError("Visible observation aliases must be sorted and unique")
        if self.omitted_observation_ids != tuple(
            sorted(set(self.omitted_observation_ids))
        ):
            raise ValueError("Omitted observation aliases must be sorted and unique")
        if set(visible_ids).intersection(self.omitted_observation_ids):
            raise ValueError("Visible and omitted observation scopes must be disjoint")
        expected_degraded = tuple(
            item.observation_id
            for item in self.visible_observations
            if item.perception_status == "degraded"
        )
        if self.degraded_observation_ids != expected_degraded:
            raise ValueError("Degraded aliases must exactly match degraded observations")
        artifact_ids = tuple(item.artifact_id for item in self.visible_artifacts)
        if artifact_ids != tuple(sorted(set(artifact_ids))):
            raise ValueError("Visible artifact aliases must be sorted and unique")
        if self.visible_artifact_ids != artifact_ids:
            raise ValueError("Visible artifact IDs differ from artifact metadata")
        if any(
            not set(item.public_artifact_ids).issubset(artifact_ids)
            for item in self.visible_observations
        ):
            raise ValueError("An observation cites an artifact outside packet scope")
        option_ids = tuple(item.option_id for item in self.public_option_scope)
        if option_ids != tuple(sorted(set(option_ids))):
            raise ValueError("Public option aliases must be sorted and unique")
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"packet_id", "packet_hash"}
        )
        if self.packet_id != content_id("conscious_access", id_payload):
            raise ValueError("packet_id differs from conscious-access content")
        if self.packet_hash != self.content_hash(
            exclude_fields=frozenset({"packet_hash"})
        ):
            raise ValueError("packet_hash differs from conscious-access content")
        return self

    def provider_payload(self) -> dict[str, object]:
        """Return the explicit transport allowlist; audit lineage is unreachable."""

        return {
            "schema_version": self.schema_version,
            "source_mind": self.source_mind,
            "language": self.language,
            "ablation_mode": self.ablation_mode,
            "visible_observations": [
                item.model_dump(mode="json") for item in self.visible_observations
            ],
            "omitted_observation_ids": list(self.omitted_observation_ids),
            "degraded_observation_ids": list(self.degraded_observation_ids),
            "visible_artifacts": [
                item.model_dump(mode="json") for item in self.visible_artifacts
            ],
            "visible_artifact_ids": list(self.visible_artifact_ids),
            "public_option_scope": [
                item.model_dump(mode="json") for item in self.public_option_scope
            ],
            "channel_quality": self.channel_quality,
            "uncertainty": self.uncertainty,
        }

    def provider_payload_bytes(self) -> bytes:
        return canonical_json_bytes(self.provider_payload())


class ConsciousObservationLineage(FrozenModel):
    public_observation_id: NonEmptyId
    source_observation_id: NonEmptyId
    source_observation_hash: HashDigest
    source_manifestation_id: NonEmptyId
    source_manifestation_hash: HashDigest


class ConsciousOptionLineage(FrozenModel):
    public_option_id: NonEmptyId
    source_option_id: NonEmptyId


class ConsciousArtifactLineage(FrozenModel):
    public_artifact_id: NonEmptyId
    source_artifact_id: NonEmptyId
    source_artifact_hash: HashDigest
    kind: VisibleArtifactKind


class ConsciousAccessAudit(FrozenArtifactModel):
    """Trusted replay record. This object must never be serialized to a model."""

    schema_version: Literal["rei-conscious-access-audit-v1"] = (
        "rei-conscious-access-audit-v1"
    )
    audit_id: NonEmptyId
    source_request_id: NonEmptyId
    source_request_hash: HashDigest
    acceptance_state_id: NonEmptyId
    acceptance_state_hash: HashDigest
    relation_direction: Literal["R_to_E", "R_to_I"]
    packet_id: NonEmptyId
    packet_hash: HashDigest
    observation_lineage: tuple[ConsciousObservationLineage, ...]
    option_lineage: tuple[ConsciousOptionLineage, ...]
    artifact_lineage: tuple[ConsciousArtifactLineage, ...]
    effective_visibility: Score01
    signal_fidelity: Score01
    suppression: Score01
    signal_noise: Score01
    delegation_openness: Score01
    filter_seed: int = Field(ge=0)
    filter_policy: Literal["c3-conscious-access-filter-v1"] = (
        CONSCIOUS_ACCESS_POLICY_ID
    )
    audit_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        request: RacioInterpreterRequest,
        packet: ConsciousAccessPacket,
        observation_lineage: tuple[ConsciousObservationLineage, ...],
        option_lineage: tuple[ConsciousOptionLineage, ...],
        artifact_lineage: tuple[ConsciousArtifactLineage, ...],
        effective_visibility: Score01,
        signal_fidelity: Score01,
        suppression: Score01,
        signal_noise: Score01,
        delegation_openness: Score01,
        filter_seed: int,
    ) -> "ConsciousAccessAudit":
        base = {
            "schema_version": "rei-conscious-access-audit-v1",
            "source_request_id": request.request_id,
            "source_request_hash": request.content_hash(),
            "acceptance_state_id": request.acceptance_state_id,
            "acceptance_state_hash": request.acceptance_state_hash,
            "relation_direction": request.relation_direction,
            "packet_id": packet.packet_id,
            "packet_hash": packet.content_hash(),
            "observation_lineage": observation_lineage,
            "option_lineage": option_lineage,
            "artifact_lineage": artifact_lineage,
            "effective_visibility": effective_visibility,
            "signal_fidelity": signal_fidelity,
            "suppression": suppression,
            "signal_noise": signal_noise,
            "delegation_openness": delegation_openness,
            "filter_seed": filter_seed,
            "filter_policy": CONSCIOUS_ACCESS_POLICY_ID,
        }
        audit_id = content_id("conscious_audit", base)
        payload = {"audit_id": audit_id, **base}
        return cls(**payload, audit_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_audit(self) -> Self:
        for name in ("observation_lineage", "option_lineage", "artifact_lineage"):
            values = getattr(self, name)
            public_ids = tuple(getattr(item, next(
                field for field in type(item).model_fields if field.startswith("public_")
            )) for item in values)
            if len(set(public_ids)) != len(public_ids):
                raise ValueError(f"{name} public aliases must be unique")
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"audit_id", "audit_hash"}
        )
        if self.audit_id != content_id("conscious_audit", id_payload):
            raise ValueError("audit_id differs from conscious-access audit content")
        if self.audit_hash != self.content_hash(
            exclude_fields=frozenset({"audit_hash"})
        ):
            raise ValueError("audit_hash differs from conscious-access audit content")
        return self

    def source_observation_id(self, public_observation_id: str) -> str:
        matches = [
            item.source_observation_id
            for item in self.observation_lineage
            if item.public_observation_id == public_observation_id
        ]
        if len(matches) != 1:
            raise ValueError("Unknown or ambiguous public observation alias")
        return matches[0]

    def source_option_id(self, public_option_id: str) -> str:
        matches = [
            item.source_option_id
            for item in self.option_lineage
            if item.public_option_id == public_option_id
        ]
        if len(matches) != 1:
            raise ValueError("Unknown or ambiguous public option alias")
        return matches[0]


@dataclass(frozen=True, slots=True)
class ConsciousAccessResult:
    packet: ConsciousAccessPacket
    audit: ConsciousAccessAudit


def _safe_observation_key(observation: ManifestationObservation) -> tuple[str, ...]:
    """Order by visible content; native IDs are only a final audit tiebreaker."""

    if observation.signal_name == "visible_image_artifact_id":
        # The manifested value/content contains the storage ID.  Storage IDs are
        # trusted lineage, so alias ordering uses only the public signal kind and
        # the independently verified image bytes hash.
        public_value = ""
        public_content = ""
    else:
        public_value = observation.canonical_json_value or ""
        public_content = observation.content

    return (
        observation.signal_name or "",
        public_value,
        observation.provenance,
        observation.source_image_artifact_hash or "",
        public_content,
        observation.observation_id or "",
    )


def _rank(*, alias: str, seed: int, stage: str) -> str:
    return sha256_hex(
        {
            "policy": CONSCIOUS_ACCESS_POLICY_ID,
            "seed": seed,
            "stage": stage,
            "alias": alias,
        }
    )


@dataclass(frozen=True, slots=True)
class ConsciousAccessFilter:
    """Apply one fixed implementation-hypothesis mapping from acceptance to signal."""

    seed: int = 0

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("Conscious-access filter seed must be non-negative")

    def apply(
        self,
        request: RacioInterpreterRequest,
        *,
        language: LanguageCode = "sl",
        ablation_mode: InterpreterAblationMode = "structured_only",
        option_descriptions: Mapping[str, str] | None = None,
        supplemental_artifacts: tuple[TrustedVisibleArtifact, ...] = (),
    ) -> ConsciousAccessResult:
        relation = request.relation
        if ablation_mode in {"body_structured_only", "body_graph_plus_structured"}:
            if request.source_mind != "I":
                raise ValueError("Body ablations require an Instinkt access request")
        if ablation_mode == "image_only" and request.source_mind != "E":
            raise ValueError("Image-only ablation requires an Emocio access request")
        if supplemental_artifacts and ablation_mode not in {
            "structured_plus_image",
            "body_graph_plus_structured",
        }:
            raise ValueError("This ablation mode cannot expose supplemental artifacts")
        if any(
            item.kind != "body_trajectory_graph"
            for item in supplemental_artifacts
        ) and request.source_mind == "I":
            raise ValueError("Instinkt supplemental artifacts must be body graphs")
        source_artifact_ids = tuple(
            item.source_artifact_id for item in supplemental_artifacts
        )
        if len(set(source_artifact_ids)) != len(source_artifact_ids):
            raise ValueError("Supplemental artifact IDs must be unique")

        observations = tuple(
            sorted(
                (
                    observation
                    for view in request.observable_views
                    for observation in view.observations
                ),
                key=_safe_observation_key,
            )
        )
        source_observation_ids = tuple(
            observation.observation_id for observation in observations
        )
        if None in source_observation_ids:
            raise ValueError("Conscious access requires stable source observation IDs")
        if len(set(source_observation_ids)) != len(source_observation_ids):
            raise ValueError("Source observation IDs must be unique")
        aliases = {
            observation.observation_id: f"observation_{index:03d}"
            for index, observation in enumerate(observations, start=1)
        }

        artifact_inputs: list[TrustedVisibleArtifact] = list(supplemental_artifacts)
        for observation in observations:
            if observation.source_image_artifact_id is None:
                continue
            if observation.source_image_artifact_hash is None:
                raise ValueError("Visible image observation is missing its byte hash")
            artifact_inputs.append(
                TrustedVisibleArtifact(
                    source_artifact_id=observation.source_image_artifact_id,
                    source_artifact_hash=observation.source_image_artifact_hash,
                    kind="emocio_image",
                    media_type="image/png",
                )
            )
        artifact_by_source: dict[str, TrustedVisibleArtifact] = {}
        for item in artifact_inputs:
            prior = artifact_by_source.get(item.source_artifact_id)
            if prior is not None and prior != item:
                raise ValueError("Visible artifact lineage is ambiguous")
            artifact_by_source[item.source_artifact_id] = item
        canonical_artifacts = tuple(
            sorted(
                artifact_by_source.values(),
                key=lambda item: (
                    item.kind,
                    item.source_artifact_hash,
                    item.source_artifact_id,
                ),
            )
        )
        artifact_aliases = {
            item.source_artifact_id: f"artifact_{index:03d}"
            for index, item in enumerate(canonical_artifacts, start=1)
        }

        def admitted_by_ablation(observation: ManifestationObservation) -> bool:
            is_image = observation.signal_name in _IMAGE_SIGNAL_NAMES
            if ablation_mode == "image_only":
                return is_image
            if ablation_mode in {
                "structured_only",
                "body_structured_only",
                "body_graph_plus_structured",
            }:
                return not is_image
            return True

        admitted = tuple(
            observation for observation in observations if admitted_by_ablation(observation)
        )
        suppression = _round_score(
            (1.0 - relation.tolerance) * relation.sabotage_risk
        )
        effective_visibility = _round_score(
            relation.visibility * (1.0 - suppression)
        )
        signal_fidelity = _round_score(
            relation.interpretation_fidelity
            * (1.0 - 0.5 * relation.sabotage_risk)
        )
        signal_noise = _round_score(1.0 - signal_fidelity)
        delegation_openness = _round_score(relation.delegation_willingness)

        if not admitted or effective_visibility == 0.0:
            visible_count = 0
        else:
            visible_count = min(
                len(admitted),
                max(1, math.ceil(len(admitted) * effective_visibility)),
            )
        ranked_visible = tuple(
            sorted(
                admitted,
                key=lambda item: _rank(
                    alias=aliases[item.observation_id],
                    seed=self.seed,
                    stage="visibility",
                ),
            )[:visible_count]
        )
        if not ranked_visible or signal_fidelity == 0.0:
            clear_count = 0
        else:
            clear_count = min(
                len(ranked_visible),
                max(1, math.ceil(len(ranked_visible) * signal_fidelity)),
            )
        clear_ids = {
            item.observation_id
            for item in sorted(
                ranked_visible,
                key=lambda item: _rank(
                    alias=aliases[item.observation_id],
                    seed=self.seed,
                    stage="fidelity",
                ),
            )[:clear_count]
        }
        selected_ids = {item.observation_id for item in ranked_visible}

        visible_public: list[ConsciousAccessObservation] = []
        used_artifact_source_ids: set[str] = set()
        for observation in ranked_visible:
            source_id = observation.observation_id
            assert source_id is not None
            source_artifact_id = observation.source_image_artifact_id
            public_artifact_ids = (
                (artifact_aliases[source_artifact_id],)
                if source_artifact_id is not None
                else ()
            )
            used_artifact_source_ids.update(
                (source_artifact_id,) if source_artifact_id is not None else ()
            )
            if source_id not in clear_ids:
                perceived_value = None
                status: ConsciousObservationStatus = "degraded"
            elif observation.signal_name == "visible_image_artifact_id":
                perceived_value = _canonical_json_text(public_artifact_ids[0])
                status = "clear"
            else:
                perceived_value = observation.canonical_json_value
                status = "clear"
            if observation.signal_name is None:
                raise ValueError("Conscious access requires typed signal names")
            visible_public.append(
                ConsciousAccessObservation(
                    observation_id=aliases[source_id],
                    signal_name=observation.signal_name,
                    perception_status=status,
                    perceived_value_json=perceived_value,
                    provenance=observation.provenance,
                    public_artifact_ids=public_artifact_ids,
                )
            )

        if effective_visibility > 0.0 and ablation_mode in {
            "body_graph_plus_structured",
            "structured_plus_image",
        }:
            supplemental_visible_count = min(
                len(supplemental_artifacts),
                max(
                    1,
                    math.ceil(
                        len(supplemental_artifacts) * effective_visibility
                    ),
                ),
            )
            selected_supplemental = sorted(
                supplemental_artifacts,
                key=lambda item: _rank(
                    alias=artifact_aliases[item.source_artifact_id],
                    seed=self.seed,
                    stage="artifact_visibility",
                ),
            )[:supplemental_visible_count]
            used_artifact_source_ids.update(
                item.source_artifact_id for item in selected_supplemental
            )
        visible_artifacts = tuple(
            ConsciousAccessArtifact(
                artifact_id=artifact_aliases[item.source_artifact_id],
                kind=item.kind,
                media_type=item.media_type,
            )
            for item in canonical_artifacts
            if item.source_artifact_id in used_artifact_source_ids
        )

        expected_option_ids = set(request.allowed_option_ids)
        if option_descriptions is not None and set(option_descriptions) != expected_option_ids:
            raise ValueError("Option descriptions must exactly cover public option scope")
        option_rows = tuple(
            sorted(
                (
                    (
                        option_id,
                        (
                            option_descriptions[option_id]
                            if option_descriptions is not None
                            else "Available option"
                        ),
                    )
                    for option_id in request.allowed_option_ids
                ),
                key=lambda item: (item[1], item[0]),
            )
        )
        public_options = tuple(
            ConsciousAccessOption(
                option_id=f"option_{index:03d}",
                description=description,
            )
            for index, (_, description) in enumerate(option_rows, start=1)
        )

        omitted_ids = tuple(
            aliases[item.observation_id]
            for item in observations
            if item.observation_id not in selected_ids
        )
        channel_quality = _round_score(
            effective_visibility
            * (
                0.70 * signal_fidelity
                + 0.15 * relation.tolerance
                + 0.15 * delegation_openness
            )
        )
        if not visible_public:
            channel_quality = 0.0
        uncertainty = (
            "Filter lahko zavestno izpusti ali oslabi del signala; sklep naj ostane hipoteza."
            if language == "sl"
            else "The filter may omit or degrade part of the signal; keep any inference hypothetical."
        )
        packet = ConsciousAccessPacket.create(
            source_mind=request.source_mind,
            language=language,
            ablation_mode=ablation_mode,
            visible_observations=tuple(visible_public),
            omitted_observation_ids=omitted_ids,
            visible_artifacts=visible_artifacts,
            public_option_scope=public_options,
            channel_quality=channel_quality,
            uncertainty=uncertainty,
        )
        observation_lineage = tuple(
            ConsciousObservationLineage(
                public_observation_id=aliases[item.observation_id],
                source_observation_id=item.observation_id,
                source_observation_hash=item.content_hash(),
                source_manifestation_id=item.manifestation_id,
                source_manifestation_hash=item.source_manifestation_hash,
            )
            for item in observations
            if item.observation_id is not None
            and item.source_manifestation_hash is not None
        )
        option_lineage = tuple(
            ConsciousOptionLineage(
                public_option_id=public.option_id,
                source_option_id=source_id,
            )
            for public, (source_id, _) in zip(public_options, option_rows, strict=True)
        )
        artifact_lineage = tuple(
            ConsciousArtifactLineage(
                public_artifact_id=artifact_aliases[item.source_artifact_id],
                source_artifact_id=item.source_artifact_id,
                source_artifact_hash=item.source_artifact_hash,
                kind=item.kind,
            )
            for item in canonical_artifacts
        )
        audit = ConsciousAccessAudit.create(
            request=request,
            packet=packet,
            observation_lineage=observation_lineage,
            option_lineage=option_lineage,
            artifact_lineage=artifact_lineage,
            effective_visibility=effective_visibility,
            signal_fidelity=signal_fidelity,
            suppression=suppression,
            signal_noise=signal_noise,
            delegation_openness=delegation_openness,
            filter_seed=self.seed,
        )
        return ConsciousAccessResult(packet=packet, audit=audit)


__all__ = [
    "CONSCIOUS_ACCESS_POLICY_ID",
    "ConsciousAccessArtifact",
    "ConsciousAccessAudit",
    "ConsciousAccessFilter",
    "ConsciousAccessObservation",
    "ConsciousAccessOption",
    "ConsciousAccessPacket",
    "ConsciousAccessResult",
    "ConsciousArtifactLineage",
    "ConsciousObservationLineage",
    "ConsciousOptionLineage",
    "InterpreterAblationMode",
    "TrustedVisibleArtifact",
]
