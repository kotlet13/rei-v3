"""Provider-free Racio interpretation over sanitized observable views only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import ClassVar, Literal, Protocol, runtime_checkable

from ..ids import sha256_hex
from ..models.communication import (
    ManifestationObservation,
    RacioInterpretation,
    RacioInterpreterRequest,
)


def _request_observations(
    request: RacioInterpreterRequest,
) -> tuple[ManifestationObservation, ...]:
    return tuple(
        observation
        for view in request.observable_views
        for observation in view.observations
    )


def _inferred_action(
    observations: tuple[ManifestationObservation, ...],
) -> str | None:
    for observation in observations:
        if observation.signal_name not in {"motor_urge", "raw_urge"}:
            continue
        assert observation.canonical_json_value is not None
        value = json.loads(observation.canonical_json_value)
        if isinstance(value, str) and value.startswith("structured_tendency:"):
            action = value.removeprefix("structured_tendency:")
            return action or None
    return None


def _build_interpretation(
    *,
    request: RacioInterpreterRequest,
    observations: tuple[ManifestationObservation, ...],
    inferred_option_id: str | None,
    inferred_action_tendency: str | None,
    inferred_motive: str,
    confidence: float,
    alternative_hypotheses: tuple[str, ...],
    interpreter_id: str,
    interpreter_revision: str,
    interpreter_policy: str,
) -> RacioInterpretation:
    status = "interpreted_b9" if observations else "omitted_b9"
    if not observations:
        inferred_option_id = None
        inferred_action_tendency = None
        inferred_motive = "no_consciously_visible_structured_signal"
        confidence = 0.0
        alternative_hypotheses = ()
    return RacioInterpretation.create_b9(
        request=request,
        status=status,
        observations=observations,
        inferred_option_id=inferred_option_id,
        inferred_action_tendency=inferred_action_tendency,
        inferred_motive=inferred_motive,
        confidence=confidence,
        alternative_hypotheses=alternative_hypotheses,
        interpreter_id=interpreter_id,
        interpreter_revision=interpreter_revision,
        interpreter_policy=interpreter_policy,
    )


@runtime_checkable
class RacioInterpreter(Protocol):
    """Domain protocol whose sole semantic input is a sanitized B9 request."""

    @property
    def interpreter_id(self) -> str: ...

    @property
    def interpreter_revision(self) -> str: ...

    @property
    def interpreter_policy(self) -> str: ...

    def interpret(self, request: RacioInterpreterRequest) -> RacioInterpretation: ...


class ReplaySafeRacioInterpreter(RacioInterpreter, Protocol):
    """A pure adapter that explicitly permits deterministic re-execution."""

    replay_safe: ClassVar[Literal[True]]


@dataclass(frozen=True, slots=True)
class DeterministicRacioInterpreter:
    """Conservative record-only default; never infer from AcceptanceState."""

    interpreter_id: str = "b9_deterministic_racio_interpreter"
    interpreter_revision: str = "1"
    interpreter_policy: str = "b9_conservative_observable_signals_v1"
    replay_safe: ClassVar[Literal[True]] = True

    def interpret(self, request: RacioInterpreterRequest) -> RacioInterpretation:
        observations = _request_observations(request)
        action = _inferred_action(observations)
        motive = ";".join(item.content for item in observations)
        return _build_interpretation(
            request=request,
            observations=observations,
            inferred_option_id=None,
            inferred_action_tendency=action,
            inferred_motive=motive,
            confidence=(1.0 if action is not None else 0.5),
            alternative_hypotheses=tuple(
                f"public_option:{option_id}" for option_id in request.allowed_option_ids
            ),
            interpreter_id=self.interpreter_id,
            interpreter_revision=self.interpreter_revision,
            interpreter_policy=self.interpreter_policy,
        )


@dataclass(frozen=True, slots=True)
class ScriptedRacioInterpreter:
    """Provider-free record-only adapter for explicit wrong/partial scenarios."""

    scripted_option_id: str | None
    scripted_action_tendency: str | None
    scripted_motive: str
    scripted_confidence: float
    scripted_alternatives: tuple[str, ...] = ()
    observation_limit: int | None = None
    interpreter_id: str = "b9_scripted_racio_interpreter"
    interpreter_revision: str = "1"
    replay_safe: ClassVar[Literal[True]] = True

    @property
    def interpreter_policy(self) -> str:
        config_hash = sha256_hex(
            {
                "scripted_option_id": self.scripted_option_id,
                "scripted_action_tendency": self.scripted_action_tendency,
                "scripted_motive": self.scripted_motive,
                "scripted_confidence": self.scripted_confidence,
                "scripted_alternatives": self.scripted_alternatives,
                "observation_limit": self.observation_limit,
            }
        )
        return f"b9_scripted_provider_free_implementation_hypothesis_v1:{config_hash}"

    def interpret(self, request: RacioInterpreterRequest) -> RacioInterpretation:
        if (
            self.scripted_option_id is not None
            and self.scripted_option_id not in request.allowed_option_ids
        ):
            raise ValueError("Scripted interpretation option is outside public scope")
        observations = _request_observations(request)
        if self.observation_limit is not None:
            if self.observation_limit < 0:
                raise ValueError("Scripted observation_limit cannot be negative")
            observations = observations[: self.observation_limit]
        return _build_interpretation(
            request=request,
            observations=observations,
            inferred_option_id=self.scripted_option_id,
            inferred_action_tendency=self.scripted_action_tendency,
            inferred_motive=self.scripted_motive,
            confidence=self.scripted_confidence,
            alternative_hypotheses=self.scripted_alternatives,
            interpreter_id=self.interpreter_id,
            interpreter_revision=self.interpreter_revision,
            interpreter_policy=self.interpreter_policy,
        )


def validate_interpretation_attribution(
    *,
    interpreter: RacioInterpreter,
    request: RacioInterpreterRequest,
    interpretation: RacioInterpretation,
) -> RacioInterpretation:
    """Close one returned artifact to the adapter without executing it again."""

    interpretation.validate_against_request(request)
    if (
        interpretation.interpreter_id != interpreter.interpreter_id
        or interpretation.interpreter_revision != interpreter.interpreter_revision
        or interpretation.interpreter_policy != interpreter.interpreter_policy
    ):
        raise ValueError("Racio interpretation misattributes its adapter provenance")
    return interpretation


def validate_interpretation_replay(
    *,
    interpreter: ReplaySafeRacioInterpreter,
    request: RacioInterpreterRequest,
    interpretation: RacioInterpretation,
) -> RacioInterpretation:
    """Replay only adapters that explicitly declare pure deterministic execution."""

    validate_interpretation_attribution(
        interpreter=interpreter,
        request=request,
        interpretation=interpretation,
    )
    if getattr(interpreter, "replay_safe", False) is not True:
        raise ValueError("Racio interpreter is not declared safe for deterministic replay")
    if interpreter.interpret(request) != interpretation:
        raise ValueError("Racio interpretation differs from deterministic replay")
    return interpretation


__all__ = [
    "DeterministicRacioInterpreter",
    "RacioInterpreter",
    "ReplaySafeRacioInterpreter",
    "ScriptedRacioInterpreter",
    "validate_interpretation_attribution",
    "validate_interpretation_replay",
]
