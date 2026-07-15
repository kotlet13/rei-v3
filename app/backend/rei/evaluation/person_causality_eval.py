"""Bounded C7 person-causality evaluation over the real REI engine.

This evaluator is deliberately narrower than the integrated C7 benchmark.  It
tests one architectural claim: two persons may start from the same native
inputs, diverge through Character-governed observable behavior, receive
different deterministic simulator outcomes, and consequently expose different
later native semantics through their learned worlds.  Character is never an
input to the simulator transition and the authoritative mediation probe runs
with history removed so content-addressed Ego lineage cannot masquerade as a
semantic effect.

The result is a bounded simulator contract, not empirical evidence about a
person and not semantic or diagnostic authority.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from ..ego.trace_store import InMemoryEgoTraceStore
from ..ego.world_updates import (
    EmocioLongitudinalVisualSignal,
    EmocioWorldUpdater,
    InstinktLongitudinalBodySignal,
    InstinktWorldUpdater,
    RacioWorldUpdater,
)
from ..engine import ReiNativeCycleRequest, ReiNativeEngine
from ..governance.profiles import parse_character_profile
from ..ids import content_id, sha256_hex
from ..models.character import CharacterProfileId
from ..models.common import (
    FrozenArtifactModel,
    FrozenModel,
    HashDigest,
    NonEmptyId,
    NonEmptyText,
    Score01,
)
from ..models.conscious import BehaviorResultant, BehaviorStatus
from ..models.ego import OutcomeRecord
from ..models.emocio import EmocioWorld
from ..models.instinkt import InstinktWorld
from ..models.racio import RacioWorld
from ..models.scene import EvidenceItem, SceneEvent
from ..profile_matrix import build_matrix_acceptance_state
from ..providers.deterministic import build_deterministic_native_providers
from ..providers.native import DeterministicExecutionClock
from .longitudinal_eval import (
    MAX_LONGITUDINAL_CORPUS_BYTES,
    MAX_LONGITUDINAL_TEMPLATE_BYTES,
    _InMemoryEvaluationArtifactStore,
    _build_scenario,
    _materialize_visual_signal,
    _read_bounded,
    parse_longitudinal_corpus,
)


PERSON_CAUSALITY_EVALUATOR_REVISION = "c7-person-causality-v1"
PERSON_CAUSALITY_POLICY_ID = "c7-observable-action-simulator-v1"
PERSON_CAUSALITY_POLICY_REVISION = "1"
PERSON_CAUSALITY_SCOPE = "deterministic_simulator_only"
PERSON_CAUSALITY_GATE_KIND = "bounded_simulator_causal_contract"
PERSON_CAUSALITY_REVIEW_STATUS = "internal_non_blind"
PERSON_CAUSALITY_GOLD_STATUS = "implementation_hypothesis"
PERSON_CAUSALITY_HISTORY_SCOPE = (
    "not_claimed_lineage_ids_character_dependent"
)
PERSON_CAUSALITY_MEASURED_BODY_STATUS = "open_no_verified_c5_replay"
PERSON_CAUSALITY_INSTINKT_SCOPE = (
    "prediction_sidecar_only_world_mutation_open_until_verified_c5_replay"
)
SOURCE_SEQUENCE_ID = "paired_character_repeated_stall"
_EXPECTED_CASE_IDS = (
    "equal_action_e_vs_i",
    "identity_sham_r_top",
    "positive_r_vs_e",
    "positive_r_vs_i",
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PERSON_CAUSALITY_CORPUS_PATH = (
    _REPO_ROOT
    / "knowledge"
    / "canon_v2"
    / "semantic_lab_v1"
    / "c6_longitudinal"
    / "corpus.json"
)
DEFAULT_PERSON_CAUSALITY_TEMPLATE_PATH = (
    _REPO_ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)

ControlKind = Literal["positive", "equal_action", "identity_sham"]
ObservationCode = Literal[
    "workshop_remained_closed",
    "workshop_reopened",
]

_TRANSITION_RULES: dict[tuple[str, str | None], tuple[ObservationCode, str]] = {
    ("executed", "option_leave"): (
        "workshop_remained_closed",
        "workshop remained closed after option_leave",
    ),
    ("executed", "option_restore"): (
        "workshop_reopened",
        "workshop reopened after option_restore",
    ),
}
_POLICY_HASH = sha256_hex(
    {
        "policy_id": PERSON_CAUSALITY_POLICY_ID,
        "revision": PERSON_CAUSALITY_POLICY_REVISION,
        "rules": tuple(
            (status, option_id, code, effect)
            for (status, option_id), (code, effect) in sorted(
                _TRANSITION_RULES.items()
            )
        ),
    }
)


def _identity_payload(value: FrozenArtifactModel) -> dict[str, object]:
    """Return a model payload without its conventional ID/hash envelope."""

    id_fields = tuple(name for name in type(value).model_fields if name.endswith("_id"))
    hash_fields = tuple(
        name for name in type(value).model_fields if name.endswith("_hash")
    )
    return value.model_dump(
        mode="python",
        round_trip=True,
        exclude={*id_fields, *hash_fields},
    )


def _validate_content_addressed(
    value: FrozenArtifactModel,
    *,
    prefix: str,
    id_field: str,
    hash_field: str,
) -> None:
    base = value.model_dump(
        mode="python",
        round_trip=True,
        exclude={id_field, hash_field},
    )
    if getattr(value, id_field) != content_id(prefix, base):
        raise ValueError(f"{type(value).__name__} ID differs from its content")
    payload = {id_field: getattr(value, id_field), **base}
    if getattr(value, hash_field) != sha256_hex(payload):
        raise ValueError(f"{type(value).__name__} hash differs from its content")


class PersonCausalityArmSpec(FrozenModel):
    arm_id: NonEmptyId
    profile_id: CharacterProfileId
    character_id: NonEmptyId


class PersonCausalityCaseSpec(FrozenModel):
    case_id: NonEmptyId
    control_kind: ControlKind
    arms: tuple[PersonCausalityArmSpec, PersonCausalityArmSpec]

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        if self.arms[0].arm_id == self.arms[1].arm_id:
            raise ValueError("Person-causality arm IDs must be distinct")
        if self.arms[0].character_id == self.arms[1].character_id:
            raise ValueError("Person-causality Character IDs must be distinct")
        same_profile = self.arms[0].profile_id == self.arms[1].profile_id
        if same_profile != (self.control_kind == "identity_sham"):
            raise ValueError(
                "Only an identity-sham case may use the same Character profile"
            )
        return self


class ObservableAction(FrozenArtifactModel):
    """The only behavior fields visible to the deterministic environment."""

    schema_version: Literal["rei-c7-observable-action-v1"] = (
        "rei-c7-observable-action-v1"
    )
    action_id: NonEmptyId
    source_resultant_id: NonEmptyId
    source_resultant_hash: HashDigest
    behavior_status: BehaviorStatus
    option_id: NonEmptyId | None
    action_hash: HashDigest

    @classmethod
    def create(cls, resultant: BehaviorResultant) -> "ObservableAction":
        resultant = BehaviorResultant.model_validate(
            resultant.model_dump(mode="python", round_trip=True)
        )
        base = {
            "schema_version": "rei-c7-observable-action-v1",
            "source_resultant_id": resultant.resultant_id,
            "source_resultant_hash": resultant.resultant_hash
            or resultant.content_hash(),
            "behavior_status": resultant.status,
            "option_id": resultant.option_id,
        }
        action_id = content_id("observable_action", base)
        payload = {"action_id": action_id, **base}
        return cls(**payload, action_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        _validate_content_addressed(
            self,
            prefix="observable_action",
            id_field="action_id",
            hash_field="action_hash",
        )
        return self


def _evidence_for_transition(
    *,
    observation_code: ObservationCode,
    observed_effect: str,
) -> EvidenceItem:
    base = {
        "schema_version": "rei-native-evidence-v1",
        "modality": "simulator",
        "content": observed_effect,
        "grounded": False,
        "source_ref": (
            f"c7-simulator-policy:{PERSON_CAUSALITY_POLICY_ID}:"
            f"{observation_code}"
        ),
        "confidence": 1.0,
        "provenance_kind": "generated",
        "inferred_by": PERSON_CAUSALITY_POLICY_ID,
    }
    return EvidenceItem(evidence_id=content_id("evidence", base), **base)


def _outcome_for_transition(
    *,
    event_id: str,
    recorded_at: object,
    observed_effect: str,
    evidence_id: str,
) -> OutcomeRecord:
    base = {
        "schema_version": "rei-native-outcome-record-v1",
        "event_id": event_id,
        "recorded_at": recorded_at,
        "source": "simulator",
        "observed_effects": (observed_effect,),
        "evidence_ids": (evidence_id,),
    }
    return OutcomeRecord(outcome_id=content_id("outcome", base), **base)


class SimulatorOutcomeTransition(FrozenArtifactModel):
    """One character-blind mapping from observable action to simulated outcome."""

    schema_version: Literal["rei-c7-simulator-transition-v1"] = (
        "rei-c7-simulator-transition-v1"
    )
    transition_id: NonEmptyId
    policy_id: Literal["c7-observable-action-simulator-v1"] = (
        PERSON_CAUSALITY_POLICY_ID
    )
    policy_revision: Literal["1"] = PERSON_CAUSALITY_POLICY_REVISION
    policy_hash: HashDigest
    causality_scope: Literal["deterministic_simulator_only"] = (
        PERSON_CAUSALITY_SCOPE
    )
    source_action: ObservableAction
    observation_code: ObservationCode
    observed_effect: NonEmptyText
    generated_evidence: EvidenceItem
    simulator_outcome: OutcomeRecord
    transition_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        resultant: BehaviorResultant,
        target_event_id: str,
        recorded_at: object,
    ) -> "SimulatorOutcomeTransition":
        action = ObservableAction.create(resultant)
        key = (action.behavior_status, action.option_id)
        rule = _TRANSITION_RULES.get(key)
        if rule is None:
            raise ValueError(f"Unsupported bounded simulator action: {key!r}")
        observation_code, observed_effect = rule
        evidence = _evidence_for_transition(
            observation_code=observation_code,
            observed_effect=observed_effect,
        )
        outcome = _outcome_for_transition(
            event_id=target_event_id,
            recorded_at=recorded_at,
            observed_effect=observed_effect,
            evidence_id=evidence.evidence_id,
        )
        base = {
            "schema_version": "rei-c7-simulator-transition-v1",
            "policy_id": PERSON_CAUSALITY_POLICY_ID,
            "policy_revision": PERSON_CAUSALITY_POLICY_REVISION,
            "policy_hash": _POLICY_HASH,
            "causality_scope": PERSON_CAUSALITY_SCOPE,
            "source_action": action,
            "observation_code": observation_code,
            "observed_effect": observed_effect,
            "generated_evidence": evidence,
            "simulator_outcome": outcome,
        }
        transition_id = content_id("simulator_transition", base)
        payload = {"transition_id": transition_id, **base}
        return cls(**payload, transition_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_transition(self) -> Self:
        key = (self.source_action.behavior_status, self.source_action.option_id)
        expected = _TRANSITION_RULES.get(key)
        if expected != (self.observation_code, self.observed_effect):
            raise ValueError(
                "Simulator transition must depend only on behavior status and option"
            )
        expected_evidence = _evidence_for_transition(
            observation_code=self.observation_code,
            observed_effect=self.observed_effect,
        )
        if self.generated_evidence != expected_evidence:
            raise ValueError("Generated transition evidence differs from its rule")
        expected_outcome = _outcome_for_transition(
            event_id=self.simulator_outcome.event_id,
            recorded_at=self.simulator_outcome.recorded_at,
            observed_effect=self.observed_effect,
            evidence_id=expected_evidence.evidence_id,
        )
        if self.simulator_outcome != expected_outcome:
            raise ValueError("Simulator outcome differs from its transition evidence")
        if (
            self.policy_hash != _POLICY_HASH
            or self.generated_evidence.grounded
            or self.generated_evidence.provenance_kind != "generated"
            or self.generated_evidence.modality != "simulator"
            or self.simulator_outcome.source != "simulator"
        ):
            raise ValueError("Simulator transition crosses its authority boundary")
        _validate_content_addressed(
            self,
            prefix="simulator_transition",
            id_field="transition_id",
            hash_field="transition_hash",
        )
        return self


class RacioNativeSemanticView(FrozenModel):
    option_id: NonEmptyId | None
    facts_used: tuple[str, ...]
    uncertainty: str


class EmocioNativeSemanticView(FrozenModel):
    option_id: NonEmptyId | None
    action_tendency: str
    valuation_dimensions: tuple[tuple[NonEmptyText, Score01], ...]


class InstinktNativeSemanticView(FrozenModel):
    option_id: NonEmptyId | None
    dominant_alarm: str
    danger_claims: tuple[str, ...]
    protected_targets: tuple[str, ...]
    predicted_loss: Score01
    recoverability: Score01
    boundary_outcome: str
    trust_outcome: str
    attachment_outcome: str
    escape_outcome: str


class NativeSemanticFingerprint(FrozenArtifactModel):
    """Whitelisted native semantics with all lineage/artifact IDs omitted."""

    schema_version: Literal["rei-c7-native-semantic-fingerprint-v1"] = (
        "rei-c7-native-semantic-fingerprint-v1"
    )
    fingerprint_id: NonEmptyId
    racio: RacioNativeSemanticView
    emocio: EmocioNativeSemanticView
    instinkt: InstinktNativeSemanticView
    fingerprint_hash: HashDigest

    @classmethod
    def create(cls, result: object) -> "NativeSemanticFingerprint":
        bundle = result.native_bundle
        selected = next(
            item
            for item in result.instinkt_execution.rollouts
            if item.rollout_id == bundle.instinkt.decisive_rollout_id
        )
        base = {
            "schema_version": "rei-c7-native-semantic-fingerprint-v1",
            "racio": RacioNativeSemanticView(
                option_id=bundle.racio.option_id,
                facts_used=bundle.racio.facts_used,
                uncertainty=bundle.racio.uncertainty,
            ),
            "emocio": EmocioNativeSemanticView(
                option_id=bundle.emocio.option_id,
                action_tendency=bundle.emocio.action_tendency,
                valuation_dimensions=tuple(
                    (item.name, item.score)
                    for item in bundle.emocio.valuation_dimensions
                ),
            ),
            "instinkt": InstinktNativeSemanticView(
                option_id=bundle.instinkt.option_id,
                dominant_alarm=bundle.instinkt.dominant_alarm,
                danger_claims=bundle.instinkt.danger_claims,
                protected_targets=bundle.instinkt.protected_targets,
                predicted_loss=selected.predicted_loss,
                recoverability=selected.recoverability,
                boundary_outcome=selected.boundary_outcome,
                trust_outcome=selected.trust_outcome,
                attachment_outcome=selected.attachment_outcome,
                escape_outcome=selected.escape_outcome,
            ),
        }
        fingerprint_id = content_id("native_semantics", base)
        payload = {"fingerprint_id": fingerprint_id, **base}
        return cls(**payload, fingerprint_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        _validate_content_addressed(
            self,
            prefix="native_semantics",
            id_field="fingerprint_id",
            hash_field="fingerprint_hash",
        )
        return self


class WorldSemanticFingerprint(FrozenArtifactModel):
    """Substantive world fields used by the causal gate, excluding lineage refs."""

    schema_version: Literal["rei-c7-world-semantic-fingerprint-v1"] = (
        "rei-c7-world-semantic-fingerprint-v1"
    )
    fingerprint_id: NonEmptyId
    racio_facts: tuple[str, ...]
    racio_commitments: tuple[str, ...]
    emocio_motor_patterns: tuple[str, ...]
    instinkt_threat_patterns: tuple[str, ...]
    instinkt_attachment_objects: tuple[str, ...]
    instinkt_boundary_patterns: tuple[str, ...]
    fingerprint_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        racio_world: RacioWorld,
        emocio_world: EmocioWorld,
        instinkt_world: InstinktWorld,
    ) -> "WorldSemanticFingerprint":
        base = {
            "schema_version": "rei-c7-world-semantic-fingerprint-v1",
            "racio_facts": racio_world.facts,
            "racio_commitments": racio_world.commitments,
            "emocio_motor_patterns": tuple(
                item
                for item in emocio_world.motor_patterns
                if item.startswith(("behavior:", "outcome:"))
            ),
            "instinkt_threat_patterns": instinkt_world.threat_patterns,
            "instinkt_attachment_objects": instinkt_world.attachment_objects,
            "instinkt_boundary_patterns": instinkt_world.boundary_patterns,
        }
        fingerprint_id = content_id("world_semantics", base)
        payload = {"fingerprint_id": fingerprint_id, **base}
        return cls(**payload, fingerprint_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        _validate_content_addressed(
            self,
            prefix="world_semantics",
            id_field="fingerprint_id",
            hash_field="fingerprint_hash",
        )
        return self


def _surface_hash(result: object) -> str:
    def canonical_surface_item(value: object) -> object:
        if isinstance(value, BaseModel):
            return canonical_surface_item(
                value.model_dump(mode="python", round_trip=True)
            )
        if is_dataclass(value):
            return {
                field.name: canonical_surface_item(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, dict):
            return {
                str(key): canonical_surface_item(item)
                for key, item in value.items()
            }
        if isinstance(value, (tuple, list)):
            return tuple(canonical_surface_item(item) for item in value)
        namespace = getattr(value, "__dict__", None)
        if isinstance(namespace, dict):
            return canonical_surface_item(namespace)
        return value

    return sha256_hex(
        tuple(
            canonical_surface_item(item)
            for item in (
                result.racio_packet,
                result.emocio_packet,
                result.instinkt_packet,
                result.racio_execution,
                result.emocio_execution,
                result.instinkt_execution,
                result.native_bundle,
            )
        )
    )


def _initial_condition_hash(request: ReiNativeCycleRequest) -> str:
    """Hash every initial input except arm identity and structural Character."""

    return sha256_hex(
        request.model_dump(
            mode="python",
            round_trip=True,
            exclude={"run_id", "ego_id", "character"},
        )
    )


def _world_divergence(
    worlds: tuple[WorldSemanticFingerprint, WorldSemanticFingerprint],
) -> tuple[bool, bool, bool]:
    first, second = worlds
    racio = (
        first.racio_facts,
        first.racio_commitments,
    ) != (
        second.racio_facts,
        second.racio_commitments,
    )
    emocio = first.emocio_motor_patterns != second.emocio_motor_patterns
    instinkt = (
        first.instinkt_threat_patterns,
        first.instinkt_attachment_objects,
        first.instinkt_boundary_patterns,
    ) != (
        second.instinkt_threat_patterns,
        second.instinkt_attachment_objects,
        second.instinkt_boundary_patterns,
    )
    return racio, emocio, instinkt


def _semantic_text(value: FrozenArtifactModel) -> str:
    return json.dumps(
        _identity_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).casefold()


def _literal_leakage_count(
    *,
    character_ids: tuple[str, str],
    profile_ids: tuple[str, str],
    transitions: tuple[SimulatorOutcomeTransition, SimulatorOutcomeTransition],
    cycle1: tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
    worlds: tuple[WorldSemanticFingerprint, WorldSemanticFingerprint],
    probes: tuple[
        tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
        tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
    ],
) -> int:
    # Only public semantic content is scanned. Source IDs/hashes are deliberately
    # excluded because the report separately declines full-history lineage
    # noninterference.
    texts = [
        *(_semantic_text(item) for item in cycle1),
        *(_semantic_text(item) for item in worlds),
        *(_semantic_text(item) for row in probes for item in row),
        *(
            json.dumps(
                {
                    "observation_code": item.observation_code,
                    "observed_effect": item.observed_effect,
                    "evidence_content": item.generated_evidence.content,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).casefold()
            for item in transitions
        ),
    ]
    forbidden = tuple(
        value.casefold()
        for value in (*character_ids, *profile_ids)
        if value.strip()
    )
    return sum(text.count(token) for text in texts for token in forbidden)


def _case_result_base(
    *,
    case: PersonCausalityCaseSpec,
    initial_condition_hashes: tuple[str, str],
    initial_native_surface_hashes: tuple[str, str],
    initial_behavior_statuses: tuple[BehaviorStatus, BehaviorStatus],
    initial_behavior_option_ids: tuple[str | None, str | None],
    transitions: tuple[SimulatorOutcomeTransition, SimulatorOutcomeTransition],
    cycle1_native_semantics: tuple[
        NativeSemanticFingerprint, NativeSemanticFingerprint
    ],
    world_semantics: tuple[WorldSemanticFingerprint, WorldSemanticFingerprint],
    probe_native_surface_hashes: tuple[tuple[str, str], tuple[str, str]],
    probe_native_semantics: tuple[
        tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
        tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
    ],
) -> dict[str, object]:
    initial_condition_equal = initial_condition_hashes[0] == initial_condition_hashes[1]
    initial_equal = initial_native_surface_hashes[0] == initial_native_surface_hashes[1]
    behavior_diverged = (
        initial_behavior_statuses[0],
        initial_behavior_option_ids[0],
    ) != (
        initial_behavior_statuses[1],
        initial_behavior_option_ids[1],
    )
    outcomes_diverged = transitions[0].observation_code != transitions[1].observation_code
    cycle1_equal = cycle1_native_semantics[0] == cycle1_native_semantics[1]
    racio_diverged, emocio_diverged, instinkt_diverged = _world_divergence(
        world_semantics
    )
    fixed_world_invariant = all(
        row[0] == row[1] for row in probe_native_surface_hashes
    )
    mediation = all(
        probe_native_semantics[0][index]
        != probe_native_semantics[1][index]
        for index in range(2)
    )
    character_ids = tuple(item.character_id for item in case.arms)
    profile_ids = tuple(item.profile_id for item in case.arms)
    leakage_count = _literal_leakage_count(
        character_ids=character_ids,
        profile_ids=profile_ids,
        transitions=transitions,
        cycle1=cycle1_native_semantics,
        worlds=world_semantics,
        probes=probe_native_semantics,
    )
    common = (
        initial_condition_equal
        and initial_equal
        and cycle1_equal
        and fixed_world_invariant
        and leakage_count == 0
    )
    if case.control_kind == "positive":
        passes = bool(
            common
            and behavior_diverged
            and outcomes_diverged
            and racio_diverged
            and emocio_diverged
            and not instinkt_diverged
            and mediation
        )
    else:
        passes = bool(
            common
            and not behavior_diverged
            and not outcomes_diverged
            and not racio_diverged
            and not emocio_diverged
            and not instinkt_diverged
            and not mediation
        )
    return {
        "schema_version": "rei-c7-person-causality-case-result-v1",
        "case_id": case.case_id,
        "control_kind": case.control_kind,
        "arm_ids": tuple(item.arm_id for item in case.arms),
        "profile_ids": profile_ids,
        "character_ids": character_ids,
        "initial_condition_hashes": initial_condition_hashes,
        "initial_condition_equal": initial_condition_equal,
        "initial_native_surface_hashes": initial_native_surface_hashes,
        "initial_native_surface_equal": initial_equal,
        "initial_behavior_statuses": initial_behavior_statuses,
        "initial_behavior_option_ids": initial_behavior_option_ids,
        "behavior_diverged": behavior_diverged,
        "transitions": transitions,
        "simulator_outcomes_diverged": outcomes_diverged,
        "cycle1_native_semantics": cycle1_native_semantics,
        "cycle1_native_semantics_equal": cycle1_equal,
        "world_semantics": world_semantics,
        "racio_world_diverged": racio_diverged,
        "emocio_world_diverged": emocio_diverged,
        "instinkt_world_diverged": instinkt_diverged,
        "probe_native_surface_hashes": probe_native_surface_hashes,
        "probe_native_semantics": probe_native_semantics,
        "fixed_world_character_invariance": fixed_world_invariant,
        "world_mediation_semantic_divergence": mediation,
        "literal_character_leakage_count": leakage_count,
        "passes": passes,
    }


class PersonCausalityCaseResult(FrozenArtifactModel):
    schema_version: Literal["rei-c7-person-causality-case-result-v1"] = (
        "rei-c7-person-causality-case-result-v1"
    )
    case_result_id: NonEmptyId
    case_id: NonEmptyId
    control_kind: ControlKind
    arm_ids: tuple[NonEmptyId, NonEmptyId]
    profile_ids: tuple[CharacterProfileId, CharacterProfileId]
    character_ids: tuple[NonEmptyId, NonEmptyId]
    initial_condition_hashes: tuple[HashDigest, HashDigest]
    initial_condition_equal: bool
    initial_native_surface_hashes: tuple[HashDigest, HashDigest]
    initial_native_surface_equal: bool
    initial_behavior_statuses: tuple[BehaviorStatus, BehaviorStatus]
    initial_behavior_option_ids: tuple[NonEmptyId | None, NonEmptyId | None]
    behavior_diverged: bool
    transitions: tuple[SimulatorOutcomeTransition, SimulatorOutcomeTransition]
    simulator_outcomes_diverged: bool
    cycle1_native_semantics: tuple[
        NativeSemanticFingerprint, NativeSemanticFingerprint
    ]
    cycle1_native_semantics_equal: bool
    world_semantics: tuple[WorldSemanticFingerprint, WorldSemanticFingerprint]
    racio_world_diverged: bool
    emocio_world_diverged: bool
    instinkt_world_diverged: bool
    probe_native_surface_hashes: tuple[
        tuple[HashDigest, HashDigest], tuple[HashDigest, HashDigest]
    ]
    probe_native_semantics: tuple[
        tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
        tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
    ]
    fixed_world_character_invariance: bool
    world_mediation_semantic_divergence: bool
    literal_character_leakage_count: int = Field(ge=0)
    passes: bool
    result_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        case: PersonCausalityCaseSpec,
        initial_condition_hashes: tuple[str, str],
        initial_native_surface_hashes: tuple[str, str],
        initial_behavior_statuses: tuple[BehaviorStatus, BehaviorStatus],
        initial_behavior_option_ids: tuple[str | None, str | None],
        transitions: tuple[
            SimulatorOutcomeTransition, SimulatorOutcomeTransition
        ],
        cycle1_native_semantics: tuple[
            NativeSemanticFingerprint, NativeSemanticFingerprint
        ],
        world_semantics: tuple[
            WorldSemanticFingerprint, WorldSemanticFingerprint
        ],
        probe_native_surface_hashes: tuple[
            tuple[str, str], tuple[str, str]
        ],
        probe_native_semantics: tuple[
            tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
            tuple[NativeSemanticFingerprint, NativeSemanticFingerprint],
        ],
    ) -> "PersonCausalityCaseResult":
        base = _case_result_base(
            case=case,
            initial_condition_hashes=initial_condition_hashes,
            initial_native_surface_hashes=initial_native_surface_hashes,
            initial_behavior_statuses=initial_behavior_statuses,
            initial_behavior_option_ids=initial_behavior_option_ids,
            transitions=transitions,
            cycle1_native_semantics=cycle1_native_semantics,
            world_semantics=world_semantics,
            probe_native_surface_hashes=probe_native_surface_hashes,
            probe_native_semantics=probe_native_semantics,
        )
        case_result_id = content_id("person_causality_case", base)
        payload = {"case_result_id": case_result_id, **base}
        return cls(**payload, result_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        case = PersonCausalityCaseSpec(
            case_id=self.case_id,
            control_kind=self.control_kind,
            arms=(
                PersonCausalityArmSpec(
                    arm_id=self.arm_ids[0],
                    profile_id=self.profile_ids[0],
                    character_id=self.character_ids[0],
                ),
                PersonCausalityArmSpec(
                    arm_id=self.arm_ids[1],
                    profile_id=self.profile_ids[1],
                    character_id=self.character_ids[1],
                ),
            ),
        )
        expected = _case_result_base(
            case=case,
            initial_condition_hashes=self.initial_condition_hashes,
            initial_native_surface_hashes=self.initial_native_surface_hashes,
            initial_behavior_statuses=self.initial_behavior_statuses,
            initial_behavior_option_ids=self.initial_behavior_option_ids,
            transitions=self.transitions,
            cycle1_native_semantics=self.cycle1_native_semantics,
            world_semantics=self.world_semantics,
            probe_native_surface_hashes=self.probe_native_surface_hashes,
            probe_native_semantics=self.probe_native_semantics,
        )
        actual = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"case_result_id", "result_hash"},
        )
        if sha256_hex(actual) != sha256_hex(expected):
            changed = tuple(
                key
                for key in sorted(set(actual) | set(expected))
                if actual.get(key) != expected.get(key)
            )
            raise ValueError(
                "Person-causality case result differs from replayed metrics: "
                f"{changed!r}"
            )
        _validate_content_addressed(
            self,
            prefix="person_causality_case",
            id_field="case_result_id",
            hash_field="result_hash",
        )
        return self


def _report_base(
    *,
    source_corpus_sha256: str,
    template_request_hash: str,
    shared_scenario_id: str,
    shared_scenario_hash: str,
    cases: tuple[PersonCausalityCaseResult, ...],
) -> dict[str, object]:
    ordered = tuple(sorted(cases, key=lambda item: item.case_id))
    case_count = len(ordered)
    positive_count = sum(item.control_kind == "positive" for item in ordered)
    control_count = case_count - positive_count
    passing_count = sum(item.passes for item in ordered)
    shared_initial_conditions = sum(
        item.initial_condition_equal for item in ordered
    )
    initial_invariance = sum(item.initial_native_surface_equal for item in ordered)
    fixed_invariance = sum(
        item.fixed_world_character_invariance for item in ordered
    )
    mediation = sum(
        item.control_kind == "positive"
        and item.world_mediation_semantic_divergence
        for item in ordered
    )
    leakage = sum(item.literal_character_leakage_count for item in ordered)
    kinds = tuple(item.control_kind for item in ordered)
    case_ids = tuple(item.case_id for item in ordered)
    gate = bool(
        case_count == 4
        and case_ids == _EXPECTED_CASE_IDS
        and positive_count == 2
        and control_count == 2
        and kinds.count("equal_action") == 1
        and kinds.count("identity_sham") == 1
        and passing_count == case_count
        and shared_initial_conditions == case_count
        and initial_invariance == case_count
        and fixed_invariance == case_count
        and mediation == positive_count
        and leakage == 0
    )
    return {
        "schema_version": "rei-c7-person-causality-report-v1",
        "evaluator_revision": PERSON_CAUSALITY_EVALUATOR_REVISION,
        "gate_kind": PERSON_CAUSALITY_GATE_KIND,
        "review_status": PERSON_CAUSALITY_REVIEW_STATUS,
        "gold_status": PERSON_CAUSALITY_GOLD_STATUS,
        "person_causality_scope": PERSON_CAUSALITY_SCOPE,
        "full_history_character_noninterference": (
            PERSON_CAUSALITY_HISTORY_SCOPE
        ),
        "semantic_authority_granted": False,
        "measured_body_outcome_status": PERSON_CAUSALITY_MEASURED_BODY_STATUS,
        "instinkt_learning_scope": PERSON_CAUSALITY_INSTINKT_SCOPE,
        "measured_body_signal_cycle_count": 0,
        "source_sequence_id": SOURCE_SEQUENCE_ID,
        "source_corpus_sha256": source_corpus_sha256,
        "template_request_hash": template_request_hash,
        "shared_scenario_id": shared_scenario_id,
        "shared_scenario_hash": shared_scenario_hash,
        "cases": ordered,
        "case_count": case_count,
        "positive_case_count": positive_count,
        "control_case_count": control_count,
        "passing_case_count": passing_count,
        "shared_initial_condition_case_count": shared_initial_conditions,
        "initial_native_invariance_case_count": initial_invariance,
        "fixed_world_character_invariance_case_count": fixed_invariance,
        "positive_world_mediation_case_count": mediation,
        "literal_character_leakage_count": leakage,
        "gate_passed": gate,
    }


class PersonCausalityEvaluationReport(FrozenArtifactModel):
    schema_version: Literal["rei-c7-person-causality-report-v1"] = (
        "rei-c7-person-causality-report-v1"
    )
    report_id: NonEmptyId
    evaluator_revision: Literal["c7-person-causality-v1"] = (
        PERSON_CAUSALITY_EVALUATOR_REVISION
    )
    gate_kind: Literal["bounded_simulator_causal_contract"] = (
        PERSON_CAUSALITY_GATE_KIND
    )
    review_status: Literal["internal_non_blind"] = PERSON_CAUSALITY_REVIEW_STATUS
    gold_status: Literal["implementation_hypothesis"] = PERSON_CAUSALITY_GOLD_STATUS
    person_causality_scope: Literal["deterministic_simulator_only"] = (
        PERSON_CAUSALITY_SCOPE
    )
    full_history_character_noninterference: Literal[
        "not_claimed_lineage_ids_character_dependent"
    ] = PERSON_CAUSALITY_HISTORY_SCOPE
    semantic_authority_granted: Literal[False] = False
    measured_body_outcome_status: Literal["open_no_verified_c5_replay"] = (
        PERSON_CAUSALITY_MEASURED_BODY_STATUS
    )
    instinkt_learning_scope: Literal[
        "prediction_sidecar_only_world_mutation_open_until_verified_c5_replay"
    ] = PERSON_CAUSALITY_INSTINKT_SCOPE
    measured_body_signal_cycle_count: Literal[0] = 0
    source_sequence_id: Literal["paired_character_repeated_stall"] = (
        SOURCE_SEQUENCE_ID
    )
    source_corpus_sha256: HashDigest
    template_request_hash: HashDigest
    shared_scenario_id: NonEmptyId
    shared_scenario_hash: HashDigest
    cases: tuple[PersonCausalityCaseResult, ...]
    case_count: int = Field(ge=0)
    positive_case_count: int = Field(ge=0)
    control_case_count: int = Field(ge=0)
    passing_case_count: int = Field(ge=0)
    shared_initial_condition_case_count: int = Field(ge=0)
    initial_native_invariance_case_count: int = Field(ge=0)
    fixed_world_character_invariance_case_count: int = Field(ge=0)
    positive_world_mediation_case_count: int = Field(ge=0)
    literal_character_leakage_count: int = Field(ge=0)
    gate_passed: bool
    report_hash: HashDigest

    @classmethod
    def create(
        cls,
        *,
        source_corpus_sha256: str,
        template_request_hash: str,
        shared_scenario_id: str,
        shared_scenario_hash: str,
        cases: tuple[PersonCausalityCaseResult, ...],
    ) -> "PersonCausalityEvaluationReport":
        base = _report_base(
            source_corpus_sha256=source_corpus_sha256,
            template_request_hash=template_request_hash,
            shared_scenario_id=shared_scenario_id,
            shared_scenario_hash=shared_scenario_hash,
            cases=cases,
        )
        report_id = content_id("person_causality_report", base)
        payload = {"report_id": report_id, **base}
        return cls(**payload, report_hash=sha256_hex(payload))

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        expected = _report_base(
            source_corpus_sha256=self.source_corpus_sha256,
            template_request_hash=self.template_request_hash,
            shared_scenario_id=self.shared_scenario_id,
            shared_scenario_hash=self.shared_scenario_hash,
            cases=self.cases,
        )
        actual = self.model_dump(
            mode="python",
            round_trip=True,
            exclude={"report_id", "report_hash"},
        )
        if sha256_hex(actual) != sha256_hex(expected):
            raise ValueError("Person-causality report differs from replayed aggregates")
        _validate_content_addressed(
            self,
            prefix="person_causality_report",
            id_field="report_id",
            hash_field="report_hash",
        )
        return self


@dataclass(slots=True)
class _ArmRuntime:
    spec: PersonCausalityArmSpec
    ego_id: str
    character: object
    artifact_store: _InMemoryEvaluationArtifactStore
    trace_store: InMemoryEgoTraceStore
    providers: object
    racio_world: RacioWorld
    emocio_world: EmocioWorld
    instinkt_world: InstinktWorld
    historical_bundles: list[object]
    historical_emocio_signals: list[EmocioLongitudinalVisualSignal]
    historical_instinkt_signals: list[InstinktLongitudinalBodySignal]


def _new_arm(
    *,
    case: PersonCausalityCaseSpec,
    arm: PersonCausalityArmSpec,
    template: ReiNativeCycleRequest,
) -> _ArmRuntime:
    return _ArmRuntime(
        spec=arm,
        ego_id=f"c7_person_{case.case_id}_{arm.arm_id}",
        character=parse_character_profile(
            arm.profile_id,
            character_id=arm.character_id,
        ),
        artifact_store=_InMemoryEvaluationArtifactStore(),
        trace_store=InMemoryEgoTraceStore(),
        providers=build_deterministic_native_providers(),
        racio_world=template.racio_world,
        emocio_world=template.emocio_world,
        instinkt_world=template.instinkt_world,
        historical_bundles=[],
        historical_emocio_signals=[],
        historical_instinkt_signals=[],
    )


def _run_arm_cycle(
    *,
    runtime: _ArmRuntime,
    case_id: str,
    cycle_index: int,
    template: ReiNativeCycleRequest,
    scene: SceneEvent,
    source_prompt: str,
    outcome: OutcomeRecord | None,
) -> object:
    request = template.model_copy(
        update={
            "run_id": f"c7-person-{case_id}-{runtime.spec.arm_id}-{cycle_index:02d}",
            "ego_id": runtime.ego_id,
            "scene": scene,
            "racio_world": runtime.racio_world,
            "emocio_world": runtime.emocio_world,
            "instinkt_world": runtime.instinkt_world,
            "body_state": template.body_state,
            "character": runtime.character,
            "acceptance_state": build_matrix_acceptance_state("accepting"),
            "outcome": outcome,
            "historical_bundles": tuple(runtime.historical_bundles),
            "historical_emocio_signals": tuple(
                runtime.historical_emocio_signals
            ),
            "historical_instinkt_signals": tuple(
                runtime.historical_instinkt_signals
            ),
            "symbolic_and_language_cues": (
                source_prompt,
                *(template.symbolic_and_language_cues or ()),
            ),
            "started_at": template.started_at + timedelta(seconds=cycle_index),
        }
    )
    result = ReiNativeEngine(
        artifact_store=runtime.artifact_store,
        ego_trace_store=runtime.trace_store,
        providers=runtime.providers,
        clock=DeterministicExecutionClock(request.started_at),
    ).run_cycle(request)

    racio_update = RacioWorldUpdater().update(
        runtime.racio_world,
        result.ego_measure,
        result.native_bundle,
        result.narrative,
    )
    visual_signal = _materialize_visual_signal(
        result=result,
        artifact_store=runtime.artifact_store,
        evaluation_seed=cycle_index,
    )
    emocio_update = EmocioWorldUpdater().update(
        runtime.emocio_world,
        result.ego_measure,
        result.native_bundle,
        visual_signal,
        runtime.artifact_store,
    )
    selected_rollout = next(
        item
        for item in result.instinkt_execution.rollouts
        if item.rollout_id == result.native_bundle.instinkt.decisive_rollout_id
    )
    body_signal = InstinktLongitudinalBodySignal.create(
        measure=result.ego_measure,
        bundle=result.native_bundle,
        rollout=selected_rollout,
    )
    instinkt_update = InstinktWorldUpdater().update(
        runtime.instinkt_world,
        result.ego_measure,
        result.native_bundle,
        body_signal,
    )
    runtime.racio_world = racio_update.updated_world
    runtime.emocio_world = emocio_update.updated_world
    runtime.instinkt_world = instinkt_update.updated_world
    runtime.historical_bundles.append(result.native_bundle)
    runtime.historical_emocio_signals.append(visual_signal)
    runtime.historical_instinkt_signals.append(body_signal)
    return result


def _run_probe(
    *,
    case_id: str,
    world_arm_id: str,
    character_arm: PersonCausalityArmSpec,
    template: ReiNativeCycleRequest,
    scene: SceneEvent,
    source_prompt: str,
    racio_world: RacioWorld,
    emocio_world: EmocioWorld,
    instinkt_world: InstinktWorld,
) -> object:
    character = parse_character_profile(
        character_arm.profile_id,
        character_id=(
            f"c7_probe_{case_id}_{world_arm_id}_{character_arm.arm_id}"
        ),
    )
    request = template.model_copy(
        update={
            "run_id": f"c7-probe-{case_id}-{world_arm_id}-{character_arm.arm_id}",
            "ego_id": f"c7-probe-ego-{case_id}-{world_arm_id}-{character_arm.arm_id}",
            "scene": scene,
            "racio_world": racio_world,
            "emocio_world": emocio_world,
            "instinkt_world": instinkt_world,
            "body_state": template.body_state,
            "character": character,
            "acceptance_state": build_matrix_acceptance_state("accepting"),
            "outcome": None,
            "historical_bundles": (),
            "historical_emocio_signals": (),
            "historical_instinkt_signals": (),
            "symbolic_and_language_cues": (
                source_prompt,
                *(template.symbolic_and_language_cues or ()),
            ),
            "started_at": template.started_at + timedelta(seconds=20),
        }
    )
    return ReiNativeEngine(
        artifact_store=_InMemoryEvaluationArtifactStore(),
        ego_trace_store=InMemoryEgoTraceStore(),
        providers=build_deterministic_native_providers(),
        clock=DeterministicExecutionClock(request.started_at),
    ).run_cycle(request)


def _case_specs() -> tuple[PersonCausalityCaseSpec, ...]:
    def arm(arm_id: str, profile_id: CharacterProfileId, case_id: str):
        return PersonCausalityArmSpec(
            arm_id=arm_id,
            profile_id=profile_id,
            character_id=f"c7_character_{case_id}_{arm_id}",
        )

    cases = (
        ("positive_r_vs_e", "positive", "R>E>I", "E>R>I"),
        ("positive_r_vs_i", "positive", "R>E>I", "I>R>E"),
        ("equal_action_e_vs_i", "equal_action", "E>R>I", "I>R>E"),
        ("identity_sham_r_top", "identity_sham", "R>E>I", "R>E>I"),
    )
    return tuple(
        PersonCausalityCaseSpec(
            case_id=case_id,
            control_kind=control_kind,
            arms=(
                arm("a", first_profile, case_id),
                arm("b", second_profile, case_id),
            ),
        )
        for case_id, control_kind, first_profile, second_profile in cases
    )


def _evaluate_case(
    *,
    case: PersonCausalityCaseSpec,
    template: ReiNativeCycleRequest,
    source_sequence: object,
    scenario: object,
) -> PersonCausalityCaseResult:
    runtimes = tuple(
        _new_arm(case=case, arm=arm, template=template) for arm in case.arms
    )
    initial_results = tuple(
        _run_arm_cycle(
            runtime=runtime,
            case_id=case.case_id,
            cycle_index=0,
            template=template,
            scene=scenario.steps[0].scene,
            source_prompt=source_sequence.steps[0],
            outcome=None,
        )
        for runtime in runtimes
    )
    transitions = tuple(
        SimulatorOutcomeTransition.create(
            resultant=result.behavior_resultant,
            target_event_id=scenario.steps[1].scene.event_id,
            recorded_at=template.started_at + timedelta(seconds=1),
        )
        for result in initial_results
    )
    cycle1_results = tuple(
        _run_arm_cycle(
            runtime=runtime,
            case_id=case.case_id,
            cycle_index=1,
            template=template,
            scene=scenario.steps[1].scene,
            source_prompt=source_sequence.steps[1],
            outcome=transition.simulator_outcome,
        )
        for runtime, transition in zip(runtimes, transitions, strict=True)
    )
    world_semantics = tuple(
        WorldSemanticFingerprint.create(
            racio_world=runtime.racio_world,
            emocio_world=runtime.emocio_world,
            instinkt_world=runtime.instinkt_world,
        )
        for runtime in runtimes
    )
    probe_results = tuple(
        tuple(
            _run_probe(
                case_id=case.case_id,
                world_arm_id=runtime.spec.arm_id,
                character_arm=character_arm,
                template=template,
                scene=scenario.steps[2].scene,
                source_prompt=source_sequence.steps[2],
                racio_world=runtime.racio_world,
                emocio_world=runtime.emocio_world,
                instinkt_world=runtime.instinkt_world,
            )
            for character_arm in case.arms
        )
        for runtime in runtimes
    )
    return PersonCausalityCaseResult.create(
        case=case,
        initial_condition_hashes=tuple(
            _initial_condition_hash(item.request) for item in initial_results
        ),
        initial_native_surface_hashes=tuple(
            _surface_hash(item) for item in initial_results
        ),
        initial_behavior_statuses=tuple(
            item.behavior_resultant.status for item in initial_results
        ),
        initial_behavior_option_ids=tuple(
            item.behavior_resultant.option_id for item in initial_results
        ),
        transitions=transitions,
        cycle1_native_semantics=tuple(
            NativeSemanticFingerprint.create(item) for item in cycle1_results
        ),
        world_semantics=world_semantics,
        probe_native_surface_hashes=tuple(
            tuple(_surface_hash(item) for item in row) for row in probe_results
        ),
        probe_native_semantics=tuple(
            tuple(NativeSemanticFingerprint.create(item) for item in row)
            for row in probe_results
        ),
    )


def evaluate_person_causality(
    *,
    corpus_path: str | Path = DEFAULT_PERSON_CAUSALITY_CORPUS_PATH,
    template_fixture_path: str | Path = DEFAULT_PERSON_CAUSALITY_TEMPLATE_PATH,
) -> PersonCausalityEvaluationReport:
    """Run the four-case bounded C7 person-causality slice."""

    corpus_bytes = _read_bounded(
        corpus_path,
        maximum_bytes=MAX_LONGITUDINAL_CORPUS_BYTES,
        label="C7 person-causality source corpus",
    )
    corpus = parse_longitudinal_corpus(corpus_bytes)
    template_bytes = _read_bounded(
        template_fixture_path,
        maximum_bytes=MAX_LONGITUDINAL_TEMPLATE_BYTES,
        label="C7 person-causality template fixture",
    )
    template = ReiNativeCycleRequest.model_validate_json(template_bytes)
    source_sequence = next(
        (item for item in corpus.sequences if item.sequence_id == SOURCE_SEQUENCE_ID),
        None,
    )
    if source_sequence is None:
        raise ValueError(
            f"C7 source sequence {SOURCE_SEQUENCE_ID!r} is absent from the corpus"
        )
    if (
        len(source_sequence.steps) < 3
        or source_sequence.reverse_option_order_until_step is None
        or source_sequence.reverse_option_order_until_step < 3
    ):
        raise ValueError(
            "C7 source sequence must expose three bounded reversed-option steps"
        )
    scenario = _build_scenario(template, source_sequence)
    cases = tuple(
        _evaluate_case(
            case=case,
            template=template,
            source_sequence=source_sequence,
            scenario=scenario,
        )
        for case in _case_specs()
    )
    return PersonCausalityEvaluationReport.create(
        source_corpus_sha256=hashlib.sha256(corpus_bytes).hexdigest(),
        template_request_hash=template.content_hash(),
        shared_scenario_id=scenario.scenario_id,
        shared_scenario_hash=scenario.scenario_hash,
        cases=cases,
    )


__all__ = [
    "DEFAULT_PERSON_CAUSALITY_CORPUS_PATH",
    "DEFAULT_PERSON_CAUSALITY_TEMPLATE_PATH",
    "NativeSemanticFingerprint",
    "ObservableAction",
    "PersonCausalityCaseResult",
    "PersonCausalityEvaluationReport",
    "SimulatorOutcomeTransition",
    "WorldSemanticFingerprint",
    "evaluate_person_causality",
]
