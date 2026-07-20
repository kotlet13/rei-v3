from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from ..ids import canonical_json_bytes, sha256_hex


MindId = Literal["R", "E", "I"]
LanguageCode = Literal["sl", "en"]
SourceModality = Literal[
    "text",
    "image",
    "video",
    "audio",
    "body",
    "smell",
    "taste",
    "simulator",
]

NonEmptyId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SchemaVersion = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9._-]*$",
    ),
]
HashDigest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
CommitDigest = Annotated[
    str,
    StringConstraints(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"),
]
Score01 = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


def _validate_artifact_relative_path(value: str) -> str:
    """Require one portable path below a run's artifact root."""

    if "\\" in value:
        raise ValueError("Artifact paths must use canonical forward slashes")
    if value.startswith("/"):
        raise ValueError("Artifact paths must be relative")
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("Artifact paths cannot contain empty, dot, or traversal segments")
    windows_forbidden = set('<>:"|?*')
    if any(
        any(character in windows_forbidden for character in segment)
        for segment in segments
    ):
        raise ValueError("Artifact paths must be portable across supported platforms")
    if any(
        segment != segment.strip() or segment.endswith(".")
        for segment in segments
    ):
        raise ValueError("Artifact path segments cannot have edge spaces or trailing dots")
    if any(
        any(ord(character) < 32 or ord(character) == 127 for character in segment)
        for segment in segments
    ):
        raise ValueError("Artifact paths cannot contain control characters")
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    if any(
        segment.split(".", 1)[0].rstrip(" .").upper() in reserved_names
        for segment in segments
    ):
        raise ValueError("Artifact paths cannot use reserved platform device names")
    return value


ArtifactRelativePath = Annotated[
    str,
    StringConstraints(min_length=1),
    AfterValidator(_validate_artifact_relative_path),
]


def _normalize_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


UtcTimestamp = Annotated[AwareDatetime, AfterValidator(_normalize_utc)]


PUBLIC_SAFETY_CAVEAT_SL = (
    "REI-v3 je konceptualni simulator teorije REI; ni diagnostično orodje, "
    "empirično potrjena psihologija ali model resnične osebe."
)


PUBLIC_SAFETY_CAVEAT_EN = (
    "REI-v3 is a conceptual simulator of REI theory; it is not a diagnostic "
    "tool, empirically validated psychology, or a model of a real person."
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        validate_assignment=True,
        validate_default=True,
    )

    def canonical_json_bytes(self, *, exclude_fields: frozenset[str] = frozenset()) -> bytes:
        return canonical_json_bytes(self, exclude_fields=exclude_fields)

    def content_hash(self, *, exclude_fields: frozenset[str] = frozenset()) -> str:
        return sha256_hex(self, exclude_fields=exclude_fields)


class FrozenModel(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        frozen=True,
        validate_default=True,
    )


class ArtifactModel(StrictModel):
    """Mutable construction record with an explicit schema contract.

    Concrete artifacts provide a domain-specific stable ID such as ``event_id``
    or ``decision_id``. A generic ID is intentionally not added because it would
    duplicate and obscure those canonical fields.
    """

    schema_version: SchemaVersion

    @model_validator(mode="after")
    def require_domain_id(self) -> ArtifactModel:
        id_fields = (
            name
            for name in type(self).model_fields
            if name == "id" or (name.endswith("_id") and not name.endswith("_ids"))
        )
        if not any(getattr(self, name, None) for name in id_fields):
            raise ValueError("Every artifact must carry a non-empty domain-specific ID")
        return self


class FrozenArtifactModel(FrozenModel):
    schema_version: SchemaVersion

    @model_validator(mode="after")
    def require_domain_id(self) -> FrozenArtifactModel:
        id_fields = (
            name
            for name in type(self).model_fields
            if name == "id" or (name.endswith("_id") and not name.endswith("_ids"))
        )
        if not any(getattr(self, name, None) for name in id_fields):
            raise ValueError("Every artifact must carry a non-empty domain-specific ID")
        return self


class SafetyNotice(FrozenModel):
    conceptual_simulator: Literal[True] = True
    diagnostic_use_allowed: Literal[False] = False
    real_person_characterization_allowed: Literal[False] = False
    canonical_sl: str = PUBLIC_SAFETY_CAVEAT_SL
