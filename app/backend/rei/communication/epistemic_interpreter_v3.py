"""Isolated v3 contract for bounded, bilingual Racio interpretation.

The historical C3 v1 and Gemma epistemic v2 contracts are deliberately not
modified by this module.  V3 separates action families from exact action
subtypes, treats model support modes as claims rather than evaluator truth,
and represents a reviewed Slovene/English gloss as one evidence identity.

This is a communication contract only.  It has no provider, runtime,
governance, decision, or behavioural authority.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from types import MappingProxyType
from typing import Annotated, Final, Literal, Mapping, Self

from pydantic import Field, StringConstraints, model_validator

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from .epistemic_interpreter import (
    MOTIVE_SUBTYPES_BY_FAMILY,
    MOTIVE_UNKNOWN_REASON_SL,
    MotorSocialMotiveSubtype,
    MotiveFamily,
    ProtectionMotiveSubtype,
    RacioReportedUncertainty,
    SceneMotiveSubtype,
    motive_subtype_belongs_to_family,
)


ActionFamilyV3 = Literal[
    "approach_engage",
    "protection_regulation",
    "confrontation",
    "execution_expression",
]
ApproachEngageActionSubtypeV3 = Literal[
    "approach",
    "connect",
    "seek_contact",
    "maintain_contact",
]
ProtectionRegulationActionSubtypeV3 = Literal[
    "set_boundary",
    "seek_safety",
    "retreat",
    "withdraw_contact",
    "freeze",
    "conserve",
    "maintain_boundary",
]
ConfrontationActionSubtypeV3 = Literal[
    "attack",
    "compete",
    "remove_obstacle",
]
ExecutionExpressionActionSubtypeV3 = Literal[
    "perform",
    "improvise",
    "coordinate",
    "maintain_execution",
]
ActionSubtypeV3 = (
    ApproachEngageActionSubtypeV3
    | ProtectionRegulationActionSubtypeV3
    | ConfrontationActionSubtypeV3
    | ExecutionExpressionActionSubtypeV3
)
ActionFamilyFallbackV3 = Literal["protect"]
ActionSupportModeV3 = Literal[
    "direct_manifestation",
    "functional_inference",
    "speculative",
]
MotiveSubtypeV3 = (
    SceneMotiveSubtype | MotorSocialMotiveSubtype | ProtectionMotiveSubtype
)
MotiveSupportModeV3 = Literal[
    "directly_supported",
    "contextually_supported",
    "speculative",
]
PresentationModeV3 = Literal[
    "canonical_sl_only",
    "operational_en_only",
    "canonical_sl_plus_operational_en",
]

OpaqueSignalAliasV3 = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^signal_[0-9]{3,}$",
        max_length=80,
    ),
]
AtomicEvidenceUnitIdV3 = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^atomic_[0-9]{3,}$",
        max_length=80,
    ),
]

ACTION_SUBTYPES_BY_FAMILY_V3: Final[Mapping[str, frozenset[str]]] = (
    MappingProxyType(
        {
            "approach_engage": frozenset(
                {"approach", "connect", "seek_contact", "maintain_contact"}
            ),
            "protection_regulation": frozenset(
                {
                    "set_boundary",
                    "seek_safety",
                    "retreat",
                    "withdraw_contact",
                    "freeze",
                    "conserve",
                    "maintain_boundary",
                }
            ),
            "confrontation": frozenset(
                {"attack", "compete", "remove_obstacle"}
            ),
            "execution_expression": frozenset(
                {"perform", "improvise", "coordinate", "maintain_execution"}
            ),
        }
    )
)

ACTION_PARENT_FALLBACKS_V3: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {"protection_regulation": frozenset({"protect"})}
)

# This is documentation as immutable data, not a runtime adapter.  Empty tuples
# are intentional: legacy ``unknown`` becomes no action hypothesis, while bare
# ``withdraw`` cannot be resolved without visible context.  Legacy ``maintain``
# is likewise ambiguous among contact, boundary, and execution maintenance.
LEGACY_ACTION_RESOLUTION_V3: Final[Mapping[str, tuple[str, ...]]] = (
    MappingProxyType(
        {
            "approach": ("approach_engage/approach",),
            "attack": ("confrontation/attack",),
            "compete": ("confrontation/compete",),
            "connect": ("approach_engage/connect",),
            "conserve": ("protection_regulation/conserve",),
            "freeze": ("protection_regulation/freeze",),
            "improvise": ("execution_expression/improvise",),
            "maintain": (
                "approach_engage/maintain_contact",
                "protection_regulation/maintain_boundary",
                "execution_expression/maintain_execution",
            ),
            "perform": ("execution_expression/perform",),
            "protect": ("protection_regulation/<family_fallback:protect>",),
            "retreat": ("protection_regulation/retreat",),
            "seek_attachment": ("approach_engage/seek_contact",),
            "seek_safety": ("protection_regulation/seek_safety",),
            "set_boundary": ("protection_regulation/set_boundary",),
            "unknown": (),
            "withdraw": (),
            "withdraw_contact": ("protection_regulation/withdraw_contact",),
        }
    )
)

# Bare legacy ``withdraw`` remains unresolved at the communication boundary.
# Evaluator gold may explicitly select one of these two context-dependent
# resolutions without turning either into an automatic legacy rewrite.
LEGACY_AMBIGUOUS_ACTION_GOLD_RESOLUTIONS_V3: Final[
    Mapping[str, tuple[str, ...]]
] = MappingProxyType(
    {
        "withdraw": (
            "protection_regulation/retreat",
            "protection_regulation/withdraw_contact",
        )
    }
)

ACTION_UNKNOWN_REASON_SL_V3: Final = (
    "Racio iz navedenih vidnih opazk ni izpeljal akcijske hipoteze."
)
ActionUnknownReasonSlV3 = Literal[
    "Racio iz navedenih vidnih opazk ni izpeljal akcijske hipoteze."
]
MotiveUnknownReasonSlV3 = Literal[
    "Racio iz navedenih vidnih opazk ni izpeljal motivne hipoteze."
]
OPTION_UNKNOWN_REASON_SL_V3: Final = (
    "Racio iz navedenih vidnih opazk ni izpeljal dovolj podprte izbire možnosti."
)
OptionUnknownReasonSlV3 = Literal[
    "Racio iz navedenih vidnih opazk ni izpeljal dovolj podprte izbire možnosti."
]


def action_subtype_belongs_to_family_v3(family: str, subtype: str) -> bool:
    """Return whether an exact v3 action subtype belongs to one family."""

    return subtype in ACTION_SUBTYPES_BY_FAMILY_V3.get(family, frozenset())


def action_fallback_belongs_to_family_v3(family: str, fallback: str) -> bool:
    """Return whether one generic family fallback is registered for a family."""

    return fallback in ACTION_PARENT_FALLBACKS_V3.get(family, frozenset())


class ActionHypothesisV3(FrozenModel):
    """One cited action hypothesis; support mode remains a Racio-owned claim."""

    family: ActionFamilyV3
    subtype: ActionSubtypeV3 | None
    family_fallback: ActionFamilyFallbackV3 | None = None
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01
    support_mode: ActionSupportModeV3

    @property
    def key(self) -> tuple[str, str]:
        identity = (
            self.subtype
            if self.subtype is not None
            else f"<family_fallback:{self.family_fallback}>"
        )
        return (self.family, identity)

    @model_validator(mode="after")
    def validate_action_hypothesis(self) -> Self:
        exact = self.subtype is not None
        fallback = self.family_fallback is not None
        if exact == fallback:
            raise ValueError(
                "An action hypothesis requires exactly one subtype or family fallback"
            )
        if exact and not action_subtype_belongs_to_family_v3(
            self.family, self.subtype or ""
        ):
            raise ValueError("Action subtype does not belong to its declared family")
        if fallback and not action_fallback_belongs_to_family_v3(
            self.family, self.family_fallback or ""
        ):
            raise ValueError("Action fallback does not belong to its declared family")
        if not self.cited_observation_ids:
            raise ValueError("An action hypothesis requires visible citations")
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Action citations must be sorted and unique")
        if self.confidence == 0.0:
            raise ValueError("A claimed action hypothesis requires positive confidence")
        return self


class MotiveHypothesisV3(FrozenModel):
    """One cited motive hypothesis, independent of every action hypothesis."""

    family: MotiveFamily
    subtype: MotiveSubtypeV3
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01
    support_mode: MotiveSupportModeV3

    @property
    def key(self) -> tuple[str, str]:
        return (self.family, self.subtype)

    @model_validator(mode="after")
    def validate_motive_hypothesis(self) -> Self:
        if not motive_subtype_belongs_to_family(self.family, self.subtype):
            raise ValueError("Motive subtype does not belong to its declared family")
        if not self.cited_observation_ids:
            raise ValueError("A motive hypothesis requires visible citations")
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Motive citations must be sorted and unique")
        if self.confidence == 0.0:
            raise ValueError("A claimed motive hypothesis requires positive confidence")
        return self


class OptionInferenceV3(FrozenModel):
    """One option claim with evidence scoped only to that claim."""

    option_id: NonEmptyId
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01

    @model_validator(mode="after")
    def validate_option_inference(self) -> Self:
        if not self.cited_observation_ids:
            raise ValueError("An option inference requires visible citations")
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Option citations must be sorted and unique")
        if self.confidence == 0.0:
            raise ValueError("A selected option requires positive confidence")
        return self


class ActionHypothesisDraftV3(FrozenModel):
    """Model-facing action claim before deterministic canonical ordering."""

    family: ActionFamilyV3
    subtype: ActionSubtypeV3 | None
    family_fallback: ActionFamilyFallbackV3 | None = None
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01
    support_mode: ActionSupportModeV3

    @model_validator(mode="after")
    def validate_action_draft(self) -> Self:
        exact = self.subtype is not None
        fallback = self.family_fallback is not None
        if exact == fallback:
            raise ValueError(
                "An action draft requires exactly one subtype or family fallback"
            )
        if exact and not action_subtype_belongs_to_family_v3(
            self.family, self.subtype or ""
        ):
            raise ValueError("Action draft subtype does not belong to its family")
        if fallback and not action_fallback_belongs_to_family_v3(
            self.family, self.family_fallback or ""
        ):
            raise ValueError("Action draft fallback does not belong to its family")
        if not self.cited_observation_ids:
            raise ValueError("An action draft requires claim-local citations")
        if self.confidence == 0.0:
            raise ValueError("A claimed action draft requires positive confidence")
        return self


class OptionInferenceDraftV3(FrozenModel):
    """Model-facing option claim with evidence local to this claim."""

    option_id: NonEmptyId
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01

    @model_validator(mode="after")
    def validate_option_draft(self) -> Self:
        if not self.cited_observation_ids:
            raise ValueError("An option draft requires claim-local citations")
        if self.confidence == 0.0:
            raise ValueError("A selected option draft requires positive confidence")
        return self


class MotiveHypothesisDraftV3(FrozenModel):
    """Model-facing motive claim before deterministic canonical ordering."""

    family: MotiveFamily
    subtype: MotiveSubtypeV3
    cited_observation_ids: tuple[NonEmptyId, ...]
    confidence: Score01
    support_mode: MotiveSupportModeV3

    @model_validator(mode="after")
    def validate_motive_draft(self) -> Self:
        if not motive_subtype_belongs_to_family(self.family, self.subtype):
            raise ValueError("Motive draft subtype does not belong to its family")
        if not self.cited_observation_ids:
            raise ValueError("A motive draft requires claim-local citations")
        if self.confidence == 0.0:
            raise ValueError("A claimed motive draft requires positive confidence")
        return self


class RacioEpistemicDraftV3(FrozenModel):
    """Minimal semantic output exposed to a model-facing V3 provider."""

    source_mind: Literal["E", "I"]
    action_hypotheses: tuple[ActionHypothesisDraftV3, ...]
    option_inference: OptionInferenceDraftV3 | None
    motive_hypotheses: tuple[MotiveHypothesisDraftV3, ...]
    racio_reported_uncertainty: RacioReportedUncertainty

    @model_validator(mode="after")
    def validate_draft_bounds(self) -> Self:
        if len(self.action_hypotheses) > 2:
            raise ValueError("At most two action drafts are permitted")
        if len(self.motive_hypotheses) > 3:
            raise ValueError("At most three motive drafts are permitted")
        return self


_DIRECT_RESERVED_MARKERS_V3: Final[Mapping[str, str]] = MappingProxyType(
    {
        **{
            family: f"action_family:{family}"
            for family in ACTION_SUBTYPES_BY_FAMILY_V3
        },
        **{
            subtype: f"action:{subtype}"
            for subtypes in ACTION_SUBTYPES_BY_FAMILY_V3.values()
            for subtype in subtypes
        },
        **{
            fallback: f"family_fallback:{fallback}"
            for fallbacks in ACTION_PARENT_FALLBACKS_V3.values()
            for fallback in fallbacks
        },
        **{
            family: f"motive_family:{family}"
            for family in MOTIVE_SUBTYPES_BY_FAMILY
        },
        **{
            subtype: f"motive:{family}/{subtype}"
            for family, subtypes in MOTIVE_SUBTYPES_BY_FAMILY.items()
            for subtype in subtypes
        },
        "direct_manifestation": "action_support:direct_manifestation",
        "functional_inference": "action_support:functional_inference",
        "speculative": "support:speculative",
        "directly_supported": "motive_support:directly_supported",
        "contextually_supported": "motive_support:contextually_supported",
        "evaluator": "evaluator:evaluator",
        "evaluator_gold": "evaluator:gold",
        "gold": "evaluator:gold",
        "ground_truth": "evaluator:gold",
        "expected_action": "evaluator:expected_action",
        "expected_motive": "evaluator:expected_motive",
        "expected_option": "evaluator:expected_option",
        "native_truth": "evaluator:native_truth",
        "profile_id": "evaluator:profile_id",
        "canary": "evaluator:canary",
        "confidence": "support:confidence",
        "supported": "support:supported",
        "unsupported": "support:unsupported",
    }
)

# Aliases map ordinary Slovene and English surface forms onto the same reserved
# marker.  They are deliberately conservative.  Deeper semantic equivalence,
# role, strength, polarity, and modality remain explicit human attestations.
_RESERVED_MARKER_ALIASES_V3: Final[Mapping[str, tuple[str, ...]]] = (
    MappingProxyType(
        {
            "action:approach": ("približati se", "pristop", "approach"),
            "action:connect": ("vzpostaviti stik", "establish contact", "connect"),
            "action:seek_contact": ("poiskati stik", "seek contact", "seek closeness"),
            "action:maintain_contact": ("ohraniti stik", "maintain contact"),
            "action:set_boundary": ("postaviti mejo", "set boundary"),
            "action:seek_safety": ("poiskati varnost", "seek safety", "safer direction"),
            "action:retreat": (
                "umik",
                "umika",
                "prostorski umik",
                "umik v prostoru",
                "retreat",
            ),
            "action:withdraw_contact": ("prekiniti stik", "end contact", "withdraw contact"),
            "action:freeze": ("zamrzniti", "freeze"),
            "action:conserve": ("varčevati", "conserve"),
            "action:maintain_boundary": ("ohraniti mejo", "maintain boundary"),
            "action:attack": ("napasti", "attack", "enter confrontation"),
            "action:compete": ("tekmovati", "compete", "outperform"),
            "action:remove_obstacle": ("odstraniti oviro", "remove obstacle"),
            "action:perform": ("izvesti", "perform", "execute"),
            "action:improvise": ("improvizirati", "improvise"),
            "action:coordinate": ("uskladiti", "coordinate"),
            "action:maintain_execution": ("ohraniti izvedbo", "maintain execution"),
            "family_fallback:protect": ("zaščititi", "protect"),
            "action_family:approach_engage": (
                "pristop in vključevanje",
                "approach engage",
            ),
            "action_family:protection_regulation": (
                "zaščitna regulacija",
                "protection regulation",
            ),
            "action_family:confrontation": ("soočenje", "confrontation"),
            "action_family:execution_expression": (
                "izvedba in izražanje",
                "execution expression",
            ),
            "motive_family:scene": ("prizor", "prizora", "scene"),
            "motive_family:motor_social": (
                "motorično socialno",
                "motorično-socialno",
                "motor social",
            ),
            "motive_family:protection": (
                "zaščita",
                "zaščitna",
                "protection",
            ),
            "motive:scene/broken_scene": (
                "porušen prizor",
                "pokvarjen prizor",
                "broken scene",
            ),
            "motive:scene/desired_scene_absent": (
                "želeni prizor manjka",
                "odsoten želeni prizor",
                "desired scene absent",
            ),
            "motive:scene/desired_scene_mismatch": (
                "neskladje želenega prizora",
                "želeni prizor se ne ujema",
                "desired scene mismatch",
            ),
            "motive:scene/recurrent_broken_scene": (
                "ponavljajoč se porušen prizor",
                "ponavljajoč se pokvarjen prizor",
                "recurrent broken scene",
            ),
            "motive:scene/scene_realization": (
                "uresničitev prizora",
                "scene realization",
            ),
            "motive:scene/scene_repair": (
                "popravilo prizora",
                "scene repair",
            ),
            "motive:motor_social/attention_or_status": (
                "pozornost ali status",
                "attention or status",
            ),
            "motive:motor_social/competition": (
                "tekmovalnost",
                "competition",
            ),
            "motive:motor_social/connection": (
                "povezanost",
                "connection",
            ),
            "motive:motor_social/motor_execution": (
                "motorična izvedba",
                "motor execution",
            ),
            "motive:protection/attachment_alarm": (
                "alarm navezanosti",
                "navezanostni alarm",
                "attachment alarm",
            ),
            "motive:protection/boundary_alarm": (
                "alarm meje",
                "mejni alarm",
                "boundary alarm",
            ),
            "motive:protection/escape_alarm": (
                "pobeg",
                "alarm pobega",
                "escape",
                "escape alarm",
            ),
            "motive:protection/general_body_alarm": (
                "splošni telesni alarm",
                "general body alarm",
            ),
            "motive:protection/resource_alarm": (
                "alarm virov",
                "resource alarm",
            ),
            "motive:protection/trust_alarm": (
                "alarm zaupanja",
                "trust alarm",
            ),
            "action_support:direct_manifestation": (
                "neposredna manifestacija",
                "direct manifestation",
            ),
            "action_support:functional_inference": (
                "funkcionalno sklepanje",
                "functional inference",
            ),
            "support:speculative": (
                "spekulativno",
                "speculative",
            ),
            "motive_support:directly_supported": (
                "neposredno podprto",
                "directly supported",
            ),
            "motive_support:contextually_supported": (
                "kontekstualno podprto",
                "contextually supported",
            ),
            "causal:claim": (
                "ker",
                "zato",
                "zaradi",
                "vzrok",
                "razlog",
                "because",
                "therefore",
                "due to",
                "cause",
                "reason",
            ),
            "evaluator:gold": ("zlati odgovor", "gold answer", "ground truth"),
            "evaluator:expected": ("pričakovani odgovor", "expected answer"),
            "evaluator:evaluator": ("ocenjevalec", "evaluator"),
            "support:confidence": ("stopnja zaupanja", "confidence"),
            "support:supported": ("podprto", "supported"),
            "support:unsupported": ("nepodprto", "unsupported"),
        }
    )
)


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_bilingual_audit_text_v3(text: str) -> str:
    """Return deterministic NFKC/casefold text and reject control characters."""

    if any(unicodedata.category(character).startswith("C") for character in text):
        raise ValueError("Audited bilingual text cannot contain control characters")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split())


def _contains_phrase(text: str, phrase: str) -> bool:
    return (
        re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, flags=re.UNICODE)
        is not None
    )


def reserved_bilingual_markers_v3(text: str) -> tuple[str, ...]:
    """Detect reserved taxonomy, support, evaluator, and causal markers."""

    normalized = normalize_bilingual_audit_text_v3(text)
    markers: set[str] = set()
    for identifier, marker in _DIRECT_RESERVED_MARKERS_V3.items():
        normalized_identifier = identifier.replace("_", " ")
        if _contains_phrase(normalized, identifier) or _contains_phrase(
            normalized, normalized_identifier
        ):
            markers.add(marker)
    for marker, aliases in _RESERVED_MARKER_ALIASES_V3.items():
        if any(_contains_phrase(normalized, alias) for alias in aliases):
            markers.add(marker)
    return tuple(sorted(markers))


class BilingualGlossAuditV3(FrozenArtifactModel):
    """Human attestation bound to exact bilingual text and detected markers."""

    schema_version: Literal["rei-racio-bilingual-gloss-audit-v3"] = (
        "rei-racio-bilingual-gloss-audit-v3"
    )
    audit_id: NonEmptyId
    reviewer_id: NonEmptyId
    canonical_sl_sha256: HashDigest
    operational_en_sha256: HashDigest
    canonical_sl_normalized_sha256: HashDigest
    operational_en_normalized_sha256: HashDigest
    canonical_sl_reserved_markers: tuple[NonEmptyId, ...]
    operational_en_reserved_markers: tuple[NonEmptyId, ...]
    canonical_sl_signature: tuple[NonEmptyId, ...]
    operational_en_signature: tuple[NonEmptyId, ...]
    approved: Literal[True]
    signatures_equivalent: Literal[True]
    reserved_collisions_aligned: Literal[True]
    no_added_action_claims: Literal[True]
    no_added_motive_claims: Literal[True]
    no_added_causal_claims: Literal[True]
    role_aligned: Literal[True]
    strength_aligned: Literal[True]
    polarity_aligned: Literal[True]
    modality_aligned: Literal[True]
    audit_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        reviewer_id: NonEmptyId,
        canonical_sl: NonEmptyText,
        operational_en: NonEmptyText,
        canonical_sl_signature: tuple[NonEmptyId, ...],
        operational_en_signature: tuple[NonEmptyId, ...],
        approved: Literal[True],
        signatures_equivalent: Literal[True],
        reserved_collisions_aligned: Literal[True],
        no_added_action_claims: Literal[True],
        no_added_motive_claims: Literal[True],
        no_added_causal_claims: Literal[True],
        role_aligned: Literal[True],
        strength_aligned: Literal[True],
        polarity_aligned: Literal[True],
        modality_aligned: Literal[True],
    ) -> "BilingualGlossAuditV3":
        canonical_normalized = normalize_bilingual_audit_text_v3(canonical_sl)
        operational_normalized = normalize_bilingual_audit_text_v3(operational_en)
        base = {
            "schema_version": "rei-racio-bilingual-gloss-audit-v3",
            "reviewer_id": reviewer_id,
            "canonical_sl_sha256": _text_sha256(canonical_sl),
            "operational_en_sha256": _text_sha256(operational_en),
            "canonical_sl_normalized_sha256": _text_sha256(canonical_normalized),
            "operational_en_normalized_sha256": _text_sha256(
                operational_normalized
            ),
            "canonical_sl_reserved_markers": reserved_bilingual_markers_v3(
                canonical_sl
            ),
            "operational_en_reserved_markers": reserved_bilingual_markers_v3(
                operational_en
            ),
            "canonical_sl_signature": tuple(canonical_sl_signature),
            "operational_en_signature": tuple(operational_en_signature),
            "approved": approved,
            "signatures_equivalent": signatures_equivalent,
            "reserved_collisions_aligned": reserved_collisions_aligned,
            "no_added_action_claims": no_added_action_claims,
            "no_added_motive_claims": no_added_motive_claims,
            "no_added_causal_claims": no_added_causal_claims,
            "role_aligned": role_aligned,
            "strength_aligned": strength_aligned,
            "polarity_aligned": polarity_aligned,
            "modality_aligned": modality_aligned,
        }
        audit_id = content_id("racio_bilingual_gloss_audit_v3", base)
        payload = {"audit_id": audit_id, **base}
        return cls(**payload, audit_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_audit(self) -> Self:
        canonical_fields = (
            "canonical_sl_reserved_markers",
            "operational_en_reserved_markers",
            "canonical_sl_signature",
            "operational_en_signature",
        )
        for field_name in canonical_fields:
            values = getattr(self, field_name)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"Bilingual audit {field_name} must be canonical")
        if not self.canonical_sl_signature:
            raise ValueError("Bilingual audit requires a nonempty semantic signature")
        if self.canonical_sl_signature != self.operational_en_signature:
            raise ValueError("Bilingual semantic signatures must be equivalent")
        if self.canonical_sl_reserved_markers != self.operational_en_reserved_markers:
            raise ValueError("Bilingual reserved markers are not aligned")
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"audit_id", "audit_hash"}
        )
        if self.audit_id != content_id("racio_bilingual_gloss_audit_v3", id_payload):
            raise ValueError("Bilingual audit ID differs from its attestation")
        hash_payload = {"audit_id": self.audit_id, **id_payload}
        if self.audit_hash != sha256_hex(hash_payload):
            raise ValueError("Bilingual audit hash differs from its attestation")
        return self

    def validate_against(
        self,
        *,
        canonical_sl: str,
        operational_en: str,
    ) -> "BilingualGlossAuditV3":
        canonical_normalized = normalize_bilingual_audit_text_v3(canonical_sl)
        operational_normalized = normalize_bilingual_audit_text_v3(operational_en)
        expected = {
            "canonical_sl_sha256": _text_sha256(canonical_sl),
            "operational_en_sha256": _text_sha256(operational_en),
            "canonical_sl_normalized_sha256": _text_sha256(canonical_normalized),
            "operational_en_normalized_sha256": _text_sha256(
                operational_normalized
            ),
            "canonical_sl_reserved_markers": reserved_bilingual_markers_v3(
                canonical_sl
            ),
            "operational_en_reserved_markers": reserved_bilingual_markers_v3(
                operational_en
            ),
        }
        for field_name, expected_value in expected.items():
            if getattr(self, field_name) != expected_value:
                raise ValueError("Bilingual audit does not bind the supplied text")
        return self


class AuditedBilingualTextV3(FrozenModel):
    """Canonical Slovene text with at most one hash-bound operational gloss."""

    canonical_sl: NonEmptyText
    operational_en: NonEmptyText | None = None
    gloss_audit: BilingualGlossAuditV3 | None = None

    @model_validator(mode="after")
    def validate_audited_text(self) -> Self:
        normalize_bilingual_audit_text_v3(self.canonical_sl)
        if self.operational_en is None:
            if self.gloss_audit is not None:
                raise ValueError("A missing operational gloss cannot carry an audit")
            return self
        normalize_bilingual_audit_text_v3(self.operational_en)
        if self.gloss_audit is None:
            raise ValueError("An operational gloss requires a human audit")
        self.gloss_audit.validate_against(
            canonical_sl=self.canonical_sl,
            operational_en=self.operational_en,
        )
        return self


class BilingualObservationV3(FrozenModel):
    """One citeable observation plus non-provider-facing atomicity attestation."""

    observation_id: NonEmptyId
    atomic_evidence_unit_id: AtomicEvidenceUnitIdV3
    perceptual_unit_count: Literal[1] = 1
    signal_alias: OpaqueSignalAliasV3
    perception_status: Literal["clear", "degraded"]
    text: AuditedBilingualTextV3 | None
    provenance: Literal["manifested", "renderer_added_ungrounded"]

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.perception_status == "degraded":
            if self.text is not None:
                raise ValueError("A degraded observation cannot expose exact text")
        elif self.text is None:
            raise ValueError("A clear observation requires audited visible text")
        return self


class BilingualOptionV3(FrozenModel):
    """One public option alias with the same audited bilingual text boundary."""

    option_id: NonEmptyId
    text: AuditedBilingualTextV3


class BilingualUncertaintyV3(FrozenModel):
    """Packet uncertainty rendered through the audited bilingual text boundary."""

    text: AuditedBilingualTextV3


def _present_audited_text_v3(
    value: AuditedBilingualTextV3,
    mode: PresentationModeV3,
) -> dict[str, str]:
    if mode == "canonical_sl_only":
        return {"canonical_sl": value.canonical_sl}
    if value.operational_en is None:
        raise ValueError("English presentation requires an audited operational gloss")
    if mode == "operational_en_only":
        return {"operational_en": value.operational_en}
    return {
        "canonical_sl": value.canonical_sl,
        "operational_en": value.operational_en,
    }


class RacioEpistemicPacketV3(FrozenArtifactModel):
    """Sanitized v3 packet; bilingual text never creates a second evidence ID."""

    schema_version: Literal["rei-racio-epistemic-packet-v3"] = (
        "rei-racio-epistemic-packet-v3"
    )
    packet_id: NonEmptyId
    source_mind: Literal["E", "I"]
    presentation_mode: PresentationModeV3
    visible_observations: tuple[BilingualObservationV3, ...] = ()
    omitted_observation_ids: tuple[NonEmptyId, ...] = ()
    degraded_observation_ids: tuple[NonEmptyId, ...] = ()
    public_option_scope: tuple[BilingualOptionV3, ...] = ()
    channel_quality: Score01
    uncertainty: BilingualUncertaintyV3
    packet_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        source_mind: Literal["E", "I"],
        presentation_mode: PresentationModeV3,
        visible_observations: tuple[BilingualObservationV3, ...],
        omitted_observation_ids: tuple[NonEmptyId, ...],
        public_option_scope: tuple[BilingualOptionV3, ...],
        channel_quality: Score01,
        uncertainty: BilingualUncertaintyV3,
    ) -> "RacioEpistemicPacketV3":
        observations = tuple(
            sorted(visible_observations, key=lambda item: item.observation_id)
        )
        omitted = tuple(sorted(set(omitted_observation_ids)))
        options = tuple(sorted(public_option_scope, key=lambda item: item.option_id))
        degraded = tuple(
            item.observation_id
            for item in observations
            if item.perception_status == "degraded"
        )
        base = {
            "schema_version": "rei-racio-epistemic-packet-v3",
            "source_mind": source_mind,
            "presentation_mode": presentation_mode,
            "visible_observations": observations,
            "omitted_observation_ids": omitted,
            "degraded_observation_ids": degraded,
            "public_option_scope": options,
            "channel_quality": channel_quality,
            "uncertainty": uncertainty,
        }
        packet_id = content_id("racio_epistemic_packet_v3", base)
        payload = {"packet_id": packet_id, **base}
        return cls(**payload, packet_hash=sha256_hex(payload))

    @property
    def visible_observation_ids(self) -> tuple[str, ...]:
        return tuple(item.observation_id for item in self.visible_observations)

    @property
    def public_option_ids(self) -> tuple[str, ...]:
        return tuple(item.option_id for item in self.public_option_scope)

    @model_validator(mode="after")
    def validate_packet(self) -> Self:
        visible_ids = self.visible_observation_ids
        if visible_ids != tuple(sorted(set(visible_ids))):
            raise ValueError("Visible observation aliases must be sorted and unique")
        signal_aliases = tuple(item.signal_alias for item in self.visible_observations)
        if len(signal_aliases) != len(set(signal_aliases)):
            raise ValueError("Opaque signal aliases must be unique")
        atomic_unit_ids = tuple(
            item.atomic_evidence_unit_id for item in self.visible_observations
        )
        if len(atomic_unit_ids) != len(set(atomic_unit_ids)):
            raise ValueError(
                "One atomic evidence unit cannot be duplicated across observations"
            )
        if self.omitted_observation_ids != tuple(
            sorted(set(self.omitted_observation_ids))
        ):
            raise ValueError("Omitted observation aliases must be sorted and unique")
        if set(visible_ids).intersection(self.omitted_observation_ids):
            raise ValueError("Visible and omitted observation aliases must be disjoint")
        expected_degraded = tuple(
            item.observation_id
            for item in self.visible_observations
            if item.perception_status == "degraded"
        )
        if self.degraded_observation_ids != expected_degraded:
            raise ValueError("Degraded aliases must exactly match visible observations")
        option_ids = self.public_option_ids
        if option_ids != tuple(sorted(set(option_ids))):
            raise ValueError("Public option aliases must be sorted and unique")
        if self.presentation_mode != "canonical_sl_only":
            presented_texts = [
                item.text
                for item in self.visible_observations
                if item.text is not None
            ]
            presented_texts.extend(item.text for item in self.public_option_scope)
            presented_texts.append(self.uncertainty.text)
            if any(item.operational_en is None for item in presented_texts):
                raise ValueError(
                    "English presentation requires audited glosses for every text"
                )
        id_payload = self.model_dump(
            mode="python", round_trip=True, exclude={"packet_id", "packet_hash"}
        )
        if self.packet_id != content_id("racio_epistemic_packet_v3", id_payload):
            raise ValueError("Epistemic v3 packet ID differs from sanitized content")
        if self.packet_hash != self.content_hash(exclude_fields=frozenset({"packet_hash"})):
            raise ValueError("Epistemic v3 packet hash differs from sanitized content")
        return self

    def provider_payload(self) -> dict[str, object]:
        """Return one citeable row per observation, without audit/atomic metadata."""

        observations: list[dict[str, object]] = []
        for item in self.visible_observations:
            observations.append(
                {
                    "observation_id": item.observation_id,
                    "signal_alias": item.signal_alias,
                    "perception_status": item.perception_status,
                    "text": (
                        None
                        if item.text is None
                        else _present_audited_text_v3(
                            item.text, self.presentation_mode
                        )
                    ),
                    "provenance": item.provenance,
                }
            )
        return {
            "schema_version": self.schema_version,
            "source_mind": self.source_mind,
            "presentation_mode": self.presentation_mode,
            "visible_observations": observations,
            "omitted_observation_ids": list(self.omitted_observation_ids),
            "degraded_observation_ids": list(self.degraded_observation_ids),
            "public_option_scope": [
                {
                    "option_id": item.option_id,
                    "text": _present_audited_text_v3(
                        item.text, self.presentation_mode
                    ),
                }
                for item in self.public_option_scope
            ],
            "channel_quality": self.channel_quality,
            "uncertainty": _present_audited_text_v3(
                self.uncertainty.text, self.presentation_mode
            ),
        }

    def provider_payload_bytes(self) -> bytes:
        return canonical_json_bytes(self.provider_payload())


class RacioEpistemicInterpretationV3(FrozenModel):
    """V3 interpretation with independent action, option, and motive claims."""

    source_mind: Literal["E", "I"]
    cited_observation_ids: tuple[NonEmptyId, ...]
    action_hypotheses: tuple[ActionHypothesisV3, ...]
    action_unknown_reason: ActionUnknownReasonSlV3 | None
    option_inference: OptionInferenceV3 | None
    option_unknown_reason: OptionUnknownReasonSlV3 | None
    motive_hypotheses: tuple[MotiveHypothesisV3, ...]
    motive_unknown_reason: MotiveUnknownReasonSlV3 | None
    racio_reported_uncertainty: RacioReportedUncertainty

    @model_validator(mode="after")
    def validate_canonical_output(self) -> Self:
        if self.cited_observation_ids != tuple(
            sorted(set(self.cited_observation_ids))
        ):
            raise ValueError("Global observation citations must be sorted and unique")
        if len(self.action_hypotheses) > 2:
            raise ValueError("At most two action hypotheses are permitted")
        if len(self.motive_hypotheses) > 3:
            raise ValueError("At most three motive hypotheses are permitted")
        action_keys = tuple(item.key for item in self.action_hypotheses)
        motive_keys = tuple(item.key for item in self.motive_hypotheses)
        if len(set(action_keys)) != len(action_keys):
            raise ValueError("Action family/subtype combinations must be unique")
        if len(set(motive_keys)) != len(motive_keys):
            raise ValueError("Motive family/subtype combinations must be unique")
        expected_actions = tuple(
            sorted(
                self.action_hypotheses,
                key=lambda item: (-item.confidence, *item.key),
            )
        )
        expected_motives = tuple(
            sorted(
                self.motive_hypotheses,
                key=lambda item: (-item.confidence, *item.key),
            )
        )
        if self.action_hypotheses != expected_actions:
            raise ValueError("Action hypotheses must use canonical confidence order")
        if self.motive_hypotheses != expected_motives:
            raise ValueError("Motive hypotheses must use canonical confidence order")
        global_citations = set(self.cited_observation_ids)
        scoped_claims = (
            *self.action_hypotheses,
            *((self.option_inference,) if self.option_inference is not None else ()),
            *self.motive_hypotheses,
        )
        if any(
            not set(item.cited_observation_ids).issubset(global_citations)
            for item in scoped_claims
        ):
            raise ValueError("Claim-specific citations must be included globally")
        if self.action_hypotheses:
            if self.action_unknown_reason is not None:
                raise ValueError("Populated actions cannot claim action unknown")
        elif self.action_unknown_reason != ACTION_UNKNOWN_REASON_SL_V3:
            raise ValueError("Empty actions require the exact bounded unknown reason")
        if self.motive_hypotheses:
            if self.motive_unknown_reason is not None:
                raise ValueError("Populated motives cannot claim motive unknown")
        elif self.motive_unknown_reason != MOTIVE_UNKNOWN_REASON_SL:
            raise ValueError("Empty motives require the exact bounded unknown reason")
        if self.option_inference is None:
            if self.option_unknown_reason != OPTION_UNKNOWN_REASON_SL_V3:
                raise ValueError(
                    "Option abstention requires the exact bounded unknown reason"
                )
        elif self.option_unknown_reason is not None:
            raise ValueError("A selected option cannot also claim option unknown")
        return self

    def validate_against(
        self,
        packet: RacioEpistemicPacketV3,
    ) -> "RacioEpistemicInterpretationV3":
        if self.source_mind != packet.source_mind:
            raise ValueError("Epistemic v3 output source mind differs from its packet")
        visible_ids = set(packet.visible_observation_ids)
        if not set(self.cited_observation_ids).issubset(visible_ids):
            raise ValueError("Epistemic v3 output cites outside packet scope")
        if packet.visible_observations and not self.cited_observation_ids:
            raise ValueError("An epistemic v3 interpretation requires citations")
        if not packet.visible_observations:
            if self.cited_observation_ids:
                raise ValueError("An empty packet cannot have citations")
            if (
                self.action_hypotheses
                or self.option_inference is not None
                or self.motive_hypotheses
            ):
                raise ValueError("An empty packet requires full epistemic abstention")
        if (
            self.option_inference is not None
            and self.option_inference.option_id not in set(packet.public_option_ids)
        ):
            raise ValueError("Epistemic v3 output selects outside public options")
        scoped_claims = (
            *self.action_hypotheses,
            *((self.option_inference,) if self.option_inference is not None else ()),
            *self.motive_hypotheses,
        )
        for claim in scoped_claims:
            if not set(claim.cited_observation_ids).issubset(visible_ids):
                raise ValueError("A v3 claim cites outside packet scope")
        return self


def canonicalize_racio_epistemic_draft_v3(
    packet: RacioEpistemicPacketV3,
    draft: RacioEpistemicDraftV3,
) -> RacioEpistemicInterpretationV3:
    """Canonicalize syntax and scope without changing a model's semantics.

    The canonicalizer only normalizes citation and hypothesis ordering, derives
    the global citation union, and supplies the frozen bounded unknown strings
    for claims the draft explicitly leaves empty.  Invalid semantic identities
    or packet-local references fail closed through the V3 model validators.
    """

    if draft.source_mind != packet.source_mind:
        raise ValueError("Draft source mind differs from its packet")

    visible_ids = set(packet.visible_observation_ids)
    public_option_ids = set(packet.public_option_ids)

    def canonical_citations(values: tuple[str, ...]) -> tuple[str, ...]:
        citations = tuple(sorted(set(values)))
        if not set(citations).issubset(visible_ids):
            raise ValueError("Draft claim cites outside visible packet scope")
        return citations

    actions = tuple(
        sorted(
            (
                ActionHypothesisV3(
                    family=item.family,
                    subtype=item.subtype,
                    family_fallback=item.family_fallback,
                    cited_observation_ids=canonical_citations(
                        item.cited_observation_ids
                    ),
                    confidence=item.confidence,
                    support_mode=item.support_mode,
                )
                for item in draft.action_hypotheses
            ),
            key=lambda item: (-item.confidence, *item.key),
        )
    )
    motives = tuple(
        sorted(
            (
                MotiveHypothesisV3(
                    family=item.family,
                    subtype=item.subtype,
                    cited_observation_ids=canonical_citations(
                        item.cited_observation_ids
                    ),
                    confidence=item.confidence,
                    support_mode=item.support_mode,
                )
                for item in draft.motive_hypotheses
            ),
            key=lambda item: (-item.confidence, *item.key),
        )
    )
    option: OptionInferenceV3 | None = None
    if draft.option_inference is not None:
        if draft.option_inference.option_id not in public_option_ids:
            raise ValueError("Draft selects outside public option scope")
        option = OptionInferenceV3(
            option_id=draft.option_inference.option_id,
            cited_observation_ids=canonical_citations(
                draft.option_inference.cited_observation_ids
            ),
            confidence=draft.option_inference.confidence,
        )

    claim_citations = {
        citation
        for claim in (
            *actions,
            *((option,) if option is not None else ()),
            *motives,
        )
        for citation in claim.cited_observation_ids
    }
    output = RacioEpistemicInterpretationV3(
        source_mind=draft.source_mind,
        cited_observation_ids=tuple(sorted(claim_citations)),
        action_hypotheses=actions,
        action_unknown_reason=(None if actions else ACTION_UNKNOWN_REASON_SL_V3),
        option_inference=option,
        option_unknown_reason=(
            None if option is not None else OPTION_UNKNOWN_REASON_SL_V3
        ),
        motive_hypotheses=motives,
        motive_unknown_reason=(None if motives else MOTIVE_UNKNOWN_REASON_SL),
        racio_reported_uncertainty=draft.racio_reported_uncertainty,
    )
    return output.validate_against(packet)


class RacioEpistemicStructuralSidecarV3(FrozenModel):
    """Provider-derived structure only; never semantic evidence or authority."""

    option_id_present: bool
    motive_hypothesis_count: int = Field(ge=0, le=3)

    @classmethod
    def from_output(
        cls,
        output: RacioEpistemicInterpretationV3,
    ) -> "RacioEpistemicStructuralSidecarV3":
        return cls(
            option_id_present=output.option_inference is not None,
            motive_hypothesis_count=len(output.motive_hypotheses),
        )


__all__ = [
    "ACTION_PARENT_FALLBACKS_V3",
    "ACTION_SUBTYPES_BY_FAMILY_V3",
    "ACTION_UNKNOWN_REASON_SL_V3",
    "AtomicEvidenceUnitIdV3",
    "ActionFamilyFallbackV3",
    "ActionFamilyV3",
    "ActionHypothesisDraftV3",
    "ActionHypothesisV3",
    "ActionSubtypeV3",
    "ActionSupportModeV3",
    "ActionUnknownReasonSlV3",
    "ApproachEngageActionSubtypeV3",
    "AuditedBilingualTextV3",
    "BilingualGlossAuditV3",
    "BilingualObservationV3",
    "BilingualOptionV3",
    "BilingualUncertaintyV3",
    "ConfrontationActionSubtypeV3",
    "ExecutionExpressionActionSubtypeV3",
    "LEGACY_AMBIGUOUS_ACTION_GOLD_RESOLUTIONS_V3",
    "LEGACY_ACTION_RESOLUTION_V3",
    "MotiveHypothesisV3",
    "MotiveHypothesisDraftV3",
    "MotiveSupportModeV3",
    "MotiveSubtypeV3",
    "MotiveUnknownReasonSlV3",
    "OpaqueSignalAliasV3",
    "OPTION_UNKNOWN_REASON_SL_V3",
    "OptionInferenceV3",
    "OptionInferenceDraftV3",
    "OptionUnknownReasonSlV3",
    "PresentationModeV3",
    "ProtectionRegulationActionSubtypeV3",
    "RacioEpistemicDraftV3",
    "RacioEpistemicInterpretationV3",
    "RacioEpistemicPacketV3",
    "RacioEpistemicStructuralSidecarV3",
    "action_fallback_belongs_to_family_v3",
    "action_subtype_belongs_to_family_v3",
    "canonicalize_racio_epistemic_draft_v3",
    "normalize_bilingual_audit_text_v3",
    "reserved_bilingual_markers_v3",
]
