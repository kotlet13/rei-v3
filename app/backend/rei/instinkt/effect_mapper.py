"""Profile-blind, evidence-gated C5 Instinkt body-effect inference."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models.instinkt import (
    BODY_DIMENSIONS,
    INSTINKT_CUE_LANES,
    BodyDelta,
    BodyState,
    InstinktAssociation,
    InstinktCueEvidenceBinding,
    InstinktInputPacket,
    InstinktWorld,
)
from ..models.instinkt_effects import (
    BodyEffectAssociationMatch,
    BodyEffectEvidence,
    EmbodiedCueRule,
    InstinktEffectRuleSet,
    OptionBodyEffectPrediction,
    classify_option_effect_relation,
    combine_body_effect_deltas,
)
from ..models.scene import DecisionOption, EvidenceItem, SceneEvent
from .effect_rules import load_instinkt_effect_rules


RULE_BASED_MAPPER_ID = "rei.instinkt.rule_based_embodied_cue_interpreter"
RULE_BASED_MAPPER_REVISION = "c5-v2"
MODEL_BACKED_MAPPER_ID = "rei.instinkt.model_backed_embodied_cue_interpreter"
MODEL_BACKED_MAPPER_REVISION = "c5-stub-v1"


@runtime_checkable
class EmbodiedCueInterpreter(Protocol):
    def infer_effects(
        self,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        world: InstinktWorld,
        body: BodyState,
        option: DecisionOption,
    ) -> OptionBodyEffectPrediction:
        ...


def _trusted_copy(value):
    return type(value).model_validate(value.model_dump(mode="python", round_trip=True))


def _source_evidence(
    *,
    scene: SceneEvent,
    rule: EmbodiedCueRule,
    bindings: tuple[InstinktCueEvidenceBinding, ...],
) -> tuple[EvidenceItem, ...]:
    scene_evidence = {item.evidence_id: item for item in scene.evidence}
    selected_ids: set[str] = set()
    for binding in bindings:
        if (
            binding.cue_class != rule.cue_class
            or binding.assertion_status != "asserted_positive"
        ):
            return ()
        for citation in binding.citations:
            item = scene_evidence.get(citation.evidence_id)
            if (
                item is None
                or not item.grounded
                or item.provenance_kind != "supplied"
                or item.modality not in rule.supported_evidence_modalities
            ):
                return ()
            citation.validate_against(item)
            selected_ids.add(citation.evidence_id)
    return tuple(
        item for item in scene.evidence if item.evidence_id in selected_ids
    )


def _typed_candidates(
    *, packet: InstinktInputPacket, rule: EmbodiedCueRule
) -> tuple[InstinktCueEvidenceBinding, ...]:
    return tuple(
        binding
        for binding in packet.cue_evidence_bindings
        if binding.cue_class == rule.cue_class
        and binding.lane in rule.packet_lanes
        and binding.assertion_status == "asserted_positive"
    )


def _unbound_lane_cues(
    packet: InstinktInputPacket,
) -> tuple[tuple[str, str], ...]:
    bound = {
        (binding.lane, binding.cue)
        for binding in packet.cue_evidence_bindings
    }
    return tuple(
        (lane, cue)
        for lane in INSTINKT_CUE_LANES
        for cue in getattr(packet, lane)
        if (lane, cue) not in bound
    )


def _score_association(
    *,
    association: InstinktAssociation,
    body: BodyState,
    rule: EmbodiedCueRule,
    typed_cues: tuple[str, ...],
    predicted_deltas: tuple[BodyDelta, ...],
) -> BodyEffectAssociationMatch:
    """Score semantic context; B8 separately applies memory intensity and decay."""

    return BodyEffectAssociationMatch.create(
        association=association,
        body=body,
        rule=rule,
        typed_cues=typed_cues,
        predicted_deltas=predicted_deltas,
    )


def _opposed_delta_dimensions(
    evidence: tuple[BodyEffectEvidence, ...],
) -> tuple[str, ...]:
    directions: dict[str, set[int]] = {}
    for item in evidence:
        for delta in item.predicted_deltas:
            directions.setdefault(delta.dimension, set()).add(1 if delta.delta > 0 else -1)
    return tuple(sorted(dimension for dimension, signs in directions.items() if len(signs) > 1))


class RuleBasedEmbodiedCueInterpreter:
    """Deterministic mapper requiring typed lanes, grounded evidence, and option intent."""

    mapper_id = RULE_BASED_MAPPER_ID
    mapper_revision = RULE_BASED_MAPPER_REVISION

    def __init__(
        self,
        ruleset: InstinktEffectRuleSet | None = None,
        *,
        association_records: tuple[InstinktAssociation, ...] = (),
    ) -> None:
        self._ruleset = ruleset or load_instinkt_effect_rules()
        records = tuple(_trusted_copy(item) for item in association_records)
        if len({item.association_id for item in records}) != len(records):
            raise ValueError("Instinkt association records must have unique IDs")
        self._association_records = {
            item.association_id: item for item in records
        }

    @property
    def ruleset(self) -> InstinktEffectRuleSet:
        return self._ruleset

    @property
    def association_records(self) -> tuple[InstinktAssociation, ...]:
        return tuple(
            self._association_records[key]
            for key in sorted(self._association_records)
        )

    def infer_effects(
        self,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        world: InstinktWorld,
        body: BodyState,
        option: DecisionOption,
    ) -> OptionBodyEffectPrediction:
        scene = _trusted_copy(scene)
        packet = _trusted_copy(packet)
        world = _trusted_copy(world)
        body = _trusted_copy(body)
        option = _trusted_copy(option)
        packet.validate_against(scene, body)
        if option not in scene.options:
            raise ValueError("Body-effect option must be an exact member of the scene")

        evidence: list[BodyEffectEvidence] = []
        unsupported: set[str] = set()
        conflicts: set[str] = set()
        ambiguous_relation = False
        unbound = _unbound_lane_cues(packet)
        if unbound:
            unsupported.update(BODY_DIMENSIONS)
            conflicts.update(
                f"cue_binding_missing:{lane}" for lane, _ in unbound
            )
            ambiguous_relation = True
        for rule in self._ruleset.rules:
            class_bindings = tuple(
                binding
                for binding in packet.cue_evidence_bindings
                if binding.cue_class == rule.cue_class
            )
            invalid_bindings = tuple(
                binding
                for binding in class_bindings
                if binding.lane not in rule.packet_lanes
                or binding.assertion_status != "asserted_positive"
            )
            if invalid_bindings:
                unsupported.update(rule.allowed_body_dimensions)
                conflicts.update(
                    (
                        f"cue_lane_mismatch:{rule.cue_class}"
                        if binding.lane not in rule.packet_lanes
                        else (
                            "cue_assertion_"
                            f"{binding.assertion_status}:{rule.cue_class}"
                        )
                    )
                    for binding in invalid_bindings
                )
                ambiguous_relation = True
                continue
            bindings = _typed_candidates(packet=packet, rule=rule)
            if not bindings:
                continue
            grounded = _source_evidence(
                scene=scene,
                rule=rule,
                bindings=bindings,
            )
            option_text = f"{option.label}. {option.description}"
            option_relation, relation_status = classify_option_effect_relation(
                option_text,
                protective_terms=rule.protective_option_terms,
                adverse_terms=rule.adverse_option_terms,
            )
            if not grounded or relation_status == "no_match":
                unsupported.update(rule.allowed_body_dimensions)
                continue
            if relation_status != "unambiguous" or option_relation is None:
                conflicts.add(
                    f"option_relation_{relation_status}:{rule.cue_class}"
                )
                unsupported.update(rule.allowed_body_dimensions)
                ambiguous_relation = True
                continue
            deltas = (
                rule.protective_deltas
                if option_relation == "protective"
                else rule.adverse_deltas
            )
            typed_cues = tuple(binding.cue for binding in bindings)
            scoped_association_ids = set(world.associations)
            scored_matches = tuple(
                _score_association(
                    association=record,
                    body=body,
                    rule=rule,
                    typed_cues=typed_cues,
                    predicted_deltas=deltas,
                )
                for association_id, record in sorted(self._association_records.items())
                if association_id in scoped_association_ids
            )
            association_matches = tuple(
                match
                for match in scored_matches
                if match.cue_signature_score > 0.0
                and match.retrieval_score
                >= self._ruleset.minimum_association_score
            )
            association_ids = tuple(
                item.association_id for item in association_matches
            )
            if not association_ids and rule.association_policy == "required":
                unsupported.update(delta.dimension for delta in deltas)
                continue
            evidence.append(
                BodyEffectEvidence.create(
                    rule_id=rule.rule_id,
                    cue_class=rule.cue_class,
                    cue_binding_ids=tuple(
                        binding.binding_id for binding in bindings
                    ),
                    source_evidence_ids=tuple(item.evidence_id for item in grounded),
                    association_ids=association_ids,
                    association_matches=association_matches,
                    association_basis=(
                        "matched_association"
                        if association_ids
                        else "canonical_default_rule"
                    ),
                    option_relation=option_relation,
                    predicted_deltas=deltas,
                    confidence=min(
                        rule.confidence, min(item.confidence for item in grounded)
                    ),
                    uncertainty=rule.uncertainty_rule,
                )
            )

        if ambiguous_relation:
            for item in evidence:
                unsupported.update(
                    delta.dimension for delta in item.predicted_deltas
                )
            frozen_evidence: tuple[BodyEffectEvidence, ...] = ()
        else:
            frozen_evidence = tuple(evidence)
        active = {item.cue_class for item in frozen_evidence}
        for pair in self._ruleset.conflict_pairs:
            if pair.first in active and pair.second in active:
                conflicts.add(f"cue_conflict:{pair.first}:{pair.second}")
        for dimension in _opposed_delta_dimensions(frozen_evidence):
            conflicts.add(f"delta_direction_conflict:{dimension}")

        has_delta = bool(combine_body_effect_deltas(frozen_evidence))
        uncertainty = (
            "Rule-backed effect; every delta is grounded in packet-scoped evidence "
            "and remains an implementation hypothesis."
            if has_delta
            else "Insufficient grounded, typed, option-specific support; no default effect was emitted."
        )
        prediction = OptionBodyEffectPrediction.create(
            option=option,
            scene=scene,
            packet=packet,
            world=world,
            body=body,
            ruleset=self._ruleset,
            mapper_id=self.mapper_id,
            mapper_revision=self.mapper_revision,
            evidence=frozen_evidence,
            unsupported_dimensions=tuple(unsupported),
            conflict_flags=tuple(conflicts),
            abstains=not has_delta,
            uncertainty=uncertainty,
        )
        return prediction.validate_against(
            scene=scene,
            packet=packet,
            world=world,
            body=body,
            option=option,
            ruleset=self._ruleset,
            association_records=self.association_records,
        )


class ModelBackedEffectInferenceDisabledError(RuntimeError):
    """The intentionally non-operational model-backed mapper was invoked."""


class ModelBackedEmbodiedCueInterpreterStub:
    """Protocol-conformant placeholder; it performs no model or network call."""

    mapper_id = MODEL_BACKED_MAPPER_ID
    mapper_revision = MODEL_BACKED_MAPPER_REVISION

    def infer_effects(
        self,
        scene: SceneEvent,
        packet: InstinktInputPacket,
        world: InstinktWorld,
        body: BodyState,
        option: DecisionOption,
    ) -> OptionBodyEffectPrediction:
        del scene, packet, world, body, option
        raise ModelBackedEffectInferenceDisabledError(
            "Model-backed body-effect inference is a disabled C5 stub; "
            "no validated provider implementation is configured."
        )


__all__ = [
    "EmbodiedCueInterpreter",
    "MODEL_BACKED_MAPPER_ID",
    "MODEL_BACKED_MAPPER_REVISION",
    "ModelBackedEffectInferenceDisabledError",
    "ModelBackedEmbodiedCueInterpreterStub",
    "RULE_BASED_MAPPER_ID",
    "RULE_BASED_MAPPER_REVISION",
    "RuleBasedEmbodiedCueInterpreter",
]
